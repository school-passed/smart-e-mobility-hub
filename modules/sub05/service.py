"""SUB-05 service: Network Operation & Dispatch (UC-11 to UC-14)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from shared import enums
from shared.state import get_state


NEAR_CAPACITY_FREE_RATIO = 0.20
STALE_AFTER_MINUTES = 30
DISPATCH_TRAVEL_MINUTES = 15

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

_CLOSED_SCHEDULE_STATUSES = ("CANCELLED", "COMPLETED", "REJECTED")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _result(ok: bool, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": ok, "message": message, **extra}


def _hub_by_id(hub_id: str) -> dict[str, Any] | None:
    return next((h for h in get_state()["hubs"] if h["hub_id"] == hub_id), None)


def _count(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if item["status"] == status)


def _metric(free: int, total: int) -> dict[str, Any]:
    pct = round(free / total * 100) if total else 0
    return {
        "free": free,
        "total": total,
        "pct": pct,
        "near": total > 0 and free / total <= NEAR_CAPACITY_FREE_RATIO,
    }


def _refresh_reservations() -> None:
    """Ask SUB-01 to expire old reservations so held-vehicle counts are fresh."""
    try:
        from modules.sub01 import service as sub01_service

        expire = getattr(sub01_service, "expire_pending_reservations", None)
        if callable(expire):
            expire()
    except Exception:  # never let a SUB-01 problem break SUB-05 screens
        pass


def refresh() -> None:
    """Call when a SUB-05 screen opens: expire reservations, finish due orders."""
    _refresh_reservations()
    complete_due_dispatch_orders()


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
    return max(0, int((eta - datetime.now()).total_seconds() // 60))


# ---------------------------------------------------------------------------
# UC-11 Monitor Mobility Hub Network / UC-12 Near Capacity
# ---------------------------------------------------------------------------

def _hub_rows() -> list[dict[str, Any]]:
    state = get_state()
    in_transit = _transit_vehicle_ids()
    now = datetime.now()
    rows: list[dict[str, Any]] = []
    for hub in state["hubs"]:
        hid = hub["hub_id"]
        vehicles = [v for v in state["vehicles"] if v["hub_id"] == hid]
        spaces = [p for p in state["parking_spaces"] if p["hub_id"] == hid]
        points = [c for c in state["charging_points"] if c["hub_id"] == hid]

        available = [v for v in vehicles if v["status"] == enums.VEHICLE_AVAILABLE]
        transiting = sum(1 for v in available if v["vehicle_id"] in in_transit)
        pool = len(available) - transiting
        held = max(0, min(int(hub.get("reserved_slot_count", 0)), pool))
        free = pool - held

        metrics = {
            "vehicles": _metric(free, len(vehicles)),
            "parking": _metric(_count(spaces, enums.PARKING_AVAILABLE), len(spaces)),
            "charging": _metric(
                _count(points, enums.CHARGING_POINT_AVAILABLE), len(points)
            ),
        }
        flags = [key for key, m in metrics.items() if m["near"]]
        updated = _parse(hub.get("data_updated_at"))
        stale = bool(
            updated and now - updated > timedelta(minutes=STALE_AFTER_MINUTES)
        )
        rows.append(
            {
                "hub_id": hid,
                "name": hub["name"],
                "address": hub["address"],
                **metrics,
                "near_flags": flags,
                "near": bool(flags),
                "stale": stale,
                "counts": {
                    "total": len(vehicles),
                    "free": free,
                    "in_use": _count(vehicles, enums.VEHICLE_IN_USE),
                    "charging": _count(vehicles, enums.VEHICLE_CHARGING),
                    "unavailable": _count(vehicles, enums.VEHICLE_UNAVAILABLE),
                    "held": held,
                    "transiting": transiting,
                },
            }
        )
    return rows


_FLAG_TEXT = {
    "vehicles": "xe",
    "parking": "chỗ đỗ",
    "charging": "cổng sạc",
}


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
    """Overview of the whole network (read-only)."""
    rows = _hub_rows()
    totals = {
        key: sum(r["counts"][key] for r in rows)
        for key in ("total", "free", "in_use", "charging", "unavailable", "held", "transiting")
    }
    incidents = get_incident_views()
    alerts: list[dict[str, Any]] = []
    for r in rows:
        if r["near"]:
            alerts.append(
                {
                    "kind": "capacity",
                    "hub_id": r["hub_id"],
                    "hub_name": r["name"],
                    "detail": _capacity_detail(r),
                    "action": "dispatch",
                }
            )
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
    """Hubs having a resource whose free share is <= ``threshold`` (0-1)."""
    if threshold is None:
        threshold = NEAR_CAPACITY_FREE_RATIO
    if not 0 <= threshold < 1:
        raise ValueError("threshold must be at least 0 and below 1")
    result = []
    for r in _hub_rows():
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

    rank = {"AVAILABLE": 0, "TRANSITING": 1, "CHARGING": 2, "IN_USE": 3, "UNAVAILABLE": 4}
    vehicles = []
    for v in state["vehicles"]:
        if v["hub_id"] != hub_id:
            continue
        status = (
            "TRANSITING"
            if v["status"] == enums.VEHICLE_AVAILABLE and v["vehicle_id"] in in_transit
            else v["status"]
        )
        vehicles.append(
            {
                "vehicle_id": v["vehicle_id"],
                "vehicle_type": v["vehicle_type"],
                "battery_level": v["battery_level"],
                "status": status,
                "location": {
                    "AVAILABLE": "Bãi xe Hub",
                    "TRANSITING": "Chờ điều chuyển",
                    "CHARGING": "Trụ sạc",
                    "IN_USE": "Đang di chuyển",
                    "UNAVAILABLE": "Khu bảo trì",
                }.get(status, "-"),
            }
        )
    vehicles.sort(key=lambda v: (rank.get(v["status"], 9), -v["battery_level"]))

    points = [
        {"point_id": c["charging_point_id"], "label": _point_label(c["charging_point_id"]),
         "status": c["status"]}
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
    free = sum(
        1
        for p in state["parking_spaces"]
        if p["hub_id"] == hub_id and p["status"] == enums.PARKING_AVAILABLE
    )
    incoming = sum(
        len(o["vehicle_ids"])
        for o in state["dispatch_orders"]
        if o["status"] == DISPATCH_TRANSITING and o["target_hub_id"] == hub_id
    )
    return {"free_spaces": free, "incoming": incoming, "can_receive": max(0, free - incoming)}


def get_transferable_vehicles(source_hub_id: str) -> dict[str, Any]:
    """Vehicles that may leave ``source_hub_id`` (read-only).

    Candidates are AVAILABLE vehicles at the Hub that are not already in a
    TRANSITING order. A reservation is tied to a Hub slot, not to a vehicle,
    so ``max_transferable = candidates - reserved_slot_count``.
    """
    _refresh_reservations()
    hub = _hub_by_id(source_hub_id)
    if hub is None:
        return {"vehicles": [], "by_type": {}, "held_for_reservations": 0, "max_transferable": 0}

    in_transit = _transit_vehicle_ids()
    candidates = [
        v
        for v in get_state()["vehicles"]
        if v["hub_id"] == source_hub_id
        and v["status"] == enums.VEHICLE_AVAILABLE
        and v["vehicle_id"] not in in_transit
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
            return [], f"Chỉ có {len(pool)} {label.lower()} khả dụng tại Hub nguồn."
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
        elif vehicle["status"] != enums.VEHICLE_AVAILABLE:
            problems.append(f"{vid} ({vehicle['status']})")
        elif vid in in_transit:
            problems.append(f"{vid} (đang trong lệnh điều chuyển khác)")
    if problems:
        return "Các xe sau không đủ điều kiện điều chuyển: " + ", ".join(problems) + "."
    if not check_limits:
        return None

    # Do not take vehicles that serve active reservations.
    pool = [
        v
        for v in state["vehicles"]
        if v["hub_id"] == source_hub_id
        and v["status"] == enums.VEHICLE_AVAILABLE
        and v["vehicle_id"] not in in_transit
    ]
    held = int(source.get("reserved_slot_count", 0))
    movable = max(0, len(pool) - held)
    if len(vehicle_ids) > movable:
        return (
            f"{source['name']} chỉ có thể xuất tối đa {movable} xe: "
            f"{held} xe đang được giữ cho các lượt đặt trước."
        )

    # The target Hub must have room for the vehicles.
    cap = get_receiving_capacity(target_hub_id)
    if exclude_order_id:
        order = _find_order(exclude_order_id)
        if order and order["target_hub_id"] == target_hub_id:
            cap["can_receive"] += len(order["vehicle_ids"])
    if len(vehicle_ids) > cap["can_receive"]:
        return (
            f"{target['name']} chỉ còn chỗ nhận {cap['can_receive']} xe "
            f"({cap['free_spaces']} chỗ đỗ trống, {cap['incoming']} xe đang trên đường tới)."
        )
    return None


def create_dispatch_order(
    source_hub_id: str,
    target_hub_id: str,
    vehicle_ids: list[str] | None = None,
    quantities: dict[str, int] | None = None,
    created_by: str | None = None,
) -> dict[str, Any]:
    """Validate and record a TRANSITING dispatch order.

    Pass either ``vehicle_ids`` or ``quantities`` (``{vehicle_type: count}``;
    the highest-battery eligible vehicles are picked). Vehicles are moved
    when the order is completed.
    """
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
    now = datetime.now()
    order = {
        "order_id": f"DSP-{number:03d}",
        "source_hub_id": source_hub_id,
        "target_hub_id": target_hub_id,
        "vehicle_ids": vehicle_ids,
        "quantities": counts,
        "status": DISPATCH_TRANSITING,
        "created_by": created_by,
        "created_at": now.isoformat(timespec="seconds"),
        "eta": (now + timedelta(minutes=DISPATCH_TRAVEL_MINUTES)).isoformat(timespec="seconds"),
        "completed_at": None,
    }
    state["dispatch_orders"].append(order)
    return _result(
        True,
        f"Đã tạo lệnh {order['order_id']}: điều chuyển {len(vehicle_ids)} xe.",
        order=order,
    )


def _relocate_vehicle(vehicle_id: str, target_hub_id: str) -> tuple[bool, str]:
    """Move one vehicle to another Hub through its owner (SUB-02) if possible.

    TODO (agree with M2): SUB-02 should expose
    ``relocate_vehicle(vehicle_id, target_hub_id)``. Until it exists, the
    fallback below updates ``hub_id`` directly so the demo still works.
    """
    try:
        from modules.sub02 import service as sub02_service

        relocate = getattr(sub02_service, "relocate_vehicle", None)
    except Exception:
        relocate = None

    if callable(relocate):
        outcome = relocate(vehicle_id, target_hub_id)
        if isinstance(outcome, dict):
            return bool(outcome.get("ok", True)), str(outcome.get("message", ""))
        if isinstance(outcome, tuple) and outcome:
            return bool(outcome[0]), str(outcome[1]) if len(outcome) > 1 else ""
        return outcome is not False, ""

    for vehicle in get_state()["vehicles"]:
        if vehicle["vehicle_id"] == vehicle_id:
            vehicle["hub_id"] = target_hub_id
            return True, ""
    return False, "không tìm thấy xe"


def complete_dispatch_order(order_id: str) -> dict[str, Any]:
    """Confirm arrival: move the vehicles of a TRANSITING order."""
    order = _find_order(order_id)
    if order is None:
        return _result(False, f"Không tìm thấy lệnh {order_id}.")
    if order["status"] != DISPATCH_TRANSITING:
        return _result(False, f"Lệnh {order_id} đã ở trạng thái {order['status']}.")

    error = _validate_dispatch(
        order["source_hub_id"],
        order["target_hub_id"],
        order["vehicle_ids"],
        exclude_order_id=order_id,
        check_limits=False,  # limits were checked when the order was created
    )
    if error:
        return _result(False, f"Không thể hoàn tất {order_id}: {error}")

    moved: list[str] = []
    for vehicle_id in order["vehicle_ids"]:
        ok, message = _relocate_vehicle(vehicle_id, order["target_hub_id"])
        if not ok:
            return _result(
                False,
                f"Không thể chuyển xe {vehicle_id}: {message}. "
                f"Đã chuyển: {', '.join(moved) or 'chưa có xe nào'}.",
            )
        moved.append(vehicle_id)

    order["status"] = DISPATCH_COMPLETED
    order["completed_at"] = _now()
    return _result(
        True, f"Lệnh {order_id} hoàn thành: {len(moved)} xe đã tới Hub đích.", order=order
    )


def complete_due_dispatch_orders() -> int:
    """Complete TRANSITING orders whose ETA has passed. Returns how many."""
    done = 0
    now = datetime.now()
    for order in list(get_state()["dispatch_orders"]):
        eta = _parse(order.get("eta"))
        if order["status"] == DISPATCH_TRANSITING and eta is not None and eta <= now:
            if complete_dispatch_order(order["order_id"])["ok"]:
                done += 1
    return done


def cancel_dispatch_order(order_id: str) -> dict[str, Any]:
    order = _find_order(order_id)
    if order is None:
        return _result(False, f"Không tìm thấy lệnh {order_id}.")
    if order["status"] != DISPATCH_TRANSITING:
        return _result(False, f"Chỉ hủy được lệnh đang TRANSITING (lệnh này là {order['status']}).")
    order["status"] = DISPATCH_CANCELLED
    order["completed_at"] = _now()
    return _result(True, f"Đã hủy lệnh {order_id}.", order=order)


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
            return {"resource_id": resource_id, "resource_type": "HUB", "hub_id": resource_id,
                    "hub_name": h["name"], "label": h["name"], "status": None}
    for v in state["vehicles"]:
        if v["vehicle_id"] == resource_id:
            return {"resource_id": resource_id, "resource_type": "VEHICLE", "hub_id": v["hub_id"],
                    "hub_name": hub_names.get(v["hub_id"], v["hub_id"]),
                    "label": f"Xe {resource_id}", "status": v["status"]}
    for p in state["parking_spaces"]:
        if p["space_id"] == resource_id:
            return {"resource_id": resource_id, "resource_type": "PARKING_SPACE", "hub_id": p["hub_id"],
                    "hub_name": hub_names.get(p["hub_id"], p["hub_id"]),
                    "label": f"Chỗ đỗ {resource_id}", "status": p["status"]}
    for c in state["charging_points"]:
        if c["charging_point_id"] == resource_id:
            return {"resource_id": resource_id, "resource_type": "CHARGING_POINT", "hub_id": c["hub_id"],
                    "hub_name": hub_names.get(c["hub_id"], c["hub_id"]),
                    "label": _point_label(resource_id), "status": c["status"]}
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


def _impact_and_action(info: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Business impact text and the suggested next action of an incident."""
    state = get_state()
    rtype, status = info["resource_type"], info["status"]
    if rtype == "CHARGING_POINT":
        n = sum(
            1
            for s in state["charging_schedules"]
            if s.get("charging_point_id") == info["resource_id"]
            and s.get("status") not in _CLOSED_SCHEDULE_STATUSES
        )
        if n:
            impact = f"Ảnh hưởng {n} lịch sạc"
        elif status == enums.CHARGING_POINT_UNAVAILABLE:
            impact = "Giảm 1 cổng sạc khả dụng"
        else:
            impact = "Chưa ảnh hưởng vận hành"
        return impact, {"label": "Lập lịch sạc", "target": "other:Lập lịch sạc"}
    if rtype == "VEHICLE":
        if status == enums.VEHICLE_UNAVAILABLE:
            return "Thiếu hụt 1 xe", {"label": "Điều chuyển xe", "target": "dispatch"}
        if status == enums.VEHICLE_IN_USE:
            return "Chờ kết thúc chuyến", {"label": "Tổng quan mạng lưới", "target": "overview"}
        return "Chưa ảnh hưởng vận hành", {"label": "Tổng quan mạng lưới", "target": "overview"}
    if rtype == "PARKING_SPACE":
        impact = "Giảm 1 chỗ đỗ" if status == enums.PARKING_UNAVAILABLE else "Chưa ảnh hưởng vận hành"
        return impact, {"label": "Tổng quan mạng lưới", "target": "overview"}
    return "Ảnh hưởng toàn Hub", {"label": "Tổng quan mạng lưới", "target": "overview"}


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
        impact, action = _impact_and_action(info)
        views.append(
            {
                **inc,
                "resource_label": info["label"],
                "resource_type": info["resource_type"],
                "hub_id": info["hub_id"],
                "hub_name": info["hub_name"],
                "resource_status": info["status"],
                "location": "Đang trên hành trình"
                if info["status"] == enums.VEHICLE_IN_USE
                else info["hub_name"],
                "impact": impact,
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


def create_or_update_incident(
    resource_id: str,
    description: str,
    severity: str = SEVERITY_MEDIUM,
    reported_by: str | None = None,
) -> dict[str, Any]:
    """Create an incident, or update the open one of the same resource."""
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
        return _result(
            True,
            f"{info['label']} đã có sự cố đang mở ({existing['incident_id']}); đã cập nhật.",
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
    state["incidents"].append(incident)
    return _result(
        True, f"Đã ghi nhận sự cố {incident['incident_id']}.", incident=incident, created=True
    )


def resolve_incident(incident_id: str) -> dict[str, Any]:
    incident = next(
        (i for i in get_state()["incidents"] if i["incident_id"] == incident_id), None
    )
    if incident is None:
        return _result(False, f"Không tìm thấy sự cố {incident_id}.")
    if incident["status"] == INCIDENT_RESOLVED:
        return _result(False, f"Sự cố {incident_id} đã được giải quyết trước đó.")
    now = _now()
    incident["status"] = INCIDENT_RESOLVED
    incident["updated_at"] = now
    incident["resolved_at"] = now
    incident["history"].append({"at": now, "by": None, "note": "Đã giải quyết"})
    return _result(True, f"Đã đánh dấu {incident_id} là đã giải quyết.", incident=incident)