from __future__ import annotations

import streamlit as st

from modules.sub01.service import get_student_reservations
from modules.sub02.service import (
    MIN_OPERATING_BATTERY_LEVEL,
    get_active_trip,
    get_available_vehicles_at_hub,
    get_student_trips,
    pickup_vehicle,
    report_defective_vehicle_at_pickup,
    report_defective_vehicle_at_return,
    return_vehicle,
)
from shared.enums import RESERVATION_PENDING


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-02 · Vehicle Trip Lifecycle")
    st.caption("UC-04: Pick Up Shared Vehicle · UC-05: Return Shared Vehicle")

    student_id = current_user["user_id"]
    hub_map = {h["hub_id"]: f"{h['hub_id']} · {h['name']}" for h in state["hubs"]}

    tab_pickup, tab_return, tab_history = st.tabs(
        ["Nhận xe (Pickup)", "Trả xe (Return)", "Lịch sử chuyến đi"]
    )

    # ------------------------------------------------------------------
    # TAB 1: UC-04 Pick Up Shared Vehicle
    # ------------------------------------------------------------------
    with tab_pickup:
        active_trip = get_active_trip(state, student_id)
        if active_trip is not None:
            st.warning(
                f"Bạn đang có chuyến đi **{active_trip['trip_id']}** với xe "
                f"**{active_trip['vehicle_id']}** (bắt đầu lúc `{active_trip['start_time']}`). "
                "Hãy chuyển sang tab **Trả xe** để kết thúc chuyến đi."
            )
        else:
            reservations = get_student_reservations(state, student_id)
            pending_reservations = [
                r for r in reservations if r["status"] == RESERVATION_PENDING
            ]
            if not pending_reservations:
                st.info(
                    "Bạn chưa có đơn đặt chỗ nào ở trạng thái PENDING. "
                    "Vui lòng sang **SUB-01 · Mobility Discovery & Reservation** để đặt slot trước."
                )
            else:
                res_options = {
                    f"{r['reservation_id']} · {hub_map.get(r['hub_id'], r['hub_id'])} (Code: {r['pickup_code']})": r
                    for r in pending_reservations
                }
                selected_res_label = st.selectbox(
                    "Chọn đơn đặt chỗ (Reservation)", list(res_options), key="sub02_res_select"
                )
                selected_res = res_options[selected_res_label]

                available_vehicles = get_available_vehicles_at_hub(state, selected_res["hub_id"])
                if not available_vehicles:
                    st.error("Hiện không còn xe AVAILABLE nào tại Hub này.")
                else:
                    veh_options = {
                        f"{v['vehicle_id']} · {v['vehicle_type']} · Pin {v['battery_level']}%": v["vehicle_id"]
                        for v in available_vehicles
                    }
                    selected_veh_label = st.selectbox(
                        "Quét mã QR / Chọn phương tiện tại Hub",
                        list(veh_options),
                        key="sub02_veh_select",
                    )
                    selected_veh_id = veh_options[selected_veh_label]
                    pickup_code_input = st.text_input(
                        "Nhập Pickup Code (6 chữ số)",
                        value=selected_res["pickup_code"],
                        key="sub02_pickup_code",
                    )

                    if st.button("Mở khóa & Nhận xe", type="primary", key="sub02_pickup_btn"):
                        res = pickup_vehicle(
                            state,
                            student_id=student_id,
                            reservation_id=selected_res["reservation_id"],
                            vehicle_id=selected_veh_id,
                            pickup_code=pickup_code_input,
                        )
                        if res["ok"]:
                            st.success(res["message"])
                            st.rerun()
                        else:
                            st.error(res["message"])

                    with st.expander("Báo cáo xe hỏng trước khi nhận (Luồng ngoại lệ A1)"):
                        fault_desc = st.text_input(
                            "Mô tả sự cố (ví dụ: xẹp lốp, hỏng phanh, lỗi khóa)",
                            key="sub02_pickup_fault_desc",
                        )
                        if st.button("Gửi báo cáo sự cố", key="sub02_pickup_fault_btn"):
                            res = report_defective_vehicle_at_pickup(
                                state,
                                student_id=student_id,
                                reservation_id=selected_res["reservation_id"],
                                vehicle_id=selected_veh_id,
                                issue_desc=fault_desc,
                            )
                            if res["ok"]:
                                st.warning(res["message"])
                                st.rerun()
                            else:
                                st.error(res["message"])

    # ------------------------------------------------------------------
    # TAB 2: UC-05 Return Shared Vehicle
    # ------------------------------------------------------------------
    with tab_return:
        active_trip = get_active_trip(state, student_id)
        if active_trip is None:
            st.info("Hiện bạn không có chuyến đi nào đang hoạt động.")
        else:
            st.subheader(f"Chuyến đi đang hoạt động: {active_trip['trip_id']}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Phương tiện", active_trip["vehicle_id"])
            col2.metric("Hub xuất phát", active_trip["origin_hub_id"])
            col3.metric("Pin lúc nhận", f"{active_trip['start_battery_level']}%")

            hub_ids = [h["hub_id"] for h in state["hubs"]]
            dest_hub_id = st.selectbox(
                "Chọn Hub trả xe",
                hub_ids,
                format_func=lambda hid: hub_map.get(hid, hid),
                key="sub02_dest_hub",
            )
            default_bat = max(0, int(active_trip["start_battery_level"]) - 15)
            final_battery = st.slider(
                f"Mức pin thực tế khi trả (%) — Ngưỡng sạc tự động: < {MIN_OPERATING_BATTERY_LEVEL}%",
                min_value=0,
                max_value=100,
                value=default_bat,
                key="sub02_final_battery",
            )

            if st.button("Chốt khóa & Hoàn tất trả xe", type="primary", key="sub02_return_btn"):
                res = return_vehicle(
                    state,
                    student_id=student_id,
                    trip_id=active_trip["trip_id"],
                    destination_hub_id=dest_hub_id,
                    final_battery=final_battery,
                )
                if res["ok"]:
                    st.success(res["message"])
                    st.rerun()
                else:
                    st.error(res["message"])

    # ------------------------------------------------------------------
    # TAB 3: Trip History & Fault Report at Return
    # ------------------------------------------------------------------
    with tab_history:
        trips = get_student_trips(state, student_id)
        if not trips:
            st.info("Chưa có lịch sử chuyến đi nào cho tài khoản này.")
        else:
            st.dataframe(
                [
                    {
                        "Trip ID": t["trip_id"],
                        "Vehicle": t["vehicle_id"],
                        "Origin": t["origin_hub_id"],
                        "Destination": t["destination_hub_id"] or "-",
                        "Start Battery (%)": t["start_battery_level"],
                        "End Battery (%)": t["end_battery_level"] if t["end_battery_level"] is not None else "-",
                        "Status": "ACTIVE" if t["is_active"] else "COMPLETED",
                        "Start Time": t["start_time"],
                        "End Time": t["end_time"] or "-",
                    }
                    for t in trips
                ],
                use_container_width=True,
                hide_index=True,
            )

            completed_trips = [t for t in trips if not t["is_active"]]
            if completed_trips:
                with st.expander("Báo cáo sự cố phương tiện sau khi trả xe (UC-05 A1)"):
                    trip_ids = [t["trip_id"] for t in completed_trips]
                    selected_trip_id = st.selectbox("Chọn chuyến đi", trip_ids, key="sub02_ret_fault_trip")
                    ret_fault_desc = st.text_input("Mô tả hư hại phát sinh", key="sub02_ret_fault_desc")
                    if st.button("Gửi báo cáo sự cố sau trả xe", key="sub02_ret_fault_btn"):
                        res = report_defective_vehicle_at_return(
                            state,
                            student_id=student_id,
                            trip_id=selected_trip_id,
                            issue_desc=ret_fault_desc,
                        )
                        if res["ok"]:
                            st.warning(res["message"])
                            st.rerun()
                        else:
                            st.error(res["message"])
