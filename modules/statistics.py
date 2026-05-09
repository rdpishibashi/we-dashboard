"""
Statistical Calculation Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
from typing import Optional
from .config import (
    GROUPING_LABEL_MAP, SIGNAL_LABELS, METRIC_LABELS,
    ENGAGEMENT_DIVISOR, RATING_BAND_HIGH_THRESHOLD, RATING_BAND_LOW_THRESHOLD,
)
from .utils import get_category_order_with_reference


def format_measured_data(
    df: pd.DataFrame,
    metric_col: str,
    group_col: Optional[str] = None,
    reference_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Format measurement data for display in 計測値 section.

    Aggregates data by year_month and optional grouping column, formats values,
    and renames columns to Japanese labels.

    Args:
        df: DataFrame with time series data (must have 'year_month' column)
        metric_col: The metric column to aggregate (e.g., 'engagement_rating')
        group_col: Optional grouping column (e.g., 'department', 'section', 'name').
                   Pass None or 'なし' for no grouping.
        reference_df: Optional reference DataFrame for category ordering (default: use df)

    Returns:
        Formatted DataFrame ready for display with st.dataframe()

    Example:
        >>> measured = format_measured_data(ts_df, 'engagement_rating', 'section')
        >>> st.dataframe(measured, **DATAFRAME_KWARGS)
    """
    if reference_df is None:
        reference_df = df

    # Normalize group_col
    if group_col == 'なし':
        group_col = None

    if group_col:
        # Group by year_month and grouping column
        agg = df.groupby(['year_month', group_col]).agg(
            **{metric_col: (metric_col, 'mean'),
               '人数': ('name', 'nunique') if 'name' in df.columns else (metric_col, 'count')}
        ).reset_index()
        measured_data = agg

        # Sort by grouping value using category order, then by year_month
        group_values = measured_data[group_col].unique().tolist()
        group_order = get_category_order_with_reference(group_col, group_values, reference_df)
        measured_data[group_col] = pd.Categorical(
            measured_data[group_col],
            categories=group_order,
            ordered=True
        )
        measured_data = measured_data.sort_values([group_col, 'year_month'])
        measured_data[group_col] = measured_data[group_col].astype(str)

        # Get grouping label and remove "別" suffix
        grouping_label = GROUPING_LABEL_MAP.get(group_col, group_col)
        if grouping_label != 'なし':
            grouping_label = grouping_label.replace('別', '')

        # Format metric with 2 decimal places (matches 主要な指標 precision)
        measured_data[metric_col] = measured_data[metric_col].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) else "-"
        )

        # Rename columns to Japanese
        metric_label = METRIC_LABELS.get(metric_col, metric_col)
        measured_data = measured_data.rename(columns={
            'year_month': '年月',
            group_col: grouping_label,
            metric_col: metric_label
        })

        # Reorder: grouping column, then 年月, then metric, then 人数
        measured_data = measured_data[[grouping_label, '年月', metric_label, '人数']]
    else:
        # No grouping - show overall average by month
        agg = df.groupby('year_month').agg(
            **{metric_col: (metric_col, 'mean'),
               '人数': ('name', 'nunique') if 'name' in df.columns else (metric_col, 'count')}
        ).reset_index()
        measured_data = agg.sort_values('year_month')

        # Format metric with 2 decimal places (matches 主要な指標 precision)
        measured_data[metric_col] = measured_data[metric_col].apply(
            lambda x: f"{x:.2f}" if pd.notna(x) else "-"
        )

        # Rename columns to Japanese
        metric_label = METRIC_LABELS.get(metric_col, metric_col)
        measured_data = measured_data.rename(columns={
            'year_month': '年月',
            metric_col: metric_label
        })

    return measured_data


def format_statistics_for_display(stats_df):
    """Format statistics dataframe for display with consistent decimal places."""
    display_stats = stats_df.copy()
    if '先月からの差分' in display_stats.columns:
        display_stats['先月からの差分'] = display_stats['先月からの差分'].apply(
            lambda x: f"{x:+.2f}" if pd.notna(x) and isinstance(x, (int, float)) else "-"
        )
    if '直近３ヶ月の傾き' in display_stats.columns:
        display_stats['直近３ヶ月の傾き'] = display_stats['直近３ヶ月の傾き'].apply(
            lambda x: f"{x:+.3f}" if pd.notna(x) and isinstance(x, (int, float)) else "-"
        )
    if '平均' in display_stats.columns:
        display_stats['平均'] = display_stats['平均'].apply(lambda x: f"{x:.2f}")
    if '傾向の傾き' in display_stats.columns:
        display_stats['傾向の傾き'] = display_stats['傾向の傾き'].apply(lambda x: f"{x:.3f}")
    if '標準偏差' in display_stats.columns:
        display_stats['標準偏差'] = display_stats['標準偏差'].apply(lambda x: f"{x:.2f}")
    return display_stats


def calculate_group_statistics(df, metric_col, group_col=None, signal_df=None, end_dt=None):
    """
    Calculate key statistics for each group in the data.

    Args:
        df: DataFrame with time series data
        metric_col: The metric column to analyze
        group_col: Optional grouping column (e.g., 'department', 'name')
        signal_df: Optional signal DataFrame for trend columns (used when group_col='name')
        end_dt: Optional end date for filtering signal data (used with signal_df)

    Returns:
        DataFrame with statistics for each group, sorted by group order
    """
    stats_list = []

    # Determine the column name based on grouping
    if group_col and group_col != 'なし':
        # Get the label and remove "別" suffix
        group_label = GROUPING_LABEL_MAP.get(group_col, 'グループ')
        column_name = group_label.replace('別', '') if group_label != 'なし' else 'グループ'
    else:
        column_name = 'グループ'

    if group_col and group_col != 'なし':
        # Calculate statistics for each group
        # Filter out NaN group names to avoid sorting/merge issues
        unique_groups = df[group_col].dropna().unique()
        for group_name in unique_groups:
            group_data = df[df[group_col] == group_name].copy()
            group_data = group_data.dropna(subset=[metric_col, 'year_month_dt'])

            if len(group_data) == 0:
                continue

            # Sort by date for trend calculation
            group_data = group_data.sort_values('year_month_dt')

            # Calculate average
            avg_value = group_data[metric_col].mean()

            # Calculate standard deviation
            std_value = group_data[metric_col].std()

            # Calculate trend slope using linear regression
            monthly_avg = group_data.groupby('year_month_dt')[metric_col].mean().reset_index()
            if len(monthly_avg) >= 2:
                x = np.arange(len(monthly_avg))
                y = monthly_avg[metric_col].values
                slope = np.polyfit(x, y, 1)[0]
            else:
                slope = 0.0

            # 人数: count members present in the latest month (end_dt) so that
            # transferred/retired members in earlier months are not counted.
            # Returns 0 when the group has no members in the latest month.
            if end_dt is not None and 'year_month_dt' in group_data.columns and 'name' in group_data.columns:
                n_people = group_data[group_data['year_month_dt'] == end_dt]['name'].nunique()
            elif 'name' in group_data.columns:
                n_people = group_data['name'].nunique()
            else:
                n_people = len(group_data)

            stats_list.append({
                column_name: str(group_name),
                '平均': avg_value,
                '傾向の傾き': slope,
                '標準偏差': std_value,
                '人数': n_people,
            })
    else:
        # Calculate statistics for entire dataset
        clean_data = df.dropna(subset=[metric_col, 'year_month_dt']).copy()

        if len(clean_data) > 0:
            # Sort by date
            clean_data = clean_data.sort_values('year_month_dt')

            # Calculate average
            avg_value = clean_data[metric_col].mean()

            # Calculate standard deviation
            std_value = clean_data[metric_col].std()

            # Calculate trend slope
            monthly_avg = clean_data.groupby('year_month_dt')[metric_col].mean().reset_index()
            if len(monthly_avg) >= 2:
                x = np.arange(len(monthly_avg))
                y = monthly_avg[metric_col].values
                slope = np.polyfit(x, y, 1)[0]
            else:
                slope = 0.0

            if end_dt is not None and 'year_month_dt' in clean_data.columns and 'name' in clean_data.columns:
                n_people = clean_data[clean_data['year_month_dt'] == end_dt]['name'].nunique()
            elif 'name' in clean_data.columns:
                n_people = clean_data['name'].nunique()
            else:
                n_people = len(clean_data)

            stats_list.append({
                column_name: '全体',
                '平均': avg_value,
                '傾向の傾き': slope,
                '標準偏差': std_value,
                '人数': n_people,
            })

    if not stats_list:
        return pd.DataFrame()

    stats_df = pd.DataFrame(stats_list)

    # Sort by group order if grouping is applied
    if group_col and group_col != 'なし':
        group_values = stats_df[column_name].tolist()
        group_order = get_category_order_with_reference(group_col, group_values, df)

        # Create a categorical type with the proper order
        stats_df[column_name] = pd.Categorical(
            stats_df[column_name],
            categories=group_order,
            ordered=True
        )
        stats_df = stats_df.sort_values(column_name).reset_index(drop=True)

        # Convert back to string for display
        stats_df[column_name] = stats_df[column_name].astype(str)

    # 先月からの差分: calculated from monthly group averages in df so it is
    # consistent with the chart values shown to the user.
    # Using E_delta_1 (per-person delta averaged) diverges from the chart when
    # new members join or leave mid-period, because new members have E_delta_1=0
    # while still shifting the group average.
    available_months = sorted(df['year_month_dt'].dropna().unique())
    ref_end = end_dt if (end_dt is not None and end_dt in available_months) \
        else (available_months[-1] if available_months else None)

    if ref_end is not None:
        end_idx = available_months.index(ref_end)
        if end_idx > 0:
            prev_dt = available_months[end_idx - 1]
            curr_data = df[df['year_month_dt'] == ref_end]
            prev_data = df[df['year_month_dt'] == prev_dt]
            if group_col and group_col != 'なし' and group_col in df.columns:
                curr_avg = curr_data.groupby(group_col)[metric_col].mean()
                prev_avg = prev_data.groupby(group_col)[metric_col].mean()
                stats_df['先月からの差分'] = stats_df[column_name].map(curr_avg - prev_avg)
            else:
                stats_df['先月からの差分'] = (
                    curr_data[metric_col].mean() - prev_data[metric_col].mean()
                )

    # 直近３ヶ月の傾き: keep using E_slope_3m from signal_df (analyzer-computed slope)
    if signal_df is not None and 'E_slope_3m' in signal_df.columns:
        ref_dt = end_dt
        if ref_dt is None and 'year_month_dt' in signal_df.columns:
            ref_dt = signal_df['year_month_dt'].max()

        if ref_dt is not None:
            latest_signal = signal_df[signal_df['year_month_dt'] == ref_dt]

            if not latest_signal.empty:
                if group_col and group_col != 'なし' and group_col in latest_signal.columns:
                    slope_by_group = (
                        latest_signal.groupby(group_col)['E_slope_3m'].mean() / ENGAGEMENT_DIVISOR
                    )
                    stats_df['直近３ヶ月の傾き'] = stats_df[column_name].map(slope_by_group)
                else:
                    stats_df['直近３ヶ月の傾き'] = (
                        latest_signal['E_slope_3m'].mean() / ENGAGEMENT_DIVISOR
                    )

    # Merge trend columns when grouping by name
    if group_col == 'name' and signal_df is not None and end_dt is not None:
        # Get latest wave data from signal_df
        latest_signal = signal_df[signal_df['year_month_dt'] == end_dt].copy()
        if not latest_signal.empty and 'name' in latest_signal.columns:
            # Get trend columns for each person
            trend_cols = ['trend_recent', 'trend_base', 'trend_refined']
            available_cols = [col for col in trend_cols if col in latest_signal.columns]
            if available_cols:
                # Sort to prefer rows with non-null trend values when deduplicating
                # This ensures we keep rows with valid data if duplicates exist
                trend_subset = latest_signal[['name'] + available_cols].copy()
                trend_subset = trend_subset.dropna(subset=['name'])  # Remove rows with NaN names

                # Sort by trend columns to bring non-null values first
                for col in available_cols:
                    trend_subset[f'_{col}_notna'] = trend_subset[col].notna().astype(int)
                sort_cols = [f'_{col}_notna' for col in available_cols]
                trend_subset = trend_subset.sort_values(sort_cols, ascending=False)

                # Now drop duplicates keeping first (which has non-null values if available)
                trend_data = trend_subset.drop_duplicates('name')

                # Remove helper columns
                for col in sort_cols:
                    trend_data = trend_data.drop(columns=[col])

                # Rename columns to Japanese labels
                rename_map = {col: SIGNAL_LABELS.get(col, col) for col in available_cols}
                trend_data = trend_data.rename(columns=rename_map)
                trend_data = trend_data.rename(columns={'name': column_name})

                # Ensure column types match for merge - use consistent string normalization
                stats_df[column_name] = stats_df[column_name].astype(str).str.strip()
                trend_data[column_name] = trend_data[column_name].astype(str).str.strip()

                # Create lookup dictionaries for more robust matching
                trend_labels = [SIGNAL_LABELS.get(col, col) for col in available_cols]

                # Build a simple name -> trend values dictionary
                trend_dict = {}
                for _, row in trend_data.iterrows():
                    name_key = str(row[column_name]).strip()
                    trend_dict[name_key] = {label: row[label] for label in trend_labels}

                # Add trend columns using lookup
                def get_trend_value(name, label):
                    """Get trend value for a name, returning '-' if not found or null."""
                    name_key = str(name).strip()
                    if name_key not in trend_dict:
                        return '-'
                    val = trend_dict[name_key].get(label)
                    if val is None or (isinstance(val, float) and np.isnan(val)):
                        return '-'
                    return val

                for label in trend_labels:
                    stats_df[label] = stats_df[column_name].apply(lambda x, lbl=label: get_trend_value(x, lbl))

                # Reorder columns: name column, trend columns, then other stats
                other_cols = [c for c in stats_df.columns if c != column_name and c not in trend_labels]
                stats_df = stats_df[[column_name] + trend_labels + other_cols]

    # 人数 は個人別（group_col == 'name'）では表示しない
    if group_col == 'name' and '人数' in stats_df.columns:
        stats_df = stats_df.drop(columns=['人数'])

    # Final column ordering:
    # group → (signal trends if name) → 先月差分 → 直近傾き → 平均 → 傾向の傾き → 標準偏差 → 人数
    signal_trend_labels = ['短期傾向', '中期傾向', '総合傾向']
    delta_slope_labels = ['先月からの差分', '直近３ヶ月の傾き']
    col_order = [column_name]
    col_order += [c for c in signal_trend_labels if c in stats_df.columns]
    col_order += [c for c in delta_slope_labels if c in stats_df.columns]
    col_order += [c for c in ['平均', '傾向の傾き', '標準偏差', '人数'] if c in stats_df.columns]
    col_order += [c for c in stats_df.columns if c not in col_order]
    stats_df = stats_df[col_order]

    return stats_df


def format_evaluation_measured_data(
    df: pd.DataFrame,
    metric_col: str,
    group_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Format evaluation band (高い/中間/低い) counts and ratios for display.
    Used in the 評価 tab 計測値 section (評価別比率 analysis type).

    Args:
        df: DataFrame with metric data (must have 'year_month' column)
        metric_col: The metric column used for band classification
        group_col: Optional grouping column (e.g., 'section', 'department')

    Returns:
        Formatted DataFrame with columns: (group), 年月, 高い, 中間, 低い
        Each band cell shows "count (ratio%)"
    """
    if group_col == 'なし':
        group_col = None

    working = df.dropna(subset=[metric_col, 'year_month']).copy()
    if working.empty:
        return pd.DataFrame()

    working['rating_band'] = np.select(
        [
            working[metric_col] >= RATING_BAND_HIGH_THRESHOLD,
            working[metric_col] <= RATING_BAND_LOW_THRESHOLD,
        ],
        ['高い', '低い'],
        default='中間',
    )

    category_order = ['高い', '中間', '低い']
    group_keys = [group_col, 'year_month'] if group_col else ['year_month']

    counts = (
        working.groupby(group_keys + ['rating_band'])
        .size()
        .reset_index(name='count')
    )
    totals = counts.groupby(group_keys)['count'].transform('sum').replace(0, np.nan)
    counts['ratio'] = (counts['count'] / totals * 100).fillna(0)
    counts['cell'] = counts.apply(
        lambda r: f"{int(r['count'])} ({r['ratio']:.1f}%)", axis=1
    )

    pivot = counts.pivot_table(
        index=group_keys, columns='rating_band', values='cell', aggfunc='first'
    ).reset_index()
    pivot.columns.name = None

    # Ensure all band columns exist and fill missing (0-count) cells
    for band in category_order:
        if band not in pivot.columns:
            pivot[band] = '0 (0.0%)'
        else:
            pivot[band] = pivot[band].fillna('0 (0.0%)')

    # Sort rows
    if group_col and group_col in pivot.columns:
        group_values = pivot[group_col].unique().tolist()
        group_order = get_category_order_with_reference(group_col, group_values, df)
        pivot[group_col] = pd.Categorical(pivot[group_col], categories=group_order, ordered=True)
        pivot = pivot.sort_values([group_col, 'year_month']).reset_index(drop=True)
        pivot[group_col] = pivot[group_col].astype(str)

        grouping_label = GROUPING_LABEL_MAP.get(group_col, group_col).replace('別', '')
        pivot = pivot.rename(columns={group_col: grouping_label, 'year_month': '年月'})
        col_order = [grouping_label, '年月'] + category_order
    else:
        pivot = pivot.sort_values('year_month').reset_index(drop=True)
        pivot = pivot.rename(columns={'year_month': '年月'})
        col_order = ['年月'] + category_order

    return pivot[[c for c in col_order if c in pivot.columns]]


def format_radar_measured_data(
    df: pd.DataFrame,
    group_col: Optional[str] = None,
    reference_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Format component metric averages for display in 評価 tab レーダーチャート 計測値 section.

    Args:
        df: DataFrame with rating data (must have vigor/dedication/absorption columns)
        group_col: Optional grouping column
        reference_df: Optional reference DataFrame for category ordering

    Returns:
        Formatted DataFrame with columns: (group), 活力, 熱意, 没頭
    """
    if group_col == 'なし':
        group_col = None
    if reference_df is None:
        reference_df = df

    component_cols = ['vigor_rating', 'dedication_rating', 'absorption_rating']
    rename_map = {
        'vigor_rating': '活力',
        'dedication_rating': '熱意',
        'absorption_rating': '没頭',
    }

    available = [c for c in component_cols if c in df.columns]
    if not available:
        return pd.DataFrame()

    if group_col and group_col in df.columns:
        agg = df.groupby(group_col)[available].mean().reset_index()

        group_values = agg[group_col].tolist()
        group_order = get_category_order_with_reference(group_col, group_values, reference_df)
        agg[group_col] = pd.Categorical(agg[group_col], categories=group_order, ordered=True)
        agg = agg.sort_values(group_col).reset_index(drop=True)
        agg[group_col] = agg[group_col].astype(str)

        grouping_label = GROUPING_LABEL_MAP.get(group_col, group_col).replace('別', '')
        agg = agg.rename(columns={group_col: grouping_label, **rename_map})

        for col in rename_map.values():
            if col in agg.columns:
                agg[col] = agg[col].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "-")

        col_order = [grouping_label] + [rename_map[c] for c in available]
        return agg[[c for c in col_order if c in agg.columns]]
    else:
        row = df[available].mean()
        result = pd.DataFrame([{'グループ': '全体', **{rename_map[c]: f"{row[c]:.1f}" for c in available}}])
        return result
