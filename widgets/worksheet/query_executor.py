import time

from PySide6.QtWidgets import (
    QMessageBox,
)

from widgets.worksheet.query.query_feedback import (
    append_error_message,
    set_global_status,
    set_tab_status,
)
from widgets.worksheet.query.query_dispatch import dispatch_query
from widgets.worksheet.query.query_explain import build_explain_sql, validate_explain_connection
from widgets.worksheet.query.query_preparation import (
    apply_select_pagination,
    extract_query_under_cursor,
    get_query_editor,
    get_tab_connection_data,
    resolve_output_tab_index,
    resolve_query_context,
)
from widgets.worksheet.query.query_runtime import (
    clear_query_timers,
    clear_running_query,
)
from widgets.worksheet.query.query_termination import finalize_terminated_query
from widgets.worksheet.query.query_view_state import show_error_view
from widgets.results_view.perf_metrics import perf_elapsed_ms, perf_mark, perf_now, perf_record
from workers import RunnableQuery, QuerySignals


def start_query_worker(manager, current_tab, conn_data, query, output_mode="current", output_tab_index=None):
    signals = QuerySignals()
    signals._target_tab = current_tab
    signals._output_mode = output_mode
    signals._output_tab_index = output_tab_index
    signals._perf_dispatch_start = perf_now()

    runnable = RunnableQuery(conn_data, query, signals)
    signals.finished.connect(manager._on_query_finished_signal)
    signals.error.connect(manager._on_query_error_signal)
    return runnable


def _is_stale_query_signal(manager, signals, target_tab):
    if target_tab is None:
        return True

    signal_runnable = getattr(signals, "_runnable_ref", None)
    if signal_runnable is not None:
        active_runnable = manager.running_queries.get(target_tab)
        if active_runnable is not signal_runnable:
            return True

    signal_operation_id = getattr(signals, "_operation_id", None)
    if signal_operation_id:
        timer_state = manager.tab_timers.get(target_tab)
        if not timer_state:
            return True
        if timer_state.get("operation_id") != signal_operation_id:
            return True

    return False


def on_query_finished_signal(manager, conn_data, query, results, columns, column_specs, row_count, elapsed_time, is_select_query):
    signals = manager.sender()
    target_tab = getattr(signals, "_target_tab", manager.tab_widget.currentWidget())
    if _is_stale_query_signal(manager, signals, target_tab):
        return

    dispatch_start = getattr(signals, "_perf_dispatch_start", None)
    perf_record(manager, "query_dispatch_to_finish_ms", perf_elapsed_ms(dispatch_start))
    output_mode = getattr(signals, "_output_mode", "current")
    output_tab_index = getattr(signals, "_output_tab_index", None)
    manager.handle_query_result(
        target_tab,
        output_mode,
        output_tab_index,
        conn_data,
        query,
        results,
        columns,
        column_specs,
        row_count,
        elapsed_time,
        is_select_query,
    )


def on_query_error_signal(manager, conn_data, query, row_count, elapsed_time, error_message):
    signals = manager.sender()
    target_tab = getattr(signals, "_target_tab", manager.tab_widget.currentWidget())
    if _is_stale_query_signal(manager, signals, target_tab):
        return

    output_tab_index = getattr(signals, "_output_tab_index", None)
    manager.handle_query_error(target_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message)

def explain_plan_query(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return

    query_editor = get_query_editor(current_tab)
    conn_data = get_tab_connection_data(current_tab)

    connection_error = validate_explain_connection(conn_data, analyze=False)
    if connection_error:
        manager.show_info(connection_error)
        return

    selected_query = extract_query_under_cursor(query_editor)
    if not selected_query:
        manager.show_info("Please select a query to explain.")
        return

    explain_sql, explain_error = build_explain_sql(selected_query, analyze=False)
    if explain_error:
        manager.show_info(explain_error)
        return

    dispatch_query(
        manager,
        current_tab,
        conn_data,
        explain_sql,
        "Executing Explain Plan...",
        start_query_worker,
        output_mode="current",
        output_tab_index=None,
    )


def explain_query(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return

    query_editor = get_query_editor(current_tab)
    conn_data = get_tab_connection_data(current_tab)

    connection_error = validate_explain_connection(conn_data, analyze=True)
    if connection_error:
        manager.show_info(connection_error)
        return

    selected_query = extract_query_under_cursor(query_editor)
    if not selected_query:
        manager.show_info("Please select a query to explain.")
        return

    explain_sql, explain_error = build_explain_sql(selected_query, analyze=True)
    if explain_error:
        manager.show_info(explain_error)
        return

    dispatch_query(
        manager,
        current_tab,
        conn_data,
        explain_sql,
        "Executing Explain Analyze...",
        start_query_worker,
        output_mode="current",
        output_tab_index=None,
    )


def execute_query(manager, conn_data=None, query=None, output_mode="current", preserve_pagination=False):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return

    conn_data, query = resolve_query_context(current_tab, conn_data, query)

    if not query or not query.strip():
        manager.show_info("Please enter a valid query.")
        return

    query = apply_select_pagination(query, current_tab, preserve_pagination=preserve_pagination)
    perf_mark(manager, "query_execute_start")

    output_tab_index = resolve_output_tab_index(manager, current_tab, output_mode=output_mode)

    dispatch_query(
        manager,
        current_tab,
        conn_data,
        query,
        "Executing query...",
        start_query_worker,
        output_mode=output_mode,
        output_tab_index=output_tab_index,
    )


def update_timer_label(manager, label, tab):
    if not label or tab not in manager.tab_timers:
        return
    elapsed = time.time() - manager.tab_timers[tab]["start_time"]
    label.setText(f"Running... {elapsed:.1f} sec")


def show_error_popup(error_text, parent=None):
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("Query Error")
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setText("Query execution failed")
    msg_box.setInformativeText(error_text)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()


def handle_query_error(manager, current_tab, output_tab_index, conn_data, query, row_count, elapsed_time, error_message):
    clear_query_timers(manager, current_tab, stop_timeout=True)

    manager.save_query_to_history(conn_data, query, "Failure", row_count, elapsed_time)

    set_tab_status(current_tab, "")
    append_error_message(current_tab, error_message)

    show_error_view(current_tab)

    set_global_status(manager, "Error occurred")
    manager.results_manager.stop_spinner(current_tab, success=False)

    show_error_popup(error_message, parent=current_tab)
    manager._refresh_editor_layout_for_tab(current_tab)

    clear_running_query(manager, current_tab)


def handle_query_timeout(manager, tab, runnable):
    if manager.running_queries.get(tab) is runnable:
        runnable.cancel()
        error_message = f"Error: Query Timed Out after {manager.QUERY_TIMEOUT / 1000} seconds."
        finalize_terminated_query(
            manager,
            tab,
            message_text=error_message,
            global_status_text="Error occurred",
            stop_timeout=True,
            warning_title="Query Timeout",
            warning_text=f"The query was stopped as it exceeded {manager.QUERY_TIMEOUT / 1000}s.",
        )


def cancel_current_query(manager):
    current_tab = manager.tab_widget.currentWidget()
    runnable = manager.running_queries.get(current_tab)
    if runnable:
        runnable.cancel()
        cancel_message = "Query cancelled by user."
        finalize_terminated_query(
            manager,
            current_tab,
            message_text=cancel_message,
            global_status_text="Query Cancelled",
            stop_timeout=True,
        )
