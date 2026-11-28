"""Operator UI for SUB-04: charging resources, priority queue and schedules."""

from datetime import datetime
from html import escape

import streamlit as st

from modules.sub04 import service
from shared.enums import ROLE_OPERATOR


PAGE_TITLES = {
    "resources": "Giám sát tài nguyên sạc",
    "priority": "Ưu tiên yêu cầu sạc",
    "schedule": "Lập lịch sạc",
}
POINT_LABELS = {
    "AVAILABLE": ("AVAILABLE", "Trống", "green"),
    "IN_USE": ("IN_USE", "Đang sạc", "blue"),
    "RESERVED": ("RESERVED", "Đã hẹn", "amber"),
    "UNAVAILABLE": ("UNAVAILABLE", "Sự cố", "red"),
}
SCHEDULE_STATUS = {
    "PROPOSED": ("Đề xuất", "amber"),
    "CONFIRMED": ("Đã hẹn", "blue"),
    "IN_USE": ("Đang sạc", "blue"),
    "COMPLETED": ("Thành công", "green"),
    "CANCELLED": ("Đã hủy", "gray"),
}
VEHICLE_TYPE_LABELS = {
    "ELECTRIC_BICYCLE": "Xe đạp điện",
    "ELECTRIC_MOTORCYCLE": "Xe máy điện",
}

_S4_CSS = """
<style>
.st-key-sub04_root [data-testid="stVerticalBlock"]{gap:0.75rem !important}
.st-key-sub04_root [data-testid="stMarkdown"],
.st-key-sub04_root [data-testid="stMarkdownContainer"],
.st-key-sub04_root [data-testid="stMarkdownContainer"] > p:last-child{margin-bottom:0 !important}
.st-key-sub04_root [data-testid="stHeaderActionElements"]{display:none !important}
.st-key-sub04_root .s4-page-title{
  padding:0 !important;margin:0 !important;font-weight:700 !important;
  font-size:1.85rem !important;letter-spacing:-.02em !important;line-height:1.18 !important;color:#111827 !important
}
.st-key-sub04_root [class*="st-key-s4_panel_"]{
  border-radius:18px !important;border-color:#e5e7eb !important;
  padding:18px 20px !important;background:#ffffff !important
}
.st-key-sub04_root .s4-sec-head{
  display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px
}
.st-key-sub04_root .s4-sec-title{
  color:#111827;font-size:.84rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase
}
.st-key-sub04_root .s4-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.76rem;color:#4b5563}
.st-key-sub04_root .s4-legend-item{display:inline-flex;align-items:center;gap:5px}
.st-key-sub04_root .s4-dot{width:8px;height:8px;border-radius:999px;display:inline-block}

/* KPI cards */
.st-key-sub04_root .s4-kpis{
  display:grid;grid-template-columns:repeat(var(--s4-kpi-columns,4),minmax(0,1fr));gap:12px;margin:0
}
.st-key-sub04_root .s4-kpi{
  box-sizing:border-box;min-width:0;background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px 20px
}
.st-key-sub04_root .s4-kpi-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.st-key-sub04_root .s4-kpi-label{color:#6b7280;font-size:.74rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.st-key-sub04_root .s4-kpi-val{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
.st-key-sub04_root .s4-kpi-num{font-size:2.1rem;font-weight:700;line-height:1.1;color:#111827}
.st-key-sub04_root .s4-kpi-sub{color:#6b7280;font-size:.8rem;font-weight:500}
.st-key-sub04_root .s4-kpi-badge{
  display:inline-block;margin-top:6px;padding:2px 10px;border-radius:999px;
  font-size:.72rem;font-weight:600;background:#ffe4e6;color:#be123c;border:1px solid #fecdd3
}

/* Light widget overrides for other controls in SUB-04 */
[data-testid="stMain"] .st-key-sub04_root [data-baseweb="select"] > div{
  background:#ffffff !important;border:1px solid #e5e7eb !important;border-radius:10px !important;color:#111827 !important
}
[data-testid="stMain"] .st-key-sub04_root [data-baseweb="select"] > div div{
  background:transparent !important;background-color:transparent !important;border:none !important;box-shadow:none !important
}
[data-testid="stMain"] .st-key-sub04_root [data-baseweb="select"] span,
[data-testid="stMain"] .st-key-sub04_root [data-baseweb="select"] input{color:#111827 !important;font-weight:500 !important}
[data-testid="stMain"] .st-key-sub04_root [data-baseweb="select"] svg{fill:#6b7280 !important;color:#6b7280 !important}
[data-testid="stMain"] .st-key-sub04_root [data-testid="stNumberInputContainer"]{
  background:#ffffff !important;border:1px solid #e5e7eb !important;border-radius:10px !important
}
[data-testid="stMain"] .st-key-sub04_root [data-testid="stNumberInputContainer"] input{background:#ffffff !important;color:#111827 !important}
[data-testid="stMain"] .st-key-sub04_root [data-testid="stNumberInputStepDown"],
[data-testid="stMain"] .st-key-sub04_root [data-testid="stNumberInputStepUp"]{
  background:#f8fafc !important;color:#374151 !important;border-left:1px solid #e5e7eb !important
}

/* Unified pill Hub selector ("Trạm Hub: Metro Station v") */
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker{
  box-sizing:border-box !important;width:max-content !important;max-width:100% !important;
  margin-left:auto !important;background:#ffffff !important;
  border:1px solid #e5e7eb !important;border-radius:999px !important;
  padding:2px 16px !important;height:38px !important;min-height:38px !important;
  display:inline-flex !important;align-items:center !important;cursor:pointer !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker [data-testid="stVerticalBlock"],
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker [data-testid="stElementContainer"]{
  gap:0 !important;margin:0 !important;padding:0 !important;width:auto !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker [data-testid="stHorizontalBlock"]{
  width:max-content !important;display:inline-flex !important;align-items:center !important;
  gap:6px !important;flex-wrap:nowrap !important;margin:0 !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker [data-testid="stColumn"]{
  width:auto !important;flex:0 0 auto !important;min-width:0 !important;padding:0 !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-s4_hub_picker .s4-hub-label{
  font-size:13.5px !important;color:#6b7280 !important;font-weight:400 !important;
  white-space:nowrap !important;line-height:1 !important;margin:0 !important;padding:0 !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub,
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub *{
  background:transparent !important;background-color:transparent !important;
  border:none !important;border-width:0 !important;border-color:transparent !important;
  box-shadow:none !important;outline:none !important;border-radius:0 !important;
  font-weight:600 !important;color:#1f2937 !important;font-size:13.5px !important;
  line-height:1.2 !important;white-space:nowrap !important;
  caret-color:transparent !important;user-select:none !important;cursor:pointer !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub,
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-testid="stSelectbox"],
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"],
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] div{
  width:auto !important;min-width:0 !important;max-width:none !important;
  flex:0 0 auto !important;padding:0 !important;margin:0 !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] > div{
  height:32px !important;min-height:32px !important;
  display:inline-flex !important;align-items:center !important;gap:10px !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] div:has(> input),
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] input{
  position:absolute !important;width:0 !important;height:0 !important;
  min-width:0 !important;max-width:0 !important;overflow:hidden !important;
  padding:0 !important;margin:0 !important;opacity:0 !important;pointer-events:none !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] > div > div:last-child{
  display:inline-flex !important;align-items:center !important;justify-content:center !important;
  width:14px !important;height:14px !important;flex:0 0 14px !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] svg{
  display:none !important
}
[data-testid="stMain"] .st-key-sub04_root .st-key-sub04_selected_hub [data-baseweb="select"] > div > div:last-child::after{
  content:"";width:13px;height:13px;display:block;background-color:#4b5563;
  -webkit-mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%2024%2024'%20fill%3D'none'%20stroke%3D'black'%20stroke-width%3D'2'%20stroke-linecap%3D'round'%20stroke-linejoin%3D'round'%3E%3Cpolyline%20points%3D'6%209%2012%2015%2018%209'%2F%3E%3C%2Fsvg%3E");
  mask-image:url("data:image/svg+xml;utf8,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%2024%2024'%20fill%3D'none'%20stroke%3D'black'%20stroke-width%3D'2'%20stroke-linecap%3D'round'%20stroke-linejoin%3D'round'%3E%3Cpolyline%20points%3D'6%209%2012%2015%2018%209'%2F%3E%3C%2Fsvg%3E");
  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center;
  -webkit-mask-size:contain;mask-size:contain
}
[data-baseweb="popover"] [data-baseweb="menu"]{
  min-width:210px !important;border-radius:12px !important
}

/* Charging point cards */
.st-key-sub04_root .s4-points{
  box-sizing:border-box;width:100%;display:grid;
  grid-template-columns:repeat(var(--s4-pt-cols,4),minmax(0,1fr));gap:10px;padding-bottom:2px
}
.st-key-sub04_root .s4-point{
  box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:12px 14px;border:1px solid #e5e7eb;border-radius:12px;min-width:0;
  font-size:.82rem;font-weight:600;white-space:nowrap
}
.st-key-sub04_root .s4-point.green{background:#f4f9ed;border-color:#cde4b4;color:#111827}
.st-key-sub04_root .s4-point.blue{background:#f4f8ff;border-color:#bfdbfe;color:#111827}
.st-key-sub04_root .s4-point.amber{background:#fffbeb;border-color:#fde68a;color:#111827}
.st-key-sub04_root .s4-point.red{background:#fff5f6;border-color:#fecdd3;color:#be123c}
.st-key-sub04_root .s4-status{font-size:.66rem;font-weight:600;padding:3px 8px;border-radius:7px;white-space:nowrap}
.st-key-sub04_root .s4-status.green{background:#789c28;color:#ffffff}
.st-key-sub04_root .s4-status.blue{background:#dbeafe;color:#1d4ed8}
.st-key-sub04_root .s4-status.amber{background:#fef3c7;color:#92400e}
.st-key-sub04_root .s4-status.red{background:#ffe4e6;color:#be123c}

/* Pills & tables */
.st-key-sub04_root .s4-pill{display:inline-block;padding:3px 11px;border-radius:999px;font-size:.74rem;font-weight:600;border:1px solid;white-space:nowrap}
.st-key-sub04_root .s4-green{color:#166534;background:#dcfce7;border-color:#bbf7d0}
.st-key-sub04_root .s4-blue{color:#1d4ed8;background:#dbeafe;border-color:#bfdbfe}
.st-key-sub04_root .s4-amber{color:#92400e;background:#fef3c7;border-color:#fde68a}
.st-key-sub04_root .s4-red{color:#be123c;background:#ffe4e6;border-color:#fecdd3}
.st-key-sub04_root .s4-gray{color:#4b5563;background:#f3f4f6;border-color:#e5e7eb}

.st-key-sub04_root .s4-thead{font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;padding:4px 0}
.st-key-sub04_root .s4-thead-line{border:none;border-top:1px solid #e5e7eb;margin:-2px 0 2px 0}
.st-key-sub04_root .s4-sep{border:none;border-top:1px solid #f1f5f9;margin:-2px 0}
.st-key-sub04_root .s4-cell{font-size:.86rem;padding:4px 0;color:#111827;font-weight:500}
.st-key-sub04_root .s4-cell-muted{font-size:.86rem;padding:4px 0;color:#4b5563;font-weight:500}
.st-key-sub04_root .s4-sub{font-size:.76rem;color:#6b7280;margin-top:1px}
.st-key-sub04_root .s4-strong{font-weight:600;color:#111827}
.st-key-sub04_root .s4-rank{
  display:inline-flex;width:26px;height:26px;align-items:center;justify-content:center;
  border-radius:50%;background:#f1f5f9;color:#475569;font-weight:600;font-size:.76rem
}
.st-key-sub04_root .s4-rank.bad{background:#ffe4e6;color:#be123c}
.st-key-sub04_root .s4-rank.warn{background:#fef3c7;color:#92400e}
.st-key-sub04_root .s4-empty{
  box-sizing:border-box;background:#f8fafc;border:1px solid #e5e7eb;border-radius:12px;
  padding:12px 16px;font-size:.86rem;color:#6b7280
}
.st-key-sub04_root [class*="st-key-s4_row_head_"],
.st-key-sub04_root [class*="st-key-s4_row_ok_"]{box-sizing:border-box;padding:0 10px;margin:0}
.st-key-sub04_root [class*="st-key-s4_row_bad_"]{box-sizing:border-box;background:#fff5f6;border-radius:12px;padding:6px 10px;margin:0}
.st-key-sub04_root [class*="st-key-s4_row_warn_"]{box-sizing:border-box;background:#fffbeb;border-radius:12px;padding:6px 10px;margin:0}

/* Buttons */
.st-key-sub04_root button[kind="primary"],
.st-key-sub04_root button[data-testid="stBaseButton-primary"]{
  background:#789c28 !important;border-color:#789c28 !important;color:#fff !important;border-radius:10px !important;font-weight:600 !important
}
.st-key-sub04_root button[kind="primary"] *{color:#fff !important;font-weight:600 !important}
.st-key-sub04_root .st-key-sub04_go_sched button{
  background:#f4f8ec !important;border:1px solid #cde4b4 !important;border-radius:10px !important;padding:4px 12px !important;min-height:32px !important
}
.st-key-sub04_root .st-key-sub04_go_sched button *{color:#4d7c0f !important;font-size:.8rem !important;font-weight:600 !important}
.st-key-sub04_root [class*="st-key-sub04_act_"] button,
.st-key-sub04_root [class*="st-key-sub04_view_"] button,
.st-key-sub04_root [class*="st-key-sub04_skip_"] button,
.st-key-sub04_root [class*="st-key-sub04_priority_"] button,
.st-key-sub04_root [class*="st-key-sub04_propose_"] button{
  background:#fff !important;border:1px solid #e5e7eb !important;border-radius:10px !important;
  padding:3px 12px !important;min-height:30px !important;height:30px !important
}
.st-key-sub04_root [class*="st-key-sub04_act_"] button *,
.st-key-sub04_root [class*="st-key-sub04_view_"] button *,
.st-key-sub04_root [class*="st-key-sub04_skip_"] button *,
.st-key-sub04_root [class*="st-key-sub04_priority_"] button *,
.st-key-sub04_root [class*="st-key-sub04_propose_"] button *{color:#111827 !important;font-size:.78rem !important;font-weight:600 !important}
.st-key-sub04_root [class*="st-key-sub04_confirm_"] button{
  background:#eef7e6 !important;border:1px solid #cde4b4 !important;border-radius:10px !important;
  padding:3px 12px !important;min-height:30px !important;height:30px !important
}
.st-key-sub04_root [class*="st-key-sub04_confirm_"] button *{color:#3f6212 !important;font-size:.78rem !important;font-weight:600 !important}
.st-key-sub04_root [class*="st-key-sub04_report_"] button{
  background:#e11d48 !important;border:1px solid #e11d48 !important;border-radius:10px !important;
  padding:3px 14px !important;min-height:30px !important;height:30px !important
}
.st-key-sub04_root [class*="st-key-sub04_report_"] button *{color:#fff !important;font-size:.78rem !important;font-weight:600 !important}
.st-key-sub04_root [class*="st-key-sub04_stop_"] button,
.st-key-sub04_root [class*="st-key-sub04_cancel_"] button{
  background:#fff !important;border:1px solid #fecdd3 !important;border-radius:10px !important;
  padding:3px 12px !important;min-height:30px !important;height:30px !important
}
.st-key-sub04_root [class*="st-key-sub04_stop_"] button *,
.st-key-sub04_root [class*="st-key-sub04_cancel_"] button *{color:#be123c !important;font-size:.78rem !important;font-weight:600 !important}

@media(max-width:900px){
  .st-key-sub04_root .s4-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .st-key-sub04_root .s4-points{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media(max-width:600px){
  .st-key-sub04_root .s4-kpis{grid-template-columns:1fr}
  .st-key-sub04_root .s4-points{grid-template-columns:1fr}
}
</style>
"""


def _cols(spec, **kwargs):
    try:
        return st.columns(spec, **kwargs)
    except TypeError:
        kwargs.pop("vertical_alignment", None)
        return st.columns(spec, **kwargs)


def _display_time(value, with_date=False):
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%d/%m/%Y • %H:%M:%S" if with_date else "%H:%M:%S")
    except (TypeError, ValueError):
        return "-"


def _pick_time(*values):
    for value in values:
        formatted = _display_time(value, True)
        if formatted != "-":
            return formatted
    return st.session_state.setdefault(
        "sub04_seed_time",
        datetime.now().strftime("%d/%m/%Y • %H:%M:%S"),
    )


def _point_label(point_id):
    digits = "".join(char for char in str(point_id or "") if char.isdigit())
    return f"Trụ #{int(digits):02d}" if digits else str(point_id or "-")


def _hub_label(hub):
    return str(hub.get("name") or hub.get("address") or hub.get("hub_id", ""))


def _vehicle_label(vehicle):
    if not vehicle:
        return "-"
    vtype = VEHICLE_TYPE_LABELS.get(vehicle.get("vehicle_type"), "")
    vid = vehicle.get("vehicle_id", "-")
    return f"{vtype} #{vid}".strip()


def _pill(text, tone):
    return f'<span class="s4-pill s4-{tone}">{escape(str(text))}</span>'


def _show_kpis(items, columns=4):
    html = [f'<div class="s4-kpis" style="--s4-kpi-columns:{columns}">']
    for item in items:
        label, value, unit, dot_color = item[:4]
        num_color = item[4] if len(item) > 4 else "#111827"
        badge = item[5] if len(item) > 5 else ""
        badge_html = f'<div><span class="s4-kpi-badge">{escape(badge)}</span></div>' if badge else ""
        dot_html = f'<span class="s4-dot" style="background:{dot_color}"></span>' if dot_color else ""
        html.append(
            '<div class="s4-kpi">'
            f'<div class="s4-kpi-top"><span class="s4-kpi-label">{escape(str(label))}</span>{dot_html}</div>'
            f'<div class="s4-kpi-val"><span class="s4-kpi-num" style="color:{num_color}">{escape(str(value))}</span>'
            f'<span class="s4-kpi-sub">{escape(str(unit))}</span></div>'
            f'{badge_html}</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)

def _header(title, hubs):
    left, right = _cols([5.5, 3.5], vertical_alignment="center")
    with left:
        st.markdown(f'<div class="s4-page-title">{escape(title)}</div>', unsafe_allow_html=True)
    hub_ids = [hub["hub_id"] for hub in hubs]
    hub_names = {hub["hub_id"]: _hub_label(hub) for hub in hubs}
    with right:
        with st.container(key="s4_hub_picker"):
            c_lbl, c_sel = _cols([1.0, 1.9], vertical_alignment="center")
            c_lbl.markdown('<div class="s4-hub-label">Trạm Hub:</div>', unsafe_allow_html=True)
            hub_id = c_sel.selectbox(
                "Trạm Hub",
                hub_ids,
                format_func=lambda value: hub_names.get(value, value),
                key="sub04_selected_hub",
                label_visibility="collapsed",
            )
    return hub_id, hub_names


def _nav_to(label, **extra):
    st.session_state["sub05_nav_request"] = label
    for key, value in extra.items():
        st.session_state[key] = value

def _emergency_stop_point(state, point_id, schedule_id=None, vehicle_id=None):
    for pt in state.get("charging_points", []):
        if pt.get("charging_point_id") == point_id:
            pt["status"] = "AVAILABLE"
            break
    if schedule_id:
        for sc in state.get("charging_schedules", []):
            if sc.get("schedule_id") == schedule_id:
                sc["status"] = "CANCELLED"
                break
    if vehicle_id:
        for veh in state.get("vehicles", []):
            if veh.get("vehicle_id") == vehicle_id and veh.get("status") == "CHARGING":
                veh["status"] = "AVAILABLE"
                break
    st.session_state["sub04_notice"] = f"Đã ngắt an toàn phiên sạc tại {_point_label(point_id)}."
    st.rerun()


def _resources(state, hub_id):
    data = service.get_charging_resources(state, hub_id)
    points = data["points"]
    total = len(points)
    available = sum(point["status"] == "AVAILABLE" for point in points)
    in_use = sum(point["status"] == "IN_USE" for point in points)
    reserved = sum(point["status"] == "RESERVED" for point in points)
    unavailable = sum(point["status"] == "UNAVAILABLE" for point in points)
    near = total > 0 and available / total <= 0.2

    k1, k2, k3 = st.columns(3)
    k1.markdown(
        '<div class="s4-kpi">'
        '<div class="s4-kpi-top"><span class="s4-kpi-label">Cổng khả dụng (AVAILABLE)</span>'
        '<span class="s4-dot" style="background:#789c28"></span></div>'
        f'<div class="s4-kpi-val"><span class="s4-kpi-num" style="color:{"#e11d48" if near else "#111827"}">{available}</span>'
        f'<span class="s4-kpi-sub">/ {total} cổng</span></div>'
        + ('<div><span class="s4-kpi-badge">Near Capacity</span></div>' if near else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    k2.markdown(
        '<div class="s4-kpi">'
        '<div class="s4-kpi-top"><span class="s4-kpi-label">Đang cắm sạc (IN_USE)</span>'
        '<span class="s4-dot" style="background:#2563eb"></span></div>'
        f'<div class="s4-kpi-val"><span class="s4-kpi-num">{in_use}</span>'
        '<span class="s4-kpi-sub">phiên</span></div></div>',
        unsafe_allow_html=True,
    )
    k3.markdown(
        '<div class="s4-kpi">'
        '<div class="s4-kpi-top"><span class="s4-kpi-label">Lịch hẹn / Sự cố</span></div>'
        '<div class="s4-kpi-val" style="gap:10px">'
        f'<span style="color:#2563eb;font-size:1.35rem;font-weight:700">{reserved} Lịch Hẹn</span>'
        '<span style="color:#d1d5db">|</span>'
        f'<span style="color:#e11d48;font-size:1.35rem;font-weight:700">{unavailable} Hỏng</span>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    with st.container(border=True, key="s4_panel_points"):
        st.markdown(
            '<div class="s4-sec-head">'
            '<div class="s4-sec-title">Trạng thái các cổng sạc</div>'
            '<div class="s4-legend">'
            '<span class="s4-legend-item"><span class="s4-dot" style="background:#789c28"></span>AVAILABLE (Trống)</span>'
            '<span class="s4-legend-item"><span class="s4-dot" style="background:#2563eb"></span>IN_USE (Đang sạc)</span>'
            '<span class="s4-legend-item"><span class="s4-dot" style="background:#f59e0b"></span>RESERVED (Đã hẹn)</span>'
            '<span class="s4-legend-item"><span class="s4-dot" style="background:#e11d48"></span>UNAVAILABLE (Sự cố)</span>'
            "</div></div>",
            unsafe_allow_html=True,
        )
        cols_count = max(len(points), 1)
        html = [f'<div class="s4-points" style="--s4-pt-cols:{cols_count}">']
        for point in points:
            status = point.get("status", "UNAVAILABLE")
            code, _, tone = POINT_LABELS.get(status, (status, status, "red"))
            label = _point_label(point.get("charging_point_id"))
            html.append(
                f'<div class="s4-point {tone}"><span>{escape(label.upper())}</span>'
                f'<span class="s4-status {tone}">{escape(code)}</span></div>'
            )
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)

    with st.container(border=True, key="s4_panel_logs"):
        st.markdown('<div class="s4-sec-title" style="margin-bottom:8px">Nhật ký phiên sạc & lịch đặt trước tại trạm</div>', unsafe_allow_html=True)
        schedules = data["schedules"]
        requests = state.get("charging_requests", []) + state.get("shared_charging_requests", [])
        request_map = {request.get("request_id"): request for request in requests}
        vehicles_by_id = {v.get("vehicle_id"): v for v in state.get("vehicles", [])}
        scheduled_point_ids = {
            s.get("charging_point_id")
            for s in schedules
            if s.get("status") in ("PROPOSED", "CONFIRMED", "IN_USE")
        }
        scheduled_vids = {
            request_map.get(s.get("request_id"), {}).get("vehicle_id")
            for s in schedules
            if s.get("status") in ("PROPOSED", "CONFIRMED", "IN_USE")
        }
        free_charging_vehicles = [
            v
            for v in state.get("vehicles", [])
            if v.get("hub_id") == hub_id
            and v.get("status") == "CHARGING"
            and v.get("vehicle_id") not in scheduled_vids
        ]
        incidents_by_res = {
            inc.get("resource_id"): inc
            for inc in state.get("incidents", [])
            if inc.get("status") == "OPEN"
        }
        hub_obj = next((h for h in state.get("hubs", []) if h.get("hub_id") == hub_id), {})
        hub_updated = hub_obj.get("data_updated_at") or hub_obj.get("updated_at")

        rows = []
        for schedule in reversed(schedules):
            request = request_map.get(schedule.get("request_id"), {})
            rows.append({"kind": "schedule", "schedule": schedule, "request": request})
        for point in points:
            pid = point.get("charging_point_id")
            pstatus = point.get("status")
            if pid in scheduled_point_ids:
                continue
            if pstatus == "IN_USE":
                veh = free_charging_vehicles.pop(0) if free_charging_vehicles else None
                rows.append({"kind": "point_in_use", "point": point, "vehicle": veh})
            elif pstatus == "RESERVED":
                rows.append({"kind": "point_reserved", "point": point})
            elif pstatus == "UNAVAILABLE":
                rows.append({"kind": "broken_point", "point": point})

        if not rows:
            st.markdown('<div class="s4-empty">Chưa có phiên sạc, lịch đặt trước hoặc sự cố tại Hub này.</div>', unsafe_allow_html=True)
        else:
            widths = [1.85, 1.0, 2.0, 1.25, 1.25, 1.25]
            with st.container(key="s4_row_head_logs"):
                head = st.columns(widths)
                for col, text in zip(head, ["NGÀY & THỜI GIAN TẠO", "CỔNG SẠC", "PHƯƠNG TIỆN", "MỨC PIN HIỆN TẠI", "TRẠNG THÁI", "LỆNH ĐIỀU KHIỂN"]):
                    col.markdown(f'<div class="s4-thead">{text}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="s4-thead-line">', unsafe_allow_html=True)

            for idx, item in enumerate(rows):
                kind = item["kind"]
                if kind == "broken_point":
                    pt = item["point"]
                    pid = pt["charging_point_id"]
                    inc = incidents_by_res.get(pid)
                    time_txt = _pick_time(
                        inc.get("created_at") if inc else None,
                        pt.get("updated_at"),
                        pt.get("created_at"),
                        hub_updated,
                    )
                    with st.container(key=f"s4_row_bad_{pid}"):
                        r = _cols(widths, vertical_alignment="center")
                        r[0].markdown(f'<div class="s4-cell" style="color:#be123c">{escape(time_txt)}</div>', unsafe_allow_html=True)
                        r[1].markdown(f'<div class="s4-cell" style="color:#be123c;font-weight:600">{escape(_point_label(pid))}</div>', unsafe_allow_html=True)
                        r[2].markdown('<div class="s4-cell"></div>', unsafe_allow_html=True)
                        r[3].markdown('<div class="s4-cell"></div>', unsafe_allow_html=True)
                        r[4].markdown(f'<div class="s4-cell">{_pill("UNAVAILABLE", "red")}</div>', unsafe_allow_html=True)
                        r[5].button(
                            "Báo kỹ thuật",
                            key=f"sub04_report_{pid}",
                            on_click=_nav_to,
                            args=("Sự cố",),
                            kwargs={"sub05_prefill_resource": pid, "sub05_show_incident_form": True},
                        )
                elif kind in ("point_in_use", "point_reserved"):
                    pt = item["point"]
                    pid = pt["charging_point_id"]
                    pstatus = pt.get("status", "IN_USE")
                    veh = item.get("vehicle")
                    bat = veh.get("battery_level") if veh else None
                    veh_txt = _vehicle_label(veh) if veh else ""
                    pt_time = _pick_time(
                        pt.get("updated_at"),
                        pt.get("created_at"),
                        veh.get("updated_at") if veh else None,
                        hub_updated,
                    )
                    with st.container(key=f"s4_row_ok_pt_{pid}"):
                        r = _cols(widths, vertical_alignment="center")
                        r[0].markdown(f'<div class="s4-cell-muted">{escape(pt_time)}</div>', unsafe_allow_html=True)
                        r[1].markdown(f'<div class="s4-cell s4-strong">{escape(_point_label(pid))}</div>', unsafe_allow_html=True)
                        r[2].markdown(f'<div class="s4-cell s4-strong">{escape(veh_txt)}</div>', unsafe_allow_html=True)
                        r[3].markdown(
                            f'<div class="s4-cell s4-strong">{f"{bat:g}%" if bat is not None else ""}</div>',
                            unsafe_allow_html=True,
                        )
                        r[4].markdown(f'<div class="s4-cell">{_pill(pstatus, "blue" if pstatus == "IN_USE" else "amber")}</div>', unsafe_allow_html=True)
                        if pstatus == "IN_USE":
                            if r[5].button("Ngắt an toàn", key=f"sub04_stop_pt_{pid}"):
                                _emergency_stop_point(state, pid, vehicle_id=veh.get("vehicle_id") if veh else None)
                        else:
                            r[5].button(
                                "Xem lịch hẹn",
                                key=f"sub04_view_pt_{pid}",
                                on_click=_nav_to,
                                args=("Lập lịch sạc",),
                            )
                else:
                    sc = item["schedule"]
                    req = item["request"]
                    sid = sc["schedule_id"]
                    pid = sc.get("charging_point_id")
                    status = sc.get("status", "-")
                    _, tone = SCHEDULE_STATUS.get(status, (status, "gray"))
                    vid = req.get("vehicle_id")
                    veh_obj = vehicles_by_id.get(vid)
                    vehicle_text = _vehicle_label(veh_obj) if veh_obj else str(vid or req.get("request_id", "-"))
                    bat = req.get("current_battery")
                    sc_time = _pick_time(sc.get("created_at"), sc.get("start_time"), hub_updated)
                    with st.container(key=f"s4_row_ok_{sid}"):
                        r = _cols(widths, vertical_alignment="center")
                        r[0].markdown(f'<div class="s4-cell-muted">{escape(sc_time)}</div>', unsafe_allow_html=True)
                        r[1].markdown(f'<div class="s4-cell s4-strong">{escape(_point_label(pid))}</div>', unsafe_allow_html=True)
                        r[2].markdown(f'<div class="s4-cell s4-strong">{escape(vehicle_text)}</div>', unsafe_allow_html=True)
                        r[3].markdown(
                            f'<div class="s4-cell s4-strong">{f"{bat:g}%" if bat is not None else ""}</div>',
                            unsafe_allow_html=True,
                        )
                        r[4].markdown(f'<div class="s4-cell">{_pill(status, tone)}</div>', unsafe_allow_html=True)
                        if status == "IN_USE":
                            if r[5].button("Ngắt an toàn", key=f"sub04_stop_sc_{sid}"):
                                _emergency_stop_point(state, pid, schedule_id=sid, vehicle_id=vid)
                        elif status == "PROPOSED":
                            if r[5].button("Xác nhận", key=f"sub04_confirm_res_{sid}"):
                                _run_action(service.confirm_charging_schedule, state, sid)
                        elif status == "CONFIRMED":
                            r[5].button(
                                "Xem lịch hẹn",
                                key=f"sub04_view_sc_{sid}",
                                on_click=_nav_to,
                                args=("Lập lịch sạc",),
                            )
                        else:
                            r[5].markdown('<div class="s4-cell"></div>', unsafe_allow_html=True)

                next_bad = idx + 1 < len(rows) and rows[idx + 1]["kind"] == "broken_point"
                if idx < len(rows) - 1 and kind != "broken_point" and not next_bad:
                    st.markdown('<hr class="s4-sep">', unsafe_allow_html=True)

        active = [schedule for schedule in schedules if schedule.get("status") in service.ACTIVE]
        if active:
            with st.expander("Cập nhật tiến độ phiên sạc"):
                schedule_ids = [schedule["schedule_id"] for schedule in active]
                selected_id = st.selectbox("Phiên sạc", schedule_ids, key="sub04_resource_active")
                selected = next(item for item in active if item["schedule_id"] == selected_id)
                progress = st.number_input(
                    "Tiến độ (%)", min_value=int(selected["progress"]), max_value=100,
                    value=int(selected["progress"]), key=f"sub04_resource_progress_{selected_id}",
                )
                if st.button("Cập nhật phiên sạc", type="primary", key="sub04_resource_update"):
                    _run_action(service.update_charging_progress, state, selected_id, progress)


def _priority(state, hub_id):
    ranked, incomplete = service.prioritize_charging_requests(state, hub_id)
    skipped = st.session_state.setdefault("sub04_skipped_requests", set())
    incomplete_visible = [item for item in incomplete if item.get("request_id") not in skipped]

    high = sum(float(item.get("current_battery", 100)) < 20 for item in ranked)
    normal = len(ranked) - high
    _show_kpis([
        ("Tổng yêu cầu chờ", len(ranked) + len(incomplete_visible), "yêu cầu", "#6b7280", "#111827"),
        ("Ưu tiên cao", high, "Pin < 20%", "#e11d48", "#e11d48"),
        ("Ưu tiên bình thường", normal, "Pin ≥ 20%", "#2563eb", "#2563eb"),
        ("Chờ xác minh", len(incomplete_visible), "Thiếu / Trễ dữ liệu", "#f59e0b", "#d97706"),
    ])

    with st.container(border=True, key="s4_panel_priority"):
        top_left, top_right = _cols([4.2, 1.4], vertical_alignment="center")
        top_left.markdown('<div class="s4-sec-title">Bảng xếp hạng ưu tiên</div>', unsafe_allow_html=True)
        top_right.button(
            "Chuyển sang Lập lịch →",
            key="sub04_go_sched",
            on_click=_nav_to,
            args=("Lập lịch sạc",),
            use_container_width=True,
        )

        if not ranked and not incomplete_visible:
            st.markdown('<div class="s4-empty">Chưa có yêu cầu sạc nào đang chờ tại Hub này.</div>', unsafe_allow_html=True)
            return

        widths = [0.55, 1.45, 0.8, 1.05, 1.0, 1.85, 0.9]
        with st.container(key="s4_row_head_prio"):
            head = st.columns(widths)
            for col, text in zip(head, ["HẠNG", "PHƯƠNG TIỆN", "MỨC PIN", "GIỜ DÙNG DỰ KIẾN", "GIỜ GỬI YÊU CẦU", "TIÊU CHÍ ƯU TIÊN CHÍNH", "HÀNH ĐỘNG"]):
                col.markdown(f'<div class="s4-thead">{text}</div>', unsafe_allow_html=True)
        st.markdown('<hr class="s4-thead-line">', unsafe_allow_html=True)

        for rank, request in enumerate(ranked, 1):
            battery = float(request.get("current_battery", 0))
            vehicle_id = request.get("vehicle_id") or request.get("request_id", "-")
            kind = "Xe dùng chung" if request.get("vehicle_id") else "Xe cá nhân"
            departure = request.get("departure_time")
            created = request.get("created_at")
            criteria = "Pin thấp" if battery < 20 else "Giờ dùng gần / FIFO"
            if departure:
                criteria += " + Dùng gần"
            bat_color = "#e11d48" if battery < 20 else "#2563eb"
            crit_color = "#e11d48" if battery < 20 else "#374151"

            with st.container(key=f"s4_row_ok_prio_{request['request_id']}"):
                row = _cols(widths, vertical_alignment="center")
                row[0].markdown(f'<span class="s4-rank">{rank}</span>', unsafe_allow_html=True)
                row[1].markdown(
                    f'<div class="s4-cell s4-strong">{escape(str(vehicle_id))}</div>'
                    f'<div class="s4-sub">{kind}</div>',
                    unsafe_allow_html=True,
                )
                row[2].markdown(f'<div class="s4-cell" style="color:{bat_color};font-weight:600">{battery:g}%</div>', unsafe_allow_html=True)
                row[3].markdown(
                    f'<div class="s4-cell" style="font-weight:600">{escape(str(departure))}</div>'
                    if departure else '<div class="s4-cell-muted"><i>Không có</i></div>',
                    unsafe_allow_html=True,
                )
                row[4].markdown(f'<div class="s4-cell">{escape(_display_time(created))}</div>', unsafe_allow_html=True)
                row[5].markdown(f'<div class="s4-cell" style="color:{crit_color};font-weight:600">{escape(criteria)}</div>', unsafe_allow_html=True)
                if row[6].button("Xếp lịch", key=f"sub04_priority_{request['request_id']}"):
                    _run_action(service.propose_charging_schedule, state, request["request_id"])
            if rank < len(ranked):
                st.markdown('<hr class="s4-sep">', unsafe_allow_html=True)

        for item in incomplete_visible:
            rid = item["request_id"]
            vid = item.get("vehicle_id") or rid
            bat = item.get("current_battery")
            with st.container(key=f"s4_row_warn_{rid}"):
                row = _cols(widths, vertical_alignment="center")
                row[0].markdown('<span class="s4-rank warn">--</span>', unsafe_allow_html=True)
                row[1].markdown(f'<div class="s4-cell s4-strong">{escape(str(vid))}</div>', unsafe_allow_html=True)
                row[2].markdown(
                    f'<div class="s4-cell">{f"{bat:g}%" if bat is not None else "?"}</div>',
                    unsafe_allow_html=True,
                )
                row[3].markdown(f'<div class="s4-cell-muted">{escape(str(item.get("departure_time") or "--"))}</div>', unsafe_allow_html=True)
                row[4].markdown(f'<div class="s4-cell">{escape(_display_time(item.get("created_at")))}</div>', unsafe_allow_html=True)
                row[5].markdown(
                    f'<div class="s4-cell" style="color:#b45309;font-weight:600">{escape(str(item.get("reason", "Thiếu dữ liệu")))}</div>',
                    unsafe_allow_html=True,
                )
                if row[6].button("Bỏ qua", key=f"sub04_skip_{rid}"):
                    skipped.add(rid)
                    st.rerun()

def _scheduling(state, hub_id):
    data = service.get_charging_resources(state, hub_id)
    ranked, incomplete = service.prioritize_charging_requests(state, hub_id)
    schedules = data["schedules"]
    schedules_by_request = {schedule.get("request_id"): schedule for schedule in schedules}
    points = data["points"]

    confirmed = sum(schedule.get("status") in service.ACTIVE for schedule in schedules)
    rejected = 0
    candidate_rows = []
    for request in ranked:
        schedule = schedules_by_request.get(request["request_id"])
        preview = None
        reason = ""
        if schedule:
            preview = schedule
        else:
            try:
                preview = service.preview_charging_schedule(state, request["request_id"])
            except ValueError as error:
                reason = str(error)
                rejected += 1
        candidate_rows.append((request, schedule, preview, reason))

    avail_pts = sum(p["status"] == "AVAILABLE" for p in points)
    _show_kpis([
        ("Yêu cầu chờ xử lý", len(ranked) + len(incomplete), "yêu cầu", "#6b7280", "#111827"),
        ("Candidate Pool", avail_pts, f"/ {len(points)} cổng khả dụng", "#2563eb", "#2563eb"),
        ("Phân bổ thành công", confirmed, "đã xác nhận / đang sạc", "#789c28", "#658520"),
        ("Từ chối", rejected + len(incomplete), "", "#e11d48", "#e11d48"),
    ])

    with st.container(border=True, key="s4_panel_schedule"):
        top_l, top_r = _cols([4.2, 1.8], vertical_alignment="center")
        top_l.markdown(
            '<div class="s4-sec-title" style="margin-bottom:0">Chi tiết đề xuất phân bổ theo thứ tự ưu tiên</div>',
            unsafe_allow_html=True,
        )
        proposable_ids = [
            req["request_id"]
            for req, sc, prev, rsn in candidate_rows
            if not rsn and not sc and prev
        ]
        if proposable_ids and top_r.button(
            "Lập tất cả đề xuất",
            type="primary",
            key="sub04_propose_all",
            use_container_width=True,
        ):
            for rid in proposable_ids:
                try:
                    service.propose_charging_schedule(state, rid)
                except ValueError:
                    pass
            st.session_state["sub04_notice"] = f"Đã tạo đề xuất lịch cho {len(proposable_ids)} yêu cầu."
            st.rerun()

        if not candidate_rows and not incomplete:
            st.markdown('<div class="s4-empty">Chưa có yêu cầu chờ xử lý tại Hub này.</div>', unsafe_allow_html=True)
        else:
            widths = [0.5, 1.35, 1.1, 1.45, 1.1, 2.0]
            with st.container(key="s4_row_head_sched"):
                head = st.columns(widths)
                for col, text in zip(head, ["HẠNG", "PHƯƠNG TIỆN", "TRỤ SẠC ĐỀ XUẤT", "KHUNG THỜI GIAN", "TRẠNG THÁI PHÂN BỔ", "THAO TÁC / GHI CHÚ"]):
                    col.markdown(f'<div class="s4-thead">{text}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="s4-thead-line">', unsafe_allow_html=True)

            for rank, (request, schedule, preview, reason) in enumerate(candidate_rows, 1):
                vehicle = request.get("vehicle_id") or request.get("request_id", "-")
                kind = "Xe dùng chung" if request.get("vehicle_id") else "Xe cá nhân"
                if preview:
                    point_label = _point_label(preview.get("charging_point_id"))
                    time_range = f"{_display_time(preview.get('start_time'))} - {_display_time(preview.get('end_time'))}"
                else:
                    point_label, time_range = "Không có", "-"

                is_bad = bool(reason)
                row_key = f"s4_row_bad_sch_{request['request_id']}" if is_bad else f"s4_row_ok_sch_{request['request_id']}"
                with st.container(key=row_key):
                    r = _cols(widths, vertical_alignment="center")
                    r[0].markdown(f'<span class="s4-rank {"bad" if is_bad else ""}">{rank}</span>', unsafe_allow_html=True)
                    r[1].markdown(
                        f'<div class="s4-cell s4-strong" style="color:{"#be123c" if is_bad else "#111827"}">{escape(str(vehicle))}</div>'
                        f'<div class="s4-sub">{kind}</div>',
                        unsafe_allow_html=True,
                    )
                    r[2].markdown(
                        f'<div class="s4-cell" style="color:{"#6b7280" if is_bad else "#2563eb"};font-weight:600">{escape(point_label)}</div>',
                        unsafe_allow_html=True,
                    )
                    r[3].markdown(
                        f'<div class="s4-cell" style="color:{"#be123c" if is_bad else "#111827"}">{escape(time_range)}</div>',
                        unsafe_allow_html=True,
                    )
                    if is_bad:
                        r[4].markdown(f'<div class="s4-cell">{_pill("Từ chối", "red")}</div>', unsafe_allow_html=True)
                        r[5].markdown(f'<div class="s4-cell" style="color:#be123c;font-weight:600">{escape(reason)}</div>', unsafe_allow_html=True)
                    elif schedule and schedule.get("status") == "PROPOSED":
                        r[4].markdown(f'<div class="s4-cell">{_pill("Đề xuất", "amber")}</div>', unsafe_allow_html=True)
                        b_ok, b_no = r[5].columns(2, gap="small")
                        if b_ok.button("Xác nhận", key=f"sub04_confirm_{schedule['schedule_id']}", use_container_width=True):
                            _run_action(service.confirm_charging_schedule, state, schedule["schedule_id"])
                        if b_no.button("Hủy", key=f"sub04_cancel_prop_{schedule['schedule_id']}", use_container_width=True):
                            _run_action(service.cancel_charging_schedule, state, request["request_id"])
                    elif schedule and schedule.get("status") in service.ACTIVE:
                        r[4].markdown(f'<div class="s4-cell">{_pill("Thành công", "green")}</div>', unsafe_allow_html=True)
                        if r[5].button("Hủy lịch", key=f"sub04_cancel_act_{schedule['schedule_id']}"):
                            _run_action(service.cancel_charging_schedule, state, request["request_id"])
                    else:
                        r[4].markdown(f'<div class="s4-cell">{_pill("Chờ lập lịch", "blue")}</div>', unsafe_allow_html=True)
                        if preview and r[5].button("Tạo đề xuất", key=f"sub04_propose_{request['request_id']}"):
                            _run_action(service.propose_charging_schedule, state, request["request_id"])

                next_bad = rank < len(candidate_rows) and bool(candidate_rows[rank][3])
                if rank < len(candidate_rows) and not is_bad and not next_bad:
                    st.markdown('<hr class="s4-sep">', unsafe_allow_html=True)

            for item in incomplete:
                with st.container(key=f"s4_row_warn_sch_{item['request_id']}"):
                    r = _cols(widths, vertical_alignment="center")
                    r[0].markdown('<span class="s4-rank warn">--</span>', unsafe_allow_html=True)
                    r[1].markdown(f'<div class="s4-cell s4-strong">{escape(str(item.get("vehicle_id", item.get("request_id"))))}</div>', unsafe_allow_html=True)
                    r[2].markdown('<div class="s4-cell">-</div>', unsafe_allow_html=True)
                    r[3].markdown('<div class="s4-cell">-</div>', unsafe_allow_html=True)
                    r[4].markdown(f'<div class="s4-cell">{_pill("Chờ xác minh", "amber")}</div>', unsafe_allow_html=True)
                    r[5].markdown(f'<div class="s4-cell" style="color:#b45309;font-weight:600">{escape(str(item.get("reason", "-")))}</div>', unsafe_allow_html=True)

    active_schedules = [schedule for schedule in schedules if schedule.get("status") in service.ACTIVE]
    if active_schedules:
        with st.expander("Cập nhật tiến độ phiên sạc"):
            selected_id = st.selectbox("Phiên sạc", [s["schedule_id"] for s in active_schedules], key="sub04_progress_schedule")
            selected = next(s for s in active_schedules if s["schedule_id"] == selected_id)
            progress = st.number_input(
                "Tiến độ (%)", min_value=int(selected["progress"]), max_value=100,
                value=int(selected["progress"]), key=f"sub04_progress_{selected_id}",
            )
            if st.button("Cập nhật tiến độ", type="primary", key="sub04_update_progress"):
                _run_action(service.update_charging_progress, state, selected_id, progress)
                
def _run_action(function, state, *args):
    try:
        result = function(state, *args)
        if isinstance(result, tuple) and result and result[0] is False:
            st.error(result[1])
            return
        st.session_state["sub04_notice"] = "Đã cập nhật thành công."
        st.rerun()
    except ValueError as error:
        st.error(str(error))


def render(state, current_user, page="resources"):
    """Render one of the three Operator screens owned by SUB-04."""
    if current_user.get("role") != ROLE_OPERATOR:
        st.error("Chức năng này dành cho Operator.")
        return
    st.markdown(_S4_CSS, unsafe_allow_html=True)
    with st.container(key="sub04_root"):
        hubs = state.get("hubs", [])
        if not hubs:
            st.info("Chưa có Hub.")
            return
        if page not in PAGE_TITLES:
            page = "resources"
        hub_id, _ = _header(PAGE_TITLES[page], hubs)
        notice = st.session_state.pop("sub04_notice", None)
        if notice:
            st.success(notice)
        if page == "resources":
            _resources(state, hub_id)
        elif page == "priority":
            _priority(state, hub_id)
        else:
            _scheduling(state, hub_id)