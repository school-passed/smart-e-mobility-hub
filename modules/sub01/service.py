"""SUB-01 business logic: Mobility Discovery & Reservation (UC-01 to UC-03-02).

Reservation is linked to a Student and Hub slot, not to a specific vehicle
before pickup. SUB-02 calls consume_reservation() only after successful pickup.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from secrets import randbelow
from typing import Any

from shared.enums import (
    RESERVATION_CANCELLED,
    RESERVATION_CONSUMED,
    RESERVATION_EXPIRED,
    RESERVATION_PENDING,
)
from shared.state import atomic, available_vehicle, free_spaces, hub_validity

DEMO_RESERVATION_TTL_MINUTES = 30


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _find_hub(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    return next((hub for hub in state["hubs"] if hub["hub_id"] == hub_id), None)


def _active_reservations(
    state: dict[str, Any], hub_id: str | None = None
) -> list[dict[str, Any]]:
    reservations = [r for r in state["reservations"] if r["status"] == RESERVATION_PENDING]
    if hub_id is not None:
        reservations = [r for r in reservations if r["hub_id"] == hub_id]
    return reservations


def _release_hub_slot(state: dict[str, Any], hub_id: str) -> None:
    hub = _find_hub(state, hub_id)
    if hub is not None:
        hub["reserved_slot_count"] = max(0, hub["reserved_slot_count"] - 1)


@atomic
def expire_pending_reservations(
    state: dict[str, Any], now: datetime | None = None
) -> int:
    """Expire overdue PENDING reservations and release each Hub slot once."""
    current_time = now or _now()
    expired_count = 0
    for reservation in state["reservations"]:
        if reservation["status"] != RESERVATION_PENDING:
            continue
        exp = _parse_datetime(reservation["expires_at"])
        cmp_now = current_time if exp.tzinfo else current_time.replace(tzinfo=None)
        if exp <= cmp_now:
            reservation["status"] = RESERVATION_EXPIRED
            reservation["expired_at"] = current_time.isoformat(timespec="seconds")
            _release_hub_slot(state, reservation["hub_id"])
            expired_count += 1
    return expired_count


def get_hub_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Hub summaries and read-only availability counts (UC-01)."""
    expire_pending_reservations(state)
    summaries = []
    for hub in state["hubs"]:
        hub_id = hub["hub_id"]
        hub_vehicles = [v for v in state["vehicles"] if v["hub_id"] == hub_id]
        available_vehicles = sum(1 for v in hub_vehicles if available_vehicle(state, v))
        hub_spaces = [p for p in state["parking_spaces"] if p["hub_id"] == hub_id]
        available_parking = len(free_spaces(state, hub_id))
        hub_points = [cp for cp in state["charging_points"] if cp["hub_id"] == hub_id]
        available_points = sum(
            1
            for cp in hub_points
            if cp["status"] == "AVAILABLE" and not cp.get("incident_blocked")
        )
        active_res = len(_active_reservations(state, hub_id))
        uncommitted_vehicles = max(0, available_vehicles - active_res)
        slot_room = max(0, hub["reservation_capacity"] - hub["reserved_slot_count"])
        validity = hub_validity(state, hub)

        summaries.append(
            {
                **hub,
                "available_vehicle_count": available_vehicles,
                "uncommitted_vehicle_count": uncommitted_vehicles,
                "total_vehicle_count": len(hub_vehicles),
                "available_parking_space_count": available_parking,
                "total_parking_space_count": len(hub_spaces),
                "available_charging_point_count": available_points,
                "total_charging_point_count": len(hub_points),
                "available_reservation_slots": slot_room,
                "can_accept_reservation": slot_room > 0 and uncommitted_vehicles > 0 and validity != "DISCONNECTED",
                "data_validity": validity,
                "data_updated_at": hub.get("data_updated_at"),
            }
        )
    return summaries


def get_hub_details(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    """Return one Hub with current vehicle/parking/charging counts."""
    if not hub_id:
        return None
    return next((h for h in get_hub_list(state) if h["hub_id"] == hub_id), None)


def find_suitable_vehicles(
    state: dict[str, Any],
    hub_id: str | None = None,
    vehicle_type: str | None = None,
    min_battery: int = 25,
) -> list[dict[str, Any]]:
    """Find AVAILABLE vehicles matching the user's basic search criteria (UC-02)."""
    results = []
    for vehicle in state["vehicles"]:
        if not available_vehicle(state, vehicle):
            continue
        if hub_id and vehicle["hub_id"] != hub_id:
            continue
        if vehicle_type and vehicle["vehicle_type"] != vehicle_type:
            continue
        if vehicle["battery_level"] < min_battery:
            continue
        results.append(vehicle)
    return sorted(results, key=lambda item: item["battery_level"], reverse=True)


def find_suitable_hubs(
    state: dict[str, Any],
    vehicle_type: str | None = None,
    min_battery: int = 25,
) -> list[dict[str, Any]]:
    """Return Hubs that have at least one suitable AVAILABLE vehicle (UC-02)."""
    hubs = get_hub_list(state)
    suitable = []
    for hub in hubs:
        matching = find_suitable_vehicles(state, hub["hub_id"], vehicle_type, min_battery)
        if matching:
            suitable.append(
                {
                    **hub,
                    "matching_vehicle_count": len(matching),
                    "top_battery_level": matching[0]["battery_level"],
                }
            )
    return suitable


@atomic
def create_reservation(
    state: dict[str, Any],
    student_id: str,
    hub_id: str,
    ttl_minutes: int = DEMO_RESERVATION_TTL_MINUTES,
    now: datetime | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a Hub-slot reservation after checking Hub and vehicle capacity (UC-03-01)."""
    current_time = now or _now()
    expire_pending_reservations(state, current_time)

    if idempotency_key:
        existing = next(
            (
                r
                for r in state["reservations"]
                if r.get("student_id") == student_id
                and r.get("idempotency_key") == idempotency_key
            ),
            None,
        )
        if existing is not None:
            return existing

    hub = _find_hub(state, hub_id)
    if hub is None:
        raise ValueError("Không tìm thấy Mobility Hub.")
    if hub_validity(state, hub, current_time) == "DISCONNECTED":
        raise ValueError("Hub đang mất kết nối dữ liệu (DISCONNECTED), chưa thể tạo reservation.")

    available_slots = hub["reservation_capacity"] - hub["reserved_slot_count"]
    if available_slots <= 0:
        raise ValueError("Hub đã hết slot reservation.")

    available_vehicle_count = sum(
        1
        for v in state["vehicles"]
        if v["hub_id"] == hub_id and available_vehicle(state, v)
    )
    active_reservation_count = len(_active_reservations(state, hub_id))
    if available_vehicle_count - active_reservation_count <= 0:
        raise ValueError("Hub không còn đủ xe khả dụng để đáp ứng reservation mới.")

    reservation_number = len(state["reservations"]) + 1
    reservation_id = f"RSV-{reservation_number:04d}"
    pickup_code = f"{randbelow(1_000_000):06d}"
    reservation = {
        "reservation_id": reservation_id,
        "student_id": student_id,
        "hub_id": hub_id,
        "pickup_code": pickup_code,
        "created_at": current_time.isoformat(timespec="seconds"),
        "expires_at": (current_time + timedelta(minutes=ttl_minutes)).isoformat(timespec="seconds"),
        "cancelled_at": None,
        "expired_at": None,
        "consumed_at": None,
        "status": RESERVATION_PENDING,
    }
    if idempotency_key:
        reservation["idempotency_key"] = idempotency_key
    state["reservations"].append(reservation)
    hub["reserved_slot_count"] += 1
    return reservation


def get_student_reservations(
    state: dict[str, Any], student_id: str
) -> list[dict[str, Any]]:
    """Return reservations belonging to one Student, newest first."""
    expire_pending_reservations(state)
    records = [r for r in state["reservations"] if r["student_id"] == student_id]
    return sorted(records, key=lambda item: item["created_at"], reverse=True)


@atomic
def cancel_reservation(
    state: dict[str, Any],
    reservation_id: str,
    student_id: str,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Cancel a PENDING reservation owned by the requesting Student (UC-03-02)."""
    current_time = now or _now()
    expire_pending_reservations(state, current_time)
    reservation = next(
        (r for r in state["reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy reservation."
    if reservation["student_id"] != student_id:
        return False, "Reservation không thuộc tài khoản hiện tại."
    if reservation["status"] == RESERVATION_EXPIRED:
        return False, "Reservation đã hết hạn (EXPIRED); slot giữ trước đã được giải phóng."
    if reservation["status"] == RESERVATION_CONSUMED:
        return False, "Reservation đã được sử dụng để nhận xe (CONSUMED), không thể hủy."
    if reservation["status"] == RESERVATION_CANCELLED:
        return False, "Reservation này đã được hủy trước đó."
    if reservation["status"] != RESERVATION_PENDING:
        return False, f"Không thể hủy reservation ở trạng thái {reservation['status']}."

    reservation["status"] = RESERVATION_CANCELLED
    reservation["cancelled_at"] = current_time.isoformat(timespec="seconds")
    _release_hub_slot(state, reservation["hub_id"])
    return True, "Đã hủy reservation và giải phóng Hub slot."


@atomic
def consume_reservation(
    state: dict[str, Any], reservation_id: str, now: datetime | None = None
) -> tuple[bool, str]:
    """Consume a reservation after SUB-02 confirms successful pickup."""
    current_time = now or _now()
    expire_pending_reservations(state, current_time)
    reservation = next(
        (r for r in state["reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy reservation."
    if reservation["status"] != RESERVATION_PENDING:
        return False, f"Không thể consume reservation ở trạng thái {reservation['status']}."

    reservation["status"] = RESERVATION_CONSUMED
    reservation["consumed_at"] = current_time.isoformat(timespec="seconds")
    _release_hub_slot(state, reservation["hub_id"])
    return True, "Reservation đã được consume sau pickup thành công."
