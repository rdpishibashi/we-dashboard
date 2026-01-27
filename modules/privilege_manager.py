"""
Privilege Manager for Work Engagement Dashboard
Provides centralized privilege management with YAML-based configuration.
"""

import yaml
from pathlib import Path
from typing import Optional, Any
from functools import lru_cache
from dataclasses import dataclass


# Path to configuration file
CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'privileges.yaml'

# All available tabs
ALL_TABS = ["時系列", "グループ比較", "評価", "個人", "分布"]

# All available groupings
ALL_GROUPINGS = ['なし', 'department', 'section', 'team', 'project', 'grade', 'name']


@dataclass
class DataScope:
    """Represents a data scope configuration."""
    type: str  # 'all', 'organization', 'none'
    values: list[str]  # List of allowed organization names

    @classmethod
    def from_dict(cls, data: dict) -> 'DataScope':
        return cls(
            type=data.get('type', 'organization'),
            values=data.get('values', [])
        )

    @classmethod
    def all(cls) -> 'DataScope':
        return cls(type='all', values=[])

    @classmethod
    def none(cls) -> 'DataScope':
        return cls(type='none', values=[])


class PrivilegeManager:
    """
    Manages privilege configuration and access control.

    Singleton pattern ensures configuration is loaded once and cached.
    """

    _instance: Optional['PrivilegeManager'] = None
    _config: Optional[dict] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            self._config = self._get_default_config()
        except yaml.YAMLError as e:
            print(f"Warning: Failed to parse privileges.yaml: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self) -> dict:
        """Return minimal default config as fallback."""
        return {
            'grade_groups': {
                'non_managers': [],
                'managers': []
            },
            'section_aliases': {},
            'privileges': {
                'admin': {
                    'tabs': {'allowed': 'all'},
                    'data_scope': {'default': {'type': 'all'}},
                    'groupings': {'allowed': 'all'},
                    'features': {
                        '気になった出来事や気づき': True,
                        '共有したいこと': {'access': True, 'anonymize': False}
                    }
                },
                'anonymous': {
                    'tabs': {'allowed': []},
                    'data_scope': {'default': {'type': 'none'}},
                    'groupings': {'allowed': ['なし']},
                    'features': {
                        '気になった出来事や気づき': False,
                        '共有したいこと': {'access': False, 'anonymize': True}
                    }
                }
            },
            'user_privileges': {}
        }

    def reload_config(self):
        """Force reload of configuration (useful for testing)."""
        self._load_config()
        self._resolve_privilege_config.cache_clear()

    @lru_cache(maxsize=128)
    def _resolve_privilege_config(self, privilege: str) -> dict:
        """
        Resolve privilege configuration with inheritance.

        Args:
            privilege: Privilege identifier (e.g., 'sw', 'admin')

        Returns:
            Fully resolved privilege configuration dict
        """
        if privilege is None:
            return self._config['privileges'].get('anonymous', {})

        # Check if it's a user privilege
        user_config = self._config.get('user_privileges', {}).get(privilege, {})

        # Check if it's a base privilege class
        base_config = self._config.get('privileges', {}).get(privilege, {})

        # Determine base config
        if user_config:
            config = user_config.copy()
        elif base_config:
            config = base_config.copy()
        else:
            # Unknown privilege, return anonymous
            return self._config['privileges'].get('anonymous', {})

        # Resolve inheritance
        if 'inherits' in config:
            parent_privilege = config['inherits']
            parent_config = self._resolve_privilege_config(parent_privilege)
            config = self._merge_configs(parent_config, config)

        return config

    def _merge_configs(self, parent: dict, child: dict) -> dict:
        """
        Merge child configuration over parent configuration.

        Args:
            parent: Parent privilege configuration
            child: Child privilege configuration (overrides parent)

        Returns:
            Merged configuration
        """
        result = {}

        # Deep merge each key
        all_keys = set(parent.keys()) | set(child.keys())

        for key in all_keys:
            if key == 'inherits':
                continue  # Don't include inherits in merged result

            parent_val = parent.get(key)
            child_val = child.get(key)

            if child_val is None:
                result[key] = parent_val
            elif parent_val is None:
                result[key] = child_val
            elif isinstance(parent_val, dict) and isinstance(child_val, dict):
                # Deep merge for nested dicts
                result[key] = self._merge_configs(parent_val, child_val)
            else:
                # Child overrides parent
                result[key] = child_val

        return result

    def get_privilege_config(self, privilege: str) -> dict:
        """
        Get the full resolved configuration for a privilege.

        Args:
            privilege: User's privilege identifier

        Returns:
            Resolved privilege configuration dict
        """
        return self._resolve_privilege_config(privilege)

    def get_allowed_tabs(self, privilege: str) -> list[str]:
        """
        Get list of allowed tabs for a privilege.

        Args:
            privilege: User's privilege identifier

        Returns:
            List of allowed tab names
        """
        config = self.get_privilege_config(privilege)
        tabs_config = config.get('tabs', {})

        allowed = tabs_config.get('allowed', [])
        denied = tabs_config.get('denied', [])

        if allowed == 'all':
            allowed = ALL_TABS.copy()

        # Remove denied tabs
        return [t for t in allowed if t not in denied]

    def get_data_scope(self, privilege: str, tab: Optional[str] = None) -> DataScope:
        """
        Get data scope for a privilege and optional tab.

        Args:
            privilege: User's privilege identifier
            tab: Optional tab name for tab-specific scope

        Returns:
            DataScope object with type and allowed values
        """
        config = self.get_privilege_config(privilege)
        data_scope_config = config.get('data_scope', {})

        # Check for tab-specific scope first
        if tab and tab in data_scope_config:
            scope_data = data_scope_config[tab]
        else:
            scope_data = data_scope_config.get('default', {'type': 'none'})

        return DataScope.from_dict(scope_data)

    def get_section_scope(self, privilege: str, section: str) -> DataScope:
        """
        Get data scope for a specific UI section.

        Sections include:
        - 計測値 (Measured values)
        - 主な指標 (Main metrics)
        - アクション対象候補 (Action candidates)
        - 共有したいこと (Comments/things to share)

        Args:
            privilege: User's privilege identifier
            section: Section name

        Returns:
            DataScope object with type and allowed values
        """
        config = self.get_privilege_config(privilege)
        section_scope_config = config.get('section_scope', {})

        # Check for section-specific scope
        if section in section_scope_config:
            scope_data = section_scope_config[section]
        else:
            # Fall back to default data scope
            data_scope_config = config.get('data_scope', {})
            scope_data = data_scope_config.get('default', {'type': 'none'})

        return DataScope.from_dict(scope_data)

    def get_allowed_groupings(self, privilege: str, tab: Optional[str] = None) -> list[str]:
        """
        Get list of allowed groupings for a privilege.

        Args:
            privilege: User's privilege identifier
            tab: Optional tab name (reserved for future use)

        Returns:
            List of allowed grouping options
        """
        config = self.get_privilege_config(privilege)
        groupings_config = config.get('groupings', {})

        allowed = groupings_config.get('allowed', [])
        denied = groupings_config.get('denied', [])

        if allowed == 'all':
            allowed = ALL_GROUPINGS.copy()

        # Remove denied groupings
        return [g for g in allowed if g not in denied]

    def filter_grades(self, privilege: str, grades: list[str]) -> list[str]:
        """
        Filter grades based on privilege configuration.

        Members can only see non-manager grades in 職位別 grouping.

        Args:
            privilege: User's privilege identifier
            grades: List of all available grades

        Returns:
            Filtered list of grades visible to the user
        """
        config = self.get_privilege_config(privilege)
        groupings_config = config.get('groupings', {})
        grade_filter = groupings_config.get('grade_filter')

        if not grade_filter:
            return grades

        filter_type = grade_filter.get('type', 'include')
        values_from = grade_filter.get('values_from')

        if values_from:
            # Get values from grade_groups
            filter_values = self._config.get('grade_groups', {}).get(values_from, [])

            if filter_type == 'include':
                return [g for g in grades if g in filter_values]
            elif filter_type == 'exclude':
                return [g for g in grades if g not in filter_values]

        return grades

    def get_grade_group(self, group_name: str) -> list[str]:
        """
        Get grades in a named group.

        Args:
            group_name: Name of the grade group ('non_managers' or 'managers')

        Returns:
            List of grade names in the group
        """
        return self._config.get('grade_groups', {}).get(group_name, [])

    def get_section_aliases(self, privilege: str, tab: Optional[str] = None) -> list[dict]:
        """
        Get section aliases visible to a privilege in a specific tab.

        Args:
            privilege: User's privilege identifier
            tab: Tab name to filter visibility

        Returns:
            List of section alias dicts with display_name and members
        """
        aliases = []
        section_aliases = self._config.get('section_aliases', {})

        for alias_id, alias_config in section_aliases.items():
            visible_to = alias_config.get('visible_to', [])
            visible_in_tabs = alias_config.get('visible_in_tabs', [])

            # Check if privilege can see this alias
            if privilege not in visible_to and 'admin' not in visible_to:
                # Also check if privilege inherits from a visible privilege
                user_config = self._config.get('user_privileges', {}).get(privilege, {})
                if not user_config:
                    continue
                # Check direct privilege match
                if privilege not in visible_to:
                    continue

            # Check if tab matches (if tab filter is specified)
            if tab and visible_in_tabs and tab not in visible_in_tabs:
                continue

            aliases.append({
                'id': alias_id,
                'display_name': alias_config.get('display_name', alias_id),
                'members': alias_config.get('members', [])
            })

        return aliases

    def can_access_feature(self, privilege: str, feature: str) -> bool:
        """
        Check if a privilege can access a specific feature.

        Args:
            privilege: User's privilege identifier
            feature: Feature name (e.g., '気になった出来事や気づき')

        Returns:
            True if feature is accessible
        """
        config = self.get_privilege_config(privilege)
        features_config = config.get('features', {})
        feature_setting = features_config.get(feature, False)

        if isinstance(feature_setting, bool):
            return feature_setting
        elif isinstance(feature_setting, dict):
            return feature_setting.get('access', False)

        return False

    def should_anonymize_comments(self, privilege: str) -> bool:
        """
        Check if comments should be anonymized for a privilege.

        Args:
            privilege: User's privilege identifier

        Returns:
            True if comments should not show author names
        """
        config = self.get_privilege_config(privilege)
        features_config = config.get('features', {})
        comment_setting = features_config.get('共有したいこと', {})

        if isinstance(comment_setting, dict):
            return comment_setting.get('anonymize', False)

        return False

    def should_auto_reset_filters(
        self,
        privilege: str,
        from_tab: str,
        to_tab: str
    ) -> Optional[str]:
        """
        Check if filters should auto-reset when switching tabs.

        Args:
            privilege: User's privilege identifier
            from_tab: Tab user is switching from
            to_tab: Tab user is switching to

        Returns:
            'user_section' if should reset, None otherwise
        """
        config = self.get_privilege_config(privilege)
        auto_reset = config.get('auto_reset_filters', {})
        on_tab_change = auto_reset.get('on_tab_change', {})

        from_tabs = on_tab_change.get('from', [])
        to_tabs = on_tab_change.get('to', [])
        reset_to = on_tab_change.get('reset_to')

        if from_tab in from_tabs and to_tab in to_tabs:
            return reset_to

        return None

    def get_user_section_scope(self, privilege: str) -> list[str]:
        """
        Get the section-level scope for a user's privilege.

        Used for auto-resetting filters to the user's section when
        switching from wider-scope tabs to narrower-scope tabs.

        Args:
            privilege: User's privilege identifier

        Returns:
            List of section names the user has access to at section level
        """
        config = self.get_privilege_config(privilege)
        data_scope_config = config.get('data_scope', {})

        # Try to get section-level scope from 個人 tab scope
        individual_scope = data_scope_config.get('個人', {})
        if individual_scope:
            return individual_scope.get('values', [])

        # Fall back to default scope
        default_scope = data_scope_config.get('default', {})
        return default_scope.get('values', [])


# Singleton accessor
_privilege_manager: Optional[PrivilegeManager] = None


def get_privilege_manager() -> PrivilegeManager:
    """Get the singleton PrivilegeManager instance."""
    global _privilege_manager
    if _privilege_manager is None:
        _privilege_manager = PrivilegeManager()
    return _privilege_manager
