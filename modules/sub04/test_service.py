"""Regression tests for the SUB-04 allocation rules and SUB-03 service contract."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from modules.sub03 import service as parking
from modules.sub04 import service as charging
from shared.state import _seed_data


class ChargingTests(unittest.TestCase):
    def setUp(self):
        self.state = _seed_data()
        self.now = datetime(2026, 5, 1, 20, tzinfo=timezone.utc).astimezone()
        for module in (parking, charging):
            mock = patch.object(module, "_now", side_effect=lambda: self.now)
            mock.start()
            self.addCleanup(mock.stop)
        self.end = self.now + timedelta(hours=3)

    def shared(self, vehicle, battery=25, departure=True):
        return charging.receive_shared_vehicle_charging_need(
            self.state, vehicle, battery, self.end.isoformat() if departure else None
        )["request_id"]

    def propose(self, rid, start=None, end=None):
        return charging.propose_charging_schedule(self.state, rid, start, end)["schedule_id"]

    def confirm(self, sid):
        return charging.confirm_charging_schedule(self.state, sid)

    def private(self):
        hold = parking.create_temporary_hold(self.state, "PS-001", "student")
        reservation = parking.confirm_parking_reservation(
            self.state, hold["hold_id"], "student", "EV1", self.now.strftime("%H:%M"), self.end.strftime("%H:%M")
        )
        return parking.create_charging_request(
            self.state, reservation["reservation_id"], "student", 20, 80, self.end.strftime("%H:%M")
        )

    def test_private_round_trip_and_release(self):
        req = self.private()
        sid = self.propose(req["request_id"])
        self.assertEqual(len(self.state["charging_requests"]), 1)
        self.assertEqual(self.state["charging_points"][0]["status"], "AVAILABLE")
        self.confirm(sid)
        self.assertEqual(req["status"], "CONFIRMED")
        self.assertEqual(self.state["charging_points"][0]["status"], "RESERVED")
        self.assertTrue(parking.cancel_charging_request(self.state, req["request_id"], "student")[0])
        self.assertEqual(self.state["charging_points"][0]["status"], "AVAILABLE")

    def test_private_parking_revalidated_and_stale_proposal_rejected(self):
        req = self.private()
        sid = self.propose(req["request_id"])
        self.state["parking_reservations"][0]["hub_id"] = "HUB-02"
        with self.assertRaises(ValueError):
            self.confirm(sid)
        parking.cancel_charging_request(self.state, req["request_id"], "student")
        self.assertEqual(charging.get_charging_resources(self.state, "HUB-01")["schedules"][0]["status"], "CANCELLED")

    def test_priority_and_missing_data(self):
        first = self.shared("EV-001", 10)
        self.now += timedelta(seconds=2)
        second = self.shared("EV-002", 10)
        third = self.shared("EV-003", 50)
        absent = self.shared("EV-004", 5, False)
        sooner = self.shared("EV-005", 10, False)
        charging.set_shared_departure(self.state, sooner, (self.end - timedelta(minutes=1)).isoformat())
        ranked, incomplete = charging.prioritize_charging_requests(self.state, "HUB-01")
        self.assertEqual([r["request_id"] for r in ranked], [sooner, first, second, third])
        self.assertEqual([r["request_id"] for r in incomplete], [absent])
        self.assertEqual(self.shared("EV-004", 5), absent)

    def test_concurrent_confirmation_and_capacity(self):
        self.state["hubs"][0]["charging_capacity_kw"] = 14
        ids = [self.propose(self.shared(v)) for v in ("EV-001", "EV-002")]
        with ThreadPoolExecutor(2) as pool:
            results = [pool.submit(self.confirm, sid) for sid in ids]
        self.assertEqual(sum(f.exception() is None for f in results), 1)
        loser = next(i for i, f in enumerate(results) if f.exception())
        rid = self.state["charging_schedules"][loser]["request_id"]
        with self.assertRaisesRegex(ValueError, "công suất"):
            self.propose(rid)

    def test_adjacent_slots_session_and_cancellation(self):
        middle = self.now + timedelta(hours=1)
        first, second = self.shared("EV-001"), self.shared("EV-002")
        sid = self.propose(first, end=middle)
        schedule = self.confirm(sid)
        next_slot = self.confirm(self.propose(second, start=middle))
        self.assertEqual(schedule["charging_point_id"], next_slot["charging_point_id"])
        self.now += timedelta(minutes=2)
        self.assertFalse(charging.cancel_charging_schedule(self.state, first)[0])
        charging.update_charging_progress(self.state, sid, 50)
        self.assertEqual(self.state["charging_points"][0]["status"], "IN_USE")
        charging.update_charging_progress(self.state, sid, 100)
        self.assertEqual(self.state["charging_points"][0]["status"], "RESERVED")
        charging.cancel_charging_schedule(self.state, second)
        self.assertEqual(self.state["charging_points"][0]["status"], "AVAILABLE")

    def test_missing_connector_and_eligibility_change(self):
        req = self.private()
        req["connector_type"] = "TYPE2"
        with self.assertRaisesRegex(ValueError, "tương thích"):
            self.propose(req["request_id"])
        self.state["charging_points"][0]["connector_type"] = "TYPE2"
        sid = self.propose(req["request_id"])
        self.state["charging_points"][0]["status"] = "UNAVAILABLE"
        with self.assertRaises(ValueError):
            self.confirm(sid)
        self.assertEqual(req["status"], "PENDING")

    def test_checked_in_private_session_finishes_and_releases_point(self):
        req = self.private()
        ok, _ = parking.check_in_vehicle(self.state, req["reservation_id"], "student")
        self.assertTrue(ok)
        sid = self.propose(req["request_id"])
        self.confirm(sid)
        self.now += timedelta(minutes=2)
        charging.update_charging_progress(self.state, sid, 40)
        self.assertFalse(parking.cancel_charging_request(self.state, req["request_id"], "student")[0])
        result = charging.update_charging_progress(self.state, sid, 100)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(self.state["charging_points"][0]["status"], "AVAILABLE")

    def test_capacity_change_before_session_start(self):
        sid = self.propose(self.shared("EV-001"))
        self.confirm(sid)
        self.now += timedelta(minutes=2)
        self.state["hubs"][0]["charging_capacity_kw"] = 10
        with self.assertRaisesRegex(ValueError, "công suất"):
            charging.update_charging_progress(self.state, sid, 10)
        self.assertEqual(self.state["charging_schedules"][0]["progress"], 0)


if __name__ == "__main__":
    unittest.main()
