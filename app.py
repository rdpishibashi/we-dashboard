"""
Work Engagement Analysis Dashboard
===================================
Work Engagement Streamlit Cloud対応インタラクティブダッシュボード
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.colors import sample_colorscale
import numpy as np
import os

# Import from local modules
from modules.config import (
    PLOTLY_CHART_KWARGS, RADAR_CHART_CONFIG, DATAFRAME_KWARGS,
    METRIC_LABELS, SIGNAL_TABLE_COLUMNS, RATING_AXIS_MAX,
    DEFAULT_FILE_PATH, RATING_BAND_HIGH_THRESHOLD, RATING_BAND_LOW_THRESHOLD,
    COLOR_SCALE_START, COLOR_SCALE_END, GROUPING_LABEL_MAP
)
from modules.utils import get_options, render_department_and_group_controls
from modules.data_loader import load_data
from modules.signal_processing import (
    apply_signal_rating_calculations, format_individual_signal_data,
    get_signal_data, render_signal_table
)
from modules.statistics import calculate_group_statistics, format_statistics_for_display
from modules.charts import (
    create_time_series_chart, create_recent_group_comparison_chart,
    create_box_plot, create_group_rating_distribution, create_radar_chart,
    create_individual_trend
)
from modules.auth import (
    render_login_ui, is_authenticated, has_privilege,
    get_current_privilege
)
from modules.privilege_manager import (
    get_privilege_manager, filter_dataframe_by_scope, apply_section_aliases,
    filter_dataframe_by_grade, anonymize_dataframe
)

# ページ設定
st.set_page_config(
    page_title="Work Engagement Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# メインアプリケーション
# =============================================================================

st.title("Work Engagement Analysis Dashboard")
st.write("ワーク・エンゲージメント分析ダッシュボード")

# サイドバー: ファイルアップロード
st.sidebar.header("📁 データアップロード")
uploaded_file = st.sidebar.file_uploader(
    "データファイルをアップロード",
    type=['xlsx', 'xls'],
    help="ワーク･エンゲージメント・データのExcelファイルをアップロードしてください"
)

# デフォルトファイルの使用
if uploaded_file is None and os.path.exists(DEFAULT_FILE_PATH):
    uploaded_file = DEFAULT_FILE_PATH
    st.sidebar.info(f"📋 デフォルトファイルを使用: {DEFAULT_FILE_PATH}")

# ログイン機能
if render_login_ui():
    st.rerun()

if uploaded_file is not None:
    # データ読み込み
    try:
        df, signal_df, comment_df = load_data(uploaded_file)
        st.sidebar.success(f"✅ データ読み込み完了: {len(df):,}件")
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        st.stop()

    # Get privilege manager for per-tab filtering
    privilege_mgr = get_privilege_manager()
    # Use 'anonymous' privilege when not authenticated
    current_privilege = get_current_privilege() if is_authenticated() else 'anonymous'

    # サイドバー: フィルター設定
    st.sidebar.header("🔍 フィルター設定")

    # 期間・組織フィルター（複数選択対応）
    filtered_df = df.copy()

    available_months = filtered_df['year_month_dt'].dropna().sort_values().unique()
    available_months = pd.to_datetime(available_months)
    if len(available_months) == 0:
        st.error("年月の情報が不足しているためフィルターを設定できません。")
        st.stop()

    default_end = available_months[-1]
    default_start = available_months[max(0, len(available_months) - 6)]
    default_period = (default_start.to_pydatetime(), default_end.to_pydatetime())

    # Initialize or reset period filter
    if "filter_period" not in st.session_state:
        st.session_state["filter_period"] = default_period
    elif st.session_state.get("reset_period_filter", False):
        st.session_state["filter_period"] = default_period
        st.session_state["reset_period_filter"] = False

    start_dt, end_dt = st.sidebar.slider(
        "期間",
        min_value=available_months[0].to_pydatetime(),
        max_value=available_months[-1].to_pydatetime(),
        format="YYYY-MM",
        key="filter_period"
    )
    start_dt = pd.Timestamp(start_dt).replace(day=1)
    end_dt = pd.Timestamp(end_dt).replace(day=1)
    selected_period_label = f"{start_dt.strftime('%Y-%m')}〜{end_dt.strftime('%Y-%m')}"

    metric_keys = list(METRIC_LABELS.keys())
    selected_metric = st.sidebar.selectbox(
        "表示指標",
        metric_keys,
        format_func=lambda x: METRIC_LABELS.get(x, x),
        key="global_metric_select"
    )

    filtered_df = filtered_df[
        (filtered_df['year_month_dt'] >= start_dt) &
        (filtered_df['year_month_dt'] <= end_dt)
    ]

    division_options = get_options(filtered_df['division'], remove_unset=True, order_key='division')
    selected_divisions = st.sidebar.multiselect(
        "部門",
        division_options,
        default=division_options,
        key="filter_divisions"
    )
    if selected_divisions:
        filtered_df = filtered_df[filtered_df['division'].isin(selected_divisions)]

    department_options = get_options(filtered_df['department'], remove_unset=True, order_key='department')
    selected_departments = st.sidebar.multiselect(
        "部署",
        department_options,
        default=department_options,
        key="filter_departments"
    )
    if selected_departments:
        filtered_df = filtered_df[filtered_df['department'].isin(selected_departments)]

    section_options = get_options(filtered_df['section'], remove_unset=False, order_key='section')
    selected_sections = st.sidebar.multiselect(
        "課",
        section_options,
        default=section_options,
        key="filter_sections"
    )
    if selected_sections:
        filtered_df = filtered_df[filtered_df['section'].isin(selected_sections)]

    team_options = get_options(filtered_df['team'], order_key='team')
    selected_teams = st.sidebar.multiselect(
        "チーム",
        team_options,
        default=team_options,
        key="filter_teams"
    )
    if selected_teams:
        filtered_df = filtered_df[filtered_df['team'].isin(selected_teams)]

    project_options = get_options(filtered_df['project'], order_key='project')
    selected_projects = st.sidebar.multiselect(
        "プロジェクト",
        project_options,
        default=project_options,
        key="filter_projects"
    )
    if selected_projects:
        filtered_df = filtered_df[filtered_df['project'].isin(selected_projects)]

    grade_options = get_options(filtered_df['grade'], order_key='grade')
    selected_grades = st.sidebar.multiselect(
        "職位",
        grade_options,
        default=grade_options,
        key="filter_grades"
    )
    if selected_grades:
        filtered_df = filtered_df[filtered_df['grade'].isin(selected_grades)]

    st.sidebar.info(f"期間: {selected_period_label}\n有効データ: {len(filtered_df):,}件 / {len(df):,}件")

    # Define tabs and grouping options based on privilege
    if is_authenticated() and current_privilege:
        tab_labels = privilege_mgr.get_allowed_tabs(current_privilege)
        base_grouping_options = privilege_mgr.get_allowed_groupings(current_privilege)
    else:
        tab_labels = ["時系列", "グループ比較", "評価", "分布"]
        base_grouping_options = ['なし', 'department', 'section', 'team', 'project']

    # Initialize tab selection on first load
    tab_key = "main_tab_selector_v2"
    if tab_key not in st.session_state:
        st.session_state[tab_key] = "時系列"

    st.radio(
        "レポート種別",
        tab_labels,
        horizontal=True,
        key=tab_key
    )

    # Always read the selected tab from session state to ensure consistency
    selected_tab = st.session_state[tab_key]

    # =============================================================================
    # 時系列 Tab
    # =============================================================================
    if selected_tab == "時系列":
        st.subheader("時系列トレンド")

        # Apply per-tab data scope filtering
        tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "時系列") if current_privilege else None
        tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
        tab_signal_df = filter_dataframe_by_scope(signal_df, tab_scope)

        ts_df, _, _, ts_group_choice = render_department_and_group_controls(
            tab_filtered_df,
            "timeseries",
            grouping_options=base_grouping_options
        )

        # Apply additional grouping scope filtering
        if current_privilege and ts_group_choice:
            grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, ts_group_choice)
            ts_df = filter_dataframe_by_scope(ts_df, grouping_scope)
            tab_signal_df = filter_dataframe_by_scope(tab_signal_df, grouping_scope)

            # Apply grade filtering when grouping by 'grade'
            if ts_group_choice == 'grade':
                grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, ts_group_choice)
                if grade_filter:
                    ts_df = filter_dataframe_by_grade(ts_df, grade_filter)
                    tab_signal_df = filter_dataframe_by_grade(tab_signal_df, grade_filter)

            # Apply section aliases when grouping by 'section'
            if ts_group_choice == 'section':
                alias_mapping = privilege_mgr.get_section_aliases(current_privilege, "時系列")
                if alias_mapping:
                    ts_df = apply_section_aliases(ts_df, alias_mapping)
                    tab_signal_df = apply_section_aliases(tab_signal_df, alias_mapping)

        if ts_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            fig = create_time_series_chart(
                ts_df,
                selected_metric,
                f'{METRIC_LABELS.get(selected_metric, selected_metric)}推移',
                ts_group_choice if ts_group_choice != 'なし' else None
            )
            st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)

            # Display measured values section (collapsible)
            with st.expander("計測値", expanded=False):
                if ts_group_choice and ts_group_choice != 'なし':
                    from modules.utils import get_category_order_with_reference

                    # Group by year_month and grouping column
                    measured_data = ts_df.groupby(['year_month', ts_group_choice])['engagement_rating'].mean().reset_index()

                    # Sort by grouping value using category order, then by year_month
                    group_values = measured_data[ts_group_choice].unique().tolist()
                    group_order = get_category_order_with_reference(ts_group_choice, group_values, ts_df)
                    measured_data[ts_group_choice] = pd.Categorical(
                        measured_data[ts_group_choice],
                        categories=group_order,
                        ordered=True
                    )
                    measured_data = measured_data.sort_values([ts_group_choice, 'year_month'])
                    measured_data[ts_group_choice] = measured_data[ts_group_choice].astype(str)

                    # Format engagement_rating with 1 decimal place
                    measured_data['engagement_rating'] = measured_data['engagement_rating'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                    )

                    # Get grouping label and remove "別" suffix
                    grouping_label = GROUPING_LABEL_MAP.get(ts_group_choice, ts_group_choice)
                    if grouping_label != 'なし':
                        grouping_label = grouping_label.replace('別', '')

                    # Rename columns to Japanese
                    measured_data = measured_data.rename(columns={
                        'year_month': '年月',
                        ts_group_choice: grouping_label,
                        'engagement_rating': 'ワーク・エンゲージメント'
                    })

                    st.dataframe(measured_data, **DATAFRAME_KWARGS)
                else:
                    # No grouping - show overall average by month
                    measured_data = ts_df.groupby('year_month')['engagement_rating'].mean().reset_index()
                    measured_data = measured_data.sort_values('year_month')

                    # Format engagement_rating with 1 decimal place
                    measured_data['engagement_rating'] = measured_data['engagement_rating'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                    )

                    # Rename columns to Japanese
                    measured_data = measured_data.rename(columns={
                        'year_month': '年月',
                        'engagement_rating': 'ワーク・エンゲージメント'
                    })

                    st.dataframe(measured_data, **DATAFRAME_KWARGS)

            # Display key statistics (collapsible)
            with st.expander("主要な指標", expanded=False):
                stats_df = calculate_group_statistics(
                    ts_df,
                    selected_metric,
                    ts_group_choice if ts_group_choice != 'なし' else None
                )
                if not stats_df.empty:
                    # Format the statistics for display
                    display_stats = format_statistics_for_display(stats_df)
                    st.dataframe(display_stats, **DATAFRAME_KWARGS)
                else:
                    st.info("統計情報を計算できません。")

            # Signal section - アクション対象候補 (認証時のみ表示)
            if is_authenticated():
                # Apply section scope filtering for アクション対象候補
                action_scope = privilege_mgr.get_section_scope(current_privilege, "アクション対象候補")
                action_signal_df = filter_dataframe_by_scope(tab_signal_df, action_scope)

                if action_scope is None or len(action_scope) > 0:
                    st.subheader("アクション対象候補（介入優先度 > 1）")

                    try:
                        signals = get_signal_data(action_signal_df, ts_df, end_dt)
                        render_signal_table(signals, SIGNAL_TABLE_COLUMNS)
                    except Exception as e:
                        st.error(f"シグナルデータの取得に失敗しました: {e}")

                # Get comment data for individuals in current graph
                valid_names = ts_df['name'].dropna().unique()
                # Get name to section mapping from the latest data
                name_section_map = ts_df.drop_duplicates('name').set_index('name')['section'].to_dict()

                # Apply section scope filtering for 共有したいこと
                share_scope = privilege_mgr.get_section_scope(current_privilege, "共有したいこと")
                share_comment_df = filter_dataframe_by_scope(comment_df, share_scope)

                # Filter comment data by names and date range
                graph_comments = share_comment_df[
                    (share_comment_df['mail_address'].isin(
                        ts_df[ts_df['name'].isin(valid_names)]['mail_address'].dropna().unique()
                    )) &
                    (share_comment_df['year_month_dt'] >= start_dt) &
                    (share_comment_df['year_month_dt'] <= end_dt)
                ].copy()

                # Add name and section columns to comments
                if not graph_comments.empty:
                    mail_to_name = ts_df.drop_duplicates('mail_address').set_index('mail_address')['name'].to_dict()
                    graph_comments['name'] = graph_comments['mail_address'].map(mail_to_name)
                    graph_comments['section'] = graph_comments['name'].map(name_section_map)

                    # Get section order from config
                    from modules.utils import GROUP_ORDER_MAP
                    section_order = GROUP_ORDER_MAP.get('section', [])

                    # Concern section - 気になった出来事や気づき (feature access check)
                    if privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
                        with st.expander("気になった出来事や気づき", expanded=False):
                            concern_data = graph_comments[graph_comments['concern'].notna()].copy()
                            if not concern_data.empty:
                                # Sort by section order, then name, then date
                                if section_order:
                                    section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                    concern_data['_section_order'] = concern_data['section'].apply(
                                        lambda x: section_order_map.get(x, len(section_order))
                                    )
                                    concern_data = concern_data.sort_values(['_section_order', 'name', 'year_month'])
                                else:
                                    concern_data = concern_data.sort_values(['section', 'name', 'year_month'])

                                # Display nested: section -> name -> content
                                sections = concern_data['section'].unique()
                                for section in sections:
                                    section_data = concern_data[concern_data['section'] == section]
                                    with st.expander(f"{section}", expanded=False):
                                        names = section_data['name'].unique()
                                        for name in names:
                                            name_data = section_data[section_data['name'] == name]
                                            with st.expander(f"{name}", expanded=False):
                                                for _, row in name_data.iterrows():
                                                    st.markdown(f"**{row['year_month']}**")
                                                    st.text(row['concern'])
                                                    st.divider()
                            else:
                                st.info("データがありません")

                    # Comment section - 共有したいこと (feature access check)
                    if privilege_mgr.has_feature_access(current_privilege, "共有したいこと") and (share_scope is None or len(share_scope) > 0):
                        with st.expander("共有したいこと", expanded=False):
                            share_data = graph_comments[graph_comments['comment'].notna()].copy()
                            if not share_data.empty:
                                # Check if names should be anonymized
                                anonymize_names = privilege_mgr.should_anonymize_section(current_privilege, "共有したいこと")

                                # Sort by section order, then name, then date
                                if section_order:
                                    section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                    share_data['_section_order'] = share_data['section'].apply(
                                        lambda x: section_order_map.get(x, len(section_order))
                                    )
                                    share_data = share_data.sort_values(['_section_order', 'name', 'year_month'])
                                else:
                                    share_data = share_data.sort_values(['section', 'name', 'year_month'])

                                # Display nested: section -> (name ->) content
                                sections = share_data['section'].unique()
                                for section in sections:
                                    section_data = share_data[share_data['section'] == section]
                                    with st.expander(f"{section}", expanded=False):
                                        if anonymize_names:
                                            # Show comments without names
                                            for _, row in section_data.iterrows():
                                                st.markdown(f"**{row['year_month']}**")
                                                st.text(row['comment'])
                                                st.divider()
                                        else:
                                            # Show comments with names
                                            names = section_data['name'].unique()
                                            for name in names:
                                                name_data = section_data[section_data['name'] == name]
                                                with st.expander(f"{name}", expanded=False):
                                                    for _, row in name_data.iterrows():
                                                        st.markdown(f"**{row['year_month']}**")
                                                        st.text(row['comment'])
                                                        st.divider()
                            else:
                                st.info("データがありません")

    # =============================================================================
    # グループ比較 Tab
    # =============================================================================
    elif selected_tab == "グループ比較":
        st.subheader("グループ比較")

        # Apply per-tab data scope filtering
        tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "グループ比較") if current_privilege else None
        tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
        tab_signal_df = filter_dataframe_by_scope(signal_df, tab_scope)

        comparison_df, _, _, comparison_group = render_department_and_group_controls(
            tab_filtered_df,
            "group_comparison",
            grouping_options=base_grouping_options
        )

        # Apply additional grouping scope filtering
        if current_privilege and comparison_group:
            grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, comparison_group)
            comparison_df = filter_dataframe_by_scope(comparison_df, grouping_scope)
            tab_signal_df = filter_dataframe_by_scope(tab_signal_df, grouping_scope)

            # Apply grade filtering when grouping by 'grade'
            if comparison_group == 'grade':
                grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, comparison_group)
                if grade_filter:
                    comparison_df = filter_dataframe_by_grade(comparison_df, grade_filter)
                    tab_signal_df = filter_dataframe_by_grade(tab_signal_df, grade_filter)

            # Apply section aliases when grouping by 'section'
            if comparison_group == 'section':
                alias_mapping = privilege_mgr.get_section_aliases(current_privilege, "グループ比較")
                if alias_mapping:
                    comparison_df = apply_section_aliases(comparison_df, alias_mapping)
                    tab_signal_df = apply_section_aliases(tab_signal_df, alias_mapping)

        if comparison_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            if not comparison_group or comparison_group == 'なし':
                # Show overall bar chart without grouping
                working_df = comparison_df.dropna(subset=['year_month_dt']).copy()
                if working_df.empty:
                    st.info("比較対象のデータがありません。")
                else:
                    # Calculate monthly averages
                    summary = working_df.groupby('year_month_dt')[selected_metric].mean().reset_index()
                    summary = summary.sort_values('year_month_dt')
                    summary['month_label'] = summary['year_month_dt'].dt.strftime('%Y-%m')

                    month_labels = summary['month_label'].tolist()

                    # Create color mapping similar to grouped chart
                    if month_labels:
                        color_positions = np.linspace(COLOR_SCALE_START, COLOR_SCALE_END, len(month_labels))
                        colors = sample_colorscale('Blues', color_positions)
                        color_map = {label: colors[idx] for idx, label in enumerate(month_labels)}
                    else:
                        color_map = {}

                    title_text = f"{METRIC_LABELS.get(selected_metric, selected_metric)}（{selected_period_label}）"

                    fig = px.bar(
                        summary,
                        x='month_label',
                        y=selected_metric,
                        color='month_label',
                        category_orders={'month_label': month_labels},
                        color_discrete_map=color_map,
                        title=title_text
                    )
                    fig.update_layout(
                        xaxis_title='年月',
                        yaxis_title=METRIC_LABELS.get(selected_metric, selected_metric),
                        showlegend=False,
                        height=480
                    )
                    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
                    fig.update_traces(
                        marker_line_color='white',
                        marker_line_width=1,
                        hovertemplate=(
                            f"年月: %{{x}}<br>"
                            f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{y:.1f}}<extra></extra>"
                        )
                    )
                    st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)

                # Display measured values section (collapsible)
                with st.expander("計測値", expanded=False):
                    # No grouping - show overall average by month
                    measured_data = comparison_df.groupby('year_month')['engagement_rating'].mean().reset_index()
                    measured_data = measured_data.sort_values('year_month')

                    # Format engagement_rating with 1 decimal place
                    measured_data['engagement_rating'] = measured_data['engagement_rating'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                    )

                    # Rename columns to Japanese
                    measured_data = measured_data.rename(columns={
                        'year_month': '年月',
                        'engagement_rating': 'ワーク・エンゲージメント'
                    })

                    st.dataframe(measured_data, **DATAFRAME_KWARGS)

                # Display key statistics (collapsible)
                with st.expander("主要な指標", expanded=False):
                    stats_df = calculate_group_statistics(
                        comparison_df,
                        selected_metric,
                        None
                    )
                    if not stats_df.empty:
                        # Format the statistics for display
                        display_stats = format_statistics_for_display(stats_df)
                        st.dataframe(display_stats, **DATAFRAME_KWARGS)
                    else:
                        st.info("統計情報を計算できません。")

                # Signal section - アクション対象候補 (認証時のみ表示)
                if is_authenticated():
                    # Apply section scope filtering for アクション対象候補
                    action_scope = privilege_mgr.get_section_scope(current_privilege, "アクション対象候補")
                    action_signal_df = filter_dataframe_by_scope(tab_signal_df, action_scope)

                    if action_scope is None or len(action_scope) > 0:
                        st.subheader("アクション対象候補（介入優先度 > 1）")

                        try:
                            signals = get_signal_data(action_signal_df, comparison_df, end_dt)
                            render_signal_table(signals, SIGNAL_TABLE_COLUMNS)
                        except Exception as e:
                            st.error(f"シグナルデータの取得に失敗しました: {e}")

                    # Get comment data for individuals in current graph
                    valid_names = comparison_df['name'].dropna().unique()
                    # Get name to section mapping from the latest data
                    name_section_map = comparison_df.drop_duplicates('name').set_index('name')['section'].to_dict()

                    # Apply section scope filtering for 共有したいこと
                    share_scope = privilege_mgr.get_section_scope(current_privilege, "共有したいこと")
                    share_comment_df = filter_dataframe_by_scope(comment_df, share_scope)

                    # Filter comment data by names and date range
                    graph_comments = share_comment_df[
                        (share_comment_df['mail_address'].isin(
                            comparison_df[comparison_df['name'].isin(valid_names)]['mail_address'].dropna().unique()
                        )) &
                        (share_comment_df['year_month_dt'] >= start_dt) &
                        (share_comment_df['year_month_dt'] <= end_dt)
                    ].copy()

                    # Add name and section columns to comments
                    if not graph_comments.empty:
                        mail_to_name = comparison_df.drop_duplicates('mail_address').set_index('mail_address')['name'].to_dict()
                        graph_comments['name'] = graph_comments['mail_address'].map(mail_to_name)
                        graph_comments['section'] = graph_comments['name'].map(name_section_map)

                        # Get section order from config
                        from modules.utils import GROUP_ORDER_MAP
                        section_order = GROUP_ORDER_MAP.get('section', [])

                        # Concern section - 気になった出来事や気づき (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
                            with st.expander("気になった出来事や気づき", expanded=False):
                                concern_data = graph_comments[graph_comments['concern'].notna()].copy()
                                if not concern_data.empty:
                                    # Sort by section order, then name, then date
                                    if section_order:
                                        section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                        concern_data['_section_order'] = concern_data['section'].apply(
                                            lambda x: section_order_map.get(x, len(section_order))
                                        )
                                        concern_data = concern_data.sort_values(['_section_order', 'name', 'year_month'])
                                    else:
                                        concern_data = concern_data.sort_values(['section', 'name', 'year_month'])

                                    # Display nested: section -> name -> content
                                    sections = concern_data['section'].unique()
                                    for section in sections:
                                        section_data = concern_data[concern_data['section'] == section]
                                        with st.expander(f"{section}", expanded=False):
                                            names = section_data['name'].unique()
                                            for name in names:
                                                name_data = section_data[section_data['name'] == name]
                                                with st.expander(f"{name}", expanded=False):
                                                    for _, row in name_data.iterrows():
                                                        st.markdown(f"**{row['year_month']}**")
                                                        st.text(row['concern'])
                                                        st.divider()
                                else:
                                    st.info("データがありません")

                        # Comment section - 共有したいこと (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "共有したいこと") and (share_scope is None or len(share_scope) > 0):
                            with st.expander("共有したいこと", expanded=False):
                                share_data = graph_comments[graph_comments['comment'].notna()].copy()
                                if not share_data.empty:
                                    # Check if names should be anonymized
                                    anonymize_names = privilege_mgr.should_anonymize_section(current_privilege, "共有したいこと")

                                    # Sort by section order, then name, then date
                                    if section_order:
                                        section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                        share_data['_section_order'] = share_data['section'].apply(
                                            lambda x: section_order_map.get(x, len(section_order))
                                        )
                                        share_data = share_data.sort_values(['_section_order', 'name', 'year_month'])
                                    else:
                                        share_data = share_data.sort_values(['section', 'name', 'year_month'])

                                    # Display nested: section -> (name ->) content
                                    sections = share_data['section'].unique()
                                    for section in sections:
                                        section_data = share_data[share_data['section'] == section]
                                        with st.expander(f"{section}", expanded=False):
                                            if anonymize_names:
                                                # Show comments without names
                                                for _, row in section_data.iterrows():
                                                    st.markdown(f"**{row['year_month']}**")
                                                    st.text(row['comment'])
                                                    st.divider()
                                            else:
                                                # Show comments with names
                                                names = section_data['name'].unique()
                                                for name in names:
                                                    name_data = section_data[section_data['name'] == name]
                                                    with st.expander(f"{name}", expanded=False):
                                                        for _, row in name_data.iterrows():
                                                            st.markdown(f"**{row['year_month']}**")
                                                            st.text(row['comment'])
                                                            st.divider()
                                else:
                                    st.info("データがありません")

            else:
                comparison_fig = create_recent_group_comparison_chart(
                    comparison_df,
                    selected_metric,
                    comparison_group,
                    selected_period_label
                )
                st.plotly_chart(comparison_fig, **PLOTLY_CHART_KWARGS)

                # Display measured values section (collapsible)
                with st.expander("計測値", expanded=False):
                    from modules.utils import get_category_order_with_reference

                    # Group by grouping column and year_month
                    measured_data = comparison_df.groupby([comparison_group, 'year_month'])['engagement_rating'].mean().reset_index()

                    # Sort by grouping value using category order, then by year_month
                    group_values = measured_data[comparison_group].unique().tolist()
                    group_order = get_category_order_with_reference(comparison_group, group_values, comparison_df)
                    measured_data[comparison_group] = pd.Categorical(
                        measured_data[comparison_group],
                        categories=group_order,
                        ordered=True
                    )
                    measured_data = measured_data.sort_values([comparison_group, 'year_month'])
                    measured_data[comparison_group] = measured_data[comparison_group].astype(str)

                    # Format engagement_rating with 1 decimal place
                    measured_data['engagement_rating'] = measured_data['engagement_rating'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                    )

                    # Get grouping label and remove "別" suffix
                    grouping_label = GROUPING_LABEL_MAP.get(comparison_group, comparison_group)
                    if grouping_label != 'なし':
                        grouping_label = grouping_label.replace('別', '')

                    # Rename columns to Japanese
                    measured_data = measured_data.rename(columns={
                        comparison_group: grouping_label,
                        'year_month': '年月',
                        'engagement_rating': 'ワーク・エンゲージメント'
                    })

                    st.dataframe(measured_data, **DATAFRAME_KWARGS)

                # Display key statistics (collapsible)
                with st.expander("主要な指標", expanded=False):
                    stats_df = calculate_group_statistics(
                        comparison_df,
                        selected_metric,
                        comparison_group
                    )
                    if not stats_df.empty:
                        # Format the statistics for display
                        display_stats = format_statistics_for_display(stats_df)
                        st.dataframe(display_stats, **DATAFRAME_KWARGS)
                    else:
                        st.info("統計情報を計算できません。")

                # Signal section - アクション対象候補 (認証時のみ表示)
                if is_authenticated():
                    # Apply section scope filtering for アクション対象候補
                    action_scope = privilege_mgr.get_section_scope(current_privilege, "アクション対象候補")
                    action_signal_df = filter_dataframe_by_scope(tab_signal_df, action_scope)

                    if action_scope is None or len(action_scope) > 0:
                        st.subheader("アクション対象候補（介入優先度 > 1）")

                        try:
                            signals = get_signal_data(action_signal_df, comparison_df, end_dt)
                            display_cols = ['name', 'section', 'intervention_priority', 'trend_refined',
                                           'change_tag', 'stability']
                            render_signal_table(signals, display_cols)
                        except Exception as e:
                            st.error(f"シグナルデータの取得に失敗しました: {e}")

                    # Get comment data for individuals in current graph
                    valid_names = comparison_df['name'].dropna().unique()
                    # Get name to section mapping from the latest data
                    name_section_map = comparison_df.drop_duplicates('name').set_index('name')['section'].to_dict()

                    # Apply section scope filtering for 共有したいこと
                    share_scope = privilege_mgr.get_section_scope(current_privilege, "共有したいこと")
                    share_comment_df = filter_dataframe_by_scope(comment_df, share_scope)

                    # Filter comment data by names and date range
                    graph_comments = share_comment_df[
                        (share_comment_df['mail_address'].isin(
                            comparison_df[comparison_df['name'].isin(valid_names)]['mail_address'].dropna().unique()
                        )) &
                        (share_comment_df['year_month_dt'] >= start_dt) &
                        (share_comment_df['year_month_dt'] <= end_dt)
                    ].copy()

                    # Add name and section columns to comments
                    if not graph_comments.empty:
                        mail_to_name = comparison_df.drop_duplicates('mail_address').set_index('mail_address')['name'].to_dict()
                        graph_comments['name'] = graph_comments['mail_address'].map(mail_to_name)
                        graph_comments['section'] = graph_comments['name'].map(name_section_map)

                        # Get section order from config
                        from modules.utils import GROUP_ORDER_MAP
                        section_order = GROUP_ORDER_MAP.get('section', [])

                        # Concern section - 気になった出来事や気づき (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
                            with st.expander("気になった出来事や気づき", expanded=False):
                                concern_data = graph_comments[graph_comments['concern'].notna()].copy()
                                if not concern_data.empty:
                                    # Sort by section order, then name, then date
                                    if section_order:
                                        section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                        concern_data['_section_order'] = concern_data['section'].apply(
                                            lambda x: section_order_map.get(x, len(section_order))
                                        )
                                        concern_data = concern_data.sort_values(['_section_order', 'name', 'year_month'])
                                    else:
                                        concern_data = concern_data.sort_values(['section', 'name', 'year_month'])

                                    # Display nested: section -> name -> content
                                    sections = concern_data['section'].unique()
                                    for section in sections:
                                        section_data = concern_data[concern_data['section'] == section]
                                        with st.expander(f"{section}", expanded=False):
                                            names = section_data['name'].unique()
                                            for name in names:
                                                name_data = section_data[section_data['name'] == name]
                                                with st.expander(f"{name}", expanded=False):
                                                    for _, row in name_data.iterrows():
                                                        st.markdown(f"**{row['year_month']}**")
                                                        st.text(row['concern'])
                                                        st.divider()
                                else:
                                    st.info("データがありません")

                        # Comment section - 共有したいこと (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "共有したいこと") and (share_scope is None or len(share_scope) > 0):
                            with st.expander("共有したいこと", expanded=False):
                                share_data = graph_comments[graph_comments['comment'].notna()].copy()
                                if not share_data.empty:
                                    # Check if names should be anonymized
                                    anonymize_names = privilege_mgr.should_anonymize_section(current_privilege, "共有したいこと")

                                    # Sort by section order, then name, then date
                                    if section_order:
                                        section_order_map = {name: idx for idx, name in enumerate(section_order)}
                                        share_data['_section_order'] = share_data['section'].apply(
                                            lambda x: section_order_map.get(x, len(section_order))
                                        )
                                        share_data = share_data.sort_values(['_section_order', 'name', 'year_month'])
                                    else:
                                        share_data = share_data.sort_values(['section', 'name', 'year_month'])

                                    # Display nested: section -> (name ->) content
                                    sections = share_data['section'].unique()
                                    for section in sections:
                                        section_data = share_data[share_data['section'] == section]
                                        with st.expander(f"{section}", expanded=False):
                                            if anonymize_names:
                                                # Show comments without names
                                                for _, row in section_data.iterrows():
                                                    st.markdown(f"**{row['year_month']}**")
                                                    st.text(row['comment'])
                                                    st.divider()
                                            else:
                                                # Show comments with names
                                                names = section_data['name'].unique()
                                                for name in names:
                                                    name_data = section_data[section_data['name'] == name]
                                                    with st.expander(f"{name}", expanded=False):
                                                        for _, row in name_data.iterrows():
                                                            st.markdown(f"**{row['year_month']}**")
                                                            st.text(row['comment'])
                                                            st.divider()
                                else:
                                    st.info("データがありません")

    # =============================================================================
    # 評価 Tab
    # =============================================================================
    elif selected_tab == "評価":
        st.subheader("評価別")

        # Apply per-tab data scope filtering
        tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "評価") if current_privilege else None
        tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)

        evaluation_df, _, _, evaluation_group = render_department_and_group_controls(
            tab_filtered_df,
            "evaluation",
            grouping_options=base_grouping_options
        )

        # Apply additional grouping scope filtering
        if current_privilege and evaluation_group:
            grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, evaluation_group)
            evaluation_df = filter_dataframe_by_scope(evaluation_df, grouping_scope)

            # Apply grade filtering when grouping by 'grade'
            if evaluation_group == 'grade':
                grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, evaluation_group)
                if grade_filter:
                    evaluation_df = filter_dataframe_by_grade(evaluation_df, grade_filter)

            # Apply section aliases when grouping by 'section'
            if evaluation_group == 'section':
                alias_mapping = privilege_mgr.get_section_aliases(current_privilege, "評価")
                if alias_mapping:
                    evaluation_df = apply_section_aliases(evaluation_df, alias_mapping)

        if evaluation_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            # Preserve analysis type selection across period changes
            analysis_options = ['評価別比率', 'レーダーチャート']
            analysis_key = 'analysis_type_selector'
            analysis_idx = 0
            if analysis_key in st.session_state and st.session_state[analysis_key] in analysis_options:
                analysis_idx = analysis_options.index(st.session_state[analysis_key])

            analysis_type = st.radio(
                "レポートタイプ",
                analysis_options,
                index=analysis_idx,
                horizontal=True,
                key=analysis_key
            )

            if analysis_type == '評価別比率':
                if not evaluation_group or evaluation_group == 'なし':
                    # Show overall rating distribution by month without grouping
                    working = evaluation_df.dropna(subset=[selected_metric, 'year_month_dt']).copy()
                    if working.empty:
                        st.info("表示できるデータがありません")
                    else:
                        working['rating_band'] = np.select(
                            [
                                working[selected_metric] >= RATING_BAND_HIGH_THRESHOLD,
                                working[selected_metric] <= RATING_BAND_LOW_THRESHOLD
                            ],
                            ['高い', '低い'],
                            default='中間'
                        )

                        category_order = ['低い', '中間', '高い']
                        months = sorted(working['year_month_dt'].unique())

                        # Create base dataframe with all combinations
                        base_records = []
                        for month_dt in months:
                            for band in category_order:
                                base_records.append({
                                    'year_month_dt': month_dt,
                                    'rating_band': band
                                })
                        base_df = pd.DataFrame(base_records)

                        # Count by month and rating band
                        counts = (
                            base_df.merge(
                                working.groupby(['year_month_dt', 'rating_band'])
                                .size()
                                .reset_index(name='count'),
                                on=['year_month_dt', 'rating_band'],
                                how='left'
                            )
                            .fillna({'count': 0})
                        )
                        counts['count'] = counts['count'].astype(int)
                        totals = counts.groupby('year_month_dt')['count'].transform('sum')
                        totals = totals.replace(0, np.nan)
                        counts['ratio'] = (counts['count'] / totals * 100).fillna(0)
                        counts['month_label'] = counts['year_month_dt'].dt.strftime('%Y-%m')

                        title_text = f'{METRIC_LABELS.get(selected_metric, selected_metric)}（{selected_period_label}）'

                        fig = px.bar(
                            counts,
                            x='month_label',
                            y='ratio',
                            color='rating_band',
                            barmode='stack',
                            text='count',
                            category_orders={
                                'month_label': sorted(counts['month_label'].unique()),
                                'rating_band': category_order
                            },
                            color_discrete_map={
                                '低い': '#d9534f',
                                '中間': '#1f77b4',
                                '高い': '#5cb85c'
                            },
                            title=title_text,
                            custom_data=['month_label', 'rating_band', 'ratio']
                        )
                        fig.update_layout(
                            xaxis_title='年月',
                            yaxis_title='構成比 (%)',
                            height=500,
                            legend_title='評価'
                        )
                        fig.update_yaxes(range=[0, 100], ticksuffix='%', dtick=10)
                        fig.update_traces(
                            opacity=0.8,
                            texttemplate='%{text:.0f}',
                            textposition='inside',
                            hovertemplate=(
                                "年月: %{customdata[0]}<br>"
                                "評価: %{customdata[1]}<br>"
                                "比率: %{customdata[2]:.1f}%<extra></extra>"
                            )
                        )
                        st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)
                else:
                    fig_heat = create_group_rating_distribution(
                        evaluation_df,
                        evaluation_group,
                        selected_metric,
                        selected_period_label
                    )
                    st.plotly_chart(fig_heat, **PLOTLY_CHART_KWARGS)

            elif analysis_type == 'レーダーチャート':
                if not evaluation_group or evaluation_group == 'なし':
                    # Show overall radar chart without grouping
                    categories = ['vigor_rating', 'dedication_rating', 'absorption_rating']
                    avg_values = evaluation_df[categories].mean().tolist()
                    avg_values.append(avg_values[0])  # Close the radar

                    fig = go.Figure()
                    theta_labels = ['活力', '熱意', '没頭', '活力']
                    group_name = '全体'

                    fig.add_trace(go.Scatterpolar(
                        r=avg_values,
                        theta=theta_labels,
                        name=str(group_name),
                        mode='lines',
                        line=dict(width=3),
                        hovertemplate=(
                            f'対象：{group_name}<br>'
                            '%{theta}：%{r:.1f}<extra></extra>'
                        )
                    ))

                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, 10],
                                dtick=1
                            )
                        ),
                        title='ワーク･エンゲージメント構成要素',
                        height=500
                    )
                    st.plotly_chart(
                        fig,
                        width='stretch',
                        config=RADAR_CHART_CONFIG
                    )
                else:
                    fig_radar = create_radar_chart(
                        evaluation_df.dropna(subset=[evaluation_group]),
                        evaluation_group,
                        f'{GROUPING_LABEL_MAP.get(evaluation_group, evaluation_group)}別ワーク･エンゲージメント構成要素'
                    )
                    st.plotly_chart(
                        fig_radar,
                        width='stretch',
                        config=RADAR_CHART_CONFIG
                    )

    # =============================================================================
    # 個人 Tab
    # =============================================================================
    elif selected_tab == "個人":
        st.subheader("個人別推移")

        from modules.utils import sort_names_by_grade

        # Apply per-tab data scope filtering
        tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "個人") if current_privilege else None
        tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
        tab_signal_df = filter_dataframe_by_scope(signal_df, tab_scope)

        individual_df, _, _, individual_group_choice = render_department_and_group_controls(
            tab_filtered_df,
            "individual",
            grouping_options=base_grouping_options
        )

        # Apply additional grouping scope filtering
        if current_privilege and individual_group_choice:
            grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, individual_group_choice)
            individual_df = filter_dataframe_by_scope(individual_df, grouping_scope)
            tab_signal_df = filter_dataframe_by_scope(tab_signal_df, grouping_scope)

            # Apply grade filtering when grouping by 'grade'
            if individual_group_choice == 'grade':
                grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, individual_group_choice)
                if grade_filter:
                    individual_df = filter_dataframe_by_grade(individual_df, grade_filter)
                    tab_signal_df = filter_dataframe_by_grade(tab_signal_df, grade_filter)

        if individual_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            group_value_choice = None
            if individual_group_choice and individual_group_choice != 'なし':
                value_options = get_options(individual_df[individual_group_choice], order_key=individual_group_choice)
                if individual_group_choice == 'name':
                    value_options = sort_names_by_grade(value_options, individual_df)
                value_choices = ['すべて'] + value_options if value_options else ['すべて']

                group_value_key = 'individual_group_value'
                # Reset to default if flag is set
                if st.session_state.get("reset_local_filters", False):
                    st.session_state[group_value_key] = 'すべて'

                group_value_idx = 0
                if group_value_key in st.session_state and st.session_state[group_value_key] in value_choices:
                    group_value_idx = value_choices.index(st.session_state[group_value_key])

                group_value_choice = st.selectbox(
                    f"{GROUPING_LABEL_MAP.get(individual_group_choice, individual_group_choice)}を選択",
                    value_choices,
                    index=group_value_idx,
                    key=group_value_key
                )
                if group_value_choice != 'すべて':
                    individual_df = individual_df[individual_df[individual_group_choice] == group_value_choice]

            if individual_df.empty:
                st.info("選択された条件に該当するデータがありません。")
            else:
                individuals = sort_names_by_grade(
                    individual_df['name'].dropna().astype(str).unique().tolist(),
                    individual_df
                )

                individual_key = 'individual_selector'
                # Reset to first individual if flag is set
                if st.session_state.get("reset_local_filters", False) and individuals:
                    st.session_state[individual_key] = individuals[0]

                individual_idx = 0
                if individual_key in st.session_state and st.session_state[individual_key] in individuals:
                    individual_idx = individuals.index(st.session_state[individual_key])

                selected_individual = st.selectbox(
                    "表示対象者を選択",
                    individuals,
                    index=individual_idx,
                    key=individual_key
                )

                if selected_individual:
                    fig_ind = create_individual_trend(individual_df, selected_individual)
                    st.plotly_chart(fig_ind, **PLOTLY_CHART_KWARGS)

                    ind_data = individual_df[individual_df['name'] == selected_individual]

                    # Get mail_address for the selected individual from the full dataset
                    # Use the full df (not filtered by period) to ensure we can always get mail_address
                    individual_mail_lookup = df[df['name'] == selected_individual]
                    individual_mail = individual_mail_lookup['mail_address'].iloc[0] if not individual_mail_lookup.empty and 'mail_address' in individual_mail_lookup.columns else None

                    # Key Indicators section - Wave data table (collapsible)
                    with st.expander("計測値", expanded=False):
                        # Select and sort wave data
                        wave_data = ind_data.sort_values('year_month_dt')[
                            ['year_month', 'engagement_rating', 'vigor_rating',
                             'dedication_rating', 'absorption_rating']
                        ].copy()

                        # Format ratings with 1 decimal place
                        for col in ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']:
                            if col in wave_data.columns:
                                wave_data[col] = wave_data[col].apply(
                                    lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                                )

                        # Rename columns to Japanese
                        wave_data = wave_data.rename(columns={
                            'year_month': '年月',
                            'engagement_rating': 'エンゲージメント',
                            'vigor_rating': '活力',
                            'dedication_rating': '熱意',
                            'absorption_rating': '没頭'
                        })

                        st.dataframe(wave_data, **DATAFRAME_KWARGS)

                    if individual_mail:
                        # Filter comment data by mail_address and date range
                        individual_comments = comment_df[
                            (comment_df['mail_address'] == individual_mail) &
                            (comment_df['year_month_dt'] >= start_dt) &
                            (comment_df['year_month_dt'] <= end_dt)
                        ].copy()

                        # Concern section - 気になった出来事や気づき (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
                            with st.expander("気になった出来事や気づき", expanded=False):
                                concern_data = individual_comments[individual_comments['concern'].notna()][['year_month', 'concern']].copy()
                                if not concern_data.empty:
                                    concern_data = concern_data.sort_values('year_month')
                                    for _, row in concern_data.iterrows():
                                        st.markdown(f"**{row['year_month']}**")
                                        st.text(row['concern'])
                                        st.divider()
                                else:
                                    st.info("データがありません")

                        # Comment section - 共有したいこと (feature access check)
                        if privilege_mgr.has_feature_access(current_privilege, "共有したいこと"):
                            with st.expander("共有したいこと", expanded=False):
                                comment_data = individual_comments[individual_comments['comment'].notna()][['year_month', 'comment']].copy()
                                if not comment_data.empty:
                                    comment_data = comment_data.sort_values('year_month')
                                    for _, row in comment_data.iterrows():
                                        st.markdown(f"**{row['year_month']}**")
                                        st.text(row['comment'])
                                        st.divider()
                                else:
                                    st.info("データがありません")

                    # Signal section
                    st.subheader("シグナル")

                    try:
                        # Filter signal data for the selected individual up to end_dt
                        # Signal calculations use data from the beginning up to the end date
                        individual_signal = tab_signal_df[
                            (tab_signal_df['name'] == selected_individual) &
                            (tab_signal_df['year_month_dt'] == end_dt)
                        ]

                        if individual_signal.empty:
                            st.info(f"{end_dt.strftime('%Y-%m')}のシグナルデータがありません")
                        else:
                            # Warn about duplicates
                            if len(individual_signal) > 1:
                                st.warning(f"注意: {selected_individual}の{end_dt.strftime('%Y-%m')}データが{len(individual_signal)}件あります。最初のレコードを表示しています。")

                            # Apply calculation to rating values
                            individual_signal = apply_signal_rating_calculations(individual_signal)

                            # Format and display signal data (transposed table with labels in index)
                            display_signal_t = format_individual_signal_data(individual_signal)
                            st.dataframe(
                                display_signal_t,
                                column_config={
                                    "Index": st.column_config.TextColumn(
                                        "Index",
                                        width="large"
                                    )
                                },
                                hide_index=False,
                                width=DATAFRAME_KWARGS.get("width")
                            )

                    except Exception as e:
                        st.error(f"シグナルデータの取得に失敗しました: {e}")

    # =============================================================================
    # 分布 Tab
    # =============================================================================
    elif selected_tab == "分布":
        st.subheader("分布分析")

        # Apply per-tab data scope filtering
        tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "分布") if current_privilege else None
        tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)

        dist_df, _, _, dist_group = render_department_and_group_controls(
            tab_filtered_df,
            "distribution",
            grouping_options=base_grouping_options
        )

        # Apply additional grouping scope filtering
        if current_privilege and dist_group:
            grouping_scope = privilege_mgr.get_grouping_scope(current_privilege, dist_group)
            dist_df = filter_dataframe_by_scope(dist_df, grouping_scope)

            # Apply grade filtering when grouping by 'grade'
            if dist_group == 'grade':
                grade_filter = privilege_mgr.get_grade_filter_for_grouping(current_privilege, dist_group)
                if grade_filter:
                    dist_df = filter_dataframe_by_grade(dist_df, grade_filter)

            # Apply section aliases when grouping by 'section'
            if dist_group == 'section':
                alias_mapping = privilege_mgr.get_section_aliases(current_privilege, "分布")
                if alias_mapping:
                    dist_df = apply_section_aliases(dist_df, alias_mapping)

        if dist_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            if not dist_group or dist_group == 'なし':
                # Show overall distribution without grouping
                # Create a single box plot for all data
                fig_box = go.Figure()
                fig_box.add_trace(go.Box(
                    y=dist_df[selected_metric],
                    name='全体',
                    marker_color="#4c78a8",
                    marker_line_color="#274060",
                    marker_line_width=1.5,
                    hovertemplate=(
                        f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{y:.1f}}<extra></extra>"
                    )
                ))
                fig_box.update_layout(
                    title=f'{METRIC_LABELS.get(selected_metric, selected_metric)} 分布',
                    yaxis_title=METRIC_LABELS.get(selected_metric, selected_metric),
                    showlegend=False,
                    height=450
                )
                fig_box.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
                st.plotly_chart(fig_box, **PLOTLY_CHART_KWARGS)
            else:
                clean_df = dist_df.dropna(subset=[dist_group])
                if clean_df.empty:
                    st.info("選択された分類軸に有効なデータがありません。")
                else:
                    fig_box = create_box_plot(
                        clean_df,
                        dist_group,
                        selected_metric,
                        f'{METRIC_LABELS.get(selected_metric, selected_metric)} {GROUPING_LABEL_MAP.get(dist_group, dist_group)}分布'
                    )
                    st.plotly_chart(fig_box, **PLOTLY_CHART_KWARGS)

            # Create histogram with marginal box plot and fixed 1-step bins
            # This is shown regardless of grouping selection
            fig_hist = go.Figure()

            # Add histogram with explicit bin configuration
            fig_hist.add_trace(go.Histogram(
                x=dist_df[selected_metric],
                xbins=dict(
                    start=0,
                    end=10,
                    size=1
                ),
                marker_color="#4c78a8",
                marker_line_color='white',
                marker_line_width=1,
                hovertemplate=(
                    "範囲: %{x}<br>"
                    f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{x:.2f}}<br>"
                    "件数: %{y}<extra></extra>"
                )
            ))

            # Add marginal box plot
            fig_hist.add_trace(go.Box(
                x=dist_df[selected_metric],
                name='',
                marker_color="#4c78a8",
                showlegend=False,
                yaxis='y2',
                hovertemplate=(
                    f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{x:.1f}}<extra></extra>"
                )
            ))

            fig_hist.update_layout(
                title=f'{METRIC_LABELS.get(selected_metric, selected_metric)} ヒストグラム',
                xaxis_title=METRIC_LABELS.get(selected_metric, selected_metric),
                yaxis_title='件数',
                xaxis=dict(range=[0, RATING_AXIS_MAX], dtick=1),
                yaxis=dict(domain=[0, 0.85]),
                yaxis2=dict(domain=[0.85, 1], showticklabels=False),
                showlegend=False,
                height=450
            )

            st.plotly_chart(fig_hist, **PLOTLY_CHART_KWARGS)

    # Clear reset flags after all tabs have been processed
    if st.session_state.get("reset_local_filters", False):
        st.session_state["reset_local_filters"] = False

else:
    # ファイル未アップロード時のガイダンス
    st.info("サイドバーからデータファイルをアップロードしてください")

    st.markdown("""
    ### 使い方

    1. **データアップロード**: ワーク･エンゲージメントのデータファイル（Excel）をアップロード
    2. **フィルター設定**: サイドバーで表示対象データの期間・組織などを絞り込み
    3. **表示タブ選択**: 時系列、グループ比較、分布分析、評価別、個人別の表示分類を選択
    4. **インタラクティブ操作**: グラフ上でズーム、ホバー、凡例クリックなど
    """)

# フッター
st.sidebar.markdown("---")
st.sidebar.markdown("©RDPi Corporation")
