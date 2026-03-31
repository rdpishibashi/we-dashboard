"""
Signal Data Processing Functions for Work Engagement Dashboard
"""

import pandas as pd
import streamlit as st
from .config import (
    ENGAGEMENT_DIVISOR, COMPONENT_DIVISOR,
    SIGNAL_LABELS, POSITIVE_TRENDS, NEGATIVE_TRENDS,
    INDIVIDUAL_SIGNAL_COLUMNS, DATAFRAME_KWARGS, LEVEL_LABELS,
    INTERVENTION_PRIORITY_THRESHOLD,
    FLAG_CONSTANT_LABELS, FLAG_CONSTANT_PRIORITY_POINTS,
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


def derive_intervention_priority(df):
    """
    Derive intervention_priority and _priority_is_neg from neg/pos columns.

    When both qualify (> INTERVENTION_PRIORITY_THRESHOLD), _neg takes precedence.
    The displayed value is raw - INTERVENTION_PRIORITY_THRESHOLD (minimum 1).

    Args:
        df: DataFrame with intervention_priority_neg and intervention_priority_pos columns

    Returns:
        DataFrame with added intervention_priority (derived) and _priority_is_neg (bool) columns
    """
    df = df.copy()
    neg = df['intervention_priority_neg'].fillna(0)
    pos = df['intervention_priority_pos'].fillna(0)

    # Add flag_constant_6m points to neg score
    if 'flag_constant_6m' in df.columns:
        flag_points = df['flag_constant_6m'].map(FLAG_CONSTANT_PRIORITY_POINTS).fillna(0)
        neg = neg + flag_points

    threshold = INTERVENTION_PRIORITY_THRESHOLD
    neg_qualifies = neg > threshold
    pos_qualifies = pos > threshold

    # _neg takes precedence when both qualify
    df['_priority_is_neg'] = neg_qualifies | (~pos_qualifies)
    # Select the raw value, then subtract threshold for display
    raw = neg.where(df['_priority_is_neg'], pos)
    df['intervention_priority'] = raw - threshold

    return df


def style_signal_columns(df, priority_is_neg):
    """
    Apply color styling to 介入必要度 column.

    - 介入必要度: red when from _neg, green when from _pos

    Args:
        df: Display DataFrame with 介入必要度 column
        priority_is_neg: Series of bools aligned with df index

    Returns:
        Styled DataFrame
    """
    is_neg = priority_is_neg.values
    priority_label = SIGNAL_LABELS['intervention_priority']

    def style_row(row):
        idx = row.name
        pos_idx = df.index.get_loc(idx)
        neg = is_neg[pos_idx]
        styles = [''] * len(row)

        for col_idx, col_name in enumerate(row.index):
            if col_name == priority_label:
                styles[col_idx] = 'color: red' if neg else 'color: green'

        return styles

    return df.style.apply(style_row, axis=1)


def format_signal_display_columns(df):
    """
    Format signal dataframe columns for display.

    Args:
        df: Signal dataframe with raw column values

    Returns:
        DataFrame with formatted values
    """
    df = df.copy()

    # Format intervention_priority as full-width integer
    if 'intervention_priority' in df.columns:
        df['intervention_priority'] = df['intervention_priority'].apply(
            lambda x: _to_fullwidth(f"{x:.0f}") if pd.notna(x) else "-"
        )

    # Format flag_constant_6m to Japanese label
    if 'flag_constant_6m' in df.columns:
        df['flag_constant_6m'] = df['flag_constant_6m'].apply(
            lambda x: FLAG_CONSTANT_LABELS.get(str(x), "-") if pd.notna(x) and str(x) else "-"
        )

    return df


def get_signal_column_config():
    """
    Get column configuration for signal tables.

    Returns:
        Dictionary of column configurations
    """
    priority_label = SIGNAL_LABELS['intervention_priority']
    return {
        priority_label: st.column_config.TextColumn(
            priority_label,
            width="small",
        ),
    }


def render_signal_table(signals, display_cols):
    """
    Render signal table with formatting and styling.

    Args:
        signals: Signal dataframe (with _priority_is_neg column)
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

    # Extract _priority_is_neg before creating display_df
    priority_is_neg = signals['_priority_is_neg'].reset_index(drop=True)

    # Prepare display dataframe
    display_df = signals[display_cols].copy().reset_index(drop=True)
    display_df = format_signal_display_columns(display_df)
    display_df = display_df.rename(columns=SIGNAL_LABELS)

    # Apply styling and display
    styled_df = style_signal_columns(display_df, priority_is_neg)
    st.dataframe(
        styled_df,
        column_config=get_signal_column_config(),
        **DATAFRAME_KWARGS
    )

    col1, col2, _ = st.columns([27, 27, 26])
    with col1:
        with st.popover("介入必要度について"):
            st.markdown(
                "中期傾向と短期傾向の内容によって、ケアやサポートの必要度合い、"
                "もしくは充実した状態の要因分析の必要度合いを示している。\n\n"
                "- **赤色の数値**: ネガティブな状態への介入（ケア・サポート）の必要度\n"
                "- **緑色の数値**: ポジティブな状態の要因分析の必要度\n\n"
                "大きな値ほど緊急度は高い。"
            )
    with col2:
        with st.popover("中期傾向について"):
            st.markdown(
                "| **中期傾向** | **説明** |\n"
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


def _to_fullwidth(s):
    """Convert ASCII digits to Japanese full-width digits."""
    return s.translate(str.maketrans('0123456789', '０１２３４５６７８９'))


def format_individual_signal_data(signal_data):
    """
    Format individual signal data for display.

    Args:
        signal_data: Individual signal dataframe

    Returns:
        Tuple of (formatted transposed dataframe, priority_is_neg bool)
    """
    # Derive intervention_priority from neg/pos columns
    signal_data = derive_intervention_priority(signal_data)
    priority_is_neg = signal_data['_priority_is_neg'].iloc[0]

    display_signal = signal_data[INDIVIDUAL_SIGNAL_COLUMNS].copy()

    # Process strength/weakness columns
    for col in ['strength_short', 'weakness_short', 'strength_mid', 'weakness_mid']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(replace_abbreviations)

    # Format intervention_priority: clamp to 0, full-width digits, neg/pos suffix
    # When value is 0, no suffix and no color (handled in app.py styling)
    if 'intervention_priority' in display_signal.columns:
        suffix = "(negative)" if priority_is_neg else "(positive)"

        def _fmt_priority(x):
            if pd.isna(x):
                return "-"
            val = max(int(x), 0)
            if val == 0:
                return _to_fullwidth("0")
            return f"{_to_fullwidth(str(val))} {suffix}"

        display_signal['intervention_priority'] = display_signal['intervention_priority'].apply(
            _fmt_priority
        )

    # Translate level values to Japanese
    if 'level' in display_signal.columns:
        display_signal['level'] = display_signal['level'].apply(
            lambda x: LEVEL_LABELS.get(str(x), str(x)) if pd.notna(x) else "-"
        )

    # Format other columns as strings
    for col in ['trend_recent', 'trend_refined', 'big_change', 'stability_6']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(
                lambda x: str(x) if pd.notna(x) else "-"
            )

    # Format flag_constant_6m to Japanese label
    if 'flag_constant_6m' in display_signal.columns:
        display_signal['flag_constant_6m'] = display_signal['flag_constant_6m'].apply(
            lambda x: FLAG_CONSTANT_LABELS.get(str(x), "-") if pd.notna(x) and str(x) else "-"
        )

    # Transpose for better display
    display_signal_t = display_signal.T
    display_signal_t.columns = ['値']
    display_signal_t.index = display_signal_t.index.map(
        lambda x: SIGNAL_LABELS.get(x, x)
    )
    display_signal_t.index.name = '指標'

    return display_signal_t, priority_is_neg


def sort_signals_by_trend_and_priority(signals):
    """
    Sort signal data by trend group, intervention_priority, and section (課).

    Sort order:
    1. Priority type (negative first, then positive)
    2. Intervention priority (descending)
    3. Trend group (negative trends first, then neutral, then positive)
    4. Section (課) - using configured order from group_order_config.json

    Args:
        signals: Signal dataframe with _priority_is_neg, section, trend_refined
                 and intervention_priority columns

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

    # Sort by priority type (neg first), priority value, trend group, then section
    signals = signals.sort_values(
        ['_priority_is_neg', 'intervention_priority', '_trend_group', '_section_order'],
        ascending=[False, False, True, True]
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
        Filtered signal dataframe for individuals exceeding INTERVENTION_PRIORITY_THRESHOLD
    """
    # Filter to latest wave
    latest_wave = signal_df[signal_df['year_month_dt'] == end_dt].copy()

    # Apply same filters as main data by matching on available individuals
    valid_names = filtered_df['name'].dropna().unique()
    latest_wave = latest_wave[latest_wave['name'].isin(valid_names)]

    # Filter to intervention priority exceeding threshold.
    # Threshold check uses raw neg/pos values (without flag_constant_6m bonus).
    # flag_constant_6m only boosts the displayed priority value for already-eligible persons.
    threshold = INTERVENTION_PRIORITY_THRESHOLD
    neg = latest_wave['intervention_priority_neg'].fillna(0)
    pos = latest_wave['intervention_priority_pos'].fillna(0)
    signals = latest_wave[(neg > threshold) | (pos > threshold)].copy()

    # Derive combined intervention_priority and _priority_is_neg
    signals = derive_intervention_priority(signals)

    # Sort by trend group and priority
    signals = sort_signals_by_trend_and_priority(signals)

    return signals
