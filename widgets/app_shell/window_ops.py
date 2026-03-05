from PyQt6.QtWidgets import QSplitter, QMessageBox
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl


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
    tab = main_window.tab_widget.widget(index)
    if tab in main_window.running_queries:
        main_window.running_queries[tab].cancel()
        del main_window.running_queries[tab]
        if not main_window.running_queries:
            main_window.cancel_action.setEnabled(False)
    if tab in main_window.tab_timers:
        main_window.tab_timers[tab]["timer"].stop()
        if "timeout_timer" in main_window.tab_timers[tab]:
            main_window.tab_timers[tab]["timeout_timer"].stop()
        del main_window.tab_timers[tab]
    if main_window.tab_widget.count() > 1:
        main_window.tab_widget.removeTab(index)
        main_window.renumber_tabs()
    else:
        main_window.status.showMessage("Must keep at least one tab", 3000)


def restore_tool(main_window):
    main_window.main_splitter.setSizes([280, 920])
    main_window.left_vertical_splitter.setSizes([240, 360])
    current_tab = main_window.tab_widget.currentWidget()
    if current_tab:
        tab_splitter = current_tab.findChild(QSplitter, "tab_vertical_splitter")
        if tab_splitter:
            tab_splitter.setSizes([300, 300])
    main_window.status.showMessage("Layout restored to defaults.", 3000)


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
