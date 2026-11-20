"""SUB-01 business logic: Mobility Discovery & Reservation.

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
    VEHICLE_AVAILABLE,
)

# Demo-only assumption. Confirm the exact reservation duration against the
# group's final requirements before the final demo.
DEMO_RESERVATION_TTL_MINUTES = 30


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _find_hub(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    return next((hub for hub in state["hubs"] if hub["hub_id"] == hub_id), None)


def _active_reservations(state: dict[str, Any], hub_id: str | None = None) -> list[dict[str, Any]]:
    reservations = [r for r in state["reservations"] if r["status"] == RESERVATION_PENDING]
    if hub_id is not None:
        reservations = [r for r in reservations if r["hub_id"] == hub_id]
    return reservations


def _release_hub_slot(state: dict[str, Any], hub_id: str) -> None:
    hub = _find_hub(state, hub_id)
    if hub is not None:
        hub["reserved_slot_count"] = max(0, hub["reserved_slot_count"] - 1)


def expire_pending_reservations(
    state: dict[str, Any], now: datetime | None = None
) -> int:
    """Expire overdue PENDING reservations and release each Hub slot once."""
    current_time = now or _now()
    expired_count = 0
    for reservation in state["reservations"]:
        if reservation["status"] != RESERVATION_PENDING:
            continue
        if _parse_datetime(reservation["expires_at"]) <= current_time:
            reservation["status"] = RESERVATION_EXPIRED
            reservation["expired_at"] = current_time.isoformat(timespec="seconds")
            _release_hub_slot(state, reservation["hub_id"])
            expired_count += 1
    return expired_count


def get_hub_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Hub summaries and read-only availability counts."""
    expire_pending_reservations(state)
    summaries = []
    for hub in state["hubs"]:
        hub_id = hub["hub_id"]
        available_vehicles = sum(
            1 for v in state["vehicles"]
            if v["hub_id"] == hub_id and v["status"] == VEHICLE_AVAILABLE
        )
        available_parking = sum(
            1 for p in state["parking_spaces"]
            if p["hub_id"] == hub_id and p["status"] == "AVAILABLE"
        )
        summaries.append(
            {
                **hub,
                "available_vehicle_count": available_vehicles,
                "available_parking_space_count": available_parking,
                "available_reservation_slots": max(
                    0, hub["reservation_capacity"] - hub["reserved_slot_count"]
                ),
            }
        )
    return summaries


def get_hub_details(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    """Return one Hub with current vehicle/parking counts."""
    return next((h for h in get_hub_list(state) if h["hub_id"] == hub_id), None)


def find_suitable_vehicles(
    state: dict[str, Any],
    hub_id: str | None = None,
    vehicle_type: str | None = None,
    min_battery: int = 25,
) -> list[dict[str, Any]]:
    """Find AVAILABLE vehicles matching the user's basic search criteria."""
    results = []
    for vehicle in state["vehicles"]:
        if vehicle["status"] != VEHICLE_AVAILABLE:
            continue
        if hub_id and vehicle["hub_id"] != hub_id:
            continue
        if vehicle_type and vehicle["vehicle_type"] != vehicle_type:
            continue
        if vehicle["battery_level"] < min_battery:
            continue
        results.append(vehicle)
    return sorted(results, key=lambda item: item["battery_level"], reverse=True)


def create_reservation(
    state: dict[str, Any],
    student_id: str,
    hub_id: str,
    ttl_minutes: int = DEMO_RESERVATION_TTL_MINUTES,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a Hub-slot reservation after checking Hub and vehicle capacity."""
    current_time = now or _now()
    expire_pending_reservations(state, current_time)

    hub = _find_hub(state, hub_id)
    if hub is None:
        raise ValueError("Không tìm thấy Mobility Hub.")

    available_slots = hub["reservation_capacity"] - hub["reserved_slot_count"]
    if available_slots <= 0:
        raise ValueError("Hub đã hết slot reservation.")

    available_vehicle_count = sum(
        1 for v in state["vehicles"]
        if v["hub_id"] == hub_id and v["status"] == VEHICLE_AVAILABLE
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


def cancel_reservation(
    state: dict[str, Any], reservation_id: str, student_id: str
) -> tuple[bool, str]:
    """Cancel a PENDING reservation owned by the requesting Student."""
    expire_pending_reservations(state)
    reservation = next(
        (r for r in state["reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy reservation."
    if reservation["student_id"] != student_id:
        return False, "Reservation không thuộc tài khoản hiện tại."
    if reservation["status"] == RESERVATION_EXPIRED:
        return False, "Reservation đã hết hạn."
    if reservation["status"] != RESERVATION_PENDING:
        return False, f"Không thể hủy reservation ở trạng thái {reservation['status']}."

    reservation["status"] = RESERVATION_CANCELLED
    reservation["cancelled_at"] = _now().isoformat(timespec="seconds")
    _release_hub_slot(state, reservation["hub_id"])
    return True, "Đã hủy reservation và giải phóng Hub slot."


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
