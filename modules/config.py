"""
Configuration and Constants for Work Engagement Dashboard
"""

from pathlib import Path

# =============================================================================
# Organizational Structure
# =============================================================================
# Hierarchy: Division (部門) → Department (部署) → Section (課)
#
# Excel column mapping (current_* = current affiliation):
#   current_division   → division   (部門/Division)
#   current_department → department (部署/Department)
#   current_section    → section    (課/Section)
#
# This structure is fixed and used throughout the application.

# Column names used in the application (mapped from Excel)
ORG_COLUMNS = {
    'division': 'division',     # 部門 - highest level
    'department': 'department', # 部署 - middle level
    'section': 'section',       # 課 - lowest level
}

# Excel source column names (current affiliation)
ORG_EXCEL_COLUMNS = {
    'division': 'current_division',
    'department': 'current_department',
    'section': 'current_section',
}

# Columns to check for privilege-based filtering (in order of hierarchy)
ORG_FILTER_COLUMNS = ['division', 'department', 'section']

# Plotly chart configuration
PLOTLY_CHART_KWARGS = {"width": "stretch"}

RADAR_CHART_CONFIG = {
    "modeBarButtonsToAdd": ["resetCameraDefault"]
}

DATAFRAME_KWARGS = {"width": "stretch", "hide_index": True}

# Metric labels
METRIC_LABELS = {
    'engagement_rating': 'ワーク･エンゲージメント',
    'vigor_rating': '活力 (Vigor)',
    'dedication_rating': '熱意 (Dedication)',
    'absorption_rating': '没頭 (Absorption)'
}

# Signal labels
SIGNAL_LABELS = {
    'section': '課',
    'name': '氏名',
    'intervention_priority': '介入必要度',
    'level': 'レベル',
    'trend_recent': '短期傾向',
    'trend_base': '中期傾向',
    'trend_refined': '総合傾向',
    'big_change': '短期変動',
    'mid_variability': '変動パターン',
    'stability_6': '中期安定性',
    'engagement_rating': 'エンゲージメント',
    'vigor_rating': '活力',
    'dedication_rating': '熱意',
    'absorption_rating': '没頭',
    'flag_constant_6m': '調査抵抗疑義',
    'strength_short': '強み（短期）',
    'weakness_short': '弱み（短期）',
    'strength_mid': '強み（中期）',
    'weakness_mid': '弱み（中期）'
}

# flag_constant_6m display labels
FLAG_CONSTANT_LABELS = {
    'LOW_FIXED': '連続固定低評価回答',
    'MID_EVASION': '連続固定中評価回答',
    'HIGH_AVOIDANCE': '連続固定高評価回答',
    'FIX_SHIFTED': '連続固定回答シフト',
}

# Level value mapping (English → Japanese)
LEVEL_LABELS = {
    'Critical': '要注意',
    'Low': '低調',
    'Moderate': '標準',
    'High': '良好',
    'Thriving': '充実',
}

# Rating axis maximum
RATING_AXIS_MAX = 10.3

# Trend color groups
POSITIVE_TRENDS = ['上昇加速', '上昇継続', '回復期待', '回復', '復活', '上昇期待', '上昇']
NEGATIVE_TRENDS = ['低下懸念', '悪化', '低下危機', '低下加速', '低下継続', '低下警戒', '下降']

# Signal table display columns
SIGNAL_TABLE_COLUMNS = ['name', 'section', 'intervention_priority', 'trend_recent', 'trend_base', 'trend_refined', 'big_change', 'mid_variability', 'stability_6', 'flag_constant_6m']
INDIVIDUAL_SIGNAL_COLUMNS = [
    'intervention_priority', 'level', 'trend_recent',
    'trend_base', 'trend_refined', 'big_change', 'mid_variability', 'stability_6', 'flag_constant_6m',
    'strength_short', 'weakness_short', 'strength_mid', 'weakness_mid'
]

# Group order configuration file
GROUP_ORDER_FILE = Path(__file__).parent.parent / 'group_order_config.json'

# Intervention priority threshold: 介入必要度 = pos - neg のとき、
# ネガティブ・メンバー: 介入必要度 <= -threshold / ポジティブ・メンバー: 介入必要度 >= +threshold
# のみテーブルに掲載する（表示は絶対値）
INTERVENTION_PRIORITY_THRESHOLD = 2

# Rating calculation constants
ENGAGEMENT_DIVISOR = 5.4
COMPONENT_DIVISOR = 1.8

# Rating band thresholds
RATING_BAND_HIGH_THRESHOLD = 6.0
RATING_BAND_LOW_THRESHOLD = 2.0

# Color scale configuration
COLOR_SCALE_START = 0.35
COLOR_SCALE_END = 1

# Bar chart opacity for 評価別比率 (group rating distribution)
RATING_DISTRIBUTION_BAR_OPACITY = 0.9

# Grouping label map
GROUPING_LABEL_MAP = {
    'なし': 'なし',
    'division': '部門別',
    'department': '部署別',
    'section': '課別',
    'team': 'チーム別',
    'project': 'プロジェクト別',
    'grade': '職位別',
    'name': '個人別'
}

# =============================================================================
# Tab Configuration
# =============================================================================
# Centralized tab definitions to avoid hardcoded tab names scattered in code

TAB_NAMES = ['時系列', 'カテゴリ比較', '評価', '分布', '個人']
TAB_NAMES_AUTHENTICATED = ['時系列', 'カテゴリ比較', '評価', '分布', '個人']
TAB_NAMES_ANONYMOUS = ['時系列', 'カテゴリ比較', '評価', '分布']  # 個人 tab hidden

# Tab-specific configuration
TAB_CONFIG = {
    '時系列': {
        'key': 'timeseries',
        'subheader': '時系列トレンド',
        'has_grouping': True,
        'has_measured_data': True,
        'has_statistics': True,
        'has_signals': True,
        'has_comments': True,
    },
    'カテゴリ比較': {
        'key': 'group_comparison',
        'subheader': 'カテゴリ比較',
        'has_grouping': True,
        'has_measured_data': True,
        'has_statistics': True,
        'has_signals': True,
        'has_comments': True,
    },
    '評価': {
        'key': 'evaluation',
        'subheader': '評価分析',
        'has_grouping': True,
        'has_measured_data': False,
        'has_statistics': False,
        'has_signals': False,
        'has_comments': False,
    },
    '分布': {
        'key': 'distribution',
        'subheader': '分布分析',
        'has_grouping': True,
        'has_measured_data': False,
        'has_statistics': True,
        'has_signals': False,
        'has_comments': False,
    },
    '個人': {
        'key': 'individual',
        'subheader': '個人分析',
        'has_grouping': False,
        'has_measured_data': True,
        'has_statistics': False,
        'has_signals': True,
        'has_comments': True,
    },
}

# Grouping options by authentication state
GROUPING_OPTIONS_AUTHENTICATED = ['なし', 'department', 'section', 'team', 'project', 'grade', 'name']
GROUPING_OPTIONS_ANONYMOUS = ['なし', 'department', 'section', 'team', 'project']

# Group labels (without 別 suffix)
GROUP_LABELS = {
    'division': '部門',
    'department': '部署',
    'section': '課',
    'team': 'チーム',
    'project': 'プロジェクト',
    'grade': '職位',
    'name': '個人'
}

# Default data file — looks for EngagementData-*.xlsx
def find_default_data_files():
    """
    Search for EngagementData-*.xlsx in a platform-appropriate location.

    - Windows: ~/Documents/WE-Dashboard/  (user-visible folder next to the exe)
    - Other (Mac / Streamlit Cloud): same directory as app.py (project root)

    Returns a list of matching paths (may be empty).
    """
    import glob
    import sys
    if sys.platform == 'win32':
        data_dir = Path.home() / 'Documents' / 'WE-Dashboard'
    else:
        # Path(__file__) is modules/config.py → .parent.parent is project root
        data_dir = Path(__file__).resolve().parent.parent
    return glob.glob(str(data_dir / 'EngagementData-*.xlsx'))

# Privilege-based access control for 共有したいこと section
# Maps privilege to allowed groups (None = all groups allowed)
PRIVILEGE_GROUP_ACCESS = {
    'admin': None,                   # Admin - all groups
    'sd': ['システム開発部', '機電設計部'],
    'me': ['システム開発部', '機電設計部'],
    'sw': ['ソフトウェア開発課'],
    'pd': ['製品技術課'],
    'me1': ['第一設計課'],
    'me2': ['第二設計課'],
    'me3': ['第三設計課'],
    'dev': ['開発部'],
    'dev1': ['開発部'],
    'dev2': ['開発部'],
    'uti': ['開発部'],
    'uks': ['開発部']
}
