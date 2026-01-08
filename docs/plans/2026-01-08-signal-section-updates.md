# Signal Section Updates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add intervention signal displays to dashboard reports and remove deprecated features.

**Architecture:** Extend data loading to include rating2 sheet with signal indicators, add conditional signal sections to three report tabs, remove CSV download and summary statistics.

**Tech Stack:** Streamlit, Pandas, Plotly

---

## Task 1: Add Signal Data Loading

**Files:**
- Modify: `app.py:197-262` (load_data function)

**Step 1: Update load_data function signature to return both dataframes**

Modify the `load_data` function to load the rating2 sheet and return both dataframes:

```python
@st.cache_data
def load_data(uploaded_file):
    """データファイルの読み込みと整形"""
    # Existing rating sheet loading code (lines 200-262) stays unchanged
    raw_df = pd.read_excel(uploaded_file, sheet_name='rating')
    # ... all existing code ...
    pivot_df['year_month_dt'] = pd.to_datetime(pivot_df['year_month'], format='%Y-%m', errors='coerce')

    # Load rating2 sheet for signal data
    signal_df = pd.read_excel(uploaded_file, sheet_name='rating2')
    signal_df['year'] = pd.to_numeric(signal_df['year'], errors='coerce').astype(int)
    signal_df['month'] = pd.to_numeric(signal_df['month'], errors='coerce').astype(int)
    signal_df['year_month'] = (
        signal_df['year'].astype(str) + '-' +
        signal_df['month'].astype(str).str.zfill(2)
    )
    signal_df['year_month_dt'] = pd.to_datetime(
        signal_df['year_month'], format='%Y-%m', errors='coerce'
    )

    # Fill missing values for organizational columns
    fill_cols = ['current_division', 'current_department', 'current_section',
                 'current_team', 'current_project', 'grade']
    for col in fill_cols:
        if col in signal_df.columns:
            signal_df[col] = signal_df[col].fillna('未設定')

    # Map to consistent column names
    signal_df['section'] = signal_df.get('current_division', pd.Series([None] * len(signal_df)))
    signal_df['department'] = signal_df.get('current_department', pd.Series([None] * len(signal_df)))
    signal_df['group'] = signal_df.get('current_section', pd.Series([None] * len(signal_df)))
    signal_df['team'] = signal_df.get('current_team', pd.Series([None] * len(signal_df)))
    signal_df['project'] = signal_df.get('current_project', pd.Series([None] * len(signal_df)))

    return pivot_df, signal_df
```

**Step 2: Update all calls to load_data to unpack both dataframes**

Find the line around 754 where load_data is called:
```python
df = load_data(uploaded_file)
```

Replace with:
```python
df, signal_df = load_data(uploaded_file)
```

**Step 3: Test data loading**

Run: `streamlit run app.py`

Expected:
- App loads without errors
- Default data loads successfully
- No visible changes to UI yet

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: load rating2 sheet for signal data

Load signal indicators from rating2 sheet including intervention
priority, trends, and stability metrics.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Add Signal Label Constants and Helper Function

**Files:**
- Modify: `app.py:44-54` (after METRIC_LABELS constant)

**Step 1: Add SIGNAL_LABELS constant**

Add after the METRIC_LABELS constant (around line 49):

```python
SIGNAL_LABELS = {
    'name': '氏名',
    'intervention_priority': '介入優先度',
    'trend_refined': '中期トレンド',
    'change_tag': '短期変動',
    'stability': '中期安定性',
    'engagement_rating': 'ワーク･エンゲージメント',
    'vigor_rating': '活力',
    'dedication_rating': '熱意',
    'absorption_rating': '没頭',
    'strength_short': '強み（短期）',
    'weakness_short': '弱み（短期）',
    'strength_mid': '強み（中期）',
    'weakness_mid': '弱み（中期）'
}
```

**Step 2: Add helper function to filter signal data**

Add before the main application section (around line 730):

```python
def get_signal_data(signal_df, filtered_df, end_dt):
    """
    Filter signal data to match current sidebar filters and latest wave.

    Args:
        signal_df: Full rating2 dataframe
        filtered_df: Currently filtered rating dataframe (from sidebar filters)
        end_dt: End date of global period filter (defines "latest wave")

    Returns:
        Filtered signal dataframe for individuals with intervention_priority > 1
    """
    # Filter to latest wave
    latest_wave = signal_df[signal_df['year_month_dt'] == end_dt].copy()

    # Apply same filters as main data by matching on available individuals
    valid_names = filtered_df['name'].dropna().unique()
    latest_wave = latest_wave[latest_wave['name'].isin(valid_names)]

    # Filter to intervention priority > 1
    signals = latest_wave[latest_wave['intervention_priority'] > 1].copy()

    # Sort by priority descending
    signals = signals.sort_values('intervention_priority', ascending=False)

    return signals
```

**Step 3: Test the app still loads**

Run: `streamlit run app.py`

Expected:
- App loads without errors
- No functional changes yet

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add signal labels and filtering helper

Add Japanese label mappings for signal fields and helper function
to filter signal data based on active filters.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Remove CSV Download from データ Tab

**Files:**
- Modify: `app.py:1103-1142` (データ tab section)

**Step 1: Remove CSV download button**

Find the CSV download section (lines 1135-1141):

```python
csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
st.download_button(
    "📥 CSVダウンロード",
    csv,
    "filtered_data.csv",
    "text/csv"
)
```

Delete these lines entirely.

**Step 2: Test データ tab**

Run: `streamlit run app.py`

Expected:
- Navigate to データ tab
- Dataframe displays correctly
- CSV download button is gone
- Column selector still works

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: remove CSV download from データ tab

Remove CSV download functionality per requirements.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Remove Period Summary from 時系列 Tab

**Files:**
- Modify: `app.py:886-932` (時系列 tab section)

**Step 1: Remove period summary section**

Find the "期間サマリー" section (lines 905-931):

```python
st.subheader("期間サマリー")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "ワーク･エンゲージメント 平均値",
        f"{ts_df['engagement_rating'].mean():.1f}" if not ts_df.empty else "N/A",
        f"SD: {ts_df['engagement_rating'].std():.1f}" if not ts_df.empty else "N/A"
    )
# ... rest of the metrics ...
```

Delete from `st.subheader("期間サマリー")` through the end of the last `st.metric()` call.

**Step 2: Test 時系列 tab**

Run: `streamlit run app.py`

Expected:
- Navigate to 時系列 tab
- Time series chart displays
- Period summary section is gone
- No errors

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: remove period summary from 時系列 tab

Remove period summary statistics section per requirements.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Add Signal Section to 時系列 Tab

**Files:**
- Modify: `app.py:886-904` (時系列 tab section)

**Step 1: Add signal section after time series chart**

After the `st.plotly_chart(fig, **PLOTLY_CHART_KWARGS)` line (around line 903), add:

```python
# Signal section - only show when grouping by individual
if ts_group_choice == 'name':
    st.subheader("シグナル（介入優先度 > 1）")

    signals = get_signal_data(signal_df, ts_df, end_dt)

    if signals.empty:
        st.info("シグナル対象者はいません")
    else:
        display_cols = ['name', 'intervention_priority', 'trend_refined',
                       'change_tag', 'stability']
        display_df = signals[display_cols].copy()
        display_df = display_df.rename(columns=SIGNAL_LABELS)
        st.dataframe(display_df, use_container_width=True)
```

**Step 2: Test signal section in 時系列 tab**

Run: `streamlit run app.py`

Test cases:
1. Navigate to 時系列 tab
2. Select グルーピング = "なし" → Signal section should NOT appear
3. Select グルーピング = "個人別" → Signal section should appear
4. Verify table shows correct columns with Japanese labels
5. Change period filter → Signal data should update

Expected:
- Signal section only appears when grouping is "個人別"
- Table displays individuals with intervention_priority > 1
- Columns show Japanese labels
- Data updates with filter changes

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add signal section to 時系列 tab

Display intervention signals when grouping by individual.
Shows individuals with priority > 1 from latest wave.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Add Signal Section to グループ比較 Tab

**Files:**
- Modify: `app.py:933-951` (グループ比較 tab section)

**Step 1: Add signal section after comparison chart**

After the `st.plotly_chart(comparison_fig, **PLOTLY_CHART_KWARGS)` line (around line 951), add:

```python
# Signal section - only show when grouping by individual
if comparison_group == 'name':
    st.subheader("シグナル（介入優先度 > 1）")

    signals = get_signal_data(signal_df, comparison_df, end_dt)

    if signals.empty:
        st.info("シグナル対象者はいません")
    else:
        display_cols = ['name', 'intervention_priority', 'trend_refined',
                       'change_tag', 'stability']
        display_df = signals[display_cols].copy()
        display_df = display_df.rename(columns=SIGNAL_LABELS)
        st.dataframe(display_df, use_container_width=True)
```

**Step 2: Test signal section in グループ比較 tab**

Run: `streamlit run app.py`

Test cases:
1. Navigate to グループ比較 tab
2. Select グルーピング = "部署別" → Signal section should NOT appear
3. Select グルーピング = "個人別" → Signal section should appear
4. Verify table shows correct data
5. Apply department/section filters → Signal data should filter accordingly

Expected:
- Signal section only appears when grouping is "個人別"
- Table displays filtered individuals
- Respects all active filters

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add signal section to グループ比較 tab

Display intervention signals when grouping by individual.
Consistent with 時系列 tab implementation.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Update 個人 Tab - Remove Statistics and Add Signal Section

**Files:**
- Modify: `app.py:1042-1102` (個人 tab section)

**Step 1: Remove statistics summary section**

Find the "統計サマリー" section (lines 1084-1101):

```python
st.subheader(f"{selected_individual}の統計サマリー")

col1, col2 = st.columns(2)
with col1:
    st.dataframe(
        ind_data[['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']].describe().round(2)
    )
with col2:
    if len(ind_data) > 1:
        first = ind_data.iloc[0]['engagement_rating']
        last = ind_data.iloc[-1]['engagement_rating']
        change = ((last - first) / first * 100) if first != 0 else 0
        st.metric(
            "ワーク･エンゲージメント変化率",
            f"{change:+.1f}%",
            f"初回: {first:.1f} → 最新: {last:.1f}"
        )
```

Delete from `st.subheader(f"{selected_individual}の統計サマリー")` through the end of this section.

**Step 2: Add signal section after individual trend chart**

After the section where ind_data is defined (around line 1084), add:

```python
# Signal section
st.subheader("シグナル")

individual_signal = signal_df[
    (signal_df['name'] == selected_individual) &
    (signal_df['year_month_dt'] == end_dt)
]

if individual_signal.empty:
    st.info("最新データがありません")
else:
    data = individual_signal.iloc[0]

    # Row 1: Engagement metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        val = data['engagement_rating']
        st.metric("ワーク･エンゲージメント", f"{val:.1f}" if pd.notna(val) else "N/A")
    with col2:
        val = data['vigor_rating']
        st.metric("活力", f"{val:.1f}" if pd.notna(val) else "N/A")
    with col3:
        val = data['dedication_rating']
        st.metric("熱意", f"{val:.1f}" if pd.notna(val) else "N/A")
    with col4:
        val = data['absorption_rating']
        st.metric("没頭", f"{val:.1f}" if pd.notna(val) else "N/A")

    # Row 2: Signal indicators
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        val = data['intervention_priority']
        st.metric("介入優先度", f"{val:.0f}" if pd.notna(val) else "N/A")
    with col2:
        val = data['trend_refined']
        st.metric("中期トレンド", str(val) if pd.notna(val) else "N/A")
    with col3:
        val = data['change_tag']
        st.metric("短期変動", str(val) if pd.notna(val) else "N/A")
    with col4:
        val = data['stability']
        st.metric("中期安定性", str(val) if pd.notna(val) else "N/A")

    # Row 3: Strengths and weaknesses
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("強み・弱み（短期）", expanded=False):
            strength = data.get('strength_short', '')
            weakness = data.get('weakness_short', '')
            if pd.notna(strength) and str(strength).strip():
                st.write("**強み:**", strength)
            else:
                st.write("**強み:** データなし")
            if pd.notna(weakness) and str(weakness).strip():
                st.write("**弱み:**", weakness)
            else:
                st.write("**弱み:** データなし")
    with col2:
        with st.expander("強み・弱み（中期）", expanded=False):
            strength = data.get('strength_mid', '')
            weakness = data.get('weakness_mid', '')
            if pd.notna(strength) and str(strength).strip():
                st.write("**強み:**", strength)
            else:
                st.write("**強み:** データなし")
            if pd.notna(weakness) and str(weakness).strip():
                st.write("**弱み:**", weakness)
            else:
                st.write("**弱み:** データなし")
```

**Step 3: Test 個人 tab**

Run: `streamlit run app.py`

Test cases:
1. Navigate to 個人 tab
2. Select an individual
3. Verify trend chart displays
4. Verify signal section appears below chart
5. Check all four rows of metrics display correctly
6. Expand strength/weakness sections
7. Select different individual → Signal data should update
8. Change period filter → Signal data should reflect latest wave

Expected:
- Statistics summary is gone
- Signal section displays with 4 metrics, 4 indicators, and 2 expandable sections
- Data updates when individual or filters change
- Handles missing data gracefully (shows "N/A" or "データなし")

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: replace statistics with signal section in 個人 tab

Remove statistics summary and add comprehensive signal display
showing engagement metrics, intervention indicators, and
strengths/weaknesses.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Final Integration Testing

**Step 1: Comprehensive testing across all tabs**

Run: `streamlit run app.py`

Test matrix:

**時系列 Tab:**
- [ ] Time series chart displays
- [ ] Period summary is removed
- [ ] Signal section appears only when grouping = "個人別"
- [ ] Signal table shows correct individuals with priority > 1
- [ ] Changing filters updates signal data

**グループ比較 Tab:**
- [ ] Comparison chart displays
- [ ] Signal section appears only when grouping = "個人別"
- [ ] Signal table matches filtered individuals
- [ ] Department/section filters affect signal data

**分布 Tab:**
- [ ] No changes, functions normally
- [ ] Box plot and histogram display

**評価 Tab:**
- [ ] No changes, functions normally
- [ ] Rating bands and radar chart display

**個人 Tab:**
- [ ] Individual trend chart displays
- [ ] Statistics summary is removed
- [ ] Signal section displays with all metrics
- [ ] Engagement metrics (4 columns) show correctly
- [ ] Signal indicators (4 columns) show correctly
- [ ] Strength/weakness expanders work
- [ ] Handles missing data gracefully

**データ Tab:**
- [ ] CSV download is removed
- [ ] Dataframe displays correctly
- [ ] Column selector works

**Global Filters:**
- [ ] Period slider affects "latest wave" in signal sections
- [ ] Section/department/group filters affect signal visibility
- [ ] All combinations work correctly

**Step 2: Edge case testing**

Test edge cases:
- [ ] No individuals with intervention_priority > 1 → Shows "シグナル対象者はいません"
- [ ] Individual without latest wave data → Shows "最新データがありません"
- [ ] Empty filtered dataset → Handles gracefully
- [ ] Missing strength/weakness fields → Shows "データなし"

**Step 3: Document any issues found**

If issues found, create follow-up tasks in this plan. Otherwise, proceed to commit.

**Step 4: Final commit**

```bash
git add app.py
git commit -m "test: verify all signal section features

Comprehensive testing across all tabs confirms:
- Signal sections display correctly
- Filtering logic works as expected
- Deprecated features removed
- Edge cases handled gracefully

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `README.md`

**Step 1: Update README with new features**

Add to the features section (around line 5):

```markdown
### 🚨 シグナル機能
- 介入優先度に基づく個人アラート表示
- 最新期間のトレンド・変動・安定性指標
- 個人別の強み・弱み分析
```

Update the data format section to mention rating2 sheet:

```markdown
## データ形式

### rating シート
アップロードするExcelファイルは**EngagementMasterSS.xlsx形式**（`rating`シート）を想定しています。

### rating2 シート
介入シグナル用の補足データを`rating2`シートから読み込みます。以下のカラムが必要です:
- intervention_priority: 介入優先度
- trend_refined: 中期トレンド
- change_tag: 短期変動
- stability: 中期安定性
- strength_short, weakness_short: 短期の強み・弱み
- strength_mid, weakness_mid: 中期の強み・弱み
```

**Step 2: Commit documentation**

```bash
git add README.md
git commit -m "docs: update README with signal features

Document new signal section functionality and rating2
sheet requirements.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary

**Total commits:** 9
**Estimated time:** 45-60 minutes
**Testing approach:** Manual integration testing (no automated tests for Streamlit app)

**Key principles applied:**
- ✅ YAGNI: Only implementing requested features, no extras
- ✅ DRY: Reusable helper function for signal filtering
- ✅ Incremental commits: Each task is independently testable
- ✅ Manual testing: Comprehensive checklist for each feature

**Files modified:**
- `app.py`: All feature changes
- `README.md`: Documentation updates

**Next steps after implementation:**
- Use @superpowers:requesting-code-review to review changes
- Use @superpowers:finishing-a-development-branch to merge or create PR
