"""Streamlit Mobile UI for SUB-01: Mobility Discovery, Vehicle Search & Reservation."""

from __future__ import annotations

from datetime import datetime
from html import escape
import streamlit as st

from modules.sub01.service import (
    create_reservation,
    get_hub_list,
    get_student_reservations,
)

_VN_HUB_NAMES = {
    "HUB-01": "Trạm Ga Metro ĐHQG",
    "HUB-02": "Trạm KTX Khu A",
    "HUB-03": "Trạm ĐH Bách Khoa (CS2)",
    "HUB-04": "Trạm ĐH Công nghệ Thông tin (UIT)",
    "HUB-05": "Trạm KTX Khu B",
}

_SUB01_CSS = """
<style>
.s1-greet-sub {
    font-size: 0.84rem;
    color: #64748B;
    font-weight: 500;
}
.s1-greet-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #0F172A;
    line-height: 1.15;
    letter-spacing: -0.02em;
}
.s1-avatar-circle {
    width: 38px;
    height: 38px;
    border-radius: 999px;
    background: #ECFCCB;
    color: #365314;
    font-size: 0.82rem;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.s1-map-box {
    background: linear-gradient(180deg, #F0FDF4 0%, #ECFDF5 100%);
    border: 1px solid #DCFCE7;
    border-radius: 18px;
    padding: 6px 8px;
    margin: 8px 0 14px 0;
}
.s1-sec-hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    color: #334155;
    text-transform: uppercase;
    margin: 12px 0 8px 0;
}
.s1-hub-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 16px;
    padding: 13px 14px;
    margin-bottom: 10px;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.025);
}
.s1-hub-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
}
.s1-hub-left {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
}
.s1-num-badge {
    width: 22px;
    height: 22px;
    border-radius: 999px;
    background: #334155;
    color: #FFFFFF;
    font-size: 0.72rem;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.s1-hub-name {
    font-size: 0.88rem;
    font-weight: 800;
    color: #0F172A;
}
.s1-badge-low {
    background: #FFE4E6;
    color: #E11D48;
    font-size: 0.66rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
}
.s1-badge-ok {
    background: #DCFCE7;
    color: #15803D;
    font-size: 0.66rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
}
.s1-stats-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    text-align: center;
    margin-top: 10px;
}
.s1-stat-pill-box {
    background: #F8FAFC;
    border-radius: 10px;
    padding: 7px 4px;
}
.s1-stat-lbl {
    font-size: 0.66rem;
    color: #64748B;
    font-weight: 600;
}
.s1-stat-val {
    font-size: 0.92rem;
    font-weight: 800;
    color: #0F172A;
    margin-top: 2px;
}
.s1-checkout-bar {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-top: 1px solid #E2E8F0;
    padding: 12px 2px 8px 2px;
    margin-top: 10px;
}
.s1-success-circle {
    width: 48px;
    height: 48px;
    border-radius: 999px;
    background: #8CE600;
    color: #0F172A;
    font-size: 1.45rem;
    font-weight: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 4px auto 10px auto;
}
.s1-receipt-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 20px;
    padding: 16px;
    margin: 12px 0 16px 0;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}
.s1-code-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 14px 10px;
    text-align: center;
    margin: 12px 0;
}
.s1-code-digits {
    font-size: 1.9rem;
    font-weight: 900;
    letter-spacing: 0.24em;
    color: #0F172A;
    margin: 4px 0;
}
.s1-kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    font-size: 0.84rem;
}
.s1-status-blue {
    background: #DBEAFE;
    color: #1D4ED8;
    font-size: 0.72rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 999px;
}

/* Hàng 4 nút lọc trên Trang chủ vừa khít 1 dòng */
div[class*="st-key-s1_pill_"] div[data-testid="stButton"] button {
    padding: 0 4px !important;
    min-height: 2.15rem !important;
}
div[class*="st-key-s1_pill_"] div[data-testid="stButton"] button p {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
}

/* =========================================================================
   THẺ BẤM TRỰC TIẾP: KHUNG CHỮ NHẬT BO GÓC 16PX, KHÓA TRÀN NGANG
   ========================================================================= */
div[class*="st-key-s1_hub_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_svc_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvt_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvh_"] div[data-testid="stButton"] button[kind="secondary"] {
    border-radius: 16px !important;
    padding: 13px 14px !important;
    min-height: auto !important;
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    text-align: left !important;
    white-space: normal !important;
    overflow: hidden !important;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.03) !important;
}
div[class*="st-key-s1_hub_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s1_hub_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s1_svc_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s1_svc_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s1_fvt_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s1_fvt_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s1_fvh_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s1_fvh_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    text-align: left !important;
}

/* 1. Thẻ Danh sách trạm */
div[class*="st-key-s1_hub_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
}
div[class*="st-key-s1_hub_"] div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #8CE600 !important;
    background-color: #FAFFF2 !important;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    font-size: 0.86rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: normal !important;
    line-height: 1.25 !important;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) code {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 22px !important;
    height: 22px !important;
    border-radius: 999px !important;
    background-color: #334155 !important;
    color: #FFFFFF !important;
    font-family: inherit !important;
    font-size: 0.72rem !important;
    font-weight: 800 !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
}
div[class*="st-key-s1_hub_low_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "Sắp hết xe";
    margin-left: auto !important;
    background: #FFE4E6;
    color: #E11D48;
    font-size: 0.66rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
}
div[class*="st-key-s1_hub_ok_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "Còn xe";
    margin-left: auto !important;
    background: #DCFCE7;
    color: #15803D;
    font-size: 0.66rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    display: grid !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    column-gap: 6px !important;
    text-align: center !important;
    margin: 10px 0 0 0 !important;
    width: 100% !important;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) code,
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) em,
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) strong {
    display: block !important;
    background: #F8FAFC !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 6px 2px 1px 2px !important;
    font-family: inherit !important;
    font-style: normal !important;
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    color: #64748B !important;
    white-space: nowrap !important;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(3) {
    display: grid !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    column-gap: 6px !important;
    text-align: center !important;
    margin: 0 !important;
    width: 100% !important;
}
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(3) code,
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(3) em,
div[class*="st-key-s1_hub_"] button [data-testid="stMarkdownContainer"] p:nth-child(3) strong {
    display: block !important;
    background: #F8FAFC !important;
    border-radius: 0 0 10px 10px !important;
    padding: 1px 2px 7px 2px !important;
    font-family: inherit !important;
    font-style: normal !important;
    font-size: 0.92rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: nowrap !important;
}

/* 2. Thẻ Chọn dịch vụ cần đặt & Tìm xe phù hợp */
div[class*="st-key-s1_svc_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvt_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvh_on_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #F7FEE7 !important;
    border: 2px solid #8CE600 !important;
    box-shadow: 0 4px 14px rgba(140, 230, 0, 0.14) !important;
}
div[class*="st-key-s1_svc_off_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvt_off_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s1_fvh_off_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
}
div[class*="st-key-s1_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(1),
div[class*="st-key-s1_fvt_"] button [data-testid="stMarkdownContainer"] p:nth-child(1),
div[class*="st-key-s1_fvh_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    font-size: 0.92rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: normal !important;
}
div[class*="st-key-s1_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) code {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 34px !important;
    height: 34px !important;
    border-radius: 10px !important;
    background-color: #F1F5F9 !important;
    font-family: inherit !important;
    font-size: 1.05rem !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
}
div[class*="st-key-s1_svc_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s1_fvt_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s1_fvh_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "";
    margin-left: auto !important;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    border: 2px solid #8CE600;
    background: radial-gradient(circle, #365314 42%, #FFFFFF 48%);
    flex-shrink: 0;
}
div[class*="st-key-s1_svc_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s1_fvt_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s1_fvh_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "";
    margin-left: auto !important;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    border: 1.5px solid #CBD5E1;
    background: #FFFFFF;
    flex-shrink: 0;
}
div[class*="st-key-s1_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    margin: 12px 0 0 0 !important;
    font-size: 0.78rem !important;
    color: #64748B !important;
    font-weight: 500 !important;
    white-space: normal !important;
}
div[class*="st-key-s1_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) em {
    margin-left: auto !important;
    font-style: normal !important;
    color: #64748B !important;
    font-size: 0.78rem !important;
}
div[class*="st-key-s1_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) em strong {
    color: #0F172A !important;
    font-size: 0.85rem !important;
    font-weight: 800 !important;
}
div[class*="st-key-s1_fvt_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    margin: 6px 0 0 0 !important;
    font-size: 0.78rem !important;
    color: #64748B !important;
    white-space: normal !important;
}
div[class*="st-key-s1_fvh_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    margin: 4px 0 0 0 !important;
    font-size: 0.74rem !important;
    color: #16A34A !important;
    font-weight: 700 !important;
    white-space: normal !important;
}
</style>
"""


def _vn_hub(hub_obj: dict) -> str:
    return _VN_HUB_NAMES.get(hub_obj["hub_id"], hub_obj["name"])


def _short_name(full_name: str) -> str:
    parts = [p for p in (full_name or "").strip().split() if p]
    if len(parts) >= 2:
        return f"{parts[-2]} {parts[-1]}"
    return parts[0] if parts else "Sinh viên"


def _initials(full_name: str) -> str:
    parts = [p for p in (full_name or "").strip().split() if p]
    if len(parts) >= 2:
        return (parts[-2][0] + parts[-1][0]).upper()
    return parts[0][:2].upper() if parts else "SV"


def _fmt_hhmm(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return f"{dt.strftime('%H:%M')} hôm nay"
    except Exception:
        return iso_str


def _render_route_map_svg() -> str:
    nodes = [(1, 52, 62), (2, 138, 30), (3, 138, 86), (4, 230, 56), (5, 308, 66)]
    circles = [
        f'<circle cx="{cx}" cy="{cy}" r="13" fill="#334155" />'
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="11" font-weight="800" fill="#FFFFFF">{num}</text>'
        for num, cx, cy in nodes
    ]
    return f"""
    <div class="s1-map-box">
        <svg viewBox="0 0 360 112" width="100%" height="100" xmlns="http://www.w3.org/2000/svg">
            <line x1="52" y1="62" x2="138" y2="30" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
            <line x1="52" y1="62" x2="138" y2="86" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
            <line x1="138" y1="30" x2="230" y2="56" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
            <line x1="138" y1="86" x2="230" y2="56" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
            <line x1="230" y1="56" x2="308" y2="66" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
            {''.join(circles)}
        </svg>
    </div>
    """


def render(state: dict, current_user: dict) -> None:
    st.markdown(_SUB01_CSS, unsafe_allow_html=True)
    student_id = current_user["user_id"]
    display_name = current_user.get("display_name", "Sinh viên")

    hub_summaries = get_hub_list(state)
    all_vehicles = state.get("vehicles", [])
    all_parking = state.get("parking_spaces", [])
    all_charging = state.get("charging_points", [])

    enriched_hubs: list[dict] = []
    for idx, h in enumerate(hub_summaries, start=1):
        hid = h["hub_id"]
        h_vehs = [v for v in all_vehicles if v["hub_id"] == hid]
        h_parks = [p for p in all_parking if p["hub_id"] == hid]
        h_cps = [cp for cp in all_charging if cp["hub_id"] == hid]

        avail_bikes = sum(
            1 for v in h_vehs if v["status"] == "AVAILABLE" and v["vehicle_type"] == "ELECTRIC_BICYCLE"
        )
        avail_motos = sum(
            1 for v in h_vehs if v["status"] == "AVAILABLE" and v["vehicle_type"] == "ELECTRIC_MOTORCYCLE"
        )
        avail_cp = sum(1 for cp in h_cps if cp["status"] == "AVAILABLE")

        enriched_hubs.append(
            {
                **h,
                "name": _vn_hub(h),
                "index": idx,
                "total_vehicles": len(h_vehs),
                "total_parking": len(h_parks),
                "available_charging": avail_cp,
                "total_charging": len(h_cps),
                "avail_bikes": avail_bikes,
                "avail_motos": avail_motos,
            }
        )

    hub_by_id = {h["hub_id"]: h for h in enriched_hubs}
    st.session_state.setdefault("s1_view", "home")
    view = st.session_state["s1_view"]

    # =========================================================================
    # MÀN HÌNH: ĐẶT CHỖ THÀNH CÔNG
    # =========================================================================
    if view == "booking_success":
        back_col, _ = st.columns([1, 5])
        if back_col.button("‹", key="s1_succ_back", use_container_width=True):
            st.session_state["s1_view"] = "home"
            st.rerun()

        reservations = get_student_reservations(state, student_id)
        pending_list = [r for r in reservations if r["status"] == "PENDING"]
        rsv = pending_list[0] if pending_list else (reservations[0] if reservations else None)

        if rsv is None:
            st.session_state["s1_view"] = "home"
            st.rerun()

        hub_name = hub_by_id.get(rsv["hub_id"], {}).get("name", _VN_HUB_NAMES.get(rsv["hub_id"], rsv["hub_id"]))
        spaced_code = " ".join(list(str(rsv["pickup_code"])))

        st.markdown(
            f"""
            <div class="s1-success-circle">✓</div>
            <div style="text-align:center;font-size:1.35rem;font-weight:800;color:#0F172A;">Đặt chỗ thành công</div>
            <div class="s1-receipt-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:0.72rem;font-weight:700;color:#64748B;">MÃ RESERVATION</span>
                    <span style="font-size:0.84rem;font-weight:800;color:#0F172A;">{escape(rsv['reservation_id'])}</span>
                </div>
                <div class="s1-code-box">
                    <div style="font-size:0.72rem;font-weight:700;color:#64748B;">MÃ LẤY XE</div>
                    <div class="s1-code-digits">{escape(spaced_code)}</div>
                    <div style="font-size:0.72rem;color:#64748B;">Nhập mã này hoặc quét QR trên xe khi nhận</div>
                </div>
                <div style="border-top:1px solid #F1F5F9;padding-top:8px;">
                    <div class="s1-kv-row">
                        <span style="color:#64748B;">Hub nhận xe</span>
                        <span style="font-weight:800;color:#0F172A;">{escape(hub_name)}</span>
                    </div>
                    <div class="s1-kv-row">
                        <span style="color:#64748B;">Trạng thái</span>
                        <span class="s1-status-blue">Đã đặt</span>
                    </div>
                    <div class="s1-kv-row">
                        <span style="color:#64748B;">Nhận xe trước</span>
                        <span style="font-weight:800;color:#0F172A;">{escape(_fmt_hhmm(rsv['expires_at']))}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Đến nhận xe →", type="primary", use_container_width=True, key="s1_succ_goto_pickup"):
            st.session_state["s1_view"] = "home"
            st.session_state["s2_view"] = "pickup"
            st.session_state["student_nav_tab"] = "mine"
            st.rerun()

        st.write("")
        if st.button("Xem đặt chỗ của tôi", type="secondary", use_container_width=True, key="s1_succ_goto_mine"):
            st.session_state["s1_view"] = "home"
            st.session_state["s2_view"] = "main"
            st.session_state["student_nav_tab"] = "mine"
            st.rerun()
        return

    # =========================================================================
    # MÀN HÌNH: TÌM XE PHÙ HỢP
    # =========================================================================
    if view == "find_vehicle":
        c_back, c_title = st.columns([1, 4.5])
        if c_back.button("‹", key="s1_fv_back", use_container_width=True):
            st.session_state["s1_view"] = "home"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.25rem;font-weight:800;color:#0F172A;padding-top:6px;">Tìm xe phù hợp</div>',
            unsafe_allow_html=True,
        )

        st.session_state.setdefault("s1_fv_type", "ELECTRIC_BICYCLE")
        fv_type = st.session_state["s1_fv_type"]

        vc1, vc2 = st.columns(2)
        with vc1:
            is_bike = fv_type == "ELECTRIC_BICYCLE"
            if st.button(
                "🚲 Xe đạp điện\n\n**2.000đ**/15p",
                key=f"s1_fvt_{'on' if is_bike else 'off'}_bike",
                use_container_width=True,
            ):
                if not is_bike:
                    st.session_state["s1_fv_type"] = "ELECTRIC_BICYCLE"
                    st.rerun()

        with vc2:
            is_moto = fv_type == "ELECTRIC_MOTORCYCLE"
            if st.button(
                "🛵 Xe máy điện\n\n**5.000đ**/15p",
                key=f"s1_fvt_{'on' if is_moto else 'off'}_moto",
                use_container_width=True,
            ):
                if not is_moto:
                    st.session_state["s1_fv_type"] = "ELECTRIC_MOTORCYCLE"
                    st.rerun()

        st.markdown(
            """
            <div class="s1-sec-hdr">
                <span>HUB CÒN XE</span>
                <span class="s1-badge-ok">Gần nhất trước</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        matching_hubs = [
            h
            for h in enriched_hubs
            if (h["avail_bikes"] > 0 if fv_type == "ELECTRIC_BICYCLE" else h["avail_motos"] > 0)
        ]

        if not matching_hubs:
            st.info("Hiện chưa có trạm nào còn loại xe này.")
            return

        valid_hids = [h["hub_id"] for h in matching_hubs]
        if st.session_state.get("s1_fv_hub") not in valid_hids:
            st.session_state["s1_fv_hub"] = valid_hids[0]
        chosen_hid = st.session_state["s1_fv_hub"]

        for h in matching_hubs:
            is_sel = h["hub_id"] == chosen_hid
            cnt = h["avail_bikes"] if fv_type == "ELECTRIC_BICYCLE" else h["avail_motos"]
            if st.button(
                f"{h['index']} · {h['name']}\n\nCòn {cnt} xe sẵn sàng",
                key=f"s1_fvh_{'on' if is_sel else 'off'}_{h['hub_id']}",
                use_container_width=True,
            ):
                if not is_sel:
                    st.session_state["s1_fv_hub"] = h["hub_id"]
                    st.rerun()

        chosen_hub = hub_by_id[chosen_hid]
        st.markdown(
            f"""
            <div class="s1-checkout-bar">
                <div>
                    <div style="font-size:0.74rem;color:#64748B;">Trạm đang chọn:</div>
                    <div style="font-size:0.96rem;font-weight:800;color:#0F172A;">{escape(chosen_hub['name'])}</div>
                </div>
                <span class="s1-badge-ok">Giữ chỗ miễn phí 15p</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Xác nhận & Nhận mã lấy xe →", type="primary", use_container_width=True, key="s1_fv_confirm"):
            try:
                create_reservation(state, student_id, chosen_hid)
                st.session_state["preferred_vehicle_type"] = fv_type
                st.session_state["s1_view"] = "booking_success"
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        return

    # =========================================================================
    # MÀN HÌNH: CHI TIẾT TRẠM & ĐẶT CHỖ
    # =========================================================================
    if view == "hub_detail":
        detail_hub_id = st.session_state.get("s1_detail_hub_id")
        if detail_hub_id not in hub_by_id:
            st.session_state["s1_view"] = "home"
            st.rerun()

        hub = hub_by_id[detail_hub_id]
        c_back, c_title = st.columns([1, 4.5])
        if c_back.button("‹", key="s1_det_back", use_container_width=True):
            st.session_state["s1_view"] = "home"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.22rem;font-weight:800;color:#0F172A;padding-top:6px;">Chi tiết trạm &amp; Đặt chỗ</div>',
            unsafe_allow_html=True,
        )

        badge_html = (
            '<span class="s1-badge-low">Sắp hết xe</span>'
            if hub["available_vehicle_count"] <= 2
            else '<span class="s1-badge-ok">Còn xe</span>'
        )
        st.markdown(
            f"""
            <div class="s1-hub-card">
                <div class="s1-hub-top">
                    <div class="s1-hub-left">
                        <span class="s1-num-badge">{hub['index']}</span>
                        <span class="s1-hub-name">{escape(hub['name'])}</span>
                    </div>
                    {badge_html}
                </div>
                <div class="s1-stats-row">
                    <div class="s1-stat-pill-box">
                        <div class="s1-stat-lbl">Xe khả dụng</div>
                        <div class="s1-stat-val">{hub['available_vehicle_count']}/{hub['total_vehicles']}</div>
                    </div>
                    <div class="s1-stat-pill-box">
                        <div class="s1-stat-lbl">Chỗ đỗ trống</div>
                        <div class="s1-stat-val">{hub['available_parking_space_count']}/{hub['total_parking']}</div>
                    </div>
                    <div class="s1-stat-pill-box">
                        <div class="s1-stat-lbl">Chỗ sạc trống</div>
                        <div class="s1-stat-val">{hub['available_charging']}/{hub['total_charging']}</div>
                    </div>
                </div>
            </div>
            <div class="s1-sec-hdr"><span>CHỌN DỊCH VỤ CẦN ĐẶT</span></div>
            """,
            unsafe_allow_html=True,
        )

        st.session_state.setdefault("s1_selected_service", "bike")
        selected_svc = st.session_state["s1_selected_service"]

        services = [
            {
                "key": "bike",
                "label": "`🚲` Xe đạp điện\n\nGiá thuê: ***2.000đ** / 15 phút*",
            },
            {
                "key": "moto",
                "label": "`🛵` Xe máy điện\n\nGiá thuê: ***5.000đ** / 15 phút*",
            },
            {
                "key": "charger",
                "label": "`⚡` Trụ sạc xe cá nhân\n\nĐơn giá điện: ***1.000đ** / kWh*",
            },
        ]

        for svc in services:
            is_sel = selected_svc == svc["key"]
            if st.button(
                svc["label"],
                key=f"s1_svc_{'on' if is_sel else 'off'}_{svc['key']}",
                use_container_width=True,
            ):
                if not is_sel:
                    st.session_state["s1_selected_service"] = svc["key"]
                    st.rerun()

        svc_names = {"bike": "Xe đạp điện", "moto": "Xe máy điện", "charger": "Trụ sạc xe cá nhân"}
        hold_note = "0đ (Miễn phí 15p)" if selected_svc in ("bike", "moto") else "Đặt lịch sạc tại Hub"

        st.markdown(
            f"""
            <div class="s1-checkout-bar">
                <div>
                    <div style="font-size:0.74rem;color:#64748B;">Dịch vụ đã chọn:</div>
                    <div style="font-size:0.98rem;font-weight:800;color:#0F172A;">{svc_names[selected_svc]}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.74rem;color:#64748B;">Tạm giữ chỗ:</div>
                    <div style="font-size:0.9rem;font-weight:800;color:#16A34A;">{hold_note}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if selected_svc in ("bike", "moto"):
            if st.button("Xác nhận đặt giữ xe ngay →", type="primary", use_container_width=True, key="s1_det_book_veh"):
                try:
                    create_reservation(state, student_id, hub["hub_id"])
                    st.session_state["preferred_vehicle_type"] = (
                        "ELECTRIC_BICYCLE" if selected_svc == "bike" else "ELECTRIC_MOTORCYCLE"
                    )
                    st.session_state["s1_view"] = "booking_success"
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        else:
            if st.button("Đặt trụ sạc xe cá nhân →", type="primary", use_container_width=True, key="s1_det_book_chg"):
                st.session_state["s3_selected_hub"] = hub["hub_id"]
                st.session_state["s3_view"] = "charging"
                st.session_state["s1_view"] = "home"
                st.session_state["student_nav_tab"] = "parking"
                st.rerun()
        return

    # =========================================================================
    # MÀN HÌNH CHÍNH: TRANG CHỦ / TÌM TRẠM
    # =========================================================================
    h_left, h_mid, h_right = st.columns([2.5, 1.35, 0.7])
    h_left.markdown(
        f"""
        <div class="s1-greet-sub">Xin chào, {escape(_short_name(display_name))}</div>
        <div class="s1-greet-title">Mobility Hub</div>
        """,
        unsafe_allow_html=True,
    )
    if h_mid.button("Tìm xe", type="primary", key="s1_top_find_veh", use_container_width=True):
        st.session_state["s1_view"] = "find_vehicle"
        st.rerun()
    h_right.markdown(
        f'<div style="padding-top:4px;text-align:right;"><span class="s1-avatar-circle">{escape(_initials(display_name))}</span></div>',
        unsafe_allow_html=True,
    )

    search_query = st.text_input(
        "Tìm trạm",
        placeholder="🔍 Tìm trạm",
        label_visibility="collapsed",
        key="s1_search_hub",
    ).strip().lower()

    st.session_state.setdefault("s1_filter_pill", "Tất cả")
    active_pill = st.session_state["s1_filter_pill"]
    pills = ["Tất cả", "Còn xe", "Còn chỗ đỗ", "Có cổng sạc"]
    p_cols = st.columns(4)
    for col, p_lbl in zip(p_cols, pills):
        if col.button(
            p_lbl,
            key=f"s1_pill_{p_lbl}",
            type="primary" if active_pill == p_lbl else "secondary",
            use_container_width=True,
        ):
            st.session_state["s1_filter_pill"] = p_lbl
            st.rerun()

    st.markdown(_render_route_map_svg(), unsafe_allow_html=True)

    filtered_hubs = []
    for h in enriched_hubs:
        if search_query and (
            search_query not in h["name"].lower() and search_query not in h["address"].lower()
        ):
            continue
        if active_pill == "Còn xe" and h["available_vehicle_count"] <= 0:
            continue
        if active_pill == "Còn chỗ đỗ" and h["available_parking_space_count"] <= 0:
            continue
        if active_pill == "Có cổng sạc" and h["available_charging"] <= 0:
            continue
        filtered_hubs.append(h)

    st.markdown('<div class="s1-sec-hdr"><span>DANH SÁCH TRẠM</span></div>', unsafe_allow_html=True)

    if not filtered_hubs:
        st.info("Không tìm thấy trạm Hub phù hợp.")
        return

    for h in filtered_hubs:
        is_low = h["available_vehicle_count"] <= 2
        card_md = (
            f"`{h['index']}` {h['name']}\n\n"
            f"`Xe khả dụng` *Chỗ đỗ trống* **Chỗ sạc trống**\n\n"
            f"`{h['available_vehicle_count']}/{h['total_vehicles']}` "
            f"*{h['available_parking_space_count']}/{h['total_parking']}* "
            f"**{h['available_charging']}/{h['total_charging']}**"
        )
        if st.button(
            card_md,
            key=f"s1_hub_{'low' if is_low else 'ok'}_{h['hub_id']}",
            use_container_width=True,
        ):
            st.session_state["s1_detail_hub_id"] = h["hub_id"]
            st.session_state["s1_view"] = "hub_detail"
            st.rerun()