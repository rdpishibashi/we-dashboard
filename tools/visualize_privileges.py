#!/usr/bin/env python3
"""
Privilege Configuration Visualizer

Generates visual representations of the privilege configuration:
1. Text summary table
2. Mermaid diagram (can be viewed in GitHub, VS Code, etc.)

Usage:
    python tools/visualize_privileges.py
    python tools/visualize_privileges.py --mermaid > privileges.md
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.privilege_manager import get_privilege_manager

# All tabs
ALL_TABS = ["時系列", "グループ比較", "評価", "個人", "分布"]


def get_scope_display(pm, privilege, tab):
    """Get a short display string for a scope."""
    scope = pm.get_data_scope(privilege, tab)
    if scope.type == 'all':
        return "全て"
    elif scope.type == 'none':
        return "なし"
    else:
        values = scope.values
        if len(values) == 0:
            return "なし"
        elif len(values) == 1:
            return values[0]
        elif len(values) <= 2:
            return " + ".join(values)
        else:
            return f"{values[0]} + {len(values)-1}件"


def print_text_summary(pm):
    """Print a text summary of all privileges."""
    print("=" * 100)
    print("PRIVILEGE CONFIGURATION SUMMARY")
    print("=" * 100)

    # Get all user privileges
    user_privileges = list(pm._config.get('user_privileges', {}).keys())
    base_privileges = ['admin', 'anonymous']
    all_privileges = base_privileges + sorted(user_privileges)

    # Print header
    print(f"\n{'Privilege':<12} | {'Tabs':<30} | {'Default Scope':<25} | {'個人別 Scope':<20} | {'Anon?':<5}")
    print("-" * 100)

    for priv in all_privileges:
        tabs = pm.get_allowed_tabs(priv)
        tabs_str = ", ".join(tabs) if tabs else "なし"
        if len(tabs_str) > 28:
            tabs_str = tabs_str[:25] + "..."

        default_scope = get_scope_display(pm, priv, None)
        individual_scope = get_scope_display(pm, priv, '個人')
        anonymize = "Yes" if pm.should_anonymize_comments(priv) else "No"

        print(f"{priv:<12} | {tabs_str:<30} | {default_scope:<25} | {individual_scope:<20} | {anonymize:<5}")

    # Print section aliases
    print("\n" + "=" * 100)
    print("SECTION ALIASES")
    print("=" * 100)

    aliases = pm._config.get('section_aliases', {})
    for alias_id, alias_config in aliases.items():
        display_name = alias_config.get('display_name', alias_id)
        members = alias_config.get('members', [])
        visible_to = alias_config.get('visible_to', [])
        visible_in_tabs = alias_config.get('visible_in_tabs', [])

        print(f"\n{display_name}")
        print(f"  Members: {', '.join(members)}")
        print(f"  Visible to: {', '.join(visible_to)}")
        print(f"  In tabs: {', '.join(visible_in_tabs)}")

    # Print detailed scope table
    print("\n" + "=" * 100)
    print("DETAILED SCOPE BY TAB")
    print("=" * 100)

    print(f"\n{'Privilege':<12} | ", end="")
    for tab in ALL_TABS:
        print(f"{tab:<18} | ", end="")
    print()
    print("-" * 115)

    for priv in all_privileges:
        print(f"{priv:<12} | ", end="")
        for tab in ALL_TABS:
            scope = get_scope_display(pm, priv, tab)
            if len(scope) > 16:
                scope = scope[:13] + "..."
            print(f"{scope:<18} | ", end="")
        print()


def generate_mermaid_diagram(pm):
    """Generate a Mermaid diagram of the privilege hierarchy."""
    lines = []
    lines.append("```mermaid")
    lines.append("graph TD")
    lines.append("    subgraph Privilege Hierarchy")

    # Define nodes
    lines.append("        admin[\"admin<br/>全アクセス\"]")
    lines.append("        dept_head[\"department_head<br/>部署レベル\"]")
    lines.append("        sect_mgr[\"section_manager<br/>課レベル+タブ別スコープ\"]")
    lines.append("        member[\"member<br/>課レベル・個人タブなし\"]")
    lines.append("        anon[\"anonymous<br/>アクセスなし\"]")

    # Define hierarchy
    lines.append("        admin --> dept_head")
    lines.append("        dept_head --> sect_mgr")
    lines.append("        sect_mgr --> member")
    lines.append("        admin --> anon")
    lines.append("    end")

    # User privileges
    user_privileges = pm._config.get('user_privileges', {})

    # Group by inherits
    dept_heads = []
    sect_mgrs = []
    members = []

    for priv, config in user_privileges.items():
        inherits = config.get('inherits', '')
        if inherits == 'department_head':
            dept_heads.append(priv)
        elif inherits == 'section_manager':
            sect_mgrs.append(priv)
        elif inherits == 'member':
            members.append(priv)

    if dept_heads:
        lines.append("    subgraph Department Heads")
        for priv in dept_heads:
            scope = get_scope_display(pm, priv, None)
            lines.append(f"        {priv}[\"{priv}<br/>{scope}\"]")
        lines.append("    end")
        for priv in dept_heads:
            lines.append(f"    dept_head -.-> {priv}")

    if sect_mgrs:
        lines.append("    subgraph Section Managers")
        for priv in sect_mgrs:
            default_scope = get_scope_display(pm, priv, None)
            ind_scope = get_scope_display(pm, priv, '個人')
            lines.append(f"        {priv}[\"{priv}<br/>広域:{default_scope}<br/>個人:{ind_scope}\"]")
        lines.append("    end")
        for priv in sect_mgrs:
            lines.append(f"    sect_mgr -.-> {priv}")

    if members:
        lines.append("    subgraph Members")
        for priv in members:
            scope = get_scope_display(pm, priv, None)
            lines.append(f"        {priv}[\"{priv}<br/>{scope}\"]")
        lines.append("    end")
        for priv in members:
            lines.append(f"    member -.-> {priv}")

    lines.append("```")

    return "\n".join(lines)


def generate_scope_table_markdown(pm):
    """Generate a markdown table of scopes."""
    lines = []
    lines.append("## Data Scope by Privilege and Tab")
    lines.append("")

    # Header
    header = "| Privilege | " + " | ".join(ALL_TABS) + " |"
    separator = "|" + "|".join(["---"] * (len(ALL_TABS) + 1)) + "|"
    lines.append(header)
    lines.append(separator)

    # Get all privileges
    user_privileges = list(pm._config.get('user_privileges', {}).keys())
    base_privileges = ['admin', 'anonymous']
    all_privileges = base_privileges + sorted(user_privileges)

    for priv in all_privileges:
        row = f"| {priv} |"
        for tab in ALL_TABS:
            scope = get_scope_display(pm, priv, tab)
            row += f" {scope} |"
        lines.append(row)

    return "\n".join(lines)


def get_grouping_scope_display(pm, privilege, grouping):
    """Get a short display string for a scope based on grouping filter.

    For 'name' grouping, use 個人 tab scope.
    For 'grade' grouping, check if grade filtering applies.
    For others, use default scope.
    """
    scope = pm.get_data_scope(privilege, None)  # Default scope

    if scope.type == 'all':
        return "全て"
    elif scope.type == 'none':
        return "なし"

    # For 個人別 grouping, use the 個人 tab scope
    if grouping == 'name':
        scope = pm.get_data_scope(privilege, '個人')
        if scope.type == 'none':
            return "なし"
        elif scope.type == 'all':
            return "全て"
        values = scope.values
        if len(values) == 0:
            return "なし"
        elif len(values) == 1:
            return values[0]
        elif len(values) <= 2:
            return " + ".join(values)
        else:
            return f"{values[0]} + {len(values)-1}件"

    # For 職位別 grouping, check if grade filtering applies
    if grouping == 'grade':
        # Check if this privilege has grade filtering
        config = pm._resolve_privilege_config(privilege)
        groupings = config.get('groupings', {})
        grade_filter = groupings.get('grade_filter')

        base_scope = get_scope_display(pm, privilege, None)
        if base_scope == "なし":
            return "なし"

        if grade_filter and grade_filter.get('type') == 'include':
            # Has grade filtering - show with 非管理職 suffix
            return f"{base_scope}の非管理職"
        else:
            return base_scope

    # For other groupings (なし, department, section, team, project), use default scope
    values = scope.values
    if len(values) == 0:
        return "なし"
    elif len(values) == 1:
        return values[0]
    elif len(values) <= 2:
        return " + ".join(values)
    else:
        return f"{values[0]} + {len(values)-1}件"


def generate_grouping_scope_table_markdown(pm):
    """Generate a markdown table of scopes by grouping filter."""
    lines = []
    lines.append("## Data Scope by Grouping local filter")

    # Grouping options
    groupings = ["なし", "部署別・課別・チーム別・プロジェクト別", "職位別", "個人別"]
    grouping_keys = [None, "section", "grade", "name"]  # Internal keys

    # Header
    header = "| Privilege | " + " | ".join(groupings) + " |"
    separator = "|" + "|".join(["---"] * (len(groupings) + 1)) + "|"
    lines.append(header)
    lines.append(separator)

    # Get all privileges
    user_privileges = list(pm._config.get('user_privileges', {}).keys())
    base_privileges = ['admin', 'anonymous']
    all_privileges = base_privileges + sorted(user_privileges)

    for priv in all_privileges:
        row = f"| {priv} |"
        for i, grouping in enumerate(grouping_keys):
            scope = get_grouping_scope_display(pm, priv, grouping)
            row += f" {scope} |"
        lines.append(row)

    return "\n".join(lines)


def main():
    pm = get_privilege_manager()
    pm.reload_config()

    if "--mermaid" in sys.argv:
        # Output Mermaid diagram and markdown table
        print("# Privilege Configuration Visualization")
        print("")
        print("## Privilege Hierarchy")
        print("")
        print(generate_mermaid_diagram(pm))
        print("")
        print(generate_scope_table_markdown(pm))
        print("")
        print(generate_grouping_scope_table_markdown(pm))
        print("")
        print("## Section Aliases")
        print("")
        aliases = pm._config.get('section_aliases', {})
        for alias_id, alias_config in aliases.items():
            display_name = alias_config.get('display_name', alias_id)
            members = alias_config.get('members', [])
            visible_to = alias_config.get('visible_to', [])
            visible_in_tabs = alias_config.get('visible_in_tabs', [])
            print(f"### {display_name}")
            print(f"- **Members**: {', '.join(members)}")
            print(f"- **Visible to**: {', '.join(visible_to)}")
            print(f"- **In tabs**: {', '.join(visible_in_tabs)}")
            print("")
    else:
        # Print text summary to console
        print_text_summary(pm)


if __name__ == "__main__":
    main()
