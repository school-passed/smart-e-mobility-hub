"""Smart charging service (SUB-04: UC-08, UC-09, UC-10).

Times are local ISO datetimes, intervals are [start, end).
A confirmed schedule is the allocation record (point, interval and kW).
Private requests are shared with SUB-03. Shared-vehicle needs live separately
because they do not have a parking reservation or a student owner.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time, timedelta
from math import isfinite

from shared.enums import (
    CHARGING_POINT_AVAILABLE,
    CHARGING_POINT_IN_USE,
    CHARGING_POINT_RESERVED,
    CHARGING_POINT_UNAVAILABLE,
    CHARGING_REQUEST_CANCELLED,
    CHARGING_REQUEST_CONFIRMED,
    CHARGING_REQUEST_PENDING,
)
from shared.state import STATE_LOCK as _LOCK, hub_validity, point_validity

ACTIVE = ("CONFIRMED", "IN_USE")
PRIORITY_BATTERY_THRESHOLD = 30


def _now():
    return datetime.now().astimezone()


def _find(rows, key, value):
    for row in rows:
        if row.get(key) == value:
            return row
    raise ValueError(f"Không tìm thấy {key} = {value}.")


def _requests(state):
    return [*state["charging_requests"], *state.get("shared_charging_requests", [])]


def _date(value, anchor=None):
    """Resolve HH:MM on the anchor date, rolling overnight when needed."""
    if isinstance(value, datetime):
        return value.astimezone() if value.tzinfo else value.replace(tzinfo=_now().tzinfo)
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed.astimezone() if parsed.tzinfo else parsed.replace(tzinfo=_now().tzinfo)
    except (TypeError, ValueError):
        pass
    try:
        clock = time.fromisoformat(str(value))
        if anchor is None:
            raise ValueError
        result = datetime.combine(anchor.date(), clock, anchor.tzinfo)
        if result < anchor.replace(second=0, microsecond=0):
            result += timedelta(days=1)
        return result
    except (TypeError, ValueError):
        raise ValueError("Thiếu hoặc sai thời gian.") from None


def _number(value, label):
    try:
        result = float(value)
        if not isfinite(result) or result < 0 or isinstance(value, bool):
            raise ValueError
        return result
    except (TypeError, ValueError):
        raise ValueError(f"Thiếu hoặc sai {label}.") from None


def receive_charging_request(state, request_id):
    """Acknowledge an existing SUB-03 record without duplicating it."""
    with _LOCK:
        return _find(state["charging_requests"], "request_id", request_id).copy()


def receive_shared_vehicle_charging_need(state, vehicle_id, battery_level, departure_time=None):
    """SUB-02 return hook. A retry reuses the outstanding need for this vehicle."""
    with _LOCK:
        vehicle = _find(state["vehicles"], "vehicle_id", vehicle_id)
        needs = state.setdefault("shared_charging_requests", [])
        for req in needs:
            if req["vehicle_id"] == vehicle_id and req["status"] in ("PENDING", "CONFIRMED"):
                req["current_battery"] = battery_level
                req["hub_id"] = vehicle["hub_id"]
                if departure_time and req["status"] == "PENDING":
                    req["departure_time"] = departure_time
                return req.copy()
        req = dict(
            request_id=f"SHRQ-{len(needs) + 1:04d}",
            hub_id=vehicle["hub_id"],
            vehicle_id=vehicle_id,
            current_battery=battery_level,
            target_battery=100,
            departure_time=departure_time,
            created_at=_now().isoformat(timespec="seconds"),
            status=CHARGING_REQUEST_PENDING,
        )
        needs.append(req)
        return req.copy()


def _priority(req):
    level = _number(req.get("current_battery"), "mức pin")
    if level > 100:
        raise ValueError("Mức pin phải trong khoảng 0–100%.")
    created = _date(req.get("created_at"))
    departure = req.get("departure_time")
    if not departure and not req.get("end_time"):
        raise ValueError("Thiếu giờ cần xe hoặc khung giờ sạc.")
    return level, _date(departure or req["end_time"], created), created


def describe_priority_reason(req: dict) -> str:
    """Return human-readable priority rule criterion (FR-04-08 / Submission 2 Hình 59)."""
    bat = req.get("current_battery")
    has_dep = bool(req.get("departure_time"))
    if isinstance(bat, (int, float)) and bat < PRIORITY_BATTERY_THRESHOLD:
        criterion = "Dùng gần" if has_dep else "FIFO"
        return f"Pin thấp (<{PRIORITY_BATTERY_THRESHOLD}%) + {criterion}"
    return "Giờ dùng gần + FIFO" if has_dep else "Gửi yêu cầu sớm (FIFO)"


def get_pending_charging_requests(state, hub_id=None):
    with _LOCK:
        return [
            r.copy()
            for r in _requests(state)
            if r["status"] == CHARGING_REQUEST_PENDING
            and (hub_id is None or r["hub_id"] == hub_id)
        ]


def prioritize_charging_requests(state, hub_id):
    ranked, incomplete = [], []
    hub = next((h for h in state.get("hubs", []) if h.get("hub_id") == hub_id), None)
    hub_data_state = hub.get("data_validity", "VALID") if hub else "VALID"
    for req in get_pending_charging_requests(state, hub_id):
        if hub_data_state in ("STALE", "DISCONNECTED"):
            incomplete.append(
                dict(req, reason=f"Dữ liệu Hub đang ở trạng thái {hub_data_state}")
            )
            continue
        if req.get("data_validity", "VALID") != "VALID":
            incomplete.append(
                dict(req, reason=f"Dữ liệu yêu cầu {req.get('data_validity')}")
            )
            continue
        try:
            battery, departure, created = _priority(req)
            enriched = dict(req, priority_reason=describe_priority_reason(req))
            ranked.append(
                (
                    (
                        battery >= PRIORITY_BATTERY_THRESHOLD,
                        not bool(req.get("departure_time")),
                        departure if req.get("departure_time") else created,
                        created,
                    ),
                    enriched,
                )
            )
        except ValueError as exc:
            incomplete.append(dict(req, reason=str(exc)))
    ranked.sort(key=lambda item: item[0])
    return [req for _, req in ranked], incomplete


def _hub_points(state, hub_id):
    return [p for p in state["charging_points"] if p["hub_id"] == hub_id]


def _capacity(state, hub_id):
    hub = _find(state["hubs"], "hub_id", hub_id)
    limit = hub.get("charging_capacity_kw")
    if limit is None:
        limit = sum(_number(p["power_kw"], "công suất trụ") for p in _hub_points(state, hub_id))
    return _number(limit, "giới hạn công suất Hub")


def _validate_request_resources(state, req, require_check_in=False):
    hub = _find(state["hubs"], "hub_id", req["hub_id"])
    if hub.get("data_validity", "VALID") != "VALID" or req.get("data_validity", "VALID") != "VALID":
        raise ValueError("Dữ liệu yêu cầu hoặc Hub chưa đủ tin cậy để cấp trụ sạc.")
    if req.get("reservation_id"):
        parking = _find(state["parking_reservations"], "reservation_id", req["reservation_id"])
        space = _find(state["parking_spaces"], "space_id", parking["space_id"])
        if parking["status"] not in ("RESERVED", "IN_USE") or parking["hub_id"] != req["hub_id"]:
            raise ValueError("Phiếu đỗ đã đóng hoặc khác Hub.")
        if (not space["has_charger"] or space["hub_id"] != req["hub_id"]
                or req.get("space_id", space["space_id"]) != space["space_id"]
                or space.get("incident_blocked") or space["status"] == "UNAVAILABLE"):
            raise ValueError("Ô đỗ không khả dụng hoặc không phù hợp với yêu cầu sạc.")
        if require_check_in and parking["status"] != "IN_USE":
            raise ValueError("Xe cá nhân phải check-in trước khi bắt đầu sạc.")
        return parking

    if not req.get("vehicle_id"):
        raise ValueError("Thiếu phiếu đỗ của xe cá nhân.")
    vehicle = _find(state["vehicles"], "vehicle_id", req["vehicle_id"])
    if vehicle["hub_id"] != req["hub_id"] or vehicle.get("incident_blocked") or vehicle["status"] in ("IN_USE", "UNAVAILABLE"):
        raise ValueError("Xe dùng chung đang được sử dụng, bị khóa hoặc không còn ở Hub đặt lịch.")
    return None


def _window(state, req, start, end, allow_current_minute=False):
    _, departure, created = _priority(req)
    now = _now()
    default_earliest = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    min_allowed = now.replace(second=0, microsecond=0) if allow_current_minute else default_earliest
    earliest = default_earliest
    latest = departure

    parking = _validate_request_resources(state, req)
    if parking:
        arrival = (
            _date(parking["start_iso"])
            if parking.get("start_iso")
            else _date(parking["start_time"], _date(parking.get("created_at", created)))
        )
        park_end = (
            _date(parking["end_iso"])
            if parking.get("end_iso")
            else _date(parking["end_time"], arrival)
        )
        latest = min(latest, park_end)
        earliest = max(earliest, arrival)
        min_allowed = max(min_allowed, arrival)

    requested_start = req.get("start_time")
    requested_end = req.get("end_time")
    if requested_start is not None:
        requested_start = _date(requested_start, created)
        if start is not None and _date(start, created) != requested_start:
            raise ValueError("Lịch phải giữ đúng giờ bắt đầu yêu cầu.")
        start = requested_start
    if requested_end is not None:
        requested_end = _date(requested_end, requested_start or created)
        if end is not None and _date(end, requested_start or created) != requested_end:
            raise ValueError("Lịch phải giữ đúng giờ kết thúc yêu cầu.")
        end = requested_end

    start = _date(start, now) if start is not None else earliest
    end = _date(end, start) if end is not None else latest
    if start < min_allowed or end <= start or end > latest:
        raise ValueError("Khung giờ sạc đã qua hoặc nằm ngoài thời gian đỗ/lấy xe.")
    return start, end


def _check_point(state, req, point, start, end, starting_schedule=None):
    schedules = [
        s
        for s in state["charging_schedules"]
        if s["hub_id"] == req["hub_id"] and s["status"] in ACTIVE
    ]
    point_id = point["charging_point_id"]
    owned = [s for s in schedules if s["charging_point_id"] == point_id]
    status = point["status"]
    if status != CHARGING_POINT_AVAILABLE and not (status == CHARGING_POINT_RESERVED and owned):
        raise ValueError("Trụ đang bận hoặc ngừng hoạt động.")
    if point.get("incident_blocked") or point.get("allocation_blocked") or point_validity(point) != "VALID":
        raise ValueError("Trụ bị khóa hoặc dữ liệu chưa hợp lệ.")
    if req.get("connector_type") and req["connector_type"] != point.get("connector_type"):
        raise ValueError("Đầu nối không tương thích.")
    power = _number(point["power_kw"], "công suất trụ")
    if power <= 0:
        raise ValueError("Công suất trụ phải lớn hơn 0.")
    busy_ids = {s["charging_point_id"] for s in schedules if s["status"] == "IN_USE"}
    load = power + sum(
        p["power_kw"]
        for p in _hub_points(state, req["hub_id"])
        if p["status"] == CHARGING_POINT_IN_USE and p["charging_point_id"] not in busy_ids
    )
    events = {start: 0.0}
    for s in schedules:
        if s is starting_schedule:
            continue
        left = max(start, _date(s["start_time"]))
        right = min(end, _date(s["end_time"])) if s["status"] != "IN_USE" else end
        if left >= right:
            continue
        if s["charging_point_id"] == point_id:
            raise ValueError("Trùng lịch trên cùng trụ.")
        events[left] = events.get(left, 0) + s["power_kw"]
        events[right] = events.get(right, 0) - s["power_kw"]
    limit = _capacity(state, req["hub_id"])
    for instant in sorted(events):
        load += events[instant]
        if instant < end and load > limit + 1e-9:
            raise ValueError("Vượt giới hạn công suất Hub.")
    return power


def _candidate(state, req, start=None, end=None, point_id=None, allow_current_minute=False):
    if req["status"] != CHARGING_REQUEST_PENDING:
        raise ValueError("Yêu cầu không còn chờ xếp lịch.")
    start, end = _window(state, req, start, end, allow_current_minute=allow_current_minute)
    reasons = []
    for p in _hub_points(state, req["hub_id"]):
        if point_id and point_id != p["charging_point_id"]:
            continue
        try:
            power = _check_point(state, req, p, start, end)
            return dict(
                charging_point_id=p["charging_point_id"],
                power_kw=power,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
            )
        except ValueError as exc:
            reasons.append(str(exc))
    raise ValueError(" ".join(dict.fromkeys(reasons)) or "Không có trụ phù hợp tại Hub.")


def propose_charging_schedule(state, request_id, start_time=None, end_time=None, point_id=None):
    """Store an operator-reviewable proposal. Proposals do not reserve any power."""
    with _LOCK:
        req = _find(_requests(state), "request_id", request_id)
        candidate = _candidate(state, req, start_time, end_time, point_id=point_id)
        schedules = state["charging_schedules"]
        for s in schedules:
            if s["request_id"] == request_id and s["status"] == "PROPOSED":
                s.update(candidate)
                return s.copy()
        n = state["next_charging_schedule_number"]
        schedule = dict(
            schedule_id=f"CS-{n:04d}",
            request_id=request_id,
            hub_id=req["hub_id"],
            status="PROPOSED",
            progress=0,
            **candidate,
        )
        schedules.append(schedule)
        state["next_charging_schedule_number"] = n + 1
        return schedule.copy()


def confirm_charging_schedule(state, schedule_id, idempotency_key=None):
    with _LOCK:
        s = _find(state["charging_schedules"], "schedule_id", schedule_id)
        if s["status"] == "CONFIRMED":
            return s.copy()
        if s["status"] != "PROPOSED":
            raise ValueError("Chỉ có thể xác nhận lịch đề xuất.")
        req = _find(_requests(state), "request_id", s["request_id"])
        candidate = _candidate(
            state,
            req,
            s["start_time"],
            s["end_time"],
            s["charging_point_id"],
            allow_current_minute=True,
        )
        if candidate["power_kw"] != s["power_kw"]:
            raise ValueError("Công suất đã thay đổi. Hãy tạo lại đề xuất.")
        point = _find(state["charging_points"], "charging_point_id", s["charging_point_id"])
        s["status"] = "CONFIRMED"
        s["confirmed_at"] = _now().isoformat(timespec="seconds")
        if idempotency_key:
            s["idempotency_key"] = idempotency_key
        req["status"] = CHARGING_REQUEST_CONFIRMED
        point["status"] = CHARGING_POINT_RESERVED
        return s.copy()


def _refresh_point(state, point_id):
    p = _find(state["charging_points"], "charging_point_id", point_id)
    statuses = {
        s["status"]
        for s in state["charging_schedules"]
        if s["charging_point_id"] == point_id
    }
    if "IN_USE" in statuses:
        p["status"] = CHARGING_POINT_IN_USE
    elif p.get("incident_blocked") or p["status"] == CHARGING_POINT_UNAVAILABLE:
        p["status"] = CHARGING_POINT_UNAVAILABLE
    elif "CONFIRMED" in statuses:
        p["status"] = CHARGING_POINT_RESERVED
    else:
        p["status"] = CHARGING_POINT_AVAILABLE


def _close_request(state, req, now):
    req["status"] = CHARGING_REQUEST_CANCELLED
    req["cancelled_at"] = now.isoformat(timespec="seconds")
    if req.get("vehicle_id"):
        vehicle = _find(state["vehicles"], "vehicle_id", req["vehicle_id"])
        departure = req.get("departure_time")
        if departure and _date(departure, _date(req["created_at"])) <= now:
            departure = None
        follow_up = receive_shared_vehicle_charging_need(
            state, vehicle["vehicle_id"], vehicle["battery_level"], departure
        )
        req["follow_up_request_id"] = follow_up["request_id"]


def _close_schedule(state, schedule, status, now):
    schedule["status"] = status
    schedule["closed_at"] = now.isoformat(timespec="seconds")
    schedule.pop("replacement", None)
    _refresh_point(state, schedule["charging_point_id"])


def expire_unused_schedules(state, request_id=None):
    """Release elapsed allocations that never entered an active session."""
    with _LOCK:
        now = _now()
        expired = 0
        for schedule in state["charging_schedules"]:
            if request_id is not None and schedule["request_id"] != request_id:
                continue
            if schedule["status"] != "CONFIRMED" or _date(schedule["end_time"]) > now:
                continue
            req = _find(_requests(state), "request_id", schedule["request_id"])
            _close_schedule(state, schedule, "EXPIRED", now)
            if req["status"] == CHARGING_REQUEST_CONFIRMED:
                _close_request(state, req, now)
            expired += 1
        return expired


def interrupt_charging_session(state, schedule_id):
    """Close an interrupted session without treating the battery as fully charged."""
    with _LOCK:
        schedule = _find(state["charging_schedules"], "schedule_id", schedule_id)
        if schedule["status"] == "INTERRUPTED":
            return schedule.copy()
        if schedule["status"] != "IN_USE":
            raise ValueError("Chỉ có thể ngắt phiên sạc đang hoạt động.")
        req = _find(_requests(state), "request_id", schedule["request_id"])
        now = _now()
        _close_schedule(state, schedule, "INTERRUPTED", now)
        _close_request(state, req, now)
        return schedule.copy()


def cancel_charging_schedule(state, request_id):
    """Cancel a request before its confirmed allocation begins."""
    with _LOCK:
        try:
            req = _find(_requests(state), "request_id", request_id)
        except ValueError as exc:
            return False, str(exc)
        expire_unused_schedules(state, request_id)
        if req["status"] == CHARGING_REQUEST_CANCELLED:
            return True, "Yêu cầu sạc đã đóng trước đó."
        now = _now()
        schedules = [s for s in state["charging_schedules"] if s["request_id"] == request_id]
        for s in schedules:
            if s["status"] in ("IN_USE", "COMPLETED") or (
                s["status"] == "CONFIRMED" and now >= _date(s["start_time"])
            ):
                return False, "Lịch đã bắt đầu, không thể hủy."
        for s in schedules:
            if s["status"] == "CONFIRMED":
                _close_schedule(state, s, "CANCELLED", now)
            elif s["status"] == "PROPOSED":
                s["status"] = "CANCELLED"
        _close_request(state, req, now)
        if req.get("follow_up_request_id"):
            return True, f"Đã hủy lịch. Xe vẫn cần sạc, mã chờ mới là {req['follow_up_request_id']}."
        return True, "Đã hủy yêu cầu sạc."


cancel_charging_request = cancel_charging_schedule


def update_charging_progress(state, schedule_id, progress):
    with _LOCK:
        s = _find(state["charging_schedules"], "schedule_id", schedule_id)
        value = _number(progress, "tiến độ")
        if s["status"] == "COMPLETED" and value == 100:
            return s.copy()
        if s["status"] not in ACTIVE or not s["progress"] <= value <= 100:
            raise ValueError("Lịch hoặc tiến độ không hợp lệ.")
        now = _now()
        if now < _date(s["start_time"]):
            raise ValueError("Chưa tới giờ bắt đầu sạc.")
        req = _find(_requests(state), "request_id", s["request_id"])
        if s["status"] == "CONFIRMED":
            if now >= _date(s["end_time"]):
                expire_unused_schedules(state, s["request_id"])
                raise ValueError("Khung giờ sạc đã kết thúc. Lịch và phân bổ đã được đóng.")
            _validate_request_resources(state, req, require_check_in=True)
            p = _find(state["charging_points"], "charging_point_id", s["charging_point_id"])
            if p["status"] != CHARGING_POINT_RESERVED:
                raise ValueError("Trụ chưa sẵn sàng bắt đầu phiên.")
            if req["status"] != CHARGING_REQUEST_CONFIRMED:
                raise ValueError("Yêu cầu sạc không còn hiệu lực.")
            power = _check_point(state, req, p, now, _date(s["end_time"]), starting_schedule=s)
            if power != s["power_kw"]:
                raise ValueError("Công suất trụ đã thay đổi từ khi xác nhận.")
        if value == 100 and req.get("vehicle_id"):
            from modules.sub02.service import finish_vehicle_charging

            finish_vehicle_charging(state, req["vehicle_id"], req.get("target_battery", 100))
        s["progress"] = value
        s["status"] = "COMPLETED" if value == 100 else "IN_USE"
        if value == 100:
            req["status"] = "COMPLETED"
        _refresh_point(state, s["charging_point_id"])
        return s.copy()


def get_charging_resources(state, hub_id):
    with _LOCK:
        points_by_id = {p["charging_point_id"]: p for p in _hub_points(state, hub_id)}
        reqs_by_id = {r["request_id"]: r for r in _requests(state)}
        schedules = []
        for s in state["charging_schedules"]:
            if s["hub_id"] != hub_id:
                continue
            req = reqs_by_id.get(s["request_id"], {})
            if s["status"] == "PROPOSED" and req.get("status") == CHARGING_REQUEST_CANCELLED:
                schedules.append(dict(s, status="CANCELLED", needs_reschedule=False))
                continue
            pt = points_by_id.get(s["charging_point_id"], {})
            affected = s["status"] == "CONFIRMED" and (
                pt.get("status") == "UNAVAILABLE" or bool(pt.get("incident_blocked"))
            )
            vehicle_label = req.get("vehicle_id") or req.get("license_plate") or "—"
            schedules.append(
                dict(
                    s,
                    needs_reschedule=affected,
                    vehicle_label=vehicle_label,
                    current_battery=req.get("current_battery"),
                )
            )
        points_out = []
        for p in _hub_points(state, hub_id):
            points_out.append(dict(p, effective_validity=point_validity(p)))
        hub = _find(state["hubs"], "hub_id", hub_id)
        return dict(
            points=points_out,
            capacity_kw=_capacity(state, hub_id),
            schedules=schedules,
            hub_validity=hub_validity(state, hub),
        )


def preview_charging_schedule(state, request_id):
    """Preview the default window without changing the queue or allocating a point."""
    with _LOCK:
        return _candidate(state, _find(_requests(state), "request_id", request_id))


def set_shared_departure(state, request_id, departure):
    with _LOCK:
        req = _find(state.get("shared_charging_requests", []), "request_id", request_id)
        if req["status"] != CHARGING_REQUEST_PENDING:
            raise ValueError("Yêu cầu không còn chờ xếp lịch.")
        value = _date(departure, max(_now(), _date(req["created_at"])))
        if value <= _now():
            raise ValueError("Giờ cần xe phải ở tương lai.")
        req["departure_time"] = value.isoformat(timespec="seconds")


def replace_charging_point(state, schedule_id, confirm=False):
    """Keep the original allocation until the reviewed replacement is confirmed (FR-04-14)."""
    with _LOCK:
        schedule = _find(state["charging_schedules"], "schedule_id", schedule_id)
        points = state["charging_points"]
        old = _find(points, "charging_point_id", schedule["charging_point_id"])
        if schedule["status"] != "CONFIRMED" or (
            not old.get("incident_blocked") and old["status"] != "UNAVAILABLE"
        ):
            raise ValueError("Lịch không cần đổi trụ.")
        req = _find(_requests(state), "request_id", schedule["request_id"])
        _validate_request_resources(state, req)
        now_floor = _now().replace(second=0, microsecond=0)
        sched_start = max(_date(schedule["start_time"]), now_floor)
        sched_end = _date(schedule["end_time"])
        if sched_end <= sched_start:
            raise ValueError("Khung giờ sạc của lịch này đã kết thúc, không thể đổi trụ.")

        proposal = schedule.get("replacement")
        for point in _hub_points(state, req["hub_id"]):
            pid = point["charging_point_id"]
            if pid == old["charging_point_id"] or (confirm and pid != proposal):
                continue
            try:
                power = _check_point(state, req, point, sched_start, sched_end, starting_schedule=schedule)
            except ValueError:
                continue
            if confirm:
                schedule.update(
                    charging_point_id=pid,
                    power_kw=power,
                    start_time=sched_start.isoformat(),
                )
                point["status"] = CHARGING_POINT_RESERVED
                schedule.pop("replacement", None)
                _refresh_point(state, old["charging_point_id"])
            else:
                schedule["replacement"] = pid
            return schedule.copy()
        raise ValueError("Chưa có trụ thay thế đủ điều kiện trong khung giờ này.")


def propose_queue(state, hub_id):
    """Reserve candidates in a private planning copy, then publish draft rows only."""
    with _LOCK:
        trial = deepcopy(state)
        ranked, incomplete = prioritize_charging_requests(trial, hub_id)
        waiting = {r["request_id"]: r["reason"] for r in incomplete}
        drafts = []
        for req in ranked:
            rid = req["request_id"]
            try:
                draft = propose_charging_schedule(trial, rid)
                confirm_charging_schedule(trial, draft["schedule_id"])
            except ValueError as exc:
                waiting[rid] = str(exc)
                continue
            schedules = state["charging_schedules"]
            old = next(
                (s for s in schedules if s["request_id"] == rid and s["status"] == "PROPOSED"),
                None,
            )
            if old:
                old.update(draft)
            else:
                schedules.append(draft)
            drafts.append(draft.copy())
        state["next_charging_schedule_number"] = trial["next_charging_schedule_number"]
        return drafts, waiting


def confirm_charging_plan(state, drafts, idempotency_key):
    """Commit all reviewed drafts together after validating them against current allocations."""
    if not drafts or not idempotency_key:
        raise ValueError("Chưa có phương án để xác nhận.")
    with _LOCK:
        comparison_fields = ("schedule_id", "request_id", "charging_point_id", "power_kw", "start_time", "end_time")
        fingerprint = tuple(tuple(row[field] for field in comparison_fields) for row in drafts)
        confirmed_plans = state.get("charging_plan_confirmations", {})
        if idempotency_key in confirmed_plans:
            previous = confirmed_plans[idempotency_key]
            if previous["fingerprint"] != fingerprint:
                raise ValueError("Phương án đã thay đổi. Hãy tạo và xem lại phương án mới.")
            return deepcopy(previous["schedules"])

        trial = deepcopy(state)
        results = []
        schedules = state["charging_schedules"]
        for draft in drafts:
            sid = draft["schedule_id"]
            current = _find(schedules, "schedule_id", sid)
            if current["status"] != "PROPOSED" or any(current[f] != draft[f] for f in comparison_fields):
                raise ValueError("Phương án đã thay đổi. Hãy tạo và xem lại phương án mới.")
            results.append(confirm_charging_schedule(trial, sid, idempotency_key))

        for result in results:
            schedule = _find(schedules, "schedule_id", result["schedule_id"])
            request = _find(_requests(state), "request_id", result["request_id"])
            point = _find(state["charging_points"], "charging_point_id", result["charging_point_id"])
            schedule.update(result)
            request["status"] = CHARGING_REQUEST_CONFIRMED
            point["status"] = CHARGING_POINT_RESERVED
        state.setdefault("charging_plan_confirmations", {})[idempotency_key] = {
            "fingerprint": fingerprint,
            "schedules": deepcopy(results),
        }
        return results


def monitor_window(state, hub_id, start, end):
    with _LOCK:
        start, end = _date(start), _date(end)
        if end <= start:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu.")
        resources = get_charging_resources(state, hub_id)
        events = {}
        slots = []
        for point in resources["points"]:
            allocations = [
                s
                for s in resources["schedules"]
                if s["charging_point_id"] == point["charging_point_id"]
                and s["status"] in ACTIVE
                and _date(s["start_time"]) < end
                and _date(s["end_time"]) > start
            ]
            for s in allocations:
                left = max(start, _date(s["start_time"]))
                right = min(end, _date(s["end_time"]))
                events[left] = events.get(left, 0) + s["power_kw"]
                events[right] = events.get(right, 0) - s["power_kw"]
            validity = point_validity(point)
            status = point["status"]
            if validity != "VALID":
                slot_status = validity
            elif status in ("AVAILABLE", "RESERVED"):
                slot_status = "RESERVED" if allocations else "AVAILABLE"
            else:
                slot_status = status
            slots.append(
                {
                    "Trụ sạc": point["charging_point_id"],
                    "Công suất (kW)": point["power_kw"],
                    "Trạng thái khung giờ": slot_status,
                    "Lịch phân bổ": ", ".join(s["schedule_id"] for s in allocations) or "—",
                    "Độ tin cậy dữ liệu": validity,
                    "Cập nhật cuối": point.get("data_updated_at") or "Trực tuyến",
                }
            )
        total = peak = 0.0
        for instant in sorted(events):
            total += events[instant]
            peak = max(peak, total)
        used = sum(
            p.get("measured_kw", p["power_kw"])
            for p in resources["points"]
            if p["status"] == "IN_USE"
        )
        return slots, peak, used
