from __future__ import annotations

import os
from typing import Any
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import db
from db.db_retrieval import get_connection_types
from dialogs.connections.engine_forms import (
    BaseEngineForm,
    CSVEngineForm,
    OracleEngineForm,
    PostgresEngineForm,
    SQLiteEngineForm,
    ServiceNowEngineForm,
)
from dialogs.connections.launcher_widget import LauncherWidget
from ui.components import PrimaryButton, SecondaryButton
from workers.workers import WorkerThread


class UnifiedConnectionDialog(QDialog):
    """
    Two-screen connection dialog:
    - Screen 1: Fast launcher with search & engine cards.
    - Screen 2: Master-detail view with sidebar switcher, static headers, and right-aligned footer.
    """

    ENGINES = [
        ("ORACLE", "Oracle", "assets/oracle.svg", "ORACLE_DB"),
        ("POSTGRES", "PostgreSQL", "assets/postgresql.svg", "POSTGRES"),
        ("SQLITE", "SQLite", "assets/sqlite.svg", "SQLITE"),
        ("SERVICENOW", "ServiceNow", "assets/servicenow.svg", "SERVICENOW"),
        ("CSV", "CSV / Flat Files", "assets/csv.svg", "CSV"),
    ]

    def __init__(
        self,
        parent: QWidget | None = None,
        is_editing: bool = False,
        conn_data: dict[str, Any] | None = None,
        initial_engine: str = "ORACLE",
        type_id: int | None = None,
        group_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_editing = is_editing or (conn_data is not None)
        self.conn_data = conn_data
        self.group_id = group_id
        self.type_id = type_id
        self.current_engine_code: str = ""
        self.form_scroll: QScrollArea | None = None

        self.setObjectName("unifiedConnDialog")
        self.setWindowTitle("Edit Connection" if self.is_editing else "New connection")
        self.resize(850, 560)
        self.setMinimumSize(800, 500)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.CustomizeWindowHint
        )

        self.type_map: dict[str, int] = self._load_type_map()

        self._load_stylesheet()
        self._init_ui(initial_engine)

        if self.is_editing and self.conn_data:
            self._load_existing_connection()

    def _load_stylesheet(self) -> None:
        qss_path = os.path.join(os.path.dirname(__file__), "..", "..", "ui", "style.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _load_type_map(self) -> dict[str, int]:
        mapping: dict[str, int] = {}
        try:
            types = get_connection_types()
            for t in types:
                mapping[t["code"].upper()] = t["id"]
        except Exception:
            pass
        return mapping

    def _init_ui(self, initial_engine: str) -> None:
        self.dialog_layout = QVBoxLayout(self)
        self.dialog_layout.setContentsMargins(0, 0, 0, 0)
        self.dialog_layout.setSpacing(0)

        self.main_stack = QStackedWidget()
        self.dialog_layout.addWidget(self.main_stack)

        # ── Screen 1: Launcher ─────────────────────────────────────────
        self.launcher = LauncherWidget(self)
        self.launcher.engine_selected.connect(self._on_launcher_engine_selected)
        self.launcher.cancelled.connect(self.reject)
        self.main_stack.addWidget(self.launcher)

        # ── Screen 2: Master-Detail Config Container ──────────────────
        self.config_page = QWidget()
        self.config_layout = QHBoxLayout(self.config_page)
        self.config_layout.setContentsMargins(0, 0, 0, 0)
        self.config_layout.setSpacing(0)

        self._build_sidebar()
        self._build_right_form_area()

        self.main_stack.addWidget(self.config_page)

        # Initial view selection
        if self.is_editing:
            self.main_stack.setCurrentIndex(1)
            self.sidebar_back_btn.setVisible(False)
        else:
            self.main_stack.setCurrentIndex(0)
            self.switch_to_engine(initial_engine)

    def _build_sidebar(self) -> None:
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("configSidebar")
        self.sidebar_widget.setFixedWidth(215)
        sidebar_layout = QVBoxLayout(self.sidebar_widget)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(6)

        # Back Button: ← All engines
        self.sidebar_back_btn = QPushButton("← All engines")
        self.sidebar_back_btn.setObjectName("configSidebarBackBtn")
        self.sidebar_back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_back_btn.clicked.connect(self._on_back_to_launcher)
        sidebar_layout.addWidget(self.sidebar_back_btn)

        # Section Header
        sec_header = QLabel("DATABASES")
        sec_header.setObjectName("launcherSectionHeader")
        sec_header.setStyleSheet("padding-top: 10px; padding-left: 4px;")
        sidebar_layout.addWidget(sec_header)

        # Sidebar Engine Buttons
        self.sidebar_buttons: dict[str, QPushButton] = {}
        for code, label, icon_rel, _ in self.ENGINES:
            btn = QPushButton(f" {label}")
            btn.setObjectName("configSidebarItem")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIconSize(QSize(20, 20))
            icon_path = db.resource_path(icon_rel)
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
            btn.clicked.connect(lambda checked=False, c=code: self.switch_to_engine(c))
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[code] = btn

        sidebar_layout.addStretch()
        self.config_layout.addWidget(self.sidebar_widget)

    def _build_right_form_area(self) -> None:
        right_container = QWidget()
        right_container.setObjectName("configRightContainer")
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(20, 14, 20, 14)
        right_layout.setSpacing(10)

        # Scroll area for form
        self.form_scroll = QScrollArea()
        self.form_scroll.setObjectName("configFormScroll")
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Forms Stack
        self.forms_stack = QStackedWidget()
        self.forms_stack.setObjectName("configFormsStack")
        self.forms: dict[str, BaseEngineForm] = {
            "ORACLE": OracleEngineForm(),
            "POSTGRES": PostgresEngineForm(),
            "SQLITE": SQLiteEngineForm(),
            "SERVICENOW": ServiceNowEngineForm(),
            "CSV": CSVEngineForm(),
        }

        # Wire type context into forms
        for code, form in self.forms.items():
            type_code = self._get_db_type_code(code)
            tid = self.type_map.get(type_code, self.type_id)
            form.set_type_context(tid, self.group_id)
            self.forms_stack.addWidget(form)

        self.form_scroll.setWidget(self.forms_stack)
        right_layout.addWidget(self.form_scroll)

        # Right-aligned footer: [ Test connection ] [ Cancel ] [ Save ]
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch()

        self.test_btn = SecondaryButton("Test connection")
        self.test_btn.clicked.connect(self._on_test_connection)
        footer_layout.addWidget(self.test_btn)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        save_label = "Update" if self.is_editing else "Save"
        self.save_btn = PrimaryButton(save_label)
        self.save_btn.clicked.connect(self._on_save_connection)
        footer_layout.addWidget(self.save_btn)

        right_layout.addLayout(footer_layout)
        self.config_layout.addWidget(right_container)

    def _get_db_type_code(self, engine_key: str) -> str:
        for code, _, _, db_code in self.ENGINES:
            if code == engine_key:
                return db_code
        return engine_key

    def switch_to_engine(self, engine_code: str) -> None:
        norm = engine_code.upper()
        if norm.startswith("ORACLE"):
            norm = "ORACLE"
        if norm not in self.forms:
            norm = "ORACLE"

        if norm == self.current_engine_code and self.forms_stack.currentWidget() == self.forms.get(norm):
            return

        self.setUpdatesEnabled(False)
        try:
            old_code = self.current_engine_code
            self.current_engine_code = norm

            # Only re-polish affected sidebar buttons to eliminate layout flicker
            if old_code and old_code in self.sidebar_buttons:
                old_btn = self.sidebar_buttons[old_code]
                old_btn.setProperty("active", "false")
                old_btn.style().unpolish(old_btn)
                old_btn.style().polish(old_btn)

            new_btn = self.sidebar_buttons.get(norm)
            if new_btn:
                new_btn.setProperty("active", "true")
                new_btn.style().unpolish(new_btn)
                new_btn.style().polish(new_btn)

            form = self.forms[norm]
            self.forms_stack.setCurrentWidget(form)
            if self.form_scroll:
                self.form_scroll.verticalScrollBar().setValue(0)
        finally:
            self.setUpdatesEnabled(True)

    def _on_launcher_engine_selected(self, engine_code: str) -> None:
        self.setUpdatesEnabled(False)
        try:
            self.switch_to_engine(engine_code)
            self.main_stack.setCurrentIndex(1)
        finally:
            self.setUpdatesEnabled(True)

    def _on_back_to_launcher(self) -> None:
        self.setUpdatesEnabled(False)
        try:
            self.launcher.reset_state()
            self.main_stack.setCurrentIndex(0)
        finally:
            self.setUpdatesEnabled(True)

    def _get_active_form(self) -> BaseEngineForm:
        return self.forms_stack.currentWidget()

    def _on_test_connection(self) -> None:
        form = self._get_active_form()
        valid, msg = form.validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation", msg)
            return

        self.test_btn.start_loading("Testing")

        def _do_test():
            return form.test_connection()

        self._test_worker = WorkerThread(_do_test)
        self._test_worker.finished_signal.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, result: Any, error: Exception | str | None) -> None:
        self.test_btn.stop_loading()
        if error:
            QMessageBox.critical(self, "Connection Error", f"Unexpected error during test:\n{error}")
            return
        success, result_msg = result if isinstance(result, tuple) else (False, str(result))
        if success:
            QMessageBox.information(self, "Connection Test", result_msg or "Connection successful!")
        else:
            QMessageBox.critical(self, "Connection Test Failed", result_msg or "Failed to connect.")

    def _on_save_connection(self) -> None:
        form = self._get_active_form()
        valid, msg = form.validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation", msg)
            return
        self.accept()

    def getData(self) -> dict[str, Any]:
        """Returns the full connection dictionary from the active engine form."""
        form = self._get_active_form()
        return form.get_data()

    def _load_existing_connection(self) -> None:
        if not self.conn_data:
            return
        code = self.conn_data.get("code") or self.conn_data.get("db_type", "")
        code = str(code).upper()
        self.switch_to_engine(code)
        form = self._get_active_form()
        form.load_data(self.conn_data)
