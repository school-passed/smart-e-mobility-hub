"""Pure What-if simulation services for SUB-06 (UC-15, UC-16, UC-17).

The service reads an operational state, copies the relevant records into an
immutable snapshot, and returns hypothetical results without ever mutating the
live operational state. Simulation history is stored only in the isolated
sandbox store (Submission 3 ``simulation_sandbox``).
"""

from __future__ import annotations

from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from math import ceil
from threading import RLock
from typing import Any

from shared.state import atomic, get_sandbox_store, point_validity

_SANDBOX_LOCK = RLock()
_WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="what-if")

SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "id": "metro_demand_surge",
        "name": "Peak Student Arrivals · Tăng nhu cầu Metro",
        "description": "Lượng sinh viên đến Ga Metro tăng đột biến vào giờ cao điểm; đánh giá thiếu hụt xe dùng chung.",
    },
    {
        "id": "hub_near_capacity",
        "name": "Full Parking · Hub đầy chỗ hoặc thiếu xe",
        "description": "Bãi đỗ xe đạt giới hạn sức chứa hoặc nhu cầu đặt xe vượt nguồn xe khả dụng tại Hub.",
    },
    {
        "id": "charging_pressure",
        "name": "Charging Surge · Nhu cầu sạc tăng đột biến",
        "description": "Số yêu cầu sạc tăng mạnh vượt số cổng sạc rảnh; đánh giá lượng yêu cầu tồn đọng.",
    },
    {
        "id": "point_failures",
        "name": "Charging-Point Failures · Trụ sạc ngừng hoạt động",
        "description": "Một số cổng sạc bị lỗi/mất khả dụng; đánh giá sụt giảm công suất sạc và lịch bị ảnh hưởng.",
    },
    {
        "id": "vehicle_concentration",
        "name": "Vehicle Concentration · Xe dồn về một Hub",
        "description": "Phương tiện tập trung quá mức tại một Hub gây áp lực bãi đỗ trong khi Hub nguồn thiếu xe.",
    },
)
_BATTERY_PER_TRIP = 8
_BATTERY_PER_CHARGE = 15
_LOW_BATTERY_THRESHOLD = 25


class SimulationInputError(ValueError):
    """Raised when required snapshot data or scenario input is invalid."""


def get_available_scenarios() -> list[dict[str, str]]:
    """Return the five What-if scenarios from Submission 1 & Submission 2."""
    return [dict(scenario) for scenario in SCENARIOS]


@atomic
def get_network_snapshot(
    operational_state: dict[str, Any],
    hub_id: str | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Copy relevant network records and derive read-only summary metrics.

    IMPORTANT: ``operational_state`` and its nested records are NEVER modified.
    """
    if not isinstance(operational_state, dict):
        raise SimulationInputError("Không đọc được dữ liệu vận hành dạng hợp lệ.")

    copied: dict[str, Any] = {}
    sections_present: dict[str, bool] = {}
    for key in (
        "hubs",
        "vehicles",
        "reservations",
        "trips",
        "parking_spaces",
        "parking_reservations",
        "charging_points",
        "charging_requests",
        "shared_charging_requests",
        "charging_schedules",
        "incidents",
        "dispatch_orders",
        "temporary_holds",
    ):
        value = operational_state.get(key, [])
        sections_present[key] = key in operational_state and isinstance(value, list)
        if not isinstance(value, list):
            raise SimulationInputError(f"Dữ liệu {key} chưa đúng định dạng danh sách.")
        copied[key] = deepcopy(value)

    in_transit = {
        vid
        for order in copied["dispatch_orders"]
        if order.get("status") == "TRANSITING"
        for vid in order.get("vehicle_ids", [])
    }
    for v in copied["vehicles"]:
        if v.get("incident_blocked") and v.get("status") == "AVAILABLE":
            v["status"] = "UNAVAILABLE"
        elif v.get("vehicle_id") in in_transit:
            v["status"] = "TRANSITING"

    captured = captured_at or datetime.now().astimezone()
    held_spaces = set()
    for h in copied["temporary_holds"]:
        try:
            exp = datetime.fromisoformat(str(h["expires_at"]))
            cmp_cap = captured if exp.tzinfo else captured.replace(tzinfo=None)
            if exp > cmp_cap:
                held_spaces.add(h["space_id"])
        except (KeyError, TypeError, ValueError):
            continue
    held_spaces.update(
        sid
        for order in copied["dispatch_orders"]
        if order.get("status") == "TRANSITING"
        for sid in order.get("space_ids", [])
    )
    for p in copied["parking_spaces"]:
        if p.get("incident_blocked"):
            p["status"] = "UNAVAILABLE"
        elif p.get("space_id") in held_spaces and p.get("status") == "AVAILABLE":
            p["status"] = "RESERVED"

    for point in copied["charging_points"]:
        val = point_validity(point, captured)
        if val != "VALID":
            point["data_validity"] = val
        elif point.get("incident_blocked"):
            point["status"] = "UNAVAILABLE"

    hubs_by_id = {
        str(hub.get("hub_id")): hub
        for hub in copied["hubs"]
        if isinstance(hub, dict) and hub.get("hub_id") is not None
    }
    if not hubs_by_id:
        raise SimulationInputError("Snapshot chưa có thông tin Hub để mô phỏng.")
    if hub_id is not None and hub_id not in hubs_by_id:
        raise SimulationInputError("Hub được chọn không còn trong dữ liệu snapshot.")

    # Check data completeness / Hub disconnection (UC-16 A1 / TC-SUB06-003)
    selected_hub_obj = hubs_by_id.get(str(hub_id)) if hub_id else None
    hub_disconnected = bool(
        selected_hub_obj and selected_hub_obj.get("data_validity") == "DISCONNECTED"
    )
    completeness_pct = 0 if hub_disconnected else (100 if (copied["hubs"] and copied["vehicles"]) else 0)

    summary = {
        "hub_count": len(hubs_by_id),
        "vehicle_count": len(copied["vehicles"]),
        "parking_space_count": len(copied["parking_spaces"]),
        "charging_point_count": len(copied["charging_points"]),
        "completeness_pct": completeness_pct,
    }
    return {
        "captured_at": (captured_at or datetime.now()).isoformat(timespec="seconds"),
        "selected_hub_id": hub_id,
        "data_complete": bool(copied["hubs"] and copied["vehicles"] and not hub_disconnected),
        "sections_present": sections_present,
        "summary": summary,
        "records": copied,
    }


def validate_scenario_parameters(
    scenario_id: str,
    parameters: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> list[str]:
    """Return human-readable validation errors; an empty list means valid."""
    errors: list[str] = []
    valid_ids = {scenario["id"] for scenario in SCENARIOS}
    if scenario_id not in valid_ids:
        return ["Kịch bản không được hỗ trợ."]
    if not isinstance(parameters, dict):
        return ["Tham số đầu vào không hợp lệ."]

    if snapshot is not None:
        if not snapshot.get("data_complete"):
            errors.append(
                "Snapshot thiếu dữ liệu bắt buộc hoặc Hub đang mất kết nối cảm biến (DISCONNECTED) — UC-16 A1."
            )
        records = snapshot.get("records", {})
        selected_hub = snapshot.get("selected_hub_id")
        selected_record = None
        if not selected_hub:
            errors.append("Cần chọn Hub trước khi chạy kịch bản.")
        else:
            selected_record = next(
                (hub for hub in records.get("hubs", []) if hub.get("hub_id") == selected_hub),
                None,
            )
            if selected_record is None:
                errors.append("Hub đã chọn không có trong snapshot.")
            elif scenario_id == "metro_demand_surge" and "metro" not in str(selected_record.get("name", "")).lower():
                errors.append("Kịch bản này cần chọn Metro Hub.")

        required_sections = {
            "metro_demand_surge": ("hubs", "vehicles"),
            "hub_near_capacity": ("hubs", "vehicles", "parking_spaces", "reservations"),
            "vehicle_concentration": ("hubs", "vehicles", "parking_spaces"),
            "point_failures": ("hubs", "charging_points", "charging_requests"),
            "charging_pressure": ("hubs", "charging_points", "charging_requests"),
        }[scenario_id]
        for section in required_sections:
            if not snapshot.get("sections_present", {}).get(section, False):
                errors.append(f"Snapshot thiếu dữ liệu {section} cần cho kịch bản.")

        if (
            selected_hub
            and scenario_id in ("charging_pressure", "point_failures")
            and any(p.get("data_validity", "VALID") != "VALID" for p in _hub_points(snapshot, selected_hub))
        ):
            errors.append("Dữ liệu trụ sạc bị trễ hoặc mất kết nối. Hãy cập nhật rồi chụp snapshot mới.")

        selected_vehicles = _hub_vehicles(snapshot, selected_hub) if selected_hub else []
        if selected_record is not None and not selected_vehicles:
            errors.append("Hub đã chọn chưa có dữ liệu xe để mô phỏng.")

        if selected_record is not None and scenario_id == "hub_near_capacity":
            selected_spaces = _hub_spaces(snapshot, selected_hub)
            if not selected_spaces:
                errors.append("Hub đã chọn chưa có dữ liệu chỗ đỗ để xác định mức sử dụng.")
            elif not any(space.get("status") != "UNAVAILABLE" for space in selected_spaces):
                errors.append("Hub đã chọn không còn chỗ đỗ khả dụng để mô phỏng capacity.")
            raw_parking_capacity = selected_record.get("parking_capacity", 0)
            parking_capacity = len(selected_spaces) or (
                raw_parking_capacity
                if isinstance(raw_parking_capacity, int) and not isinstance(raw_parking_capacity, bool)
                else 0
            )
            if parking_capacity <= 0:
                errors.append("Hub đã chọn chưa có dữ liệu capacity chỗ đỗ để mô phỏng.")
            raw_reservation_capacity = selected_record.get("reservation_capacity", 0)
            reservation_capacity = (
                raw_reservation_capacity
                if isinstance(raw_reservation_capacity, int) and not isinstance(raw_reservation_capacity, bool)
                else 0
            )
            if reservation_capacity <= 0:
                errors.append("Hub đã chọn chưa có dữ liệu capacity reservation để mô phỏng.")

        if selected_record is not None and scenario_id in ("charging_pressure", "point_failures"):
            if not _hub_points(snapshot, selected_hub):
                errors.append("Hub đã chọn chưa có dữ liệu trụ sạc để mô phỏng.")

        if selected_vehicles and any(
            isinstance(vehicle.get("battery_level"), bool)
            or not isinstance(vehicle.get("battery_level"), (int, float))
            for vehicle in selected_vehicles
        ):
            errors.append("Snapshot thiếu mức pin hợp lệ của một hoặc nhiều xe tại Hub.")

    if scenario_id == "metro_demand_surge":
        errors.extend(_require_int(parameters, "base_demand", "Nhu cầu nền", 1, 500))
        errors.extend(_require_int(parameters, "increase_percent", "Tỷ lệ tăng nhu cầu", 1, 300))
    elif scenario_id == "hub_near_capacity":
        errors.extend(_require_int(parameters, "additional_vehicle_demand", "Nhu cầu xe tăng thêm", 0, 500))
        errors.extend(_require_int(parameters, "additional_parking_occupancy", "Số chỗ đỗ bị chiếm thêm", 0, 500))
    elif scenario_id == "vehicle_concentration":
        errors.extend(_require_int(parameters, "moved", "Số xe tập trung", 1, 500))
        if snapshot:
            source = parameters.get("source_hub_id")
            pool = sum(v.get("status") == "AVAILABLE" for v in _hub_vehicles(snapshot, source)) if source else 0
            if (
                not source
                or source == snapshot.get("selected_hub_id")
                or not pool
                or (isinstance(parameters.get("moved"), int) and parameters["moved"] > pool)
            ):
                errors.append("Chọn Hub nguồn khác và số xe tập trung không vượt quá số xe khả dụng tại nguồn.")
    elif scenario_id in ("charging_pressure", "point_failures"):
        errors.extend(_require_int(parameters, "additional_requests", "Số yêu cầu sạc tăng thêm", 0, 500))
        min_failed = 1 if scenario_id == "point_failures" else 0
        errors.extend(_require_int(parameters, "failed_points", "Số trụ sạc giả định bị lỗi", min_failed, 500))
        if snapshot is not None:
            available = _available_charging_points(snapshot)
            failed = parameters.get("failed_points")
            if isinstance(failed, int) and not isinstance(failed, bool) and failed > available:
                errors.append(f"Số trụ sạc lỗi không thể vượt quá {available} trụ đang khả dụng tại Hub.")

    return errors


def _prepare_session(scenario_id, parameters, snapshot, operator_id):
    errors = validate_scenario_parameters(scenario_id, parameters, snapshot)
    if errors:
        raise SimulationInputError(" ".join(errors))
    with _SANDBOX_LOCK:
        sandbox = get_sandbox_store()
        number = sandbox["next_session_number"]
        sandbox["next_session_number"] = number + 1
        session = {
            "session_id": f"SIM-{number:04d}",
            "operator_id": operator_id,
            "scenario_id": scenario_id,
            "hub_id": snapshot["selected_hub_id"],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "RUNNING",
        }
        sandbox["sessions"].append(session)
        return sandbox, session


def _require_running(session):
    with _SANDBOX_LOCK:
        if session["status"] == "CANCELLED":
            raise CancelledError()


def _calculate_result(session, scenario_id, parameters, snapshot):
    _require_running(session)
    result: dict[str, Any] = {
        "session_id": session["session_id"],
        "scenario_id": scenario_id,
        "scenario_name": next(s["name"] for s in SCENARIOS if s["id"] == scenario_id),
        "hub_id": snapshot.get("selected_hub_id"),
        "snapshot_time": snapshot["captured_at"],
        "time_window": str(parameters.get("time_window", "Chưa chọn")),
        "parameters": deepcopy(parameters),
        "snapshot": deepcopy(snapshot),
        "metrics": [],
        "issues": [],
        "recommendations": [],
        "infeasibility_reason": None,
        "status": "completed",
    }

    if scenario_id == "metro_demand_surge":
        _simulate_metro_surge(result)
    elif scenario_id == "hub_near_capacity":
        _simulate_hub_capacity(result)
    elif scenario_id == "vehicle_concentration":
        _simulate_vehicle_concentration(result)
    elif scenario_id in ("charging_pressure", "point_failures"):
        _simulate_charging_pressure(result)

    _require_running(session)
    result["issues"] = evaluate_simulation_impact(result)
    _require_running(session)
    result["recommendations"] = generate_recommendations(result)
    has_real_problem = any(i.get("code") != "no_issue_detected" for i in result["issues"])
    if has_real_problem and not result["recommendations"]:
        result["infeasibility_reason"] = (
            "Các Hub lân cận trong snapshot hiện không còn đủ nguồn xe dự phòng, chỗ đỗ trống hoặc trụ sạc rảnh để điều tiết (UC-17 A4)."
        )

    return result


def _execute_session(sandbox, session, scenario_id, parameters, snapshot):
    try:
        result = _calculate_result(session, scenario_id, parameters, snapshot)
        with _SANDBOX_LOCK:
            _require_running(session)
            sandbox["results"].append(deepcopy({k: v for k, v in result.items() if k != "snapshot"}))
            del sandbox["results"][:-30]
            session["status"] = "COMPLETED"
        return result
    except Exception:
        with _SANDBOX_LOCK:
            if session["status"] == "RUNNING":
                session["status"] = "FAILED"
        raise


def run_simulation(
    scenario_id: str,
    parameters: dict[str, Any],
    snapshot: dict[str, Any],
    operator_id: str = "Operator",
) -> dict[str, Any]:
    """Run one scenario against a snapshot and record the result in the sandbox."""
    sandbox, session = _prepare_session(scenario_id, parameters, snapshot, operator_id)
    return _execute_session(sandbox, session, scenario_id, parameters, snapshot)


def start_simulation(
    scenario_id: str,
    parameters: dict[str, Any],
    snapshot: dict[str, Any],
    operator_id: str = "Operator",
) -> tuple[str, Future]:
    """Run in the background while the Operator can navigate or cancel."""
    sandbox, session = _prepare_session(scenario_id, parameters, snapshot, operator_id)
    future = _WORKERS.submit(
        _execute_session, sandbox, session, scenario_id, deepcopy(parameters), deepcopy(snapshot)
    )
    return session["session_id"], future


def cancel_simulation_session(session_id: str) -> bool:
    """Stop a pending result from being committed to the isolated sandbox."""
    with _SANDBOX_LOCK:
        for session in get_sandbox_store()["sessions"]:
            if session["session_id"] == session_id and session["status"] == "RUNNING":
                session["status"] = "CANCELLED"
                return True
    return False


def get_sandbox_history(limit: int = 10) -> list[dict[str, Any]]:
    with _SANDBOX_LOCK:
        return deepcopy(list(reversed(get_sandbox_store()["results"][-limit:])))


def evaluate_simulation_impact(result: dict[str, Any]) -> list[dict[str, str]]:
    """Classify simulated capacity problems without changing live resources (UC-17)."""
    issues: list[dict[str, str]] = []
    metrics = result.get("metrics", [])
    by_id = {m.get("id"): m for m in metrics}

    for metric in metrics:
        metric_id = metric.get("id")
        before = metric.get("before")
        after = metric.get("after")

        if metric_id == "vehicle_shortage" and isinstance(after, (int, float)) and after > 0:
            issues.append(
                {
                    "code": "vehicle_shortage",
                    "severity": "high",
                    "title": "Nguy cơ thiếu hụt xe dùng chung",
                    "detail": f"Ước tính thiếu {int(after)} xe trong khung giờ mô phỏng do nhu cầu vượt nguồn xe AVAILABLE.",
                }
            )
        elif metric_id in {"parking_utilization", "reservation_utilization"} and isinstance(after, (int, float)):
            target_label = "bãi đỗ xe" if metric_id == "parking_utilization" else "slot đặt xe trước"
            overflow = int(by_id.get("rejected_parking", {}).get("after", 0)) if metric_id == "parking_utilization" else 0
            if after >= 100:
                extra = f" Ước tính khoảng {overflow} lượt xe đến sau bị từ chối gửi." if overflow > 0 else ""
                issues.append(
                    {
                        "code": f"{metric_id}_full",
                        "severity": "high",
                        "title": f"Cạn kiệt không gian {target_label}",
                        "detail": f"Mức sử dụng {target_label} chạm/vượt giới hạn ({after:.0f}%).{extra}",
                    }
                )
            elif after >= 80:
                issues.append(
                    {
                        "code": f"{metric_id}_near_capacity",
                        "severity": "medium",
                        "title": f"Áp lực {target_label} (Near Capacity)",
                        "detail": f"Mức sử dụng sau mô phỏng đạt {after:.0f}% (vượt ngưỡng cảnh báo 80%).",
                    }
                )
        elif metric_id == "unserved_charging_requests" and isinstance(after, (int, float)) and after > 0:
            issues.append(
                {
                    "code": "charging_shortage",
                    "severity": "high",
                    "title": "Quá tải điểm sạc — Tồn đọng yêu cầu sạc",
                    "detail": f"Còn {int(after)} yêu cầu sạc chưa có trụ khả dụng đáp ứng trong khung giờ.",
                }
            )
        elif (
            metric_id == "available_charging_points"
            and isinstance(before, (int, float))
            and isinstance(after, (int, float))
            and after < before
        ):
            kw_m = by_id.get("effective_charging_kw", {})
            kw_note = (
                f" (công suất khả dụng giảm từ {kw_m.get('before', 0):g} kW xuống {kw_m.get('after', 0):g} kW)"
                if kw_m
                else ""
            )
            sev = "high" if after == 0 else "medium"
            issues.append(
                {
                    "code": "charger_failure_impact",
                    "severity": sev,
                    "title": "Sụt giảm năng lực sạc do sự cố trụ sạc",
                    "detail": f"Số trụ sạc sẵn sàng giảm còn {int(after)}/{int(before)} trụ{kw_note}.",
                }
            )
        elif metric_id == "source_stock" and isinstance(after, (int, float)):
            moved = int(result.get("parameters", {}).get("moved", 0))
            src = result.get("parameters", {}).get("source_hub_id", "Hub nguồn")
            tgt = result.get("hub_id", "Hub đích")
            sev = "high" if after <= 1 else "medium"
            issues.append(
                {
                    "code": "vehicle_concentration_imbalance",
                    "severity": sev,
                    "title": "Mất cân bằng phân bố đội xe giữa các Hub",
                    "detail": f"{src} chỉ còn {int(after)} xe sẵn sàng sau khi {moved} xe dồn về {tgt}.",
                }
            )
        elif metric_id == "low_battery_vehicles" and isinstance(after, (int, float)) and after > 0:
            issues.append(
                {
                    "code": "low_battery_risk",
                    "severity": "medium",
                    "title": "Gia tăng số xe chạm ngưỡng pin thấp",
                    "detail": f"Dự báo có {int(after)} xe xuống dưới {_LOW_BATTERY_THRESHOLD}% pin cần ưu tiên sạc.",
                }
            )

    vehicle_shortage = int(by_id.get("vehicle_shortage", {}).get("after", 0) or 0)
    if vehicle_shortage > 0:
        donor = _find_vehicle_donor(
            result.get("snapshot", {}).get("records", {}),
            result.get("hub_id"),
            vehicle_shortage,
        )
        if donor:
            issues.append(
                {
                    "code": "network_imbalance",
                    "severity": "medium",
                    "title": "Có thể cân bằng từ Hub dư nguồn xe",
                    "detail": f"Hub đang thiếu {vehicle_shortage} xe trong khi {donor['name']} còn {donor['available']} xe khả dụng.",
                }
            )

    if not issues:
        issues.append(
            {
                "code": "no_issue_detected",
                "severity": "low",
                "title": "Mạng lưới vẫn đáp ứng tốt nhu cầu",
                "detail": "Theo snapshot và giả định đã nhập, chưa phát hiện điểm nghẽn vượt ngưỡng.",
            }
        )
    return issues


def generate_recommendations(result: dict[str, Any]) -> list[dict[str, str]]:
    """Suggest feasible, reviewable operational actions; never execute them (UC-17)."""
    if any(issue.get("code") == "no_issue_detected" for issue in result.get("issues", [])):
        return [
            {
                "action": "Tiếp tục giám sát bình thường trên Network Dashboard.",
                "feasibility": "Ổn định",
                "reason": "Các chỉ số xe, bãi đỗ và cổng sạc đều nằm trong ngưỡng an toàn.",
                "nav_target": "network",
                "nav_label": "Tổng quan mạng lưới →",
            }
        ]

    records = result.get("snapshot", {}).get("records", {})
    selected_hub_id = result.get("hub_id")
    recommendations: list[dict[str, str]] = []
    codes = {issue.get("code") for issue in result.get("issues", [])}
    metrics_by_id = {m.get("id"): m for m in result.get("metrics", [])}

    if "vehicle_shortage" in codes:
        shortage = int(metrics_by_id.get("vehicle_shortage", {}).get("after", 1) or 1)
        donor = _find_vehicle_donor(records, selected_hub_id, shortage)
        if donor:
            recommendations.append(
                {
                    "action": f"Điều chuyển khoảng {shortage} xe khả dụng từ {donor['name']} sang Hub đang thiếu.",
                    "feasibility": f"Khả thi · Nguồn có {donor['available']} xe",
                    "reason": f"{donor['name']} còn dư xe sau khi giữ dự phòng tại chỗ; cần Operator xác nhận lệnh tại UC-13.",
                    "nav_target": "dispatch",
                    "nav_label": "Điều chuyển xe →",
                }
            )

    if "vehicle_concentration_imbalance" in codes:
        source_id = result.get("parameters", {}).get("source_hub_id")
        moved = int(result.get("parameters", {}).get("moved", 1) or 1)
        source_spaces = sum(
            1 for p in records.get("parking_spaces", [])
            if p.get("hub_id") == source_id and p.get("status") == "AVAILABLE"
        )
        hub_names = {h.get("hub_id"): h.get("name", h.get("hub_id")) for h in records.get("hubs", [])}
        if source_id and source_spaces >= 1:
            rebalance_qty = min(moved, source_spaces)
            recommendations.append(
                {
                    "action": f"Tổ chức điều chuyển cân bằng {rebalance_qty} xe từ {hub_names.get(selected_hub_id, selected_hub_id)} về lại {hub_names.get(source_id, source_id)}.",
                    "feasibility": f"Khả thi · {source_spaces} ô đỗ trống tại đích",
                    "reason": "Giảm áp lực bãi đỗ tại Hub tập trung và khôi phục nguồn xe dự phòng cho Hub xuất phát.",
                    "nav_target": "dispatch",
                    "nav_label": "Điều chuyển xe →",
                }
            )
        else:
            alt_park = _find_parking_alternative(records, selected_hub_id, 1)
            if alt_park:
                recommendations.append(
                    {
                        "action": f"Phân tán bớt xe tập trung sang {alt_park['name']}.",
                        "feasibility": f"Còn {alt_park['available']} ô trống",
                        "reason": "Hub xuất phát đã hết chỗ nhận, chuyển sang trạm lân cận còn sức chứa.",
                        "nav_target": "dispatch",
                        "nav_label": "Điều chuyển xe →",
                    }
                )

    if any(code and code.startswith("parking_utilization") for code in codes):
        required_spaces = max(1, int(result.get("parameters", {}).get("additional_parking_occupancy", 1) or 1))
        alternate = _find_parking_alternative(records, selected_hub_id, min(required_spaces, 1))
        if alternate:
            recommendations.append(
                {
                    "action": f"Điều hướng nhu cầu gửi xe cá nhân sang {alternate['name']} và điều chuyển bớt xe dùng chung khỏi bãi.",
                    "feasibility": f"Còn {alternate['available']} chỗ đỗ tại {alternate['name']}",
                    "reason": "Tránh ùn tắc lối ra vào khi bãi đỗ chạm ngưỡng giới hạn sức chứa.",
                    "nav_target": "dispatch",
                    "nav_label": "Điều chuyển xe →",
                }
            )

    if any(code and code.startswith("reservation_utilization") for code in codes):
        requested_slots = max(1, int(result.get("parameters", {}).get("additional_vehicle_demand", 1) or 1))
        alternate = _find_reservation_alternative(records, selected_hub_id, min(requested_slots, 1))
        if alternate:
            recommendations.append(
                {
                    "action": f"Khuyến nghị sinh viên đặt slot xe tại {alternate['name']}.",
                    "feasibility": f"Còn {alternate['available']} slot đặt trước",
                    "reason": "Giảm tỷ lệ từ chối đặt chỗ khi slot giữ trước tại Hub vượt ngưỡng.",
                    "nav_target": "network",
                    "nav_label": "Xem mạng lưới →",
                }
            )

    if "charging_shortage" in codes or "charger_failure_impact" in codes:
        unserved = max(1, int(metrics_by_id.get("unserved_charging_requests", {}).get("after", 1) or 1))
        alternate = _find_charging_alternative(records, selected_hub_id, 1)
        if alternate:
            recommendations.append(
                {
                    "action": f"Rà soát tái lập lịch sạc ưu tiên (UC-10) hoặc điều hướng nhu cầu sạc sang {alternate['name']}.",
                    "feasibility": f"{alternate['name']} còn {alternate['available']} trụ khả dụng",
                    "reason": f"Cân đối phụ tải cho {unserved} nhu cầu sạc và xử lý các lịch bị ảnh hưởng bởi trụ lỗi.",
                    "nav_target": "charging",
                    "nav_label": "Lập lịch sạc →",
                }
            )
        elif "charger_failure_impact" in codes:
            local_left = int(metrics_by_id.get("available_charging_points", {}).get("after", 0) or 0)
            if local_left > 0:
                recommendations.append(
                    {
                        "action": "Chuyển phân bổ các lịch sạc ưu tiên sang các trụ còn hoạt động tại Hub (UC-10).",
                        "feasibility": f"Còn {local_left} trụ hoạt động tại chỗ",
                        "reason": "Bảo toàn lịch sạc cho xe pin thấp khi một phần trụ sạc gặp sự cố.",
                        "nav_target": "charging",
                        "nav_label": "Lập lịch sạc →",
                    }
                )

    if "low_battery_risk" in codes:
        low_battery = int(metrics_by_id.get("low_battery_vehicles", {}).get("after", 0) or 0)
        local_capacity = _available_charging_points(result.get("snapshot", {}))
        if local_capacity >= max(1, low_battery):
            recommendations.append(
                {
                    "action": "Ưu tiên xếp lịch sạc sớm cho nhóm xe dưới ngưỡng pin trước ca cao điểm kế tiếp.",
                    "feasibility": f"Đủ {local_capacity} trụ rảnh tại trạm",
                    "reason": f"Mô hình ghi nhận {low_battery} xe dưới {_LOW_BATTERY_THRESHOLD}% pin; chưa tự tạo lịch thật.",
                    "nav_target": "resources",
                    "nav_label": "Giám sát tài nguyên sạc →",
                }
            )

    return recommendations


def _require_int(
    parameters: dict[str, Any], key: str, label: str, minimum: int, maximum: int
) -> list[str]:
    value = parameters.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{label} phải là số nguyên."]
    if not minimum <= value <= maximum:
        return [f"{label} phải nằm trong khoảng {minimum}–{maximum}."]
    return []


def _selected_hub(snapshot: dict[str, Any]) -> dict[str, Any]:
    hub_id = snapshot.get("selected_hub_id")
    return next(hub for hub in snapshot["records"]["hubs"] if hub.get("hub_id") == hub_id)


def _hub_vehicles(snapshot: dict[str, Any], hub_id: str | None) -> list[dict[str, Any]]:
    return [v for v in snapshot["records"]["vehicles"] if v.get("hub_id") == hub_id]


def _hub_spaces(snapshot: dict[str, Any], hub_id: str | None) -> list[dict[str, Any]]:
    return [p for p in snapshot["records"]["parking_spaces"] if p.get("hub_id") == hub_id]


def _hub_points(snapshot: dict[str, Any], hub_id: str | None) -> list[dict[str, Any]]:
    return [p for p in snapshot["records"]["charging_points"] if p.get("hub_id") == hub_id]


def _pending_reservations(snapshot: dict[str, Any], hub_id: str | None) -> int:
    return sum(
        1
        for reservation in snapshot["records"]["reservations"]
        if reservation.get("hub_id") == hub_id and reservation.get("status") == "PENDING"
    )


def _pending_charging_requests(snapshot: dict[str, Any], hub_id: str | None) -> int:
    records = snapshot["records"]
    requests = [
        *records.get("charging_requests", []),
        *records.get("shared_charging_requests", []),
    ]
    return sum(
        1
        for request in requests
        if request.get("hub_id") == hub_id and request.get("status") == "PENDING"
    )


def _available_charging_points(snapshot: dict[str, Any]) -> int:
    hub_id = snapshot.get("selected_hub_id")
    return sum(
        1
        for point in _hub_points(snapshot, hub_id)
        if point.get("status") == "AVAILABLE" and point.get("data_validity", "VALID") == "VALID"
    )


def _simulate_metro_surge(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    hub = _selected_hub(snapshot)
    vehicles = _hub_vehicles(snapshot, hub["hub_id"])
    available = sum(v.get("status") == "AVAILABLE" for v in vehicles)
    base_demand = parameters["base_demand"]
    demand_after = ceil(base_demand * (1 + parameters["increase_percent"] / 100))
    shortage_before = max(0, base_demand - available)
    shortage_after = max(0, demand_after - available)
    result["metrics"] = [
        _metric("base_demand", "Đỉnh nhu cầu dự kiến", base_demand, demand_after, "lượt"),
        _metric("available_vehicles", "Xe dùng chung khả dụng", available, available, "xe"),
        _metric("vehicle_shortage", "Mức thiếu hụt xe", shortage_before, shortage_after, "xe"),
        *_battery_metrics(snapshot, hub["hub_id"], max(0, demand_after - base_demand)),
    ]
    result["assumptions"] = [
        "Nhu cầu nền do Operator thiết lập cho khung giờ cao điểm tại Ga Metro.",
        "Số xe khả dụng lấy từ snapshot trạng thái AVAILABLE thực tế tại Metro Hub.",
        f"Mỗi chuyến phát sinh tiêu thụ trung bình {_BATTERY_PER_TRIP}% pin trên nhóm xe sẵn sàng.",
    ]


def _simulate_hub_capacity(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    hub = _selected_hub(snapshot)
    hub_id = hub["hub_id"]

    vehicles = _hub_vehicles(snapshot, hub_id)
    available_vehicles = sum(v.get("status") == "AVAILABLE" for v in vehicles)
    vehicle_demand = parameters["additional_vehicle_demand"]
    shortage_before = 0
    shortage_after = max(0, vehicle_demand - available_vehicles)

    spaces = _hub_spaces(snapshot, hub_id)
    parking_capacity = sum(space.get("status") != "UNAVAILABLE" for space in spaces)
    if not spaces:
        parking_capacity = int(hub.get("parking_capacity", 0) or 0)
    occupied_before = sum(space.get("status") in {"RESERVED", "IN_USE"} for space in spaces)
    occupied_after = occupied_before + parameters["additional_parking_occupancy"]
    rejected_after = max(0, occupied_after - parking_capacity)
    parking_before = _percent(occupied_before, parking_capacity)
    parking_after = _percent(occupied_after, parking_capacity)

    reservation_capacity = int(hub.get("reservation_capacity", 0) or 0)
    reserved_before = max(
        int(hub.get("reserved_slot_count", 0) or 0),
        _pending_reservations(snapshot, hub_id),
    )
    reserved_after = reserved_before + parameters["additional_vehicle_demand"]
    reservation_before = _percent(reserved_before, reservation_capacity)
    reservation_after = _percent(reserved_after, reservation_capacity)

    result["metrics"] = [
        _metric("parking_capacity", "Sức chứa bãi đỗ khả dụng", parking_capacity, parking_capacity, "chỗ"),
        _metric("parking_utilization", "Tỷ lệ lấp đầy bãi đỗ", parking_before, parking_after, "%"),
        _metric("rejected_parking", "Xe cá nhân bị từ chối do đầy bãi", 0, rejected_after, "xe"),
        _metric("available_vehicles", "Xe dùng chung khả dụng", available_vehicles, available_vehicles, "xe"),
        _metric("vehicle_shortage", "Xe thiếu theo nhu cầu tăng thêm", shortage_before, shortage_after, "xe"),
        _metric("reservation_utilization", "Mức sử dụng slot đặt trước", reservation_before, reservation_after, "%"),
        *_battery_metrics(snapshot, hub_id, vehicle_demand),
    ]
    result["assumptions"] = [
        f"Hub có {parking_capacity} ô đỗ hoạt động (loại trừ ô UNAVAILABLE); RESERVED và IN_USE tính là đã chiếm chỗ.",
        "Số xe bị từ chối bằng phần vượt quá sức chứa vật lý khi lượng xe gửi thêm làm bãi đỗ vượt 100%.",
        f"Sức chứa slot đặt xe lấy từ reservation_capacity ({reservation_capacity} slot).",
    ]


def _simulate_vehicle_concentration(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    source = parameters["source_hub_id"]
    target = snapshot["selected_hub_id"]
    moved = parameters["moved"]

    src_avail = sum(v.get("status") == "AVAILABLE" for v in _hub_vehicles(snapshot, source))
    tgt_avail = sum(v.get("status") == "AVAILABLE" for v in _hub_vehicles(snapshot, target))

    spaces = _hub_spaces(snapshot, target)
    parking_capacity = sum(s.get("status") != "UNAVAILABLE" for s in spaces) or 20
    occupied_before = sum(s.get("status") in {"RESERVED", "IN_USE"} for s in spaces)
    occupied_after = occupied_before + moved
    rejected_after = max(0, occupied_after - parking_capacity)

    result["metrics"] = [
        _metric("source_stock", f"Xe khả dụng còn lại tại {source}", src_avail, src_avail - moved, "xe"),
        _metric("target_stock", f"Xe khả dụng tập trung tại {target}", tgt_avail, tgt_avail + moved, "xe"),
        _metric(
            "parking_utilization",
            f"Tỷ lệ lấp đầy bãi đỗ {target}",
            _percent(occupied_before, parking_capacity),
            _percent(occupied_after, parking_capacity),
            "%",
        ),
        _metric("rejected_parking", "Số xe vượt sức chứa bãi đích", 0, rejected_after, "xe"),
    ]
    result["assumptions"] = [
        "Tổng số phương tiện trên toàn mạng giữ nguyên, chỉ dịch chuyển phân bố giữa Hub nguồn và Hub đích.",
        "Mỗi xe tập trung thêm về Hub đích chiếm 01 vị trí đỗ tại bãi đích.",
    ]


def _simulate_charging_pressure(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    hub_id = snapshot.get("selected_hub_id")
    points = _hub_points(snapshot, hub_id)
    avail_pts = [p for p in points if p.get("status") == "AVAILABLE"]
    available_before = len(avail_pts)
    failed_points = parameters["failed_points"]
    available_after = max(0, available_before - failed_points)

    kw_before = sum(float(p.get("power_kw", 0)) for p in avail_pts)
    sorted_avail_kw = sorted((float(p.get("power_kw", 0)) for p in avail_pts), reverse=True)
    kw_lost = sum(sorted_avail_kw[:failed_points])
    kw_after = max(0.0, round(kw_before - kw_lost, 1))

    pending = _pending_charging_requests(snapshot, hub_id)
    demand_before = pending
    demand_after = pending + parameters["additional_requests"]
    unserved_before = max(0, demand_before - available_before)
    unserved_after = max(0, demand_after - available_after)
    served_new_requests = min(
        parameters["additional_requests"], max(0, available_after - demand_before)
    )

    result["metrics"] = [
        _metric("charging_demand", "Yêu cầu sạc trong khung giờ", demand_before, demand_after, "yêu cầu"),
        _metric("available_charging_points", "Trụ sạc khả dụng", available_before, available_after, "trụ"),
        _metric("effective_charging_kw", "Công suất sạc sẵn sàng", round(kw_before, 1), kw_after, "kW"),
        _metric("unserved_charging_requests", "Yêu cầu sạc chưa được đáp ứng", unserved_before, unserved_after, "yêu cầu"),
        *_battery_metrics(snapshot, hub_id, served_charging_requests=served_new_requests),
    ]
    result["assumptions"] = [
        "Mỗi trụ sạc khả dụng phục vụ tối đa một phiên trong khung giờ đánh giá.",
        "Tổng nhu cầu tính cả yêu cầu sạc xe cá nhân (SUB-03) và nhu cầu sạc xe dùng chung (SUB-02) đang PENDING.",
        "Khi giả định trụ lỗi, mô hình xét kịch bản bất lợi nhất (trụ công suất cao ngừng hoạt động trước).",
    ]


def _battery_metrics(
    snapshot: dict[str, Any],
    hub_id: str | None,
    vehicle_trips: int = 0,
    served_charging_requests: int = 0,
) -> list[dict[str, Any]]:
    vehicles = [
        vehicle
        for vehicle in _hub_vehicles(snapshot, hub_id)
        if vehicle.get("status") == "AVAILABLE"
        and isinstance(vehicle.get("battery_level"), (int, float))
        and not isinstance(vehicle.get("battery_level"), bool)
    ]
    if not vehicles:
        return []

    before = [max(0, min(100, float(vehicle["battery_level"]))) for vehicle in vehicles]
    after = before.copy()
    if vehicle_trips:
        selected = sorted(range(len(before)), key=before.__getitem__, reverse=True)
        for index in selected[: min(vehicle_trips, len(selected))]:
            after[index] = max(0, after[index] - _BATTERY_PER_TRIP)
    if served_charging_requests:
        selected = sorted(range(len(before)), key=after.__getitem__)
        for index in selected[: min(served_charging_requests, len(selected))]:
            after[index] = min(100, after[index] + _BATTERY_PER_CHARGE)

    average_before = round(sum(before) / len(before), 1)
    average_after = round(sum(after) / len(after), 1)
    low_before = sum(level < _LOW_BATTERY_THRESHOLD for level in before)
    low_after = sum(level < _LOW_BATTERY_THRESHOLD for level in after)
    return [
        _metric("battery_average", "Pin trung bình đội xe sẵn sàng", average_before, average_after, "%"),
        _metric("low_battery_vehicles", "Xe dưới ngưỡng pin an toàn", low_before, low_after, "xe"),
    ]


def _metric(
    metric_id: str, label: str, before: int | float, after: int | float, unit: str
) -> dict[str, Any]:
    return {"id": metric_id, "label": label, "before": before, "after": after, "unit": unit}


def _percent(part: int, total: int) -> float:
    return round(part * 100 / total, 1) if total > 0 else 0.0


def _find_vehicle_donor(
    records: dict[str, Any],
    selected_hub_id: str | None,
    shortage: int = 1,
) -> dict[str, Any] | None:
    hubs = {hub.get("hub_id"): hub for hub in records.get("hubs", [])}
    counts: dict[str, int] = {}
    for vehicle in records.get("vehicles", []):
        if vehicle.get("status") == "AVAILABLE":
            counts[vehicle.get("hub_id")] = counts.get(vehicle.get("hub_id"), 0) + 1
    candidates = [
        {
            "hub_id": hub_id,
            "name": hubs.get(hub_id, {}).get("name", str(hub_id)),
            "available": count,
        }
        for hub_id, count in counts.items()
        if hub_id != selected_hub_id and count >= min(shortage, 1) + 1
    ]
    return max(candidates, key=lambda item: item["available"], default=None)


def _find_parking_alternative(
    records: dict[str, Any],
    selected_hub_id: str | None,
    required_spaces: int = 1,
) -> dict[str, Any] | None:
    hubs = {hub.get("hub_id"): hub for hub in records.get("hubs", [])}
    counts: dict[str, int] = {}
    for space in records.get("parking_spaces", []):
        if space.get("status") == "AVAILABLE":
            counts[space.get("hub_id")] = counts.get(space.get("hub_id"), 0) + 1
    candidates = [
        {
            "hub_id": hub_id,
            "name": hubs.get(hub_id, {}).get("name", str(hub_id)),
            "available": count,
        }
        for hub_id, count in counts.items()
        if hub_id != selected_hub_id and count >= required_spaces
    ]
    return max(candidates, key=lambda item: item["available"], default=None)


def _find_charging_alternative(
    records: dict[str, Any],
    selected_hub_id: str | None,
    required_points: int = 1,
) -> dict[str, Any] | None:
    hubs = {hub.get("hub_id"): hub for hub in records.get("hubs", [])}
    counts: dict[str, int] = {}
    for point in records.get("charging_points", []):
        if point.get("status") == "AVAILABLE":
            counts[point.get("hub_id")] = counts.get(point.get("hub_id"), 0) + 1
    candidates = [
        {
            "hub_id": hub_id,
            "name": hubs.get(hub_id, {}).get("name", str(hub_id)),
            "available": count,
        }
        for hub_id, count in counts.items()
        if hub_id != selected_hub_id and count >= required_points
    ]
    return max(candidates, key=lambda item: item["available"], default=None)


def _find_reservation_alternative(
    records: dict[str, Any],
    selected_hub_id: str | None,
    required_slots: int,
) -> dict[str, Any] | None:
    hubs = {hub.get("hub_id"): hub for hub in records.get("hubs", [])}
    pending: dict[str, int] = {}
    for reservation in records.get("reservations", []):
        if reservation.get("status") == "PENDING":
            hub_id = reservation.get("hub_id")
            pending[hub_id] = pending.get(hub_id, 0) + 1

    candidates = []
    for hub_id, hub in hubs.items():
        if hub_id == selected_hub_id:
            continue
        capacity = int(hub.get("reservation_capacity", 0) or 0)
        reserved = max(
            int(hub.get("reserved_slot_count", 0) or 0),
            pending.get(hub_id, 0),
        )
        available = max(0, capacity - reserved)
        if available >= required_slots:
            candidates.append(
                {
                    "hub_id": hub_id,
                    "name": hub.get("name", str(hub_id)),
                    "available": available,
                }
            )
    return max(candidates, key=lambda item: item["available"], default=None)
