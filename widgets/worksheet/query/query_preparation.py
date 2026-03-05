from PyQt6.QtWidgets import QComboBox, QPlainTextEdit, QTabWidget

from widgets.worksheet.code_editor import CodeEditor


def get_query_editor(current_tab):
    query_editor = current_tab.findChild(CodeEditor, "query_editor")
    if not query_editor:
        query_editor = current_tab.findChild(QPlainTextEdit, "query_editor")
    return query_editor


def extract_query_under_cursor(query_editor):
    cursor = query_editor.textCursor()
    cursor_pos = cursor.position()
    full_text = query_editor.toPlainText()
    queries = full_text.split(";")

    selected_query = ""
    start = 0
    for query_part in queries:
        end = start + len(query_part)
        if start <= cursor_pos <= end:
            selected_query = query_part.strip()
            break
        start = end + 1
    return selected_query


def get_tab_connection_data(current_tab):
    db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
    if not db_combo_box:
        return None
    index = db_combo_box.currentIndex()
    return db_combo_box.itemData(index)


def resolve_query_context(current_tab, conn_data=None, query=None):
    resolved_conn_data = conn_data if isinstance(conn_data, dict) else None
    resolved_query = query if isinstance(query, str) else None

    if resolved_conn_data is not None and resolved_query is not None:
        return resolved_conn_data, resolved_query

    query_editor = get_query_editor(current_tab)
    if resolved_query is None and query_editor:
        resolved_query = extract_query_under_cursor(query_editor)

    if resolved_conn_data is None:
        resolved_conn_data = get_tab_connection_data(current_tab)

    return resolved_conn_data, resolved_query


def apply_select_pagination(query, current_tab, preserve_pagination=False):
    if not query:
        return query

    normalized_query = query.strip().rstrip(";")
    upper_query = normalized_query.upper()

    if upper_query.startswith("SELECT") and not preserve_pagination and "OFFSET" not in upper_query:
        current_tab.current_offset = 0
        current_tab.current_page = 1

    limit = getattr(current_tab, "current_limit", 0)
    offset = getattr(current_tab, "current_offset", 0)

    if upper_query.startswith("SELECT") and limit > 0:
        if "LIMIT" not in upper_query:
            normalized_query += f" LIMIT {limit}"
            upper_query = normalized_query.upper()
        if offset > 0 and "OFFSET" not in upper_query:
            normalized_query += f" OFFSET {offset}"

    return normalized_query + ";"


def resolve_output_tab_index(manager, current_tab, output_mode="current"):
    output_tab_index = None
    if output_mode == "new":
        output_tab_index = manager.results_manager.create_output_tab(current_tab, activate=True)
    else:
        output_tabs = current_tab.findChild(QTabWidget, "output_tabs")
        if output_tabs and output_tabs.currentIndex() >= 0:
            output_tab_index = output_tabs.currentIndex()
    return output_tab_index
