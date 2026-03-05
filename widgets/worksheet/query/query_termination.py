from PyQt6.QtWidgets import QMessageBox

from widgets.worksheet.query.query_feedback import replace_message, set_global_status, set_tab_status
from widgets.worksheet.query.query_runtime import clear_query_runtime


def finalize_terminated_query(
    manager,
    tab,
    message_text,
    global_status_text,
    stop_timeout=True,
    warning_title=None,
    warning_text=None,
):
    replace_message(tab, message_text)
    set_tab_status(tab, message_text)
    manager.results_manager.stop_spinner(tab, success=False)
    clear_query_runtime(manager, tab, stop_timeout=stop_timeout)
    set_global_status(manager, global_status_text)

    if warning_title and warning_text:
        QMessageBox.warning(manager, warning_title, warning_text)

    manager._refresh_editor_layout_for_tab(tab)
