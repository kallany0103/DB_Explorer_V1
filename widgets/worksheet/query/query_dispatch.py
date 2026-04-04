from PySide6.QtWidgets import QLabel

from widgets.worksheet.query.query_feedback import set_global_status
from widgets.worksheet.query.query_runtime import begin_query_runtime
from widgets.worksheet.query.query_view_state import show_loading_view


def dispatch_query(
    manager,
    current_tab,
    conn_data,
    query_sql,
    status_text,
    worker_factory,
    output_mode="current",
    output_tab_index=None,
):
    show_loading_view(current_tab)

    tab_status_label = current_tab.findChild(QLabel, "tab_status_label")
    runnable = worker_factory(
        manager,
        current_tab,
        conn_data,
        query_sql,
        output_mode=output_mode,
        output_tab_index=output_tab_index,
    )
    begin_query_runtime(manager, current_tab, tab_status_label, runnable)
    set_global_status(manager, status_text)
    return runnable
