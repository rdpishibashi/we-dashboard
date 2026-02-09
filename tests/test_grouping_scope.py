"""
Tests for conditional grouping scope (= すべて / ≠ すべて).

Verifies that cross-section information leakage is prevented when a user
selects a specific 課/チーム/プロジェクト in the sidebar, by switching to
the more restrictive grouping_scope_filtered.

Run with:
    python -m pytest tests/test_grouping_scope.py -v

Requires:
    - EngagementMasterSS.xlsx in project root
    - config/privileges.yaml generated from privileges_configuration.md
"""

import pytest

NON_MANAGER_GRADES = {'サプライヤー', '一般職', '主任', '主事補', '主事', '主管'}
MANAGER_GRADES = {'特命職', '特命職・専門職', 'エキスパート', '課長', '部長'}


# =========================================================================
# Member class: soft (ソフトウェア開発課, grade_filter: non_managers)
# =========================================================================

class TestSoftMember:
    """soft — member in ソフトウェア開発課 with non-manager grade filter."""

    def test_subete_grade_aggregate(self, filter_chain):
        """課=すべて + 職位別 → aggregate grade distribution across SD+ME, non-managers only."""
        df = filter_chain('soft', '時系列', 'すべて', '職位別')
        assert len(df) > 0
        depts = set(df['department'].unique())
        assert depts <= {'システム開発部', '機電設計部'}
        grades = set(df['grade'].unique())
        assert grades <= NON_MANAGER_GRADES

    def test_own_section_grade(self, filter_chain):
        """課=ソフトウェア開発課 + 職位別 → own section's grade distribution, non-managers."""
        df = filter_chain('soft', '時系列', 'ソフトウェア開発課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'ソフトウェア開発課'}
        grades = set(df['grade'].unique())
        assert grades <= NON_MANAGER_GRADES

    def test_other_section_grade_blocked(self, filter_chain):
        """課=第一設計課 + 職位別 → empty (cross-section grade leak blocked)."""
        df = filter_chain('soft', '時系列', '第一設計課', '職位別')
        assert len(df) == 0

    def test_other_section_org_blocked(self, filter_chain):
        """課=第一設計課 + 部署別 → empty (organization scope = none)."""
        df = filter_chain('soft', '時系列', '第一設計課', '部署別')
        assert len(df) == 0

    def test_other_section_nashi_allowed(self, filter_chain):
        """課=第一設計課 + なし → data shows (なし grouping not restricted)."""
        df = filter_chain('soft', '時系列', '第一設計課', 'なし')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'第一設計課'}

    def test_own_section_nashi(self, filter_chain):
        """課=ソフトウェア開発課 + なし → data shows for own section."""
        df = filter_chain('soft', '時系列', 'ソフトウェア開発課', 'なし')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'ソフトウェア開発課'}


# =========================================================================
# Member class: prod (製品技術課, grade_filter: non_managers)
# =========================================================================

class TestProdMember:
    """prod — member in 製品技術課 with non-manager grade filter."""

    def test_own_section_grade(self, filter_chain):
        """課=製品技術課 + 職位別 → own section grades, non-managers only."""
        df = filter_chain('prod', '時系列', '製品技術課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'製品技術課'}
        assert set(df['grade'].unique()) <= NON_MANAGER_GRADES

    def test_other_section_grade_blocked(self, filter_chain):
        """課=ソフトウェア開発課 + 職位別 → empty (cross-section blocked)."""
        df = filter_chain('prod', '時系列', 'ソフトウェア開発課', '職位別')
        assert len(df) == 0


# =========================================================================
# Member class: mechele1 (第一設計課, grade_filter: non_managers)
# =========================================================================

class TestMechele1Member:
    """mechele1 — member in 第一設計課 with non-manager grade filter."""

    def test_own_section_grade(self, filter_chain):
        """課=第一設計課 + 職位別 → own section grades, non-managers."""
        df = filter_chain('mechele1', '時系列', '第一設計課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'第一設計課'}
        assert set(df['grade'].unique()) <= NON_MANAGER_GRADES

    def test_other_section_grade_blocked(self, filter_chain):
        """課=ソフトウェア開発課 + 職位別 → empty."""
        df = filter_chain('mechele1', '時系列', 'ソフトウェア開発課', '職位別')
        assert len(df) == 0

    def test_subete_grade_aggregate(self, filter_chain):
        """課=すべて + 職位別 → aggregate SD+ME non-managers."""
        df = filter_chain('mechele1', '時系列', 'すべて', '職位別')
        assert len(df) > 0
        depts = set(df['department'].unique())
        assert depts <= {'システム開発部', '機電設計部'}
        assert set(df['grade'].unique()) <= NON_MANAGER_GRADES


# =========================================================================
# Section manager: me1 (第一設計課)
# =========================================================================

class TestMe1SectionManager:
    """me1 — section manager for 第一設計課."""

    def test_subete_grade_all_grades(self, filter_chain):
        """課=すべて + 職位別 → aggregate SD+ME, all grade levels (no grade filter)."""
        df = filter_chain('me1', '時系列', 'すべて', '職位別')
        assert len(df) > 0
        depts = set(df['department'].unique())
        assert depts <= {'システム開発部', '機電設計部'}
        # Section managers see all grades including managers
        grades = set(df['grade'].unique())
        assert grades & MANAGER_GRADES  # should contain some manager grades

    def test_filtered_org_blocked(self, filter_chain):
        """課=第一設計課 + 部署別 → empty (organization scope = none in ≠すべて)."""
        df = filter_chain('me1', '時系列', '第一設計課', '部署別')
        assert len(df) == 0

    def test_filtered_grade_still_works(self, filter_chain):
        """課=第一設計課 + 職位別 → shows data (grade scope = SD+ME in ≠すべて)."""
        df = filter_chain('me1', '時系列', '第一設計課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'第一設計課'}


# =========================================================================
# Section manager: sw (ソフトウェア開発課)
# =========================================================================

class TestSwSectionManager:
    """sw — section manager for ソフトウェア開発課."""

    def test_filtered_org_own_section(self, filter_chain):
        """課=ソフトウェア開発課 + 部署別 → shows own section (org restricted to own)."""
        df = filter_chain('sw', '時系列', 'ソフトウェア開発課', '部署別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'ソフトウェア開発課'}

    def test_filtered_org_other_section_empty(self, filter_chain):
        """課=第一設計課 + 部署別 → empty (org scope=ソフトウェア開発課, no overlap)."""
        df = filter_chain('sw', '時系列', '第一設計課', '部署別')
        assert len(df) == 0


# =========================================================================
# Member (no grade filter): develop1 (開発部 1課)
# =========================================================================

class TestDevelop1Member:
    """develop1 — member in 開発部 without grade filter."""

    def test_subete_org(self, filter_chain):
        """課=すべて + 部署別 → shows 開発部 data."""
        df = filter_chain('develop1', '時系列', 'すべて', '部署別')
        assert len(df) > 0
        assert set(df['department'].unique()) == {'開発部'}

    def test_filtered_org_blocked(self, filter_chain):
        """課=開発部 1課 + 部署別 → empty (organization scope = none in ≠すべて)."""
        df = filter_chain('develop1', '時系列', '開発部 1課', '部署別')
        assert len(df) == 0

    def test_filtered_grade_own_sections(self, filter_chain):
        """課=開発部 1課 + 職位別 → shows data (grade scope = 開発部 1課 + UTI技術発展処)."""
        df = filter_chain('develop1', '時系列', '開発部 1課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'開発部 1課'}

    def test_subete_grade(self, filter_chain):
        """課=すべて + 職位別 → shows 開発部 data (no grade filter)."""
        df = filter_chain('develop1', '時系列', 'すべて', '職位別')
        assert len(df) > 0
        assert set(df['department'].unique()) == {'開発部'}
        # develop1 has no grade filter — should see all grades
        grades = set(df['grade'].unique())
        assert grades & MANAGER_GRADES


# =========================================================================
# Admin: no restrictions
# =========================================================================

class TestAdmin:
    """admin — full access, no restrictions."""

    def test_subete_all_data(self, filter_chain, real_df):
        """課=すべて + 職位別 → all data, no restrictions."""
        df = filter_chain('admin', '時系列', 'すべて', '職位別')
        assert len(df) == len(real_df)

    def test_filtered_still_all(self, filter_chain):
        """課=第一設計課 + 職位別 → only sidebar-filtered rows (no grouping restriction)."""
        df = filter_chain('admin', '時系列', '第一設計課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'第一設計課'}
        # Admin has no grade filter — whatever grades exist in this section are shown

    def test_filtered_org(self, filter_chain):
        """課=第一設計課 + 部署別 → data shows (admin has no restriction)."""
        df = filter_chain('admin', '時系列', '第一設計課', '部署別')
        assert len(df) > 0


# =========================================================================
# Department heads: no conditional scope (identical in both tables)
# =========================================================================

class TestDepartmentHead:
    """Department heads have identical scopes in both tables."""

    def test_sd_subete(self, filter_chain):
        """sd + 課=すべて + 職位別 → SD+ME data."""
        df = filter_chain('sd', '時系列', 'すべて', '職位別')
        assert len(df) > 0
        assert set(df['department'].unique()) <= {'システム開発部', '機電設計部'}

    def test_sd_filtered(self, filter_chain):
        """sd + 課=第一設計課 + 職位別 → same scope (no restriction change)."""
        df = filter_chain('sd', '時系列', '第一設計課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'第一設計課'}

    def test_dev_subete(self, filter_chain):
        """dev + 課=すべて + 部署別 → 開発部 data."""
        df = filter_chain('dev', '時系列', 'すべて', '部署別')
        assert len(df) > 0
        assert set(df['department'].unique()) == {'開発部'}

    def test_dev_filtered(self, filter_chain):
        """dev + 課=開発部 1課 + 部署別 → still shows (dept head has no restriction)."""
        df = filter_chain('dev', '時系列', '開発部 1課', '部署別')
        assert len(df) > 0


# =========================================================================
# Cross-tab consistency
# =========================================================================

class TestCrossTab:
    """Verify grouping scope applies consistently across tabs."""

    @pytest.mark.parametrize('tab', ['時系列', 'グループ比較', '評価'])
    def test_soft_blocked_across_tabs(self, filter_chain, tab):
        """soft + 課=第一設計課 + 職位別 → empty on ALL member-accessible tabs."""
        df = filter_chain('soft', tab, '第一設計課', '職位別')
        assert len(df) == 0

    @pytest.mark.parametrize('tab', ['時系列', 'グループ比較', '評価'])
    def test_soft_own_section_across_tabs(self, filter_chain, tab):
        """soft + 課=ソフトウェア開発課 + 職位別 → data on all member-accessible tabs."""
        df = filter_chain('soft', tab, 'ソフトウェア開発課', '職位別')
        assert len(df) > 0
        assert set(df['section'].unique()) == {'ソフトウェア開発課'}
