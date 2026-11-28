"""Entry point for the Smart E-Mobility Hub MVP."""

from html import escape
from urllib.parse import quote
import streamlit as st

from shared.auth import render_auth, sign_out
from shared.state import get_state
from shared.enums import ROLE_OPERATOR
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


# These styles are injected only for an Operator session. Student screens
# continue using their original UI and are not affected by Operator CSS.
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
[data-testid="collapsedControl"] {{
    pointer-events: auto !important;
    visibility: visible !important;
    opacity: 1 !important;
    background: #ffffff !important;
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
}}
[data-testid="stSidebar"] {{
    width: clamp(220px, 16.5vw, 250px) !important;
    min-width: 220px !important;
    max-width: 250px !important;
    background: #ffffff !important;
    border-right: 1px solid #eef2f6 !important;
}}
[data-testid="stSidebar"] > div {{ width: clamp(220px, 16.5vw, 250px) !important; }}
[data-testid="stSidebarHeader"] {{
    height: auto !important;
    min-height: 0 !important;
    padding: 8px 14px 0 !important;
    margin: 0 !important;
}}
[data-testid="stSidebarContent"] {{
    padding: 0 14px 14px !important;
    display: flex !important;
    flex-direction: column !important;
}}
[data-testid="stSidebarUserContent"] {{
    padding: 2px 0 0 !important;
    flex: 1 1 auto !important;
    display: flex !important;
    flex-direction: column !important;
}}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:has(.st-key-operator_footer):not(.st-key-operator_footer):not([data-testid="stColumn"] [data-testid="stVerticalBlock"]) {{
    gap: 6px !important;
    min-height: calc(100vh - 108px) !important;
    display: flex !important;
    flex-direction: column !important;
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
    font-weight: 500 !important;
    font-size: .84rem !important;
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
    font-weight: 600 !important;
}}
[data-testid="stSidebar"] [class*="st-key-operator_nav_button_"] button[kind="primary"]::before {{
    background-color: #ffffff !important;
}}

/* Sidebar footer pinned cleanly above bottom edge: profile + inline logout icon */
[data-testid="stSidebar"] .st-key-operator_footer,
[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:has(> .st-key-operator_footer) {{
    margin-top: auto !important;
}}
[data-testid="stSidebar"] .st-key-operator_footer {{
    border-top: 1px solid #edf0f4;
    padding-top: 12px;
    padding-bottom: 4px;
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
    color: #94a3b8; font-size: .72rem; margin-top: 1px;
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

[data-testid="stSidebar"] .st-key-operator_footer {{
    position: relative !important;
    top: 20px !important;
}}
</style>
"""

state = get_state()
current_user = render_auth(state)
if current_user is None:
    st.stop()

role = current_user["role"]

if role == ROLE_OPERATOR:
    # Resolve navigation requests raised by SUB-05/06 before creating the radio.
    requested_page = st.session_state.pop("sub05_nav_request", None)
    request_map = {
        "Tổng quan mạng lưới": "network",
        "Điều chuyển xe": "dispatch",
        "Giám sát tài nguyên sạc": "resources",
        "Ưu tiên yêu cầu sạc": "priority",
        "Lập lịch sạc": "schedule",
        "Sự cố": "incidents",
        "What-if Simulation": "simulation",
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
            "background:#ffe4e6;color:#e11d48;font-size:.72rem;font-weight:600;line-height:1.4;"
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
            '</div>',
            unsafe_allow_html=True,
        )

        def _choose_operator_page(page_key):
            st.session_state["operator_nav"] = page_key

        for page_key, page_label in operator_pages.items():
            active = st.session_state.get("operator_nav") == page_key
            st.button(
                page_label,
                key=f"operator_nav_button_{page_key}",
                type="primary" if active else "secondary",
                use_container_width=True,
                on_click=_choose_operator_page,
                args=(page_key,),
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
                f'{escape(name)}</div><div class="operator-profile-role">{escape(subtitle)}</div></div></div>',
                unsafe_allow_html=True,
            )
            with out_col:
                if st.button("\u200B", key="operator_sign_out", help="Đăng xuất"):
                    sign_out()
                    st.rerun()

    if selected_page == "network":
        render_sub05(state, current_user, page="overview")
    elif selected_page == "dispatch":
        render_sub05(state, current_user, page="dispatch")
    elif selected_page == "resources":
        render_sub04(state, current_user, page="resources")
    elif selected_page == "priority":
        render_sub04(state, current_user, page="priority")
    elif selected_page == "schedule":
        render_sub04(state, current_user, page="schedule")
    elif selected_page == "incidents":
        render_sub05(state, current_user, page="incidents")
    elif selected_page == "simulation":
        render_sub06(state, current_user)

else:
    # Original Student and Private EV Student navigation is unchanged.
    st.sidebar.divider()
    st.sidebar.caption(f"Người dùng: {current_user['display_name']}")

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