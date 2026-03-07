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
from modules.response_manager import (
    load_responses, post_response, get_responses_for_comment, make_comment_key
)
from modules.auth import get_current_user, get_current_display_name


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


def _render_responses(responses_df: pd.DataFrame, year_month: str, member_email: str, comment: str) -> None:
    """Display existing responses for a comment."""
    comment_responses = get_responses_for_comment(responses_df, year_month, member_email, comment)
    if comment_responses.empty:
        return
    for _, resp in comment_responses.iterrows():
        resp_date = resp.get("responded_at", "")[:10] if resp.get("responded_at") else ""
        resp_name = resp.get("responder_name", "")
        resp_text = resp.get("response_text", "")
        st.markdown(
            f'<div style="border-left: 3px solid #4CAF50; padding-left: 12px; margin: 4px 0 8px 0;">'
            f'<span style="font-size: 0.85em; color: #888;">{resp_name} ({resp_date})</span><br>'
            f'{resp_text}</div>',
            unsafe_allow_html=True,
        )


def _render_response_input(
    key_prefix: str,
    comment_key: str,
    year_month: str,
    member_email: str,
    comment: str,
) -> None:
    """Render inline response input form with confirmation step."""
    toggle_key = f"{key_prefix}_resp_toggle_{comment_key}"
    text_key = f"{key_prefix}_resp_text_{comment_key}"
    saved_text_key = f"{key_prefix}_resp_saved_{comment_key}"
    confirm_key = f"{key_prefix}_resp_confirm_{comment_key}"

    if st.session_state.get(confirm_key):
        # Confirmation step: show preview
        # Use saved_text_key (non-widget key) since text_area is not rendered here
        preview_text = st.session_state.get(saved_text_key, "")
        st.markdown(
            f'<div style="border-left: 3px solid #FF9800; padding-left: 12px; margin: 4px 0 8px 0;">'
            f'<span style="font-size: 0.85em; color: #888;">プレビュー</span><br>'
            f'{preview_text}</div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("送信する", key=f"{key_prefix}_resp_send_{comment_key}"):
                responder_account = get_current_user() or ""
                responder_name = get_current_display_name() or responder_account
                success = post_response(
                    year_month, member_email, comment,
                    responder_account, responder_name, preview_text
                )
                if success:
                    st.session_state[confirm_key] = False
                    st.session_state[toggle_key] = False
                    st.session_state.pop(saved_text_key, None)
                    st.rerun()
        with col2:
            if st.button("戻る", key=f"{key_prefix}_resp_back_{comment_key}"):
                # Restore saved text to widget key so text_area shows it
                st.session_state[text_key] = st.session_state.get(saved_text_key, "")
                st.session_state[confirm_key] = False
                st.rerun()

    elif st.session_state.get(toggle_key):
        # Input step
        st.text_area("返信を入力", key=text_key, height=100, label_visibility="collapsed")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("送信確認", key=f"{key_prefix}_resp_cfm_{comment_key}"):
                entered_text = st.session_state.get(text_key, "").strip()
                if entered_text:
                    # Save text to a non-widget key so it survives rerun
                    st.session_state[saved_text_key] = entered_text
                    st.session_state[confirm_key] = True
                    st.rerun()
                else:
                    st.warning("返信を入力してください")
        with col2:
            if st.button("キャンセル", key=f"{key_prefix}_resp_cancel_{comment_key}"):
                st.session_state[toggle_key] = False
                st.session_state.pop(text_key, None)
                st.session_state.pop(saved_text_key, None)
                st.rerun()
    else:
        if st.button("💬 返信する", key=f"{key_prefix}_resp_btn_{comment_key}", type="secondary"):
            st.session_state[toggle_key] = True
            st.rerun()


def render_comment_section(
    comment_data: pd.DataFrame,
    end_dt: pd.Timestamp,
    key_prefix: str,
    privilege_mgr,
    current_privilege: str,
    share_scope: Optional[List[str]] = None,
    latest_year_month: Optional[pd.Timestamp] = None
) -> None:
    """
    Render the 共有したいこと section with optional anonymization and response support.

    Args:
        comment_data: Prepared comment DataFrame (from prepare_comment_data)
        end_dt: End date for "直近1ヶ月" filtering
        key_prefix: Unique key prefix for Streamlit widgets
        privilege_mgr: PrivilegeManager instance
        current_privilege: Current user's privilege
        share_scope: Section scope for 共有したいこと (used to check access)
        latest_year_month: Latest year_month_dt in the full comment dataset (for response eligibility)
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
            # Non-anonymized users can respond to latest month comments
            can_respond = not anonymize_names

            # Load responses once for all comments in this section
            responses_df = load_responses()

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
                                    # Display responses (read-only for anonymized users)
                                    if 'mail_address' in row.index:
                                        _render_responses(
                                            responses_df, row['year_month'],
                                            row.get('mail_address', ''), row['comment']
                                        )
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
                                    member_email = row.get('mail_address', '') if 'mail_address' in row.index else ''
                                    # Display existing responses
                                    _render_responses(
                                        responses_df, row['year_month'],
                                        member_email, row['comment']
                                    )
                                    # Response input for latest month only
                                    if (can_respond and latest_year_month is not None
                                            and row['year_month_dt'] == latest_year_month):
                                        comment_key = make_comment_key(
                                            row['year_month'], member_email, row['comment']
                                        )
                                        _render_response_input(
                                            key_prefix, comment_key,
                                            row['year_month'], member_email, row['comment']
                                        )
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
    is_authenticated: bool,
    latest_year_month: Optional[pd.Timestamp] = None
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
        latest_year_month: Latest year_month_dt in full comment dataset (for response eligibility)
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
            privilege_mgr, current_privilege, share_scope,
            latest_year_month
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
