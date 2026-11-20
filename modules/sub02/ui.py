"""Starter UI for SUB-02. M2 replaces this placeholder with UC-04 and UC-05."""

import streamlit as st


def render(state: dict, current_user: dict) -> None:
    st.title("SUB-02 · Vehicle Trip Lifecycle")
    st.caption("UC-04 Pick Up Shared Vehicle · UC-05 Return Shared Vehicle")
    st.info("TODO – M2: implement pickup and return screens.")
    st.write("Required flow: validate reservation and pickup code → set vehicle IN_USE → create Trip → consume reservation through SUB-01.")
    st.write("Return flow: select active Trip → choose return Hub → enter battery level → update vehicle state and charging demand when needed.")
