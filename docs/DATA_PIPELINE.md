# データパイプライン仕様書

WE-Dashboard アプリケーションにおける、Excel 入力からグラフ表示までのデータフローを記述する。

---

## 1. データソース

### 入力ファイル: EngagementMasterSS.xlsx

アプリケーションが読み込む唯一の入力ファイル。以下の 2 シートを使用する。

| シート名 | 用途 |
|----------|------|
| **rating2** | signal_df および pivot_df の主データソース |
| **comment** | コメントデータ（懸念事項・共有事項） |

---

### rating2 シートのカラム

| カラム名 | 説明 |
|----------|------|
| `year` | 年 |
| `month` | 月 |
| `mail_address` | メールアドレス（個人識別子） |
| `name` | 氏名 |
| `current_division` | 部門（現所属） |
| `current_department` | 部署（現所属） |
| `current_section` | 課（現所属） |
| `current_team` | チーム |
| `current_project` | プロジェクト |
| `grade` | 職位 |
| `intervention_priority_neg` | 介入優先度（ネガティブ方向） |
| `intervention_priority_pos` | 介入優先度（ポジティブ方向） |
| `trend_recent` | 短期変化 |
| `trend_refined` | 中期トレンド |
| `big_change` | 短期変動（旧称: `change_tag`） |
| `stability_6` | 中期安定性（旧称: `stability`） |
| `flag_constant_6m` | 調査抵抗疑義（V/D/A 固定化パターン判定） |
| `strength_short` | 強み（短期） |
| `strength_mid` | 強み（中期） |
| `weakness_short` | 弱み（短期） |
| `weakness_mid` | 弱み（中期） |
| `engagement_rating` | エンゲージメント値（生スコア 0–54） |
| `vigor_rating` | 活力値（生スコア 0–18） |
| `dedication_rating` | 熱意値（生スコア 0–18） |
| `absorption_rating` | 没頭値（生スコア 0–18） |

---

### comment シートのカラム

| カラム名 | 説明 |
|----------|------|
| `year` | 年 |
| `month` | 月 |
| `mail_address` | メールアドレス |
| `name` | 氏名 |
| `division` / `current_division` | 部門 |
| `department` / `current_department` | 部署 |
| `section` / `current_section` | 課 |
| `team` / `current_team` | チーム |
| `project` / `current_project` | プロジェクト |
| `grade` | 職位 |
| `concern` | 懸念事項（コメント本文） |
| `comment` | 共有事項（コメント本文） |

---

## 2. データ読み込み (data_loader.py)

### load_data() の処理フロー

```
EngagementMasterSS.xlsx
        │
        ▼
[1] decrypt_excel_if_needed()
        │  パスワード保護 Excel を msoffcrypto で復号
        │  保護なしの場合はそのままスキップ
        ▼
[2] rating2 シート読み込み
        │  → signal_raw_df
        ▼
[3] 後方互換リネーム
        │  change_tag  → big_change
        │  stability   → stability_6
        ▼
[4] 組織カラムマッピング
        │  current_division   → division
        │  current_department → department
        │  current_section    → section
        │  flag_constant_6m   → flag_constant_6m (列なし時は None)
        ▼
[5] 欠損値補完
        │  組織カラムを「未設定」で fillna
        ▼
[6] pivot_df 導出
        │  signal_df から評価カラムを選択し正規化
        │  engagement_rating / ENGAGEMENT_DIVISOR (5.4) → 0–10 スケール
        │  vigor / dedication / absorption_rating
        │      / COMPONENT_DIVISOR (1.8)             → 0–10 スケール
        ▼
[7] comment シート読み込み
        │  → comment_df
        ▼
[8] @st.cache_data でキャッシュ
        │
        ├─▶ pivot_df    (正規化済み評価データ)
        ├─▶ signal_df   (生シグナルデータ)
        └─▶ comment_df  (コメントデータ)
```

### 出力 DataFrame

| DataFrame | 内容 | 主な用途 |
|-----------|------|----------|
| **pivot_df** | 0–10 スケールに正規化した評価データ | グラフ表示全般 |
| **signal_df** | trend, intervention_priority 等の生シグナル | シグナルテーブル表示 |
| **comment_df** | concern / comment の全コメント | コメントセクション表示 |

### スケール変換の詳細

| 元カラム | 除数 (Divisor) | 変換後レンジ |
|----------|---------------|-------------|
| `engagement_rating` (0–54) | `ENGAGEMENT_DIVISOR` = 5.4 | 0–10 |
| `vigor_rating` (0–18) | `COMPONENT_DIVISOR` = 1.8 | 0–10 |
| `dedication_rating` (0–18) | `COMPONENT_DIVISOR` = 1.8 | 0–10 |
| `absorption_rating` (0–18) | `COMPONENT_DIVISOR` = 1.8 | 0–10 |

---

## 3. フィルタリングパイプライン

### レイヤー構成

データはアプリケーション内で以下の 5 段階のフィルタリングを順に通過する。

```
Layer 0: @st.cache_data
         全データを一度だけ読み込みキャッシュ
                │
                ▼
Layer 1: 期間フィルター
         year_month_dt の範囲指定
         (サイドバーのスライダーで制御)
                │
                ▼
Layer 2: サイドバースコープ
         get_sidebar_scope() → filter_dataframe_by_scope()
         ログインユーザーの権限に応じた組織スコープ制限
                │
                ▼
Layer 3: カスケードフィルター
         部門 → 職位 → 部署 → 課 → チーム → プロジェクト → 個人
         (filter_helpers.py)
                │
                ▼
Layer 4: タブスコープ
         get_data_scope_for_tab() → filter_dataframe_by_scope()
         各タブ固有の表示スコープ
                │
                ▼
Layer 5: グルーピングスコープ
         get_grouping_scope() + grade_filter + section_aliases
         グラフのグルーピング単位に応じた絞り込み
```

---

### サイドバーフィルターのカスケード (filter_helpers.py)

フィルター選択は親から子へ一方向に連鎖する。

```
部門
 └─ 職位
      └─ 部署
           └─ 課
                └─ チーム
                     └─ プロジェクト
                          └─ 個人
```

**動作規則:**

- 親フィルターが変更されると、すべての子フィルターは `すべて` にリセットされる。
- 各フィルターの選択肢は、親フィルターの選択結果によって動的に絞り込まれる。
- 課マネージャー権限のユーザーには、管理対象の課のみが表示されるセクション制限が適用される。

---

### signal_df のフィルタリング

signal_df は pivot_df と同一のフィルター条件を適用するが、フィルタリング方式が異なる。pivot_df でフィルタリング済みの `mail_address` を抽出し、それを使って signal_df を絞り込む。

```python
valid_mail_addresses = current_df['mail_address'].dropna().unique()
filtered_signal_df = scoped_signal_df[
    scoped_signal_df['mail_address'].isin(valid_mail_addresses)
]
```

この方式により、pivot_df と signal_df の対象個人が常に一致することが保証される。

---

### コメントデータのフィルタリング

comment_df は自己完結型であり、独自の組織列を保持している。メインデータ (pivot_df / signal_df) との結合は不要。

```python
graph_comments['section'] = graph_comments['current_section'].fillna('未設定')
graph_comments = filter_dataframe_by_scope(graph_comments, share_scope)
```

comment_df に対して直接 `filter_dataframe_by_scope()` を適用することで、表示スコープと一致するコメントのみを取得する。

---

## 4. シグナル処理 (signal_processing.py)

### intervention_priority の導出

rating2 シートには `intervention_priority_neg` と `intervention_priority_pos` の 2 列が存在する。加えて `flag_constant_6m` の値に基づく追加ポイントを `_neg` に加算した上で、以下の規則で 1 列の `intervention_priority` に統合する。

**flag_constant_6m 加算ポイント:**

| 値 | 加算ポイント |
|----|------------|
| `LOW_FIXED` | +3 |
| `MID_EVASION` | +2 |
| `HIGH_AVOIDANCE` | +2 |
| `FIX_SHIFTED` | +4 |
| その他（空文字・None） | 0 |

```
(intervention_priority_neg + flag_constant_6m ポイント) > INTERVENTION_PRIORITY_THRESHOLD (= 2)
    → タイプ: negative
    → 表示値 = 加算後 neg 値 - threshold

intervention_priority_pos > INTERVENTION_PRIORITY_THRESHOLD (= 2)
    → タイプ: positive
    → 表示値 = intervention_priority_pos - threshold

どちらも threshold 以下
    → シグナルテーブルに表示しない
```

`_neg` は `_pos` より優先される（両方が閾値超でも negative として扱う）。

---

### シグナルテーブルのソート順

シグナルテーブルは以下の優先順位でソートされる。

| 優先度 | ソートキー | 順序 |
|--------|-----------|------|
| 1 | 優先度タイプ | negative → positive |
| 2 | 介入必要度 | 降順（値が大きいほど上位） |
| 3 | トレンドグループ | ネガティブ → 中立 → ポジティブ |
| 4 | 課 | `group_order_config.json` の設定順 |

---

### 表示フォーマット変換

| フィールド | 変換内容 |
|-----------|---------|
| 介入必要度 | 全角数字で表示。negative は赤色、positive は緑色 |
| `level` | 英語ラベル → 日本語変換（下表参照） |
| `flag_constant_6m` | 内部値 → 日本語変換（下表参照） |
| `strength` / `weakness` | 略称 → 日本語変換（下表参照） |

**flag_constant_6m 変換テーブル:**

| 内部値 | 日本語表示名 |
|--------|------------|
| `LOW_FIXED` | 連続固定低評価回答 |
| `MID_EVASION` | 連続固定中評価回答 |
| `HIGH_AVOIDANCE` | 連続固定高評価回答 |
| `FIX_SHIFTED` | 連続固定回答シフト |
| その他 | `-` |

**level 変換テーブル:**

| 英語 | 日本語 |
|------|--------|
| Critical | 低調 |
| Low | やや低調 |
| Moderate | 標準 |
| High | 良好 |
| Thriving | 非常に良好 |

**strength / weakness 変換テーブル:**

| 略称 | 日本語 |
|------|--------|
| V | 活力 |
| D | 熱意 |
| A | 没頭 |

---

## 5. 統計計算 (statistics.py)

### calculate_group_statistics()

グループ別の統計量を算出する。

| 統計量 | 算出方法 |
|--------|---------|
| 平均値 | `mean()` |
| 傾向の傾き | 線形回帰の傾き（`np.polyfit` 使用） |
| 標準偏差 | `std()` |

個人別グルーピング時は、signal_df から `trend_recent` および `trend_refined` 列を結合して追加する。

---

### format_measured_data()

計測値表示用に、グループ × 年月の平均値を算出する。結果は小数点 1 桁でフォーマットして返す。

---

## 6. グラフ生成 (charts.py)

### グラフ一覧

| 関数名 | グラフタイプ | 使用タブ |
|--------|------------|---------|
| `create_time_series_chart()` | 折れ線グラフ | 時系列 |
| `create_recent_group_comparison_chart()` | グループ棒グラフ | カテゴリ比較 |
| `create_group_rating_distribution()` | 評価バンド積み上げ棒グラフ | 評価 |
| `create_box_plot()` | ボックスプロット | 分布 |
| `create_radar_chart()` | レーダーチャート | 分布 |
| `create_individual_trend()` | 個人推移グラフ（棒 + 折れ線） | 個人 |

---

### 共通設定

| 設定項目 | 値 |
|---------|-----|
| Y 軸範囲 | 0 – 10.3 (`RATING_AXIS_MAX`) |
| X 軸フォーマット | `'%Y-%m'`（年月形式） |
| 評価バンド: 高い | スコア ≥ 6.0 |
| 評価バンド: 低い | スコア ≤ 2.0 |
| カラースケール | Blues (0.35 to 1.0) |

---

## 7. グループ順序設定 (group_order_config.json)

グラフおよびシグナルテーブルにおけるカテゴリの表示順序を JSON 形式で定義する。

```json
{
  "department": ["部署A", "部署B", "..."],
  "section":    ["課A",   "課B",   "..."],
  "grade":      ["職位A", "職位B", "..."]
}
```

### 参照方法

`get_category_order_with_reference()` 関数が `group_order_config.json` を読み込み、各カテゴリの順序配列を返す。

**未定義値の扱い:** 設定ファイルに記載のない値は、アルファベット順で末尾に配置される。

**個人名のソート:** `sort_names_by_grade()` 関数により、個人名は職位順（`grade` の設定順）でソートされる。

---

## 8. データフロー全体図

```
EngagementMasterSS.xlsx
        │
        ▼
  data_loader.py
  ┌─────────────────────────────────────────┐
  │ decrypt → read → rename → map → fillna  │
  │                                          │
  │  signal_raw_df ──normalize──▶ pivot_df  │
  │  signal_raw_df ────────────▶ signal_df  │
  │  comment sheet ────────────▶ comment_df │
  └─────────────────────────────────────────┘
        │           │           │
        ▼           ▼           ▼
   pivot_df    signal_df   comment_df
        │           │           │
        ▼           │           │
  フィルタリングパイプライン (Layer 1–5)
        │           │           │
        │    signal_processing.py
        │           │
        │    intervention_priority 統合
        │    ソート・フォーマット変換
        │           │
        ▼           ▼           ▼
   statistics.py              コメント表示
   ┌──────────────────┐
   │ 平均 / 傾き / std │
   └──────────────────┘
        │
        ▼
   charts.py
   ┌──────────────────────────────────────┐
   │ 時系列 / 棒グラフ / 分布 / 個人推移  │
   └──────────────────────────────────────┘
        │
        ▼
   Streamlit UI 表示
```
