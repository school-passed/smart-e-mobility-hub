"""Streamlit screens for UC-15, UC-16 and UC-17."""

from __future__ import annotations

import csv
from datetime import date
from html import escape
from io import StringIO
from typing import Any

import streamlit as st

from shared.enums import ROLE_OPERATOR
from modules.sub06.service import (
    SimulationInputError,
    get_available_scenarios,
    get_network_snapshot,
    run_simulation,
    validate_scenario_parameters,
)


_STATE_KEY = "sub06_prepared_simulation"
_RESULT_KEY = "sub06_latest_simulation"
_SCENARIO_KEY = "sub06_selected_scenario"
_TIME_WINDOWS = (
    "07:00–09:00 · Cao điểm sáng",
    "11:00–13:00 · Giữa ngày",
    "16:00–18:00 · Cao điểm chiều",
    "19:00–21:00 · Buổi tối",
)


def render(state: dict[str, Any], current_user: dict[str, Any]) -> None:
    """Render the What-if demo for the Operator role."""
    _inject_styles()
    hubs = [hub for hub in state.get("hubs", []) if isinstance(hub, dict) and hub.get("hub_id")]

    role = current_user.get("role") if isinstance(current_user, dict) else None
    if role and role != ROLE_OPERATOR:
        st.warning("What-if Simulation chỉ dành cho Operator.")
        return
    if not hubs:
        st.error("Chưa có dữ liệu Hub để tạo demo snapshot.")
        return

    scenario_list = get_available_scenarios()
    scenario_by_name = {scenario["name"]: scenario for scenario in scenario_list}
    _render_hero()
    _render_workspace_overview(state, hubs)

    scenario_names = list(scenario_by_name)
    if st.session_state.get(_SCENARIO_KEY) not in scenario_names:
        st.session_state[_SCENARIO_KEY] = next(
            (
                scenario["name"] for scenario in scenario_list
                if scenario["id"] == "hub_near_capacity"
            ),
            scenario_names[0],
        )

    st.markdown('<div class="section-kicker">MÔ PHỎNG · SUB-06</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-intro"><div><h2>Chọn kịch bản</h2>'
        '<p>Chọn một tình huống để xem hệ thống phản ứng như thế nào.</p></div>'
        '<span class="sample-label">3 kịch bản đang có</span></div>',
        unsafe_allow_html=True,
    )
    scenario_columns = st.columns(len(scenario_names))
    scenario_icons = ("↗", "⌖", "ϟ")
    for index, (column, name) in enumerate(zip(scenario_columns, scenario_names)):
        scenario_option = scenario_by_name[name]
        with column:
            active = st.session_state[_SCENARIO_KEY] == name
            st.markdown(
                f'<div class="scenario-card {"scenario-card-active" if active else ""}">'
                f'<span class="scenario-card-icon">{scenario_icons[index % len(scenario_icons)]}</span>'
                f'<span class="scenario-card-label">KỊCH BẢN 0{index + 1}</span>'
                f'<strong>{escape(name)}</strong><p>{escape(scenario_option["description"])}</p></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Đang chọn" if active else "Chọn tình huống",
                key=f"scenario_{scenario_option['id']}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                st.session_state[_SCENARIO_KEY] = name
                st.session_state.pop(_STATE_KEY, None)
                st.session_state.pop(_RESULT_KEY, None)
                st.rerun()

    with st.container(border=True):
        _section_heading("01", "Thiết lập kịch bản", "Chọn tình huống, Hub và khung giờ muốn xem trước.")

        scenario_name = st.session_state[_SCENARIO_KEY]
        scenario = scenario_by_name[scenario_name]
        st.markdown(
            f'<div class="scenario-note"><span class="scenario-note-dot"></span>'
            f'{escape(scenario["description"])}</div>',
            unsafe_allow_html=True,
        )

        hub_names = {hub["hub_id"]: hub.get("name", hub["hub_id"]) for hub in hubs}
        hub_options = hubs
        if scenario["id"] == "metro_demand_surge":
            metro_hubs = [
                hub for hub in hubs
                if "metro" in str(hub.get("name", "")).lower()
            ]
            if metro_hubs:
                hub_options = metro_hubs
        default_hub_term = "metro" if scenario["id"] == "metro_demand_surge" else "hcmut"
        default_hub_index = next(
            (
                index for index, hub in enumerate(hub_options)
                if default_hub_term in str(hub.get("name", "")).lower()
            ),
            0,
        )
        first, second, third = st.columns([1.3, 1, 1])
        with first:
            hub_id = st.selectbox(
                "Mobility Hub",
                [hub["hub_id"] for hub in hub_options],
                index=default_hub_index,
                format_func=lambda value: hub_names.get(value, value),
            )
        with second:
            simulation_date = st.date_input("Ngày mô phỏng", value=date.today())
        with third:
            time_window = st.selectbox("Khung giờ", _TIME_WINDOWS)

        parameters: dict[str, Any] = {"time_window": f"{simulation_date.isoformat()} · {time_window}"}
        if scenario["id"] == "metro_demand_surge":
            base, increase = st.columns(2)
            with base:
                parameters["base_demand"] = st.number_input(
                    "Nhu cầu nền trong khung giờ (lượt xe)",
                    min_value=1,
                    max_value=500,
                    value=6,
                    step=1,
                    help="Giá trị nền giả lập để demo mức tăng nhu cầu.",
                )
            with increase:
                parameters["increase_percent"] = st.slider("Mức tăng nhu cầu (%)", 1, 300, 50, 1)
        elif scenario["id"] == "hub_near_capacity":
            additional_demand, additional_parking = st.columns(2)
            with additional_demand:
                parameters["additional_vehicle_demand"] = st.number_input(
                    "Nhu cầu xe tăng thêm (lượt)", min_value=0, max_value=500, value=8, step=1
                )
            with additional_parking:
                parameters["additional_parking_occupancy"] = st.number_input(
                    "Chỗ đỗ bị chiếm thêm", min_value=0, max_value=500, value=12, step=1,
                    help="Tạo tình huống Hub gần đầy trong dữ liệu demo.",
                )
        else:
            extra_requests, failed_points = st.columns(2)
            points = [point for point in state.get("charging_points", []) if point.get("hub_id") == hub_id]
            available_points = sum(point.get("status") == "AVAILABLE" for point in points)
            with extra_requests:
                parameters["additional_requests"] = st.number_input(
                    "Yêu cầu sạc tăng thêm", min_value=0, max_value=500, value=3, step=1
                )
            with failed_points:
                parameters["failed_points"] = st.number_input(
                    "Trụ sạc khả dụng giả định bị lỗi",
                    min_value=0,
                    max_value=available_points,
                    value=0,
                    step=1,
                    help=f"Hiện có {available_points} trụ sạc khả dụng tại Hub đã chọn.",
                )

        capture_column, cancel_column = st.columns([4, 1])
        with capture_column:
            capture_requested = st.button(
                "Lưu snapshot cho lượt này", type="primary", use_container_width=True
            )
        with cancel_column:
            cancel_requested = st.button("Hủy thiết lập", use_container_width=True)

        if cancel_requested:
            st.session_state.pop(_STATE_KEY, None)
            st.session_state.pop(_RESULT_KEY, None)
            st.rerun()

        if capture_requested:
            try:
                snapshot = get_network_snapshot(state, hub_id)
                errors = validate_scenario_parameters(scenario["id"], parameters, snapshot)
                if errors:
                    st.session_state.pop(_STATE_KEY, None)
                    st.session_state.pop(_RESULT_KEY, None)
                    for error in errors:
                        st.error(error)
                else:
                    st.session_state[_STATE_KEY] = {
                        "scenario_id": scenario["id"],
                        "hub_id": hub_id,
                        "time_window": parameters["time_window"],
                        "parameters": dict(parameters),
                        "snapshot": snapshot,
                    }
                    st.session_state.pop(_RESULT_KEY, None)
                    st.rerun()
            except SimulationInputError as error:
                st.error(str(error))

    prepared = st.session_state.get(_STATE_KEY)
    matching_prepared = bool(
        prepared
        and prepared.get("scenario_id") == scenario["id"]
        and prepared.get("hub_id") == hub_id
        and prepared.get("time_window") == parameters["time_window"]
        and prepared.get("parameters") == parameters
    )

    if matching_prepared:
        snapshot = prepared["snapshot"]
        _render_snapshot(snapshot, hub_names)
        run_column, cancel_column = st.columns([4, 1])
        with run_column:
            run_requested = st.button("▶  Chạy thử tình huống", type="primary", use_container_width=True)
        with cancel_column:
            cancel_run = st.button("Hủy phiên", use_container_width=True)
        if cancel_run:
            st.session_state.pop(_STATE_KEY, None)
            st.session_state.pop(_RESULT_KEY, None)
            st.rerun()
        if run_requested:
            try:
                latest_snapshot = get_network_snapshot(state, prepared["hub_id"])
                validation_errors = validate_scenario_parameters(
                    prepared["scenario_id"], prepared["parameters"], latest_snapshot
                )
                if validation_errors:
                    st.session_state.pop(_RESULT_KEY, None)
                    for error in validation_errors:
                        st.error(error)
                    return
                prepared = {**prepared, "snapshot": latest_snapshot}
                st.session_state[_STATE_KEY] = prepared
                st.session_state[_RESULT_KEY] = run_simulation(
                    prepared["scenario_id"], prepared["parameters"], latest_snapshot
                )
                st.rerun()
            except SimulationInputError as error:
                st.error(str(error))
    elif prepared:
        st.info("Đầu vào đã thay đổi. Chụp snapshot và xác nhận lại trước khi chạy mô phỏng.")
    else:
        st.markdown('<div class="empty-state">Chọn một kịch bản để bắt đầu. Dữ liệu demo sẽ không làm thay đổi vận hành thật.</div>', unsafe_allow_html=True)

    result = st.session_state.get(_RESULT_KEY)
    if result and matching_prepared:
        _render_results(result, hub_names)


def _render_hero() -> None:
    st.markdown(
        """
        <section class="page-intro">
          <div class="intro-copy">
            <span class="intro-tag">SUB-06 · THỬ NGHIỆM MẠNG LƯỚI</span>
            <h1>Nếu hôm nay đông hơn thì sao?</h1>
            <p>Chọn một Hub, thử một thay đổi nhỏ rồi xem xe và khách sẽ đi đâu.</p>
            <span class="demo-note"><i>✳</i> Dữ liệu demo thôi nha — vận hành thật vẫn nguyên vẹn.</span>
          </div>
          <svg class="intro-doodle" viewBox="0 0 250 145" role="img" aria-label="Minh họa xe chạy giữa các Hub">
            <path d="M19 100 C62 60 86 120 124 78 S187 41 231 76" fill="none" stroke="#d7dfc8" stroke-width="7" stroke-linecap="round" stroke-dasharray="2 11"/>
            <path d="M19 100 C62 60 86 120 124 78 S187 41 231 76" fill="none" stroke="#fffdf8" stroke-width="3" stroke-linecap="round"/>
            <circle cx="25" cy="96" r="17" fill="#f7d7c7"/><path d="M18 98h14m-10-5 3-5h7l4 7" fill="none" stroke="#bf7158" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="21" cy="101" r="3" fill="#fffdf8"/><circle cx="31" cy="101" r="3" fill="#fffdf8"/>
            <circle cx="123" cy="78" r="18" fill="#dcebc9"/><path d="M117 75h12v10h-12zM115 75l8-6 8 6" fill="none" stroke="#729052" stroke-width="2" stroke-linejoin="round"/>
            <circle cx="225" cy="73" r="18" fill="#dce7f4"/><path d="M218 76c1-6 4-9 7-9s6 3 7 9m-7-9v12m-6-5h12" fill="none" stroke="#6882a4" stroke-width="2" stroke-linecap="round"/>
            <path d="M70 42c6-10 22-8 24 3-7 8-17 9-24-3Z" fill="#b7d9a6"/><path d="M172 113c5-9 18-7 20 3-6 7-14 8-20-3Z" fill="#b7d9a6"/>
            <path d="M90 35c6-8 13-9 20-6" fill="none" stroke="#eca88c" stroke-width="2" stroke-linecap="round"/><circle cx="111" cy="29" r="3" fill="#eca88c"/>
          </svg>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_workspace_overview(state: dict[str, Any], hubs: list[dict[str, Any]]) -> None:
    vehicles = state.get("vehicles", [])
    spaces = state.get("parking_spaces", [])
    points = state.get("charging_points", [])
    available_vehicles = sum(item.get("status") == "AVAILABLE" for item in vehicles)
    available_spaces = sum(item.get("status") == "AVAILABLE" for item in spaces)
    available_points = sum(item.get("status") == "AVAILABLE" for item in points)
    values = (
        ("Hub trong mạng", len(hubs), "điểm dừng trong bản demo", "⌖", "#edf3e5"),
        ("Xe sẵn sàng", available_vehicles, f"trên {len(vehicles)} xe", "↗", "#f8eadf"),
        ("Chỗ đỗ còn trống", available_spaces, f"trên {len(spaces)} vị trí", "▦", "#e8eff6"),
        ("Trụ sạc còn rảnh", available_points, f"trên {len(points)} trụ", "ϟ", "#f2ecdf"),
    )
    st.markdown(
        '<div class="overview-heading"><div><span>MẠNG LƯỚI TRONG BẢN DEMO</span>'
        '<h3>Tài nguyên mạng lưới</h3></div>'
        '<div class="network-status"><i></i> Dữ liệu mẫu</div></div>',
        unsafe_allow_html=True,
    )
    metrics = st.columns(4)
    for column, (label, value, foot, icon, tint) in zip(metrics, values):
        column.markdown(
            f'<div class="summary-card"><span class="summary-icon" style="background:{tint}">'
            f'{icon}</span><div><span class="summary-label">{label}</span>'
            f'<strong>{value}</strong></div><span class="summary-foot">{foot}</span></div>',
            unsafe_allow_html=True,
        )


def _render_snapshot(snapshot: dict[str, Any], hub_names: dict[str, str]) -> None:
    with st.container(border=True):
        _section_heading("02", "Snapshot mạng lưới", "Bản chụp dữ liệu dùng cho lần chạy này.")
        captured = snapshot.get("captured_at", "Không rõ")
        hub_id = snapshot.get("selected_hub_id")
        st.markdown(
            f'<div class="snapshot-meta"><span class="status-dot"></span> {escape(str(hub_names.get(hub_id, hub_id)))} <span class="meta-separator">·</span> Chụp lúc {escape(str(captured))}</div>',
            unsafe_allow_html=True,
        )
        summary = snapshot.get("summary", {})
        columns = st.columns(4)
        for column, label, value in zip(
            columns,
            ("Hub", "Xe", "Chỗ đỗ", "Trụ sạc"),
            ("hub_count", "vehicle_count", "parking_space_count", "charging_point_count"),
        ):
            column.metric(label, summary.get(value, 0))
        if snapshot.get("data_complete"):
            st.success("Snapshot sẵn sàng. Các thay đổi chỉ xuất hiện trong kết quả giả định.")
        else:
            st.error("Snapshot chưa đủ dữ liệu cần thiết để chạy.")


def _render_results(result: dict[str, Any], hub_names: dict[str, str]) -> None:
    with st.container(border=True):
        _section_heading("03", "Kết quả mô phỏng", "So sánh trạng thái hiện tại với tình huống giả định.")
        st.markdown(
            f'<div class="result-meta"><span class="result-pill">{escape(str(result["scenario_name"]))}</span><span>{escape(str(hub_names.get(result.get("hub_id"), result.get("hub_id"))))}</span><span>·</span><span>{escape(str(result.get("time_window")))}</span></div>',
            unsafe_allow_html=True,
        )

        _render_flow_map(result, hub_names)

        metric_columns = st.columns(min(3, max(1, len(result.get("metrics", [])))))
        for index, metric in enumerate(result.get("metrics", [])):
            column = metric_columns[index % len(metric_columns)]
            before = _format_metric(metric["before"], metric["unit"])
            after = _format_metric(metric["after"], metric["unit"])
            column.metric(metric["label"], after, delta=f"Trước: {before}", delta_color="off")

        left, right = st.columns([1, 1])
        with left, st.container(border=True):
            st.markdown("##### Tác động")
            for issue in result.get("issues", []):
                if issue["severity"] == "high":
                    st.error(f"**{issue['title']}**\n\n{issue['detail']}")
                elif issue["severity"] == "medium":
                    st.warning(f"**{issue['title']}**\n\n{issue['detail']}")
                else:
                    st.success(f"**{issue['title']}**\n\n{issue['detail']}")
        with right, st.container(border=True):
            st.markdown("##### Gợi ý cho Operator")
            for recommendation in result.get("recommendations", []):
                action = escape(str(recommendation["action"]))
                feasibility = escape(str(recommendation["feasibility"]))
                reason = escape(str(recommendation["reason"]))
                st.markdown(f'<div class="recommendation-card"><span class="recommendation-icon">↗</span><div><strong>{action}</strong><div class="recommendation-meta">{feasibility}</div><div class="recommendation-reason">{reason}</div></div></div>', unsafe_allow_html=True)

        st.caption("Kết quả chỉ hỗ trợ quyết định; hệ thống không điều chuyển xe, đổi lịch sạc hay sửa dữ liệu thật.")
        report = _build_csv_report(result, hub_names)
        filename = f"what-if-{result.get('scenario_id', 'simulation')}.csv"
        st.download_button(
            "Tải báo cáo kết quả",
            data=report,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )
        with st.expander("Giả định của lần mô phỏng"):
            for assumption in result.get("assumptions", []):
                st.markdown(f"- {assumption}")


def _render_flow_map(result: dict[str, Any], hub_names: dict[str, str]) -> None:
    snapshot = result.get("snapshot", {})
    records = snapshot.get("records", {})
    hubs = [hub for hub in records.get("hubs", []) if isinstance(hub, dict)]
    if len(hubs) < 2:
        st.info("Cần ít nhất hai Hub trong snapshot để minh họa luồng di chuyển.")
        return

    target_id = result.get("hub_id")
    target_index = next((i for i, hub in enumerate(hubs) if hub.get("hub_id") == target_id), 0)
    source_index = target_index - 1 if target_index > 0 else 1
    scenario_id = result.get("scenario_id")
    parameters = result.get("parameters", {})
    metrics_by_id = {metric.get("id"): metric for metric in result.get("metrics", [])}

    if scenario_id == "metro_demand_surge":
        metric = metrics_by_id.get("base_demand", {})
        count = max(0, int(metric.get("after", 0)) - int(metric.get("before", 0)))
        flow_label = f"{count} lượt khách phát sinh"
        flow_detail = "Nhu cầu mới đang dồn về Hub được chọn."
        marker_kind = "person"
    elif scenario_id == "hub_near_capacity":
        count = max(0, int(parameters.get("additional_vehicle_demand", 0)))
        flow_label = f"{count} lượt khách dự kiến"
        flow_detail = "Khách tìm xe tại Hub trong khung giờ này."
        marker_kind = "person"
    else:
        count = max(0, int(parameters.get("additional_requests", 0)))
        flow_label = f"{count} yêu cầu sạc mới"
        flow_detail = "Xe điện đang tìm điểm sạc còn chỗ."
        marker_kind = "bike"
    if count == 0:
        flow_label = "Không có nhu cầu tăng thêm"
        flow_detail = "Luồng trên tuyến đang được giữ nguyên."

    speeds = {"Nhẹ nhàng": 7.0, "Vừa phải": 4.5, "Nhanh": 2.8}
    controls, play_column, speed_column = st.columns([4, 1.2, 1.3])
    with controls:
        st.markdown(
            f'<div class="flow-heading"><span class="flow-kicker">NHÌN TRÊN BẢN ĐỒ</span>'
            f'<strong>{escape(flow_label)}</strong><span>{escape(flow_detail)}</span></div>',
            unsafe_allow_html=True,
        )
    with play_column:
        playing = st.toggle("Chạy chuyển động", value=True, key="sub06_flow_playing")
    with speed_column:
        speed = st.select_slider(
            "Nhịp di chuyển",
            options=list(speeds),
            value="Vừa phải",
            key="sub06_flow_speed",
        )

    coordinates = _hub_coordinates(len(hubs))
    positions = {str(hub.get("hub_id")): coordinates[i] for i, hub in enumerate(hubs)}
    source = hubs[source_index]
    target = hubs[target_index]
    source_id = str(source.get("hub_id"))
    target_key = str(target.get("hub_id"))
    source_x, source_y = positions[source_id]
    target_x, target_y = positions[target_key]
    route_direction = 1 if target_x > source_x else -1
    route = _curve_path(source_x + route_direction * 34, source_y, target_x - route_direction * 34, target_y)
    marker_drawing = _flow_marker_drawing(marker_kind)

    park_shapes = (
        '<defs><linearGradient id="campus-bg" x2="0" y2="1"><stop stop-color="#eff5e9"/><stop offset="1" stop-color="#fbf8f0"/></linearGradient>'
        '<linearGradient id="route-road" x2="0" y2="1"><stop stop-color="#d4d2c7"/><stop offset="1" stop-color="#c2c3b7"/></linearGradient>'
        '<filter id="island-shadow" x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#65715b" flood-opacity=".18"/></filter></defs>'
        '<path d="M0 0h850v285H0z" fill="url(#campus-bg)"/>'
        '<path d="M22 33c20-22 55-18 64 7-10 19-43 23-62 7-5-4-6-10-2-14Z" fill="#dce9d1"/>'
        '<path d="M268 211c18-19 48-17 58 2-10 20-38 25-57 10-5-3-5-8-1-12Z" fill="#dce9d1"/>'
        '<path d="M524 27c18-18 51-15 60 5-7 19-39 26-58 10-5-4-6-10-2-15Z" fill="#dce9d1"/>'
        '<path d="M740 211c15-16 44-15 53 3-6 17-34 22-51 10-5-3-6-9-2-13Z" fill="#dce9d1"/>'
        '<g fill="#9db883" opacity=".75"><circle cx="114" cy="207" r="5"/><circle cx="122" cy="204" r="7"/><circle cx="130" cy="208" r="5"/><circle cx="694" cy="41" r="5"/><circle cx="702" cy="38" r="7"/><circle cx="710" cy="42" r="5"/></g>'
    )
    road_layers = []
    for index in range(len(hubs) - 1):
        start_x, start_y = coordinates[index]
        end_x, end_y = coordinates[index + 1]
        road = _curve_path(start_x, start_y, end_x, end_y)
        active_edge = tuple(sorted((source_index, target_index)))
        is_active_edge = index == active_edge[0]
        road_layers.append(
            f'<path d="{road}" fill="none" stroke="#bcbcaf" stroke-width="23" stroke-linecap="round" opacity=".32"/>'
            f'<path d="{road}" fill="none" stroke="url(#route-road)" stroke-width="18" stroke-linecap="round"/>'
            f'<path d="{road}" fill="none" stroke="{"#fff9ee" if is_active_edge else "#f8f6ee"}" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 10" opacity=".9"/>'
        )

    moving_icons = []
    if playing and count:
        for index in range(min(10, max(3, count))):
            delay = round(index * speeds[speed] / min(10, max(3, count)), 1)
            moving_icons.append(
                f'<g>{marker_drawing}<animateMotion dur="{speeds[speed]}s" '
                f'begin="{delay}s" repeatCount="indefinite" path="{route}"/></g>'
            )
    ambient_icons = []
    if playing:
        active_edge = tuple(sorted((source_index, target_index)))
        for edge_index in range(len(hubs) - 1):
            if edge_index == active_edge[0]:
                continue
            start_x, start_y = coordinates[edge_index]
            end_x, end_y = coordinates[edge_index + 1]
            for marker_index in range(2):
                reverse = marker_index == 1
                ambient_route = _curve_path(end_x, end_y, start_x, start_y) if reverse else _curve_path(start_x, start_y, end_x, end_y)
                kind = "bike" if reverse else "person"
                duration = round(5.6 + edge_index * .45, 1)
                delay = round(edge_index * .7 + marker_index * 1.8, 1)
                ambient_icons.append(
                    f'<g class="ambient-marker">{_flow_marker_drawing(kind)}'
                    f'<animateMotion dur="{duration}s" begin="{delay}s" '
                    f'repeatCount="indefinite" path="{ambient_route}"/></g>'
                )
    elif count:
        middle_x = (source_x + target_x) // 2
        middle_y = (source_y + target_y) // 2 - 23
        moving_icons.append(f'<g transform="translate({middle_x} {middle_y})">{marker_drawing}</g>')

    hub_nodes = []
    hub_stat_cards = []
    demo_visitors_by_hub = {"HUB-01": 42, "HUB-02": 68, "HUB-03": 54, "HUB-04": 39, "HUB-05": 27}
    for index, hub in enumerate(hubs):
        hub_id = str(hub.get("hub_id"))
        x, y = positions[hub_id]
        selected = hub_id == target_key
        fill = "#cde7a8" if selected else "#f8e8d9"
        stroke = "#82a95a" if selected else "#d5ad94"
        label = escape(_short_hub_name(hub_names.get(hub.get("hub_id"), hub_id)))
        visitors = demo_visitors_by_hub.get(hub_id.upper(), (42, 68, 54, 39, 27)[index % 5])
        bustle = "đông" if visitors >= 60 else "vừa" if visitors >= 38 else "êm"
        activity_color = "#e98f70" if visitors >= 60 else "#91ad70" if visitors >= 38 else "#8ba2b2"
        selected_badge = (
            f'<rect x="{x - 33}" y="{y - 56}" width="66" height="19" rx="9.5" fill="#fffdf8"/>'
            f'<text x="{x}" y="{y - 43}" text-anchor="middle" class="map-badge">HUB ĐƯỢC CHỌN</text>'
            if selected
            else ""
        )
        map_icon = _hub_map_icon(hub, x, y)
        hcmut = "hcmut" in str(hub.get("name", "")).lower() or "bách khoa" in str(hub.get("name", "")).lower() or hub_id.upper() == "HUB-03"
        radius = 34 if hcmut else 28
        platform = (
            f'<g filter="url(#island-shadow)"><path d="M{x-radius-5} {y+4} Q{x} {y-radius-3} {x+radius+5} {y+4} L{x+radius+2} {y+17} Q{x} {y+29} {x-radius-2} {y+17}Z" fill="#b9c8a9" stroke="#9eaf91" stroke-width="1"/>'
            f'<ellipse cx="{x}" cy="{y + 4}" rx="{radius + 5}" ry="{max(12, radius // 2)}" fill="#e7eedc" stroke="#c5d2b9" stroke-width="1"/></g>'
            f'<ellipse cx="{x}" cy="{y + 26}" rx="{radius + 7}" ry="4" fill="#d1ccbc" opacity=".65"/>'
            f'<g fill="#88a974"><circle cx="{x - radius + 5}" cy="{y + 4}" r="2.2"/><circle cx="{x + radius - 5}" cy="{y + 5}" r="2.2"/></g>'
        )
        activity_x = x + radius + 7 if x < 700 else x - radius - 52
        activity_badge = (
            f'<g class="hub-activity"><rect x="{activity_x}" y="{y - 10}" width="45" height="18" rx="9" fill="#fffdf8" stroke="{activity_color}" stroke-width="1"/>'
            f'<circle cx="{activity_x + 8}" cy="{y - 1}" r="2.5" fill="{activity_color}"/><text x="{activity_x + 27}" y="{y + 2}" text-anchor="middle" class="activity-label">{visitors}/h</text></g>'
        )
        hub_nodes.append(
            f'{selected_badge}{platform}'
            f'<circle class="hub-halo" cx="{x}" cy="{y}" r="{radius + 4}" fill="none" stroke="{stroke}" stroke-width="1.5" opacity=".48"/>'
            f'<circle cx="{x}" cy="{y}" r="{radius}" fill="#fffdf8" stroke="{stroke}" stroke-width="2"/>'
            f'<circle cx="{x}" cy="{y}" r="{radius - 8}" fill="{fill}"/>'
            f'{map_icon}'
            f'{activity_badge}'
            f'<text x="{x}" y="{y + 51}" text-anchor="middle" class="map-name">{label}</text>'
            f'<text x="{x}" y="{y + 65}" text-anchor="middle" class="map-id">HUB 0{index + 1} · {bustle.upper()}</text>'
        )
        hub_stat_cards.append(_hub_stats_card(hub, records, hub_names, selected, visitors))

    svg = (
        '<div class="flow-map-wrap"><svg class="flow-map" viewBox="0 0 850 285" role="img" '
        f'aria-label="Luồng minh họa từ {escape(str(hub_names.get(source.get("hub_id"), source_id)))} đến '
        f'{escape(str(hub_names.get(target.get("hub_id"), target_key)))}">'
        f'<rect x="0" y="0" width="850" height="285" rx="20" fill="url(#campus-bg)"/>'
        f'{park_shapes}{"".join(road_layers)}'
        f'<path d="{route}" fill="none" stroke="{("#ef9b7f" if count else "#b5bbae")}" '
        'stroke-width="8" stroke-linecap="round" opacity=".72"/>'
        f'<path d="{route}" fill="none" stroke="#fff9ee" stroke-width="2" stroke-linecap="round" stroke-dasharray="2 8"/>'
        f'{"".join(hub_nodes)}{"".join(ambient_icons)}{"".join(moving_icons)}'
        '</svg></div>'
    )
    st.markdown(svg, unsafe_allow_html=True)
    st.markdown(
        f'<div class="hub-stats-grid">{"".join(hub_stat_cards)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="flow-map-footer"><span><i class="legend-person"></i> {escape(flow_label)}</span>'
        f'<span>{escape(str(hub_names.get(source.get("hub_id"), source_id)))} '
        f'<b>→</b> {escape(str(hub_names.get(target.get("hub_id"), target_key)))}</span>'
        '<small>Lượt ghé/giờ và luồng đều là dữ liệu demo; không phải GPS hay số liệu vận hành.</small></div>',
        unsafe_allow_html=True,
    )


def _hub_coordinates(count: int) -> list[tuple[int, int]]:
    if count <= 5:
        return [(90, 136), (255, 76), (425, 160), (595, 76), (760, 136)][:count]
    return [
        (int(55 + index * 740 / (count - 1)), 132 + (index % 2) * 55 - 28)
        for index in range(count)
    ]


def _curve_path(x1: int, y1: int, x2: int, y2: int) -> str:
    dx = x2 - x1
    bend = -28 if y1 < y2 else 28
    return (
        f"M{x1} {y1} C{x1 + int(dx * .34)} {y1 + bend}, "
        f"{x1 + int(dx * .66)} {y2 + bend}, {x2} {y2}"
    )


def _flow_marker_drawing(kind: str) -> str:
    if kind == "person":
        return (
            '<circle cy="-8" r="4" fill="#ef8c70"/>'
            '<path d="M0-3v9m-5-5h10m-5 5-4 7m4-7 4 7" fill="none" '
            'stroke="#ef8c70" stroke-width="2.7" stroke-linecap="round"/>'
        )
    return (
        '<circle cx="-8" cy="5" r="5" fill="none" stroke="#6f91b1" stroke-width="2"/>'
        '<circle cx="9" cy="5" r="5" fill="none" stroke="#6f91b1" stroke-width="2"/>'
        '<path d="M-8 5l6-9 7 9h-9l5-7h5m-3-3h4" fill="none" stroke="#6f91b1" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def _short_hub_name(name: Any, limit: int = 22) -> str:
    value = str(name or "Hub")
    return value if len(value) <= limit else f"{value[:limit - 1]}…"


def _hub_stats_card(
    hub: dict[str, Any],
    records: dict[str, Any],
    hub_names: dict[str, str],
    selected: bool,
    visitors: int,
) -> str:
    hub_id = hub.get("hub_id")
    vehicles = [item for item in records.get("vehicles", []) if item.get("hub_id") == hub_id]
    parking = [item for item in records.get("parking_spaces", []) if item.get("hub_id") == hub_id]
    chargers = [item for item in records.get("charging_points", []) if item.get("hub_id") == hub_id]
    available_vehicles = sum(item.get("status") == "AVAILABLE" for item in vehicles)
    available_parking = sum(item.get("status") == "AVAILABLE" for item in parking)
    available_chargers = sum(item.get("status") == "AVAILABLE" for item in chargers)
    battery = [
        item.get("battery_level")
        for item in vehicles
        if item.get("status") == "AVAILABLE"
        and isinstance(item.get("battery_level"), (int, float))
        and not isinstance(item.get("battery_level"), bool)
    ]
    battery_average = f"{round(sum(battery) / len(battery))}%" if battery else "—"
    title = escape(str(hub_names.get(hub_id, hub.get("name", hub_id))))
    is_hcmut = "hcmut" in str(hub.get("name", "")).lower() or "bách khoa" in str(hub.get("name", "")).lower() or str(hub_id).upper() == "HUB-03"
    card_class = "hub-stat-card" + (" hub-stat-card-hcmut" if is_hcmut else "") + (" hub-stat-card-selected" if selected else "")
    selected_tag = '<span class="hub-selected-tag">ĐANG MÔ PHỎNG</span>' if selected else ""
    crowd = "ĐÔNG VUI" if visitors >= 60 else "NHỘN NHỊP" if visitors >= 38 else "THƯ THẢ"
    return (
        f'<article class="{card_class}"><div class="hub-stat-heading">'
        f'<strong>{title}</strong>{selected_tag}</div>'
        f'<div class="hub-miniature">{_hub_model_svg(hub)}</div>'
        f'<div class="hub-visitor-line"><b>{visitors}</b><span>lượt ghé / giờ</span><em>{crowd}</em></div>'
        f'<div class="hub-stat-main"><b>{available_vehicles}</b>'
        f'<span>/{len(vehicles)} xe sẵn sàng</span></div>'
        '<div class="hub-stat-lines">'
        f'<span>🅿️ <b>{available_parking}/{len(parking)}</b> chỗ trống</span>'
        f'<span>⚡ <b>{available_chargers}/{len(chargers)}</b> trụ rảnh</span>'
        f'<span>🔋 <b>{battery_average}</b> pin TB</span>'
        '</div></article>'
    )


def _hub_map_icon(hub: dict[str, Any], x: int, y: int) -> str:
    hub_id = str(hub.get("hub_id", "")).upper()
    name = str(hub.get("name", "")).lower()
    if "hcmut" in name or "bách khoa" in name or hub_id == "HUB-03":
        return (
            f'<path d="M{x - 20} {y - 8}h40l-6-7h-28z" fill="#fffefa" stroke="#567ea2" stroke-width="1.6"/>'
            f'<rect x="{x - 17}" y="{y - 8}" width="34" height="20" rx="1.5" fill="#dcebf4" stroke="#567ea2" stroke-width="1.5"/>'
            f'<rect x="{x - 14}" y="{y - 14}" width="28" height="4.5" rx="1.5" fill="#537da0"/>'
            f'<text x="{x}" y="{y - 10.5}" text-anchor="middle" fill="#fff" font-size="3.5" font-weight="800">BK</text>'
            f'<path d="M{x - 11} {y - 7}v19m11-19v19m11-19v19" stroke="#6889a7" stroke-width="2.8"/>'
            f'<rect x="{x - 2.7}" y="{y + 3}" width="5.4" height="9" fill="#fffefa"/>'
        )
    if "dorm" in name or "ký túc" in name or hub_id == "HUB-02":
        return (
            f'<rect x="{x - 13}" y="{y - 12}" width="8" height="22" rx="1" fill="#d7e7f0" stroke="#748ca3" stroke-width="1"/>'
            f'<rect x="{x - 3}" y="{y - 7}" width="8" height="17" rx="1" fill="#f0dba9" stroke="#9d8d66" stroke-width="1"/>'
            f'<rect x="{x + 7}" y="{y - 10}" width="6" height="20" rx="1" fill="#d5e7ee" stroke="#748ca3" stroke-width="1"/>'
            f'<path d="M{x - 10} {y - 8}v2m4-2v2m-4 3v2m4-2v2m8-4v2m0 3v2m7-7v2m0 3v2" stroke="#789ab0" stroke-width="1.4"/>'
        )
    if "uit" in name or hub_id == "HUB-04":
        return (
            f'<path d="M{x - 13} {y - 10}h25v19h-25z" fill="#d9eee7" stroke="#598e7c" stroke-width="1.2"/>'
            f'<path d="M{x - 7} {y - 8}v15m7-15v15m7-15v15M{x - 11} {y - 1}h20" stroke="#79a99a" stroke-width="1.4"/>'
            f'<path d="M{x - 15} {y + 10}h29" stroke="#8b9b83" stroke-width="1.5"/>'
        )
    if "metro" in name or hub_id == "HUB-01":
        return (
            f'<path d="M{x - 13} {y - 3}h26v10h-26z" fill="#f5e4c9" stroke="#bd9160" stroke-width="1.2"/>'
            f'<path d="M{x - 15} {y - 4}h30M{x - 8} {y + 7}v3m16-3v3" stroke="#8e7358" stroke-width="1.6"/>'
            f'<circle cx="{x}" cy="{y - 10}" r="6" fill="#e9f0dc" stroke="#8da275" stroke-width="1"/>'
            f'<text x="{x}" y="{y - 8}" text-anchor="middle" fill="#647b50" font-size="6" font-weight="800">M</text>'
        )
    return (
        f'<path d="M{x - 13} {y - 4}h26v14h-26z" fill="#f3dfcd" stroke="#b98b6b" stroke-width="1.2"/>'
        f'<path d="M{x - 15} {y - 4}l4-5h22l4 5z" fill="#e8aa81" stroke="#b98b6b" stroke-width="1"/>'
        f'<path d="M{x - 7} {y - 3}v4m7-4v4m7-4v4" stroke="#fff8ee" stroke-width="2"/>'
    )


def _hub_model_svg(hub: dict[str, Any]) -> str:
    hub_id = str(hub.get("hub_id", "")).upper()
    name = str(hub.get("name", "")).lower()
    if "hcmut" in name or "bách khoa" in name or hub_id == "HUB-03":
        building = (
            '<path d="M39 41h122l-12-12H52z" fill="#fff" stroke="#718fa8" stroke-width="1.5"/>'
            '<rect x="47" y="41" width="108" height="27" rx="2" fill="#deedf4" stroke="#718fa8" stroke-width="1.5"/>'
            '<rect x="56" y="32" width="90" height="7" rx="2" fill="#537da0"/>'
            '<text x="101" y="37.5" text-anchor="middle" fill="#fff" font-size="5.5" font-weight="800">BK · TP.HCM</text>'
            '<path d="M62 42v26m18-26v26m18-26v26m18-26v26m18-26v26" stroke="#718fa8" stroke-width="3"/>'
            '<path d="M40 69h124" stroke="#657b65" stroke-width="2"/>'
            '<path d="M30 68c-2-12 3-20 9-20s11 8 9 20m114 0c-2-12 3-20 9-20s11 8 9 20" fill="#9abd87" stroke="#78966e" stroke-width="1"/>'
            '<path d="M38 75h133" stroke="#d3cbbc" stroke-width="3" stroke-linecap="round"/>'
        )
    elif "dorm" in name or "ký túc" in name or hub_id == "HUB-02":
        building = (
            '<path d="M49 65V22h35v43z" fill="#e4edf0" stroke="#82969a" stroke-width="1.5"/>'
            '<path d="M87 65V13h39v52z" fill="#f2e4c5" stroke="#a79670" stroke-width="1.5"/>'
            '<path d="M129 65V24h25v41z" fill="#dce9ed" stroke="#82969a" stroke-width="1.5"/>'
            '<path d="M49 54h35v5H49zm38-25h39v5H87zm0 18h39v5H87z" fill="#d09c64" opacity=".85"/>'
            '<path d="M56 29v5m12-5v5m11-5v5m-23 7v5m12-5v5m11-5v5m-23 7v5m12-5v5m11-5v5M96 20v6m13-6v6m12-6v6m-25 9v6m13-6v6m12-6v6m-25 9v6m13-6v6m12-6v6m-23-37v6m12-6v6m-12 9v6m12-6v6m-12 9v6m12-6v6m-12 9v6m12-6v6" stroke="#7f9ca5" stroke-width="2"/>'
            '<path d="M42 66h121" stroke="#697e69" stroke-width="2"/><circle cx="177" cy="62" r="13" fill="#a7c28d"/><path d="M29 68h160" stroke="#d3cbbc" stroke-width="3" stroke-linecap="round"/>'
        )
    elif "uit" in name or hub_id == "HUB-04":
        building = (
            '<path d="M52 65V24l47-12 49 12v41z" fill="#d8eee7" stroke="#688f83" stroke-width="1.5"/>'
            '<path d="M99 16v49m-39-29h78m-78 16h78" stroke="#7da89a" stroke-width="2"/>'
            '<path d="M70 25v10m17-14v14m25-14v14m17-10v10m-59 7v9m17-9v9m25-9v9m17-9v9m-59 7v8m17-8v8m25-8v8m17-8v8" stroke="#fffdf8" stroke-width="4"/>'
            '<rect x="89" y="51" width="20" height="14" fill="#a8cfc2"/><path d="M42 67h122" stroke="#718c70" stroke-width="2"/>'
            '<path d="M45 22h111" stroke="#fffdf8" stroke-width="3"/>'
        )
    elif "metro" in name or hub_id == "HUB-01":
        building = (
            '<path d="M46 49h107l-10-15H57z" fill="#fffdf8" stroke="#b4946e" stroke-width="1.5"/>'
            '<rect x="53" y="49" width="93" height="17" rx="3" fill="#f4e5cf" stroke="#b4946e" stroke-width="1.5"/>'
            '<rect x="64" y="53" width="71" height="9" rx="2" fill="#d9e9ed"/><path d="M83 53v9m20-9v9" stroke="#8ca6a6" stroke-width="1.5"/>'
            '<circle cx="99" cy="28" r="12" fill="#e8f0dc" stroke="#91a47a" stroke-width="1.5"/><text x="99" y="32" text-anchor="middle" fill="#61794c" font-size="12" font-weight="800">M</text>'
            '<path d="M39 68h123m-104 4h84" stroke="#d0c7b5" stroke-width="2" stroke-linecap="round"/>'
        )
    else:
        building = (
            '<path d="M62 66V34l37-19 38 19v32z" fill="#f4e3d1" stroke="#b18a6b" stroke-width="1.5"/>'
            '<path d="M58 34h83M68 35v8m15-8v8m15-8v8m15-8v8m15-8v8" stroke="#d08e69" stroke-width="5"/>'
            '<rect x="91" y="48" width="18" height="18" fill="#fff9ee" stroke="#b18a6b"/>'
            '<path d="M38 68h128" stroke="#718c70" stroke-width="2"/><circle cx="47" cy="56" r="13" fill="#a7c28d"/><circle cx="157" cy="57" r="12" fill="#b4cc98"/>'
        )
    return (
        '<svg viewBox="0 0 205 82" role="img" aria-label="Mô hình Hub" '
        'xmlns="http://www.w3.org/2000/svg">'
        '<path d="M18 72h170" stroke="#e6e1d5" stroke-width="3" stroke-linecap="round"/>'
        f'{building}</svg>'
    )


def _build_csv_report(result: dict[str, Any], hub_names: dict[str, str]) -> str:
    report = StringIO()
    writer = csv.writer(report)
    writer.writerow(("Kịch bản", result.get("scenario_name", "")))
    writer.writerow(("Hub", hub_names.get(result.get("hub_id"), result.get("hub_id", ""))))
    writer.writerow(("Khung giờ", result.get("time_window", "")))
    writer.writerow(())
    writer.writerow(("Chỉ số", "Trước mô phỏng", "Sau mô phỏng", "Đơn vị"))
    for metric in result.get("metrics", []):
        writer.writerow((metric.get("label", ""), metric.get("before", ""), metric.get("after", ""), metric.get("unit", "")))
    writer.writerow(())
    writer.writerow(("Khuyến nghị", "Khả thi", "Lý do"))
    for recommendation in result.get("recommendations", []):
        writer.writerow((recommendation.get("action", ""), recommendation.get("feasibility", ""), recommendation.get("reason", "")))
    return "\ufeff" + report.getvalue()


def _section_heading(number: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="section-heading"><span class="step-number">{number}</span><div><div class="section-title">{title}</div><div class="section-subtitle">{subtitle}</div></div></div>',
        unsafe_allow_html=True,
    )


def _format_metric(value: Any, unit: str) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    suffix = "%" if unit == "%" else f" {unit}" if unit else ""
    return f"{value}{suffix}"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root { --ink:#304052; --muted:#798391; }
        [data-testid="stAppViewContainer"] { background:#f6f5ef; }
        [data-testid="stSidebar"] { background:#fffdf8; border-right:1px solid #e9e7de; }
        [data-testid="stMain"] .block-container { max-width:1160px; padding:1.5rem 2rem 4rem; }
        h1,h2,h3,h4 { color:var(--ink); letter-spacing:-.025em; }
        div[data-testid="stButton"] button { min-height:2.55rem; border:1px solid #e5e5db; border-radius:12px; color:#59675b; background:#fffefa; font-size:.82rem; font-weight:700; transition:all .18s ease; }
        div[data-testid="stButton"] button:hover { border-color:#b4ce98; color:#3c563c; background:#f4f8ed; }
        div[data-testid="stButton"] button[kind="primary"] { border:0; color:#2f492e; background:#c5e69c; box-shadow:0 4px 11px rgba(115,151,82,.12); }
        div[data-testid="stButton"] button[kind="primary"]:hover { background:#b5dc86; transform:translateY(-1px); }
        .page-intro { display:flex; align-items:center; justify-content:space-between; gap:1.5rem; padding:1.65rem 2rem; margin:.25rem 0 1.55rem; border:1px solid #eae8dc; border-radius:21px; background:#fffdf8; box-shadow:0 8px 22px rgba(76,75,54,.045); }
        .intro-copy { max-width:650px; }
        .intro-tag { display:inline-block; color:#7c8b69; font-size:.63rem; font-weight:800; letter-spacing:.08em; }
        .intro-copy h1 { margin:.55rem 0 .3rem; color:#304052; font-size:2rem; font-weight:760; letter-spacing:-.055em; line-height:1.18; }
        .intro-copy p { margin:0; color:#798391; font-size:.9rem; line-height:1.55; }
        .demo-note { display:inline-flex; align-items:center; gap:.45rem; margin-top:.85rem; padding:.42rem .68rem; border-radius:999px; color:#657b52; background:#eef4e6; font-size:.69rem; font-weight:700; }
        .demo-note i { color:#7ba155; font-size:.88rem; font-style:normal; }
        .intro-doodle { flex:none; width:min(30%,250px); height:auto; overflow:visible; }
        .overview-heading,.section-intro { display:flex; justify-content:space-between; align-items:end; gap:1rem; margin:.45rem 0 .8rem; }
        .overview-heading>div:first-child>span,.section-kicker { color:#919687; font-size:.63rem; font-weight:800; letter-spacing:.08em; }
        .overview-heading h3,.section-intro h2 { margin:.22rem 0 0; color:#304052; font-size:1.12rem; font-weight:780; letter-spacing:-.035em; }
        .network-status { display:flex; align-items:center; gap:.45rem; color:#71805c; font-size:.65rem; font-weight:700; }
        .network-status i { width:.42rem; height:.42rem; border-radius:50%; background:#96bd70; }
        .summary-card { display:grid; min-height:6.3rem; grid-template-columns:auto 1fr; gap:.25rem .7rem; align-content:start; padding:1rem 1.05rem; border:1px solid #e9e8df; border-radius:18px; background:#fffefa; box-shadow:0 4px 15px rgba(76,75,54,.035); transition:transform .18s ease,box-shadow .18s ease; }
        .summary-card:hover { transform:translateY(-2px); box-shadow:0 9px 20px rgba(76,75,54,.07); }
        .summary-icon { display:grid; width:2.2rem; height:2.2rem; grid-row:span 2; place-items:center; border-radius:13px; color:#657c5a; font-weight:900; }
        .summary-label { color:#818a80; font-size:.71rem; }
        .summary-card strong { color:var(--ink); font-size:1.4rem; }
        .summary-foot { grid-column:2; color:#a0a397; font-size:.61rem; }
        .section-kicker { margin-top:2rem; }
        .section-intro { align-items:center; margin:.35rem 0 1rem; }
        .section-intro p { margin:.25rem 0 0; color:#838a84; font-size:.8rem; }
        .sample-label { padding:.4rem .65rem; border:1px solid #e8e7dd; border-radius:999px; color:#747e70; background:#fffdf8; font-size:.65rem; font-weight:700; }
        .scenario-card { height:165px; padding:1rem 1rem .6rem; border:1px solid #e9e8df; border-radius:18px; background:#fffefa; box-shadow:0 4px 15px rgba(76,75,54,.035); transition:all .18s ease; }
        .scenario-card-active { border-color:#a6c77d; box-shadow:0 0 0 3px rgba(166,199,125,.16),0 7px 18px rgba(76,75,54,.045); }
        .scenario-card-icon { display:grid; width:2rem; height:2rem; place-items:center; margin-bottom:.65rem; border-radius:11px; color:#657c5a; background:#edf3e5; font-weight:900; }
        .scenario-card-label { display:block; color:#999d91; font-size:.55rem; font-weight:800; letter-spacing:.08em; }
        .scenario-card strong { display:block; margin-top:.18rem; color:#394b43; font-size:.84rem; line-height:1.3; }
        .scenario-card p { margin:.35rem 0 0; color:#838a84; font-size:.68rem; line-height:1.42; }
        div[data-testid="stVerticalBlock"]:has(>.scenario-card) { gap:.3rem; }
        [data-testid="stVerticalBlockBorderWrapper"] { border:1px solid #e9e8df; border-radius:21px; background:#fffefa; box-shadow:0 7px 21px rgba(76,75,54,.04); }
        .section-heading { display:flex; align-items:center; gap:.8rem; margin-bottom:1rem; }
        .step-number { display:grid; flex:none; width:2.4rem; height:2.4rem; place-items:center; border-radius:14px; color:#698454; background:#edf3e5; font-size:.78rem; font-weight:850; }
        .section-title { color:#304052; font-size:1.04rem; font-weight:780; letter-spacing:-.02em; }
        .section-subtitle { margin-top:.12rem; color:#858d85; font-size:.8rem; }
        .scenario-note { display:flex; align-items:center; gap:.55rem; margin:.1rem 0 .9rem; padding:.46rem .72rem; border:1px solid #edede5; border-radius:12px; color:#667566; background:#f8f8f2; font-size:.82rem; }
        .scenario-note-dot,.status-dot { display:inline-block; width:.45rem; height:.45rem; border-radius:50%; background:#91b973; }
        .empty-state { margin:.25rem 0; padding:1rem; border:1px dashed #d9ddcf; border-radius:15px; color:#798478; background:#fffefa; text-align:center; font-size:.85rem; }
        .snapshot-meta,.result-meta { display:flex; align-items:center; gap:.5rem; margin-bottom:.65rem; color:#758078; font-size:.78rem; }
        .meta-separator { color:#c4c9bc; }
        .result-meta { margin:.1rem 0 1rem; }
        .result-pill { padding:.35rem .7rem; border-radius:999px; color:#687a59; background:#edf3e5; font-size:.68rem; font-weight:750; }
        [data-testid="stMetric"] { padding:.85rem 1rem; border:1px solid #eeede5; border-radius:15px; background:#f8f8f2; }
        [data-testid="stMetricLabel"] { color:#788279; font-size:.76rem; }
        [data-testid="stMetricValue"] { color:var(--ink); font-weight:780; }
        div[data-testid="stSelectbox"] div[data-baseweb="select"]>div,div[data-testid="stDateInput"] input,div[data-testid="stNumberInput"] input { min-height:2.7rem; border-radius:12px; background:#fffefa; }
        div[data-testid="stAlert"] { border-radius:14px; }
        .recommendation-card { display:flex; gap:.65rem; margin:.35rem 0; padding:.9rem; border:1px solid #edede5; border-radius:15px; background:#fffefa; }
        .recommendation-icon { display:grid; flex:none; width:1.8rem; height:1.8rem; place-items:center; border-radius:10px; color:#678351; background:#edf3e5; font-weight:850; }
        .recommendation-card strong { color:#394b43; font-size:.84rem; line-height:1.4; }
        .recommendation-meta { margin-top:.28rem; color:#688453; font-size:.7rem; font-weight:750; }
        .recommendation-reason { margin-top:.2rem; color:#838a84; font-size:.75rem; line-height:1.45; }
        .flow-heading { display:flex; flex-direction:column; align-items:flex-start; gap:.13rem; padding:.35rem 0 .7rem; }
        .flow-kicker { color:#9a9d91; font-size:.59rem; font-weight:800; letter-spacing:.09em; }
        .flow-heading strong { color:#304052; font-size:1.08rem; letter-spacing:-.025em; }
        .flow-heading>span:last-child { color:#838a84; font-size:.74rem; }
        .flow-map-wrap { overflow:hidden; border:1px solid #e2e5d8; border-radius:22px; background:#f7f7ef; box-shadow:0 11px 28px rgba(70,82,64,.09); }
        .flow-map { display:block; width:100%; height:auto; }
        .ambient-marker { opacity:.88; }
        .hub-halo { animation:hub-breathe 3s ease-in-out infinite; transform-box:fill-box; transform-origin:center; }
        .hub-activity { filter:drop-shadow(0 2px 2px rgba(75,80,62,.18)); }
        .activity-label { fill:#526052; font:800 7px sans-serif; }
        @keyframes hub-breathe { 0%,100% { opacity:.3; transform:scale(.96); } 50% { opacity:.75; transform:scale(1.06); } }
        .map-badge { fill:#72875d; font:700 6px sans-serif; letter-spacing:.05em; }
        .map-name { fill:#475446; font:700 10px sans-serif; }
        .map-id { fill:#9a9d91; font:700 7px sans-serif; letter-spacing:.08em; }
        .hub-stats-grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:.55rem; margin-top:.65rem; }
        .hub-stat-card { min-width:0; padding:.72rem; border:1px solid #e9e8df; border-radius:15px; background:#fffefa; }
        .hub-stat-card-selected { border-color:#a6c77d; background:#f8fbf3; box-shadow:0 0 0 2px rgba(166,199,125,.12); }
        .hub-stat-card-hcmut { position:relative; z-index:1; transform:translateY(-5px); background:linear-gradient(155deg,#eaf3f5,#fffefa 68%); border-color:#a9c4d2; box-shadow:0 8px 20px rgba(82,119,142,.12); }
        .hub-stat-card-hcmut .hub-miniature { height:82px; background:linear-gradient(180deg,#deedf1,#f8f6eb); }
        .hub-stat-heading { display:flex; min-height:2.2rem; align-items:flex-start; justify-content:space-between; gap:.25rem; }
        .hub-stat-heading strong { overflow:hidden; color:#394b43; font-size:.68rem; line-height:1.25; text-overflow:ellipsis; }
        .hub-selected-tag { flex:none; color:#718d59; font-size:.43rem; font-weight:850; letter-spacing:.04em; }
        .hub-miniature { height:68px; margin:.05rem -.2rem .25rem; overflow:hidden; border-radius:10px; background:linear-gradient(180deg,#f1f5ed,#faf8f0); }
        .hub-miniature svg { display:block; width:100%; height:100%; }
        .hub-stat-main { display:flex; align-items:baseline; gap:.22rem; margin:.3rem 0 .45rem; }
        .hub-stat-main b { color:#304052; font-size:1.2rem; }
        .hub-stat-main span { color:#858d85; font-size:.58rem; }
        .hub-visitor-line { display:flex; align-items:baseline; gap:.25rem; margin:.12rem 0 .34rem; padding-bottom:.4rem; border-bottom:1px solid #efeee7; }
        .hub-visitor-line b { color:#d27e62; font-size:1rem; }
        .hub-visitor-line span { color:#858d85; font-size:.53rem; }
        .hub-visitor-line em { margin-left:auto; color:#788d60; font-size:.46rem; font-style:normal; font-weight:850; letter-spacing:.035em; }
        .hub-stat-lines { display:grid; gap:.25rem; padding-top:.45rem; border-top:1px solid #efeee7; }
        .hub-stat-lines span { color:#7e887d; font-size:.57rem; white-space:nowrap; }
        .hub-stat-lines b { color:#4e6251; font-weight:750; }
        .flow-map-footer { display:flex; align-items:center; gap:.8rem; flex-wrap:wrap; padding:.55rem .1rem .15rem; color:#6d786c; font-size:.68rem; }
        .flow-map-footer span:first-child { display:flex; align-items:center; gap:.35rem; font-weight:750; }
        .flow-map-footer b { padding:0 .25rem; color:#dc8b6e; }
        .flow-map-footer small { margin-left:auto; color:#9b9e95; font-size:.61rem; }
        .legend-person { width:.48rem; height:.48rem; border-radius:50%; background:#ef8c70; box-shadow:0 0 0 3px #f8e4dc; }
        [data-testid="stToggle"] label { color:#677469; font-size:.7rem; }
        @media(max-width:900px) { [data-testid="stMain"] .block-container { padding:1rem 1.2rem 3rem; }.page-intro { padding:1.4rem 1.5rem; }.intro-doodle { width:28%; }.summary-card { padding:.8rem; }.hub-stats-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
        @media(max-width:650px) { .page-intro { padding:1.2rem; }.intro-copy h1 { font-size:1.55rem; }.intro-doodle { width:92px; opacity:.8; }.overview-heading,.section-intro { align-items:flex-start; flex-direction:column; }.network-status { margin-top:.5rem; }.scenario-card { height:auto; min-height:145px; }.flow-map-footer small { width:100%; margin-left:0; }.hub-stats-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.hub-stat-card:last-child:nth-child(odd) { grid-column:1 / -1; } }
        </style>
        """,
        unsafe_allow_html=True,
    )
