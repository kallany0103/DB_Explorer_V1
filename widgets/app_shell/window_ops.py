# from PyQt6.QtWidgets import QSplitter, QMessageBox
# from PyQt6.QtGui import QDesktopServices
# from PyQt6.QtCore import QUrl

from PySide6.QtWidgets import QSplitter, QMessageBox, QStackedWidget, QTabWidget, QTextEdit, QWidget, QPushButton
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl


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
        main_window.showMaximized()
        
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
        import traceback
        traceback.print_exc()

def reset_to_dashboard(main_window):
    try:
        main_window.showMaximized()
        main_window.main_splitter.setSizes([280, 920])
        if hasattr(main_window, 'connection_manager'):
            cm = main_window.connection_manager
            if hasattr(cm, 'vertical_splitter'):
                cm.vertical_splitter.setSizes([240, 360])
            if hasattr(cm, 'tree'):
                cm.tree.collapseAll()
            if hasattr(cm, 'schema_tree'):
                cm.schema_tree.collapseAll()

        # Add dashboard tab first
        main_window.add_dashboard_tab()
        
        main_window.status.showMessage("Layout reset to Dashboard.", 4000)
    except Exception as e:
        main_window.status.showMessage(f"Error resetting layout: {e}", 5000)
        import traceback
        traceback.print_exc()

def toggle_maximize(main_window):
    if main_window.isMaximized():
        main_window.showNormal()
    else:
        main_window.showMaximized()


def open_help_url(main_window, url_string):
    if not QDesktopServices.openUrl(QUrl(url_string)):
        QMessageBox.warning(main_window, "Open URL", f"Could not open URL: {url_string}")


def update_thread_pool_status(main_window):
    active = main_window.thread_pool.activeThreadCount()
    max_threads = main_window.thread_pool.maxThreadCount()
    main_window.status.showMessage(f"ThreadPool: {active} active of {max_threads}", 3000)
