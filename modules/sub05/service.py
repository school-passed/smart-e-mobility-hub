"""SUB-05 service: Network Operation & Dispatch (UC-11 to UC-14)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from shared import enums
from shared.state import (
    atomic,
    available_vehicle,
    free_spaces,
    get_state,
    hub_validity,
    point_validity,
    record_audit_log,
)

NEAR_CAPACITY_FREE_RATIO = 0.20
STALE_AFTER_MINUTES = 30
DISPATCH_TRAVEL_MINUTES = 15
MIN_OPERATING_BATTERY = 20

DISPATCH_TRANSITING = "TRANSITING"
DISPATCH_COMPLETED = "COMPLETED"
DISPATCH_CANCELLED = "CANCELLED"

INCIDENT_OPEN = "OPEN"
INCIDENT_RESOLVED = "RESOLVED"

SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
SEVERITIES = (SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW)

VEHICLE_TYPE_LABELS = {
    "ELECTRIC_BICYCLE": "Xe đạp điện",
    "ELECTRIC_MOTORCYCLE": "Xe máy điện",
}

_CLOSED_SCHEDULE_STATUSES = ("CANCELLED", "COMPLETED", "REJECTED", "EXPIRED", "INTERRUPTED")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now_dt() -> datetime:
    return datetime.now().astimezone()


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _parse(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=_now_dt().tzinfo)
    except (TypeError, ValueError):
        return None


def _result(ok: bool, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": ok, "message": message, **extra}


def _hub_by_id(hub_id: str) -> dict[str, Any] | None:
    return next((h for h in get_state()["hubs"] if h["hub_id"] == hub_id), None)


def _count(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if item["status"] == status)


def _metric(free: int, total: int, reliable: bool = True) -> dict[str, Any]:
    pct = round(free / total * 100) if total else 0
    return {
        "free": free,
        "total": total,
        "pct": pct,
        "near": reliable and total > 0 and (free / total) <= NEAR_CAPACITY_FREE_RATIO,
    }


def _refresh_reservations() -> None:
    """Ask SUB-01 to expire old reservations so held-vehicle counts are fresh."""
    try:
        from modules.sub01 import service as sub01_service

        expire = getattr(sub01_service, "expire_pending_reservations", None)
        if callable(expire):
            expire(get_state())
    except Exception:
        pass


def refresh(operator_id: str | None = None) -> None:
    """Call when a SUB-05 screen opens: expire reservations, finish due orders."""
    from modules.sub04.service import expire_unused_schedules

    _refresh_reservations()
    expire_unused_schedules(get_state())
    complete_due_dispatch_orders()
    if operator_id:
        state = get_state()
        logs = state.setdefault("audit_logs", [])
        if not logs or logs[-1].get("action") != "MONITOR_DASHBOARD" or logs[-1].get("actor") != operator_id:
            record_audit_log(state, operator_id, "MONITOR_DASHBOARD", "Truy cập bảng điều khiển giám sát mạng lưới (UC-11)")


def get_audit_logs(limit: int = 40) -> list[dict[str, Any]]:
    logs = get_state().get("audit_logs", [])
    return list(reversed(logs[-limit:]))


def _point_label(point_id: str) -> str:
    digits = "".join(ch for ch in point_id if ch.isdigit())
    return f"Trụ #{int(digits):02d}" if digits else point_id


# ---------------------------------------------------------------------------
# Dispatch order helpers
# ---------------------------------------------------------------------------

def _transit_vehicle_ids(exclude_order_id: str | None = None) -> set[str]:
    ids: set[str] = set()
    for order in get_state()["dispatch_orders"]:
        if order["status"] == DISPATCH_TRANSITING and order["order_id"] != exclude_order_id:
            ids.update(order["vehicle_ids"])
    return ids


def _find_order(order_id: str) -> dict[str, Any] | None:
    return next(
        (o for o in get_state()["dispatch_orders"] if o["order_id"] == order_id), None
    )


def eta_minutes_left(order: dict[str, Any]) -> int:
    eta = _parse(order.get("eta"))
    if eta is None:
        return 0
    return max(0, int((eta - _now_dt()).total_seconds() // 60))


# ---------------------------------------------------------------------------
# UC-11 Monitor Mobility Hub Network / UC-12 Near Capacity
# ---------------------------------------------------------------------------

def _hub_rows() -> list[dict[str, Any]]:
    state = get_state()
    in_transit = _transit_vehicle_ids()
    now = _now_dt()
    rows: list[dict[str, Any]] = []
    for hub in state["hubs"]:
        hid = hub["hub_id"]
        vehicles = [v for v in state["vehicles"] if v["hub_id"] == hid]
        spaces = [p for p in state["parking_spaces"] if p["hub_id"] == hid]
        points = [c for c in state["charging_points"] if c["hub_id"] == hid]

        healthy_avail = [
            v
            for v in vehicles
            if v["status"] == enums.VEHICLE_AVAILABLE and not v.get("incident_blocked")
        ]
        transiting = sum(1 for v in healthy_avail if v["vehicle_id"] in in_transit)
        pool = len(healthy_avail) - transiting
        held = max(0, min(int(hub.get("reserved_slot_count", 0)), pool))
        free = pool - held

        validity = hub_validity(state, hub, now)
        reliable = validity == "VALID"
        free_chargers = sum(
            1
            for c in points
            if c["status"] == enums.CHARGING_POINT_AVAILABLE
            and not c.get("incident_blocked")
            and point_validity(c, now) == "VALID"
        )

        metrics = {
            "vehicles": _metric(free, len(vehicles), reliable=reliable),
            "parking": _metric(len(free_spaces(state, hid)), len(spaces), reliable=reliable),
            "charging": _metric(free_chargers, len(points), reliable=reliable),
        }
        flags = [key for key, m in metrics.items() if m["near"]]
        unavailable_veh = sum(
            1
            for v in vehicles
            if v["status"] == enums.VEHICLE_UNAVAILABLE or v.get("incident_blocked")
        )
        rows.append(
            {
                "hub_id": hid,
                "name": hub["name"],
                "address": hub["address"],
                **metrics,
                "near_flags": flags,
                "near": bool(flags),
                "stale": not reliable,
                "data_validity": validity,
                "data_updated_at": hub.get("data_updated_at"),
                "counts": {
                    "total": len(vehicles),
                    "free": free,
                    "in_use": _count(vehicles, enums.VEHICLE_IN_USE),
                    "charging": _count(vehicles, enums.VEHICLE_CHARGING),
                    "unavailable": unavailable_veh,
                    "held": held,
                    "transiting": transiting,
                },
            }
        )
    return rows


def _capacity_detail(row: dict[str, Any]) -> str:
    parts = []
    for flag in row["near_flags"]:
        m = row[flag]
        if flag == "vehicles":
            parts.append(f"sắp hết xe (còn {m['free']}/{m['total']} xe khả dụng, {m['pct']}%)")
        elif flag == "parking":
            parts.append(f"sắp hết chỗ đỗ (còn {m['free']}/{m['total']} trống, {m['pct']}%)")
        else:
            parts.append(f"sắp hết cổng sạc (còn {m['free']}/{m['total']} rảnh, {m['pct']}%)")
    return " và ".join(parts) + "."


def get_network_dashboard() -> dict[str, Any]:
    """Overview of the whole network (UC-11 & UC-12)."""
    state = get_state()
    rows = _hub_rows()
    totals = {
        key: sum(r["counts"][key] for r in rows)
        for key in ("total", "free", "in_use", "charging", "unavailable", "held", "transiting")
    }
    incidents = get_incident_views()
    alerts: list[dict[str, Any]] = []
    active_alert_keys: set[str] = set()
    logged_keys: set[str] = state.setdefault("_logged_capacity_alerts", set())

    for r in rows:
        if r["stale"]:
            mode_vi = "mất kết nối (DISCONNECTED)" if r["data_validity"] == "DISCONNECTED" else "dữ liệu trễ (STALE)"
            alerts.append(
                {
                    "kind": "stale",
                    "hub_id": r["hub_id"],
                    "hub_name": r["name"],
                    "detail": f"đang {mode_vi}; tạm ngưng đánh giá ngưỡng Near Capacity tự động (UC-12).",
                    "action": "hub",
                }
            )
        elif r["near"]:
            detail = _capacity_detail(r)
            alert_key = f"{r['hub_id']}:{','.join(r['near_flags'])}"
            active_alert_keys.add(alert_key)
            if alert_key not in logged_keys:
                logged_keys.add(alert_key)
                record_audit_log(
                    state,
                    "SYSTEM",
                    "NEAR_CAPACITY_ALERT",
                    f"{r['name']} {detail}",
                    r["hub_id"],
                )
            alerts.append(
                {
                    "kind": "capacity",
                    "hub_id": r["hub_id"],
                    "hub_name": r["name"],
                    "detail": detail,
                    "action": "dispatch",
                }
            )
    # Remove resolved alert keys so re-crossing threshold logs cleanly
    logged_keys.intersection_update(active_alert_keys)

    for inc in incidents:
        if inc["severity"] == SEVERITY_HIGH:
            alerts.append(
                {
                    "kind": "incident",
                    "incident_id": inc["incident_id"],
                    "hub_id": inc["hub_id"],
                    "hub_name": inc["hub_name"],
                    "detail": f"{inc['resource_label']} ({inc['hub_name']}): {inc['description']}",
                    "action": "incidents",
                }
            )
    return {
        "hubs": rows,
        "totals": totals,
        "near_capacity_count": sum(1 for r in rows if r["near"]),
        "stale_count": sum(1 for r in rows if r["stale"]),
        "open_incidents": len(incidents),
        "alerts": alerts,
    }


def identify_near_capacity_hubs(threshold: float | None = None) -> list[dict[str, Any]]:
    """Hubs having a reliable resource whose free share is <= ``threshold`` (0-1)."""
    if threshold is None:
        threshold = NEAR_CAPACITY_FREE_RATIO
    if not 0 <= threshold < 1:
        raise ValueError("threshold must be at least 0 and below 1")
    result = []
    for r in _hub_rows():
        if r["stale"]:
            continue
        flags = [
            key
            for key in ("vehicles", "parking", "charging")
            if r[key]["total"] > 0 and r[key]["free"] / r[key]["total"] <= threshold
        ]
        if flags:
            result.append({"hub_id": r["hub_id"], "name": r["name"], "resources": flags})
    return result


def get_hub_detail(hub_id: str) -> dict[str, Any] | None:
    """Everything the Hub detail screen needs, or None if the Hub is unknown."""
    row = next((r for r in _hub_rows() if r["hub_id"] == hub_id), None)
    if row is None:
        return None
    state = get_state()
    in_transit = _transit_vehicle_ids()
    space_by_veh = {
        p["vehicle_id"]: p["space_id"]
        for p in state["parking_spaces"]
        if p.get("hub_id") == hub_id and p.get("vehicle_id")
    }

    rank = {"AVAILABLE": 0, "TRANSITING": 1, "CHARGING": 2, "IN_USE": 3, "UNAVAILABLE": 4}
    vehicles = []
    for v in state["vehicles"]:
        if v["hub_id"] != hub_id:
            continue
        if v["status"] == enums.VEHICLE_AVAILABLE and v.get("incident_blocked"):
            status = "UNAVAILABLE"
        elif v["status"] == enums.VEHICLE_AVAILABLE and v["vehicle_id"] in in_transit:
            status = "TRANSITING"
        else:
            status = v["status"]
        stall = space_by_veh.get(v["vehicle_id"])
        vehicles.append(
            {
                "vehicle_id": v["vehicle_id"],
                "vehicle_type": v["vehicle_type"],
                "battery_level": v["battery_level"],
                "status": status,
                "location": {
                    "AVAILABLE": stall or "Bãi xe Hub",
                    "TRANSITING": "Chờ điều chuyển",
                    "CHARGING": "Khu vực sạc",
                    "IN_USE": "Đang di chuyển",
                    "UNAVAILABLE": "Khu bảo trì",
                }.get(status, "-"),
            }
        )
    vehicles.sort(key=lambda v: (rank.get(v["status"], 9), -v["battery_level"]))

    points = [
        {
            "point_id": c["charging_point_id"],
            "label": _point_label(c["charging_point_id"]),
            "power_kw": c.get("power_kw", 0),
            "status": (
                point_validity(c)
                if point_validity(c) != "VALID"
                else ("UNAVAILABLE" if c.get("incident_blocked") else c["status"])
            ),
        }
        for c in state["charging_points"]
        if c["hub_id"] == hub_id
    ]
    spaces_total = row["parking"]["total"]
    occupied = spaces_total - row["parking"]["free"]
    return {
        "summary": row,
        "parking_occupied_pct": round(occupied / spaces_total * 100) if spaces_total else 0,
        "vehicles": vehicles,
        "charging_points": points,
        "incoming_orders": [
            {**o, "minutes_left": eta_minutes_left(o)}
            for o in get_dispatch_orders(DISPATCH_TRANSITING)
            if o["target_hub_id"] == hub_id
        ],
        "incidents": [i for i in get_incident_views() if i["hub_id"] == hub_id],
    }


# ---------------------------------------------------------------------------
# UC-13 Redistribute Vehicles
# ---------------------------------------------------------------------------

def get_receiving_capacity(hub_id: str) -> dict[str, int]:
    """Free parking spaces of a Hub minus vehicles already on their way to it."""
    state = get_state()
    free = len(free_spaces(state, hub_id))
    incoming = sum(
        len(o["vehicle_ids"])
        for o in state["dispatch_orders"]
        if o["status"] == DISPATCH_TRANSITING and o["target_hub_id"] == hub_id
    )
    legacy = sum(
        len(o["vehicle_ids"])
        for o in state["dispatch_orders"]
        if o["target_hub_id"] == hub_id
        and o["status"] == DISPATCH_TRANSITING
        and not o.get("space_ids")
    )
    return {
        "free_spaces": free + incoming - legacy,
        "incoming": incoming,
        "can_receive": max(0, free - legacy),
    }


def get_transferable_vehicles(source_hub_id: str) -> dict[str, Any]:
    """Vehicles that may leave ``source_hub_id`` (read-only)."""
    _refresh_reservations()
    state = get_state()
    hub = _hub_by_id(source_hub_id)
    if hub is None:
        return {"vehicles": [], "by_type": {}, "held_for_reservations": 0, "max_transferable": 0}

    candidates = [
        v
        for v in state["vehicles"]
        if v["hub_id"] == source_hub_id
        and available_vehicle(state, v)
        and v.get("battery_level", 0) >= MIN_OPERATING_BATTERY
    ]
    candidates.sort(key=lambda v: v["battery_level"], reverse=True)
    by_type: dict[str, int] = {}
    for v in candidates:
        by_type[v["vehicle_type"]] = by_type.get(v["vehicle_type"], 0) + 1
    held = int(hub.get("reserved_slot_count", 0))
    return {
        "vehicles": candidates,
        "by_type": by_type,
        "held_for_reservations": held,
        "max_transferable": max(0, len(candidates) - held),
    }


def _select_vehicles(
    source_hub_id: str, quantities: dict[str, int]
) -> tuple[list[str], str | None]:
    """Pick the highest-battery eligible vehicles of each requested type."""
    info = get_transferable_vehicles(source_hub_id)
    chosen: list[str] = []
    for vtype, qty in quantities.items():
        qty = int(qty or 0)
        if qty < 0:
            return [], "Số lượng không hợp lệ."
        if qty == 0:
            continue
        pool = [v for v in info["vehicles"] if v["vehicle_type"] == vtype]
        if qty > len(pool):
            label = VEHICLE_TYPE_LABELS.get(vtype, vtype)
            return [], f"Số lượng vượt quá {len(pool)} {label.lower()} khả dụng tại Hub nguồn."
        chosen.extend(v["vehicle_id"] for v in pool[:qty])
    return chosen, None


def _validate_dispatch(
    source_hub_id: str,
    target_hub_id: str,
    vehicle_ids: list[str],
    exclude_order_id: str | None = None,
    check_limits: bool = True,
) -> str | None:
    """Return an error message, or None when the dispatch is allowed."""
    state = get_state()
    source = _hub_by_id(source_hub_id)
    target = _hub_by_id(target_hub_id)
    if source is None:
        return "Không tìm thấy Hub nguồn."
    if target is None:
        return "Không tìm thấy Hub đích."
    if any(hub.get("data_validity") == "DISCONNECTED" for hub in (source, target)):
        return "Hub nguồn hoặc Hub đích đang mất kết nối. Hãy cập nhật trạng thái trước khi điều chuyển."
    if source_hub_id == target_hub_id:
        return "Hub nguồn và Hub đích phải khác nhau."
    if not vehicle_ids:
        return "Hãy chọn ít nhất một xe để điều chuyển."
    if len(set(vehicle_ids)) != len(vehicle_ids):
        return "Có xe bị chọn trùng."

    in_transit = _transit_vehicle_ids(exclude_order_id)
    by_id = {v["vehicle_id"]: v for v in state["vehicles"]}
    problems = []
    for vid in vehicle_ids:
        vehicle = by_id.get(vid)
        if vehicle is None:
            problems.append(f"{vid} (không tồn tại)")
        elif vehicle["hub_id"] != source_hub_id:
            problems.append(f"{vid} (không ở Hub nguồn)")
        elif vehicle["status"] != enums.VEHICLE_AVAILABLE or vehicle.get("incident_blocked"):
            problems.append(f"{vid} ({vehicle['status']})")
        elif vehicle.get("battery_level", 0) < MIN_OPERATING_BATTERY:
            problems.append(f"{vid} (pin thấp {vehicle.get('battery_level')}%)")
        elif vid in in_transit:
            problems.append(f"{vid} (đang trong lệnh điều chuyển khác)")
    if problems:
        return "Các xe sau không đủ điều kiện điều chuyển: " + ", ".join(problems) + "."
    if not check_limits:
        return None

    pool = [
        v
        for v in state["vehicles"]
        if v["hub_id"] == source_hub_id
        and v["status"] == enums.VEHICLE_AVAILABLE
        and not v.get("incident_blocked")
        and v.get("battery_level", 0) >= MIN_OPERATING_BATTERY
        and v["vehicle_id"] not in in_transit
    ]
    held = int(source.get("reserved_slot_count", 0))
    movable = max(0, len(pool) - held)
    if len(vehicle_ids) > movable:
        return (
            f"Số xe khả dụng tại {source['name']} chỉ có thể xuất tối đa {movable} xe "
            f"({held} xe đang được giữ cho các lượt đặt trước)."
        )

    cap = get_receiving_capacity(target_hub_id)
    order = _find_order(exclude_order_id) if exclude_order_id else None
    if order and order["target_hub_id"] == target_hub_id:
        cap["can_receive"] = max(
            0, cap["free_spaces"] - cap["incoming"] + len(order["vehicle_ids"])
        )
    if order and order.get("space_ids"):
        usable = {p["space_id"] for p in free_spaces(state, target_hub_id, exclude_order_id)}
        if not usable.issuperset(order["space_ids"]):
            return "Chỗ tiếp nhận tại Hub đích đã bị khóa hoặc không còn trống."
    if len(vehicle_ids) > cap["can_receive"]:
        return (
            f"Số lượng vượt quá {cap['can_receive']} chỗ trống có thể tiếp nhận tại {target['name']} "
            f"({cap['free_spaces']} chỗ trống vật lý, {cap['incoming']} xe đang trên đường tới)."
        )
    return None


@atomic
def create_dispatch_order(
    source_hub_id: str,
    target_hub_id: str,
    vehicle_ids: list[str] | None = None,
    quantities: dict[str, int] | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Validate and record a TRANSITING dispatch order (UC-13)."""
    _refresh_reservations()
    if vehicle_ids is None:
        vehicle_ids, error = _select_vehicles(source_hub_id, quantities or {})
        if error:
            return _result(False, error)
    vehicle_ids = list(vehicle_ids)

    error = _validate_dispatch(source_hub_id, target_hub_id, vehicle_ids)
    if error:
        return _result(False, error)

    state = get_state()
    by_id = {v["vehicle_id"]: v for v in state["vehicles"]}
    counts: dict[str, int] = {}
    for vid in vehicle_ids:
        vtype = by_id[vid]["vehicle_type"]
        counts[vtype] = counts.get(vtype, 0) + 1

    number = state["next_dispatch_number"]
    state["next_dispatch_number"] = number + 1
    now = _now_dt()
    reserved_spaces = [p["space_id"] for p in free_spaces(state, target_hub_id)[: len(vehicle_ids)]]
    order = {
        "order_id": f"DSP-{number:03d}",
        "source_hub_id": source_hub_id,
        "target_hub_id": target_hub_id,
        "vehicle_ids": vehicle_ids,
        "space_ids": reserved_spaces,
        "quantities": counts,
        "status": DISPATCH_TRANSITING,
        "created_by": created_by,
        "created_at": now.isoformat(timespec="seconds"),
        "eta": (now + timedelta(minutes=DISPATCH_TRAVEL_MINUTES)).isoformat(timespec="seconds"),
        "completed_at": None,
    }
    state["dispatch_orders"].append(order)
    record_audit_log(
        state,
        created_by or "Operator",
        "CREATE_DISPATCH",
        f"Tạo lệnh {order['order_id']}: chuyển {len(vehicle_ids)} xe từ {source_hub_id} sang {target_hub_id} (giữ ô {', '.join(reserved_spaces)})",
        target_hub_id,
    )
    return _result(
        True,
        f"Đã tạo lệnh {order['order_id']}: điều chuyển {len(vehicle_ids)} xe sang {target_hub_id}.",
        order=order,
    )


@atomic
def complete_dispatch_order(order_id: str) -> dict[str, Any]:
    """Confirm arrival: move the vehicles of a TRANSITING order."""
    order = _find_order(order_id)
    if order is None:
        return _result(False, f"Không tìm thấy lệnh {order_id}.")
    if order["status"] == DISPATCH_COMPLETED:
        return _result(True, f"Lệnh {order_id} đã hoàn tất trước đó.", order=order)
    if order["status"] != DISPATCH_TRANSITING:
        return _result(False, f"Lệnh {order_id} đang ở trạng thái {order['status']}.")

    error = _validate_dispatch(
        order["source_hub_id"],
        order["target_hub_id"],
        order["vehicle_ids"],
        exclude_order_id=order_id,
        check_limits=True,
    )
    if error:
        return _result(False, f"Không thể hoàn tất {order_id}: {error}")

    moved: list[str] = []
    from modules.sub02.service import relocate_vehicle

    for index, vehicle_id in enumerate(order["vehicle_ids"]):
        spaces = order.get("space_ids", [])
        result = relocate_vehicle(
            vehicle_id,
            order["target_hub_id"],
            order_id,
            spaces[index] if index < len(spaces) else None,
        )
        if not result["ok"]:
            return _result(
                False,
                f"Không thể chuyển xe {vehicle_id}: {result['message']}. "
                f"Đã chuyển: {', '.join(moved) or 'chưa có xe nào'}.",
            )
        moved.append(vehicle_id)

    order["status"] = DISPATCH_COMPLETED
    order["completed_at"] = _now()
    record_audit_log(
        get_state(),
        order.get("created_by") or "Operator",
        "COMPLETE_DISPATCH",
        f"Hoàn tất lệnh {order_id}: {len(moved)} xe đã tới {order['target_hub_id']}",
        order["target_hub_id"],
    )
    return _result(
        True,
        f"Lệnh {order_id} hoàn thành: {len(moved)} xe đã tới Hub đích.",
        order=order,
    )


def complete_due_dispatch_orders() -> int:
    """Complete TRANSITING orders whose ETA has passed. Returns how many."""
    done = 0
    now = _now_dt()
    for order in list(get_state()["dispatch_orders"]):
        eta = _parse(order.get("eta"))
        if order["status"] == DISPATCH_TRANSITING and eta is not None and eta <= now:
            if complete_dispatch_order(order["order_id"])["ok"]:
                done += 1
    return done


@atomic
def cancel_dispatch_order(order_id: str) -> dict[str, Any]:
    order = _find_order(order_id)
    if order is None:
        return _result(False, f"Không tìm thấy lệnh {order_id}.")
    if order["status"] == DISPATCH_CANCELLED:
        return _result(True, f"Lệnh {order_id} đã được hủy trước đó.", order=order)
    if order["status"] != DISPATCH_TRANSITING:
        return _result(False, f"Chỉ hủy được lệnh đang TRANSITING (lệnh này là {order['status']}).")
    order["status"] = DISPATCH_CANCELLED
    order["completed_at"] = _now()
    record_audit_log(
        get_state(),
        order.get("created_by") or "Operator",
        "CANCEL_DISPATCH",
        f"Hủy lệnh {order_id} và giải phóng chỗ giữ tại {order['target_hub_id']}",
        order["target_hub_id"],
    )
    return _result(True, f"Đã hủy lệnh {order_id} và giải phóng các ô giữ trước.", order=order)


def get_dispatch_orders(status: str | None = None) -> list[dict[str, Any]]:
    orders = get_state()["dispatch_orders"]
    if status is not None:
        orders = [o for o in orders if o["status"] == status]
    return sorted(orders, key=lambda o: (o["created_at"], o["order_id"]), reverse=True)


# ---------------------------------------------------------------------------
# UC-14 Handle Incident
# ---------------------------------------------------------------------------

def _resource_info(resource_id: str) -> dict[str, Any] | None:
    state = get_state()
    hub_names = {h["hub_id"]: h["name"] for h in state["hubs"]}
    for h in state["hubs"]:
        if h["hub_id"] == resource_id:
            return {
                "resource_id": resource_id,
                "resource_type": "HUB",
                "hub_id": resource_id,
                "hub_name": h["name"],
                "label": h["name"],
                "status": h.get("data_validity", "VALID"),
            }
    for v in state["vehicles"]:
        if v["vehicle_id"] == resource_id:
            return {
                "resource_id": resource_id,
                "resource_type": "VEHICLE",
                "hub_id": v["hub_id"],
                "hub_name": hub_names.get(v["hub_id"], v["hub_id"]),
                "label": f"Xe {resource_id}",
                "status": v["status"],
            }
    for p in state["parking_spaces"]:
        if p["space_id"] == resource_id:
            return {
                "resource_id": resource_id,
                "resource_type": "PARKING_SPACE",
                "hub_id": p["hub_id"],
                "hub_name": hub_names.get(p["hub_id"], p["hub_id"]),
                "label": f"Chỗ đỗ {resource_id}",
                "status": p["status"],
            }
    for c in state["charging_points"]:
        if c["charging_point_id"] == resource_id:
            return {
                "resource_id": resource_id,
                "resource_type": "CHARGING_POINT",
                "hub_id": c["hub_id"],
                "hub_name": hub_names.get(c["hub_id"], c["hub_id"]),
                "label": _point_label(resource_id),
                "status": c["status"],
            }
    return None


def list_resources() -> list[dict[str, str]]:
    """Every resource an incident can be reported against."""
    state = get_state()
    ids = (
        [h["hub_id"] for h in state["hubs"]]
        + [c["charging_point_id"] for c in state["charging_points"]]
        + [v["vehicle_id"] for v in state["vehicles"]]
        + [p["space_id"] for p in state["parking_spaces"]]
    )
    items = []
    for rid in ids:
        info = _resource_info(rid)
        if info:
            items.append(
                {
                    "resource_id": rid,
                    "resource_type": info["resource_type"],
                    "hub_id": info["hub_id"],
                    "label": f"{info['label']} · {info['hub_name']}",
                }
            )
    return items


def _impact_and_action(info: dict[str, Any]) -> tuple[str, dict[str, str], list[str]]:
    """Business impact text, suggested next action, and affected commitment IDs (FR-05-17)."""
    state = get_state()
    rtype, status = info["resource_type"], info["status"]
    hub_id = info["hub_id"]
    affected_ids: list[str] = []

    if rtype == "CHARGING_POINT":
        active_scheds = [
            s["schedule_id"]
            for s in state["charging_schedules"]
            if s.get("charging_point_id") == info["resource_id"]
            and s.get("status") in ("CONFIRMED", "IN_USE")
        ]
        draft_scheds = [
            s["schedule_id"]
            for s in state["charging_schedules"]
            if s.get("charging_point_id") == info["resource_id"]
            and s.get("status") == "PROPOSED"
        ]
        affected_ids.extend(active_scheds)
        if active_scheds:
            impact = f"Ảnh hưởng {len(active_scheds)} lịch sạc: {', '.join(active_scheds)}"
        elif draft_scheds:
            impact = f"Ảnh hưởng {len(draft_scheds)} đề xuất ({', '.join(draft_scheds)})"
        elif status == enums.CHARGING_POINT_UNAVAILABLE:
            impact = "Giảm 1 cổng sạc khả dụng"
        else:
            impact = "Chưa ảnh hưởng lịch đã xác nhận"
        return impact, {"label": "Lập lịch sạc", "target": "other:Lập lịch sạc"}, affected_ids

    if rtype == "VEHICLE":
        pending_res = [
            r["reservation_id"]
            for r in state["reservations"]
            if r.get("hub_id") == hub_id and r.get("status") == "PENDING"
        ]
        healthy_avail = sum(
            1 for v in state["vehicles"] if v["hub_id"] == hub_id and available_vehicle(state, v)
        )
        if pending_res and healthy_avail < len(pending_res):
            affected_ids.extend(pending_res)
            impact = f"Thiếu xe cho đặt trước: {', '.join(pending_res)}"
        elif status == enums.VEHICLE_UNAVAILABLE:
            impact = "Thiếu hụt 1 xe khả dụng"
        elif status == enums.VEHICLE_IN_USE:
            impact = "Đang có khách thuê · Chờ hết chuyến / Dừng khẩn"
        else:
            impact = "Đã chặn cấp phát mới"
        return impact, {"label": "Điều chuyển xe", "target": "dispatch"}, affected_ids

    if rtype == "PARKING_SPACE":
        active_prsv = [
            r["reservation_id"]
            for r in state.get("parking_reservations", [])
            if r.get("space_id") == info["resource_id"] and r.get("status") in ("RESERVED", "IN_USE")
        ]
        affected_ids.extend(active_prsv)
        if active_prsv:
            impact = f"Ảnh hưởng phiếu đỗ {', '.join(active_prsv)}"
        else:
            impact = "Giảm 1 chỗ đỗ khả dụng" if status == enums.PARKING_UNAVAILABLE else "Chưa ảnh hưởng vận hành"
        return impact, {"label": "Tổng quan mạng lưới", "target": "overview"}, affected_ids

    pending_res = [
        r["reservation_id"]
        for r in state["reservations"]
        if r.get("hub_id") == hub_id and r.get("status") == "PENDING"
    ]
    affected_ids.extend(pending_res)
    impact = f"Ảnh hưởng toàn Hub ({len(pending_res)} đặt chỗ chờ)" if pending_res else "Ảnh hưởng toàn Hub"
    return impact, {"label": "Tổng quan mạng lưới", "target": "overview"}, affected_ids


def get_incident_views(include_resolved: bool = False) -> list[dict[str, Any]]:
    """Incidents enriched for display, most severe and newest first."""
    rank = {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}
    incidents = [
        i
        for i in get_state()["incidents"]
        if include_resolved or i["status"] == INCIDENT_OPEN
    ]
    incidents.sort(key=lambda i: i["created_at"], reverse=True)
    incidents.sort(key=lambda i: rank.get(i["severity"], 9))
    views = []
    for inc in incidents:
        info = _resource_info(inc["resource_id"])
        if info is None:
            continue
        impact, action, affected_ids = _impact_and_action(info)
        views.append(
            {
                **inc,
                "resource_label": info["label"],
                "resource_type": info["resource_type"],
                "hub_id": info["hub_id"],
                "hub_name": info["hub_name"],
                "resource_status": info["status"],
                "location": (
                    "Đang trên hành trình"
                    if info["status"] == enums.VEHICLE_IN_USE and info["resource_type"] == "VEHICLE"
                    else info["hub_name"]
                ),
                "impact": impact,
                "affected_ids": affected_ids,
                "action": action,
            }
        )
    return views


def get_incident_summary() -> dict[str, int]:
    open_items = [i for i in get_state()["incidents"] if i["status"] == INCIDENT_OPEN]
    return {
        "total": len(open_items),
        "high": sum(1 for i in open_items if i["severity"] == SEVERITY_HIGH),
        "medium": sum(1 for i in open_items if i["severity"] == SEVERITY_MEDIUM),
        "low": sum(1 for i in open_items if i["severity"] == SEVERITY_LOW),
    }


def _incident_resource(state, resource_id):
    for table, key in (
        ("vehicles", "vehicle_id"),
        ("parking_spaces", "space_id"),
        ("charging_points", "charging_point_id"),
    ):
        for resource in state[table]:
            if resource[key] == resource_id:
                return resource
    return None


@atomic
def create_or_update_incident(
    resource_id: str,
    description: str,
    severity: str = SEVERITY_MEDIUM,
    reported_by: str | None = None,
) -> dict[str, Any]:
    """Create an incident, or update the open one of the same resource (UC-14 & FR-05-18)."""
    description = (description or "").strip()
    if not description:
        return _result(False, "Hãy nhập mô tả sự cố.")
    if severity not in SEVERITIES:
        return _result(False, "Mức độ sự cố không hợp lệ.")
    info = _resource_info(resource_id)
    if info is None:
        return _result(False, f"Tài nguyên {resource_id} không tồn tại.")

    state = get_state()
    now = _now()
    existing = next(
        (
            i
            for i in state["incidents"]
            if i["resource_id"] == resource_id and i["status"] == INCIDENT_OPEN
        ),
        None,
    )
    if existing is not None:
        existing["description"] = description
        existing["severity"] = severity
        existing["updated_at"] = now
        existing["history"].append({"at": now, "by": reported_by, "note": description})
        record_audit_log(
            state,
            reported_by or "Operator",
            "UPDATE_INCIDENT",
            f"Cập nhật sự cố {existing['incident_id']} ({resource_id}, {severity}): {description}",
            info["hub_id"],
        )
        return _result(
            True,
            f"{info['label']} đã có sự cố đang mở ({existing['incident_id']}); đã cập nhật nội dung.",
            incident=existing,
            created=False,
        )

    number = state["next_incident_number"]
    state["next_incident_number"] = number + 1
    incident = {
        "incident_id": f"INC-{number:03d}",
        "resource_id": resource_id,
        "description": description,
        "severity": severity,
        "status": INCIDENT_OPEN,
        "reported_by": reported_by,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "history": [{"at": now, "by": reported_by, "note": description}],
    }
    resource = _incident_resource(state, resource_id)
    if resource is not None:
        incident["previous_status"] = resource["status"]
        resource["incident_blocked"] = True
        if (
            resource["status"] == "AVAILABLE"
            or (info["resource_type"] == "VEHICLE" and resource["status"] == "CHARGING")
            or (info["resource_type"] == "CHARGING_POINT" and resource["status"] == "RESERVED")
        ):
            resource["status"] = "UNAVAILABLE"
    elif info["resource_type"] == "HUB":
        hub = _hub_by_id(resource_id)
        if hub is not None and severity == SEVERITY_HIGH:
            hub["data_validity"] = "DISCONNECTED"
            hub["data_updated_at"] = now

    state["incidents"].append(incident)
    record_audit_log(
        state,
        reported_by or "Operator",
        "CREATE_INCIDENT",
        f"Ghi nhận sự cố {incident['incident_id']} ({resource_id}, {severity}): {description}",
        info["hub_id"],
    )
    return _result(
        True,
        f"Đã ghi nhận sự cố {incident['incident_id']}.",
        incident=incident,
        created=True,
    )


@atomic
def emergency_stop_resource_session(
    incident_id: str, operator_name: str | None = None
) -> dict[str, Any]:
    """UC-14 A1: Operator confirms immediate session termination for a HIGH-severity incident."""
    state = get_state()
    incident = next((i for i in state["incidents"] if i["incident_id"] == incident_id), None)
    if incident is None or incident["status"] != INCIDENT_OPEN:
        return _result(False, "Không tìm thấy sự cố đang mở.")

    rid = incident["resource_id"]
    info = _resource_info(rid)
    if info is None:
        return _result(False, "Không tìm thấy tài nguyên.")

    now = _now()
    if info["resource_type"] == "VEHICLE":
        veh = next((v for v in state["vehicles"] if v["vehicle_id"] == rid), None)
        trip = next((t for t in state["trips"] if t["vehicle_id"] == rid and t["is_active"]), None)
        if trip is not None:
            trip["destination_hub_id"] = veh["hub_id"] if veh else trip["origin_hub_id"]
            trip["end_time"] = now
            trip["end_battery_level"] = veh["battery_level"] if veh else trip["start_battery_level"]
            trip["is_active"] = False
            spaces = free_spaces(state, trip["destination_hub_id"])
            if spaces and veh:
                spaces[0].update(status="IN_USE", vehicle_id=veh["vehicle_id"])
        if veh is not None:
            veh["incident_blocked"] = True
            veh["status"] = "UNAVAILABLE"
        incident["history"].append({"at": now, "by": operator_name, "note": "Dừng khẩn cấp chuyến đi an toàn"})
        record_audit_log(state, operator_name or "Operator", "EMERGENCY_STOP", f"Dừng khẩn cấp phiên của xe {rid} ({incident_id})", info["hub_id"])
        return _result(True, f"Đã dừng khẩn cấp phiên sử dụng và khóa an toàn xe {rid} (UNAVAILABLE).")

    if info["resource_type"] == "CHARGING_POINT":
        pt = next((c for c in state["charging_points"] if c["charging_point_id"] == rid), None)
        from modules.sub04.service import interrupt_charging_session

        for s in state["charging_schedules"]:
            if s["charging_point_id"] == rid and s["status"] == "IN_USE":
                interrupt_charging_session(state, s["schedule_id"])
        if pt is not None:
            pt["incident_blocked"] = True
            pt["status"] = "UNAVAILABLE"
        incident["history"].append({"at": now, "by": operator_name, "note": "Ngắt khẩn cấp phiên sạc"})
        record_audit_log(state, operator_name or "Operator", "EMERGENCY_STOP", f"Ngắt khẩn cấp trụ sạc {rid} ({incident_id})", info["hub_id"])
        return _result(True, f"Đã ngắt khẩn cấp phiên sạc và cô lập trụ {rid} (UNAVAILABLE).")

    return _result(False, "Loại tài nguyên này không có phiên đang chạy để dừng khẩn cấp.")


@atomic
def resolve_incident(incident_id: str, resolved_by: str | None = None) -> dict[str, Any]:
    state = get_state()
    incident = next(
        (i for i in state["incidents"] if i["incident_id"] == incident_id), None
    )
    if incident is None:
        return _result(False, f"Không tìm thấy sự cố {incident_id}.")
    if incident["status"] == INCIDENT_RESOLVED:
        return _result(False, f"Sự cố {incident_id} đã được giải quyết trước đó.")

    now = _now()
    rid = incident["resource_id"]
    info = _resource_info(rid)
    resource = _incident_resource(state, rid)

    if resource is not None:
        resource.pop("incident_blocked", None)
        if resource.get("vehicle_id"):
            active_trip = any(
                t["vehicle_id"] == rid and t["is_active"] for t in state.get("trips", [])
            )
            open_charge = any(
                r["vehicle_id"] == rid and r["status"] in ("PENDING", "CONFIRMED")
                for r in state.get("shared_charging_requests", [])
            )
            if active_trip:
                resource["status"] = "IN_USE"
            elif resource.get("battery_level", 100) < MIN_OPERATING_BATTERY or open_charge:
                resource["status"] = "CHARGING"
                if not open_charge:
                    from modules.sub04.service import receive_shared_vehicle_charging_need

                    receive_shared_vehicle_charging_need(
                        state, rid, resource.get("battery_level", 15)
                    )
            else:
                resource["status"] = "AVAILABLE"
        elif resource.get("charging_point_id"):
            resource["status"] = "AVAILABLE"
            from modules.sub04.service import _refresh_point

            _refresh_point(state, resource["charging_point_id"])
        elif resource.get("space_id"):
            active_prsv = next(
                (
                    r
                    for r in state.get("parking_reservations", [])
                    if r["space_id"] == rid and r["status"] in ("RESERVED", "IN_USE")
                ),
                None,
            )
            if active_prsv:
                resource["status"] = active_prsv["status"]
            elif resource.get("vehicle_id"):
                resource["status"] = "IN_USE"
            else:
                resource["status"] = "AVAILABLE"
    elif info and info["resource_type"] == "HUB":
        hub = _hub_by_id(rid)
        if hub is not None:
            hub["data_validity"] = "VALID"
            hub["data_updated_at"] = None

    incident["status"] = INCIDENT_RESOLVED
    incident["updated_at"] = now
    incident["resolved_at"] = now
    incident["history"].append({"at": now, "by": resolved_by, "note": "Đã giải quyết và khôi phục tài nguyên"})
    record_audit_log(
        state,
        resolved_by or "Operator",
        "RESOLVE_INCIDENT",
        f"Đóng sự cố {incident_id} và tính lại trạng thái khả dụng cho {rid}",
        info["hub_id"] if info else None,
    )
    return _result(True, f"Đã đánh dấu {incident_id} là đã giải quyết và khôi phục trạng thái phù hợp.", incident=incident)
