"""
Unit tests for PrivilegeManager

Run with: python -m pytest tests/test_privilege_manager.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.privilege_manager import PrivilegeManager, get_privilege_manager


@pytest.fixture
def pm():
    """Get a fresh PrivilegeManager instance for each test."""
    PrivilegeManager._instance = None
    manager = PrivilegeManager()
    manager.reload_config()
    return manager


class TestInheritanceResolution:
    """Test inheritance resolution in privilege configuration."""

    def test_admin_has_full_access(self, pm):
        """Admin should have access to all tabs."""
        tabs = pm.get_allowed_tabs('admin')
        assert '時系列' in tabs
        assert 'グループ比較' in tabs
        assert '評価' in tabs
        assert '個人' in tabs
        assert '分布' in tabs

    def test_section_manager_inherits_from_department_head(self, pm):
        """Section manager should inherit department_head privileges."""
        # sw is a section manager
        config = pm.get_effective_config('sw')
        # Should have tabs config from inheritance chain
        assert 'tabs' in config
        assert 'data_scope' in config

    def test_member_inherits_from_section_manager(self, pm):
        """Member should inherit section_manager privileges."""
        # soft is a member
        config = pm.get_effective_config('soft')
        assert 'tabs' in config

    def test_member_has_restricted_tabs(self, pm):
        """Members should have restricted tab access."""
        tabs = pm.get_allowed_tabs('soft')
        assert '時系列' in tabs
        assert 'グループ比較' in tabs
        assert '評価' in tabs
        # Members should NOT have access to 個人 and 分布
        assert '個人' not in tabs
        assert '分布' not in tabs

    def test_anonymous_has_no_tabs(self, pm):
        """Anonymous users should have no tab access."""
        tabs = pm.get_allowed_tabs(None)
        assert tabs == []


class TestPerTabDataScoping:
    """Test per-tab data scoping for section managers."""

    def test_section_manager_wider_scope_on_timeseries(self, pm):
        """Section manager should see department data on 時系列 tab."""
        # sw is a section manager for ソフトウェア開発課
        scope = pm.get_data_scope_for_tab('sw', '時系列')
        assert scope is not None  # Not 'all'
        assert len(scope) > 0  # Not 'none'
        # Should include both departments
        assert 'システム開発部' in scope
        assert '機電設計部' in scope

    def test_section_manager_narrower_scope_on_individual(self, pm):
        """Section manager should see only section data on 個人 tab."""
        # sw is a section manager for ソフトウェア開発課
        scope = pm.get_data_scope_for_tab('sw', '個人')
        assert scope is not None
        # Should only include their section
        assert 'ソフトウェア開発課' in scope
        # Should NOT include departments
        assert 'システム開発部' not in scope

    def test_admin_has_all_scope(self, pm):
        """Admin should have 'all' scope regardless of tab."""
        for tab in ['時系列', 'グループ比較', '評価', '個人', '分布']:
            scope = pm.get_data_scope_for_tab('admin', tab)
            # None means 'all' (no restriction)
            assert scope is None

    def test_anonymous_has_no_scope(self, pm):
        """Anonymous should have 'none' scope."""
        scope = pm.get_data_scope_for_tab(None, '時系列')
        # Empty list means 'none' (no access)
        assert scope == []


class TestGradeFiltering:
    """Test grade filtering for members."""

    def test_member_only_sees_non_manager_grades(self, pm):
        """Members should only see non-manager grades in 職位別 grouping."""
        grade_filter = pm.get_grade_filter_for_grouping('soft', 'grade')
        assert grade_filter is not None

        # Non-manager grades should be in the allowed list
        assert 'サプライヤー' in grade_filter
        assert '一般職' in grade_filter
        assert '主任' in grade_filter
        assert '主事補' in grade_filter
        assert '主事' in grade_filter
        assert '主管' in grade_filter

        # Manager grades should NOT be in the allowed list
        assert '特命職' not in grade_filter
        assert '課長' not in grade_filter
        assert '部長' not in grade_filter

    def test_section_manager_sees_all_grades(self, pm):
        """Section managers should see all grades (no grade filter)."""
        grade_filter = pm.get_grade_filter_for_grouping('sw', 'grade')
        # None means no grade filtering (all grades visible)
        assert grade_filter is None

    def test_admin_sees_all_grades(self, pm):
        """Admin should see all grades (no grade filter)."""
        grade_filter = pm.get_grade_filter_for_grouping('admin', 'grade')
        assert grade_filter is None


class TestAnonymousComments:
    """Test comment anonymization flags."""

    def test_member_comments_anonymized(self, pm):
        """Members should have comments anonymized."""
        assert pm.should_anonymize('soft', '共有したいこと') is True

    def test_section_manager_comments_not_anonymized(self, pm):
        """Section managers should see author names."""
        assert pm.should_anonymize('sw', '共有したいこと') is False

    def test_admin_comments_not_anonymized(self, pm):
        """Admin should see author names."""
        assert pm.should_anonymize('admin', '共有したいこと') is False


class TestSectionAliases:
    """Test section alias visibility."""

    def test_develop1_sees_combined_section_alias(self, pm):
        """develop1 should see combined section aliases."""
        aliases = pm.get_section_aliases('develop1', '評価')

        # Should have aliases (dict mapping section → display_name)
        assert len(aliases) > 0

        # Should see the develop1-related alias
        alias_display_names = set(aliases.values())
        assert '開発部 1課・UTI技術発展処' in alias_display_names

    def test_develop1_sees_all_aliases(self, pm):
        """develop1 should see both combined section aliases."""
        aliases = pm.get_section_aliases('develop1', '評価')

        alias_display_names = set(aliases.values())
        assert '開発部 1課・UTI技術発展処' in alias_display_names
        assert '開発部 2課・UK S1-Project' in alias_display_names

    def test_alias_not_visible_outside_specified_tabs(self, pm):
        """Section aliases should not be visible on non-specified tabs."""
        # The aliases are only visible in 時系列, グループ比較, 評価, 分布 tabs
        # 個人 tab is not in the list
        aliases = pm.get_section_aliases('develop1', '個人')

        # Should be empty (no aliases visible for this tab)
        assert len(aliases) == 0

    def test_non_listed_privilege_sees_no_aliases(self, pm):
        """Privileges not in visible_to should see no aliases."""
        # sw is not in visible_to list
        aliases = pm.get_section_aliases('sw', '評価')
        assert len(aliases) == 0


class TestFeatureAccess:
    """Test feature access control."""

    def test_admin_can_access_concern_feature(self, pm):
        """Admin should access 気になった出来事や気づき."""
        assert pm.has_feature_access('admin', '気になった出来事や気づき') is True

    def test_section_manager_cannot_access_concern_feature(self, pm):
        """Section managers should NOT access 気になった出来事や気づき."""
        assert pm.has_feature_access('sw', '気になった出来事や気づき') is False

    def test_member_cannot_access_concern_feature(self, pm):
        """Members should NOT access 気になった出来事や気づき."""
        assert pm.has_feature_access('soft', '気になった出来事や気づき') is False

    def test_all_authenticated_can_access_share_feature(self, pm):
        """Admin and section managers should access 共有したいこと."""
        assert pm.has_feature_access('admin', '共有したいこと') is True
        assert pm.has_feature_access('sw', '共有したいこと') is True
        assert pm.has_feature_access('soft', '共有したいこと') is True


class TestAllowedGroupings:
    """Test grouping option restrictions."""

    def test_admin_has_all_groupings(self, pm):
        """Admin should have access to all groupings."""
        groupings = pm.get_allowed_groupings('admin')
        assert 'なし' in groupings
        assert 'department' in groupings
        assert 'section' in groupings
        assert 'team' in groupings
        assert 'project' in groupings
        assert 'grade' in groupings
        assert 'name' in groupings

    def test_member_has_no_name_grouping(self, pm):
        """Members should NOT have access to name grouping."""
        groupings = pm.get_allowed_groupings('soft')
        assert 'name' not in groupings
        # But should have other groupings
        assert 'なし' in groupings
        assert 'department' in groupings
        assert 'grade' in groupings


class TestGetPrivilegeManager:
    """Test the singleton get_privilege_manager function."""

    def test_returns_instance(self):
        """get_privilege_manager should return a PrivilegeManager instance."""
        pm = get_privilege_manager()
        assert isinstance(pm, PrivilegeManager)

    def test_returns_same_instance(self):
        """get_privilege_manager should return the same instance each time."""
        pm1 = get_privilege_manager()
        pm2 = get_privilege_manager()
        assert pm1 is pm2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
