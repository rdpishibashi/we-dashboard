"""
Work Engagement Analysis Dashboard
===================================
Streamlit Cloud対応のインタラクティブダッシュボード
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
import numpy as np
import inspect
import json
from pathlib import Path

# ページ設定
st.set_page_config(
    page_title="Work Engagement Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f4e79;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

PLOTLY_CHART_KWARGS = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.plotly_chart).parameters
    else {"use_container_width": True}
)

DATAFRAME_KWARGS = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.dataframe).parameters
    else {"use_container_width": True}
)

METRIC_LABELS = {
    'engagement_rating': 'エンゲージメント',
    'vigor_rating': '活力 (Vigor)',
    'dedication_rating': '熱意 (Dedication)',
    'absorption_rating': '没頭 (Absorption)'
}

RATING_AXIS_MAX = 10.3

GROUP_ORDER_FILE = Path(__file__).with_name('group_order_config.json')


def load_group_orders():
    try:
        with GROUP_ORDER_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            return {str(k): list(map(str, v)) for k, v in data.items()}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        st.warning("グループ順序設定ファイルの読み込みに失敗しました。デフォルト順序を使用します。")
        return {}


GROUP_ORDER_MAP = load_group_orders()
GROUP_ORDER_ALIASES = {
    'group': 'section'
}


def resolve_order_key(order_key):
    if order_key is None:
        return None
    return GROUP_ORDER_ALIASES.get(order_key, order_key)


def sort_with_config(values, order_key=None):
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
    resolved_key = resolve_order_key(order_key)
    return sort_with_config(values, resolved_key)


GROUPING_LABEL_MAP = {
    'なし': 'なし',
    'department': '部別',
    'group': '課別',
    'team': 'チーム別',
    'project': 'プロジェクト別',
    'grade': '職位別'
}


def render_department_and_group_controls(
    df,
    tab_key,
    grouping_options
):
    dept_options = get_options(df['department'], remove_unset=True, order_key='department')
    dept_choices = ['すべて'] + dept_options if dept_options else ['すべて']
    filtered = df.copy()
    
    col1, col2 = st.columns(2)
    with col1:
        dept_choice = st.selectbox(
            "部を選択",
            dept_choices,
            key=f"{tab_key}_department_select"
        )
    if dept_choice != 'すべて':
        filtered = filtered[filtered['department'] == dept_choice]
    
    grouping_choice = None
    format_func = lambda x: GROUPING_LABEL_MAP.get(x, x)
    if grouping_options:
        with col2:
            grouping_choice = st.selectbox(
                "グループ化",
                grouping_options,
                format_func=format_func,
                key=f"{tab_key}_grouping_select"
            )
    return filtered, dept_choice, grouping_choice


@st.cache_data
def load_data(uploaded_file):
    """新フォーマット(workengagement.xlsx)の読み込みと整形"""
    raw_df = pd.read_excel(uploaded_file, sheet_name='rating')
    required_cols = {'year', 'month', 'mail_address', 'name', 'factor', 'rating'}
    missing_cols = required_cols - set(raw_df.columns)
    if missing_cols:
        raise ValueError(f"必要なカラムが不足しています: {', '.join(sorted(missing_cols))}")

    df = raw_df.copy()
    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    df['month'] = pd.to_numeric(df['month'], errors='coerce')
    if df['year'].isna().any() or df['month'].isna().any():
        raise ValueError("year/月の値に欠損が存在します。")
    df['year'] = df['year'].astype(int)
    df['month'] = df['month'].astype(int)

    def get_column(col_name):
        if col_name in raw_df.columns:
            return raw_df[col_name]
        return pd.Series([None] * len(raw_df))

    df['section'] = get_column('current_division')
    df['department'] = get_column('current_department')
    df['group'] = get_column('current_section')
    df['team'] = get_column('current_team')
    df['project'] = get_column('current_project')
    df['grade'] = get_column('grade')

    factor_map = {
        'エンゲージメント': 'engagement_rating',
        '活力': 'vigor_rating',
        '熱意': 'dedication_rating',
        '没頭': 'absorption_rating'
    }
    df['metric'] = df['factor'].map(factor_map)
    if df['metric'].isna().any():
        unknown = sorted(df.loc[df['metric'].isna(), 'factor'].dropna().unique())
        raise ValueError(f"未対応のfactor値があります: {', '.join(unknown)}")

    fill_cols = ['section', 'department', 'team', 'group', 'project', 'grade']
    for col in fill_cols:
        if col not in df.columns:
            df[col] = pd.Series([None] * len(df))
        df[col] = df[col].fillna('未設定')

    id_cols = ['year', 'month', 'mail_address', 'name', 'section', 'department', 'team', 'group', 'project', 'grade']
    pivot_df = (
        df[id_cols + ['metric', 'rating']]
        .pivot_table(index=id_cols, columns='metric', values='rating', aggfunc='mean')
        .reset_index()
    )
    pivot_df.columns.name = None

    pivot_df['year'] = pivot_df['year'].astype(int)
    pivot_df['month'] = pivot_df['month'].astype(int)

    for col in factor_map.values():
        if col not in pivot_df.columns:
            pivot_df[col] = np.nan

    pivot_df['year_month'] = (
        pivot_df['year'].astype(str) + '-' + pivot_df['month'].astype(str).str.zfill(2)
    )
    pivot_df['year_month_dt'] = pd.to_datetime(pivot_df['year_month'], format='%Y-%m', errors='coerce')
    return pivot_df


def create_time_series_chart(df, y_col, title, color_by=None):
    """時系列チャートの作成"""
    axis_title = METRIC_LABELS.get(y_col, y_col)

    if color_by and color_by != 'なし':
        # グループ別の月次平均
        grouped = df.groupby(['year_month', color_by])[y_col].mean().reset_index()
        grouped['year_month_dt'] = pd.to_datetime(grouped['year_month'], format='%Y-%m', errors='coerce')
        fig = px.line(
            grouped, 
            x='year_month_dt', 
            y=y_col, 
            color=color_by,
            title=title,
            markers=True
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
    fig.update_traces(
        hovertemplate=f"{axis_title}: %{{y:.1f}}<extra></extra>"
    )
    return fig


def create_recent_group_comparison_chart(df, metric, group_col, range_label=None):
    """選択したグループ軸ごとの期間内データ比較バー"""
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
    group_order = get_category_order_for_values(group_col, group_values)
    summary[group_col] = pd.Categorical(summary[group_col], categories=group_order, ordered=True)

    group_labels = {
        'section': '部門',
        'department': '部',
        'group': '課',
        'team': 'チーム',
        'project': 'プロジェクト',
        'grade': '職位'
    }

    if month_labels:
        color_positions = np.linspace(0.35, 1, len(month_labels))
        colors = sample_colorscale('Blues', color_positions)
        color_map = {label: colors[idx] for idx, label in enumerate(month_labels)}
    else:
        color_map = {}

    title_text = f"{group_labels.get(group_col, group_col)}別 {METRIC_LABELS.get(metric, metric)}"
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
        xaxis_title=group_labels.get(group_col, group_col),
        yaxis_title=METRIC_LABELS.get(metric, metric),
        legend_title='年月',
        height=480,
        bargap=0.25
    )
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
    fig.update_traces(
        marker_line_color='white',
        marker_line_width=1,
        hovertemplate=(
            f"{group_labels.get(group_col, group_col)}: %{{x}}<br>"
            f"年月: %{{customdata[0]}}<br>"
            f"{METRIC_LABELS.get(metric, metric)}: %{{y:.1f}}<extra></extra>"
        ),
        selector=dict(type='bar')
    )
    return fig


def create_box_plot(df, x_col, y_col, title):
    """ボックスプロットの作成"""
    category_order = {x_col: get_category_order_for_values(x_col, df[x_col].dropna().astype(str).unique().tolist())}
    fig = px.box(
        df, 
        x=x_col, 
        y=y_col, 
        title=title,
        color=x_col,
        category_orders=category_order
    )
    fig.update_layout(
        xaxis_title=x_col,
        yaxis_title=METRIC_LABELS.get(y_col, y_col),
        showlegend=False,
        height=450
    )
    fig.update_traces(
        hovertemplate=(
            f"{GROUPING_LABEL_MAP.get(x_col, x_col)}: %{{x}}<br>"
            f"{METRIC_LABELS.get(y_col, y_col)}: %{{y:.1f}}<extra></extra>"
        )
    )
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
    return fig


def create_group_rating_distribution(df, group_col, metric_col, range_label=None):
    """グループ別の評価バンド構成（選択期間内）"""
    working = df.dropna(subset=[group_col, metric_col, 'year_month_dt']).copy()
    if working.empty:
        fig = go.Figure()
        fig.add_annotation(text="表示できるデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

    working[group_col] = working[group_col].astype(str)
    working['rating_band'] = np.select(
        [
            working[metric_col] >= 6.0,
            working[metric_col] <= 2.0
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
        fig = go.Figure()
        fig.add_annotation(text="表示できるデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

    group_months = {}
    for grp, month_dt in pair_list_raw:
        group_months.setdefault(grp, []).append(month_dt)
    group_values = list(group_months.keys())
    group_sequence = get_category_order_for_values(group_col, group_values)

    ordered_pairs = []
    for grp in group_sequence:
        months = sorted(group_months.get(grp, []))
        for month_dt in months:
            ordered_pairs.append((grp, month_dt))

    if not ordered_pairs:
        fig = go.Figure()
        fig.add_annotation(text="表示できるデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

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
            month_num = str(int(month_dt.strftime('%m')))
            label = month_num if idx_month > 0 else f"{month_num}\n{grp}"
            ticktext.append(label)
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
        fig = go.Figure()
        fig.add_annotation(text="表示できるデータがありません", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(height=420)
        return fig

    group_labels = {
        'section': '部門',
        'department': '部',
        'group': '課',
        'team': 'チーム',
        'project': 'プロジェクト',
        'grade': '職位'
    }

    title_text = f"{group_labels.get(group_col, group_col)}別 {METRIC_LABELS.get(metric_col, metric_col)}"
    if range_label:
        title_text += f"（{range_label}）"

    fig = px.bar(
        counts,
        x='x_key',
        y='ratio',
        color='rating_band',
        barmode='stack',
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
        custom_data=[group_col, 'month_label', 'rating_band']
    )
    fig.update_layout(
        xaxis_title=group_labels.get(group_col, group_col),
        yaxis_title='構成比 (%)',
        height=500,
        legend_title='レベル'
    )
    if tickvals:
        fig.update_xaxes(tickmode='array', tickvals=tickvals, ticktext=ticktext)
    fig.update_yaxes(range=[0, 100], ticksuffix='%')
    fig.update_traces(
        hovertemplate=(
            f"{group_labels.get(group_col, group_col)}: %{{customdata[0]}}<br>"
            "年月: %{customdata[1]}<br>"
            "レベル: %{customdata[2]}<br>"
            "構成比: %{y:.1f}%<extra></extra>"
        )
    )
    return fig


def create_scatter_plot(df, x_col, y_col, color_by, title):
    """散布図の作成"""
    x_label = METRIC_LABELS.get(x_col, x_col)
    y_label = METRIC_LABELS.get(y_col, y_col)
    fig = px.scatter(
        df, 
        x=x_col, 
        y=y_col, 
        color=color_by if color_by != 'なし' else None,
        title=title,
        opacity=0.6,
        trendline='ols' if color_by == 'なし' else None
    )
    fig.update_layout(height=450)
    fig.update_yaxes(range=[0, RATING_AXIS_MAX], dtick=1)
    fig.update_traces(
        hovertemplate=(
            f"{x_label}: %{{x:.1f}}<br>"
            f"{y_label}: %{{y:.1f}}<extra></extra>"
        )
    )
    return fig


def create_radar_chart(df, group_col, title):
    """レーダーチャートの作成"""
    categories = ['vigor_rating', 'dedication_rating', 'absorption_rating']
    
    grouped = df.groupby(group_col)[categories].mean()
    
    fig = go.Figure()
    
    for group_name in grouped.index:
        values = grouped.loc[group_name].tolist()
        values.append(values[0])  # 閉じるため
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=['活力', '熱意', '没頭', '活力'],
            name=str(group_name),
            fill='toself',
            opacity=0.6,
            hovertemplate='%{theta}: %{r:.1f}<extra></extra>'
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 18])),
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
            name='Engagement',
            marker=dict(color=color),
            opacity=1.0,
            hovertemplate='Engagement: %{y:.1f}<extra></extra>'
        )

    try:
        fig.add_trace(engagement_trace(engagement_color))
    except ValueError:
        fig.add_trace(engagement_trace(engagement_fallback))
    
    line_configs = [
        ('vigor_rating', 'Vigor', '#ff8c00'),
        ('dedication_rating', 'Dedication', '#b22222'),
        ('absorption_rating', 'Absorption', '#006d5b')
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
        title=f'{individual_name} のエンゲージメント推移',
        barmode='overlay',
        height=480,
        yaxis=dict(range=[0, RATING_AXIS_MAX], title='Score', dtick=1),
        hovermode='x unified'
    )
    unique_dates = x_values.dropna().sort_values().unique()
    if 0 < len(unique_dates) <= 6:
        tickvals = [pd.Timestamp(val) for val in unique_dates]
        ticktext = [val.strftime('%Y-%m') for val in unique_dates]
        fig.update_xaxes(tickmode='array', tickvals=tickvals, ticktext=ticktext, title='年月')
    else:
        fig.update_xaxes(tickformat="%Y-%m", title='年月')
    fig.update_yaxes(dtick=1)
    return fig


# =============================================================================
# メインアプリケーション
# =============================================================================

st.markdown('<p class="main-header">📊 Work Engagement Analysis Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">UWES-9ベースのワーク・エンゲージメント分析ツール</p>', unsafe_allow_html=True)

# サイドバー: ファイルアップロード
st.sidebar.header("📁 データアップロード")
uploaded_file = st.sidebar.file_uploader(
    "Excelファイルをアップロード",
    type=['xlsx', 'xls'],
    help="workengagement.xlsx形式の'rating'シートを含むExcelファイルをアップロードしてください"
)

if uploaded_file is not None:
    # データ読み込み
    try:
        df = load_data(uploaded_file)
        st.sidebar.success(f"✅ データ読み込み完了: {len(df):,}件")
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        st.stop()
    
    # サイドバー: フィルター設定
    st.sidebar.header("🔍 フィルター設定")
    
    def get_options(series, remove_unset=False, order_key=None):
        opts = series.dropna().unique().tolist()
        if remove_unset:
            opts = [opt for opt in opts if opt != '未設定']
        return sort_with_config(opts, resolve_order_key(order_key))
    
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
        "指標",
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
        "部",
        department_options,
        default=department_options,
        key="filter_departments"
    )
    if selected_departments:
        filtered_df = filtered_df[filtered_df['department'].isin(selected_departments)]
    
    group_options = get_options(filtered_df['group'], remove_unset=True, order_key='group')
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
    
    st.sidebar.info(f"📅 期間: {selected_period_label}\n📊 フィルター後: {len(filtered_df):,}件 / {len(df):,}件")
    
    tab_labels = [
        "時系列",
        "グループ比較",
        "分布",
        "評価",
        "個人",
        "データ"
    ]
    selected_tab = st.radio(
        "表示メニュー",
        tab_labels,
        horizontal=True,
        index=0,
        key="main_tab_selector_v2"
    )

    if selected_tab == "時系列":
        st.subheader("時系列トレンド分析")
        
        ts_df, _, ts_group_choice = render_department_and_group_controls(
            filtered_df,
            "timeseries",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade']
        )
        if ts_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            fig = create_time_series_chart(
                ts_df, 
                selected_metric, 
                f'{METRIC_LABELS.get(selected_metric, selected_metric)} の推移',
                ts_group_choice if ts_group_choice != 'なし' else None
            )
            st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)
        
        st.subheader("期間サマリー")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "エンゲージメント平均",
                f"{ts_df['engagement_rating'].mean():.1f}" if not ts_df.empty else "N/A",
                f"SD: {ts_df['engagement_rating'].std():.1f}" if not ts_df.empty else "N/A"
            )
        with col2:
            st.metric(
                "活力平均",
                f"{ts_df['vigor_rating'].mean():.1f}" if not ts_df.empty else "N/A",
                f"SD: {ts_df['vigor_rating'].std():.1f}" if not ts_df.empty else "N/A"
            )
        with col3:
            st.metric(
                "熱意平均",
                f"{ts_df['dedication_rating'].mean():.1f}" if not ts_df.empty else "N/A",
                f"SD: {ts_df['dedication_rating'].std():.1f}" if not ts_df.empty else "N/A"
            )
        with col4:
            st.metric(
                "没頭平均",
                f"{ts_df['absorption_rating'].mean():.1f}" if not ts_df.empty else "N/A",
                f"SD: {ts_df['absorption_rating'].std():.1f}" if not ts_df.empty else "N/A"
            )

    elif selected_tab == "グループ比較":
        st.subheader("グループ比較（期間内）")
        comparison_df, _, comparison_group = render_department_and_group_controls(
            filtered_df,
            "group_comparison",
            grouping_options=['department', 'group', 'team', 'project', 'grade']
        )
        if comparison_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        elif not comparison_group:
            st.info("グループ化を選択してください。")
        else:
            comparison_fig = create_recent_group_comparison_chart(
                comparison_df,
                selected_metric,
                comparison_group,
                selected_period_label
            )
            st.plotly_chart(comparison_fig, **PLOTLY_CHART_KWARGS)

    elif selected_tab == "分布":
        st.subheader("分布分析")
        
        dist_df, _, dist_group = render_department_and_group_controls(
            filtered_df,
            "distribution",
            grouping_options=['department', 'group', 'project', 'grade']
        )
        if dist_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        elif not dist_group:
            st.info("分類軸を選択してください。")
        else:
            clean_df = dist_df.dropna(subset=[dist_group])
            if clean_df.empty:
                st.info("選択された分類軸に有効なデータがありません。")
            else:
                fig_box = create_box_plot(
                    clean_df,
                    dist_group,
                    selected_metric,
                    f'{METRIC_LABELS.get(selected_metric, selected_metric)} の {GROUPING_LABEL_MAP.get(dist_group, dist_group)} 別分布'
                )
                st.plotly_chart(fig_box, **PLOTLY_CHART_KWARGS)
            
            fig_hist = px.histogram(
                dist_df,
                x=selected_metric,
                nbins=30,
                title=f'{METRIC_LABELS.get(selected_metric, selected_metric)} の分布',
                marginal='box'
            )
            fig_hist.update_traces(
                marker_line_color='white',
                marker_line_width=1,
                hovertemplate=(
                    f"{METRIC_LABELS.get(selected_metric, selected_metric)}: %{{x:.1f}}<br>"
                    "件数: %{y}<extra></extra>"
                )
            )
            st.plotly_chart(fig_hist, **PLOTLY_CHART_KWARGS)

    elif selected_tab == "評価":
        st.subheader("比較分析")
        
        evaluation_df, _, evaluation_group = render_department_and_group_controls(
            filtered_df,
            "evaluation",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade']
        )
        if evaluation_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            analysis_type = st.radio(
                "分析タイプ",
                ['ヒートマップ', 'レーダーチャート', '散布図'],
                horizontal=True,
                key='analysis_type_selector'
            )
            
            if analysis_type == 'ヒートマップ':
                if not evaluation_group or evaluation_group == 'なし':
                    st.info("ヒートマップにはグループ化を選択してください。")
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
                    st.info("レーダーチャートにはグループ化を選択してください。")
                else:
                    fig_radar = create_radar_chart(
                        evaluation_df.dropna(subset=[evaluation_group]),
                        evaluation_group,
                        f'{GROUPING_LABEL_MAP.get(evaluation_group, evaluation_group)} 別エンゲージメント構成要素'
                    )
                    st.plotly_chart(fig_radar, **PLOTLY_CHART_KWARGS)
            
            else:
                col1, col2, col3 = st.columns(3)
                with col1:
                    scatter_x = st.selectbox(
                        "X軸",
                        ['vigor_rating', 'dedication_rating', 'absorption_rating'],
                        index=0
                    )
                with col2:
                    scatter_y = st.selectbox(
                        "Y軸",
                        ['vigor_rating', 'dedication_rating', 'absorption_rating'],
                        index=1
                    )
                color_choice = evaluation_group if evaluation_group != 'なし' else 'なし'
                fig_scatter = create_scatter_plot(
                    evaluation_df,
                    scatter_x,
                    scatter_y,
                    color_choice,
                    f'{scatter_x} vs {scatter_y}'
                )
                st.plotly_chart(fig_scatter, **PLOTLY_CHART_KWARGS)

    elif selected_tab == "個人":
        st.subheader("個人別エンゲージメント推移")
        
        individual_df, _, individual_group_choice = render_department_and_group_controls(
            filtered_df,
            "individual",
            grouping_options=['なし', 'department', 'group', 'team', 'project', 'grade']
        )
        if individual_df.empty:
            st.info("選択された条件に該当するデータがありません。")
        else:
            group_value_choice = None
            if individual_group_choice and individual_group_choice != 'なし':
                value_options = get_options(individual_df[individual_group_choice], order_key=individual_group_choice)
                value_choices = ['すべて'] + value_options if value_options else ['すべて']
                group_value_choice = st.selectbox(
                    f"{GROUPING_LABEL_MAP.get(individual_group_choice, individual_group_choice)} を選択",
                    value_choices,
                    key='individual_group_value'
                )
                if group_value_choice != 'すべて':
                    individual_df = individual_df[individual_df[individual_group_choice] == group_value_choice]
            
            if individual_df.empty:
                st.info("選択された条件に該当するデータがありません。")
            else:
                individuals = sorted(individual_df['name'].dropna().unique().tolist())
                selected_individual = st.selectbox(
                    "対象者を選択",
                    individuals,
                    key='individual_selector'
                )
                
                if selected_individual:
                    fig_ind = create_individual_trend(individual_df, selected_individual)
                    st.plotly_chart(fig_ind, **PLOTLY_CHART_KWARGS)
                    
                    ind_data = individual_df[individual_df['name'] == selected_individual]
                    st.subheader(f"{selected_individual} の統計サマリー")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.dataframe(
                            ind_data[['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']].describe().round(2)
                        )
                    with col2:
                        if len(ind_data) > 1:
                            first = ind_data.iloc[0]['engagement_rating']
                            last = ind_data.iloc[-1]['engagement_rating']
                            change = ((last - first) / first * 100) if first != 0 else 0
                            st.metric(
                                "エンゲージメント変化率",
                                f"{change:+.1f}%",
                                f"初回: {first:.1f} → 最新: {last:.1f}"
                            )

    elif selected_tab == "データ":
        st.subheader("フィルター済みデータ")
        
        display_cols = st.multiselect(
            "表示するカラム",
            filtered_df.columns.tolist(),
            default=[
                'year_month',
                'name',
                'section',
                'department',
                'team',
                'group',
                'engagement_rating',
                'vigor_rating',
                'dedication_rating',
                'absorption_rating'
            ],
            key='display_cols_selector'
        )
        
        display_df = filtered_df[display_cols].sort_values(['year_month', 'name']).copy()
        rating_cols = [col for col in ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating'] if col in display_df.columns]
        for col in rating_cols:
            display_df[col] = display_df[col].map(lambda v: f"{v:.1f}" if pd.notna(v) else v)
        
        st.dataframe(
            display_df,
            height=500,
            **DATAFRAME_KWARGS
        )
        
        csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 CSVダウンロード",
            csv,
            "filtered_data.csv",
            "text/csv"
        )

else:
    # ファイル未アップロード時のガイダンス
    st.info("👈 サイドバーからExcelファイルをアップロードしてください")
    
    st.markdown("""
    ### 使い方
    
    1. **データアップロード**: workengagement.xlsx形式の`rating`シートを含むExcelファイルをアップロード
    2. **フィルター設定**: サイドバーで期間・組織などを絞り込み
    3. **分析タブ選択**: 時系列、分布、比較、個人分析から選択
    4. **インタラクティブ操作**: グラフ上でズーム、ホバー、凡例クリックなど
    
    ### 必要なデータ形式
    
    `rating`シートは、UWES各因子を1行ずつ格納したworkengagement.xlsx形式です。主なカラム:
    - `year`, `month`: 時間情報
    - `name`, `mail_address`: 個人識別
    - `current_division`, `current_department`, `current_section`, `current_team`, `current_project`, `grade`: 組織属性
    - `factor`, `rating`: 因子名（エンゲージメント/活力/熱意/没頭）とスコア
    """)

# フッター
st.sidebar.markdown("---")
st.sidebar.markdown("Built with Streamlit & Plotly")
