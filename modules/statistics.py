"""
Statistical Calculation Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
from .config import GROUPING_LABEL_MAP, SIGNAL_LABELS
from .utils import get_category_order_with_reference


def format_statistics_for_display(stats_df):
    """Format statistics dataframe for display with consistent decimal places."""
    display_stats = stats_df.copy()
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

    # Merge trend columns when grouping by name
    if group_col == 'name' and signal_df is not None and end_dt is not None:
        # Get latest wave data from signal_df
        latest_signal = signal_df[signal_df['year_month_dt'] == end_dt].copy()
        if not latest_signal.empty and 'name' in latest_signal.columns:
            # Get trend columns for each person
            trend_cols = ['trend_recent', 'trend_refined']
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

    return stats_df
