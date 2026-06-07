# Technical Architecture Document

Work Engagement Dashboard 技術仕様書

> **関連ドキュメント:** 詳細な仕様は以下を参照してください。
> - [INDEX.md](INDEX.md) - ドキュメント一覧・読書ガイド
> - [DATA_PIPELINE.md](DATA_PIPELINE.md) - データパイプライン詳細仕様
> - [PRIVILEGE_SYSTEM.md](PRIVILEGE_SYSTEM.md) - 権限管理システム詳細仕様
> - [MODULE_REFERENCE.md](MODULE_REFERENCE.md) - モジュールAPIリファレンス
> - [SETUP_GUIDE.md](SETUP_GUIDE.md) - セットアップガイド

## 1. システム概要

Work Engagement Dashboardは、従業員のワーク・エンゲージメントデータを可視化・分析するStreamlitベースのWebアプリケーションです。

### 1.1 技術スタック

| 要素 | 技術 |
|------|------|
| フレームワーク | Streamlit |
| データ処理 | pandas, numpy |
| 可視化 | Plotly |
| 認証 | カスタム実装（SHA-256ハッシュ） |
| Excel処理 | openpyxl, msoffcrypto |
| デプロイ | Streamlit Cloud |

### 1.2 ディレクトリ構成

```
WE-Dashboard/
├── app.py                    # メインアプリケーション
├── modules/
│   ├── __init__.py
│   ├── auth.py               # 認証・権限管理
│   ├── charts.py             # グラフ生成
│   ├── components.py         # 再利用可能UIコンポーネント
│   ├── config.py             # 設定・定数
│   ├── data_loader.py        # データ読み込み
│   ├── encryption.py             # 暗号化ユーティリティ
│   ├── filter_helpers.py         # サイドバーフィルターカスケードロジック
│   ├── member_loader.py          # メンバーリスト読み込み（未記入者機能用）
│   ├── privilege_manager.py      # 権限ベースフィルタリング
│   ├── response_file_manager.py  # レスポンスファイル保存/読み込み（パスワード保護Excel・低レベルユーティリティ）
│   ├── response_manager_local.py # 返信管理・ローカル実行用（Mac/Windows → response.xlsx）
│   ├── response_manager_cloud.py # 返信管理・クラウド用（Streamlit Cloud → Google Sheets）
│   ├── signal_processing.py      # シグナルデータ処理
│   ├── statistics.py             # 統計計算
│   ├── utils.py                  # ユーティリティ関数
│   └── windows_config.py         # ローカルスタンドアロン用パスワード設定（git-ignored、AES暗号化）
├── config/
│   ├── privileges_configuration.md  # 権限設定（ソースオブトゥルース）
│   ├── privileges.yaml              # 権限設定（自動生成）
│   └── members.yaml                 # アクティブメンバーリスト（自動生成）
├── tools/
│   ├── generate_privileges_yaml.py  # 権限YAML生成ツール
│   ├── generate_member_yaml.py      # メンバーYAML生成ツール
│   ├── split_by_division.py         # 部門別データ分割ツール（leave メンバーを members.yaml で振り分け）
│   └── encrypt_passwords.py         # パスワード暗号化ツール（windows_config.py 更新用）
├── docs/
├── auth_users.json           # 認証情報（開発用）
├── auth_users.dat            # 認証情報（本番用・エンコード済）
├── group_order_config.json   # グループ順序設定
├── convert_auth.py           # 認証ファイル変換ツール
├── encrypt_data.py           # データ暗号化ツール
├── CLAUDE.md                 # プロジェクトコンテキスト（Claude用）
└── requirements.txt          # 依存パッケージ
```

---

## 2. データ構造

### 2.1 入力Excelファイル構成

入力ファイル（`EngagementMasterSS.xlsx`）は2つのデータシートで構成されます。

#### rating2 シート（唯一のデータソース）

pivot_df（正規化済み評価データ）とsignal_df（シグナルデータ）の両方がこのシートから生成されます。

| カラム | 説明 |
|--------|------|
| year, month | 年月 |
| mail_address | メールアドレス |
| name | 氏名 |
| current_division | 部門（現所属） |
| current_department | 部署（現所属） |
| current_section | 課（現所属） |
| current_team | チーム |
| current_project | プロジェクト |
| grade | 職位 |
| intervention_priority_neg | 介入優先度（ネガティブ） |
| intervention_priority_pos | 介入優先度（ポジティブ） |
| trend_recent | 短期変化（trend_recent） |
| trend_refined | 中期トレンド |
| big_change | 短期変動 |
| stability_6 | 中期安定性 |
| flag_constant_6m | 調査抵抗疑義（V/D/A 固定化パターン判定） |
| strength_short/mid | 強み（短期/中期） |
| weakness_short/mid | 弱み（短期/中期） |
| engagement_rating | エンゲージメント値（生スコア 0-54） |
| vigor_rating | 活力値（生スコア 0-18） |
| dedication_rating | 熱意値（生スコア 0-18） |
| absorption_rating | 没頭値（生スコア 0-18） |

**データ変換:**
- `signal_df`: rating2シートの全カラムをそのまま保持（生スコア）
- `pivot_df`: rating2の評価カラムを正規化（0-10スケール）して生成
  - `engagement_rating / ENGAGEMENT_DIVISOR (5.4)`
  - `vigor_rating / COMPONENT_DIVISOR (1.8)`
  - `dedication_rating / COMPONENT_DIVISOR (1.8)`
  - `absorption_rating / COMPONENT_DIVISOR (1.8)`

#### comment シート（コメントデータ）
| カラム | 説明 |
|--------|------|
| year, month | 年月 |
| mail_address | メールアドレス |
| name | 氏名 |
| division, current_division | 部門 |
| department, current_department | 部署 |
| section, current_section | 課 |
| team, current_team | チーム |
| project, current_project | プロジェクト |
| grade | 職位 |
| concern | 気になった出来事や気づき |
| comment | 共有したいこと |

**重要: コメントデータは自己完結型**

コメントシートには組織情報が含まれているため、メインデータとの結合は不要です：
- メインデータの`mail_address`でフィルタリングしない（コメント投稿者が現在のビューに含まれない場合、コメントが除外される）
- `current_*`列を標準名にマッピングしてからフィルタリング

```python
# 正しいパターン
# section NaN は部署長（課未所属）を意味するため '部門長' で補完
graph_comments['section'] = graph_comments['current_section'].fillna('部門長')
graph_comments['department'] = graph_comments['current_department'].fillna('未設定')
graph_comments['division'] = graph_comments['current_division'].fillna('未設定')
graph_comments = filter_dataframe_by_scope(graph_comments, share_scope)
```

### 2.2 組織構造

#### 組織階層（上位→下位）
```
部門 (Division/division)
  └── 部署 (Department/department)
        └── 課 (Section/section)
```

#### 横断的組織（Cross-organizational Units）
チームとプロジェクトは組織階層とは独立した横断的な単位です。
様々な部門・部署・課のメンバーが所属できます。

```
チーム (team)     ← 複数の課/部署から参加
プロジェクト (project) ← 複数の課/部署から参加
```

**Excel→アプリ間のカラムマッピング:**
| Excel列名 | アプリ内カラム名 | 日本語名 |
|-----------|------------------|----------|
| current_division | division | 部門 |
| current_department | department | 部署 |
| current_section | section | 課 |

---

## 3. モジュール詳細

### 3.1 app.py（メインアプリケーション）

**主要機能:**
- Streamlit UI構成
- サイドバーフィルター管理
- タブ表示（`st.tabs()`によるピル型タブバー）
- セッション状態管理
- 認証ベースの機能制限

**認証状態による表示制御:**

| 機能 | 認証済み | 未認証 |
|------|----------|--------|
| メイン画面 | ダッシュボード（タブ + グラフ） | ウェルカムページ（使い方ガイド） |
| サイドバー | ログイン + 期間 + 指標 + 表示カテゴリ + フィルター + データ | ログインのみ |
| タブ表示 | `st.tabs()` 5タブ（時系列/カテゴリ比較/評価/分布/個人） | なし |

**データフロー:**
```
1. ファイルアップロード/デフォルトファイル読込
2. load_data() でデータ取得
3. 未認証の場合 → ウェルカムページ表示（ダッシュボードなし）
4. 認証済みの場合 → サイドバーフィルター表示 + タブ表示
5. filter_helpers.py の render_unified_sidebar_filters() でフィルター適用
6. 各タブ（st.tabs）でグラフ/テーブル表示
```

**フィルターリセット機構:**
ログイン/ログアウト時に以下のフラグがセットされ、フィルターがリセットされます：
- `reset_period_filter`: 期間スライダーをリセット
- `reset_local_filters`: ローカルフィルター（部署/課/グルーピング）をリセット

### 3.2 modules/auth.py（認証モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `hash_password(password)` | SHA-256でパスワードをハッシュ化 |
| `load_auth_users()` | 認証ファイルからユーザー情報を読込 |
| `verify_login(username, password)` | ログイン認証 |
| `login(username, privilege)` | ログイン処理 + フィルターリセット |
| `logout()` | ログアウト処理 + フィルターリセット |
| `is_authenticated()` | 認証状態確認 |
| `has_privilege(required_privileges)` | 権限チェック |
| `filter_by_privilege(data, privilege)` | 権限に基づくデータフィルタリング |
| `reset_filters()` | フィルター状態をリセット |

**権限ベースアクセス制御:**
`config.py`の`PRIVILEGE_GROUP_ACCESS`で定義された権限に基づき、ユーザーがアクセスできる組織範囲を制限します。

```python
# 例: PRIVILEGE_GROUP_ACCESS
{
    'admin': None,                   # 全データアクセス可
    'sd': ['システム開発部', '機電設計部'],  # 特定部署のみ
    'sw': ['ソフトウェア開発課'],    # 特定課のみ
}
```

### 3.3 modules/config.py（設定モジュール）

**主要設定:**

| 定数 | 説明 |
|------|------|
| `ORG_COLUMNS` | 組織階層カラムマッピング |
| `ORG_FILTER_COLUMNS` | 権限フィルタリング対象カラム |
| `METRIC_LABELS` | 指標の日本語ラベル |
| `SIGNAL_LABELS` | シグナル項目の日本語ラベル |
| `FLAG_CONSTANT_LABELS` | `flag_constant_6m` 値の日本語表示名マッピング |
| `FLAG_CONSTANT_PRIORITY_POINTS` | `flag_constant_6m` 値の介入優先度加算ポイント |
| `RATING_AXIS_MAX` | Y軸最大値（10.3） |
| `POSITIVE_TRENDS` / `NEGATIVE_TRENDS` | トレンド分類 |
| `PRIVILEGE_GROUP_ACCESS` | 権限別アクセス範囲 |
| `ENGAGEMENT_DIVISOR` / `COMPONENT_DIVISOR` | 評価値計算の除数 |

### 3.4 modules/data_loader.py（データ読込モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `get_excel_password()` | 入力Excelパスワード取得（`windows_config.py` 優先、次いで `st.secrets`） |
| `decrypt_excel_if_needed(file_obj)` | Excelの復号（暗号化されていない場合はそのまま返す。暗号化されている場合はパスワードで復号） |
| `load_data(uploaded_file)` | データ読込・前処理（キャッシュ対応） |

**パスワード取得の優先順位:**
1. `modules/windows_config.py` が存在する場合 → `EXCEL_PASSWORD`（AES復号済み、ローカルスタンドアロン）
2. 存在しない場合 → `st.secrets["EXCEL_PASSWORD"]`（Streamlit Cloud）

`windows_config.py` は git-ignored であり、ローカル環境にのみ存在する。Streamlit Cloud にはデプロイされず、`st.secrets` にフォールバックする。パスワードは AES（Fernet）暗号化済みで保存され、平文はファイルに書かれない。

**データ変換処理:**
1. rating2シートを読み込み、signal_dfを構築（組織カラムマッピング、年月カラム生成）
2. signal_dfから評価カラムを選択・正規化してpivot_dfを導出
3. 欠損値を「未設定」で補完
4. `flag_constant_6m` 列を追加（Excel に列がない場合は None で補完）

### 3.5 modules/charts.py（グラフ生成モジュール）

**主要関数:**

| 関数 | 用途 |
|------|------|
| `create_time_series_chart()` | 時系列折れ線グラフ |
| `create_recent_group_comparison_chart()` | グループ別棒グラフ |
| `create_box_plot()` | ボックスプロット |
| `create_group_rating_distribution()` | 評価バンド積み上げ棒グラフ |
| `create_radar_chart()` | レーダーチャート |
| `create_individual_trend()` | 個人別推移グラフ |

**個人別（`color_by='name'`）のホバー順序:**

`hovermode='x unified'` では統合ホバーリストのアイテム順がトレース順に対応する。`color_by='name'` の場合、トレース順を最新データ時点の値の降順でソートすることで、ホバーウィンドウのリストが最新時点の折れ線の上下順と一致するようにしている。他のグルーピング（課別・部署別等）では `get_category_order_with_reference` による従来の順序（グループ順序設定ベース）を維持する。

### 3.6 modules/signal_processing.py（シグナル処理モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `apply_signal_rating_calculations()` | シグナル値の計算適用 |
| `derive_intervention_priority()` | 介入優先度の表示値を導出（閾値引き算のみ） |
| `get_signal_data()` | フィルタリング済みシグナルデータ取得 |
| `sort_signals_by_trend_and_priority()` | トレンド・優先度でソート |
| `render_signal_table()` | シグナルテーブル表示 |
| `format_individual_signal_data()` | 個人シグナルの整形 |

**介入優先度（intervention_priority）の計算:**

1. **`intervention_priority_neg` には flag ボーナス込み**: Admin GAS が rating2 シートに書き込む時点で `flag_constant_6m` ボーナスを含めた値が生データとなる。Dashboard 側では flag ボーナスを加算しない。
2. **側（neg/pos）の判定は大小比較**: `_priority_is_neg = neg >= pos`。大きい方が勝ち、同点（neg == pos、0 == 0 を含む）は neg を優先。これによりエンゲージメントグラフと色（赤=neg / 緑=pos）の側が一致する（pos が neg を明確に上回る人を赤に倒さない）。
3. **足切りはアクション対象候補の抽出側で実施**: シグナルテーブルに載るのは `neg > threshold` または `pos > threshold` の行（`get_signal_data`）。勝った側の値は必ず閾値超えなので表示値は正値になる。個人レポートでは閾値以下も呼ばれるため、表示値が ≤ 0 のときフォーマット側で ０ にクランプされる。
4. **表示値 = (勝った側) − threshold**: `flag_constant_6m` はラベル表示専用で計算には影響しない。

**シグナルソート順:**
1. 優先度タイプ（neg first）→ 優先度値 → トレンドグループ → 課

### 3.7 modules/components.py（UIコンポーネントモジュール）

重複するUIパターンを集約した再利用可能コンポーネント集。

**主要関数:**

| 関数 | 説明 |
|------|------|
| `get_management_override()` | チームオーバーライドからマネジメント設定を抽出 |
| `prepare_comment_data()` | コメントデータの組織列マッピングとスコープフィルタリング |
| `apply_grouping_filters()` | グルーピング別フィルター適用（スコープ、職位、エイリアス、オーバーライド） |
| `render_action_candidates()` | アクション対象候補セクション表示 |
| `render_concern_section()` | 気になった出来事や気づきセクション表示 |
| `render_comment_section()` | 共有したいことセクション表示（匿名化対応） |
| `render_non_respondents()` | 未記入者セクション表示（管理職のみ、サイドバーフィルター対応） |
| `render_comments_and_signals()` | 上記4セクションの一括表示 |

**`render_non_respondents()` のフィルタリング:**

`member_df` に対して2段階のフィルタリングを適用する：
1. **権限スコープ**: `get_data_scope_for_tab` で権限に応じた組織範囲に制限
2. **サイドバーフィルター**: `selected_filters` の `division` / `department` / `section` / `individual` を適用（`individual` は `member_name` 列で照合）

`team` / `project` フィルターは `member_df` に該当列が存在しないためスキップする。

**設計思想:**
- app.pyの1763行から1249行へ削減（-29%）
- 各タブで重複していたコメント/シグナル表示ロジックを共通化
- グルーピングフィルター処理を1関数に集約

**apply_grouping_filters() のレイヤー構成:**

グルーピング選択に応じて複数のフィルター処理を順次適用します。

| レイヤー | 適用条件 | 処理内容 | 状態 |
|----------|----------|----------|------|
| Layer 1 | - | グルーピングスコープ適用 | **無効化** |
| Layer 2 | `grouping == 'grade'` | 職位フィルター適用 | 有効 |
| Layer 3 | `grouping == 'section'` | セクションエイリアス適用 | 有効 |
| Layer 4 | `grouping == 'section'` | チームセクションオーバーライド適用 | 有効 |

**Layer 1 無効化の理由:**

`grouping_scope`による制限は、権限設定に明示的に記載されていない部署（例: 品質保証部）を
意図せずフィルタリングしてしまう問題がありました。`data_scope`がタブレベルの表示制御を
既に行っており、ローカルフィルター（部署/課選択）がユーザー選択を制御するため、
このレイヤーは冗長であり無効化されています。

### 3.8 modules/member_loader.py（メンバーリスト読み込みモジュール）

`config/members.yaml` からアクティブメンバーリストを読み込み、未記入者セクションに提供する。`members.yaml` が存在しない場合は空 DataFrame を返し、未記入者セクションをサイレントにスキップする。

**データソース**: `config/members.yaml`（`tools/generate_member_yaml.py` で `Member.xlsx` から生成）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `load_members()` | `members.yaml` からアクティブメンバーを読み込む（`@st.cache_data`） |

**YAML生成ワークフロー:**
```
Member.xlsx → tools/generate_member_yaml.py → config/members.yaml → member_loader.py
```

---

### 3.9 modules/response_file_manager.py（レスポンスファイル管理モジュール）

パスワード保護された応答 Excel ファイルの保存・読み込みを提供する。ローカルスタンドアロン（Mac/Windows）と Streamlit Cloud の両方で動作する。

**主要関数:**

| 関数 | 説明 |
|------|------|
| `get_response_password()` | レスポンスファイル用パスワード取得 |
| `save_responses(df, path)` | DataFrame をパスワード保護Excelとして保存 |
| `load_responses(path)` | パスワード保護Excelを読み込み DataFrame として返す |

**パスワード取得の優先順位:**（`get_excel_password()` と同じロジック）
1. `modules/windows_config.py` が存在する場合 → `RESPONSE_PASSWORD`（AES復号済み）
2. 存在しない場合 → `st.secrets["RESPONSE_PASSWORD"]`

**ファイル確認方法:** パスワードを知っていれば Excel / LibreOffice で直接開くことができる。専用のエクスポートツールは不要。

### 3.10 返信管理モジュール（環境自動判別）

`共有したいこと`セクションのコメントへの返信機能を提供します。実行環境（OS）に応じてバックエンドを自動選択します。

**自動判別ロジック（`components.py` / `app.py`）:**

```python
import sys
if sys.platform in ("darwin", "win32"):
    from modules.response_manager_local import ...   # Mac/Windows → Excel
else:
    from modules.response_manager_cloud import ...   # Linux(Streamlit Cloud) → Google Sheets
```

| 実行環境 | `sys.platform` | バックエンド | 保存先 |
|---|---|---|---|
| ローカル Mac | `darwin` | `response_manager_local.py` | `response.xlsx`（プロジェクトルート） |
| ローカル Windows | `win32` | `response_manager_local.py` | `response.xlsx`（プロジェクトルート） |
| Streamlit Cloud | `linux` | `response_manager_cloud.py` | Google Sheets |

**両モジュール共通の公開 API:**

| 関数 | 説明 |
|------|------|
| `load_responses()` | 返信一覧読込（session_stateキャッシュ） |
| `post_response()` | 返信投稿（書込→キャッシュ無効化） |
| `get_responses_for_comment()` | 特定コメントの返信取得 |
| `make_comment_key()` | MD5ハッシュによるウィジェットキー生成 |

**response_manager_local.py（ローカル用）:**
- 保存先: `<プロジェクトルート>/response.xlsx`（`Path(__file__).parent.parent / "response.xlsx"`）
- 暗号化: `EXCEL_PASSWORD` が secrets にある場合は `msoffcrypto` でパスワード保護
- 初回起動時にファイルが存在しなければ自動作成

**response_manager_cloud.py（クラウド用）:**
- バックエンド: Google Sheets API（`gspread`）
- 必要な設定: `gcp_service_account`（サービスアカウント情報）、`RESPONSE_SHEET_ID`（スプレッドシートID）

### 3.11 modules/utils.py（ユーティリティモジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `load_group_orders()` | グループ順序設定読込 |
| `sort_with_config()` | 設定に基づくソート |
| `sort_names_by_grade()` | 職位順で氏名をソート |
| `get_options()` | フィルター選択肢取得 |
| `render_department_and_group_controls()` | 部署/課/グルーピングコントロール表示 |

### 3.12 modules/statistics.py（統計モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `calculate_group_statistics()` | グループ別統計計算（平均/傾き/標準偏差） |
| `format_statistics_for_display()` | 表示用フォーマット |

**個人別グルーピング時のトレンド列追加:**

`group_col == 'name'`の場合、signal_dfから短期変化・中期トレンドを結合：

```python
stats_df = calculate_group_statistics(
    df, selected_metric, group_col,
    signal_df=tab_signal_df if group_col == 'name' else None,
    end_dt=end_dt if group_col == 'name' else None
)
```

結果テーブル: `| 個人 | 短期変化 | 中期トレンド | 平均 | 傾向の傾き | 標準偏差 |`

### 3.13 modules/privilege_manager.py（権限管理モジュール）

`config/privileges.yaml`を読み込み、権限ベースのデータフィルタリングを提供します。

**主要クラス・関数:**

| 名前 | 説明 |
|------|------|
| `PrivilegeManager` | シングルトンパターンの権限管理クラス |
| `get_data_scope_for_tab()` | タブ別データスコープ取得 |
| `get_grouping_scope()` | グルーピング別データスコープ取得 |
| `get_grade_filter_for_grouping()` | 職位フィルター値取得 |
| `should_anonymize_section()` | セクション匿名化判定 |
| `get_section_aliases()` | セクションエイリアス取得 |
| `filter_dataframe_by_scope()` | スコープによるDataFrameフィルタリング |
| `filter_dataframe_by_grade()` | 職位によるDataFrameフィルタリング |
| `get_team_section_overrides()` | チームセクションオーバーライド取得 |

**スコープフィルタリングの注意点:**

`get_section_scope()`は部署・部門名を返す場合があります（課名とは限らない）：
```python
# 誤: sectionカラムのみでフィルタリング
df = df[df['section'].isin(share_scope)]

# 正: 全組織カラムをチェック
df = filter_dataframe_by_scope(df, share_scope)
```

`filter_dataframe_by_scope()`は`division`、`department`、`section`全てをチェックします。

**チームセクションオーバーライド（マネジメント機能）:**

特定の`team`値を持つメンバーを仮想セクションとして表示：
- **適用タイミング**: `grouping == 'section'`（課別）の時のみ
- **設定**: `privileges.yaml`の`team_section_overrides`
- **ローカルフィルター**: 課選択で「マネジメント」を選択可能

```python
# 課別グルーピング時に適用（apply_grouping_filters内）
if grouping_choice == 'section':
    team_overrides = privilege_mgr.get_team_section_overrides(current_privilege, tab_name)
    if team_overrides:
        df = apply_team_section_overrides(df, team_overrides)
```

オーバーライド構造:
```yaml
team_section_overrides:
  マネジメント:
    match_team: Management
    display_section: マネジメント
    visible_to: [all]  # 全ユーザーに表示
    visible_in_tabs: [時系列, カテゴリ比較, 評価, 分布]
    exclude_sections: [未設定]  # 注: 現在は無効化（下記参照）
```

**注意: exclude_sectionsは無効化**

`exclude_sections`は以下の理由で無効化されています：
- 一部の部署（例: 品質保証部）はサブセクションを持たず、全メンバーが`section='未設定'`
- 除外すると部署全体が非表示になる問題が発生

**権限設定の階層:**
```
config/privileges_configuration.md  ← ソースオブトゥルース（Markdown表形式）
        ↓ (generate_privileges_yaml.py)
config/privileges.yaml            ← 生成された設定ファイル
        ↓ (privilege_manager.py)
アプリケーション                   ← 実行時フィルタリング
```

**権限クラス:**
| クラス | 対象ユーザー | 特徴 |
|--------|--------------|------|
| `admin` | 管理者 | 全データアクセス可 |
| `anonymous` | 未認証 | データアクセス不可 |
| `department_head` | sd, me, dev | 部署レベルアクセス |
| `section_manager` | sw, pd, me1-3等 | 課レベルアクセス |
| `member` | soft, prod等 | 制限付き、職位フィルタあり |
| `member_no_grade_filter` | develop1-2 | 制限付き、職位フィルタなし |

---

## 4. セッション状態管理

### 4.1 認証関連
| キー | 説明 |
|------|------|
| `authenticated` | 認証状態（bool） |
| `current_user` | ログインユーザー名 |
| `current_privilege` | ユーザー権限 |

### 4.2 フィルター関連（統一フィルターシステム）
| キー | 説明 |
|------|------|
| `filter_period` | 期間スライダー値 |
| `unified_division` | 部門セレクトボックス |
| `unified_grade` | 職位セレクトボックス |
| `unified_department` | 部署セレクトボックス |
| `unified_section` | 課セレクトボックス |
| `unified_team` | チームセレクトボックス |
| `unified_project` | プロジェクトセレクトボックス |
| `unified_individual` | 個人セレクトボックス（サイドバー） |
| `unified_grouping` | 表示カテゴリ（グルーピング）セレクトボックス |
| `reset_period_filter` | 期間リセットフラグ |
| `reset_local_filters` | ローカルフィルターリセットフラグ |
| `individual_selector` | 個人タブのローカルセレクトボックス値 |

### 4.3 アクション対象候補ナビゲーション関連

アクション対象候補テーブルの行選択から個人タブへ遷移する機能で使用するセッションステートキー。

| キー | 説明 |
|------|------|
| `_last_{key_prefix}_selection` | テーブルごとの前回選択氏名（`ts`・`gc_no_group`・`gc_grouped` 等）。テーブル間の干渉防止に使用 |
| `_nav_individual` | 個人タブへのナビゲーション対象氏名。`render_action_candidates` がセットし、個人タブが消費（del）する |
| `_clear_action_selection` | 個人タブが `_nav_individual` を消費した後にセットするフラグ。次の rerun でシグナルテーブルの選択をリセットする |
| `_signal_tables_version` | シグナルテーブルウィジェットのバージョンカウンター。インクリメントするとキーが変わりウィジェットが再生成され選択状態がリセットされる |

**制約**: `st.tabs()` のタブ切り替えは CSS による show/hide であり rerun を発生させないため、タブを切り替えた瞬間に選択をリセットすることは Streamlit の仕組み上不可能。選択のリセットは次のユーザー操作（いずれかのウィジェット操作）で発生する。

**カスケードリセット:**
親フィルター変更時、子フィルターが自動リセットされます。
```
部門 → 部署 → 課 → チーム → プロジェクト → 職位 → 個人
```

---

## 5. 今後の拡張ポイント

### 5.1 アーキテクチャ改善

| 項目 | 現状 | 改善案 |
|------|------|--------|
| **コードの重複** | ✅ 解決済み - components.pyに共通化 | - |
| **フィルター管理** | セッション状態でのフラグ管理が複雑 | 状態管理クラスの導入 |
| **データキャッシュ** | `@st.cache_data`のみ | フィルター結果もキャッシュ検討 |

### 5.2 機能拡張候補

| 機能 | 説明 |
|------|------|
| **エクスポート機能** | グラフ/データのCSV/PDF出力 |
| **アラート設定** | 閾値ベースの通知機能 |
| **比較機能** | 期間間/グループ間の比較分析 |
| **ダッシュボードカスタマイズ** | ユーザー別のレイアウト保存 |

### 5.3 コード品質改善

| 項目 | 詳細 |
|------|------|
| **型ヒント** | 関数シグネチャに型アノテーション追加 |
| **テスト** | pytest によるユニットテスト整備 |
| **ドキュメント** | docstringの充実化 |
| **エラーハンドリング** | より詳細なエラーメッセージ |

### 5.4 リファクタリング対象

1. **app.py**: 1249行 → 必要に応じてタブ別モジュール分割を検討
2. **charts.py**: グラフ設定の共通化
3. ~~**コメント表示ロジック**: 4箇所で重複 → 共通関数化~~ ✅ components.pyに共通化済み

---

## 6. セキュリティ考慮事項

| 項目 | 実装状況 |
|------|----------|
| パスワードハッシュ | SHA-256 |
| Excelパスワード保護 | msoffcryptoで復号（入力ファイル・レスポンスファイル） |
| 権限ベースアクセス制御 | PRIVILEGE_GROUP_ACCESSで実装 |
| 認証情報の保護 | .dat形式でBase64+pickle |
| シークレット管理（Cloud） | Streamlit Secrets を使用 |
| シークレット管理（ローカル） | `modules/windows_config.py`（git-ignored、AES Fernet 暗号化 + バイトコード保護） |
| 未認証ユーザー制限 | 個人情報関連機能を非表示 |

### 6.0 ローカルスタンドアロン動作時のパスワード管理

`streamlit run app.py` をローカル PC（Mac/Windows）で実行する場合、`.streamlit/secrets.toml` はファイルシステム上に平文で存在するため、閲覧可能になる。これを避けるため、ローカル環境では `modules/windows_config.py` に **AES（Fernet）暗号化済みパスワード** を保存する方式を採用している。

```
windows_config.py（git-ignored）
  ├─ _KEY                   — Fernet AES キー（バイナリに埋め込み）
  ├─ _EXCEL_PASSWORD_ENC    — 暗号化済み入力Excelパスワード
  ├─ _RESPONSE_PASSWORD_ENC — 暗号化済みレスポンスファイルパスワード
  ├─ EXCEL_PASSWORD         — 起動時に復号されたパスワード（メモリ上のみ）
  └─ RESPONSE_PASSWORD      — 起動時に復号されたパスワード（メモリ上のみ）
```

平文パスワードはファイルに書かれない。PyInstaller でビルドされた `.exe` に埋め込まれると、暗号化キーと暗号文の両方をバイトコードから抽出しなければ復号できない。

**パスワード更新手順:**
1. `python tools/encrypt_passwords.py` を実行（入力は非表示）
2. 出力された `_EXCEL_PASSWORD_ENC` / `_RESPONSE_PASSWORD_ENC` を `windows_config.py` に貼り付け
3. `windows_config.py` は git-ignored のためリポジトリにはコミットされない

**優先順位ロジック（`get_excel_password()` / `get_response_password()`）:**
```python
try:
    from modules import windows_config  # ローカル環境のみ存在（暗号化済みパスワードを復号）
    return windows_config.EXCEL_PASSWORD
except ImportError:
    return st.secrets.get("EXCEL_PASSWORD")  # Streamlit Cloud
```

`windows_config.py` が存在しない Streamlit Cloud では自動的に `st.secrets` にフォールバックする。

### 6.1 未認証ユーザー向け機能制限

未認証（ログインしていない）ユーザーには**ダッシュボードが表示されません**。
代わりにウェルカムページ（使い方ガイド）が表示されます。

**実装方法:**
```python
if not is_authenticated():
    # ウェルカムページ表示（サイドバーはログインのみ）
    st.markdown("#### 使い方 ...")
else:
    # 認証済み — フル・ダッシュボード表示
    current_privilege = get_current_privilege()
    tab_labels = privilege_mgr.get_allowed_tabs(current_privilege)
    base_grouping_options = privilege_mgr.get_allowed_groupings(current_privilege)
    # ... sidebar filters, st.tabs(), charts ...
```

**注意点:**
- SHA-256は基本的なハッシュであり、本番運用ではbcryptなどの検討を推奨
- 認証ファイルはGitにコミットしないこと

---

## 7. 依存関係

```
streamlit>=1.35.0
pandas>=2.0.0
plotly>=5.18.0
openpyxl>=3.1.0
numpy>=1.24.0
statsmodels>=0.14.0
msoffcrypto-tool>=5.0.0
cryptography>=41.0.0
pyyaml>=6.0.0       # 権限設定YAML読み込み用
gspread              # Google Sheets API（返信機能）
google-auth>=2.0.0   # Google認証
```

---

## 8. 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2025-01-21 | 初版作成 |
| 2025-01-21 | グルーピングフィルターの修正（フィルターリセット機構追加） |
| 2025-01-21 | 組織カラム名のリファクタリング（section→division, group→section） |
| 2025-01-21 | 未認証ユーザー向け機能制限（個人タブ、職位/個人グルーピング、アクション対象候補、共有したいこと非表示） |
| 2025-01-31 | privilege_manager.py追加（YAML設定ベースの権限管理） |
| 2025-01-31 | グローバルフィルター階層同期機能追加（sync_filter_selection） |
| 2025-01-31 | signal_df, comment_dfへのグローバルフィルター適用修正 |
| 2025-01-31 | 組織フィルターを折りたたみ可能に変更 |
| 2025-01-31 | 職位フィルター（非管理職）機能追加 |
| 2025-01-31 | コメント匿名化機能追加（共有したいこと） |
| 2025-01-31 | コメント表示を年月降順（最新が上）に変更 |
| 2025-01-31 | 匿名化時のコメントを年月でグループ化 |
| 2025-02 | チームセクションオーバーライド機能追加（マネジメント） |
| 2025-02 | 主要な指標にトレンド列追加（個人別グルーピング時） |
| 2025-02 | コメントデータの組織フィルタリング修正 |
| 2025-02 | modules/components.py追加（重複コード削減、1763行→1249行） |
| 2025-02-06 | チームオーバーライドの適用条件を修正（name→section grouping） |
| 2025-02-06 | signal_dfのマネジメントフィルタリングを名前ベースに修正 |
| 2025-02-06 | apply_grouping_filtersのLayer 1（grouping_scope）を無効化 |
| 2025-02-06 | exclude_sectionsを無効化（サブセクションなし部署対応） |
| 2025-02-06 | TAB_CONFIG定数追加（config.py） - タブ名のハードコード削減 |
| 2025-02-06 | format_measured_data()追加（statistics.py） - 計測値表示の共通化 |
| 2025-02-06 | filter_signal_by_selection()追加（components.py） - signal_dfフィルタリング共通化 |
| 2025-02-06 | app.pyを1279行→1172行に削減（-8.4%） |
| 2026-02-09 | 未認証ユーザーにウェルカムページ表示（ダッシュボード非表示化） |
| 2026-02-09 | st.radio→st.tabs()への移行（ピル型タブバー） |
| 2026-02-09 | サイドバー再構成（表示カテゴリ→フィルター設定expander→データexpander） |
| 2026-02-09 | グループ（絞り込み軸）メタセレクタを廃止、課/チーム/プロジェクト個別ドロップダウンに変更 |
| 2026-02-09 | filter_helpers.py追加（サイドバーフィルターカスケードロジック） |
| 2026-02-10 | ratingシート依存を廃止、rating2シートからpivot_dfを導出（データソース統一） |
| 2026-03 | response_manager.py追加（共有したいことへの返信機能、Google Sheets連携） |
| 2026-03 | change_tag→big_change, stability→stability_6 にフィールド名統一 |
| 2026-03-08 | 技術ドキュメント再構成（INDEX/SETUP_GUIDE/DATA_PIPELINE/PRIVILEGE_SYSTEM/MODULE_REFERENCE追加） |
| 2026-03-31 | `flag_constant_6m`（調査抵抗疑義）をシグナル表示に追加 |
| 2026-03-31 | `derive_intervention_priority()` を修正: `intervention_priority_neg` には Admin GAS で flag ボーナス込みの生データが格納されるため、Dashboard での flag 加算を廃止。表示値 = neg（または pos）− threshold のみ |
| 2026-03-31 | `get_signal_data()` の足切りフィルターを neg/pos 直接比較に修正（flag_constant_6m はラベル表示専用） |
| 2026-03-31 | signal_processing.py リファクタリング: プライベートヘルパー抽出（`_fmt_flag_constant`, `_fmt_priority_table`, `_fmt_priority_individual`）、`_get_flag_points` / `FLAG_CONSTANT_PRIORITY_POINTS` を廃止、`get_signal_column_config()` を `render_signal_table()` にインライン化 |
| 2026-04-04 | `render_non_respondents()` に `selected_filters` 引数を追加し、サイドバーフィルター設定（部門・部署・課・個人）を未記入者セクションに適用 |
| 2026-04-04 | `render_comments_and_signals()` に `member_df` / `selected_filters` 引数を追加し、`render_non_respondents()` に転送 |
| 2026-04-04 | `create_time_series_chart()`: `color_by='name'`（個人別）のトレース順を最新データ時点の値の降順でソート。統合ホバーリストが折れ線の上下順と一致 |
| 2026-04-04 | `member_loader.py` / `config/members.yaml` / `tools/generate_member_yaml.py` を追加（未記入者機能のメンバーリスト管理） |
| 2026-04-05 | サイドバーフィルター順序変更: 職位（grade）を プロジェクト の後・個人 の前に移動（部門→部署→課→チーム→プロジェクト→職位→個人）|
| 2026-04-05 | ローカルスタンドアロン用パスワード管理を追加: `modules/windows_config.py`（git-ignored）に `EXCEL_PASSWORD` / `RESPONSE_PASSWORD` をハードコード。`get_excel_password()` が `windows_config.py` 優先で取得し、存在しない場合は `st.secrets` にフォールバック |
| 2026-04-05 | `modules/response_file_manager.py` を追加: `msoffcrypto` を使用したパスワード保護レスポンス Excel の保存・読み込み |
| 2026-04-05 | `decrypt_excel_if_needed()` を簡略化: 暗号化有無を `is_encrypted()` で判定し、非暗号化ファイルはそのまま返す。暗号化ファイルの場合は設定済みパスワードで復号（パスワード未設定時は ValueError） |
| 2026-04-05 | `modules/windows_config.py` のパスワード管理を強化: 平文ハードコードから AES（Fernet）暗号化方式に変更。`tools/encrypt_passwords.py` を追加（開発者がパスワードを更新する際に使用）。配布 `.exe` ではバイトコード＋暗号化の二重保護となる |
| 2026-04-05 | `calculate_group_statistics()` に `E_delta_1`（先月差分）・`E_slope_3m`（3ヶ月傾き）列を追加。`signal_df` の最新波データから取得し `ENGAGEMENT_DIVISOR`（5.4）で正規化。グループ別集計時のみ（`group_col != 'name'`）に表示 |
| 2026-04-05 | `calculate_group_statistics()` に `人数`（ユニーク氏名数）列を追加。`group_col == 'name'`（個人別）の場合は追加しない |
| 2026-04-05 | `format_statistics_for_display()` に `先月からの差分`・`直近３ヶ月の傾き` 列のフォーマット（符号付き小数）を追加 |
| 2026-04-05 | 評価タブに計測値セクション追加: グルーピングに応じた `format_evaluation_measured_data()` / `format_radar_measured_data()` によるバンド集計・コンポーネント平均テーブルを `st.expander` で表示 |
| 2026-04-05 | `format_evaluation_measured_data()` / `format_radar_measured_data()` を `statistics.py` に追加 |
| 2026-04-05 | レーダーチャート軸設定変更: `theta=['熱意','活力','没頭']`、`rotation=330, direction='counterclockwise'` で活力を 12 時位置に配置 |
| 2026-04-05 | `config/members.yaml` / `tools/generate_member_yaml.py` / `modules/member_loader.py` に `team`, `project`, `grade` 列を追加。未記入者テーブルで動的表示（列が存在する場合のみ追加） |
| 2026-04-05 | 個人タブにプロフィールセクション追加: `st.expander` 内で部門・部署・課・チーム・プロジェクト・職位を表示（`tab_signal_df` から取得） |
| 2026-04-05 | `prepare_comment_data()` の section 欠損補完を `'未設定'` → `'部門長'` に変更。課未所属メンバー（部署長）のコメントが「部門長」として表示される |
| 2026-04-05 | `render_comments_and_signals()` に section_manager 向け部門長コメント表示を追加: `get_privilege_base_class()` で base class を検出し、`計測値` スコープで '部門長' 行を取得して結合 |
| 2026-04-05 | `PrivilegeManager.get_privilege_base_class(privilege)` メソッドを追加: ユーザー固有権限から基本クラス名を返す |
| 2026-04-12 | 転属・退職メンバー表示トグル実装（`app.py` / `modules/member_loader.py`）: `@st.cache_data` の `_` プレフィックス引数問題修正、チェックボックス描画を `app.py` に移動、leave メンバーの org 情報を `members.yaml` から復元。詳細: `docs/LEAVE_MEMBER_TOGGLE.md` |
| 2026-04-12 | `tools/split_by_division.py` を修正: パスワードを `.streamlit/secrets.toml` から読み込む、退職メンバー（`leave == "leave"`）を `members.yaml` の `division` に基づいて部門別ファイルに含める（Admin GAS が `current_division` をクリアするため、`current_division` フィールドでは判定不可） |
| 2026-05-08 | シグナル列追加・改名: `trend_base`（中期傾向）を `trend_recent` と `trend_refined` の間に追加。`trend_refined` の表示名を「中期傾向」→「総合傾向」に変更。`SIGNAL_TABLE_COLUMNS` / `INDIVIDUAL_SIGNAL_COLUMNS` / `SIGNAL_LABELS` / `calculate_group_statistics` のトレンド列マージ処理をすべて更新 |
| 2026-05-08 | アクション対象候補テーブルからの個人タブナビゲーション機能を実装。`render_signal_table` に `on_select="rerun"` / `selection_mode="single-row"` / `key` を追加し選択氏名を返すように変更。`render_action_candidates` に `key_prefix` を追加（複数タブでの ID 衝突防止）。ナビゲーション状態管理に `_nav_individual`・`_last_{key_prefix}_selection`・`_clear_action_selection`・`_signal_tables_version` の 4 セッションステートキーを導入。Streamlit 最低バージョンを 1.35.0 に引き上げ |
| 2026-05-09 | 返信管理のバックエンドを環境自動判別方式に変更。`response_manager.py` を `response_manager_cloud.py` に改名し、`response_manager_local.py`（Mac/Windows・Excel保存）を新規追加。`sys.platform` で `darwin`/`win32` の場合はローカルExcel（`response.xlsx`）、`linux`（Streamlit Cloud）の場合は Google Sheets を使用。追加設定・secrets.toml の変更不要で自動切替。`WE-Dashboard-Windows` も同構成に統一（`response_manager_windows.py` 廃止） |
| 2026-06-02 | 期間スライダー初回リセットバグ修正: ログイン時に `reset_period_filter=True` が設定された後、初回認証済みリランで `filter_period` がセッション状態にない場合に `if` ブランチが実行されフラグが消費されないことで、最初のスライダー操作後にリセットが発生する問題を修正。`if not in state` と `elif reset_period_filter` を単一条件に統合しフラグを常時消費するよう変更 |
| 2026-06-02 | シグナル表示列更新: `mid_variability` の表示名を「中期変動性」→「変動パターン」に変更（`SIGNAL_LABELS`）。`stability_6`（中期安定性）を `SIGNAL_TABLE_COLUMNS` / `INDIVIDUAL_SIGNAL_COLUMNS` / `SIGNAL_LABELS` に追加し、アクション対象候補・シグナルテーブルおよび個人タブのシグナル表示に復活 |
| 2026-06-02 | `LEVEL_LABELS` 更新: Critical→「要注意」、Low→「低調」、Moderate→「標準」、High→「良好」、Thriving→「充実」。以前の婉曲表現（低調/やや低調/非常に良好）から直接的な表現に変更 |
| 2026-06-02 | アクション対象候補テーブル列幅設定: `render_signal_table` の column_config に `短期変動`（width=90）・`中期安定性`（width="small"）・`調査抵抗疑義`（width=150）を追加。ポップオーバーを 3 列構成に変更し「変動パターン・中期安定性について」を追加 |
| 2026-06-02 | 個人タブレイアウト再構成: 表示順序を「プロフィール（expander）→ 計測値（expander）→ シグナル → コメント（タイトル）→ 気になった出来事や気づき → 幹部職に伝えたいこと」に変更。プロフィールを `if individual_mail:` ブロック外に移動。シグナル表示に `height=510` を設定し全 13 行をスクロールなしで表示。コメントセクション前に `st.subheader("コメント")` を追加（他タブと統一） |
| 2026-06-06 | `derive_intervention_priority()` の側（neg/pos）判定を「neg 優先（`neg_qualifies | (~pos_qualifies)`）」から「大小比較（`neg >= pos`、同点は neg 優先）」に変更。pos が neg を明確に上回る人（例: neg=3, pos=6）がネガティブ側（赤）に倒れず、エンゲージメントグラフと色の側が一致するように修正。足切りは `get_signal_data` 側で実施するため勝った側の値はテーブル上で常に正値 |
| 2026-06-07 | アクション対象候補テーブル: `氏名` 列に明示幅 `width=120` を設定（最長の日本語氏名＋1文字分の余裕、自動幅での末尾切れ対策）。ポップオーバー「変動パターン・中期安定性について」に「分位点判定は個人の過去6ヶ月窓を基準とするため有効回答が揃って約11ヶ月分までは『判定保留』」の注記を追加 |

---

## 9. 実装パターンとよくある問題

### 9.1 クイックリファレンス

| トピック | 要点 |
|----------|------|
| コメントデータ | 独自の組織列を持つ - メインデータと結合不要 |
| 権限フィルタリング | セクションスコープは部署名を含む場合あり、`filter_dataframe_by_scope()`を使用 |
| チームオーバーライド | `grouping == 'section'`（課別）の時のみ適用 |
| 統計トレンド列 | 個人別グルーピング時にsignal_dfから結合 |
| signal_dfフィルタリング | signal_dfのフィルタリングは名前ベースを推奨 |

### 9.2 共有したいことセクション

コメントデータは自己完結型のため、以下のパターンを使用：

```python
# 全組織列をマッピングしてからフィルタリング
# section NaN は部署長（課未所属）→ '部門長' で補完
graph_comments['section'] = graph_comments['current_section'].fillna('部門長')
graph_comments['department'] = graph_comments['current_department'].fillna('未設定')
graph_comments['division'] = graph_comments['current_division'].fillna('未設定')

# filter_dataframe_by_scopeは全組織列をチェック
graph_comments = filter_dataframe_by_scope(graph_comments, share_scope)
```

**section_manager の部門長コメント表示**: section_manager の課スコープでは `section='部門長'` の行がフィルターアウトされるため、`計測値` スコープ（部署名を含む広スコープ）で部門長行を別取得し、通常コメントデータに結合する。

### 9.3 ネストされたExpander

セクションとメンバー/年月のExpander構成：
- セクションExpander: `expanded=False`
- 内部のメンバー/年月Expander: `expanded=True`

### 9.4 よくある問題

| 問題 | 原因 | 解決策 |
|------|------|--------|
| コメントが表示されない（権限スコープ適用時） | タブレベルでmail_addressにより権限スコープを適用 | `filter_dataframe_by_scope()`で組織列を使ってスコープ適用 |
| スコープフィルタリング失敗 | sectionカラムのみチェック | `filter_dataframe_by_scope()`使用 |
| マネジメントが課別以外で表示される | 全グルーピングでオーバーライド適用 | `grouping == 'section'`時のみ適用 |
| 列名の不一致 | comment_dfは`current_section`、main_dfは`section` | マッピング後にフィルタリング |
| マネジメント選択時にトレンド列が空 | signal_dfをteam列でフィルタリング | 名前でフィルタリング（rating2のteam値は異なる場合あり） |
| 部署全体が非表示 | exclude_sectionsで未設定を除外 | exclude_sectionsは無効化済み |
| section_managerが部門長コメントを見れない | 課スコープでは section='部門長' がフィルターアウトされる | `計測値`スコープで部門長行を取得して結合 |

### 9.5 signal_dfのフィルタリング

signal_dfにはシグナル固有のカラム（trend, intervention_priority等）が含まれるため、
pivot_dfでフィルタリングした結果と同期させる場合は名前ベースでフィルタリングします：

```python
# 推奨: メインdfの名前でフィルタリング
names_in_filtered = ts_df['name'].unique()
tab_signal_df = tab_signal_df[tab_signal_df['name'].isin(names_in_filtered)]
```

### 9.6 intervention_priority の計算ルールと落とし穴

#### 設計原則

| レイヤー | 使用する値 | 理由 |
|----------|-----------|------|
| 生データ（rating2 シート） | **neg = 基本スコア + flag_constant_6m ボーナス** | Admin GAS が算出して書き込む |
| 足切りフィルター（`get_signal_data`） | **neg / pos をそのまま比較** | Dashboard では加工しない |
| 表示値（`derive_intervention_priority`） | **(勝った側) − threshold** | flag 処理は Admin 側で完結 |

#### derive_intervention_priority() のルール

```python
neg = df['intervention_priority_neg'].fillna(0)  # Admin が flag ボーナス込みで計算済み
pos = df['intervention_priority_pos'].fillna(0)  # flag 処理なし
_priority_is_neg = neg >= pos                    # 大小比較：大きい方が勝ち、同点は neg 優先
intervention_priority = neg.where(_priority_is_neg, pos) - threshold
```

`_priority_is_neg` は表示の赤/緑の色分けだけでなく、ソート順にも影響する。
側の判定は **neg/pos の大小比較**（同点は neg 優先）。これによりエンゲージメントグラフと
赤/緑の側が一致する。足切り（`neg > threshold or pos > threshold`）は `get_signal_data`
側で行うため、勝った側の値はシグナルテーブル上では必ず正値になる。

#### よくある落とし穴

| 問題 | 症状 | 原因 | 対策 |
|------|------|------|------|
| Dashboard 側で flag ボーナスを再加算 | 二重計上になり、数値が過大になる | `intervention_priority_neg` にはすでに Admin が flag ボーナスを含めている | Dashboard では `intervention_priority_neg` をそのまま使い、flag 加算コードを持たない |
| flag_constant_6m を閾値判定に使う | 本来対象外の人が表示される | 足切り前に flag ボーナスを加えてしまう | flag_constant_6m はラベル表示専用。`intervention_priority_neg` 自体が判定値 |
| flag 変換ロジックの重複 | flag ラベル変更時の更新漏れ | 同一の変換 lambda が複数箇所に存在 | `_fmt_flag_constant()` プライベートヘルパーを唯一の場所とする |
