
from typing import Dict
from ..Model.supportLevel import SupportLevelConfig

SUPPORT_LEVELS: Dict[str, SupportLevelConfig] = {
    "none": {"pct": 5, "color": "#e59aa5", "label": "None"},
    "limited": {"pct": 30, "color": "#ebb184", "label": "Limited"},
    "indirect": {"pct": 50, "color": "#e3a377", "label": "Indirect"},
    "moderate": {"pct": 70, "color": "#c2c9d4", "label": "Moderate"},
    "direct": {"pct": 100, "color": "#d9dde5", "label": "Direct"},
}