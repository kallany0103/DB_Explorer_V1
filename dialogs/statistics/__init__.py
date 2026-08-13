# dialogs/statistics/__init__.py

from .database_statistics_dialog import DatabaseStatisticsDialog
from .stats_dialog import ObjectStatisticsDialog
from .stats_tab import StatisticsTab

__all__ = [
    "DatabaseStatisticsDialog",
    "ObjectStatisticsDialog",
    "StatisticsTab",
]
