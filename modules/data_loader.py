"""
Data Loading Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
import streamlit as st

from .config import ENGAGEMENT_DIVISOR, COMPONENT_DIVISOR


def get_excel_password():
    """
    Get Excel password for input files.

    When modules/windows_config.py exists (local standalone mode, git-ignored),
    reads from it. Otherwise reads from Streamlit secrets (Cloud deployment).

    Returns:
        Password string or None if not configured
    """
    try:
        from modules import windows_config
        return windows_config.EXCEL_PASSWORD
    except ImportError:
        pass
    try:
        return st.secrets.get("EXCEL_PASSWORD")
    except (AttributeError, FileNotFoundError):
        return None


def decrypt_excel_if_needed(file_obj):
    """
    Return a readable BytesIO for an Excel file, decrypting if needed.

    - パスワード保護あり → 設定済みパスワードで復号して返す
    - パスワード保護なし → そのまま返す

    Args:
        file_obj: File object (UploadedFile / BytesIO) or path string

    Returns:
        BytesIO ready for pd.read_excel()

    Raises:
        ValueError: If the file is encrypted but decryption fails
    """
    import io
    import msoffcrypto

    if isinstance(file_obj, str):
        with open(file_obj, 'rb') as f:
            file_data = io.BytesIO(f.read())
    else:
        file_obj.seek(0)
        file_data = io.BytesIO(file_obj.read())

    # Check whether the file is encrypted
    office_file = msoffcrypto.OfficeFile(file_data)
    if not office_file.is_encrypted():
        file_data.seek(0)
        return file_data

    # File is encrypted — decrypt with configured password
    password = get_excel_password()
    if not password:
        raise ValueError(
            "Excelファイルはパスワード保護されていますが、パスワードが設定されていません。"
            "Streamlit Cloud の場合は App Settings → Secrets に "
            "EXCEL_PASSWORD を設定してください。"
        )

    try:
        file_data.seek(0)
        office_file = msoffcrypto.OfficeFile(file_data)
        office_file.load_key(password=password)
        decrypted = io.BytesIO()
        office_file.decrypt(decrypted)
        decrypted.seek(0)
        return decrypted
    except Exception as e:
        raise ValueError(f"Excelファイルの復号化に失敗しました。パスワードが正しくない可能性があります。({e})")


@st.cache_data
def load_data(uploaded_file, file_fingerprint=None):
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

    # Open Excel file once and read all sheets from it
    xls = pd.ExcelFile(decrypted_file, engine='openpyxl')

    # Load rating2 sheet (sole data source for both signal_df and pivot_df)
    if 'rating2' not in xls.sheet_names:
        raise ValueError("rating2シートが見つかりません。")
    signal_raw_df = pd.read_excel(xls, sheet_name='rating2')

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
    # These working columns always reflect the CURRENT affiliation — org_basis.py
    # (applied post-cache, per the 組織・職位 toggle) is what may later overwrite
    # them with their at-survey counterparts.
    signal_df['division'] = get_signal_column('current_division')     # 部門 (Division)
    signal_df['department'] = get_signal_column('current_department') # 部署 (Department)
    signal_df['section'] = get_signal_column('current_section')       # 課 (Section)
    signal_df['team'] = get_signal_column('current_team')
    signal_df['project'] = get_signal_column('current_project')
    # grade は rating2 の 'grade' 列自体が当時値（その行の year/month 時点の等級）を保持する
    # よう2026-09に修正された。ダッシュボードでは他の組織属性と同じく「現在の等級」で
    # 集計したいため、対になる current_grade 列（無ければ None → 下の fillna で '未設定'）を読む。
    signal_df['grade'] = get_signal_column('current_grade')
    signal_df['flag_constant_6m'] = get_signal_column('flag_constant_6m')

    # Pinned current-affiliation copies. org_basis.py only overwrites the working
    # columns above; privilege scoping (division_current/department_current/
    # section_current/grade_current — see docs/PRIVILEGE_SYSTEM.md "権限は現在値固定")
    # and the 個人 tab profile (all six — see docs/ORG_BASIS_TOGGLE.md, profile
    # always shows current) must keep reading the current affiliation regardless
    # of the toggle.
    signal_df['division_current'] = signal_df['division']
    signal_df['department_current'] = signal_df['department']
    signal_df['section_current'] = signal_df['section']
    signal_df['team_current'] = signal_df['team']
    signal_df['project_current'] = signal_df['project']
    signal_df['grade_current'] = signal_df['grade']

    # At-survey (measured-at-the-time) values, kept separate from the working
    # columns above. Sourced from rating2's bare (non current_*) columns.
    signal_df['division_at'] = get_signal_column('division')
    signal_df['department_at'] = get_signal_column('department')
    signal_df['section_at'] = get_signal_column('section')
    signal_df['team_at'] = get_signal_column('team')
    signal_df['project_at'] = get_signal_column('project')
    signal_df['grade_at'] = get_signal_column('grade')

    # Fill missing values for organizational columns
    fill_cols = [
        'division', 'department', 'section', 'team', 'project', 'grade',
        'division_current', 'department_current', 'section_current',
        'team_current', 'project_current', 'grade_current',
        'division_at', 'department_at', 'section_at', 'team_at', 'project_at', 'grade_at',
    ]
    for col in fill_cols:
        if col not in signal_df.columns:
            signal_df[col] = pd.Series([None] * len(signal_df))
        signal_df[col] = signal_df[col].fillna('未設定')

    # Derive pivot_df from signal_df by normalizing raw ratings
    # rating2 stores raw scores (0-54 for engagement, 0-18 for components);
    # dividing by the respective divisors produces the 0-10 scale.
    rating_cols = ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']
    id_cols = ['year', 'month', 'name', 'division', 'department', 'section',
               'team', 'project', 'grade',
               'division_current', 'department_current', 'section_current',
               'team_current', 'project_current', 'grade_current',
               'division_at', 'department_at', 'section_at', 'team_at', 'project_at', 'grade_at']
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
    if 'comment' not in xls.sheet_names:
        raise ValueError("commentシートが見つかりません。")
    comment_raw_df = pd.read_excel(xls, sheet_name='comment')

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
