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
Load Data → Global Filters → Per-Tab Filters → Per-Grouping Filters → Display
```

1. `df`, `signal_df`, `comment_df` loaded from Excel
2. Global filters applied → `filtered_df`, `filtered_signal_df`, `filtered_comment_df`
3. Per-tab privilege scope applied → `tab_filtered_df`
4. Per-grouping scope and grade filter applied
5. Section aliases applied if configured

### Filter Hierarchy (Global Filters)
```
部門 (Division) → 部署 (Department) → 課 (Section) → チーム (Team) → プロジェクト (Project) → 職位 (Grade)
```

**Important**: Use `sync_filter_selection()` pattern to sync child filters when parent changes. See `~/.claude/skills/streamlit/SKILL.md`.

## Important Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application |
| `modules/privilege_manager.py` | Privilege-based filtering logic |
| `modules/auth.py` | Authentication (user login) |
| `modules/config.py` | Configuration constants |
| `config/privileges_configuration.md` | **Source of truth** for privileges |
| `config/privileges.yaml` | Generated privilege config |
| `tools/generate_privileges_yaml.py` | Generates YAML from markdown |

## UI Structure

### Sidebar (Global Filters)
- 期間 (Period slider) - always visible
- 表示指標 (Metric selector) - always visible
- 組織フィルター (collapsible) - 部門, 部署, 課, チーム, プロジェクト, 職位

### Tabs
- 時系列 - Time series charts
- グループ比較 - Group comparison
- 評価 - Evaluation/ratings
- 分布 - Distribution
- 個人 - Individual view

### Sections within tabs
- 計測値 - Measured values
- 主な指標 - Key indicators
- アクション対象候補 - Action candidates (signals)
- 気になった出来事や気づき - Concerns (admin only)
- 共有したいこと - Shared comments

## Key Implementation Details

### Anonymous User Handling
```python
current_privilege = get_current_privilege() if is_authenticated() else 'anonymous'
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
