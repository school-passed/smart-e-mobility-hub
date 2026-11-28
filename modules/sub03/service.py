"""SUB-03 business logic: Private EV Parking & Charging (UC-06-01 to UC-07-02).

SUB-03 owns ParkingSpace, ParkingReservation, TemporaryHold and ChargingRequest state.
Calls SUB-04 service functions safely when charging schedules need updates.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from shared.enums import (
    CHARGING_REQUEST_CANCELLED,
    CHARGING_REQUEST_CONFIRMED,
    CHARGING_REQUEST_PENDING,
    PARKING_AVAILABLE,
    PARKING_IN_USE,
    PARKING_RESERVED,
    PARKING_RESERVATION_EXPIRED,
    PARKING_UNAVAILABLE,
)
from shared.state import atomic, incoming_spaces, point_validity

TEMPORARY_HOLD_TTL_MINUTES = 5


def _now() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _resolve_clock(value: str | datetime, reference: datetime, grace_past_minutes: int = 0) -> datetime:
    """Resolve HH:MM or ISO string against ``reference`` without accidental +24h rollover."""
    if isinstance(value, datetime):
        return value.astimezone() if value.tzinfo else value.replace(tzinfo=reference.tzinfo)
    text = str(value or "").strip()
    if not text:
        raise ValueError("Thiếu thông tin thời gian.")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.astimezone() if parsed.tzinfo else parsed.replace(tzinfo=reference.tzinfo)
    except ValueError:
        pass
    try:
        clk = time.fromisoformat(text)
    except ValueError:
        raise ValueError(f"Định dạng giờ '{text}' không hợp lệ (cần HH:MM).") from None

    candidate = datetime.combine(reference.date(), clk, reference.tzinfo)
    floor_ref = reference.replace(second=0, microsecond=0) - timedelta(minutes=grace_past_minutes)
    if candidate < floor_ref:
        candidate += timedelta(days=1)
    return candidate


def _parking_window(reservation, now):
    created = _resolve_clock(reservation["created_at"], now)
    arrival = _resolve_clock(reservation.get("start_iso") or reservation["start_time"], created)
    departure = _resolve_clock(reservation.get("end_iso") or reservation["end_time"], arrival)
    return arrival, departure


@atomic
def expire_unused_parking_reservations(state, now=None):
    """Release booked spaces after the end of a reservation with no check-in."""
    now = now or _now()
    for reservation in state["parking_reservations"]:
        if reservation["status"] != PARKING_RESERVED or _parking_window(reservation, now)[1] > now:
            continue
        ok, _, _ = _release_charging(state, reservation["reservation_id"])
        if not ok:
            continue
        space = _find_space(state, reservation["space_id"])
        if space and space["status"] == PARKING_RESERVED:
            space["status"] = PARKING_UNAVAILABLE if space.get("incident_blocked") else PARKING_AVAILABLE
        reservation["status"] = PARKING_RESERVATION_EXPIRED
        reservation["expired_at"] = now.isoformat(timespec="seconds")


def _find_space(state: dict[str, Any], space_id: str) -> dict[str, Any] | None:
    return next((s for s in state["parking_spaces"] if s["space_id"] == space_id), None)


def _find_hub(state: dict[str, Any], hub_id: str) -> dict[str, Any] | None:
    return next((h for h in state["hubs"] if h["hub_id"] == hub_id), None)


def _notify_sub04_receive(state: dict[str, Any], request_id: str) -> None:
    """Safely notify SUB-04 about a new PENDING charging request."""
    try:
        from modules.sub04 import service as sub04_service

        if hasattr(sub04_service, "receive_charging_request"):
            try:
                sub04_service.receive_charging_request(state, request_id)
            except TypeError:
                sub04_service.receive_charging_request(request_id)
    except Exception:
        pass


def _notify_sub04_cancel(state: dict[str, Any], request_id: str) -> tuple[bool, str]:
    """Safely ask SUB-04 to release any confirmed charging schedule/allocation."""
    try:
        from modules.sub04 import service as sub04_service

        for fn_name in ("cancel_charging_request", "cancel_charging_schedule"):
            if hasattr(sub04_service, fn_name):
                fn = getattr(sub04_service, fn_name)
                try:
                    res = fn(state, request_id)
                except TypeError:
                    res = fn(request_id)
                if isinstance(res, tuple) and len(res) == 2:
                    return bool(res[0]), str(res[1])
                return True, "Đã giải phóng lịch sạc bên SUB-04."
    except Exception as exc:
        return False, f"Lỗi khi liên hệ SUB-04: {exc}"

    for sch in state.get("charging_schedules", []):
        if sch.get("request_id") == request_id and sch.get("status") not in ("IN_USE", "COMPLETED", "CANCELLED"):
            sch["status"] = "CANCELLED"
    return True, "Đã cập nhật trạng thái hủy yêu cầu sạc."


@atomic
def clean_expired_holds(state: dict[str, Any], now: datetime | None = None) -> int:
    """Remove expired 5-minute temporary holds on every interaction."""
    current_time = now or _now()
    holds = state.setdefault("temporary_holds", [])
    active_holds = []
    expired_count = 0
    for hold in holds:
        exp = _parse_datetime(hold["expires_at"])
        cmp_now = current_time if exp.tzinfo else current_time.replace(tzinfo=None)
        if exp <= cmp_now:
            expired_count += 1
        else:
            active_holds.append(hold)
    state["temporary_holds"] = active_holds
    return expired_count


def get_active_hold_for_student(state: dict[str, Any], student_id: str) -> dict[str, Any] | None:
    """Return the active (unexpired) temporary hold belonging to a student, if any."""
    clean_expired_holds(state)
    return next(
        (h for h in state.setdefault("temporary_holds", []) if h["student_id"] == student_id),
        None,
    )


def get_parking_spaces_by_hub(
    state: dict[str, Any],
    hub_id: str,
    only_available: bool = False,
    only_with_charger: bool = False,
) -> list[dict[str, Any]]:
    """List parking spaces at a Hub, reflecting holds, dispatch locks, and incidents."""
    clean_expired_holds(state)
    student_held_ids = {h["space_id"] for h in state.setdefault("temporary_holds", [])}
    dispatch_held_ids = incoming_spaces(state)

    results = []
    for space in state["parking_spaces"]:
        if space["hub_id"] != hub_id:
            continue
        if only_with_charger and not space["has_charger"]:
            continue

        if space.get("incident_blocked") or space["status"] == PARKING_UNAVAILABLE:
            effective_status = PARKING_UNAVAILABLE
        elif space["status"] == PARKING_AVAILABLE and space["space_id"] in student_held_ids:
            effective_status = "HELD (5m)"
        elif space["status"] == PARKING_AVAILABLE and space["space_id"] in dispatch_held_ids:
            effective_status = "HELD (Điều chuyển)"
        else:
            effective_status = space["status"]

        if only_available and effective_status != PARKING_AVAILABLE:
            continue

        results.append({**space, "effective_status": effective_status})
    return results


def get_reference_charging_availability(state: dict[str, Any], hub_id: str) -> dict[str, Any]:
    """Read-only reference charging availability at a Hub before submitting UC-07-01."""
    points = [p for p in state.get("charging_points", []) if p.get("hub_id") == hub_id]
    usable_points = [
        p
        for p in points
        if p.get("status") in ("AVAILABLE", "RESERVED")
        and not p.get("incident_blocked")
        and point_validity(p) == "VALID"
    ]
    available_now = [
        p
        for p in points
        if p.get("status") == "AVAILABLE"
        and not p.get("incident_blocked")
        and point_validity(p) == "VALID"
    ]
    active_schedules = [
        s
        for s in state.get("charging_schedules", [])
        if s.get("hub_id") == hub_id and s.get("status") in ("CONFIRMED", "IN_USE")
    ]
    hub = _find_hub(state, hub_id) or {}
    cap_kw = hub.get("charging_capacity_kw") or sum(float(p.get("power_kw", 0)) for p in points)
    return {
        "total_points": len(points),
        "usable_points": len(usable_points),
        "available_now_points": len(available_now),
        "active_schedules": len(active_schedules),
        "capacity_kw": cap_kw,
    }


# ---------------------------------------------------------------------------
# UC-06-01: Reserve Parking Space (Temporary Hold -> Confirm)
# ---------------------------------------------------------------------------

@atomic
def create_temporary_hold(
    state: dict[str, Any], space_id: str, student_id: str, now: datetime | None = None
) -> dict[str, Any]:
    """Hold an AVAILABLE parking space for 5 minutes."""
    current_time = now or _now()
    expire_unused_parking_reservations(state, current_time)
    clean_expired_holds(state, current_time)

    existing_hold = get_active_hold_for_student(state, student_id)
    if existing_hold is not None:
        raise ValueError(
            f"Bạn đang giữ tạm ô {existing_hold['space_id']}. Hãy xác nhận hoặc hủy phiên giữ tạm hiện tại trước."
        )

    space = _find_space(state, space_id)
    if space is None:
        raise ValueError("Không tìm thấy ô đỗ xe.")
    if space.get("incident_blocked") or space["status"] != PARKING_AVAILABLE:
        raise ValueError(f"Ô đỗ {space_id} hiện không trống (trạng thái: {space['status']}).")

    held_space_ids = {h["space_id"] for h in state.setdefault("temporary_holds", [])}
    if space_id in held_space_ids or space_id in incoming_spaces(state):
        raise ValueError(f"Ô đỗ {space_id} đang được giữ tạm hoặc chờ xe điều chuyển đến.")

    hold_id = f"HOLD-{space_id}-{int(current_time.timestamp()) % 10000:04d}"
    hold = {
        "hold_id": hold_id,
        "space_id": space_id,
        "hub_id": space["hub_id"],
        "has_charger": space["has_charger"],
        "student_id": student_id,
        "created_at": current_time.isoformat(timespec="seconds"),
        "expires_at": (current_time + timedelta(minutes=TEMPORARY_HOLD_TTL_MINUTES)).isoformat(timespec="seconds"),
    }
    state["temporary_holds"].append(hold)
    return hold


@atomic
def release_temporary_hold(
    state: dict[str, Any], hold_id: str, student_id: str
) -> tuple[bool, str]:
    """Cancel a temporary hold manually before it expires."""
    clean_expired_holds(state)
    holds = state.setdefault("temporary_holds", [])
    hold = next((h for h in holds if h["hold_id"] == hold_id), None)
    if hold is None:
        return False, "Phiên giữ tạm không tồn tại hoặc đã hết hạn."
    if hold["student_id"] != student_id:
        return False, "Bạn không có quyền hủy phiên giữ tạm này."

    state["temporary_holds"] = [h for h in holds if h["hold_id"] != hold_id]
    return True, f"Đã hủy giữ tạm ô {hold['space_id']}."


@atomic
def confirm_parking_reservation(
    state: dict[str, Any],
    hold_id: str,
    student_id: str,
    license_plate: str,
    start_time: str,
    end_time: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Confirm a valid temporary hold into an official ParkingReservation."""
    current_time = now or _now()
    clean_expired_holds(state, current_time)

    holds = state.setdefault("temporary_holds", [])
    hold = next((h for h in holds if h["hold_id"] == hold_id), None)
    if hold is None:
        raise ValueError("Phiên giữ chỗ 5 phút đã hết hạn hoặc không tồn tại. Vui lòng giữ chỗ lại.")
    if hold["student_id"] != student_id:
        raise ValueError("Phiên giữ chỗ này không thuộc tài khoản của bạn.")
    if not (license_plate or "").strip():
        raise ValueError("Vui lòng nhập biển số xe điện cá nhân.")

    space = _find_space(state, hold["space_id"])
    if space is None or space.get("incident_blocked") or space["status"] != PARKING_AVAILABLE:
        state["temporary_holds"] = [h for h in holds if h["hold_id"] != hold_id]
        raise ValueError("Ô đỗ không còn khả dụng để xác nhận.")

    # Resolve same-day shifts (e.g. 12:00 - 18:00 booked at 15:05) on today when end is still ahead
    try:
        s_clk = time.fromisoformat(str(start_time).strip())
        e_clk = time.fromisoformat(str(end_time).strip())
        today_start = datetime.combine(current_time.date(), s_clk, current_time.tzinfo)
        today_end = datetime.combine(current_time.date(), e_clk, current_time.tzinfo)
        if today_end <= today_start:
            today_end += timedelta(days=1)
        if today_end > current_time:
            arrival, departure = today_start, today_end
        else:
            arrival = today_start + timedelta(days=1)
            departure = today_end + timedelta(days=1)
    except ValueError:
        arrival = _resolve_clock(start_time, current_time, grace_past_minutes=120)
        departure = _resolve_clock(end_time, arrival, grace_past_minutes=0)
    if departure <= arrival or departure <= current_time:
        raise ValueError("Khung giờ đỗ không hợp lệ (giờ rời đi phải sau giờ đến và ở tương lai).")

    number = state.get("next_parking_reservation_number", len(state["parking_reservations"]) + 1)
    state["next_parking_reservation_number"] = number + 1
    reservation_id = f"PRSV-{number:04d}"

    hub = _find_hub(state, space["hub_id"])
    reservation = {
        "reservation_id": reservation_id,
        "student_id": student_id,
        "hub_id": space["hub_id"],
        "hub_name": hub["name"] if hub else space["hub_id"],
        "space_id": space["space_id"],
        "has_charger": space["has_charger"],
        "license_plate": license_plate.strip().upper(),
        "start_time": start_time,
        "end_time": end_time,
        "start_iso": arrival.isoformat(timespec="seconds"),
        "end_iso": departure.isoformat(timespec="seconds"),
        "status": PARKING_RESERVED,
        "created_at": current_time.isoformat(timespec="seconds"),
        "checked_in_at": None,
        "checked_out_at": None,
        "cancelled_at": None,
    }

    space["status"] = PARKING_RESERVED
    state["parking_reservations"].append(reservation)
    state["temporary_holds"] = [h for h in holds if h["hold_id"] != hold_id]
    return reservation


def get_student_parking_reservations(
    state: dict[str, Any], student_id: str
) -> list[dict[str, Any]]:
    """Return all parking reservations belonging to a student, newest first."""
    records = [r for r in state["parking_reservations"] if r["student_id"] == student_id]
    return sorted(records, key=lambda item: item["created_at"], reverse=True)


# ---------------------------------------------------------------------------
# UC-06-02: Cancel Parking Reservation (with Cascading Charging Cancellation)
# ---------------------------------------------------------------------------

@atomic
def cancel_parking_reservation(
    state: dict[str, Any], reservation_id: str, student_id: str
) -> tuple[bool, str]:
    """Cancel a RESERVED parking reservation, release space, and cascade cancel linked charging requests."""
    reservation = next(
        (r for r in state["parking_reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy phiếu đặt chỗ đỗ."
    if reservation["student_id"] != student_id:
        return False, "Phiếu đặt chỗ này không thuộc tài khoản của bạn."
    expire_unused_parking_reservations(state)
    if reservation["status"] == "CANCELLED":
        return True, f"Phiếu đặt chỗ {reservation_id} đã ở trạng thái CANCELLED."
    if reservation["status"] != PARKING_RESERVED:
        return False, f"Chỉ có thể hủy phiếu ở trạng thái RESERVED (hiện tại: {reservation['status']})."

    ok, message, cascaded_count = _release_charging(state, reservation_id)
    if not ok:
        return False, message

    reservation["status"] = "CANCELLED"
    reservation["cancelled_at"] = _now().isoformat(timespec="seconds")

    space = _find_space(state, reservation["space_id"])
    if space is not None and space["status"] == PARKING_RESERVED:
        space["status"] = PARKING_UNAVAILABLE if space.get("incident_blocked") else PARKING_AVAILABLE

    extra_msg = f" (Đã tự động hủy kèm {cascaded_count} yêu cầu sạc liên quan)." if cascaded_count else "."
    return True, f"Đã hủy phiếu đặt chỗ {reservation_id} và trả lại ô {reservation['space_id']}{extra_msg}"


# ---------------------------------------------------------------------------
# UC-06-03: Check-in / Check-out (Simulated Sensor Events)
# ---------------------------------------------------------------------------

@atomic
def check_in_vehicle(
    state: dict[str, Any], reservation_id: str, student_id: str
) -> tuple[bool, str]:
    """Simulate parking sensor / user check-in: RESERVED -> IN_USE."""
    reservation = next(
        (r for r in state["parking_reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy phiếu đặt chỗ."
    if reservation["student_id"] != student_id:
        return False, "Phiếu đặt chỗ không thuộc tài khoản hiện tại."
    if reservation["status"] != PARKING_RESERVED:
        return False, f"Không thể Check-in khi phiếu đang ở trạng thái {reservation['status']}."

    now = _now()
    arrival, departure = _parking_window(reservation, now)
    if now >= departure:
        expire_unused_parking_reservations(state, now)
    if not arrival <= now < departure:
        return False, "Check-in chỉ được phép trong khung giờ của phiếu đỗ."

    space = _find_space(state, reservation["space_id"])
    if not space or space.get("incident_blocked") or space["status"] != PARKING_RESERVED:
        return False, "Ô đỗ đang gặp sự cố bảo trì, vui lòng hủy phiếu và chọn ô khác."

    reservation["status"] = PARKING_IN_USE
    reservation["checked_in_at"] = now.isoformat(timespec="seconds")
    space["status"] = PARKING_IN_USE

    return True, f"Check-in thành công tại ô {reservation['space_id']}. Trạng thái chuyển sang IN_USE."


@atomic
def check_out_vehicle(
    state: dict[str, Any], reservation_id: str, student_id: str
) -> tuple[bool, str]:
    """Simulate parking sensor / user check-out: IN_USE -> COMPLETED and release space to AVAILABLE."""
    reservation = next(
        (r for r in state["parking_reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        return False, "Không tìm thấy phiếu đặt chỗ."
    if reservation["student_id"] != student_id:
        return False, "Phiếu đặt chỗ không thuộc tài khoản hiện tại."
    if reservation["status"] != PARKING_IN_USE:
        return False, f"Chỉ có thể Check-out khi xe đang đỗ (IN_USE). Hiện tại: {reservation['status']}."

    ok, message, _ = _release_charging(state, reservation_id)
    if not ok:
        return False, message

    reservation["status"] = "COMPLETED"
    reservation["checked_out_at"] = _now().isoformat(timespec="seconds")

    space = _find_space(state, reservation["space_id"])
    if space is not None:
        space["status"] = PARKING_UNAVAILABLE if space.get("incident_blocked") else PARKING_AVAILABLE

    return True, f"Check-out thành công! Ô đỗ {reservation['space_id']} đã được trả về trạng thái AVAILABLE."


# ---------------------------------------------------------------------------
# UC-07-01 & UC-07-02: Charging Request Creation & Cancellation
# ---------------------------------------------------------------------------

@atomic
def create_charging_request(
    state: dict[str, Any],
    reservation_id: str,
    student_id: str,
    current_battery: int,
    target_battery: int,
    departure_time: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """Create a PENDING ChargingRequest linked to a valid charger-equipped parking reservation."""
    reservation = next(
        (r for r in state["parking_reservations"] if r["reservation_id"] == reservation_id),
        None,
    )
    if reservation is None:
        raise ValueError("Không tìm thấy phiếu đặt chỗ đỗ tương ứng.")
    if reservation["student_id"] != student_id:
        raise ValueError("Phiếu đặt chỗ không thuộc tài khoản của bạn.")
    if reservation["status"] not in (PARKING_RESERVED, PARKING_IN_USE):
        raise ValueError("Chỉ có thể gửi yêu cầu sạc cho phiếu đỗ đang RESERVED hoặc IN_USE.")

    space = _find_space(state, reservation["space_id"])
    if space is None or not space["has_charger"]:
        raise ValueError(f"Ô đỗ {reservation['space_id']} không hỗ trợ trụ sạc cho xe cá nhân.")

    if not (0 <= current_battery < target_battery <= 100):
        raise ValueError("Mức pin mục tiêu phải lớn hơn mức pin hiện tại và nằm trong khoảng 1% – 100%.")

    duplicate = next(
        (
            req
            for req in state["charging_requests"]
            if req["reservation_id"] == reservation_id
            and req["status"] in (CHARGING_REQUEST_PENDING, CHARGING_REQUEST_CONFIRMED)
        ),
        None,
    )
    if duplicate is not None:
        raise ValueError(f"Phiếu đỗ này đã có yêu cầu sạc đang hoạt động ({duplicate['request_id']}).")

    created = _now()
    res_created = _parse_datetime(reservation["created_at"])
    parked_from = (
        _parse_datetime(reservation["start_iso"])
        if reservation.get("start_iso")
        else _resolve_clock(reservation["start_time"], res_created, grace_past_minutes=120)
    )
    parked_until = (
        _parse_datetime(reservation["end_iso"])
        if reservation.get("end_iso")
        else _resolve_clock(reservation["end_time"], parked_from, grace_past_minutes=0)
    )
    if str(departure_time).strip() == str(reservation.get("end_time", "")).strip() and parked_until > created:
        departure = parked_until
    else:
        departure = _resolve_clock(departure_time, max(created, parked_from), grace_past_minutes=0)
    if departure <= created:
        raise ValueError("Giờ dự kiến lấy xe phải ở tương lai.")

    number = state.get("next_charging_request_number", len(state["charging_requests"]) + 1)
    state["next_charging_request_number"] = number + 1
    request_id = f"CHRQ-{number:04d}"

    charging_request: dict[str, Any] = {
        "request_id": request_id,
        "reservation_id": reservation_id,
        "student_id": student_id,
        "hub_id": reservation["hub_id"],
        "space_id": reservation["space_id"],
        "license_plate": reservation["license_plate"],
        "current_battery": int(current_battery),
        "target_battery": int(target_battery),
        "departure_time": departure.isoformat(timespec="seconds"),
        "status": CHARGING_REQUEST_PENDING,
        "created_at": created.isoformat(timespec="seconds"),
        "cancelled_at": None,
    }
    if start_time or end_time:
        if not (start_time and end_time):
            raise ValueError("Vui lòng nhập cả giờ bắt đầu và giờ kết thúc khung sạc mong muốn (hoặc để trống cả hai).")
        start = _resolve_clock(start_time, created, grace_past_minutes=0)
        end = _resolve_clock(end_time, start, grace_past_minutes=0)
        if start <= created or not (parked_from <= start < end <= min(parked_until, departure)):
            raise ValueError("Khung sạc mong muốn phải ở tương lai, nằm trong khung giờ đỗ và trước giờ lấy xe.")
        charging_request.update(
            start_time=start.isoformat(timespec="seconds"),
            end_time=end.isoformat(timespec="seconds"),
        )

    state["charging_requests"].append(charging_request)
    _notify_sub04_receive(state, request_id)
    return charging_request


def get_student_charging_requests(
    state: dict[str, Any], student_id: str
) -> list[dict[str, Any]]:
    """Return all charging requests submitted by a student, newest first."""
    records = [r for r in state["charging_requests"] if r["student_id"] == student_id]
    return sorted(records, key=lambda item: item["created_at"], reverse=True)


@atomic
def cancel_charging_request(
    state: dict[str, Any], request_id: str, student_id: str
) -> tuple[bool, str]:
    """Cancel a PENDING or CONFIRMED charging request (coordinating with SUB-04 if confirmed)."""
    req = next((r for r in state["charging_requests"] if r["request_id"] == request_id), None)
    if req is None:
        return False, "Không tìm thấy yêu cầu sạc."
    if req["student_id"] != student_id:
        return False, "Yêu cầu sạc này không thuộc tài khoản của bạn."
    if req["status"] == CHARGING_REQUEST_CANCELLED:
        return True, f"Yêu cầu sạc {request_id} đã ở trạng thái CANCELLED trước đó."
    if req["status"] not in (CHARGING_REQUEST_PENDING, CHARGING_REQUEST_CONFIRMED):
        return False, f"Không thể hủy yêu cầu sạc ở trạng thái {req['status']}."

    ok, msg = _notify_sub04_cancel(state, request_id)
    if not ok:
        return False, msg

    req["status"] = CHARGING_REQUEST_CANCELLED
    req["cancelled_at"] = _now().isoformat(timespec="seconds")
    return True, f"Đã hủy yêu cầu sạc {request_id} thành công."


def _release_charging(state: dict[str, Any], reservation_id: str) -> tuple[bool, str, int]:
    """UC-07 permits one outstanding request per reservation."""
    for req in state["charging_requests"]:
        if req["reservation_id"] == reservation_id and req["status"] in ("PENDING", "CONFIRMED"):
            ok, message = _notify_sub04_cancel(state, req["request_id"])
            if ok:
                req["status"] = CHARGING_REQUEST_CANCELLED
                req["cancelled_at"] = req.get("cancelled_at") or _now().isoformat(timespec="seconds")
            return ok, message, int(ok)
    return True, "", 0
