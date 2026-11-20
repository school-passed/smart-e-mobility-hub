"""Starter UI for SUB-04. M4 replaces this placeholder with charging management screens."""

import streamlit as st


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-04 · Smart Charging Management")
    st.caption("UC-08 Monitor Charging Resources · UC-09 Prioritize Charging Requests · UC-10 Schedule Charging")
    st.info("TODO – M4: implement charging resource dashboard, priority queue and schedule confirmation.")
    st.write("Apply agreed ordering: lower battery first, nearer expected use next, then FIFO. Separate requests with insufficient data.")
    st.write("Check point availability, time conflicts and Hub power capacity before confirming a schedule.")
