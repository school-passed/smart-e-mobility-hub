"""Starter UI for SUB-06. M6 replaces this placeholder with simulation screens."""

import streamlit as st


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-06 · What-if Simulation")
    st.caption("UC-15 Select Scenario · UC-16 Run Simulation · UC-17 Evaluate Impact & Recommend Actions")
    st.info("TODO – M6: implement scenario selection, parameter inputs, simulation and recommendations.")
    st.write("Start with three demo scenarios: Metro arrivals surge, Hub near capacity, charging demand surge / charging point failure.")
    st.warning("Simulation must work on a copy/snapshot and must never overwrite operational state.")
