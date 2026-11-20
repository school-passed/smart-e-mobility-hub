"""In-memory shared application state for the 9-day MVP.

The store is process-wide: all Streamlit browser sessions connected to this
single Python process see the same demo data. It is NOT durable storage. Data
is reset when the app process restarts. Do not deploy multiple workers for
this MVP because each worker would have its own in-memory copy.

Each SUB may read shared data but should only change data it owns, preferably
through the owning SUB's service functions.
"""

from __future__ import annotations

from typing import Any

_STORE: dict[str, Any] | None = None

HUB_SEEDS = [
    ("HUB-01", "Metro Station", "Ga Metro ĐHQG", 20),
    ("HUB-02", "Dormitory Zone", "Khu ký túc xá", 20),
    ("HUB-03", "HCMUT Campus", "Khuôn viên Bách Khoa", 20),
    ("HUB-04", "UIT Campus", "Khuôn viên UIT", 20),
    ("HUB-05", "Central Service Area", "Khu dịch vụ trung tâm", 20),
]


def _seed_data() -> dict[str, Any]:
    hubs = []
    for hub_id, name, address, parking_capacity in HUB_SEEDS:
        hubs.append(
            {
                "hub_id": hub_id,
                "name": name,
                "address": address,
                "reservation_capacity": 10,
                "reserved_slot_count": 0,
                "parking_capacity": parking_capacity,
            }
        )

    vehicles = []
    vehicle_statuses = [
        "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE",
        "AVAILABLE", "IN_USE", "IN_USE", "CHARGING", "UNAVAILABLE",
    ]
    battery_values = [95, 88, 82, 76, 69, 61, 54, 43, 32, 18]
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        for local_index in range(10):
            number = hub_index * 10 + local_index + 1
            vehicle_type = "ELECTRIC_BICYCLE" if local_index % 2 == 0 else "ELECTRIC_MOTORCYCLE"
            vehicles.append(
                {
                    "vehicle_id": f"EV-{number:03d}",
                    "hub_id": hub_id,
                    "vehicle_type": vehicle_type,
                    "battery_level": battery_values[local_index],
                    "status": vehicle_statuses[local_index],
                }
            )

    parking_spaces = []
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        for local_index in range(20):
            number = hub_index * 20 + local_index + 1
            if local_index < 14:
                status = "AVAILABLE"
            elif local_index < 17:
                status = "RESERVED"
            elif local_index < 19:
                status = "IN_USE"
            else:
                status = "UNAVAILABLE"
            parking_spaces.append(
                {
                    "space_id": f"PS-{number:03d}",
                    "hub_id": hub_id,
                    "has_charger": local_index % 3 == 0,
                    "status": status,
                }
            )

    charging_points = []
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        for local_index in range(4):
            number = hub_index * 4 + local_index + 1
            statuses = ["AVAILABLE", "AVAILABLE", "IN_USE", "UNAVAILABLE"]
            charging_points.append(
                {
                    "charging_point_id": f"CP-{number:03d}",
                    "hub_id": hub_id,
                    "status": statuses[local_index],
                    "power_kw": 7.0 if local_index % 2 == 0 else 3.5,
                }
            )

    return {
        "hubs": hubs,
        "vehicles": vehicles,
        "reservations": [],
        "trips": [],
        "parking_spaces": parking_spaces,
        "parking_reservations": [],
        "charging_points": charging_points,
        "charging_requests": [],
        "charging_schedules": [],
        "dispatch_orders": [],
        "incidents": [],
        "simulation_history": [],
        "next_trip_number": 1,
        "next_parking_reservation_number": 1,
        "next_charging_request_number": 1,
        "next_charging_schedule_number": 1,
        "next_dispatch_number": 1,
        "next_incident_number": 1,
    }


def get_state() -> dict[str, Any]:
    """Return the single shared in-memory data store, initializing it once."""
    global _STORE
    if _STORE is None:
        _STORE = _seed_data()
    return _STORE


def reset_state() -> dict[str, Any]:
    """Reset demo data. Intended for local development and demo preparation."""
    global _STORE
    _STORE = _seed_data()
    return _STORE
