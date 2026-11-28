"""SUB-05 UI: Network Operation & Dispatch, following the team's Figma design.

Screens: Tổng quan mạng lưới (+ chi tiết Hub), Điều chuyển xe, Sự cố.
This file only shows screens and collects input; all rules live in service.py.

``render(state, current_user)`` is the entry point called by app.py. It shows a
small navigation bar on top. If app.py already has a sidebar, it can instead call
``render(state, current_user, page="overview" | "hub" | "dispatch" | "incidents")``
and the internal navigation bar is hidden.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from modules.sub05 import service

PAGE_KEY = "sub05_page"
HUB_KEY = "sub05_hub"
NAV_KEY = "sub05_nav"
EXT_PAGE_KEY = "sub05_ext_page"
FLASH_KEY = "sub05_flash"
SHOW_FORM_KEY = "sub05_show_incident_form"
PREFILL_KEY = "sub05_prefill_resource"
NAV_REQUEST_KEY = "sub05_nav_request"

PAGES = {
    "overview": "Tổng quan mạng lưới",
    "dispatch": "Điều chuyển xe",
    "incidents": "Sự cố",
}

STATUS_TONE = {
    "AVAILABLE": "green",
    "IN_USE": "blue",
    "CHARGING": "amber",
    "UNAVAILABLE": "red",
    "RESERVED": "blue",
    "TRANSITING": "purple",
    "COMPLETED": "green",
    "CANCELLED": "gray",
}
SEVERITY_TEXT = {"HIGH": "NGHIÊM TRỌNG", "MEDIUM": "TRUNG BÌNH", "LOW": "NHẸ"}
SEVERITY_TONE = {"HIGH": "red", "MEDIUM": "amber", "LOW": "blue"}
POINT_TEXT = {
    "IN_USE": ("Đang sạc", "blue"),
    "RESERVED": ("Đã hẹn", "amber"),
    "AVAILABLE": ("Trống", "green"),
    "UNAVAILABLE": ("Hỏng", "red"),
}
ORDER_TEXT = {
    "TRANSITING": ("TRANSITING", "purple"),
    "COMPLETED": ("HOÀN THÀNH", "green"),
    "CANCELLED": ("ĐÃ HỦY", "gray"),
}
FLAG_TEXT = {"vehicles": "Xe", "parking": "Chỗ đỗ", "charging": "Cổng sạc"}

_CSS = """
<style>
/* Scoped strictly to SUB-05 root so other SUBs are never affected */
.st-key-sub05_root [data-testid="stVerticalBlock"]{
  gap:0.7rem !important
}
.st-key-sub05_root .s5-eyebrow{
  font-size:.8rem;color:#6b7280;margin:0 0 2px 0;line-height:1.3
}
.st-key-sub05_root [data-testid="stHeaderActionElements"]{display:none !important}
.st-key-sub05_root h1,
.st-key-sub05_root .s5-page-title{
  padding:0 !important;margin:0 !important;
  font-weight:700 !important;font-size:1.85rem !important;
  letter-spacing:-.02em !important;line-height:1.18 !important;color:#111827 !important
}
.st-key-sub05_root b,
.st-key-sub05_root strong{font-weight:600}

/* Prevent Streamlit markdown negative bottom-margin from pulling cards past borders */
.st-key-sub05_root [data-testid="stMarkdown"],
.st-key-sub05_root [data-testid="stMarkdownContainer"],
.st-key-sub05_root [data-testid="stMarkdownContainer"] > p:last-child{
  margin-bottom:0 !important
}

/* Outer panel cards (st.container border=True with key="s5_panel_*") */
.st-key-sub05_root [class*="st-key-s5_panel_"]{
  border-radius:18px !important;border-color:#e5e7eb !important;
  padding:18px 20px !important;background:#ffffff !important
}
.st-key-sub05_root .st-key-s5_panel_dispatch_table{
  border-radius:14px !important;padding:12px 16px !important
}

.st-key-sub05_root .s5-card{box-sizing:border-box;background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:16px 20px;color:#111827;margin:0}
.st-key-sub05_root .s5-card *{color:inherit}
.st-key-sub05_root .s5-h{font-size:.84rem;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:#111827;margin:0 0 8px 0}
.st-key-sub05_root .s5-sub{font-size:.8rem;color:#6b7280}
.st-key-sub05_root .s5-strong{font-weight:600;color:#111827}
.st-key-sub05_root .s5-dim{font-size:.8rem;color:#6b7280}
.st-key-sub05_root .s5-m-t{font-size:.74rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:#9ca3af}
.st-key-sub05_root .s5-m-n{font-size:2.2rem;font-weight:700;line-height:1.15;color:#111827;margin:4px 0}
.st-key-sub05_root .s5-m-s{font-size:.72rem;font-weight:500;letter-spacing:.03em;text-transform:uppercase;color:#9ca3af}
.st-key-sub05_root .s5-m-lime{background:#d9ec9f;border-color:#c5de7e}
.st-key-sub05_root .s5-m-lime .s5-m-t,.st-key-sub05_root .s5-m-lime .s5-m-s{color:#2f4411}
.st-key-sub05_root .s5-m-blue .s5-m-t{color:#2563eb}
.st-key-sub05_root .s5-m-red .s5-m-t{color:#e11d48}
.st-key-sub05_root .s5-m-green .s5-m-t{color:#6b8e23}

/* Incident KPI cards */
.st-key-sub05_root .s5-inc-card{box-sizing:border-box;background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px 20px;margin:0}
.st-key-sub05_root .s5-inc-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.st-key-sub05_root .s5-dot{width:8px;height:8px;border-radius:999px;display:inline-block}
.st-key-sub05_root .s5-inc-n{font-size:2.15rem;font-weight:700;line-height:1.1}

/* Light theme overrides for Streamlit input widgets inside SUB-05 */
.st-key-sub05_root [data-testid="stForm"]{
  border-radius:16px !important;border-color:#e5e7eb !important;
  background:#ffffff !important;padding:16px 20px !important
}
.st-key-sub05_root [data-baseweb="select"] > div{
  background:#ffffff !important;background-color:#ffffff !important;
  border:1px solid #e5e7eb !important;border-radius:10px !important;color:#111827 !important
}
.st-key-sub05_root [data-baseweb="select"] > div > div{
  background:transparent !important;background-color:transparent !important;border:none !important
}
.st-key-sub05_root [data-baseweb="select"] span,
.st-key-sub05_root [data-baseweb="select"] input{color:#111827 !important;font-weight:500 !important}
.st-key-sub05_root [data-baseweb="select"] svg{fill:#6b7280 !important;color:#6b7280 !important}

.st-key-sub05_root [data-testid="stNumberInputContainer"]{
  background:#ffffff !important;background-color:#ffffff !important;
  border:1px solid #e5e7eb !important;border-radius:10px !important;overflow:hidden
}
.st-key-sub05_root [data-testid="stNumberInputContainer"] input{
  background:#ffffff !important;color:#111827 !important;font-weight:500 !important
}
.st-key-sub05_root [data-testid="stNumberInputStepDown"],
.st-key-sub05_root [data-testid="stNumberInputStepUp"]{
  background:#f8fafc !important;background-color:#f8fafc !important;
  color:#374151 !important;border-left:1px solid #e5e7eb !important
}
.st-key-sub05_root [data-testid="stNumberInputStepDown"]:hover,
.st-key-sub05_root [data-testid="stNumberInputStepUp"]:hover{
  background:#f1f5f9 !important
}
.st-key-sub05_root [data-testid="stNumberInputStepDown"] svg,
.st-key-sub05_root [data-testid="stNumberInputStepUp"] svg{fill:#374151 !important}

.st-key-sub05_root [data-baseweb="checkbox"]:has(input:not(:checked)) > span:first-child{
  background:#ffffff !important;background-color:#ffffff !important;
  border:1.5px solid #cbd5e1 !important;border-radius:5px !important
}
.st-key-sub05_root [data-baseweb="checkbox"]:has(input:checked) > span:first-child{
  background:#789c28 !important;background-color:#789c28 !important;
  border-color:#789c28 !important;border-radius:5px !important
}
.st-key-sub05_root [data-testid="stTextArea"] textarea{
  background:#ffffff !important;color:#111827 !important;
  border:1px solid #e5e7eb !important;border-radius:10px !important
}

/* Pills */
.st-key-sub05_root .s5-pill{display:inline-block;padding:3px 12px;border-radius:999px;font-size:.75rem;font-weight:600;border:1px solid;white-space:nowrap}
.st-key-sub05_root .s5-red{color:#be123c;background:#ffe4e6;border-color:#fecdd3}
.st-key-sub05_root .s5-amber{color:#92400e;background:#fef3c7;border-color:#fde68a}
.st-key-sub05_root .s5-green{color:#166534;background:#dcfce7;border-color:#bbf7d0}
.st-key-sub05_root .s5-blue{color:#1d4ed8;background:#dbeafe;border-color:#bfdbfe}
.st-key-sub05_root .s5-purple{color:#6b21a8;background:#f3e8ff;border-color:#e9d5ff}
.st-key-sub05_root .s5-gray{color:#4b5563;background:#f3f4f6;border-color:#e5e7eb}

/* Primary & action buttons inside SUB-05 (including st.form_submit_button) */
.st-key-sub05_root button[kind="primary"],
.st-key-sub05_root button[data-testid="stBaseButton-primary"],
.st-key-sub05_root button[kind="primaryFormSubmit"],
.st-key-sub05_root button[data-testid="stBaseButton-primaryFormSubmit"]{
  background:#789c28 !important;background-color:#789c28 !important;
  border:1px solid #789c28 !important;color:#ffffff !important;
  border-radius:12px !important;font-weight:600 !important
}
.st-key-sub05_root button[kind="primary"] *,
.st-key-sub05_root button[data-testid="stBaseButton-primary"] *,
.st-key-sub05_root button[kind="primaryFormSubmit"] *,
.st-key-sub05_root button[data-testid="stBaseButton-primaryFormSubmit"] *{
  color:#ffffff !important;font-weight:600 !important
}
.st-key-sub05_root button[kind="primary"]:hover,
.st-key-sub05_root button[data-testid="stBaseButton-primary"]:hover,
.st-key-sub05_root button[kind="primaryFormSubmit"]:hover,
.st-key-sub05_root button[data-testid="stBaseButton-primaryFormSubmit"]:hover{
  background:#658520 !important;background-color:#658520 !important;
  border-color:#658520 !important
}
.st-key-sub05_root button[kind="primary"]:disabled,
.st-key-sub05_root button[data-testid="stBaseButton-primary"]:disabled,
.st-key-sub05_root button[kind="primaryFormSubmit"]:disabled,
.st-key-sub05_root button[data-testid="stBaseButton-primaryFormSubmit"]:disabled{
  background:#d1d5db !important;background-color:#d1d5db !important;
  border-color:#d1d5db !important;opacity:1 !important
}

/* Overview Hub rows */
.st-key-sub05_root [class*="st-key-s5_hubcard_"]{
  box-sizing:border-box;border-radius:16px;padding:12px 18px;margin:0;width:auto
}
.st-key-sub05_root [class*="st-key-s5_hubcard_normal_"]{
  background:#f8fafc;border:1px solid #f1f5f9
}
.st-key-sub05_root [class*="st-key-s5_hubcard_near_"]{
  background:#fff5f6;border:1px solid #fecdd3
}
.st-key-sub05_root [class*="st-key-s5_hubcard_stale_"]{
  background:#fffbeb;border:2px dashed #e6c34a
}
.st-key-sub05_root [class*="st-key-s5_hubcard_"] [data-testid="stHorizontalBlock"]{
  align-items:center !important;width:100% !important
}
.st-key-sub05_root [class*="st-key-s5_hubcard_"] [data-testid="stColumn"] > div,
.st-key-sub05_root [class*="st-key-s5_hubcard_"] [data-testid="stVerticalBlock"],
.st-key-sub05_root [class*="st-key-s5_hubcard_"] [data-testid="stElementContainer"],
.st-key-sub05_root [class*="st-key-s5_hubcard_"] [data-testid="stMarkdownContainer"]{
  width:100% !important;max-width:100% !important
}
.st-key-sub05_root .s5-idx{
  display:inline-flex;width:26px;height:26px;border-radius:8px;
  align-items:center;justify-content:center;background:#e5e7eb;
  font-size:.78rem;font-weight:700;color:#374151
}
.st-key-sub05_root [class*="st-key-s5_hubcard_near_"] .s5-idx{background:#e11d48;color:#fff}
.st-key-sub05_root [class*="st-key-s5_hubcard_stale_"] .s5-idx{background:#fef3c7;color:#92400e}

/* Hub name button aligned flush left right next to the index badge */
.st-key-sub05_root [class*="st-key-sub05_open_"],
.st-key-sub05_root [class*="st-key-sub05_open_"] [data-testid="stButton"]{
  display:flex !important;justify-content:flex-start !important;width:100% !important
}
.st-key-sub05_root [class*="st-key-sub05_open_"] button,
.st-key-sub05_root [class*="st-key-sub05_open_"] button[data-testid="stBaseButton-secondary"]{
  background:transparent !important;background-color:transparent !important;
  border:none !important;box-shadow:none !important;padding:2px 0 !important;
  display:flex !important;justify-content:flex-start !important;text-align:left !important;
  min-height:0 !important;width:100% !important
}
.st-key-sub05_root [class*="st-key-sub05_open_"] button > div{
  width:100% !important;justify-content:flex-start !important;text-align:left !important
}
.st-key-sub05_root [class*="st-key-sub05_open_"] button *,
.st-key-sub05_root [class*="st-key-sub05_open_"] button p{
  font-weight:600 !important;color:#111827 !important;font-size:.94rem !important;
  text-align:left !important;white-space:nowrap !important;
  overflow:hidden !important;text-overflow:ellipsis !important
}
.st-key-sub05_root [class*="st-key-sub05_open_"] button:hover *{
  color:#658520 !important;text-decoration:underline !important
}

/* Pure CSS grid for the 3 progress bars + badge inside each Hub row */
.st-key-sub05_root .s5-bars-grid{
  box-sizing:border-box;display:grid;grid-template-columns:1fr 1fr 1fr 124px;
  gap:22px;align-items:center;width:100%
}
.st-key-sub05_root .s5-bar-head{
  display:flex;justify-content:space-between;align-items:baseline;
  font-size:.78rem;color:#6b7280;margin-bottom:5px;gap:8px;white-space:nowrap
}
.st-key-sub05_root .s5-bar-head b{color:#111827;font-weight:600}
.st-key-sub05_root .s5-bar{height:8px;border-radius:6px;background:#e2e8f0;overflow:hidden;width:100%}
.st-key-sub05_root .s5-bar span{display:block;height:100%;border-radius:6px}
.st-key-sub05_root .s5-ok{background:#7ba03b}.st-key-sub05_root .s5-bad{background:#e11d48}.st-key-sub05_root .s5-old{background:#d4a017}
.st-key-sub05_root .s5-note{font-size:.72rem;font-weight:500;margin-top:4px;white-space:nowrap}
.st-key-sub05_root .s5-note-bad{color:#e11d48}.st-key-sub05_root .s5-note-old{color:#92400e}

/* Overview alert bars & empty states */
.st-key-sub05_root [class*="st-key-s5_alert_warn_"]{
  box-sizing:border-box;background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:8px 16px;margin:0
}
.st-key-sub05_root [class*="st-key-s5_alert_bad_"]{
  box-sizing:border-box;background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;padding:8px 16px;margin:0
}
.st-key-sub05_root [class*="st-key-s5_alert_"] [data-testid="stVerticalBlock"],
.st-key-sub05_root [class*="st-key-s5_alert_"] [data-testid="stElementContainer"],
.st-key-sub05_root [class*="st-key-s5_alert_"] [data-testid="stMarkdownContainer"]{
  width:100% !important
}
.st-key-sub05_root .s5-alert-txt{font-size:.9rem;color:#111827;line-height:1.4}
.st-key-sub05_root [class*="st-key-sub05_alert_warn_"] button,
.st-key-sub05_root [class*="st-key-sub05_alert_bad_"] button{
  background:transparent !important;background-color:transparent !important;
  border:none !important;box-shadow:none !important;padding:0 !important;
  min-height:0 !important;justify-content:flex-end !important
}
.st-key-sub05_root [class*="st-key-sub05_alert_warn_"] button *{
  color:#d97706 !important;font-weight:600 !important;font-size:.88rem !important
}
.st-key-sub05_root [class*="st-key-sub05_alert_warn_"] button:hover *{
  color:#b45309 !important;text-decoration:underline !important
}
.st-key-sub05_root [class*="st-key-sub05_alert_bad_"] button *{
  color:#e11d48 !important;font-weight:600 !important;font-size:.88rem !important
}
.st-key-sub05_root [class*="st-key-sub05_alert_bad_"] button:hover *{
  color:#be123c !important;text-decoration:underline !important
}
.st-key-sub05_root .s5-empty-alert,
.st-key-sub05_root .s5-empty-box{
  display:block !important;box-sizing:border-box !important;width:auto !important;
  background:#f8fafc !important;border:1px solid #e5e7eb !important;
  border-radius:12px !important;padding:12px 16px !important;margin:0 !important;
  font-size:.88rem !important;color:#6b7280 !important
}

/* Hub detail: unified 3-stat banner, vehicle rows, charging chips, incident card */
.st-key-sub05_root .s5-hub-stats{box-sizing:border-box;display:grid;grid-template-columns:repeat(3,1fr);background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:16px 0;margin:0}
.st-key-sub05_root .s5-hub-stat{text-align:center;padding:0 16px;border-right:1px solid #e5e7eb}
.st-key-sub05_root .s5-hub-stat:last-child{border-right:none}
.st-key-sub05_root .s5-stat-n{font-size:2.05rem;font-weight:700;line-height:1.1;color:#111827}
.st-key-sub05_root .s5-bad-text{color:#e11d48}
.st-key-sub05_root .s5-chips{
  box-sizing:border-box;width:100%;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(74px,1fr));gap:8px;padding-bottom:4px
}
.st-key-sub05_root .s5-chip{display:block;border:1px solid;border-radius:12px;padding:8px 6px;font-size:.74rem;text-align:center;line-height:1.35}
.st-key-sub05_root .s5-chip b{display:block;font-size:.82rem;font-weight:600;margin-top:2px}
.st-key-sub05_root .s5-box{box-sizing:border-box;border:1px solid #e5e7eb;border-radius:14px;padding:12px 14px;background:#f8fafc;font-size:.88rem;color:#111827;margin:0}
.st-key-sub05_root .st-key-s5_veh_head,
.st-key-sub05_root [class*="st-key-s5_veh_ok_"]{
  box-sizing:border-box;padding:0 10px;margin:0
}
.st-key-sub05_root [class*="st-key-s5_veh_bad_"]{
  box-sizing:border-box;background:#fff5f6;border-radius:12px;padding:6px 10px;margin:0
}
.st-key-sub05_root [class*="st-key-sub05_fix_"] button{
  background:#fff !important;border:1px solid #fecdd3 !important;border-radius:10px !important;
  padding:2px 10px !important;min-height:30px !important;height:30px !important
}
.st-key-sub05_root [class*="st-key-sub05_fix_"] button *{color:#be123c !important;font-size:.78rem !important;font-weight:600 !important}
.st-key-sub05_root [class*="st-key-sub05_fix_"] button:hover{background:#ffe4e6 !important}
.st-key-sub05_root [class*="st-key-s5_hub_inc_"]{
  box-sizing:border-box;background:#fff1f2;border:1px solid #fecdd3;border-radius:12px;padding:10px 14px;margin:0
}
.st-key-sub05_root [class*="st-key-sub05_hubinc_"] button{
  background:#e11d48 !important;border:1px solid #e11d48 !important;border-radius:10px !important;padding:5px 10px !important;min-height:0 !important
}
.st-key-sub05_root [class*="st-key-sub05_hubinc_"] button *{color:#fff !important;font-size:.8rem !important;font-weight:600 !important}
.st-key-sub05_root [class*="st-key-sub05_hubinc_"] button:hover{background:#be123c !important;border-color:#be123c !important}

/* Tables & Incident action buttons */
.st-key-sub05_root .s5-thead{font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;padding:4px 0}
.st-key-sub05_root .s5-thead-line{border:none;border-top:1px solid #e5e7eb;margin:-2px 0 2px 0}
.st-key-sub05_root .s5-cell{font-size:.88rem;padding:4px 0;color:#111827}
.st-key-sub05_root .s5-sep{border:none;border-top:1px solid #f1f5f9;margin:-2px 0}
.st-key-sub05_root [class*="st-key-sub05_act_"] button{
  background:#fff !important;border:1px solid #e5e7eb !important;border-radius:10px !important;padding:5px 10px !important;min-height:0 !important
}
.st-key-sub05_root [class*="st-key-sub05_act_"] button *{color:#111827 !important;font-size:.8rem !important;font-weight:600 !important}
.st-key-sub05_root [class*="st-key-sub05_act_"] button:hover{background:#f8fafc !important;border-color:#d1d5db !important}
.st-key-sub05_root [class*="st-key-sub05_res_"] button{
  background:#eef7e6 !important;border:1px solid #cde4b4 !important;border-radius:10px !important;padding:5px 10px !important;min-height:0 !important
}
.st-key-sub05_root [class*="st-key-sub05_res_"] button *{color:#3f6212 !important;font-size:.8rem !important;font-weight:600 !important}
.st-key-sub05_root [class*="st-key-sub05_res_"] button:hover{background:#dcfce7 !important}
.st-key-sub05_root [class*="st-key-sub05_done_"] button{
  background:#eef7e6 !important;border:1px solid #cde4b4 !important;border-radius:8px !important;padding:4px 8px !important;min-height:0 !important
}
.st-key-sub05_root [class*="st-key-sub05_done_"] button *{color:#3f6212 !important;font-size:.78rem !important;font-weight:600 !important}
.st-key-sub05_root [class*="st-key-sub05_cancel_"] button{
  background:#fff !important;border:1px solid #fecdd3 !important;border-radius:8px !important;padding:4px 8px !important;min-height:0 !important
}
.st-key-sub05_root [class*="st-key-sub05_cancel_"] button *{color:#be123c !important;font-size:.78rem !important;font-weight:600 !important}

/* Incident toolbar: move only the checkbox toward the report button.
   The three columns and the report button itself keep their original sizes. */
.st-key-sub05_root .st-key-s5_incident_show_resolved [data-testid="stCheckbox"]{
  width:100% !important;
  display:flex !important;
  justify-content:flex-end !important;
  position:relative !important;
  left:10px !important;
  z-index:1 !important;
}
.st-key-sub05_root .st-key-s5_incident_show_resolved [data-testid="stCheckbox"] label{
  width:max-content !important;
  margin-left:auto !important;
  margin-right:0 !important;
  justify-content:flex-end !important;
}

/* Responsive adjustments */
@media(max-width:1100px){
  .st-key-sub05_root .s5-bars-grid{grid-template-columns:1fr 1fr;gap:12px}
}
@media(max-width:760px){
  .st-key-sub05_root .s5-m-n{font-size:1.8rem}
  .st-key-sub05_root .s5-bars-grid{grid-template-columns:1fr;gap:10px}
  .st-key-sub05_root .s5-hub-stats{grid-template-columns:1fr}
  .st-key-sub05_root .s5-hub-stat{border-right:none;border-bottom:1px solid #e5e7eb;padding:10px 0}
  .st-key-sub05_root .s5-hub-stat:last-child{border-bottom:none}
}
</style>
"""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def esc(value) -> str:
    return escape(str(value))


def _pill(text: str, tone: str) -> str:
    return f'<span class="s5-pill s5-{tone}">{esc(text)}</span>'


def _fmt_dt(iso: str | None, sep: str = " - ") -> str:
    try:
        return datetime.fromisoformat(str(iso)).strftime(f"%d/%m/%Y{sep}%H:%M:%S")
    except (TypeError, ValueError):
        return "-"


def _type_label(vtype: str) -> str:
    return service.VEHICLE_TYPE_LABELS.get(vtype, vtype)


def _qty_text(quantities: dict[str, int]) -> str:
    return " · ".join(f"{n} {_type_label(t)}" for t, n in quantities.items() if n)


def _hub_label(hub: dict) -> str:
    return str(hub.get("name") or hub.get("address") or hub.get("hub_id", ""))


def _cols(spec, **kwargs):
    """st.columns with vertical alignment when this Streamlit version supports it."""
    try:
        return st.columns(spec, **kwargs)
    except TypeError:
        kwargs.pop("vertical_alignment", None)
        return st.columns(spec, **kwargs)


def _user_name(current_user: dict) -> str:
    for key in ("display_name", "name", "full_name", "username", "user_id"):
        if current_user.get(key):
            return str(current_user[key])
    return "Operator"


def _flash(kind: str, message: str) -> None:
    st.session_state[FLASH_KEY] = (kind, message)


def _show_flash() -> None:
    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        {"success": st.success, "error": st.error, "info": st.info, "warning": st.warning}.get(
            flash[0], st.info
        )(flash[1])


# ---------------------------------------------------------------------------
# Navigation (callbacks run before the rerun, so they may set widget state)
# ---------------------------------------------------------------------------

def _go(page: str, hub_id: str | None = None, **extra) -> None:
    st.session_state[PAGE_KEY] = page
    if hub_id is not None:
        st.session_state[HUB_KEY] = hub_id
    st.session_state[NAV_KEY] = PAGES.get(page, PAGES["overview"])
    for key, value in extra.items():
        st.session_state[key] = value


def _on_nav_change() -> None:
    label = st.session_state.get(NAV_KEY)
    st.session_state[PAGE_KEY] = next(
        (k for k, v in PAGES.items() if v == label), "overview"
    )


def _go_other(label: str) -> None:
    """Screens owned by other SUBs: ask app.py's navigation (if it listens)."""
    st.session_state[NAV_REQUEST_KEY] = label
    _flash("info", f"Mở mục «{label}» ở thanh điều hướng bên trái.")


def _follow(target: str, hub_id: str | None = None) -> None:
    if target.startswith("other:"):
        _go_other(target.split(":", 1)[1])
    else:
        _go(target, hub_id)


# ---------------------------------------------------------------------------
# Reusable HTML pieces
# ---------------------------------------------------------------------------

def _metric_card(title: str, value, sub: str, tone: str = "plain") -> str:
    return (
        f'<div class="s5-card s5-m-{tone}"><div class="s5-m-t">{esc(title)}</div>'
        f'<div class="s5-m-n">{esc(value)}</div><div class="s5-m-s">{esc(sub)}</div></div>'
    )


def _incident_metric_card(
    title: str, value, border: str, num_color: str, title_color: str, dot_color: str
) -> str:
    return (
        f'<div class="s5-inc-card" style="border-color:{border}">'
        f'<div class="s5-inc-head">'
        f'<span class="s5-m-t" style="color:{title_color}">{esc(title)}</span>'
        f'<span class="s5-dot" style="background:{dot_color}"></span>'
        f'</div>'
        f'<div class="s5-inc-n" style="color:{num_color}">{esc(value)}</div>'
        f'</div>'
    )


def _bar(label: str, m: dict, near_text: str, stale: bool) -> str:
    cls = "s5-old" if stale else ("s5-bad" if m["near"] else "s5-ok")
    note = ""
    if stale:
        note = '<div class="s5-note s5-note-old">Dữ liệu có thể cũ</div>'
    elif m["near"]:
        note = f'<div class="s5-note s5-note-bad">Near Capacity · {esc(near_text)}</div>'
    return (
        f'<div><div class="s5-bar-head"><span>{esc(label)}</span>'
        f'<b>{m["free"]}/{m["total"]} · {m["pct"]}%</b></div>'
        f'<div class="s5-bar"><span class="{cls}" style="width:{m["pct"]}%"></span></div>{note}</div>'
    )


# ---------------------------------------------------------------------------
# Page: Tổng quan mạng lưới
# ---------------------------------------------------------------------------

def _page_overview(data: dict, user: str) -> None:
    """Network overview. Hub names are clickable and open their detail page."""
    totals = data["totals"]

    title_col, right_col = _cols([5.2, 4.8], vertical_alignment="center")
    with title_col:
        st.markdown(
            f'<div class="s5-eyebrow">Xin chào, {esc(user)}</div>'
            '<div class="s5-page-title">Tổng quan mạng lưới</div>',
            unsafe_allow_html=True,
        )
    with right_col:
        pills_col, action_col = _cols([2.8, 1.6], vertical_alignment="center")
        badges = []
        if data["near_capacity_count"]:
            badges.append(_pill(f"{data['near_capacity_count']} Hub gần đầy", "red"))
        if data["stale_count"]:
            badges.append(_pill(f"{data['stale_count']} Hub dữ liệu trễ", "amber"))
        with pills_col:
            if badges:
                st.markdown(
                    '<div style="display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap">'
                    + "".join(badges)
                    + "</div>",
                    unsafe_allow_html=True,
                )
        with action_col:
            st.button(
                "Chạy What-if →",
                type="primary",
                key="sub05_whatif",
                on_click=_go_other,
                args=("What-if Simulation",),
            )

    cards = [
        ("Khả dụng", totals["free"], f"AVAILABLE · trên tổng {totals['total']} xe", "lime"),
        ("Đang dùng", totals["in_use"], "IN_USE", "plain"),
        ("Đã đặt", totals["held"], "RESERVED", "blue"),
        ("Sự cố", totals["unavailable"], "UNAVAILABLE", "red"),
        ("Điều chuyển", totals["transiting"], "TRANSITING", "green"),
    ]
    metric_columns = st.columns(5)
    for column, (label, value, foot, tone) in zip(metric_columns, cards):
        column.markdown(_metric_card(label, value, foot, tone), unsafe_allow_html=True)

    with st.container(border=True, key="s5_panel_hubs"):
        head_left, head_right = st.columns([3, 2])
        head_left.markdown('<div class="s5-h">Trạng thái từng Hub</div>', unsafe_allow_html=True)
        head_right.markdown(
            f'<div class="s5-sub" style="text-align:right">Near Capacity: ≤ '
            f'{round(service.NEAR_CAPACITY_FREE_RATIO * 100)}% khả dụng</div>',
            unsafe_allow_html=True,
        )

        for index, hub in enumerate(data["hubs"], start=1):
            state_class = "stale" if hub["stale"] else "near" if hub["near"] else "normal"
            safe_hub_id = "".join(ch if ch.isalnum() else "_" for ch in hub["hub_id"])
            with st.container(key=f"s5_hubcard_{state_class}_{safe_hub_id}"):
                left_col, right_col = st.columns([1.45, 3.85])
                with left_col:
                    c_idx, c_name = st.columns([0.12, 1.38], gap="small")
                    c_idx.markdown(f'<span class="s5-idx">{index}</span>', unsafe_allow_html=True)
                    c_name.button(
                        _hub_label(hub),
                        key=f"sub05_open_{hub['hub_id']}",
                        on_click=_go,
                        args=("hub", hub["hub_id"]),
                        use_container_width=True,
                    )
                badge_html = ""
                if hub["stale"]:
                    badge_html = _pill("Dữ liệu trễ", "amber")
                elif hub["near"]:
                    badge_html = _pill("Near Capacity", "red")
                right_col.markdown(
                    '<div class="s5-bars-grid">'
                    + _bar("Xe khả dụng", hub["vehicles"], "sắp hết xe", hub["stale"])
                    + _bar("Chỗ đỗ trống", hub["parking"], "sắp hết chỗ đỗ", hub["stale"])
                    + _bar("Cổng sạc rảnh", hub["charging"], "sắp hết cổng sạc", hub["stale"])
                    + f'<div style="text-align:right">{badge_html}</div>'
                    + "</div>",
                    unsafe_allow_html=True,
                )

    with st.container(border=True, key="s5_panel_alerts"):
        st.markdown('<div class="s5-h">Cảnh báo cần xử lý</div>', unsafe_allow_html=True)
        if not data["alerts"]:
            st.markdown(
                '<div class="s5-empty-alert">Hiện không có cảnh báo nào cần xử lý.</div>',
                unsafe_allow_html=True,
            )
        for index, alert in enumerate(data["alerts"]):
            tone = "bad" if alert["kind"] == "incident" else "warn"
            with st.container(key=f"s5_alert_{tone}_{index}"):
                text_col, action_col = _cols([7.8, 2.2], vertical_alignment="center")
                if alert["kind"] == "capacity":
                    body = f'<b>{esc(alert["hub_name"])}</b> {esc(alert["detail"])}'
                    label = "Điều chuyển xe →"
                else:
                    body = esc(alert["detail"])
                    label = "Xử lý sự cố →"
                text_col.markdown(f'<div class="s5-alert-txt">{body}</div>', unsafe_allow_html=True)
                action_col.button(
                    label,
                    key=f"sub05_alert_{tone}_{index}",
                    on_click=_go,
                    args=(alert["action"],),
                    kwargs={"sub05_tgt": alert["hub_id"]} if alert["kind"] == "capacity" else {},
                    use_container_width=True,
                )


# ---------------------------------------------------------------------------
# Page: chi tiết Hub
# ---------------------------------------------------------------------------

def _page_hub(hub_id: str) -> None:
    d = service.get_hub_detail(hub_id)
    if d is None:
        st.error("Không tìm thấy Hub.")
        st.button("← Quay lại", on_click=_go, args=("overview",), key="sub05_back_missing")
        return
    s = d["summary"]

    c_back, c_title, c_pill = _cols([0.45, 8.55, 5.5], vertical_alignment="center")
    c_back.button("‹", key="sub05_back", on_click=_go, args=("overview",))
    with c_title:
        st.markdown(
            f'<div class="s5-eyebrow">Tổng quan mạng lưới</div>'
            f'<div class="s5-page-title">{esc(_hub_label(s))}</div>',
            unsafe_allow_html=True,
        )
    with c_pill:
        if s["near"]:
            parts = " & ".join(f"{FLAG_TEXT[f]} ({s[f]['pct']}%)" for f in s["near_flags"])
            st.markdown(
                f'<div style="text-align:right">{_pill("Near Capacity: " + parts, "red")}</div>',
                unsafe_allow_html=True,
            )

    v, p, c = s["vehicles"], s["parking"], s["charging"]
    stats = [
        ("Xe khả dụng", v, f"/ {v['total']} xe ({v['pct']}%)"),
        ("Chỗ đỗ xe còn trống", p, f"/ {p['total']} chỗ ({d['parking_occupied_pct']}% đỗ)"),
        ("Cổng sạc sẵn sàng", c, f"/ {c['total']} cổng ({c['pct']}%)"),
    ]
    stat_html = '<div class="s5-hub-stats">'
    for title, m, tail in stats:
        num_cls = "s5-bad-text" if m["near"] else ""
        stat_html += (
            f'<div class="s5-hub-stat">'
            f'<div class="s5-m-t" style="margin-bottom:6px">{esc(title)}</div>'
            f'<div><span class="s5-stat-n {num_cls}">{m["free"]}</span> '
            f'<span class="s5-sub">{esc(tail)}</span></div></div>'
        )
    stat_html += "</div>"
    st.markdown(stat_html, unsafe_allow_html=True)

    left, right = st.columns([6, 4])
    with left:
        with st.container(border=True, key="s5_panel_vehicles"):
            st.markdown('<div class="s5-h">Danh sách phương tiện tại Hub</div>', unsafe_allow_html=True)
            widths = [1.5, 1.9, 1.7, 1.3, 1.8, 1.7]
            with st.container(key="s5_veh_head"):
                head = st.columns(widths)
                for col, text in zip(head, ["MÃ XE", "LOẠI XE", "VỊ TRÍ ĐỖ", "MỨC PIN (%)", "TRẠNG THÁI", ""]):
                    col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="s5-thead-line">', unsafe_allow_html=True)
            if not d["vehicles"]:
                st.caption("Hub chưa có xe.")
            vehicles = d["vehicles"]
            for idx, veh in enumerate(vehicles):
                bad = veh["status"] == "UNAVAILABLE"
                row_key = f"s5_veh_bad_{veh['vehicle_id']}" if bad else f"s5_veh_ok_{veh['vehicle_id']}"
                with st.container(key=row_key):
                    row = _cols(widths, vertical_alignment="center")
                    color = "#be123c" if bad else "#111827"
                    row[0].markdown(
                        f'<div class="s5-cell" style="font-weight:600;color:{color}">{esc(veh["vehicle_id"])}</div>',
                        unsafe_allow_html=True,
                    )
                    row[1].markdown(
                        f'<div class="s5-cell">{esc(_type_label(veh["vehicle_type"]))}</div>',
                        unsafe_allow_html=True,
                    )
                    row[2].markdown(
                        f'<div class="s5-cell">{esc(veh["location"])}</div>',
                        unsafe_allow_html=True,
                    )
                    row[3].markdown(
                        f'<div class="s5-cell" style="font-weight:600">{veh["battery_level"]}%</div>',
                        unsafe_allow_html=True,
                    )
                    row[4].markdown(
                        f'<div class="s5-cell">{_pill(veh["status"], STATUS_TONE.get(veh["status"], "gray"))}</div>',
                        unsafe_allow_html=True,
                    )
                    if bad:
                        row[5].button(
                            "Xử lý sự cố",
                            key=f"sub05_fix_{veh['vehicle_id']}",
                            on_click=_go,
                            args=("incidents",),
                            kwargs={PREFILL_KEY: veh["vehicle_id"], SHOW_FORM_KEY: True},
                            use_container_width=True,
                        )
                next_is_bad = idx + 1 < len(vehicles) and vehicles[idx + 1]["status"] == "UNAVAILABLE"
                if idx < len(vehicles) - 1 and not bad and not next_is_bad:
                    st.markdown('<hr class="s5-sep">', unsafe_allow_html=True)

    with right:
        with st.container(border=True, key="s5_panel_points"):
            st.markdown('<div class="s5-h">Trạng thái các cổng sạc</div>', unsafe_allow_html=True)
            if d["charging_points"]:
                chips = '<div class="s5-chips">'
                for pt in d["charging_points"]:
                    text, tone = POINT_TEXT.get(pt["status"], (pt["status"], "gray"))
                    chips += f'<span class="s5-chip s5-{tone}">{esc(pt["label"])}<b>{esc(text)}</b></span>'
                chips += "</div>"
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.markdown('<div class="s5-sub">Hub chưa có cổng sạc.</div>', unsafe_allow_html=True)

        with st.container(border=True, key="s5_panel_incoming"):
            st.markdown('<div class="s5-h">Lệnh điều chuyển đang đến</div>', unsafe_allow_html=True)
            names = {r["hub_id"]: _hub_label(r) for r in service.get_network_dashboard()["hubs"]}
            if not d["incoming_orders"]:
                st.caption("Không có lệnh điều chuyển nào đang đến Hub này.")
            for o in d["incoming_orders"]:
                st.markdown(
                    f'<div class="s5-box"><div style="text-align:right">{_pill("TRANSITING (Đang giao)", "purple")}</div>'
                    f'<div style="display:flex;justify-content:space-between;margin-top:6px">'
                    f'<span>Nguồn: <b>{esc(names.get(o["source_hub_id"], o["source_hub_id"]))}</b></span>'
                    f'<span>Đích: <b>{esc(names.get(o["target_hub_id"], o["target_hub_id"]))}</b></span></div>'
                    f'<div style="display:flex;justify-content:space-between;margin-top:6px" class="s5-dim">'
                    f'<span>Số lượng: <b>{esc(_qty_text(o["quantities"]))}</b></span>'
                    f'<span style="color:#15803d;font-weight:600">Dự kiến đến: '
                    f'{esc(_fmt_dt(o["eta"], " ")[-8:-3])} (còn {o["minutes_left"]}p)</span></div></div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "Xác nhận đã đến",
                    key=f"sub05_arrive_{o['order_id']}",
                    on_click=_complete_order,
                    args=(o["order_id"],),
                )

        with st.container(border=True, key="s5_panel_hub_inc"):
            st.markdown('<div class="s5-h">Sự cố cần can thiệp</div>', unsafe_allow_html=True)
            if not d["incidents"]:
                st.caption("Hub không có sự cố đang mở.")
            for inc in d["incidents"]:
                with st.container(key=f"s5_hub_inc_{inc['incident_id']}"):
                    c_t, c_b = _cols([3.2, 1.5], vertical_alignment="center")
                    c_t.markdown(
                        f'<div style="font-size:.88rem;color:#9f1239;font-weight:500">'
                        f'<b>{esc(inc["resource_label"])}</b>: {esc(inc["description"])}</div>',
                        unsafe_allow_html=True,
                    )
                    c_b.button(
                        "Xử lý",
                        key=f"sub05_hubinc_{inc['incident_id']}",
                        on_click=_go,
                        args=("incidents",),
                        use_container_width=True,
                    )

        st.button(
            "+ Tạo thêm lệnh điều chuyển xe đến Hub này",
            type="primary",
            key="sub05_new_dispatch_here",
            on_click=_go,
            args=("dispatch",),
            kwargs={"sub05_tgt": hub_id},
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Page: Điều chuyển xe
# ---------------------------------------------------------------------------

def _complete_order(order_id: str) -> None:
    result = service.complete_dispatch_order(order_id)
    _flash("success" if result["ok"] else "error", result["message"])


def _cancel_order(order_id: str) -> None:
    result = service.cancel_dispatch_order(order_id)
    _flash("success" if result["ok"] else "error", result["message"])


def _page_dispatch(data: dict, user: str) -> None:
    st.markdown('<div class="s5-page-title">Điều chuyển xe</div>', unsafe_allow_html=True)
    hubs = {h["hub_id"]: _hub_label(h) for h in data["hubs"]}
    ids = list(hubs)

    with st.container(border=True, key="s5_panel_dispatch_form"):
        st.markdown(
            '<div class="s5-h"><span style="color:#789c28;margin-right:6px">●</span> Tạo lệnh điều chuyển xe</div>',
            unsafe_allow_html=True,
        )
        if len(ids) > 1:
            st.session_state.setdefault("sub05_tgt", ids[1])

        c_src, c_arr, c_tgt, c_qty, c_btn = _cols([2.2, 0.25, 2.2, 2.8, 1.5], vertical_alignment="top")

        with c_src:
            src = st.selectbox(
                "HUB NGUỒN (TRẠM XUẤT XE) *", ids, format_func=hubs.get, key="sub05_src"
            )
        with c_arr:
            st.markdown(
                '<div style="text-align:center;color:#789c28;font-size:1.3rem;font-weight:600;padding-top:32px">→</div>',
                unsafe_allow_html=True,
            )
        with c_tgt:
            tgt = st.selectbox(
                "HUB ĐÍCH (TRẠM NHẬN XE) *", ids, format_func=hubs.get, key="sub05_tgt"
            )

        info = service.get_transferable_vehicles(src)
        cap = service.get_receiving_capacity(tgt)
        by_type = " · ".join(
            f"{n} {_type_label(t).lower()}" for t, n in info["by_type"].items()
        )
        c_src.caption(
            f"Khả dụng: **{info['max_transferable']} xe** ({by_type or 'không có xe'})"
            + (f" · {info['held_for_reservations']} xe đang giữ cho đặt trước" if info["held_for_reservations"] else "")
        )
        c_tgt.caption(
            f"Chỗ đỗ trống: **{cap['free_spaces']} chỗ**"
            + (f" · {cap['incoming']} xe đang trên đường tới" if cap["incoming"] else "")
        )

        quantities: dict[str, int] = {}
        qty_keys = []
        with c_qty:
            st.markdown(
                '<div class="s5-m-t" style="margin-bottom:4px">SỐ LƯỢNG ĐIỀU CHUYỂN THEO LOẠI</div>',
                unsafe_allow_html=True,
            )
            q_cols = st.columns(len(service.VEHICLE_TYPE_LABELS))
            for col, (vtype, label) in zip(q_cols, service.VEHICLE_TYPE_LABELS.items()):
                max_v = min(info["by_type"].get(vtype, 0), info["max_transferable"])
                key = f"sub05_qty_{src}_{vtype}"
                qty_keys.append(key)
                if st.session_state.get(key, 0) > max_v:
                    st.session_state[key] = max_v
                quantities[vtype] = col.number_input(
                    f"{label} (tối đa {max_v})",
                    min_value=0,
                    max_value=max_v,
                    step=1,
                    key=key,
                    disabled=max_v == 0,
                )

        total = sum(quantities.values())
        with c_btn:
            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            confirm = st.button(
                "Xác nhận điều phối",
                type="primary",
                key="sub05_confirm",
                disabled=total == 0 or src == tgt,
                use_container_width=True,
            )

        if src == tgt:
            st.warning("Hub nguồn và Hub đích phải khác nhau.")
        if confirm:
            result = service.create_dispatch_order(
                src, tgt, quantities=quantities, created_by=user
            )
            _flash("success" if result["ok"] else "error", result["message"])
            if result["ok"]:
                for key in qty_keys:
                    st.session_state.pop(key, None)
            st.rerun()

    orders = service.get_dispatch_orders()
    with st.container(border=True, key="s5_panel_dispatch_log"):
        head_l, head_r = _cols([4, 1.2], vertical_alignment="center")
        head_l.markdown(
            '<div class="s5-h" style="margin:0">Nhật ký & tiến độ các lệnh điều chuyển phương tiện</div>',
            unsafe_allow_html=True,
        )
        head_r.markdown(
            f'<div style="text-align:right">{_pill(f"Tổng cộng: {len(orders)} lệnh", "gray")}</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True, key="s5_panel_dispatch_table"):
            widths = [2.0, 2.2, 2.2, 2.6, 1.6, 1.8]
            head = st.columns(widths)
            for col, text in zip(
                head,
                ["THỜI ĐIỂM TẠO", "HUB NGUỒN (XUẤT XE)", "HUB ĐÍCH (NHẬN XE)", "SỐ LƯỢNG THEO LOẠI", "TRẠNG THÁI VẬN CHUYỂN", ""],
            ):
                col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
            st.markdown('<hr class="s5-thead-line">', unsafe_allow_html=True)
            if not orders:
                st.markdown(
                    '<div class="s5-dim" style="padding:4px 0">Chưa có lệnh điều chuyển nào.</div>',
                    unsafe_allow_html=True,
                )
            for idx, o in enumerate(orders):
                row = _cols(widths, vertical_alignment="center")
                row[0].markdown(f'<div class="s5-cell s5-dim">{esc(_fmt_dt(o["created_at"]))}</div>', unsafe_allow_html=True)
                row[1].markdown(f'<div class="s5-cell s5-strong">{esc(hubs.get(o["source_hub_id"], o["source_hub_id"]))}</div>', unsafe_allow_html=True)
                row[2].markdown(f'<div class="s5-cell s5-strong">{esc(hubs.get(o["target_hub_id"], o["target_hub_id"]))}</div>', unsafe_allow_html=True)
                row[3].markdown(
                    f'<div class="s5-cell"><b>{len(o["vehicle_ids"])} xe</b><div class="s5-dim">{esc(_qty_text(o["quantities"]))}</div></div>',
                    unsafe_allow_html=True,
                )
                text, tone = ORDER_TEXT.get(o["status"], (o["status"], "gray"))
                row[4].markdown(f'<div class="s5-cell">{_pill(text, tone)}</div>', unsafe_allow_html=True)
                if o["status"] == service.DISPATCH_TRANSITING:
                    b1, b2 = row[5].columns(2)
                    b1.button(
                        "Hoàn tất",
                        key=f"sub05_done_{o['order_id']}",
                        on_click=_complete_order,
                        args=(o["order_id"],),
                        use_container_width=True,
                    )
                    b2.button(
                        "Hủy",
                        key=f"sub05_cancel_{o['order_id']}",
                        on_click=_cancel_order,
                        args=(o["order_id"],),
                        use_container_width=True,
                    )
                if idx < len(orders) - 1:
                    st.markdown('<hr class="s5-sep">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page: Sự cố
# ---------------------------------------------------------------------------

RESOURCE_TYPE_LABELS = {
    "VEHICLE": "Phương tiện (Xe)",
    "CHARGING_POINT": "Trụ sạc",
    "PARKING_SPACE": "Chỗ đỗ xe",
    "HUB": "Toàn Hub",
}


def _resolve(incident_id: str) -> None:
    result = service.resolve_incident(incident_id)
    _flash("success" if result["ok"] else "error", result["message"])


def _clear_incident_form_state() -> None:
    for key in (
        PREFILL_KEY,
        "sub05_inc_prefilled_for",
        "sub05_inc_hub",
        "sub05_inc_rtype",
        "sub05_inc_res",
        "sub05_inc_sev",
        "sub05_inc_desc",
    ):
        st.session_state.pop(key, None)


def _toggle_form() -> None:
    opening = not st.session_state.get(SHOW_FORM_KEY, False)
    st.session_state[SHOW_FORM_KEY] = opening
    _clear_incident_form_state()


def _incident_form(user: str) -> None:
    resources = service.list_resources()
    if not resources:
        st.info("Chưa có tài nguyên nào để báo cáo sự cố.")
        return

    hubs = {h["hub_id"]: _hub_label(h) for h in service.get_network_dashboard()["hubs"]}
    hub_ids = [hid for hid in hubs if any(r["hub_id"] == hid for r in resources)]
    if not hub_ids:
        hub_ids = list(dict.fromkeys(r["hub_id"] for r in resources))

    prefill = st.session_state.get(PREFILL_KEY)
    if prefill and st.session_state.get("sub05_inc_prefilled_for") != prefill:
        match = next((r for r in resources if r["resource_id"] == prefill), None)
        if match:
            st.session_state["sub05_inc_hub"] = match["hub_id"]
            st.session_state["sub05_inc_rtype"] = match["resource_type"]
            st.session_state["sub05_inc_res"] = match["resource_id"]
            st.session_state["sub05_inc_prefilled_for"] = prefill

    if st.session_state.get("sub05_inc_hub") not in hub_ids:
        st.session_state["sub05_inc_hub"] = hub_ids[0]

    with st.container(border=True, key="s5_panel_incident_form"):
        st.markdown('<div class="s5-h">Báo cáo sự cố mới</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        selected_hub = c1.selectbox(
            "1. Chọn Hub *",
            hub_ids,
            format_func=lambda hid: hubs.get(hid, hid),
            key="sub05_inc_hub",
        )

        type_order = tuple(RESOURCE_TYPE_LABELS)
        available_types = [
            t
            for t in type_order
            if any(r["hub_id"] == selected_hub and r["resource_type"] == t for r in resources)
        ]
        if st.session_state.get("sub05_inc_rtype") not in available_types:
            st.session_state["sub05_inc_rtype"] = available_types[0]

        selected_type = c2.selectbox(
            "2. Chọn loại tài nguyên *",
            available_types,
            format_func=lambda t: RESOURCE_TYPE_LABELS.get(t, t),
            key="sub05_inc_rtype",
        )

        filtered = [
            r
            for r in resources
            if r["hub_id"] == selected_hub and r["resource_type"] == selected_type
        ]
        res_ids = [r["resource_id"] for r in filtered]
        res_labels = {
            r["resource_id"]: r["label"].split(" · ")[0]
            for r in filtered
        }
        if st.session_state.get("sub05_inc_res") not in res_ids:
            st.session_state["sub05_inc_res"] = res_ids[0]

        c3, c4 = st.columns(2)
        resource_id = c3.selectbox(
            "3. Chọn tài nguyên *",
            res_ids,
            format_func=lambda rid: res_labels.get(rid, rid),
            key="sub05_inc_res",
        )
        st.session_state.setdefault("sub05_inc_sev", service.SEVERITY_MEDIUM)
        severity = c4.selectbox(
            "Mức độ sự cố *",
            list(service.SEVERITIES),
            format_func=lambda s: SEVERITY_TEXT[s].capitalize(),
            key="sub05_inc_sev",
        )

        description = st.text_area("Mô tả sự cố *", key="sub05_inc_desc")
        b_submit, b_cancel, _ = st.columns([1.2, 1.0, 4.0])
        submitted = b_submit.button(
            "Gửi báo cáo",
            type="primary",
            key="sub05_inc_submit",
            use_container_width=True,
        )
        if b_cancel.button("Hủy", key="sub05_inc_cancel", use_container_width=True):
            st.session_state[SHOW_FORM_KEY] = False
            _clear_incident_form_state()
            st.rerun()

    if submitted:
        result = service.create_or_update_incident(
            resource_id, description, severity=severity, reported_by=user
        )
        _flash("success" if result["ok"] else "error", result["message"])
        if result["ok"]:
            st.session_state[SHOW_FORM_KEY] = False
            _clear_incident_form_state()
        st.rerun()


def _page_incidents(user: str) -> None:
    st.markdown('<div class="s5-page-title">Quản lý sự cố</div>', unsafe_allow_html=True)
    sm = service.get_incident_summary()
    cols = st.columns(4)
    cards = [
        ("Tổng sự cố", sm["total"], "#e5e7eb", "#111827", "#6b7280", "#111827"),
        ("Nghiêm trọng", sm["high"], "#fecdd3", "#e11d48", "#e11d48", "#e11d48"),
        ("Trung bình", sm["medium"], "#fde68a", "#d97706", "#d97706", "#f59e0b"),
        ("Đang chờ xử lý / Nhẹ", sm["low"], "#bfdbfe", "#2563eb", "#2563eb", "#3b82f6"),
    ]
    for col, (title, value, border, num_c, title_c, dot_c) in zip(cols, cards):
        col.markdown(
            _incident_metric_card(title, value, border, num_c, title_c, dot_c),
            unsafe_allow_html=True,
        )

    with st.container(border=True, key="s5_panel_incidents"):
        # Giữ nguyên 3 cột gốc để nút "Báo cáo sự cố mới" không đổi kích thước/vị trí.
        c_head, c_chk, c_btn = _cols(
            [2.9, 1.5, 1.4],
            vertical_alignment="center",
        )

        c_head.markdown(
            '<div class="s5-h" style="margin:0">Danh sách sự cố</div>',
            unsafe_allow_html=True,
        )

        # Đặt checkbox trong container có key để CSS đẩy riêng checkbox về bên phải.
        with c_chk:
            with st.container(key="s5_incident_show_resolved"):
                show_all = st.checkbox(
                    "Hiện cả sự cố đã giải quyết",
                    key="sub05_show_resolved",
                )

        # Giữ nguyên nút và use_container_width như bản ban đầu.
        c_btn.button(
            "+ Báo cáo sự cố mới",
            type="primary",
            key="sub05_new_incident",
            on_click=_toggle_form,
            use_container_width=True,
        )
        if st.session_state.get(SHOW_FORM_KEY):
            _incident_form(user)

        views = service.get_incident_views(include_resolved=show_all)
        if not views:
            st.markdown(
                '<div class="s5-empty-box">Không có sự cố nào để hiển thị.</div>',
                unsafe_allow_html=True,
            )
            return

        widths = [2.0, 2.8, 1.6, 1.8, 3.0]
        head = st.columns(widths)
        for col, text in zip(
            head,
            ["THỜI GIAN & TÀI NGUYÊN", "MỨC ĐỘ & MÔ TẢ", "TRẠNG THÁI TÀI NGUYÊN", "ẢNH HƯỞNG NGHIỆP VỤ", "HÀNH ĐỘNG XỬ LÝ"],
        ):
            col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
        st.markdown('<hr class="s5-thead-line">', unsafe_allow_html=True)
        for idx, inc in enumerate(views):
            row = _cols(widths, vertical_alignment="center")
            row[0].markdown(
                f'<div class="s5-dim">{esc(_fmt_dt(inc["created_at"], " • "))}</div>'
                f'<div class="s5-strong" style="font-size:.98rem">{esc(inc["resource_label"])}</div>'
                f'<div class="s5-dim">{esc(inc["location"])}</div>',
                unsafe_allow_html=True,
            )
            sev = inc["severity"]
            resolved = inc["status"] == service.INCIDENT_RESOLVED
            row[1].markdown(
                f'{_pill(SEVERITY_TEXT.get(sev, sev), SEVERITY_TONE.get(sev, "gray"))}'
                f'{" " + _pill("ĐÃ GIẢI QUYẾT", "green") if resolved else ""}'
                f'<div class="s5-strong" style="margin-top:4px">{esc(inc["description"])}</div>',
                unsafe_allow_html=True,
            )
            status = inc["resource_status"]
            row[2].markdown(
                _pill(status, STATUS_TONE.get(status, "gray")) if status else '<span class="s5-dim">-</span>',
                unsafe_allow_html=True,
            )
            impact_color = (
                "#e11d48"
                if "Ảnh hưởng" in inc["impact"]
                else "#d97706"
                if "Thiếu" in inc["impact"] or "Giảm" in inc["impact"]
                else "#374151"
            )
            row[3].markdown(
                f'<div style="font-weight:600;color:{impact_color}">{esc(inc["impact"])}</div>',
                unsafe_allow_html=True,
            )
            if not resolved:
                action = inc["action"]
                b1, b2 = row[4].columns([1.0, 1.35])
                b1.button(
                    action["label"],
                    key=f"sub05_act_{inc['incident_id']}",
                    on_click=_follow,
                    args=(action["target"],),
                    use_container_width=True,
                )
                b2.button(
                    "Đánh dấu đã giải quyết",
                    key=f"sub05_res_{inc['incident_id']}",
                    on_click=_resolve,
                    args=(inc["incident_id"],),
                    use_container_width=True,
                )
            if idx < len(views) - 1:
                st.markdown('<hr class="s5-sep">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Entry point called by app.py
# ---------------------------------------------------------------------------

def render(state: dict | None = None, current_user: dict | None = None, page: str | None = None) -> None:
    current_user = current_user or {}
    st.markdown(_CSS, unsafe_allow_html=True)
    service.refresh()

    with st.container(key="sub05_root"):
        st.session_state.setdefault(PAGE_KEY, "overview")
        if page is not None:  # app.py's own sidebar chooses the screen
            if st.session_state.get(EXT_PAGE_KEY) != page:
                st.session_state[EXT_PAGE_KEY] = page
                st.session_state[PAGE_KEY] = page
        else:
            current = st.session_state[PAGE_KEY]
            st.session_state.setdefault(NAV_KEY, PAGES.get(current, PAGES["overview"]))
            st.radio(
                "Điều hướng SUB-05",
                list(PAGES.values()),
                key=NAV_KEY,
                horizontal=True,
                on_change=_on_nav_change,
                label_visibility="collapsed",
            )

        _show_flash()

        user = _user_name(current_user)
        current = st.session_state[PAGE_KEY]
        if current == "hub":
            hub_id = st.session_state.get(HUB_KEY)
            if hub_id:
                _page_hub(hub_id)
                return
            current = "overview"

        data = service.get_network_dashboard()
        if current == "dispatch":
            _page_dispatch(data, user)
        elif current == "incidents":
            _page_incidents(user)
        else:
            _page_overview(data, user)
