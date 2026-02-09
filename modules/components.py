"""
Reusable UI components for the WE-Dashboard.

This module consolidates duplicated patterns from app.py into reusable functions:
- Comment section rendering (共有したいこと, 気になった出来事や気づき)
- Action candidates rendering (アクション対象候補)
- Comment data preparation
"""

import streamlit as st
import pandas as pd
from typing import Optional, List, Dict, Any

from modules.signal_processing import get_signal_data, render_signal_table
from modules.config import SIGNAL_TABLE_COLUMNS
from modules.privilege_manager import filter_dataframe_by_scope
from modules.utils import GROUP_ORDER_MAP


def filter_signal_by_selection(
    signal_df: pd.DataFrame,
    main_df: pd.DataFrame,
    dept_choice: str,
    section_choice: str
) -> pd.DataFrame:
    """
    Filter signal DataFrame by department/section selections.

    Args:
        signal_df: Signal DataFrame to filter
        main_df: Main DataFrame (already filtered by dept/section)
        dept_choice: Selected department ('すべて' for all)
        section_choice: Selected section ('すべて' for all)

    Returns:
        Filtered signal DataFrame
    """
    result = signal_df.copy()

    if dept_choice != 'すべて':
        result = result[result['department'] == dept_choice]

    if section_choice != 'すべて':
        result = result[result['section'] == section_choice]

    return result


def prepare_comment_data(
    comment_df: pd.DataFrame,
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
    scope: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Prepare comment data for display by mapping org columns and applying scope filter.

    Comment data has its own organization columns (current_section, etc.) and should
    NOT be joined with main data. This function:
    1. Filters by date range
    2. Maps current_* columns to standard names (section, department, division)
    3. Applies scope filtering using filter_dataframe_by_scope (checks all org columns)

    Args:
        comment_df: Raw comment DataFrame with current_* columns
        start_dt: Start date for filtering
        end_dt: End date for filtering
        scope: Organization scope values (may contain dept/division names, not just sections)

    Returns:
        Prepared and filtered comment DataFrame
    """
    # Filter by date range
    graph_comments = comment_df[
        (comment_df['year_month_dt'] >= start_dt) &
        (comment_df['year_month_dt'] <= end_dt)
    ].copy()

    # Map current_* columns to standard names for filtering and display
    if 'current_section' in graph_comments.columns:
        graph_comments['section'] = graph_comments['current_section'].fillna('未設定')
    if 'current_department' in graph_comments.columns:
        graph_comments['department'] = graph_comments['current_department'].fillna('未設定')
    if 'current_division' in graph_comments.columns:
        graph_comments['division'] = graph_comments['current_division'].fillna('未設定')

    # Apply section scope filtering using comment's own organization columns
    # filter_dataframe_by_scope checks division, department, AND section columns
    graph_comments = filter_dataframe_by_scope(graph_comments, scope)

    return graph_comments


def _sort_by_section_order(df: pd.DataFrame, section_order: List[str]) -> pd.DataFrame:
    """Sort DataFrame by section order, then name, then year_month (descending)."""
    if section_order:
        section_order_map = {name: idx for idx, name in enumerate(section_order)}
        df['_section_order'] = df['section'].apply(
            lambda x: section_order_map.get(x, len(section_order))
        )
        df = df.sort_values(['_section_order', 'name', 'year_month'], ascending=[True, True, False])
    else:
        df = df.sort_values(['section', 'name', 'year_month'], ascending=[True, True, False])
    return df


def render_action_candidates(
    signal_df: pd.DataFrame,
    main_df: pd.DataFrame,
    end_dt: pd.Timestamp,
    privilege_mgr,
    current_privilege: str
) -> None:
    """
    Render the アクション対象候補 section.

    Args:
        signal_df: Signal DataFrame (already filtered by tab scope)
        main_df: Main DataFrame for the current view
        end_dt: End date for signal data
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
    """
    # Apply section scope filtering for アクション対象候補
    action_scope = privilege_mgr.get_section_scope(current_privilege, "アクション対象候補")
    action_signal_df = filter_dataframe_by_scope(signal_df, action_scope)

    if action_scope is None or len(action_scope) > 0:
        st.subheader("アクション対象候補")

        try:
            signals = get_signal_data(action_signal_df, main_df, end_dt)
            render_signal_table(signals, SIGNAL_TABLE_COLUMNS)
        except Exception as e:
            st.error(f"シグナルデータの取得に失敗しました: {e}")


def render_concern_section(
    comment_data: pd.DataFrame,
    end_dt: pd.Timestamp,
    key_prefix: str,
    privilege_mgr,
    current_privilege: str
) -> None:
    """
    Render the 気になった出来事や気づき section.

    Args:
        comment_data: Prepared comment DataFrame (from prepare_comment_data)
        end_dt: End date for "直近1ヶ月" filtering
        key_prefix: Unique key prefix for Streamlit widgets
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
    """
    if not privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
        return

    if comment_data.empty:
        return

    section_order = GROUP_ORDER_MAP.get('section', [])

    with st.expander("気になった出来事や気づき", expanded=False):
        concern_period = st.radio(
            "表示期間",
            ["全期間", "直近1ヶ月"],
            index=1,
            horizontal=True,
            key=f"{key_prefix}_concern_period"
        )
        concern_data = comment_data[comment_data['concern'].notna()].copy()
        if concern_period == "直近1ヶ月":
            concern_data = concern_data[concern_data['year_month_dt'] == end_dt]

        if not concern_data.empty:
            concern_data = _sort_by_section_order(concern_data, section_order)

            # Display nested: section -> name -> content
            sections = concern_data['section'].unique()
            for section in sections:
                section_data = concern_data[concern_data['section'] == section]
                with st.expander(f"{section}", expanded=False):
                    names = section_data['name'].unique()
                    for name in names:
                        name_data = section_data[section_data['name'] == name]
                        with st.expander(f"{name}", expanded=True):
                            for _, row in name_data.iterrows():
                                st.markdown(f"**{row['year_month']}**")
                                st.text(row['concern'])
                                st.divider()
        else:
            st.info("データがありません")


def render_comment_section(
    comment_data: pd.DataFrame,
    end_dt: pd.Timestamp,
    key_prefix: str,
    privilege_mgr,
    current_privilege: str,
    share_scope: Optional[List[str]] = None
) -> None:
    """
    Render the 共有したいこと section with optional anonymization.

    When anonymized (for member-class privileges):
    - Comments grouped by year_month instead of by name
    - Display hierarchy: section → year_month → comments

    When NOT anonymized:
    - Comments grouped by name
    - Display hierarchy: section → name → comments (with date header)

    Args:
        comment_data: Prepared comment DataFrame (from prepare_comment_data)
        end_dt: End date for "直近1ヶ月" filtering
        key_prefix: Unique key prefix for Streamlit widgets
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
        share_scope: Section scope for 共有したいこと (used to check access)
    """
    if not privilege_mgr.has_feature_access(current_privilege, "共有したいこと"):
        return

    # Check if scope allows access
    if share_scope is not None and len(share_scope) == 0:
        return

    if comment_data.empty:
        return

    section_order = GROUP_ORDER_MAP.get('section', [])

    with st.expander("共有したいこと", expanded=False):
        share_period = st.radio(
            "表示期間",
            ["全期間", "直近1ヶ月"],
            index=1,
            horizontal=True,
            key=f"{key_prefix}_share_period"
        )
        share_data = comment_data[comment_data['comment'].notna()].copy()
        if share_period == "直近1ヶ月":
            share_data = share_data[share_data['year_month_dt'] == end_dt]

        if not share_data.empty:
            # Check if names should be anonymized
            anonymize_names = privilege_mgr.should_anonymize_section(current_privilege, "共有したいこと")

            share_data = _sort_by_section_order(share_data, section_order)

            # Display nested: section -> (year_month or name) -> content
            sections = share_data['section'].unique()
            for section in sections:
                section_data = share_data[share_data['section'] == section]
                with st.expander(f"{section}", expanded=False):
                    if anonymize_names:
                        # Show comments grouped by year_month (without names)
                        year_months = section_data['year_month'].unique()
                        for ym in year_months:
                            ym_data = section_data[section_data['year_month'] == ym]
                            with st.expander(f"{ym}", expanded=True):
                                for _, row in ym_data.iterrows():
                                    st.text(row['comment'])
                                    st.divider()
                    else:
                        # Show comments with names
                        names = section_data['name'].unique()
                        for name in names:
                            name_data = section_data[section_data['name'] == name]
                            with st.expander(f"{name}", expanded=True):
                                for _, row in name_data.iterrows():
                                    st.markdown(f"**{row['year_month']}**")
                                    st.text(row['comment'])
                                    st.divider()
        else:
            st.info("データがありません")


def render_comments_and_signals(
    signal_df: pd.DataFrame,
    main_df: pd.DataFrame,
    comment_df: pd.DataFrame,
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
    key_prefix: str,
    privilege_mgr,
    current_privilege: str,
    is_authenticated: bool
) -> None:
    """
    Render the complete comments and signals section for a tab.

    This is a convenience function that combines:
    - アクション対象候補 (action candidates)
    - 気になった出来事や気づき (concerns)
    - 共有したいこと (comments)

    Args:
        signal_df: Signal DataFrame (already filtered by tab/grouping scope)
        main_df: Main DataFrame for the current view
        comment_df: Raw comment DataFrame (will be prepared internally)
        start_dt: Start date
        end_dt: End date
        key_prefix: Unique key prefix for Streamlit widgets
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
        is_authenticated: Whether user is authenticated
    """
    if not is_authenticated:
        return

    # Render action candidates
    render_action_candidates(signal_df, main_df, end_dt, privilege_mgr, current_privilege)

    # Get comment scope and prepare comment data
    share_scope = privilege_mgr.get_section_scope(current_privilege, "共有したいこと")
    graph_comments = prepare_comment_data(comment_df, start_dt, end_dt, share_scope)

    if not graph_comments.empty:
        # Render concern section
        render_concern_section(
            graph_comments, end_dt, key_prefix,
            privilege_mgr, current_privilege
        )

        # Render comment section
        render_comment_section(
            graph_comments, end_dt, key_prefix,
            privilege_mgr, current_privilege, share_scope
        )


def apply_grouping_filters(
    df: pd.DataFrame,
    signal_df: Optional[pd.DataFrame],
    privilege_mgr,
    current_privilege: str,
    grouping_choice: str,
    tab_name: str,
    selected_filters: dict = None
) -> tuple:
    """
    Apply grouping-specific filters to DataFrames.

    This applies the following layers in order:
    1. Grouping scope - restricts data based on privilege's grouping_scope config
       (uses grouping_scope_filtered when a specific dimension value is selected)
    2. Grade filtering - applies only when grouping by 'grade'
    3. Section aliases - renames section values for aggregation/privacy

    Args:
        df: Main DataFrame
        signal_df: Signal DataFrame (can be None if not needed)
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
        grouping_choice: Selected grouping option
        tab_name: Current tab name (for aliases)
        selected_filters: Sidebar filter selections (used to detect dimension ≠ すべて)

    Returns:
        Tuple of (filtered_df, filtered_signal_df)
    """
    from modules.privilege_manager import (
        filter_dataframe_by_scope, filter_dataframe_by_grade,
        apply_section_aliases
    )

    if not current_privilege or not grouping_choice:
        return df, signal_df

    # Determine if a specific dimension value is selected (≠ すべて)
    dimension_filtered = (
        selected_filters is not None and
        selected_filters.get('dimension_value', 'すべて') != 'すべて'
    )

    # Layer 1: Grouping scope (restricts data based on grouping type)
    grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, grouping_choice, dimension_filtered)
    df = filter_dataframe_by_scope(df, grouping_scope)
    if signal_df is not None:
        signal_df = filter_dataframe_by_scope(signal_df, grouping_scope)

    # Layer 2: Grade filtering (only for grade grouping)
    if grouping_choice == 'grade':
        grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, grouping_choice, dimension_filtered)
        if grade_filter:
            df = filter_dataframe_by_grade(df, grade_filter)
            if signal_df is not None:
                signal_df = filter_dataframe_by_grade(signal_df, grade_filter)

    # Layer 3: Section aliases (only for section grouping)
    if grouping_choice == 'section':
        alias_mapping = privilege_mgr.get_section_aliases(current_privilege, tab_name)
        if alias_mapping:
            df = apply_section_aliases(df, alias_mapping)
            if signal_df is not None:
                signal_df = apply_section_aliases(signal_df, alias_mapping)

    return df, signal_df
