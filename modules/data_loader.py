"""
Data Loading Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
import streamlit as st

from .config import ENGAGEMENT_DIVISOR, COMPONENT_DIVISOR


def get_excel_password():
    """
    Get Excel password from Streamlit secrets.

    Returns:
        Password string or None if not configured
    """
    try:
        return st.secrets.get("EXCEL_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


def decrypt_excel_if_needed(file_obj):
    """
    Decrypt Excel file if password-protected.

    Args:
        file_obj: File object or path to Excel file

    Returns:
        Decrypted file object (BytesIO) or original file object
    """
    import io
    import msoffcrypto

    password = get_excel_password()

    if password is None:
        # No password configured, return as-is
        return file_obj

    try:
        # Read file into memory
        if isinstance(file_obj, str):
            # It's a file path
            with open(file_obj, 'rb') as f:
                file_data = io.BytesIO(f.read())
        else:
            # It's already a file object
            file_data = io.BytesIO(file_obj.read())
            file_obj.seek(0)  # Reset for potential retry

        # Try to decrypt
        decrypted = io.BytesIO()
        office_file = msoffcrypto.OfficeFile(file_data)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted)
        decrypted.seek(0)

        return decrypted

    except Exception as e:
        error_msg = str(e).lower()
        if 'password' in error_msg or 'key' in error_msg:
            raise ValueError(f"Excelファイルのパスワードが正しくありません。管理者に連絡してください。")

        # File might not be encrypted, try returning original
        if isinstance(file_obj, str):
            return file_obj
        else:
            file_obj.seek(0)
            return file_obj


@st.cache_data
def load_data(uploaded_file):
    """
    Load and preprocess data file.
    Supports password-protected Excel files.

    Reads the rating2 sheet as the sole data source for both signal_df (raw
    scores + signal columns) and pivot_df (normalized 0-10 scale ratings).
    Also reads the comment sheet for comment data.

    Args:
        uploaded_file: File object or path to Excel file

    Returns:
        Tuple of (pivot_df, signal_df, comment_df) - normalized rating data,
        raw signal data, and comment data

    Raises:
        ValueError: If required columns are missing or data is invalid
    """
    # Decrypt file if password-protected
    try:
        decrypted_file = decrypt_excel_if_needed(uploaded_file)
    except ValueError:
        raise  # Re-raise password errors
    except Exception as e:
        raise ValueError(f"ファイルの処理中にエラーが発生しました: {e}")

    # Load rating2 sheet (sole data source for both signal_df and pivot_df)
    try:
        signal_raw_df = pd.read_excel(decrypted_file, sheet_name='rating2', engine='openpyxl')
    except Exception as e:
        raise ValueError(f"rating2シートの読み込みに失敗しました: {e}")

    signal_df = signal_raw_df.copy()
    signal_df['year'] = pd.to_numeric(signal_df['year'], errors='coerce')
    signal_df['month'] = pd.to_numeric(signal_df['month'], errors='coerce')
    if signal_df['year'].isna().any() or signal_df['month'].isna().any():
        raise ValueError("rating2シートのyear/monthの値に欠損が存在します。")
    signal_df['year'] = signal_df['year'].astype(int)
    signal_df['month'] = signal_df['month'].astype(int)

    signal_df['year_month'] = (
        signal_df['year'].astype(str) + '-' +
        signal_df['month'].astype(str).str.zfill(2)
    )
    signal_df['year_month_dt'] = pd.to_datetime(
        signal_df['year_month'], format='%Y-%m', errors='coerce'
    )

    def get_signal_column(col_name):
        if col_name in signal_raw_df.columns:
            return signal_raw_df[col_name]
        return pd.Series([None] * len(signal_raw_df))

    # Organizational structure mapping (current_* = current affiliation)
    # Hierarchy: Division (部門) → Department (部署) → Section (課)
    signal_df['division'] = get_signal_column('current_division')     # 部門 (Division)
    signal_df['department'] = get_signal_column('current_department') # 部署 (Department)
    signal_df['section'] = get_signal_column('current_section')       # 課 (Section)
    signal_df['team'] = get_signal_column('current_team')
    signal_df['project'] = get_signal_column('current_project')
    signal_df['grade'] = get_signal_column('grade')

    # Fill missing values for organizational columns
    fill_cols = ['division', 'department', 'section', 'team', 'project', 'grade']
    for col in fill_cols:
        if col not in signal_df.columns:
            signal_df[col] = pd.Series([None] * len(signal_df))
        signal_df[col] = signal_df[col].fillna('未設定')

    # Derive pivot_df from signal_df by normalizing raw ratings
    # rating2 stores raw scores (0-54 for engagement, 0-18 for components);
    # dividing by the respective divisors produces the 0-10 scale.
    rating_cols = ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']
    id_cols = ['year', 'month', 'name', 'division', 'department', 'section',
               'team', 'project', 'grade']
    if 'mail_address' in signal_df.columns:
        id_cols.insert(2, 'mail_address')

    pivot_df = signal_df[id_cols + rating_cols + ['year_month', 'year_month_dt']].copy()

    for col in rating_cols:
        if col not in pivot_df.columns:
            pivot_df[col] = np.nan
    pivot_df['engagement_rating'] = pivot_df['engagement_rating'] / ENGAGEMENT_DIVISOR
    pivot_df['vigor_rating'] = pivot_df['vigor_rating'] / COMPONENT_DIVISOR
    pivot_df['dedication_rating'] = pivot_df['dedication_rating'] / COMPONENT_DIVISOR
    pivot_df['absorption_rating'] = pivot_df['absorption_rating'] / COMPONENT_DIVISOR

    # Load comment sheet for concern and comment data
    try:
        comment_raw_df = pd.read_excel(decrypted_file, sheet_name='comment', engine='openpyxl')
    except Exception as e:
        raise ValueError(f"commentシートの読み込みに失敗しました: {e}")

    comment_df = comment_raw_df.copy()
    comment_df['year'] = pd.to_numeric(comment_df['year'], errors='coerce')
    comment_df['month'] = pd.to_numeric(comment_df['month'], errors='coerce')
    if comment_df['year'].isna().any() or comment_df['month'].isna().any():
        raise ValueError("commentシートのyear/monthの値に欠損が存在します。")
    comment_df['year'] = comment_df['year'].astype(int)
    comment_df['month'] = comment_df['month'].astype(int)

    comment_df['year_month'] = (
        comment_df['year'].astype(str) + '-' +
        comment_df['month'].astype(str).str.zfill(2)
    )
    comment_df['year_month_dt'] = pd.to_datetime(
        comment_df['year_month'], format='%Y-%m', errors='coerce'
    )

    return pivot_df, signal_df, comment_df
