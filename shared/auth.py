"""Temporary role switcher used only while the MVP is being assembled.

M2 owns the final Sign Up / Sign In / Sign Out implementation. Replace this
selector with the agreed authentication screens before final demonstration.
"""

from __future__ import annotations

import streamlit as st

DEMO_ACCOUNTS = {
    "Student": {"user_id": "STU-001", "role": "Student", "display_name": "Demo Student"},
    "Private EV Student": {
        "user_id": "PSTU-001",
        "role": "Private EV Student",
        "display_name": "Demo Private EV Student",
    },
    "Operator": {"user_id": "OP-001", "role": "Operator", "display_name": "Demo Operator"},
}


def render_demo_role_selector() -> dict[str, str]:
    """Select a demo role; M2 will replace this with real use-case screens."""
    selected_role = st.sidebar.selectbox(
        "Demo role (temporary)",
        list(DEMO_ACCOUNTS),
        help="Bản khởi tạo để kiểm thử giao diện. M2 sẽ thay bằng Sign Up / Sign In / Sign Out.",
    )
    return DEMO_ACCOUNTS[selected_role]
