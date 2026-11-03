# ui/messages_style.py
"""Styling and constants for modern card-based Messages tab view."""


# Accent Colors matching modern design
COLOR_SUCCESS = "#00c951"
COLOR_ERROR = "#ef4444"
COLOR_INFO = "#3b82f6"
COLOR_WARNING = "#f59e0b"

COLOR_TIMESTAMP = "#9ca3af"
COLOR_BORDER_HOVER = "#e2e8f0"

TEXT_COLOR_SUCCESS = "#00c951"
TEXT_COLOR_ERROR = "#b91c1c"
TEXT_COLOR_DEFAULT = "#1f2937"

MESSAGES_SCROLL_STYLE = """
QScrollArea {
    background-color: #ffffff;
    border: none;
}
QScrollBar:vertical {
    border: none;
    background: #f8fafc;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

COPY_BUTTON_STYLE = """
QToolButton {
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px;
}
QToolButton:hover {
    background-color: #f1f5f9;
}
QToolButton:pressed {
    background-color: #e2e8f0;
}
"""


def format_elapsed_time_hms(seconds: float) -> str:
    """Format elapsed time in seconds to HH:MM:SS format."""
    secs = max(0, int(round(seconds)))
    hours = secs // 3600
    minutes = (secs % 3600) // 60
    rem_seconds = secs % 60
    return f"{hours:02d}:{minutes:02d}:{rem_seconds:02d}"

