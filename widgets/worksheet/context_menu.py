from PyQt6.QtWidgets import QMenu, QApplication
from PyQt6.QtGui import QAction, QIcon


def show_editor_context_menu(manager, pos, editor):
    menu = QMenu(manager)
    menu.setStyleSheet(
        """
            QMenu { background-color: #ffffff; border: 1px solid #cccccc; }
            QMenu::item { padding: 5px 25px 5px 25px; font-size: 10pt; color: #333333; }
            QMenu::item:selected { background-color: #e8eaed; color: #000000; }
            QMenu::icon { padding-left: 5px; }
            QMenu::separator { height: 1px; background: #eeeeee; margin: 4px 0px; }
        """
    )

    undo_action = QAction(QIcon("assets/undo.svg"), "Undo", manager)
    undo_action.setIconVisibleInMenu(False)
    undo_action.setShortcut("Ctrl+Z")
    undo_action.triggered.connect(editor.undo)
    undo_action.setEnabled(editor.document().isUndoAvailable())
    menu.addAction(undo_action)

    redo_action = QAction(QIcon("assets/redo.svg"), "Redo", manager)
    redo_action.setIconVisibleInMenu(False)
    redo_action.setShortcut("Ctrl+Y")
    redo_action.triggered.connect(editor.redo)
    redo_action.setEnabled(editor.document().isRedoAvailable())
    menu.addAction(redo_action)

    menu.addSeparator()

    cut_action = QAction("Cut", manager)
    cut_action.setShortcut("Ctrl+X")
    cut_action.triggered.connect(editor.cut)
    cut_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(cut_action)

    copy_action = QAction("Copy", manager)
    copy_action.setShortcut("Ctrl+C")
    copy_action.triggered.connect(editor.copy)
    copy_action.setEnabled(editor.textCursor().hasSelection())
    menu.addAction(copy_action)

    paste_action = QAction(QIcon("assets/paste.svg"), "Paste", manager)
    paste_action.setIconVisibleInMenu(False)
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
    format_action = QAction(QIcon("assets/format_icon.png"), "Format SQL", manager)
    format_action.setIconVisibleInMenu(False)
    format_action.setShortcut("Ctrl+Shift+F")
    format_action.triggered.connect(manager.format_sql_text)
    menu.addAction(format_action)

    menu.exec(editor.mapToGlobal(pos))
