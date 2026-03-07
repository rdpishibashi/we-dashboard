"""
Response Manager for 共有したいこと comment responses.

Manages reading/writing responses from/to a Google Sheet.
Responses are cached in st.session_state to minimize API calls,
and invalidated immediately after writes.
"""

import hashlib
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Google Sheet column order
RESPONSE_COLUMNS = [
    "year_month",       # Comment's year_month (e.g., "2026-03")
    "member_email",     # Comment author's email
    "comment",          # Original comment text
    "responder_account", # Responder's login account name
    "responder_name",   # Responder's display name
    "response_text",    # Response content
    "responded_at",     # ISO timestamp of response
]

CACHE_KEY = "_response_cache"
SHEET_NAME = "responses"


def _get_gspread_client() -> gspread.Client:
    """Get authenticated gspread client using Streamlit secrets."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    return gspread.authorize(creds)


def _get_worksheet() -> gspread.Worksheet:
    """Get the responses worksheet."""
    client = _get_gspread_client()
    sheet_id = st.secrets["RESPONSE_SHEET_ID"]
    spreadsheet = client.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(RESPONSE_COLUMNS))
        worksheet.append_row(RESPONSE_COLUMNS)
    return worksheet


def load_responses() -> pd.DataFrame:
    """
    Load all responses from the Google Sheet.

    Uses session_state cache to avoid repeated API calls within a session.
    Returns empty DataFrame with correct columns if sheet is empty or on error.
    """
    if CACHE_KEY in st.session_state:
        return st.session_state[CACHE_KEY]

    try:
        worksheet = _get_worksheet()
        records = worksheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
        else:
            df = pd.DataFrame(columns=RESPONSE_COLUMNS)
    except Exception as e:
        st.warning(f"返信データの読み込みに失敗しました: {e}")
        df = pd.DataFrame(columns=RESPONSE_COLUMNS)

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
    Post a response to a comment by appending a row to the Google Sheet.

    Args:
        year_month: The comment's year_month
        member_email: The comment author's email address
        comment: The original comment text
        responder_account: Responder's login account
        responder_name: Responder's display name
        response_text: The response content

    Returns:
        True if successful, False otherwise
    """
    try:
        worksheet = _get_worksheet()
        row = [
            year_month,
            member_email,
            comment,
            responder_account,
            responder_name,
            response_text,
            datetime.now().isoformat(),
        ]
        worksheet.append_row(row, value_input_option="RAW")

        # Invalidate cache
        if CACHE_KEY in st.session_state:
            del st.session_state[CACHE_KEY]

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
    Get all responses for a specific comment.

    Args:
        responses_df: DataFrame of all responses (from load_responses)
        year_month: The comment's year_month
        member_email: The comment author's email
        comment: The original comment text

    Returns:
        DataFrame of matching responses, sorted by responded_at
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
    Create an MD5 hash key for unique widget identification.

    Args:
        year_month: The comment's year_month
        member_email: The comment author's email
        comment: The comment text

    Returns:
        Short MD5 hash string
    """
    raw = f"{year_month}|{member_email}|{comment}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]
