from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
import os
import json

def get_saved_theme():
    """Reads the saved theme from session_state.json, defaulting to Grey (Default)."""
    try:
        if os.path.exists("session_state.json"):
            with open("session_state.json", "r") as f:
                data = json.load(f)
                return data.get("theme", "Grey (Default)")
    except Exception:
        pass
    return "Grey (Default)"

def setup_theme(app: QApplication, theme_name=None):
    """
    Applies the global theme, palette, and enforces the 'Fusion' style
    to ensure consistent rendering across Windows 10, Windows 11, and other OSes.
    """
    app.setStyle("Fusion")
    
    if theme_name is None:
        theme_name = get_saved_theme()

    palette = QPalette()
    
    if theme_name == "Light Blue":
        window_bg = "#E1EAEE"  # Subtle Light Blue
        alt_bg = "#F2F7FA"
        highlight = "#007acc"
    elif theme_name == "Light Green":
        window_bg = "#E6ECE6"  # Subtle Light Green
        alt_bg = "#F4F8F4"
        highlight = "#28a745"
    else:
        # Default / Grey
        window_bg = "#ECEFF3"
        alt_bg = "#F7F8FA"
        highlight = "#8E959E"

    palette.setColor(QPalette.ColorRole.Window, QColor(window_bg))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(alt_bg))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Button, QColor(window_bg))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(highlight))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9CA3AF"))
        
    app.setPalette(palette)
    
    # Load global application stylesheet
    style_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            qss = f.read()
            
        if theme_name == "Light Blue":
            qss = qss.replace("#9FA6AF", "#859FB3")
            qss = qss.replace("#8B929B", "#748C9E")
            qss = qss.replace("#8E959E", "#6E93B0")
        elif theme_name == "Light Green":
            qss = qss.replace("#9FA6AF", "#95B395")
            qss = qss.replace("#8B929B", "#839E83")
            qss = qss.replace("#8E959E", "#7EB07E")
            
        app.setStyleSheet(qss)

