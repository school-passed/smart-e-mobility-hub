"""Streamlit UI for SUB-03: Private EV Parking & Charging."""

from __future__ import annotations

from datetime import datetime, timedelta
import streamlit as st

from modules.sub03 import service as sub03_service
from shared.enums import (
    CHARGING_REQUEST_CONFIRMED,
    CHARGING_REQUEST_PENDING,
    PARKING_AVAILABLE,
    PARKING_IN_USE,
    PARKING_RESERVED,
    ROLE_PRIVATE_EV_STUDENT,
)


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-03 · Private EV Parking & Charging")
    st.caption("UC-06-01 · UC-06-02 · UC-06-03 · UC-07-01 · UC-07-02")

    role = current_user.get("role", "")
    if role != ROLE_PRIVATE_EV_STUDENT:
        st.warning(
            f"Bạn đang xem màn hình SUB-03 với vai trò **{role}**. "
            f"Chức năng này dành chính cho **{ROLE_PRIVATE_EV_STUDENT}**."
        )

    student_id = (
        current_user.get("user_id")
        or current_user.get("id")
        or current_user.get("username")
        or "PEV-STU-001"
    )

    tab_reserve, tab_manage, tab_charging = st.tabs(
        [
            "1. Đặt chỗ đỗ (UC-06-01)",
            "2. Phiếu đỗ & Check-in/out (UC-06-02, 06-03)",
            "3. Yêu cầu sạc xe (UC-07-01, 07-02)",
        ]
    )

    # =========================================================================
    # TAB 1: UC-06-01 RESERVE PARKING SPACE (HOLD 5 MIN -> CONFIRM)
    # =========================================================================
    with tab_reserve:
        st.subheader("Tìm và giữ chỗ đỗ xe điện cá nhân")

        active_hold = sub03_service.get_active_hold_for_student(state, student_id)
        if active_hold is not None:
            st.info(
                f"⏳ **Bạn đang giữ tạm ô `{active_hold['space_id']}` tại `{active_hold['hub_id']}`** "
                f"({'Có trụ sạc ⚡' if active_hold['has_charger'] else 'Không trụ sạc'}). "
                f"Hết hạn lúc: **{active_hold['expires_at']}**"
            )
            with st.form("confirm_hold_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    license_plate = st.text_input("Biển số xe điện cá nhân", value="59-M1 123.45")
                with col2:
                    default_start = datetime.now().strftime("%H:%M")
                    start_time = st.text_input("Giờ dự kiến đến (HH:MM)", value=default_start)
                with col3:
                    default_end = (datetime.now() + timedelta(hours=2)).strftime("%H:%M")
                    end_time = st.text_input("Giờ dự kiến rời đi (HH:MM)", value=default_end)

                c_btn1, c_btn2 = st.columns([1, 1])
                confirm_clicked = c_btn1.form_submit_button("✅ Xác nhận đặt chỗ", type="primary")
                cancel_hold_clicked = c_btn2.form_submit_button("❌ Hủy giữ tạm")

                if confirm_clicked:
                    try:
                        res = sub03_service.confirm_parking_reservation(
                            state=state,
                            hold_id=active_hold["hold_id"],
                            student_id=student_id,
                            license_plate=license_plate,
                            start_time=start_time,
                            end_time=end_time,
                        )
                        st.success(f"Đặt chỗ thành công! Mã phiếu: **{res['reservation_id']}** (Ô **{res['space_id']}**).")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

                if cancel_hold_clicked:
                    ok, msg = sub03_service.release_temporary_hold(state, active_hold["hold_id"], student_id)
                    if ok:
                        st.warning(msg)
                        st.rerun()
                    else:
                        st.error(msg)

            st.divider()

        hubs = state["hubs"]
        hub_options = {f"{h['hub_id']} - {h['name']} ({h['address']})": h["hub_id"] for h in hubs}
        selected_hub_label = st.selectbox("Chọn Mobility Hub", list(hub_options.keys()))
        selected_hub_id = hub_options[selected_hub_label]

        col_f1, col_f2 = st.columns(2)
        only_avail = col_f1.checkbox("Chỉ hiển thị ô đang trống (AVAILABLE)", value=False)
        only_charger = col_f2.checkbox("Chỉ hiển thị ô có trụ sạc (⚡)", value=False)

        spaces = sub03_service.get_parking_spaces_by_hub(
            state, selected_hub_id, only_available=only_avail, only_with_charger=only_charger
        )

        m1, m2, m3 = st.columns(3)
        all_hub_spaces = [s for s in state["parking_spaces"] if s["hub_id"] == selected_hub_id]
        avail_count = sum(1 for s in all_hub_spaces if s["status"] == PARKING_AVAILABLE)
        charger_avail_count = sum(
            1 for s in all_hub_spaces if s["status"] == PARKING_AVAILABLE and s["has_charger"]
        )
        m1.metric("Tổng số ô đỗ tại Hub", len(all_hub_spaces))
        m2.metric("Số ô đang trống", avail_count)
        m3.metric("Ô trống có trụ sạc ⚡", charger_avail_count)

        if not spaces:
            st.warning("Không có ô đỗ nào phù hợp bộ lọc hiện tại.")
        else:
            table_rows = [
                {
                    "Mã ô đỗ": s["space_id"],
                    "Hub": s["hub_id"],
                    "Trụ sạc": "Có sạc ⚡" if s["has_charger"] else "Chỉ đỗ xe",
                    "Trạng thái": s["effective_status"],
                }
                for s in spaces
            ]
            st.dataframe(table_rows, use_container_width=True, hide_index=True)

            available_spaces = [s for s in spaces if s["effective_status"] == PARKING_AVAILABLE]
            if available_spaces and active_hold is None:
                space_choices = {
                    f"{s['space_id']} ({'Có trụ sạc ⚡' if s['has_charger'] else 'Chỉ đỗ xe'})": s["space_id"]
                    for s in available_spaces
                }
                chosen_label = st.selectbox("Chọn ô đỗ muốn giữ tạm (5 phút)", list(space_choices.keys()))
                if st.button("🔒 Giữ chỗ tạm thời (5 phút)", type="primary"):
                    try:
                        hold = sub03_service.create_temporary_hold(
                            state, space_choices[chosen_label], student_id
                        )
                        st.success(f"Đã giữ tạm ô {hold['space_id']} trong 5 phút! Vui lòng xác nhận ở khung phía trên.")
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

    # =========================================================================
    # TAB 2: UC-06-02 & UC-06-03 MY RESERVATIONS, CHECK-IN / CHECK-OUT
    # =========================================================================
    with tab_manage:
        st.subheader("Danh sách phiếu đặt chỗ đỗ của bạn")
        my_reservations = sub03_service.get_student_parking_reservations(state, student_id)

        if not my_reservations:
            st.info("Bạn chưa có phiếu đặt chỗ đỗ nào. Hãy sang Tab 1 để đặt chỗ nhé!")
        else:
            for res in my_reservations:
                with st.container(border=True):
                    top1, top2 = st.columns([3, 1])
                    top1.markdown(
                        f"**{res['reservation_id']}** · Ô **{res['space_id']}** ({res['hub_name']}) "
                        f"| Biển số: `{res['license_plate']}`"
                    )
                    top2.markdown(f"Trạng thái: **{res['status']}**")
                    st.caption(
                        f"Khung giờ: {res['start_time']} → {res['end_time']} | "
                        f"Hỗ trợ sạc: {'Có ⚡' if res['has_charger'] else 'Không'}"
                    )

                    if res["status"] == PARKING_RESERVED:
                        b1, b2, _ = st.columns([1, 1, 2])
                        if b1.button("🚗 Check-in (Giả lập cảm biến vào)", key=f"ci_{res['reservation_id']}", type="primary"):
                            ok, msg = sub03_service.check_in_vehicle(state, res["reservation_id"], student_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

                        if b2.button("❌ Hủy đặt chỗ", key=f"cancel_res_{res['reservation_id']}"):
                            ok, msg = sub03_service.cancel_parking_reservation(
                                state, res["reservation_id"], student_id
                            )
                            if ok:
                                st.warning(msg)
                                st.rerun()
                            else:
                                st.error(msg)

                    elif res["status"] == PARKING_IN_USE:
                        st.caption(f"Đã Check-in lúc: {res['checked_in_at']}")
                        if st.button("🏁 Check-out (Giả lập cảm biến rời ô)", key=f"co_{res['reservation_id']}", type="primary"):
                            ok, msg = sub03_service.check_out_vehicle(state, res["reservation_id"], student_id)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    # =========================================================================
    # TAB 3: UC-07-01 & UC-07-02 CHARGING REQUESTS FOR PRIVATE EV
    # =========================================================================
    with tab_charging:
        st.subheader("Gửi yêu cầu sạc cho xe điện cá nhân (UC-07-01)")
        my_reservations = sub03_service.get_student_parking_reservations(state, student_id)
        eligible_reservations = [
            r
            for r in my_reservations
            if r["status"] in (PARKING_RESERVED, PARKING_IN_USE) and r["has_charger"]
        ]

        if not eligible_reservations:
            st.info(
                "Bạn cần có phiếu đặt chỗ đang hoạt động (RESERVED hoặc IN_USE) tại **ô đỗ có trụ sạc (⚡)** "
                "để gửi yêu cầu sạc."
            )
        else:
            with st.form("charging_request_form"):
                res_choices = {
                    f"{r['reservation_id']} - Ô {r['space_id']} ({r['hub_name']}) [{r['status']}]": r["reservation_id"]
                    for r in eligible_reservations
                }
                selected_res_label = st.selectbox("Chọn phiếu đỗ có trụ sạc", list(res_choices.keys()))

                c1, c2, c3 = st.columns(3)
                current_bat = c1.number_input("Mức pin hiện tại (%)", min_value=0, max_value=99, value=30)
                target_bat = c2.number_input("Mức pin mục tiêu (%)", min_value=1, max_value=100, value=85)
                selected_res_obj = next(
                    r for r in eligible_reservations if r["reservation_id"] == res_choices[selected_res_label]
                )
                dep_time = c3.text_input("Giờ dự kiến lấy xe (HH:MM)", value=selected_res_obj["end_time"])

                submitted = st.form_submit_button("⚡ Gửi yêu cầu sạc (tới SUB-04)", type="primary")
                if submitted:
                    try:
                        creq = sub03_service.create_charging_request(
                            state=state,
                            reservation_id=res_choices[selected_res_label],
                            student_id=student_id,
                            current_battery=int(current_bat),
                            target_battery=int(target_bat),
                            departure_time=dep_time,
                        )
                        st.success(
                            f"Đã tạo yêu cầu sạc **{creq['request_id']}** (trạng thái **{creq['status']}**) "
                            f"và chuyển sang SUB-04 để điều phối!"
                        )
                        st.rerun()
                    except ValueError as err:
                        st.error(str(err))

        st.divider()
        st.subheader("Danh sách yêu cầu sạc của bạn (UC-07-02)")
        my_requests = sub03_service.get_student_charging_requests(state, student_id)
        if not my_requests:
            st.caption("Chưa có yêu cầu sạc nào.")
        else:
            for req in my_requests:
                with st.container(border=True):
                    col_a, col_b = st.columns([3, 1])
                    col_a.markdown(
                        f"**{req['request_id']}** (Phiếu đỗ `{req['reservation_id']}` · Ô **{req['space_id']}**) "
                        f"| Pin: **{req['current_battery']}% → {req['target_battery']}%**"
                    )
                    col_b.markdown(f"Trạng thái: **{req['status']}**")
                    st.caption(f"Giờ rời đi dự kiến: {req['departure_time']} | Tạo lúc: {req['created_at']}")

                    if req["status"] in (CHARGING_REQUEST_PENDING, CHARGING_REQUEST_CONFIRMED):
                        if st.button("🚫 Hủy yêu cầu sạc", key=f"cancel_creq_{req['request_id']}"):
                            ok, msg = sub03_service.cancel_charging_request(state, req["request_id"], student_id)
                            if ok:
                                st.warning(msg)
                                st.rerun()
                            else:
                                st.error(msg)