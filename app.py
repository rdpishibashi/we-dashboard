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
from streamlit.components.v1 import html as st_components_html
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
    find_default_data_files, RATING_BAND_HIGH_THRESHOLD, RATING_BAND_LOW_THRESHOLD,
    COLOR_SCALE_START, COLOR_SCALE_END, GROUPING_LABEL_MAP,
)
from modules.utils import get_options
from modules.data_loader import load_data
from modules.member_loader import load_members
from modules.signal_processing import (
    apply_signal_rating_calculations, format_individual_signal_data,
    get_signal_data, render_signal_table
)
from modules.statistics import (
    calculate_group_statistics, format_statistics_for_display, format_measured_data,
    format_evaluation_measured_data, format_radar_measured_data,
)
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
if uploaded_file is None:
    _defaults = find_default_data_files()
    if len(_defaults) == 1:
        uploaded_file = _defaults[0]
        st.session_state['current_uploaded_file'] = _defaults[0]
    elif len(_defaults) > 1:
        uploaded_file = _defaults  # list of paths
        st.session_state['current_uploaded_file'] = _defaults


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
        if isinstance(uploaded_file, list):
            results = [load_data(p) for p in uploaded_file]
            df = pd.concat([r[0] for r in results], ignore_index=True)
            signal_df = pd.concat([r[1] for r in results], ignore_index=True)
            comment_df = pd.concat([r[2] for r in results], ignore_index=True)
        else:
            df, signal_df, comment_df = load_data(uploaded_file)
        # Success message will be shown in upload section at bottom
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        # Allow re-upload via sidebar instead of stopping the app
        with st.sidebar.expander("データ", expanded=True):
            new_uploaded_file = st.file_uploader(
                "データファイルをアップロード",
                type=['xlsx', 'xls'],
                help="ワーク･エンゲージメント・データのExcelファイルをアップロードしてください",
                key='data_file_uploader_error'
            )
            if new_uploaded_file is not None:
                st.session_state['current_uploaded_file'] = new_uploaded_file
                st.rerun()
        st.stop()

    # Load member list from members.yaml (source of truth for member status)
    member_df = load_members()

    # Derive leave addresses from member_df (leave = retired/transferred)
    leave_addresses = set()
    if not member_df.empty and 'leave' in member_df.columns:
        leave_addresses = set(
            member_df[member_df['leave'] == 'leave']['mail_address'].dropna()
        )

    # Compute latest_year_month from full comment data (before period filtering)
    latest_year_month = comment_df['year_month_dt'].max() if not comment_df.empty else None

    # Get privilege manager for per-tab filtering
    privilege_mgr = get_privilege_manager()

    if not is_authenticated():
        # Pre-login welcome page — no sidebar filters, no tabs
        st.markdown("""

#### 機能
- **フィルター設定**：期間・組織などでの絞り込み
- **レポート種別**：時系列、カテゴリ比較、評価、分布、個人の各レポートタブで表示内容を選択
- **インタラクティブ操作**：グラフ上でズーム、全画面表示、ホバー、凡例クリックによる選択など

#### 使い方
##### ログイン
- サイドバーにあるログイン・ボックスを開く
- 職位（部長、課長、一般など）に応じて提供されたアカウントでログインする
- ログインアカウントによって見ることができるデータ範囲を制御している

##### サイド・ウィンドウでの操作
- **期間**：表示期間の調整（デフォルトは直近６ヶ月）
- **表示指標**：ワーク・エンゲージメント総合値、活力／熱意／没頭の構成要素値の選択
- **表示カテゴリ**：表示をグルーピングするカテゴリの選択
- **フィルター設定**：表示データを部署などの属性でフィルターする
- **データ**：工数データファイルのアップロード

##### メイン・ウィンドウでの操作
- **タブ**：表示するグラフ種類の選択
- **計測値**：表示しているデータの値
- **主要な指標**：表示しているデータの主要統計値
- **アクション対象候補**：アクションの必要性が高いメンバーと主要な分析値
- **幹部職に伝えたいこと**：「幹部職に伝えたいこと」の記入内容一覧

##### グラフの種類
- **時系列**：年月推移の表示カテゴリ別折れ線グラフ
- **カテゴリ比較**：年月別棒グラフ
- **評価（評価別比率）**：高い／中間／低い比率棒グラフ
- **評価（レーダーチャート）**：構成要素別レーダーチャート
- **分布**：平均／最大／最小／四分位の統計表示と点数別ヒストグラム
- **個人**：個人の時系列表示とアクション用シグナル（主要な分析値）
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

        min_dt = available_months[0].to_pydatetime()
        max_dt = available_months[-1].to_pydatetime()

        # Initialize or reset period filter
        # Both cases (key missing and reset flag set) use the same default — combine
        # them so the flag is always consumed on first authenticated render, preventing
        # it from surviving to the next rerun and resetting the slider after the user's
        # first interaction.
        if "filter_period" not in st.session_state or st.session_state.get("reset_period_filter", False):
            st.session_state["filter_period"] = default_period
            st.session_state["reset_period_filter"] = False
        else:
            # Clamp stored value into the current data's date range.
            # This prevents StreamlitValueBelowMinError when a new file
            # is uploaded with a different (e.g. narrower) date range.
            stored_start, stored_end = st.session_state["filter_period"]
            clamped_start = max(min_dt, min(stored_start, max_dt))
            clamped_end = max(min_dt, min(stored_end, max_dt))
            if clamped_start != stored_start or clamped_end != stored_end:
                st.session_state["filter_period"] = (clamped_start, clamped_end)

        start_dt, end_dt = st.sidebar.slider(
            "期間",
            min_value=min_dt,
            max_value=max_dt,
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

        # Apply period filter to main DataFrame (.copy() ensures .loc assignment is safe)
        filtered_df = filtered_df[
            (filtered_df['year_month_dt'] >= start_dt) &
            (filtered_df['year_month_dt'] <= end_dt)
        ].copy()

        # Apply period filter to signal DataFrame (needed for unified filters)
        filtered_signal_df = signal_df[
            (signal_df['year_month_dt'] >= start_dt) &
            (signal_df['year_month_dt'] <= end_dt)
        ].copy()

        # Define tabs and grouping options based on privilege
        tab_labels = privilege_mgr.get_allowed_tabs(current_privilege)
        base_grouping_options = privilege_mgr.get_allowed_groupings(current_privilege)

        # ── 表示カテゴリ (Grouping selectbox) ──
        from modules.config import GROUPING_LABEL_MAP
        _cleaned_grouping_opts = list(dict.fromkeys(base_grouping_options or ['なし'])) or ['なし']
        _grouping_key = 'unified_grouping'
        # 表示カテゴリの初期値をウィジェット生成前に設定する（key= と index= の併用警告を回避）。
        # ログイン直後は reset_filters() が unified_grouping を削除するため、ここでキーが無い。
        # その場合は「課別」(section) を既定にする。section が許可されていない権限、または
        # 保存値が現在の選択肢に無い場合は先頭にフォールバック。
        if _grouping_key not in st.session_state or st.session_state[_grouping_key] not in _cleaned_grouping_opts:
            st.session_state[_grouping_key] = (
                'section' if 'section' in _cleaned_grouping_opts else _cleaned_grouping_opts[0]
            )
        unified_grouping = st.sidebar.selectbox(
            "表示カテゴリ",
            _cleaned_grouping_opts,
            format_func=lambda x: GROUPING_LABEL_MAP.get(x, x),
            key=_grouping_key
        )

        # ── 転属・退職メンバーを含む (checkbox) ──
        # Rendered here in app.py to guarantee execution order:
        # render → read value → filter DataFrames → call filter_helpers
        include_leave = False
        if leave_addresses:
            if "include_leave_members" not in st.session_state:
                st.session_state["include_leave_members"] = False
            include_leave = st.sidebar.checkbox(
                "転属・退職メンバーを含む",
                key="include_leave_members"
            )
            if not include_leave:
                filtered_df = filtered_df[~filtered_df['mail_address'].isin(leave_addresses)]
                filtered_signal_df = filtered_signal_df[~filtered_signal_df['mail_address'].isin(leave_addresses)]
            else:
                # Leave members have current_* fields cleared by Admin GAS (→ '' or '未設定').
                # Restore their org info from members.yaml so they appear in the correct
                # department/section dropdowns and charts.
                if not member_df.empty:
                    leave_member_info = member_df[member_df['leave'] == 'leave'][
                        ['mail_address', 'division', 'department', 'section', 'team', 'project', 'grade']
                    ].copy()
                    if not leave_member_info.empty:
                        _org_cols = ['division', 'department', 'section', 'team', 'project', 'grade']
                        for col in _org_cols:
                            if col not in leave_member_info.columns:
                                continue
                            addr_to_val = leave_member_info.set_index('mail_address')[col]
                            for _fdf in [filtered_df, filtered_signal_df]:
                                if col not in _fdf.columns:
                                    continue
                                # Match leave member rows where org field is empty/unset
                                # (Admin GAS clears to '' which fillna converts to '未設定',
                                #  but handle both '' and '未設定' for safety)
                                _leave_mask = _fdf['mail_address'].isin(leave_addresses)
                                _empty_mask = _fdf[col].isin(['', '未設定']) | _fdf[col].isna()
                                _mask = _leave_mask & _empty_mask
                                if not _mask.any():
                                    continue
                                # Map mail_address → org value; use index-aligned ops to avoid shape mismatch
                                _mapped = _fdf.loc[_mask, 'mail_address'].map(addr_to_val)
                                # Keep only rows where members.yaml has a valid (non-empty) value
                                _valid = _mapped[_mapped.notna() & (_mapped != '')]
                                if not _valid.empty:
                                    _fdf.loc[_valid.index, col] = _valid

        # Unified organization filters (cascading dropdowns)
        # 表示カテゴリ and leave checkbox are already rendered above
        from modules.filter_helpers import render_unified_sidebar_filters

        filtered_df, filtered_signal_df, selected_filters, _ = render_unified_sidebar_filters(
            filtered_df,
            filtered_signal_df,
            privilege_mgr,
            current_privilege,
            is_authenticated(),
            grouping_options=None,   # grouping already rendered above
            leave_addresses=None     # leave filtering already applied above
        )

        # データアップロード section (collapsible, at bottom of sidebar)
        with st.sidebar.expander("データ", expanded=False):
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
            if isinstance(uploaded_file, list):
                names = ', '.join(os.path.basename(p) for p in uploaded_file)
                st.info(f"📋 自動読み込み中: {names}")
            elif isinstance(uploaded_file, str):
                st.info(f"📋 自動読み込み中: {os.path.basename(uploaded_file)}")
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

        # Apply sidebar organization filters to comment_df
        # (same approach as signal_df: filter by mail_address from filtered main df)
        valid_mail_addresses = filtered_df['mail_address'].dropna().unique()
        filtered_comment_df = filtered_comment_df[
            filtered_comment_df['mail_address'].isin(valid_mail_addresses)
        ]

        # =================================================================
        # TAB RENDERING (st.tabs)
        # =================================================================
        # タブを箱型（┏━┓）デザインにし、ラベルを +2pt 拡大して視認性を上げる。
        # ライト/ダークテーマ両対応のため色は無彩色の rgba を使う。
        st.markdown("""
            <style>
            .stTabs [data-baseweb="tab-list"] {
                gap: 6px;
                align-items: flex-end;
            }
            .stTabs button[data-baseweb="tab"] {
                border: 1px solid rgba(128, 128, 128, 0.5);
                border-bottom: none;
                border-radius: 10px 10px 0 0;
                padding: 4px 20px;
                background: rgba(128, 128, 128, 0.12);
            }
            .stTabs button[data-baseweb="tab"][aria-selected="true"] {
                background: transparent;
            }
            /* タブ文字: 既定 14px + 2pt(≒2.7px) */
            .stTabs button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p {
                font-size: 16.7px;
            }
            .stTabs button[data-baseweb="tab"][aria-selected="true"] [data-testid="stMarkdownContainer"] p {
                font-weight: 700;
            }
            </style>
        """, unsafe_allow_html=True)

        tabs = st.tabs(tab_labels)
        tab_map = dict(zip(tab_labels, tabs))

        # 「個人表示」ボタン（アクション対象候補テーブル下）からのタブ切替要求を処理。
        # st.tabs はプログラムからの切替 API を持たないため、親ドキュメントの
        # タブボタンを JS でクリックする。フラグはコールバックで設定される
        # （ボタン再実行時にはテーブル選択がリセットされボタン自体が消えるため、
        # 戻り値ではなく on_click + セッションフラグで受け渡す）。
        if st.session_state.pop("_jump_individual", False):
            st_components_html(
                """
                <script>
                const doc = window.parent.document;
                const tabs = doc.querySelectorAll('button[data-baseweb="tab"]');
                for (const t of tabs) {
                    if (t.innerText.trim() === "個人") { t.click(); break; }
                }
                // タブメニューから遷移したときと同様にページ上部から表示する。
                // スクロールコンテナは Streamlit のバージョンにより異なるため複数候補を順に試す。
                setTimeout(() => {
                    const containers = [
                        doc.querySelector('section[data-testid="stMain"]'),
                        doc.querySelector('section.main'),
                        doc.querySelector('[data-testid="stAppViewContainer"]'),
                    ];
                    for (const c of containers) {
                        if (c) { c.scrollTo({top: 0, behavior: "instant"}); }
                    }
                    window.parent.scrollTo({top: 0, behavior: "instant"});
                }, 100);
                </script>
                """,
                height=0,
            )

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
                        signal_df=tab_signal_df,
                        end_dt=end_dt,
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
                    privilege_mgr, current_privilege, is_authenticated(),
                    latest_year_month, member_df, selected_filters
                )

        # =============================================================
        # カテゴリ比較 Tab
        # =============================================================
        if "カテゴリ比較" in tab_map:
          with tab_map["カテゴリ比較"]:
            st.subheader("カテゴリ比較")

            # Apply per-tab data scope filtering
            tab_scope = privilege_mgr.get_data_scope_for_tab(current_privilege, "カテゴリ比較") if current_privilege else None
            tab_filtered_df = filter_dataframe_by_scope(filtered_df, tab_scope)
            tab_signal_df = filter_dataframe_by_scope(filtered_signal_df, tab_scope)

            # Use unified grouping from sidebar
            comparison_group = unified_grouping

            comparison_df = tab_filtered_df

            # Apply grouping-specific filters (scope, grade, aliases, team overrides)
            comparison_df, tab_signal_df = apply_grouping_filters(
                comparison_df, tab_signal_df, privilege_mgr, current_privilege,
                comparison_group, "カテゴリ比較", selected_filters
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
                            height=480                        )
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
                            None,
                            signal_df=tab_signal_df,
                            end_dt=end_dt,
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
                        privilege_mgr, current_privilege, is_authenticated(),
                        latest_year_month, member_df, selected_filters
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
                            signal_df=tab_signal_df,
                            end_dt=end_dt,
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
                        privilege_mgr, current_privilege, is_authenticated(),
                        latest_year_month, member_df, selected_filters
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

                            with st.expander("計測値", expanded=False):
                                eval_measured = format_evaluation_measured_data(
                                    working, selected_metric, None
                                )
                                st.dataframe(eval_measured, **DATAFRAME_KWARGS)
                    else:
                        fig_heat = create_group_rating_distribution(
                            evaluation_df,
                            evaluation_group,
                            selected_metric,
                            selected_period_label
                        )
                        st.plotly_chart(fig_heat, **PLOTLY_CHART_KWARGS)

                        with st.expander("計測値", expanded=False):
                            eval_measured = format_evaluation_measured_data(
                                evaluation_df, selected_metric, evaluation_group
                            )
                            st.dataframe(eval_measured, **DATAFRAME_KWARGS)

                elif analysis_type == 'レーダーチャート':
                    if not evaluation_group or evaluation_group == 'なし':
                        # theta order: 熱意→活力→没頭 (熱意を12時、活力を11時方向に)
                        avg = evaluation_df[['dedication_rating', 'vigor_rating', 'absorption_rating']].mean()
                        avg_values = [avg['dedication_rating'], avg['vigor_rating'], avg['absorption_rating']]
                        avg_values.append(avg_values[0])  # Close the radar

                        fig = go.Figure()
                        theta_labels = ['熱意', '活力', '没頭', '熱意']
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
                                angularaxis=dict(rotation=330, direction='counterclockwise'),
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

                        with st.expander("計測値", expanded=False):
                            radar_measured = format_radar_measured_data(evaluation_df)
                            st.dataframe(radar_measured, **DATAFRAME_KWARGS)
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

                        with st.expander("計測値", expanded=False):
                            radar_measured = format_radar_measured_data(
                                evaluation_df.dropna(subset=[evaluation_group]),
                                evaluation_group,
                                reference_df=evaluation_df,
                            )
                            st.dataframe(radar_measured, **DATAFRAME_KWARGS)

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

                        # Transfer navigation request from action candidates.
                        # Consumed here so it does not persist across reruns.
                        # Signal all action candidate tables to reset their row
                        # selection on the next rerun (user has seen the report).
                        if "_nav_individual" in st.session_state:
                            nav_name = st.session_state["_nav_individual"]
                            del st.session_state["_nav_individual"]
                            if nav_name in individuals:
                                st.session_state[individual_key] = nav_name
                            st.session_state["_clear_action_selection"] = True
                            # Note: st.tabs() tab switches do not trigger reruns,
                            # so the selection cannot be cleared the instant the
                            # user returns to 時系列/カテゴリ比較. The flag is
                            # processed on the next user-initiated interaction.

                        # Ensure a valid value exists before widget creation.
                        # Do NOT pass index= with key= — combining them causes a
                        # Streamlit warning when session state is also set via API.
                        if individual_key not in st.session_state or st.session_state[individual_key] not in individuals:
                            st.session_state[individual_key] = individuals[0]

                        selected_individual = st.selectbox(
                            "表示対象者を選択",
                            individuals,
                            key=individual_key
                        )

            # Render individual's data
            if selected_individual:
                fig_ind = create_individual_trend(individual_df, selected_individual)
                st.plotly_chart(fig_ind, **PLOTLY_CHART_KWARGS)

                ind_data = individual_df[individual_df['name'] == selected_individual]

                individual_mail_lookup = df[df['name'] == selected_individual]
                individual_mail = individual_mail_lookup['mail_address'].iloc[0] if not individual_mail_lookup.empty and 'mail_address' in individual_mail_lookup.columns else None

                # Profile section (above 計測値)
                with st.expander("プロフィール", expanded=False):
                    profile_row = tab_signal_df[
                        (tab_signal_df['name'] == selected_individual) &
                        (tab_signal_df['year_month_dt'] == end_dt)
                    ]
                    if profile_row.empty:
                        # Fall back to latest available record for this individual
                        profile_row = tab_signal_df[
                            tab_signal_df['name'] == selected_individual
                        ].sort_values('year_month_dt', ascending=False)

                    if not profile_row.empty:
                        pr = profile_row.iloc[0]
                        profile_fields = [
                            ('部門',       pr.get('division',   '')),
                            ('部署',       pr.get('department', '')),
                            ('課',         pr.get('section',    '')),
                            ('チーム',     pr.get('team',       '')),
                            ('プロジェクト', pr.get('project',   '')),
                            ('職位',       pr.get('grade',      '')),
                        ]
                        profile_df = pd.DataFrame(
                            [(k, str(v) if pd.notna(v) and v != '' else '-') for k, v in profile_fields],
                            columns=['項目', '値']
                        )
                        st.dataframe(profile_df, **DATAFRAME_KWARGS)
                    else:
                        st.info("プロフィール情報がありません")

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

                # Signal section (between 計測値 and コメント)
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
                        # height=510 shows all 13 rows without scrolling (13×35px + 38px header)
                        st.dataframe(
                            styled_signal,
                            column_config={
                                "Index": st.column_config.TextColumn(
                                    "Index",
                                    width="large"
                                )
                            },
                            hide_index=False,
                            height=510,
                            width=DATAFRAME_KWARGS.get("width")
                        )

                except Exception as e:
                    st.error(f"シグナルデータの取得に失敗しました: {e}")

                # Comment section
                if individual_mail:
                    individual_comments = filtered_comment_df[
                        (filtered_comment_df['mail_address'] == individual_mail)
                    ].copy()

                    has_concern = privilege_mgr.has_feature_access(current_privilege, "気になった出来事や気づき")
                    has_share = privilege_mgr.has_feature_access(current_privilege, "幹部職に伝えたいこと")

                    if has_concern or has_share:
                        st.subheader("コメント")

                    if has_concern:
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

                    if has_share:
                        with st.expander("幹部職に伝えたいこと", expanded=False):
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
                                import sys
                                if sys.platform in ("darwin", "win32"):
                                    from modules.response_manager_local import (
                                        load_responses, get_responses_for_comment, make_comment_key
                                    )
                                else:
                                    from modules.response_manager_cloud import (
                                        load_responses, get_responses_for_comment, make_comment_key
                                    )
                                from modules.components import _render_responses, _render_response_input
                                anonymize_names = privilege_mgr.should_anonymize_section(current_privilege, "幹部職に伝えたいこと")
                                can_respond = not anonymize_names and privilege_mgr.is_response_enabled(current_privilege, "幹部職に伝えたいこと")
                                responses_df = load_responses()
                                member_email = individual_mail or ''
                                comment_data = comment_data.sort_values('year_month', ascending=False)
                                for _, row in comment_data.iterrows():
                                    st.markdown(f"**{row['year_month']}**")
                                    st.text(row['comment'])
                                    _render_responses(
                                        responses_df, row['year_month'],
                                        member_email, row['comment']
                                    )
                                    if (can_respond and latest_year_month is not None
                                            and row['year_month_dt'] == latest_year_month):
                                        comment_key = make_comment_key(
                                            row['year_month'], member_email, row['comment']
                                        )
                                        _render_response_input(
                                            "ind", comment_key,
                                            row['year_month'], member_email, row['comment']
                                        )
                                    st.divider()
                            else:
                                st.info("データがありません")

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
    #### 機能
    - **フィルター設定**：期間・組織などでの絞り込み
    - **レポート種別**：時系列、カテゴリ比較、評価、分布、個人の各レポートタブで表示内容を選択
    - **インタラクティブ操作**：グラフ上でズーム、全画面表示、ホバー、凡例クリックによる選択など

    #### 使い方
    ##### ログイン
    - サイドバーにあるログイン・ボックスを開く
    - 職位（部長、課長、一般など）に応じて提供されたアカウントでログインする
    - ログインアカウントによって見ることができるデータ範囲を制御している

    ##### サイド・ウィンドウでの操作
    - **期間**：表示期間の調整（デフォルトは直近６ヶ月）
    - **表示指標**：ワーク・エンゲージメント総合値、活力／熱意／没頭の構成要素値の選択
    - **表示カテゴリ**：表示をグルーピングするカテゴリの選択
    - **フィルター設定**：表示データを部署などの属性でフィルターする
    - **データ**：工数データファイルのアップロード

    ##### メイン・ウィンドウでの操作
    - **タブ**：表示するグラフ種類の選択
    - **計測値**：表示しているデータの値
    - **主要な指標**：表示しているデータの主要統計値
    - **アクション対象候補**：アクションの必要性が高いメンバーと主要な分析値
    - **幹部職に伝えたいこと**：「幹部職に伝えたいこと」の記入内容一覧

    ##### グラフの種類
    - **時系列**：年月推移の表示カテゴリ別折れ線グラフ
    - **カテゴリ比較**：年月別棒グラフ
    - **評価（評価別比率）**：高い／中間／低い比率棒グラフ
    - **評価（レーダーチャート）**：構成要素別レーダーチャート
    - **分布**：平均／最大／最小／四分位の統計表示と点数別ヒストグラム
    - **個人**：個人の時系列表示とアクション用シグナル（主要な分析値）
    """)

# フッター
st.sidebar.markdown("---")
st.sidebar.markdown("©RDPi Corporation")
