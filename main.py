# main.py
import sys
import os
import pathlib
import traceback
import multiprocessing
import time
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QThread, Signal, QEventLoop
from PySide6.QtGui import QIcon
from widgets.splash_screen import SplashScreen
from widgets.encryption.secure_sqlite import enable_transparent_encryption
from db.db_bootstrap import ensure_hierarchy_db
from ui.theme import setup_theme
from main_window import MainWindow

os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"


class _StartupWorker(QThread):
    """Runs all blocking startup I/O off the main thread."""

    progress: Signal = Signal(str, int)  # (message, percent)
    finished: Signal = Signal()
    failed: Signal = Signal(str)         # traceback string

    def run(self) -> None:
        try:
            enable_transparent_encryption("mysecretpassword")

            self.progress.emit("Bootstrapping database...", 10)
            ensure_hierarchy_db()
            time.sleep(3)  # DEBUG: Artificial delay to test splash screen dragging

        except Exception:
            self.failed.emit(traceback.format_exc())
        else:
            self.finished.emit()


if __name__ == "__main__":

    multiprocessing.freeze_support()  # required for ProcessPoolExecutor in PyInstaller executable

    app = QApplication(sys.argv)

    _icon_path = pathlib.Path(__file__).parent / "assets" / "sql_icon.ico"
    if not _icon_path.exists():
        _icon_path = pathlib.Path(__file__).parent / "assets" / "sql_icon.png"
    app.setWindowIcon(QIcon(str(_icon_path)))

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Run blocking I/O on a worker thread so the main thread stays free
    # to dispatch events — keeping the splash screen fully interactive/draggable.
    loop = QEventLoop()

    worker = _StartupWorker()
    worker.progress.connect(lambda msg, val: splash.advance(msg, val))
    worker.finished.connect(loop.quit)
    worker.failed.connect(lambda err: (setattr(loop, "_startup_error", err), loop.quit()))
    worker.start()

    loop.exec()  # main thread is free here; splash is fully draggable

    if hasattr(loop, "_startup_error"):
        splash.close()
        QMessageBox.critical(
            None,
            "Universal SQL Client — Startup Error",
            f"Startup failed:\n\n{loop._startup_error}",
        )
        sys.exit(1)

    # theme and window construction must stay on the main (GUI) thread
    splash.advance("Applying theme...", 50)
    setup_theme(app)

    splash.advance("Loading main window...", 75)
    try:
        window = MainWindow()
        splash.advance("Ready...", 100)
        window.show()
        splash.close()
        sys.exit(app.exec())
    except Exception:
        if splash.isVisible():
            splash.close()
        QMessageBox.critical(
            None,
            "Universal SQL Client Error",
            f"An unexpected error occurred during startup:\n\n{traceback.format_exc()}",
        )
        sys.exit(1)