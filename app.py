"""Entry point for the Smart E-Mobility Hub MVP."""

from html import escape
import streamlit as st

from shared.auth import AUTH_USER_KEY, render_auth, sign_in, sign_out
from shared.enums import ROLE_OPERATOR, ROLE_PRIVATE_EV_STUDENT, ROLE_STUDENT
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

_STUDENT_MOBILE_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background-color: #F8FAFC;
}
[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stSidebar"] {
    display: none;
}

/* Khung Mobile App 440px: bao trọn chiều cao khi cuộn và khóa tràn ngang */
[data-testid="stMain"] .block-container,
[data-testid="stMainBlockContainer"] {
    max-width: 440px !important;
    width: 100% !important;
    height: auto !important;
    min-height: 100vh !important;
    background-color: #FFFFFF !important;
    padding: 1.1rem 1rem 2.2rem 1rem !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
    overflow-x: hidden !important;
    box-shadow: 0 0 36px rgba(15, 23, 42, 0.06) !important;
}
[data-testid="stMain"] .block-container * {
    box-sizing: border-box !important;
}

/* Cho phép các cột và phần tử con co gọn vừa khít khung 440px */
[data-testid="stMain"] [data-testid="stHorizontalBlock"] {
    gap: 0.42rem !important;
    width: 100% !important;
    max-width: 100% !important;
}
[data-testid="stMain"] [data-testid="stColumn"] {
    min-width: 0 !important;
}
[data-testid="stMain"] [data-testid="stElementContainer"],
[data-testid="stMain"] [data-testid="stButton"] {
    width: 100% !important;
    max-width: 100% !important;
}

/* Nút hành động chính xanh lá mạ #8CE600 */
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"],
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: #8CE600 !important;
    color: #0F172A !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 800 !important;
    font-size: 0.9rem !important;
    min-height: 2.7rem !important;
    max-width: 100% !important;
    box-shadow: 0 4px 12px rgba(140, 230, 0, 0.24) !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: #7ED100 !important;
    color: #0F172A !important;
}

/* Nút phụ mặc định */
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"],
div[data-testid="stButton"] button[kind="secondary"],
div[data-testid="stFormSubmitButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
    min-height: 2.4rem !important;
    max-width: 100% !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #8CE600 !important;
    background-color: #F7FEE7 !important;
}

/* Thanh điều hướng 4 tab ở đáy */
div[class*="st-key-mob_nav_"] div[data-testid="stButton"] button {
    border-radius: 14px !important;
    padding: 6px 2px !important;
    min-height: 3.25rem !important;
    box-shadow: none !important;
}
div[class*="st-key-mob_nav_"] div[data-testid="stButton"] button p {
    font-size: 0.72rem !important;
    font-weight: 800 !important;
    line-height: 1.25 !important;
    white-space: pre-line !important;
    margin: 0 !important;
}

div[data-testid="stTextInput"] input {
    border-radius: 14px !important;
    border: 1px solid #E2E8F0 !important;
    background-color: #F8FAFC !important;
}

.emob-nav-divider {
    border-top: 1px solid #E2E8F0;
    margin: 18px 0 10px 0;
}
.emob-profile-hero {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    border-radius: 22px;
    padding: 20px;
    color: #FFFFFF;
    margin-bottom: 14px;
}
.emob-avatar {
    width: 52px;
    height: 52px;
    border-radius: 999px;
    background: #8CE600;
    color: #0F172A;
    font-size: 1.25rem;
    font-weight: 900;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 10px;
}
.emob-stat-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 14px;
}
.emob-stat-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 12px 8px;
    text-align: center;
}
.emob-stat-num {
    font-size: 1.3rem;
    font-weight: 800;
    color: #0F172A;
}
.emob-stat-lbl {
    font-size: 0.72rem;
    color: #64748B;
    font-weight: 600;
}
</style>
"""


def _initials(name: str) -> str:
    parts = [p for p in (name or "").strip().split() if p]
    if len(parts) >= 2:
        return (parts[-2][0] + parts[-1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "SV"


def _render_student_profile(state: dict, current_user: dict) -> None:
    uid = current_user["user_id"]
    name = current_user.get("display_name", "Sinh viên")
    ini = _initials(name)

    my_res = [r for r in state.get("reservations", []) if r["student_id"] == uid]
    my_trips = [t for t in state.get("trips", []) if t["student_id"] == uid]
    my_parking = [p for p in state.get("parking_reservations", []) if p["student_id"] == uid]

    st.markdown(
        f"""
        <div style="font-size:1.45rem;font-weight:800;color:#0F172A;margin-bottom:12px;">Hồ sơ cá nhân</div>
        <div class="emob-profile-hero">
            <div class="emob-avatar">{escape(ini)}</div>
            <div style="font-size:1.15rem;font-weight:800;">{escape(name)}</div>
            <div style="font-size:0.8rem;color:#CBD5E1;margin-top:2px;">
                Mã SV: <b>{escape(uid)}</b> · {escape(current_user.get("username", ""))}
            </div>
            <div style="margin-top:10px;">
                <span style="background:rgba(140,230,0,0.2);color:#8CE600;padding:4px 12px;border-radius:999px;font-size:0.74rem;font-weight:700;">
                    ✓ Tài khoản Sinh viên VNU-HCM
                </span>
            </div>
        </div>
        <div class="emob-stat-grid">
            <div class="emob-stat-box">
                <div class="emob-stat-num">{len(my_trips)}</div>
                <div class="emob-stat-lbl">Chuyến đi</div>
            </div>
            <div class="emob-stat-box">
                <div class="emob-stat-num">{len(my_res)}</div>
                <div class="emob-stat-lbl">Lượt đặt xe</div>
            </div>
            <div class="emob-stat-box">
                <div class="emob-stat-num">{len(my_parking)}</div>
                <div class="emob-stat-lbl">Đỗ &amp; Sạc</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("Chuyển nhanh tài khoản Demo")
    c1, c2 = st.columns(2)
    if c1.button("Student (STU-001)", use_container_width=True, key="prof_sw_stu"):
        _, _, u = sign_in(state, "student", "123")
        st.session_state[AUTH_USER_KEY] = u
        st.rerun()
    if c2.button("Private EV (PSTU-001)", use_container_width=True, key="prof_sw_pstu"):
        _, _, u = sign_in(state, "pstudent", "123")
        st.session_state[AUTH_USER_KEY] = u
        st.rerun()

    st.write("")
    if st.button("🚪 Đăng xuất", type="primary", use_container_width=True, key="prof_signout"):
        sign_out()
        st.session_state.pop("student_nav_tab", None)
        st.rerun()


state = get_state()
current_user = render_auth(state)
if current_user is None:
    st.stop()
role = current_user["role"]

# ---------------------------------------------------------------------------
# GIAO DIỆN MOBILE APP CHO SINH VIÊN (4 TAB)
# ---------------------------------------------------------------------------
if role in (ROLE_STUDENT, ROLE_PRIVATE_EV_STUDENT):
    st.markdown(_STUDENT_MOBILE_CSS, unsafe_allow_html=True)

    st.session_state.setdefault("student_nav_tab", "explore")
    active_tab = st.session_state["student_nav_tab"]

    if active_tab == "explore":
        render_sub01(state, current_user)
    elif active_tab == "mine":
        render_sub02(state, current_user)
    elif active_tab == "parking":
        render_sub03(state, current_user)
    else:
        _render_student_profile(state, current_user)

    st.markdown('<div class="emob-nav-divider"></div>', unsafe_allow_html=True)
    nav_items = [
        ("explore", "📍\nKhám phá"),
        ("mine", "🔖\nCủa tôi"),
        ("parking", "⚡\nĐỗ & Sạc"),
        ("profile", "👤\nHồ sơ"),
    ]
    nav_cols = st.columns(4)
    for col, (tab_key, tab_label) in zip(nav_cols, nav_items):
        if col.button(
            tab_label,
            key=f"mob_nav_{tab_key}",
            type="primary" if active_tab == tab_key else "secondary",
            use_container_width=True,
        ):
            st.session_state["student_nav_tab"] = tab_key
            st.rerun()

# ---------------------------------------------------------------------------
# GIAO DIỆN DESKTOP CHO OPERATOR
# ---------------------------------------------------------------------------
else:
    st.sidebar.divider()
    st.sidebar.caption(f"Người dùng: {current_user['display_name']}")

    role_pages = {
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
    elif page == "charging":
        render_sub04(state, current_user)
    elif page == "network":
        render_sub05(state, current_user)
    elif page == "simulation":
        render_sub06(state, current_user)