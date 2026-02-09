"""
Unified Filter System Helper Functions
=======================================
Handles cascading selectbox filters in sidebar for WE-Dashboard.

Filter cascade order: 部門 → 職位 → 部署 → (課|チーム|プロジェクト) → 個人

Key features:
- Privilege-based option filtering
- Parent-child cascade reset logic
- Dimension selector (課/チーム/プロジェクト mutual exclusion)
- "すべて" (all) option for each filter
"""

import streamlit as st
import pandas as pd
from typing import Optional, Dict, List, Tuple
import urllib.parse

from modules.utils import get_options, sort_names_by_grade
from modules.privilege_manager import filter_dataframe_by_scope


def get_sidebar_scope(privilege_mgr, current_privilege: str) -> Optional[list]:
    """
    Get the BROADEST data scope across all allowed tabs for sidebar filtering.

    Uses the UNION of all tab scopes so that data from any accessible tab
    can appear in sidebar dropdown options. Each tab's per-tab scope still
    restricts what data is shown in that tab's charts.

    Returns:
        None if all data allowed (admin), list of allowed org values,
        or empty list if no access.
    """
    if not current_privilege:
        return None

    allowed_tabs = privilege_mgr.get_allowed_tabs(current_privilege)
    if not allowed_tabs:
        return []

    all_values = set()
    for tab in allowed_tabs:
        scope = privilege_mgr.get_data_scope_for_tab(current_privilege, tab)
        if scope is None:  # admin - no restriction
            return None
        all_values.update(scope)

    return list(all_values) if all_values else []


def get_section_restriction(df: pd.DataFrame, privilege_mgr, current_privilege: str) -> Optional[list]:
    """
    Get section-level scope values for restricting the 課 dropdown.

    Section managers have department-level scope in some tabs (e.g., 時系列)
    and section-level scope in others (e.g., 個人). The 課 dropdown should
    only show the specific sections they manage, not all sections in the
    department.

    This works by finding scope values that are actual section names (not
    department or division names) across all tab scopes.

    Returns:
        None if no section-level restriction (admin or department-level only),
        or list of allowed section values.
    """
    if not current_privilege:
        return None

    allowed_tabs = privilege_mgr.get_allowed_tabs(current_privilege)
    if not allowed_tabs:
        return None

    # Determine which org level each scope value belongs to
    dept_values = set(df['department'].dropna().unique()) if 'department' in df.columns else set()
    div_values = set(df['division'].dropna().unique()) if 'division' in df.columns else set()
    non_section_values = dept_values | div_values

    section_level_values = set()
    for tab in allowed_tabs:
        scope = privilege_mgr.get_data_scope_for_tab(current_privilege, tab)
        if scope is None:  # admin - no restriction
            return None
        for val in scope:
            if val not in non_section_values:
                section_level_values.add(val)

    if section_level_values:
        return list(section_level_values)

    return None  # All scopes are department/division level — no section restriction


def get_cascaded_options(
    df: pd.DataFrame,
    filter_type: str,
    privilege_mgr,
    current_privilege: str
) -> List[str]:
    """
    Get dropdown options for a filter based on parent selections and privilege restrictions.

    Args:
        df: DataFrame already filtered by parent selections and sidebar scope
        filter_type: 'division' | 'grade' | 'department' | 'section' | 'team' | 'project' | 'name'
        privilege_mgr: PrivilegeManager instance
        current_privilege: User's privilege class

    Returns:
        List of available options (privilege-filtered)
    """
    # Column mapping
    column_map = {
        'division': 'division',
        'grade': 'grade',
        'department': 'department',
        'section': 'section',
        'team': 'team',
        'project': 'project',
        'name': 'name'
    }

    if filter_type not in column_map:
        return []

    col = column_map[filter_type]

    # Get raw options from current df state (already filtered by parents and scope)
    remove_unset = filter_type not in ['grade']  # Keep "未設定" for grade
    options = get_options(df[col], remove_unset=remove_unset, order_key=filter_type)

    # Remove empty strings (data quality)
    options = [opt for opt in options if opt and str(opt).strip()]

    return options


def apply_unified_filter(
    df: pd.DataFrame,
    filter_key: str,
    selected_value: str,
    dimension_info: Optional[Tuple] = None
) -> pd.DataFrame:
    """
    Apply a single unified filter to DataFrame.

    Args:
        df: DataFrame to filter
        filter_key: 'division' | 'grade' | 'department' | 'dimension_value' | 'individual'
        selected_value: Selected value (or 'すべて' for no filter)
        dimension_info: For dimension_value, tuple of (dimension_type, value)

    Returns:
        Filtered DataFrame
    """
    if selected_value == 'すべて':
        return df

    column_map = {
        'division': 'division',
        'grade': 'grade',
        'department': 'department',
        'individual': 'name'
    }

    if filter_key == 'dimension_value':
        if dimension_info is None:
            return df

        dimension_type, value = dimension_info
        col_map = {'課': 'section', 'チーム': 'team', 'プロジェクト': 'project'}
        col = col_map[dimension_type]

        return df[df[col] == value]

    if filter_key not in column_map:
        return df

    col = column_map[filter_key]
    return df[df[col] == selected_value]


def should_reset_child_filters(parent_key: str, current_value: str) -> bool:
    """
    Check if parent filter changed and child filters should reset.

    Args:
        parent_key: Session state key for parent filter
        current_value: Current value of parent filter

    Returns:
        True if parent changed (children should reset)
    """
    prev_key = f"_prev_{parent_key}"
    prev_value = st.session_state.get(prev_key)

    if prev_value is not None and prev_value != current_value:
        st.session_state[prev_key] = current_value
        return True

    st.session_state[prev_key] = current_value
    return False


def reset_child_filters(parent_level: str):
    """
    Reset all child filters below the specified parent level.

    Cascade: 部門 → 職位 → 部署 → dimension → individual

    Args:
        parent_level: 'division' | 'grade' | 'department' | 'dimension' | 'dimension_value'
    """
    reset_mapping = {
        'division': ['unified_grade', 'unified_department', 'unified_section', 'unified_team', 'unified_project', 'unified_individual'],
        'grade': ['unified_department', 'unified_section', 'unified_team', 'unified_project', 'unified_individual'],
        'department': ['unified_section', 'unified_team', 'unified_project', 'unified_individual'],
        'section': ['unified_team', 'unified_project', 'unified_individual'],
        'team': ['unified_project', 'unified_individual'],
        'project': ['unified_individual']
    }

    if parent_level in reset_mapping:
        for child_key in reset_mapping[parent_level]:
            st.session_state[child_key] = 'すべて'


def render_unified_sidebar_filters(
    df: pd.DataFrame,
    signal_df: pd.DataFrame,
    privilege_mgr,
    current_privilege: str,
    is_authenticated_user: bool,
    grouping_options: List[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, str], str]:
    """
    Render unified sidebar filter cascade and return filtered DataFrames.

    Filter cascade: 部門 → 職位 → 部署 → (課|チーム|プロジェクト) → 個人
    Plus: グルーピング selector

    The sidebar pre-filters by the BROADEST scope (union of all tab scopes)
    to build dropdown options. Each tab then applies its own per-tab scope
    for chart data.

    Args:
        df: Main DataFrame (already filtered by period)
        signal_df: Signal DataFrame (already filtered by period)
        privilege_mgr: PrivilegeManager instance
        current_privilege: User's privilege class
        is_authenticated_user: Whether user is authenticated
        grouping_options: List of allowed grouping options

    Returns:
        Tuple of (filtered_df, filtered_signal_df, selected_filters_dict, grouping_choice)
    """
    # Pre-filter by broadest privilege scope (union of all tab scopes)
    # This excludes completely out-of-scope data from dropdown options
    # while still allowing per-tab scope to control chart data
    sidebar_scope = get_sidebar_scope(privilege_mgr, current_privilege)
    scoped_df = filter_dataframe_by_scope(df.copy(), sidebar_scope)

    # Get section restriction for 課 dropdown (section managers only)
    section_restriction = get_section_restriction(df, privilege_mgr, current_privilege)

    # Track current df state through cascade (using scope-filtered data)
    current_df = scoped_df

    # Dictionary to store selected values
    selected_filters = {}

    # ── 表示カテゴリ (Grouping) — rendered BEFORE filters ──
    # Use provided grouping options or default
    if grouping_options is None:
        grouping_options = ['なし']

    # Remove duplicates while preserving order
    cleaned_options = list(dict.fromkeys(grouping_options))
    if not cleaned_options:
        cleaned_options = ['なし']

    # Get current selection
    grouping_key = 'unified_grouping'
    default_idx = 0
    if grouping_key in st.session_state and st.session_state[grouping_key] in cleaned_options:
        default_idx = cleaned_options.index(st.session_state[grouping_key])

    # Import GROUPING_LABEL_MAP
    from modules.config import GROUPING_LABEL_MAP

    # Render grouping selectbox directly in sidebar (like 表示指標)
    format_func = lambda x: GROUPING_LABEL_MAP.get(x, x)
    grouping_choice = st.sidebar.selectbox(
        "表示カテゴリ",
        cleaned_options,
        index=default_idx,
        format_func=format_func,
        key=grouping_key
    )

    # ── フィルター設定 (Organization filters) ──
    st.sidebar.markdown("---")
    with st.sidebar.expander("フィルター設定", expanded=False):
        # 1. 部門 (Division) Filter
        division_options = get_cascaded_options(
            current_df, 'division', privilege_mgr, current_privilege
        )

        selected_division = st.selectbox(
            "部門",
            ["すべて"] + division_options,
            key="unified_division"
        )
        selected_filters['division'] = selected_division

        # Check if division changed → reset children
        if should_reset_child_filters('unified_division', selected_division):
            reset_child_filters('division')

        # Apply division filter
        current_df = apply_unified_filter(current_df, 'division', selected_division)

        # 2. 職位 (Grade) Filter
        grade_options = get_cascaded_options(
            current_df, 'grade', privilege_mgr, current_privilege
        )

        # Apply grade_filter restriction if configured (e.g., non_managers only)
        if current_privilege:
            grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, 'grade')
            if grade_filter:
                grade_options = [g for g in grade_options if g in grade_filter]

        selected_grade = st.selectbox(
            "職位",
            ["すべて"] + grade_options,
            key="unified_grade"
        )
        selected_filters['grade'] = selected_grade

        # Check if grade changed → reset children
        if should_reset_child_filters('unified_grade', selected_grade):
            reset_child_filters('grade')

        # Apply grade filter
        current_df = apply_unified_filter(current_df, 'grade', selected_grade)

        # 3. 部署 (Department) Filter
        department_options = get_cascaded_options(
            current_df, 'department', privilege_mgr, current_privilege
        )

        selected_department = st.selectbox(
            "部署",
            ["すべて"] + department_options,
            key="unified_department"
        )
        selected_filters['department'] = selected_department

        # Check if department changed → reset children
        if should_reset_child_filters('unified_department', selected_department):
            reset_child_filters('department')

        # Apply department filter
        current_df = apply_unified_filter(current_df, 'department', selected_department)

        # 4. 課 (Section) Filter
        section_options = get_cascaded_options(
            current_df, 'section', privilege_mgr, current_privilege
        )

        # Apply section restriction for 課 dropdown (section managers)
        if section_restriction:
            section_options = [opt for opt in section_options if opt in section_restriction]

        selected_section = st.selectbox(
            "課",
            ["すべて"] + section_options,
            key="unified_section"
        )
        selected_filters['section'] = selected_section

        if should_reset_child_filters('unified_section', selected_section):
            reset_child_filters('section')

        current_df = apply_unified_filter(
            current_df, 'dimension_value', selected_section,
            dimension_info=('課', selected_section)
        )

        # 5. チーム (Team) Filter
        team_options = get_cascaded_options(
            current_df, 'team', privilege_mgr, current_privilege
        )

        selected_team = st.selectbox(
            "チーム",
            ["すべて"] + team_options,
            key="unified_team"
        )
        selected_filters['team'] = selected_team

        if should_reset_child_filters('unified_team', selected_team):
            reset_child_filters('team')

        current_df = apply_unified_filter(
            current_df, 'dimension_value', selected_team,
            dimension_info=('チーム', selected_team)
        )

        # 6. プロジェクト (Project) Filter
        project_options = get_cascaded_options(
            current_df, 'project', privilege_mgr, current_privilege
        )

        selected_project = st.selectbox(
            "プロジェクト",
            ["すべて"] + project_options,
            key="unified_project"
        )
        selected_filters['project'] = selected_project

        if should_reset_child_filters('unified_project', selected_project):
            reset_child_filters('project')

        current_df = apply_unified_filter(
            current_df, 'dimension_value', selected_project,
            dimension_info=('プロジェクト', selected_project)
        )

        # Set dimension_value for downstream privilege checks
        # (components.py checks if any dimension filter is active)
        if selected_section != 'すべて' or selected_team != 'すべて' or selected_project != 'すべて':
            selected_filters['dimension_value'] = 'filtered'
        else:
            selected_filters['dimension_value'] = 'すべて'

        # 7. 個人 (Individual) Filter — only show if user has individual access
        allowed_groupings = privilege_mgr.get_allowed_groupings(current_privilege) if current_privilege else []
        show_individual_filter = 'name' in allowed_groupings

        if show_individual_filter:
            # Apply section restriction for individual filter (section managers see only their section's members)
            individual_source_df = current_df
            if section_restriction:
                individual_source_df = current_df[current_df['section'].isin(section_restriction)]

            individual_options = get_cascaded_options(
                individual_source_df, 'name', privilege_mgr, current_privilege
            )

            # Sort by grade
            if individual_options:
                individual_options = sort_names_by_grade(individual_options, individual_source_df)

            selected_individual = st.selectbox(
                "個人",
                ["すべて"] + individual_options,
                key="unified_individual"
            )
        else:
            selected_individual = 'すべて'
            # Ensure session state is consistent
            st.session_state['unified_individual'] = 'すべて'

        selected_filters['individual'] = selected_individual

    # Apply individual filter (outside expander — just data logic)
    current_df = apply_unified_filter(current_df, 'individual', selected_individual)

    # Pre-filter signal_df by the same broadest scope
    scoped_signal_df = filter_dataframe_by_scope(signal_df, sidebar_scope)

    # Filter signal_df to match filtered main df
    if selected_individual != 'すべて':
        # Filter by mail_address for specific individual
        individual_mail = current_df[current_df['name'] == selected_individual]['mail_address'].unique()
        if len(individual_mail) > 0:
            filtered_signal_df = scoped_signal_df[scoped_signal_df['mail_address'].isin(individual_mail)]
        else:
            filtered_signal_df = scoped_signal_df.head(0)  # Empty
    else:
        # Filter signal_df by mail_address match
        valid_mail_addresses = current_df['mail_address'].dropna().unique()
        filtered_signal_df = scoped_signal_df[scoped_signal_df['mail_address'].isin(valid_mail_addresses)]

    return current_df, filtered_signal_df, selected_filters, grouping_choice
