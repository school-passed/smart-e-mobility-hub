"""In-memory shared application state for the Smart E-Mobility Hub MVP.

The store is process-wide: all Streamlit browser sessions connected to this
single Python process see the same demo data. It is NOT durable storage. Data
is reset when the app process restarts. Do not deploy multiple workers for
this MVP because each worker would have its own in-memory copy.

Each SUB may read shared data but should only change data it owns, preferably
through the owning SUB's service functions.
"""

from __future__ import annotations

from datetime import datetime
from functools import wraps
from threading import RLock
from typing import Any

STATE_LOCK = RLock()


def atomic(operation):
    """Serialize commands from different Streamlit sessions in this MVP process."""

    @wraps(operation)
    def run(*args, **kwargs):
        with STATE_LOCK:
            return operation(*args, **kwargs)

    return run


def _to_timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except (TypeError, ValueError):
        return None


def available_vehicle(state: dict[str, Any], vehicle: dict[str, Any]) -> bool:
    return (
        vehicle["status"] == "AVAILABLE"
        and not vehicle.get("incident_blocked")
        and not any(
            order["status"] == "TRANSITING" and vehicle["vehicle_id"] in order["vehicle_ids"]
            for order in state["dispatch_orders"]
        )
    )


def incoming_spaces(state: dict[str, Any], exclude_order_id: str | None = None) -> set[str]:
    return {
        sid
        for order in state["dispatch_orders"]
        if order["status"] == "TRANSITING" and order["order_id"] != exclude_order_id
        for sid in order.get("space_ids", [])
    }


def free_spaces(
    state: dict[str, Any], hub_id: str, exclude_order_id: str | None = None
) -> list[dict[str, Any]]:
    from modules.sub03.service import clean_expired_holds

    clean_expired_holds(state)
    held = {hold["space_id"] for hold in state["temporary_holds"]}
    held.update(incoming_spaces(state, exclude_order_id))
    return [
        p
        for p in state["parking_spaces"]
        if p["hub_id"] == hub_id
        and p["status"] == "AVAILABLE"
        and not p.get("incident_blocked")
        and p["space_id"] not in held
    ]


def release_vehicle_space(state: dict[str, Any], vehicle_id: str) -> None:
    for space in state["parking_spaces"]:
        if space.get("vehicle_id") == vehicle_id:
            space.pop("vehicle_id", None)
            space["status"] = "UNAVAILABLE" if space.get("incident_blocked") else "AVAILABLE"


def point_validity(point: dict[str, Any], now: datetime | None = None) -> str:
    quality = point.get("data_validity", "VALID")
    if quality != "VALID" or not point.get("data_updated_at"):
        return quality
    last_ts = _to_timestamp(point.get("data_updated_at"))
    if last_ts is None:
        return "DISCONNECTED"
    now_ts = (now or datetime.now().astimezone()).timestamp()
    return "DISCONNECTED" if (now_ts - last_ts) > 1800 else "VALID"


def hub_validity(
    state: dict[str, Any], hub: dict[str, Any], now: datetime | None = None
) -> str:
    quality = hub.get("data_validity", "VALID")
    if quality != "VALID":
        return quality
    if hub.get("data_updated_at"):
        last_ts = _to_timestamp(hub.get("data_updated_at"))
        if last_ts is None:
            return "DISCONNECTED"
        now_ts = (now or datetime.now().astimezone()).timestamp()
        if (now_ts - last_ts) > 1800:
            return "STALE"
    points = [p for p in state.get("charging_points", []) if p.get("hub_id") == hub["hub_id"]]
    point_states = {point_validity(p, now) for p in points}
    if "DISCONNECTED" in point_states:
        return "DISCONNECTED"
    if "STALE" in point_states:
        return "STALE"
    return "VALID"


def record_audit_log(
    state: dict[str, Any],
    actor: str,
    action: str,
    details: str,
    hub_id: str | None = None,
) -> dict[str, Any]:
    """Append an operational audit log entry (SUB-05 / NFR 3.1.5 Auditability)."""
    logs = state.setdefault("audit_logs", [])
    entry = {
        "log_id": f"LOG-{len(logs) + 1:04d}",
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "actor": actor or "SYSTEM",
        "action": action,
        "hub_id": hub_id,
        "details": details,
    }
    logs.append(entry)
    if len(logs) > 250:
        del logs[:-250]
    return entry


_STORE: dict[str, Any] | None = None
_SANDBOX_STORE: dict[str, Any] | None = None

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
    # Realistic heterogeneous fleet distribution across 5 Hubs (Submission 2 Hình 50 & Hình 55):
    # - HUB-01 (Metro): 6/10 available
    # - HUB-02 (Dorm A): 6/10 available
    # - HUB-03 (HCMUT): 8/10 available (high vehicle supply)
    # - HUB-04 (UIT): 0/10 available (out of shared vehicles -> filtered by 'Còn xe')
    # - HUB-05 (Central/Dorm B): 2/10 available ('Sắp hết xe')
    hub_vehicle_statuses = {
        "HUB-01": [
            "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE",
            "AVAILABLE", "IN_USE", "IN_USE", "CHARGING", "UNAVAILABLE",
        ],
        "HUB-02": [
            "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE",
            "AVAILABLE", "IN_USE", "IN_USE", "CHARGING", "UNAVAILABLE",
        ],
        "HUB-03": [
            "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE", "AVAILABLE",
            "AVAILABLE", "AVAILABLE", "AVAILABLE", "IN_USE", "CHARGING",
        ],
        "HUB-04": [
            "IN_USE", "IN_USE", "IN_USE", "IN_USE", "IN_USE",
            "IN_USE", "IN_USE", "CHARGING", "CHARGING", "UNAVAILABLE",
        ],
        "HUB-05": [
            "AVAILABLE", "AVAILABLE", "IN_USE", "IN_USE", "IN_USE",
            "IN_USE", "IN_USE", "CHARGING", "CHARGING", "UNAVAILABLE",
        ],
    }
    battery_values = [95, 88, 82, 76, 69, 61, 54, 43, 32, 18]
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        v_statuses = hub_vehicle_statuses[hub_id]
        for local_index in range(10):
            number = hub_index * 10 + local_index + 1
            vehicle_type = "ELECTRIC_BICYCLE" if local_index % 2 == 0 else "ELECTRIC_MOTORCYCLE"
            vehicles.append(
                {
                    "vehicle_id": f"EV-{number:03d}",
                    "hub_id": hub_id,
                    "vehicle_type": vehicle_type,
                    "battery_level": battery_values[local_index],
                    "status": v_statuses[local_index],
                }
            )

    # Parking availability per Hub:
    # - HUB-01: 14/20 free | HUB-02: 16/20 free | HUB-03: 11/20 free
    # - HUB-04: 18/20 free | HUB-05: 0/20 free (full parking -> filtered by 'Còn chỗ đỗ')
    hub_parking_profiles = {
        "HUB-01": (14, 17, 19),  # 14 AVAILABLE, 3 RESERVED, 2 IN_USE, 1 UNAVAILABLE
        "HUB-02": (16, 17, 19),  # 16 AVAILABLE, 1 RESERVED, 2 IN_USE, 1 UNAVAILABLE
        "HUB-03": (11, 15, 19),  # 11 AVAILABLE, 4 RESERVED, 4 IN_USE, 1 UNAVAILABLE
        "HUB-04": (18, 19, 19),  # 18 AVAILABLE, 1 RESERVED, 0 IN_USE, 1 UNAVAILABLE
        "HUB-05": (0, 6, 19),    # 0 AVAILABLE,  6 RESERVED, 13 IN_USE, 1 UNAVAILABLE
    }
    parking_spaces = []
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        avail_end, res_end, in_use_end = hub_parking_profiles[hub_id]
        avail_veh_ids = [
            v["vehicle_id"]
            for v in vehicles
            if v["hub_id"] == hub_id and v["status"] == "AVAILABLE"
        ]
        linked_idx = 0
        for local_index in range(20):
            number = hub_index * 20 + local_index + 1
            space_record: dict[str, Any] = {
                "space_id": f"PS-{number:03d}",
                "hub_id": hub_id,
                "has_charger": local_index % 3 == 0,
            }
            if local_index < avail_end:
                space_record["status"] = "AVAILABLE"
            elif local_index < res_end:
                space_record["status"] = "RESERVED"
            elif local_index < in_use_end:
                space_record["status"] = "IN_USE"
                # Link up to 2 parked AVAILABLE vehicles so pickup/dispatch frees origin hub stall cleanly
                if linked_idx < min(2, len(avail_veh_ids)):
                    space_record["vehicle_id"] = avail_veh_ids[linked_idx]
                    linked_idx += 1
            else:
                space_record["status"] = "UNAVAILABLE"
            parking_spaces.append(space_record)

    # Charging point availability per Hub:
    # - HUB-01: 2/4 free | HUB-02: 3/4 free | HUB-03: 3/4 free
    # - HUB-04: 1/4 free | HUB-05: 0/4 free (all busy/faulty -> filtered by 'Có cổng sạc')
    hub_charger_statuses = {
        "HUB-01": ["AVAILABLE", "AVAILABLE", "IN_USE", "UNAVAILABLE"],
        "HUB-02": ["AVAILABLE", "AVAILABLE", "AVAILABLE", "IN_USE"],
        "HUB-03": ["AVAILABLE", "AVAILABLE", "AVAILABLE", "IN_USE"],
        "HUB-04": ["AVAILABLE", "IN_USE", "IN_USE", "UNAVAILABLE"],
        "HUB-05": ["IN_USE", "IN_USE", "IN_USE", "UNAVAILABLE"],
    }
    charging_points = []
    for hub_index, (hub_id, _, _, _) in enumerate(HUB_SEEDS):
        cp_statuses = hub_charger_statuses[hub_id]
        for local_index in range(4):
            number = hub_index * 4 + local_index + 1
            charging_points.append(
                {
                    "charging_point_id": f"CP-{number:03d}",
                    "hub_id": hub_id,
                    "status": cp_statuses[local_index],
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
        "temporary_holds": [],
        "charging_points": charging_points,
        "charging_requests": [],        # Private EV (SUB-03 -> SUB-04)
        "shared_charging_requests": [], # Shared EV (SUB-02 -> SUB-04)
        "charging_schedules": [],
        "dispatch_orders": [],
        "incidents": [],
        "audit_logs": [],
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


def get_sandbox_store() -> dict[str, Any]:
    """Return isolated simulation sandbox store (Submission 3 simulation_sandbox)."""
    global _SANDBOX_STORE
    if _SANDBOX_STORE is None:
        _SANDBOX_STORE = {"sessions": [], "results": [], "next_session_number": 1}
    return _SANDBOX_STORE


def reset_state() -> dict[str, Any]:
    """Reset demo data and isolated sandbox store."""
    global _STORE, _SANDBOX_STORE
    _STORE = _seed_data()
    _SANDBOX_STORE = {"sessions": [], "results": [], "next_session_number": 1}
    return _STORE
