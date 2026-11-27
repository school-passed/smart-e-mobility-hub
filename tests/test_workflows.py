"""Cross-module integration tests using the real shared demo state, without Streamlit UI."""
from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timedelta

from shared.state import reset_state
from modules.sub01 import service as sub01
from modules.sub02 import service as sub02
from modules.sub03 import service as sub03
from modules.sub04 import service as sub04
from modules.sub05 import service as sub05
from modules.sub06 import service as sub06


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.state = reset_state()

    def test_reserve_pickup_return_to_shared_charging(self):
        reservation = sub01.create_reservation(self.state, "STU-001", "HUB-01")
        vehicle = sub02.get_available_vehicles_at_hub(self.state, "HUB-01")[0]
        wrong_code = sub02.pickup_vehicle(
            self.state, "STU-001", reservation["reservation_id"], vehicle["vehicle_id"], ""
        )
        self.assertFalse(wrong_code["ok"])
        self.assertEqual(self.state["reservations"][0]["status"], "PENDING")

        pickup = sub02.pickup_vehicle(
            self.state, "STU-001", reservation["reservation_id"],
            vehicle["vehicle_id"], reservation["pickup_code"],
        )
        self.assertTrue(pickup["ok"], pickup["message"])
        self.assertEqual(self.state["reservations"][0]["status"], "CONSUMED")

        ret = sub02.return_vehicle(
            self.state, "STU-001", pickup["trip"]["trip_id"], "HUB-02", 10,
        )
        self.assertTrue(ret["ok"], ret["message"])
        self.assertEqual(len(self.state["charging_requests"]), 0)
        self.assertEqual(len(self.state["shared_charging_requests"]), 1)
        request = self.state["shared_charging_requests"][0]
        self.assertEqual(request["current_battery"], 10)
        ranked, incomplete = sub04.prioritize_charging_requests(self.state, "HUB-02")
        self.assertFalse(ranked)
        self.assertEqual(incomplete[0]["request_id"], request["request_id"])
        # Shared EV needs Operator's planned departure before it can be ranked.
        depart = (datetime.now().astimezone() + timedelta(hours=3)).isoformat()
        sub04.set_shared_departure(self.state, request["request_id"], depart)
        ranked, incomplete = sub04.prioritize_charging_requests(self.state, "HUB-02")
        self.assertEqual([r["request_id"] for r in ranked], [request["request_id"]])
        self.assertFalse(incomplete)
        proposed = sub04.propose_charging_schedule(self.state, request["request_id"])
        confirmed = sub04.confirm_charging_schedule(self.state, proposed["schedule_id"])
        self.assertEqual(confirmed["status"], "CONFIRMED")

    def test_private_parking_charging_schedule(self):
        now = datetime.now().astimezone()
        hold = sub03.create_temporary_hold(self.state, "PS-001", "PSTU-001")
        reservation = sub03.confirm_parking_reservation(
            self.state, hold["hold_id"], "PSTU-001", "59-M1 1234",
            (now + timedelta(hours=1)).strftime("%H:%M"),
            (now + timedelta(hours=4)).strftime("%H:%M"),
        )
        charging = sub03.create_charging_request(
            self.state, reservation["reservation_id"], "PSTU-001", 22, 80,
            (now + timedelta(hours=4)).strftime("%H:%M"),
        )
        proposal = sub04.propose_charging_schedule(self.state, charging["request_id"])
        sub04.confirm_charging_schedule(self.state, proposal["schedule_id"])
        self.assertEqual(charging["status"], "CONFIRMED")
        success, message = sub03.cancel_charging_request(self.state, charging["request_id"], "PSTU-001")
        self.assertTrue(success, message)
        self.assertEqual(charging["status"], "CANCELLED")

    def test_operator_refresh_expires_reservations(self):
        reservation = sub01.create_reservation(self.state, "STU-001", "HUB-01")
        reservation["expires_at"] = (datetime.now().astimezone() - timedelta(minutes=1)).isoformat()
        self.assertEqual(self.state["hubs"][0]["reserved_slot_count"], 1)
        sub05.refresh()
        self.assertEqual(reservation["status"], "EXPIRED")
        self.assertEqual(self.state["hubs"][0]["reserved_slot_count"], 0)

    def test_simulation_reads_both_charging_queues_without_writing(self):
        sub04.receive_shared_vehicle_charging_need(self.state,"EV-001",15)
        before=deepcopy(self.state)
        snap=sub06.get_network_snapshot(self.state,"HUB-01")
        self.assertEqual(len(snap["records"]["shared_charging_requests"]),1)
        result=sub06.run_simulation(
            "charging_pressure", {"additional_requests": 2, "failed_points": 1},snap
        )
        metric=next(x for x in result["metrics"] if x["id"]=="charging_demand")
        self.assertEqual(metric["before"],1)
        self.assertEqual(self.state,before)


if __name__ == "__main__":
    unittest.main()
