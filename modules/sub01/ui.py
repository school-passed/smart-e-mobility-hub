"""Streamlit UI for SUB-01: Mobility Discovery & Reservation."""

import streamlit as st

from modules.sub01.service import (
    cancel_reservation,
    create_reservation,
    find_suitable_vehicles,
    get_hub_details,
    get_hub_list,
    get_student_reservations,
)


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-01 · Mobility Discovery & Reservation")
    st.caption("UC-01 · UC-02 · UC-03-01 · UC-03-02")

    hubs = get_hub_list(state)
    st.subheader("Mobility Hubs")
    st.dataframe(
        [
            {
                "Hub": h["name"],
                "Address": h["address"],
                "Available vehicles": h["available_vehicle_count"],
                "Available reservation slots": h["available_reservation_slots"],
                "Available parking spaces": h["available_parking_space_count"],
            }
            for h in hubs
        ],
        use_container_width=True,
        hide_index=True,
    )

    hub_options = {f"{h['hub_id']} · {h['name']}": h["hub_id"] for h in hubs}
    selected_label = st.selectbox("Select Mobility Hub", list(hub_options))
    selected_hub_id = hub_options[selected_label]
    details = get_hub_details(state, selected_hub_id)
    if details:
        st.info(
            f"{details['address']} · {details['available_vehicle_count']} xe khả dụng · "
            f"{details['available_reservation_slots']} slot còn trống"
        )

    st.subheader("Find suitable shared vehicles")
    col1, col2 = st.columns(2)
    with col1:
        vehicle_type_label = st.selectbox(
            "Vehicle type",
            ["All", "Electric bicycle", "Electric motorcycle"],
        )
    with col2:
        min_battery = st.slider("Minimum battery (%)", min_value=0, max_value=100, value=25)

    vehicle_type = {
        "All": None,
        "Electric bicycle": "ELECTRIC_BICYCLE",
        "Electric motorcycle": "ELECTRIC_MOTORCYCLE",
    }[vehicle_type_label]
    matching_vehicles = find_suitable_vehicles(
        state, selected_hub_id, vehicle_type, min_battery
    )
    st.write(f"Found **{len(matching_vehicles)}** suitable vehicles")
    if matching_vehicles:
        st.dataframe(
            [
                {
                    "Vehicle ID": v["vehicle_id"],
                    "Type": v["vehicle_type"],
                    "Battery (%)": v["battery_level"],
                    "Status": v["status"],
                }
                for v in matching_vehicles
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("Không có xe phù hợp với tiêu chí tìm kiếm.")

    st.subheader("Reserve a Hub slot")
    st.caption("Reservation chỉ giữ slot tại Hub, chưa gắn với một xe cụ thể.")
    if st.button("Create reservation", type="primary"):
        try:
            reservation = create_reservation(
                state, current_user["user_id"], selected_hub_id
            )
            st.success(
                f"Reservation thành công · ID: {reservation['reservation_id']} · "
                f"Pickup code: {reservation['pickup_code']}"
            )
            st.info(f"Thời hạn demo: {reservation['expires_at']}")
        except ValueError as exc:
            st.error(str(exc))

    st.subheader("My reservations")
    reservations = get_student_reservations(state, current_user["user_id"])
    if reservations:
        st.dataframe(
            [
                {
                    "Reservation ID": r["reservation_id"],
                    "Hub": r["hub_id"],
                    "Pickup code": r["pickup_code"],
                    "Status": r["status"],
                    "Expires at": r["expires_at"],
                }
                for r in reservations
            ],
            use_container_width=True,
            hide_index=True,
        )
        pending = [r for r in reservations if r["status"] == "PENDING"]
        if pending:
            options = {r["reservation_id"]: r["reservation_id"] for r in pending}
            selected_reservation = st.selectbox(
                "Reservation to cancel", list(options)
            )
            if st.button("Cancel selected reservation"):
                success, message = cancel_reservation(
                    state, selected_reservation, current_user["user_id"]
                )
                (st.success if success else st.error)(message)
                if success:
                    st.rerun()
    else:
        st.info("Chưa có reservation nào cho tài khoản demo này.")
