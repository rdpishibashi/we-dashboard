# セッションステート設計パターン

このプロジェクトで発見・確立した Streamlit セッションステートの設計パターンをまとめる。
実装の意図と背景を残し、将来の変更時の参照資料とする。

---

## 1. Streamlit 実行モデルの制約

このプロジェクトで直面した Streamlit 固有の制約を記録する。

### 1.1 ウィジェット生成後はキーを書き換えられない

```python
# ❌ エラー: widget with key "X" cannot be modified after instantiation
st.selectbox("選択", options, key="X")       # ← ここで X がウィジェット管理下に入る
st.session_state["X"] = "new_value"          # ← 同一 rerun 内での書き換えは禁止
```

ウィジェットキーへの書き込みは「そのウィジェットが描画される前」のみ許可される。

### 1.2 st.tabs() のタブ切り替えは rerun を発生させない

```
タブ A → タブ B への切り替え = CSS の show/hide のみ
サーバー側コードは実行されない → セッションステートを変更できない
```

「タブ B に戻ったら選択をリセット」のような動作は、純粋な Streamlit の仕組みでは実現不可。

### 1.3 st.tabs() は全タブのコンテンツを毎 rerun 描画する

タブの表示・非表示に関わらず、全タブの Python コードが毎回実行される。
同じ関数（例: `render_action_candidates`）が複数タブで呼ばれる場合、共有キーに干渉する。

### 1.4 index= と key= の同時指定はワーニングを引き起こす

```python
st.session_state["X"] = "value"   # API でセット
st.selectbox(..., index=0, key="X")  # ← ワーニング: default value + API set の競合
```

**ルール**: `key=` を使うウィジェットには `index=`/`value=`/`default=` を渡さない。
ウィジェット生成前にセッションステートに正しい値をセットしておくことで代替する。

---

## 2. セッションステートの所有権モデル

`st.session_state` はフラットなグローバル辞書であり、複数モジュールが書き込むと干渉する。
このプロジェクトでは以下のドメイン区分と命名規則でキーを管理する。

### 2.1 ドメイン区分と命名規則

| プレフィックス | ドメイン | 書き込み元 | 読み取り元 |
|--------------|---------|-----------|----------|
| `unified_*` | サイドバー統合フィルター | `filter_helpers.py` | `app.py`・各タブ |
| `reset_*` | フィルターリセットフラグ | `app.py` | `app.py`・`filter_helpers.py` |
| `_nav_*` | ナビゲーション中間キー（非ウィジェット） | `components.py` | `app.py`（個人タブ） |
| `_last_*` | コンポーネント内前回値追跡 | `components.py` | `components.py` |
| `_clear_*` | ウィジェット状態リセットフラグ | `app.py` | `signal_processing.py` |
| `_signal_tables_*` | シグナルテーブルウィジェット制御 | `signal_processing.py` | `signal_processing.py` |
| `individual_selector` | 個人タブのローカルセレクトボックス | `app.py`（ウィジェット） | `app.py` |

### 2.2 現在の全キー一覧

**フィルター系**（サイドバーウィジェットが所有）
```
unified_division / unified_grade / unified_department / unified_section
unified_team / unified_project / unified_individual / unified_grouping
filter_period / reset_period_filter / reset_local_filters
```

**ナビゲーション系**（非ウィジェット、中間値として使用）
```
_nav_individual            # action candidates → 個人タブへの氏名受け渡し
_last_{key_prefix}_{side_key}_selection  # テーブルごとの前回選択
                           # key_prefix = ts / gc_no_group / gc_grouped、side_key = neg / pos
_clear_action_selection    # 個人タブ表示後、シグナルテーブルの選択リセット要求フラグ
_signal_tables_version     # シグナルテーブルウィジェットキーのバージョンカウンター
_jump_individual           # 「個人表示」ボタン → 個人タブへの JS 切替要求フラグ
```

**ローカルウィジェット系**（app.py が所有）
```
individual_selector        # 個人タブのセレクトボックス（unified_individual とは別）
```

---

## 3. クロスタブナビゲーションパターン

「タブ A のウィジェット選択 → タブ B のウィジェットを更新する」パターン。
Streamlit はクロスウィジェット書き込みを制限するため、中間キーを介した間接的な受け渡しが必要。

### 3.1 このプロジェクトでの実装（アクション対象候補 → 個人タブ）

```
[時系列タブ or カテゴリ比較タブ]
  render_action_candidates()
    ネガティブ・メンバー / ポジティブ・メンバーの 2 テーブルをループで描画
    ↓ 行を選択
    render_signal_table() → selected_name を返す
    ↓ 前回選択と比較（_last_{key_prefix}_{side_key}_selection）
    変化あり → _nav_individual = selected_name をセット
               st.info("個人タブで確認できます") ＋「個人表示」ボタン
               （選択直後のみ、メッセージ位置へ scrollIntoView する iframe を注入）

[個人タブ]（同一 rerun 内、タブ描画順が後のため安全に読める）
  "_nav_individual" がセッションに存在するか確認
    → あり: nav_name = ss["_nav_individual"]
            del ss["_nav_individual"]           # 消費（一度だけ反映）
            ss["individual_selector"] = nav_name  # ウィジェット生成前に書く
            ss["_clear_action_selection"] = True  # 次 rerun でテーブル選択リセット要求
  st.selectbox(key="individual_selector")       # セッションステートの値を使って描画
```

### 3.1b 「個人表示」ボタンによる JS タブ切替（on_click コールバック必須）

「個人表示」ボタンのクリックで個人タブへ自動切替する機能。`st.tabs` にはプログラムからの
切替 API がないため、親ドキュメントのタブボタンを JS でクリックする。

**戻り値方式（`if st.button(...)`）は使えない**: ボタンクリックの再実行では
`_clear_action_selection` フラグの処理によりテーブル選択がリセットされ、
`selected_name` が None になってボタン自体が描画されなくなる（クリックが失われる）。

```python
# components.py — コールバックは描画より先（rerun の冒頭）に実行される
def _request_individual_jump():
    st.session_state["_jump_individual"] = True

st.button("個人表示", key=..., on_click=_request_individual_jump)

# app.py — st.tabs 直後でフラグを消費し JS を注入
if st.session_state.pop("_jump_individual", False):
    st_components_html("<script>…個人タブをクリック→ページ上部へスクロール…</script>", height=0)
```

### 3.2 複数テーブルの干渉防止

同一 rerun 内で複数の `render_action_candidates` が実行される（ts / gc_no_group / gc_grouped）。
共有キーを使うと、選択のないテーブルが「選択なし（None）」で上書きしてしまう。

**解決策**: テーブルごとの追跡キーを使う

```python
# ❌ 共有キーは干渉する
current = st.session_state.get("_action_candidate_selection")  # ts が書いた直後に gc が None で上書き

# ✅ テーブルごとのキー（key_prefix × side_key の組み合わせで一意）
last_key = f"_last_{key_prefix}_{side_key}_selection"   # 例: "_last_ts_neg_selection"
current = st.session_state.get(last_key)     # 他テーブルと干渉しない
```

### 3.3 パターンの一般化

```python
# 送信側（コンポーネント A、先に描画される）
def component_a():
    value = get_selected_value()
    prev_key = f"_last_{component_id}_selection"
    if value != st.session_state.get(prev_key):
        st.session_state[prev_key] = value
        if value:
            st.session_state["_nav_to_component_b"] = value  # 中間キー

# 受信側（コンポーネント B、後に描画される）
def component_b():
    nav_value = st.session_state.get("_nav_to_component_b")
    if nav_value:
        del st.session_state["_nav_to_component_b"]          # 消費
        st.session_state["widget_key_b"] = nav_value         # ウィジェット生成前に書く
    # ... ウィジェット生成 ...
    st.selectbox(key="widget_key_b")
```

**前提条件**: コンポーネント A の描画がコンポーネント B より前であること。
`st.tabs()` では全タブが毎回描画されるが、`with tab_map[...]` ブロックの記述順が実行順になる。

---

## 4. ウィジェットキー・バージョニングパターン

ウィジェットの選択状態（`event.selection.rows` など）を外部からリセットする方法。

Streamlit ではウィジェットの内部状態を直接クリアできないが、**キーを変えると新しいウィジェットインスタンスが生成され、状態が初期化される**。

### 4.1 実装（シグナルテーブルの選択リセット）

```python
# signal_processing.py の render_signal_table() 内

# バージョンカウンターをキーに付加
version = st.session_state.get("_signal_tables_version", 0)
if st.session_state.pop("_clear_action_selection", False):
    version += 1
    st.session_state["_signal_tables_version"] = version

effective_key = f"{key}_v{version}"   # "ts_signal_table_v0" → "ts_signal_table_v1"

event = st.dataframe(..., key=effective_key, on_select="rerun")
```

**ポイント**:
- `pop()` を使うことで、最初に処理したテーブルがフラグを消費する
- バージョンカウンターは `pop()` 後も残るため、後続テーブルも同じバージョンキーを使う（全テーブルが同時にリセット）
- バージョンカウンターは永続するため、アプリ再起動まで単調増加する（問題なし）

### 4.2 インデックス境界チェック（安全策）

フィルター変更でデータが減少した場合、保存されていた行インデックスが範囲外になる場合がある。

```python
if event.selection.rows:
    row_idx = event.selection.rows[0]
    if row_idx < len(signals_indexed):      # 境界チェック必須
        selected_name = signals_indexed.at[row_idx, 'name']
    # else: 範囲外 → selected_name = None のまま（エラーにならない）
```

---

## 5. 将来のコード変更計画

現状、ナビゲーション関連のセッションステートキーは文字列リテラルとして各所に散在している。
**タイポ防止と所有権の明示化のため、`config.py` への定数化を推奨する**。

### 5.1 追加すべき定数（`modules/config.py`）

```python
# =============================================================================
# Navigation session state keys (cross-tab individual navigation)
# =============================================================================

# Written by: components.py (render_action_candidates)
# Read/consumed by: app.py (個人 tab)
NAV_INDIVIDUAL_KEY = "_nav_individual"

# Written by: app.py (個人 tab, after _nav_individual is consumed)
# Read by: signal_processing.py (render_signal_table)
CLEAR_ACTION_SELECTION_KEY = "_clear_action_selection"

# Written/read by: signal_processing.py (render_signal_table)
SIGNAL_TABLES_VERSION_KEY = "_signal_tables_version"

# Written/read by: app.py (個人 tab selectbox)
INDIVIDUAL_SELECTOR_KEY = "individual_selector"


def last_selection_key(key_prefix: str, side_key: str) -> str:
    """Per-table selection tracking key for render_action_candidates."""
    return f"_last_{key_prefix}_{side_key}_selection"
```

### 5.2 変更が必要なファイルと箇所

| ファイル | 現在の文字列リテラル | 置換後 |
|---------|-------------------|--------|
| `modules/components.py` | `"_nav_individual"` | `NAV_INDIVIDUAL_KEY` |
| `modules/components.py` | `f"_last_{key_prefix}_{side_key}_selection"` | `last_selection_key(key_prefix, side_key)` |
| `modules/signal_processing.py` | `"_clear_action_selection"` | `CLEAR_ACTION_SELECTION_KEY` |
| `modules/signal_processing.py` | `"_signal_tables_version"` | `SIGNAL_TABLES_VERSION_KEY` |
| `app.py` | `"_nav_individual"` | `NAV_INDIVIDUAL_KEY` |
| `app.py` | `"_clear_action_selection"` | `CLEAR_ACTION_SELECTION_KEY` |
| `app.py` | `"individual_selector"` | `INDIVIDUAL_SELECTOR_KEY` |

### 5.3 変更手順

1. `modules/config.py` に上記定数を追記する
2. `modules/components.py` の import に定数を追加する
3. `modules/signal_processing.py` の import に定数を追加する
4. `app.py` の import に定数を追加する
5. 各ファイルの文字列リテラルを定数に置換する（grep で漏れ確認）
6. 動作確認（ナビゲーション・選択リセット・エラーなし）

---

## 6. このパターンを適用する前のチェックリスト

新たに「タブ間でウィジェット状態を渡す」機能を実装する際に確認する。

- [ ] 送信側コンポーネントと受信側コンポーネントの描画順を確認したか
- [ ] 「共有キー」ではなくコンポーネント固有のキーを使っているか（`_last_{id}_*`）
- [ ] 中間キーはウィジェットキーではないことを確認したか（`_nav_*` プレフィックス）
- [ ] 受信側で中間キーを `del` して消費しているか（再適用防止）
- [ ] 受信側ウィジェットの `key=` 生成前にセッションステートへの書き込みが完了しているか
- [ ] `index=` や `value=` をウィジェットに渡していないか（`key=` との競合回避）
- [ ] フィルター変更でデータが減少した場合の境界チェックを実装したか

---

*作成: 2026-05-09 / 最終更新: 2026-07-04*
