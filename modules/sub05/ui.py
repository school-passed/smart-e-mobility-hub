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
.s5-card{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:14px 18px;color:#111827;margin-bottom:10px}
.s5-card *{color:inherit}
.s5-h{font-size:.9rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#111827;margin:2px 0 10px 0}
.s5-sub{font-size:.8rem;color:#6b7280}
.s5-strong{font-weight:700;color:#111827}
.s5-dim{font-size:.8rem;color:#6b7280}
.s5-m-t{font-size:.78rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#9ca3af}
.s5-m-n{font-size:2.3rem;font-weight:800;line-height:1.15;color:#111827}
.s5-m-s{font-size:.75rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#9ca3af}
.s5-m-lime{background:#d9ec9f;border-color:#c5de7e}
.s5-m-lime .s5-m-t,.s5-m-lime .s5-m-s{color:#1f2d0a}
.s5-m-blue .s5-m-t{color:#2563eb}
.s5-m-red .s5-m-t{color:#e11d48}
.s5-m-green .s5-m-t{color:#6b8e23}
.s5-pill{display:inline-block;padding:2px 12px;border-radius:999px;font-size:.76rem;font-weight:700;border:1px solid;white-space:nowrap}
.s5-red{color:#be123c;background:#ffe4e6;border-color:#fecdd3}
.s5-amber{color:#92400e;background:#fef3c7;border-color:#fde68a}
.s5-green{color:#166534;background:#dcfce7;border-color:#bbf7d0}
.s5-blue{color:#1d4ed8;background:#dbeafe;border-color:#bfdbfe}
.s5-purple{color:#6b21a8;background:#f3e8ff;border-color:#e9d5ff}
.s5-gray{color:#4b5563;background:#f3f4f6;border-color:#e5e7eb}
.s5-hubrow{border:1px solid #e5e7eb;background:#f8fafc;border-radius:16px;padding:14px 18px;color:#111827}
.s5-hubrow.s5-near{background:#fff1f2;border-color:#fecdd3}
.s5-hubrow.s5-stale{background:#fffbeb;border:2px dashed #e6c34a}
.s5-grid{display:grid;grid-template-columns:1.2fr 1fr 1fr 1fr 120px;gap:22px;align-items:center}
.s5-name{font-weight:700;display:flex;align-items:center;gap:10px}
.s5-idx{display:inline-flex;width:26px;height:26px;border-radius:8px;align-items:center;justify-content:center;background:#e5e7eb;font-size:.8rem;font-weight:800}
.s5-near .s5-idx{background:#e11d48;color:#fff}
.s5-stale .s5-idx{background:#fef3c7;color:#92400e}
.s5-bar-head{display:flex;justify-content:space-between;font-size:.78rem;color:#6b7280;margin-bottom:4px}
.s5-bar-head b{color:#111827}
.s5-bar{height:8px;border-radius:6px;background:#e2e8f0;overflow:hidden}
.s5-bar span{display:block;height:100%;border-radius:6px}
.s5-ok{background:#7ba03b}.s5-bad{background:#e11d48}.s5-old{background:#d4a017}
.s5-note{font-size:.72rem;font-weight:600;margin-top:3px}
.s5-note-bad{color:#e11d48}.s5-note-old{color:#92400e}
.s5-alert{border-radius:14px;padding:12px 16px;font-size:.9rem;color:#111827;border:1px solid}
.s5-alert-warn{background:#fff7ed;border-color:#fed7aa}
.s5-alert-bad{background:#fff1f2;border-color:#fecdd3}
.s5-thead{font-size:.72rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#6b7280;padding:6px 0;border-bottom:1px solid #e5e7eb}
.s5-cell{font-size:.88rem;padding:6px 0}
.s5-chip{display:inline-block;border:1px solid;border-radius:12px;padding:6px 14px;margin:0 6px 6px 0;font-size:.78rem;text-align:center;line-height:1.3}
.s5-chip b{display:block;font-size:.88rem}
.s5-box{border:1px solid #e5e7eb;border-radius:14px;padding:10px 14px;background:#f8fafc;font-size:.88rem;color:#111827;margin-bottom:8px}
.s5-stat-n{font-size:2.2rem;font-weight:800;line-height:1.1}
.s5-bad-text{color:#e11d48}
.st-key-sub05_whatif,.st-key-sub05_new_incident,.st-key-sub05_confirm{display:flex;justify-content:flex-end}
.st-key-sub05_whatif{margin-bottom:.6rem}
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


def _hub_row_html(index: int, h: dict) -> str:
    cls = "s5-hubrow" + (" s5-stale" if h["stale"] else " s5-near" if h["near"] else "")
    badge = ""
    if h["stale"]:
        badge = _pill("Dữ liệu trễ", "amber")
    elif h["near"]:
        badge = _pill("Near Capacity", "red")
    return (
        f'<div class="{cls}"><div class="s5-grid">'
        f'<div class="s5-name"><span class="s5-idx">{index}</span>{esc(h["name"])}</div>'
        f'{_bar("Xe khả dụng", h["vehicles"], "sắp hết xe", h["stale"])}'
        f'{_bar("Chỗ đỗ trống", h["parking"], "sắp hết chỗ đỗ", h["stale"])}'
        f'{_bar("Cổng sạc rảnh", h["charging"], "sắp hết cổng sạc", h["stale"])}'
        f'<div>{badge}</div></div></div>'
    )


# ---------------------------------------------------------------------------
# Page: Tổng quan mạng lưới
# ---------------------------------------------------------------------------

def _page_overview(data: dict, user: str) -> None:
    t = data["totals"]
    c_title, c_p1, c_p2, c_btn = _cols([5, 1.7, 1.9, 1.8], vertical_alignment="bottom")
    with c_title:
        st.caption(f"Xin chào, {user}")
        st.title("Tổng quan mạng lưới")
    with c_p1:
        if data["near_capacity_count"]:
            st.markdown(
                f'<div style="margin-bottom:.9rem">{_pill(str(data["near_capacity_count"]) + " Hub gần đầy", "red")}</div>',
                unsafe_allow_html=True,
            )
    with c_p2:
        if data["stale_count"]:
            st.markdown(
                f'<div style="margin-bottom:.9rem">{_pill(str(data["stale_count"]) + " Hub dữ liệu trễ", "amber")}</div>',
                unsafe_allow_html=True,
            )
    with c_btn:
        st.button(
            "Chạy What-if →",
            type="primary",
            key="sub05_whatif",
            on_click=_go_other,
            args=("What-if Simulation",),
        )

    cols = st.columns(5)
    cards = [
        ("Khả dụng", t["free"], f"AVAILABLE · trên tổng {t['total']} xe", "lime"),
        ("Đang dùng", t["in_use"], "IN_USE", "plain"),
        ("Đã đặt", t["held"], "RESERVED", "blue"),
        ("Sự cố", t["unavailable"], "UNAVAILABLE", "red"),
        ("Điều chuyển", t["transiting"], "TRANSITING", "green"),
    ]
    for col, (title, value, sub, tone) in zip(cols, cards):
        col.markdown(_metric_card(title, value, sub, tone), unsafe_allow_html=True)
    if t["charging"]:
        st.caption(f"Ngoài ra có {t['charging']} xe đang sạc (CHARGING), không nằm trong 5 nhóm trên.")

    head_l, head_r = st.columns([3, 2])
    head_l.markdown('<div class="s5-h">Trạng thái từng Hub</div>', unsafe_allow_html=True)
    head_r.markdown(
        f'<div class="s5-sub" style="text-align:right">Near Capacity: ≤ '
        f'{round(service.NEAR_CAPACITY_FREE_RATIO * 100)}% khả dụng</div>',
        unsafe_allow_html=True,
    )
    for i, h in enumerate(data["hubs"], start=1):
        c_row, c_btn = _cols([11, 1.6], vertical_alignment="center")
        c_row.markdown(_hub_row_html(i, h), unsafe_allow_html=True)
        with c_btn:
            st.button(
                "Chi tiết →",
                key=f"sub05_open_{h['hub_id']}",
                on_click=_go,
                args=("hub", h["hub_id"]),
            )

    st.markdown('<div class="s5-h" style="margin-top:14px">Cảnh báo cần xử lý</div>', unsafe_allow_html=True)
    if not data["alerts"]:
        st.success("Hiện không có cảnh báo nào cần xử lý.")
    for i, alert in enumerate(data["alerts"]):
        c_text, c_btn = st.columns([8, 2])
        tone = "bad" if alert["kind"] == "incident" else "warn"
        if alert["kind"] == "capacity":
            body = f'<b>{esc(alert["hub_name"])}</b> {esc(alert["detail"])}'
            label = "Điều chuyển xe →"
        else:
            body = esc(alert["detail"])
            label = "Xử lý sự cố →"
        c_text.markdown(f'<div class="s5-alert s5-alert-{tone}">{body}</div>', unsafe_allow_html=True)
        c_btn.button(
            label,
            key=f"sub05_alert_{i}",
            on_click=_go,
            args=(alert["action"],),
            kwargs={"sub05_tgt": alert["hub_id"]} if alert["kind"] == "capacity" else None,
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

    c_back, c_title, c_pill = _cols([1, 8, 6], vertical_alignment="center")
    c_back.button("←", key="sub05_back", on_click=_go, args=("overview",))
    with c_title:
        st.caption("Tổng quan mạng lưới")
        st.title(s["name"])
    with c_pill:
        if s["near"]:
            parts = " & ".join(f"{FLAG_TEXT[f]} ({s[f]['pct']}%)" for f in s["near_flags"])
            st.markdown(
                f'<div style="text-align:right">{_pill("Near Capacity: " + parts, "red")}</div>',
                unsafe_allow_html=True,
            )

    v, p, c = s["vehicles"], s["parking"], s["charging"]
    stat_cols = st.columns(3)
    stats = [
        ("Xe khả dụng", v, f"/ {v['total']} xe ({v['pct']}%)"),
        ("Chỗ đỗ xe còn trống", p, f"/ {p['total']} chỗ ({d['parking_occupied_pct']}% đỗ)"),
        ("Cổng sạc sẵn sàng", c, f"/ {c['total']} cổng ({c['pct']}%)"),
    ]
    for col, (title, m, tail) in zip(stat_cols, stats):
        num_cls = "s5-bad-text" if m["near"] else ""
        col.markdown(
            f'<div class="s5-card" style="text-align:center"><div class="s5-m-t">{esc(title)}</div>'
            f'<div><span class="s5-stat-n {num_cls}">{m["free"]}</span> '
            f'<span class="s5-sub">{esc(tail)}</span></div></div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([6, 4])
    with left:
        with st.container(border=True):
            st.markdown('<div class="s5-h">Danh sách phương tiện tại Hub</div>', unsafe_allow_html=True)
            widths = [1.6, 2, 1.8, 1.2, 2, 1.8]
            head = st.columns(widths)
            for col, text in zip(head, ["MÃ XE", "LOẠI XE", "VỊ TRÍ ĐỖ", "MỨC PIN", "TRẠNG THÁI", ""]):
                col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
            if not d["vehicles"]:
                st.caption("Hub chưa có xe.")
            for veh in d["vehicles"]:
                row = st.columns(widths)
                bad = veh["status"] == "UNAVAILABLE"
                color = "#be123c" if bad else "#111827"
                row[0].markdown(f'<div class="s5-cell" style="font-weight:700;color:{color}">{esc(veh["vehicle_id"])}</div>', unsafe_allow_html=True)
                row[1].markdown(f'<div class="s5-cell">{esc(_type_label(veh["vehicle_type"]))}</div>', unsafe_allow_html=True)
                row[2].markdown(f'<div class="s5-cell">{esc(veh["location"])}</div>', unsafe_allow_html=True)
                row[3].markdown(f'<div class="s5-cell" style="font-weight:700">{veh["battery_level"]}%</div>', unsafe_allow_html=True)
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
                    )

    with right:
        with st.container(border=True):
            st.markdown('<div class="s5-h">Trạng thái các cổng sạc</div>', unsafe_allow_html=True)
            chips = ""
            for pt in d["charging_points"]:
                text, tone = POINT_TEXT.get(pt["status"], (pt["status"], "gray"))
                chips += f'<span class="s5-chip s5-{tone}">{esc(pt["label"])}<b>{esc(text)}</b></span>'
            st.markdown(chips or '<div class="s5-sub">Hub chưa có cổng sạc.</div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div class="s5-h">Lệnh điều chuyển đang đến</div>', unsafe_allow_html=True)
            names = {r["hub_id"]: r["name"] for r in service.get_network_dashboard()["hubs"]}
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
                    f'<span style="color:#15803d;font-weight:700">Dự kiến đến: '
                    f'{esc(_fmt_dt(o["eta"], " ")[-8:-3])} (còn {o["minutes_left"]}p)</span></div></div>',
                    unsafe_allow_html=True,
                )
                st.button(
                    "Xác nhận đã đến",
                    key=f"sub05_arrive_{o['order_id']}",
                    on_click=_complete_order,
                    args=(o["order_id"],),
                )

        with st.container(border=True):
            st.markdown('<div class="s5-h">Sự cố cần can thiệp</div>', unsafe_allow_html=True)
            if not d["incidents"]:
                st.caption("Hub không có sự cố đang mở.")
            for inc in d["incidents"]:
                c_t, c_b = st.columns([3, 2])
                c_t.markdown(
                    f'<div class="s5-alert s5-alert-bad"><b>{esc(inc["resource_label"])}</b>: {esc(inc["description"])}</div>',
                    unsafe_allow_html=True,
                )
                c_b.button(
                    "Xử lý",
                    key=f"sub05_hubinc_{inc['incident_id']}",
                    on_click=_go,
                    args=("incidents",),
                )

        st.button(
            "+ Tạo thêm lệnh điều chuyển xe đến Hub này",
            type="primary",
            key="sub05_new_dispatch_here",
            on_click=_go,
            args=("dispatch",),
            kwargs={"sub05_tgt": hub_id},
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
    st.title("Điều chuyển xe")
    hubs = {h["hub_id"]: h["name"] for h in data["hubs"]}
    ids = list(hubs)

    with st.container(border=True):
        st.markdown('<div class="s5-h">● Tạo lệnh điều chuyển xe</div>', unsafe_allow_html=True)
        c_src, c_tgt = st.columns(2)
        if len(ids) > 1:
            st.session_state.setdefault("sub05_tgt", ids[1])
        src = c_src.selectbox(
            "HUB NGUỒN (TRẠM XUẤT XE) *", ids, format_func=hubs.get, key="sub05_src"
        )
        tgt = c_tgt.selectbox(
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

        st.markdown('<div class="s5-m-t">Số lượng điều chuyển theo loại</div>', unsafe_allow_html=True)
        qty_cols = _cols(len(service.VEHICLE_TYPE_LABELS) + 1, vertical_alignment="bottom")
        quantities: dict[str, int] = {}
        qty_keys = []
        for col, (vtype, label) in zip(qty_cols, service.VEHICLE_TYPE_LABELS.items()):
            max_v = min(info["by_type"].get(vtype, 0), info["max_transferable"])
            key = f"sub05_qty_{src}_{vtype}"
            qty_keys.append(key)
            if st.session_state.get(key, 0) > max_v:  # keep stored value inside the new range
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
        with qty_cols[-1]:
            confirm = st.button(
                "Xác nhận điều phối",
                type="primary",
                key="sub05_confirm",
                disabled=total == 0 or src == tgt,
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
    with st.container(border=True):
        head_l, head_r = st.columns([4, 1])
        head_l.markdown('<div class="s5-h">Nhật ký & tiến độ các lệnh điều chuyển phương tiện</div>', unsafe_allow_html=True)
        head_r.markdown(_pill(f"Tổng cộng: {len(orders)} lệnh", "gray"), unsafe_allow_html=True)
        widths = [2.2, 2.4, 2.4, 3, 1.8, 1.6]
        head = st.columns(widths)
        for col, text in zip(head, ["THỜI ĐIỂM TẠO", "HUB NGUỒN (XUẤT XE)", "HUB ĐÍCH (NHẬN XE)", "SỐ LƯỢNG THEO LOẠI", "TRẠNG THÁI", ""]):
            col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
        if not orders:
            st.caption("Chưa có lệnh điều chuyển nào.")
        for o in orders:
            row = st.columns(widths)
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
                row[5].button("Hoàn tất", key=f"sub05_done_{o['order_id']}", on_click=_complete_order, args=(o["order_id"],))
                row[5].button("Hủy lệnh", key=f"sub05_cancel_{o['order_id']}", on_click=_cancel_order, args=(o["order_id"],))


# ---------------------------------------------------------------------------
# Page: Sự cố
# ---------------------------------------------------------------------------

def _resolve(incident_id: str) -> None:
    result = service.resolve_incident(incident_id)
    _flash("success" if result["ok"] else "error", result["message"])


def _toggle_form() -> None:
    st.session_state[SHOW_FORM_KEY] = not st.session_state.get(SHOW_FORM_KEY, False)
    st.session_state.pop(PREFILL_KEY, None)


def _incident_form(user: str) -> None:
    resources = service.list_resources()
    ids = [r["resource_id"] for r in resources]
    labels = {r["resource_id"]: r["label"] for r in resources}
    prefill = st.session_state.get(PREFILL_KEY)
    index = ids.index(prefill) if prefill in ids else 0
    with st.form("sub05_incident_form", clear_on_submit=True):
        st.markdown('<div class="s5-h">Báo cáo sự cố mới</div>', unsafe_allow_html=True)
        resource_id = st.selectbox("Tài nguyên", ids, index=index, format_func=labels.get)
        severity = st.selectbox(
            "Mức độ",
            list(service.SEVERITIES),
            index=1,
            format_func=lambda s: SEVERITY_TEXT[s].capitalize(),
        )
        description = st.text_area("Mô tả sự cố")
        submitted = st.form_submit_button("Gửi báo cáo", type="primary")
    if submitted:
        result = service.create_or_update_incident(
            resource_id, description, severity=severity, reported_by=user
        )
        _flash("success" if result["ok"] else "error", result["message"])
        if result["ok"]:
            st.session_state[SHOW_FORM_KEY] = False
            st.session_state.pop(PREFILL_KEY, None)
        st.rerun()


def _page_incidents(user: str) -> None:
    st.title("Quản lý sự cố")
    sm = service.get_incident_summary()
    cols = st.columns(4)
    cards = [
        ("Tổng sự cố", sm["total"], "", "plain"),
        ("Nghiêm trọng", sm["high"], "", "red"),
        ("Trung bình", sm["medium"], "", "plain"),
        ("Đang chờ xử lý / Nhẹ", sm["low"], "", "blue"),
    ]
    for col, (title, value, sub, tone) in zip(cols, cards):
        col.markdown(_metric_card(title, value, sub or " ", tone), unsafe_allow_html=True)

    c_head, c_btn = _cols([4, 1.6], vertical_alignment="center")
    c_head.markdown('<div class="s5-h" style="margin:0">Danh sách sự cố</div>', unsafe_allow_html=True)
    c_btn.button("+ Báo cáo sự cố mới", type="primary", key="sub05_new_incident", on_click=_toggle_form)
    if st.session_state.get(SHOW_FORM_KEY):
        _incident_form(user)

    show_all = st.checkbox("Hiện cả sự cố đã giải quyết", key="sub05_show_resolved")
    views = service.get_incident_views(include_resolved=show_all)
    if not views:
        st.info("Không có sự cố nào để hiển thị.")
        return

    widths = [2.2, 3.4, 1.8, 2, 2.6]
    with st.container(border=True):
        head = st.columns(widths)
        for col, text in zip(head, ["THỜI GIAN & TÀI NGUYÊN", "MỨC ĐỘ & MÔ TẢ", "TRẠNG THÁI TÀI NGUYÊN", "ẢNH HƯỞNG NGHIỆP VỤ", "HÀNH ĐỘNG XỬ LÝ"]):
            col.markdown(f'<div class="s5-thead">{text}</div>', unsafe_allow_html=True)
        for inc in views:
            row = st.columns(widths)
            row[0].markdown(
                f'<div class="s5-dim">{esc(_fmt_dt(inc["created_at"], " · "))}</div>'
                f'<div class="s5-strong" style="font-size:1.05rem">{esc(inc["resource_label"])}</div>'
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
            impact_color = "#e11d48" if "Ảnh hưởng" in inc["impact"] else "#d97706" if "Thiếu" in inc["impact"] or "Giảm" in inc["impact"] else "#374151"
            row[3].markdown(
                f'<div style="font-weight:700;color:{impact_color}">{esc(inc["impact"])}</div>',
                unsafe_allow_html=True,
            )
            if not resolved:
                action = inc["action"]
                row[4].button(
                    action["label"],
                    key=f"sub05_act_{inc['incident_id']}",
                    on_click=_follow,
                    args=(action["target"],),
                )
                row[4].button(
                    "Đánh dấu đã giải quyết",
                    key=f"sub05_res_{inc['incident_id']}",
                    on_click=_resolve,
                    args=(inc["incident_id"],),
                )


# ---------------------------------------------------------------------------
# Entry point called by app.py
# ---------------------------------------------------------------------------

def render(state: dict | None = None, current_user: dict | None = None, page: str | None = None) -> None:
    current_user = current_user or {}
    st.markdown(_CSS, unsafe_allow_html=True)
    service.refresh()

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