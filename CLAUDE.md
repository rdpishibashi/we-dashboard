# WE-Dashboard Project Context

> **技術文書** (`docs/INDEX.md` に全一覧):
> - `docs/TECHNICAL_ARCHITECTURE.md` — アーキテクチャ・モジュール詳細
> - `docs/DATA_PIPELINE.md` — データフロー仕様
> - `docs/PRIVILEGE_SYSTEM.md` — 権限管理システム仕様
> - `docs/MODULE_REFERENCE.md` — 関数レベル API リファレンス
> - `docs/SESSION_STATE_PATTERNS.md` — セッションステート設計パターン
> - `docs/LEAVE_MEMBER_TOGGLE.md` — 転属・退職メンバー表示トグル仕様
>
> **コード例詳細**: `.claude/skills/we-dashboard/SKILL.md`（任意参照）

## プロジェクト概要

従業員のワーク・エンゲージメントデータを可視化・分析する Streamlit ベースの Web アプリケーション。権限クラスによるアクセス制御を実装。

## 技術スタック

| 要素 | 技術 |
|------|------|
| フレームワーク | Streamlit ≥ 1.40.0 |
| データ処理 | pandas, numpy |
| 可視化 | Plotly |
| 認証 | カスタム実装（SHA-256） |
| Excel 処理 | openpyxl, msoffcrypto |
| デプロイ | Streamlit Cloud (Linux) + ローカル Mac/Windows |

## ディレクトリ構成

```
WE-Dashboard/
├── app.py                          # メインアプリケーション（エントリポイント）
├── modules/
│   ├── auth.py                     # 認証・ログイン
│   ├── charts.py                   # グラフ生成
│   ├── components.py               # 再利用可能 UI コンポーネント
│   ├── config.py                   # 定数・設定（TAB_NAMES, GROUPING_OPTIONS, METRIC_LABELS 等）
│   ├── data_loader.py              # Excel 読み込み・前処理（復号対応）
│   ├── encryption.py               # 暗号化ユーティリティ
│   ├── filter_helpers.py           # サイドバーフィルターカスケードロジック
│   ├── member_loader.py            # メンバーリスト読み込み（未記入者機能用）
│   ├── privilege_manager.py        # 権限ベースフィルタリング（シングルトン）
│   ├── response_file_manager.py    # レスポンスファイル保存/読み込み（低レベル）
│   ├── response_manager_local.py   # 返信管理 — Mac/Windows（response.xlsx）
│   ├── response_manager_cloud.py   # 返信管理 — Streamlit Cloud（Google Sheets）
│   ├── signal_processing.py        # シグナルデータ処理・テーブル表示
│   ├── statistics.py               # 統計計算
│   ├── utils.py                    # ユーティリティ関数
│   └── windows_config.py           # ローカル専用・git-ignored・AES 暗号化パスワード
├── config/
│   ├── privileges_configuration.md # 権限設定ソースオブトゥルース（これを編集する）
│   ├── privileges.yaml             # 自動生成（直接編集不可）
│   └── members.yaml                # 自動生成（Member.xlsx から生成）
├── tools/
│   ├── generate_privileges_yaml.py # privileges.yaml 生成
│   ├── generate_member_yaml.py     # members.yaml 生成
│   ├── split_by_division.py        # 部門別 Excel 分割ツール
│   └── encrypt_passwords.py        # パスワード暗号化ツール（windows_config.py 更新用）
├── docs/                           # 技術ドキュメント
├── group_order_config.json         # グループ・課・職位の表示順設定
└── requirements.txt
```

## 権限システム

### 設定ファイル階層

```
config/privileges_configuration.md  ← ソースオブトゥルース（手動編集）
        ↓ python tools/generate_privileges_yaml.py
config/privileges.yaml              ← 生成済み設定（直接編集不可）
        ↓ privilege_manager.py（シングルトン）
アプリケーション（実行時フィルタリング）
```

### 権限クラス

| クラス | ユーザー | アクセス範囲 |
|--------|---------|-------------|
| `admin` | 管理者 | 全データアクセス |
| `anonymous` | 未認証 | データアクセス不可 |
| `department_head` | sd, me, dev | 部署レベル |
| `section_manager` | sw, pd, me1-3, dev1-2, uti, uks | 課レベル |
| `member` | soft, prod, mechele1-3 | 制限付き + 職位フィルター |
| `member_no_grade_filter` | develop1-2 | 制限付き、職位フィルターなし |

### 権限フィーチャー

| フィーチャー | 説明 |
|------------|------|
| `data_scope` | タブ別データ表示範囲 |
| `section_scope` | UI セクション別表示範囲 |
| `grade_filter` | 職位フィルター（non_managers 等） |
| `anonymize` | コメント内の個人名匿名化 |
| `section_aliases` | 課をまとめて表示名に変換 |
| `team_section_overrides` | チームメンバーを仮想課として表示（マネジメント機能） |

## データ構造

### 入力ファイル: EngagementData-*.xlsx（部門別）

`config.py` の `find_default_data_files()` が `EngagementData-*.xlsx` を検索して読み込む。複数ファイルがある場合は `pd.concat` で結合。

#### rating2 シート → pivot_df + signal_df

| カラム | 説明 |
|--------|------|
| year, month | 年月 |
| mail_address, name | 個人識別子・氏名 |
| current_division → division | 部門 |
| current_department → department | 部署 |
| current_section → section | 課 |
| current_team → team, current_project → project | 横断的組織 |
| grade | 職位 |
| engagement_rating (0-54) | エンゲージメント生スコア |
| vigor/dedication/absorption_rating (0-18) | 構成要素生スコア |
| intervention_priority_neg/pos | 介入優先度（neg は Admin GAS で flag ボーナス込み） |
| trend_recent, trend_base, trend_refined | トレンドシグナル |
| big_change | 短期変動 |
| direction_6_p90, volatility_6_p90 | 変動パターン計算元（合成 → `mid_variability`） |
| stability_6 | 中期安定性 |
| flag_constant_6m | 調査抵抗疑義フラグ |
| strength_short/mid, weakness_short/mid | 強み・弱み |

**正規化**: pivot_df は signal_df の評価カラムを除数で割ったもの
- `engagement_rating / ENGAGEMENT_DIVISOR (5.4)` → 0–10
- `vigor/dedication/absorption_rating / COMPONENT_DIVISOR (1.8)` → 0–10

**復号処理**: `decrypt_excel_if_needed()` は `is_encrypted()` で判定し、非暗号化はそのまま返す。暗号化ファイルはパスワードで復号（パスワード未設定時は ValueError）。

#### comment シート → comment_df（自己完結型）

独自の組織列（`division`, `current_division`, `department`, `current_department`, `section`, `current_section` 等）を持つ。

## 5 レイヤー フィルタリングパイプライン

```
Layer 0: @st.cache_data — Excel を一度だけ読み込みキャッシュ
Layer 1: 期間フィルター（サイドバースライダー）
Layer 2: サイドバースコープ — get_sidebar_scope() → filter_dataframe_by_scope()
         全許可タブのスコープの和集合（最広スコープ）
Layer 3: カスケードフィルター（filter_helpers.py）
         部門 → 部署 → 課 → チーム → プロジェクト → 職位 → 個人
Layer 4: タブスコープ — get_data_scope_for_tab() → filter_dataframe_by_scope()
Layer 5: グルーピングスコープ（components.py / apply_grouping_filters()）
         grade_filter + section_aliases + team_section_overrides
         ※ grouping_scope（Layer 1 of apply_grouping_filters）は無効化済み
```

**Layer 5 の grouping_scope 無効化理由**: 権限設定に明示されていない部署（品質保証部等）を意図せず除外するため。`data_scope` がタブレベルの表示制御を担う。

## コメントデータのフィルタリング（2 段階）

**① アプリレベル（app.py）**: サイドバーの組織条件を反映するため `filtered_df` の `mail_address` で絞り込む。

**② タブレベル（components.py / prepare_comment_data）**: comment_df は独自の組織列を持つ自己完結型。mail_address 結合は不要。必ず `filter_dataframe_by_scope()` を使う。

```python
# section NaN = 課未所属（部署長）→ '部門長'（'未設定' ではない）
graph_comments['section'] = graph_comments['current_section'].fillna('部門長')
graph_comments['department'] = graph_comments['current_department'].fillna('未設定')
graph_comments['division'] = graph_comments['current_division'].fillna('未設定')
graph_comments = filter_dataframe_by_scope(graph_comments, share_scope)
```

## 返信管理バックエンドの自動選択

```python
import sys
if sys.platform in ("darwin", "win32"):
    from modules.response_manager_local import ...   # Mac/Windows → response.xlsx
else:
    from modules.response_manager_cloud import ...   # Linux/Streamlit Cloud → Google Sheets
```

## パスワード管理（ローカル vs クラウド）

- **Streamlit Cloud**: `st.secrets["EXCEL_PASSWORD"]` / `st.secrets["RESPONSE_PASSWORD"]`
- **ローカル Mac/Windows**: `modules/windows_config.py`（git-ignored、AES Fernet 暗号化）
  - `get_excel_password()` は `windows_config.py` 優先、なければ `st.secrets` にフォールバック
  - パスワード更新: `python tools/encrypt_passwords.py`

## UI 構造

### 未認証

ウェルカムページ（使い方ガイド）のみ表示。ダッシュボードは描画しない。

### サイドバー（認証済み）

```
1. ログイン（expander）
2. 期間（スライダー）
3. 表示指標（selectbox）
4. 表示カテゴリ（grouping selectbox）※ ログイン直後の既定は「課別」(section)。`section` 非許可の権限は先頭(`なし`)にフォールバック。初期値はウィジェット生成前に `unified_grouping` を session_state に設定（`key=`+`index=` 併用回避）
5. 転属・退職メンバーを含む（checkbox）※ leave_addresses がある場合のみ
── separator ──
6. フィルター設定（expander、デフォルト折り畳み）:
   部門 → 部署 → 課 → チーム → プロジェクト → 職位 → 個人
7. データ（expander）— ファイルアップロード
8. 期間＆有効データ（info box）
```

### タブ（st.tabs）

| タブ | キー | 主な機能 |
|-----|-----|---------|
| 時系列 | timeseries | 月次推移グラフ、計測値、統計、シグナル・コメント |
| カテゴリ比較 | group_comparison | グループ比較棒グラフ、レーダー、統計、シグナル・コメント |
| 評価 | evaluation | 評価バンド積み上げグラフ、計測値セクション |
| 分布 | distribution | ボックスプロット、統計テーブル |
| 個人 | individual | 個人推移グラフ、プロフィール（expander）、計測値（expander）、シグナル（全行固定表示）、コメント |

認証済み: 5 タブ / 未認証: 個人タブなし（4 タブ）

### タブ内セクション（時系列・カテゴリ比較・評価・分布）

- 計測値（expander）— 計測データテーブル
- 主な指標（expander）— 統計サマリー
- アクション対象候補 — シグナルテーブル（行選択→個人タブナビゲーション対応）
- **コメント**（subheader）
- 気になった出来事や気づき — 懸念事項（admin のみ）
- 共有したいこと — コメントと返信
- 未記入者（expander）— 未記入者リスト（管理職のみ）

### 個人タブ セクション順序

1. 推移グラフ
2. **プロフィール**（expander）— 部門・部署・課・チーム・プロジェクト・職位
3. **計測値**（expander）— 月次評価値テーブル
4. **シグナル**（subheader）— 個人シグナル詳細（`height=510` で全 13 行スクロールなし固定表示）
5. **コメント**（subheader、権限がある場合のみ表示）
6. 気になった出来事や気づき（expander）
7. 幹部職に伝えたいこと（expander）

## 実装ルール

### Streamlit 固有のルール

**width パラメータ（use_container_width は廃止済み）**
`use_container_width` は削除済み。`config.py` の定数を使う。
```python
from modules.config import PLOTLY_CHART_KWARGS, DATAFRAME_KWARGS
st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)   # {"width": "stretch"}
st.dataframe(df, **DATAFRAME_KWARGS)          # {"width": "stretch", "hide_index": True}
```

**セッション状態とウィジェットキー**
- ウィジェット生成後はそのキーを session_state に書き込めない（StreamlitAPIException）
- `key=` を使うウィジェットには `index=`/`value=`/`default=` を渡さない（競合警告）
- 初期値の設定はウィジェット生成前に `if key not in st.session_state:` で行う

**`@st.cache_data` のアンダースコア引数**
アンダースコアで始まるパラメータはキャッシュキーから除外される。ファイル変更検知キーはアンダースコアなしで渡す。
```python
# ❌ _mtime はハッシュされず、ファイルが変わってもキャッシュが更新されない
@st.cache_data
def load_impl(_mtime): ...

# ✅
@st.cache_data
def load_impl(mtime): ...
```

### pandas の安全パターン

**boolean indexing の後は `.copy()`**
```python
# ❌ view かもしれない → .loc 代入がサイレントに失敗
filtered = df[df['period'] == selected]
filtered.loc[mask, 'col'] = value

# ✅
filtered = df[df['period'] == selected].copy()
filtered.loc[mask, 'col'] = value
```

**インデックス整合操作**（shape mismatch の回避）
```python
# ❌ 全 df のマスクとサブセットを AND → shape mismatch
df.loc[mask_full & subset['other'].isna(), 'col'] = value

# ✅ サブセットのインデックスで操作
mapped = df.loc[mask_full, 'mail'].map(lookup)
valid = mapped[mapped.notna() & (mapped != '')]
df.loc[valid.index, 'col'] = valid
```

## 重要な実装パターン

### スコープフィルタリング（必須）

`get_section_scope()` は課名だけでなく部署・部門名も返す場合がある。section 列だけで `isin()` すると漏れる。

```python
# ❌ section 列だけチェック
df = df[df['section'].isin(scope)]

# ✅ division / department / section 全列をチェック
from modules.privilege_manager import filter_dataframe_by_scope
df = filter_dataframe_by_scope(df, scope)
```

### グルーピングフィルター（apply_grouping_filters）

```python
from modules.components import apply_grouping_filters

# Layer 2 (grade filter), Layer 3 (section aliases), Layer 4 (team overrides) を適用
df, signal_df = apply_grouping_filters(
    df, signal_df, privilege_mgr, current_privilege,
    grouping_choice, tab_name, selected_filters
)
```

### コメント・シグナル一括表示（render_comments_and_signals）

```python
from modules.components import render_comments_and_signals

render_comments_and_signals(
    signal_df=tab_signal_df, df=ts_df, comment_df=filtered_comment_df,
    privilege_mgr=privilege_mgr, current_privilege=current_privilege,
    start_dt=start_dt, end_dt=end_dt,
    selected_filters=selected_filters, member_df=member_df,
    tab_name="時系列", grouping_choice=ts_group_choice,
)
```

### signal_df のローカルフィルタリング（名前ベース）

rating2 シートの team 列の値はメインデータと異なる場合があるため名前ベースで絞り込む。

```python
tab_signal_df = tab_signal_df[tab_signal_df['name'].isin(tab_df['name'].unique())]
```

### チームセクションオーバーライド（マネジメント）

`grouping == 'section'`（課別）の時のみ適用。`apply_grouping_filters()` 内で処理。
`exclude_sections` は**無効化済み**（サブセクションを持たない部署が除外されるため）。

### intervention_priority の計算ルール

- `intervention_priority_neg` には Admin GAS が `flag_constant_6m` ボーナスを含めて計算済み
- Dashboard では flag ボーナスを**加算しない**（二重計上になる）
- 側（neg/pos）の判定は**大小比較**: `_priority_is_neg = neg >= pos`（大きい方が勝ち、同点は neg 優先）。エンゲージメントグラフと赤/緑の側を一致させるため
- 表示値 = `(勝った側) - threshold`、`flag_constant_6m` はラベル表示専用。足切り（`neg > threshold or pos > threshold`）は `get_signal_data` で実施

### 転属・退職メンバーの leave ステータス

leave ステータスは `config/members.yaml` から取得（Admin GAS が `current_*` をクリアするため rating2 は使えない）。

- `""` → 在籍中（常時表示）
- `"absence"` → 休職中（常時表示）
- `"leave"` → 退職・転属（チェックボックスで切替）

チェックボックスで含める場合、members.yaml から org 情報を復元して `filtered_df` に反映する。

### クロスタブナビゲーション（アクション対象候補→個人タブ）

中間キー `_nav_individual` を使う one-shot パターン。受信側（個人タブ）がウィジェット生成前に中間キーを `del` して消費する。セッションステートキー: `_nav_individual`・`_last_{key_prefix}_selection`・`_clear_action_selection`・`_signal_tables_version`。詳細は `docs/SESSION_STATE_PATTERNS.md` 参照。

## よくある落とし穴

| 問題 | 原因 | 対処 |
|------|------|------|
| コメントが権限スコープで除外される | tab レベルで mail_address を使ってスコープ適用 | `filter_dataframe_by_scope()` を使う |
| スコープフィルタリング漏れ | `section` 列のみ `isin()` | `filter_dataframe_by_scope()` を使う |
| section NaN のコメントが表示されない | `fillna('未設定')` にしている | `fillna('部門長')` にする |
| マネジメントが課別以外で表示される | 全グルーピングでオーバーライド適用 | `grouping == 'section'` 時のみ適用 |
| signal_df トレンド列が空（マネジメント） | team 列でフィルタリング | 名前ベースでフィルタリング |
| @st.cache_data が更新されない | `_` プレフィックス引数を使用 | プレフィックスなしの引数名にする |
| 部署全体が非表示 | `exclude_sections` で未設定を除外 | `exclude_sections` は無効化済み |
| section_manager が部門長コメントを見れない | 課スコープでは `section='部門長'` が除外される | `計測値`スコープで部門長行を別取得して結合 |
| グラフ幅が効かない | `use_container_width` は削除済み | `PLOTLY_CHART_KWARGS` / `DATAFRAME_KWARGS` を使う |
| グラフに「未設定」が出るのにフィルター選択肢に無い | `get_cascaded_options` が課/チーム/プロジェクトで `remove_unset=True` | `filter_helpers.py:131` の除外リストに `'section','team','project'` を含めない（`['grade','section','team','project']`）。data_loader が NaN を `'未設定'` に fillna 済みなので選択肢に残せばグラフと整合 |

## セッション状態キー（主要なもの）

| キー | 説明 |
|------|------|
| `authenticated`, `current_user`, `current_privilege` | 認証関連 |
| `filter_period` | 期間スライダー |
| `unified_division`, `unified_department`, `unified_section` | 組織フィルター |
| `unified_team`, `unified_project`, `unified_grade` | 横断組織・職位フィルター |
| `unified_individual` | 個人フィルター |
| `unified_grouping` | 表示カテゴリ |
| `include_leave_members` | 転属・退職メンバーを含む（checkbox） |
| `reset_period_filter`, `reset_local_filters` | ログイン/ログアウト時リセットフラグ |
| `_nav_individual` | アクション対象候補→個人タブナビゲーション（中間キー） |
| `_signal_tables_version` | シグナルテーブルウィジェットバージョン |

## デプロイ

### Streamlit Cloud

- Config: `.streamlit/config.toml`
- Secrets: `EXCEL_PASSWORD`, `RESPONSE_PASSWORD`, `gcp_service_account`, `RESPONSE_SHEET_ID`

### ローカル起動

```bash
streamlit run app.py
```

Windows スタンドアロン: PyInstaller ビルド版は `~/Documents/WE-Dashboard/EngagementData-*.xlsx` を自動読み込み。

## 開発ワークフロー

### 権限設定の更新

1. `config/privileges_configuration.md` を編集
2. `python tools/generate_privileges_yaml.py` を実行
3. ローカルでテスト → `config/privileges.yaml` をコミット

### メンバーリストの更新

1. `Member.xlsx` を更新 → `python tools/generate_member_yaml.py` → `config/members.yaml` をコミット

### 部門別データ分割

```bash
python tools/split_by_division.py
```

パスワードは `.streamlit/secrets.toml` から読み込む。leave メンバーの部門情報は `members.yaml` から取得。

### 新機能追加時のチェックリスト

1. 権限要件の確認（`docs/PRIVILEGE_SYSTEM.md`）
2. データフローへの影響確認（`docs/DATA_PIPELINE.md`）
3. 既存コンポーネントの再利用検討（`modules/components.py`）
4. 複数権限レベルでテスト
