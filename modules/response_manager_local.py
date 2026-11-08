"""
Response Manager (Local Excel backend)
======================================
Manages reading/writing comment responses from/to a local Excel file:
  <project-root>/response.xlsx

Used when running on macOS or Windows (local execution).
On Streamlit Cloud (Linux), response_manager.py (Google Sheets) is used instead.

The file is password-protected with RESPONSE_PASSWORD (see _get_password for the
lookup order). Files written by older versions (encrypted with EXCEL_PASSWORD, or not
encrypted at all) are still read and are re-saved with the current password.
A file that exists but cannot be read is never overwritten.
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

def _response_password() -> str | None:
    """
    RESPONSE_PASSWORD: modules/windows_config.py (local standalone, git-ignored)
    first, otherwise st.secrets["RESPONSE_PASSWORD"]. Same lookup as
    data_loader.get_excel_password() uses for the input data file.
    """
    try:
        from modules import windows_config
        return windows_config.RESPONSE_PASSWORD
    except ImportError:
        pass
    try:
        return st.secrets.get("RESPONSE_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


def _legacy_password() -> str | None:
    """EXCEL_PASSWORD from secrets: what response.xlsx used before RESPONSE_PASSWORD."""
    try:
        return st.secrets.get("EXCEL_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


def _get_password() -> str | None:
    """
    Password used to encrypt response.xlsx: RESPONSE_PASSWORD, or EXCEL_PASSWORD
    when RESPONSE_PASSWORD is not configured anywhere (so a setup that has not been
    updated yet keeps the file encrypted instead of silently writing it in the clear).
    None only when neither is configured.
    """
    return _response_password() or _legacy_password()


# ---------------------------------------------------------------------------
# Low-level read / write with optional encryption
# ---------------------------------------------------------------------------

def _open_responses_file(path: Path) -> tuple[pd.DataFrame, bool]:
    """
    Read the responses file. Returns (df, needs_resave).

    Candidates, in order: the current password, then the legacy EXCEL_PASSWORD, then
    "not encrypted". needs_resave is True when the file was readable only through a
    legacy route (old password / unencrypted) while a current password is configured.
    Raises if the file cannot be read.
    """
    import msoffcrypto

    primary = _get_password()
    with open(path, "rb") as fh:
        raw = fh.read()

    office_file = msoffcrypto.OfficeFile(io.BytesIO(raw))
    if not office_file.is_encrypted():
        source, used = io.BytesIO(raw), None
    else:
        candidates = []
        for pw in (primary, _legacy_password()):
            if pw and pw not in candidates:
                candidates.append(pw)
        if not candidates:
            raise ValueError("返信ファイルはパスワード保護されていますが、パスワードが設定されていません")
        source, used = None, None
        for pw in candidates:
            try:
                office_file = msoffcrypto.OfficeFile(io.BytesIO(raw))
                office_file.load_key(password=pw)
                decrypted = io.BytesIO()
                office_file.decrypt(decrypted)
                decrypted.seek(0)
                source, used = decrypted, pw
                break
            except Exception:
                continue
        if source is None:
            raise ValueError("返信ファイルを復号できません（設定されたパスワードのいずれとも一致しません）")

    df = pd.read_excel(source, sheet_name=SHEET_NAME, engine="openpyxl")
    for col in RESPONSE_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[RESPONSE_COLUMNS], bool(primary) and used != primary


def _read_responses_file(path: Path) -> pd.DataFrame:
    """
    Read the responses Excel file for display.
    Returns an empty DataFrame (with correct columns) if the file is absent or
    cannot be read (a warning is shown). Never modifies a file it cannot read.
    A file readable only via a legacy route is re-saved with the current password.
    """
    if not path.exists():
        return pd.DataFrame(columns=RESPONSE_COLUMNS)

    try:
        df, needs_resave = _open_responses_file(path)
    except Exception as e:
        st.warning(f"返信データの読み込みに失敗しました: {e}")
        return pd.DataFrame(columns=RESPONSE_COLUMNS)

    if needs_resave:
        try:
            _write_responses_file(path, df)
        except Exception:
            pass
    return df


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
        if path.exists():
            # Strict: if the existing file cannot be read, stop rather than overwrite it
            # (an empty stand-in plus one new row would erase every earlier response).
            try:
                existing, _ = _open_responses_file(path)
            except Exception as e:
                raise RuntimeError(
                    f"既存の返信ファイルを読み込めないため、上書きを避けて中止しました: {e}"
                ) from e
        else:
            existing = pd.DataFrame(columns=RESPONSE_COLUMNS)
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
