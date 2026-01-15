"""
Data Loading Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
import streamlit as st


@st.cache_data
def load_data(uploaded_file):
    """
    Load and preprocess data file.

    Args:
        uploaded_file: File object or path to Excel file

    Returns:
        Tuple of (pivot_df, signal_df) - rating data and signal data

    Raises:
        ValueError: If required columns are missing or data is invalid
    """
    raw_df = pd.read_excel(uploaded_file, sheet_name='rating')
    required_cols = {'year', 'month', 'mail_address', 'name', 'factor', 'score'}
    missing_cols = required_cols - set(raw_df.columns)
    if missing_cols:
        raise ValueError(f"必要なカラムが不足しています: {', '.join(sorted(missing_cols))}")

    df = raw_df.copy()
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['month'] = pd.to_numeric(df['month'], errors='coerce')
    if df['year'].isna().any() or df['month'].isna().any():
        raise ValueError("year/monthの値に欠損が存在します。")
    df['year'] = df['year'].astype(int)
    df['month'] = df['month'].astype(int)

    def get_column(col_name):
        if col_name in raw_df.columns:
            return raw_df[col_name]
        return pd.Series([None] * len(raw_df))

    df['section'] = get_column('current_division')
    df['department'] = get_column('current_department')
    df['group'] = get_column('current_section')
    df['team'] = get_column('current_team')
    df['project'] = get_column('current_project')
    df['grade'] = get_column('grade')

    factor_map = {
        'エンゲージメント': 'engagement_rating',
        '活力': 'vigor_rating',
        '熱意': 'dedication_rating',
        '没頭': 'absorption_rating'
    }
    df['metric'] = df['factor'].map(factor_map)
    if df['metric'].isna().any():
        unknown = sorted(df.loc[df['metric'].isna(), 'factor'].dropna().unique())
        raise ValueError(f"未対応のfactor値があります: {', '.join(unknown)}")

    fill_cols = ['section', 'department', 'team', 'group', 'project', 'grade']
    for col in fill_cols:
        if col not in df.columns:
            df[col] = pd.Series([None] * len(df))
        df[col] = df[col].fillna('未設定')

    id_cols = ['year', 'month', 'mail_address', 'name', 'section', 'department', 'team', 'group', 'project', 'grade']
    pivot_df = (
        df[id_cols + ['metric', 'score']]
        .pivot_table(index=id_cols, columns='metric', values='score', aggfunc='mean')
        .reset_index()
    )
    pivot_df.columns.name = None

    pivot_df['year'] = pivot_df['year'].astype(int)
    pivot_df['month'] = pivot_df['month'].astype(int)

    for col in factor_map.values():
        if col not in pivot_df.columns:
            pivot_df[col] = np.nan

    pivot_df['year_month'] = (
        pivot_df['year'].astype(str) + '-' + pivot_df['month'].astype(str).str.zfill(2)
    )
    pivot_df['year_month_dt'] = pd.to_datetime(pivot_df['year_month'], format='%Y-%m', errors='coerce')

    # Load rating2 sheet for signal data
    try:
        signal_raw_df = pd.read_excel(uploaded_file, sheet_name='rating2')
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

    # Map to consistent column names
    signal_df['section'] = get_signal_column('current_division')
    signal_df['department'] = get_signal_column('current_department')
    signal_df['group'] = get_signal_column('current_section')
    signal_df['team'] = get_signal_column('current_team')
    signal_df['project'] = get_signal_column('current_project')
    signal_df['grade'] = get_signal_column('grade')

    # Fill missing values for organizational columns
    fill_cols = ['section', 'department', 'group', 'team', 'project', 'grade']
    for col in fill_cols:
        if col not in signal_df.columns:
            signal_df[col] = pd.Series([None] * len(signal_df))
        signal_df[col] = signal_df[col].fillna('未設定')

    # Load comment sheet for concern and comment data
    try:
        comment_raw_df = pd.read_excel(uploaded_file, sheet_name='comment')
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
