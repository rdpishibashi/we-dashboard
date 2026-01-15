"""
Utility Functions for Work Engagement Dashboard
"""

import json
import streamlit as st
from .config import GROUP_ORDER_FILE, GROUPING_LABEL_MAP


def load_group_orders():
    """Load group order configuration from JSON file."""
    try:
        with GROUP_ORDER_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            return {str(k): list(map(str, v)) for k, v in data.items()}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        st.warning("グループ順序設定ファイルの読み込みに失敗しました。デフォルト順序を使用します。")
        return {}


# Load group order map at module level
GROUP_ORDER_MAP = load_group_orders()

# Group order aliases
GROUP_ORDER_ALIASES = {
    'group': 'section'
}


def resolve_order_key(order_key):
    """Resolve order key using aliases."""
    if order_key is None:
        return None
    return GROUP_ORDER_ALIASES.get(order_key, order_key)


def sort_with_config(values, order_key=None):
    """Sort values using configuration or alphabetically."""
    values = list(dict.fromkeys(values))
    if not order_key:
        return sorted(values)
    config = GROUP_ORDER_MAP.get(order_key)
    if not config:
        return sorted(values)
    ordered = [val for val in config if val in values]
    remaining = [val for val in values if val not in ordered]
    ordered.extend(sorted(remaining))
    return ordered


def get_category_order_for_values(order_key, values):
    """Get category order for given values."""
    resolved_key = resolve_order_key(order_key)
    return sort_with_config(values, resolved_key)


def sort_names_by_grade(names, reference_df):
    """Sort individual names based on grade order, fallback to alphabetical."""
    if not names:
        return names
    if reference_df is None or 'name' not in reference_df.columns or 'grade' not in reference_df.columns:
        return sorted(names)
    working = reference_df[['name', 'grade']].dropna(subset=['name']).copy()
    if working.empty:
        return sorted(names)
    working['grade'] = working['grade'].fillna('未設定').astype(str)
    grade_values = working['grade'].unique().tolist()
    grade_order = get_category_order_for_values('grade', grade_values)
    grade_rank = {grade: idx for idx, grade in enumerate(grade_order)}
    if not grade_rank:
        return sorted(names)
    working['rank'] = working['grade'].map(lambda g: grade_rank.get(g, len(grade_rank)))
    name_rank = (
        working.groupby('name')['rank']
        .min()
        .to_dict()
    )
    deduped_names = list(dict.fromkeys(names))
    default_rank = len(grade_rank)
    return sorted(deduped_names, key=lambda name: (name_rank.get(name, default_rank), str(name)))


def get_category_order_with_reference(order_key, values, reference_df):
    """Get category order with reference to dataframe (for name sorting by grade)."""
    if order_key == 'name':
        return sort_names_by_grade(values, reference_df)
    return get_category_order_for_values(order_key, values)


def get_options(series, remove_unset=False, order_key=None):
    """Get unique options from series, optionally sorted and filtered."""
    opts = series.dropna().unique().tolist()
    if remove_unset:
        opts = [opt for opt in opts if opt != '未設定']
    return sort_with_config(opts, resolve_order_key(order_key))


def render_department_and_group_controls(df, tab_key, grouping_options):
    """
    Render department, group (section), and grouping controls.

    Args:
        df: DataFrame to filter
        tab_key: Unique key prefix for this tab's controls
        grouping_options: List of grouping options to display

    Returns:
        Tuple of (filtered_df, dept_choice, section_choice, grouping_choice)
    """
    dept_options = get_options(df['department'], remove_unset=True, order_key='department')
    dept_choices = ['すべて'] + dept_options if dept_options else ['すべて']
    filtered = df.copy()

    # Initialize session state for this tab if not exists
    dept_key = f"{tab_key}_department_select"
    section_key = f"{tab_key}_section_select"
    grouping_key = f"{tab_key}_grouping_select"

    col1, col2, col3 = st.columns(3)
    with col1:
        # Determine default index for department
        dept_default_idx = 0
        if dept_key in st.session_state and st.session_state[dept_key] in dept_choices:
            dept_default_idx = dept_choices.index(st.session_state[dept_key])

        dept_choice = st.selectbox(
            "部署",
            dept_choices,
            index=dept_default_idx,
            key=dept_key
        )
    if dept_choice != 'すべて':
        filtered = filtered[filtered['department'] == dept_choice]

    section_options = get_options(
        filtered['group'],
        remove_unset=True,
        order_key='group'
    )
    section_choices = ['すべて'] + section_options if section_options else ['すべて']
    with col2:
        # Determine default index for section
        section_default_idx = 0
        if section_key in st.session_state and st.session_state[section_key] in section_choices:
            section_default_idx = section_choices.index(st.session_state[section_key])

        section_choice = st.selectbox(
            "課",
            section_choices,
            index=section_default_idx,
            key=section_key
        )
    if section_choice != 'すべて':
        filtered = filtered[filtered['group'] == section_choice]

    grouping_choice = None
    format_func = lambda x: GROUPING_LABEL_MAP.get(x, x)
    if grouping_options:
        cleaned_grouping_options = []
        seen = set()
        for option in grouping_options:
            if option in seen:
                continue
            cleaned_grouping_options.append(option)
            seen.add(option)
        if cleaned_grouping_options:
            with col3:
                # Determine default index for grouping
                grouping_default_idx = 0
                if grouping_key in st.session_state and st.session_state[grouping_key] in cleaned_grouping_options:
                    grouping_default_idx = cleaned_grouping_options.index(st.session_state[grouping_key])

                grouping_choice = st.selectbox(
                    "グルーピング",
                    cleaned_grouping_options,
                    index=grouping_default_idx,
                    format_func=format_func,
                    key=grouping_key
                )
    return filtered, dept_choice, section_choice, grouping_choice
