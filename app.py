"""
Work Engagement Analysis Dashboard
===================================
Work Engagement Streamlit Cloud対応インタラクティブダッシュボード

ARCHITECTURE OVERVIEW
=====================
This dashboard displays work engagement survey data with privilege-based access control.

Data Sources:
- df: Main engagement data (ratings, demographics per person per month)
- signal_df: Calculated signal metrics (trend, intervention priority)
- comment_df: Free-text comments (concern, things to share)

Filter Hierarchy:
1. Global filters (sidebar) → applied to all DataFrames
   - Period (year_month)
   - Organization (division → department → section → team → project → grade)

2. Per-tab privilege filtering → based on user's privilege class
   - Tab visibility (which tabs user can see)
   - Tab data scope (which data rows visible in tab)
   - Grouping options (which grouping dimensions allowed)
   - Section scope (per-feature section restrictions)
   - Anonymization (hide personal names in comments)

3. Local filters (within each tab)
   - Grouping selection (部署別, 課別, etc.)
   - Individual selection (個人 tab)

Key Patterns:
- sync_filter_selection(): Hierarchical filter synchronization
- filter_dataframe_by_scope(): Apply privilege-based data restrictions
- filter_dataframe_by_grade(): Apply grade-level filtering
- apply_section_aliases(): Rename/aggregate section values

See CLAUDE.md and docs/TECHNICAL_ARCHITECTURE.md for detailed documentation.
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
    METRIC_LABELS, SIGNAL_LABELS, SIGNAL_TABLE_COLUMNS, RATING_AXIS_MAX,
    DEFAULT_FILE_PATH, RATING_BAND_HIGH_THRESHOLD, RATING_BAND_LOW_THRESHOLD,
    COLOR_SCALE_START, COLOR_SCALE_END, GROUPING_LABEL_MAP,
)
from modules.utils import get_options
from modules.data_loader import load_data
from modules.signal_processing import (
    apply_signal_rating_calculations, format_individual_signal_data,
    get_signal_data, render_signal_table
)
from modules.statistics import calculate_group_statistics, format_statistics_for_display, format_measured_data
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
from modules.components import (
    prepare_comment_data, apply_grouping_filters,
    render_action_candidates, render_concern_section, render_comment_section,
    render_comments_and_signals, filter_signal_by_selection
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

# ログイン機能
if render_login_ui():
    st.rerun()

# Initialize uploaded file from previous upload (will render uploader at bottom later)
uploaded_file = st.session_state.get('current_uploaded_file', None)
if uploaded_file is None and os.path.exists(DEFAULT_FILE_PATH):
    uploaded_file = DEFAULT_FILE_PATH
    st.session_state['current_uploaded_file'] = DEFAULT_FILE_PATH


def migrate_session_state():
    """
    Migrate from old filter system to new unified system.
    Removes old multiselect keys and initializes new unified keys.
    """
    # Old keys to remove
    old_keys = [
        # Global multiselect filters
        "filter_divisions", "_options_filter_divisions",
        "filter_departments", "_options_filter_departments",
        "filter_sections", "_options_filter_sections",
        "filter_teams", "_options_filter_teams",
        "filter_projects", "_options_filter_projects",
        "filter_grades", "_options_filter_grades",
        # Per-tab local filters (dept/section only - keep grouping)
        "timeseries_department_select", "timeseries_section_select",
        "group_comparison_department_select", "group_comparison_section_select",
        "evaluation_department_select", "evaluation_section_select",
        "distribution_department_select", "distribution_section_select",
        "individual_department_select", "individual_section_select",
    ]

    for key in old_keys:
        if key in st.session_state:
            del st.session_state[key]

    # Remove old dimension selector keys (replaced by separate 課/チーム/プロジェクト)
    for old_dim_key in ["unified_dimension", "unified_dimension_value",
                         "_prev_unified_dimension", "_prev_unified_dimension_value"]:
        if old_dim_key in st.session_state:
            del st.session_state[old_dim_key]

    # Initialize new unified keys with defaults (in cascade order)
    unified_defaults = {
        "unified_division": "すべて",
        "unified_grade": "すべて",
        "unified_department": "すべて",
        "unified_section": "すべて",
        "unified_team": "すべて",
        "unified_project": "すべて",
        "unified_individual": "すべて",
    }

    for key, default in unified_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


if uploaded_file is not None:
    # Migrate session state from old to new filter system
    migrate_session_state()
    # データ読み込み
    try:
        df, signal_df, comment_df = load_data(uploaded_file)
        # Success message will be shown in upload section at bottom
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        st.stop()

    # Get privilege manager for per-tab filtering
    privilege_mgr = get_privilege_manager()

    if not is_authenticated():
        # Pre-login welcome page — no sidebar filters, no tabs
        st.markdown("""

#### 使い方
1. **ログイン**：サイドバーからログインしてください
2. **フィルター設定**：期間・組織などを絞り込み
3. **レポート種別**：時系列、グループ比較、評価、分布、個人の各タブで分析
4. **インタラクティブ操作**：グラフ上でズーム、ホバー、凡例クリック
        """)
    else:
        # =====================================================================
        # Authenticated — show full dashboard
        # =====================================================================
        current_privilege = get_current_privilege()

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

        # Apply period filter to main DataFrame
        filtered_df = filtered_df[
            (filtered_df['year_month_dt'] >= start_dt) &
            (filtered_df['year_month_dt'] <= end_dt)
        ]

        # Apply period filter to signal DataFrame (needed for unified filters)
        filtered_signal_df = signal_df[
            (signal_df['year_month_dt'] >= start_dt) &
            (signal_df['year_month_dt'] <= end_dt)
        ].copy()

        # Define tabs and grouping options based on privilege
        tab_labels = privilege_mgr.get_allowed_tabs(current_privilege)
        base_grouping_options = privilege_mgr.get_allowed_groupings(current_privilege)

        # Unified organization filters + grouping selector
        # Renders: 表示カテゴリ + 部門 → 職位 → 部署 → (課|チーム|プロジェクト) → 個人
        from modules.filter_helpers import render_unified_sidebar_filters

        filtered_df, filtered_signal_df, selected_filters, unified_grouping = render_unified_sidebar_filters(
            filtered_df,
            filtered_signal_df,
            privilege_mgr,
            current_privilege,
            is_authenticated(),
            grouping_options=base_grouping_options
        )

        # データアップロード section (collapsible, at bottom of sidebar)
        with st.sidebar.expander("📁 データ", expanded=False):
            new_uploaded_file = st.file_uploader(
                "データファイルをアップロード",
                type=['xlsx', 'xls'],
                help="ワーク･エンゲージメント・データのExcelファイルをアップロードしてください",
                key='data_file_uploader'
            )

            if new_uploaded_file is not None:
                # Store in session state and trigger rerun
                if st.session_state.get('current_uploaded_file') != new_uploaded_file:
                    st.session_state['current_uploaded_file'] = new_uploaded_file
                    st.rerun()

            # Show current file status
            if uploaded_file == DEFAULT_FILE_PATH:
                st.info(f"📋 デフォルトファイルを使用中")
            elif uploaded_file is not None:
                st.success(f"✅ データ読み込み完了: {len(df):,}件")

        st.sidebar.info(f"期間: {selected_period_label}\n\n有効データ: {len(filtered_df):,}件 / {len(df):,}件")

        # =================================================================
        # COMMENT DATAFRAME FILTERING
        # =================================================================
        filtered_comment_df = comment_df[
            (comment_df['year_month_dt'] >= start_dt) &
            (comment_df['year_month_dt'] <= end_dt)
        ].copy()

        # =================================================================
        # TAB RENDERING (st.tabs)
        # =================================================================
        tabs = st.tabs(tab_labels)
        tab_map = dict(zip(tab_labels, tabs))

        # =============================================================
        # 時系列 Tab
        # =============================================================
        if "時系列" in tab_map:
          with tab_map["時系列"]:
            st.subheader("時系列トレンド")

            # Layer 1: Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "時系列") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
            tab_signal_df = filter_dataframe_by_scope(filtered_signal_df, tab_scope)

            # Use unified grouping from sidebar
            ts_group_choice = unified_grouping

            # Use tab_filtered_df directly (already filtered by unified sidebar)
            ts_df = tab_filtered_df

            # Apply grouping-specific filters (scope, grade, aliases, team overrides)
            ts_df, tab_signal_df = apply_grouping_filters(
                ts_df, tab_signal_df, privilege_mgr, current_privilege,
                ts_group_choice, "時系列", selected_filters
            )

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
                    group_col = ts_group_choice if ts_group_choice != 'なし' else None
                    measured_data = format_measured_data(ts_df, selected_metric, group_col)
                    st.dataframe(measured_data, **DATAFRAME_KWARGS)

                # Display key statistics (collapsible)
                with st.expander("主要な指標", expanded=False):
                    group_col = ts_group_choice if ts_group_choice != 'なし' else None
                    stats_df = calculate_group_statistics(
                        ts_df,
                        selected_metric,
                        group_col,
                        signal_df=tab_signal_df if group_col == 'name' else None,
                        end_dt=end_dt if group_col == 'name' else None
                    )
                    if not stats_df.empty:
                        display_stats = format_statistics_for_display(stats_df)
                        st.dataframe(display_stats, **DATAFRAME_KWARGS)
                    else:
                        st.info("統計情報を計算できません。")

                # Render action candidates and comment sections
                render_comments_and_signals(
                    tab_signal_df, ts_df, filtered_comment_df,
                    start_dt, end_dt, "ts",
                    privilege_mgr, current_privilege, is_authenticated()
                )

        # =============================================================
        # グループ比較 Tab
        # =============================================================
        if "グループ比較" in tab_map:
          with tab_map["グループ比較"]:
            st.subheader("グループ比較")

            # Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "グループ比較") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
            tab_signal_df = filter_dataframe_by_scope(filtered_signal_df, tab_scope)

            # Use unified grouping from sidebar
            comparison_group = unified_grouping

            comparison_df = tab_filtered_df

            # Apply grouping-specific filters (scope, grade, aliases, team overrides)
            comparison_df, tab_signal_df = apply_grouping_filters(
                comparison_df, tab_signal_df, privilege_mgr, current_privilege,
                comparison_group, "グループ比較", selected_filters
            )

            if comparison_df.empty:
                st.info("選択された条件に該当するデータがありません。")
            else:
                if not comparison_group or comparison_group == 'なし':
                    # Show overall bar chart without grouping
                    working_df = comparison_df.dropna(subset=['year_month_dt']).copy()
                    if working_df.empty:
                        st.info("比較対象のデータがありません。")
                    else:
                        summary = working_df.groupby('year_month_dt')[selected_metric].mean().reset_index()
                        summary = summary.sort_values('year_month_dt')
                        summary['month_label'] = summary['year_month_dt'].dt.strftime('%Y-%m')

                        month_labels = summary['month_label'].tolist()

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
                        measured_data = format_measured_data(comparison_df, selected_metric, None)
                        st.dataframe(measured_data, **DATAFRAME_KWARGS)

                    # Display key statistics (collapsible)
                    with st.expander("主要な指標", expanded=False):
                        stats_df = calculate_group_statistics(
                            comparison_df,
                            selected_metric,
                            None
                        )
                        if not stats_df.empty:
                            display_stats = format_statistics_for_display(stats_df)
                            st.dataframe(display_stats, **DATAFRAME_KWARGS)
                        else:
                            st.info("統計情報を計算できません。")

                    # Render action candidates and comment sections
                    render_comments_and_signals(
                        tab_signal_df, comparison_df, filtered_comment_df,
                        start_dt, end_dt, "gc_no_group",
                        privilege_mgr, current_privilege, is_authenticated()
                    )

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
                        measured_data = format_measured_data(comparison_df, selected_metric, comparison_group)
                        st.dataframe(measured_data, **DATAFRAME_KWARGS)

                    # Display key statistics (collapsible)
                    with st.expander("主要な指標", expanded=False):
                        stats_df = calculate_group_statistics(
                            comparison_df,
                            selected_metric,
                            comparison_group,
                            signal_df=tab_signal_df if comparison_group == 'name' else None,
                            end_dt=end_dt if comparison_group == 'name' else None
                        )
                        if not stats_df.empty:
                            display_stats = format_statistics_for_display(stats_df)
                            st.dataframe(display_stats, **DATAFRAME_KWARGS)
                        else:
                            st.info("統計情報を計算できません。")

                    # Render action candidates and comment sections
                    render_comments_and_signals(
                        tab_signal_df, comparison_df, filtered_comment_df,
                        start_dt, end_dt, "gc_grouped",
                        privilege_mgr, current_privilege, is_authenticated()
                    )

        # =============================================================
        # 評価 Tab
        # =============================================================
        if "評価" in tab_map:
          with tab_map["評価"]:
            st.subheader("評価別")

            # Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "評価") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)

            evaluation_group = unified_grouping
            evaluation_df = tab_filtered_df

            # Apply grouping-specific filters (scope, grade, aliases, team overrides)
            evaluation_df, _ = apply_grouping_filters(
                evaluation_df, None, privilege_mgr, current_privilege,
                evaluation_group, "評価", selected_filters
            )

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

                            base_records = []
                            for month_dt in months:
                                for band in category_order:
                                    base_records.append({
                                        'year_month_dt': month_dt,
                                        'rating_band': band
                                    })
                            base_df = pd.DataFrame(base_records)

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

        # =============================================================
        # 個人 Tab
        # =============================================================
        if "個人" in tab_map:
          with tab_map["個人"]:
            st.subheader("個人別推移")

            from modules.utils import sort_names_by_grade

            # Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "個人") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
            tab_signal_df = filter_dataframe_by_scope(filtered_signal_df, tab_scope)

            # Check if individual is already selected in sidebar
            sidebar_individual = st.session_state.get("unified_individual", "すべて")

            if sidebar_individual != "すべて":
                st.info(f"📊 表示対象: {sidebar_individual} （サイドバーで選択中）")
                selected_individual = sidebar_individual
                individual_df = tab_filtered_df
            else:
                individual_df = tab_filtered_df

                if individual_df.empty:
                    st.info("選択された条件に該当するデータがありません。")
                    selected_individual = None
                else:
                    individuals = sort_names_by_grade(
                        individual_df['name'].dropna().astype(str).unique().tolist(),
                        individual_df
                    )

                    if not individuals:
                        st.info("選択された条件に該当する個人がいません。")
                        selected_individual = None
                    else:
                        individual_key = 'individual_selector'
                        if st.session_state.get("reset_local_filters", False):
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

            # Render individual's data
            if selected_individual:
                fig_ind = create_individual_trend(individual_df, selected_individual)
                st.plotly_chart(fig_ind, **PLOTLY_CHART_KWARGS)

                ind_data = individual_df[individual_df['name'] == selected_individual]

                individual_mail_lookup = df[df['name'] == selected_individual]
                individual_mail = individual_mail_lookup['mail_address'].iloc[0] if not individual_mail_lookup.empty and 'mail_address' in individual_mail_lookup.columns else None

                # Key Indicators section - Wave data table (collapsible)
                with st.expander("計測値", expanded=False):
                    wave_data = ind_data.sort_values('year_month_dt')[
                        ['year_month', 'engagement_rating', 'vigor_rating',
                         'dedication_rating', 'absorption_rating']
                    ].copy()

                    for col in ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']:
                        if col in wave_data.columns:
                            wave_data[col] = wave_data[col].apply(
                                lambda x: f"{x:.1f}" if pd.notna(x) else "-"
                            )

                    wave_data = wave_data.rename(columns={
                        'year_month': '年月',
                        'engagement_rating': 'エンゲージメント',
                        'vigor_rating': '活力',
                        'dedication_rating': '熱意',
                        'absorption_rating': '没頭'
                    })

                    st.dataframe(wave_data, **DATAFRAME_KWARGS)

                if individual_mail:
                    individual_comments = filtered_comment_df[
                        (filtered_comment_df['mail_address'] == individual_mail)
                    ].copy()

                    # Concern section
                    if privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき"):
                        with st.expander("気になった出来事や気づき", expanded=False):
                            concern_period = st.radio(
                                "表示期間",
                                ["全期間", "直近1ヶ月"],
                                index=1,
                                horizontal=True,
                                key="ind_concern_period"
                            )
                            concern_data = individual_comments[individual_comments['concern'].notna()][['year_month', 'year_month_dt', 'concern']].copy()
                            if concern_period == "直近1ヶ月":
                                concern_data = concern_data[concern_data['year_month_dt'] == end_dt]
                            if not concern_data.empty:
                                concern_data = concern_data.sort_values('year_month', ascending=False)
                                for _, row in concern_data.iterrows():
                                    st.markdown(f"**{row['year_month']}**")
                                    st.text(row['concern'])
                                    st.divider()
                            else:
                                st.info("データがありません")

                    # Comment section
                    if privilege_mgr.has_feature_access(current_privilege, "共有したいこと"):
                        with st.expander("共有したいこと", expanded=False):
                            share_period = st.radio(
                                "表示期間",
                                ["全期間", "直近1ヶ月"],
                                index=1,
                                horizontal=True,
                                key="ind_share_period"
                            )
                            comment_data = individual_comments[individual_comments['comment'].notna()][['year_month', 'year_month_dt', 'comment']].copy()
                            if share_period == "直近1ヶ月":
                                comment_data = comment_data[comment_data['year_month_dt'] == end_dt]
                            if not comment_data.empty:
                                comment_data = comment_data.sort_values('year_month', ascending=False)
                                for _, row in comment_data.iterrows():
                                    st.markdown(f"**{row['year_month']}**")
                                    st.text(row['comment'])
                                    st.divider()
                            else:
                                st.info("データがありません")

                # Signal section
                st.subheader("シグナル")

                try:
                    individual_signal = tab_signal_df[
                        (tab_signal_df['name'] == selected_individual) &
                        (tab_signal_df['year_month_dt'] == end_dt)
                    ]

                    if individual_signal.empty:
                        st.info(f"{end_dt.strftime('%Y-%m')}のシグナルデータがありません")
                    else:
                        if len(individual_signal) > 1:
                            st.warning(f"注意: {selected_individual}の{end_dt.strftime('%Y-%m')}データが{len(individual_signal)}件あります。最初のレコードを表示しています。")

                        individual_signal = apply_signal_rating_calculations(individual_signal)

                        display_signal_t, priority_is_neg = format_individual_signal_data(individual_signal)

                        # Apply red/green color to 介入必要度 row (skip when value is ０)
                        priority_color = 'color: red' if priority_is_neg else 'color: green'
                        priority_label = SIGNAL_LABELS.get('intervention_priority', '介入必要度')

                        def style_individual_signal(df):
                            styles = pd.DataFrame('', index=df.index, columns=df.columns)
                            if priority_label in df.index:
                                val = str(df.loc[priority_label, '値']).strip()
                                if val != '０':
                                    styles.loc[priority_label] = priority_color
                            return styles

                        styled_signal = display_signal_t.style.apply(style_individual_signal, axis=None)
                        st.dataframe(
                            styled_signal,
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

        # =============================================================
        # 分布 Tab
        # =============================================================
        if "分布" in tab_map:
          with tab_map["分布"]:
            st.subheader("分布分析")

            # Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "分布") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)

            dist_group = unified_grouping
            dist_df = tab_filtered_df

            # Apply grouping-specific filters (scope, grade, aliases, team overrides)
            dist_df, _ = apply_grouping_filters(
                dist_df, None, privilege_mgr, current_privilege,
                dist_group, "分布", selected_filters
            )

            if dist_df.empty:
                st.info("選択された条件に該当するデータがありません。")
            else:
                if not dist_group or dist_group == 'なし':
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

                # Create histogram with marginal box plot
                fig_hist = go.Figure()

                fig_hist.add_trace(go.Histogram(
                    x=dist_df[selected_metric],
                    xbins=dict(start=0, end=10, size=1),
                    marker_color="#4c78a8",
                    marker_line_color='white',
                    marker_line_width=1,
                    hovertemplate=(
                        "範囲: %{x}<br>"
                        f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{x:.2f}}<br>"
                        "件数: %{y}<extra></extra>"
                    )
                ))

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
    # ファイル未アップロード時 - Show upload section in sidebar
    st.sidebar.markdown("---")
    with st.sidebar.expander("📁 データ", expanded=True):
        new_uploaded_file = st.file_uploader(
            "データファイルをアップロード",
            type=['xlsx', 'xls'],
            help="ワーク･エンゲージメント・データのExcelファイルをアップロードしてください",
            key='data_file_uploader_initial'
        )

        if new_uploaded_file is not None:
            # Store in session state and trigger rerun
            st.session_state['current_uploaded_file'] = new_uploaded_file
            st.rerun()

        st.info("データファイルをアップロードしてください")

    # ファイル未アップロード時のガイダンス
    st.info("サイドバーからデータファイルをアップロードしてください")

    st.markdown("""
    ### 使い方

    1. **ログイン**:　設定されたアカウントでログインする
    2. **フィルター設定**:　サイドバーで表示対象データの期間・組織などを絞り込み
    3. **表示タブ選択**:　時系列、グループ比較、分布分析、評価別、個人別の表示分類を選択
    4. **インタラクティブ操作**:　グラフ上でズーム、ホバー、凡例クリックなど
    """)

# フッター
st.sidebar.markdown("---")
st.sidebar.markdown("©RDPi Corporation")
