"""Streamlit Mobile UI for SUB-03: Private EV Parking & Charging."""

from __future__ import annotations

from html import escape
import streamlit as st

from modules.sub03 import service as sub03_service
from shared.enums import (
    CHARGING_REQUEST_CONFIRMED,
    CHARGING_REQUEST_PENDING,
    PARKING_AVAILABLE,
    PARKING_IN_USE,
    PARKING_RESERVED,
)

_VN_HUB_NAMES = {
    "HUB-01": "Trạm Ga Metro ĐHQG",
    "HUB-02": "Trạm KTX Khu A",
    "HUB-03": "Trạm ĐH Bách Khoa (CS2)",
    "HUB-04": "Trạm ĐH Công nghệ Thông tin (UIT)",
    "HUB-05": "Trạm KTX Khu B",
}

_RECEIPT_HUB_NAMES = {
    "HUB-01": "Ga Metro ĐHQG",
    "HUB-02": "KTX Khu A",
    "HUB-03": "ĐH Bách Khoa (CS2)",
    "HUB-04": "ĐH CNTT (UIT)",
    "HUB-05": "KTX Khu B",
}

_PILL_HUB_NAMES = {
    "HUB-03": "ĐH Bách Khoa (CS2)",
    "HUB-02": "KTX Khu A",
    "HUB-01": "Ga Metro ĐHQG",
    "HUB-04": "ĐH CNTT (UIT)",
    "HUB-05": "KTX Khu B",
}

_SUB03_CSS = """
<style>
.s3-sec-hdr {
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: #334155;
    text-transform: uppercase;
    margin: 14px 0 8px 0;
}
.s3-hub-summary {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 16px;
    padding: 13px 14px;
    margin: 8px 0 12px 0;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.025);
}
.s3-two-boxes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 10px;
}
.s3-mini-box {
    background: #F8FAFC;
    border-radius: 12px;
    padding: 9px 10px;
}
.s3-legend {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.66rem;
    font-weight: 700;
    color: #475569;
}
.s3-success-circle {
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
    margin: 6px auto 10px auto;
}
.s3-receipt-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 20px;
    padding: 16px;
    margin: 14px 0 18px 0;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.03);
}
.s3-big-slot-box {
    background: #F8FAFC;
    border-radius: 14px;
    padding: 14px 10px;
    text-align: center;
    margin-bottom: 12px;
}
.s3-kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    font-size: 0.82rem;
}
.s3-kv-divider {
    border-top: 1px solid #F1F5F9;
    margin: 4px 0;
}

/* Nút quay lại tròn < */
div[class*="st-key-s3_"][class*="_back"] div[data-testid="stButton"] button {
    width: 36px !important;
    height: 36px !important;
    min-height: 36px !important;
    border-radius: 999px !important;
    background-color: #F1F5F9 !important;
    border: none !important;
    color: #334155 !important;
    padding: 0 !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}

/* Thanh chọn trạm Hub dạng pill đen #0F172A khi active */
div[class*="st-key-s3_main_hub_on_"] div[data-testid="stButton"] button {
    background-color: #0F172A !important;
    color: #FFFFFF !important;
    border: 1px solid #0F172A !important;
    border-radius: 999px !important;
    padding: 0 6px !important;
    min-height: 2.1rem !important;
    box-shadow: none !important;
}
div[class*="st-key-s3_main_hub_on_"] div[data-testid="stButton"] button p {
    color: #FFFFFF !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
}
div[class*="st-key-s3_main_hub_off_"] div[data-testid="stButton"] button {
    background-color: #FFFFFF !important;
    color: #475569 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 999px !important;
    padding: 0 6px !important;
    min-height: 2.1rem !important;
    box-shadow: none !important;
}
div[class*="st-key-s3_main_hub_off_"] div[data-testid="stButton"] button p {
    color: #475569 !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
}

/* Nút Đổi trạm nhỏ gọn */
div[class*="st-key-s3_cg_switch_hub"] div[data-testid="stButton"] button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    min-height: auto !important;
    padding: 2px 4px !important;
    text-align: right !important;
}
div[class*="st-key-s3_cg_switch_hub"] div[data-testid="stButton"] button p {
    color: #16A34A !important;
    font-size: 0.76rem !important;
    font-weight: 800 !important;
    text-align: right !important;
}

/* =========================================================================
   THẺ DỊCH VỤ CHÍNH (ĐẶT CHỖ ĐỖ XE & ĐĂNG KÝ LỊCH SẠC)
   ========================================================================= */
div[class*="st-key-s3_svc_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 16px !important;
    padding: 13px 14px !important;
    min-height: auto !important;
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    text-align: left !important;
    white-space: normal !important;
    box-shadow: 0 2px 8px rgba(15, 23, 42, 0.025) !important;
}
div[class*="st-key-s3_svc_"] div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #8CE600 !important;
    background-color: #FAFFF2 !important;
}
div[class*="st-key-s3_svc_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s3_svc_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
}
div[class*="st-key-s3_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
    width: 100% !important;
    margin: 0 !important;
    font-size: 0.92rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: normal !important;
}
div[class*="st-key-s3_svc_open_parking"] button [data-testid="stMarkdownContainer"] p:nth-child(1) code {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 34px !important;
    height: 34px !important;
    border-radius: 10px !important;
    background-color: #EFF6FF !important;
    font-family: inherit !important;
    font-size: 1.05rem !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
}
div[class*="st-key-s3_svc_open_charging"] button [data-testid="stMarkdownContainer"] p:nth-child(1) code {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 34px !important;
    height: 34px !important;
    border-radius: 10px !important;
    background-color: #FEF9C3 !important;
    font-family: inherit !important;
    font-size: 1.05rem !important;
    padding: 0 !important;
    flex-shrink: 0 !important;
}
div[class*="st-key-s3_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "›";
    margin-left: auto !important;
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    color: #64748B;
    font-size: 0.95rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
div[class*="st-key-s3_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    margin: 10px 0 0 0 !important;
    padding-top: 8px !important;
    border-top: 1px solid #F1F5F9 !important;
    text-align: right !important;
    font-size: 0.76rem !important;
    color: #64748B !important;
    font-weight: 500 !important;
}
div[class*="st-key-s3_svc_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) strong {
    color: #0F172A !important;
    font-weight: 800 !important;
}

/* =========================================================================
   Ô ĐỖ XE, CA GỬI XE, TRỤ SẠC, KHUNG GIỜ SẠC (CÓ DẤU TÍCH XANH KHI CHỌN)
   ========================================================================= */
div[class*="st-key-s3_sl_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_sh_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_cp_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_ts_"] div[data-testid="stButton"] button[kind="secondary"] {
    border-radius: 14px !important;
    padding: 10px 6px !important;
    min-height: auto !important;
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    white-space: normal !important;
    position: relative !important;
    overflow: visible !important;
}
div[class*="st-key-s3_sl_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s3_sl_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s3_sh_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s3_sh_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s3_cp_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s3_cp_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s3_ts_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s3_ts_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
}

/* Trạng thái ĐANG CHỌN: nền xanh nhạt #F7FEE7, viền #8CE600, dấu tích ✓ góc trên phải */
div[class*="st-key-s3_sl_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_cp_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_sh_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_ts_on_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #F7FEE7 !important;
    border: 2px solid #8CE600 !important;
    color: #0F172A !important;
}
div[class*="st-key-s3_sl_on_"] div[data-testid="stButton"] button[kind="secondary"]::after,
div[class*="st-key-s3_cp_on_"] div[data-testid="stButton"] button[kind="secondary"]::after,
div[class*="st-key-s3_sh_on_"] div[data-testid="stButton"] button[kind="secondary"]::after,
div[class*="st-key-s3_ts_on_"] div[data-testid="stButton"] button[kind="secondary"]::after {
    content: "✓";
    position: absolute;
    top: -6px;
    right: -6px;
    width: 17px;
    height: 17px;
    border-radius: 999px;
    background-color: #8CE600;
    color: #0F172A;
    font-size: 0.65rem;
    font-weight: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(140, 230, 0, 0.35);
}

/* Trạng thái TRỐNG / CHƯA CHỌN */
div[class*="st-key-s3_sl_av_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_cp_av_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_sh_off_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_ts_off_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    color: #0F172A !important;
}

/* Trạng thái BẬN / ĐÃ KÍN / BẢO TRÌ */
div[class*="st-key-s3_sl_bz_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_cp_bz_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_cp_mt_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s3_ts_bz_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #F1F5F9 !important;
    border: 1.5px solid #E2E8F0 !important;
    color: #94A3B8 !important;
    opacity: 1 !important;
}

/* Căn chữ và tô màu dòng phụ trong từng loại thẻ */
div[class*="st-key-s3_sl_"] button [data-testid="stMarkdownContainer"] p,
div[class*="st-key-s3_sh_"] button [data-testid="stMarkdownContainer"] p,
div[class*="st-key-s3_cp_"] button [data-testid="stMarkdownContainer"] p {
    margin: 1px 0 !important;
    text-align: center !important;
    line-height: 1.25 !important;
    font-size: 0.76rem !important;
    white-space: normal !important;
}
div[class*="st-key-s3_sl_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #365314 !important;
    font-weight: 700 !important;
    font-size: 0.68rem !important;
}
div[class*="st-key-s3_sl_av_"] button [data-testid="stMarkdownContainer"] p:nth-child(2),
div[class*="st-key-s3_sh_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #64748B !important;
    font-weight: 600 !important;
    font-size: 0.68rem !important;
}
div[class*="st-key-s3_sl_bz_"] button [data-testid="stMarkdownContainer"] p {
    color: #94A3B8 !important;
}

/* Màu chữ Trụ sạc */
div[class*="st-key-s3_cp_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(2),
div[class*="st-key-s3_cp_av_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #16A34A !important;
    font-weight: 800 !important;
    font-size: 0.7rem !important;
}
div[class*="st-key-s3_cp_bz_"] button [data-testid="stMarkdownContainer"] p {
    color: #94A3B8 !important;
    font-size: 0.7rem !important;
}
div[class*="st-key-s3_cp_mt_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    color: #94A3B8 !important;
    font-size: 0.74rem !important;
}
div[class*="st-key-s3_cp_mt_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #E11D48 !important;
    font-weight: 800 !important;
    font-size: 0.7rem !important;
}

/* Khung giờ sạc căn trái */
div[class*="st-key-s3_ts_"] button [data-testid="stMarkdownContainer"] p {
    margin: 1px 4px !important;
    text-align: left !important;
    line-height: 1.3 !important;
    font-size: 0.78rem !important;
    white-space: normal !important;
}
div[class*="st-key-s3_ts_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(2),
div[class*="st-key-s3_ts_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #16A34A !important;
    font-weight: 700 !important;
    font-size: 0.68rem !important;
}
div[class*="st-key-s3_ts_bz_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    color: #94A3B8 !important;
}
div[class*="st-key-s3_ts_bz_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    color: #E11D48 !important;
    font-weight: 700 !important;
    font-size: 0.68rem !important;
}
</style>
"""


def _format_slot_code(space_id: str, fallback_idx: int) -> str:
    digits = "".join(ch for ch in space_id if ch.isdigit())
    if digits:
        return f"P-{int(digits):02d}"
    return f"P-{fallback_idx:02d}"


def render(state: dict, current_user: dict) -> None:
    st.markdown(_SUB03_CSS, unsafe_allow_html=True)
    student_id = (
        current_user.get("user_id")
        or current_user.get("id")
        or current_user.get("username")
        or "PSTU-001"
    )

    hubs = state["hubs"]
    hub_ids = [h["hub_id"] for h in hubs]
    if st.session_state.get("s3_selected_hub") not in hub_ids:
        st.session_state["s3_selected_hub"] = "HUB-03" if "HUB-03" in hub_ids else hub_ids[0]
    selected_hub_id = st.session_state["s3_selected_hub"]
    selected_hub_obj = next(h for h in hubs if h["hub_id"] == selected_hub_id)
    selected_hub_vn = _VN_HUB_NAMES.get(selected_hub_id, selected_hub_obj["name"])
    selected_hub_receipt = _RECEIPT_HUB_NAMES.get(selected_hub_id, selected_hub_obj["name"])

    st.session_state.setdefault("s3_view", "main")
    view = st.session_state["s3_view"]

    # =========================================================================
    # MÀN HÌNH 4: ĐẶT CHỖ ĐỖ THÀNH CÔNG
    # =========================================================================
    if view == "parking_success":
        back_col, _ = st.columns([1, 5])
        if back_col.button("‹", key="s3_ps_back"):
            st.session_state["s3_view"] = "main"
            st.rerun()

        info = st.session_state.get("s3_last_parking_receipt", {})
        st.markdown(
            f"""
            <div class="s3-success-circle">✓</div>
            <div style="text-align:center;font-size:1.35rem;font-weight:800;color:#0F172A;">Đặt chỗ đỗ thành công</div>
            <div class="s3-receipt-card">
                <div class="s3-big-slot-box">
                    <div style="font-size:0.7rem;font-weight:700;color:#64748B;letter-spacing:0.04em;">VỊ TRÍ Ô ĐỖ</div>
                    <div style="font-size:1.85rem;font-weight:900;color:#0F172A;margin-top:4px;">{escape(info.get('slot_label', 'P-03'))}</div>
                </div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Trạm Hub</span>
                    <span style="font-weight:800;color:#0F172A;">{escape(info.get('hub_name', selected_hub_receipt))}</span>
                </div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Khung giờ</span>
                    <span style="font-weight:800;color:#0F172A;">{escape(info.get('time_range', '12:00 - 18:00 (Hôm nay)'))}</span>
                </div>
                <div class="s3-kv-divider"></div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Tổng tiền</span>
                    <span style="font-weight:800;color:#0F172A;">2.000 VNĐ</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Về trang chủ", type="primary", use_container_width=True, key="s3_ps_home"):
            st.session_state["s3_view"] = "main"
            st.rerun()
        return

    # =========================================================================
    # MÀN HÌNH 5: ĐĂNG KÝ LỊCH SẠC THÀNH CÔNG
    # =========================================================================
    if view == "charging_success":
        back_col, _ = st.columns([1, 5])
        if back_col.button("‹", key="s3_cs_back"):
            st.session_state["s3_view"] = "main"
            st.rerun()

        info = st.session_state.get("s3_last_charging_receipt", {})
        st.markdown(
            f"""
            <div class="s3-success-circle">✓</div>
            <div style="text-align:center;font-size:1.3rem;font-weight:800;color:#0F172A;">Đăng ký lịch sạc thành công</div>
            <div class="s3-receipt-card">
                <div class="s3-big-slot-box">
                    <div style="font-size:0.7rem;font-weight:700;color:#64748B;letter-spacing:0.04em;">CỔNG SẠC ĐĂNG KÝ</div>
                    <div style="font-size:1.85rem;font-weight:900;color:#0F172A;margin-top:4px;">{escape(info.get('charger_label', 'TRỤ #02'))}</div>
                </div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Trạm sạc</span>
                    <span style="font-weight:800;color:#0F172A;">{escape(info.get('hub_name', selected_hub_receipt))}</span>
                </div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Khung giờ</span>
                    <span style="font-weight:800;color:#0F172A;">{escape(info.get('time_range', '13:30 - 15:00 (Hôm nay)'))}</span>
                </div>
                <div class="s3-kv-divider"></div>
                <div class="s3-kv-row">
                    <span style="color:#64748B;">Đơn giá điện</span>
                    <span style="font-weight:800;color:#0F172A;">1.000 VNĐ/kWh</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Về trang chủ", type="primary", use_container_width=True, key="s3_cs_home"):
            st.session_state["s3_view"] = "main"
            st.rerun()
        return

    # =========================================================================
    # MÀN HÌNH 2: ĐẶT CHỖ ĐỖ XE
    # =========================================================================
    if view == "parking":
        c_back, c_title = st.columns([0.8, 4.2])
        if c_back.button("‹", key="s3_pk_back"):
            st.session_state["s3_view"] = "main"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.25rem;font-weight:800;color:#0F172A;padding-top:4px;">Đặt chỗ đỗ xe</div>',
            unsafe_allow_html=True,
        )

        spaces = sub03_service.get_parking_spaces_by_hub(state, selected_hub_id)
        avail_spaces = [s for s in spaces if s["effective_status"] == PARKING_AVAILABLE]

        st.markdown(
            f"""
            <div class="s3-hub-summary" style="padding:12px 14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;gap:6px;">
                    <div>
                        <div style="font-size:0.65rem;font-weight:700;color:#64748B;">BÃI ĐỖ XE ĐÃ CHỌN</div>
                        <div style="font-size:0.92rem;font-weight:800;color:#0F172A;">{escape(selected_hub_vn)}</div>
                    </div>
                    <span style="background:#DCFCE7;color:#15803D;font-size:0.68rem;font-weight:800;padding:3px 10px;border-radius:999px;white-space:nowrap;">
                        Còn {len(avail_spaces)} chỗ trống
                    </span>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin:12px 0 8px 0;">
                <span class="s3-sec-hdr" style="margin:0;">SƠ ĐỒ BÃI ĐỖ XE</span>
                <div class="s3-legend">
                    <span><b style="color:#8CE600;">●</b> Đang chọn</span>
                    <span><b style="color:#94A3B8;">○</b> Trống</span>
                    <span><b style="color:#CBD5E1;">●</b> Đã kín</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not avail_spaces:
            st.warning("Hiện bãi đỗ tại trạm này đã kín chỗ.")
            return

        avail_ids = [s["space_id"] for s in avail_spaces]
        if st.session_state.get("s3_pk_chosen_slot") not in avail_ids:
            st.session_state["s3_pk_chosen_slot"] = avail_ids[2] if len(avail_ids) >= 3 else avail_ids[0]
        chosen_slot = st.session_state["s3_pk_chosen_slot"]

        display_spaces = spaces[:6]
        slot_label_map: dict[str, str] = {}
        for r_idx in range(0, len(display_spaces), 3):
            cols = st.columns(3)
            for offset, (col, sp) in enumerate(zip(cols, display_spaces[r_idx : r_idx + 3])):
                idx = r_idx + offset + 1
                sid = sp["space_id"]
                p_code = _format_slot_code(sid, idx)
                slot_label_map[sid] = p_code

                is_avail = sp["effective_status"] == PARKING_AVAILABLE
                is_sel = sid == chosen_slot
                if is_sel:
                    prefix, lbl = "on", "Đang chọn"
                elif is_avail:
                    prefix, lbl = "av", "Trống"
                else:
                    prefix, lbl = "bz", "Đã kín"

                if col.button(
                    f"**{p_code}**\n\n{lbl}",
                    key=f"s3_sl_{prefix}_{sid}",
                    disabled=not is_avail,
                    use_container_width=True,
                ):
                    if is_avail and not is_sel:
                        st.session_state["s3_pk_chosen_slot"] = sid
                        st.rerun()

        st.markdown('<div class="s3-sec-hdr">CHỌN KHUNG GIỜ GỬI XE HÔM NAY:</div>', unsafe_allow_html=True)
        shifts = [
            ("Ca sáng", "(07h - 12h)", "07:00", "12:00"),
            ("Ca chiều", "(12h - 18h)", "12:00", "18:00"),
            ("Cả ngày", "(07h - 22h)", "07:00", "22:00"),
        ]
        st.session_state.setdefault("s3_pk_shift", "Ca chiều")
        sel_shift = st.session_state["s3_pk_shift"]

        scols = st.columns(3)
        for idx, (col, (s_name, s_sub, _, _)) in enumerate(zip(scols, shifts)):
            is_s = sel_shift == s_name
            if col.button(
                f"**{s_name}**\n\n{s_sub}",
                key=f"s3_sh_{'on' if is_s else 'off'}_{idx}",
                use_container_width=True,
            ):
                if not is_s:
                    st.session_state["s3_pk_shift"] = s_name
                    st.rerun()

        st.session_state.setdefault("s3_pk_plate_val", "59-M1 123.45")
        with st.expander(f"Biển số xe cá nhân: {st.session_state['s3_pk_plate_val']}"):
            st.session_state["s3_pk_plate_val"] = st.text_input(
                "Nhập biển số xe",
                value=st.session_state["s3_pk_plate_val"],
                key="s3_pk_plate_input",
            )

        shift_obj = next(s for s in shifts if s[0] == sel_shift)
        chosen_p_code = slot_label_map.get(chosen_slot, _format_slot_code(chosen_slot, 1))

        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid #E2E8F0;padding:12px 2px 8px 2px;margin-top:10px;">
                <div>
                    <div style="font-size:0.7rem;color:#64748B;">Vị trí ô đỗ:</div>
                    <div style="font-size:0.9rem;font-weight:800;color:#0F172A;">Ô {escape(chosen_p_code)} ({sel_shift})</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.7rem;color:#64748B;">Tổng tiền:</div>
                    <div style="font-size:0.9rem;font-weight:800;color:#0F172A;">2.000 VNĐ / buổi</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            f"Xác nhận giữ chỗ đỗ {chosen_p_code} →",
            type="primary",
            use_container_width=True,
            key="s3_pk_confirm",
        ):
            try:
                active_hold = sub03_service.get_active_hold_for_student(state, student_id)
                if active_hold is not None:
                    sub03_service.release_temporary_hold(state, active_hold["hold_id"], student_id)
                hold = sub03_service.create_temporary_hold(state, chosen_slot, student_id)
                sub03_service.confirm_parking_reservation(
                    state=state,
                    hold_id=hold["hold_id"],
                    student_id=student_id,
                    license_plate=st.session_state["s3_pk_plate_val"],
                    start_time=shift_obj[2],
                    end_time=shift_obj[3],
                )
                st.session_state["s3_last_parking_receipt"] = {
                    "slot_label": chosen_p_code,
                    "hub_name": selected_hub_receipt,
                    "time_range": f"{shift_obj[2]} - {shift_obj[3]} (Hôm nay)",
                }
                st.session_state["s3_view"] = "parking_success"
                st.rerun()
            except ValueError as err:
                st.error(str(err))
        return

    # =========================================================================
    # MÀN HÌNH 3: ĐĂNG KÝ LỊCH SẠC
    # =========================================================================
    if view == "charging":
        c_back, c_title = st.columns([0.8, 4.2])
        if c_back.button("‹", key="s3_cg_back"):
            st.session_state["s3_view"] = "main"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.25rem;font-weight:800;color:#0F172A;padding-top:4px;">Đăng ký lịch sạc</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="s3-hub-summary" style="padding:12px 14px;margin-bottom:4px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:0.65rem;font-weight:700;color:#64748B;">TRẠM SẠC ĐÃ CHỌN</div>
                        <div style="font-size:0.92rem;font-weight:800;color:#0F172A;">{escape(selected_hub_vn)}</div>
                    </div>
                    <span style="font-size:0.76rem;font-weight:800;color:#16A34A;">Đổi trạm</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _, sw_col = st.columns([3.2, 1.3])
        if sw_col.button("Đổi trạm", key="s3_cg_switch_hub", use_container_width=True):
            cur_i = hub_ids.index(selected_hub_id)
            st.session_state["s3_selected_hub"] = hub_ids[(cur_i + 1) % len(hub_ids)]
            st.rerun()

        st.markdown('<div class="s3-sec-hdr" style="margin-top:4px;">CHỌN TRỤ SẠC TẠI HUB:</div>', unsafe_allow_html=True)

        hub_cps = [cp for cp in state.get("charging_points", []) if cp["hub_id"] == selected_hub_id]
        avail_cp_indices = [idx for idx, cp in enumerate(hub_cps, start=1) if cp["status"] == "AVAILABLE"]
        if not avail_cp_indices:
            st.warning("Hiện trạm này không còn trụ sạc trống.")
            return

        if st.session_state.get("s3_cg_chosen_idx") not in avail_cp_indices:
            st.session_state["s3_cg_chosen_idx"] = avail_cp_indices[0]
        chosen_cp_idx = st.session_state["s3_cg_chosen_idx"]

        cp_cols = st.columns(min(4, len(hub_cps)))
        for idx, (col, cp) in enumerate(zip(cp_cols, hub_cps), start=1):
            st_val = cp["status"]
            is_avail = st_val == "AVAILABLE"
            is_sel = idx == chosen_cp_idx
            if is_sel:
                prefix, lbl = "on", "Trống"
            elif is_avail:
                prefix, lbl = "av", "Trống"
            elif st_val in ("IN_USE", "RESERVED"):
                prefix, lbl = "bz", "Bận"
            else:
                prefix, lbl = "mt", "Bảo trì"

            if col.button(
                f"Trụ #{idx:02d}\n\n**{lbl}**",
                key=f"s3_cp_{prefix}_{idx}",
                disabled=not is_avail,
                use_container_width=True,
            ):
                if is_avail and not is_sel:
                    st.session_state["s3_cg_chosen_idx"] = idx
                    st.rerun()

        st.markdown('<div class="s3-sec-hdr">CHỌN KHUNG GIỜ SẠC HÔM NAY:</div>', unsafe_allow_html=True)
        cg_slots = [
            ("11:30 - 13:00", "Còn 2 trụ trống", "11:30", "13:00", True),
            ("13:30 - 15:00", "Còn 5 trụ trống", "13:30", "15:00", True),
            ("15:30 - 17:00", "Đã kín chỗ", "15:30", "17:00", False),
            ("17:30 - 19:00", "Còn 3 trụ trống", "17:30", "19:00", True),
        ]
        st.session_state.setdefault("s3_cg_slot", "13:30 - 15:00")
        sel_cg_slot = st.session_state["s3_cg_slot"]

        for r_idx in range(0, len(cg_slots), 2):
            cols = st.columns(2)
            for offset, (col, (lbl, sub_txt, st_t, en_t, enabled)) in enumerate(zip(cols, cg_slots[r_idx : r_idx + 2])):
                idx = r_idx + offset
                is_s = sel_cg_slot == lbl
                prefix = "bz" if not enabled else ("on" if is_s else "off")
                if col.button(
                    f"**{lbl}**\n\n{sub_txt}",
                    key=f"s3_ts_{prefix}_{idx}",
                    disabled=not enabled,
                    use_container_width=True,
                ):
                    if enabled and not is_s:
                        st.session_state["s3_cg_slot"] = lbl
                        st.rerun()

        st.session_state.setdefault("s3_cg_cur_val", 30)
        st.session_state.setdefault("s3_cg_tgt_val", 85)
        with st.expander(f"Tùy chỉnh mức pin sạc ({st.session_state['s3_cg_cur_val']}% → {st.session_state['s3_cg_tgt_val']}%)"):
            c_b1, c_b2 = st.columns(2)
            st.session_state["s3_cg_cur_val"] = c_b1.number_input(
                "Pin hiện tại (%)", 0, 99, st.session_state["s3_cg_cur_val"], key="s3_cg_cur_bat"
            )
            st.session_state["s3_cg_tgt_val"] = c_b2.number_input(
                "Pin mục tiêu (%)", 1, 100, st.session_state["s3_cg_tgt_val"], key="s3_cg_tgt_bat"
            )

        slot_obj = next(s for s in cg_slots if s[0] == sel_cg_slot)
        charger_lbl = f"Trụ #{chosen_cp_idx:02d}"

        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid #E2E8F0;padding:12px 2px 8px 2px;margin-top:10px;">
                <div>
                    <div style="font-size:0.7rem;color:#64748B;">Vị trí sạc đã chọn:</div>
                    <div style="font-size:0.88rem;font-weight:800;color:#0F172A;">{charger_lbl} ({sel_cg_slot})</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.7rem;color:#64748B;">Đơn giá điện:</div>
                    <div style="font-size:0.88rem;font-weight:800;color:#0F172A;">1.000đ / kWh</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            f"Xác nhận đặt lịch sạc ({charger_lbl}) →",
            type="primary",
            use_container_width=True,
            key="s3_cg_confirm",
        ):
            try:
                my_res = sub03_service.get_student_parking_reservations(state, student_id)
                eligible = [
                    r
                    for r in my_res
                    if r["hub_id"] == selected_hub_id
                    and r["status"] in (PARKING_RESERVED, PARKING_IN_USE)
                    and r["has_charger"]
                ]
                if eligible:
                    target_res_id = eligible[0]["reservation_id"]
                else:
                    charger_spaces = sub03_service.get_parking_spaces_by_hub(
                        state, selected_hub_id, only_available=True, only_with_charger=True
                    )
                    if not charger_spaces:
                        raise ValueError("Hiện không còn ô đỗ có trụ sạc trống tại trạm này.")
                    active_hold = sub03_service.get_active_hold_for_student(state, student_id)
                    if active_hold is not None:
                        sub03_service.release_temporary_hold(state, active_hold["hold_id"], student_id)
                    hold = sub03_service.create_temporary_hold(state, charger_spaces[0]["space_id"], student_id)
                    new_res = sub03_service.confirm_parking_reservation(
                        state=state,
                        hold_id=hold["hold_id"],
                        student_id=student_id,
                        license_plate=st.session_state.get("s3_pk_plate_val", "59-M1 123.45"),
                        start_time=slot_obj[2],
                        end_time=slot_obj[3],
                    )
                    target_res_id = new_res["reservation_id"]

                sub03_service.create_charging_request(
                    state=state,
                    reservation_id=target_res_id,
                    student_id=student_id,
                    current_battery=int(st.session_state["s3_cg_cur_val"]),
                    target_battery=int(st.session_state["s3_cg_tgt_val"]),
                    departure_time=slot_obj[3],
                )
                st.session_state["s3_last_charging_receipt"] = {
                    "charger_label": f"TRỤ #{chosen_cp_idx:02d}",
                    "hub_name": selected_hub_receipt,
                    "time_range": f"{sel_cg_slot} (Hôm nay)",
                }
                st.session_state["s3_view"] = "charging_success"
                st.rerun()
            except ValueError as err:
                st.error(str(err))
        return

    # =========================================================================
    # MÀN HÌNH 1: TRANG CHÍNH TAB ĐỖ & SẠC XE
    # =========================================================================
    st.markdown(
        '<div style="font-size:1.45rem;font-weight:800;color:#0F172A;margin-bottom:6px;">Đỗ &amp; Sạc xe</div>'
        '<div class="s3-sec-hdr">1. CHỌN TRẠM HUB</div>',
        unsafe_allow_html=True,
    )

    preferred_order = ["HUB-03", "HUB-02", "HUB-01"]
    pill_ids = [hid for hid in preferred_order if hid in hub_ids]
    if selected_hub_id not in pill_ids:
        pill_ids = [selected_hub_id] + pill_ids[:2]

    hub_cols = st.columns([1.45, 0.95, 1.15])
    for col, hid in zip(hub_cols, pill_ids):
        is_sel = hid == selected_hub_id
        short_lbl = _PILL_HUB_NAMES.get(hid, hid)
        if col.button(
            short_lbl,
            key=f"s3_main_hub_{'on' if is_sel else 'off'}_{hid}",
            use_container_width=True,
        ):
            if not is_sel:
                st.session_state["s3_selected_hub"] = hid
                st.rerun()

    avail_parks_cnt = len(sub03_service.get_parking_spaces_by_hub(state, selected_hub_id, only_available=True))
    avail_cps_cnt = sum(
        1
        for cp in state.get("charging_points", [])
        if cp["hub_id"] == selected_hub_id and cp["status"] == "AVAILABLE"
    )

    st.markdown(
        f"""
        <div class="s3-hub-summary">
            <div style="font-weight:800;font-size:0.96rem;color:#0F172A;">{escape(selected_hub_vn)}</div>
            <div class="s3-two-boxes">
                <div class="s3-mini-box">
                    <div style="font-size:0.65rem;font-weight:700;color:#64748B;">CHỖ ĐỖ XE</div>
                    <div style="font-size:0.88rem;font-weight:800;color:#16A34A;margin-top:2px;">Còn {avail_parks_cnt} ô trống</div>
                </div>
                <div class="s3-mini-box">
                    <div style="font-size:0.65rem;font-weight:700;color:#64748B;">TRỤ SẠC ĐIỆN</div>
                    <div style="font-size:0.88rem;font-weight:800;color:#16A34A;margin-top:2px;">Còn {avail_cps_cnt} trụ trống</div>
                </div>
            </div>
        </div>
        <div class="s3-sec-hdr">2. CHỌN DỊCH VỤ BẠN CẦN SỬ DỤNG:</div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "`🅿️` Đặt chỗ đỗ xe\n\nGiá: **2.000đ**/buổi",
        key="s3_svc_open_parking",
        use_container_width=True,
    ):
        st.session_state["s3_view"] = "parking"
        st.rerun()

    if st.button(
        "`⚡` Đăng ký lịch sạc\n\nĐơn giá điện: **1.000đ**/kWh",
        key="s3_svc_open_charging",
        use_container_width=True,
    ):
        st.session_state["s3_view"] = "charging"
        st.rerun()

    my_res = sub03_service.get_student_parking_reservations(state, student_id)
    my_reqs = sub03_service.get_student_charging_requests(state, student_id)
    if my_res or my_reqs:
        with st.expander(f"Phiếu đỗ & Lịch sạc của tôi ({len(my_res)} phiếu đỗ · {len(my_reqs)} lịch sạc)"):
            for res in my_res:
                st.markdown(
                    f"**{res['reservation_id']}** · Ô `{res['space_id']}` ({_VN_HUB_NAMES.get(res['hub_id'], res['hub_name'])}) — **{res['status']}** "
                    f"({res['start_time']} - {res['end_time']})"
                )
                if res["status"] == PARKING_RESERVED:
                    b1, b2 = st.columns(2)
                    if b1.button("Check-in", key=f"s3_ci_{res['reservation_id']}", use_container_width=True):
                        ok, msg = sub03_service.check_in_vehicle(state, res["reservation_id"], student_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    if b2.button("Hủy phiếu", key=f"s3_can_{res['reservation_id']}", use_container_width=True):
                        ok, msg = sub03_service.cancel_parking_reservation(state, res["reservation_id"], student_id)
                        if ok:
                            st.warning(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                elif res["status"] == PARKING_IN_USE:
                    if st.button("Check-out rời bãi", key=f"s3_co_{res['reservation_id']}", use_container_width=True):
                        ok, msg = sub03_service.check_out_vehicle(state, res["reservation_id"], student_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

            for req in my_reqs:
                st.markdown(
                    f"**{req['request_id']}** · Ô `{req['space_id']}` — **{req['status']}** "
                    f"(Pin {req['current_battery']}% → {req['target_battery']}%)"
                )
                if req["status"] in (CHARGING_REQUEST_PENDING, CHARGING_REQUEST_CONFIRMED):
                    if st.button("Hủy lịch sạc", key=f"s3_ccg_{req['request_id']}", use_container_width=True):
                        ok, msg = sub03_service.cancel_charging_request(state, req["request_id"], student_id)
                        if ok:
                            st.warning(msg)
                            st.rerun()
                        else:
                            st.error(msg)