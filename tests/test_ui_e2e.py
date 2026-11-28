"""End-to-end Streamlit UI tests (AppTest) across unified Student Mobile UI + Operator Console UI."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import patch

from modules.sub01 import service as discovery
from modules.sub02 import service as trips
from modules.sub04 import service as charging
from modules.sub06 import service as simulation
from modules.sub06.ui import SCENARIOS
from shared.state import get_sandbox_store, get_state, reset_state

APP_PATH = str((Path(__file__).resolve().parents[1] / "app.py").resolve())


class StreamlitUIEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_state()

    def _login(self, app, username: str, password: str = "123") -> None:
        if any(b.key == "welcome_goto_signin" for b in app.button):
            app.button(key="welcome_goto_signin").click().run()
        app.text_input(key="si_user").set_value(username)
        app.text_input(key="si_pass").set_value(password)
        app.button(key="si_submit_btn").click().run()
        self.assertFalse(app.exception, [str(e.value) for e in app.exception])

    def test_student_mobile_tabs_and_operator_console_all_five_whatif_scenarios(self) -> None:
        from streamlit.testing.v1 import AppTest

        # 1. Student Mobile App (4 bottom tabs + subviews)
        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self.assertFalse(app.exception)
        self._login(app, "student")

        for tab_key in ("explore", "mine", "parking", "profile"):
            app.button(key=f"mob_nav_{tab_key}").click().run()
            self.assertFalse(app.exception, (tab_key, [str(e.value) for e in app.exception]))
            self.assertFalse(app.error, (tab_key, [e.value for e in app.error]))

        # Verify SUB-01 Home 4 filter pills actively filter and re-order Hubs
        app.button(key="mob_nav_explore").click().run()
        hub_cards_all = [b.key.rsplit("_", 1)[-1] for b in app.button if (b.key or "").startswith("s1_hub_")]
        self.assertEqual(hub_cards_all, ["HUB-01", "HUB-02", "HUB-03", "HUB-04", "HUB-05"])

        app.button(key="s1_pill_veh").click().run()
        hub_cards_veh = [b.key.rsplit("_", 1)[-1] for b in app.button if (b.key or "").startswith("s1_hub_")]
        self.assertEqual(hub_cards_veh, ["HUB-03", "HUB-01", "HUB-02", "HUB-05"])

        app.button(key="s1_pill_park").click().run()
        hub_cards_park = [b.key.rsplit("_", 1)[-1] for b in app.button if (b.key or "").startswith("s1_hub_")]
        self.assertEqual(hub_cards_park, ["HUB-04", "HUB-02", "HUB-01", "HUB-03"])

        app.button(key="s1_pill_chg").click().run()
        hub_cards_chg = [b.key.rsplit("_", 1)[-1] for b in app.button if (b.key or "").startswith("s1_hub_")]
        self.assertEqual(hub_cards_chg, ["HUB-02", "HUB-03", "HUB-01", "HUB-04"])

        app.button(key="s1_pill_all").click().run()
        hub_cards_reset = [b.key.rsplit("_", 1)[-1] for b in app.button if (b.key or "").startswith("s1_hub_")]
        self.assertEqual(hub_cards_reset, ["HUB-01", "HUB-02", "HUB-03", "HUB-04", "HUB-05"])

        app.button(key="mob_nav_profile").click().run()
        app.button(key="prof_signout").click().run()
        self.assertFalse(app.exception)

        # 2. Operator Desktop Console (7 sidebar pages + Hub detail + 5 What-if scenarios)
        self._login(app, "operator")
        for page_key in ("network", "dispatch", "resources", "priority", "schedule", "incidents", "simulation"):
            app.button(key=f"operator_nav_button_{page_key}").click().run()
            self.assertFalse(app.exception, (page_key, [str(e.value) for e in app.exception]))
            self.assertFalse(app.error, (page_key, [e.value for e in app.error]))

        # Open Hub detail in SUB-05 then return via back button
        app.button(key="operator_nav_button_network").click().run()
        app.button(key="sub05_open_HUB-01").click().run()
        self.assertFalse(app.exception)
        app.button(key="sub05_back").click().run()
        self.assertFalse(app.exception)

        # Open What-if from the dashboard and run all five scenarios.
        app.button(key="sub05_whatif").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["operator_nav"], "simulation")
        for idx, scenario_name in enumerate(SCENARIOS):
            opt_btn = next(b for b in app.button if (b.key or "").endswith(f"_{idx}") and "s6_opt_" in (b.key or ""))
            opt_btn.click().run()
            self.assertFalse(app.exception, (scenario_name, [str(e.value) for e in app.exception]))
            app.button(key="sub06_run_simulation").click().run()
            self.assertFalse(app.exception, (scenario_name, [str(e.value) for e in app.exception]))
            self.assertFalse(app.error, (scenario_name, [e.value for e in app.error]))
            if "sub06_operator_job" in app.session_state:
                _, future, _ = app.session_state["sub06_operator_job"]
                future.result(timeout=10)
                app.run()
            self.assertEqual(app.session_state["sub06_operator_result"]["ui_scenario_name"], scenario_name)
            self.assertTrue(
                any("Kết quả mô phỏng" in m.value for m in app.markdown),
                f"Missing result heading for {scenario_name}",
            )
            app.button(key="sub06_edit_parameters").click().run()
            self.assertFalse(app.exception)

        app.button(key="operator_sign_out").click().run()
        self.assertFalse(app.exception)

    def test_interactive_student_pickup_swap_low_battery_to_operator_schedule(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self._login(app, "student")

        # SUB-01: Open HUB-01 detail -> book shared bicycle -> go directly to pickup
        app.button(key="s1_hub_ok_HUB-01").click().run()
        self.assertFalse(app.exception)
        app.button(key="s1_det_book_veh").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(get_state()["reservations"]), 1)

        app.button(key="s1_succ_goto_pickup").click().run()
        self.assertFalse(app.exception)

        # SUB-02: Report defective vehicle at pickup (UC-04 A1) -> swap to another vehicle
        app.button(key="s2_pu_fault_nav").click().run()
        self.assertFalse(app.exception)
        app.button(key="s2_pi_submit").click().run()
        self.assertFalse(app.exception)
        self.assertGreaterEqual(len(get_state()["incidents"]), 1)
        self.assertEqual(get_state()["reservations"][0]["status"], "PENDING")

        # Confirm pickup on replacement vehicle
        app.button(key="s2_pu_confirm").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(get_state()["trips"]), 1)

        # Return with low battery (12% < 20%) -> triggers shared charging request in SUB-04
        app.button(key="s2_goto_return").click().run()
        self.assertFalse(app.exception)
        app.slider(key="s2_ret_battery").set_value(12).run()
        app.button(key="s2_ret_confirm").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(get_state()["shared_charging_requests"]), 1)

        # Sign out student -> Sign in Operator -> Priority -> Save departure -> Propose -> Confirm
        app.button(key="mob_nav_profile").click().run()
        app.button(key="prof_signout").click().run()
        self._login(app, "operator")

        app.button(key="operator_nav_button_priority").click().run()
        self.assertFalse(app.exception)
        app.button(key="sub04_save_departure").click().run()
        self.assertFalse(app.exception)

        req_id = get_state()["shared_charging_requests"][0]["request_id"]
        app.button(key=f"sub04_priority_{req_id}").click().run()
        self.assertFalse(app.exception)

        app.button(key="sub04_go_sched").click().run()
        self.assertFalse(app.exception)
        sched_id = get_state()["charging_schedules"][0]["schedule_id"]
        app.button(key="sub04_plan_queue").click().run()
        self.assertFalse(app.exception)
        app.button(key="sub04_confirm_plan").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(get_state()["charging_schedules"][0]["schedule_id"], sched_id)
        self.assertEqual(get_state()["charging_schedules"][0]["status"], "CONFIRMED")

        app.button(key="operator_nav_button_resources").click().run()
        self.assertFalse(app.exception)
        self.assertIsNotNone(app.date_input(key="sub04_monitor_day"))
        self.assertIsNotNone(app.time_input(key="sub04_monitor_from"))
        self.assertIn("Đỉnh công suất đã phân bổ", [metric.label for metric in app.metric])

    def test_private_ev_mobile_parking_charging_and_operator_dispatch_reschedule(self) -> None:
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self._login(app, "pstudent")

        # SUB-03 Mobile UI: Parking booking + Charging booking at HUB-03
        app.button(key="mob_nav_parking").click().run()
        app.button(key="s3_svc_open_parking").click().run()
        self.assertFalse(app.exception)
        app.button(key="s3_pk_confirm").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(get_state()["parking_reservations"]), 1)
        app.button(key="s3_ps_home").click().run()

        app.button(key="s3_svc_open_charging").click().run()
        self.assertFalse(app.exception)
        app.button(key="s3_cg_confirm").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(get_state()["charging_requests"]), 1)
        app.button(key="s3_cs_home").click().run()

        # Switch to Operator: Dispatch 1 bike & complete arrival; confirm schedule then replace broken point
        app.button(key="mob_nav_profile").click().run()
        app.button(key="prof_signout").click().run()
        self._login(app, "operator")

        app.button(key="operator_nav_button_dispatch").click().run()
        qty_input = next(n for n in app.number_input if (n.key or "").startswith("sub05_qty_"))
        qty_input.set_value(1).run()
        app.button(key="sub05_confirm").click().run()
        self.assertFalse(app.exception)
        oid = get_state()["dispatch_orders"][0]["order_id"]
        app.button(key=f"sub05_done_{oid}").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(get_state()["dispatch_orders"][0]["status"], "COMPLETED")

        # Schedule private EV charging at HUB-03, report incident on assigned charger, then replace point
        app.button(key="operator_nav_button_schedule").click().run()
        app.selectbox(key="sub04_selected_hub").set_value("HUB-03").run()
        creq_id = get_state()["charging_requests"][0]["request_id"]
        app.button(key=f"sub04_propose_{creq_id}").click().run()
        sched_id = get_state()["charging_schedules"][0]["schedule_id"]
        app.button(key=f"sub04_confirm_{sched_id}").click().run()
        assigned_pt = get_state()["charging_schedules"][0]["charging_point_id"]

        app.button(key="operator_nav_button_resources").click().run()
        # Report incident on assigned point via Incidents page
        app.button(key="operator_nav_button_incidents").click().run()
        app.button(key="sub05_new_incident").click().run()
        app.selectbox(key="sub05_inc_hub").set_value("HUB-03").run()
        app.selectbox(key="sub05_inc_rtype").set_value("CHARGING_POINT").run()
        app.selectbox(key="sub05_inc_res").set_value(assigned_pt).run()
        app.text_area(key="sub05_inc_desc").set_value("Mất tín hiệu trụ sạc").run()
        app.button(key="sub05_inc_submit").click().run()
        self.assertFalse(app.exception)

        # Jump from incident row to Lập lịch sạc -> preview & confirm replacement point
        inc_id = get_state()["incidents"][-1]["incident_id"]
        app.button(key=f"sub05_act_{inc_id}").click().run()
        self.assertFalse(app.exception)
        app.button(key=f"sub04_act_findrep_{sched_id}").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(get_state()["charging_schedules"][0]["charging_point_id"], assigned_pt)
        app.button(key=f"sub04_confirm_rep_{sched_id}").click().run()
        self.assertFalse(app.exception)
        self.assertNotEqual(get_state()["charging_schedules"][0]["charging_point_id"], assigned_pt)


    def test_operator_charging_actions_restore_view_and_interrupt(self):
        from streamlit.testing.v1 import AppTest

        state = get_state()
        reservation = discovery.create_reservation(state, "STU-001", "HUB-01")
        vehicle = trips.get_available_vehicles_at_hub(state, "HUB-01")[0]
        pickup = trips.pickup_vehicle(
            state, "STU-001", reservation["reservation_id"], vehicle["vehicle_id"], reservation["pickup_code"]
        )
        self.assertTrue(pickup["ok"])
        returned = trips.return_vehicle(state, "STU-001", pickup["trip"]["trip_id"], "HUB-01", 12)
        self.assertTrue(returned["ok"])
        request_id = returned["charging_request"]["request_id"]

        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self._login(app, "operator")
        app.button(key="operator_nav_button_priority").click().run()
        app.button(key=f"sub04_skip_{request_id}").click().run()
        self.assertFalse(any(b.key == f"sub04_skip_{request_id}" for b in app.button))
        self.assertEqual(state["shared_charging_requests"][0]["status"], "PENDING")
        app.button(key="sub04_restore_hidden").click().run()
        self.assertIsNotNone(app.button(key=f"sub04_skip_{request_id}"))
        app.button(key="sub04_save_departure").click().run()

        draft = charging.propose_charging_schedule(state, request_id)
        sid = draft["schedule_id"]
        charging.confirm_charging_schedule(state, sid)
        app.button(key="operator_nav_button_resources").click().run()
        app.button(key=f"sub04_view_sc_{sid}").click().run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.session_state["operator_nav"], "schedule")
        self.assertEqual(app.session_state["sub04_focused_schedule"], sid)
        self.assertIsNotNone(app.button(key=f"sub04_cancel_{sid}"))

        session_start = datetime.fromisoformat(draft["start_time"]) + timedelta(seconds=1)
        with patch.object(charging, "_now", return_value=session_start):
            charging.update_charging_progress(state, sid, 40)
            app.button(key="operator_nav_button_resources").click().run()
            app.button(key=f"sub04_stop_sc_{sid}").click().run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(state["charging_schedules"][0]["status"], "INTERRUPTED")
        self.assertEqual(state["charging_schedules"][0]["progress"], 40)
        self.assertEqual(vehicle["status"], "CHARGING")
        queued = charging.get_pending_charging_requests(state, "HUB-01")
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["vehicle_id"], vehicle["vehicle_id"])

    def test_operator_can_switch_to_dashboard_and_cancel_running_simulation(self):
        from streamlit.testing.v1 import AppTest

        original = simulation._simulate_metro_surge
        started, release = Event(), Event()

        def hold_calculation(result):
            started.set()
            if not release.wait(timeout=10):
                raise RuntimeError("Test did not release the worker")
            original(result)

        app = AppTest.from_file(APP_PATH, default_timeout=30).run()
        self._login(app, "operator")
        with patch.object(simulation, "_simulate_metro_surge", hold_calculation):
            try:
                app.button(key="operator_nav_button_simulation").click().run()
                app.button(key="sub06_run_simulation").click().run()
                self.assertTrue(started.wait(timeout=5))
                app.button(key="operator_nav_button_network").click().run()
                self.assertFalse(app.exception)
                app.button(key="operator_nav_button_simulation").click().run()
                app.button(key="sub06_cancel_simulation").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any("Đã hủy mô phỏng" in msg.value for msg in app.info))
            finally:
                release.set()
        self.assertEqual(get_sandbox_store()["sessions"][-1]["status"], "CANCELLED")
        self.assertFalse(simulation.get_sandbox_history())


if __name__ == "__main__":
    unittest.main()
