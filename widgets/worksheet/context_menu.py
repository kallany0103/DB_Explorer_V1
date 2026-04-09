from PySide6.QtWidgets import QMenu, QApplication
from PySide6.QtGui import QAction, QIcon
import qtawesome as qta


def show_editor_context_menu(manager, pos, editor):
    menu = QMenu(manager)
    menu.setStyleSheet(
        """
            QMenu { background-color: #ffffff; border: 1px solid #cccccc; }
            QMenu::item { padding: 4px; spacing: 4px; font-size: 10pt; color: #333333; }
            QMenu::item:selected { background-color: #e8eaed; color: #000000; }
            QMenu::icon { padding: 4px; }
            QMenu::separator { height: 1px; background: #eeeeee; margin: 4px 0px; }
        """
    )

    undo_action = QAction(qta.icon("fa5s.undo", color="#555555"), "Undo", manager)
    undo_action.setIconVisibleInMenu(True)
    undo_action.setShortcut("Ctrl+Z")
    undo_action.triggered.connect(editor.undo)
    undo_action.setEnabled(editor.document().isUndoAvailable())
    menu.addAction(undo_action)

    redo_action = QAction(qta.icon("fa5s.redo", color="#555555"), "Redo", manager)
    redo_action.setIconVisibleInMenu(True)
    redo_action.setShortcut("Ctrl+Y")
    redo_action.triggered.connect(editor.redo)
    redo_action.setEnabled(editor.document().isRedoAvailable())
    menu.addAction(redo_action)

    menu.addSeparator()

    cut_action = QAction(qta.icon("fa5s.cut", color="#555555"), "Cut", manager)
    cut_action.setIconVisibleInMenu(True)
    cut_action.setShortcut("Ctrl+X")
    cut_action.triggered.connect(editor.cut)
    cut_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(cut_action)

    copy_action = QAction(qta.icon("fa5s.copy", color="#555555"), "Copy", manager)
    copy_action.setIconVisibleInMenu(True)
    copy_action.setShortcut("Ctrl+C")
    copy_action.triggered.connect(editor.copy)
    copy_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(copy_action)

    paste_action = QAction(qta.icon("fa5s.paste", color="#555555"), "Paste", manager)
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

    explain_analyze_action = QAction("Explain Analyze", manager)
    explain_analyze_action.triggered.connect(manager.explain_query)
    menu.addAction(explain_analyze_action)



    explain_plan_action = QAction("Explain Plan", manager)
    explain_plan_action.triggered.connect(manager.explain_plan_query)
    menu.addAction(explain_plan_action)

    menu.addSeparator()
    format_action = QAction(QIcon("assets/format_icon.png"), "Format SQL", manager)
    format_action.setIconVisibleInMenu(False)
    format_action.setShortcut("Ctrl+Shift+F")
    format_action.triggered.connect(manager.format_sql_text)
    menu.addAction(format_action)

    menu.exec(editor.mapToGlobal(pos))
