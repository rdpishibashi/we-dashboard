# Technical Architecture Document

Work Engagement Dashboard 技術仕様書

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
│   ├── config.py             # 設定・定数
│   ├── data_loader.py        # データ読み込み
│   ├── encryption.py         # 暗号化ユーティリティ
│   ├── privilege_manager.py  # 権限ベースフィルタリング（NEW）
│   ├── signal_processing.py  # シグナルデータ処理
│   ├── statistics.py         # 統計計算
│   └── utils.py              # ユーティリティ関数
├── config/
│   └── privileges.yaml       # 権限設定（自動生成）
├── tools/
│   └── generate_privileges_yaml.py  # 権限YAML生成ツール
├── docs/
│   └── privileges_configuration.md  # 権限設定（ソースオブトゥルース）
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

入力ファイル（`EngagementMasterSS.xlsx`）は3つのシートで構成されます。

#### rating シート（評価データ）
| カラム | 説明 | 必須 |
|--------|------|------|
| year | 年 | ○ |
| month | 月 | ○ |
| mail_address | メールアドレス | ○ |
| name | 氏名 | ○ |
| factor | 評価項目（エンゲージメント/活力/熱意/没頭） | ○ |
| score | スコア | ○ |
| current_division | 部門（現所属） | |
| current_department | 部署（現所属） | |
| current_section | 課（現所属） | |
| current_team | チーム | |
| current_project | プロジェクト | |
| grade | 職位 | |

#### rating2 シート（シグナルデータ）
| カラム | 説明 |
|--------|------|
| year, month | 年月 |
| name | 氏名 |
| current_division | 部門（現所属） |
| current_department | 部署（現所属） |
| current_section | 課（現所属） |
| current_team | チーム |
| current_project | プロジェクト |
| grade | 職位 |
| intervention_priority | 介入優先度 |
| trend_recent | 短期変化（trend_recent） |
| trend_refined | 中期トレンド |
| change_tag | 短期変動 |
| stability | 中期安定性 |
| strength_short/mid | 強み（短期/中期） |
| weakness_short/mid | 弱み（短期/中期） |
| engagement_rating | エンゲージメント値 |
| vigor_rating | 活力値 |
| dedication_rating | 熱意値 |
| absorption_rating | 没頭値 |

**重要: rating2シートの組織列はratingシートと異なる場合あり**

rating2シートの組織列（section, team等）の値は、ratingシートと一致しない場合があります。
signal_dfをフィルタリングする際は、組織列ではなく**名前**でフィルタリングすることを推奨します：

```python
# 推奨: メインdfの名前でフィルタリング
names_in_filtered = main_df['name'].unique()
signal_df = signal_df[signal_df['name'].isin(names_in_filtered)]
```

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
graph_comments['section'] = graph_comments['current_section'].fillna('未設定')
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
- タブ表示（認証状態により表示内容が変化）
- セッション状態管理
- 認証ベースの機能制限

**認証状態による表示制御:**

| 機能 | 認証済み | 未認証 |
|------|----------|--------|
| タブ表示 | 5タブ（時系列/グループ比較/評価/個人/分布） | 4タブ（個人タブ非表示） |
| グルーピング選択肢 | すべて（部署/課/チーム/プロジェクト/職位/個人） | 制限（職位/個人を除外） |
| アクション対象候補 | 表示 | 非表示 |
| 共有したいこと | 表示 | 非表示 |

**データフロー:**
```
1. ファイルアップロード/デフォルトファイル読込
2. load_data() でデータ取得
3. 認証済みの場合 filter_by_privilege() でデータフィルタリング
4. サイドバーフィルター適用
5. 各タブでグラフ/テーブル表示
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
| `RATING_AXIS_MAX` | Y軸最大値（10.3） |
| `POSITIVE_TRENDS` / `NEGATIVE_TRENDS` | トレンド分類 |
| `PRIVILEGE_GROUP_ACCESS` | 権限別アクセス範囲 |
| `ENGAGEMENT_DIVISOR` / `COMPONENT_DIVISOR` | 評価値計算の除数 |

### 3.4 modules/data_loader.py（データ読込モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `get_excel_password()` | Streamlit secretsからパスワード取得 |
| `decrypt_excel_if_needed(file_obj)` | パスワード保護Excelの復号 |
| `load_data(uploaded_file)` | データ読込・前処理（キャッシュ対応） |

**データ変換処理:**
1. ratingシートをpivot形式に変換（factor列→各評価列）
2. 年月カラム生成（`year_month`, `year_month_dt`）
3. 組織カラムマッピング
4. 欠損値を「未設定」で補完

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

### 3.6 modules/signal_processing.py（シグナル処理モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `apply_signal_rating_calculations()` | シグナル値の計算適用 |
| `get_signal_data()` | フィルタリング済みシグナルデータ取得 |
| `sort_signals_by_trend_and_priority()` | トレンド・優先度でソート |
| `render_signal_table()` | シグナルテーブル表示 |
| `format_individual_signal_data()` | 個人シグナルの整形 |

**シグナルソート順:**
1. トレンドグループ（ネガティブ → 中立 → ポジティブ）
2. 介入優先度（降順）
3. 課（設定順）

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
| `render_comments_and_signals()` | 上記3セクションの一括表示 |

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

### 3.8 modules/utils.py（ユーティリティモジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `load_group_orders()` | グループ順序設定読込 |
| `sort_with_config()` | 設定に基づくソート |
| `sort_names_by_grade()` | 職位順で氏名をソート |
| `get_options()` | フィルター選択肢取得 |
| `render_department_and_group_controls()` | 部署/課/グルーピングコントロール表示 |

### 3.9 modules/statistics.py（統計モジュール）

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

### 3.10 modules/privilege_manager.py（権限管理モジュール）

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
    visible_in_tabs: [時系列, グループ比較, 評価, 分布]
    exclude_sections: [未設定]  # 注: 現在は無効化（下記参照）
```

**注意: exclude_sectionsは無効化**

`exclude_sections`は以下の理由で無効化されています：
- 一部の部署（例: 品質保証部）はサブセクションを持たず、全メンバーが`section='未設定'`
- 除外すると部署全体が非表示になる問題が発生

**権限設定の階層:**
```
docs/privileges_configuration.md  ← ソースオブトゥルース（Markdown表形式）
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

### 4.2 フィルター関連
| キー | 説明 |
|------|------|
| `filter_period` | 期間スライダー値 |
| `filter_divisions` | 選択部門 |
| `filter_departments` | 選択部署 |
| `filter_sections` | 選択課 |
| `reset_period_filter` | 期間リセットフラグ |
| `reset_local_filters` | ローカルフィルターリセットフラグ |

### 4.3 タブ固有
| キー | 説明 |
|------|------|
| `{tab}_department_select` | タブ別部署選択 |
| `{tab}_section_select` | タブ別課選択 |
| `{tab}_grouping_select` | タブ別グルーピング選択 |

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
| Excelパスワード保護 | msoffcryptoで復号 |
| 権限ベースアクセス制御 | PRIVILEGE_GROUP_ACCESSで実装 |
| 認証情報の保護 | .dat形式でBase64+pickle |
| シークレット管理 | Streamlit Secretsを使用 |
| 未認証ユーザー制限 | 個人情報関連機能を非表示 |

### 6.1 未認証ユーザー向け機能制限

未認証（ログインしていない）ユーザーに対して、以下の機能が非表示となります：

| 非表示項目 | 理由 |
|------------|------|
| 個人タブ | 個人別の詳細データを保護 |
| 職位別グルーピング | 職位情報の保護 |
| 個人別グルーピング | 個人名の保護 |
| アクション対象候補セクション | 個人のシグナル情報を保護 |
| 共有したいことセクション | 個人のコメント情報を保護 |

**実装方法:**
```python
# タブの動的生成
if is_authenticated():
    tab_labels = ["時系列", "グループ比較", "評価", "個人", "分布"]
else:
    tab_labels = ["時系列", "グループ比較", "評価", "分布"]

# グルーピング選択肢の動的生成
if is_authenticated():
    base_grouping_options = ['なし', 'department', 'section', 'team', 'project', 'grade', 'name']
else:
    base_grouping_options = ['なし', 'department', 'section', 'team', 'project']
```

**注意点:**
- SHA-256は基本的なハッシュであり、本番運用ではbcryptなどの検討を推奨
- 認証ファイルはGitにコミットしないこと

---

## 7. 依存関係

```
streamlit
pandas
plotly
openpyxl
numpy
msoffcrypto-tool
pyyaml          # 権限設定YAML読み込み用
cryptography
statsmodels
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

---

## 9. 実装パターンとよくある問題

### 9.1 クイックリファレンス

| トピック | 要点 |
|----------|------|
| コメントデータ | 独自の組織列を持つ - メインデータと結合不要 |
| 権限フィルタリング | セクションスコープは部署名を含む場合あり、`filter_dataframe_by_scope()`を使用 |
| チームオーバーライド | `grouping == 'section'`（課別）の時のみ適用 |
| 統計トレンド列 | 個人別グルーピング時にsignal_dfから結合 |
| signal_dfフィルタリング | rating2シートの組織列はratingシートと異なる場合あり - 名前でフィルタリング |

### 9.2 共有したいことセクション

コメントデータは自己完結型のため、以下のパターンを使用：

```python
# 全組織列をマッピングしてからフィルタリング
graph_comments['section'] = graph_comments['current_section'].fillna('未設定')
graph_comments['department'] = graph_comments['current_department'].fillna('未設定')
graph_comments['division'] = graph_comments['current_division'].fillna('未設定')

# filter_dataframe_by_scopeは全組織列をチェック
graph_comments = filter_dataframe_by_scope(graph_comments, share_scope)
```

### 9.3 ネストされたExpander

セクションとメンバー/年月のExpander構成：
- セクションExpander: `expanded=False`
- 内部のメンバー/年月Expander: `expanded=True`

### 9.4 よくある問題

| 問題 | 原因 | 解決策 |
|------|------|--------|
| コメントが表示されない | mail_addressでフィルタリング | 組織列でフィルタリング |
| スコープフィルタリング失敗 | sectionカラムのみチェック | `filter_dataframe_by_scope()`使用 |
| マネジメントが課別以外で表示される | 全グルーピングでオーバーライド適用 | `grouping == 'section'`時のみ適用 |
| 列名の不一致 | comment_dfは`current_section`、main_dfは`section` | マッピング後にフィルタリング |
| マネジメント選択時にトレンド列が空 | signal_dfをteam列でフィルタリング | 名前でフィルタリング（rating2のteam値は異なる場合あり） |
| 部署全体が非表示 | exclude_sectionsで未設定を除外 | exclude_sectionsは無効化済み |

### 9.5 signal_dfのフィルタリング

rating2シート（signal_df）とratingシート（main df）では組織列の値が異なる場合があります。
特にマネジメント選択時は、team列ではなく名前でフィルタリングする必要があります：

```python
# 誤: team列でフィルタリング（rating2にteam値がない場合、空になる）
tab_signal_df = tab_signal_df[tab_signal_df['team'] == 'Management']

# 正: メインdfの名前でフィルタリング
names_in_filtered = ts_df['name'].unique()
tab_signal_df = tab_signal_df[tab_signal_df['name'].isin(names_in_filtered)]
```

この問題は以下の場合に発生します：
- 課選択で「マネジメント」を選択
- グルーピングで「個人別」を選択
- 「主要な指標」テーブルにトレンド列（短期変化/中期トレンド）が表示されない
