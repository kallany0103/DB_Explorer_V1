# main.py
import ctypes
import sys
import os
import pathlib
import traceback
import multiprocessing
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QThread, Signal, QEventLoop
from PySide6.QtGui import QIcon
from widgets.splash_screen import SplashScreen
from db.db_bootstrap import ensure_hierarchy_db
from ui.theme import setup_theme
from main_window import MainWindow

os.environ["QT_QPA_PLATFORM"] = "windows:darkmode=0"
# Suppress harmless Qt font warnings (legacy bitmap fonts and OpenType script fallbacks for Segoe UI Variable)
_FONT_LOGGING_RULES = "qt.qpa.fonts.warning=false;qt.text.font.db=false;qt.text.font.db.warning=false"
if "QT_LOGGING_RULES" in os.environ:
    os.environ["QT_LOGGING_RULES"] += f";{_FONT_LOGGING_RULES}"
else:
    os.environ["QT_LOGGING_RULES"] = _FONT_LOGGING_RULES

# The AppMutex name must match the AppMutex directive in Universal_SQL_Client.iss.
# Holding this mutex lets the installer/uninstaller detect a running instance.
_APP_MUTEX_NAME = "UniversalSQLClientAppMutex"
_app_mutex_handle = None


def _acquire_app_mutex() -> None:
    global _app_mutex_handle
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _app_mutex_handle = kernel32.CreateMutexW(None, 0, _APP_MUTEX_NAME)
    except Exception:
        _app_mutex_handle = None


class _StartupWorker(QThread):
    """Runs all blocking startup I/O off the main thread."""

    progress: Signal = Signal(str, int)  # (message, percent)
    finished: Signal = Signal()
    failed: Signal = Signal(str)         # traceback string

    def run(self) -> None:
        try:
            self.progress.emit("Bootstrapping database...", 25)
            ensure_hierarchy_db()
        except Exception:
            self.failed.emit(traceback.format_exc())
        else:
            self.finished.emit()


if __name__ == "__main__":

    multiprocessing.freeze_support()  # required for ProcessPoolExecutor in PyInstaller executable

    _acquire_app_mutex()

    app = QApplication(sys.argv)

    _icon_path = pathlib.Path(__file__).parent / "assets" / "sql_icon.png"
    app.setWindowIcon(QIcon(str(_icon_path)))

    splash = SplashScreen()
    splash.show()
    app.processEvents()

    # Run blocking I/O on a worker thread so the main thread stays free
    # to dispatch events — keeping the splash screen fully interactive/draggable.
    loop = QEventLoop()

    worker = _StartupWorker()
    worker.setObjectName("_StartupWorker")
    worker.progress.connect(lambda msg, val: splash.advance(msg, val))
    worker.finished.connect(loop.quit)
    worker.failed.connect(lambda err: (setattr(loop, "_startup_error", err), loop.quit()))
    worker.start()

    loop.exec()  # main thread is free here; splash is fully draggable
    worker.wait(2000)

    if hasattr(loop, "_startup_error"):
        splash.close()
        QMessageBox.critical(
            None,
            "Universal SQL Client — Startup Error",
            f"Startup failed:\n\n{loop._startup_error}",
        )
        sys.exit(1)

    # theme and window construction must stay on the main (GUI) thread
    splash.advance("Applying theme...", 45)
    setup_theme(app)
    app.processEvents()

    splash.advance("Initializing main window...", 55)
    app.processEvents()

    try:
        window = MainWindow(splash=splash)
        splash.advance("Ready...", 100)
        app.processEvents()
        window.show()
        splash.fade_close(duration=250)
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
