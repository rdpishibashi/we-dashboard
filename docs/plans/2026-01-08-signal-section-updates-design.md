# Signal Section Updates Design

**Date:** 2026-01-08
**Project:** Work Engagement Analysis Dashboard
**Scope:** Add signal/intervention priority displays and remove deprecated features

## Overview

Update the dashboard to display intervention signals for individuals requiring attention based on their engagement trends. Remove CSV download and summary statistics sections per new requirements.

## Requirements

1. Delete CSV download functionality in the "データ" (Data) report
2. Delete "期間サマリー" section in the "時系列" (Time Series) report
3. Add "シグナル" section to "時系列" and "グループ比較" reports when "個人別" grouping is selected
4. Add "シグナル" section to "個人" report showing latest wave data
5. Delete "統計サマリー" in the "個人" report
6. "Latest wave" is defined as the latest year-month from the global period filter (end date)

## Data Sources

### rating2 Sheet Structure

The signal data comes from the `rating2` sheet in the Excel input file with these key columns:

**Identity:**
- year, month
- mail_address, name
- Current organization fields (current_division, current_department, current_section, current_team, current_project, grade)

**Engagement Metrics:**
- engagement_rating, vigor_rating, dedication_rating, absorption_rating

**Signal Indicators:**
- intervention_priority: Priority level for intervention (show only if > 1)
- trend_refined: Medium-term trend
- change_tag: Short-term change indicator
- stability: Medium-term stability

**Contextual Information:**
- strength_short, weakness_short: Short-term strengths and weaknesses
- strength_mid, weakness_mid: Medium-term strengths and weaknesses

## Architecture

### Data Loading Enhancement

Modify `load_data()` function to load both sheets:

```python
@st.cache_data
def load_data(uploaded_file):
    # Existing rating sheet loading (unchanged)
    pivot_df = # ... existing code ...

    # Load rating2 sheet
    signal_df = pd.read_excel(uploaded_file, sheet_name='rating2')
    signal_df['year'] = signal_df['year'].astype(int)
    signal_df['month'] = signal_df['month'].astype(int)
    signal_df['year_month'] = (
        signal_df['year'].astype(str) + '-' +
        signal_df['month'].astype(str).str.zfill(2)
    )
    signal_df['year_month_dt'] = pd.to_datetime(
        signal_df['year_month'], format='%Y-%m', errors='coerce'
    )

    return pivot_df, signal_df
```

### Column Label Mapping

Create constant for Japanese labels:

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

### Helper Function

Create function to filter signal data based on active filters:

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
    valid_names = filtered_df['name'].unique()
    latest_wave = latest_wave[latest_wave['name'].isin(valid_names)]

    # Filter to intervention priority > 1
    signals = latest_wave[latest_wave['intervention_priority'] > 1].copy()

    # Sort by priority descending
    signals = signals.sort_values('intervention_priority', ascending=False)

    return signals
```

## Implementation Plan by Tab

### 1. データ (Data) Tab

**Remove:**
- CSV download button (lines 1135-1141)

**Keep:**
- Dataframe display with column selector
- All other functionality unchanged

### 2. 時系列 (Time Series) Tab

**Remove:**
- "期間サマリー" section with 4-column metrics (lines 905-931)

**Add:**
- Conditional "シグナル" section after the time series chart
- Only display when `ts_group_choice == 'name'`

**Signal Section Layout:**
```
st.subheader("シグナル（介入優先度 > 1）")

signals = get_signal_data(signal_df, ts_df, end_dt)

if signals.empty:
    st.info("シグナル対象者はいません")
else:
    display_df = signals[['name', 'intervention_priority',
                          'trend_refined', 'change_tag', 'stability']]
    display_df = display_df.rename(columns=SIGNAL_LABELS)
    st.dataframe(display_df, use_container_width=True)
```

### 3. グループ比較 (Group Comparison) Tab

**Add:**
- Same "シグナル" section as 時系列 tab
- Display when `comparison_group == 'name'`
- Section appears after the comparison chart

### 4. 個人 (Individual) Tab

**Remove:**
- "統計サマリー" section showing describe() stats and change rate (lines 1084-1101)

**Add:**
- "シグナル" section below the individual trend chart
- Show latest wave data for selected individual

**Signal Section Layout:**

```
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
        st.metric("ワーク･エンゲージメント", f"{data['engagement_rating']:.1f}")
    with col2:
        st.metric("活力", f"{data['vigor_rating']:.1f}")
    with col3:
        st.metric("熱意", f"{data['dedication_rating']:.1f}")
    with col4:
        st.metric("没頭", f"{data['absorption_rating']:.1f}")

    # Row 2: Signal indicators
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("介入優先度", f"{data['intervention_priority']:.0f}")
    with col2:
        st.metric("中期トレンド", data['trend_refined'])
    with col3:
        st.metric("短期変動", data['change_tag'])
    with col4:
        st.metric("中期安定性", data['stability'])

    # Row 3: Strengths and weaknesses
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("強み・弱み（短期）"):
            st.write("**強み:**", data['strength_short'])
            st.write("**弱み:**", data['weakness_short'])
    with col2:
        with st.expander("強み・弱み（中期）"):
            st.write("**強み:**", data['strength_mid'])
            st.write("**弱み:**", data['weakness_mid'])
```

## Signal Data Filtering Logic

The signal section displays individuals meeting ALL criteria:

1. **Global Filter Compliance:** Individual passes all active sidebar filters (period, section, department, group, team, project, grade)
2. **Latest Wave Presence:** Individual has data for the latest wave (year_month == end_dt from period slider)
3. **Intervention Threshold:** Individual has intervention_priority > 1

This ensures the signal section only shows actionable alerts for individuals currently visible in the filtered dataset.

## Testing Considerations

1. **Empty State Handling:** Verify appropriate messages when no signals exist
2. **Filter Interaction:** Confirm signals update when sidebar filters change
3. **Period Selection:** Validate "latest wave" correctly uses end_dt from slider
4. **Missing Data:** Handle cases where individuals lack rating2 data
5. **Column Presence:** Ensure all expected columns exist in rating2 sheet

## Migration Notes

**Breaking Changes:**
- CSV download removed (users should use Excel file directly if raw data export needed)
- Period summary statistics removed (users can view summary metrics in other tabs)
- Individual statistics removed (signal data provides more actionable insights)

**Data Dependencies:**
- Requires rating2 sheet in Excel input file
- All signal columns must be present in rating2 sheet

## Future Enhancements (Out of Scope)

- Downloadable signal reports
- Historical signal tracking
- Alert threshold customization
- Signal trend visualization
