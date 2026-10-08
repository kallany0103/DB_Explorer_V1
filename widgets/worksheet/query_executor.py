import time

from PySide6.QtWidgets import (
    QMessageBox, QLabel
)
import qtawesome as qta


from widgets.worksheet.query.query_feedback import (
    append_error_message,
    set_global_status,
    set_tab_status,
)
from widgets.worksheet.query.query_dispatch import dispatch_query
from widgets.worksheet.query.query_explain import build_explain_sql, validate_explain_connection
from widgets.worksheet.query.query_preparation import (
    apply_select_pagination,
    extract_identifier_under_cursor,
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


def describe_query(manager):
    """
    Toad for Oracle: 'Describe (Parse) Select Query' (Shift+F4).
    Parses the active SELECT statement or selection without executing/fetching rows.
    """
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        manager.show_info("Please open a worksheet tab with a database connection to describe a query.")
        return

    query_editor = get_query_editor(current_tab)
    conn_data = get_tab_connection_data(current_tab)

    if not conn_data:
        manager.show_info("Please select a database connection for the current worksheet.")
        return

    from db.query_describe import resolve_describe_query

    clean_query = ""
    object_name = None
    resolve_error = None

    # 1. If text is explicitly highlighted/selected, prioritize the selection
    cursor = query_editor.textCursor() if query_editor else None
    if cursor and cursor.hasSelection():
        selected_text = cursor.selectedText().replace('\u2029', '\n').strip()
        if selected_text:
            try:
                clean_query, object_name = resolve_describe_query(selected_text)
            except ValueError as val_err:
                manager.show_info(str(val_err))
                return

    # 2. If no selection, check query under cursor
    if not clean_query:
        selected_query = extract_query_under_cursor(query_editor) if query_editor else ""
        if selected_query and selected_query.strip():
            try:
                clean_query, object_name = resolve_describe_query(selected_query)
            except ValueError as val_err:
                resolve_error = str(val_err)

    if not clean_query:
        msg = resolve_error or "Please place the cursor in or select a SELECT query to describe."
        manager.show_info(msg)
        return

    from dialogs.tools.query_describe_dialog import QueryDescribeDialog
    dlg = QueryDescribeDialog(parent=manager.main_window, conn_data=conn_data, query=clean_query, object_name=object_name)
    dlg.exec()


RESERVED_SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "UPDATE", "DELETE",
    "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "OUTER", "CROSS", "ON",
    "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "OFFSET", "UNION", "ALL",
    "SET", "VALUES", "AS", "AND", "OR", "NOT", "IN", "IS", "NULL",
    "CASE", "WHEN", "THEN", "ELSE", "END", "DISTINCT", "EXISTS", "BETWEEN",
    "CREATE", "ALTER", "DROP", "TABLE", "VIEW", "SCHEMA", "DATABASE", "INDEX",
}


def describe_object(manager, target: str = None, conn_data: dict = None):
    """
    Toad for Oracle: 'Describe' (F4).
    Describes database tables, views, and schemas.
    """
    current_tab = manager.tab_widget.currentWidget()

    # 1. Resolve connection data
    if not conn_data:
        if current_tab:
            conn_data = get_tab_connection_data(current_tab)
        if not conn_data:
            conn_mgr = getattr(manager.main_window, "connection_manager", None)
            if conn_mgr and hasattr(conn_mgr, "_get_selected_schema_item_data"):
                item_data = conn_mgr._get_selected_schema_item_data()
                if item_data:
                    conn_data = item_data.get("connection") or item_data

    if not conn_data:
        manager.show_info("Please select a database connection to describe an object.")
        return

    query_editor = get_query_editor(current_tab) if current_tab else None
    resolved_target = (target or "").strip()

    # 2. If target not provided, resolve from editor selection or cursor
    if not resolved_target and query_editor:
        cursor = query_editor.textCursor()
        if cursor and cursor.hasSelection():
            sel = cursor.selectedText().replace('\u2029', '\n').strip()
            # If selection is a single token / name without newlines
            if sel and "\n" not in sel and len(sel) < 128:
                resolved_target = sel

        if not resolved_target:
            ident = extract_identifier_under_cursor(query_editor)
            if ident and ident.upper() not in RESERVED_SQL_KEYWORDS:
                resolved_target = ident

    # 3. If still empty, prompt the user with QInputDialog
    if not resolved_target:
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(
            manager.main_window,
            "Describe (F4)",
            "Enter Table, View, or Schema name:\n(e.g., employees, hr.departments, public)",
        )
        if ok and text and text.strip():
            resolved_target = text.strip()
        else:
            return

    # Normalize partially selected or malformed quotes (e.g. Emam"."credential)
    from db.object_describe import parse_object_identifier
    s_hint, o_name = parse_object_identifier(resolved_target)
    if s_hint and o_name:
        resolved_target = f'"{s_hint}"."{o_name}"'
    elif o_name:
        resolved_target = o_name

    from dialogs.tools.object_describe_dialog import ObjectDescribeDialog
    dlg = ObjectDescribeDialog(parent=manager.main_window, conn_data=conn_data, target=resolved_target)
    dlg.exec()


def quick_describe(manager, target: str = None, conn_data: dict = None):
    """
    Toad for Oracle: 'Quick Describe' (Ctrl+D).
    Lightweight, fast describe window for database objects with instant editor insertion.
    """
    current_tab = manager.tab_widget.currentWidget()

    # 1. Resolve connection data
    if not conn_data:
        if current_tab:
            conn_data = get_tab_connection_data(current_tab)
        if not conn_data:
            conn_mgr = getattr(manager.main_window, "connection_manager", None)
            if conn_mgr and hasattr(conn_mgr, "_get_selected_schema_item_data"):
                item_data = conn_mgr._get_selected_schema_item_data()
                if item_data:
                    conn_data = item_data.get("connection") or item_data

    # 2. If target not provided, resolve from editor selection or cursor
    resolved_target = (target or "").strip()
    query_editor = get_query_editor(current_tab) if current_tab else None
    if not resolved_target and query_editor:
        cursor = query_editor.textCursor()
        if cursor and cursor.hasSelection():
            sel = cursor.selectedText().replace('\u2029', '\n').strip()
            if sel and "\n" not in sel and len(sel) < 128:
                resolved_target = sel

        if not resolved_target:
            ident = extract_identifier_under_cursor(query_editor)
            if ident and ident.upper() not in RESERVED_SQL_KEYWORDS:
                resolved_target = ident

    # Normalize partially selected or malformed quotes
    if resolved_target:
        from db.object_describe import parse_object_identifier
        s_hint, o_name = parse_object_identifier(resolved_target)
        if s_hint and o_name:
            resolved_target = f'"{s_hint}"."{o_name}"'
        elif o_name:
            resolved_target = o_name

    from dialogs.tools.quick_describe_dialog import QuickDescribeDialog
    dlg = QuickDescribeDialog(
        parent=manager.main_window,
        conn_data=conn_data,
        target=resolved_target,
        worksheet_manager=manager,
    )
    dlg.exec()


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

    # Update status icon to 'Executing' (Hourglass)
    status_icon = current_tab.findChild(QLabel, "conn_status_icon")
    if status_icon:
        status_icon.setPixmap(qta.icon("fa5s.hourglass-half", color="#ff9800").pixmap(18, 18))


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

    # Push to Dashboard Logs tab (non-blocking, best-effort)
    try:
        dw = getattr(manager.main_window, "dashboard_widget", None)
        if dw is not None and conn_data:
            dw.log_query(conn_data, query, "Failure", elapsed_time, row_count)
    except Exception:
        pass

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
