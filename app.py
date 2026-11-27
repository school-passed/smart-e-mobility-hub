"""Entry point for the Smart E-Mobility Hub MVP."""

import streamlit as st

from shared.auth import render_auth
from shared.state import get_state
from modules.sub01.ui import render as render_sub01
from modules.sub02.ui import render as render_sub02
from modules.sub03.ui import render as render_sub03
from modules.sub04.ui import render as render_sub04
from modules.sub05.ui import render as render_sub05
from modules.sub06.ui import render as render_sub06

st.set_page_config(
    page_title="Smart E-Mobility Hub",
    page_icon="🔋",
    layout="wide",
)

state = get_state()
current_user = render_auth(state)
if current_user is None:
    st.stop()
role = current_user["role"]

st.sidebar.divider()
st.sidebar.caption(f"Người dùng: {current_user['display_name']}")

# One product organized by user workflows. Each page still calls its owning SUB.
role_pages = {
    "Student": {
        "overview": "Tổng quan",
        "discovery": "Tìm kiếm & đặt xe",
        "trip": "Nhận xe & trả xe",
    },
    "Private EV Student": {
        "overview": "Tổng quan",
        "parking": "Đỗ xe & yêu cầu sạc",
    },
    "Operator": {
        "overview": "Tổng quan",
        "charging": "Quản lý sạc",
        "network": "Vận hành mạng lưới",
        "simulation": "Mô phỏng What-if",
    },
}
page = st.sidebar.radio(
    "Chức năng",
    options=list(role_pages[role]),
    format_func=lambda key: role_pages[role][key],
)

if page == "overview":
    st.title("Smart E-Mobility Hub")
    st.write("Electric Mobility Coordination System for the VNU-HCM Urban Area")
    st.info(
        "Đây là một MVP tích hợp: các nghiệp vụ chia sẻ cùng dữ liệu demo. "
        "Dữ liệu chỉ lưu trong bộ nhớ và sẽ reset khi khởi động lại ứng dụng."
    )
    hubs = state["hubs"]
    vehicles = state["vehicles"]
    parking = state["parking_spaces"]
    charging = state["charging_points"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mobility Hubs", len(hubs))
    c2.metric("Shared vehicles", len(vehicles))
    c3.metric("Parking spaces", len(parking))
    c4.metric("Charging points", len(charging))
    st.subheader("Hub overview")
    st.dataframe(
        [
            {
                "Hub": h["name"],
                "Available vehicles": sum(
                    1 for v in vehicles
                    if v["hub_id"] == h["hub_id"] and v["status"] == "AVAILABLE"
                ),
                "Available parking": sum(
                    1 for p in parking
                    if p["hub_id"] == h["hub_id"] and p["status"] == "AVAILABLE"
                ),
                "Available charging points": sum(
                    1 for cp in charging
                    if cp["hub_id"] == h["hub_id"] and cp["status"] == "AVAILABLE"
                ),
            }
            for h in hubs
        ],
        use_container_width=True,
        hide_index=True,
    )
elif page == "discovery":
    render_sub01(state, current_user)
elif page == "trip":
    render_sub02(state, current_user)
elif page == "parking":
    render_sub03(state, current_user)
elif page == "charging":
    render_sub04(state, current_user)
elif page == "network":
    render_sub05(state, current_user)
elif page == "simulation":
    render_sub06(state, current_user)
