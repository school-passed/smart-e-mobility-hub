"""Operator UI for the What-if Simulation use cases (SUB-06)."""

from __future__ import annotations

from concurrent.futures import CancelledError
from datetime import datetime
from html import escape
import inspect
from typing import Any

import streamlit as st

from shared.enums import ROLE_OPERATOR
from modules.sub06.service import (
    SimulationInputError,
    cancel_simulation_session,
    get_network_snapshot,
    start_simulation,
)

_FULL = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.button).parameters
    else {"use_container_width": True}
)

_RESULT_KEY = "sub06_operator_result"
_JOB_KEY = "sub06_operator_job"
_NOTICE_KEY = "sub06_simulation_notice"
_SCENARIO_KEY = "sub06_operator_scenario"
_HUB_KEY = "sub06_operator_hub"

SCENARIOS = {
    "Peak student arrivals": {
        "engine": "metro_demand_surge",
        "description": "Tăng nhu cầu tại Metro Hub trong khung giờ cao điểm.",
        "group": "demand",
    },
    "Full parking": {
        "engine": "hub_near_capacity",
        "description": "Tăng số xe cá nhân chiếm chỗ đỗ tại Hub.",
        "group": "parking",
    },
    "Charging surge": {
        "engine": "charging_pressure",
        "description": "Tăng số yêu cầu sạc trong cùng khung giờ.",
        "group": "charging",
    },
    "Charging-point failures": {
        "engine": "point_failures",
        "description": "Giả định một số trụ sạc khả dụng bị lỗi.",
        "group": "failures",
    },
    "Vehicle concentration": {
        "engine": "vehicle_concentration",
        "description": "Tập trung thêm phương tiện từ Hub khác về một Hub.",
        "group": "vehicles",
    },
}

_PARAM_LABELS = {
    "base_demand": "Nhu cầu nền (lượt)",
    "increase_percent": "Tỷ lệ tăng nhu cầu",
    "additional_vehicle_demand": "Nhu cầu xe tăng thêm",
    "additional_parking_occupancy": "Xe cá nhân gửi thêm",
    "additional_requests": "Yêu cầu sạc tăng thêm",
    "failed_points": "Trụ sạc giả định lỗi",
    "source_hub_id": "Hub nguồn chuyển xe",
    "moved": "Số xe tập trung",
}

_S6_CSS = """
<style>
[data-testid="stMain"] .st-key-sub06_root [data-testid="stVerticalBlock"]{gap:0.8rem !important}
[data-testid="stMain"] .st-key-sub06_root [data-testid="stMarkdown"],
[data-testid="stMain"] .st-key-sub06_root [data-testid="stMarkdownContainer"],
[data-testid="stMain"] .st-key-sub06_root [data-testid="stMarkdownContainer"] > p:last-child{margin-bottom:0 !important}
[data-testid="stMain"] .st-key-sub06_root [data-testid="stHeaderActionElements"]{display:none !important}
[data-testid="stMain"] .st-key-sub06_root .s6-eyebrow{font-size:.8rem;color:#6b7280;margin:0 0 2px 0;line-height:1.3}
[data-testid="stMain"] .st-key-sub06_root .s6-page-title{
  padding:0 !important;margin:0 !important;font-weight:700 !important;
  font-size:1.85rem !important;letter-spacing:-.02em !important;line-height:1.18 !important;color:#111827 !important
}

[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_panel_"]{
  box-sizing:border-box;border-radius:18px !important;border:1px solid #e5e7eb !important;
  padding:20px 22px !important;background:#ffffff !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-s6_setup_top [data-testid="stHorizontalBlock"]{
  align-items:stretch !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-s6_panel_scope,
[data-testid="stMain"] .st-key-sub06_root .st-key-s6_panel_scenario{
  min-height:336px !important;height:100% !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-s6_panel_scenario [data-testid="stVerticalBlock"]{
  gap:8px !important
}

[data-testid="stMain"] .st-key-sub06_root .s6-card-title{
  display:flex;align-items:center;gap:10px;color:#111827;font-size:.94rem;font-weight:700;margin-bottom:12px
}
[data-testid="stMain"] .st-key-sub06_root .s6-sec-title{
  color:#111827;font-size:.82rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;margin-bottom:10px
}
[data-testid="stMain"] .st-key-sub06_root .s6-step{
  display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;
  border-radius:50%;background:#eef2f7;color:#475569;font-size:.76rem;font-weight:700
}
[data-testid="stMain"] .st-key-sub06_root .s6-step.ok{background:#789c28;color:#ffffff}
[data-testid="stMain"] .st-key-sub06_root .s6-unit{
  font-size:.86rem;color:#6b7280;font-weight:500;padding-top:26px
}

/* Light widget overrides */
[data-testid="stMain"] .st-key-sub06_root [data-baseweb="select"] > div,
[data-testid="stMain"] .st-key-sub06_root [data-testid="stTextInput"] [data-baseweb="input"] > div{
  background:#ffffff !important;border:1px solid #e5e7eb !important;border-radius:10px !important;color:#111827 !important
}
[data-testid="stMain"] .st-key-sub06_root [data-baseweb="select"] > div div,
[data-testid="stMain"] .st-key-sub06_root [data-testid="stTextInput"] [data-baseweb="input"] > div div{
  background:transparent !important;border:none !important;box-shadow:none !important
}
[data-testid="stMain"] .st-key-sub06_root [data-baseweb="select"] span,
[data-testid="stMain"] .st-key-sub06_root [data-baseweb="select"] input,
[data-testid="stMain"] .st-key-sub06_root [data-testid="stTextInput"] input{
  color:#111827 !important;font-weight:500 !important
}
[data-testid="stMain"] .st-key-sub06_root [data-baseweb="select"] svg{fill:#6b7280 !important;color:#6b7280 !important}
[data-testid="stMain"] .st-key-sub06_root [data-testid="stNumberInputContainer"]{
  background:#ffffff !important;border:1px solid #e5e7eb !important;border-radius:10px !important
}
[data-testid="stMain"] .st-key-sub06_root [data-testid="stNumberInputContainer"] input{background:#ffffff !important;color:#111827 !important}
[data-testid="stMain"] .st-key-sub06_root [data-testid="stNumberInputStepDown"],
[data-testid="stMain"] .st-key-sub06_root [data-testid="stNumberInputStepUp"]{
  background:#f8fafc !important;color:#374151 !important;border-left:1px solid #e5e7eb !important
}

/* Scenario option cards (higher specificity than app.py .stButton rule) */
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_"] button{
  width:100% !important;min-height:44px !important;height:auto !important;
  display:flex !important;justify-content:flex-start !important;align-items:center !important;
  gap:12px !important;padding:10px 14px !important;margin:0 !important;
  border-radius:12px !important;box-shadow:none !important;text-align:left !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_"] button > div{
  width:auto !important;flex:0 1 auto !important;text-align:left !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_off_"] button{
  background:#ffffff !important;border:1px solid #e5e7eb !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_off_"] button *{
  color:#374151 !important;font-weight:500 !important;font-size:.88rem !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_off_"] button:hover{
  background:#f9fafb !important;border-color:#cbd5e1 !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_off_"] button::before{
  content:"";flex:0 0 18px;width:18px;height:18px;border-radius:50%;
  border:1.5px solid #cbd5e1;background:#ffffff;box-sizing:border-box
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_on_"] button{
  background:#fafdf5 !important;border:1.5px solid #789c28 !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_on_"] button *{
  color:#111827 !important;font-weight:600 !important;font-size:.88rem !important
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_opt_on_"] button::before{
  content:"";flex:0 0 18px;width:18px;height:18px;border-radius:50%;
  border:2px solid #789c28;box-sizing:border-box;
  background:radial-gradient(circle,#ffffff 0%,#ffffff 28%,#789c28 32%,#789c28 100%)
}

/* Primary & action buttons */
[data-testid="stMain"] .st-key-sub06_root button[kind="primary"],
[data-testid="stMain"] .st-key-sub06_root button[data-testid="stBaseButton-primary"]{
  background:#789c28 !important;border:1px solid #789c28 !important;color:#ffffff !important;
  border-radius:12px !important;font-weight:600 !important
}
[data-testid="stMain"] .st-key-sub06_root button[kind="primary"] *{color:#ffffff !important;font-weight:600 !important}
[data-testid="stMain"] .st-key-sub06_root button[kind="primary"]:hover{background:#658520 !important;border-color:#658520 !important}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_run_simulation,
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_run_simulation [data-testid="stButton"]{
  display:flex !important;justify-content:flex-end !important;width:100% !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_run_simulation button{
  width:auto !important;min-width:148px !important;padding:9px 26px !important;min-height:40px !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_back button{
  border-radius:12px !important;border:1px solid #e5e7eb !important;
  background:#fff !important;min-height:38px !important;height:38px !important;width:38px !important;padding:0 !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_back button *{color:#111827 !important;font-size:1.15rem !important;font-weight:600 !important}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_edit_parameters button{
  background:#ffffff !important;border:1px solid #e5e7eb !important;border-radius:14px !important;
  min-height:42px !important;display:flex !important;justify-content:center !important;align-items:center !important;gap:8px !important
}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_edit_parameters button > div{width:auto !important;flex:0 1 auto !important}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_edit_parameters button *{color:#374151 !important;font-weight:500 !important;font-size:.86rem !important}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_edit_parameters button::before{
  content:"";width:15px;height:15px;flex:0 0 15px;background-color:#4b5563;
  -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%2024%2024'%20fill%3D'none'%20stroke%3D'black'%20stroke-width%3D'2'%20stroke-linecap%3D'round'%20stroke-linejoin%3D'round'%3E%3Cpath%20d%3D'M11%204H4a2%202%200%200%200-2%202v14a2%202%200%200%200%202%202h14a2%202%200%200%200%202-2v-7'%2F%3E%3Cpath%20d%3D'M18.5%202.5a2.121%202.121%200%200%201%203%203L12%2015l-4%201%201-4%209.5-9.5z'%2F%3E%3C%2Fsvg%3E");
  mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%2024%2024'%20fill%3D'none'%20stroke%3D'black'%20stroke-width%3D'2'%20stroke-linecap%3D'round'%20stroke-linejoin%3D'round'%3E%3Cpath%20d%3D'M11%204H4a2%202%200%200%200-2%202v14a2%202%200%200%200%202%202h14a2%202%200%200%200%202-2v-7'%2F%3E%3Cpath%20d%3D'M18.5%202.5a2.121%202.121%200%200%201%203%203L12%2015l-4%201%201-4%209.5-9.5z'%2F%3E%3C%2Fsvg%3E");
  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-size:contain;mask-size:contain
}
[data-testid="stMain"] .st-key-sub06_root .st-key-sub06_edit_parameters button:hover{background:#f8fafc !important}

/* Results KPI & summary boxes */
[data-testid="stMain"] .st-key-sub06_root .s6-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi{
  box-sizing:border-box;background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:15px 18px;min-width:0
}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.bad{background:#fff5f6;border-color:#fecdd3}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.warn{background:#fffbeb;border-color:#fde68a}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi-label{font-size:.7rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#6b7280}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.bad .s6-kpi-label{color:#be123c}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.warn .s6-kpi-label{color:#b45309}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi-val{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-top:6px}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi-num{font-size:1.85rem;font-weight:700;line-height:1.1;color:#111827}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.bad .s6-kpi-num{color:#e11d48}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.warn .s6-kpi-num{color:#d97706}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi-detail{font-size:.76rem;color:#6b7280}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.bad .s6-kpi-detail{color:#be123c}
[data-testid="stMain"] .st-key-sub06_root .s6-kpi.warn .s6-kpi-detail{color:#b45309}

[data-testid="stMain"] .st-key-sub06_root .s6-info-lbl{font-size:.7rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#9ca3af;margin:10px 0 4px 0}
[data-testid="stMain"] .st-key-sub06_root .s6-summary-line{
  box-sizing:border-box;padding:10px 12px;background:#f8fafc;border:1px solid #f1f5f9;
  border-radius:10px;color:#111827;font-size:.84rem;font-weight:500
}
[data-testid="stMain"] .st-key-sub06_root .s6-param-kv{display:flex;justify-content:space-between;gap:8px;padding:3px 0;font-size:.82rem}
[data-testid="stMain"] .st-key-sub06_root .s6-param-kv span{color:#6b7280}
[data-testid="stMain"] .st-key-sub06_root .s6-param-kv b{color:#111827;font-weight:600}

/* Issue & Recommendation cards */
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_issue_"]{
  box-sizing:border-box;border-radius:16px !important;padding:16px 18px !important;margin:0
}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_issue_high_"]{background:#fff8f8 !important;border:1px solid #fecdd3 !important}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_issue_medium_"]{background:#fffdf5 !important;border:1px solid #fde68a !important}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_issue_low_"]{background:#f8fbf3 !important;border:1px solid #d9e9ca !important}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-head{display:flex;align-items:flex-start;gap:10px}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-ico{
  flex:0 0 24px;width:24px;height:24px;border-radius:50%;display:inline-flex;
  align-items:center;justify-content:center;font-size:.78rem;font-weight:700
}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-ico.high{background:#ffe4e6;color:#e11d48}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-ico.medium{background:#fef3c7;color:#d97706}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-ico.low{background:#dcfce7;color:#166534}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-title{font-weight:700;font-size:.92rem;margin-bottom:3px}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-title.high{color:#be123c}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-title.medium{color:#b45309}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-title.low{color:#166534}
[data-testid="stMain"] .st-key-sub06_root .s6-issue-detail{font-size:.84rem;line-height:1.5;color:#4b5563}
[data-testid="stMain"] .st-key-sub06_root [class*="st-key-s6_rec_box_"]{
  box-sizing:border-box;background:#ffffff !important;border:1px solid #e5e7eb !important;
  border-radius:12px !important;padding:10px 14px !important;margin-top:4px
}
[data-testid="stMain"] .st-key-sub06_root .s6-recommend-label{font-size:.66rem;font-weight:600;letter-spacing:.04em;color:#9ca3af;text-transform:uppercase;margin-bottom:3px}
[data-testid="stMain"] .st-key-sub06_root .s6-recommend-action{color:#111827;font-size:.84rem;font-weight:600;line-height:1.4}
[data-testid="stMain"] .st-key-sub06_root .s6-recommend-reason{color:#6b7280;font-size:.76rem;line-height:1.45;margin-top:3px}

@media(max-width:900px){
  [data-testid="stMain"] .st-key-sub06_root .s6-kpis{grid-template-columns:1fr 1fr}
  [data-testid="stMain"] .st-key-sub06_root .st-key-s6_panel_scope,
  [data-testid="stMain"] .st-key-sub06_root .st-key-s6_panel_scenario{min-height:auto !important}
}
@media(max-width:600px){[data-testid="stMain"] .st-key-sub06_root .s6-kpis{grid-template-columns:1fr}}
</style>
"""


def _cols(spec, **kwargs):
    try:
        return st.columns(spec, **kwargs)
    except TypeError:
        kwargs.pop("vertical_alignment", None)
        return st.columns(spec, **kwargs)


def _clear_result():
    st.session_state.pop(_RESULT_KEY, None)


def _select_scenario(name):
    st.session_state[_SCENARIO_KEY] = name
    _clear_result()


def _hub_label(hub):
    return str(hub.get("name") or hub.get("address") or hub.get("hub_id", ""))


def _format_value(value, unit):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value} {unit}".strip()


def _go_operator_page(label, hub_id=None):
    if hub_id:
        st.session_state["sub04_selected_hub"] = hub_id
        st.session_state["sub05_tgt"] = hub_id
    st.session_state["sub05_nav_request"] = label


def _parse_hhmm(value):
    try:
        return datetime.strptime(str(value).strip(), "%H:%M")
    except ValueError:
        return None


def _scenario_parameters(group, hub_id, state):
    parameters = {}
    if group == "demand":
        left, right = st.columns(2)
        with left:
            parameters["base_demand"] = st.number_input(
                "Nhu cầu nền (lượt xe)", min_value=1, max_value=500, value=6, step=1,
            )
        with right:
            parameters["increase_percent"] = st.number_input(
                "Mức tăng nhu cầu (%)", min_value=1, max_value=300, value=100, step=10,
            )
    elif group == "parking":
        parameters["additional_vehicle_demand"] = 0
        parameters["additional_parking_occupancy"] = st.number_input(
            "Số lượng xe cá nhân gửi thêm", min_value=0, max_value=500, value=40, step=1,
        )
    elif group == "charging":
        parameters["additional_requests"] = st.number_input(
            "Số yêu cầu sạc tăng thêm", min_value=0, max_value=500, value=3, step=1,
        )
        parameters["failed_points"] = 0
    elif group == "failures":
        points = [point for point in state.get("charging_points", []) if point.get("hub_id") == hub_id]
        available = sum(
            point.get("status") == "AVAILABLE" and not point.get("incident_blocked")
            for point in points
        )
        parameters["additional_requests"] = 0
        parameters["failed_points"] = st.number_input(
            "Số trụ sạc khả dụng giả định bị lỗi",
            min_value=1 if available > 0 else 0,
            max_value=max(1, available),
            value=min(1, max(1, available)) if available > 0 else 0,
            step=1,
        )
    else:
        hubs = [h for h in state.get("hubs", []) if h.get("hub_id") and h.get("hub_id") != hub_id]
        hub_names = {h["hub_id"]: _hub_label(h) for h in hubs}
        left, right = st.columns(2)
        with left:
            source_id = st.selectbox(
                "Hub nguồn chuyển xe",
                list(hub_names),
                format_func=lambda v: hub_names.get(v, v),
                key="sub06_vc_src",
            )
        src_avail = sum(
            1
            for v in state.get("vehicles", [])
            if v.get("hub_id") == source_id and v.get("status") == "AVAILABLE" and not v.get("incident_blocked")
        )
        parameters["source_hub_id"] = source_id
        with right:
            parameters["moved"] = st.number_input(
                f"Số xe tập trung sang Hub đích (nguồn có {src_avail} xe)",
                min_value=1,
                max_value=max(1, src_avail),
                value=min(4, max(1, src_avail)),
                step=1,
            )
    return parameters


def _run_simulation(state, scenario_name, hub_id, parameters, start_time, end_time, operator_id="Operator"):
    t_start = _parse_hhmm(start_time)
    t_end = _parse_hhmm(end_time)
    if t_start is None or t_end is None:
        st.error("Vui lòng nhập giờ Từ và Đến đúng định dạng HH:MM (ví dụ: 07:00).")
        return
    if t_end <= t_start:
        st.error("Giờ kết thúc (Đến) phải lớn hơn giờ bắt đầu (Từ).")
        return
    parameters["time_window"] = f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}"

    option = SCENARIOS[scenario_name]
    try:
        snapshot = get_network_snapshot(state, hub_id)
        session_id, future = start_simulation(option["engine"], parameters, snapshot, operator_id)
        st.session_state[_JOB_KEY] = (session_id, future, scenario_name)
        st.rerun()
    except SimulationInputError as error:
        st.error(str(error))


def clear_simulation_view():
    job = st.session_state.pop(_JOB_KEY, None)
    if job:
        session_id, future, _ = job
        if cancel_simulation_session(session_id):
            future.cancel()
    st.session_state.pop(_NOTICE_KEY, None)
    _clear_result()


@st.fragment(run_every=0.5)
def _render_running():
    session_id, future, scenario = st.session_state[_JOB_KEY]
    if st.button("Hủy mô phỏng", key="sub06_cancel_simulation"):
        if cancel_simulation_session(session_id):
            future.cancel()
            st.session_state.pop(_JOB_KEY, None)
            st.session_state[_NOTICE_KEY] = ("info", "Đã hủy mô phỏng.")
            st.rerun()

    if not future.done():
        st.info(f"Đang chạy {scenario}.")
        return

    st.session_state.pop(_JOB_KEY, None)
    try:
        result = future.result()
        result["ui_scenario_name"] = scenario
        result["ui_scenario_description"] = SCENARIOS[scenario]["description"]
        st.session_state[_RESULT_KEY] = result
    except CancelledError:
        st.session_state[_NOTICE_KEY] = ("info", "Đã hủy mô phỏng.")
    except Exception:
        st.session_state[_NOTICE_KEY] = ("error", "Mô phỏng gặp lỗi. Vui lòng thử lại.")
    st.rerun()


def _render_setup(state, hubs, operator_id):
    st.markdown('<div class="s6-page-title">What-if Simulation</div>', unsafe_allow_html=True)
    hub_ids = [hub["hub_id"] for hub in hubs]
    hub_names = {hub["hub_id"]: _hub_label(hub) for hub in hubs}

    if st.session_state.get(_SCENARIO_KEY) not in SCENARIOS:
        st.session_state[_SCENARIO_KEY] = "Peak student arrivals"
    scenario_name = st.session_state[_SCENARIO_KEY]
    option = SCENARIOS[scenario_name]

    with st.container(key="s6_setup_top"):
        top_left, top_right = st.columns(2)
        with top_left:
            with st.container(border=True, key="s6_panel_scope"):
                st.markdown('<div class="s6-card-title"><span class="s6-step">1</span>Phạm vi mô phỏng</div>', unsafe_allow_html=True)
                scoped_hubs = (
                    [h["hub_id"] for h in hubs if "metro" in h.get("name", "").lower()]
                    if option["engine"] == "metro_demand_surge"
                    else hub_ids
                ) or hub_ids
                if st.session_state.get(_HUB_KEY) not in scoped_hubs:
                    st.session_state[_HUB_KEY] = scoped_hubs[0]
                hub_id = st.selectbox(
                    "Hub",
                    scoped_hubs,
                    format_func=lambda value: hub_names.get(value, value),
                    key=_HUB_KEY,
                    on_change=_clear_result,
                )
                time_from, time_to = st.columns(2)
                with time_from:
                    start_time = st.text_input("Từ", value="07:00", placeholder="HH:MM", key="sub06_from_time", on_change=_clear_result)
                with time_to:
                    end_time = st.text_input("Đến", value="09:00", placeholder="HH:MM", key="sub06_to_time", on_change=_clear_result)

        with top_right:
            with st.container(border=True, key="s6_panel_scenario"):
                st.markdown('<div class="s6-card-title"><span class="s6-step">2</span>Chọn kịch bản</div>', unsafe_allow_html=True)
                for idx, name in enumerate(SCENARIOS):
                    selected = name == scenario_name
                    st.button(
                        name,
                        key=f"s6_opt_{'on' if selected else 'off'}_{idx}",
                        on_click=_select_scenario,
                        args=(name,),
                        **_FULL,
                    )

    with st.container(border=True, key="s6_panel_params"):
        st.markdown(
            f'<div class="s6-card-title"><span class="s6-step">3</span>'
            f"Tham số: {escape(scenario_name)}</div>",
            unsafe_allow_html=True,
        )
        parameters = _scenario_parameters(option["group"], hub_id, state)
        st.markdown('<hr style="border:none;border-top:1px solid #edf0f4;margin:6px 0">', unsafe_allow_html=True)
        _, run_right = st.columns([4.5, 1.5])
        with run_right:
            if st.button("Chạy mô phỏng", type="primary", key="sub06_run_simulation"):
                _run_simulation(state, scenario_name, hub_id, parameters, start_time, end_time, operator_id=operator_id)


def _kpi_tone(metric):
    mid = metric.get("id")
    after = metric.get("after", 0)
    if not isinstance(after, (int, float)):
        return ""
    if mid in {"vehicle_shortage", "unserved_charging_requests"} and after > 0:
        return "bad"
    if mid in {"parking_utilization", "reservation_utilization"}:
        if after >= 100:
            return "bad"
        if after >= 80:
            return "warn"
    if mid == "low_battery_vehicles" and after > 0:
        return "warn"
    return ""


def _issue_action_button(issue_code):
    if issue_code in {"vehicle_shortage", "network_imbalance", "vehicle_concentration_imbalance"}:
        return "Điều chuyển xe →", "Điều chuyển xe"
    if issue_code == "charger_failure_impact":
        return "Lập lịch sạc →", "Lập lịch sạc"
    if issue_code in {"charging_shortage", "low_battery_risk"}:
        return "Giám sát tài nguyên sạc →", "Giám sát tài nguyên sạc"
    if issue_code and ("parking" in issue_code or "reservation" in issue_code):
        return "Điều chuyển xe →", "Điều chuyển xe"
    return None, None


def _render_result(result, hubs):
    hub_names = {hub["hub_id"]: _hub_label(hub) for hub in hubs}
    c_back, c_title = _cols([0.45, 10], vertical_alignment="center")
    if c_back.button("‹", key="sub06_back"):
        _clear_result()
        st.rerun()
    c_title.markdown(
        '<div class="s6-eyebrow">What-if Simulation</div>'
        '<div class="s6-page-title">Kết quả mô phỏng</div>',
        unsafe_allow_html=True,
    )

    metrics = result.get("metrics", [])
    visible_metrics = metrics[:3]
    left, right = st.columns([0.85, 1.75])

    with left:
        with st.container(border=True, key="s6_panel_summary"):
            hub_name = hub_names.get(result.get("hub_id"), result.get("hub_id", "-"))
            window = result.get("time_window", "-")
            scenario = result.get("ui_scenario_name", result.get("scenario_name", "-"))
            kv_rows = []
            for key, value in result.get("parameters", {}).items():
                if key == "time_window":
                    continue
                label = _PARAM_LABELS.get(key, key.replace("_", " ").capitalize())
                disp_val = hub_names.get(value, value) if key == "source_hub_id" else value
                suffix = "%" if key == "increase_percent" else ""
                kv_rows.append(
                    f'<div class="s6-param-kv"><span>{escape(label)}:</span>'
                    f'<b>{escape(str(disp_val))}{suffix}</b></div>'
                )
            params_html = (
                '<div class="s6-info-lbl">Tham số chi tiết</div>'
                f'<div class="s6-summary-line">{"".join(kv_rows)}</div>'
                if kv_rows
                else ""
            )
            st.markdown(
                '<div class="s6-card-title" style="margin-bottom:14px">'
                '<span class="s6-step ok">✓</span>Thông số đầu vào</div>'
                '<div class="s6-info-lbl" style="margin-top:0">Phạm vi</div>'
                f'<div class="s6-summary-line">{escape(str(hub_name))}'
                '<span style="color:#cbd5e1;margin:0 8px">|</span>'
                f'{escape(str(window))}</div>'
                '<div class="s6-info-lbl">Kịch bản</div>'
                '<div class="s6-summary-line"><span style="color:#789c28;margin-right:8px">●</span>'
                f"{escape(str(scenario))}</div>"
                f"{params_html}",
                unsafe_allow_html=True,
            )

        if st.button("Điều chỉnh tham số", key="sub06_edit_parameters", **_FULL):
            _clear_result()
            st.rerun()

    with right:
        cards = ['<div class="s6-kpis">']
        for metric in visible_metrics:
            before = _format_value(metric.get("before"), metric.get("unit", ""))
            after = _format_value(metric.get("after"), metric.get("unit", ""))
            tone = _kpi_tone(metric)
            cards.append(
                f'<div class="s6-kpi {tone}">'
                f'<div class="s6-kpi-label">{escape(str(metric.get("label", "Chỉ số")))}</div>'
                f'<div class="s6-kpi-val"><span class="s6-kpi-num">{escape(after)}</span>'
                f'<span class="s6-kpi-detail">Trước: {escape(before)}</span></div>'
                "</div>"
            )
        cards.append("</div>")
        st.markdown("".join(cards), unsafe_allow_html=True)

        with st.container(border=True, key="s6_panel_impact"):
            st.markdown('<div class="s6-sec-title">Phân tích tác động & khuyến nghị điều phối</div>', unsafe_allow_html=True)
            recommendations = result.get("recommendations", [])
            for index, issue in enumerate(result.get("issues", [])):
                severity = issue.get("severity", "low")
                icon = "!" if severity in {"high", "medium"} else "✓"
                with st.container(border=True, key=f"s6_issue_{severity}_{index}"):
                    st.markdown(
                        '<div class="s6-issue-head">'
                        f'<span class="s6-issue-ico {severity}">{icon}</span>'
                        f'<div><div class="s6-issue-title {severity}">{escape(str(issue.get("title", "Tác động mô phỏng")))}</div>'
                        f'<div class="s6-issue-detail">{escape(str(issue.get("detail", "")))}</div></div>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    if index < len(recommendations):
                        rec = recommendations[index]
                        btn_label, nav_target = _issue_action_button(issue.get("code"))
                        with st.container(border=True, key=f"s6_rec_box_{index}"):
                            if btn_label:
                                r_txt, r_btn = _cols([3.2, 1.5], vertical_alignment="center")
                            else:
                                r_txt, r_btn = st.container(), None
                            r_txt.markdown(
                                '<div class="s6-recommend-label">Khuyến nghị từ hệ thống</div>'
                                f'<div class="s6-recommend-action">{escape(str(rec.get("action", "")))}</div>'
                                f'<div class="s6-recommend-reason">{escape(str(rec.get("reason", "")))}</div>',
                                unsafe_allow_html=True,
                            )
                            if r_btn is not None:
                                r_btn.button(
                                    btn_label,
                                    type="primary",
                                    key=f"sub06_rec_go_{index}",
                                    on_click=_go_operator_page,
                                    args=(nav_target, result.get("hub_id")),
                                    **_FULL,
                                )
                    elif index == 0 and not recommendations and result.get("infeasibility_reason"):
                        with st.container(border=True, key="s6_rec_box_infeasible"):
                            st.markdown(
                                '<div class="s6-recommend-label">Đánh giá tính khả thi</div>'
                                f'<div class="s6-recommend-reason">{escape(str(result["infeasibility_reason"]))}</div>',
                                unsafe_allow_html=True,
                            )

        st.caption("Kết quả được tính từ bản chụp dữ liệu và lưu trong sandbox.")
        with st.expander("Giả định của lần mô phỏng"):
            for assumption in result.get("assumptions", []):
                st.write(f"• {assumption}")


def render(state: dict[str, Any], current_user: dict[str, Any]) -> None:
    """Render the Operator what-if setup or its latest result."""
    if current_user.get("role") != ROLE_OPERATOR:
        st.warning("What-if Simulation chỉ dành cho Operator.")
        return
    st.markdown(_S6_CSS, unsafe_allow_html=True)
    operator_id = current_user.get("user_id") or current_user.get("username") or "Operator"
    with st.container(key="sub06_root"):
        hubs = [hub for hub in state.get("hubs", []) if hub.get("hub_id")]
        if not hubs:
            st.error("Chưa có dữ liệu Hub để mô phỏng.")
            return
        if notice := st.session_state.pop(_NOTICE_KEY, None):
            kind, message = notice
            (st.error if kind == "error" else st.info)(message)
        result = st.session_state.get(_RESULT_KEY)
        if _JOB_KEY in st.session_state:
            _render_running()
        elif result:
            _render_result(result, hubs)
        else:
            _render_setup(state, hubs, operator_id)
