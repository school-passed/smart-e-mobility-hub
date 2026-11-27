
from __future__ import annotations

from datetime import datetime
from typing import Any

from modules.sub01 import service as sub01_service
from shared.enums import (
    CHARGING_REQUEST_PENDING,
    PARKING_AVAILABLE,
    RESERVATION_PENDING,
    VEHICLE_AVAILABLE,
    VEHICLE_CHARGING,
    VEHICLE_IN_USE,
    VEHICLE_UNAVAILABLE,
)
from shared.state import get_state

MIN_OPERATING_BATTERY_LEVEL = 20


def _now() -> datetime:
    return datetime.now().astimezone()


def _find_vehicle(state: dict[str, Any], vehicle_id: str) -> dict[str, Any] | None:
    return next((v for v in state["vehicles"] if v["vehicle_id"] == vehicle_id), None)


def _find_hub(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    return next((h for h in state["hubs"] if h["hub_id"] == hub_id), None)


def _find_trip(state: dict[str, Any], trip_id: str) -> dict[str, Any] | None:
    return next((t for t in state["trips"] if t["trip_id"] == trip_id), None)


def _available_parking_count(state: dict[str, Any], hub_id: str) -> int:
    return sum(
        1
        for p in state["parking_spaces"]
        if p["hub_id"] == hub_id and p["status"] == PARKING_AVAILABLE
    )


def _notify_sub05_incident(
    vehicle_id: str, description: str, reported_by: str, severity: str = "MEDIUM"
) -> str:
    """Forward defective vehicle report to SUB-05 if available."""
    try:
        from modules.sub05 import service as sub05_service

        create_inc = getattr(sub05_service, "create_or_update_incident", None)
        if callable(create_inc):
            res = create_inc(
                resource_id=vehicle_id,
                description=description,
                severity=severity,
                reported_by=reported_by,
            )
            return str(res.get("message", ""))
    except Exception:
        pass
    return ""


def _create_low_battery_charging_request(
    state: dict[str, Any], vehicle: dict[str, Any], now_iso: str
) -> dict[str, Any]:
    """Use SUB-04's existing shared-vehicle request contract instead of a parallel schema.

    The request intentionally has no departure_time until Operator supplies it.
    Kept ``now_iso`` in the signature for compatibility with the existing return flow.
    """
    from modules.sub04 import service as charging_service

    return charging_service.receive_shared_vehicle_charging_need(
        state,
        vehicle_id=vehicle["vehicle_id"],
        battery_level=vehicle["battery_level"],
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_active_trip(state: dict[str, Any], student_id: str) -> dict[str, Any] | None:
    """Return the currently active trip for a student, if any."""
    return next(
        (t for t in state["trips"] if t["student_id"] == student_id and t["is_active"]),
        None,
    )


def get_student_trips(state: dict[str, Any], student_id: str) -> list[dict[str, Any]]:
    """Return all trips of a student, newest first."""
    trips = [t for t in state["trips"] if t["student_id"] == student_id]
    return sorted(trips, key=lambda item: item["start_time"], reverse=True)


def get_available_vehicles_at_hub(state: dict[str, Any], hub_id: str) -> list[dict[str, Any]]:
    """Return AVAILABLE vehicles currently parked at a Hub."""
    return [
        v
        for v in state["vehicles"]
        if v["hub_id"] == hub_id and v["status"] == VEHICLE_AVAILABLE
    ]


# ---------------------------------------------------------------------------
# UC-04: Pick Up Shared Vehicle
# ---------------------------------------------------------------------------

def pickup_vehicle(
    state: dict[str, Any],
    student_id: str,
    reservation_id: str,
    vehicle_id: str,
    pickup_code: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate reservation & vehicle, consume reservation via SUB-01, start trip."""
    current_time = now or _now()
    sub01_service.expire_pending_reservations(state, current_time)

    if get_active_trip(state, student_id) is not None:
        return {
            "ok": False,
            "status": "ACTIVE_TRIP_EXISTS",
            "message": "Bạn đang có một chuyến đi chưa kết thúc. Vui lòng trả xe trước khi nhận xe mới.",
        }

    reservation = next(
        (r for r in state["reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return {"ok": False, "status": "RESERVATION_NOT_FOUND", "message": "Không tìm thấy đơn đặt chỗ."}
    if reservation["student_id"] != student_id:
        return {"ok": False, "status": "NOT_RESERVATION_OWNER", "message": "Đơn đặt chỗ không thuộc tài khoản hiện tại."}
    if reservation["status"] != RESERVATION_PENDING:
        return {
            "ok": False,
            "status": "RESERVATION_NOT_PENDING",
            "message": f"Đơn đặt chỗ không ở trạng thái PENDING (hiện tại: {reservation['status']}).",
        }
    if not pickup_code or str(pickup_code).strip() != reservation["pickup_code"]:
        return {"ok": False, "status": "INVALID_PICKUP_CODE", "message": "Mã pickup code không khớp."}

    vehicle = _find_vehicle(state, vehicle_id)
    if vehicle is None:
        return {"ok": False, "status": "VEHICLE_NOT_FOUND", "message": f"Không tìm thấy xe {vehicle_id}."}
    if vehicle["hub_id"] != reservation["hub_id"]:
        return {
            "ok": False,
            "status": "VEHICLE_AT_ANOTHER_HUB",
            "message": f"Xe {vehicle_id} đang ở {vehicle['hub_id']}, không khớp Hub đặt chỗ ({reservation['hub_id']}).",
        }
    if vehicle["status"] != VEHICLE_AVAILABLE:
        return {
            "ok": False,
            "status": "VEHICLE_NOT_AVAILABLE",
            "message": f"Xe {vehicle_id} không khả dụng (trạng thái: {vehicle['status']}).",
        }

    # Gọi SUB-01 để consume reservation và giải phóng reserved slot
    consumed, consume_msg = sub01_service.consume_reservation(state, reservation_id, current_time)
    if not consumed:
        return {"ok": False, "status": "CONSUME_FAILED", "message": consume_msg}

    # Cập nhật trạng thái xe và tạo TripRecord
    now_iso = current_time.isoformat(timespec="seconds")
    vehicle["status"] = VEHICLE_IN_USE

    trip_num = state["next_trip_number"]
    state["next_trip_number"] = trip_num + 1
    trip = {
        "trip_id": f"TRP-{trip_num:04d}",
        "reservation_id": reservation_id,
        "student_id": student_id,
        "vehicle_id": vehicle_id,
        "origin_hub_id": reservation["hub_id"],
        "destination_hub_id": None,
        "start_time": now_iso,
        "end_time": None,
        "start_battery_level": vehicle["battery_level"],
        "end_battery_level": None,
        "is_active": True,
    }
    state["trips"].append(trip)

    return {
        "ok": True,
        "status": "SUCCESS",
        "message": f"Mở khóa thành công! Bắt đầu chuyến đi {trip['trip_id']} với xe {vehicle_id}.",
        "trip": trip,
    }


def report_defective_vehicle_at_pickup(
    state: dict[str, Any],
    student_id: str,
    reservation_id: str,
    vehicle_id: str,
    issue_desc: str,
) -> dict[str, Any]:
    """Mark vehicle UNAVAILABLE, notify SUB-05, and keep reservation PENDING."""
    issue_desc = (issue_desc or "").strip()
    if not issue_desc:
        return {"ok": False, "message": "Vui lòng nhập mô tả sự cố của phương tiện."}

    sub01_service.expire_pending_reservations(state)
    reservation = next(
        (r for r in state["reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None or reservation["student_id"] != student_id:
        return {"ok": False, "message": "Đơn đặt chỗ không hợp lệ hoặc không thuộc tài khoản hiện tại."}
    if reservation["status"] != RESERVATION_PENDING:
        return {"ok": False, "message": "Đơn đặt chỗ không còn ở trạng thái PENDING."}

    vehicle = _find_vehicle(state, vehicle_id)
    if vehicle is None or vehicle["hub_id"] != reservation["hub_id"]:
        return {"ok": False, "message": "Phương tiện không tồn tại tại Hub của đơn đặt chỗ."}

    vehicle["status"] = VEHICLE_UNAVAILABLE
    inc_msg = _notify_sub05_incident(vehicle_id, f"[Pickup] {issue_desc}", reported_by=student_id)
    return {
        "ok": True,
        "message": (
            f"Đã đánh dấu xe {vehicle_id} là UNAVAILABLE và giữ nguyên đơn {reservation_id} "
            f"để bạn chọn xe khác. {inc_msg}"
        ).strip(),
    }


# ---------------------------------------------------------------------------
# UC-05: Return Shared Vehicle
# ---------------------------------------------------------------------------

def return_vehicle(
    state: dict[str, Any],
    student_id: str,
    trip_id: str,
    destination_hub_id: str,
    final_battery: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Close active trip, update vehicle hub/battery/status, trigger SUB-04 if low battery."""
    current_time = now or _now()
    trip = _find_trip(state, trip_id)
    if trip is None or not trip["is_active"]:
        return {"ok": False, "status": "ACTIVE_TRIP_NOT_FOUND", "message": "Không tìm thấy chuyến đi đang hoạt động."}
    if trip["student_id"] != student_id:
        return {"ok": False, "status": "NOT_TRIP_OWNER", "message": "Chuyến đi không thuộc tài khoản hiện tại."}

    dest_hub = _find_hub(state, destination_hub_id)
    if dest_hub is None:
        return {"ok": False, "status": "HUB_NOT_FOUND", "message": "Không tìm thấy Hub đích."}

    if _available_parking_count(state, destination_hub_id) <= 0:
        return {
            "ok": False,
            "status": "DESTINATION_HUB_FULL",
            "message": f"{dest_hub['name']} đã hết chỗ đỗ trống. Vui lòng chọn Hub lân cận.",
        }

    if not (0 <= final_battery <= 100):
        return {"ok": False, "status": "INVALID_BATTERY", "message": "Mức pin phải nằm trong khoảng 0–100%."}

    vehicle = _find_vehicle(state, trip["vehicle_id"])
    if vehicle is None:
        return {"ok": False, "status": "VEHICLE_NOT_FOUND", "message": "Không tìm thấy phương tiện của chuyến đi."}

    now_iso = current_time.isoformat(timespec="seconds")
    vehicle["hub_id"] = destination_hub_id
    vehicle["battery_level"] = int(final_battery)

    charging_request = None
    if final_battery < MIN_OPERATING_BATTERY_LEVEL:
        vehicle["status"] = VEHICLE_CHARGING
        charging_request = _create_low_battery_charging_request(state, vehicle, now_iso)
        result_status = "BATTERY_CRITICAL_ROUTED_TO_CHARGING"
        extra_msg = (
            f" Pin còn {final_battery}% (< {MIN_OPERATING_BATTERY_LEVEL}%), "
            f"xe đã chuyển sang CHARGING và gửi yêu cầu sạc {charging_request['request_id']} sang SUB-04."
        )
    else:
        vehicle["status"] = VEHICLE_AVAILABLE
        result_status = "SUCCESS"
        extra_msg = f" Xe {vehicle['vehicle_id']} đã sẵn sàng (AVAILABLE) tại {dest_hub['name']}."

    trip["destination_hub_id"] = destination_hub_id
    trip["end_time"] = now_iso
    trip["end_battery_level"] = int(final_battery)
    trip["is_active"] = False

    return {
        "ok": True,
        "status": result_status,
        "message": f"Trả xe thành công! Đã đóng chuyến đi {trip_id}.{extra_msg}",
        "trip": trip,
        "vehicle": vehicle,
        "charging_request": charging_request,
    }


def report_defective_vehicle_at_return(
    state: dict[str, Any],
    student_id: str,
    trip_id: str,
    issue_desc: str,
) -> dict[str, Any]:
    """Mark vehicle UNAVAILABLE after return and report incident to SUB-05."""
    issue_desc = (issue_desc or "").strip()
    if not issue_desc:
        return {"ok": False, "message": "Vui lòng nhập mô tả sự cố."}

    trip = _find_trip(state, trip_id)
    if trip is None:
        return {"ok": False, "message": "Không tìm thấy chuyến đi."}
    if trip["student_id"] != student_id:
        return {"ok": False, "message": "Chuyến đi không thuộc tài khoản hiện tại."}

    vehicle = _find_vehicle(state, trip["vehicle_id"])
    if vehicle is None:
        return {"ok": False, "message": "Không tìm thấy phương tiện."}

    vehicle["status"] = VEHICLE_UNAVAILABLE
    inc_msg = _notify_sub05_incident(
        vehicle["vehicle_id"], f"[Return] {issue_desc}", reported_by=student_id
    )
    return {
        "ok": True,
        "message": f"Đã ghi nhận xe {vehicle['vehicle_id']} hỏng (UNAVAILABLE). {inc_msg}".strip(),
    }


# ---------------------------------------------------------------------------
# Cross-SUB Contract for SUB-05 (Redistribution)
# ---------------------------------------------------------------------------

def relocate_vehicle(vehicle_id: str, target_hub_id: str) -> dict[str, Any]:
    """Move an AVAILABLE vehicle to another Hub (called by SUB-05 dispatch)."""
    state = get_state()
    vehicle = _find_vehicle(state, vehicle_id)
    if vehicle is None:
        return {"ok": False, "message": f"Không tìm thấy xe {vehicle_id}."}
    if _find_hub(state, target_hub_id) is None:
        return {"ok": False, "message": f"Không tìm thấy Hub đích {target_hub_id}."}
    if vehicle["status"] != VEHICLE_AVAILABLE:
        return {
            "ok": False,
            "message": f"Xe {vehicle_id} đang ở trạng thái {vehicle['status']}, không thể điều chuyển.",
        }

    vehicle["hub_id"] = target_hub_id
    return {"ok": True, "message": f"Đã chuyển xe {vehicle_id} sang {target_hub_id}."}
