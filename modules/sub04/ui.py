"""Streamlit operator screens for charging resources, priority and scheduling."""
from datetime import datetime

import streamlit as st

from modules.sub04 import service
from shared.enums import ROLE_OPERATOR


def _local(value):
    return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")


def _action(fn, message, *args):
    try:
        result = fn(*args)
        if isinstance(result, tuple) and not result[0]:
            st.error(result[1])
            return
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state["sub04_notice"] = message
    st.rerun()


def _resources(data):
    points = data["points"]
    a, b, c = st.columns(3)
    a.metric("Trụ khả dụng", f"{sum(p['status'] == 'AVAILABLE' for p in points)} / {len(points)}")
    b.metric("Giới hạn công suất Hub", f"{data['capacity_kw']:g} kW")
    c.metric("Trụ đang sạc", sum(p["status"] == "IN_USE" for p in points))
    st.dataframe([
        {"Trụ": p["charging_point_id"], "Trạng thái": p["status"], "Công suất (kW)": p["power_kw"],
         "Lịch đã giữ": ", ".join(s["schedule_id"] for s in data["schedules"]
                                 if s["charging_point_id"] == p["charging_point_id"] and s["status"] in service.ACTIVE)}
        for p in points
    ], hide_index=True, use_container_width=True)


def _queue(state, hub_id):
    ranked, incomplete = service.prioritize_charging_requests(state, hub_id)
    st.caption("Ưu tiên pin thấp, sau đó đến giờ cần xe sớm hơn, rồi đến yêu cầu gửi trước.")
    rows = []
    for rank, req in enumerate(ranked, 1):
        try:
            preview = service.preview_charging_schedule(state, req["request_id"])
            availability = f"Có thể xếp tại {preview['charging_point_id']}"
        except ValueError as exc:
            availability = str(exc)
        rows.append({"Ưu tiên": rank, "Yêu cầu": req["request_id"], "Pin (%)": req["current_battery"],
                     "Giờ cần xe": req["departure_time"], "Khả năng xếp lịch": availability})
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
        selected = st.selectbox("Yêu cầu cần lập lịch", [r["request_id"] for r in ranked])
        if st.button("Đề xuất lịch", type="primary"):
            _action(service.propose_charging_schedule, "Đã tạo đề xuất. Xem và xác nhận trong mục Lịch sạc.",
                    state, selected)
    else:
        st.info("Chưa có yêu cầu đủ dữ liệu trong hàng chờ tại Hub này.")
    if incomplete:
        st.subheader("Yêu cầu thiếu dữ liệu")
        st.dataframe([{"Yêu cầu": r["request_id"], "Lý do": r["reason"]} for r in incomplete],
                     hide_index=True, use_container_width=True)
        shared = {r["request_id"]: r for r in incomplete if r.get("vehicle_id") and not r.get("departure_time")}
        if shared:
            rid = st.selectbox("Xe dùng chung cần bổ sung giờ sử dụng", list(shared))
            departure = st.text_input("Giờ cần xe (HH:MM hoặc YYYY-MM-DD HH:MM)", key=f"departure_{rid}")
            if st.button("Lưu giờ cần xe"):
                _action(service.set_shared_departure, "Đã cập nhật giờ cần xe.", state, rid, departure)


def _schedules(state, schedules):
    if not schedules:
        st.info("Hub này chưa có lịch sạc.")
        return
    st.dataframe([
        {"Lịch": s["schedule_id"], "Yêu cầu": s["request_id"], "Trụ": s["charging_point_id"],
         "Bắt đầu": _local(s["start_time"]), "Kết thúc": _local(s["end_time"]),
         "kW": s["power_kw"], "Trạng thái": s["status"], "Tiến độ (%)": s["progress"]}
        for s in reversed(schedules)
    ], use_container_width=True, hide_index=True)
    active = {s["schedule_id"]: s for s in schedules if s["status"] in ("PROPOSED", *service.ACTIVE)}
    if not active:
        return
    sid = st.selectbox("Lịch cần xử lý", list(reversed(active)))
    s = active[sid]
    if s["status"] == "PROPOSED" and st.button("Xác nhận lịch", type="primary"):
        _action(service.confirm_charging_schedule, "Đã xác nhận lịch và giữ công suất.", state, sid)
    if s["status"] in ("PROPOSED", "CONFIRMED") and st.button("Hủy lịch và yêu cầu"):
        _action(service.cancel_charging_schedule, "Đã hủy yêu cầu và giải phóng lịch.", state, s["request_id"])
    if s["status"] in service.ACTIVE:
        progress = st.number_input("Tiến độ phiên sạc (%)", min_value=int(s["progress"]), max_value=100,
                                   value=int(s["progress"]), key=f"progress_{sid}")
        if st.button("Cập nhật phiên sạc"):
            _action(service.update_charging_progress, "Đã cập nhật phiên sạc.", state, sid, progress)


def render(state, current_user):
    if current_user.get("role") != ROLE_OPERATOR:
        st.error("Chức năng này dành cho Operator.")
        return
    st.title("SUB-04 · Smart Charging Management")
    hubs = {h["hub_id"]: h["name"] for h in state["hubs"]}
    if not hubs:
        st.info("Chưa có Hub.")
        return
    hub_id = st.selectbox("Mobility Hub", list(hubs), format_func=hubs.get)
    if notice := st.session_state.pop("sub04_notice", None):
        st.success(notice)
    data = service.get_charging_resources(state, hub_id)
    resources, queue, schedules = st.tabs(["Tài nguyên sạc", "Hàng chờ ưu tiên", "Lịch sạc"])
    with resources:
        _resources(data)
    with queue:
        _queue(state, hub_id)
    with schedules:
        _schedules(state, data["schedules"])
