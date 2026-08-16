from PySide6.QtWidgets import QSplitter, QMessageBox, QApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
import traceback

def close_current_tab(main_window):
    index = main_window.tab_widget.currentIndex()
    if index != -1:
        if main_window.tab_widget.count() == 1:
            main_window.add_tab()
            main_window.close_tab(0)
        else:
            main_window.close_tab(index)


def close_all_tabs(main_window):
    main_window.add_tab()
    while main_window.tab_widget.count() > 1:
        main_window.close_tab(0)
    main_window.status.showMessage("All tabs closed. New worksheet opened.", 3000)


def close_tab(main_window, index):
    wm = main_window.worksheet_manager
    tab = main_window.tab_widget.widget(index)
    if tab in wm.running_queries:
        wm.running_queries[tab].cancel()
        del wm.running_queries[tab]
        if not wm.running_queries:
            main_window.cancel_action.setEnabled(False)
    if tab in wm.tab_timers:
        wm.tab_timers[tab]["timer"].stop()
        if "timeout_timer" in wm.tab_timers[tab]:
            wm.tab_timers[tab]["timeout_timer"].stop()
        del wm.tab_timers[tab]
    if main_window.tab_widget.count() > 1:
        main_window.tab_widget.removeTab(index)
        main_window.renumber_tabs()
    else:
        main_window.status.showMessage("Must keep at least one tab", 3000)


def reset_layout(main_window):
    try:
        # Always maximize the window on layout restore
        main_window.toggle_maximize() if not getattr(main_window, "_is_maximized", False) else None

        # 1. Reset Splitter Sizes
        main_window.main_splitter.setSizes([280, 920])
        if hasattr(main_window, 'connection_manager'):
            cm = main_window.connection_manager
            if hasattr(cm, 'vertical_splitter'):
                cm.vertical_splitter.setSizes([240, 360])

            # 2. Collapse DB Explorer Trees
            if hasattr(cm, 'tree'):
                cm.tree.collapseAll()
            if hasattr(cm, 'schema_tree'):
                cm.schema_tree.collapseAll()
            if hasattr(cm, 'schema_model'):
                cm.schema_model.clear()
                cm.schema_model.setHorizontalHeaderLabels(["Database Schema"])

        # 3. Close all tabs and ensure a single fresh worksheet remains
        main_window.add_tab()
        while main_window.tab_widget.count() > 1:
            main_window.close_tab(0)

        # 4. Reset Current Tab Splitter
        current_tab = main_window.tab_widget.currentWidget()
        if current_tab:
            tab_splitter = current_tab.findChild(QSplitter, "tab_vertical_splitter")
            if tab_splitter:
                tab_splitter.setSizes([300, 300])

        main_window.status.showMessage("Layout reset: Explorer collapsed, extra tabs closed, and sizes restored.", 4000)
    except Exception as e:
        main_window.status.showMessage(f"Error resetting layout: {e}", 5000)
        traceback.print_exc()


def reset_to_dashboard(main_window):
    try:
        if not getattr(main_window, "_is_maximized", False):
            main_window.toggle_maximize()
        main_window.main_splitter.setSizes([280, 920])
        if hasattr(main_window, 'connection_manager'):
            cm = main_window.connection_manager
            if hasattr(cm, 'vertical_splitter'):
                cm.vertical_splitter.setSizes([240, 360])

        # Add dashboard tab first
        main_window.add_dashboard_tab()

        main_window.status.showMessage("Layout reset to Dashboard.", 4000)
    except Exception as e:
        main_window.status.showMessage(f"Error resetting layout: {e}", 5000)
        traceback.print_exc()


def toggle_maximize(main_window):
    """Toggle between maximized and normal state for a frameless window.

    ``showMaximized()`` on a frameless window expands to the full monitor
    rectangle (covering the taskbar).  Instead we manually move/resize the
    window to ``QScreen.availableGeometry()``, which excludes the taskbar,
    and track the state ourselves via ``_is_maximized``.
    """
    if getattr(main_window, "_is_maximized", False):
        # Restore to the geometry saved before maximizing
        pre = getattr(main_window, "_pre_max_geometry", None)
        if pre is not None:
            main_window.setGeometry(pre)
        else:
            main_window.showNormal()
        main_window._is_maximized = False
        main_window.maximize_action.setText("Maximize")
    else:
        # Save current normal geometry before expanding
        main_window._pre_max_geometry = main_window.geometry()
        screen = (
            QApplication.screenAt(main_window.geometry().center())
            or QApplication.primaryScreen()
        )
        avail = screen.availableGeometry()
        
        # If the taskbar is auto-hidden, availableGeometry equals the full screen.
        # A frameless window sized exactly to the screen enters 'exclusive fullscreen'
        # mode on Windows, which blocks the auto-hidden taskbar from popping up.
        # We subtract 1 pixel to prevent exclusive mode.
        if avail == screen.geometry():
            avail.setHeight(avail.height() - 1)
            
        main_window.setGeometry(avail)
        main_window._is_maximized = True
        main_window.maximize_action.setText("Restore")
    # Icon update is handled by title_bar.update_maximize_button() using
    # pre-cached icons — do not call qta.icon() here to avoid stutter.


def open_help_url(main_window, url_string):
    if not QDesktopServices.openUrl(QUrl(url_string)):
        QMessageBox.warning(main_window, "Open URL", f"Could not open URL: {url_string}")


def update_thread_pool_status(main_window):
    active = main_window.thread_pool.activeThreadCount()
    max_threads = main_window.thread_pool.maxThreadCount()
    main_window.thread_pool_status_label.setText(
        f"ThreadPool: {active} active of {max_threads}"
    )
