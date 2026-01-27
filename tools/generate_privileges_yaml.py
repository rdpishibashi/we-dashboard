#!/usr/bin/env python3
"""
Generate privileges.yaml from privileges_configuration.md

This script reads the markdown documentation and converts it to the YAML
configuration file, ensuring the documentation is the single source of truth.

Usage:
    python tools/generate_privileges_yaml.py
    python tools/generate_privileges_yaml.py --check  # Verify without writing
"""

import re
import sys
import yaml
from pathlib import Path
from typing import Optional
from collections import OrderedDict


# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
MD_FILE = PROJECT_ROOT / 'docs' / 'privileges_configuration.md'
YAML_FILE = PROJECT_ROOT / 'config' / 'privileges.yaml'


# Grade groups - these are static and not in the markdown
GRADE_GROUPS = {
    'non_managers': [
        'サプライヤー',
        '一般職',
        '主任',
        '主事補',
        '主事',
        '主管'
    ],
    'managers': [
        '特命職',
        '特命職・専門職',
        'エキスパート',
        '課長',
        '部長'
    ]
}

# All available tabs
ALL_TABS = ['時系列', 'グループ比較', '評価', '個人', '分布']

# All available groupings
ALL_GROUPINGS = ['なし', 'department', 'section', 'team', 'project', 'grade', 'name']

# Privilege class hierarchy mapping
# Format: privilege -> (class_type, inherits_from)
PRIVILEGE_CLASSES = {
    'admin': ('admin', None),
    'anonymous': ('anonymous', None),
    # Department heads
    'sd': ('department_head', 'department_head'),
    'me': ('department_head', 'department_head'),
    'dev': ('department_head', 'department_head'),
    # Section managers - SD/ME department
    'sw': ('section_manager', 'section_manager'),
    'pd': ('section_manager', 'section_manager'),
    'me1': ('section_manager', 'section_manager'),
    'me2': ('section_manager', 'section_manager'),
    'me3': ('section_manager', 'section_manager'),
    # Section managers - Dev department
    'dev1': ('section_manager', 'section_manager'),
    'dev2': ('section_manager', 'section_manager'),
    'uti': ('section_manager', 'section_manager'),
    'uks1': ('section_manager', 'section_manager'),
    # Members - SD/ME department (with grade filtering)
    'soft': ('member', 'member'),
    'prod': ('member', 'member'),
    'design1': ('member', 'member'),
    'design2': ('member', 'member'),
    'design3': ('member', 'member'),
    # Members - Dev department (without grade filtering)
    'develop': ('member_no_grade_filter', 'member_no_grade_filter'),
}


def parse_markdown_table(content: str, header_pattern: str) -> list[dict]:
    """
    Parse a markdown table following a specific header.

    Args:
        content: Full markdown content
        header_pattern: Regex pattern to match the table header

    Returns:
        List of dicts, each representing a row with column names as keys
    """
    # Find the header and table
    match = re.search(header_pattern + r'\s*\n\|([^\n]+)\|\s*\n\|[-|\s]+\|\s*\n((?:\|[^\n]+\|\s*\n)+)', content)
    if not match:
        return []

    # Parse header row
    header_line = match.group(1)
    headers = [h.strip() for h in header_line.split('|')]

    # Parse data rows
    data_lines = match.group(2).strip().split('\n')
    rows = []
    for line in data_lines:
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))

    return rows


def parse_section_aliases(content: str) -> dict:
    """Parse Section Aliases section from markdown."""
    aliases = {}

    # Find the Section Aliases section
    aliases_match = re.search(r'## Section Aliases\s*\n((?:###[^\n]+\n(?:[^\n#]+\n)*)+)', content)
    if not aliases_match:
        return aliases

    aliases_content = aliases_match.group(1)

    # Parse each alias block
    alias_blocks = re.findall(
        r'### ([^\n]+)\n'
        r'- \*\*Members\*\*: ([^\n]+)\n'
        r'- \*\*Visible to\*\*: ([^\n]+)\n'
        r'- \*\*In tabs\*\*: ([^\n]+)',
        aliases_content
    )

    for display_name, members, visible_to, visible_in_tabs in alias_blocks:
        # Create alias ID from display name
        alias_id = display_name.replace('・', '_').replace(' ', '_')

        aliases[alias_id] = {
            'display_name': display_name.strip(),
            'members': [m.strip() for m in members.split(',')],
            'visible_to': [v.strip() for v in visible_to.split(',')],
            'visible_in_tabs': [t.strip() for t in visible_in_tabs.split(',')]
        }

    return aliases


def parse_scope_value(value: str) -> tuple[str, list[str], bool]:
    """
    Parse a scope value from the markdown table.

    Args:
        value: Raw cell value like "システム開発部 + 機電設計部" or "なし" or "全て"

    Returns:
        Tuple of (scope_type, values_list, anonymize_flag)
    """
    value = value.strip()
    anonymize = False

    # Check for "without 個人名" suffix
    if 'without 個人名' in value:
        anonymize = True
        value = value.replace('without 個人名', '').strip()

    if value == '全て':
        return ('all', [], anonymize)
    elif value == 'なし':
        return ('none', [], anonymize)
    else:
        # Parse organization values
        values = [v.strip() for v in value.split('+')]
        return ('organization', values, anonymize)


def determine_allowed_tabs(tab_scope: dict[str, tuple]) -> list[str]:
    """Determine which tabs a privilege has access to based on their data scope."""
    allowed = []
    for tab in ALL_TABS:
        if tab in tab_scope:
            scope_type, _, _ = tab_scope[tab]
            if scope_type != 'none':
                allowed.append(tab)
    return allowed


def determine_groupings(privilege: str, grouping_scope: dict) -> dict:
    """Determine grouping permissions based on privilege class."""
    class_type, _ = PRIVILEGE_CLASSES.get(privilege, ('anonymous', None))

    if class_type == 'admin':
        return {'allowed': 'all'}
    elif class_type == 'anonymous':
        return {
            'allowed': ['なし', 'department', 'section', 'team', 'project']
        }
    elif class_type in ('member', 'member_no_grade_filter'):
        result = {
            'allowed': ['なし', 'department', 'section', 'team', 'project', 'grade'],
            'denied': ['name']
        }
        # Add grade filter for regular members
        if class_type == 'member':
            result['grade_filter'] = {
                'type': 'include',
                'values_from': 'non_managers'
            }
        return result
    else:
        # Section managers and department heads
        return {'allowed': 'all'}


def determine_features(privilege: str, section_scope: dict) -> dict:
    """Determine feature access based on privilege class and section scope."""
    class_type, _ = PRIVILEGE_CLASSES.get(privilege, ('anonymous', None))

    features = {}

    # 気になった出来事や気づき - only admin has access
    features['気になった出来事や気づき'] = (class_type == 'admin')

    # 共有したいこと
    if class_type == 'anonymous':
        features['共有したいこと'] = {
            'access': False,
            'anonymize': True
        }
    elif class_type in ('member', 'member_no_grade_filter'):
        # Check if member has access (not 'none' scope)
        share_scope = section_scope.get('共有したいこと', ('none', [], False))
        has_access = share_scope[0] != 'none'
        features['共有したいこと'] = {
            'access': has_access,
            'anonymize': True  # Members always see anonymized
        }
    else:
        features['共有したいこと'] = {
            'access': True,
            'anonymize': False
        }

    return features


def build_data_scope(privilege: str, tab_scope: dict) -> dict:
    """Build data_scope configuration from tab scope data."""
    result = {}

    for tab, (scope_type, values, _) in tab_scope.items():
        if scope_type == 'all':
            continue  # Use default for 'all'
        elif scope_type == 'none':
            result[tab] = {'type': 'none'}
        else:
            result[tab] = {'values': values}

    # Set default based on most common scope
    # For simplicity, use the first non-none tab's scope as default
    for tab in ALL_TABS:
        if tab in tab_scope:
            scope_type, values, _ = tab_scope[tab]
            if scope_type == 'all':
                result['default'] = {'type': 'all'}
                break
            elif scope_type == 'organization' and values:
                result['default'] = {'values': values}
                break

    if 'default' not in result:
        result['default'] = {'type': 'none'}

    return result


def build_section_scope(privilege: str, section_scope: dict) -> dict:
    """Build section_scope configuration from section scope data."""
    result = {}

    for section, (scope_type, values, _) in section_scope.items():
        if section == '気になった出来事や気づき':
            continue  # This is handled as a feature, not section_scope

        if scope_type == 'all':
            result[section] = {'type': 'all'}
        elif scope_type == 'none':
            result[section] = {'type': 'none'}
        else:
            result[section] = {'values': values}

    return result


def generate_base_privileges() -> dict:
    """Generate base privilege class definitions."""
    return {
        'admin': {
            'tabs': {'allowed': 'all'},
            'data_scope': {'default': {'type': 'all'}},
            'section_scope': {
                '計測値': {'type': 'all'},
                '主な指標': {'type': 'all'},
                'アクション対象候補': {'type': 'all'},
                '共有したいこと': {'type': 'all'}
            },
            'groupings': {'allowed': 'all'},
            'features': {
                '気になった出来事や気づき': True,
                '共有したいこと': {'access': True, 'anonymize': False}
            }
        },
        'department_head': {
            'tabs': {'allowed': 'all'},
            'data_scope': {'default': {'type': 'organization'}},
            'section_scope': {
                '計測値': {'type': 'organization'},
                '主な指標': {'type': 'organization'},
                'アクション対象候補': {'type': 'organization'},
                '共有したいこと': {'type': 'organization'}
            },
            'groupings': {'allowed': 'all'},
            'features': {
                '気になった出来事や気づき': False,
                '共有したいこと': {'access': True, 'anonymize': False}
            }
        },
        'section_manager': {
            'inherits': 'department_head',
            'tabs': {'allowed': 'all'},
            'data_scope': {
                '時系列': {'type': 'organization'},
                'グループ比較': {'type': 'organization'},
                '評価': {'type': 'organization'},
                '個人': {'type': 'organization'},
                '分布': {'type': 'organization'},
                'default': {'type': 'organization'}
            },
            'section_scope': {
                '計測値': {'type': 'organization'},
                '主な指標': {'type': 'organization'},
                'アクション対象候補': {'type': 'organization'},
                '共有したいこと': {'type': 'organization'}
            },
            'groupings': {'allowed': 'all'},
            'auto_reset_filters': {
                'on_tab_change': {
                    'from': ['時系列', 'グループ比較', '評価'],
                    'to': ['個人', '分布'],
                    'reset_to': 'user_section'
                }
            },
            'features': {
                '気になった出来事や気づき': False,
                '共有したいこと': {'access': True, 'anonymize': False}
            }
        },
        'member': {
            'inherits': 'section_manager',
            'tabs': {
                'allowed': ['時系列', 'グループ比較', '評価'],
                'denied': ['個人', '分布']
            },
            'data_scope': {'default': {'type': 'organization'}},
            'section_scope': {
                '計測値': {'type': 'organization'},
                '主な指標': {'type': 'organization'},
                'アクション対象候補': {'type': 'none'},
                '共有したいこと': {'type': 'organization'}
            },
            'groupings': {
                'allowed': ['なし', 'department', 'section', 'team', 'project', 'grade'],
                'denied': ['name'],
                'grade_filter': {
                    'type': 'include',
                    'values_from': 'non_managers'
                }
            },
            'features': {
                '気になった出来事や気づき': False,
                '共有したいこと': {'access': True, 'anonymize': True}
            }
        },
        'member_no_grade_filter': {
            'inherits': 'section_manager',
            'tabs': {
                'allowed': ['時系列', 'グループ比較', '評価'],
                'denied': ['個人', '分布']
            },
            'data_scope': {'default': {'type': 'organization'}},
            'section_scope': {
                '計測値': {'type': 'organization'},
                '主な指標': {'type': 'organization'},
                'アクション対象候補': {'type': 'none'},
                '共有したいこと': {'type': 'none'}
            },
            'groupings': {
                'allowed': ['なし', 'department', 'section', 'team', 'project', 'grade'],
                'denied': ['name']
            },
            'features': {
                '気になった出来事や気づき': False,
                '共有したいこと': {'access': False, 'anonymize': True}
            }
        },
        'anonymous': {
            'tabs': {'allowed': []},
            'data_scope': {'default': {'type': 'none'}},
            'section_scope': {
                '計測値': {'type': 'none'},
                '主な指標': {'type': 'none'},
                'アクション対象候補': {'type': 'none'},
                '共有したいこと': {'type': 'none'}
            },
            'groupings': {
                'allowed': ['なし', 'department', 'section', 'team', 'project']
            },
            'features': {
                '気になった出来事や気づき': False,
                '共有したいこと': {'access': False, 'anonymize': True}
            }
        }
    }


def generate_user_privilege(privilege: str, tab_scope: dict, section_scope: dict) -> Optional[dict]:
    """Generate a user privilege configuration."""
    if privilege in ('admin', 'anonymous'):
        return None  # These are base classes

    class_type, inherits = PRIVILEGE_CLASSES.get(privilege, ('anonymous', None))
    if not inherits:
        return None

    result = {'inherits': inherits}

    # Build data_scope
    data_scope = {}
    for tab in ALL_TABS:
        if tab in tab_scope:
            scope_type, values, _ = tab_scope[tab]
            if scope_type == 'organization' and values:
                data_scope[tab] = {'values': values}

    # Set default from the most common values
    if tab_scope:
        first_tab = list(tab_scope.keys())[0]
        scope_type, values, _ = tab_scope[first_tab]
        if scope_type == 'organization' and values:
            data_scope['default'] = {'values': values}

    if data_scope:
        result['data_scope'] = data_scope

    # Build section_scope
    sec_scope = {}
    for section in ['計測値', '主な指標', 'アクション対象候補', '共有したいこと']:
        if section in section_scope:
            scope_type, values, _ = section_scope[section]
            if scope_type == 'organization' and values:
                sec_scope[section] = {'values': values}

    if sec_scope:
        result['section_scope'] = sec_scope

    return result


def generate_yaml_content(md_content: str) -> str:
    """Generate the full YAML content from markdown."""
    # Parse tables
    tab_data = parse_markdown_table(md_content, r'## Data Scope by Privilege and Tab')
    section_data = parse_markdown_table(md_content, r'## Data Scope by Section')
    aliases = parse_section_aliases(md_content)

    # Build scope mappings per privilege
    privilege_tab_scope = {}
    privilege_section_scope = {}

    for row in tab_data:
        privilege = row.get('Privilege', '').strip()
        if not privilege:
            continue

        tab_scope = {}
        for tab in ALL_TABS:
            if tab in row:
                tab_scope[tab] = parse_scope_value(row[tab])

        privilege_tab_scope[privilege] = tab_scope

    for row in section_data:
        privilege = row.get('Privilege', '').strip()
        if not privilege:
            continue

        section_scope = {}
        for section in ['計測値', '主な指標', 'アクション対象候補', '気になった出来事や気づき', '共有したいこと']:
            if section in row:
                section_scope[section] = parse_scope_value(row[section])

        privilege_section_scope[privilege] = section_scope

    # Build YAML structure
    yaml_data = OrderedDict()

    # Grade groups
    yaml_data['grade_groups'] = GRADE_GROUPS

    # Section aliases
    yaml_data['section_aliases'] = aliases

    # Base privilege classes
    yaml_data['privileges'] = generate_base_privileges()

    # User privileges
    user_privileges = OrderedDict()

    # Group by class type for organization
    class_groups = {
        'department_head': [],
        'section_manager': [],
        'member': [],
        'member_no_grade_filter': []
    }

    for privilege in privilege_tab_scope.keys():
        if privilege in ('admin', 'anonymous'):
            continue
        class_type, _ = PRIVILEGE_CLASSES.get(privilege, (None, None))
        if class_type in class_groups:
            class_groups[class_type].append(privilege)

    # Generate user privileges in order
    for class_type in ['department_head', 'section_manager', 'member', 'member_no_grade_filter']:
        for privilege in class_groups[class_type]:
            tab_scope = privilege_tab_scope.get(privilege, {})
            section_scope = privilege_section_scope.get(privilege, {})

            user_config = generate_user_privilege(privilege, tab_scope, section_scope)
            if user_config:
                user_privileges[privilege] = user_config

    yaml_data['user_privileges'] = user_privileges

    # Generate YAML string with comments
    yaml_output = generate_yaml_with_comments(yaml_data)

    return yaml_output


def generate_yaml_with_comments(data: dict) -> str:
    """Generate YAML string with helpful comments."""
    lines = [
        "# Privilege Configuration for WE-Dashboard",
        "# This file is auto-generated from docs/privileges_configuration.md",
        "# Do not edit this file directly - edit the markdown and run:",
        "#   python tools/generate_privileges_yaml.py",
        "#",
        "# Configuration based on: docs/privileges_configuration.md",
        "#",
        "# Four tables define data access:",
        "# 1. Data Scope by Privilege and Tab - controls which data is visible per tab",
        "# 2. Data Scope by Grouping local filter - controls which data is visible per grouping option",
        "# 3. Data Scope by Section - controls which data is visible in specific UI sections",
        "#    (計測値, 主な指標, アクション対象候補, 気になった出来事や気づき, 共有したいこと)",
        ""
    ]

    # Custom YAML dumper for better formatting
    class CustomDumper(yaml.SafeDumper):
        pass

    def str_representer(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    CustomDumper.add_representer(str, str_representer)

    # Dump each section with comments
    sections = [
        ('grade_groups', '# Grade groups for filtering'),
        ('section_aliases', '# Section aliases for grouped display in 課別 grouping\n# Note: dev (department head) sees individual sections, NOT combined aliases\n# All section managers in 開発部 (dev1, dev2, uti, uks1) see BOTH combined aliases'),
        ('privileges', '# Privilege class definitions'),
        ('user_privileges', '# User to privilege mapping with specific data scopes'),
    ]

    for key, comment in sections:
        lines.append(comment)
        section_data = {key: data[key]}
        yaml_str = yaml.dump(section_data, Dumper=CustomDumper, allow_unicode=True,
                            default_flow_style=False, sort_keys=False, width=120)
        lines.append(yaml_str)

    return '\n'.join(lines)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate privileges.yaml from markdown')
    parser.add_argument('--check', action='store_true',
                       help='Check if YAML is up to date without writing')
    args = parser.parse_args()

    # Read markdown
    if not MD_FILE.exists():
        print(f"Error: {MD_FILE} not found")
        sys.exit(1)

    md_content = MD_FILE.read_text(encoding='utf-8')

    # Generate YAML
    yaml_content = generate_yaml_content(md_content)

    if args.check:
        # Compare with existing
        if YAML_FILE.exists():
            existing = YAML_FILE.read_text(encoding='utf-8')
            if existing.strip() == yaml_content.strip():
                print("privileges.yaml is up to date")
                sys.exit(0)
            else:
                print("privileges.yaml needs to be regenerated")
                print("Run: python tools/generate_privileges_yaml.py")
                sys.exit(1)
        else:
            print("privileges.yaml does not exist")
            sys.exit(1)
    else:
        # Write YAML
        YAML_FILE.parent.mkdir(parents=True, exist_ok=True)
        YAML_FILE.write_text(yaml_content, encoding='utf-8')
        print(f"Generated {YAML_FILE}")


if __name__ == '__main__':
    main()
