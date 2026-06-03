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
    FLAG_CONSTANT_LABELS,
)


# =============================================================================
# Private helpers
# =============================================================================

def _to_fullwidth(s: str) -> str:
    """Convert ASCII digits to full-width digits."""
    return s.translate(str.maketrans('0123456789', '０１２３４５６７８９'))


def _fmt_flag_constant(x) -> str:
    """Translate a flag_constant_6m value to its Japanese display label."""
    if pd.isna(x) or not str(x):
        return "-"
    return FLAG_CONSTANT_LABELS.get(str(x), "-")


def _fmt_priority_table(x) -> str:
    """Format intervention_priority as a full-width integer for table display."""
    return _to_fullwidth(f"{x:.0f}") if pd.notna(x) else "-"


def _fmt_priority_individual(x, suffix: str) -> str:
    """Format intervention_priority with neg/pos suffix for the individual report.

    Returns '０' (no suffix, no color) when the clamped value is 0.
    """
    if pd.isna(x):
        return "-"
    val = max(int(x), 0)
    if val == 0:
        return _to_fullwidth("0")
    return f"{_to_fullwidth(str(val))} {suffix}"


# =============================================================================
# Core signal calculations
# =============================================================================

def _dash_if_empty(value):
    """空・NaN・None 相当は '-'、それ以外は文字列化（判定保留は合成側で 'n/a'）。"""
    if pd.isna(value):
        return "-"
    s = str(value).strip()
    return "-" if s in ("", "None", "nan") else s


def _mid_variability(direction, volatility):
    """中期変動性 = volatility_6_p90 × direction_6_p90 の合成（R4 マッピング）。"""
    d = "" if pd.isna(direction) else str(direction).strip()
    v = "" if pd.isna(volatility) else str(volatility).strip()
    if d in ("", "判定保留") or v in ("", "判定保留"):
        return "n/a"
    if v == "波動あり":
        return "波動あり" + d        # 波動あり下降 / 波動あり上昇 / 波動あり横ばい
    return "安定" if d == "横ばい" else "波動なし" + d  # 波動なし下降 / 波動なし上昇 / 安定


def add_mid_variability(signal_df):
    """direction_6_p90 × volatility_6_p90 から中期変動性カラム(mid_variability)を生成。"""
    signal_df = signal_df.copy()
    if 'direction_6_p90' in signal_df.columns and 'volatility_6_p90' in signal_df.columns:
        signal_df['mid_variability'] = [
            _mid_variability(d, v)
            for d, v in zip(signal_df['direction_6_p90'], signal_df['volatility_6_p90'])
        ]
    elif 'mid_variability' not in signal_df.columns:
        signal_df['mid_variability'] = 'n/a'   # 新カラム未提供（EngagementMasterSS 再エクスポート前）の暫定
    return signal_df


def apply_signal_rating_calculations(signal_df):
    """Apply rating divisor calculations to signal data."""
    signal_df = signal_df.copy()
    if 'engagement_rating' in signal_df.columns:
        signal_df['engagement_rating'] = signal_df['engagement_rating'] / ENGAGEMENT_DIVISOR
    for col in ['vigor_rating', 'dedication_rating', 'absorption_rating']:
        if col in signal_df.columns:
            signal_df[col] = signal_df[col] / COMPONENT_DIVISOR
    signal_df = add_mid_variability(signal_df)
    return signal_df


def derive_intervention_priority(df):
    """
    Derive intervention_priority and _priority_is_neg from neg/pos columns.

    Rules
    -----
    - intervention_priority_neg already includes flag_constant_6m bonus points,
      computed by Admin GAS before writing to rating2 sheet.
      The Dashboard does NOT add any flag bonus — flag_constant_6m is display-only here.
    - intervention_priority_pos has no flag adjustment.
    - When neg qualifies (> threshold), it takes precedence over pos.
    - When neither qualifies, _priority_is_neg defaults to True and the displayed
      value will be ≤ 0 (clamped to ０ in display formatters).
    - Displayed value = (neg or pos) − threshold.

    Returns the input DataFrame with two new columns:
      intervention_priority  – numeric score ready for display formatting
      _priority_is_neg       – bool, drives red/green coloring
    """
    df = df.copy()
    neg = df['intervention_priority_neg'].fillna(0)
    pos = df['intervention_priority_pos'].fillna(0)
    threshold = INTERVENTION_PRIORITY_THRESHOLD

    neg_qualifies = neg > threshold
    pos_qualifies = pos > threshold

    df['_priority_is_neg']     = neg_qualifies | (~pos_qualifies)
    df['intervention_priority'] = neg.where(df['_priority_is_neg'], pos) - threshold
    return df


def get_signal_data(signal_df, filtered_df, end_dt):
    """
    Filter signal data to the latest wave and derive display priority.

    The threshold filter uses neg/pos directly. intervention_priority_neg already
    includes flag_constant_6m bonus from Admin GAS — no Dashboard-side adjustment.

    Args:
        signal_df:   Full rating2 dataframe
        filtered_df: Currently filtered rating dataframe (defines visible individuals)
        end_dt:      End date of global period filter (defines "latest wave")

    Returns:
        Filtered and sorted signal dataframe for individuals exceeding the threshold
    """
    latest_wave = signal_df[signal_df['year_month_dt'] == end_dt].copy()

    valid_names = filtered_df['name'].dropna().unique()
    latest_wave = latest_wave[latest_wave['name'].isin(valid_names)]

    threshold = INTERVENTION_PRIORITY_THRESHOLD
    raw_neg = latest_wave['intervention_priority_neg'].fillna(0)
    raw_pos = latest_wave['intervention_priority_pos'].fillna(0)
    signals = latest_wave[(raw_neg > threshold) | (raw_pos > threshold)].copy()

    signals = derive_intervention_priority(signals)
    signals = add_mid_variability(signals)
    signals = sort_signals_by_trend_and_priority(signals)
    return signals


def sort_signals_by_trend_and_priority(signals):
    """
    Sort signal data by priority type → priority value → trend group → section.

    Sort order:
    1. Priority type  (negative first, then positive)
    2. Priority value (descending)
    3. Trend group    (negative trends → neutral → positive)
    4. Section (課)   (using configured order from group_order_config.json)
    """
    if signals.empty:
        return signals

    from .utils import GROUP_ORDER_MAP

    def _trend_group(trend_value):
        if pd.isna(trend_value):
            return 1
        s = str(trend_value)
        if s in NEGATIVE_TRENDS:
            return 0
        if s in POSITIVE_TRENDS:
            return 2
        return 1

    signals = signals.copy()
    signals['_trend_group'] = signals['trend_refined'].apply(_trend_group)

    section_order = GROUP_ORDER_MAP.get('section', [])
    if section_order and 'section' in signals.columns:
        order_map = {name: idx for idx, name in enumerate(section_order)}
        signals['_section_order'] = signals['section'].apply(
            lambda x: order_map.get(x, len(section_order))
        )
    else:
        signals['_section_order'] = signals['section'] if 'section' in signals.columns else 0

    signals = signals.sort_values(
        ['_priority_is_neg', 'intervention_priority', '_trend_group', '_section_order'],
        ascending=[False, False, True, True],
    )
    return signals.drop(columns=['_trend_group', '_section_order'])


# =============================================================================
# Display formatting
# =============================================================================

def replace_abbreviations(text) -> str:
    """Replace V/D/A abbreviations in strength/weakness text with Japanese terms."""
    if pd.isna(text) or not str(text).strip():
        return "-"
    text = str(text)
    text = text.replace("データなし", "-")
    text = text.replace("V", "活力")
    text = text.replace("D", "熱意")
    text = text.replace("A", "没頭")
    return text


def format_signal_display_columns(df):
    """Format intervention_priority and flag_constant_6m columns for table display."""
    df = df.copy()
    if 'intervention_priority' in df.columns:
        df['intervention_priority'] = df['intervention_priority'].apply(_fmt_priority_table)
    if 'flag_constant_6m' in df.columns:
        df['flag_constant_6m'] = df['flag_constant_6m'].apply(_fmt_flag_constant)
    # 短期変動(big_change)・変動パターン(mid_variability)・中期安定性(stability_6) の空値を "-" に
    for col in ['big_change', 'mid_variability', 'stability_6']:
        if col in df.columns:
            df[col] = df[col].apply(_dash_if_empty)
    return df


def format_individual_signal_data(signal_data):
    """
    Derive and format signal data for the individual report.

    Returns:
        Tuple of (transposed display DataFrame indexed by 指標, priority_is_neg bool)
    """
    signal_data = derive_intervention_priority(signal_data)
    priority_is_neg = signal_data['_priority_is_neg'].iloc[0]

    display_signal = signal_data[INDIVIDUAL_SIGNAL_COLUMNS].copy()

    for col in ['strength_short', 'weakness_short', 'strength_mid', 'weakness_mid']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(replace_abbreviations)

    if 'intervention_priority' in display_signal.columns:
        suffix = "(negative)" if priority_is_neg else "(positive)"
        display_signal['intervention_priority'] = display_signal['intervention_priority'].apply(
            lambda x: _fmt_priority_individual(x, suffix)
        )

    if 'level' in display_signal.columns:
        display_signal['level'] = display_signal['level'].apply(
            lambda x: LEVEL_LABELS.get(str(x), str(x)) if pd.notna(x) else "-"
        )

    for col in ['trend_recent', 'trend_base', 'trend_refined']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(
                lambda x: str(x) if pd.notna(x) else "-"
            )

    # 短期変動(big_change)・変動パターン(mid_variability)・中期安定性(stability_6): 空・None も "-" に
    for col in ['big_change', 'mid_variability', 'stability_6']:
        if col in display_signal.columns:
            display_signal[col] = display_signal[col].apply(_dash_if_empty)

    if 'flag_constant_6m' in display_signal.columns:
        display_signal['flag_constant_6m'] = display_signal['flag_constant_6m'].apply(_fmt_flag_constant)

    display_signal_t = display_signal.T
    display_signal_t.columns = ['値']
    display_signal_t.index = display_signal_t.index.map(lambda x: SIGNAL_LABELS.get(x, x))
    display_signal_t.index.name = '指標'
    return display_signal_t, priority_is_neg


# =============================================================================
# Streamlit rendering
# =============================================================================

def style_signal_columns(df, priority_is_neg):
    """Apply red/green coloring to the 介入必要度 column based on priority type."""
    is_neg = priority_is_neg.values
    priority_label = SIGNAL_LABELS['intervention_priority']

    def _style_row(row):
        pos_idx = df.index.get_loc(row.name)
        styles = [''] * len(row)
        for col_idx, col_name in enumerate(row.index):
            if col_name == priority_label:
                styles[col_idx] = 'color: red' if is_neg[pos_idx] else 'color: green'
        return styles

    return df.style.apply(_style_row, axis=1)


def render_signal_table(signals, display_cols, key=None):
    """Render the action-candidates signal table with formatting, styling, and help popovers.

    Returns the name of the selected person, or None if no row is selected.
    """
    if signals.empty:
        st.info("アクション対象候補はいません")
        return None

    missing_cols = [col for col in display_cols if col not in signals.columns]
    if missing_cols:
        st.error(f"signal データに必要なカラムがありません: {', '.join(missing_cols)}")
        return None

    signals_indexed = signals.reset_index(drop=True)
    priority_is_neg = signals_indexed['_priority_is_neg']
    display_df = signals_indexed[display_cols].copy()
    display_df = format_signal_display_columns(display_df)
    display_df = display_df.rename(columns=SIGNAL_LABELS)

    priority_label = SIGNAL_LABELS['intervention_priority']
    styled_df = style_signal_columns(display_df, priority_is_neg)

    # When the individual report was shown (_clear_action_selection flag set by
    # the 個人 tab), increment the shared version counter so ALL signal tables
    # get a new widget key → selection state resets automatically.
    # The first table to run in the rerun clears the flag; subsequent tables
    # read the already-incremented version, so all tables reset consistently.
    version = st.session_state.get("_signal_tables_version", 0)
    if st.session_state.pop("_clear_action_selection", False):
        version += 1
        st.session_state["_signal_tables_version"] = version

    effective_key = f"{key}_v{version}" if key else key

    big_change_label = SIGNAL_LABELS['big_change']
    stability_label = SIGNAL_LABELS['stability_6']
    flag_label = SIGNAL_LABELS['flag_constant_6m']

    event = st.dataframe(
        styled_df,
        column_config={
            priority_label: st.column_config.TextColumn(priority_label, width="small"),
            big_change_label: st.column_config.TextColumn(big_change_label, width=90),
            stability_label: st.column_config.TextColumn(stability_label, width="small"),
            flag_label: st.column_config.TextColumn(flag_label, width=150),
        },
        on_select="rerun",
        selection_mode="single-row",
        key=effective_key,
        **DATAFRAME_KWARGS,
    )

    selected_name = None
    if event.selection.rows:
        row_idx = event.selection.rows[0]
        # Guard against stale index when filter change shrinks the signals list
        if row_idx < len(signals_indexed) and 'name' in signals_indexed.columns:
            selected_name = signals_indexed.at[row_idx, 'name']

    col1, col2, col3 = st.columns([27, 27, 26])
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
        with st.popover("総合傾向について"):
            st.markdown(
                "| **総合傾向** | **説明** |\n"
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
    with col3:
        with st.popover("変動パターン・中期安定性について"):
            st.markdown(
                "**変動パターン**: 過去6ヶ月の自分自身の変動履歴を基準として、"
                "スコアの方向性（上昇・下降・横ばい）と波動性（行ったり来たりの繰り返し）を組み合わせたパターン。\n\n"
                "| **変動パターン** | **説明** |\n"
                "| --- | --- |\n"
                "| 安定 | 方向性も波動もなく横ばい |\n"
                "| 波動なし上昇 | 一方向にスムーズに上昇 |\n"
                "| 波動なし下降 | 一方向にスムーズに下降 |\n"
                "| 波動あり上昇 | 行き来しながら上昇傾向 |\n"
                "| 波動あり下降 | 行き来しながら下降傾向 |\n"
                "| 波動あり横ばい | 行き来しながら水準は変わらず |\n\n"
                "**中期安定性**: 過去6ヶ月のスコア変動幅が組織標準値と比べて大きいか小さいかを示す。"
                "「不安定」は変動幅が大きく、スコアに大きな浮き沈みがあったことを意味する。\n\n"
                "| **中期安定性** | **説明** |\n"
                "| --- | --- |\n"
                "| 安定 | 変動幅が小さく安定 |\n"
                "| やや不安定 | 変動幅は普通 |\n"
                "| 不安定 | 変動幅が大きく浮き沈みあり |\n"
                "| 不変 | 変化がほぼなし（調査抵抗の疑い） |"
            )

    return selected_name
