"""
Authentication module for Work Engagement Dashboard
Provides login functionality with privilege-based access control
"""

import hashlib
import json
import base64
import pickle
import streamlit as st
from pathlib import Path
from typing import Optional, Union

# Authentication file paths
AUTH_FILE_JSON = Path(__file__).parent.parent / 'auth_users.json'
AUTH_FILE_DAT = Path(__file__).parent.parent / 'auth_users.dat'


def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256.

    Args:
        password: Plain text password

    Returns:
        SHA-256 hash of the password as hexadecimal string
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def load_auth_users() -> dict:
    """
    Load authenticated users from file.

    Tries to load from encoded .dat file first (production),
    falls back to .json file (development).

    Returns:
        Dictionary with 'users' list containing user credentials
    """
    try:
        # Production: Load from encoded .dat file
        if AUTH_FILE_DAT.exists():
            with open(AUTH_FILE_DAT, 'rb') as f:
                encoded_data = f.read()
                return pickle.loads(base64.b64decode(encoded_data))

        # Development: Load from JSON file
        if AUTH_FILE_JSON.exists():
            with open(AUTH_FILE_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)

        return {"users": []}

    except (json.JSONDecodeError, pickle.UnpicklingError, Exception) as e:
        st.warning(f"認証ファイルの読み込みに失敗しました: {e}")
        return {"users": []}


def get_user_data(username: str) -> Optional[dict]:
    """
    Get user data by username.

    Args:
        username: User's login name

    Returns:
        User dictionary with name, privilege, password_hash or None if not found
    """
    auth_data = load_auth_users()
    for user in auth_data.get("users", []):
        if user.get("name") == username:
            return user
    return None


def verify_login(username: str, password: str) -> Optional[dict]:
    """
    Verify username and password against stored credentials.

    Args:
        username: User's login name
        password: User's plain text password

    Returns:
        User data dict if credentials are valid, None otherwise
    """
    if not username or not password:
        return None

    auth_data = load_auth_users()
    password_hash = hash_password(password)

    for user in auth_data.get("users", []):
        if user.get("name") == username and user.get("password_hash") == password_hash:
            return user

    return None


def init_auth_state():
    """Initialize authentication state in session."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "current_user" not in st.session_state:
        st.session_state["current_user"] = None
    if "current_privilege" not in st.session_state:
        st.session_state["current_privilege"] = None


def is_authenticated() -> bool:
    """
    Check if the current user is authenticated.

    Returns:
        True if user is logged in, False otherwise
    """
    init_auth_state()
    return st.session_state.get("authenticated", False)


def get_current_user() -> Optional[str]:
    """
    Get the username of the currently logged-in user.

    Returns:
        Username string or None if not logged in
    """
    init_auth_state()
    return st.session_state.get("current_user")


def get_current_privilege() -> Optional[str]:
    """
    Get the privilege class of the currently logged-in user.

    Returns:
        Privilege string or None if not logged in
    """
    init_auth_state()
    return st.session_state.get("current_privilege")


def has_privilege(required_privileges: Union[list[str], str]) -> bool:
    """
    Check if the current user has any of the required privileges.

    Args:
        required_privileges: Single privilege string or list of privilege strings

    Returns:
        True if user has any of the required privileges, False otherwise
    """
    if not is_authenticated():
        return False

    current_privilege = get_current_privilege()
    if current_privilege is None:
        return False

    if isinstance(required_privileges, str):
        required_privileges = [required_privileges]

    return current_privilege in required_privileges


def login(username: str, privilege: Optional[str] = None):
    """
    Set the user as logged in.

    Args:
        username: The username to log in
        privilege: The user's privilege class
    """
    st.session_state["authenticated"] = True
    st.session_state["current_user"] = username
    st.session_state["current_privilege"] = privilege


def logout():
    """Log out the current user."""
    st.session_state["authenticated"] = False
    st.session_state["current_user"] = None
    st.session_state["current_privilege"] = None


def render_login_ui():
    """
    Render the login UI in the sidebar.

    Returns:
        True if login state changed (requires rerun), False otherwise
    """
    init_auth_state()

    if is_authenticated():
        with st.sidebar.expander("ログイン状態", expanded=False):
            user = get_current_user()
            privilege = get_current_privilege()
            st.success(f"ログイン中: {user} ({privilege})")
            if st.button("ログアウト", key="logout_button"):
                logout()
                return True
    else:
        with st.sidebar.expander("ログイン", expanded=False):
            username = st.text_input("ユーザー名", key="login_username")
            password = st.text_input("パスワード", type="password", key="login_password")

            if st.button("ログイン", key="login_button"):
                user_data = verify_login(username, password)
                if user_data:
                    login(username, user_data.get("privilege"))
                    st.success("ログインしました")
                    return True
                else:
                    st.error("ユーザー名またはパスワードが正しくありません")

    return False
