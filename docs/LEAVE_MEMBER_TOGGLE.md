# 転属・退職メンバー表示トグル 設計・実装仕様

## 概要

サイドバーに「転属・退職メンバーを含む」チェックボックスを設け、  
`leave` ステータスのメンバーのデータを表示/非表示に切り替える機能。

---

## データ設計

### メンバーステータスの3値

| `leave` 値 | 意味 | ダッシュボードでの扱い |
|---|---|---|
| `""` (空) | 在籍中 | 常に表示 |
| `"absence"` | 長期休職（在籍中） | 常に表示（非表示にしない） |
| `"leave"` | 退職・転属 | チェックボックスで表示/非表示を切り替え |

`absence` メンバーをチェックボックスの対象外にした理由：在籍中であり、復職後も継続してデータが追加されるため、非表示にすることは適切でない。

### データソース

| 情報 | ソース |
|---|---|
| leave ステータス | `config/members.yaml` （`member_loader.py` 経由） |
| エンゲージメントデータ | `Engagement Master.xlsx` の `rating2`/`comment` シート |
| 組織情報（退職後の復元用） | `config/members.yaml` |

`leave` ステータスの判定に Engagement Master.xlsx は使わない。  
Admin GAS が `EngagementMasterSS.rating2` の `current_*` フィールドをクリアするため、  
退職後のデータには正確な組織情報が含まれていない。

---

## 実装

### 処理フロー（app.py）

```
期間フィルター適用 (.copy() で真のコピーを作成)
↓
表示カテゴリ selectbox 描画
↓
「転属・退職メンバーを含む」checkbox 描画 → include_leave 取得
↓
if not include_leave:
    leave_addresses のメール行を filtered_df から除外
else:
    members.yaml の組織情報で退職メンバーの org フィールドを復元
↓
render_unified_sidebar_filters() 呼び出し
```

### leave_addresses の生成

```python
member_df = load_members()  # config/members.yaml から読み込み
leave_addresses = set()
if not member_df.empty and 'leave' in member_df.columns:
    leave_addresses = set(
        member_df[member_df['leave'] == 'leave']['mail_address'].dropna()
    )
```

### 組織情報の復元（チェックON時）

Admin GAS は退職メンバーの `current_*` フィールドを空文字 `""` にクリアする。  
`data_loader.py` の `fillna('未設定')` は NaN を変換するが、  
**Excel から読み込んだ空文字 `""` は NaN にならないため、`'未設定'` と `""` の両方を対象にする必要がある。**

```python
leave_member_info = member_df[member_df['leave'] == 'leave'][
    ['mail_address', 'division', 'department', 'section', 'team', 'project', 'grade']
].copy()

for col in ['division', 'department', 'section', 'team', 'project', 'grade']:
    addr_to_val = leave_member_info.set_index('mail_address')[col]
    for _fdf in [filtered_df, filtered_signal_df]:
        _leave_mask = _fdf['mail_address'].isin(leave_addresses)
        _empty_mask = _fdf[col].isin(['', '未設定']) | _fdf[col].isna()
        _mask = _leave_mask & _empty_mask
        if not _mask.any():
            continue
        _mapped = _fdf.loc[_mask, 'mail_address'].map(addr_to_val)
        _valid = _mapped[_mapped.notna() & (_mapped != '')]
        if not _valid.empty:
            _fdf.loc[_valid.index, col] = _valid
```

### members.yaml にないメンバーの扱い

退職・転属メンバーが `members.yaml` に存在しない場合（古い在籍者など）：
- `leave_addresses` に含まれないため、チェックOFF でも除外されない
- `members.yaml` に組織情報がないため、org フィールドは `'未設定'` のまま表示される
- これは仕様通りの動作

---

## member_loader.py のキャッシュ設計

### 問題（解決済み）

```python
# NG: _mtime は Streamlit によってハッシュ対象外 → キャッシュが無効化されない
@st.cache_data
def _load_members_impl(_mtime):
    ...
```

Streamlit の `@st.cache_data` は **`_` で始まるパラメータをハッシュ対象から除外する**（非ハッシュ引数の渡し方として設計された仕様）。  
キャッシュキーに使いたいパラメータには `_` プレフィックスを付けてはいけない。

```python
# OK: mtime がハッシュされ、ファイル更新時にキャッシュが無効化される
@st.cache_data
def _load_members_impl(mtime):
    ...
```

### 現在の実装

```python
_MEMBERS_YAML = Path(__file__).resolve().parent.parent / 'config' / 'members.yaml'

def _get_yaml_mtime():
    if _MEMBERS_YAML.exists():
        return _MEMBERS_YAML.stat().st_mtime
    return None

@st.cache_data
def _load_members_impl(mtime):
    """Load members from YAML. Cached by file modification time."""
    if not _MEMBERS_YAML.exists():
        return pd.DataFrame()
    with open(_MEMBERS_YAML, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    members = data.get('members', [])
    if not members:
        return pd.DataFrame()
    return pd.DataFrame(members).fillna('')

def load_members() -> pd.DataFrame:
    return _load_members_impl(_get_yaml_mtime())
```

---

## 設計上の重要な教訓

### 1. Streamlit ウィジェットは「描画してから読む」

**問題のあったパターン（filter_helpers.py）：**

```python
def render_unified_sidebar_filters(...):
    # ❌ セッション状態を先に読む
    include = st.session_state.get("include_leave_members", False)
    if not include:
        df = df[~df['mail_address'].isin(leave_addresses)]

    # ... 長い処理 ...

    # ❌ ウィジェットを後で描画
    st.sidebar.checkbox("転属・退職メンバーを含む", value=False, key="include_leave_members")
```

セッション状態の読み取りとウィジェットの描画がコード上は正しく見えても、  
Streamlit の実行モデルの中でセッション状態が期待通りの値にならないことがある。  
特に `value=False` をウィジェット呼び出し時に指定すると、バージョンや実行コンテキストによって  
セッション状態が上書きされる場合がある。

**正しいパターン（app.py）：**

```python
# ✅ ウィジェットを描画して値を取得
if "include_leave_members" not in st.session_state:
    st.session_state["include_leave_members"] = False
include_leave = st.sidebar.checkbox(
    "転属・退職メンバーを含む",
    key="include_leave_members"
    # value= は指定しない（session_state で管理）
)

# ✅ 取得した値をすぐに使ってフィルタリング
if not include_leave:
    filtered_df = filtered_df[~filtered_df['mail_address'].isin(leave_addresses)]
```

**原則：**
- ウィジェットの描画と値の利用は同じスコープで行う
- `value=` パラメータは使わず、初期値は `session_state` の初期化で管理する
- フィルタリングロジックを担うヘルパー関数にウィジェット描画を混在させない

### 2. チェックボックスと表示カテゴリの分離

チェックボックスが filter_helpers 内で表示カテゴリ selectbox と同じ関数に入っていたため、  
両者を切り離す必要があった。現在の設計：

- **app.py**: 表示カテゴリ selectbox + 転属・退職チェックボックス + leave フィルタリング
- **filter_helpers.py**: 組織フィルター（部門・部署・課・チーム・プロジェクト・職位・個人）のみ

### 3. pandas DataFrame の安全な変更

**`.copy()` なしでの代入は不安定：**

```python
# ❌ boolean indexing の結果はビューになる場合がある
filtered_df = df[period_mask]
filtered_df.loc[mask, col] = value  # SettingWithCopyWarning → 代入が失敗する場合がある
```

```python
# ✅ 明示的に .copy() でコピーを作成
filtered_df = df[period_mask].copy()
filtered_df.loc[mask, col] = value  # 安全
```

### 4. pandas のインデックス整合性

boolean 条件でマスクされた部分集合に対して演算するとき、形状の不一致が発生する。

```python
# ❌ _mask は全行数 (1143)、_valid.values は部分集合の行数 (42) → ValueError
_fdf.loc[_mask & _valid.values, col] = _mapped[_valid].values
```

```python
# ✅ インデックスベースで操作する
_mapped = _fdf.loc[_mask, 'mail_address'].map(addr_to_val)  # 部分集合のインデックスを保持
_valid = _mapped[_mapped.notna() & (_mapped != '')]          # さらに絞る
_fdf.loc[_valid.index, col] = _valid                         # インデックスで代入
```

---

## サイドバー表示順序

```
1. ログイン (expander)
2. 期間 (slider)
3. 表示指標 (selectbox)         ← app.py
4. 表示カテゴリ (selectbox)     ← app.py
5. 転属・退職メンバーを含む (checkbox) ← app.py
6. ─── separator ───
7. フィルター設定 (expander)    ← filter_helpers.py
     部門 → 部署 → 課 → チーム → プロジェクト → 職位 → 個人
8. データ (expander)
```

「転属・退職メンバーを含む」をフィルター設定の外（上）に配置する理由：  
このチェックボックスはデータ全体のスコープに影響するため、個別の組織フィルターより  
上位の設定として位置づける必要がある。フィルター設定の expander 内に入れると、  
チェックボックスの ON/OFF がフィルター選択肢の構築に先行して適用されない問題が生じる。

---

## Streamlit Cloud でのデータ準備（split_by_division.py）

### 問題と背景

Streamlit Cloud では、ユーザーが `tools/split_by_division.py` で生成した部門別ファイル  
（`EngagementData-{部門名}.xlsx`）をアップロードして使用する。

このスクリプトは当初、`current_division == division` でのみ行を抽出していた。  
Admin GAS は退職メンバーの `current_division` を空文字にクリアするため、  
**退職メンバーの行はどの部門ファイルにも含まれなかった**。  
チェックボックスをONにしても `filtered_df` に該当行がなく、表示されなかった。

### 修正内容

`split_by_division.py` を以下のように修正：

```python
# members.yaml から leave メンバーの mail_address → division マッピングを取得
leave_div_map = _load_leave_division_map()   # {mail: division}

# 各部門ファイルに以下を含める
active_mask = df["current_division"] == division          # 在籍メンバー
leave_mask  = df["mail_address"].isin(leave_addrs)        # その部門のleaveメンバー
filtered = df[active_mask | leave_mask].copy()
```

`config/members.yaml` の `division` フィールドを使って、leave メンバーを  
元の所属部門のファイルに含めることで、チェックボックスON時に正しく表示される。

### 設計上の注意

- `current_division` が空でも `members.yaml` に `division` があれば正しく分類される
- `members.yaml` に存在しない退職メンバー（古い在籍者）は引き続きどのファイルにも含まれない（仕様通り）
- ファイル再生成後、Streamlit Cloud に再アップロードする必要がある

---

## 関連ファイル

| ファイル | 役割 |
|---|---|
| `app.py` | チェックボックス描画、leave フィルタリング、org 情報復元 |
| `modules/member_loader.py` | `members.yaml` からメンバーリスト読み込み（mtime キャッシュ） |
| `modules/filter_helpers.py` | 組織フィルターカスケード（leave 処理は含まない） |
| `modules/components.py` | `render_non_respondents()` — leave メンバーを未記入者から除外 |
| `config/members.yaml` | メンバーステータスのソースオブトゥルース |
| `tools/generate_member_yaml.py` | `Member.xlsx` → `members.yaml` 生成 |
| `tools/split_by_division.py` | 部門別 Excel 生成（leave メンバーを members.yaml の division で振り分け） |

---

*最終更新: 2026-04-12*
