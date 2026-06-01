# WE-Dashboard コード例集

> 重要なルールと実装パターンは `CLAUDE.md` に記載済み。
> このファイルは詳細コード例の補助資料。

---

## 1. クロスタブナビゲーション（アクション対象候補→個人タブ）詳細

`st.tabs()` は全タブを毎 rerun 描画する。受信側ウィジェット生成前に中間キーを消費する。

```python
# SENDER（render_action_candidates 内）
last_key = f"_last_{key_prefix}_selection"
if selected != st.session_state.get(last_key):
    st.session_state[last_key] = selected
    if selected:
        st.session_state["_nav_individual"] = selected  # 中間キー（ウィジェット管理外）

# RECEIVER（個人タブ側 — sender より後に描画される）
widget_key = "individual_selector"
if "_nav_individual" in st.session_state:
    nav_value = st.session_state["_nav_individual"]
    del st.session_state["_nav_individual"]          # one-shot: 読んだら即削除
    if nav_value in available_options:
        st.session_state[widget_key] = nav_value     # ウィジェット生成前なので安全

if widget_key not in st.session_state or st.session_state[widget_key] not in available_options:
    st.session_state[widget_key] = available_options[0]

selected = st.selectbox("個人", available_options, key=widget_key)  # index= なし
```

---

## 2. シグナルテーブルの選択状態リセット（キーバージョニング）

```python
version = st.session_state.get("_signal_tables_version", 0)
if st.session_state.pop("_clear_action_selection", False):
    version += 1
    st.session_state["_signal_tables_version"] = version

event = st.dataframe(
    df, key=f"signal_table_v{version}",
    on_select="rerun", selection_mode="single-row"
)
```

`pop()` は「読んで即削除」なので、同一 rerun で複数テーブルがあっても最初の 1 テーブルがフラグを消費し、残りはインクリメント済みバージョンを参照する。

---

## 3. 統計・計測値の表示パターン

```python
from modules.statistics import (
    calculate_group_statistics, format_statistics_for_display,
    format_measured_data
)
from modules.config import DATAFRAME_KWARGS

# 計測値（expander 内）
with st.expander("計測値", expanded=False):
    group_col = grouping_choice if grouping_choice != 'なし' else None
    st.dataframe(format_measured_data(df, selected_metric, group_col), **DATAFRAME_KWARGS)

# 主要な指標（expander 内）
with st.expander("主要な指標", expanded=False):
    group_col = grouping_choice if grouping_choice != 'なし' else None
    # group_col == 'name' のとき signal_df からトレンド列を結合
    stats_df = calculate_group_statistics(
        df, selected_metric, group_col,
        signal_df=tab_signal_df if group_col == 'name' else None,
        end_dt=end_dt if group_col == 'name' else None,
    )
    if not stats_df.empty:
        st.dataframe(format_statistics_for_display(stats_df), **DATAFRAME_KWARGS)
```

---

## 4. @st.cache_data ファイル変更検知パターン

```python
from pathlib import Path

def _get_mtime(path: str):
    p = Path(path)
    return p.stat().st_mtime if p.exists() else None

@st.cache_data
def load_config(mtime):          # アンダースコアなし！
    with open("config/data.yaml") as f:
        return yaml.safe_load(f)

def get_config():
    return load_config(_get_mtime("config/data.yaml"))
```

---

## 5. サイドバー expander 内のウィジェット

```python
with st.sidebar.expander("フィルター設定", expanded=False):
    # expander の中では st.selectbox を使う（st.sidebar.selectbox ではない）
    selected = st.selectbox("部門", options, key="unified_division")
```

---

*最終更新: 2026-05*
