"""Entry point for the Smart E-Mobility Hub MVP (Unified Student Mobile UI + Operator Console UI)."""

from __future__ import annotations

from html import escape
import inspect
from urllib.parse import quote
import streamlit as st

from shared.auth import AUTH_USER_KEY, render_auth, sign_in, sign_out
from shared.enums import ROLE_OPERATOR, ROLE_PRIVATE_EV_STUDENT, ROLE_STUDENT
from shared.state import get_state
from modules.sub01.ui import render as render_sub01
from modules.sub02.ui import render as render_sub02
from modules.sub03.service import expire_unused_parking_reservations
from modules.sub03.ui import render as render_sub03
from modules.sub04.service import expire_unused_schedules
from modules.sub04.ui import render as render_sub04
from modules.sub05.ui import render as render_sub05
from modules.sub06.ui import clear_simulation_view, render as render_sub06

st.set_page_config(
    page_title="Smart E-Mobility Hub",
    page_icon="🔋",
    layout="wide",
)

_FULL = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.button).parameters
    else {"use_container_width": True}
)


# ===========================================================================
# STUDENT MOBILE APP SHELL (440px, 4 Bottom Tabs — feature/student-ui)
# ===========================================================================
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
    padding: 1.1rem 1rem calc(5.4rem + env(safe-area-inset-bottom)) !important;
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

/* Giữ điều hướng trong tầm tay khi cuộn danh sách trạm. */
.st-key-student_bottom_nav {
    position: fixed !important;
    z-index: 25;
    left: 50%;
    bottom: 0;
    transform: translateX(-50%);
    width: min(100%, 440px) !important;
    padding: 0.5rem 1rem calc(0.5rem + env(safe-area-inset-bottom));
    background: #FFFFFF;
    border-top: 1px solid #E2E8F0;
    box-shadow: 0 -4px 18px rgba(15, 23, 42, 0.06);
}
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
    if c1.button("Student (STU-001)", key="prof_sw_stu", **_FULL):
        _, _, u = sign_in(state, "student", "123")
        st.session_state[AUTH_USER_KEY] = u
        st.rerun()
    if c2.button("Private EV (PSTU-001)", key="prof_sw_pstu", **_FULL):
        _, _, u = sign_in(state, "pstudent", "123")
        st.session_state[AUTH_USER_KEY] = u
        st.rerun()

    st.write("")
    if st.button("🚪 Đăng xuất", type="primary", key="prof_signout", **_FULL):
        sign_out()
        st.session_state.pop("student_nav_tab", None)
        st.rerun()


# ===========================================================================
# OPERATOR DESKTOP CONSOLE SHELL (7-Item SVG Sidebar — feature/operator-ui)
# ===========================================================================
def _svg_mask(selector: str, svg: str) -> str:
    uri = "data:image/svg+xml;utf8," + quote(svg)
    return (
        f"{selector}{{"
        f"-webkit-mask-image:url('{uri}');mask-image:url('{uri}');"
        "}"
    )


_SIDEBAR_SVGS = {
    "network": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='3' width='7' height='7' rx='1.5'/><rect x='14' y='3' width='7' height='7' rx='1.5'/><rect x='3' y='14' width='7' height='7' rx='1.5'/><rect x='14' y='14' width='7' height='7' rx='1.5'/></svg>",
    "dispatch": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8 3 4 7l4 4'/><path d='M4 7h16'/><path d='m16 21 4-4-4-4'/><path d='M20 17H4'/></svg>",
    "resources": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polygon points='13 2 3 14 12 14 11 22 21 10 12 10 13 2'/></svg>",
    "priority": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 6h18'/><path d='M3 12h12'/><path d='M3 18h7'/></svg>",
    "schedule": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='4' width='18' height='18' rx='2'/><path d='M16 2v4'/><path d='M8 2v4'/><path d='M3 10h18'/></svg>",
    "incidents": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z'/><path d='M12 9v4'/><path d='M12 17h.01'/></svg>",
    "simulation": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='2' y='3' width='20' height='14' rx='2'/><path d='M8 21h8'/><path d='M12 17v4'/></svg>",
}
_LOGOUT_SVG = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4'/><polyline points='16 17 21 12 16 7'/><line x1='21' y1='12' x2='9' y2='12'/></svg>"

_SIDEBAR_ICON_CSS = "\n".join(
    [
        _svg_mask(
            f"[data-testid='stSidebar'] .st-key-operator_nav_button_{k} button::before",
            svg,
        )
        for k, svg in _SIDEBAR_SVGS.items()
    ]
    + [
        _svg_mask(
            "[data-testid='stSidebar'] .st-key-operator_sign_out button::before",
            _LOGOUT_SVG,
        )
    ]
)

OPERATOR_CSS = f"""
<style>
:root {{ color-scheme: light; }}
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {{
    background: #ffffff !important;
    color: #111827 !important;
}}
[data-testid="stHeader"] {{
    background: transparent !important;
    pointer-events: none !important;
}}
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
#MainMenu, footer {{
    display: none !important;
}}
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarHeader"] * {{
    pointer-events: auto !important;
    font-size: 0 !important;
    line-height: 0 !important;
    color: transparent !important;
}}
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
[data-testid="collapsedControl"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarHeader"] [data-testid="stIconMaterial"] {{
    font-size: 18px !important;
    line-height: 1 !important;
    color: #6b7280 !important;
}}
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] {{
    visibility: visible !important;
    opacity: 1 !important;
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
}}
[data-testid="stSidebar"][aria-expanded="true"] ~ div [data-testid="stExpandSidebarButton"] {{
    display: none !important;
}}

/* Sidebar layout & clean default font */
[data-testid="stSidebar"] {{
    display: block !important;
    width: clamp(220px, 16.5vw, 248px) !important;
    min-width: 220px !important;
    max-width: 248px !important;
    background: #ffffff !important;
    border-right: 1px solid #eef2f6 !important;
}}
[data-testid="stSidebar"] > div {{
    width: clamp(220px, 16.5vw, 248px) !important;
    height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
}}
[data-testid="stSidebarHeader"] {{
    height: 16px !important;
    min-height: 16px !important;
    max-height: 16px !important;
    padding: 4px 14px 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
    flex: 0 0 auto !important;
}}
[data-testid="stSidebarContent"] {{
    flex: 1 1 auto !important;
    padding: 0 14px 16px !important;
    display: flex !important;
    flex-direction: column !important;
    overflow-y: auto !important;
}}
[data-testid="stSidebarUserContent"] {{
    flex: 1 1 auto !important;
    padding: 4px 0 0 !important;
    display: flex !important;
    flex-direction: column !important;
}}
[data-testid="stSidebarUserContent"] > div,
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"]:has(.st-key-operator_footer):not(.st-key-operator_footer):not([data-testid="stColumn"] [data-testid="stVerticalBlock"]) {{
    flex: 1 1 auto !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 6px !important;
}}

[data-testid="stMainBlockContainer"],
[data-testid="stMain"] .block-container {{
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    padding: 24px 32px 44px !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}}
[data-testid="stMain"] h1 {{
    color: #101828 !important;
    font-size: clamp(1.6rem, 1.9vw, 2rem) !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    line-height: 1.15 !important;
    margin-bottom: 1rem !important;
}}
[data-testid="stMain"] h2, [data-testid="stMain"] h3,
[data-testid="stMain"] h4, [data-testid="stMain"] p,
[data-testid="stMain"] label, [data-testid="stMain"] span,
[data-testid="stMain"] div {{
    color: inherit;
}}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
[data-testid="stMain"] [data-testid="stCaptionContainer"] p {{
    color: #66758b;
}}

/* Sidebar branding and 7-item navigation */
.operator-brand {{ padding: 4px 12px 18px; }}
.operator-brand .eyebrow {{
    color: #789c28; font-size: .72rem; font-weight: 700;
    letter-spacing: .06em; margin-bottom: 3px; text-transform: uppercase;
}}
.operator-brand .brand-name {{
    color: #101828; font-size: 1.02rem; font-weight: 600; letter-spacing: -.02em;
}}
[data-testid="stSidebar"] .stButton > button {{
    width: 100% !important;
    min-height: 38px !important;
    height: 38px !important;
    display: flex !important;
    justify-content: flex-start !important;
    align-items: center !important;
    gap: 10px !important;
    text-align: left !important;
    padding: 6px 14px !important;
    margin: 0 !important;
    border: 1px solid transparent !important;
    border-radius: 999px !important;
    background: transparent !important;
    color: #4b5563 !important;
    font-size: .84rem !important;
    font-weight: 500 !important;
    box-shadow: none !important;
}}
[data-testid="stSidebar"] .stButton > button > div {{
    width: auto !important;
    flex: 0 1 auto !important;
    display: flex !important;
    justify-content: flex-start !important;
    text-align: left !important;
}}
[data-testid="stSidebar"] .stButton > button p {{
    text-align: left !important;
    font-size: .84rem !important;
    font-weight: 500 !important;
    line-height: 1.2 !important;
    white-space: nowrap !important;
}}
[data-testid="stSidebar"] [class*="st-key-operator_nav_button_"] button::before {{
    content: "";
    flex: 0 0 17px;
    width: 17px;
    height: 17px;
    background-color: #6b7280;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-position: center;
    -webkit-mask-size: contain;
    mask-size: contain;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: #f4f7ed !important;
    color: #536f27 !important;
}}
[data-testid="stSidebar"] [class*="st-key-operator_nav_button_"] button:hover::before {{
    background-color: #536f27 !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: #789c28 !important;
    border-color: #789c28 !important;
    color: #ffffff !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] *,
[data-testid="stSidebar"] .stButton > button[kind="primary"] p {{
    color: #ffffff !important;
    font-size: .84rem !important;
    font-weight: 600 !important;
}}
[data-testid="stSidebar"] [class*="st-key-operator_nav_button_"] button[kind="primary"]::before {{
    background-color: #ffffff !important;
}}

/* Sidebar footer pinned to bottom: profile + inline logout icon */
[data-testid="stSidebar"] .st-key-operator_footer,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > div:has(.st-key-operator_footer) {{
    margin-top: auto !important;
}}
[data-testid="stSidebar"] .st-key-operator_footer {{
    position: relative;
    z-index: 10;
    background: #ffffff;
    border-top: 1px solid #edf0f4;
    padding-top: 14px;
    padding-bottom: 2px;
}}
[data-testid="stSidebar"] .st-key-operator_footer [data-testid="stHorizontalBlock"] {{
    align-items: center !important;
    gap: 6px !important;
}}
.operator-profile {{
    display: flex; align-items: center; gap: 10px; min-width: 0;
}}
.operator-avatar {{
    width: 36px; height: 36px; border-radius: 50%; display: flex;
    align-items: center; justify-content: center; flex: 0 0 36px;
    background: #eef5db; color: #5b7c22; font-weight: 700; font-size: .8rem;
}}
.operator-profile-name {{
    color: #1f2937; font-size: .84rem; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.operator-profile-role {{
    color: #94a3b8; font-size: .72rem; font-weight: 400; margin-top: 1px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
[data-testid="stSidebar"] .st-key-operator_sign_out button {{
    width: 34px !important; min-width: 34px !important;
    height: 34px !important; min-height: 34px !important;
    padding: 0 !important; gap: 0 !important; justify-content: center !important;
    border-radius: 10px !important;
    background: transparent !important; border: 1px solid transparent !important;
}}
[data-testid="stSidebar"] .st-key-operator_sign_out button > div {{
    display: none !important;
}}
[data-testid="stSidebar"] .st-key-operator_sign_out button::before {{
    content: "";
    width: 17px;
    height: 17px;
    background-color: #e11d48;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-position: center;
    mask-position: center;
    -webkit-mask-size: contain;
    mask-size: contain;
}}
[data-testid="stSidebar"] .st-key-operator_sign_out button:hover {{
    background: #fff1f2 !important; border-color: #fecdd3 !important;
}}
{_SIDEBAR_ICON_CSS}

/* Light, consistent controls for Operator only */
[data-testid="stMain"] input, [data-testid="stMain"] textarea,
[data-testid="stMain"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-baseweb="input"] > div,
[data-testid="stMain"] [data-baseweb="textarea"] > div {{
    background: #ffffff !important;
    color: #172033 !important;
    border-color: #dfe6ef !important;
    border-radius: 10px !important;
}}
[data-testid="stMain"] [data-baseweb="select"] *,
[data-testid="stMain"] [data-baseweb="menu"],
[data-testid="stMain"] [data-baseweb="popover"],
[data-testid="stMain"] input::placeholder,
[data-testid="stMain"] textarea::placeholder {{ color: #66758b !important; }}
[data-testid="stMain"] [data-baseweb="menu"] {{ background: #ffffff !important; }}
[data-testid="stMain"] [role="option"] {{ color: #34445c !important; background: #ffffff !important; }}
[data-testid="stMain"] [role="option"]:hover {{ background: #f4f7ed !important; }}
[data-testid="stMain"] .stButton > button,
[data-testid="stMain"] .stDownloadButton > button {{
    border-radius: 10px !important;
    border: 1px solid #e1e7ef !important;
    color: #34445c !important;
    background: #f7f9fc !important;
    font-weight: 600 !important;
    min-height: 38px;
    box-shadow: none !important;
}}
[data-testid="stMain"] .stButton > button[kind="primary"],
[data-testid="stMain"] .stDownloadButton > button[kind="primary"],
[data-testid="stMain"] button[kind="primary"] {{
    color: #ffffff !important;
    background: #789c28 !important;
    border-color: #789c28 !important;
}}
[data-testid="stMain"] .stButton > button:hover,
[data-testid="stMain"] .stDownloadButton > button:hover {{
    border-color: #789c28 !important;
    color: #607f28 !important;
}}
[data-testid="stMain"] .stButton > button[kind="primary"]:hover {{
    color: #ffffff !important; background: #658520 !important;
}}
[data-testid="stMain"] [data-testid="stAlert"] {{
    background: #f4f8ec !important;
    color: #456322 !important;
    border: 1px solid #dce9c8 !important;
    border-radius: 12px !important;
}}
[data-testid="stMain"] [data-testid="stMetric"] {{
    background: #ffffff; border: 1px solid #e6ebf2;
    border-radius: 15px; padding: 14px 16px;
}}
[data-testid="stMain"] [data-testid="stDataFrame"],
[data-testid="stMain"] [data-testid="stTable"] {{ border-radius: 12px; }}
[data-testid="stMain"] [data-testid="stMarkdown"],
[data-testid="stMain"] [data-testid="stMarkdownContainer"],
[data-testid="stMain"] [data-testid="stMarkdownContainer"] > p:last-child {{
    margin-bottom: 0 !important;
}}
[data-testid="stMain"] hr {{ border-color: #edf0f4 !important; }}

.s5-empty-alert {{ padding:13px 16px; border:1px solid #dbe9c7; border-radius:12px; background:#f5f9ed; color:#54742a; font-weight:600; }}

@media (max-width: 1180px) {{
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ width:215px !important; min-width:215px !important; }}
    [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {{ padding:20px 22px 36px !important; }}
}}
@media (max-width: 850px) {{
    [data-testid="stSidebar"], [data-testid="stSidebar"] > div {{ width:205px !important; min-width:205px !important; }}
    [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {{ padding:16px 16px 32px !important; }}
}}
@media (max-width: 640px) {{
    [data-testid="stMainBlockContainer"], [data-testid="stMain"] .block-container {{ padding:14px 12px 28px !important; }}
}}
</style>
"""


@st.fragment(run_every=1.0)
def _render_live_operator_page(state, current_user, page):
    expire_unused_parking_reservations(state)
    if page == "network":
        render_sub05(state, current_user, page="overview")
        same_page = "Tổng quan mạng lưới"
    else:
        expire_unused_schedules(state)
        render_sub04(state, current_user, page="resources")
        same_page = "Giám sát tài nguyên sạc"

    destination = st.session_state.get("sub05_nav_request")
    if destination and destination != same_page:
        st.rerun()


# ===========================================================================
# MAIN ENTRY ROUTER
# ===========================================================================
state = get_state()
current_user = render_auth(state, render_sidebar=False)
if current_user is None:
    st.stop()

expire_unused_schedules(state)
expire_unused_parking_reservations(state)
role = current_user["role"]

if role == ROLE_OPERATOR:
    requested_page = st.session_state.pop("sub05_nav_request", None)
    request_map = {
        "Tổng quan mạng lưới": "network",
        "network": "network",
        "Điều chuyển xe": "dispatch",
        "dispatch": "dispatch",
        "Giám sát tài nguyên sạc": "resources",
        "resources": "resources",
        "Ưu tiên yêu cầu sạc": "priority",
        "priority": "priority",
        "Lập lịch sạc": "schedule",
        "schedule": "schedule",
        "Sự cố": "incidents",
        "Quản lý sự cố": "incidents",
        "incidents": "incidents",
        "What-if Simulation": "simulation",
        "simulation": "simulation",
    }
    if requested_page in request_map:
        st.session_state["operator_nav"] = request_map[requested_page]

    st.markdown(OPERATOR_CSS, unsafe_allow_html=True)

    open_incidents = sum(
        1 for inc in state.get("incidents", []) if inc.get("status") == "OPEN"
    )
    if open_incidents > 0:
        st.markdown(
            "<style>"
            "[data-testid='stSidebar'] .st-key-operator_nav_button_incidents button::after{"
            f"content:'{open_incidents}';margin-left:auto;padding:1px 8px;border-radius:999px;"
            "background:#ffe4e6;color:#e11d48;font-size:11px;font-weight:700;line-height:1.4;"
            "}"
            "[data-testid='stSidebar'] .st-key-operator_nav_button_incidents button[kind='primary']::after{"
            "background:#ffffff;color:#658520;"
            "}"
            "</style>",
            unsafe_allow_html=True,
        )

    operator_pages = {
        "network": "Tổng quan mạng lưới",
        "dispatch": "Điều chuyển xe",
        "resources": "Giám sát tài nguyên sạc",
        "priority": "Ưu tiên yêu cầu sạc",
        "schedule": "Lập lịch sạc",
        "incidents": "Sự cố",
        "simulation": "What-if Simulation",
    }
    st.session_state.setdefault("operator_nav", "network")

    with st.sidebar:
        st.markdown(
            '<div class="operator-brand">'
            '<div class="eyebrow">OPERATOR CONSOLE</div>'
            '<div class="brand-name">Smart E-Mobility Hub</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        def _choose_operator_page(page_key: str) -> None:
            st.session_state["operator_nav"] = page_key
            if page_key == "network":
                st.session_state["sub05_page"] = "overview"

        for page_key, page_label in operator_pages.items():
            active = st.session_state.get("operator_nav") == page_key
            st.button(
                page_label,
                key=f"operator_nav_button_{page_key}",
                type="primary" if active else "secondary",
                on_click=_choose_operator_page,
                args=(page_key,),
                **_FULL,
            )
        selected_page = st.session_state.get("operator_nav", "network")
        name = current_user.get("display_name", "Operator")
        subtitle = current_user.get("email") or current_user.get("username") or "Operator"
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "OP"
        with st.container(key="operator_footer"):
            p_col, out_col = st.columns([4.2, 1.0])
            p_col.markdown(
                '<div class="operator-profile">'
                f'<div class="operator-avatar">{escape(initials)}</div>'
                '<div style="min-width:0"><div class="operator-profile-name">'
                f"{escape(name)}</div><div class='operator-profile-role'>{escape(subtitle)}</div></div></div>",
                unsafe_allow_html=True,
            )
            with out_col:
                if st.button("\u200B", key="operator_sign_out", help="Đăng xuất"):
                    clear_simulation_view()
                    sign_out()
                    st.rerun()

    if selected_page in ("network", "resources"):
        _render_live_operator_page(state, current_user, selected_page)
    elif selected_page == "dispatch":
        render_sub05(state, current_user, page="dispatch")
    elif selected_page == "priority":
        render_sub04(state, current_user, page="priority")
    elif selected_page == "schedule":
        render_sub04(state, current_user, page="schedule")
    elif selected_page == "incidents":
        render_sub05(state, current_user, page="incidents")
    elif selected_page == "simulation":
        render_sub06(state, current_user)

else:
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

    nav_items = [
        ("explore", "📍\nKhám phá"),
        ("mine", "🔖\nCủa tôi"),
        ("parking", "⚡\nĐỗ & Sạc"),
        ("profile", "👤\nHồ sơ"),
    ]
    with st.container(key="student_bottom_nav"):
        nav_cols = st.columns(4)
        for col, (tab_key, tab_label) in zip(nav_cols, nav_items):
            if col.button(
                tab_label,
                key=f"mob_nav_{tab_key}",
                type="primary" if active_tab == tab_key else "secondary",
                **_FULL,
            ):
                st.session_state["student_nav_tab"] = tab_key
                st.rerun()
