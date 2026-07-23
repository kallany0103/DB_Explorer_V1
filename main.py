# main.py
import sys
import os
import pathlib
import traceback
import multiprocessing
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from main_window import MainWindow
from ui.theme import setup_theme
from widgets.encryption.secure_sqlite import enable_transparent_encryption

os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"

if __name__ == "__main__":

    multiprocessing.freeze_support()  # required for ProcessPoolExecutor in PyInstaller executable
    enable_transparent_encryption("mysecretpassword")
    
    # Bootstrap the database schema/tables if they don't exist
    from db.db_bootstrap import ensure_hierarchy_db
    try:
        ensure_hierarchy_db()
    except Exception as e:
        print(f"Database bootstrap failed: {e}", file=sys.stderr)
        
    app = QApplication(sys.argv)

    # Set application icon (taskbar, title bar, Alt+Tab)
    _icon_path = pathlib.Path(__file__).parent / "assets" / "sql_icon.ico"
    if not _icon_path.exists():
        _icon_path = pathlib.Path(__file__).parent / "assets" / "sql_icon.png"
    app_icon = QIcon(str(_icon_path))
    app.setWindowIcon(app_icon)

    setup_theme(app)

    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        error_msg = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        QMessageBox.critical(None, "DB Explorer Error", f"An unexpected error occurred during startup:\n\n{error_msg}")
        sys.exit(1)
    