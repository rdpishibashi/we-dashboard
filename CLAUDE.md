# WE-Dashboard Project Context

## Project Overview
Work Engagement Dashboard - A Streamlit-based analytics application for visualizing employee engagement data with privilege-based access control.

## Key Architecture

### Privilege System
- **Source of truth**: `config/privileges_configuration.md` (markdown tables)
- **Generated config**: `config/privileges.yaml` (auto-generated)
- **Generator**: `tools/generate_privileges_yaml.py`
- **Manager**: `modules/privilege_manager.py` (singleton pattern)

#### Privilege Features
| Feature | Description |
|---------|-------------|
| `data_scope` | Per-tab data visibility |
| `grouping_scope` | Per-grouping data visibility |
| `section_scope` | Per-UI-section data visibility |
| `grade_filter` | Filter by grade (e.g., non_managers only) |
| `anonymize` | Hide individual names in comments |
| `section_aliases` | Combine sections under display names |

#### Key Privilege Classes
- `admin` - Full access
- `anonymous` - No data access (unauthenticated users)
- `department_head` (sd, me, dev) - Department-level access
- `section_manager` (sw, pd, me1-3, dev1-2, uti, uks) - Section-level access
- `member` (soft, prod, mechele1-3) - Limited access with grade filter
- `member_no_grade_filter` (develop1-2) - Limited access without grade filter

### Data Flow
```
Login → Sidebar (Period, Metric, Grouping, Filters) → Per-Tab Privilege Scope → Display
```

1. **Pre-login**: Welcome page with usage instructions (no dashboard)
2. **Post-login**: Full dashboard with sidebar controls and `st.tabs()`
3. `df`, `signal_df`, `comment_df` loaded from Excel
4. Unified sidebar filters applied → `filtered_df`, `filtered_signal_df` (shared by all tabs)
5. Per-tab privilege scope applied → `tab_filtered_df`
6. 表示カテゴリ (grouping) controls visualization per tab
7. Grade filter, section aliases applied if configured

### Unified Filter System (Sidebar)
**Cascade Order**: 部門 → 職位 → 部署 → 課 → チーム → プロジェクト → 個人

- All filters are **selectboxes** with "すべて" (all) option
- **課, チーム, プロジェクト** are separate cascading dropdowns (not a dimension selector)
- **個人 filter**: When selected, affects ALL tabs (not just 個人 tab)
- **Privilege-based**: Filter options restricted by user's data_scope
- **Cascading**: Parent changes reset children automatically

## Important Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application |
| `modules/filter_helpers.py` | Unified filter cascade logic |
| `modules/privilege_manager.py` | Privilege-based filtering logic |
| `modules/auth.py` | Authentication (user login) |
| `modules/config.py` | Configuration constants |
| `modules/utils.py` | Utility functions (grouping selector, etc.) |
| `config/privileges_configuration.md` | **Source of truth** for privileges |
| `config/privileges.yaml` | Generated privilege config |
| `tools/generate_privileges_yaml.py` | Generates YAML from markdown |

## UI Structure

### Pre-Login
- Unauthenticated users see a **welcome page** with usage instructions
- Sidebar shows only the login expander — no filters, no tabs

### Sidebar (Authenticated)
```
1. ログイン (login expander)
2. 期間 (period slider)
3. 表示指標 (metric selectbox)
4. 表示カテゴリ (grouping selectbox) — controls chart aggregation
5. ── separator ──
6. フィルター設定 (expander, collapsed by default):
     部門 → 職位 → 部署 → 課 → チーム → プロジェクト → 個人
7. データ (expander) — file upload
8. 期間＆有効データ info box
9. ── separator ──
10. Footer ©RDPi
```

### Tabs (st.tabs)
- **時系列** - Time series charts
- **カテゴリ比較** - Group comparison
- **評価** - Evaluation/ratings
- **分布** - Distribution
- **個人** - Individual view

Tabs use `st.tabs()` (pill-style bar). All tab content renders on every rerun.
表示カテゴリ in the sidebar controls how data is aggregated/visualized across all tabs.

### Sections within tabs
- 計測値 - Measured values
- 主な指標 - Key indicators
- アクション対象候補 - Action candidates (signals)
- 気になった出来事や気づき - Concerns (admin only)
- 共有したいこと - Shared comments

## Key Implementation Details

### Anonymous User Handling
Unauthenticated users see a welcome page — the dashboard is not rendered at all.
```python
if not is_authenticated():
    # Show welcome page
else:
    current_privilege = get_current_privilege()
    # ... full dashboard
```

### Comment Display (共有したいこと)
- **With names**: Section → Name → Year-month → Comment
- **Anonymized**: Section → Year-month → Comments (grouped)
- Sorted by year-month descending (latest first)

### Grade Filtering
When `grade_filter: non_managers` is set, only show these grades:
- サプライヤー, 一般職, 主任, 主事補, 主事, 主管

## Deployment

### Streamlit Cloud
- Platform: Streamlit Cloud
- Config: `.streamlit/config.toml`
- Secrets: Streamlit Cloud dashboard

### Requirements
All dependencies must be in `requirements.txt`:
```
streamlit>=1.28.0
pandas>=2.0.0
pyyaml>=6.0.0  # Required for yaml module
...
```

## Development Workflow

### Updating Privileges
1. Edit `config/privileges_configuration.md`
2. Run `python tools/generate_privileges_yaml.py`
3. Test locally
4. Deploy

### Adding New Features
1. Check privilege requirements
2. Update `privilege_manager.py` if needed
3. Apply filtering in `app.py`
4. Test with different privilege levels

## Streamlit Patterns
See `~/.claude/skills/streamlit/SKILL.md` for reusable patterns:
- Session state management
- Hierarchical filter synchronization
- Sidebar organization
- Multiple data source filtering

## Recent Changes (2025-01)
- Added grade filtering for member class privileges
- Added name anonymization for 共有したいこと section
- Fixed global filter synchronization
- Added collapsible organization filters
- Fixed signal_df and comment_df not being filtered by global filters
- Comments now sorted by year-month descending (latest first)
- Anonymized comments grouped by year-month

## Recent Changes (2026-02)
- **Pre-login welcome page**: Unauthenticated users see instructions instead of dashboard
- **st.tabs()**: Switched from `st.radio("レポート種別")` to `st.tabs()` (pill-style bar)
- **Sidebar restructured**: 表示カテゴリ (grouping) moved before filters; フィルター設定 wrapped in expander (collapsed by default)
- **Separate dimension filters**: Replaced グループ（絞り込み軸）meta-selector with three independent cascading dropdowns: 課, チーム, プロジェクト
- **Session state keys**: `unified_dimension` / `unified_dimension_value` replaced by `unified_section`, `unified_team`, `unified_project`
