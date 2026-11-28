"""Comprehensive verification suite covering Submission 1, 2, and 3 test cases across Auth and SUB-01..06."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from modules.sub01 import service as sub01
from modules.sub02 import service as sub02
from modules.sub03 import service as sub03
from modules.sub04 import service as sub04
from modules.sub05 import service as sub05
from modules.sub06 import service as sub06
from shared import auth
from shared.state import reset_state


class FullSubmissionSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = reset_state()

    # ------------------------------------------------------------------
    # Authentication & Security NFR 3.1.4
    # ------------------------------------------------------------------
    def test_auth_signup_signin_and_password_hashing(self) -> None:
        ok, _, user = auth.sign_in(self.state, "student", "123")
        self.assertTrue(ok)
        self.assertEqual(user["role"], "Student")
        # Stored password must be hashed, never plaintext
        for u in self.state["users"]:
            self.assertTrue(u["password"].startswith("sha256$"))
            self.assertNotEqual(u["password"], "123")

        # Cannot self-register as Operator
        ok_op, _, _ = auth.sign_up(
            self.state, "hacker", "secret123", "secret123", "Hacker", "Operator"
        )
        self.assertFalse(ok_op)

        # Must accept terms
        ok_terms, _, _ = auth.sign_up(
            self.state, "newstu", "secret123", "secret123", "New Stu", "Student", accepted_terms=False
        )
        self.assertFalse(ok_terms)

        # Valid student sign-up + login
        ok_new, _, created = auth.sign_up(
            self.state, "newstu", "secret123", "secret123", "Lê Văn B", "Student", "10/05/2004"
        )
        self.assertTrue(ok_new)
        self.assertEqual(created["user_id"], "STU-002")
        ok_login, _, _ = auth.sign_in(self.state, "newstu", "secret123")
        self.assertTrue(ok_login)

    # ------------------------------------------------------------------
    # SUB-01: UC-01, UC-02, UC-03-01, UC-03-02 & TC-SUB01 boundary
    # ------------------------------------------------------------------
    def test_sub01_discovery_reservation_and_expired_cancel_boundary(self) -> None:
        hubs = sub01.get_hub_list(self.state)
        self.assertEqual(len(hubs), 5)
        suitable = sub01.find_suitable_hubs(self.state, "ELECTRIC_BICYCLE", min_battery=70)
        self.assertEqual(
            [h["hub_id"] for h in suitable],
            ["HUB-01", "HUB-02", "HUB-03", "HUB-05"],
        )

        # Idempotent reservation creation
        r1 = sub01.create_reservation(
            self.state, "STU-001", "HUB-01", idempotency_key="IDEM-R1"
        )
        r1_dup = sub01.create_reservation(
            self.state, "STU-001", "HUB-01", idempotency_key="IDEM-R1"
        )
        self.assertEqual(r1["reservation_id"], r1_dup["reservation_id"])
        self.assertEqual(self.state["hubs"][0]["reserved_slot_count"], 1)

        # TC-SUB01 boundary: cancelling an overdue reservation marks EXPIRED and frees slot once
        r1["expires_at"] = (datetime.now().astimezone() - timedelta(seconds=10)).isoformat()
        ok, msg = sub01.cancel_reservation(self.state, r1["reservation_id"], "STU-001")
        self.assertFalse(ok)
        self.assertIn("EXPIRED", msg)
        self.assertEqual(r1["status"], "EXPIRED")
        self.assertEqual(self.state["hubs"][0]["reserved_slot_count"], 0)

    # ------------------------------------------------------------------
    # SUB-02: TC-SUB02-001..005 & Faulty Vehicle Swap
    # ------------------------------------------------------------------
    def test_sub02_pickup_fault_swap_and_full_hub_return_suggestions(self) -> None:
        res = sub01.create_reservation(self.state, "STU-001", "HUB-01")
        avail = sub02.get_available_vehicles_at_hub(self.state, "HUB-01")
        faulty_veh = avail[0]
        replacement_veh = avail[1]

        # UC-04 A1: report defective vehicle at pickup keeps reservation PENDING
        rep = sub02.report_defective_vehicle_at_pickup(
            self.state, "STU-001", res["reservation_id"], faulty_veh["vehicle_id"], "Khóa không mở"
        )
        self.assertTrue(rep["ok"])
        self.assertEqual(faulty_veh["status"], "UNAVAILABLE")
        self.assertEqual(res["status"], "PENDING")

        # TC-SUB02-002: picking up UNAVAILABLE vehicle is rejected
        bad_pickup = sub02.pickup_vehicle(
            self.state, "STU-001", res["reservation_id"], faulty_veh["vehicle_id"], res["pickup_code"]
        )
        self.assertFalse(bad_pickup["ok"])
        self.assertEqual(bad_pickup["status"], "VEHICLE_NOT_AVAILABLE")

        # TC-SUB02-001: pick up replacement vehicle succeeds and frees origin stall
        good_pickup = sub02.pickup_vehicle(
            self.state, "STU-001", res["reservation_id"], replacement_veh["vehicle_id"], res["pickup_code"]
        )
        self.assertTrue(good_pickup["ok"])
        self.assertEqual(res["status"], "CONSUMED")
        self.assertEqual(replacement_veh["status"], "IN_USE")

        # TC-SUB02-005: destination Hub full -> rejected with nearby Hub suggestions
        for sp in self.state["parking_spaces"]:
            if sp["hub_id"] == "HUB-02" and sp["status"] == "AVAILABLE":
                sp["status"] = "IN_USE"
        full_ret = sub02.return_vehicle(
            self.state, "STU-001", good_pickup["trip"]["trip_id"], "HUB-02", 65
        )
        self.assertFalse(full_ret["ok"])
        self.assertEqual(full_ret["status"], "DESTINATION_HUB_FULL")
        self.assertTrue(len(full_ret["suggested_hubs"]) >= 1)
        self.assertTrue(good_pickup["trip"]["is_active"])

        # TC-SUB02-003: return at HUB-03 with healthy battery -> AVAILABLE
        ok_ret = sub02.return_vehicle(
            self.state, "STU-001", good_pickup["trip"]["trip_id"], "HUB-03", 65
        )
        self.assertTrue(ok_ret["ok"])
        self.assertEqual(replacement_veh["status"], "AVAILABLE")
        self.assertEqual(replacement_veh["hub_id"], "HUB-03")

    # ------------------------------------------------------------------
    # SUB-03: TC-SUB03-001..005 & Same-Minute Clock-Drift Resilience
    # ------------------------------------------------------------------
    def test_sub03_private_ev_hold_checkin_charging_and_non_charger_rejection(self) -> None:
        now = datetime.now().astimezone()
        # Simulate user opening form 2 minutes ago so start_time HH:MM is slightly in the past today
        start_hhmm = (now - timedelta(minutes=2)).strftime("%H:%M")
        end_hhmm = (now + timedelta(hours=2)).strftime("%H:%M")

        hold = sub03.create_temporary_hold(self.state, "PS-001", "PSTU-001", now=now)
        prsv = sub03.confirm_parking_reservation(
            self.state, hold["hold_id"], "PSTU-001", "59-X3 888.88", start_hhmm, end_hhmm, now=now
        )
        self.assertEqual(prsv["status"], "RESERVED")

        # TC-SUB03-004: charger-equipped space creates PENDING ChargingRequest and can be scheduled
        creq = sub03.create_charging_request(
            self.state, prsv["reservation_id"], "PSTU-001", 25, 85, end_hhmm
        )
        self.assertEqual(creq["status"], "PENDING")
        prop = sub04.propose_charging_schedule(self.state, creq["request_id"])
        conf = sub04.confirm_charging_schedule(self.state, prop["schedule_id"])
        self.assertEqual(conf["status"], "CONFIRMED")

        # TC-SUB03-003: check-in -> start charging -> check-out blocked while IN_USE -> finish -> check-out
        ok_ci, _ = sub03.check_in_vehicle(self.state, prsv["reservation_id"], "PSTU-001")
        self.assertTrue(ok_ci)
        self.state["charging_schedules"][0]["start_time"] = (now - timedelta(seconds=5)).isoformat(timespec="seconds")
        sub04.update_charging_progress(self.state, conf["schedule_id"], 50)
        ok_co_early, _ = sub03.check_out_vehicle(self.state, prsv["reservation_id"], "PSTU-001")
        self.assertFalse(ok_co_early)
        sub04.update_charging_progress(self.state, conf["schedule_id"], 100)
        ok_co, _ = sub03.check_out_vehicle(self.state, prsv["reservation_id"], "PSTU-001")
        self.assertTrue(ok_co)
        self.assertEqual(prsv["status"], "COMPLETED")

        # TC-SUB03-005: non-charger space PS-002 (local_index=1, has_charger=False) rejects charging request
        hold2 = sub03.create_temporary_hold(self.state, "PS-002", "PSTU-001", now=now)
        prsv2 = sub03.confirm_parking_reservation(
            self.state, hold2["hold_id"], "PSTU-001", "59-X3 999.99", start_hhmm, end_hhmm, now=now
        )
        with self.assertRaises(ValueError):
            sub03.create_charging_request(
                self.state, prsv2["reservation_id"], "PSTU-001", 25, 85, end_hhmm
            )

    # ------------------------------------------------------------------
    # SUB-04 & SUB-05: TC-SUB04-005 (Point Failure Reschedule) & Dispatch/Incident Rules
    # ------------------------------------------------------------------
    def test_sub04_sub05_point_failure_reschedule_dispatch_and_low_battery_incident_recovery(self) -> None:
        # 1. Schedule shared EV charging on CP-001, then report incident on CP-001 (TC-SUB04-005)
        depart = (datetime.now().astimezone() + timedelta(hours=2)).isoformat()
        sh_req = sub04.receive_shared_vehicle_charging_need(self.state, "EV-009", 15, depart)
        prop = sub04.propose_charging_schedule(self.state, sh_req["request_id"], point_id="CP-001")
        conf = sub04.confirm_charging_schedule(self.state, prop["schedule_id"])
        self.assertEqual(conf["charging_point_id"], "CP-001")

        inc_res = sub05.create_or_update_incident("CP-001", "Lỗi cảm biến dòng", severity="HIGH", reported_by="OP-001")
        self.assertTrue(inc_res["ok"])
        resources = sub04.get_charging_resources(self.state, "HUB-01")
        sched_view = next(s for s in resources["schedules"] if s["schedule_id"] == conf["schedule_id"])
        self.assertTrue(sched_view["needs_reschedule"])
        # Preview replacement keeps original CP-001 until confirmed
        preview_rep = sub04.replace_charging_point(self.state, conf["schedule_id"], confirm=False)
        self.assertEqual(preview_rep["charging_point_id"], "CP-001")
        self.assertEqual(preview_rep["replacement"], "CP-002")
        confirmed_rep = sub04.replace_charging_point(self.state, conf["schedule_id"], confirm=True)
        self.assertEqual(confirmed_rep["charging_point_id"], "CP-002")

        # 2. Dispatch holds target spaces, blocks pickup of transiting vehicles, and protects reservations
        res_h2 = sub01.create_reservation(self.state, "STU-001", "HUB-02")
        transferable = sub05.get_transferable_vehicles("HUB-02")
        self.assertEqual(transferable["max_transferable"], 5)  # 6 AVAILABLE - 1 reserved slot
        too_many = sub05.create_dispatch_order("HUB-02", "HUB-03", quantities={"ELECTRIC_BICYCLE": 3, "ELECTRIC_MOTORCYCLE": 3})
        self.assertFalse(too_many["ok"])

        disp = sub05.create_dispatch_order("HUB-02", "HUB-03", quantities={"ELECTRIC_BICYCLE": 2}, created_by="OP-001")
        self.assertTrue(disp["ok"])
        transit_vid = disp["order"]["vehicle_ids"][0]
        # Student cannot pick up a transiting vehicle
        blocked_pickup = sub02.pickup_vehicle(
            self.state, "STU-001", res_h2["reservation_id"], transit_vid, res_h2["pickup_code"]
        )
        self.assertFalse(blocked_pickup["ok"])
        arrived = sub05.complete_dispatch_order(disp["order"]["order_id"])
        self.assertTrue(arrived["ok"])
        moved_veh = next(v for v in self.state["vehicles"] if v["vehicle_id"] == transit_vid)
        self.assertEqual(moved_veh["hub_id"], "HUB-03")

        # 3. Resolving an incident on a low-battery (<20%) vehicle keeps it CHARGING, never AVAILABLE
        low_veh = next(v for v in self.state["vehicles"] if v["vehicle_id"] == "EV-001")
        low_veh["battery_level"] = 12
        inc_v = sub05.create_or_update_incident("EV-001", "Xẹp lốp", severity="MEDIUM", reported_by="OP-001")
        self.assertEqual(low_veh["status"], "UNAVAILABLE")
        sub05.resolve_incident(inc_v["incident"]["incident_id"], resolved_by="OP-001")
        self.assertEqual(low_veh["status"], "CHARGING")

    # ------------------------------------------------------------------
    # SUB-06: All 5 Scenarios, Immutability, Disconnected Hub & Infeasible A4
    # ------------------------------------------------------------------
    def test_sub06_all_five_scenarios_sandbox_isolation_and_edge_cases(self) -> None:
        scenarios = sub06.get_available_scenarios()
        self.assertEqual(len(scenarios), 5)

        before = deepcopy(self.state)
        snap_metro = sub06.get_network_snapshot(self.state, "HUB-01")
        snap_hcmut = sub06.get_network_snapshot(self.state, "HUB-03")

        # 1. Metro demand surge
        r1 = sub06.run_simulation("metro_demand_surge", {"base_demand": 8, "increase_percent": 50}, snap_metro)
        self.assertTrue(any(i["code"] == "vehicle_shortage" for i in r1["issues"]))

        # 2. Full parking / Hub near capacity
        r2 = sub06.run_simulation(
            "hub_near_capacity",
            {"additional_vehicle_demand": 5, "additional_parking_occupancy": 18},
            snap_hcmut,
        )
        self.assertTrue(any(i["code"] == "parking_utilization_full" for i in r2["issues"]))

        # 3. Charging surge
        r3 = sub06.run_simulation(
            "charging_pressure", {"additional_requests": 5, "failed_points": 0}, snap_hcmut
        )
        self.assertTrue(any(i["code"] == "charging_shortage" for i in r3["issues"]))

        # 4. Charging-point failures (even with 0 extra requests, detects capacity drop!)
        r4 = sub06.run_simulation(
            "point_failures", {"additional_requests": 0, "failed_points": 2}, snap_hcmut
        )
        self.assertTrue(any(i["code"] == "charger_failure_impact" for i in r4["issues"]))

        # 5. Vehicle concentration
        r5 = sub06.run_simulation(
            "vehicle_concentration", {"source_hub_id": "HUB-02", "moved": 5}, snap_hcmut
        )
        self.assertTrue(any(i["code"] == "vehicle_concentration_imbalance" for i in r5["issues"]))

        # Operational state must remain 100% identical after all 5 simulations!
        self.assertEqual(self.state, before)

        # TC-SUB06-001: Out-of-range parameter validation
        errs = sub06.validate_scenario_parameters(
            "hub_near_capacity",
            {"additional_vehicle_demand": 999, "additional_parking_occupancy": 10},
            snap_hcmut,
        )
        self.assertTrue(len(errs) >= 1)

        # TC-SUB06-003: Disconnected Hub snapshot rejected
        self.state["hubs"][0]["data_validity"] = "DISCONNECTED"
        bad_snap = sub06.get_network_snapshot(self.state, "HUB-01")
        self.assertFalse(bad_snap["data_complete"])
        with self.assertRaises(sub06.SimulationInputError):
            sub06.run_simulation("metro_demand_surge", {"base_demand": 6, "increase_percent": 50}, bad_snap)

        # TC-SUB06-004: Infeasible recommendation when no donor Hub has spare vehicles
        self.state["hubs"][0]["data_validity"] = "VALID"
        for v in self.state["vehicles"]:
            if v["hub_id"] != "HUB-01":
                v["status"] = "IN_USE"
        isolated_snap = sub06.get_network_snapshot(self.state, "HUB-01")
        r_infeasible = sub06.run_simulation(
            "metro_demand_surge", {"base_demand": 10, "increase_percent": 50}, isolated_snap
        )
        self.assertEqual(r_infeasible["recommendations"], [])
        self.assertIsNotNone(r_infeasible["infeasibility_reason"])


if __name__ == "__main__":
    unittest.main()
