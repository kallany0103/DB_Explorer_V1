from PySide6.QtWidgets import QMenu, QApplication
from PySide6.QtGui import QAction
from db.object_describe import _detect_db_code
from ui.icons import AppIcons, get_icon
from ui.menu_style import apply_menu_style
from ui.feature_flags import is_feature_enabled
from widgets.worksheet.query.query_preparation import get_tab_connection_data


def show_editor_context_menu(manager, pos, editor):
    menu = QMenu(manager)
    apply_menu_style(menu)

    undo_action = QAction(get_icon(AppIcons.UNDO), "Undo", manager)
    undo_action.setIconVisibleInMenu(True)
    undo_action.setShortcut("Ctrl+Z")
    undo_action.triggered.connect(editor.undo)
    undo_action.setEnabled(editor.document().isUndoAvailable())
    menu.addAction(undo_action)

    redo_action = QAction(get_icon(AppIcons.REDO), "Redo", manager)
    redo_action.setIconVisibleInMenu(True)
    redo_action.setShortcut("Ctrl+Y")
    redo_action.triggered.connect(editor.redo)
    redo_action.setEnabled(editor.document().isRedoAvailable())
    menu.addAction(redo_action)

    menu.addSeparator()

    cut_action = QAction(get_icon(AppIcons.CUT), "Cut", manager)
    cut_action.setIconVisibleInMenu(True)
    cut_action.setShortcut("Ctrl+X")
    cut_action.triggered.connect(editor.cut)
    cut_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(cut_action)

    copy_action = QAction(get_icon(AppIcons.COPY), "Copy", manager)
    copy_action.setIconVisibleInMenu(True)
    copy_action.setShortcut("Ctrl+C")
    copy_action.triggered.connect(editor.copy)
    copy_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(copy_action)

    paste_action = QAction(get_icon(AppIcons.PASTE), "Paste", manager)
    paste_action.setIconVisibleInMenu(True)
    paste_action.setShortcut("Ctrl+V")
    paste_action.triggered.connect(editor.paste)
    clipboard = QApplication.clipboard()
    paste_action.setEnabled(clipboard.mimeData().hasText())
    menu.addAction(paste_action)

    menu.addSeparator()

    select_all_action = QAction("Select All", manager)
    select_all_action.setShortcut("Ctrl+A")
    select_all_action.triggered.connect(editor.selectAll)
    menu.addAction(select_all_action)

    menu.addSeparator()

    tab = manager.tab_widget.currentWidget() if hasattr(manager, "tab_widget") else None
    conn_data = get_tab_connection_data(tab) if tab else None
    code = _detect_db_code(conn_data) if isinstance(conn_data, dict) and conn_data else ""
    is_explain_supported = bool(code in ("ORACLE", "ORACLE_DB", "ORACLE_FA", "POSTGRES", "POSTGRESQL") or (
        "ORACLE" in code or "POSTGRES" in code
    ))
    is_optimize_supported = is_explain_supported

    if is_feature_enabled(manager, "execution_plan"):
        explain_analyze_action = QAction("Explain Analyze", manager)
        explain_analyze_action.triggered.connect(manager.explain_query)
        explain_analyze_action.setEnabled(is_explain_supported)
        menu.addAction(explain_analyze_action)

        explain_plan_action = QAction("Explain Plan", manager)
        explain_plan_action.triggered.connect(manager.explain_plan_query)
        explain_plan_action.setEnabled(is_explain_supported)
        menu.addAction(explain_plan_action)

    if is_feature_enabled(manager, "ai_assistant"):
        explain_ai_action = QAction(get_icon(AppIcons.EXPLAIN_AI), "Explain with AI", manager)
        explain_ai_action.setIconVisibleInMenu(True)
        explain_ai_action.setShortcut("Ctrl+Alt+E")
        explain_ai_action.triggered.connect(manager.main_window.explain_code_using_ai)
        menu.addAction(explain_ai_action)

    if is_feature_enabled(manager, "sql_optimizer"):
        optimize_sql_action = QAction(get_icon(AppIcons.OPTIMIZE_QUERY), "Optimize SQL", manager)
        optimize_sql_action.setIconVisibleInMenu(True)
        optimize_sql_action.setShortcut("Ctrl+Alt+O")
        optimize_sql_action.triggered.connect(manager.optimize_query)
        optimize_sql_action.setEnabled(is_optimize_supported)
        menu.addAction(optimize_sql_action)

        optimize_batch_action = QAction(get_icon(AppIcons.OPTIMIZE_BATCH), "Optimize Script Workload (Batch)...", manager)
        optimize_batch_action.setIconVisibleInMenu(True)
        optimize_batch_action.setShortcut("Ctrl+Shift+O")
        optimize_batch_action.triggered.connect(manager.optimize_workload_script)
        optimize_batch_action.setEnabled(is_optimize_supported)
        menu.addAction(optimize_batch_action)




    menu.addSeparator()
    format_action = QAction(get_icon(AppIcons.FORMAT_SQL), "Format SQL", manager)
    format_action.setIconVisibleInMenu(False)
    format_action.setShortcut("Ctrl+Shift+F")
    format_action.triggered.connect(manager.format_sql_text)
    menu.addAction(format_action)

    menu.exec(editor.mapToGlobal(pos))
