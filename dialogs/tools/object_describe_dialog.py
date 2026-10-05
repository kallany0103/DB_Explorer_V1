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

        # 5. DDL Script Tab
        self.ddl_editor = self._create_code_editor(self.meta.get("ddl", ""))
        self.tabs.addTab(self.ddl_editor, qta.icon("mdi.script-text-outline", color="#475569"), "DDL Script")

        cols_count = len(self.meta.get("columns", []))
        self.status_label.setText(f"{cols_count} columns in {self.meta.get('name')}")

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

        # 4. DDL / Summary Tab
        self.ddl_editor = self._create_code_editor(self.meta.get("ddl", ""))
        self.tabs.addTab(self.ddl_editor, qta.icon("mdi.script-text-outline", color="#475569"), "Summary / Script")

        self.status_label.setText(f"{len(tables)} tables, {len(views)} views in schema {self.meta.get('name')}")

    def _on_table_double_clicked(self, index):
        row = index.row()
        table_name = self.schema_tables.item(row, 0).text()
        schema_name = self.meta.get("name")
        full_target = f'"{schema_name}"."{table_name}"' if schema_name else table_name
        self.target = full_target
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

    def _copy_ddl(self):
        ddl = self.meta.get("ddl", "")
        if ddl:
            QApplication.clipboard().setText(ddl)
            self.status_label.setText("DDL script copied to clipboard!")

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
