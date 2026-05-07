from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
import qtawesome as qta


def build_worksheet_toolbar_actions(manager):
    main_window = manager.main_window

    manager.ws_open_file_action = QAction(
        qta.icon("fa5s.folder-open", color="#555555"), "Open File", manager
    )
    manager.ws_open_file_action.setToolTip("Open SQL File")
    manager.ws_open_file_action.triggered.connect(main_window.open_sql_file)

    manager.ws_save_as_action = QAction(
        qta.icon("fa5s.save", color="#555555"), "Save As", manager
    )
    manager.ws_save_as_action.setToolTip("Save SQL File As")
    manager.ws_save_as_action.triggered.connect(main_window.save_sql_file_as)

    manager.ws_execute_action = QAction(
        QIcon("assets/execute_icon.png"), "Execute", manager
    )
    manager.ws_execute_action.setToolTip("Execute Query (Ctrl+Enter)")
    manager.ws_execute_action.triggered.connect(main_window.execute_query)

    manager.ws_execute_new_tab_action = QAction(
        QIcon("assets/execute_icon.png"), "Execute in New Output Tab", manager
    )
    manager.ws_execute_new_tab_action.setToolTip("Execute in New Output Tab (Ctrl+Shift+Enter)")
    manager.ws_execute_new_tab_action.triggered.connect(
        main_window.execute_query_in_new_output_tab
    )

    manager.ws_cancel_action = QAction(
        QIcon("assets/cancel_icon.png"), "Cancel", manager
    )
    manager.ws_cancel_action.setToolTip("Cancel Running Query (Alt+End)")
    manager.ws_cancel_action.triggered.connect(main_window.cancel_current_query)
    manager.ws_cancel_action.setEnabled(False)

    main_window.cancel_action.changed.connect(
        lambda: manager.ws_cancel_action.setEnabled(
            main_window.cancel_action.isEnabled()
        )
    )

    manager.ws_undo_action = QAction(
        qta.icon("fa5s.undo", color="#555555"), "Undo", manager
    )
    manager.ws_undo_action.setShortcut("Ctrl+Z")
    manager.ws_undo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_undo_action.triggered.connect(main_window.undo_text)

    manager.ws_redo_action = QAction(
        qta.icon("fa5s.redo", color="#555555"), "Redo", manager
    )
    manager.ws_redo_action.setShortcut("Ctrl+Y")
    manager.ws_redo_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_redo_action.triggered.connect(main_window.redo_text)

    manager.ws_cut_action = QAction(
        qta.icon("fa5s.cut", color="#555555"), "Cut", manager
    )
    manager.ws_cut_action.setShortcut("Ctrl+X")
    manager.ws_cut_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_cut_action.triggered.connect(main_window.cut_text)

    manager.ws_copy_action = QAction(
        qta.icon("fa5s.copy", color="#555555"), "Copy", manager
    )
    manager.ws_copy_action.setShortcut("Ctrl+C")
    manager.ws_copy_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_copy_action.triggered.connect(main_window.copy_text)

    manager.ws_paste_action = QAction(
        qta.icon("fa5s.paste", color="#555555"), "Paste", manager
    )
    manager.ws_paste_action.setShortcut("Ctrl+V")
    manager.ws_paste_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_paste_action.triggered.connect(main_window.paste_text)

    manager.ws_select_all_action = QAction(
        QIcon("assets/select_all.svg"), "Select ALL", manager
    )
    manager.ws_select_all_action.setShortcut("Ctrl+A")
    manager.ws_select_all_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_select_all_action.triggered.connect(main_window.select_all_text)

    manager.ws_find_action = QAction(
        qta.icon("fa5s.search", color="#555555"), "Find...", manager
    )
    manager.ws_find_action.setShortcut("Ctrl+F")
    manager.ws_find_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_find_action.triggered.connect(lambda: main_window.open_find_dialog(False))

    manager.ws_replace_action = QAction(
        qta.icon("fa5s.sync-alt", color="#555555"), "Replace...", manager
    )
    manager.ws_replace_action.setShortcut("Ctrl+H")
    manager.ws_replace_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_replace_action.triggered.connect(lambda: main_window.open_find_dialog(True))

    manager.ws_goto_line_action = QAction(
        QIcon("assets/goto_line.svg"), "Goto Line", manager
    )
    manager.ws_goto_line_action.setShortcut("Ctrl+G")
    manager.ws_goto_line_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_goto_line_action.triggered.connect(main_window.goto_line)

    manager.ws_comment_block_action = QAction(
        QIcon("assets/comment.svg"), "Comment Block", manager
    )
    manager.ws_comment_block_action.setShortcut("Ctrl+/")
    manager.ws_comment_block_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_comment_block_action.triggered.connect(main_window.comment_block)

    manager.ws_uncomment_block_action = QAction(
        QIcon("assets/uncomment.svg"), "Uncomment Block", manager
    )
    manager.ws_uncomment_block_action.setShortcut("Ctrl+Shift+/")
    manager.ws_uncomment_block_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_uncomment_block_action.triggered.connect(main_window.uncomment_block)

    manager.ws_upper_case_action = QAction(
        QIcon("assets/uppercase.svg"), "Upper Case", manager
    )
    manager.ws_upper_case_action.setShortcut("Ctrl+Shift+U")
    manager.ws_upper_case_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_upper_case_action.triggered.connect(main_window.upper_case_text)

    manager.ws_lower_case_action = QAction(
        QIcon("assets/lowercase.svg"), "Lower Case", manager
    )
    manager.ws_lower_case_action.setShortcut("Ctrl+Shift+L")
    manager.ws_lower_case_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_lower_case_action.triggered.connect(main_window.lower_case_text)

    manager.ws_initial_caps_action = QAction(
        qta.icon("mdi.format-letter-case", color="#555555"), "Initial Caps", manager
    )
    manager.ws_initial_caps_action.setShortcut("Ctrl+I")
    manager.ws_initial_caps_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_initial_caps_action.triggered.connect(main_window.initial_caps_text)

    manager.ws_clear_all_action = QAction(
        qta.icon("fa5s.trash-alt", color="#d93025"), "Clear All", manager
    )
    manager.ws_clear_all_action.setShortcut("F7")
    manager.ws_clear_all_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_clear_all_action.triggered.connect(main_window.clear_query_text)

    manager.ws_format_sql_action = QAction(
        qta.icon("mdi.auto-fix", color="#555555"), "Format SQL", manager
    )
    manager.ws_format_sql_action.setShortcut("Ctrl+Shift+F")
    manager.ws_format_sql_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    manager.ws_format_sql_action.triggered.connect(main_window.format_sql_text)
