"""
dialogs/tools/object_describe_dialog.py
Implements the Toad for Oracle-style "Describe (F4)" window for database tables,
views, and schemas. Displays columns, indexes, constraints, sample data preview,
and DDL script with real-time filtering and copying.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QTabWidget,
    QWidget,
    QPlainTextEdit,
    QApplication,
    QFrame,
    QMessageBox,
    QComboBox,
    QFileDialog,
)
import qtawesome as qta

from ui.components import LoadingOverlay, SecondaryButton
from workers.workers import WorkerThread
from db.object_describe import describe_database_object
from dialogs.tools.query_describe_dialog import DescribeHighlighter


class ObjectDescribeDialog(QDialog):
    """
    Toad-like Object Describe window (F4) that displays full schema and object metadata.
    """

    def __init__(self, parent=None, conn_data: dict = None, target: str = ""):
        super().__init__(parent)
        self.conn_data = conn_data or {}
        self.target = target or ""
        self.meta = {}
        self._worker = None

        self.setWindowTitle(f"Describe - {self.target}")
        self.resize(850, 580)
        self.setMinimumSize(600, 420)
        self.setSizeGripEnabled(True)

        self._init_ui()
        self._start_fetch()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Header Banner ──
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(10)

        # Object Type Badge
        self.type_badge = QLabel("OBJECT")
        self.type_badge.setStyleSheet("""
            QLabel {
                background-color: #0284c7;
                color: #ffffff;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
        """)
        header_layout.addWidget(self.type_badge)

        # Object Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = QLabel(self.target)
        self.title_label.setStyleSheet("font-size: 13pt; font-weight: 700; color: #0f172a;")
        self.subtitle_label = QLabel("Loading object details...")
        self.subtitle_label.setStyleSheet("font-size: 8.5pt; color: #64748b;")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Search / Filter Box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter columns / tables...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self.search_box)

        # Refresh button
        self.refresh_btn = QToolButton()
        self.refresh_btn.setIcon(qta.icon("fa5s.redo-alt", color="#475569"))
        self.refresh_btn.setToolTip("Refresh metadata")
        self.refresh_btn.clicked.connect(self._start_fetch)
        header_layout.addWidget(self.refresh_btn)

        # Copy DDL button
        self.copy_ddl_btn = QToolButton()
        self.copy_ddl_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        self.copy_ddl_btn.setToolTip("Copy DDL Script to Clipboard")
        self.copy_ddl_btn.clicked.connect(self._copy_ddl)
        header_layout.addWidget(self.copy_ddl_btn)

        # View Schema button (shown when table has parent schema info)
        self.schema_jump_btn = QToolButton()
        self.schema_jump_btn.setIcon(qta.icon("mdi.database-outline", color="#475569"))
        self.schema_jump_btn.setToolTip("View Parent Schema Details")
        self.schema_jump_btn.clicked.connect(self._jump_to_schema_tab)
        self.schema_jump_btn.setVisible(False)
        header_layout.addWidget(self.schema_jump_btn)

        layout.addWidget(header_frame)

        # ── Tabbed View Container ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 6px 14px;
                margin-right: 2px;
                font-size: 9pt;
                font-weight: 500;
                color: #475569;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #0284c7;
                font-weight: 600;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #e2e8f0;
            }
        """)
        layout.addWidget(self.tabs, stretch=1)

        # ── Bottom Status Bar ──
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 2, 4, 2)
        bottom_bar.setSpacing(10)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        bottom_bar.addWidget(self.status_label)

        bottom_bar.addStretch()

        self.close_btn = SecondaryButton("Close")
        self.close_btn.setFixedWidth(80)
        self.close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(self.close_btn)

        layout.addLayout(bottom_bar)

        # Loading Spinner Overlay
        self._loading_overlay = LoadingOverlay(self)

    def _start_fetch(self):
        self._loading_overlay.show_overlay()
        self.status_label.setText("Fetching metadata...")

        self._worker = WorkerThread(describe_database_object, self.conn_data, self.target)
        self._worker.finished_signal.connect(self._on_fetch_finished)
        self._worker.start()

    def _on_fetch_finished(self, result, error):
        self._loading_overlay.hide_overlay()
        if error:
            err_msg = str(error)
            QMessageBox.critical(self, "Describe Error", f"Failed to describe '{self.target}':\n\n{err_msg}")
            self.status_label.setText("Error describing object")
            return

        self.meta = result or {}
        self._populate_ui()

    def _populate_ui(self):
        target_type = self.meta.get("target_type", "table")
        obj_type = self.meta.get("object_type", "Table")
        title = self.meta.get("title") or self.meta.get("name") or self.target
        schema = self.meta.get("schema") or "public"

        # Update Banner
        self.title_label.setText(title)
        self.type_badge.setText(obj_type.upper())
        if target_type == "schema":
            self.type_badge.setStyleSheet("""
                QLabel {
                    background-color: #d97706;
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 700;
                }
            """)
        elif "view" in target_type:
            self.type_badge.setStyleSheet("""
                QLabel {
                    background-color: #059669;
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 700;
                }
            """)
        else:
            self.type_badge.setStyleSheet("""
                QLabel {
                    background-color: #0284c7;
                    color: #ffffff;
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 700;
                }
            """)

        # Subtitle details
        details = self.meta.get("details", {})
        parts = []
        for k, v in details.items():
            if v and v != "N/A":
                parts.append(f"<b>{k}:</b> {v}")
        self.subtitle_label.setText(" &nbsp;|&nbsp; ".join(parts) if parts else f"Schema: {schema}")

        # Clear existing tabs
        self.tabs.clear()

        if target_type in ("table", "view"):
            self._build_table_tabs()
        else:
            self._build_schema_tabs()

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE TABS
    # ─────────────────────────────────────────────────────────────────────────
    def _build_table_tabs(self):
        # 1. Columns Tab
        self.cols_table = self._create_data_table([
            "#", "Column Name", "Data Type", "Nullable", "Default", "Key", "Comments"
        ])
        self._populate_columns_table(self.cols_table, self.meta.get("columns", []))
        self.tabs.addTab(self.cols_table, qta.icon("fa5s.columns", color="#475569"), "Columns")

        # 2. Indexes Tab
        indexes = self.meta.get("indexes", [])
        self.idx_table = self._create_data_table(["Index Name", "Definition / Columns", "Unique?", "Type"])
        self.idx_table.setRowCount(len(indexes))
        for row, idx in enumerate(indexes):
            name_item = QTableWidgetItem(idx.get("name", ""))
            name_item.setFont(self._bold_font())
            self.idx_table.setItem(row, 0, name_item)
            self.idx_table.setItem(row, 1, QTableWidgetItem(idx.get("definition", "")))
            uniq_item = QTableWidgetItem("UNIQUE" if idx.get("unique") else "NON-UNIQUE")
            if idx.get("unique"):
                uniq_item.setForeground(QColor("#059669"))
                uniq_item.setFont(self._bold_font())
            self.idx_table.setItem(row, 2, uniq_item)
            self.idx_table.setItem(row, 3, QTableWidgetItem(idx.get("type", "btree")))
        self.tabs.addTab(self.idx_table, qta.icon("mdi.key-variant", color="#475569"), f"Indexes ({len(indexes)})")

        # 3. Constraints Tab
        constraints = self.meta.get("constraints", [])
        self.cst_table = self._create_data_table(["Constraint Name", "Type", "Definition / Details"])
        self.cst_table.setRowCount(len(constraints))
        for row, cst in enumerate(constraints):
            name_item = QTableWidgetItem(cst.get("name", ""))
            name_item.setFont(self._bold_font())
            self.cst_table.setItem(row, 0, name_item)
            type_item = QTableWidgetItem(cst.get("type", ""))
            if "Primary" in cst.get("type", ""):
                type_item.setForeground(QColor("#b45309"))
                type_item.setFont(self._bold_font())
            self.cst_table.setItem(row, 1, type_item)
            self.cst_table.setItem(row, 2, QTableWidgetItem(cst.get("definition", "")))
        self.tabs.addTab(self.cst_table, qta.icon("mdi.shield-check-outline", color="#475569"), f"Constraints ({len(constraints)})")

        # 4. Data Preview Tab
        sample = self.meta.get("sample_data", {})
        headers = sample.get("headers", [])
        rows = sample.get("rows", [])
        self.data_table = self._create_data_table(headers)
        self.data_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                val_str = "" if val is None else str(val)
                self.data_table.setItem(r_idx, c_idx, QTableWidgetItem(val_str))
        self.tabs.addTab(self.data_table, qta.icon("fa5s.table", color="#475569"), f"Data Preview ({len(rows)})")

        # 5. Scripts Tab (Toad for Oracle Style Suite)
        scripts = self.meta.get("scripts", {})
        if not scripts:
            scripts = {"Full DDL": self.meta.get("ddl", "")}
        self.scripts_widget = self._build_scripts_tab_widget(scripts, default_key="Full DDL")
        self.ddl_editor = getattr(self.scripts_widget, "editor", None)
        self.tabs.addTab(self.scripts_widget, qta.icon("mdi.script-text-outline", color="#475569"), "Scripts")

        # 6. Parent Schema Tab (describing both Table and Schema simultaneously)
        schema_info = self.meta.get("schema_info")
        if schema_info:
            schema_name = schema_info.get("name") or self.meta.get("schema") or "Schema"
            self.schema_tab = self._build_schema_container_widget(schema_info)
            self.tabs.addTab(self.schema_tab, qta.icon("mdi.database-outline", color="#475569"), f"Schema ({schema_name})")
            if hasattr(self, "schema_jump_btn"):
                self.schema_jump_btn.setVisible(True)
                self.schema_jump_btn.setToolTip(f"View Parent Schema ({schema_name})")
        else:
            if hasattr(self, "schema_jump_btn"):
                self.schema_jump_btn.setVisible(False)

        cols_count = len(self.meta.get("columns", []))
        schema_name = self.meta.get("schema") or ""
        schema_str = f" in schema {schema_name}" if schema_name else ""
        self.status_label.setText(f"{cols_count} columns in {self.meta.get('name')}{schema_str}")

    def _populate_columns_table(self, table: QTableWidget, columns: list[dict]):
        table.setRowCount(len(columns))
        for row, c in enumerate(columns):
            pos_item = QTableWidgetItem(str(c.get("position", row + 1)))
            pos_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, 0, pos_item)

            name_item = QTableWidgetItem(c.get("name", ""))
            name_item.setFont(self._bold_font())
            table.setItem(row, 1, name_item)

            type_item = QTableWidgetItem(c.get("data_type", ""))
            type_item.setForeground(QColor("#0369a1"))
            table.setItem(row, 2, type_item)

            is_nullable = c.get("nullable", True)
            null_item = QTableWidgetItem("NOT NULL" if not is_nullable else "NULL")
            if not is_nullable:
                null_item.setForeground(QColor("#b91c1c"))
                null_item.setFont(self._bold_font())
            else:
                null_item.setForeground(QColor("#64748b"))
            table.setItem(row, 3, null_item)

            table.setItem(row, 4, QTableWidgetItem(c.get("default", "")))

            # Key Badges
            keys = []
            if c.get("is_pk"):
                keys.append("PK")
            if c.get("is_fk"):
                keys.append("FK")
            key_text = " / ".join(keys)
            key_item = QTableWidgetItem(key_text)
            if "PK" in keys:
                key_item.setForeground(QColor("#d97706"))
                key_item.setFont(self._bold_font())
            table.setItem(row, 5, key_item)

            table.setItem(row, 6, QTableWidgetItem(c.get("comment", "")))

    # ─────────────────────────────────────────────────────────────────────────
    # SCHEMA TABS
    # ─────────────────────────────────────────────────────────────────────────
    def _build_schema_tabs(self):
        # 1. Tables Tab
        tables = self.meta.get("tables", [])
        self.schema_tables = self._create_data_table([
            "Table Name", "Type", "Columns", "Est. Rows", "Total Size", "Comment"
        ])
        self.schema_tables.setRowCount(len(tables))
        for row, t in enumerate(tables):
            name_item = QTableWidgetItem(t.get("name", ""))
            name_item.setFont(self._bold_font())
            self.schema_tables.setItem(row, 0, name_item)
            self.schema_tables.setItem(row, 1, QTableWidgetItem(t.get("type", "Table")))
            self.schema_tables.setItem(row, 2, QTableWidgetItem(str(t.get("columns_count", 0))))
            self.schema_tables.setItem(row, 3, QTableWidgetItem(str(t.get("estimated_rows", "N/A"))))
            self.schema_tables.setItem(row, 4, QTableWidgetItem(t.get("size", "")))
            self.schema_tables.setItem(row, 5, QTableWidgetItem(t.get("comment", "")))

        # Double-click a table to drill down into it!
        self.schema_tables.doubleClicked.connect(self._on_table_double_clicked)
        self.tabs.addTab(self.schema_tables, qta.icon("fa5s.table", color="#475569"), f"Tables ({len(tables)})")

        # 2. Views Tab
        views = self.meta.get("views", [])
        self.schema_views = self._create_data_table(["View Name", "Owner", "Comment"])
        self.schema_views.setRowCount(len(views))
        for row, v in enumerate(views):
            name_item = QTableWidgetItem(v.get("name", ""))
            name_item.setFont(self._bold_font())
            self.schema_views.setItem(row, 0, name_item)
            self.schema_views.setItem(row, 1, QTableWidgetItem(v.get("owner", "")))
            self.schema_views.setItem(row, 2, QTableWidgetItem(v.get("comment", "")))
        self.tabs.addTab(self.schema_views, qta.icon("mdi.eye", color="#475569"), f"Views ({len(views)})")

        # 3. Functions Tab
        funcs = self.meta.get("functions", [])
        if funcs:
            self.schema_funcs = self._create_data_table(["Function / Signature", "Owner", "Language", "Comment"])
            self.schema_funcs.setRowCount(len(funcs))
            for row, f in enumerate(funcs):
                name_item = QTableWidgetItem(f.get("name", ""))
                name_item.setFont(self._bold_font())
                self.schema_funcs.setItem(row, 0, name_item)
                self.schema_funcs.setItem(row, 1, QTableWidgetItem(f.get("owner", "")))
                self.schema_funcs.setItem(row, 2, QTableWidgetItem(f.get("language", "")))
                self.schema_funcs.setItem(row, 3, QTableWidgetItem(f.get("comment", "")))
            self.tabs.addTab(self.schema_funcs, qta.icon("mdi.function", color="#475569"), f"Functions ({len(funcs)})")

        # 4. Scripts Tab
        scripts = self.meta.get("scripts", {})
        if not scripts:
            scripts = {"Full DDL": self.meta.get("ddl", "")}
        self.schema_scripts_widget = self._build_scripts_tab_widget(scripts, default_key="Full DDL")
        self.ddl_editor = getattr(self.schema_scripts_widget, "editor", None)
        self.tabs.addTab(self.schema_scripts_widget, qta.icon("mdi.script-text-outline", color="#475569"), "Scripts")

        self.status_label.setText(f"{len(tables)} tables, {len(views)} views in schema {self.meta.get('name')}")

    def _on_table_double_clicked(self, index):
        row = index.row()
        table_name = self.schema_tables.item(row, 0).text()
        schema_name = self.meta.get("name")
        full_target = f'"{schema_name}"."{table_name}"' if schema_name else table_name
        self.target = full_target
        self._start_fetch()

    def _jump_to_schema_tab(self):
        if hasattr(self, "schema_tab") and self.schema_tab:
            self.tabs.setCurrentWidget(self.schema_tab)

    def _build_schema_container_widget(self, schema_meta: dict) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        schema_name = schema_meta.get("name") or "Schema"
        owner = schema_meta.get("details", {}).get("Owner") or schema_meta.get("details", {}).get("Schema / User", "")
        tables = schema_meta.get("tables", [])
        views = schema_meta.get("views", [])
        funcs = schema_meta.get("functions", [])

        stats_banner = QLabel(
            f"<b>Schema:</b> <code>{schema_name}</code> &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Owner:</b> {owner} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Tables:</b> {len(tables)} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Views:</b> {len(views)}"
            + (f" &nbsp;&nbsp;|&nbsp;&nbsp; <b>Functions:</b> {len(funcs)}" if funcs else "")
        )
        stats_banner.setStyleSheet("""
            QLabel {
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 4px 8px;
                color: #334155;
                font-size: 8.5pt;
            }
        """)
        layout.addWidget(stats_banner)

        sub_tabs = QTabWidget()
        sub_tabs.setStyleSheet(self.tabs.styleSheet())

        # Tables sub-tab
        s_tables = self._create_data_table([
            "Table Name", "Type", "Columns", "Est. Rows", "Total Size", "Comment"
        ])
        s_tables.setRowCount(len(tables))
        for row, t in enumerate(tables):
            name_item = QTableWidgetItem(t.get("name", ""))
            name_item.setFont(self._bold_font())
            s_tables.setItem(row, 0, name_item)
            s_tables.setItem(row, 1, QTableWidgetItem(t.get("type", "Table")))
            s_tables.setItem(row, 2, QTableWidgetItem(str(t.get("columns_count", 0))))
            s_tables.setItem(row, 3, QTableWidgetItem(str(t.get("estimated_rows", "N/A"))))
            s_tables.setItem(row, 4, QTableWidgetItem(t.get("size", "")))
            s_tables.setItem(row, 5, QTableWidgetItem(t.get("comment", "")))
        s_tables.doubleClicked.connect(lambda idx, s=schema_name, tbl=s_tables: self._on_sub_table_double_clicked(s, tbl.item(idx.row(), 0).text()))
        sub_tabs.addTab(s_tables, qta.icon("fa5s.table", color="#475569"), f"Tables ({len(tables)})")

        if views:
            s_views = self._create_data_table(["View Name", "Owner", "Comment"])
            s_views.setRowCount(len(views))
            for row, v in enumerate(views):
                name_item = QTableWidgetItem(v.get("name", ""))
                name_item.setFont(self._bold_font())
                s_views.setItem(row, 0, name_item)
                s_views.setItem(row, 1, QTableWidgetItem(v.get("owner", "")))
                s_views.setItem(row, 2, QTableWidgetItem(v.get("comment", "")))
            sub_tabs.addTab(s_views, qta.icon("mdi.eye", color="#475569"), f"Views ({len(views)})")

        if funcs:
            s_funcs = self._create_data_table(["Function / Signature", "Owner", "Language", "Comment"])
            s_funcs.setRowCount(len(funcs))
            for row, f in enumerate(funcs):
                name_item = QTableWidgetItem(f.get("name", ""))
                name_item.setFont(self._bold_font())
                s_funcs.setItem(row, 0, name_item)
                s_funcs.setItem(row, 1, QTableWidgetItem(f.get("owner", "")))
                s_funcs.setItem(row, 2, QTableWidgetItem(f.get("language", "")))
                s_funcs.setItem(row, 3, QTableWidgetItem(f.get("comment", "")))
            sub_tabs.addTab(s_funcs, qta.icon("mdi.function", color="#475569"), f"Functions ({len(funcs)})")

        sub_scripts = schema_meta.get("scripts", {})
        if not sub_scripts:
            sub_scripts = {"Full DDL": schema_meta.get("ddl", "")}
        s_scripts_widget = self._build_scripts_tab_widget(sub_scripts, default_key="Full DDL")
        sub_tabs.addTab(s_scripts_widget, qta.icon("mdi.script-text-outline", color="#475569"), "Schema Scripts")

        layout.addWidget(sub_tabs, stretch=1)
        return container

    def _on_sub_table_double_clicked(self, schema_name: str, table_name: str):
        full_target = f'"{schema_name}"."{table_name}"' if schema_name else table_name
        self.target = full_target
        self.setWindowTitle(f"Describe - {self.target}")
        self._start_fetch()

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS & FACTORIES
    # ─────────────────────────────────────────────────────────────────────────
    def _create_data_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #f1f5f9;
                border: none;
                selection-background-color: #e0f2fe;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #475569;
                padding: 5px 8px;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                border-right: 1px solid #e2e8f0;
                font-weight: 600;
            }
        """)
        return table

    def _create_code_editor(self, text: str) -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        editor.setFont(font)
        editor.document().setDefaultFont(font)
        editor.setPlainText(text)
        DescribeHighlighter(editor.document())
        editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff;
                color: #1e293b;
                border: none;
                selection-background-color: #bae6fd;
                selection-color: #0f172a;
                padding: 8px;
            }
        """)
        return editor

    def _bold_font(self) -> QFont:
        f = QFont()
        f.setBold(True)
        return f

    def _build_scripts_tab_widget(self, scripts_dict: dict, default_key: str = "Full DDL") -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(6)

        # Toolbar Frame
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                padding: 3px 6px;
            }
        """)
        tb_layout = QHBoxLayout(toolbar_frame)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(8)

        lbl = QLabel("Script Type:")
        lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 8.5pt;")
        tb_layout.addWidget(lbl)

        combo = QComboBox()
        combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 8.5pt;
                font-weight: 500;
                color: #0f172a;
                min-width: 180px;
            }
            QComboBox:hover {
                border-color: #0284c7;
            }
            QComboBox::drop-down {
                border: none;
                width: 18px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                selection-background-color: #e0f2fe;
                selection-color: #0284c7;
            }
        """)
        for s_name in scripts_dict.keys():
            combo.addItem(s_name)

        if default_key in scripts_dict:
            combo.setCurrentText(default_key)
        tb_layout.addWidget(combo)

        tb_layout.addStretch()

        copy_btn = QToolButton()
        copy_btn.setText("Copy")
        copy_btn.setIcon(qta.icon("fa5s.copy", color="#475569"))
        copy_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        copy_btn.setToolTip("Copy displayed script to clipboard")
        copy_btn.setStyleSheet("""
            QToolButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8.5pt;
                color: #334155;
            }
            QToolButton:hover {
                background: #f1f5f9;
                border-color: #94a3b8;
            }
        """)
        tb_layout.addWidget(copy_btn)

        worksheet_btn = QToolButton()
        worksheet_btn.setText("Open in Worksheet")
        worksheet_btn.setIcon(qta.icon("fa5s.external-link-alt", color="#0284c7"))
        worksheet_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        worksheet_btn.setToolTip("Open script in a new SQL Worksheet tab")
        worksheet_btn.setStyleSheet("""
            QToolButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8.5pt;
                color: #0369a1;
                font-weight: 600;
            }
            QToolButton:hover {
                background: #f0f9ff;
                border-color: #0284c7;
            }
        """)
        tb_layout.addWidget(worksheet_btn)

        save_btn = QToolButton()
        save_btn.setText("Save...")
        save_btn.setIcon(qta.icon("fa5s.save", color="#475569"))
        save_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        save_btn.setToolTip("Save script as .sql file")
        save_btn.setStyleSheet("""
            QToolButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8.5pt;
                color: #334155;
            }
            QToolButton:hover {
                background: #f1f5f9;
                border-color: #94a3b8;
            }
        """)
        tb_layout.addWidget(save_btn)

        layout.addWidget(toolbar_frame)

        initial_text = scripts_dict.get(combo.currentText(), "")
        editor = self._create_code_editor(initial_text)
        layout.addWidget(editor, stretch=1)

        container.editor = editor
        container.combo = combo

        combo.currentTextChanged.connect(lambda text: editor.setPlainText(scripts_dict.get(text, "")))
        copy_btn.clicked.connect(lambda: self._copy_script_text(editor.toPlainText(), combo.currentText()))
        worksheet_btn.clicked.connect(lambda: self._open_script_in_worksheet(editor.toPlainText()))
        save_btn.clicked.connect(lambda: self._save_script_to_file(editor.toPlainText(), combo.currentText()))

        return container

    def _copy_script_text(self, sql: str, script_name: str):
        if sql:
            QApplication.clipboard().setText(sql)
            self.status_label.setText(f"'{script_name}' copied to clipboard!")

    def _open_script_in_worksheet(self, sql: str):
        if not sql:
            return
        p = self.parent()
        opened = False
        while p is not None:
            if hasattr(p, "_open_script_in_editor"):
                p._open_script_in_editor({"conn_data": self.conn_data}, sql)
                opened = True
                break
            elif hasattr(p, "connection_manager") and hasattr(p.connection_manager, "script_generator"):
                p.connection_manager.script_generator.open_script_in_editor({"conn_data": self.conn_data}, sql)
                opened = True
                break
            elif hasattr(p, "worksheet_manager"):
                new_tab = p.worksheet_manager.add_tab()
                if new_tab:
                    from widgets.worksheet.editor import CodeEditor
                    qe = new_tab.findChild(CodeEditor, "query_editor") or new_tab.findChild(QPlainTextEdit, "query_editor")
                    if qe:
                        qe.setPlainText(sql)
                    p.worksheet_manager.tab_widget.setCurrentWidget(new_tab)
                opened = True
                break
            p = p.parent()

        if opened:
            self.status_label.setText("Script opened in SQL Worksheet.")
        else:
            QApplication.clipboard().setText(sql)
            self.status_label.setText("Copied script to clipboard (Worksheet not directly accessible).")

    def _save_script_to_file(self, sql: str, script_name: str):
        if not sql:
            return
        obj_name = self.meta.get("name", "script")
        clean_type = script_name.lower().replace(" ", "_").replace("&", "and").replace("/", "_")
        default_filename = f"{obj_name}_{clean_type}.sql"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save SQL Script",
            default_filename,
            "SQL Files (*.sql);;All Files (*)"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(sql)
                self.status_label.setText(f"Script saved to {filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Failed to save file:\n{e}")

    def _copy_ddl(self):
        curr = self.tabs.currentWidget()
        if hasattr(self, "schema_tab") and curr == self.schema_tab:
            schema_info = self.meta.get("schema_info") or {}
            scripts = schema_info.get("scripts", {})
            ddl = scripts.get("Full DDL") or schema_info.get("ddl") or self.meta.get("ddl", "")
        else:
            scripts = self.meta.get("scripts", {})
            ddl = scripts.get("Full DDL") or self.meta.get("ddl", "")
        if ddl:
            QApplication.clipboard().setText(ddl)
            self.status_label.setText("Full DDL script copied to clipboard!")

    def _on_filter_changed(self, text: str):
        filter_text = text.strip().lower()
        # Filter current active table
        curr = self.tabs.currentWidget()
        if isinstance(curr, QTableWidget):
            for row in range(curr.rowCount()):
                match = False
                for col in range(curr.columnCount()):
                    item = curr.item(row, col)
                    if item and filter_text in item.text().lower():
                        match = True
                        break
                curr.setRowHidden(row, not match)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_loading_overlay") and self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())
            self._loading_overlay.raise_()
