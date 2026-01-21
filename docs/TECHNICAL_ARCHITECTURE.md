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
│   ├── signal_processing.py  # シグナルデータ処理
│   ├── statistics.py         # 統計計算
│   └── utils.py              # ユーティリティ関数
├── docs/                     # ドキュメント
├── auth_users.json           # 認証情報（開発用）
├── auth_users.dat            # 認証情報（本番用・エンコード済）
├── group_order_config.json   # グループ順序設定
├── convert_auth.py           # 認証ファイル変換ツール
├── encrypt_data.py           # データ暗号化ツール
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
| intervention_priority | 介入優先度 |
| trend_refined | 中期トレンド |
| change_tag | 短期変動 |
| stability | 中期安定性 |
| strength_short/mid | 強み（短期/中期） |
| weakness_short/mid | 弱み（短期/中期） |
| engagement_rating | エンゲージメント値 |
| vigor_rating | 活力値 |
| dedication_rating | 熱意値 |
| absorption_rating | 没頭値 |

#### comment シート（コメントデータ）
| カラム | 説明 |
|--------|------|
| year, month | 年月 |
| mail_address | メールアドレス |
| concern | 気になった出来事や気づき |
| comment | 共有したいこと |

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
- 5つのタブ表示（時系列/グループ比較/評価/個人/分布）
- セッション状態管理

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

### 3.7 modules/utils.py（ユーティリティモジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `load_group_orders()` | グループ順序設定読込 |
| `sort_with_config()` | 設定に基づくソート |
| `sort_names_by_grade()` | 職位順で氏名をソート |
| `get_options()` | フィルター選択肢取得 |
| `render_department_and_group_controls()` | 部署/課/グルーピングコントロール表示 |

### 3.8 modules/statistics.py（統計モジュール）

**主要関数:**

| 関数 | 説明 |
|------|------|
| `calculate_group_statistics()` | グループ別統計計算（平均/傾き/標準偏差） |
| `format_statistics_for_display()` | 表示用フォーマット |

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
| **コードの重複** | 各タブでコメント表示ロジックが重複 | 共通コンポーネント化 |
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

1. **app.py**: 1200行超 → タブ別モジュール分割を検討
2. **charts.py**: グラフ設定の共通化
3. **コメント表示ロジック**: 4箇所で重複 → 共通関数化

---

## 6. セキュリティ考慮事項

| 項目 | 実装状況 |
|------|----------|
| パスワードハッシュ | SHA-256 |
| Excelパスワード保護 | msoffcryptoで復号 |
| 権限ベースアクセス制御 | PRIVILEGE_GROUP_ACCESSで実装 |
| 認証情報の保護 | .dat形式でBase64+pickle |
| シークレット管理 | Streamlit Secretsを使用 |

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
```

---

## 8. 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2026-01-21 | 初版作成 |
| 2026-01-21 | グルーピングフィルターの修正（フィルターリセット機構追加） |
| 2026-01-21 | 組織カラム名のリファクタリング（section→division, group→section） |
