# Work Engagement Analysis Dashboard

ワーク・エンゲージメント分析用インタラクティブ・ダッシュボード

## 機能

### 🚨 対応優先順位リスト
- 介入優先度に基づく対応が必要な個人の表示
- 最新期間のトレンド・変動・安定性指標
- 個人別の強み・弱み分析

### 📈 時系列分析
- エンゲージメント指標（総合、活力、熱意、没頭）の月次推移
- 部門・課・プロジェクト・職位別のグループ化表示
- 期間サマリー統計
- 主要な指標（平均、傾向の傾き、標準偏差）

### 📊 主要な指標（Key Indicators）
- 時系列およびグループ比較レポートに統計指標を表示
- 各グループの平均値、傾向の傾き（線形回帰による月次トレンド）、標準偏差
- カスタム順序対応（group_order_config.json）

### 📊 分布分析
- 組織属性別のボックスプロット（日本語ラベル対応）
- ヒストグラム表示
  - 固定X軸範囲（0-10.3）
  - 1ステップ間隔のビン（0-1, 1-2, ..., 9-10）
  - マージナルボックスプロット付き

### 🎯 比較分析
- ヒートマップ（時間×組織属性）
- レーダーチャート（エンゲージメント構成要素の比較）
- 散布図（指標間の相関）

### 👤 個人分析
- 個人別の時系列推移（4指標同時表示）
- 個人シグナル情報
  - エンゲージメント
  - 活力・熱意・没頭
  - 介入優先度、中期トレンド、短期変動、中期安定性
  - 強み・弱み分析（短期・中期）

### 🔍 フィルタリング機能
- 年度
- 部門（division）
- 部（department）
- 課（setction）
- チーム（team）
- プロジェクト（project）
- 職位（grade）

## データ形式

### rating シート
アップロードするExcelファイルは**EngagementMasterSS.xlsx形式**（`rating`シート）を想定しています。1人×1回の回答につきUWES各因子（エンゲージメント/活力/熱意/没頭）が1行ずつ並ぶロング形式です。アプリ側で自動的にピボットし、従来の列構造に変換します。

**デフォルトファイル**: ファイルをアップロードしない場合、プロジェクトルートに`EngagementMasterSS.xlsx`が存在すれば自動的に読み込まれます。

### rating2 シート
介入シグナル用の補足データを`rating2`シートから読み込みます。以下のカラムが必要です:
- intervention_priority: 介入優先度
- trend_refined: 中期トレンド
- change_tag: 短期変動
- stability: 中期安定性
- strength_short, weakness_short: 短期の強み・弱み
- strength_mid, weakness_mid: 中期の強み・弱み

### 必須カラム

| カラム名 | 型 | 説明 |
|---------|------|------|
| year | int | 年 |
| month | int | 月 |
| mail_address | str | メールアドレス |
| name | str | 氏名 |
| current_division | str | 部門 |
| current_department | str | 部 |
| current_section | str | 課 |
| current_team | str | チーム |
| current_project | str | プロジェクト |
| grade | str | 職位 |
| factor | str | 指標名（エンゲージメント/活力/熱意/没頭） |
| score | float | 上記factorに対応するスコア |

## 設定ファイル

### group_order_config.json
グループ表示順序をカスタマイズするための設定ファイル。以下の形式で定義:

```json
{
  "section": ["部門1", "部門2", ...],
  "department": ["部署1", "部署2", ...],
  "grade": ["職位1", "職位2", ...]
}
```

このファイルが存在しない場合、アルファベット順でソートされます。

## 技術スタック

- **Streamlit**: Webアプリケーションフレームワーク
- **Plotly**: インタラクティブ可視化
  - Express API（高レベルチャート作成）
  - Graph Objects API（カスタムチャート制御）
- **Pandas**: データ処理・統計計算
- **NumPy**: 数値計算（トレンド傾き計算）
- **OpenPyXL**: Excel読み込み

## ライセンス

© RDPi Corporation
