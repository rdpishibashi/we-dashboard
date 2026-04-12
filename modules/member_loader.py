"""
Member list loader for WE-Dashboard.

Loads the member list from config/members.yaml, which is generated
by tools/generate_member_yaml.py from Member.xlsx.

The YAML contains ALL members (active, absence, leave) with their
leave status. Filtering by status is done at display time.
"""

import yaml
import pandas as pd
import streamlit as st
from pathlib import Path

_MEMBERS_YAML = Path(__file__).resolve().parent.parent / 'config' / 'members.yaml'


def _get_yaml_mtime():
    """Get members.yaml modification time for cache invalidation."""
    if _MEMBERS_YAML.exists():
        return _MEMBERS_YAML.stat().st_mtime
    return None


@st.cache_data
def _load_members_impl(mtime):
    """Load members from YAML. Cached by file modification time."""
    if not _MEMBERS_YAML.exists():
        return pd.DataFrame()

    with open(_MEMBERS_YAML, encoding='utf-8') as f:
        data = yaml.safe_load(f)

    members = data.get('members', [])
    if not members:
        return pd.DataFrame()

    return pd.DataFrame(members).fillna('')


def load_members() -> pd.DataFrame:
    """
    Load members from config/members.yaml.

    Returns:
        DataFrame with all members and their attributes including leave status.
        Returns an empty DataFrame if the file is missing.
    """
    return _load_members_impl(_get_yaml_mtime())
