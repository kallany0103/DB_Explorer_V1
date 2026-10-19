"""DBMS Output view widget for Oracle SERVEROUTPUT capture."""

import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta


def append_dbms_output(target_tab: QWidget, output_text: str) -> None:
    """Append or set text in the DBMS output view of target_tab."""
    if not target_tab or not output_text:
        return

    output_view = getattr(target_tab, "dbms_output_view", None) or target_tab.findChild(QTextEdit, "dbms_output_view")
    if not output_view:
        return

    if hasattr(target_tab, "_dbms_autoclear"):
        should_autoclear = bool(target_tab._dbms_autoclear)
    else:
        cb = getattr(target_tab, "dbms_autoclear_cb", None) or target_tab.findChild(QCheckBox, "dbms_autoclear_cb")
        should_autoclear = cb.isChecked() if cb is not None else False

    clean_text = str(output_text).rstrip()
    if should_autoclear:
        output_view.setPlainText(clean_text)
    else:
        existing = output_view.toPlainText().rstrip()
        if existing:
            output_view.setPlainText(f"{existing}\n\n{clean_text}")
        else:
            output_view.setPlainText(clean_text)

    # Scroll to bottom
    sb = output_view.verticalScrollBar()
    sb.setValue(sb.maximum())

    # Update line count label
    line_label = getattr(target_tab, "dbms_line_count_label", None) or target_tab.findChild(QLabel, "dbms_line_count_label")
    if line_label:
        num_lines = len(output_view.toPlainText().splitlines())
        line_label.setText(f"{num_lines} line{'s' if num_lines != 1 else ''}")


def create_dbms_output_view(manager, tab_content: QWidget) -> QWidget:
    """Create a dedicated DBMS Output container with toolbar and text editor."""
    container = QWidget()
    container.setObjectName("dbms_output_container")
    main_layout = QVBoxLayout(container)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # Mini toolbar at top
    toolbar = QWidget()
    toolbar.setObjectName("dbms_output_toolbar")
    toolbar.setFixedHeight(30)
    toolbar.setStyleSheet("QWidget#dbms_output_toolbar { background-color: #FAFAFA; border-bottom: 1px solid #E2E8F0; }")
    tb_layout = QHBoxLayout(toolbar)
    tb_layout.setContentsMargins(8, 2, 8, 2)
    tb_layout.setSpacing(8)

    # Status icon/label
    status_icon = QLabel()
    status_icon.setPixmap(qta.icon("fa5s.terminal", color="#28a745").pixmap(14, 14))
    status_label = QLabel("DBMS_OUTPUT")
    status_label.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #334155;")
    tb_layout.addWidget(status_icon)
    tb_layout.addWidget(status_label)

    # Separator
    sep1 = QLabel("|")
    sep1.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep1)

    # Clear button
    clear_btn = QToolButton()
    clear_btn.setIcon(qta.icon("fa5s.trash-alt", color="#64748B"))
    clear_btn.setToolTip("Clear DBMS Output")
    clear_btn.setAutoRaise(True)
    tb_layout.addWidget(clear_btn)

    # Copy All button
    copy_btn = QToolButton()
    copy_btn.setIcon(qta.icon("fa5s.copy", color="#64748B"))
    copy_btn.setToolTip("Copy All to Clipboard")
    copy_btn.setAutoRaise(True)
    tb_layout.addWidget(copy_btn)

    # Save to file button
    save_btn = QToolButton()
    save_btn.setIcon(qta.icon("fa5s.download", color="#64748B"))
    save_btn.setToolTip("Export Output to File")
    save_btn.setAutoRaise(True)
    tb_layout.addWidget(save_btn)

    # Separator
    sep2 = QLabel("|")
    sep2.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep2)

    # Auto-clear on run checkbox
    autoclear_cb = QCheckBox("Auto-clear on run")
    autoclear_cb.setObjectName("dbms_autoclear_cb")
    autoclear_cb.setChecked(True)
    autoclear_cb.setStyleSheet("QCheckBox { font-size: 8.5pt; color: #475569; }")
    tb_layout.addWidget(autoclear_cb)

    tb_layout.addStretch()

    # Line count label
    line_label = QLabel("0 lines")
    line_label.setObjectName("dbms_line_count_label")
    line_label.setStyleSheet("font-size: 8.5pt; color: #64748B;")
    tb_layout.addWidget(line_label)

    main_layout.addWidget(toolbar)

    # Text Area
    output_view = QTextEdit()
    output_view.setObjectName("dbms_output_view")
    output_view.setReadOnly(True)
    output_view.setFrameShape(QTextEdit.Shape.NoFrame)
    output_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    output_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
    output_view.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    mono_font = QFont("Consolas", 10)
    if not mono_font.exactMatch():
        mono_font = QFont("Courier New", 10)
    output_view.setFont(mono_font)
    output_view.setStyleSheet("QTextEdit { background-color: #ffffff; border: none; padding: 8px; }")

    # Wire actions
    def _do_clear():
        output_view.clear()
        line_label.setText("0 lines")

    def _do_copy():
        text = output_view.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)

    def _do_save():
        text = output_view.toPlainText()
        if not text:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            container,
            "Save DBMS Output",
            os.path.join(os.path.expanduser("~"), "dbms_output.txt"),
            "Text Files (*.txt);;Log Files (*.log);;All Files (*.*)",
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

    clear_btn.clicked.connect(_do_clear)
    copy_btn.clicked.connect(_do_copy)
    save_btn.clicked.connect(_do_save)

    # Context menu
    def _show_context_menu(pos):
        menu = QMenu(output_view)
        copy_action = QAction("Copy", menu)
        copy_action.triggered.connect(output_view.copy)
        copy_all_action = QAction("Copy All", menu)
        copy_all_action.triggered.connect(_do_copy)
        select_all_action = QAction("Select All", menu)
        select_all_action.triggered.connect(output_view.selectAll)
        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(_do_clear)

        menu.addAction(copy_action)
        menu.addAction(copy_all_action)
        menu.addAction(select_all_action)
        menu.addSeparator()
        menu.addAction(clear_action)
        menu.exec(output_view.mapToGlobal(pos))

    output_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    output_view.customContextMenuRequested.connect(_show_context_menu)

    main_layout.addWidget(output_view)

    if tab_content is not None:
        tab_content.dbms_output_view = output_view
        tab_content.dbms_autoclear_cb = autoclear_cb
        tab_content.dbms_line_count_label = line_label
        tab_content._dbms_autoclear = True
        autoclear_cb.toggled.connect(lambda val: setattr(tab_content, "_dbms_autoclear", val))

    return container
