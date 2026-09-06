"""
Organization Basis Toggle (現在／測定当時)
==========================================
Switches the working division/department/section/team/project/grade columns
(config.AT_SURVEY_TOGGLE_COLUMNS) between the current affiliation and the
at-survey (measured-at-the-time) affiliation.

This is the ONLY place that performs the switch. Every other module keeps
reading the plain column names exactly as before — apply_org_basis() must run
once, before those columns are used for anything, on any DataFrame produced
by data_loader.load_data().

Privilege scoping never follows this toggle (see docs/PRIVILEGE_SYSTEM.md);
it reads the pinned *_current columns instead (config.SCOPE_ORG_COLUMNS /
GRADE_SCOPE_COLUMN), which this function does not touch.
"""

import pandas as pd

from .config import ORG_BASIS_AT_SURVEY, AT_SURVEY_TOGGLE_COLUMNS


def apply_org_basis(df: pd.DataFrame, basis: str) -> pd.DataFrame:
    """
    Return a copy of df with the toggled columns set to the requested basis.

    Args:
        df: DataFrame produced by data_loader.load_data() (pivot_df or
            signal_df). DataFrames without the {col}_at columns (e.g.
            comment_df, member_df) are returned unchanged — this toggle does
            not apply to them.
        basis: config.ORG_BASIS_CURRENT (no-op — columns already hold the
            current affiliation) or config.ORG_BASIS_AT_SURVEY (overwrite with
            the {col}_at columns).

    Returns:
        DataFrame with the same shape; config.AT_SURVEY_TOGGLE_COLUMNS replaced
        in place when basis is at_survey, unchanged otherwise.
    """
    if basis != ORG_BASIS_AT_SURVEY:
        return df

    result = df.copy()
    for col in AT_SURVEY_TOGGLE_COLUMNS:
        at_col = f'{col}_at'
        if at_col in result.columns:
            result[col] = result[at_col]

    return result
