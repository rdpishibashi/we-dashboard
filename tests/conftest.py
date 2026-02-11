"""
Shared test fixtures for WE-Dashboard tests.

Provides:
- Real data loaded from EngagementMasterSS.xlsx
- Fresh PrivilegeManager instances
- Helper functions for simulating the filter chain
"""

import io
import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.privilege_manager import (
    PrivilegeManager, filter_dataframe_by_scope, filter_dataframe_by_grade
)

EXCEL_FILE = PROJECT_ROOT / 'EngagementMasterSS.xlsx'
EXCEL_PASSWORD = 'hachioji'


def _decrypt_and_load(sheet_name: str) -> pd.DataFrame:
    """Decrypt and load a sheet from the Excel file."""
    import msoffcrypto

    with open(EXCEL_FILE, 'rb') as f:
        file_data = io.BytesIO(f.read())
    decrypted = io.BytesIO()
    office_file = msoffcrypto.OfficeFile(file_data)
    office_file.load_key(password=EXCEL_PASSWORD)
    office_file.decrypt(decrypted)
    decrypted.seek(0)
    return pd.read_excel(decrypted, sheet_name=sheet_name, engine='openpyxl')


def _build_pivot_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Build pivot DataFrame from raw rating2 data by normalizing ratings."""
    from modules.config import ENGAGEMENT_DIVISOR, COMPONENT_DIVISOR

    df = raw_df.copy()
    df['year'] = df['year'].astype(int)
    df['month'] = df['month'].astype(int)

    for src, dst in [
        ('current_division', 'division'),
        ('current_department', 'department'),
        ('current_section', 'section'),
        ('current_team', 'team'),
        ('current_project', 'project'),
    ]:
        df[dst] = raw_df[src] if src in raw_df.columns else None

    if 'grade' not in df.columns:
        df['grade'] = None

    fill_cols = ['division', 'department', 'section', 'team', 'project', 'grade']
    for col in fill_cols:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].fillna('未設定')

    rating_cols = ['engagement_rating', 'vigor_rating', 'dedication_rating', 'absorption_rating']
    id_cols = ['year', 'month', 'name', 'division', 'department', 'section',
               'team', 'project', 'grade']
    if 'mail_address' in df.columns:
        id_cols.insert(2, 'mail_address')

    pivot_df = df[id_cols + rating_cols].copy()

    pivot_df['engagement_rating'] = pivot_df['engagement_rating'] / ENGAGEMENT_DIVISOR
    pivot_df['vigor_rating'] = pivot_df['vigor_rating'] / COMPONENT_DIVISOR
    pivot_df['dedication_rating'] = pivot_df['dedication_rating'] / COMPONENT_DIVISOR
    pivot_df['absorption_rating'] = pivot_df['absorption_rating'] / COMPONENT_DIVISOR

    pivot_df['year_month'] = (
        pivot_df['year'].astype(int).astype(str) + '-'
        + pivot_df['month'].astype(int).astype(str).str.zfill(2)
    )
    pivot_df['year_month_dt'] = pd.to_datetime(
        pivot_df['year_month'], format='%Y-%m', errors='coerce'
    )
    return pivot_df


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def real_df():
    """Load the real pivot DataFrame from EngagementMasterSS.xlsx (cached per session)."""
    if not EXCEL_FILE.exists():
        pytest.skip(f'{EXCEL_FILE} not found')
    raw = _decrypt_and_load('rating2')
    return _build_pivot_df(raw)


@pytest.fixture
def pm():
    """Fresh PrivilegeManager for each test."""
    PrivilegeManager._instance = None
    manager = PrivilegeManager()
    return manager


@pytest.fixture
def filter_chain(real_df, pm):
    """Return a callable that runs the full filter chain with real data + pm pre-bound.

    Usage in tests:
        df = filter_chain('soft', '時系列', 'すべて', '職位別')
    """
    def _run(privilege, tab, dimension_value, grouping):
        return simulate_filter_chain(real_df, pm, privilege, tab, dimension_value, grouping)
    return _run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Grouping name → internal key (same mapping as utils.py / components.py)
GROUPING_KEY_MAP = {
    'なし': 'なし',
    '部署別': 'department',
    '課別': 'section',
    'チーム別': 'team',
    'プロジェクト別': 'project',
    '職位別': 'grade',
    '個人別': 'name',
}


def simulate_filter_chain(
    base_df: pd.DataFrame,
    pm: PrivilegeManager,
    privilege: str,
    tab: str,
    dimension_value: str,
    grouping: str,
) -> pd.DataFrame:
    """
    Simulate the full filtering chain used in the app:
      sidebar dimension filter → tab scope → grouping scope → grade filter.

    Args:
        base_df: Full pivot DataFrame
        pm: PrivilegeManager instance
        privilege: e.g. 'soft', 'me1', 'admin'
        tab: Tab name (時系列, グループ比較, 評価, 分布, 個人)
        dimension_value: Sidebar 課/チーム/プロジェクト value ('すべて' or specific)
        grouping: Display grouping (なし, 部署別, 職位別, etc.)

    Returns:
        Filtered DataFrame
    """
    # 1. Sidebar dimension filter
    if dimension_value != 'すべて':
        df = base_df[base_df['section'] == dimension_value].copy()
    else:
        df = base_df.copy()

    # 2. Tab scope
    tab_scope = pm.get_data_scope_for_tab(privilege, tab)
    df = filter_dataframe_by_scope(df, tab_scope)

    # 3. Grouping scope (conditional on dimension filter)
    dimension_filtered = dimension_value != 'すべて'
    grouping_internal = GROUPING_KEY_MAP.get(grouping, grouping)
    grouping_scope = pm.get_grouping_scope(privilege, grouping_internal, dimension_filtered)
    df = filter_dataframe_by_scope(df, grouping_scope)

    # 4. Grade filter (only for grade grouping)
    if grouping_internal == 'grade':
        grade_filter = pm.get_grade_filter_for_grouping(
            privilege, grouping_internal, dimension_filtered
        )
        if grade_filter:
            df = filter_dataframe_by_grade(df, grade_filter)

    return df
