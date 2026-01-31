# WE-Dashboard Project Context

## Project Overview
Work Engagement Dashboard - A Streamlit-based analytics application for visualizing employee engagement data with privilege-based access control.

## Key Architecture

### Privilege System
- Configuration: `config/privileges.yaml` (auto-generated from `docs/privileges_configuration.md`)
- Manager: `modules/privilege_manager.py` (singleton pattern)
- Generator: `tools/generate_privileges_yaml.py`

### Data Flow
1. Main data (`df`) → filtered by global filters → `filtered_df`
2. Signal data (`signal_df`) → must also be filtered → `filtered_signal_df`
3. Comment data (`comment_df`) → must also be filtered → `filtered_comment_df`

### Filter Hierarchy
```
部門 (Division) → 部署 (Department) → 課 (Section) → チーム (Team) → プロジェクト (Project) → 職位 (Grade)
```
Child filters must sync when parent changes (see `sync_filter_selection` pattern in app.py).

## Important Files
- `app.py` - Main Streamlit application
- `modules/privilege_manager.py` - Privilege-based filtering
- `modules/auth.py` - Authentication
- `modules/config.py` - Configuration constants
- `docs/privileges_configuration.md` - Source of truth for privileges

## Deployment
- Platform: Streamlit Cloud
- Requirements: `requirements.txt` (remember to add all dependencies like `pyyaml`)

## Streamlit Patterns Used
See `~/.claude/skills/streamlit/SKILL.md` for reusable Streamlit development patterns.
