# ドキュメント一覧

Work Engagement Dashboard プロジェクトのドキュメントインデックスです。
目的・役割に応じて、下記の「推奨読書順」セクションを参照してください。

---

## ドキュメント一覧

| ファイル名 | 概要 | 主な読者 |
|-----------|------|---------|
| [INDEX.md](./INDEX.md) | このファイル。ドキュメント全体の案内 | 全員 |
| [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) | システム全体のアーキテクチャ・技術仕様 | 開発者 |
| [SETUP_GUIDE.md](./SETUP_GUIDE.md) | ローカル開発環境の構築・Streamlit Cloudへのデプロイ手順 | 開発者・管理者 |
| [DATA_PIPELINE.md](./DATA_PIPELINE.md) | Excelファイルの読み込みからDataFrame加工・画面表示までのデータフロー仕様 | 開発者 |
| [PRIVILEGE_SYSTEM.md](./PRIVILEGE_SYSTEM.md) | ユーザー権限クラスの設計・設定方法・アクセス制御ロジック | 管理者・開発者 |
| [MODULE_REFERENCE.md](./MODULE_REFERENCE.md) | `modules/` 配下の各モジュールの関数・クラスAPIリファレンス | 開発者 |
| [PASSWORD_PROTECTION_SETUP.md](./PASSWORD_PROTECTION_SETUP.md) | Excelファイルへのパスワード設定手順とダッシュボードとの連携設定 | 管理者 |
| [LEAVE_MEMBER_TOGGLE.md](./LEAVE_MEMBER_TOGGLE.md) | 転属・退職メンバー表示トグルの設計・実装仕様と実装時の教訓 | 開発者 |
| [SESSION_STATE_PATTERNS.md](./SESSION_STATE_PATTERNS.md) | セッションステートの所有権モデル・クロスタブナビゲーションパターン・将来の定数化計画 | 開発者 |

---

## 各ドキュメントの詳細説明

### TECHNICAL_ARCHITECTURE.md — 技術仕様書

システム全体の構成を解説したドキュメントです。使用技術スタック（Streamlit・pandas・Plotly等）、ディレクトリ構成、モジュール間の依存関係、認証フロー、デプロイ構成について記載しています。プロジェクトの全体像を把握したい開発者が最初に読むべきドキュメントです。

### SETUP_GUIDE.md — セットアップガイド

ローカル開発環境の構築手順から、Streamlit Cloudへのデプロイまでをカバーします。Pythonの依存パッケージインストール、`secrets.toml` の設定、ローカル起動方法、本番環境へのデプロイ設定を順を追って説明します。

### DATA_PIPELINE.md — データパイプライン仕様

Excelファイルの読み込みに始まり、DataFrame への変換・加工・フィルタリングを経て画面に表示されるまでの一連のデータフローを仕様として記述しています。`df`・`signal_df`・`comment_df` の生成ロジック、サイドバーフィルターの適用順序（部門→職位→部署→課→チーム→プロジェクト→個人）、タブごとの権限スコープ適用の仕組みを解説します。

### PRIVILEGE_SYSTEM.md — 権限管理システム仕様

ユーザーの権限クラス（`admin`・`department_head`・`section_manager`・`member` 等）の設計と、各クラスに付与できる権限フィーチャー（`data_scope`・`grouping_scope`・`section_scope`・`grade_filter`・`anonymize`・`section_aliases`）を解説します。権限設定の変更手順（`config/privileges_configuration.md` の編集 → `generate_privileges_yaml.py` の実行 → `config/privileges.yaml` の自動生成）についても記載しています。

### MODULE_REFERENCE.md — モジュールAPIリファレンス

`modules/` ディレクトリ配下の各Pythonモジュールのパブリック関数・クラスをAPIリファレンス形式で記述しています。`auth.py`（認証・権限管理）・`charts.py`（グラフ生成）・`components.py`（UIコンポーネント）・`data_loader.py`（データ読み込み）・`privilege_manager.py`（権限シングルトン）等が対象です。機能追加・修正時の実装ガイドとして活用してください。

### PASSWORD_PROTECTION_SETUP.md — Excelパスワード保護設定ガイド

Excelファイルにパスワードを設定し、ユーザーがExcelで直接開けない状態でダッシュボードからのみデータを参照できるようにするための設定手順を解説します。ExcelでのOpenXML暗号化手順、Streamlit Secretsへのパスワード登録、`msoffcrypto` を利用した自動復号の仕組みを説明します。

### SESSION_STATE_PATTERNS.md — セッションステート設計パターン

Streamlit の実行モデル制約（タブ切り替えの rerun なし・ウィジェット生成後のキー書き換え禁止など）と、それを踏まえたセッションステートの所有権モデルを記述しています。クロスタブナビゲーションパターン・ウィジェットキーバージョニングパターン・複数インスタンス干渉の防止策を実装例付きで解説します。また将来の `config.py` 定数化計画（定数名・変更対象ファイル・手順）も記載しており、コード改善の準備資料として使用できます。

### LEAVE_MEMBER_TOGGLE.md — 転属・退職メンバー表示トグル仕様

「転属・退職メンバーを含む」チェックボックスの設計・実装仕様を解説します。3値の leave ステータス設計、`members.yaml` をデータソースとした leave 判定ロジック、Admin GAS による `current_*` フィールドクリア時の組織情報復元方法、`@st.cache_data` アンダースコア引数の落とし穴など、実装で遭遇した問題とその解決策を詳細に記載しています。

---

## 推奨読書順

### 新規開発者（プロジェクトに初めて参加する場合）

1. **TECHNICAL_ARCHITECTURE.md** — システム全体の構造と使用技術を把握する
2. **SETUP_GUIDE.md** — ローカル環境を構築して動作確認する
3. **DATA_PIPELINE.md** — データの流れとフィルター・権限適用の順序を理解する
4. **PRIVILEGE_SYSTEM.md** — 権限システムの設計思想と設定方法を学ぶ
5. **MODULE_REFERENCE.md** — 実装対象のモジュールAPIを確認する

### 管理者（権限設定・ユーザー管理を担当する場合）

1. **PRIVILEGE_SYSTEM.md** — 権限クラスの種類と設定変更手順を確認する
2. **PASSWORD_PROTECTION_SETUP.md** — Excelのパスワード保護とダッシュボード連携を設定する
3. **SETUP_GUIDE.md** — デプロイ環境のSecrets設定が必要な場合に参照する

### 機能追加・バグ修正を行う開発者

1. **MODULE_REFERENCE.md** — 変更対象モジュールのAPIと責務を確認する
2. **DATA_PIPELINE.md** — データフローへの影響範囲を把握する
3. **TECHNICAL_ARCHITECTURE.md** — モジュール間の依存関係を確認する

### Excelデータを更新・管理する担当者

1. **PASSWORD_PROTECTION_SETUP.md** — Excelファイルの保護設定手順を確認する
2. **DATA_PIPELINE.md** — Excelのシート構成とカラム仕様を確認する

---

## 関連ファイル（docs外）

| ファイル・ディレクトリ | 説明 |
|----------------------|------|
| `README.md` | プロジェクトの概要と起動方法（最初に読む） |
| `CLAUDE.md` | AIアシスタント向けプロジェクトコンテキスト |
| `config/privileges_configuration.md` | 権限設定のソースファイル（マークダウンテーブル形式） |
| `config/privileges.yaml` | 権限設定の生成済みYAMLファイル（自動生成・直接編集不可） |
| `tools/generate_privileges_yaml.py` | `privileges_configuration.md` から `privileges.yaml` を生成するスクリプト |

---

*最終更新: 2026-07-04*
