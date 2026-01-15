"""
Statistical Calculation Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
from .config import GROUPING_LABEL_MAP
from .utils import get_category_order_with_reference


def format_statistics_for_display(stats_df):
    """Format statistics dataframe for display with consistent decimal places."""
    display_stats = stats_df.copy()
    display_stats['平均'] = display_stats['平均'].apply(lambda x: f"{x:.2f}")
    display_stats['傾向の傾き'] = display_stats['傾向の傾き'].apply(lambda x: f"{x:.3f}")
    display_stats['標準偏差'] = display_stats['標準偏差'].apply(lambda x: f"{x:.2f}")
    return display_stats


def calculate_group_statistics(df, metric_col, group_col=None):
    """
    Calculate key statistics for each group in the data.

    Args:
        df: DataFrame with time series data
        metric_col: The metric column to analyze
        group_col: Optional grouping column (e.g., 'department', 'name')

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
        for group_name in df[group_col].unique():
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

            stats_list.append({
                column_name: str(group_name),
                '平均': avg_value,
                '傾向の傾き': slope,
                '標準偏差': std_value
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

            stats_list.append({
                column_name: '全体',
                '平均': avg_value,
                '傾向の傾き': slope,
                '標準偏差': std_value
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

    return stats_df
