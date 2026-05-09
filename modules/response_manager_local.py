"""
Response Manager (Local Excel backend)
======================================
Manages reading/writing comment responses from/to a local Excel file:
  <project-root>/response.xlsx

Used when running on macOS or Windows (local execution).
On Streamlit Cloud (Linux), response_manager.py (Google Sheets) is used instead.

The file is password-protected when EXCEL_PASSWORD is configured in
.streamlit/secrets.toml. Uses the same password as the input data file.
"""

import hashlib
import io
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESPONSE_COLUMNS = [
    "year_month",        # Comment's year_month (e.g., "2026-03")
    "member_email",      # Comment author's email
    "comment",           # Original comment text
    "responder_account", # Responder's login account name
    "responder_name",    # Responder's display name
    "response_text",     # Response content
    "responded_at",      # ISO timestamp of response
]

CACHE_KEY = "_response_cache"
SHEET_NAME = "responses"


# ---------------------------------------------------------------------------
# File path
# ---------------------------------------------------------------------------

def _get_responses_path() -> Path:
    """Return the path to response.xlsx in the project root directory."""
    # modules/ is one level below the project root
    project_root = Path(__file__).parent.parent
    return project_root / "response.xlsx"


# ---------------------------------------------------------------------------
# Password helper
# ---------------------------------------------------------------------------

def _get_password() -> str | None:
    """
    Return the Excel password from Streamlit secrets, or None if not set.
    Uses the same secret key (EXCEL_PASSWORD) as the input data file.
    """
    try:
        return st.secrets.get("EXCEL_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Low-level read / write with optional encryption
# ---------------------------------------------------------------------------

def _read_responses_file(path: Path) -> pd.DataFrame:
    """
    Read the responses Excel file, decrypting if a password is configured.
    Returns an empty DataFrame (with correct columns) if the file is absent
    or cannot be read.
    """
    if not path.exists():
        return pd.DataFrame(columns=RESPONSE_COLUMNS)

    password = _get_password()
    try:
        with open(path, "rb") as fh:
            raw = io.BytesIO(fh.read())

        needs_migration = False
        if password:
            import msoffcrypto
            try:
                decrypted = io.BytesIO()
                office_file = msoffcrypto.OfficeFile(raw)
                office_file.load_key(password=password)
                office_file.decrypt(decrypted)
                decrypted.seek(0)
                source = decrypted
            except Exception:
                # Fall back to unencrypted file (migration case)
                raw.seek(0)
                source = raw
                needs_migration = True
        else:
            raw.seek(0)
            source = raw

        df = pd.read_excel(source, sheet_name=SHEET_NAME, engine="openpyxl")
        for col in RESPONSE_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[RESPONSE_COLUMNS]

        if needs_migration:
            try:
                _write_responses_file(path, df)
            except Exception:
                pass

        return df

    except Exception as e:
        st.warning(f"返信データの読み込みに失敗しました: {e}")
        return pd.DataFrame(columns=RESPONSE_COLUMNS)


def _write_responses_file(path: Path, df: pd.DataFrame) -> None:
    """
    Write df to the responses Excel file, encrypting if a password is configured.
    Raises on failure so the caller can surface the error.
    """
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    ws.append(RESPONSE_COLUMNS)
    for _, row in df.iterrows():
        ws.append([row.get(col, "") for col in RESPONSE_COLUMNS])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    password = _get_password()
    if password:
        import msoffcrypto
        encrypted = io.BytesIO()
        office_file = msoffcrypto.OfficeFile(buffer)
        office_file.encrypt(password, encrypted)
        encrypted.seek(0)
        data = encrypted.read()
    else:
        data = buffer.read()

    with open(path, "wb") as fh:
        fh.write(data)


# ---------------------------------------------------------------------------
# Public API (same interface as response_manager.py)
# ---------------------------------------------------------------------------

def load_responses() -> pd.DataFrame:
    """
    Load all responses from the local Excel file.

    Uses session_state cache to avoid repeated file I/O within a session.
    Returns an empty DataFrame with correct columns on error or if the file
    does not yet exist.
    """
    if CACHE_KEY in st.session_state:
        return st.session_state[CACHE_KEY]

    df = _read_responses_file(_get_responses_path())
    st.session_state[CACHE_KEY] = df
    return df


def post_response(
    year_month: str,
    member_email: str,
    comment: str,
    responder_account: str,
    responder_name: str,
    response_text: str,
) -> bool:
    """
    Append a new response row to the local Excel file.

    Returns True if successful, False otherwise.
    """
    path = _get_responses_path()
    try:
        existing = _read_responses_file(path)
        new_row = pd.DataFrame([{
            "year_month": year_month,
            "member_email": member_email,
            "comment": comment,
            "responder_account": responder_account,
            "responder_name": responder_name,
            "response_text": response_text,
            "responded_at": datetime.now().isoformat(),
        }])
        updated = pd.concat([existing, new_row], ignore_index=True)
        _write_responses_file(path, updated)
        st.session_state.pop(CACHE_KEY, None)
        return True

    except Exception as e:
        st.error(f"返信の送信に失敗しました: {e}")
        return False


def get_responses_for_comment(
    responses_df: pd.DataFrame,
    year_month: str,
    member_email: str,
    comment: str,
) -> pd.DataFrame:
    """
    Filter responses_df to rows matching the given comment identity.
    Returns matching rows sorted by responded_at (oldest first).
    """
    if responses_df.empty:
        return responses_df

    mask = (
        (responses_df["year_month"] == year_month)
        & (responses_df["member_email"] == member_email)
        & (responses_df["comment"] == comment)
    )
    result = responses_df[mask].copy()
    if not result.empty and "responded_at" in result.columns:
        result = result.sort_values("responded_at")
    return result


def make_comment_key(year_month: str, member_email: str, comment: str) -> str:
    """
    Create a short MD5 hash key for unique widget identification.
    Returns a 10-character hex string.
    """
    raw = f"{year_month}|{member_email}|{comment}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]
