from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
import os

def setup_theme(app: QApplication):
    """
    Applies the global theme, palette, and enforces the 'Fusion' style
    to ensure consistent rendering across Windows 10, Windows 11, and other OSes.
    """
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#ECEFF3"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F7F8FA"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ECEFF3"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#8E959E"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1f2937"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#9CA3AF"))
    app.setPalette(palette)
    
    # Load global application stylesheet
    style_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
