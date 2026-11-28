"""Regression cases reproduced against the integrated Submission 1–3 demo."""

from concurrent.futures import CancelledError
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Event
import unittest
from unittest.mock import patch

from modules.sub01 import service as discovery
from modules.sub02 import service as trips
from modules.sub03 import service as parking
from modules.sub04 import service as charging
from modules.sub05 import service as operations
from modules.sub06 import service as simulation
from shared.state import get_sandbox_store, reset_state


class ChargingAndParkingRegressions(unittest.TestCase):
    def setUp(self):
        self.state = reset_state()
        self.now = datetime.now().astimezone().replace(second=0, microsecond=0)
        self.end = self.now + timedelta(hours=2)
        for service in (charging, parking):
            clock = patch.object(service, "_now", side_effect=lambda: self.now)
            clock.start()
            self.addCleanup(clock.stop)

    def shared_schedule(self):
        reservation = discovery.create_reservation(self.state, "STU-001", "HUB-01")
        vehicle = trips.get_available_vehicles_at_hub(self.state, "HUB-01")[0]
        pickup = trips.pickup_vehicle(
            self.state, "STU-001", reservation["reservation_id"],
            vehicle["vehicle_id"], reservation["pickup_code"],
        )
        self.assertTrue(pickup["ok"], pickup)
        result = trips.return_vehicle(
            self.state, "STU-001", pickup["trip"]["trip_id"], "HUB-02", 12,
        )
        self.assertTrue(result["ok"], result)
        request = self.state["shared_charging_requests"][0]
        charging.set_shared_departure(self.state, request["request_id"], self.end)
        draft = charging.propose_charging_schedule(self.state, request["request_id"])
        charging.confirm_charging_schedule(self.state, draft["schedule_id"])
        return vehicle, request, self.state["charging_schedules"][0]

    def private_reservation(self, start=None):
        hold = parking.create_temporary_hold(self.state, "PS-001", "PSTU-001")
        arrival = start or self.now
        return parking.confirm_parking_reservation(
            self.state, hold["hold_id"], "PSTU-001", "59-A1 12345",
            arrival.isoformat(), self.end.isoformat(),
        )

    def assert_shared_requeued(self, vehicle, request, schedule, schedule_status):
        self.assertEqual(schedule["status"], schedule_status)
        self.assertEqual(request["status"], "CANCELLED")
        self.assertEqual(vehicle["status"], "CHARGING")
        waiting = charging.get_pending_charging_requests(self.state, "HUB-02")
        self.assertEqual(len(waiting), 1)
        self.assertEqual(waiting[0]["request_id"], request["follow_up_request_id"])
        self.assertEqual(waiting[0]["vehicle_id"], vehicle["vehicle_id"])
        self.assertEqual(waiting[0]["current_battery"], 12)
        return waiting[0]

    def test_submission_3_priority_uses_30_percent_and_fifo_within_group(self):
        data = [
            ("R01", 20, "10:30", "07:10"),
            ("R02", 10, "10:30", "07:20"),
            ("R03", 15, "11:00", "07:00"),
            ("R04", 15, None, "06:50"),
            ("R05", 30, "10:00", "06:40"),
            ("R06", None, "10:30", "06:30"),
        ]
        for request_id, battery, departure, created in data:
            self.state["charging_requests"].append({
                "request_id": request_id, "hub_id": "HUB-01", "status": "PENDING",
                "current_battery": battery, "departure_time": departure,
                "created_at": f"2026-05-01T{created}:00", "end_time": "10:00",
            })
        ranked, incomplete = charging.prioritize_charging_requests(self.state, "HUB-01")
        self.assertEqual([row["request_id"] for row in ranked], ["R01", "R02", "R03", "R04", "R05"])
        self.assertEqual([row["request_id"] for row in incomplete], ["R06"])

    def test_cancel_shared_schedule_requeues_once_and_can_schedule_again(self):
        vehicle, request, schedule = self.shared_schedule()
        for _ in range(2):
            self.assertTrue(charging.cancel_charging_schedule(self.state, request["request_id"])[0])
        follow_up = self.assert_shared_requeued(vehicle, request, schedule, "CANCELLED")
        self.assertEqual(follow_up["departure_time"], request["departure_time"])
        draft = charging.propose_charging_schedule(self.state, follow_up["request_id"])
        self.assertEqual(charging.confirm_charging_schedule(self.state, draft["schedule_id"])["status"], "CONFIRMED")

    def test_elapsed_unused_schedule_releases_point_and_requeues_shared_ev(self):
        vehicle, request, schedule = self.shared_schedule()
        self.now = self.end
        operations.refresh()
        operations.refresh()
        follow_up = self.assert_shared_requeued(vehicle, request, schedule, "EXPIRED")
        self.assertIsNone(follow_up["departure_time"])
        data = charging.get_charging_resources(self.state, "HUB-02")
        point = next(p for p in data["points"] if p["charging_point_id"] == schedule["charging_point_id"])
        self.assertEqual(point["status"], "AVAILABLE")

    def test_emergency_stop_requeues_shared_ev_and_keeps_point_unavailable(self):
        vehicle, request, schedule = self.shared_schedule()
        self.now += timedelta(minutes=2)
        charging.update_charging_progress(self.state, schedule["schedule_id"], 25)
        incident = operations.create_or_update_incident(schedule["charging_point_id"], "Lỗi trụ", "HIGH")
        stopped = operations.emergency_stop_resource_session(incident["incident"]["incident_id"])
        self.assertTrue(stopped["ok"], stopped)
        self.assert_shared_requeued(vehicle, request, schedule, "INTERRUPTED")
        self.assertEqual(schedule["progress"], 25)
        self.assertEqual(vehicle["battery_level"], 12)
        data = charging.get_charging_resources(self.state, "HUB-02")
        point = next(p for p in data["points"] if p["charging_point_id"] == schedule["charging_point_id"])
        self.assertEqual(point["status"], "UNAVAILABLE")

    def test_check_in_accepts_only_the_booked_window(self):
        arrival = self.now + timedelta(hours=1)
        prsv = self.private_reservation(arrival)
        self.assertFalse(parking.check_in_vehicle(self.state, prsv["reservation_id"], "PSTU-001")[0])
        self.now = arrival
        self.assertTrue(parking.check_in_vehicle(self.state, prsv["reservation_id"], "PSTU-001")[0])

    def test_unused_parking_reservation_expires_and_releases_space_and_schedule(self):
        prsv = self.private_reservation()
        request = parking.create_charging_request(
            self.state, prsv["reservation_id"], "PSTU-001", 22, 80, self.end.isoformat()
        )
        draft = charging.propose_charging_schedule(self.state, request["request_id"])
        charging.confirm_charging_schedule(self.state, draft["schedule_id"])
        self.now = self.end
        self.assertFalse(parking.check_in_vehicle(self.state, prsv["reservation_id"], "PSTU-001")[0])
        self.assertEqual(prsv["status"], "EXPIRED")
        self.assertEqual(self.state["charging_schedules"][0]["status"], "EXPIRED")
        self.assertEqual(request["status"], "CANCELLED")
        self.assertEqual(self.state["parking_spaces"][0]["status"], "AVAILABLE")
        self.assertFalse(parking.cancel_parking_reservation(self.state, prsv["reservation_id"], "PSTU-001")[0])

    def test_blocked_parking_rejects_propose_and_confirmation(self):
        prsv = self.private_reservation()
        request = parking.create_charging_request(
            self.state, prsv["reservation_id"], "PSTU-001", 22, 80, self.end.isoformat()
        )
        draft = charging.propose_charging_schedule(self.state, request["request_id"])
        operations.create_or_update_incident(prsv["space_id"], "Ô đỗ bị khóa", "HIGH")
        for operation, resource in (
            (charging.propose_charging_schedule, request["request_id"]),
            (charging.confirm_charging_schedule, draft["schedule_id"]),
        ):
            with self.assertRaisesRegex(ValueError, "Ô đỗ không khả dụng"):
                operation(self.state, resource)
        self.assertEqual(request["status"], "PENDING")

    def test_vehicle_fault_after_confirmation_blocks_start(self):
        vehicle, request, schedule = self.shared_schedule()
        operations.create_or_update_incident(vehicle["vehicle_id"], "Xe hỏng", "HIGH")
        self.now += timedelta(minutes=2)
        with self.assertRaisesRegex(ValueError, "bị khóa"):
            charging.update_charging_progress(self.state, schedule["schedule_id"], 10)
        self.assertEqual(schedule["status"], "CONFIRMED")
        self.assertEqual(request["status"], "CONFIRMED")

    def test_read_only_window_and_confirm_only_feasible_requests(self):
        hub_id = "HUB-01"
        self.state["hubs"][0]["charging_capacity_kw"] = 6
        points = [p for p in self.state["charging_points"] if p["hub_id"] == hub_id]
        for point in points[:3]:
            point.update(status="AVAILABLE", power_kw=3)
        window = (self.now + timedelta(hours=1), self.end)

        def request(vehicle, battery):
            return charging.receive_shared_vehicle_charging_need(
                self.state, vehicle, battery, self.end.isoformat()
            )["request_id"]

        first = request("EV-001", 25)
        first_schedule = charging.propose_charging_schedule(self.state, first, *window)
        charging.confirm_charging_schedule(self.state, first_schedule["schedule_id"])
        before = deepcopy(self.state)
        slots, peak, used = charging.monitor_window(self.state, hub_id, *window)
        self.assertEqual((peak, used), (3, 0))
        self.assertEqual(slots[0]["Trạng thái khung giờ"], "RESERVED")
        self.assertEqual(slots[1]["Trạng thái khung giờ"], "AVAILABLE")
        self.assertEqual(self.state, before)

        winner, waiting = request("EV-002", 10), request("EV-003", 35)
        for req in self.state["shared_charging_requests"][1:]:
            req.update(start_time=window[0].isoformat(), end_time=window[1].isoformat())
        drafts, reasons = charging.propose_queue(self.state, hub_id)
        self.assertEqual([row["request_id"] for row in drafts], [winner])
        self.assertIn("công suất", reasons[waiting])

        confirmed = charging.confirm_charging_plan(self.state, drafts, "K-CONF-01")
        self.assertEqual(charging.confirm_charging_plan(self.state, drafts, "K-CONF-01"), confirmed)
        self.assertEqual(len(self.state["charging_schedules"]), 2)
        self.assertEqual(charging.get_pending_charging_requests(self.state, hub_id)[0]["request_id"], waiting)
        self.assertEqual(charging.monitor_window(self.state, hub_id, *window)[1], 6)

    def test_changed_second_draft_rejects_entire_plan(self):
        for vehicle in ("EV-001", "EV-002"):
            charging.receive_shared_vehicle_charging_need(self.state, vehicle, 12, self.end.isoformat())
        drafts, waiting = charging.propose_queue(self.state, "HUB-01")
        self.assertFalse(waiting)
        self.assertEqual(len(drafts), 2)
        operations.create_or_update_incident(drafts[1]["charging_point_id"], "Lỗi trụ sau khi duyệt", "HIGH")
        before = deepcopy(self.state)
        with self.assertRaises(ValueError):
            charging.confirm_charging_plan(self.state, drafts, "K-STALE")
        self.assertEqual(self.state, before)

    def test_dispatch_revalidates_hub_connection_at_creation_and_arrival(self):
        vehicle = operations.get_transferable_vehicles("HUB-01")["vehicles"][0]
        vehicle_ids = [vehicle["vehicle_id"]]
        incident = operations.create_or_update_incident("HUB-02", "Mất kết nối", "HIGH")
        self.assertFalse(operations.create_dispatch_order("HUB-01", "HUB-02", vehicle_ids)["ok"])
        self.assertFalse(self.state["dispatch_orders"])
        operations.resolve_incident(incident["incident"]["incident_id"])
        created = operations.create_dispatch_order("HUB-01", "HUB-02", vehicle_ids)
        self.assertTrue(created["ok"], created)
        operations.create_or_update_incident("HUB-02", "Mất kết nối lại", "HIGH")
        self.assertFalse(operations.complete_dispatch_order(created["order"]["order_id"])["ok"])
        self.assertEqual(vehicle["hub_id"], "HUB-01")


class SimulationRegressions(unittest.TestCase):
    def test_cancel_running_session_discards_result_and_leaves_operational_state(self):
        state = reset_state()
        before = deepcopy(state)
        snapshot = simulation.get_network_snapshot(state, "HUB-01")
        started, release = Event(), Event()
        original = simulation._simulate_metro_surge

        def wait_during_calculation(result):
            started.set()
            if not release.wait(timeout=10):
                raise RuntimeError("Test did not release the worker")
            original(result)

        with patch.object(simulation, "_simulate_metro_surge", wait_during_calculation):
            session_id, future = simulation.start_simulation(
                "metro_demand_surge", {"base_demand": 5, "increase_percent": 20}, snapshot
            )
            try:
                self.assertTrue(started.wait(timeout=5))
                self.assertTrue(simulation.cancel_simulation_session(session_id))
            finally:
                release.set()
            with self.assertRaises(CancelledError):
                future.result(timeout=5)
        self.assertEqual(get_sandbox_store()["sessions"][0]["status"], "CANCELLED")
        self.assertFalse(simulation.get_sandbox_history())
        self.assertEqual(state, before)
