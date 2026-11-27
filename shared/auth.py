"""Authentication flows (Sign Up / Sign In / Sign Out) owned by M2.

Replaces the temporary role selector while keeping compatibility with app.py.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from shared.enums import (
    ROLE_OPERATOR,
    ROLE_PRIVATE_EV_STUDENT,
    ROLE_STUDENT,
)
from shared.state import get_state

AUTH_USER_KEY = "auth_current_user"
AUTH_MODE_KEY = "auth_mode"

# Public registration is restricted to student roles. Operator remains a seeded demo account.
VALID_ROLES = [ROLE_STUDENT, ROLE_PRIVATE_EV_STUDENT]

_DEFAULT_USERS: list[dict[str, str]] = [
    {
        "user_id": "STU-001",
        "username": "student",
        "password": "123",
        "role": ROLE_STUDENT,
        "display_name": "Demo Student",
    },
    {
        "user_id": "PSTU-001",
        "username": "pstudent",
        "password": "123",
        "role": ROLE_PRIVATE_EV_STUDENT,
        "display_name": "Demo Private EV Student",
    },
    {
        "user_id": "OP-001",
        "username": "operator",
        "password": "123",
        "role": ROLE_OPERATOR,
        "display_name": "Demo Operator",
    },
]


def _ensure_users(state: dict[str, Any]) -> list[dict[str, str]]:
    """Initialize process-wide user list inside shared state if missing."""
    if "users" not in state:
        state["users"] = [dict(u) for u in _DEFAULT_USERS]
    return state["users"]


def _generate_user_id(users: list[dict[str, str]], role: str) -> str:
    prefix = {
        ROLE_STUDENT: "STU",
        ROLE_PRIVATE_EV_STUDENT: "PSTU",
        ROLE_OPERATOR: "OP",
    }.get(role, "USR")
    count = sum(1 for u in users if u["user_id"].startswith(f"{prefix}-")) + 1
    return f"{prefix}-{count:03d}"


def sign_in(state: dict[str, Any], username: str, password: str) -> tuple[bool, str, dict[str, str] | None]:
    username = (username or "").strip().lower()
    password = (password or "").strip()
    if not username or not password:
        return False, "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.", None

    users = _ensure_users(state)
    user = next((u for u in users if u["username"].lower() == username), None)
    if user is None or user["password"] != password:
        return False, "Sai tên đăng nhập hoặc mật khẩu.", None

    session_user = {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "display_name": user["display_name"],
    }
    return True, f"Đăng nhập thành công ({user['display_name']}).", session_user


def sign_up(
    state: dict[str, Any],
    username: str,
    password: str,
    confirm_password: str,
    display_name: str,
    role: str,
) -> tuple[bool, str, dict[str, str] | None]:
    username = (username or "").strip().lower()
    password = (password or "").strip()
    confirm_password = (confirm_password or "").strip()
    display_name = (display_name or "").strip()

    if not username or not password or not display_name:
        return False, "Vui lòng điền đầy đủ thông tin bắt buộc.", None
    if len(password) < 3:
        return False, "Mật khẩu phải có ít nhất 3 ký tự.", None
    if password != confirm_password:
        return False, "Mật khẩu xác nhận không khớp.", None
    if role not in VALID_ROLES:
        return False, "Vai trò không hợp lệ.", None

    users = _ensure_users(state)
    if any(u["username"].lower() == username for u in users):
        return False, "Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác.", None

    new_user = {
        "user_id": _generate_user_id(users, role),
        "username": username,
        "password": password,
        "role": role,
        "display_name": display_name,
    }
    users.append(new_user)
    session_user = {
        "user_id": new_user["user_id"],
        "username": new_user["username"],
        "role": new_user["role"],
        "display_name": new_user["display_name"],
    }
    return True, f"Đăng ký thành công! Mã tài khoản: {new_user['user_id']}.", session_user


def sign_out() -> None:
    st.session_state.pop(AUTH_USER_KEY, None)


def render_auth(state: dict[str, Any] | None = None) -> dict[str, str] | None:
    """Render Sign In / Sign Up / Sign Out UI.

    When signed in, displays account info and Sign Out button in the sidebar
    and returns ``current_user``. When signed out, renders the Sign In / Sign Up
    screens in the main area and returns ``None``.
    """
    app_state = state if state is not None else get_state()
    _ensure_users(app_state)

    current_user: dict[str, str] | None = st.session_state.get(AUTH_USER_KEY)
    if current_user is not None:
        with st.sidebar:
            st.markdown("### Tài khoản")
            st.info(
                f"**{current_user['display_name']}**\n\n"
                f"ID: `{current_user['user_id']}` · Role: `{current_user['role']}`"
            )
            if st.button("Sign Out", use_container_width=True, key="auth_sign_out_btn"):
                sign_out()
                st.rerun()
        return current_user

    # Chưa đăng nhập: hiển thị màn hình Sign In / Sign Up
    st.title("Smart E-Mobility Hub · Authentication")
    tab_login, tab_signup = st.tabs(["Sign In (Đăng nhập)", "Sign Up (Đăng ký)"])

    with tab_login:
        with st.form("auth_signin_form"):
            username = st.text_input("Username", placeholder="student / pstudent / operator")
            password = st.text_input("Password", type="password", placeholder="123")
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        if submitted:
            ok, msg, user = sign_in(app_state, username, password)
            if ok and user is not None:
                st.session_state[AUTH_USER_KEY] = user
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        st.caption("Tài khoản demo nhanh (mật khẩu chung: `123`): `student`, `pstudent`, `operator`.")

    with tab_signup:
        with st.form("auth_signup_form"):
            new_display_name = st.text_input("Họ và tên hiển thị", placeholder="Nguyễn Văn A")
            new_username = st.text_input("Tên đăng nhập (Username)", placeholder="nguyenvana")
            new_role = st.selectbox("Vai trò (Role)", VALID_ROLES)
            new_password = st.text_input("Mật khẩu", type="password")
            confirm_password = st.text_input("Xác nhận mật khẩu", type="password")
            reg_submitted = st.form_submit_button("Sign Up", type="primary", use_container_width=True)
        if reg_submitted:
            ok, msg, user = sign_up(
                app_state,
                new_username,
                new_password,
                confirm_password,
                new_display_name,
                new_role,
            )
            if ok and user is not None:
                st.session_state[AUTH_USER_KEY] = user
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    return None


def render_demo_role_selector() -> dict[str, str]:
    """Backward-compatible entry point for app.py.

    Stops page rendering until the user signs in, then returns ``current_user``.
    """
    user = render_auth(get_state())
    if user is None:
        st.stop()
    return user
