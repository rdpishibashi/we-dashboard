# 権限システム仕様書 (PRIVILEGE_SYSTEM)

> **このドキュメントはアプリケーションの中で最も複雑な部分である権限システムの完全な仕様を記述する。**
> 変更を加える前に必ず全体を通読すること。

---

## 目次

1. [概要](#1-概要)
2. [設定ファイルの階層](#2-設定ファイルの階層)
3. [PrivilegeManager クラス](#3-privilegemanager-クラス)
4. [権限クラス体系](#4-権限クラス体系)
5. [スコープの種類と適用レイヤー](#5-スコープの種類と適用レイヤー)
6. [フィルタリング関数](#6-フィルタリング関数)
7. [チームセクションオーバーライド](#7-チームセクションオーバーライド)
8. [適用レイヤー](#8-適用レイヤー)
9. [タブとグルーピングの許可](#9-タブとグルーピングの許可)
10. [注意事項とよくある問題](#10-注意事項とよくある問題)

---

## 1. 概要

権限システムは、各ユーザーがアクセスできるデータと機能を制御する。YAML ベースの設定ファイルを使用し、クラス間の継承をサポートする。

### 設計原則

- **最小権限の原則**: デフォルトではアクセスを拒否し、必要な権限のみを付与する
- **継承による設定の再利用**: 共通設定を親クラスに定義し、子クラスで上書き・拡張する
- **単一の設定ソース**: `privileges_configuration.md` のみを手動編集する。`privileges.yaml` は生成物であり直接編集しない
- **実行時フィルタリング**: アプリケーション起動時に YAML を読み込み、データ取得のたびに権限フィルタを適用する

### 権限が制御するもの

| 制御対象 | 説明 |
|----------|------|
| 表示可能タブ | ユーザーが閲覧できるダッシュボードタブ |
| データスコープ | 各タブで表示できる組織の範囲 |
| グルーピング | 使用できるグルーピング種類（部署・課・チーム等） |
| グルーピングスコープ | グルーピング別のデータ範囲 |
| セクションの表示/非表示 | UI上の特定セクション（アクション対象候補等）の可視性 |
| 匿名化 | セクションやタブ内の個人識別情報を匿名化するか |
| 職位フィルター | 特定の職位のみのデータを表示するか |

---

## 2. 設定ファイルの階層

```
config/privileges_configuration.md   ← ソースオブトゥルース（Markdown表形式、手動編集）
        |
        | (tools/generate_privileges_yaml.py で変換)
        v
config/privileges.yaml               ← 生成された設定ファイル（直接編集しない）
        |
        | (privilege_manager.py で読み込み)
        v
アプリケーション                      ← 実行時フィルタリング
```

### 各ファイルの役割

#### `config/privileges_configuration.md` (ソースオブトゥルース)

- 人間が読み書きしやすい Markdown の表形式で権限を定義する
- **このファイルのみを手動編集する**
- 編集後は必ず `generate_privileges_yaml.py` で再生成する

#### `config/privileges.yaml` (生成物)

- アプリケーションが実際に読み込む YAML ファイル
- **直接編集してはいけない**。次回の再生成で上書きされる
- Git 管理下に置くことで、設定変更の履歴を追跡できる

#### `tools/generate_privileges_yaml.py`

- `privileges_configuration.md` を解析して `privileges.yaml` を生成するスクリプト
- 設定を変更した後は必ずこのスクリプトを実行する

```bash
# 設定変更後の再生成手順
python tools/generate_privileges_yaml.py
```

#### `privilege_manager.py`

- YAML を読み込み、継承解決を行い、各種クエリに応答するクラスを提供する

---

## 3. PrivilegeManager クラス

### 設計パターン: シングルトン

`PrivilegeManager` はシングルトンパターンで実装されている。アプリケーション全体で一つのインスタンスのみが存在し、設定ファイルの読み込みは一度だけ行われる。

```python
# 正しいインスタンス取得方法
from privilege_manager import get_privilege_manager

privilege_manager = get_privilege_manager()
```

`PrivilegeManager._instance` クラス変数でインスタンスを保持する。`get_privilege_manager()` 関数は既存のインスタンスを返すか、存在しなければ新規作成する。

### 主要メソッド

| メソッド | 説明 |
|----------|------|
| `get_privilege_manager()` | シングルトンインスタンスを取得する |
| `get_data_scope_for_tab(privilege, tab)` | タブ別データスコープを取得する |
| `get_sidebar_scope(privilege)` | サイドバー用の統合スコープを取得する |
| `get_section_scope(privilege, section_name)` | セクション別スコープを取得する |
| `get_grouping_scope(privilege, grouping, dimension_filtered)` | グルーピング別スコープを取得する |
| `get_allowed_tabs(privilege)` | 表示可能なタブリストを取得する |
| `get_allowed_groupings(privilege)` | 使用可能なグルーピングリストを取得する |
| `has_feature_access(privilege, feature)` | 特定機能へのアクセス権を確認する |
| `should_anonymize_tab(privilege, tab)` | タブの匿名化フラグを確認する |
| `should_anonymize_section(privilege, section)` | セクションの匿名化フラグを確認する |
| `get_team_section_overrides(privilege)` | チームセクションオーバーライド設定を取得する |

### `_resolve_inheritance()`: 継承チェーンの解決

YAML に定義された `inherits` キーを辿り、親クラスの設定を深いマージ (deep merge) で結合する。

```yaml
# 例: section_manager は department_head を継承する
section_manager:
  inherits: department_head
  data_scope:
    default:
      type: values
      values: [SW課, PD課]
```

深いマージの動作:
- 子クラスの設定が親クラスの設定より**優先**される
- ネストされたオブジェクトは再帰的にマージされる（単純な上書きではない）
- リストは子クラスの値で完全に置き換えられる（マージされない）

---

## 4. 権限クラス体系

### 一覧

| クラス名 | 対象ユーザー | 特徴 |
|----------|-------------|------|
| `admin` | 管理者 | 全データ・全機能へのフルアクセス |
| `anonymous` | 未認証ユーザー | ダッシュボード非表示、ウェルカムページのみ表示 |
| `department_head` | sd, me, dev 部署の部長 | 部署レベルのスコープ |
| `section_manager` | sw, pd, me1-3 等の課長 | 課レベルのスコープ |
| `member` | soft, prod 等のメンバー | 制限付き、職位フィルターあり |
| `member_no_grade_filter` | develop1-2 等のメンバー | 制限付き、職位フィルターなし |

### クラス別の主な設定差異

#### `admin`
- `data_scope.default.type: all` → 全組織のデータを閲覧可能
- 全タブ・全グルーピングが許可される
- 匿名化なし

#### `anonymous`
- ダッシュボード自体が非表示
- ウェルカムページのみ表示
- データアクセスなし

#### `department_head`
- `data_scope.default.type: values` → 担当部署の組織名リストを指定
- 部署全体（複数課を含む）が閲覧可能

#### `section_manager`
- `data_scope.default.type: values` → 担当課の組織名リストを指定
- 担当課のデータのみ閲覧可能

#### `member`
- `data_scope.default.type: values` → 所属組織の組織名リストを指定（通常1件）
- `grade_filter` が有効 → 特定職位のみのデータを表示

#### `member_no_grade_filter`
- `member` とほぼ同じだが `grade_filter` が無効
- 全職位のデータを表示する（ただしスコープは制限される）

---

## 5. スコープの種類と適用レイヤー

権限システムには複数のスコープ種類が存在し、それぞれ異なるデータフィルタリングに使用される。

### 5.1 データスコープ (data_scope)

**用途**: 各タブでユーザーが閲覧できる組織の範囲を定義する。

**取得メソッド**: `get_data_scope_for_tab(privilege, tab)`

#### スコープタイプ

| type | 戻り値 | 意味 |
|------|--------|------|
| `all` | `None` | フィルタなし（全データ） |
| `none` | `[]` (空リスト) | 全行を除外（データなし） |
| `values` | `['組織名A', '組織名B', ...]` | 指定した組織名のみ |

#### タブ別スコープの設定

タブごとに異なるスコープを設定できる。指定のないタブは `default` にフォールバックする。

```yaml
# YAML 設定例
data_scope:
  default:
    type: values
    values: [SW課, PD課]
  時系列:
    type: all  # 時系列タブのみ全データ閲覧可能
  評価:
    type: none  # 評価タブはアクセス不可
```

フォールバック順序: `タブ名` → `default`

### 5.2 サイドバースコープ (get_sidebar_scope)

**用途**: サイドバーのドロップダウン選択肢（閲覧する組織の選択）に使用する。

**取得メソッド**: `get_sidebar_scope(privilege)`

**動作**: ユーザーがアクセスできる**全タブのスコープの UNION** を取得する。

```
サイドバースコープ = タブ1スコープ ∪ タブ2スコープ ∪ ... ∪ タブNスコープ
```

**重要**: サイドバーのドロップダウンはこのスコープで絞り込まれるが、各タブ内での実際のデータフィルタリングは、タブ別の `data_scope` が個別に適用される。つまりサイドバー選択肢に表示される組織名と、タブで実際に閲覧できるデータは必ずしも一致しない。

### 5.3 セクションスコープ (section_scope)

**用途**: ダッシュボード内の特定 UI セクションに対するアクセス制御。

**取得メソッド**: `get_section_scope(privilege, section_name)`

#### 対象セクション

| セクション名 | 説明 |
|-------------|------|
| アクション対象候補 | マネージャーが次の面談対象を選ぶためのリスト |
| 共有したいこと | メンバーからのコメント一覧 |
| 気になった出来事や気づき | マネージャーの観察メモ |

#### セクション制御メソッド

```python
# セクション自体の表示/非表示
privilege_manager.has_feature_access(privilege, section_name)
# → True: 表示する / False: 非表示にする

# セクション内のデータを匿名化するか
privilege_manager.should_anonymize_section(privilege, section_name)
# → True: 匿名化する / False: そのまま表示
```

#### セクション内のスコープ値

セクションスコープも `data_scope` と同様に `type` と `values` を持つ。セクション内でさらに組織を絞り込む必要がある場合に使用する。

### 5.4 グルーピングスコープ (grouping_scope)

**用途**: グルーピング（部署・課・チーム・プロジェクト別等）でデータを集計する際の組織の範囲。

**取得メソッド**: `get_grouping_scope(privilege, grouping, dimension_filtered)`

#### パラメータ

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `privilege` | str | 権限クラス名 |
| `grouping` | str | グルーピング種類 |
| `dimension_filtered` | bool | フィルター選択肢が「すべて」以外か |

#### グルーピングの内部キーマッピング

YAML 設定では以下の内部キーを使用する。

| 外部グルーピング名 | YAML 内部キー |
|------------------|--------------|
| department | `organization` |
| section | `organization` |
| team | `organization` |
| project | `organization` |
| grade | `grade` |
| name | `name` |

#### `grouping_scope_filtered` (フィルター選択時の代替スコープ)

ユーザーがサイドバーで特定組織を選択している場合（「すべて」以外）、通常のグルーピングスコープではなく `grouping_scope_filtered` が使用される。

```yaml
# YAML 設定例
grouping_scope:
  organization:
    type: values
    values: [SW課, PD課]
  grade:
    type: all
grouping_scope_filtered:
  organization:
    type: all  # フィルター選択時はスコープを緩和
```

`dimension_filtered=True` の時に `grouping_scope_filtered` を使用する。未設定の場合は `grouping_scope` にフォールバックする。

---

## 6. フィルタリング関数

権限システムが提供する主要なフィルタリング関数。

### `filter_dataframe_by_scope(df, scope_values, org_columns)`

DataFrame を組織スコープでフィルタリングする最も基本的な関数。

#### パラメータ

| パラメータ | デフォルト値 | 説明 |
|-----------|------------|------|
| `df` | - | フィルタリング対象の DataFrame |
| `scope_values` | - | スコープ値（`None`, `[]`, または文字列リスト） |
| `org_columns` | `['division', 'department', 'section']` | 検索対象の組織列名リスト |

#### 動作ロジック

```
scope_values が None    → フィルタなし（df をそのまま返す）
scope_values が [] (空) → 全行除外（空の DataFrame を返す）
scope_values が リスト  → org_columns のいずれかの列に scope_values の
                          いずれかの値が含まれる行のみ残す
```

#### 重要な注意点

`scope_values` には**課名だけでなく、部署名や部門名が含まれる場合がある**。これは `department_head` クラスが部署全体をスコープに持つためである。`org_columns` に複数列を指定することで、division・department・section のいずれかの列に値が存在する行をすべてマッチさせる。

```python
# 使用例
from privilege_manager import filter_dataframe_by_scope

scope = privilege_manager.get_data_scope_for_tab(privilege, current_tab)
filtered_df = filter_dataframe_by_scope(df, scope, org_columns=['division', 'department', 'section'])
```

**誤った使い方（課名のみで直接フィルタリング）**:
```python
# 悪い例: 部署名がスコープに含まれる場合に漏れが生じる
df = df[df['section'].isin(scope_values)]
```

**正しい使い方**:
```python
# 良い例: 複数列のいずれかにマッチする行を残す
df = filter_dataframe_by_scope(df, scope_values)
```

### `filter_dataframe_by_grade(df, allowed_grades)`

職位 (grade) による行フィルタリング。

#### パラメータ

| パラメータ | 説明 |
|-----------|------|
| `df` | フィルタリング対象の DataFrame |
| `allowed_grades` | 許可する職位値のリスト |

#### grade_groups の参照

YAML に定義された `grade_groups` を参照することで、職位のエイリアスグループを使用できる。

```yaml
# YAML 設定例
grade_groups:
  non_managers:
    - 一般職A
    - 一般職B
    - 契約社員
```

`allowed_grades` に `non_managers` のようなグループ名が含まれる場合、`PrivilegeManager` が自動的に展開する。

### `apply_section_aliases(df, alias_mapping)`

課名を別の表示名に置換する。

#### 用途

- プライバシー保護のため、特定の課名を匿名化された名称に置換する
- 複数の課を一つの表示名に集約する（データの集約目的）

#### 適用タイミング

**section グルーピング時のみ**適用する。他のグルーピングには適用しない。

```python
# 適用例
if current_grouping == 'section':
    df = apply_section_aliases(df, alias_mapping)
```

#### `alias_mapping` の形式

```python
{
    '旧課名A': '新表示名X',
    '旧課名B': '新表示名X',  # 複数課を同一名に集約可能
    '旧課名C': '新表示名Y',
}
```

---

## 7. チームセクションオーバーライド

特定の `team` 列の値を、`section` グルーピング時に仮想セクションとして表示する機能。

### 用途

通常の section グルーピングでは `section` 列の値でグルーピングされるが、一部の組織では `team` 列を使って論理的なグルーピングを行いたい場合がある。チームセクションオーバーライドを使用すると、特定の `team` 値を持つデータを、あたかも別のセクションに属するかのように表示できる。

### 取得メソッド

```python
overrides = privilege_manager.get_team_section_overrides(privilege)
```

### YAML 設定例

```yaml
team_section_overrides:
  マネジメント:
    match_team: Management       # team 列でこの値にマッチする行を対象にする
    display_section: マネジメント  # section グルーピング時の表示セクション名
    visible_to: [all]            # このオーバーライドが適用される権限クラス
    visible_in_tabs:             # 適用されるタブ
      - 時系列
      - カテゴリ比較
      - 評価
      - 分布
    exclude_sections: [未設定]   # 注意: 現在は無効化されている
```

### 適用条件

- `grouping == 'section'` の時のみ適用する
- `visible_to` に現在の権限クラスが含まれる場合のみ適用する（`all` は全クラスに適用）
- `visible_in_tabs` に現在のタブが含まれる場合のみ適用する

### `exclude_sections` の現状

`exclude_sections` は設定ファイルに記述できるが、**現在は無効化されている**。

無効化の理由: サブセクションを持たない部署への対応。`exclude_sections` を有効にすると、該当するサブセクションなし部署でデータが意図せず除外されることが判明したため、無効化された。

将来的に再有効化する場合は、サブセクションなし部署への影響を十分に検証すること。

---

## 8. 適用レイヤー

`components.py` の `apply_grouping_filters()` 関数内で、フィルタリングは以下の順序で適用される。

```
Layer 1: グルーピングスコープ
    ↓ filter_dataframe_by_scope(df, grouping_scope_values, org_columns)
    ↓ grouping_scope または grouping_scope_filtered を使用
    ↓ (dimension_filtered の値によって切り替わる)

Layer 2: 職位フィルター (grade グルーピング時のみ)
    ↓ filter_dataframe_by_grade(df, allowed_grades)
    ↓ grade_groups 定義を参照して職位名を展開

Layer 3: セクションエイリアス (section グルーピング時のみ)
    ↓ apply_section_aliases(df, alias_mapping)
    ↓ 課名を表示用エイリアスに置換
```

### レイヤー適用の全体フロー図

```
入力: raw DataFrame (全データ)
    │
    ▼
[Layer 1] グルーピングスコープフィルター
    dimension_filtered == True  → grouping_scope_filtered を使用
    dimension_filtered == False → grouping_scope を使用
    ↓
フィルタリング済み DataFrame
    │
    ├─ grouping == 'grade' の場合
    │       ▼
    │   [Layer 2] 職位フィルター
    │       grade_groups を展開して filter_dataframe_by_grade を適用
    │
    └─ grouping == 'section' の場合
            ▼
        [Layer 3] セクションエイリアス
            apply_section_aliases を適用
    │
    ▼
出力: フィルタリング済み・整形済み DataFrame
```

### 各レイヤーが独立している理由

各レイヤーは独立した関数として実装されているため:
- 個別にテストできる
- 特定のグルーピングで特定レイヤーをスキップできる
- 将来的な新しいフィルタリングレイヤーの追加が容易

---

## 9. タブとグルーピングの許可

### タブの許可制御

```python
allowed_tabs = privilege_manager.get_allowed_tabs(privilege)
```

戻り値はユーザーが表示できるタブ名のリスト。このリストに含まれないタブはナビゲーションに表示されない。

`data_scope` で `type: none` を設定したタブも、`allowed_tabs` に含まれていれば UI 上は表示される（ただしデータは空になる）。タブ自体を非表示にするには `allowed_tabs` から除外する。

### グルーピングの許可制御

```python
allowed_groupings = privilege_manager.get_allowed_groupings(privilege)
```

戻り値はユーザーが使用できるグルーピング種類のリスト。このリストに含まれないグルーピングはドロップダウンに表示されない。

### タブの匿名化制御

```python
should_anonymize = privilege_manager.should_anonymize_tab(privilege, tab_name)
```

`True` の場合、そのタブ内では個人を特定できる情報（氏名等）を匿名化して表示する。

---

## 10. 注意事項とよくある問題

### 問題 1: スコープ値に課名以外が含まれる場合

**症状**: 部長ユーザーでデータが正しく表示されない。部署内のデータが一部欠損する。

**原因**: `scope_values` には部署名・部門名が含まれる場合があるが、`section` 列のみでフィルタリングしている。

**対策**: 必ず `filter_dataframe_by_scope()` を使用し、`org_columns` に `division`・`department`・`section` の全列を指定する。

```python
# 正しい実装
filtered_df = filter_dataframe_by_scope(
    df,
    scope_values,
    org_columns=['division', 'department', 'section']
)

# 間違った実装 (使用しないこと)
filtered_df = df[df['section'].isin(scope_values)]
```

### 問題 2: コメントデータの組織列名が異なる

**症状**: コメントデータのスコープフィルタリングが機能しない。

**原因**: コメントデータの DataFrame は `current_division`・`current_department`・`current_section` のような `current_*` プレフィックス付きの列名を持つ場合がある。

**対策**: スコープフィルタリングを適用する前に、列名を標準名（`division`・`department`・`section`）にマッピングする。

```python
# 列名のマッピング例
column_mapping = {
    'current_division': 'division',
    'current_department': 'department',
    'current_section': 'section',
}
comment_df = comment_df.rename(columns=column_mapping)
filtered_comment_df = filter_dataframe_by_scope(comment_df, scope_values)
```

### 問題 3: signal_df のフィルタリング

**症状**: シグナルデータのフィルタリングで意図しないデータが含まれる・除外される。

**原因**: `signal_df` は組織列を持たない場合があり、`filter_dataframe_by_scope()` を直接適用できない。

**対策**: `signal_df` のフィルタリングは `mail_address` ベースで行う。スコープに対応するユーザーのメールアドレスリストを取得し、`mail_address` 列でフィルタリングする。

```python
# signal_df のフィルタリング例
allowed_mail_addresses = get_mail_addresses_for_scope(scope_values, org_df)
filtered_signal_df = signal_df[signal_df['mail_address'].isin(allowed_mail_addresses)]
```

### 問題 4: 設定変更後に privileges.yaml を再生成し忘れる

**症状**: `privileges_configuration.md` を変更したのに動作が変わらない。

**原因**: `privileges.yaml` が古い状態のまま。

**対策**: 設定変更後は必ず以下を実行する。

```bash
python tools/generate_privileges_yaml.py
```

変更内容をコミットする際は `privileges_configuration.md` と `privileges.yaml` の両方をコミットする。

### 問題 5: 継承の深いマージで予期しない設定が残る

**症状**: 子クラスで設定を上書きしたつもりだが、親クラスの設定が残っている。

**原因**: 深いマージではネストされたキーが個別にマージされる。親クラスのネストされたキーを完全に削除したい場合は、子クラスで明示的に空の値または別の値を指定する必要がある。

**対策**: 設定を削除するのではなく、明示的に上書きする。

```yaml
# 親クラスで定義された設定
parent_class:
  data_scope:
    評価:
      type: values
      values: [SW課]

# 子クラスで評価タブのスコープを無効化したい場合
child_class:
  inherits: parent_class
  data_scope:
    評価:
      type: none  # 空リストを返すよう明示的に上書き
```

### 問題 6: `exclude_sections` が機能しない

**症状**: `exclude_sections` に設定した値が除外されない。

**原因**: `exclude_sections` は現在無効化されている（[7章参照](#7-チームセクションオーバーライド)）。

**対策**: 現時点では `exclude_sections` は使用できない。この機能が必要な場合は、別のアプローチを検討するか、無効化を解除する前にサブセクションなし部署への影響を検証すること。

---

## 付録: 設定変更のワークフロー

```
1. config/privileges_configuration.md を編集する
        ↓
2. python tools/generate_privileges_yaml.py を実行する
        ↓
3. config/privileges.yaml の差分を確認する (git diff)
        ↓
4. アプリケーションをローカルで起動して動作を確認する
        ↓
5. privileges_configuration.md と privileges.yaml の両方をコミットする
```

---

*最終更新: 2026-03-08*
