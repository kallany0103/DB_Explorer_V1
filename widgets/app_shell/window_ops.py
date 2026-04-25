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


def restore_tool(main_window):
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

        # 3. Close all tabs except one
        while main_window.tab_widget.count() > 1:
            # We use the main_window.close_tab method which handles manager cleanup
            main_window.close_tab(0)

        # 3b. Clear everything from the remaining tab
        current_tab = main_window.tab_widget.currentWidget()
        if current_tab:
            # Clear editor
            current_editor = main_window._get_current_editor()
            if current_editor:
                current_editor.clear()
            
            # Reset Results View
            results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
            if results_stack:
                # 6 is the index for the 'No data output' placeholder
                results_stack.setCurrentIndex(6)
            
            # Reset Result Tabs
            output_tabs_widget = current_tab.findChild(QTabWidget, "output_tabs")
            if output_tabs_widget:
                # Clear all existing result tabs and recreate a fresh one
                from widgets.results_view.output_tabs import ensure_at_least_one_output_tab
                while output_tabs_widget.count() > 0:
                    output_tabs_widget.removeTab(0)
                ensure_at_least_one_output_tab(main_window.results_manager, current_tab)

            # Clear messages
            message_view = current_tab.findChild(QTextEdit, "message_view")
            if message_view:
                message_view.clear()
            
            # Reset header buttons (uncheck all for the placeholder state)
            results_header = current_tab.findChild(QWidget, "resultsHeader")
            if results_header:
                for btn in results_header.findChildren(QPushButton):
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)

            # Hide bars
            for bar_name in ["resultsInfoBar", "processFilterBar", "processInfoBar"]:
                bar = current_tab.findChild(QWidget, bar_name)
                if bar:
                    bar.hide()

        # 4. Reset Current Tab Splitter
        current_tab = main_window.tab_widget.currentWidget()
        if current_tab:
            tab_splitter = current_tab.findChild(QSplitter, "tab_vertical_splitter")
            if tab_splitter:
                tab_splitter.setSizes([300, 300])
                
        main_window.status.showMessage("Layout reset: Explorer collapsed, extra tabs closed, and sizes restored.", 4000)
    except Exception as e:
        main_window.status.showMessage(f"Error restoring layout: {e}", 5000)
        import traceback
        traceback.print_exc()

def reset_layout(main_window):
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
