"""Streamlit Mobile UI for SUB-02: Vehicle Trip Lifecycle & Incident Reporting."""

from __future__ import annotations

from datetime import datetime
from html import escape
import streamlit as st

from modules.sub01.service import cancel_reservation, get_hub_list, get_student_reservations
from modules.sub02.service import (
    get_active_trip,
    get_available_vehicles_at_hub,
    get_student_trips,
    pickup_vehicle,
    report_defective_vehicle_at_pickup,
    report_defective_vehicle_at_return,
    return_vehicle,
)
from shared.enums import RESERVATION_PENDING

_VN_HUB_NAMES = {
    "HUB-01": "Trạm Ga Metro ĐHQG",
    "HUB-02": "Trạm KTX Khu A",
    "HUB-03": "Trạm ĐH Bách Khoa (CS2)",
    "HUB-04": "Trạm ĐH Công nghệ Thông tin (UIT)",
    "HUB-05": "Trạm KTX Khu B",
}

_SUB02_CSS = """

<style>
.s2-live-card {
    background: #FFFFFF;
    border: 2px solid #8CE600;
    border-radius: 20px;
    padding: 15px 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 16px rgba(140, 230, 0, 0.12);
}
.s2-live-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.s2-live-tag {
    color: #16A34A;
    font-size: 0.74rem;
    font-weight: 800;
}
.s2-bat-pill {
    background: #DCFCE7;
    color: #15803D;
    font-size: 0.72rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 999px;
}
.s2-veh-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 10px 0;
}
.s2-veh-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: #F1F5F9;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.15rem;
}
.s2-metrics-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    text-align: center;
    background: #F8FAFC;
    border-radius: 14px;
    padding: 10px 6px;
    margin-bottom: 12px;
}
.s2-m-lbl {
    font-size: 0.66rem;
    font-weight: 700;
    color: #64748B;
}
.s2-m-val {
    font-size: 0.94rem;
    font-weight: 800;
    color: #0F172A;
    margin-top: 2px;
}
.s2-rsv-card {
    background: #FFFFFF;
    border: 1.5px solid #E2E8F0;
    border-radius: 20px;
    padding: 15px 16px;
    margin-bottom: 12px;
}
.s2-pickup-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 12px 14px;
    margin: 10px 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.s2-qr-scanner {
    background: #0F172A;
    border-radius: 20px;
    padding: 28px 18px 20px 18px;
    text-align: center;
    margin: 12px 0;
    color: #CBD5E1;
}
.s2-qr-frame {
    width: 112px;
    height: 112px;
    margin: 0 auto 14px auto;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
}
.s2-qr-line {
    width: 84px;
    height: 3px;
    background: #8CE600;
    border-radius: 999px;
    box-shadow: 0 0 12px #8CE600;
}
.s2-notice-green {
    background: #F7FEE7;
    border: 1px solid #BEF264;
    border-radius: 14px;
    padding: 10px 12px;
    font-size: 0.78rem;
    color: #365314;
    margin: 10px 0;
}
.s2-pause-pill {
    background: #FFE4E6;
    color: #E11D48;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 999px;
}

/* =========================================================================
   THẺ SỰ CỐ & THẺ TRẠM TRẢ XE BẤM TRỰC TIẾP
   ========================================================================= */
div[class*="st-key-s2_iss_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s2_ret_"] div[data-testid="stButton"] button[kind="secondary"] {
    border-radius: 14px !important;
    padding: 11px 12px !important;
    min-height: auto !important;
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    text-align: left !important;
    white-space: normal !important;
    overflow: hidden !important;
}
div[class*="st-key-s2_iss_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s2_iss_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"],
div[class*="st-key-s2_ret_"] div[data-testid="stButton"] button > div,
div[class*="st-key-s2_ret_"] div[data-testid="stButton"] button [data-testid="stMarkdownContainer"] {
    display: block !important;
    width: 100% !important;
    max-width: 100% !important;
    text-align: left !important;
}
div[class*="st-key-s2_iss_on_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s2_ret_on_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #F7FEE7 !important;
    border: 2px solid #8CE600 !important;
}
div[class*="st-key-s2_iss_off_"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s2_ret_off_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
}
div[class*="st-key-s2_iss_"] button [data-testid="stMarkdownContainer"] p:nth-child(1),
div[class*="st-key-s2_ret_"] button [data-testid="stMarkdownContainer"] p:nth-child(1) {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    width: 100% !important;
    margin: 0 !important;
    font-size: 0.82rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    white-space: normal !important;
}
div[class*="st-key-s2_iss_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s2_ret_on_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "";
    margin-left: auto !important;
    width: 16px;
    height: 16px;
    border-radius: 999px;
    border: 2px solid #8CE600;
    background: radial-gradient(circle, #365314 42%, #FFFFFF 48%);
    flex-shrink: 0;
}
div[class*="st-key-s2_iss_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after,
div[class*="st-key-s2_ret_off_"] button [data-testid="stMarkdownContainer"] p:nth-child(1)::after {
    content: "";
    margin-left: auto !important;
    width: 16px;
    height: 16px;
    border-radius: 999px;
    border: 1.5px solid #CBD5E1;
    background: #FFFFFF;
    flex-shrink: 0;
}
div[class*="st-key-s2_ret_"] button [data-testid="stMarkdownContainer"] p:nth-child(2) {
    margin: 3px 0 0 0 !important;
    font-size: 0.72rem !important;
    color: #16A34A !important;
    font-weight: 700 !important;
    white-space: normal !important;
}
/* Nút Báo hỏng xe, Báo cáo sự cố & Hủy đặt chỗ màu đỏ nhạt */
div[class*="st-key-s2_goto_mid_inc"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s2_pu_fault_nav"] div[data-testid="stButton"] button[kind="secondary"],
div[class*="st-key-s2_can_"] div[data-testid="stButton"] button[kind="secondary"] {
    background-color: #FFF1F2 !important;
    border: 1.5px solid #FECDD3 !important;
    color: #E11D48 !important;
}
div[class*="st-key-s2_goto_mid_inc"] div[data-testid="stButton"] button[kind="secondary"] p,
div[class*="st-key-s2_pu_fault_nav"] div[data-testid="stButton"] button[kind="secondary"] p,
div[class*="st-key-s2_can_"] div[data-testid="stButton"] button[kind="secondary"] p {
    color: #E11D48 !important;
    font-weight: 700 !important;
}
div[class*="st-key-s2_goto_mid_inc"] div[data-testid="stButton"] button[kind="secondary"]:hover,
div[class*="st-key-s2_pu_fault_nav"] div[data-testid="stButton"] button[kind="secondary"]:hover,
div[class*="st-key-s2_can_"] div[data-testid="stButton"] button[kind="secondary"]:hover {
    background-color: #FFE4E6 !important;
    border-color: #FDA4AF !important;
}
</style>
"""


def _elapsed_stats(start_iso: str) -> tuple[str, int, float, int]:
    try:
        start_dt = datetime.fromisoformat(start_iso)
        now_dt = datetime.now(start_dt.tzinfo) if start_dt.tzinfo else datetime.now()
        total_sec = max(60, int((now_dt - start_dt).total_seconds()))
    except Exception:
        total_sec = 18 * 60 + 42

    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    hhmmss = f"{hrs:02d}:{mins:02d}:{secs:02d}"
    total_mins = max(1, total_sec // 60)
    dist_km = round(max(0.8, total_mins * 0.15), 1)
    cost_vnd = max(2000, ((total_mins + 14) // 15) * 2000)
    return hhmmss, total_mins, dist_km, cost_vnd


def _fmt_hhmm(iso_str: str) -> str:
    try:
        return f"{datetime.fromisoformat(iso_str).strftime('%H:%M')} hôm nay"
    except Exception:
        return iso_str


def render(state: dict, current_user: dict) -> None:
    st.markdown(_SUB02_CSS, unsafe_allow_html=True)
    student_id = current_user["user_id"]
    hub_map = {h["hub_id"]: _VN_HUB_NAMES.get(h["hub_id"], h["name"]) for h in state["hubs"]}
    veh_map = {v["vehicle_id"]: v for v in state["vehicles"]}

    st.session_state.setdefault("s2_view", "main")
    view = st.session_state["s2_view"]

    active_trip = get_active_trip(state, student_id)
    reservations = get_student_reservations(state, student_id)
    pending_rsvs = [r for r in reservations if r["status"] == RESERVATION_PENDING]

    # =========================================================================
    # MÀN HÌNH: NHẬN XE
    # =========================================================================
    if view == "pickup":
        c_back, c_title = st.columns([1, 4.5])
        if c_back.button("‹", key="s2_pu_back", use_container_width=True):
            st.session_state["s2_view"] = "main"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.3rem;font-weight:800;color:#0F172A;padding-top:6px;">Nhận xe</div>',
            unsafe_allow_html=True,
        )

        if not pending_rsvs:
            st.info("Bạn hiện không có đơn đặt chỗ nào đang chờ nhận xe.")
            if st.button("Quay lại", use_container_width=True, key="s2_pu_empty_back"):
                st.session_state["s2_view"] = "main"
                st.rerun()
            return

        rsv = pending_rsvs[0]
        hub_name = hub_map.get(rsv["hub_id"], rsv["hub_id"])
        avail_vehs = get_available_vehicles_at_hub(state, rsv["hub_id"])

        st.markdown(
            f"""
            <div class="s2-rsv-card" style="padding:12px 14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:0.74rem;color:#64748B;">Reservation {escape(rsv['reservation_id'])}</div>
                        <div style="font-size:0.98rem;font-weight:800;color:#0F172A;">{escape(hub_name)}</div>
                    </div>
                    <span style="background:#DBEAFE;color:#1D4ED8;font-size:0.72rem;font-weight:800;padding:3px 10px;border-radius:999px;">Còn hạn</span>
                </div>
            </div>
            <div class="s2-qr-scanner">
                <div class="s2-qr-frame">
                    <div style="position:absolute;top:0;left:0;width:24px;height:24px;border-top:3px solid #8CE600;border-left:3px solid #8CE600;border-top-left-radius:8px;"></div>
                    <div style="position:absolute;top:0;right:0;width:24px;height:24px;border-top:3px solid #8CE600;border-right:3px solid #8CE600;border-top-right-radius:8px;"></div>
                    <div style="position:absolute;bottom:0;left:0;width:24px;height:24px;border-bottom:3px solid #8CE600;border-left:3px solid #8CE600;border-bottom-left-radius:8px;"></div>
                    <div style="position:absolute;bottom:0;right:0;width:24px;height:24px;border-bottom:3px solid #8CE600;border-right:3px solid #8CE600;border-bottom-right-radius:8px;"></div>
                    <div class="s2-qr-line"></div>
                </div>
                <div style="font-size:0.8rem;color:#94A3B8;">Quét mã QR trên xe</div>
            </div>
            <div style="text-align:center;font-size:0.76rem;color:#94A3B8;margin:6px 0;">hoặc nhập pickup code</div>
            """,
            unsafe_allow_html=True,
        )

        if not avail_vehs:
            st.error("Hiện không còn xe khả dụng tại trạm này.")
            return

        pref_type = st.session_state.get("preferred_vehicle_type")
        sorted_vehs = sorted(
            avail_vehs,
            key=lambda v: (0 if v["vehicle_type"] == pref_type else 1, -v["battery_level"]),
        )
        veh_labels = {
            f"{v['vehicle_id']} · {'Xe đạp điện' if v['vehicle_type'] == 'ELECTRIC_BICYCLE' else 'Xe máy điện'} (Pin {v['battery_level']}%)": v["vehicle_id"]
            for v in sorted_vehs
        }
        chosen_veh_lbl = st.selectbox("Xe nhận tại bãi", list(veh_labels.keys()), key="s2_pu_veh")
        chosen_veh_id = veh_labels[chosen_veh_lbl]
        st.session_state["s2_pickup_selected_veh"] = chosen_veh_id

        code_input = st.text_input(
            "Pickup code",
            value=str(rsv["pickup_code"]),
            max_chars=6,
            key="s2_pu_code_input",
        )

        if st.button("Xác nhận nhận xe & mở khóa", type="primary", use_container_width=True, key="s2_pu_confirm"):
            res = pickup_vehicle(
                state,
                student_id=student_id,
                reservation_id=rsv["reservation_id"],
                vehicle_id=chosen_veh_id,
                pickup_code=code_input.replace(" ", ""),
            )
            if res["ok"]:
                st.session_state["s2_view"] = "main"
                st.rerun()
            else:
                st.error(res["message"])

        st.write("")
        if st.button("Xe bị lỗi? Báo cáo sự cố", type="secondary", use_container_width=True, key="s2_pu_fault_nav"):
            st.session_state["s2_view"] = "pickup_incident"
            st.rerun()
        return

    # =========================================================================
    # MÀN HÌNH: BÁO CÁO SỰ CỐ TẠI BÃI
    # =========================================================================
    if view == "pickup_incident":
        c_back, c_title, c_call = st.columns([1, 3.8, 1])
        if c_back.button("‹", key="s2_pi_back", use_container_width=True):
            st.session_state["s2_view"] = "pickup"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.25rem;font-weight:800;color:#0F172A;padding-top:6px;">Báo cáo sự cố</div>',
            unsafe_allow_html=True,
        )
        c_call.markdown(
            '<div style="text-align:right;padding-top:4px;"><span style="background:#FFE4E6;color:#E11D48;padding:7px 10px;border-radius:999px;font-size:0.85rem;">📞</span></div>',
            unsafe_allow_html=True,
        )

        if not pending_rsvs:
            st.session_state["s2_view"] = "main"
            st.rerun()

        rsv = pending_rsvs[0]
        hub_name = hub_map.get(rsv["hub_id"], rsv["hub_id"])
        avail_vehs = get_available_vehicles_at_hub(state, rsv["hub_id"])
        veh_id = st.session_state.get("s2_pickup_selected_veh") or (
            avail_vehs[0]["vehicle_id"] if avail_vehs else "EB-012"
        )
        v_obj = veh_map.get(veh_id, {})
        v_type_vn = "Xe đạp điện" if v_obj.get("vehicle_type") == "ELECTRIC_BICYCLE" else "Xe máy điện"

        st.markdown(
            f"""
            <div class="s2-rsv-card" style="padding:12px 14px;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span class="s2-veh-icon">🚲</span>
                    <div>
                        <div style="font-weight:800;font-size:0.9rem;">{v_type_vn} #{escape(veh_id)} · <span style="color:#64748B;font-weight:600;">{escape(rsv['reservation_id'])}</span></div>
                        <div style="font-size:0.75rem;color:#64748B;">Trạm: {escape(hub_name)}</div>
                    </div>
                </div>
            </div>
            <div style="font-size:0.76rem;font-weight:800;color:#334155;margin:10px 0 8px 0;">
                1. CHỌN VẤN ĐỀ XE ĐANG GẶP PHẢI <span style="color:#E11D48;">*</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        issues = [
            "Khóa không mở",
            "Hỏng phanh xe",
            "Xẹp / Thủng lốp",
            "Mất nguồn / Hết pin",
            "Đèn / Còi không kêu",
            "Hư hại bên ngoài",
        ]
        st.session_state.setdefault("s2_pi_issue", issues[0])
        sel_issue = st.session_state["s2_pi_issue"]

        for row_idx in range(0, len(issues), 2):
            cols = st.columns(2)
            for offset, (col, item) in enumerate(zip(cols, issues[row_idx : row_idx + 2])):
                idx = row_idx + offset
                is_sel = sel_issue == item
                if col.button(
                    item,
                    key=f"s2_iss_{'on' if is_sel else 'off'}_{idx}",
                    use_container_width=True,
                ):
                    if not is_sel:
                        st.session_state["s2_pi_issue"] = item
                        st.rerun()

        st.markdown(
            '<div style="font-size:0.76rem;font-weight:800;color:#334155;margin:12px 0 6px 0;">2. CHỤP ẢNH MINH CHỨNG &amp; MÔ TẢ</div>',
            unsafe_allow_html=True,
        )
        _ = st.file_uploader("📷 Thêm ảnh minh chứng", type=["png", "jpg", "jpeg"], key="s2_pi_photo")
        extra_note = st.text_input("Nhập thêm chi tiết sự cố nếu có", key="s2_pi_note")

        if st.button("Gửi báo cáo & Đổi xe khác →", type="primary", use_container_width=True, key="s2_pi_submit"):
            desc = f"{sel_issue}" + (f" - {extra_note.strip()}" if extra_note.strip() else "")
            res = report_defective_vehicle_at_pickup(
                state,
                student_id=student_id,
                reservation_id=rsv["reservation_id"],
                vehicle_id=veh_id,
                issue_desc=desc,
            )
            if res["ok"]:
                st.success(res["message"])
                st.session_state["s2_view"] = "pickup"
                st.rerun()
            else:
                st.error(res["message"])

        st.markdown(
            '<div style="text-align:center;font-size:0.74rem;color:#64748B;margin-top:6px;">Hủy chuyến và hoàn tiền cọc</div>',
            unsafe_allow_html=True,
        )
        return

    # =========================================================================
    # MÀN HÌNH: TRẢ XE TẠI TRẠM
    # =========================================================================
    if view == "return":
        c_back, c_title = st.columns([1, 4.5])
        if c_back.button("‹", key="s2_ret_back", use_container_width=True):
            st.session_state["s2_view"] = "main"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.28rem;font-weight:800;color:#0F172A;padding-top:6px;">Trả xe tại trạm</div>',
            unsafe_allow_html=True,
        )

        if active_trip is None:
            st.session_state["s2_view"] = "main"
            st.rerun()

        _, total_mins, dist_km, cost_vnd = _elapsed_stats(active_trip["start_time"])
        v_obj = veh_map.get(active_trip["vehicle_id"], {})
        v_type_vn = "Xe đạp điện" if v_obj.get("vehicle_type") == "ELECTRIC_BICYCLE" else "Xe máy điện"

        st.markdown(
            f"""
            <div class="s2-rsv-card" style="padding:12px 14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span class="s2-veh-icon">🚲</span>
                        <div>
                            <div style="font-weight:800;font-size:0.9rem;">{v_type_vn} #{escape(active_trip['vehicle_id'])}</div>
                            <div style="font-size:0.74rem;color:#64748B;">Thời gian đi: <b>{total_mins} phút</b> · {dist_km} km</div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:0.66rem;font-weight:700;color:#64748B;">CƯỚC TẠM TÍNH</div>
                        <div style="font-size:0.95rem;font-weight:800;color:#0F172A;">{cost_vnd:,}đ</div>
                    </div>
                </div>
            </div>
            <div style="font-size:0.76rem;font-weight:800;color:#334155;margin:10px 0 8px 0;">
                CHỌN TRẠM HUB BẠN MUỐN TRẢ XE:
            </div>
            """,
            unsafe_allow_html=True,
        )

        hub_list = get_hub_list(state)
        valid_hids = [h["hub_id"] for h in hub_list]
        if st.session_state.get("s2_ret_hub") not in valid_hids:
            st.session_state["s2_ret_hub"] = valid_hids[0]
        chosen_ret_hid = st.session_state["s2_ret_hub"]

        for idx, h in enumerate(hub_list, start=1):
            is_sel = h["hub_id"] == chosen_ret_hid
            h_vn = _VN_HUB_NAMES.get(h["hub_id"], h["name"])
            if st.button(
                f"{idx} · {h_vn}\n\nCòn {h['available_parking_space_count']} chỗ đỗ trống",
                key=f"s2_ret_{'on' if is_sel else 'off'}_{h['hub_id']}",
                use_container_width=True,
            ):
                if not is_sel:
                    st.session_state["s2_ret_hub"] = h["hub_id"]
                    st.rerun()

        default_bat = max(0, int(active_trip["start_battery_level"]) - 10)
        final_bat = st.slider(
            "Mức pin hiện tại khi trả (%)",
            min_value=0,
            max_value=100,
            value=default_bat,
            key="s2_ret_battery",
        )

        st.markdown(
            """
            <div class="s2-notice-green">
                Vui lòng <b>khoá xe</b> và đỗ ngay ngắn tại Hub trước khi bấm xác nhận.
            </div>
            """,
            unsafe_allow_html=True,
        )

        chosen_ret_name = hub_map.get(chosen_ret_hid, chosen_ret_hid)
        st.markdown(
            f"""
            <div style="display:flex;justify-content:space-between;align-items:flex-end;border-top:1px solid #E2E8F0;padding:10px 2px 8px 2px;">
                <div>
                    <div style="font-size:0.72rem;color:#64748B;">Trạm trả đã chọn:</div>
                    <div style="font-size:0.9rem;font-weight:800;color:#0F172A;">{escape(chosen_ret_name)}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.72rem;color:#64748B;">Tổng tiền:</div>
                    <div style="font-size:0.96rem;font-weight:800;color:#0F172A;">{cost_vnd:,} VNĐ</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Xác nhận trả xe tại trạm này", type="primary", use_container_width=True, key="s2_ret_confirm"):
            res = return_vehicle(
                state,
                student_id=student_id,
                trip_id=active_trip["trip_id"],
                destination_hub_id=chosen_ret_hid,
                final_battery=final_bat,
            )
            if res["ok"]:
                st.success(res["message"])
                st.session_state["s2_view"] = "main"
                st.rerun()
            else:
                st.error(res["message"])
        return

    # =========================================================================
    # MÀN HÌNH: BÁO SỰ CỐ GIỮA ĐƯỜNG
    # =========================================================================
    if view == "mid_incident":
        c_back, c_title = st.columns([1, 4.5])
        if c_back.button("‹", key="s2_mi_back", use_container_width=True):
            st.session_state["s2_view"] = "main"
            st.rerun()
        c_title.markdown(
            '<div style="font-size:1.25rem;font-weight:800;color:#0F172A;padding-top:6px;">Báo sự cố giữa đường</div>',
            unsafe_allow_html=True,
        )

        if active_trip is None:
            st.session_state["s2_view"] = "main"
            st.rerun()

        hhmmss, _, _, cost_vnd = _elapsed_stats(active_trip["start_time"])
        st.markdown(
            f"""
            <div class="s2-rsv-card" style="padding:12px 14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span class="s2-veh-icon">🚲</span>
                        <div>
                            <div style="font-weight:800;font-size:0.9rem;">Xe #{escape(active_trip['vehicle_id'])}</div>
                            <div style="font-size:0.74rem;color:#64748B;">Vị trí: <b>Đường Tạ Quang Bửu</b></div>
                        </div>
                    </div>
                    <span class="s2-pause-pill">Đã tạm dừng cước</span>
                </div>
                <div style="display:flex;justify-content:space-between;border-top:1px solid #F1F5F9;margin-top:10px;padding-top:8px;font-size:0.76rem;color:#64748B;">
                    <span>Thời gian: <b style="color:#0F172A;">{hhmmss}</b></span>
                    <span>Phí tạm tính: <b style="color:#0F172A;">{cost_vnd:,}đ</b></span>
                </div>
            </div>
            <div style="font-size:0.76rem;font-weight:800;color:#334155;margin:10px 0 8px 0;">
                1. CHỌN VẤN ĐỀ XE ĐANG GẶP PHẢI <span style="color:#E11D48;">*</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        mid_issues = [
            "Xẹp / Nổ lốp",
            "Đứt xích / Kẹt đạp",
            "Mất nguồn điện",
            "Hỏng phanh xe",
            "Va chạm / Tai nạn",
            "Vấn đề khác",
        ]
        st.session_state.setdefault("s2_mi_issue", mid_issues[0])
        sel_mid = st.session_state["s2_mi_issue"]

        for row_idx in range(0, len(mid_issues), 2):
            cols = st.columns(2)
            for offset, (col, item) in enumerate(zip(cols, mid_issues[row_idx : row_idx + 2])):
                idx = row_idx + offset
                is_sel = sel_mid == item
                if col.button(
                    item,
                    key=f"s2_iss_{'on' if is_sel else 'off'}_mid_{idx}",
                    use_container_width=True,
                ):
                    if not is_sel:
                        st.session_state["s2_mi_issue"] = item
                        st.rerun()

        st.markdown(
            '<div style="font-size:0.76rem;font-weight:800;color:#334155;margin:12px 0 6px 0;">2. CHỤP ẢNH MINH CHỨNG &amp; MÔ TẢ</div>',
            unsafe_allow_html=True,
        )
        _ = st.file_uploader("📷 Thêm ảnh hư hỏng", type=["png", "jpg", "jpeg"], key="s2_mi_photo")
        loc_note = st.text_input("Nhập vị trí cụ thể hoặc chi tiết lỗi", key="s2_mi_loc")

        want_swap = st.checkbox(
            "Yêu cầu mang xe khác đến đổi tận nơi",
            value=False,
            key="s2_mi_swap",
        )
        st.caption("Bạn hãy đứng tại vị trí hiện tại. Nhân viên kỹ thuật sẽ đến hỗ trợ nhận lại xe hỏng và bàn giao xe mới.")

        if st.button("Gửi báo cáo →", type="primary", use_container_width=True, key="s2_mi_submit"):
            desc = f"{sel_mid}" + (f" ({loc_note.strip()})" if loc_note.strip() else "")
            if want_swap:
                desc += " [Yêu cầu đổi xe tận nơi]"
            ret_res = return_vehicle(
                state,
                student_id=student_id,
                trip_id=active_trip["trip_id"],
                destination_hub_id=active_trip["origin_hub_id"],
                final_battery=max(0, int(active_trip["start_battery_level"]) - 5),
            )
            if ret_res["ok"]:
                rep_res = report_defective_vehicle_at_return(
                    state,
                    student_id=student_id,
                    trip_id=active_trip["trip_id"],
                    issue_desc=desc,
                )
                st.warning(rep_res["message"])
                st.session_state["s2_view"] = "main"
                st.rerun()
            else:
                st.error(ret_res["message"])
        return

    # =========================================================================
    # MÀN HÌNH CHÍNH TAB CỦA TÔI: ĐẶT CHỖ & CHUYẾN ĐI
    # =========================================================================
    st.markdown(
        '<div style="font-size:1.4rem;font-weight:800;color:#0F172A;margin-bottom:12px;">Đặt chỗ &amp; Chuyến đi</div>',
        unsafe_allow_html=True,
    )

    if active_trip is None and not pending_rsvs:
        st.markdown(
            """
            <div class="s2-rsv-card" style="text-align:center;padding:24px 16px;">
                <div style="font-size:2rem;margin-bottom:6px;">🛵</div>
                <div style="font-weight:800;font-size:0.98rem;">Chưa có chuyến đi hay đơn đặt chỗ nào</div>
                <div style="font-size:0.8rem;color:#64748B;margin-top:4px;">
                    Chọn trạm Hub tại tab Khám phá để đặt giữ xe miễn phí 15 phút.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Khám phá trạm Hub →", type="primary", use_container_width=True, key="s2_empty_explore"):
            st.session_state["student_nav_tab"] = "explore"
            st.rerun()

    if active_trip is not None:
        hhmmss, _, dist_km, cost_vnd = _elapsed_stats(active_trip["start_time"])
        origin_name = hub_map.get(active_trip["origin_hub_id"], active_trip["origin_hub_id"])
        v_obj = veh_map.get(active_trip["vehicle_id"], {})
        v_type_vn = "Xe đạp điện" if v_obj.get("vehicle_type") == "ELECTRIC_BICYCLE" else "Xe máy điện"
        cur_bat = max(10, int(active_trip["start_battery_level"]) - 8)

        st.markdown(
            f"""
            <div class="s2-live-card">
                <div class="s2-live-top">
                    <span class="s2-live-tag">● CHUYẾN ĐI ĐANG DIỄN RA</span>
                    <span class="s2-bat-pill">{cur_bat}% Pin</span>
                </div>
                <div class="s2-veh-row">
                    <span class="s2-veh-icon">🚲</span>
                    <div>
                        <div style="font-weight:800;font-size:0.94rem;">{v_type_vn} #{escape(active_trip['vehicle_id'])}</div>
                        <div style="font-size:0.74rem;color:#64748B;">Xuất phát: <b>{escape(origin_name)}</b></div>
                    </div>
                </div>
                <div class="s2-metrics-3">
                    <div>
                        <div class="s2-m-lbl">THỜI GIAN</div>
                        <div class="s2-m-val">{hhmmss}</div>
                    </div>
                    <div>
                        <div class="s2-m-lbl">QUÃNG ĐƯỜNG</div>
                        <div class="s2-m-val">{dist_km} km</div>
                    </div>
                    <div>
                        <div class="s2-m-lbl">TẠM TÍNH</div>
                        <div class="s2-m-val">{cost_vnd:,}đ</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("✓ Thực hiện trả xe tại trạm", type="primary", use_container_width=True, key="s2_goto_return"):
            st.session_state["s2_view"] = "return"
            st.rerun()

        if st.button("⚠ Báo hỏng xe", type="secondary", use_container_width=True, key="s2_goto_mid_inc"):
            st.session_state["s2_view"] = "mid_incident"
            st.rerun()

    for rsv in pending_rsvs:
        hub_name = hub_map.get(rsv["hub_id"], rsv["hub_id"])
        spaced_code = " ".join(list(str(rsv["pickup_code"])))
        st.markdown(
            f"""
            <div class="s2-rsv-card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:0.7rem;font-weight:700;color:#64748B;">MÃ: {escape(rsv['reservation_id'])}</div>
                        <div style="font-size:1rem;font-weight:800;color:#0F172A;">{escape(hub_name)}</div>
                    </div>
                    <span class="s2-veh-icon">🚲</span>
                </div>
                <div class="s2-pickup-box">
                    <div>
                        <div style="font-size:0.68rem;font-weight:700;color:#64748B;">MÃ NHẬN XE (PICKUP CODE)</div>
                        <div style="font-size:1.35rem;font-weight:900;letter-spacing:0.16em;color:#0F172A;">{escape(spaced_code)}</div>
                    </div>
                    <span style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;padding:5px 10px;font-size:0.74rem;font-weight:700;">📋 Sao chép</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.78rem;margin-top:6px;">
                    <span style="color:#64748B;">Hạn chót đến trạm:</span>
                    <span style="font-weight:800;color:#0F172A;">{escape(_fmt_hhmm(rsv['expires_at']))}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("⊞ Quét mã QR nhận xe tại trạm", type="primary", use_container_width=True, key=f"s2_qr_{rsv['reservation_id']}"):
            st.session_state["s2_view"] = "pickup"
            st.rerun()

        if st.button("✕ Hủy đặt chỗ", type="secondary", use_container_width=True, key=f"s2_can_{rsv['reservation_id']}"):
            ok, msg = cancel_reservation(state, rsv["reservation_id"], student_id)
            if ok:
                st.warning(msg)
                st.rerun()
            else:
                st.error(msg)

    completed = [t for t in get_student_trips(state, student_id) if not t["is_active"]]
    if completed:
        with st.expander(f"Lịch sử chuyến đi ({len(completed)})"):
            for t in completed:
                st.markdown(
                    f"**{t['trip_id']}** · Xe `{t['vehicle_id']}`: "
                    f"{hub_map.get(t['origin_hub_id'], t['origin_hub_id'])} → "
                    f"{hub_map.get(t['destination_hub_id'], t['destination_hub_id'])} "
                    f"(Pin: {t['start_battery_level']}% → {t['end_battery_level']}%)"
                )