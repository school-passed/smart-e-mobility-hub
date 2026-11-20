"""Entry point for the Smart E-Mobility Hub MVP."""

import streamlit as st

from shared.auth import render_demo_role_selector
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
current_user = render_demo_role_selector()
role = current_user["role"]

st.sidebar.divider()
st.sidebar.caption(f"Current demo user: {current_user['display_name']}")

role_pages = {
    "Student": ["Overview", "SUB-01 · Mobility Discovery", "SUB-02 · Shared Trip"],
    "Private EV Student": ["Overview", "SUB-03 · Private EV Parking"],
    "Operator": [
        "Overview",
        "SUB-04 · Smart Charging",
        "SUB-05 · Network Operation",
        "SUB-06 · What-if Simulation",
    ],
}
page = st.sidebar.radio("Navigation", role_pages[role])

if page == "Overview":
    st.title("Smart E-Mobility Hub")
    st.write("Electric Mobility Coordination System for the VNU-HCM Urban Area")
    st.info(
        "Project scaffold đang được khởi tạo. Dữ liệu mẫu được chia sẻ trong cùng "
        "một tiến trình ứng dụng và sẽ được reset khi khởi động lại app."
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
elif page.startswith("SUB-01"):
    render_sub01(state, current_user)
elif page.startswith("SUB-02"):
    render_sub02(state, current_user)
elif page.startswith("SUB-03"):
    render_sub03(state, current_user)
elif page.startswith("SUB-04"):
    render_sub04(state, current_user)
elif page.startswith("SUB-05"):
    render_sub05(state, current_user)
elif page.startswith("SUB-06"):
    render_sub06(state, current_user)
