"""
Unit tests for PrivilegeManager

Run with: python -m pytest tests/test_privilege_manager.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.privilege_manager import PrivilegeManager, DataScope, get_privilege_manager


@pytest.fixture
def pm():
    """Get a fresh PrivilegeManager instance for each test."""
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
        config = pm.get_privilege_config('sw')
        # Should have tabs config from inheritance chain
        assert 'tabs' in config
        assert 'data_scope' in config

    def test_member_inherits_from_section_manager(self, pm):
        """Member should inherit section_manager privileges."""
        # soft is a member
        config = pm.get_privilege_config('soft')
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
        scope = pm.get_data_scope('sw', '時系列')
        assert scope.type == 'organization'
        # Should include both departments
        assert 'システム開発部' in scope.values
        assert '機電設計部' in scope.values

    def test_section_manager_narrower_scope_on_individual(self, pm):
        """Section manager should see only section data on 個人 tab."""
        # sw is a section manager for ソフトウェア開発課
        scope = pm.get_data_scope('sw', '個人')
        assert scope.type == 'organization'
        # Should only include their section
        assert 'ソフトウェア開発課' in scope.values
        # Should NOT include departments
        assert 'システム開発部' not in scope.values

    def test_admin_has_all_scope(self, pm):
        """Admin should have 'all' scope regardless of tab."""
        for tab in ['時系列', 'グループ比較', '評価', '個人', '分布']:
            scope = pm.get_data_scope('admin', tab)
            assert scope.type == 'all'

    def test_anonymous_has_no_scope(self, pm):
        """Anonymous should have 'none' scope."""
        scope = pm.get_data_scope(None, '時系列')
        assert scope.type == 'none'


class TestGradeFiltering:
    """Test grade filtering for members."""

    def test_member_only_sees_non_manager_grades(self, pm):
        """Members should only see non-manager grades in 職位別 grouping."""
        all_grades = [
            'サプライヤー', '一般職', '主任', '主事補', '主事', '主管',
            '特命職', '特命職・専門職', 'エキスパート', '課長', '部長'
        ]
        filtered = pm.filter_grades('soft', all_grades)

        # Non-manager grades should be visible
        assert 'サプライヤー' in filtered
        assert '一般職' in filtered
        assert '主任' in filtered
        assert '主事補' in filtered
        assert '主事' in filtered
        assert '主管' in filtered

        # Manager grades should be filtered out
        assert '特命職' not in filtered
        assert '課長' not in filtered
        assert '部長' not in filtered

    def test_section_manager_sees_all_grades(self, pm):
        """Section managers should see all grades."""
        all_grades = [
            'サプライヤー', '一般職', '主任', '主事補', '主事', '主管',
            '特命職', '特命職・専門職', 'エキスパート', '課長', '部長'
        ]
        filtered = pm.filter_grades('sw', all_grades)

        # All grades should be visible
        assert len(filtered) == len(all_grades)

    def test_admin_sees_all_grades(self, pm):
        """Admin should see all grades."""
        all_grades = [
            'サプライヤー', '一般職', '主任', '主事補', '主事', '主管',
            '特命職', '特命職・専門職', 'エキスパート', '課長', '部長'
        ]
        filtered = pm.filter_grades('admin', all_grades)

        # All grades should be visible
        assert len(filtered) == len(all_grades)


class TestAnonymousComments:
    """Test comment anonymization flags."""

    def test_member_comments_anonymized(self, pm):
        """Members should have comments anonymized."""
        assert pm.should_anonymize_comments('soft') is True

    def test_section_manager_comments_not_anonymized(self, pm):
        """Section managers should see author names."""
        assert pm.should_anonymize_comments('sw') is False

    def test_admin_comments_not_anonymized(self, pm):
        """Admin should see author names."""
        assert pm.should_anonymize_comments('admin') is False


class TestSectionAliases:
    """Test section alias visibility."""

    def test_dev1_sees_combined_section_alias(self, pm):
        """dev1 should see combined section alias for 評価/分布 tabs."""
        aliases = pm.get_section_aliases('dev1', '評価')

        # Should have at least one alias
        assert len(aliases) > 0

        # Should see the dev1-related alias
        alias_names = [a['display_name'] for a in aliases]
        assert '開発部 1課・UTI技術発展処' in alias_names

    def test_admin_sees_all_aliases(self, pm):
        """Admin should see all section aliases."""
        aliases = pm.get_section_aliases('admin', '評価')

        # Admin should see both combined sections
        alias_names = [a['display_name'] for a in aliases]
        assert '開発部 1課・UTI技術発展処' in alias_names
        assert '開発部 2課・UK S1-Project' in alias_names

    def test_alias_not_visible_outside_specified_tabs(self, pm):
        """Section aliases should not be visible on non-specified tabs."""
        # The aliases are only visible in 評価 and 分布 tabs
        aliases = pm.get_section_aliases('dev1', '時系列')

        # Should be empty (no aliases visible for this tab)
        assert len(aliases) == 0


class TestFeatureAccess:
    """Test feature access control."""

    def test_admin_can_access_concern_feature(self, pm):
        """Admin should access 気になった出来事や気づき."""
        assert pm.can_access_feature('admin', '気になった出来事や気づき') is True

    def test_section_manager_cannot_access_concern_feature(self, pm):
        """Section managers should NOT access 気になった出来事や気づき."""
        assert pm.can_access_feature('sw', '気になった出来事や気づき') is False

    def test_member_cannot_access_concern_feature(self, pm):
        """Members should NOT access 気になった出来事や気づき."""
        assert pm.can_access_feature('soft', '気になった出来事や気づき') is False

    def test_all_authenticated_can_access_share_feature(self, pm):
        """All authenticated users should access 共有したいこと."""
        assert pm.can_access_feature('admin', '共有したいこと') is True
        assert pm.can_access_feature('sw', '共有したいこと') is True
        assert pm.can_access_feature('soft', '共有したいこと') is True


class TestAutoResetFilters:
    """Test auto-reset filter functionality."""

    def test_section_manager_reset_on_tab_change(self, pm):
        """Section manager should reset filters when switching from wide to narrow tabs."""
        # From 時系列 (wide) to 個人 (narrow)
        reset_to = pm.should_auto_reset_filters('sw', '時系列', '個人')
        assert reset_to == 'user_section'

    def test_no_reset_on_same_scope_tabs(self, pm):
        """No reset when switching between tabs with same scope."""
        # From 時系列 to グループ比較 (both wide)
        reset_to = pm.should_auto_reset_filters('sw', '時系列', 'グループ比較')
        assert reset_to is None

    def test_admin_no_reset(self, pm):
        """Admin should not have auto-reset."""
        reset_to = pm.should_auto_reset_filters('admin', '時系列', '個人')
        assert reset_to is None


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


class TestDataScope:
    """Test DataScope class."""

    def test_from_dict_organization(self):
        """Test creating DataScope from dict."""
        scope = DataScope.from_dict({
            'type': 'organization',
            'values': ['部署A', '部署B']
        })
        assert scope.type == 'organization'
        assert scope.values == ['部署A', '部署B']

    def test_from_dict_all(self):
        """Test creating DataScope with all type."""
        scope = DataScope.from_dict({'type': 'all'})
        assert scope.type == 'all'
        assert scope.values == []

    def test_static_all(self):
        """Test DataScope.all() factory method."""
        scope = DataScope.all()
        assert scope.type == 'all'

    def test_static_none(self):
        """Test DataScope.none() factory method."""
        scope = DataScope.none()
        assert scope.type == 'none'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
