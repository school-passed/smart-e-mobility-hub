"""Starter UI for SUB-05. M5 replaces this placeholder with network operation screens."""

import streamlit as st


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-05 · Network Operation & Dispatch")
    st.caption("UC-11 Monitor Network · UC-12 Identify Near Capacity · UC-13 Redistribute Vehicles · UC-14 Handle Incident")
    st.info("TODO – M5: implement network dashboard, capacity warnings, dispatch and incident management.")
    st.write("Read resource state from owning SUBs. Do not edit their records directly.")
    st.write("Only dispatch eligible vehicles: not reserved, not IN_USE and not UNAVAILABLE; verify capacity at destination Hub.")
