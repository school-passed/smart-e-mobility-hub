"""Pure what-if simulation services for SUB-06.

The service reads an operational state, copies the relevant records into a
snapshot, and returns hypothetical results without changing the source state.
Scenario logic is intentionally deterministic and easy to explain during demo.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from math import ceil
from typing import Any


SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "id": "metro_demand_surge",
        "name": "Metro Hub tăng nhu cầu",
        "description": "Tăng nhu cầu xe tại Hub Metro và xem lượng xe còn thiếu.",
    },
    {
        "id": "hub_near_capacity",
        "name": "Hub gần đầy hoặc thiếu xe",
        "description": "Thay đổi nhu cầu xe và chỗ đỗ để xem mức sử dụng/cảnh báo.",
    },
    {
        "id": "charging_pressure",
        "name": "Nhu cầu sạc tăng hoặc trụ sạc lỗi",
        "description": "Tăng yêu cầu sạc hoặc giả định một số trụ sạc ngừng hoạt động.",
    },
)
_BATTERY_PER_TRIP = 8
_BATTERY_PER_CHARGE = 15
_LOW_BATTERY_THRESHOLD = 25


class SimulationInputError(ValueError):
    """Raised when required snapshot data or scenario input is invalid."""


def get_available_scenarios() -> list[dict[str, str]]:
    """Return the three scenarios currently agreed for the MVP demo."""
    return [dict(scenario) for scenario in SCENARIOS]


def get_network_snapshot(
    operational_state: dict[str, Any],
    hub_id: str | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Copy relevant network records and derive read-only summary metrics.

    A focused Hub snapshot still includes every Hub so recommendations can
    identify other locations with spare capacity. The input mapping and its
    records are never modified.
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
        "charging_points",
        "charging_requests",
        "shared_charging_requests",
        "charging_schedules",
    ):
        value = operational_state.get(key, [])
        sections_present[key] = key in operational_state and isinstance(value, list)
        if not isinstance(value, list):
            raise SimulationInputError(f"Dữ liệu {key} chưa đúng định dạng danh sách.")
        copied[key] = deepcopy(value)

    hubs_by_id = {
        str(hub.get("hub_id")): hub
        for hub in copied["hubs"]
        if isinstance(hub, dict) and hub.get("hub_id") is not None
    }
    if not hubs_by_id:
        raise SimulationInputError("Snapshot chưa có thông tin Hub để mô phỏng.")
    if hub_id is not None and hub_id not in hubs_by_id:
        raise SimulationInputError("Hub được chọn không còn trong dữ liệu snapshot.")

    summary = {
        "hub_count": len(hubs_by_id),
        "vehicle_count": len(copied["vehicles"]),
        "parking_space_count": len(copied["parking_spaces"]),
        "charging_point_count": len(copied["charging_points"]),
    }
    return {
        "captured_at": (captured_at or datetime.now()).isoformat(timespec="seconds"),
        "selected_hub_id": hub_id,
        "data_complete": bool(copied["hubs"] and copied["vehicles"]),
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
            errors.append("Snapshot thiếu dữ liệu Hub hoặc xe cần thiết.")
        records = snapshot.get("records", {})
        selected_hub = snapshot.get("selected_hub_id")
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
            "charging_pressure": ("hubs", "charging_points", "charging_requests"),
        }[scenario_id]
        for section in required_sections:
            if not snapshot.get("sections_present", {}).get(section, False):
                errors.append(f"Snapshot thiếu dữ liệu {section} cần cho kịch bản.")
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
                if isinstance(raw_parking_capacity, int)
                and not isinstance(raw_parking_capacity, bool)
                else 0
            )
            if parking_capacity <= 0:
                errors.append("Hub đã chọn chưa có dữ liệu capacity chỗ đỗ để mô phỏng.")
            raw_reservation_capacity = selected_record.get("reservation_capacity", 0)
            reservation_capacity = (
                raw_reservation_capacity
                if isinstance(raw_reservation_capacity, int)
                and not isinstance(raw_reservation_capacity, bool)
                else 0
            )
            if reservation_capacity <= 0:
                errors.append("Hub đã chọn chưa có dữ liệu capacity reservation để mô phỏng.")
        if selected_record is not None and scenario_id == "charging_pressure":
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
    elif scenario_id == "charging_pressure":
        errors.extend(_require_int(parameters, "additional_requests", "Số yêu cầu sạc tăng thêm", 0, 500))
        errors.extend(_require_int(parameters, "failed_points", "Số trụ sạc giả định bị lỗi", 0, 500))
        if snapshot is not None:
            available = _available_charging_points(snapshot)
            failed = parameters.get("failed_points")
            if isinstance(failed, int) and not isinstance(failed, bool) and failed > available:
                errors.append(f"Số trụ sạc lỗi không thể vượt quá {available} trụ đang khả dụng tại Hub.")

    return errors


def run_simulation(
    scenario_id: str,
    parameters: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Run one scenario against the immutable-by-convention input snapshot."""
    errors = validate_scenario_parameters(scenario_id, parameters, snapshot)
    if errors:
        raise SimulationInputError(" ".join(errors))

    result = {
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
        "status": "completed",
    }
    if scenario_id == "metro_demand_surge":
        _simulate_metro_surge(result)
    elif scenario_id == "hub_near_capacity":
        _simulate_hub_capacity(result)
    elif scenario_id == "charging_pressure":
        _simulate_charging_pressure(result)

    result["issues"] = evaluate_simulation_impact(result)
    result["recommendations"] = generate_recommendations(result)
    return result


def evaluate_simulation_impact(result: dict[str, Any]) -> list[dict[str, str]]:
    """Classify simulated capacity problems without changing live resources."""
    issues: list[dict[str, str]] = []
    for metric in result.get("metrics", []):
        metric_id = metric.get("id")
        after = metric.get("after")
        if metric_id == "vehicle_shortage" and isinstance(after, (int, float)) and after > 0:
            issues.append({
                "code": "vehicle_shortage",
                "severity": "high",
                "title": "Nhu cầu xe vượt nguồn xe khả dụng",
                "detail": f"Ước tính thiếu {int(after)} xe trong khung giờ đã chọn.",
            })
        elif metric_id in {"parking_utilization", "reservation_utilization"} and isinstance(after, (int, float)):
            if after >= 100:
                issues.append({
                    "code": f"{metric_id}_full",
                    "severity": "high",
                    "title": "Công suất Hub đã chạm giới hạn",
                    "detail": f"Mức sử dụng sau mô phỏng là {after:.0f}%.",
                })
            elif after >= 80:
                issues.append({
                    "code": f"{metric_id}_near_capacity",
                    "severity": "medium",
                    "title": "Hub gần đầy",
                    "detail": f"Mức sử dụng sau mô phỏng là {after:.0f}% (ngưỡng cảnh báo 80%).",
                })
        elif metric_id == "unserved_charging_requests" and isinstance(after, (int, float)) and after > 0:
            issues.append({
                "code": "charging_shortage",
                "severity": "high",
                "title": "Thiếu năng lực tiếp nhận yêu cầu sạc",
                "detail": f"Còn {int(after)} yêu cầu chưa có trụ sạc khả dụng trong mô hình.",
            })
        elif metric_id == "low_battery_vehicles" and isinstance(after, (int, float)) and after > 0:
            issues.append({
                "code": "low_battery_risk",
                "severity": "medium",
                "title": "Một số xe cần được sạc trước chuyến tiếp theo",
                "detail": f"Snapshot mô phỏng có {int(after)} xe dưới {_LOW_BATTERY_THRESHOLD}% pin sau kịch bản.",
            })

    vehicle_shortage = next(
        (metric.get("after", 0) for metric in result.get("metrics", []) if metric.get("id") == "vehicle_shortage"),
        0,
    )
    if vehicle_shortage > 0:
        donor = _find_vehicle_donor(
            result.get("snapshot", {}).get("records", {}),
            result.get("hub_id"),
            int(vehicle_shortage),
        )
        if donor:
            issues.append({
                "code": "network_imbalance",
                "severity": "medium",
                "title": "Xe đang phân bố chưa đều giữa các Hub",
                "detail": f"Hub đang thiếu {int(vehicle_shortage)} xe; {donor['name']} còn đủ xe dự phòng trong snapshot.",
            })

    if not issues:
        issues.append({
            "code": "no_issue_detected",
            "severity": "low",
            "title": "Chưa phát hiện vấn đề công suất",
            "detail": "Theo dữ liệu snapshot và giả định đã nhập, mạng lưới còn đáp ứng được.",
        })
    return issues


def generate_recommendations(result: dict[str, Any]) -> list[dict[str, str]]:
    """Suggest feasible, reviewable actions; never execute them."""
    if any(issue.get("code") == "no_issue_detected" for issue in result.get("issues", [])):
        return [{
            "action": "Tiếp tục theo dõi Hub trong khung giờ đã chọn.",
            "feasibility": "Khả thi",
            "reason": "Snapshot hiện tại chưa cho thấy thiếu hụt hoặc vượt capacity.",
        }]

    records = result.get("snapshot", {}).get("records", {})
    selected_hub_id = result.get("hub_id")
    recommendations: list[dict[str, str]] = []
    codes = {issue.get("code") for issue in result.get("issues", [])}

    if "vehicle_shortage" in codes:
        shortage = next(
            metric.get("after", 0)
            for metric in result.get("metrics", [])
            if metric.get("id") == "vehicle_shortage"
        )
        donor = _find_vehicle_donor(records, selected_hub_id, int(shortage))
        if donor:
            recommendations.append({
                "action": f"Operator xem xét điều chuyển xe khả dụng từ {donor['name']} đến Hub đang thiếu.",
                "feasibility": "Có nguồn xe dự phòng",
                "reason": f"Hub nguồn có {donor['available']} xe; đủ bù mức thiếu {int(shortage)} xe và giữ lại một xe tại nguồn. Chưa thực hiện điều chuyển.",
            })
        else:
            recommendations.append({
                "action": "Chưa có Hub nguồn đủ xe dự phòng; cân nhắc giảm/giãn nhu cầu hoặc bổ sung xe ngoài khung giờ.",
                "feasibility": "Chưa xác định được nguồn điều chuyển",
                "reason": "Không tìm thấy Hub khác còn xe khả dụng sau khi giữ lại ít nhất một xe.",
            })

    if any(code and code.startswith("parking_utilization") for code in codes):
        required_spaces = int(result.get("parameters", {}).get("additional_parking_occupancy", 1))
        alternate = _find_parking_alternative(records, selected_hub_id, max(1, required_spaces))
        if alternate:
            recommendations.append({
                "action": f"Đề xuất khách đặt chỗ sang {alternate['name']} nếu phù hợp.",
                "feasibility": "Còn chỗ theo snapshot",
                "reason": f"Hub này có {alternate['available']} chỗ đỗ đang khả dụng.",
            })
        else:
            recommendations.append({
                "action": "Cân nhắc giãn khung giờ đặt chỗ hoặc bổ sung năng lực đỗ xe.",
                "feasibility": "Chưa tìm thấy Hub thay thế",
                "reason": "Snapshot không có Hub khác còn chỗ đỗ khả dụng.",
            })

    if any(code and code.startswith("reservation_utilization") for code in codes):
        requested_slots = int(result.get("parameters", {}).get("additional_vehicle_demand", 1))
        alternate = _find_reservation_alternative(
            records,
            selected_hub_id,
            max(1, requested_slots),
        )
        if alternate:
            recommendations.append({
                "action": f"Operator xem xét điều tiết reservation sang {alternate['name']}.",
                "feasibility": "Còn slot theo snapshot",
                "reason": f"Hub này còn {alternate['available']} slot; mô phỏng không tự chuyển reservation.",
            })
        else:
            recommendations.append({
                "action": "Cân nhắc giãn khung giờ hoặc giảm số lượt reservation.",
                "feasibility": "Chưa tìm thấy Hub đủ slot trống",
                "reason": "Các Hub khác không có đủ capacity reservation theo nhu cầu giả định.",
            })

    if "charging_shortage" in codes:
        unserved = next(
            metric.get("after", 1)
            for metric in result.get("metrics", [])
            if metric.get("id") == "unserved_charging_requests"
        )
        alternate = _find_charging_alternative(records, selected_hub_id, max(1, int(unserved)))
        if alternate:
            recommendations.append({
                "action": f"Operator xem xét phân bổ một phần yêu cầu sang {alternate['name']}.",
                "feasibility": "Còn trụ sạc khả dụng",
                "reason": f"Snapshot có {alternate['available']} trụ sạc khả dụng tại Hub này.",
            })
        else:
            recommendations.append({
                "action": "Ưu tiên sửa trụ sạc lỗi hoặc giãn lịch nhận yêu cầu.",
                "feasibility": "Chưa tìm thấy công suất sạc thay thế",
                "reason": "Không có Hub khác còn trụ sạc khả dụng trong snapshot.",
            })

    if "low_battery_risk" in codes:
        low_battery = next(
            metric.get("after", 0)
            for metric in result.get("metrics", [])
            if metric.get("id") == "low_battery_vehicles"
        )
        local_capacity = _available_charging_points(result.get("snapshot", {}))
        if local_capacity >= int(low_battery):
            recommendations.append({
                "action": "Ưu tiên sạc các xe pin thấp tại Hub trước khi nhận thêm chuyến.",
                "feasibility": "Đủ trụ sạc khả dụng tại Hub",
                "reason": f"Mô hình ghi nhận {int(low_battery)} xe dưới {_LOW_BATTERY_THRESHOLD}% pin; chưa tạo lịch sạc thật.",
            })
        else:
            recommendations.append({
                "action": "Giãn lượt xe pin thấp hoặc kiểm tra Hub khác còn trụ sạc.",
                "feasibility": "Hub hiện tại thiếu trụ sạc cho toàn bộ xe pin thấp",
                "reason": f"Có {local_capacity} trụ sạc khả dụng cho {int(low_battery)} xe cần sạc theo mô hình.",
            })

    if not recommendations:
        recommendations.append({
            "action": "Operator xem xét các cảnh báo và chọn phương án phù hợp trước khi cập nhật vận hành.",
            "feasibility": "Cần Operator đánh giá",
            "reason": "Mô phỏng chỉ hỗ trợ quyết định và không tự thay đổi dữ liệu thật.",
        })
    return recommendations


def _require_int(parameters: dict[str, Any], key: str, label: str, minimum: int, maximum: int) -> list[str]:
    value = parameters.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{label} phải là số nguyên."]
    if not minimum <= value <= maximum:
        return [f"{label} phải nằm trong khoảng {minimum}–{maximum}."]
    return []


def _selected_hub(snapshot: dict[str, Any]) -> dict[str, Any]:
    hub_id = snapshot.get("selected_hub_id")
    return next(
        hub for hub in snapshot["records"]["hubs"]
        if hub.get("hub_id") == hub_id
    )


def _hub_vehicles(snapshot: dict[str, Any], hub_id: str) -> list[dict[str, Any]]:
    return [v for v in snapshot["records"]["vehicles"] if v.get("hub_id") == hub_id]


def _hub_spaces(snapshot: dict[str, Any], hub_id: str) -> list[dict[str, Any]]:
    return [p for p in snapshot["records"]["parking_spaces"] if p.get("hub_id") == hub_id]


def _hub_points(snapshot: dict[str, Any], hub_id: str) -> list[dict[str, Any]]:
    return [p for p in snapshot["records"]["charging_points"] if p.get("hub_id") == hub_id]


def _pending_reservations(snapshot: dict[str, Any], hub_id: str) -> int:
    return sum(
        1 for reservation in snapshot["records"]["reservations"]
        if reservation.get("hub_id") == hub_id and reservation.get("status") == "PENDING"
    )


def _pending_charging_requests(snapshot: dict[str, Any], hub_id: str) -> int:
    """Count pending private and shared EV charging demands without duplication."""
    records = snapshot["records"]
    requests = [
        *records.get("charging_requests", []),
        *records.get("shared_charging_requests", []),
    ]
    return sum(
        1 for request in requests
        if request.get("hub_id") == hub_id and request.get("status") == "PENDING"
    )


def _available_charging_points(snapshot: dict[str, Any]) -> int:
    hub_id = snapshot.get("selected_hub_id")
    return sum(1 for point in _hub_points(snapshot, hub_id) if point.get("status") == "AVAILABLE")


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
        _metric("base_demand", "Nhu cầu xe (lượt/khung giờ)", base_demand, demand_after, "lượt"),
        _metric("available_vehicles", "Xe khả dụng tại Hub", available, available, "xe"),
        _metric("vehicle_shortage", "Xe còn thiếu", shortage_before, shortage_after, "xe"),
        *_battery_metrics(snapshot, hub["hub_id"], max(0, demand_after - base_demand)),
    ]
    result["assumptions"] = [
        "Nhu cầu nền là giá trị Operator nhập cho khung giờ mô phỏng.",
        "Số xe khả dụng lấy từ snapshot trạng thái AVAILABLE tại Metro Hub.",
        f"Mỗi lượt xe tăng thêm được giả định tiêu thụ {_BATTERY_PER_TRIP} điểm phần trăm pin; ưu tiên xe có pin cao.",
    ]


def _simulate_hub_capacity(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    hub = _selected_hub(snapshot)
    hub_id = hub["hub_id"]

    vehicles = _hub_vehicles(snapshot, hub_id)
    available_vehicles = sum(v.get("status") == "AVAILABLE" for v in vehicles)
    active_fleet = sum(v.get("status") in {"AVAILABLE", "IN_USE", "CHARGING"} for v in vehicles)
    vehicle_demand = parameters["additional_vehicle_demand"]
    shortage_before = 0
    shortage_after = max(0, vehicle_demand - available_vehicles)

    spaces = _hub_spaces(snapshot, hub_id)
    parking_capacity = sum(space.get("status") != "UNAVAILABLE" for space in spaces)
    if not spaces:
        parking_capacity = int(hub.get("parking_capacity", 0) or 0)
    occupied_before = sum(space.get("status") in {"RESERVED", "IN_USE"} for space in spaces)
    occupied_after = occupied_before + parameters["additional_parking_occupancy"]
    parking_before = _percent(occupied_before, parking_capacity)
    parking_after = _percent(occupied_after, parking_capacity)

    reservation_capacity = int(hub.get("reservation_capacity", 0) or 0)
    reserved_before = int(hub.get("reserved_slot_count", 0) or 0)
    pending_count = _pending_reservations(snapshot, hub_id)
    reserved_before = max(reserved_before, pending_count)
    reserved_after = reserved_before + parameters["additional_vehicle_demand"]
    reservation_before = _percent(reserved_before, reservation_capacity)
    reservation_after = _percent(reserved_after, reservation_capacity)

    result["metrics"] = [
        _metric("available_vehicles", "Xe khả dụng", available_vehicles, available_vehicles, "xe"),
        _metric("vehicle_shortage", "Xe thiếu theo nhu cầu nhập", shortage_before, shortage_after, "xe"),
        _metric("parking_utilization", "Mức sử dụng chỗ đỗ", parking_before, parking_after, "%"),
        _metric("reservation_utilization", "Mức sử dụng slot reservation", reservation_before, reservation_after, "%"),
        _metric("fleet_size", "Đội xe đang hoạt động", active_fleet, active_fleet, "xe"),
        *_battery_metrics(snapshot, hub_id, vehicle_demand),
    ]
    result["assumptions"] = [
        f"Hub có {parking_capacity} chỗ đỗ sử dụng được; RESERVED và IN_USE được tính là đang chiếm, UNAVAILABLE bị loại khỏi capacity.",
        f"Capacity reservation lấy từ reservation_capacity ({reservation_capacity}); nhu cầu xe tăng thêm cũng được dùng làm số slot giả định.",
        "Xe thiếu được tính bằng nhu cầu xe tăng thêm trừ số xe AVAILABLE; không giả định sức chứa bãi xe cho đội xe.",
        f"Mỗi xe được dùng cho một lượt đi giả định tiêu thụ {_BATTERY_PER_TRIP} điểm phần trăm pin.",
    ]


def _simulate_charging_pressure(result: dict[str, Any]) -> None:
    snapshot = result["snapshot"]
    parameters = result["parameters"]
    hub_id = snapshot.get("selected_hub_id")
    points = _hub_points(snapshot, hub_id)
    available_before = sum(point.get("status") == "AVAILABLE" for point in points)
    failed_points = parameters["failed_points"]
    available_after = max(0, available_before - failed_points)
    pending = _pending_charging_requests(snapshot, hub_id)
    demand_before = pending
    demand_after = pending + parameters["additional_requests"]
    unserved_before = max(0, demand_before - available_before)
    unserved_after = max(0, demand_after - available_after)
    served_new_requests = min(parameters["additional_requests"], max(0, available_after - demand_before))
    result["metrics"] = [
        _metric("charging_demand", "Yêu cầu sạc trong khung giờ", demand_before, demand_after, "yêu cầu"),
        _metric("available_charging_points", "Trụ sạc khả dụng", available_before, available_after, "trụ"),
        _metric("unserved_charging_requests", "Yêu cầu sạc chưa được đáp ứng", unserved_before, unserved_after, "yêu cầu"),
        *_battery_metrics(snapshot, hub_id, served_charging_requests=served_new_requests),
    ]
    result["assumptions"] = [
        "Mỗi trụ sạc khả dụng tiếp nhận tối đa một yêu cầu trong khung giờ mô phỏng.",
        "Chỉ đếm yêu cầu PENDING của Hub đã chọn; yêu cầu tăng thêm do Operator nhập.",
        "Số trụ giả định lỗi được trừ khỏi các trụ AVAILABLE trong snapshot.",
        f"Mỗi yêu cầu sạc được phục vụ tăng pin mô phỏng {_BATTERY_PER_CHARGE} điểm phần trăm cho một xe pin thấp tại Hub.",
    ]


def _battery_metrics(
    snapshot: dict[str, Any],
    hub_id: str,
    vehicle_trips: int = 0,
    served_charging_requests: int = 0,
) -> list[dict[str, Any]]:
    vehicles = [
        vehicle for vehicle in _hub_vehicles(snapshot, hub_id)
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
        for index in selected[:min(vehicle_trips, len(selected))]:
            after[index] = max(0, after[index] - _BATTERY_PER_TRIP)
    if served_charging_requests:
        selected = sorted(range(len(before)), key=after.__getitem__)
        for index in selected[:min(served_charging_requests, len(selected))]:
            after[index] = min(100, after[index] + _BATTERY_PER_CHARGE)

    average_before = round(sum(before) / len(before), 1)
    average_after = round(sum(after) / len(after), 1)
    low_before = sum(level < _LOW_BATTERY_THRESHOLD for level in before)
    low_after = sum(level < _LOW_BATTERY_THRESHOLD for level in after)
    return [
        _metric("battery_average", "Pin trung bình xe sẵn sàng", average_before, average_after, "%"),
        _metric("low_battery_vehicles", "Xe dưới ngưỡng pin", low_before, low_after, "xe"),
    ]


def _metric(metric_id: str, label: str, before: int | float, after: int | float, unit: str) -> dict[str, Any]:
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
        {"hub_id": hub_id, "name": hubs.get(hub_id, {}).get("name", str(hub_id)), "available": count}
        for hub_id, count in counts.items()
        if hub_id != selected_hub_id and count >= shortage + 1
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
        {"hub_id": hub_id, "name": hubs.get(hub_id, {}).get("name", str(hub_id)), "available": count}
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
        {"hub_id": hub_id, "name": hubs.get(hub_id, {}).get("name", str(hub_id)), "available": count}
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
            candidates.append({
                "hub_id": hub_id,
                "name": hub.get("name", str(hub_id)),
                "available": available,
            })
    return max(candidates, key=lambda item: item["available"], default=None)
