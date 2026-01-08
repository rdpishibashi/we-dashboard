# Work Engagement Analysis Dashboard

UWES-9ベースのワーク・エンゲージメント分析用インタラクティブダッシュボード

## 機能

### 🚨 シグナル機能
- 介入優先度に基づく個人アラート表示
- 最新期間のトレンド・変動・安定性指標
- 個人別の強み・弱み分析

### 📈 時系列分析
- エンゲージメント指標（総合、活力、熱意、没頭）の月次推移
- 部門・課・プロジェクト・職位別のグループ化表示
- 期間サマリー統計

### 📊 分布分析
- 組織属性別のボックスプロット
- ヒストグラム表示

### 🎯 比較分析
- ヒートマップ（時間×組織属性）
- レーダーチャート（エンゲージメント構成要素の比較）
- 散布図（指標間の相関）

### 👤 個人分析
- 個人別の時系列推移（4指標同時表示）
- 個人統計サマリー・変化率

### 🔍 フィルタリング機能
- 年度
- 部門（section）
- 部（department）
- 課（group）
- チーム（team）
- プロジェクト（project）
- 職位（grade）

## セットアップ

### ローカル実行

```bash
# リポジトリのクローン
git clone <repository-url>
cd we_dashboard

# 仮想環境作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# アプリ起動
streamlit run app.py
```

### Streamlit Cloud デプロイ

1. このリポジトリをGitHubにプッシュ
2. [Streamlit Cloud](https://share.streamlit.io/) にログイン
3. "New app" → リポジトリ選択 → `app.py` を指定
4. "Deploy" をクリック

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

## 技術スタック

- **Streamlit**: Webアプリケーションフレームワーク
- **Plotly**: インタラクティブ可視化
- **Pandas**: データ処理
- **OpenPyXL**: Excel読み込み

## ライセンス

Private - Internal Use Only
