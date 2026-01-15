"""
Configuration and Constants for Work Engagement Dashboard
"""

from pathlib import Path

# Plotly chart configuration
PLOTLY_CHART_KWARGS = {"use_container_width": True}

RADAR_CHART_CONFIG = {
    "modeBarButtonsToAdd": ["resetCameraDefault"]
}

DATAFRAME_KWARGS = {"width": "stretch"}

# Metric labels
METRIC_LABELS = {
    'engagement_rating': 'ワーク･エンゲージメント',
    'vigor_rating': '活力 (Vigor)',
    'dedication_rating': '熱意 (Dedication)',
    'absorption_rating': '没頭 (Absorption)'
}

# Signal labels
SIGNAL_LABELS = {
    'name': '氏名',
    'intervention_priority': '介入優先度',
    'trend_refined': '中期トレンド',
    'change_tag': '短期変動',
    'stability': '中期安定性',
    'engagement_rating': 'エンゲージメント',
    'vigor_rating': '活力',
    'dedication_rating': '熱意',
    'absorption_rating': '没頭',
    'strength_short': '強み（短期）',
    'weakness_short': '弱み（短期）',
    'strength_mid': '強み（中期）',
    'weakness_mid': '弱み（中期）'
}

# Rating axis maximum
RATING_AXIS_MAX = 10.3

# Trend color groups
POSITIVE_TRENDS = ['上昇加速', '上昇継続', '回復期待', '回復', '復活', '上昇期待', '上昇']
NEGATIVE_TRENDS = ['低下懸念', '悪化', '低下危機', '低下加速', '低下継続', '低下警戒', '下降']

# Signal table display columns
SIGNAL_TABLE_COLUMNS = ['name', 'intervention_priority', 'trend_refined', 'change_tag', 'stability']
INDIVIDUAL_SIGNAL_COLUMNS = [
    'intervention_priority', 'trend_refined', 'change_tag', 'stability',
    'strength_short', 'weakness_short', 'strength_mid', 'weakness_mid'
]

# Group order configuration file
GROUP_ORDER_FILE = Path(__file__).parent.parent / 'group_order_config.json'

# Rating calculation constants
ENGAGEMENT_DIVISOR = 5.4
COMPONENT_DIVISOR = 1.8

# Rating band thresholds
RATING_BAND_HIGH_THRESHOLD = 6.0
RATING_BAND_LOW_THRESHOLD = 2.0

# Color scale configuration
COLOR_SCALE_START = 0.35
COLOR_SCALE_END = 1

# Grouping label map
GROUPING_LABEL_MAP = {
    'なし': 'なし',
    'department': '部署別',
    'group': '課別',
    'section': '部門別',
    'team': 'チーム別',
    'project': 'プロジェクト別',
    'grade': '職位別',
    'name': '個人別'
}

# Group labels (without 別 suffix)
GROUP_LABELS = {
    'section': '部門',
    'department': '部署',
    'group': '課',
    'team': 'チーム',
    'project': 'プロジェクト',
    'grade': '職位',
    'name': '個人'
}

# Default data file
DEFAULT_FILE_PATH = "EngagementMasterSS.xlsx"
