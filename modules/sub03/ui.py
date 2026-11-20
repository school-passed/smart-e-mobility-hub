"""Starter UI for SUB-03. M3 replaces this placeholder with parking/charging screens."""

import streamlit as st


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-03 · Private EV Parking & Charging")
    st.caption("UC-06-01 · UC-06-02 · UC-06-03 · UC-07-01 · UC-07-02")
    st.info("TODO – M3: implement parking reservation, check-in/check-out and charging request screens.")
    st.write("SUB-03 owns ParkingSpace, ParkingReservation and ChargingRequest.")
    st.write("Simulate sensor check-in/check-out using UI buttons. Submit ChargingRequest to SUB-04; do not allocate charging points here.")
