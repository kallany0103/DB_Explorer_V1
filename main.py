# main.py
import sys
#from PyQt6.QtWidgets import QApplication
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception:
        error_msg = traceback.format_exc()
        print(error_msg, file=sys.stderr)
        QMessageBox.critical(None, "DB Explorer Error", f"An unexpected error occurred during startup:\n\n{error_msg}")
        sys.exit(1)
    