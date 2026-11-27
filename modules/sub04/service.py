"""Smart charging service. Times are local ISO datetimes, intervals are [start, end).

A confirmed schedule is the allocation record (point, interval and kW).
Private requests are shared with SUB-03. Shared-vehicle needs live separately
because they do not have a parking reservation or a student owner.
"""
from datetime import datetime, time, timedelta
from math import isfinite
from threading import RLock

from shared.enums import (
    CHARGING_POINT_AVAILABLE, CHARGING_POINT_IN_USE, CHARGING_POINT_RESERVED,
    CHARGING_POINT_UNAVAILABLE, CHARGING_REQUEST_CANCELLED,
    CHARGING_REQUEST_CONFIRMED, CHARGING_REQUEST_PENDING,
)

_LOCK = RLock()
ACTIVE = ("CONFIRMED", "IN_USE")


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
    """Resolve SUB-03 HH:MM on the anchor date, rolling overnight when needed."""
    if isinstance(value, datetime):
        return value.astimezone()
    try:
        return datetime.fromisoformat(value).astimezone()
    except (TypeError, ValueError):
        pass
    try:
        clock = time.fromisoformat(value)
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
                if departure_time and req["status"] == "PENDING":
                    req["departure_time"] = departure_time
                return req.copy()
        req = dict(request_id=f"SHRQ-{len(needs)+1:04d}", hub_id=vehicle["hub_id"],
                   vehicle_id=vehicle_id, current_battery=battery_level,
                   departure_time=departure_time, created_at=_now().isoformat(),
                   status=CHARGING_REQUEST_PENDING)
        needs.append(req)
        return req.copy()


def _priority(req):
    level = _number(req.get("current_battery"), "mức pin")
    if level > 100:
        raise ValueError("Mức pin phải trong khoảng 0–100%.")
    created = _date(req.get("created_at"))
    return level, _date(req.get("departure_time"), created), created


def get_pending_charging_requests(state, hub_id=None):
    with _LOCK:
        return [r.copy() for r in _requests(state) if r["status"] == CHARGING_REQUEST_PENDING
                and (hub_id is None or r["hub_id"] == hub_id)]


def prioritize_charging_requests(state, hub_id):
    ranked, incomplete = [], []
    for req in get_pending_charging_requests(state, hub_id):
        try:
            ranked.append((_priority(req), req))
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


def _window(state, req, start, end):
    _, departure, created = _priority(req)
    earliest = (_now() + timedelta(minutes=1)).replace(second=0, microsecond=0)
    latest = departure
    if req.get("reservation_id"):
        parking = _find(state["parking_reservations"], "reservation_id", req["reservation_id"])
        if parking["status"] not in ("RESERVED", "IN_USE") or parking["hub_id"] != req["hub_id"]:
            raise ValueError("Phiếu đỗ đã đóng hoặc khác Hub.")
        space = _find(state["parking_spaces"], "space_id", parking["space_id"])
        if not space["has_charger"] or space["hub_id"] != req["hub_id"] or req.get("space_id", space["space_id"]) != space["space_id"]:
            raise ValueError("Ô đỗ không phù hợp với yêu cầu sạc.")
        arrival = _date(parking["start_time"], _date(parking.get("created_at", created)))
        latest = min(latest, _date(parking["end_time"], arrival))
        earliest = max(earliest, arrival)
    elif not req.get("vehicle_id"):
        raise ValueError("Thiếu phiếu đỗ của xe cá nhân.")
    requested_start = req.get("start_time")
    requested_end = req.get("end_time")
    if requested_start is not None:
        requested_start = _date(requested_start, created)
        if start is not None and _date(start) != requested_start:
            raise ValueError("Lịch phải giữ đúng giờ bắt đầu yêu cầu.")
        start = requested_start
    if requested_end is not None:
        requested_end = _date(requested_end, requested_start or created)
        if end is not None and _date(end) != requested_end:
            raise ValueError("Lịch phải giữ đúng giờ kết thúc yêu cầu.")
        end = requested_end
    start = _date(start) if start is not None else earliest
    end = _date(end) if end is not None else latest
    if start < earliest or end <= start or end > latest:
        raise ValueError("Khung giờ sạc đã qua hoặc nằm ngoài thời gian đỗ/lấy xe.")
    return start, end


def _check_point(state, req, point, start, end, starting_schedule=None):
    schedules = [s for s in state["charging_schedules"]
                 if s["hub_id"] == req["hub_id"] and s["status"] in ACTIVE]
    point_id = point["charging_point_id"]
    owned = [s for s in schedules if s["charging_point_id"] == point_id]
    status = point["status"]
    if status != CHARGING_POINT_AVAILABLE and not (status == CHARGING_POINT_RESERVED and owned):
        raise ValueError("Trụ đang bận hoặc ngừng hoạt động.")
    if point.get("allocation_blocked") or point.get("data_validity", "VALID") != "VALID":
        raise ValueError("Trụ bị khóa hoặc dữ liệu chưa hợp lệ.")
    if req.get("connector_type") and req["connector_type"] != point.get("connector_type"):
        raise ValueError("Đầu nối không tương thích.")
    power = _number(point["power_kw"], "công suất trụ")
    if power <= 0:
        raise ValueError("Công suất trụ phải lớn hơn 0.")
    # A seeded busy point has no known finish. Reserve its rated load throughout.
    busy_ids = {s["charging_point_id"] for s in schedules if s["status"] == "IN_USE"}
    load = power + sum(p["power_kw"] for p in _hub_points(state, req["hub_id"])
                       if p["status"] == CHARGING_POINT_IN_USE and p["charging_point_id"] not in busy_ids)
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


def _candidate(state, req, start=None, end=None, point_id=None):
    if req["status"] != CHARGING_REQUEST_PENDING:
        raise ValueError("Yêu cầu không còn chờ xếp lịch.")
    start, end = _window(state, req, start, end)
    reasons = []
    for p in _hub_points(state, req["hub_id"]):
        if point_id and point_id != p["charging_point_id"]:
            continue
        try:
            power = _check_point(state, req, p, start, end)
            return dict(charging_point_id=p["charging_point_id"], power_kw=power,
                        start_time=start.isoformat(), end_time=end.isoformat())
        except ValueError as exc:
            reasons.append(str(exc))
    raise ValueError(" ".join(dict.fromkeys(reasons)) or "Không có trụ phù hợp tại Hub.")


def propose_charging_schedule(state, request_id, start_time=None, end_time=None):
    """Store an operator-reviewable proposal. Proposals do not reserve any power."""
    with _LOCK:
        req = _find(_requests(state), "request_id", request_id)
        candidate = _candidate(state, req, start_time, end_time)
        schedules = state["charging_schedules"]
        for s in schedules:
            if s["request_id"] == request_id and s["status"] == "PROPOSED":
                s.update(candidate)
                return s.copy()
        n = state["next_charging_schedule_number"]
        schedule = dict(schedule_id=f"CS-{n:04d}", request_id=request_id, hub_id=req["hub_id"],
                        status="PROPOSED", progress=0, **candidate)
        schedules.append(schedule)
        state["next_charging_schedule_number"] = n + 1
        return schedule.copy()


def confirm_charging_schedule(state, schedule_id):
    with _LOCK:
        s = _find(state["charging_schedules"], "schedule_id", schedule_id)
        if s["status"] == "CONFIRMED":
            return s.copy()
        if s["status"] != "PROPOSED":
            raise ValueError("Chỉ có thể xác nhận lịch đề xuất.")
        req = _find(_requests(state), "request_id", s["request_id"])
        candidate = _candidate(state, req, s["start_time"], s["end_time"], s["charging_point_id"])
        if candidate["power_kw"] != s["power_kw"]:
            raise ValueError("Công suất đã thay đổi. Hãy tạo lại đề xuất.")
        point = _find(state["charging_points"], "charging_point_id", s["charging_point_id"])
        s["status"] = "CONFIRMED"
        req["status"] = CHARGING_REQUEST_CONFIRMED
        point["status"] = CHARGING_POINT_RESERVED
        return s.copy()


def _refresh_point(state, point_id):
    p = _find(state["charging_points"], "charging_point_id", point_id)
    if p["status"] == CHARGING_POINT_UNAVAILABLE:
        return
    statuses = {s["status"] for s in state["charging_schedules"] if s["charging_point_id"] == point_id}
    if "IN_USE" in statuses:
        p["status"] = CHARGING_POINT_IN_USE
    elif "CONFIRMED" in statuses:
        p["status"] = CHARGING_POINT_RESERVED
    else:
        p["status"] = CHARGING_POINT_AVAILABLE


def cancel_charging_schedule(state, request_id):
    """SUB-03 cancellation contract. Only release an allocation before its start."""
    with _LOCK:
        try:
            req = _find(_requests(state), "request_id", request_id)
        except ValueError as exc:
            return False, str(exc)
        schedules = [s for s in state["charging_schedules"] if s["request_id"] == request_id]
        for s in schedules:
            if s["status"] in ("IN_USE", "COMPLETED") or (
                s["status"] == "CONFIRMED" and _now() >= _date(s["start_time"])
            ):
                return False, "Lịch đã bắt đầu, không thể hủy."
        for s in schedules:
            held = s["status"] == "CONFIRMED"
            s["status"] = "CANCELLED"
            if held:
                _refresh_point(state, s["charging_point_id"])
        req["status"] = CHARGING_REQUEST_CANCELLED
        req["cancelled_at"] = req.get("cancelled_at") or _now().isoformat()
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
                raise ValueError("Khung giờ sạc đã kết thúc.")
            p = _find(state["charging_points"], "charging_point_id", s["charging_point_id"])
            if p["status"] != CHARGING_POINT_RESERVED:
                raise ValueError("Trụ chưa sẵn sàng bắt đầu phiên.")
            if req["status"] != CHARGING_REQUEST_CONFIRMED:
                raise ValueError("Yêu cầu sạc không còn hiệu lực.")
            power = _check_point(state, req, p, now, _date(s["end_time"]), starting_schedule=s)
            if power != s["power_kw"]:
                raise ValueError("Công suất trụ đã thay đổi từ khi xác nhận.")
            if req.get("reservation_id"):
                parking = _find(state["parking_reservations"], "reservation_id", req["reservation_id"])
                if parking["status"] != "IN_USE":
                    raise ValueError("Xe cá nhân phải check-in trước khi bắt đầu sạc.")
        s["progress"] = value
        s["status"] = "COMPLETED" if value == 100 else "IN_USE"
        if value == 100 and req.get("vehicle_id"):
            req["status"] = "COMPLETED"
        _refresh_point(state, s["charging_point_id"])
        return s.copy()


def get_charging_resources(state, hub_id):
    with _LOCK:
        schedules = []
        for s in state["charging_schedules"]:
            if s["hub_id"] != hub_id:
                continue
            # SUB-03 can cancel a pending request directly, before allocation.
            if s["status"] == "PROPOSED":
                req = _find(_requests(state), "request_id", s["request_id"])
                if req["status"] == CHARGING_REQUEST_CANCELLED:
                    s["status"] = "CANCELLED"
            schedules.append(s.copy())
        return dict(points=[p.copy() for p in _hub_points(state, hub_id)],
                    capacity_kw=_capacity(state, hub_id), schedules=schedules)


def preview_charging_schedule(state, request_id):
    """Preview the default window without changing the queue or allocating a point."""
    with _LOCK:
        return _candidate(state, _find(_requests(state), "request_id", request_id))

def set_shared_departure(state, request_id, departure):
    with _LOCK:
        req = _find(state.get("shared_charging_requests", []), "request_id", request_id)
        if req["status"] != CHARGING_REQUEST_PENDING:
            raise ValueError("Yêu cầu không còn chờ xếp lịch.")
        value = _date(departure, _date(req["created_at"]))
        if value <= _now():
            raise ValueError("Giờ cần xe phải ở tương lai.")
        req["departure_time"] = value.isoformat()
