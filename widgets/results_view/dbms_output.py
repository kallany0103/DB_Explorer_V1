"""DBMS Output view widget for Oracle SERVEROUTPUT capture."""

import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

import db
from ui.menu_style import apply_menu_style


def append_dbms_output(target_tab: QWidget, output_text: str) -> None:
    """Append or set text in the DBMS output view of target_tab."""
    if not target_tab or not output_text:
        return

    if hasattr(target_tab, "_dbms_enabled") and not target_tab._dbms_enabled:
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


def _get_worksheet_manager(manager):
    """Safely retrieve WorksheetManager from manager or main_window."""
    if manager is None:
        return None
    if hasattr(manager, "tab_dbms_output"):
        return manager
    if hasattr(manager, "worksheet_manager"):
        return manager.worksheet_manager
    main_win = getattr(manager, "main_window", None)
    if main_win is not None and hasattr(main_win, "worksheet_manager"):
        return main_win.worksheet_manager
    return None


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
    toolbar.setFixedHeight(34)
    toolbar.setStyleSheet("QWidget#dbms_output_toolbar { background-color: #FAFAFA; border-bottom: 1px solid #E2E8F0; }")
    tb_layout = QHBoxLayout(toolbar)
    tb_layout.setContentsMargins(8, 2, 8, 2)
    tb_layout.setSpacing(6)
    tb_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    ws_manager = _get_worksheet_manager(manager)
    initial_enabled = True
    if ws_manager is not None and tab_content is not None:
        initial_enabled = ws_manager.tab_dbms_output.get(tab_content, True)
    elif tab_content is not None and hasattr(tab_content, "_dbms_enabled"):
        initial_enabled = bool(tab_content._dbms_enabled)

    # Turn Output On/Off toggle button (TOAD style)
    toggle_btn = QToolButton()
    toggle_btn.setObjectName("dbms_toggle_btn")
    toggle_btn.setCheckable(True)
    toggle_btn.setAutoRaise(True)
    toggle_btn.setFixedSize(24, 24)
    toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    tb_layout.addWidget(toggle_btn)

    # Status label (fixed width so it never causes layout shifts when text changes)
    status_label = QLabel("DBMS_OUTPUT: ON")
    status_label.setFixedWidth(120)
    status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    status_label.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #16a34a;")
    tb_layout.addWidget(status_label)

    def _set_toggle_state(enabled: bool) -> None:
        toggle_btn.blockSignals(True)
        toggle_btn.setChecked(enabled)
        toggle_btn.blockSignals(False)
        if enabled:
            toggle_btn.setIcon(qta.icon("fa5s.power-off", color="#16a34a"))
            toggle_btn.setToolTip("Turn Output Off (currently On)")
            status_label.setText("DBMS_OUTPUT: ON")
            status_label.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #16a34a;")
        else:
            toggle_btn.setIcon(qta.icon("fa5s.power-off", color="#dc2626"))
            toggle_btn.setToolTip("Turn Output On (currently Off)")
            status_label.setText("DBMS_OUTPUT: OFF")
            status_label.setStyleSheet("font-weight: 600; font-size: 8.5pt; color: #dc2626;")

        if tab_content is not None:
            tab_content._dbms_enabled = enabled
            if not enabled:
                view = getattr(tab_content, "dbms_output_view", None)
                if view:
                    view.clear()
                lbl = getattr(tab_content, "dbms_line_count_label", None)
                if lbl:
                    lbl.setText("0 lines")

        ws_mgr = _get_worksheet_manager(manager)
        if ws_mgr is not None and tab_content is not None:
            ws_mgr.tab_dbms_output[tab_content] = enabled
            session = getattr(ws_mgr, "tab_transactions", {}).get(tab_content)
            if session is not None and getattr(session, "is_open", False) and getattr(session, "connection", None):
                try:
                    cur = session.connection.cursor()
                    if enabled:
                        db.enable_dbms_output(cur)
                    else:
                        db.disable_dbms_output(cur)
                    cur.close()
                except Exception:
                    pass

    toggle_btn.toggled.connect(_set_toggle_state)
    _set_toggle_state(initial_enabled)

    # Separator
    sep1 = QLabel("|")
    sep1.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep1)

    # Clear button
    clear_btn = QToolButton()
    clear_btn.setIcon(qta.icon("fa5s.trash-alt", color="#64748B"))
    clear_btn.setToolTip("Clear DBMS Output")
    clear_btn.setAutoRaise(True)
    clear_btn.setFixedSize(24, 24)
    tb_layout.addWidget(clear_btn)

    # Copy All button
    copy_btn = QToolButton()
    copy_btn.setIcon(qta.icon("fa5s.copy", color="#64748B"))
    copy_btn.setToolTip("Copy All to Clipboard")
    copy_btn.setAutoRaise(True)
    copy_btn.setFixedSize(24, 24)
    tb_layout.addWidget(copy_btn)

    # Save to file button
    save_btn = QToolButton()
    save_btn.setIcon(qta.icon("fa5s.download", color="#64748B"))
    save_btn.setToolTip("Export Output to File")
    save_btn.setAutoRaise(True)
    save_btn.setFixedSize(24, 24)
    tb_layout.addWidget(save_btn)

    # Separator
    sep2 = QLabel("|")
    sep2.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep2)

    # Auto-clear on run checkbox
    autoclear_cb = QCheckBox("Auto-clear")
    autoclear_cb.setObjectName("dbms_autoclear_cb")
    autoclear_cb.setChecked(True)
    autoclear_cb.setStyleSheet("QCheckBox { font-size: 8.5pt; color: #475569; }")
    tb_layout.addWidget(autoclear_cb)

    # Separator
    sep3 = QLabel("|")
    sep3.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep3)

    # Common styling for toolbar combo boxes
    cb_style = (
        "QComboBox {"
        "  font-size: 8.5pt;"
        "  min-height: 18px;"
        "  max-height: 22px;"
        "  height: 22px;"
        "  padding: 1px 18px 1px 6px;"
        "  border: 1px solid #CBD5E1;"
        "  border-radius: 3px;"
        "  background-color: #FFFFFF;"
        "  color: #1E293B;"
        "}"
        "QComboBox:hover {"
        "  border-color: #94A3B8;"
        "}"
        "QComboBox::drop-down {"
        "  subcontrol-origin: padding;"
        "  subcontrol-position: top right;"
        "  width: 16px;"
        "  border: none;"
        "}"
        "QComboBox::down-arrow {"
        "  image: url(assets/toolbar-chevron-down.svg);"
        "  width: 8px;"
        "  height: 8px;"
        "}"
    )

    # Buffer Size dropdown
    buf_label = QLabel("Buffer:")
    buf_label.setStyleSheet("font-size: 8.5pt; color: #475569;")
    tb_layout.addWidget(buf_label)

    buffer_cb = QComboBox()
    buffer_cb.setObjectName("dbms_buffer_cb")
    buffer_cb.setFixedHeight(22)
    buffer_cb.addItems(["Unlimited", "20 KB", "100 KB", "1 MB"])
    buffer_cb.setStyleSheet(cb_style)
    buffer_cb.setToolTip("Set DBMS_OUTPUT message buffer capacity")
    tb_layout.addWidget(buffer_cb)

    BUFFER_SIZE_MAP = {
        "Unlimited": None,
        "20 KB": 20000,
        "100 KB": 100000,
        "1 MB": 1000000,
    }

    def _on_buffer_size_changed(index: int) -> None:
        val = BUFFER_SIZE_MAP.get(buffer_cb.currentText(), None)
        if tab_content is not None:
            tab_content._dbms_buffer_size = val
        ws_m = _get_worksheet_manager(manager)
        if ws_m is not None and tab_content is not None:
            if not hasattr(ws_m, "tab_dbms_buffer_size"):
                ws_m.tab_dbms_buffer_size = {}
            ws_m.tab_dbms_buffer_size[tab_content] = val
            session = getattr(ws_m, "tab_transactions", {}).get(tab_content)
            if session is not None and getattr(session, "is_open", False) and getattr(session, "connection", None):
                try:
                    cur = session.connection.cursor()
                    if getattr(tab_content, "_dbms_enabled", True):
                        db.enable_dbms_output(cur, buffer_size=val)
                    cur.close()
                except Exception:
                    pass

    buffer_cb.currentIndexChanged.connect(_on_buffer_size_changed)

    # Separator
    sep4 = QLabel("|")
    sep4.setStyleSheet("color: #CBD5E1;")
    tb_layout.addWidget(sep4)

    # Polling dropdown (Toad style)
    poll_label = QLabel("Polling:")
    poll_label.setStyleSheet("font-size: 8.5pt; color: #475569;")
    tb_layout.addWidget(poll_label)

    poll_cb = QComboBox()
    poll_cb.setObjectName("dbms_poll_cb")
    poll_cb.setFixedHeight(22)
    poll_cb.addItems(["Auto", "1 sec", "2 sec", "5 sec"])
    poll_cb.setStyleSheet(cb_style)
    poll_cb.setToolTip("Periodic interval to poll and stream DBMS_OUTPUT from active session")
    tb_layout.addWidget(poll_cb)

    poll_timer = QTimer(container)

    def _poll_session_output() -> None:
        if not tab_content or not getattr(tab_content, "_dbms_enabled", True):
            return
        ws_m = _get_worksheet_manager(manager)
        if ws_m is None:
            return
        session = getattr(ws_m, "tab_transactions", {}).get(tab_content)
        if session is not None and getattr(session, "is_open", False) and getattr(session, "connection", None):
            try:
                cur = session.connection.cursor()
                out = db.fetch_dbms_output(cur)
                cur.close()
                if out:
                    append_dbms_output(tab_content, out)
            except Exception:
                pass

    poll_timer.timeout.connect(_poll_session_output)

    def _on_poll_interval_changed(index: int) -> None:
        poll_timer.stop()
        text = poll_cb.currentText()
        if text == "1 sec":
            poll_timer.start(1000)
        elif text == "2 sec":
            poll_timer.start(2000)
        elif text == "5 sec":
            poll_timer.start(5000)

    poll_cb.currentIndexChanged.connect(_on_poll_interval_changed)

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
        apply_menu_style(menu)
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
        tab_content.dbms_toggle_btn = toggle_btn
        tab_content.set_dbms_output_enabled = _set_toggle_state
        tab_content._dbms_enabled = initial_enabled
        tab_content.dbms_autoclear_cb = autoclear_cb
        tab_content.dbms_line_count_label = line_label
        tab_content._dbms_autoclear = True
        autoclear_cb.toggled.connect(lambda val: setattr(tab_content, "_dbms_autoclear", val))

    return container
