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

if uploaded_file is not None:
    # データ読み込み
    try:
        df, signal_df, comment_df = load_data(uploaded_file)
        st.sidebar.success(f"✅ データ読み込み完了: {len(df):,}件")
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        st.stop()

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
    start_dt, end_dt = st.sidebar.slider(
        "期間",
        min_value=available_months[0].to_pydatetime(),
        max_value=available_months[-1].to_pydatetime(),
        value=(
            default_start.to_pydatetime(),
            default_end.to_pydatetime()
        ),
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

    section_options = get_options(filtered_df['section'], remove_unset=True, order_key='section')
    selected_sections = st.sidebar.multiselect(
        "部門",
        section_options,
        default=section_options,
        key="filter_sections"
    )
    if selected_sections:
        filtered_df = filtered_df[filtered_df['section'].isin(selected_sections)]

    department_options = get_options(filtered_df['department'], remove_unset=True, order_key='department')
    selected_departments = st.sidebar.multiselect(
        "部署",
        department_options,
        default=department_options,
        key="filter_departments"
    )
    if selected_departments:
        filtered_df = filtered_df[filtered_df['department'].isin(selected_departments)]

    group_options = get_options(filtered_df['group'], remove_unset=False, order_key='group')
    selected_groups = st.sidebar.multiselect(
        "課",
        group_options,
        default=group_options,
        key="filter_groups"
    )
    if selected_groups:
        filtered_df = filtered_df[filtered_df['group'].isin(selected_groups)]

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

    tab_labels = [
        "時系列",
        "グループ比較",
        "評価",
        "個人",
        "分布"
    ]
    selected_tab = st.radio(
        "レポート種別",
        tab_labels,
        horizontal=True,
        index=0,
        key="main_tab_selector_v2"
    )

    # =============================================================================
    # 時系列 Tab
    # =============================================================================
    if selected_tab == "時系列":
        st.subheader("時系列トレンド")

        ts_df, _, _, ts_group_choice = render_department_and_group_controls(
            filtered_df,
            "timeseries",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade', 'name']
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

                    st.dataframe(measured_data, hide_index=True, **DATAFRAME_KWARGS)
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

                    st.dataframe(measured_data, hide_index=True, **DATAFRAME_KWARGS)

            # Display key statistics
            st.subheader("主要な指標")
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

            # Signal section - only show when grouping by individual
            if ts_group_choice == 'name':
                st.subheader("アクション対象候補（介入優先度 > 1）")

                try:
                    signals = get_signal_data(signal_df, ts_df, end_dt)
                    render_signal_table(signals, SIGNAL_TABLE_COLUMNS)
                except Exception as e:
                    st.error(f"シグナルデータの取得に失敗しました: {e}")

    # =============================================================================
    # グループ比較 Tab
    # =============================================================================
    elif selected_tab == "グループ比較":
        st.subheader("グループ比較")
        comparison_df, _, _, comparison_group = render_department_and_group_controls(
            filtered_df,
            "group_comparison",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade', 'name']
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

                    st.dataframe(measured_data, hide_index=True, **DATAFRAME_KWARGS)

                # Display key statistics
                st.subheader("主要な指標")
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

                    st.dataframe(measured_data, hide_index=True, **DATAFRAME_KWARGS)

                # Display key statistics
                st.subheader("主要な指標")
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

                # Signal section - only show when grouping by individual
                if comparison_group == 'name':
                    st.subheader("アクション対象候補（介入優先度 > 1）")

                    try:
                        signals = get_signal_data(signal_df, comparison_df, end_dt)
                        display_cols = ['name', 'intervention_priority', 'trend_refined',
                                       'change_tag', 'stability']
                        render_signal_table(signals, display_cols)
                    except Exception as e:
                        st.error(f"シグナルデータの取得に失敗しました: {e}")

    # =============================================================================
    # 評価 Tab
    # =============================================================================
    elif selected_tab == "評価":
        st.subheader("評価別")

        evaluation_df, _, _, evaluation_group = render_department_and_group_controls(
            filtered_df,
            "evaluation",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade', 'name']
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
                        use_container_width=True,
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
                        use_container_width=True,
                        config=RADAR_CHART_CONFIG
                    )

    # =============================================================================
    # 個人 Tab
    # =============================================================================
    elif selected_tab == "個人":
        st.subheader("個人別推移")

        from modules.utils import sort_names_by_grade

        individual_df, _, _, individual_group_choice = render_department_and_group_controls(
            filtered_df,
            "individual",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade', 'name']
        )
        if individual_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            group_value_choice = None
            if individual_group_choice and individual_group_choice != 'なし':
                value_options = get_options(individual_df[individual_group_choice], order_key=individual_group_choice)
                if individual_group_choice == 'name':
                    value_options = sort_names_by_grade(value_options, individual_df)
                value_choices = ['すべて'] + value_options if value_options else ['すべて']

                # Preserve selection across period changes
                group_value_key = 'individual_group_value'
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

                # Preserve individual selection across period changes
                individual_key = 'individual_selector'
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

                        st.dataframe(wave_data, hide_index=True, **DATAFRAME_KWARGS)

                    if individual_mail:
                        # Filter comment data by mail_address and date range
                        individual_comments = comment_df[
                            (comment_df['mail_address'] == individual_mail) &
                            (comment_df['year_month_dt'] >= start_dt) &
                            (comment_df['year_month_dt'] <= end_dt)
                        ].copy()

                        # Concern section - 気になった出来事や気づき
                        with st.expander("気になった出来事や気づき", expanded=False):
                            concern_data = individual_comments[individual_comments['concern'].notna()][['year_month', 'concern']].copy()
                            if not concern_data.empty:
                                concern_data = concern_data.sort_values('year_month')
                                concern_data = concern_data.rename(columns={
                                    'year_month': '年月',
                                    'concern': '気になった出来事や気づき'
                                })
                                st.dataframe(concern_data, hide_index=True, **DATAFRAME_KWARGS)
                            else:
                                st.info("データがありません")

                        # Comment section - ご意見やリクエスト
                        with st.expander("ご意見やリクエスト", expanded=False):
                            comment_data = individual_comments[individual_comments['comment'].notna()][['year_month', 'comment']].copy()
                            if not comment_data.empty:
                                comment_data = comment_data.sort_values('year_month')
                                comment_data = comment_data.rename(columns={
                                    'year_month': '年月',
                                    'comment': 'ご意見やリクエスト'
                                })
                                st.dataframe(comment_data, hide_index=True, **DATAFRAME_KWARGS)
                            else:
                                st.info("データがありません")

                    # Signal section
                    st.subheader("シグナル")

                    try:
                        # Filter signal data for the selected individual up to end_dt
                        # Signal calculations use data from the beginning up to the end date
                        individual_signal = signal_df[
                            (signal_df['name'] == selected_individual) &
                            (signal_df['year_month_dt'] == end_dt)
                        ]

                        if individual_signal.empty:
                            st.info(f"{end_dt.strftime('%Y-%m')}のシグナルデータがありません")
                        else:
                            # Warn about duplicates
                            if len(individual_signal) > 1:
                                st.warning(f"注意: {selected_individual}の{end_dt.strftime('%Y-%m')}データが{len(individual_signal)}件あります。最初のレコードを表示しています。")

                            # Apply calculation to rating values
                            individual_signal = apply_signal_rating_calculations(individual_signal)

                            # Format and display signal data
                            display_signal_t = format_individual_signal_data(individual_signal)
                            st.dataframe(
                                display_signal_t,
                                column_config={
                                    "Index": st.column_config.TextColumn(
                                        "Index",
                                        width="large"
                                    )
                                },
                                **DATAFRAME_KWARGS
                            )

                    except Exception as e:
                        st.error(f"シグナルデータの取得に失敗しました: {e}")

    # =============================================================================
    # 分布 Tab
    # =============================================================================
    elif selected_tab == "分布":
        st.subheader("分布分析")

        dist_df, _, _, dist_group = render_department_and_group_controls(
            filtered_df,
            "distribution",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade', 'name']
        )
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
st.sidebar.markdown("©RDPi Corposation")
