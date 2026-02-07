"""
Signal Data Processing Functions for Work Engagement Dashboard
"""

import pandas as pd
import streamlit as st
from .config import (
    ENGAGEMENT_DIVISOR, COMPONENT_DIVISOR,
    SIGNAL_LABELS, POSITIVE_TRENDS, NEGATIVE_TRENDS,
    INDIVIDUAL_SIGNAL_COLUMNS, DATAFRAME_KWARGS
)


def apply_signal_rating_calculations(signal_df):
    """Apply rating divisor calculations to signal data."""
    signal_df = signal_df.copy()
    if 'engagement_rating' in signal_df.columns:
        signal_df['engagement_rating'] = signal_df['engagement_rating'] / ENGAGEMENT_DIVISOR
    for col in ['vigor_rating', 'dedication_rating', 'absorption_rating']:
        if col in signal_df.columns:
            signal_df[col] = signal_df[col] / COMPONENT_DIVISOR
    return signal_df


def style_trend_column(df):
    """
    Apply color styling to 中期トレンド column based on trend value.

    Args:
        df: DataFrame with 中期トレンド column

    Returns:
        Styled DataFrame with colored trend values
    """
    def color_trend(val):
        if pd.isna(val) or val == '' or val == '-':
            return ''
        val_str = str(val)
        if val_str in POSITIVE_TRENDS:
            return 'color: green'
        elif val_str in NEGATIVE_TRENDS:
            return 'color: red'
        return ''

    if '中期トレンド' in df.columns:
        return df.style.map(color_trend, subset=['中期トレンド'])
    return df


def format_signal_display_columns(df):
    """
    Format signal dataframe columns for display.

    Args:
        df: Signal dataframe with raw column values

    Returns:
        DataFrame with formatted values
    """
    df = df.copy()

    # Format intervention_priority as integer
    if 'intervention_priority' in df.columns:
        df['intervention_priority'] = df['intervention_priority'].apply(
            lambda x: f"{x:.0f}" if pd.notna(x) else "-"
        )

    return df


def get_signal_column_config():
    """
    Get column configuration for signal tables.

    Returns:
        Dictionary of column configurations
    """
    return {
        "介入優先度": st.column_config.TextColumn(
            "介入優先度",
            width="small",
        ),
    }


def render_signal_table(signals, display_cols):
    """
    Render signal table with formatting and styling.

    Args:
        signals: Signal dataframe
        display_cols: List of columns to display
    """
    if signals.empty:
        st.info("アクション対象候補はいません")
        return

    # Validate columns exist
    missing_cols = [col for col in display_cols if col not in signals.columns]
    if missing_cols:
        st.error(f"signal データに必要なカラムがありません: {', '.join(missing_cols)}")
        return

    # Prepare display dataframe
    display_df = signals[display_cols].copy()
    display_df = format_signal_display_columns(display_df)
    display_df = display_df.rename(columns=SIGNAL_LABELS)

    # Apply styling and display
    styled_df = style_trend_column(display_df)
    st.dataframe(
        styled_df,
        column_config=get_signal_column_config(),
        **DATAFRAME_KWARGS
    )

    col1, col2, _ = st.columns([27, 27, 26])
    with col1:
        with st.popover("介入優先度について"):
            st.markdown(
                "中期トレンドと短期変化の内容によって、状況分析に基づいたケアやサポート"
                "（ネガティブの場合）や充実した状態の要因分析（ポジティブの場合）の"
                "必要度合いを示している。大きな値ほど緊急度は高い。"
            )
    with col2:
        with st.popover("中期トレンドについて"):
            st.markdown(
                "| **中期トレンド** | **説明** |\n"
                "| --- | --- |\n"
                "| 上昇加速 | 上昇傾向の中、急上昇している |\n"
                "| 上昇継続 | 上昇傾向が継続している |\n"
                "| 復活 | 低下傾向もしくは安定から、以前よりも高い状態を超えて上昇している |\n"
                "| 回復 | 低下傾向もしくは安定から反転して、上昇している |\n"
                "| 上昇期待 | 安定から上昇となっている |\n"
                "| 低下懸念 | 上昇が頭打ちとなり、低下するおそれがある |\n"
                "| 回復期待 | 低下が一服し、上昇に転じることが期待される |\n"
                "| 低下警戒 | 安定していたが低下となっている |\n"
                "| 低下危機 | 上昇傾向もしくは安定から反転して、下降している |\n"
                "| 悪化 | 上昇傾向もしくは安定から、以前よりも低い状態よりも下降している |\n"
                "| 下降継続 | 下降傾向が継続している |\n"
                "| 下降加速 | 下降傾向の中、急激に落ち込んでいる |\n"
                "| 安定維持 | 安定した状態を維持している |"
            )


def replace_abbreviations(text):
    """
    Replace abbreviations in strength/weakness text.

    Args:
        text: Text with abbreviations (V, D, A)

    Returns:
        Text with full Japanese terms
    """
    if pd.isna(text) or not str(text).strip():
        return "-"
    text = str(text)
    text = text.replace("データなし", "-")
    text = text.replace("V", "活力")
    text = text.replace("D", "熱意")
    text = text.replace("A", "没頭")
    return text


def format_individual_signal_data(signal_data):
    """
    Format individual signal data for display.

    Args:
        signal_data: Individual signal dataframe

    Returns:
        Formatted and transposed dataframe
    """
    display_signal = signal_data[INDIVIDUAL_SIGNAL_COLUMNS].copy()

    # Process strength/weakness columns
    for col in ['strength_short', 'weakness_short', 'strength_mid', 'weakness_mid']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(replace_abbreviations)

    # Format intervention_priority as integer
    if 'intervention_priority' in display_signal.columns:
        display_signal['intervention_priority'] = display_signal['intervention_priority'].apply(
            lambda x: f"{x:.0f}" if pd.notna(x) else "-"
        )

    # Format other columns as strings
    for col in ['trend_refined', 'change_tag', 'stability']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(
                lambda x: str(x) if pd.notna(x) else "-"
            )

    # Transpose for better display
    display_signal_t = display_signal.T
    display_signal_t.columns = ['値']
    display_signal_t.index = display_signal_t.index.map(
        lambda x: SIGNAL_LABELS.get(x, x)
    )
    display_signal_t.index.name = 'Index'

    return display_signal_t


def sort_signals_by_trend_and_priority(signals):
    """
    Sort signal data by trend group, intervention_priority, and section (課).

    Sort order:
    1. Trend group (negative first, then neutral, then positive)
    2. Intervention priority (descending)
    3. Section (課) - using configured order from group_order_config.json

    Args:
        signals: Signal dataframe with section, trend_refined and intervention_priority columns

    Returns:
        Sorted signal dataframe
    """
    if signals.empty:
        return signals

    from .utils import GROUP_ORDER_MAP

    def get_trend_group(trend_value):
        """Classify trend into negative (0), neutral (1), or positive (2)."""
        if pd.isna(trend_value):
            return 1  # neutral
        trend_str = str(trend_value)
        if trend_str in NEGATIVE_TRENDS:
            return 0  # negative group first
        elif trend_str in POSITIVE_TRENDS:
            return 2  # positive group last
        return 1  # neutral in middle

    signals = signals.copy()
    signals['_trend_group'] = signals['trend_refined'].apply(get_trend_group)

    # Create section order index (use 'section' key from config for 'section' column)
    section_order = GROUP_ORDER_MAP.get('section', [])
    if section_order and 'section' in signals.columns:
        # Map section to order index, unknown sections go to end
        section_order_map = {name: idx for idx, name in enumerate(section_order)}
        signals['_section_order'] = signals['section'].apply(
            lambda x: section_order_map.get(x, len(section_order))
        )
    else:
        # Fallback to alphabetical order
        signals['_section_order'] = signals['section'] if 'section' in signals.columns else 0

    # Sort by trend group, intervention_priority, then section
    signals = signals.sort_values(
        ['_trend_group', 'intervention_priority', '_section_order'],
        ascending=[True, False, True]
    )

    # Drop temporary columns
    signals = signals.drop(columns=['_trend_group', '_section_order'])

    return signals


def get_signal_data(signal_df, filtered_df, end_dt):
    """
    Filter signal data to match current sidebar filters and latest wave.

    Args:
        signal_df: Full rating2 dataframe
        filtered_df: Currently filtered rating dataframe (from sidebar filters)
        end_dt: End date of global period filter (defines "latest wave")

    Returns:
        Filtered signal dataframe for individuals with intervention_priority > 1
    """
    # Filter to latest wave
    latest_wave = signal_df[signal_df['year_month_dt'] == end_dt].copy()

    # Apply same filters as main data by matching on available individuals
    valid_names = filtered_df['name'].dropna().unique()
    latest_wave = latest_wave[latest_wave['name'].isin(valid_names)]

    # Filter to intervention priority > 1
    signals = latest_wave[latest_wave['intervention_priority'] > 1].copy()

    # Sort by trend group and priority
    signals = sort_signals_by_trend_and_priority(signals)

    return signals
