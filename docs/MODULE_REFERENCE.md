# WE-Dashboard モジュール API リファレンス

> 最終更新: 2026-03-31

本ドキュメントは WE-Dashboard アプリケーションを構成する全モジュールの関数レベルリファレンスです。
各関数のシグネチャ・引数・戻り値・動作仕様を網羅的に記載します。

---

## 目次

1. [app.py — メインアプリケーション](#1-apppy--メインアプリケーション)
2. [modules/auth.py — 認証](#2-modulesauthpy--認証)
3. [modules/config.py — 設定・定数](#3-modulesconfigpy--設定定数)
4. [modules/data_loader.py — データ読み込み](#4-modulesdata_loaderpy--データ読み込み)
5. [modules/charts.py — グラフ生成](#5-moduleschartspy--グラフ生成)
6. [modules/signal_processing.py — シグナル処理](#6-modulessignal_processingpy--シグナル処理)
7. [modules/components.py — UI コンポーネント](#7-modulescomponentspy--ui-コンポーネント)
8. [modules/filter_helpers.py — フィルターヘルパー](#8-modulesfilter_helperspy--フィルターヘルパー)
9. [modules/privilege_manager.py — 権限管理](#9-modulesprivilege_managerpy--権限管理)
10. [modules/statistics.py — 統計](#10-modulesstatisticspy--統計)
11. [modules/utils.py — ユーティリティ](#11-modulesutilspy--ユーティリティ)
12. [modules/encryption.py — 暗号化](#12-modulesencryptionpy--暗号化)
13. [modules/response_manager.py — 返信管理](#13-modulesresponse_managerpy--返信管理)

---

## 1. app.py — メインアプリケーション

**行数**: 約 1,013 行
**役割**: Streamlit アプリのエントリポイント。UI 全体の構成、タブ表示、セッション状態管理を担当する。

### アプリケーションフロー

```
ファイル読み込み（load_data）
  └─ 認証チェック（is_authenticated）
       ├─ 未認証 → ウェルカムページ表示
       └─ 認証済み → ダッシュボード表示
            ├─ 期間フィルター（サイドバー）
            ├─ 統合サイドバーフィルター（render_unified_sidebar_filters）
            └─ 5タブ表示
                 ├─ 時系列
                 ├─ グループ比較
                 ├─ 評価
                 ├─ 分布
                 └─ 個人
```

### タブ構成

| タブ名 | キー | 主な機能 |
|--------|------|----------|
| 時系列 | `timeseries` | 月次推移折れ線グラフ、計測値テーブル、統計、シグナル・コメント |
| グループ比較 | `group_comparison` | グループ間比較棒グラフ、レーダーチャート、統計、シグナル・コメント |
| 評価 | `evaluation` | 評価バンド積み上げグラフ |
| 分布 | `distribution` | ボックスプロット、統計テーブル |
| 個人 | `individual` | 個人推移グラフ、シグナル詳細、コメント（認証ユーザーのみ） |

### セッション状態キー一覧

| キー | 型 | 説明 |
|------|----|------|
| `authenticated` | `bool` | ログイン状態 |
| `current_user` | `Optional[str]` | ログイン中のユーザー名 |
| `current_privilege` | `Optional[str]` | 現在の権限クラス |
| `current_display_name` | `Optional[str]` | 表示名 |
| `filter_period` | `tuple[datetime, datetime]` | 選択中の期間範囲 |
| `unified_division` | `str` | 部門フィルター選択値 |
| `unified_grade` | `str` | 職位フィルター選択値 |
| `unified_department` | `str` | 部署フィルター選択値 |
| `unified_section` | `str` | 課フィルター選択値 |
| `unified_team` | `str` | チームフィルター選択値 |
| `unified_project` | `str` | プロジェクトフィルター選択値 |
| `unified_individual` | `str` | 個人フィルター選択値 |
| `unified_grouping` | `str` | 表示カテゴリ（グルーピング）選択値 |
| `reset_period_filter` | `bool` | 期間フィルターリセットフラグ |
| `reset_local_filters` | `bool` | タブローカルフィルターリセットフラグ |

### ローカル関数

#### `migrate_session_state()`

旧フィルターシステム（マルチセレクト方式）から新統合フィルターシステムへのセッション状態マイグレーションを行う。

- 旧キー（`filter_divisions`, `filter_departments` 等）を削除する
- 旧ディメンションキー（`unified_dimension`, `unified_dimension_value`）を削除する
- 新統合キー（`unified_division`, `unified_grade` 等）をデフォルト値「すべて」で初期化する

**引数**: なし
**戻り値**: `None`

---

## 2. modules/auth.py — 認証

**行数**: 331 行
**役割**: ログイン認証・セッション状態管理・権限チェック・権限フィルタリングを提供する。

認証ファイルのパス:
- 本番: `auth_users.dat`（Base64 + pickle エンコード）
- 開発: `auth_users.json`（平文 JSON）

### 関数リファレンス

#### `hash_password(password)`

パスワードを SHA-256 でハッシュ化する。

| 引数 | 型 | 説明 |
|------|----|------|
| `password` | `str` | 平文パスワード |

**戻り値**: `str` — 16 進数文字列形式の SHA-256 ハッシュ

---

#### `load_auth_users()`

認証ユーザーファイルを読み込む。`.dat` ファイルが存在する場合は優先して読み込む（Base64 デコード → pickle デシリアライズ）。存在しない場合は `.json` にフォールバックする。

**引数**: なし
**戻り値**: `dict` — `{"users": [...]}` 形式。読み込み失敗時は `{"users": []}` を返す。

---

#### `get_user_data(username)`

ユーザー名でユーザーデータを取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `username` | `str` | ログインユーザー名 |

**戻り値**: `Optional[dict]` — `name`, `privilege`, `password_hash` を含む辞書。見つからない場合は `None`。

---

#### `verify_login(username, password)`

ユーザー名とパスワードを照合してログイン認証を行う。

| 引数 | 型 | 説明 |
|------|----|------|
| `username` | `str` | ログインユーザー名 |
| `password` | `str` | 平文パスワード |

**戻り値**: `Optional[dict]` — 認証成功時はユーザーデータ辞書、失敗時は `None`。
`username` または `password` が空文字の場合は即座に `None` を返す。

---

#### `init_auth_state()`

セッション状態の認証関連キーを初期化する。`authenticated=False`, `current_user=None`, `current_privilege=None` を設定する（既に存在するキーは上書きしない）。

**引数**: なし
**戻り値**: `None`

---

#### `is_authenticated()`

現在のユーザーが認証済みかどうかを確認する。内部で `init_auth_state()` を呼び出す。

**引数**: なし
**戻り値**: `bool`

---

#### `get_current_user()`

現在ログイン中のユーザー名を取得する。

**引数**: なし
**戻り値**: `Optional[str]`

---

#### `get_current_privilege()`

現在ログイン中のユーザーの権限クラスを取得する。

**引数**: なし
**戻り値**: `Optional[str]`

---

#### `get_current_display_name()`

現在ログイン中のユーザーの表示名を取得する。

**引数**: なし
**戻り値**: `Optional[str]`

---

#### `has_privilege(required_privileges)`

現在のユーザーが指定された権限のいずれかを持つかどうかを確認する。未認証の場合は常に `False` を返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `required_privileges` | `Union[list[str], str]` | 必要な権限（文字列またはリスト） |

**戻り値**: `bool`

---

#### `reset_filters()`

フィルター関連のセッション状態キーをすべてリセットする。ログイン・ログアウト時に呼び出される。

リセット対象:
- `reset_period_filter`, `reset_local_filters` フラグを `True` に設定
- サイドバーフィルターキー（`filter_divisions` 等）を削除
- タブローカルフィルターキー（`timeseries_department_select` 等）を削除
- 統合サイドバーフィルターキー（`unified_division` 等）を削除
- カスケード追跡キー（`_prev_*` プレフィックス）を削除

**引数**: なし
**戻り値**: `None`

---

#### `login(username, privilege, display_name)`

ユーザーをログイン状態に設定し、フィルターをリセットする。

| 引数 | 型 | 説明 |
|------|----|------|
| `username` | `str` | ログインユーザー名 |
| `privilege` | `Optional[str]` | 権限クラス |
| `display_name` | `Optional[str]` | 表示名（`None` の場合は `username` を使用） |

**戻り値**: `None`

---

#### `logout()`

現在のユーザーをログアウトし、セッション状態をクリアしてフィルターをリセットする。

**引数**: なし
**戻り値**: `None`

---

#### `render_login_ui()`

サイドバーにログイン UI を表示する。認証済みの場合はログアウトボタンを含む「ログイン状態」エクスパンダーを表示する。未認証の場合はユーザー名・パスワード入力フォームを表示する。

**引数**: なし
**戻り値**: `bool` — ログイン状態が変化した場合（ログイン成功またはログアウト）は `True`、それ以外は `False`。`True` が返った場合は呼び出し側で `st.rerun()` を実行する必要がある。

---

#### `get_allowed_groups_for_sharing(privilege)`

「共有したいこと」セクションで指定権限がアクセス可能なグループ一覧を取得する。`config.PRIVILEGE_GROUP_ACCESS` に基づく。

| 引数 | 型 | 説明 |
|------|----|------|
| `privilege` | `Optional[str]` | ユーザーの権限クラス |

**戻り値**: `Optional[list]`
- `None`: すべてのグループへのアクセスを許可（`admin`）
- `list`: アクセス可能なグループ名のリスト
- `[]`（空リスト）: `privilege` が `None`（未認証）のためアクセス不可

---

#### `filter_by_privilege(data, privilege)`

権限に基づいて DataFrame を組織階層でフィルタリングする。`division`、`department`、`section` の各列でいずれかが一致する行を返す（OR 条件）。

| 引数 | 型 | 説明 |
|------|----|------|
| `data` | `DataFrame` | 組織列を含む DataFrame |
| `privilege` | `Optional[str]` | ユーザーの権限クラス |

**戻り値**: `DataFrame` — 権限に基づいてフィルタリングされた DataFrame。フィルタリング可能な列が存在しない場合は元の DataFrame をそのまま返す。

---

## 3. modules/config.py — 設定・定数

**行数**: 220 行
**役割**: アプリケーション全体で使用する定数・設定値を一元管理する。

### 組織構造定数

#### `ORG_COLUMNS`

アプリケーション内部で使用する組織列名のマッピング。

```python
ORG_COLUMNS = {
    'division': 'division',     # 部門（最上位）
    'department': 'department', # 部署（中間）
    'section': 'section',       # 課（最下位）
}
```

#### `ORG_EXCEL_COLUMNS`

Excel ソースファイルの元列名（`current_*` プレフィックス付き）。

```python
ORG_EXCEL_COLUMNS = {
    'division': 'current_division',
    'department': 'current_department',
    'section': 'current_section',
}
```

#### `ORG_FILTER_COLUMNS`

権限フィルタリング対象の列名リスト（階層順）。

```python
ORG_FILTER_COLUMNS = ['division', 'department', 'section']
```

### メトリクス・ラベル定数

#### `METRIC_LABELS`

メトリクス列名と日本語表示名のマッピング。

| キー | 表示名 |
|------|--------|
| `engagement_rating` | ワーク･エンゲージメント |
| `vigor_rating` | 活力 (Vigor) |
| `dedication_rating` | 熱意 (Dedication) |
| `absorption_rating` | 没頭 (Absorption) |

#### `SIGNAL_LABELS`

シグナル列名と日本語表示名のマッピング（17 項目）。

| キー | 表示名 |
|------|--------|
| `section` | 課 |
| `name` | 氏名 |
| `intervention_priority` | 介入必要度 |
| `level` | レベル |
| `trend_recent` | 短期傾向 |
| `trend_refined` | 中期傾向 |
| `big_change` | 短期変動 |
| `stability_6` | 中期安定性 |
| `flag_constant_6m` | 調査抵抗疑義 |
| `engagement_rating` | エンゲージメント |
| `vigor_rating` | 活力 |
| `dedication_rating` | 熱意 |
| `absorption_rating` | 没頭 |
| `strength_short` | 強み（短期） |
| `weakness_short` | 弱み（短期） |
| `strength_mid` | 強み（中期） |
| `weakness_mid` | 弱み（中期） |

#### `FLAG_CONSTANT_LABELS`

`flag_constant_6m` 内部値と日本語表示名のマッピング。

| キー | 表示名 |
|------|--------|
| `LOW_FIXED` | 連続固定低評価回答 |
| `MID_EVASION` | 連続固定中評価回答 |
| `HIGH_AVOIDANCE` | 連続固定高評価回答 |
| `FIX_SHIFTED` | 連続固定回答シフト |

#### `FLAG_CONSTANT_PRIORITY_POINTS`

`flag_constant_6m` 値ごとの `intervention_priority_neg` への加算ポイント。

| キー | 加算ポイント |
|------|------------|
| `LOW_FIXED` | 3 |
| `MID_EVASION` | 2 |
| `HIGH_AVOIDANCE` | 2 |
| `FIX_SHIFTED` | 4 |

#### `LEVEL_LABELS`

レベル値の英語→日本語マッピング。

| キー | 表示名 |
|------|--------|
| `Critical` | 低調 |
| `Low` | やや低調 |
| `Moderate` | 標準 |
| `High` | 良好 |
| `Thriving` | 非常に良好 |

### トレンド分類定数

#### `POSITIVE_TRENDS`

ポジティブなトレンド値のリスト。

```python
['上昇加速', '上昇継続', '回復期待', '回復', '復活', '上昇期待', '上昇']
```

#### `NEGATIVE_TRENDS`

ネガティブなトレンド値のリスト。

```python
['低下懸念', '悪化', '低下危機', '低下加速', '低下継続', '低下警戒', '下降']
```

### 数値定数

| 定数 | 値 | 説明 |
|------|----|------|
| `INTERVENTION_PRIORITY_THRESHOLD` | `2` | 介入必要度の表示閾値（raw 値がこの値を超える場合に表示） |
| `ENGAGEMENT_DIVISOR` | `5.4` | エンゲージメント評価値の正規化除数（生スコア 0–54 → 0–10） |
| `COMPONENT_DIVISOR` | `1.8` | コンポーネント評価値の正規化除数（生スコア 0–18 → 0–10） |
| `RATING_AXIS_MAX` | `10.3` | グラフ Y 軸最大値 |
| `RATING_BAND_HIGH_THRESHOLD` | `6.0` | 評価バンド「高い」の下限値 |
| `RATING_BAND_LOW_THRESHOLD` | `2.0` | 評価バンド「低い」の上限値 |
| `COLOR_SCALE_START` | `0.35` | グラフカラースケール開始位置 |
| `COLOR_SCALE_END` | `1` | グラフカラースケール終了位置 |

### タブ定義定数

#### `TAB_NAMES`

全タブ名リスト: `['時系列', 'グループ比較', '評価', '分布', '個人']`

#### `TAB_NAMES_AUTHENTICATED` / `TAB_NAMES_ANONYMOUS`

- 認証済み: `['時系列', 'グループ比較', '評価', '分布', '個人']`（全タブ）
- 未認証: `['時系列', 'グループ比較', '評価', '分布']`（「個人」タブ非表示）

#### `TAB_CONFIG`

タブごとの詳細設定辞書。各タブのキー名、サブヘッダー、機能フラグ（グルーピング有無、計測値有無、統計有無、シグナル有無、コメント有無）を定義する。

### グルーピング定数

#### `GROUPING_LABEL_MAP`

グルーピング識別子と日本語ラベルのマッピング。

| キー | ラベル |
|------|--------|
| `なし` | なし |
| `division` | 部門別 |
| `department` | 部署別 |
| `section` | 課別 |
| `team` | チーム別 |
| `project` | プロジェクト別 |
| `grade` | 職位別 |
| `name` | 個人別 |

#### `GROUPING_OPTIONS_AUTHENTICATED`

認証済みユーザーが利用可能なグルーピングオプション:
`['なし', 'department', 'section', 'team', 'project', 'grade', 'name']`

#### `GROUPING_OPTIONS_ANONYMOUS`

未認証ユーザーが利用可能なグルーピングオプション:
`['なし', 'department', 'section', 'team', 'project']`

### アクセス制御定数

#### `PRIVILEGE_GROUP_ACCESS`

権限クラスと「共有したいこと」セクションのアクセス可能グループのマッピング。`None` はすべてのグループへのアクセスを示す。

```python
PRIVILEGE_GROUP_ACCESS = {
    'admin': None,  # 全グループ
    'sd': ['システム開発部', '機電設計部'],
    # ...
}
```

### ファイルパス定数

| 定数 | 値 |
|------|----|
| `DEFAULT_FILE_PATH` | `"EngagementMasterSS.xlsx"` |
| `GROUP_ORDER_FILE` | `group_order_config.json` のパス（`Path` オブジェクト） |

---

## 4. modules/data_loader.py — データ読み込み

**行数**: 189 行
**役割**: Excel ファイルの読み込み、パスワード解除、データ前処理を担当する。

### 関数リファレンス

#### `get_excel_password()`

Streamlit secrets から Excel パスワードを取得する。

**引数**: なし
**戻り値**: `Optional[str]` — `EXCEL_PASSWORD` シークレットが設定されていない場合は `None`。

---

#### `decrypt_excel_if_needed(file_obj)`

Excel ファイルがパスワード保護されている場合に復号する。`get_excel_password()` が `None` を返す場合（パスワード未設定）は入力をそのまま返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `file_obj` | `Union[str, file]` | ファイルパス文字列またはファイルオブジェクト |

**戻り値**: `Union[BytesIO, str, file]` — 復号済みの `BytesIO` オブジェクト、またはパスワード不要の場合は元のオブジェクト。

**例外**:
- `ValueError`: パスワードが正しくない場合

---

#### `load_data(uploaded_file)` _(キャッシュあり: `@st.cache_data`)_

Excel ファイルを読み込んでデータを前処理し、3つの DataFrame のタプルを返す。

**データソース**:
- `rating2` シート: エンゲージメントスコア・シグナル列（`signal_df` および `pivot_df` の元データ）
- `comment` シート: コメントデータ（`comment_df`）

**前処理内容**:
- `year`, `month` を数値型に変換し、欠損値チェック
- `year_month`（例: `"2026-01"`）および `year_month_dt`（`Timestamp`）列を生成
- `current_division` → `division`、`current_department` → `department`、`current_section` → `section` にマッピング
- `team`, `project`, `grade` 列を追加し、欠損値を `"未設定"` で補完
- `flag_constant_6m` 列を追加（Excel に列がない場合は `None` で補完）
- `pivot_df`: `engagement_rating` を `ENGAGEMENT_DIVISOR`（5.4）で、コンポーネント評価値を `COMPONENT_DIVISOR`（1.8）で除算して 0–10 スケールに正規化

| 引数 | 型 | 説明 |
|------|----|------|
| `uploaded_file` | `Union[str, file]` | Excel ファイルのパスまたはファイルオブジェクト |

**戻り値**: `Tuple[DataFrame, DataFrame, DataFrame]`
- `pivot_df`: 正規化済みエンゲージメント評価値 DataFrame
- `signal_df`: シグナル列を含む生データ DataFrame
- `comment_df`: コメントデータ DataFrame

**例外**:
- `ValueError`: 必須列が不足している場合、または `rating2`/`comment` シートの読み込みに失敗した場合

---

## 5. modules/charts.py — グラフ生成

**行数**: 495 行
**役割**: Plotly を使用した各種グラフの生成関数を提供する。すべての関数は `plotly.graph_objects.Figure` を返す。

### プライベート関数

#### `_create_empty_figure(message, height)`

データがない場合に表示するメッセージ付きの空グラフを生成する。

| 引数 | 型 | デフォルト | 説明 |
|------|----|-----------|------|
| `message` | `str` | `"表示できるデータがありません"` | 表示メッセージ |
| `height` | `int` | `420` | グラフ高さ（ピクセル） |

**戻り値**: `Figure`

---

### パブリック関数

#### `create_time_series_chart(df, y_col, title, color_by)`

月次平均の時系列折れ線グラフを生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | `year_month`, `year_month_dt`, および指定メトリクス列を含む DataFrame |
| `y_col` | `str` | Y 軸メトリクス列名（例: `'engagement_rating'`） |
| `title` | `str` | グラフタイトル |
| `color_by` | `Optional[str]` | 色分けグルーピング列名。`None` または `'なし'` の場合は全体平均を表示 |

**動作**:
- `color_by` が指定されている場合: グループ別に月次平均を集計し、複数折れ線を描画する。グループ順序は `get_category_order_with_reference` で決定する。
- `color_by` が `None` または `'なし'` の場合: 全体の月次平均を単一の折れ線で描画する。
- データ点数が 6 以下の場合、X 軸ティックを明示的に設定する。
- Y 軸範囲は `[0, RATING_AXIS_MAX]`（10.3）に固定する。

**戻り値**: `Figure`（高さ 480px）

---

#### `create_recent_group_comparison_chart(df, metric, group_col, range_label)`

選択期間内のグループ別月次平均を比較するグループ棒グラフを生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | `year_month_dt` および指定メトリクス・グループ列を含む DataFrame |
| `metric` | `str` | 集計対象のメトリクス列名 |
| `group_col` | `str` | グループ化に使用する列名 |
| `range_label` | `Optional[str]` | グラフタイトルに追加する期間ラベル（例: `"直近6ヶ月"`） |

**動作**:
- 月別グループ平均を集計し、グループ × 月のグループ棒グラフを生成する。
- 月の新しい順に Blues カラースケールで着色する（`COLOR_SCALE_START` ～ `COLOR_SCALE_END`）。
- Y 軸範囲は `[0, RATING_AXIS_MAX]` に固定する。
- データが空の場合は「比較対象のデータがありません」メッセージ付きの空グラフを返す。

**戻り値**: `Figure`（高さ 480px）

---

#### `create_box_plot(df, x_col, y_col, title)`

グループ別のボックスプロットを生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | データ DataFrame |
| `x_col` | `str` | X 軸グループ列名 |
| `y_col` | `str` | Y 軸メトリクス列名 |
| `title` | `str` | グラフタイトル |

**動作**:
- グループ順序を `get_category_order_with_reference` で決定する。
- マーカー色 `#4c78a8`、枠線色 `#274060`、枠線幅 1.5px で描画する。
- Y 軸範囲は `[0, RATING_AXIS_MAX]` に固定する。

**戻り値**: `Figure`（高さ 450px）

---

#### `create_group_rating_distribution(df, group_col, metric_col, range_label)`

グループ別の評価バンド（高い/中間/低い）構成比を積み上げ棒グラフで生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | データ DataFrame |
| `group_col` | `str` | グループ化に使用する列名 |
| `metric_col` | `str` | 評価対象のメトリクス列名 |
| `range_label` | `Optional[str]` | グラフタイトルに追加する期間ラベル |

**評価バンドの定義**:
- 「高い」: `metric_col >= RATING_BAND_HIGH_THRESHOLD`（6.0）
- 「低い」: `metric_col <= RATING_BAND_LOW_THRESHOLD`（2.0）
- 「中間」: その他

**動作**:
- グループ × 月の組み合わせで集計し、各バンドの構成比（%）と人数を表示する。
- グループ間のギャップを挿入して視認性を高める。
- Y 軸は `[0, 100]` の % スケール（`dtick=10`）に固定する。
- データが空の場合は `_create_empty_figure` を返す。

**戻り値**: `Figure`（高さ 500px）

---

#### `create_radar_chart(df, group_col, title)`

グループ別の活力・熱意・没頭 3 軸レーダーチャートを生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | `vigor_rating`, `dedication_rating`, `absorption_rating` 列を含む DataFrame |
| `group_col` | `str` | グループ化に使用する列名 |
| `title` | `str` | グラフタイトル |

**動作**:
- 各グループの 3 指標の平均値を計算し、グループごとに `go.Scatterpolar` トレースを追加する。
- 多角形を閉じるために最初の値を末尾に追加する。
- 動径軸は `[0, 10]` の範囲（`dtick=1`）で表示する。

**戻り値**: `Figure`（高さ 500px）

---

#### `create_individual_trend(df, individual_name)`

個人のエンゲージメント推移グラフ（棒グラフ + 折れ線グラフの複合）を生成する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | ピボット DataFrame（`name` 列でフィルタリング） |
| `individual_name` | `str` | 表示対象の個人名 |

**動作**:
- エンゲージメント評価値を半透明の棒グラフ（`rgba(15, 76, 129, 0.5)`）で表示する。
- 活力（`#ff8c00`）・熱意（`#b22222`）・没頭（`#006d5b`）を折れ線グラフで重ねる。
- データ点数が 6 以下の場合は X 軸ティックを明示的に設定する。
- Y 軸範囲は `[0, RATING_AXIS_MAX]` に固定する。

**戻り値**: `Figure`（高さ 480px）

---

## 6. modules/signal_processing.py — シグナル処理

**行数**: 367 行
**役割**: シグナル DataFrame の計算・フォーマット・表示処理を担当する。

### 関数リファレンス

#### `apply_signal_rating_calculations(signal_df)`

シグナル DataFrame の評価値を正規化する（生スコア → 0–10 スケール）。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_df` | `DataFrame` | `engagement_rating`, `vigor_rating` 等の列を含む DataFrame |

**動作**: `engagement_rating` を `ENGAGEMENT_DIVISOR`（5.4）で、各コンポーネント評価値を `COMPONENT_DIVISOR`（1.8）で除算する。元の DataFrame を変更しないよう `.copy()` を実行する。

**戻り値**: `DataFrame`

---

#### `derive_intervention_priority(df)`

`intervention_priority_neg` と `intervention_priority_pos` の生値から `intervention_priority`（表示値）と `_priority_is_neg`（フラグ）を導出する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | `intervention_priority_neg`, `intervention_priority_pos` 列、および任意で `flag_constant_6m` 列を含む DataFrame |

**ロジック**:
- `flag_constant_6m` 列が存在する場合、`FLAG_CONSTANT_PRIORITY_POINTS` に基づくポイントを `_neg` に加算する。
- `_neg`（加算後）と `_pos` のどちらが `INTERVENTION_PRIORITY_THRESHOLD`（2）を超えるかを判定する。
- 両方が閾値を超える場合は `_neg` が優先される。
- 表示値 = 選択された生値 - `INTERVENTION_PRIORITY_THRESHOLD`（最小表示値は 1 となる）。

**戻り値**: `DataFrame` — `intervention_priority`（表示値）と `_priority_is_neg`（`bool`）列を追加した DataFrame。

---

#### `style_signal_columns(df, priority_is_neg)`

シグナルテーブルの「介入必要度」列に色スタイルを適用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 日本語列名（`SIGNAL_LABELS` でリネーム済み）を含む表示用 DataFrame |
| `priority_is_neg` | `Series[bool]` | `df` のインデックスに対応する `_priority_is_neg` フラグ Series |

**動作**: `_priority_is_neg=True`（ネガティブ起因）の行は赤色、`False`（ポジティブ起因）の行は緑色でスタイルを適用する。

**戻り値**: `pandas.io.formats.style.Styler`

---

#### `format_signal_display_columns(df)`

シグナル DataFrame の表示用フォーマットを適用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 生値を含むシグナル DataFrame |

**動作**: `intervention_priority` 列の数値を全角数字（例: `２`）に変換する。`flag_constant_6m` 列が存在する場合は `FLAG_CONSTANT_LABELS` で日本語表示名に変換する（未マッチまたは空の場合は `"-"`）。`NaN` の場合は `"-"` を設定する。

**戻り値**: `DataFrame`

---

#### `get_signal_column_config()`

`st.dataframe` の `column_config` 引数に渡すシグナルテーブルのカラム設定辞書を返す。

**引数**: なし
**戻り値**: `dict` — `{"介入必要度": st.column_config.TextColumn(...)}` 形式。

---

#### `render_signal_table(signals, display_cols)`

シグナルテーブルをフォーマット・スタイリングして `st.dataframe` で表示する。

| 引数 | 型 | 説明 |
|------|----|------|
| `signals` | `DataFrame` | `_priority_is_neg` 列を含むシグナル DataFrame |
| `display_cols` | `list[str]` | 表示する列名リスト（英語列名） |

**動作**:
- `signals` が空の場合は `st.info("アクション対象候補はいません")` を表示して終了する。
- `display_cols` に存在しない列がある場合は `st.error` でエラーを表示する。
- 列を `SIGNAL_LABELS` で日本語にリネームし、`format_signal_display_columns` と `style_signal_columns` を適用する。
- テーブル下部に「介入必要度について」「中期傾向について」の popover を表示する。

**戻り値**: `None`

---

#### `replace_abbreviations(text)`

強み・弱みテキスト内の略語を日本語に展開する。

| 引数 | 型 | 説明 |
|------|----|------|
| `text` | `str` | 略語を含むテキスト（`V`, `D`, `A`） |

**変換ルール**: `V` → `活力`、`D` → `熱意`、`A` → `没頭`、`データなし` → `"-"`
空文字または `NaN` の場合は `"-"` を返す。

**戻り値**: `str`

---

#### `format_individual_signal_data(signal_data)`

個人シグナルデータを転置形式に整形して表示用にフォーマットする。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_data` | `DataFrame` | 個人の最新波シグナルデータ |

**動作**:
1. `derive_intervention_priority` を適用する。
2. 強み・弱みテキストを `replace_abbreviations` で展開する。
3. `intervention_priority` を全角数字 + `"(negative)"` または `"(positive)"` サフィックスでフォーマットする（値が 0 の場合はサフィックスなし）。
4. `level` を `LEVEL_LABELS` で日本語に変換する。
5. `flag_constant_6m` を `FLAG_CONSTANT_LABELS` で日本語表示名に変換する（未マッチまたは空の場合は `"-"`）。
6. その他列を文字列フォーマットし、`NaN` を `"-"` に変換する。
7. DataFrame を転置し、インデックスを `SIGNAL_LABELS` で日本語にリネームする。

**戻り値**: `Tuple[DataFrame, bool]`
- `DataFrame`: 転置済み表示用 DataFrame（列名: `"値"`）
- `bool`: `_priority_is_neg` の値（色スタイリング用）

---

#### `sort_signals_by_trend_and_priority(signals)`

シグナルデータをトレンドグループ・介入優先度・課の順でソートする。

| 引数 | 型 | 説明 |
|------|----|------|
| `signals` | `DataFrame` | `_priority_is_neg`, `intervention_priority`, `trend_refined`, `section` 列を含む DataFrame |

**ソート順序**:
1. 優先度タイプ（ネガティブ優先: `_priority_is_neg` 降順）
2. 介入必要度（降順）
3. トレンドグループ（ネガティブ=0、中立=1、ポジティブ=2 の昇順）
4. 課（`group_order_config.json` に基づく課順序の昇順）

**戻り値**: `DataFrame`（ソート済み、一時列 `_trend_group`, `_section_order` は削除済み）

---

#### `get_signal_data(signal_df, filtered_df, end_dt)`

現在のサイドバーフィルターと最新波に絞ったシグナルデータを取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_df` | `DataFrame` | 全 `rating2` データの DataFrame |
| `filtered_df` | `DataFrame` | サイドバーフィルター適用済みの評価 DataFrame（スコープ特定用） |
| `end_dt` | `Timestamp` | グローバル期間フィルターの終端日時（最新波を定義する） |

**動作**:
1. `signal_df` を `end_dt` でフィルタリングして最新波のみを抽出する。
2. `filtered_df` の `name` 列と突き合わせて、フィルター適用済みスコープの個人のみに絞る。
3. `intervention_priority_neg` または `intervention_priority_pos` が `INTERVENTION_PRIORITY_THRESHOLD`（2）を超える行のみを返す。
4. `derive_intervention_priority` と `sort_signals_by_trend_and_priority` を適用する。

**戻り値**: `DataFrame`

---

## 7. modules/components.py — UI コンポーネント

**行数**: 515 行
**役割**: 複数タブで共通して使用する UI コンポーネント（コメントセクション・アクション候補・グルーピングフィルター）を提供する。

### 関数リファレンス

#### `filter_signal_by_selection(signal_df, main_df, dept_choice, section_choice)`

部署・課の選択値でシグナル DataFrame をフィルタリングする。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_df` | `DataFrame` | フィルタリング対象のシグナル DataFrame |
| `main_df` | `DataFrame` | メイン DataFrame（部署・課フィルター適用済み） |
| `dept_choice` | `str` | 選択中の部署名（`"すべて"` でフィルタリングなし） |
| `section_choice` | `str` | 選択中の課名（`"すべて"` でフィルタリングなし） |

**戻り値**: `DataFrame`

---

#### `prepare_comment_data(comment_df, start_dt, end_dt, scope)`

コメントデータを表示用に前処理する。

| 引数 | 型 | 説明 |
|------|----|------|
| `comment_df` | `DataFrame` | `current_section`, `current_department`, `current_division` 列を含む生コメント DataFrame |
| `start_dt` | `Timestamp` | フィルタリング開始日時 |
| `end_dt` | `Timestamp` | フィルタリング終了日時 |
| `scope` | `Optional[list[str]]` | 組織スコープ値リスト（部署名・部門名を含む場合がある） |

**動作**:
1. `year_month_dt` で `[start_dt, end_dt]` の範囲にフィルタリングする。
2. `current_*` 列を `section`, `department`, `division` にマッピングし、欠損値を `"未設定"` で補完する。
3. `filter_dataframe_by_scope` でスコープフィルタリングを適用する（`division`, `department`, `section` の OR 条件）。

**注意**: コメントデータはメインデータと結合しない。コメント自身の組織列（`current_*`）を使用する。

**戻り値**: `DataFrame`

---

#### `render_action_candidates(signal_df, main_df, end_dt, privilege_mgr, current_privilege)`

「アクション対象候補」セクションを表示する。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_df` | `DataFrame` | タブスコープでフィルタリング済みのシグナル DataFrame |
| `main_df` | `DataFrame` | 現在のビューのメイン DataFrame |
| `end_dt` | `Timestamp` | シグナルデータの終端日時 |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |

**動作**:
1. `privilege_mgr.get_section_scope` でアクション候補のセクションスコープを取得する。
2. スコープでシグナルデータをフィルタリングする。
3. スコープがアクセス許可（`None` または空でない）の場合に `"アクション対象候補"` サブヘッダーを表示する。
4. `get_signal_data` と `render_signal_table` でテーブルを表示する。

**戻り値**: `None`

---

#### `render_concern_section(comment_data, end_dt, key_prefix, privilege_mgr, current_privilege)`

「気になった出来事や気づき」セクションをエクスパンダー内に表示する。

| 引数 | 型 | 説明 |
|------|----|------|
| `comment_data` | `DataFrame` | `prepare_comment_data` 処理済みのコメント DataFrame |
| `end_dt` | `Timestamp` | 「直近1ヶ月」フィルタリング基準日時 |
| `key_prefix` | `str` | Streamlit ウィジェットの一意キープレフィックス |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |

**動作**:
- `privilege_mgr.has_feature_access` でアクセス権を確認し、アクセス不可の場合は何も表示しない。
- 「全期間」「直近1ヶ月」のラジオボタンで期間を切り替える。
- 課 → 氏名 → コンテンツの入れ子エクスパンダー形式で表示する。
- 課の順序は `GROUP_ORDER_MAP` の `section` キーに基づく。

**戻り値**: `None`

---

#### `render_comment_section(comment_data, end_dt, key_prefix, privilege_mgr, current_privilege, share_scope, latest_year_month)`

「共有したいこと」セクションを匿名化対応・返信機能付きで表示する。

| 引数 | 型 | 説明 |
|------|----|------|
| `comment_data` | `DataFrame` | `prepare_comment_data` 処理済みのコメント DataFrame |
| `end_dt` | `Timestamp` | 「直近1ヶ月」フィルタリング基準日時 |
| `key_prefix` | `str` | Streamlit ウィジェットの一意キープレフィックス |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |
| `share_scope` | `Optional[list[str]]` | 「共有したいこと」のセクションスコープ（アクセス確認用） |
| `latest_year_month` | `Optional[Timestamp]` | 返信可能判定基準となる最新の `year_month_dt` |

**動作**:
- `privilege_mgr.has_feature_access` でアクセス権を確認する。
- `share_scope` が空リスト（`[]`）の場合は表示しない。
- `privilege_mgr.should_anonymize_section` で匿名化要否を判定する。
  - 匿名化あり: 氏名を非表示にし、年月 → コメント内容のみを表示する。
  - 匿名化なし: 課 → 氏名 → コメント内容を表示し、最新月のコメントに返信ボタンを表示する。
- 返信は `load_responses` でキャッシュ済みデータから取得し、`_render_responses` で表示する。
- 返信入力は `_render_response_input` で 2 段階確認フロー（入力 → 確認 → 送信）で処理する。

**戻り値**: `None`

---

#### `render_comments_and_signals(signal_df, main_df, comment_df, start_dt, end_dt, key_prefix, privilege_mgr, current_privilege, is_authenticated, latest_year_month)`

アクション候補・気になった出来事・共有したいことの 3 セクションをまとめて表示する便利関数。

| 引数 | 型 | 説明 |
|------|----|------|
| `signal_df` | `DataFrame` | タブ・グルーピングスコープでフィルタリング済みのシグナル DataFrame |
| `main_df` | `DataFrame` | 現在のビューのメイン DataFrame |
| `comment_df` | `DataFrame` | 生コメント DataFrame（内部で前処理を実施） |
| `start_dt` | `Timestamp` | 開始日時 |
| `end_dt` | `Timestamp` | 終了日時 |
| `key_prefix` | `str` | Streamlit ウィジェットの一意キープレフィックス |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |
| `is_authenticated` | `bool` | ユーザーが認証済みかどうか |
| `latest_year_month` | `Optional[Timestamp]` | 返信可能判定基準となる最新の `year_month_dt` |

**動作**: `is_authenticated=False` の場合は何も表示しない。`render_action_candidates` → `prepare_comment_data` → `render_concern_section` → `render_comment_section` の順で処理する。

**戻り値**: `None`

---

#### `apply_grouping_filters(df, signal_df, privilege_mgr, current_privilege, grouping_choice, tab_name, selected_filters)`

グルーピング選択に基づく 3 層フィルタリングを DataFrame に適用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | メイン DataFrame |
| `signal_df` | `Optional[DataFrame]` | シグナル DataFrame（不要な場合は `None`） |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |
| `grouping_choice` | `str` | 選択中のグルーピングオプション（例: `'section'`） |
| `tab_name` | `str` | 現在のタブ名（エイリアス適用に使用） |
| `selected_filters` | `dict` | サイドバーフィルターの選択値辞書（`dimension_value` キーを含む） |

**3 層フィルタリング**:
1. **グルーピングスコープ**: `privilege_mgr.get_grouping_scope` で権限に応じたデータスコープを適用する。`selected_filters['dimension_value'] != 'すべて'` の場合は `grouping_scope_filtered` を使用する。
2. **職位フィルター**: `grouping_choice == 'grade'` の場合のみ、`privilege_mgr.get_grade_filter_for_grouping` で職位制限を適用する。
3. **課エイリアス**: `grouping_choice == 'section'` の場合のみ、`privilege_mgr.get_section_aliases` で課名をエイリアスに置換する（プライバシー保護・集約目的）。

**戻り値**: `Tuple[DataFrame, Optional[DataFrame]]` — フィルタリング済みの `(df, signal_df)`

---

## 8. modules/filter_helpers.py — フィルターヘルパー

**行数**: 489 行
**役割**: サイドバーの統合カスケードフィルターシステムのヘルパー関数を提供する。

**フィルターカスケード順序**: 部門 → 職位 → 部署 → 課 → チーム → プロジェクト → 個人

### 関数リファレンス

#### `get_sidebar_scope(privilege_mgr, current_privilege)`

全許可タブのデータスコープの UNION を取得する。サイドバーのドロップダウン選択肢を構築するために使用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |

**戻り値**: `Optional[list]`
- `None`: すべてのデータを許可（admin）
- `list`: 許可された組織値のリスト（全タブの UNION）
- `[]`: アクセス不可

---

#### `get_section_restriction(df, privilege_mgr, current_privilege)`

課ドロップダウンを制限するための課レベルスコープ値を取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | メイン DataFrame（部署名・部門名の特定に使用） |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |

**動作**: スコープ値のうち、部署名・部門名以外のもの（= 課レベルの値）を特定する。課管理者は自分が管理する課のみ閲覧可能な場合に使用する。

**戻り値**: `Optional[list]`
- `None`: 課レベルの制限なし（admin または部署レベルのみのスコープ）
- `list`: 許可された課名のリスト

---

#### `get_cascaded_options(df, filter_type, privilege_mgr, current_privilege)`

親フィルターの選択値と権限制限に基づいたドロップダウン選択肢を取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 親フィルターおよびスコープでフィルタリング済みの DataFrame |
| `filter_type` | `str` | フィルタータイプ: `'division'` / `'grade'` / `'department'` / `'section'` / `'team'` / `'project'` / `'name'` |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |

**動作**:
- `filter_type == 'grade'` の場合は `"未設定"` を選択肢に含める。
- 空文字の選択肢を除外する。
- `get_options` で `group_order_config.json` に基づくソートを適用する。

**戻り値**: `list[str]`

---

#### `apply_unified_filter(df, filter_key, selected_value, dimension_info)`

単一フィルターを DataFrame に適用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | フィルタリング対象の DataFrame |
| `filter_key` | `str` | フィルタータイプ: `'division'` / `'grade'` / `'department'` / `'dimension_value'` / `'individual'` |
| `selected_value` | `str` | 選択値（`'すべて'` の場合はフィルタリングなし） |
| `dimension_info` | `Optional[Tuple]` | `filter_key='dimension_value'` の場合のみ使用: `(dimension_type, value)` のタプル。`dimension_type` は `'課'`、`'チーム'`、`'プロジェクト'` のいずれか |

**戻り値**: `DataFrame`

---

#### `should_reset_child_filters(parent_key, current_value)`

親フィルターの値が変化したかどうかを検知する。セッション状態の `_prev_{parent_key}` と現在値を比較する。

| 引数 | 型 | 説明 |
|------|----|------|
| `parent_key` | `str` | 親フィルターのセッション状態キー |
| `current_value` | `str` | 親フィルターの現在値 |

**戻り値**: `bool` — 変化があった場合は `True`（子フィルターをリセットすべき状態）。

**副作用**: セッション状態の `_prev_{parent_key}` を `current_value` で更新する。

---

#### `reset_child_filters(parent_level)`

指定した親レベル以下の子フィルターを全てリセットする（`'すべて'` にリセット）。

| 引数 | 型 | 説明 |
|------|----|------|
| `parent_level` | `str` | リセット起点のフィルターレベル: `'division'` / `'grade'` / `'department'` / `'section'` / `'team'` / `'project'` |

**カスケード定義**:
- `'division'` → grade, department, section, team, project, individual をリセット
- `'grade'` → department, section, team, project, individual をリセット
- `'department'` → section, team, project, individual をリセット
- `'section'` → team, project, individual をリセット
- `'team'` → project, individual をリセット
- `'project'` → individual をリセット

**戻り値**: `None`

---

#### `render_unified_sidebar_filters(df, signal_df, privilege_mgr, current_privilege, is_authenticated_user, grouping_options)`

サイドバーの統合フィルターカスケード全体をレンダリングし、フィルタリング済み DataFrame を返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 期間フィルター適用済みのメイン DataFrame |
| `signal_df` | `DataFrame` | 期間フィルター適用済みのシグナル DataFrame |
| `privilege_mgr` | `PrivilegeManager` | PrivilegeManager インスタンス |
| `current_privilege` | `str` | 現在のユーザーの権限クラス |
| `is_authenticated_user` | `bool` | ユーザーが認証済みかどうか |
| `grouping_options` | `List[str]` | 許可されたグルーピングオプションリスト |

**動作**:
1. `get_sidebar_scope` で最広スコープを取得し、`df` と `signal_df` に適用する。
2. `get_section_restriction` で課ドロップダウン制限を取得する。
3. サイドバーに「表示カテゴリ」セレクトボックスを表示する。
4. 「フィルター設定」エクスパンダー内に部門 → 職位 → 部署 → 課 → チーム → プロジェクト → 個人のカスケードフィルターを表示する。
5. 各フィルター変更時に `should_reset_child_filters` で子フィルターのリセットを検知・実行する。
6. `'name'` が許可グルーピングに含まれる場合のみ個人フィルターを表示する。
7. 個人フィルターが「すべて」以外の場合は `mail_address` でシグナル DataFrame をフィルタリングする。

**戻り値**: `Tuple[DataFrame, DataFrame, Dict[str, str], str]`
- `filtered_df`: フィルタリング済みメイン DataFrame
- `filtered_signal_df`: フィルタリング済みシグナル DataFrame
- `selected_filters`: フィルター選択値辞書（キー: `division`, `grade`, `department`, `section`, `team`, `project`, `individual`, `dimension_value`）
- `grouping_choice`: 選択中のグルーピングオプション

---

## 9. modules/privilege_manager.py — 権限管理

**行数**: 622 行
**役割**: `config/privileges.yaml` から権限設定を読み込み、タブ・セクション・グルーピング・機能単位でのアクセス制御を提供する。

詳細な権限システム仕様は `docs/PRIVILEGE_SYSTEM.md` を参照。

### クラス: `PrivilegeManager`

シングルトンパターンで実装されており、`PrivilegeManager()` の呼び出しは常に同一インスタンスを返す。設定ファイル（`config/privileges.yaml`）は起動時に一度だけ読み込まれる。

#### メソッド一覧

| メソッド | 説明 |
|----------|------|
| `reload_config()` | 設定ファイルを強制再読み込みする |
| `get_base_privilege(privilege_class)` | 基本権限クラス定義を取得する |
| `get_user_privilege(username)` | ユーザー固有の権限設定を取得する |
| `get_effective_config(privilege)` | 継承を解決した有効な権限設定を取得する |
| `get_data_scope_for_tab(privilege, tab)` | タブ別データスコープを取得する |
| `get_section_scope(privilege, section)` | UI セクション別データスコープを取得する |
| `get_grouping_scope(privilege, grouping, dimension_filtered)` | グルーピング別データスコープを取得する |
| `get_grade_filter_for_grouping(privilege, grouping, dimension_filtered)` | グルーピング別職位フィルター値を取得する |
| `should_anonymize_section(privilege, section)` | セクションの匿名化要否を確認する |
| `should_anonymize_tab(privilege, tab)` | タブの匿名化要否を確認する |
| `get_allowed_tabs(privilege)` | アクセス許可されたタブ一覧を取得する |
| `get_allowed_groupings(privilege)` | アクセス許可されたグルーピング一覧を取得する |
| `has_feature_access(privilege, feature)` | 機能へのアクセス権を確認する |
| `should_anonymize(privilege, feature)` | 機能の匿名化要否を確認する |
| `get_section_aliases(privilege, tab)` | 権限・タブ別の課エイリアスマッピングを取得する |
| `should_use_section_aliases(privilege, tab)` | 課エイリアスを使用すべきかどうかを確認する |
| `get_effective_scope(privilege, tab, grouping, dimension_filtered)` | タブとグルーピングの組み合わせから有効スコープを計算する |

#### `get_effective_config(privilege)`

継承チェーンを解決して有効な権限設定を取得する。`user_privileges` → `privileges`（基本クラス）の順に検索し、見つからない場合は `anonymous` の設定を返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `privilege` | `str` | ユーザーの権限識別子（例: `'dev1'`, `'admin'`） |

**戻り値**: `dict` — 継承解決済みの設定辞書

---

#### `get_data_scope_for_tab(privilege, tab)`

特定タブでのデータスコープを取得する。

**戻り値**: `Optional[list]`
- `None`: すべてのデータを許可
- `list`: 許可された組織値リスト
- `[]`: アクセス不可

---

#### `get_section_scope(privilege, section)`

特定 UI セクションでのデータスコープを取得する。対象セクション: `計測値`, `主な指標`, `アクション対象候補`, `共有したいこと`

**戻り値**: `Optional[list]`（`get_data_scope_for_tab` と同様）

---

#### `get_grouping_scope(privilege, grouping, dimension_filtered=False)`

グルーピング選択に応じたデータスコープを取得する。`dimension_filtered=True` の場合は `grouping_scope_filtered` 設定（ディメンション値が「すべて」以外の場合）を優先使用する。

**グルーピングと内部キーのマッピング**:
- `department`, `section`, `team`, `project` → `'organization'`
- `grade` → `'grade'`
- `name` → `'name'`
- `なし` → `'none'`

---

#### `get_section_aliases(privilege, tab)`

特定権限・タブの組み合わせで適用すべき課エイリアスマッピングを取得する。

**戻り値**: `dict` — `{課名: エイリアス表示名}` 形式。エイリアスなしの場合は `{}`。

---

### モジュールレベル関数

#### `get_privilege_manager()`

`PrivilegeManager` のシングルトンインスタンスを返す。

**引数**: なし
**戻り値**: `PrivilegeManager`

---

#### `filter_dataframe_by_scope(df, scope_values, org_columns=None)`

スコープ値に基づいて DataFrame をフィルタリングする。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | フィルタリング対象の DataFrame |
| `scope_values` | `Optional[list]` | `None`: 全データ許可、`list`: 許可値リスト、`[]`: アクセス不可 |
| `org_columns` | `list` | チェック対象の組織列名（デフォルト: `['division', 'department', 'section']`） |

**動作**: `org_columns` の各列に対して `isin(scope_values)` でマスクを生成し、OR 条件で結合する。

**戻り値**: `DataFrame`

---

#### `combine_scopes(tab_scope, grouping_scope)`

タブスコープとグルーピングスコープを組み合わせて有効スコープを返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `tab_scope` | `Optional[list]` | タブレベルのスコープ |
| `grouping_scope` | `Optional[list]` | グルーピングレベルのスコープ |

**ルール**:
- どちらかが空リスト（アクセス不可）なら空リストを返す。
- `grouping_scope` が `None`（全許可）なら `tab_scope` を返す。
- `tab_scope` が `None`（全許可）なら `grouping_scope` を返す。
- 両方に値がある場合は `grouping_scope` を返す（追加フィルターとして機能）。

**戻り値**: `Optional[list]`

---

#### `apply_section_aliases(df, alias_mapping, section_column='section')`

DataFrame の課名をエイリアス表示名に置換する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 課列を含む DataFrame |
| `alias_mapping` | `dict` | `{課名: エイリアス名}` 形式のマッピング |
| `section_column` | `str` | 課列名（デフォルト: `'section'`） |

**戻り値**: `DataFrame`

---

#### `filter_dataframe_by_grade(df, allowed_grades, grade_column='grade')`

許可された職位値で DataFrame をフィルタリングする。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | フィルタリング対象の DataFrame |
| `allowed_grades` | `Optional[list]` | `None`: 全職位許可、`list`: 許可職位リスト |
| `grade_column` | `str` | 職位列名（デフォルト: `'grade'`） |

**戻り値**: `DataFrame`

---

#### `anonymize_dataframe(df, name_columns=None)`

DataFrame の個人名列をマスク文字列 `'***'` で匿名化する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 匿名化対象の DataFrame |
| `name_columns` | `list` | 匿名化対象の列名リスト（デフォルト: `['name', '氏名', 'employee_name', 'fullname', 'full_name']`） |

**戻り値**: `DataFrame`

---

## 10. modules/statistics.py — 統計

**行数**: 285 行
**役割**: グループ別・全体の統計計算（平均・傾向の傾き・標準偏差）と表示フォーマットを提供する。

### 関数リファレンス

#### `format_measured_data(df, metric_col, group_col=None, reference_df=None)`

「計測値」セクション表示用に時系列データを集計・フォーマットする。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | `year_month` 列を含む時系列 DataFrame |
| `metric_col` | `str` | 集計対象のメトリクス列名（例: `'engagement_rating'`） |
| `group_col` | `Optional[str]` | グルーピング列名。`None` または `'なし'` の場合は全体集計 |
| `reference_df` | `Optional[DataFrame]` | カテゴリ順序決定用の参照 DataFrame（デフォルト: `df` を使用） |

**動作**:
- グルーピングあり: `year_month × group_col` でグループ平均を計算し、グルーピング列 → 年月 → メトリクスの列順で返す。
- グルーピングなし: `year_month` で全体平均を計算し、年月 → メトリクスの列順で返す。
- メトリクス値を小数点 1 桁でフォーマットし、`NaN` は `"-"` に変換する。
- 列名を日本語（`METRIC_LABELS`, `GROUPING_LABEL_MAP`）にリネームする。

**戻り値**: `DataFrame`（`st.dataframe` に直接渡せる形式）

---

#### `format_statistics_for_display(stats_df)`

統計 DataFrame の数値列を表示用にフォーマットする。

| 引数 | 型 | 説明 |
|------|----|------|
| `stats_df` | `DataFrame` | `calculate_group_statistics` の出力 DataFrame |

**フォーマット**:
- `平均`: 小数点 2 桁
- `傾向の傾き`: 小数点 3 桁
- `標準偏差`: 小数点 2 桁

**戻り値**: `DataFrame`

---

#### `calculate_group_statistics(df, metric_col, group_col=None, signal_df=None, end_dt=None)`

グループ別（または全体）の統計値を計算する。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 時系列 DataFrame |
| `metric_col` | `str` | 分析対象のメトリクス列名 |
| `group_col` | `Optional[str]` | グルーピング列名（`None` または `'なし'` の場合は全体統計） |
| `signal_df` | `Optional[DataFrame]` | トレンド列取得用のシグナル DataFrame（`group_col='name'` の場合に使用） |
| `end_dt` | `Optional[Timestamp]` | シグナルデータのフィルタリング終端日時（`signal_df` と組み合わせて使用） |

**計算内容**:
- `平均`: 全期間の平均値
- `傾向の傾き`: 月次平均値に対する線形回帰の傾き（`numpy.polyfit` を使用、データが 2 点未満の場合は 0.0）
- `標準偏差`: 全期間の標準偏差

**`group_col='name'` の場合の追加処理**:
- `signal_df` と `end_dt` が指定されている場合、最新波の `trend_recent`（短期傾向）と `trend_refined`（中期傾向）列をマージする。
- 氏名列 → トレンド列 → 統計列の順に列を並べ替える。

**グループ順序**: `get_category_order_with_reference` で `group_order_config.json` に基づく順序を適用する。

**戻り値**: `DataFrame`（グループ別統計を含む。データがない場合は空の `DataFrame`）

---

## 11. modules/utils.py — ユーティリティ

**行数**: 229 行
**役割**: グループ順序管理・ドロップダウン選択肢生成・フィルターコントロール UI のユーティリティ関数を提供する。

### モジュールレベル変数

#### `GROUP_ORDER_MAP`

モジュール読み込み時に `group_order_config.json` から読み込まれるグループ順序設定辞書。

```python
GROUP_ORDER_MAP: dict  # {order_key: [value1, value2, ...]}
```

設定ファイルが存在しない場合や読み込みに失敗した場合は空辞書 `{}` となる。

### 関数リファレンス

#### `load_group_orders()`

`GROUP_ORDER_FILE`（`group_order_config.json`）からグループ順序設定を読み込む。すべてのキー・値を文字列に変換して返す。

**引数**: なし
**戻り値**: `dict` — `{order_key: [str, ...]}` 形式。ファイル不在または JSON パースエラー時は `{}`。

---

#### `sort_with_config(values, order_key=None)`

`GROUP_ORDER_MAP` の設定に基づいて値リストをソートする。

| 引数 | 型 | 説明 |
|------|----|------|
| `values` | `list` | ソート対象の値リスト |
| `order_key` | `Optional[str]` | `GROUP_ORDER_MAP` のキー名。`None` またはキーが存在しない場合はアルファベット順 |

**動作**: 重複を除去し、設定順序に従ってソートする。設定に含まれていない値は末尾にアルファベット順で追加する。

**戻り値**: `list`

---

#### `get_category_order_for_values(order_key, values)`

指定した `order_key` と値リストに基づくカテゴリ順序リストを取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `order_key` | `str` | グループ順序設定のキー名 |
| `values` | `list` | 順序付け対象の値リスト |

**戻り値**: `list`（`sort_with_config` の結果）

---

#### `get_category_order_with_reference(order_key, values, reference_df)`

参照 DataFrame を使用したカテゴリ順序取得（個人名の職位順ソートに対応）。

| 引数 | 型 | 説明 |
|------|----|------|
| `order_key` | `str` | グループ順序設定のキー名 |
| `values` | `list` | 順序付け対象の値リスト |
| `reference_df` | `DataFrame` | 職位順序参照用 DataFrame（`name` 列と `grade` 列を含む） |

**動作**: `order_key == 'name'` の場合は `sort_names_by_grade` で職位順ソートを行う。それ以外は `get_category_order_for_values` に委譲する。

**戻り値**: `list`

---

#### `sort_names_by_grade(names, reference_df)`

個人名リストを職位順でソートする（職位が未設定の場合はアルファベット順に補完）。

| 引数 | 型 | 説明 |
|------|----|------|
| `names` | `list[str]` | ソート対象の個人名リスト |
| `reference_df` | `DataFrame` | `name` 列と `grade` 列を含む参照 DataFrame |

**動作**:
1. `grade` 列の値を `get_category_order_for_values('grade', ...)` で職位順序に変換する。
2. 各個人の最低職位ランク（最上位職位）を取得し、`(rank, name)` でソートする。
3. `reference_df` が条件を満たさない場合はアルファベット順を返す。

**戻り値**: `list[str]`

---

#### `get_options(series, remove_unset=False, order_key=None)`

Series からユニークな選択肢リストを取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `series` | `pd.Series` | 選択肢の元となるデータ Series |
| `remove_unset` | `bool` | `True` の場合、`"未設定"` を選択肢から除外する |
| `order_key` | `Optional[str]` | `GROUP_ORDER_MAP` のキー名（ソート用） |

**戻り値**: `list`（`NaN` を除いたユニーク値リスト、設定ベースでソート済み）

---

#### `render_department_and_group_controls(df, tab_key, grouping_options)`

部署・課・グルーピングの 3 コントロールを 3 カラムレイアウトで表示する（旧フィルターシステム用）。

| 引数 | 型 | 説明 |
|------|----|------|
| `df` | `DataFrame` | 対象の DataFrame |
| `tab_key` | `str` | タブ固有のキープレフィックス |
| `grouping_options` | `list` | グルーピング選択肢リスト |

**動作**:
- `reset_local_filters` フラグが `True` の場合、各コントロールをデフォルト値にリセットする。
- 部署の選択に応じてカスケード的に課の選択肢を絞り込む。

**戻り値**: `Tuple[DataFrame, str, str, str]` — `(filtered_df, dept_choice, section_choice, grouping_choice)`

---

#### `render_grouping_selector(tab_key, grouping_options)`

グルーピングセレクターのみを表示する（新統合フィルターシステム用）。`render_department_and_group_controls` の代替。

| 引数 | 型 | 説明 |
|------|----|------|
| `tab_key` | `str` | タブ固有のキープレフィックス（セッション状態キーに使用） |
| `grouping_options` | `list` | グルーピング選択肢リスト |

**動作**:
- `reset_local_filters` フラグが `True` の場合、デフォルト値にリセットする。
- `GROUPING_LABEL_MAP` で日本語ラベルを表示する。
- 選択肢が空の場合は `'なし'` を返す。

**戻り値**: `str` — 選択中のグルーピングオプション

---

## 12. modules/encryption.py — 暗号化

**行数**: 79 行
**役割**: Fernet 対称暗号化を使用したファイルの暗号化・復号ユーティリティを提供する。

### 関数リファレンス

#### `get_encryption_key()`

Streamlit secrets から暗号化キーを取得する。

**引数**: なし
**戻り値**: `bytes` — Fernet 暗号化キー
**例外**: `ValueError` — `EXCEL_ENCRYPTION_KEY` シークレットが設定されていない場合

---

#### `decrypt_file(encrypted_data)`

暗号化されたファイルデータを Fernet で復号する。

| 引数 | 型 | 説明 |
|------|----|------|
| `encrypted_data` | `bytes` | 暗号化済みファイルの内容 |

**戻り値**: `bytes` — 復号済みファイルの内容

---

#### `decrypt_file_to_stream(encrypted_file_path)`

暗号化ファイルをパスから読み込んで復号し、メモリ上のストリームとして返す。

| 引数 | 型 | 説明 |
|------|----|------|
| `encrypted_file_path` | `str` | 暗号化ファイルのパス |

**戻り値**: `BytesIO` — 復号済みデータのインメモリファイルオブジェクト

---

#### `is_encrypted_file(file_path)`

ファイルパスの拡張子から暗号化ファイルかどうかを判定する。

| 引数 | 型 | 説明 |
|------|----|------|
| `file_path` | `str` | 判定対象のファイルパス |

**戻り値**: `bool` — `.encrypted` または `.enc` 拡張子の場合は `True`

---

## 13. modules/response_manager.py — 返信管理

**行数**: 171 行
**役割**: 「共有したいこと」コメントへの返信を Google Sheets で管理する。セッション状態によるキャッシュで API 呼び出し回数を最小化する。

**必要シークレット**:
- `gcp_service_account`: Google サービスアカウント認証情報
- `RESPONSE_SHEET_ID`: Google スプレッドシート ID

**Google Sheet 列定義**:

| 列名 | 説明 |
|------|------|
| `year_month` | コメントの年月（例: `"2026-03"`） |
| `member_email` | コメント投稿者のメールアドレス |
| `comment` | 元コメントのテキスト |
| `responder_account` | 返信者のログインアカウント名 |
| `responder_name` | 返信者の表示名 |
| `response_text` | 返信内容 |
| `responded_at` | 返信日時（ISO フォーマット） |

### 定数

| 定数 | 値 | 説明 |
|------|----|------|
| `CACHE_KEY` | `"_response_cache"` | セッション状態キャッシュキー |
| `SHEET_NAME` | `"responses"` | Google Sheet のワークシート名 |

### 関数リファレンス

#### `load_responses()`

Google Sheet から返信一覧を読み込む。セッション状態にキャッシュされている場合はキャッシュを返す。

**引数**: なし
**戻り値**: `DataFrame` — 全返信データ。シートが空の場合や読み込みエラーの場合は `RESPONSE_COLUMNS` を列とする空 DataFrame。

**副作用**: 読み込み成功時はセッション状態の `"_response_cache"` に結果をキャッシュする。

---

#### `post_response(year_month, member_email, comment, responder_account, responder_name, response_text)`

コメントへの返信を Google Sheet に追記する。

| 引数 | 型 | 説明 |
|------|----|------|
| `year_month` | `str` | コメントの年月（例: `"2026-03"`） |
| `member_email` | `str` | コメント投稿者のメールアドレス |
| `comment` | `str` | 元コメントのテキスト |
| `responder_account` | `str` | 返信者のログインアカウント名 |
| `responder_name` | `str` | 返信者の表示名 |
| `response_text` | `str` | 返信内容 |

**動作**: `worksheet.append_row` で行を追記し、成功時にセッション状態のキャッシュ（`"_response_cache"`）を削除して次回アクセス時に再読み込みを強制する。

**戻り値**: `bool` — 追記成功時は `True`、例外発生時は `False`（`st.error` でエラーを表示）

---

#### `get_responses_for_comment(responses_df, year_month, member_email, comment)`

特定コメントに対する返信を取得する。

| 引数 | 型 | 説明 |
|------|----|------|
| `responses_df` | `DataFrame` | `load_responses` の出力 DataFrame |
| `year_month` | `str` | コメントの年月 |
| `member_email` | `str` | コメント投稿者のメールアドレス |
| `comment` | `str` | 元コメントのテキスト |

**動作**: `year_month`、`member_email`、`comment` の 3 列で完全一致するレコードを抽出し、`responded_at` の昇順でソートする。

**戻り値**: `DataFrame`（`responses_df` が空の場合はそのまま返す）

---

#### `make_comment_key(year_month, member_email, comment)`

コメントを一意に識別するための MD5 ハッシュキーを生成する。Streamlit ウィジェットキーの重複を防ぐために使用する。

| 引数 | 型 | 説明 |
|------|----|------|
| `year_month` | `str` | コメントの年月 |
| `member_email` | `str` | コメント投稿者のメールアドレス |
| `comment` | `str` | コメントのテキスト |

**動作**: `"{year_month}|{member_email}|{comment}"` を UTF-8 エンコードして MD5 ハッシュ化し、先頭 10 文字を返す。

**戻り値**: `str`（10 文字の 16 進数文字列）

---

## 付録: モジュール間依存関係

```
app.py
  ├─ modules/config.py          （定数・設定）
  ├─ modules/auth.py            （認証）
  │    └─ modules/config.py
  ├─ modules/data_loader.py     （データ読み込み）
  │    └─ modules/config.py
  ├─ modules/charts.py          （グラフ生成）
  │    ├─ modules/config.py
  │    └─ modules/utils.py
  ├─ modules/signal_processing.py（シグナル処理）
  │    ├─ modules/config.py
  │    └─ modules/utils.py
  ├─ modules/statistics.py      （統計計算）
  │    ├─ modules/config.py
  │    └─ modules/utils.py
  ├─ modules/utils.py           （ユーティリティ）
  │    └─ modules/config.py
  ├─ modules/privilege_manager.py（権限管理）
  ├─ modules/filter_helpers.py  （フィルターヘルパー）
  │    ├─ modules/utils.py
  │    └─ modules/privilege_manager.py
  ├─ modules/components.py      （UI コンポーネント）
  │    ├─ modules/config.py
  │    ├─ modules/utils.py
  │    ├─ modules/signal_processing.py
  │    ├─ modules/privilege_manager.py
  │    ├─ modules/auth.py
  │    └─ modules/response_manager.py
  ├─ modules/encryption.py      （暗号化）
  └─ modules/response_manager.py（返信管理）
```

---

## 付録: 主要データ型

| 変数名 | 型 | 説明 |
|--------|----|------|
| `pivot_df` | `DataFrame` | 正規化評価値（0–10）、個人×月のデータ |
| `signal_df` | `DataFrame` | シグナル列を含む生データ（`rating2` シート由来） |
| `comment_df` | `DataFrame` | コメントデータ（`comment` シート由来） |
| `filtered_df` | `DataFrame` | サイドバーフィルター適用後のメイン DataFrame |
| `filtered_signal_df` | `DataFrame` | サイドバーフィルター適用後のシグナル DataFrame |
| `scope_values` | `Optional[list]` | `None`: 全データ許可、`list`: 許可値リスト、`[]`: アクセス不可 |
| `privilege` | `str` | 権限クラス識別子（例: `'admin'`, `'dev1'`） |
| `year_month_dt` | `Timestamp` | `year_month` から変換した `pd.Timestamp`（月の初日） |
