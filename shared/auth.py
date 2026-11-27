"""Authentication flows (Welcome / Sign Up / Sign In / Sign Out) owned by M2."""

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
AUTH_VIEW_KEY = "auth_screen_view"  # "welcome" | "signin" | "signup"

VALID_ROLES = [ROLE_STUDENT, ROLE_PRIVATE_EV_STUDENT]
MIN_PASSWORD_LENGTH = 8

_DEFAULT_USERS: list[dict[str, str]] = [
    {
        "user_id": "STU-001",
        "username": "student",
        "email": "student@vnu.edu.vn",
        "password": "123",
        "role": ROLE_STUDENT,
        "display_name": "Nguyễn Minh Khoa",
    },
    {
        "user_id": "PSTU-001",
        "username": "pstudent",
        "email": "pstudent@vnu.edu.vn",
        "password": "123",
        "role": ROLE_PRIVATE_EV_STUDENT,
        "display_name": "Trần Yến Linh",
    },
    {
        "user_id": "OP-001",
        "username": "operator",
        "email": "operator@vnu.edu.vn",
        "password": "123",
        "role": ROLE_OPERATOR,
        "display_name": "Đạt (Operator)",
    },
]

_AUTH_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background-color: #FFFFFF;
}
[data-testid="stHeader"] {
    background: transparent;
}
[data-testid="stMain"] .block-container {
    max-width: 430px;
    padding-top: 1.25rem;
    padding-bottom: 2.5rem;
}

button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"],
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background-color: #8CE600 !important;
    color: #0F172A !important;
    border: none !important;
    border-radius: 999px !important;
    font-weight: 800 !important;
    font-size: 0.96rem !important;
    min-height: 2.95rem !important;
    box-shadow: 0 4px 14px rgba(140, 230, 0, 0.28) !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background-color: #7ED100 !important;
    color: #0F172A !important;
}

button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"],
div[data-testid="stButton"] button[kind="secondary"],
div[data-testid="stFormSubmitButton"] button[kind="secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    font-size: 0.94rem !important;
    min-height: 2.9rem !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #8CE600 !important;
    background-color: #F7FEE7 !important;
}

div[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    background-color: #F8FAFC !important;
    min-height: 2.7rem;
}

.emob-welcome-banner {
    position: relative;
    height: 330px;
    border-radius: 22px;
    overflow: hidden;
    background:
        linear-gradient(180deg, rgba(15, 23, 42, 0.22) 0%, rgba(15, 23, 42, 0.58) 55%, rgba(15, 23, 42, 0.85) 100%),
        url("https://images.unsplash.com/photo-1519501025264-65ba15a82390?auto=format&fit=crop&w=900&q=80") center/cover no-repeat,
        linear-gradient(135deg, #064E3B 0%, #0F172A 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 26px 24px;
    margin-bottom: 18px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.14);
}
.emob-welcome-sub {
    color: #FFFFFF;
    font-size: 1.45rem;
    font-weight: 800;
    line-height: 1.2;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
}
.emob-welcome-brand {
    color: #8CE600;
    font-size: 1.65rem;
    font-weight: 900;
    line-height: 1.22;
    margin-top: 2px;
    text-shadow: 0 2px 12px rgba(0, 0, 0, 0.55);
}
.emob-welcome-prompt {
    text-align: center;
    color: #475569;
    font-size: 0.9rem;
    font-weight: 500;
    margin: 6px 0 14px 0;
}
.emob-page-heading {
    font-size: 1.65rem;
    font-weight: 800;
    color: #0F172A;
    margin: 8px 0 14px 0;
    letter-spacing: -0.02em;
}
.emob-demo-caption {
    text-align: center;
    font-size: 0.74rem;
    font-weight: 700;
    color: #94A3B8;
    margin: 14px 0 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
</style>
"""


def _ensure_users(state: dict[str, Any]) -> list[dict[str, str]]:
    if "users" not in state:
        state["users"] = [dict(u) for u in _DEFAULT_USERS]
    return state["users"]


def _generate_user_id(users: list[dict[str, str]], role: str) -> str:
    prefix = {
        ROLE_STUDENT: "STU",
        ROLE_PRIVATE_EV_STUDENT: "PSTU",
        ROLE_OPERATOR: "OP",
    }.get(role, "STU")
    count = sum(1 for u in users if u["user_id"].startswith(f"{prefix}-")) + 1
    return f"{prefix}-{count:03d}"


def sign_in(state: dict[str, Any], username: str, password: str) -> tuple[bool, str, dict[str, str] | None]:
    identifier = (username or "").strip().lower()
    password = (password or "").strip()
    if not identifier or not password:
        return False, "Vui lòng nhập đầy đủ Email và mật khẩu.", None

    users = _ensure_users(state)
    user = next(
        (
            u
            for u in users
            if u["username"].lower() == identifier or u.get("email", "").lower() == identifier
        ),
        None,
    )
    if user is None or user["password"] != password:
        return False, "Sai email hoặc mật khẩu.", None

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
    role: str = ROLE_STUDENT,
    dob: str = "",
) -> tuple[bool, str, dict[str, str] | None]:
    identifier = (username or "").strip().lower()
    password = (password or "").strip()
    confirm_password = (confirm_password or "").strip()
    display_name = (display_name or "").strip()

    if not identifier or not password or not display_name:
        return False, "Vui lòng điền đầy đủ Họ và tên, Email và Mật khẩu.", None
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự.", None
    if password != confirm_password:
        return False, "Mật khẩu xác nhận không khớp.", None
    if role not in VALID_ROLES:
        role = ROLE_STUDENT

    users = _ensure_users(state)
    if any(
        u["username"].lower() == identifier or u.get("email", "").lower() == identifier
        for u in users
    ):
        return False, "Email này đã được đăng ký. Vui lòng dùng email khác.", None

    new_user = {
        "user_id": _generate_user_id(users, role),
        "username": identifier,
        "email": identifier if "@" in identifier else f"{identifier}@vnu.edu.vn",
        "dob": (dob or "").strip(),
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
    st.session_state[AUTH_VIEW_KEY] = "welcome"


def _render_quick_demo_bar(app_state: dict[str, Any]) -> None:
    st.markdown('<div class="emob-demo-caption">⚡ Demo nhanh 1 chạm (Pass: 123)</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("🎓 Sinh viên (Demo)", use_container_width=True, key="quick_demo_stu"):
        _, _, user = sign_in(app_state, "student", "123")
        st.session_state[AUTH_USER_KEY] = user
        st.rerun()
    if c2.button("🛠️ Operator (Demo)", use_container_width=True, key="quick_demo_op"):
        _, _, user = sign_in(app_state, "operator", "123")
        st.session_state[AUTH_USER_KEY] = user
        st.rerun()


def render_auth(state: dict[str, Any] | None = None) -> dict[str, str] | None:
    """Render Welcome / Sign In / Sign Up / Sign Out UI."""
    app_state = state if state is not None else get_state()
    _ensure_users(app_state)

    current_user: dict[str, str] | None = st.session_state.get(AUTH_USER_KEY)
    if current_user is not None:
        if current_user.get("role") == ROLE_OPERATOR:
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

    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.session_state.setdefault(AUTH_VIEW_KEY, "welcome")
    view = st.session_state[AUTH_VIEW_KEY]

    # =========================================================================
    # MÀN HÌNH 1: WELCOME TO SMART E-MOBILITY HUB
    # =========================================================================
    if view == "welcome":
        st.markdown(
            """
            <div class="emob-welcome-banner">
                <div class="emob-welcome-sub">Welcome to</div>
                <div class="emob-welcome-brand">Smart E-mobility Hub</div>
            </div>
            <div class="emob-welcome-prompt">Đăng nhập hoặc đăng ký để tiếp tục</div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Tạo tài khoản mới", type="primary", use_container_width=True, key="welcome_goto_signup"):
            st.session_state[AUTH_VIEW_KEY] = "signup"
            st.rerun()

        st.write("")
        if st.button("Đã có tài khoản", type="secondary", use_container_width=True, key="welcome_goto_signin"):
            st.session_state[AUTH_VIEW_KEY] = "signin"
            st.rerun()

        _render_quick_demo_bar(app_state)

    # =========================================================================
    # MÀN HÌNH 2: TẠO TÀI KHOẢN MỚI (ĐÚNG 5 TRƯỜNG NHƯ THIẾT KẾ)
    # =========================================================================
    elif view == "signup":
        back_col, _ = st.columns([1, 5])
        if back_col.button("‹", key="signup_back_btn", use_container_width=True):
            st.session_state[AUTH_VIEW_KEY] = "welcome"
            st.rerun()

        st.markdown('<div class="emob-page-heading">Tạo tài khoản mới</div>', unsafe_allow_html=True)

        new_display_name = st.text_input("Họ và tên", placeholder="Nguyễn Văn A", key="su_name")
        new_dob = st.text_input("Ngày sinh", placeholder="DD/MM/YYYY", key="su_dob")
        new_email = st.text_input("Email", placeholder="yourname@email.com", key="su_email")
        new_password = st.text_input("Mật khẩu", type="password", placeholder="Tối thiểu 8 ký tự", key="su_pass")
        confirm_password = st.text_input(
            "Xác nhận mật khẩu", type="password", placeholder="Nhập lại mật khẩu", key="su_confirm"
        )
        agreed = st.checkbox("Tôi đồng ý với các **Điều khoản & Quy định**", value=False, key="su_terms")

        if st.button("Tạo tài khoản", type="primary", use_container_width=True, key="su_submit_btn"):
            if not agreed:
                st.error("Vui lòng đồng ý với các Điều khoản & Quy định.")
            else:
                ok, msg, user = sign_up(
                    app_state,
                    username=new_email,
                    password=new_password,
                    confirm_password=confirm_password,
                    display_name=new_display_name,
                    role=ROLE_STUDENT,
                    dob=new_dob,
                )
                if ok and user is not None:
                    st.session_state[AUTH_USER_KEY] = user
                    st.rerun()
                else:
                    st.error(msg)

        st.write("")
        f1, f2 = st.columns([1.4, 1])
        f1.markdown(
            '<div style="text-align:right;padding-top:10px;color:#64748B;font-size:0.88rem;">Đã có tài khoản?</div>',
            unsafe_allow_html=True,
        )
        if f2.button("Đăng nhập", type="secondary", key="su_switch_signin"):
            st.session_state[AUTH_VIEW_KEY] = "signin"
            st.rerun()

    # =========================================================================
    # MÀN HÌNH 3: ĐĂNG NHẬP
    # =========================================================================
    else:
        back_col, _ = st.columns([1, 5])
        if back_col.button("‹", key="signin_back_btn", use_container_width=True):
            st.session_state[AUTH_VIEW_KEY] = "welcome"
            st.rerun()

        st.markdown('<div class="emob-page-heading">Đăng nhập</div>', unsafe_allow_html=True)

        username = st.text_input(
            "Email",
            placeholder="yourname@email.com",
            key="si_user",
        )
        password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="Nhập mật khẩu của bạn",
            key="si_pass",
        )

        r1, r2 = st.columns([1.3, 1])
        r1.checkbox("Ghi nhớ đăng nhập", value=True, key="si_remember")
        r2.markdown(
            '<div style="text-align:right;padding-top:6px;font-size:0.84rem;font-weight:700;color:#0F172A;">Quên mật khẩu?</div>',
            unsafe_allow_html=True,
        )

        if st.button("Đăng nhập", type="primary", use_container_width=True, key="si_submit_btn"):
            ok, msg, user = sign_in(app_state, username, password)
            if ok and user is not None:
                st.session_state[AUTH_USER_KEY] = user
                st.rerun()
            else:
                st.error(msg)

        st.write("")
        f1, f2 = st.columns([1.4, 1])
        f1.markdown(
            '<div style="text-align:right;padding-top:10px;color:#64748B;font-size:0.88rem;">Chưa có tài khoản?</div>',
            unsafe_allow_html=True,
        )
        if f2.button("Đăng ký", type="secondary", key="si_switch_signup"):
            st.session_state[AUTH_VIEW_KEY] = "signup"
            st.rerun()

        _render_quick_demo_bar(app_state)

    return None


def render_demo_role_selector() -> dict[str, str]:
    """Backward-compatible entry point for app.py."""
    user = render_auth(get_state())
    if user is None:
        st.stop()
    return user