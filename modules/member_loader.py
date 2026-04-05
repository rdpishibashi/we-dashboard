"""
Member list loader for WE-Dashboard.

Loads the active member list from config/members.yaml, which is generated
by tools/generate_member_yaml.py from MemberSS.xlsx.
"""

import yaml
import pandas as pd
import streamlit as st
from pathlib import Path

_MEMBERS_YAML = Path(__file__).resolve().parent.parent / 'config' / 'members.yaml'
_COLUMNS = ['mail_address', 'member_name', 'division', 'department', 'section', 'team', 'project', 'grade']


@st.cache_data
def load_members() -> pd.DataFrame:
    """
    Load active members from config/members.yaml.

    Returns:
        DataFrame with columns: mail_address, member_name, division,
        department, section. Returns an empty DataFrame if the file is
        missing (未記入者 section will be silently skipped).
    """
    if not _MEMBERS_YAML.exists():
        return pd.DataFrame(columns=_COLUMNS)

    with open(_MEMBERS_YAML, encoding='utf-8') as f:
        data = yaml.safe_load(f)

    members = data.get('members', [])
    if not members:
        return pd.DataFrame(columns=_COLUMNS)

    df = pd.DataFrame(members)
    for col in _COLUMNS:
        if col not in df.columns:
            df[col] = ''

    return df[_COLUMNS].fillna('')
