"""
Privilege Manager for Work Engagement Dashboard

Loads and manages privilege configurations from privileges.yaml,
providing per-tab and per-section data scope filtering.
"""

import yaml
from pathlib import Path
from typing import Optional, Union

# Path to privileges configuration
PRIVILEGES_FILE = Path(__file__).parent.parent / 'config' / 'privileges.yaml'


class PrivilegeManager:
    """Manages privilege-based access control using privileges.yaml configuration."""

    _instance = None
    _config = None

    def __new__(cls):
        """Singleton pattern to avoid reloading config."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Load privileges configuration from YAML file."""
        try:
            if PRIVILEGES_FILE.exists():
                with open(PRIVILEGES_FILE, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
            else:
                self._config = {}
        except Exception as e:
            print(f"Warning: Failed to load privileges.yaml: {e}")
            self._config = {}

    def reload_config(self):
        """Force reload of configuration."""
        self._load_config()

    def get_base_privilege(self, privilege_class: str) -> dict:
        """Get base privilege class definition."""
        privileges = self._config.get('privileges', {})
        return privileges.get(privilege_class, {})

    def get_user_privilege(self, username: str) -> dict:
        """Get user-specific privilege configuration."""
        user_privileges = self._config.get('user_privileges', {})
        return user_privileges.get(username, {})

    def _resolve_inheritance(self, user_config: dict) -> dict:
        """Resolve inheritance chain for a user configuration."""
        if not user_config:
            return {}

        inherits = user_config.get('inherits')
        if not inherits:
            return user_config.copy()

        # Get base class
        base_config = self.get_base_privilege(inherits)
        resolved = self._resolve_inheritance(base_config)

        # Merge user config on top of base (user config takes precedence)
        for key, value in user_config.items():
            if key == 'inherits':
                continue
            if isinstance(value, dict) and isinstance(resolved.get(key), dict):
                # Deep merge for dict values
                resolved[key] = {**resolved.get(key, {}), **value}
            else:
                resolved[key] = value

        return resolved

    def get_effective_config(self, privilege: str) -> dict:
        """
        Get effective configuration for a privilege, resolving inheritance.

        Args:
            privilege: User's privilege identifier (e.g., 'dev1', 'admin')

        Returns:
            Merged configuration dict with inheritance resolved
        """
        # Check if it's a base privilege class
        base = self.get_base_privilege(privilege)
        if base:
            return self._resolve_inheritance(base)

        # Check user privileges
        user_config = self.get_user_privilege(privilege)
        if user_config:
            return self._resolve_inheritance(user_config)

        # Default to anonymous
        return self._resolve_inheritance(self.get_base_privilege('anonymous'))

    def get_data_scope_for_tab(self, privilege: str, tab: str) -> Optional[list]:
        """
        Get allowed data scope values for a specific tab.

        Args:
            privilege: User's privilege identifier
            tab: Tab name (時系列, カテゴリ比較, 評価, 個人, 分布)

        Returns:
            None if all data allowed, list of allowed organization values,
            or empty list if no access
        """
        config = self.get_effective_config(privilege)
        data_scope = config.get('data_scope', {})

        # Check tab-specific scope first
        if tab in data_scope:
            tab_scope = data_scope[tab]
            if tab_scope.get('type') == 'all':
                return None
            elif tab_scope.get('type') == 'none':
                return []
            else:
                return tab_scope.get('values', [])

        # Fall back to default scope
        default_scope = data_scope.get('default', {})
        if default_scope.get('type') == 'all':
            return None
        elif default_scope.get('type') == 'none':
            return []
        else:
            return default_scope.get('values', [])

    def get_section_scope(self, privilege: str, section: str) -> Optional[list]:
        """
        Get allowed data scope for a specific UI section.

        Args:
            privilege: User's privilege identifier
            section: Section name (計測値, 主な指標, アクション対象候補, 幹部職に伝えたいこと)

        Returns:
            None if all data allowed, list of allowed organization values,
            or empty list if no access
        """
        config = self.get_effective_config(privilege)
        section_scope = config.get('section_scope', {})

        if section in section_scope:
            scope = section_scope[section]
            if scope.get('type') == 'all':
                return None
            elif scope.get('type') == 'none':
                return []
            else:
                return scope.get('values', [])

        return []

    def get_grouping_scope(self, privilege: str, grouping: str, dimension_filtered: bool = False) -> Optional[list]:
        """
        Get allowed data scope for a specific grouping type.

        Args:
            privilege: User's privilege identifier
            grouping: Grouping type (なし, department, section, team, project, grade, name)
            dimension_filtered: If True, use grouping_scope_filtered (≠すべて) when available

        Returns:
            None if all data allowed, list of allowed organization values,
            or empty list if no access
        """
        config = self.get_effective_config(privilege)
        if dimension_filtered:
            grouping_scope = config.get('grouping_scope_filtered', config.get('grouping_scope', {}))
        else:
            grouping_scope = config.get('grouping_scope', {})

        # Map grouping types to internal keys
        # department/section/team/project all use 'organization' scope
        grouping_key_map = {
            'なし': 'none',
            'department': 'organization',
            'section': 'organization',
            'team': 'organization',
            'project': 'organization',
            'grade': 'grade',
            'name': 'name'
        }

        internal_key = grouping_key_map.get(grouping, 'none')

        if internal_key in grouping_scope:
            scope = grouping_scope[internal_key]
            if scope.get('type') == 'all':
                return None
            elif scope.get('type') == 'none':
                return []
            else:
                return scope.get('values', [])

        # Fall back to 'none' scope or default
        if 'none' in grouping_scope:
            scope = grouping_scope['none']
            if scope.get('type') == 'all':
                return None
            elif scope.get('type') == 'none':
                return []
            else:
                return scope.get('values', [])

        return None  # No restriction if not specified

    def get_grade_filter_for_grouping(self, privilege: str, grouping: str, dimension_filtered: bool = False) -> Optional[list]:
        """
        Get grade filter values for a specific grouping type.

        Args:
            privilege: User's privilege identifier
            grouping: Grouping type (grade is the main one that uses this)
            dimension_filtered: If True, use grouping_scope_filtered (≠すべて) when available

        Returns:
            None if no grade filtering, or list of allowed grade values
        """
        config = self.get_effective_config(privilege)
        if dimension_filtered:
            grouping_scope = config.get('grouping_scope_filtered', config.get('grouping_scope', {}))
        else:
            grouping_scope = config.get('grouping_scope', {})

        # Map grouping types to internal keys
        grouping_key_map = {
            'なし': 'none',
            'department': 'organization',
            'section': 'organization',
            'team': 'organization',
            'project': 'organization',
            'grade': 'grade',
            'name': 'name'
        }

        internal_key = grouping_key_map.get(grouping, 'none')

        if internal_key in grouping_scope:
            scope = grouping_scope[internal_key]
            grade_filter = scope.get('grade_filter')
            if grade_filter:
                # grade_filter can be 'non_managers' string or config dict
                if isinstance(grade_filter, str):
                    grade_groups = self._config.get('grade_groups', {})
                    return grade_groups.get(grade_filter, [])
                elif isinstance(grade_filter, dict):
                    values_from = grade_filter.get('values_from')
                    if values_from:
                        grade_groups = self._config.get('grade_groups', {})
                        return grade_groups.get(values_from, [])

        # Also check groupings config for grade_filter
        groupings_config = config.get('groupings', {})
        grade_filter = groupings_config.get('grade_filter')
        if grade_filter:
            if isinstance(grade_filter, dict):
                values_from = grade_filter.get('values_from')
                if values_from:
                    grade_groups = self._config.get('grade_groups', {})
                    return grade_groups.get(values_from, [])

        return None

    def should_anonymize_section(self, privilege: str, section: str) -> bool:
        """
        Check if data should be anonymized for a specific section.

        Args:
            privilege: User's privilege identifier
            section: Section name (計測値, 主な指標, アクション対象候補, 幹部職に伝えたいこと)

        Returns:
            True if anonymization is required
        """
        config = self.get_effective_config(privilege)
        section_scope = config.get('section_scope', {})

        if section in section_scope:
            scope = section_scope[section]
            return scope.get('anonymize', False)

        return False

    def should_anonymize_tab(self, privilege: str, tab: str) -> bool:
        """
        Check if data should be anonymized for a specific tab.
        This is for tabs with （凡例なし） marking.

        Args:
            privilege: User's privilege identifier
            tab: Tab name (時系列, カテゴリ比較, 評価, 個人, 分布)

        Returns:
            True if anonymization is required
        """
        config = self.get_effective_config(privilege)
        data_scope = config.get('data_scope', {})

        if tab in data_scope:
            scope = data_scope[tab]
            return scope.get('anonymize', False)

        return False

    def get_allowed_tabs(self, privilege: str) -> list:
        """
        Get list of tabs the privilege has access to.

        Args:
            privilege: User's privilege identifier

        Returns:
            List of allowed tab names
        """
        config = self.get_effective_config(privilege)
        tabs_config = config.get('tabs', {})

        allowed = tabs_config.get('allowed', [])
        if allowed == 'all':
            return ['時系列', 'カテゴリ比較', '評価', '分布', '個人']

        denied = tabs_config.get('denied', [])
        if denied:
            all_tabs = ['時系列', 'カテゴリ比較', '評価', '分布', '個人']
            return [t for t in all_tabs if t not in denied]

        return allowed if allowed else []

    def get_allowed_groupings(self, privilege: str) -> list:
        """
        Get list of groupings the privilege has access to.

        Args:
            privilege: User's privilege identifier

        Returns:
            List of allowed grouping identifiers
        """
        config = self.get_effective_config(privilege)
        groupings_config = config.get('groupings', {})

        allowed = groupings_config.get('allowed', [])
        if allowed == 'all':
            return ['なし', 'department', 'section', 'team', 'project', 'grade', 'name']

        denied = groupings_config.get('denied', [])
        if denied and allowed:
            return [g for g in allowed if g not in denied]

        return allowed if allowed else ['なし', 'department', 'section', 'team', 'project']

    def get_privilege_base_class(self, privilege: str) -> str:
        """
        Return the base privilege class for a given privilege identifier.

        Returns:
            One of 'admin', 'department_head', 'section_manager',
            'member', 'member_no_grade_filter', 'anonymous', or 'unknown'.
        """
        # If it IS a base class directly
        if self.get_base_privilege(privilege):
            return privilege
        user_config = self.get_user_privilege(privilege)
        return user_config.get('inherits', 'unknown')

    def has_feature_access(self, privilege: str, feature: str) -> bool:
        """
        Check if privilege has access to a specific feature.

        Args:
            privilege: User's privilege identifier
            feature: Feature name (e.g., '気になった出来事や気づき')

        Returns:
            True if access is granted
        """
        config = self.get_effective_config(privilege)
        features = config.get('features', {})

        feature_config = features.get(feature)
        if feature_config is None:
            return False
        if isinstance(feature_config, bool):
            return feature_config
        if isinstance(feature_config, dict):
            return feature_config.get('access', False)

        return False

    def should_anonymize(self, privilege: str, feature: str) -> bool:
        """
        Check if data should be anonymized for a feature.

        Args:
            privilege: User's privilege identifier
            feature: Feature name

        Returns:
            True if anonymization is required
        """
        config = self.get_effective_config(privilege)
        features = config.get('features', {})

        feature_config = features.get(feature)
        if isinstance(feature_config, dict):
            return feature_config.get('anonymize', False)

        return False

    def is_response_enabled(self, privilege: str, feature: str) -> bool:
        """
        Check if the response functionality is enabled for a feature.

        Args:
            privilege: User's privilege identifier
            feature: Feature name (e.g., '幹部職に伝えたいこと')

        Returns:
            True if responses can be posted
        """
        config = self.get_effective_config(privilege)
        features = config.get('features', {})

        feature_config = features.get(feature)
        if isinstance(feature_config, dict):
            return feature_config.get('response_enabled', False)

        return False

    def get_section_aliases(self, privilege: str, tab: str) -> dict:
        """
        Get section aliases that should be applied for a privilege/tab combination.

        Args:
            privilege: User's privilege identifier
            tab: Tab name (時系列, カテゴリ比較, 評価, 個人, 分布)

        Returns:
            Dict mapping section names to alias display names, or empty dict if no aliases
        """
        section_aliases = self._config.get('section_aliases', {})
        result = {}

        for alias_id, alias_config in section_aliases.items():
            visible_to = alias_config.get('visible_to', [])
            visible_in_tabs = alias_config.get('visible_in_tabs', [])

            # Check if this alias applies to the privilege and tab
            if privilege in visible_to and tab in visible_in_tabs:
                display_name = alias_config.get('display_name', alias_id)
                members = alias_config.get('members', [])

                # Map each member section to the alias display name
                for member in members:
                    result[member] = display_name

        return result

    def should_use_section_aliases(self, privilege: str, tab: str) -> bool:
        """
        Check if section aliases should be used for a privilege/tab combination.

        Args:
            privilege: User's privilege identifier
            tab: Tab name

        Returns:
            True if aliases should be applied
        """
        return len(self.get_section_aliases(privilege, tab)) > 0

    def get_effective_scope(self, privilege: str, tab: str, grouping: str, dimension_filtered: bool = False) -> Optional[list]:
        """
        Get the effective data scope combining tab and grouping restrictions.

        The more restrictive scope (smaller set) is applied.

        Args:
            privilege: User's privilege identifier
            tab: Tab name (時系列, カテゴリ比較, 評価, 個人, 分布)
            grouping: Grouping type (なし, department, section, team, project, grade, name)
            dimension_filtered: If True, use grouping_scope_filtered (≠すべて) when available

        Returns:
            None if all data allowed, list of allowed organization values,
            or empty list if no access
        """
        tab_scope = self.get_data_scope_for_tab(privilege, tab)
        grouping_scope = self.get_grouping_scope(privilege, grouping, dimension_filtered)

        # Combine scopes - apply the more restrictive one
        return combine_scopes(tab_scope, grouping_scope)


# Singleton instance
_privilege_manager = None


def get_privilege_manager() -> PrivilegeManager:
    """Get the singleton PrivilegeManager instance."""
    global _privilege_manager
    if _privilege_manager is None:
        _privilege_manager = PrivilegeManager()
    return _privilege_manager


def filter_dataframe_by_scope(df, scope_values: Optional[list], org_columns: list = None):
    """
    Filter a DataFrame based on scope values.

    Args:
        df: DataFrame to filter
        scope_values: None for all data, list of allowed org values, empty list for no access
        org_columns: Organization columns to check (default: division, department, section)

    Returns:
        Filtered DataFrame
    """
    if scope_values is None:
        # None = all data allowed
        return df

    if len(scope_values) == 0:
        # Empty list = no access
        return df.iloc[0:0]

    if org_columns is None:
        org_columns = ['division', 'department', 'section']

    # Filter by matching any org column
    mask = None
    for col in org_columns:
        if col in df.columns:
            col_mask = df[col].isin(scope_values)
            mask = col_mask if mask is None else (mask | col_mask)

    if mask is None:
        return df

    return df[mask]


def combine_scopes(tab_scope: Optional[list], grouping_scope: Optional[list]) -> Optional[list]:
    """
    Combine tab scope and grouping scope, returning the effective scope.

    The grouping scope is always more restrictive (or equal) to the tab scope
    because it represents an additional filter applied when a specific grouping
    is selected.

    Rules:
    - None means "all data allowed"
    - Empty list means "no access"
    - Grouping scope takes precedence when both are specified (it's the additional filter)

    Args:
        tab_scope: Tab-level scope (None, empty list, or list of values)
        grouping_scope: Grouping-level scope (None, empty list, or list of values)

    Returns:
        The effective scope to apply
    """
    # If either is empty list (no access), return empty
    if tab_scope is not None and len(tab_scope) == 0:
        return []
    if grouping_scope is not None and len(grouping_scope) == 0:
        return []

    # If grouping scope is None (all allowed for this grouping), use tab scope
    if grouping_scope is None:
        return tab_scope

    # If tab scope is None (all allowed), use grouping scope
    if tab_scope is None:
        return grouping_scope

    # Both have specific values - grouping scope is the additional restriction
    # Use grouping scope as it represents the filter for the specific grouping
    return grouping_scope


def apply_section_aliases(df, alias_mapping: dict, section_column: str = 'section'):
    """
    Apply section aliases to a dataframe, replacing section values with alias names.

    Args:
        df: DataFrame with section column
        alias_mapping: Dict mapping section names to alias display names
        section_column: Name of the section column (default: 'section')

    Returns:
        DataFrame with aliased section values
    """
    if not alias_mapping or section_column not in df.columns:
        return df

    result = df.copy()
    result[section_column] = result[section_column].map(
        lambda x: alias_mapping.get(x, x)
    )
    return result


def filter_dataframe_by_grade(df, allowed_grades: Optional[list], grade_column: str = 'grade'):
    """
    Filter a DataFrame to only include rows with allowed grades.

    Args:
        df: DataFrame to filter
        allowed_grades: None for all grades, list of allowed grade values
        grade_column: Name of the grade column (default: 'grade')

    Returns:
        Filtered DataFrame
    """
    if allowed_grades is None:
        return df

    if grade_column not in df.columns:
        return df

    return df[df[grade_column].isin(allowed_grades)]


def anonymize_dataframe(df, name_columns: list = None):
    """
    Anonymize a DataFrame by removing or masking personal name information.

    Args:
        df: DataFrame to anonymize
        name_columns: List of column names containing personal names
                     (default: ['name', '氏名', 'employee_name'])

    Returns:
        DataFrame with anonymized name columns
    """
    if name_columns is None:
        name_columns = ['name', '氏名', 'employee_name', 'fullname', 'full_name']

    result = df.copy()
    for col in name_columns:
        if col in result.columns:
            # Replace names with anonymized labels
            result[col] = '***'

    return result
