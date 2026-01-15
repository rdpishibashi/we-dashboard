"""
Chart Creation Functions for Work Engagement Dashboard
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from .config import (
    METRIC_LABELS, RATING_AXIS_MAX, GROUPING_LABEL_MAP,
    GROUP_LABELS, COLOR_SCALE_START, COLOR_SCALE_END,
    RATING_BAND_HIGH_THRESHOLD, RATING_BAND_LOW_THRESHOLD
)
from .utils import get_category_order_with_reference


def _create_empty_figure(message="表示できるデータがありません", height=420):
    """Create an empty figure with a message."""
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, showarrow=False)
    fig.update_layout(height=height)
    return fig


def create_time_series_chart(df, y_col, title, color_by=None):
    """時系列チャートの作成"""
    axis_title = METRIC_LABELS.get(y_col, y_col)

    if color_by and color_by != 'なし':
        # グループ別の月次平均
        grouped = df.groupby(['year_month', color_by])[y_col].mean().reset_index()
        grouped['year_month_dt'] = pd.to_datetime(grouped['year_month'], format='%Y-%m', errors='coerce')

        # カテゴリ順序の設定
        color_values = grouped[color_by].unique().tolist()
        color_order = get_category_order_with_reference(color_by, color_values, df)

        fig = px.line(
            grouped,
            x='year_month_dt',
            y=y_col,
            color=color_by,
            title=title,
            markers=True,
            category_orders={color_by: color_order}
        )

        # Get Japanese label for legend title and remove "別" suffix
        legend_title = GROUPING_LABEL_MAP.get(color_by, color_by)
        if legend_title != 'なし':
            legend_title = legend_title.replace('別', '')

        fig.update_layout(
            xaxis_title='年月',
            yaxis_title=axis_title,
            hovermode='x unified',
            height=480,
            legend_title=legend_title
        )
    else:
        # 全体の月次平均
        grouped = df.groupby('year_month')[y_col].mean().reset_index()
        grouped['year_month_dt'] = pd.to_datetime(grouped['year_month'], format='%Y-%m', errors='coerce')
        fig = px.line(
            grouped,
            x='year_month_dt',
            y=y_col,
            title=title,
            markers=True
        )

        fig.update_layout(
            xaxis_title='年月',
            yaxis_title=axis_title,
            hovermode='x unified',
            height=480
        )

    unique_dates = (
        grouped['year_month_dt']
        .dropna()
        .sort_values()
        .unique()
    )
    if 0 < len(unique_dates) <= 6:
        tickvals = [pd.Timestamp(val) for val in unique_dates]
        ticktext = [val.strftime('%Y-%m') for val in tickvals]
        fig.update_xaxes(tickmode='array', tickvals=tickvals, ticktext=ticktext)
    else:
        fig.update_xaxes(tickformat="%Y-%m")
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)

    # Update hover template based on whether grouping is used
    if color_by and color_by != 'なし':
        fig.update_traces(
            hovertemplate="%{fullData.name}: %{y:.1f}<extra></extra>"
        )
    else:
        fig.update_traces(
            hovertemplate=f"{axis_title}: %{{y:.1f}}<extra></extra>"
        )
    return fig


def create_recent_group_comparison_chart(df, metric, group_col, range_label=None):
    """選択したグループ軸ごとの期間内データ比較棒グラフ"""
    working_df = df.dropna(subset=[group_col, 'year_month_dt']).copy()
    if working_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="比較対象のデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

    summary = (
        working_df.groupby([group_col, 'year_month_dt'])[metric]
        .mean()
        .reset_index()
    )
    if summary.empty:
        fig = go.Figure()
        fig.add_annotation(text="比較対象のデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

    summary = summary.sort_values('year_month_dt')
    summary[group_col] = summary[group_col].astype(str)
    summary['month_label'] = summary['year_month_dt'].dt.strftime('%Y-%m')

    month_orders = (
        summary[['year_month_dt', 'month_label']]
        .drop_duplicates()
        .sort_values('year_month_dt')
    )
    month_labels = month_orders['month_label'].tolist()

    group_values = summary[group_col].unique().tolist()
    group_order = get_category_order_with_reference(group_col, group_values, df)
    summary[group_col] = pd.Categorical(summary[group_col], categories=group_order, ordered=True)

    if month_labels:
        color_positions = np.linspace(COLOR_SCALE_START, COLOR_SCALE_END, len(month_labels))
        colors = sample_colorscale('Blues', color_positions)
        color_map = {label: colors[idx] for idx, label in enumerate(month_labels)}
    else:
        color_map = {}

    title_text = f"{GROUP_LABELS.get(group_col, group_col)}別 {METRIC_LABELS.get(metric, metric)}"
    if range_label:
        title_text += f"（{range_label}）"

    fig = px.bar(
        summary,
        x=group_col,
        y=metric,
        color='month_label',
        barmode='group',
        category_orders={
            group_col: group_order,
            'month_label': month_labels
        },
        color_discrete_map=color_map,
        title=title_text,
        custom_data=['month_label']
    )
    fig.update_layout(
        xaxis_title=GROUP_LABELS.get(group_col, group_col),
        yaxis_title=METRIC_LABELS.get(metric, metric),
        legend_title='年-月',
        height=480,
        bargap=0.25
    )
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
    fig.update_traces(
        marker_line_color='white',
        marker_line_width=1,
        hovertemplate=(
            f"{GROUP_LABELS.get(group_col, group_col)}: %{{x}}<br>"
            f"年月: %{{customdata[0]}}<br>"
            f"{METRIC_LABELS.get(metric, metric)}: %{{y:.1f}}<extra></extra>"
        ),
        selector=dict(type='bar')
    )
    return fig


def create_box_plot(df, x_col, y_col, title):
    """ボックスプロットの作成"""
    category_order = {
        x_col: get_category_order_with_reference(
            x_col,
            df[x_col].dropna().astype(str).unique().tolist(),
            df
        )
    }
    fig = px.box(
        df,
        x=x_col,
        y=y_col,
        title=title,
        category_orders=category_order
    )

    # Get Japanese label for x-axis and remove "別" suffix
    x_label = GROUPING_LABEL_MAP.get(x_col, x_col)
    if x_label != 'なし':
        x_label = x_label.replace('別', '')

    fig.update_layout(
        xaxis_title=x_label,
        yaxis_title=METRIC_LABELS.get(y_col, y_col),
        showlegend=False,
        height=450
    )
    fig.update_traces(
        marker_color="#4c78a8",
        marker_line_color="#274060",
        marker_line_width=1.5,
        hovertemplate=(
            f"{GROUPING_LABEL_MAP.get(x_col, x_col)}: %{{x}}<br>"
            f"{METRIC_LABELS.get(y_col, y_col)}: %{{y:.1f}}<extra></extra>"
        )
    )
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
    return fig


def create_group_rating_distribution(df, group_col, metric_col, range_label=None):
    """グループ別の評価バンド構成"""
    working = df.dropna(subset=[group_col, metric_col, 'year_month_dt']).copy()
    if working.empty:
        return _create_empty_figure()

    working[group_col] = working[group_col].astype(str)
    working['rating_band'] = np.select(
        [
            working[metric_col] >= RATING_BAND_HIGH_THRESHOLD,
            working[metric_col] <= RATING_BAND_LOW_THRESHOLD
        ],
        [
            '高い',
            '低い'
        ],
        default='中間'
    )

    category_order = ['低い', '中間', '高い']
    group_month_pairs = (
        working[[group_col, 'year_month_dt']]
        .drop_duplicates()
        .sort_values([group_col, 'year_month_dt'])
    )
    pair_list_raw = [
        (row[group_col], row['year_month_dt'])
        for _, row in group_month_pairs.iterrows()
    ]
    if not pair_list_raw:
        return _create_empty_figure()

    group_months = {}
    for grp, month_dt in pair_list_raw:
        group_months.setdefault(grp, []).append(month_dt)
    group_values = list(group_months.keys())
    group_sequence = get_category_order_with_reference(group_col, group_values, df)

    ordered_pairs = []
    for grp in group_sequence:
        months = sorted(group_months.get(grp, []))
        for month_dt in months:
            ordered_pairs.append((grp, month_dt))

    if not ordered_pairs:
        return _create_empty_figure()

    base_records = []
    for grp, month_dt in ordered_pairs:
        for band in category_order:
            base_records.append({
                group_col: grp,
                'year_month_dt': month_dt,
                'rating_band': band
            })
    base_df = pd.DataFrame(base_records)

    counts = (
        base_df.merge(
            working.groupby([group_col, 'year_month_dt', 'rating_band'])
            .size()
            .reset_index(name='count'),
            on=[group_col, 'year_month_dt', 'rating_band'],
            how='left'
        )
        .fillna({'count': 0})
    )
    counts['count'] = counts['count'].astype(int)
    totals = counts.groupby([group_col, 'year_month_dt'])['count'].transform('sum')
    totals = totals.replace(0, np.nan)
    counts['ratio'] = (counts['count'] / totals * 100).fillna(0)
    counts['month_label'] = counts['year_month_dt'].dt.strftime('%Y-%m')
    counts['x_key'] = counts.apply(
        lambda row: f"{row[group_col]}__{row['month_label']}",
        axis=1
    )

    category_keys = []
    tickvals = []
    ticktext = []
    gap_rows = []
    for idx_group, grp in enumerate(group_sequence):
        months = sorted(group_months[grp])
        for idx_month, month_dt in enumerate(months):
            key = f"{grp}__{month_dt.strftime('%Y-%m')}"
            category_keys.append(key)
            tickvals.append(key)
            month_text = month_dt.strftime('%Y-%m')
            if idx_month == 0:
                ticktext.append(f"{month_text}\n{grp}")
            else:
                ticktext.append(month_text)
        if idx_group != len(group_sequence) - 1:
            gap_key = f"{grp}__gap"
            category_keys.append(gap_key)
            tickvals.append(gap_key)
            ticktext.append("")
            for band in category_order:
                gap_rows.append({
                    group_col: grp,
                    'year_month_dt': pd.NaT,
                    'rating_band': band,
                    'count': 0,
                    'ratio': 0,
                    'month_label': '',
                    'x_key': gap_key
                })

    if gap_rows:
        counts = pd.concat([counts, pd.DataFrame(gap_rows)], ignore_index=True)
    if not category_keys:
        return _create_empty_figure()

    grouping_label = GROUPING_LABEL_MAP.get(group_col, GROUP_LABELS.get(group_col, group_col))

    title_text = f"{GROUP_LABELS.get(group_col, group_col)}別 {METRIC_LABELS.get(metric_col, metric_col)}"
    if range_label:
        title_text += f"（{range_label}）"

    fig = px.bar(
        counts,
        x='x_key',
        y='ratio',
        color='rating_band',
        barmode='stack',
        text='count',
        category_orders={
            'x_key': category_keys,
            'rating_band': category_order
        },
        color_discrete_map={
            '低い': '#d9534f',
            '中間': '#1f77b4',
            '高い': '#5cb85c'
        },
        title=title_text,
        custom_data=[group_col, 'month_label', 'rating_band', 'ratio']
    )
    fig.update_layout(
        xaxis_title=f"年月 {grouping_label}",
        yaxis_title='構成比 (%)',
        height=500,
        legend_title='評価'
    )
    if tickvals:
        fig.update_xaxes(tickmode='array', tickvals=tickvals, ticktext=ticktext)
    fig.update_yaxes(range=[0, 100], ticksuffix='%', dtick=10)
    fig.update_traces(
        opacity=0.8,
        texttemplate='%{text:.0f}',
        textposition='inside',
        hovertemplate=(
            f"{GROUP_LABELS.get(group_col, group_col)}: %{{customdata[0]}}<br>"
            "年月: %{customdata[1]}<br>"
            "評価: %{customdata[2]}<br>"
            "比率: %{customdata[3]:.1f}%<extra></extra>"
        )
    )
    return fig


def create_radar_chart(df, group_col, title):
    """レーダーチャートの作成"""
    categories = ['vigor_rating', 'dedication_rating', 'absorption_rating']

    grouped = df.groupby(group_col)[categories].mean()

    # グループの順序を設定
    group_values = grouped.index.tolist()
    group_order = get_category_order_with_reference(group_col, group_values, df)

    # Get grouping label and remove "別" suffix
    grouping_label = GROUPING_LABEL_MAP.get(group_col, group_col)
    if grouping_label != 'なし':
        grouping_label = grouping_label.replace('別', '')

    fig = go.Figure()
    theta_labels = ['活力', '熱意', '没頭', '活力']

    for group_name in group_order:
        values = grouped.loc[group_name].tolist()
        values.append(values[0])  # 閉じるため

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=theta_labels,
            name=str(group_name),
            mode='lines',
            line=dict(width=3),
            hovertemplate=(
                f'{grouping_label}：{group_name}<br>'
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
        title=title,
        height=500
    )
    return fig


def create_individual_trend(df, individual_name):
    """個人の時系列トレンド"""
    ind_data = df[df['name'] == individual_name].sort_values(['year', 'month'])
    x_values = pd.to_datetime(ind_data['year_month'], format='%Y-%m', errors='coerce')

    fig = go.Figure()

    engagement_color = 'rgba(15, 76, 129, 0.5)'
    engagement_fallback = '#7bb6f9'

    def engagement_trace(color):
        return go.Bar(
            x=x_values,
            y=ind_data['engagement_rating'],
            name='エンゲージメント',
            marker=dict(color=color),
            opacity=1.0,
            hovertemplate='エンゲージメント: %{y:.1f}<extra></extra>'
        )

    try:
        fig.add_trace(engagement_trace(engagement_color))
    except ValueError:
        fig.add_trace(engagement_trace(engagement_fallback))

    line_configs = [
        ('vigor_rating', '活力', '#ff8c00'),
        ('dedication_rating', '熱意', '#b22222'),
        ('absorption_rating', '没頭', '#006d5b')
    ]

    for metric, label, color in line_configs:
        fig.add_trace(go.Scatter(
            x=x_values,
            y=ind_data[metric],
            mode='lines+markers',
            name=label,
            line=dict(color=color, width=3),
            marker=dict(color=color, size=8),
            hovertemplate=f"{label}: %{{y:.1f}}<extra></extra>"
        ))

    fig.update_layout(
        title=f'{individual_name} のワーク･エンゲージメント推移',
        barmode='overlay',
        height=480,
        yaxis=dict(range=[0, RATING_AXIS_MAX], title='Score', dtick=1),
        hovermode='x unified'
    )
    unique_dates = x_values.dropna().sort_values().unique()
    if 0 < len(unique_dates) <= 6:
        tickvals = [pd.Timestamp(val) for val in unique_dates]
        ticktext = [val.strftime('%Y-%m') for val in unique_dates]
        fig.update_xaxes(tickmode='array', tickvals=tickvals, ticktext=ticktext, title='年-月')
    else:
        fig.update_xaxes(tickformat="%Y-%m", title='年-月')
    fig.update_yaxes(dtick=1)
    return fig
