# main.py
import sys
import os
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor
from main_window import MainWindow
from widgets.encryption.secure_sqlite import enable_transparent_encryption

os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"

if __name__ == "__main__":
    enable_transparent_encryption("mysecretpassword")

    app = QApplication(sys.argv)

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

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        error_msg = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        QMessageBox.critical(None, "DB Explorer Error", f"An unexpected error occurred during startup:\n\n{error_msg}")
        sys.exit(1)
    