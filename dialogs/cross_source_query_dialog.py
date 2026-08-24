# dialogs/cross_source_query_dialog.py

import os
import sqlite3
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QLabel, QComboBox, QLineEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QGridLayout, QGroupBox, QRadioButton, QButtonGroup,
    QPlainTextEdit, QMessageBox, QWidget, QFrame
)
import db
from ui.components import PrimaryButton, SecondaryButton


class CrossSourceQueryDialog(QDialog):
    """
    Visual Cross-Source Query & Join Helper for Unified Data Sources.
    Allows joining tables across multiple remote schemas and databases attached to a UDS host.
    """

    def __init__(self, manager, initial_item_data=None, initial_table_name=None, parent=None):
        super().__init__(parent or manager)
        self.manager = manager
        self.item_data = initial_item_data or {}
        self.initial_table_name = initial_table_name

        self.host_conn_data = self.item_data.get("conn_data") or getattr(self.manager, "active_postgres_conn", {})
        self.data_sources = self._load_data_sources()

        self.setWindowTitle("Cross-Source Query Helper")
        self.setMinimumSize(850, 680)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        self._build_ui()
        self._populate_sources()
        self._update_sql_preview()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
            }
            QLabel#dialogSubtitle {
                color: #6b7280;
                font-size: 9pt;
                margin-bottom: 4px;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 9.5pt;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                background-color: #ffffff;
            }
            QComboBox, QLineEdit {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 5px;
                padding: 3px 8px;
                background-color: #ffffff;
                color: #1f2937;
            }
            QComboBox:focus, QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QPlainTextEdit#sqlPreview {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 8px;
            }
        """)

    def _load_data_sources(self):
        """Loads data sources for the active UDS host connection."""
        conn_id = self.host_conn_data.get("id")
        if not conn_id:
            return []
        raw_ds = db.get_data_sources_by_connection(conn_id)
        return raw_ds or []

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 16)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon("mdi.transit-connection-variant", color="#0078d4").pixmap(32, 32))
        
        header_text = QVBoxLayout()
        header_title = QLabel("Cross-Source Query Helper")
        header_title.setObjectName("dialogTitle")
        header_subtitle = QLabel("Generate and execute multi-database JOIN queries across Unified Data Sources.")
        header_subtitle.setObjectName("dialogSubtitle")
        header_text.addWidget(header_title)
        header_text.addWidget(header_subtitle)

        header_layout.addWidget(header_icon)
        header_layout.addLayout(header_text)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # ---------------- Sources & Join Configuration Box ----------------
        join_group = QGroupBox("Cross-Source Join Configuration")
        join_layout = QGridLayout(join_group)
        join_layout.setContentsMargins(16, 18, 16, 16)
        join_layout.setHorizontalSpacing(14)
        join_layout.setVerticalSpacing(10)

        # Column A Header
        lbl_source_a = QLabel("Source A (Base)")
        lbl_source_a.setStyleSheet("font-weight: 600; color: #0078d4;")
        join_layout.addWidget(lbl_source_a, 0, 0)

        lbl_join = QLabel("Join Type & Condition")
        lbl_join.setStyleSheet("font-weight: 600; color: #4b5563;")
        join_layout.addWidget(lbl_join, 0, 1)

        lbl_source_b = QLabel("Source B (Target)")
        lbl_source_b.setStyleSheet("font-weight: 600; color: #107c41;")
        join_layout.addWidget(lbl_source_b, 0, 2)

        # Data Source selectors
        self.ds_combo_a = QComboBox()
        self.ds_combo_a.currentIndexChanged.connect(self._on_ds_a_changed)
        join_layout.addWidget(self.ds_combo_a, 1, 0)

        self.join_type_combo = QComboBox()
        self.join_type_combo.addItems([
            "INNER JOIN",
            "LEFT JOIN",
            "RIGHT JOIN",
            "FULL OUTER JOIN",
            "CROSS JOIN"
        ])
        self.join_type_combo.currentIndexChanged.connect(self._update_sql_preview)
        join_layout.addWidget(self.join_type_combo, 1, 1)

        self.ds_combo_b = QComboBox()
        self.ds_combo_b.currentIndexChanged.connect(self._on_ds_b_changed)
        join_layout.addWidget(self.ds_combo_b, 1, 2)

        # Table selectors
        self.table_combo_a = QComboBox()
        self.table_combo_a.currentIndexChanged.connect(self._on_table_a_changed)
        join_layout.addWidget(self.table_combo_a, 2, 0)

        # ON Condition row
        cond_layout = QHBoxLayout()
        self.col_combo_a = QComboBox()
        self.col_combo_a.setEditable(True)
        self.col_combo_a.setPlaceholderText("a.column")
        self.col_combo_a.currentTextChanged.connect(self._update_sql_preview)

        eq_lbl = QLabel("=")
        eq_lbl.setStyleSheet("font-weight: bold; padding: 0 4px;")

        self.col_combo_b = QComboBox()
        self.col_combo_b.setEditable(True)
        self.col_combo_b.setPlaceholderText("b.column")
        self.col_combo_b.currentTextChanged.connect(self._update_sql_preview)

        cond_layout.addWidget(self.col_combo_a, stretch=1)
        cond_layout.addWidget(eq_lbl)
        cond_layout.addWidget(self.col_combo_b, stretch=1)
        join_layout.addLayout(cond_layout, 2, 1)

        self.table_combo_b = QComboBox()
        self.table_combo_b.currentIndexChanged.connect(self._on_table_b_changed)
        join_layout.addWidget(self.table_combo_b, 2, 2)

        main_layout.addWidget(join_group)

        # ---------------- Query Options Box ----------------
        options_group = QGroupBox("Query Filters & Options")
        options_layout = QGridLayout(options_group)
        options_layout.setContentsMargins(16, 14, 16, 14)
        options_layout.setHorizontalSpacing(14)
        options_layout.setVerticalSpacing(8)

        # WHERE Clause
        options_layout.addWidget(QLabel("WHERE Filter (optional):"), 0, 0)
        self.where_input = QLineEdit()
        self.where_input.setPlaceholderText("e.g. a.status = 'ACTIVE' AND b.amount > 100")
        self.where_input.textChanged.connect(self._update_sql_preview)
        options_layout.addWidget(self.where_input, 0, 1)

        # ORDER BY & LIMIT
        options_layout.addWidget(QLabel("ORDER BY (optional):"), 1, 0)
        order_layout = QHBoxLayout()
        self.order_input = QLineEdit()
        self.order_input.setPlaceholderText("e.g. a.created_at DESC")
        self.order_input.textChanged.connect(self._update_sql_preview)
        
        limit_lbl = QLabel("LIMIT:")
        self.limit_input = QLineEdit("100")
        self.limit_input.setFixedWidth(70)
        self.limit_input.textChanged.connect(self._update_sql_preview)

        order_layout.addWidget(self.order_input, stretch=1)
        order_layout.addWidget(limit_lbl)
        order_layout.addWidget(self.limit_input)
        options_layout.addLayout(order_layout, 1, 1)

        main_layout.addWidget(options_group)

        # ---------------- SQL Preview Box ----------------
        preview_group = QGroupBox("Generated Cross-Source SQL")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(14, 14, 14, 14)

        self.sql_preview = QPlainTextEdit()
        self.sql_preview.setObjectName("sqlPreview")
        self.sql_preview.setMinimumHeight(150)
        preview_layout.addWidget(self.sql_preview)

        main_layout.addWidget(preview_group, stretch=1)

        # ---------------- Bottom Action Buttons ----------------
        btn_layout = QHBoxLayout()
        
        self.copy_btn = SecondaryButton("Copy SQL", qta.icon("mdi.content-copy", color="#374151"))
        self.copy_btn.clicked.connect(self._copy_sql)
        btn_layout.addWidget(self.copy_btn)

        self.save_view_btn = SecondaryButton("Save as View...", qta.icon("mdi.content-save-outline", color="#374151"))
        self.save_view_btn.clicked.connect(self._save_as_unified_view)
        btn_layout.addWidget(self.save_view_btn)

        btn_layout.addStretch()

        self.close_btn = SecondaryButton("Cancel")
        self.close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.close_btn)

        self.run_btn = PrimaryButton("Execute in Worksheet", qta.icon("mdi.play", color="#ffffff"))
        self.run_btn.clicked.connect(self._execute_in_worksheet)
        btn_layout.addWidget(self.run_btn)

        main_layout.addLayout(btn_layout)

    def _populate_sources(self):
        """Populates data source combos."""
        if not self.data_sources:
            return

        self.ds_combo_a.clear()
        self.ds_combo_b.clear()

        initial_ds_id = None
        if self.item_data.get("ds_data"):
            initial_ds_id = self.item_data["ds_data"].get("id")

        for ds in self.data_sources:
            name = ds.get("short_name") or ds.get("source_name") or ds.get("display_name") or ds.get("name")
            stype = (ds.get("source_type") or "POSTGRES").upper()
            label = f"{name} ({stype})"
            self.ds_combo_a.addItem(label, ds)
            self.ds_combo_b.addItem(label, ds)

        # Select initial data source for Source A
        if initial_ds_id:
            for i in range(self.ds_combo_a.count()):
                d = self.ds_combo_a.itemData(i)
                if d and d.get("id") == initial_ds_id:
                    self.ds_combo_a.setCurrentIndex(i)
                    break

        # Select a different data source for Source B if available
        if self.ds_combo_b.count() > 1:
            curr_a = self.ds_combo_a.currentIndex()
            target_b = 1 if curr_a == 0 else 0
            self.ds_combo_b.setCurrentIndex(target_b)

    def _get_tables_for_ds(self, ds_data):
        """Fetches list of table names and their schema for a data source."""
        if not ds_data:
            return []

        source_type = (ds_data.get("source_type") or "POSTGRES").upper()
        server_name = ds_data.get("server_name")
        schema_name = ds_data.get("schema_name") or f"{ds_data.get('short_name')}_schema"
        db_path = ds_data.get("db_path") or ds_data.get("file_path")

        # 1. Check local SQLite directly if SQLITE
        if source_type == "SQLITE" and db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as s_conn:
                    s_cur = s_conn.cursor()
                    s_cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;")
                    return [{"table_name": r[0], "schema_name": "main"} for r in s_cur.fetchall()]
            except Exception:
                pass

        # 2. Query host PostgreSQL foreign tables
        try:
            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Cross Source Helper)",
                bypass_cooldown=True
            )
            if conn:
                cur = conn.cursor()
                if server_name:
                    cur.execute("""
                        SELECT c.relname, n.nspname
                        FROM pg_foreign_table ft
                        JOIN pg_class c ON c.oid = ft.ftrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        JOIN pg_foreign_server s ON s.oid = ft.ftserver
                        WHERE s.srvname = %s
                        ORDER BY c.relname;
                    """, (server_name,))
                else:
                    cur.execute("""
                        SELECT c.relname, n.nspname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = %s AND c.relkind IN ('r', 'v', 'f')
                        ORDER BY c.relname;
                    """, (schema_name,))
                rows = cur.fetchall()
                conn.close()
                if rows:
                    return [{"table_name": r[0], "schema_name": r[1]} for r in rows]
        except Exception:
            pass

        return []

    def _get_columns_for_table(self, ds_data, schema_name, table_name):
        """Fetches column names for a table."""
        if not table_name:
            return []

        source_type = (ds_data.get("source_type") or "POSTGRES").upper()
        db_path = ds_data.get("db_path") or ds_data.get("file_path")

        if source_type == "SQLITE" and db_path and os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as s_conn:
                    s_cur = s_conn.cursor()
                    s_cur.execute(f"PRAGMA table_info('{table_name}');")
                    return [r[1] for r in s_cur.fetchall()]
            except Exception:
                pass

        try:
            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Column Introspector)",
                bypass_cooldown=True
            )
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = %s
                    ORDER BY ordinal_position;
                """, (table_name, schema_name))
                cols = [r[0] for r in cur.fetchall()]
                conn.close()
                if cols:
                    return cols
        except Exception:
            pass

        return ["id"]

    def _on_ds_a_changed(self):
        ds = self.ds_combo_a.currentData()
        tables = self._get_tables_for_ds(ds)
        self.table_combo_a.clear()
        for t in tables:
            self.table_combo_a.addItem(t["table_name"], t)

        if self.initial_table_name:
            idx = self.table_combo_a.findText(self.initial_table_name)
            if idx >= 0:
                self.table_combo_a.setCurrentIndex(idx)

        self._on_table_a_changed()

    def _on_ds_b_changed(self):
        ds = self.ds_combo_b.currentData()
        tables = self._get_tables_for_ds(ds)
        self.table_combo_b.clear()
        for t in tables:
            self.table_combo_b.addItem(t["table_name"], t)
        self._on_table_b_changed()

    def _on_table_a_changed(self):
        ds = self.ds_combo_a.currentData() or {}
        t_data = self.table_combo_a.currentData() or {}
        table_name = self.table_combo_a.currentText()
        schema_name = t_data.get("schema_name") or ds.get("schema_name", "public")

        cols = self._get_columns_for_table(ds, schema_name, table_name)
        self.col_combo_a.clear()
        for c in cols:
            self.col_combo_a.addItem(f"a.{c}", c)

        self._auto_match_join_columns()
        self._update_sql_preview()

    def _on_table_b_changed(self):
        ds = self.ds_combo_b.currentData() or {}
        t_data = self.table_combo_b.currentData() or {}
        table_name = self.table_combo_b.currentText()
        schema_name = t_data.get("schema_name") or ds.get("schema_name", "public")

        cols = self._get_columns_for_table(ds, schema_name, table_name)
        self.col_combo_b.clear()
        for c in cols:
            self.col_combo_b.addItem(f"b.{c}", c)

        self._auto_match_join_columns()
        self._update_sql_preview()

    def _auto_match_join_columns(self):
        """Attempts to match join columns with common names (id, dept_id, user_id, etc.)."""
        cols_a = [self.col_combo_a.itemData(i) for i in range(self.col_combo_a.count())]
        cols_b = [self.col_combo_b.itemData(i) for i in range(self.col_combo_b.count())]

        common = [c for c in cols_a if c in cols_b and c is not None]
        if common:
            target = common[0]
            for i in range(self.col_combo_a.count()):
                if self.col_combo_a.itemData(i) == target:
                    self.col_combo_a.setCurrentIndex(i)
                    break
            for i in range(self.col_combo_b.count()):
                if self.col_combo_b.itemData(i) == target:
                    self.col_combo_b.setCurrentIndex(i)
                    break

    def _generate_sql(self, include_limit=True, include_semicolon=True, include_header=True):
        """Builds the complete cross-source SQL query."""
        import re
        ds_a = self.ds_combo_a.currentData() or {}
        t_data_a = self.table_combo_a.currentData() or {}
        tbl_a = self.table_combo_a.currentText()

        ds_b = self.ds_combo_b.currentData() or {}
        t_data_b = self.table_combo_b.currentData() or {}
        tbl_b = self.table_combo_b.currentText()

        def _resolve_schema(ds, t_data):
            schema = ds.get("schema_name")
            if not schema or schema == "main":
                name = ds.get("short_name") or ds.get("source_name") or ds.get("display_name") or ds.get("name") or "sqlite"
                clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name)).strip('_').lower()
                schema = f"{clean_name}_schema"
            return schema

        schema_a = _resolve_schema(ds_a, t_data_a)
        schema_b = _resolve_schema(ds_b, t_data_b)

        if not tbl_a or not tbl_b:
            return "-- Please select tables for both Source A and Source B."

        join_type = self.join_type_combo.currentText()
        col_a_text = self.col_combo_a.currentText().strip() or "a.id"
        col_b_text = self.col_combo_b.currentText().strip() or "b.id"

        sql_lines = []
        if include_header:
            sql_lines.extend([
                f"-- ==========================================================",
                f"-- Cross-Source Query: [{self.ds_combo_a.currentText()}] x [{self.ds_combo_b.currentText()}]",
                f"-- ==========================================================",
            ])

        sql_lines.extend([
            f"SELECT",
            f"    a.*,",
            f"    b.*",
            f'FROM "{schema_a}"."{tbl_a}" AS a',
        ])

        if join_type == "CROSS JOIN":
            sql_lines.append(f'CROSS JOIN "{schema_b}"."{tbl_b}" AS b')
        else:
            sql_lines.append(f'{join_type} "{schema_b}"."{tbl_b}" AS b')
            sql_lines.append(f"    ON {col_a_text} = {col_b_text}")

        where_clause = self.where_input.text().strip()
        if where_clause:
            sql_lines.append(f"WHERE {where_clause}")

        order_clause = self.order_input.text().strip()
        if order_clause:
            sql_lines.append(f"ORDER BY {order_clause}")

        if include_limit:
            limit_val = self.limit_input.text().strip()
            if limit_val and limit_val.isdigit():
                sql_lines.append(f"LIMIT {limit_val}")

        if include_semicolon:
            sql_lines.append(";")

        return "\n".join(sql_lines)

    def _update_sql_preview(self):
        sql = self._generate_sql()
        self.sql_preview.setPlainText(sql)

    def _copy_sql(self):
        sql = self.sql_preview.toPlainText()
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(sql)
        self.copy_btn.setText("Copied!")
        self.copy_btn.setIcon(qta.icon("mdi.check", color="#107c41"))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (
            self.copy_btn.setText("Copy SQL"),
            self.copy_btn.setIcon(qta.icon("mdi.content-copy", color="#374151"))
        ))

    def _save_as_unified_view(self):
        """Saves the current cross-source JOIN query as a View on the UDS host database."""
        from PySide6.QtWidgets import QInputDialog
        tbl_a = self.table_combo_a.currentText().strip()
        tbl_b = self.table_combo_b.currentText().strip()
        default_name = f"v_{tbl_a}_{tbl_b}".lower() if tbl_a and tbl_b else "v_unified_join"

        view_name, ok = QInputDialog.getText(
            self,
            "Save JOIN as Unified View",
            "Enter View Name:",
            QLineEdit.EchoMode.Normal,
            default_name
        )
        if not ok or not view_name.strip():
            return

        view_name = view_name.strip()
        if view_name.startswith("v_"):
            view_name = view_name[2:]

        sql_body = self._generate_sql(include_limit=False, include_semicolon=False, include_header=False)

        try:
            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Create Unified View)",
                bypass_cooldown=True
            )
            if not conn:
                QMessageBox.critical(self, "Connection Error", "Could not connect to UDS host database.")
                return

            cur = conn.cursor()
            cur.execute('CREATE SCHEMA IF NOT EXISTS "uds_views";')
            cur.execute(f'CREATE OR REPLACE VIEW "uds_views"."{view_name}" AS\n{sql_body};')
            cur.execute(f'CREATE OR REPLACE VIEW "public"."v_{view_name}" AS\n{sql_body};')
            conn.commit()
            cur.close()
            conn.close()

            QMessageBox.information(
                self,
                "View Created",
                f"Unified View '{view_name}' saved successfully in host database!"
            )
            self.accept()

            # Refresh UDS Schema Tree
            if hasattr(self.manager, "refresh_uds_schema"):
                self.manager.refresh_uds_schema()
            elif hasattr(self.manager, "load_uds_schema"):
                self.manager.load_uds_schema(self.host_conn_data)

        except Exception as e:
            ds_a = self.ds_combo_a.currentData() or {}
            ds_b = self.ds_combo_b.currentData() or {}
            st_a = str(ds_a.get("source_type") or "").lower()
            st_b = str(ds_b.get("source_type") or "").lower()
            if "sqlite" in st_a or "sqlite" in st_b:
                QMessageBox.warning(
                    self,
                    "Remote View Notice",
                    f"Could not save server-side view '{view_name}':\n{e}\n\n"
                    "Note: Cloud PostgreSQL servers (like Aiven) without 'sqlite_fdw' installed cannot build server-side views referencing local SQLite files. "
                    "You can still click 'Execute in Worksheet' to query this JOIN instantly!"
                )
            else:
                QMessageBox.critical(self, "Error Creating View", f"Failed to save view '{view_name}':\n{e}")

    def _execute_in_worksheet(self):
        """Creates a new worksheet tab with the query and executes it against the host connection."""
        sql = self.sql_preview.toPlainText().strip()
        if not sql or sql.startswith("-- Please"):
            QMessageBox.warning(self, "Invalid Query", "Please select valid tables for both sources.")
            return

        self.accept()

        new_tab = self.manager.add_tab()
        query_editor = new_tab.findChild(QPlainTextEdit, "query_editor")
        db_combo_box = new_tab.findChild(QComboBox, "db_combo_box")

        # Select host UDS connection
        conn_id = self.host_conn_data.get("id")
        if db_combo_box and conn_id:
            for i in range(db_combo_box.count()):
                d = db_combo_box.itemData(i)
                if d and d.get("id") == conn_id:
                    db_combo_box.setCurrentIndex(i)
                    break

        if query_editor:
            query_editor.setPlainText(sql)

        self.manager.tab_widget.setCurrentWidget(new_tab)
        self.manager.execute_query(self.host_conn_data, sql)
