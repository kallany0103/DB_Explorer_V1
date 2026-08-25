# dialogs/uds_virtual_view_dialog.py

import json
import psycopg2
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QTabWidget, QWidget, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QAbstractItemView
)
from ui.components import SearchBox, SecondaryButton, PrimaryButton
import db


class UDSVirtualViewMaskingDialog(QDialog):
    def __init__(self, parent=None, host_conn_data=None, initial_table=None):
        super().__init__(parent)

        self.host_conn_data = host_conn_data or {}
        self.initial_table = initial_table
        self.foreign_tables = [] # list of dicts: {'schema': s, 'table': t, 'columns': [cols...]}
        self.joins = [] # list of join config dicts

        self.setWindowTitle("Create UDS Virtual View & Data Masking")
        self.setMinimumSize(860, 680)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Header Title
        header_title = QLabel("UDS Virtual View & Data Masking Creator")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Visually combine UDS foreign tables, configure column aliases, and apply column-level data masking."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        # Tabs
        self.tabs = QTabWidget()

        # ---------------- Tab 1: Visual Builder & Masking ----------------
        self.tab_builder = QWidget()
        builder_layout = QVBoxLayout(self.tab_builder)
        builder_layout.setContentsMargins(16, 16, 16, 16)
        builder_layout.setSpacing(12)

        # Config Form
        config_form = QFormLayout()
        config_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        config_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        config_form.setHorizontalSpacing(18)
        config_form.setVerticalSpacing(10)

        self.view_name_input = QLineEdit()
        self.view_name_input.setPlaceholderText("e.g. v_masked_patient_billing")
        self.view_name_input.textChanged.connect(self._generate_sql)

        self.target_schema_combo = QComboBox()
        self.target_schema_combo.addItems(["uds_views", "public"])
        self.target_schema_combo.currentTextChanged.connect(self._generate_sql)

        self.view_type_combo = QComboBox()
        self.view_type_combo.addItems(["Standard VIEW", "MATERIALIZED VIEW"])
        self.view_type_combo.currentTextChanged.connect(self._generate_sql)

        self.primary_table_combo = QComboBox()
        self.primary_table_combo.currentIndexChanged.connect(self._on_primary_table_changed)

        config_form.addRow("View Name:", self.view_name_input)
        config_form.addRow("Target Schema:", self.target_schema_combo)
        config_form.addRow("View Type:", self.view_type_combo)
        config_form.addRow("Primary Foreign Table:", self.primary_table_combo)

        builder_layout.addLayout(config_form)

        # Join Builder Section
        join_header_layout = QHBoxLayout()
        join_lbl = QLabel("Cross-Table Joins (Optional)")
        join_lbl.setStyleSheet("font-weight: 600; color: #1f2937;")
        join_header_layout.addWidget(join_lbl)

        self.btn_add_join = SecondaryButton("Add Join Table")
        self.btn_add_join.setIcon(qta.icon("fa5s.plus", color="#0078d4"))
        self.btn_add_join.clicked.connect(self._add_join_row)
        join_header_layout.addWidget(self.btn_add_join)
        join_header_layout.addStretch()

        builder_layout.addLayout(join_header_layout)

        self.joins_container = QVBoxLayout()
        self.joins_container.setSpacing(6)
        builder_layout.addLayout(self.joins_container)

        # Column & Masking Grid
        grid_lbl = QLabel("Select Columns & Apply Masking Rules")
        grid_lbl.setStyleSheet("font-weight: 600; color: #1f2937; margin-top: 4px;")
        builder_layout.addWidget(grid_lbl)

        # Grid Toolbar
        grid_toolbar = QHBoxLayout()
        self.btn_select_all = SecondaryButton("Select All")
        self.btn_select_all.clicked.connect(self._select_all_columns)
        grid_toolbar.addWidget(self.btn_select_all)

        self.btn_deselect_all = SecondaryButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self._deselect_all_columns)
        grid_toolbar.addWidget(self.btn_deselect_all)

        self.btn_auto_mask = SecondaryButton("Auto-Detect & Mask Sensitive Cols")
        self.btn_auto_mask.setIcon(qta.icon("fa5s.user-shield", color="#10b981"))
        self.btn_auto_mask.clicked.connect(self._auto_detect_masking)
        grid_toolbar.addWidget(self.btn_auto_mask)
        grid_toolbar.addStretch()

        builder_layout.addLayout(grid_toolbar)

        self.grid = QTableWidget()
        self.grid.setColumnCount(6)
        self.grid.setHorizontalHeaderLabels([
            "Include", "Source Table", "Column Name", "Output Alias", "Masking Rule", "Generated Expression"
        ])
        self.grid.setAlternatingRowColors(True)
        self.grid.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.grid.setColumnWidth(0, 65)
        self.grid.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.grid.setColumnWidth(1, 240)
        self.grid.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.grid.setColumnWidth(2, 140)
        self.grid.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.grid.setColumnWidth(3, 140)
        self.grid.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.grid.setColumnWidth(4, 240)
        self.grid.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.grid.verticalHeader().setVisible(False)
        self.grid.cellChanged.connect(self._on_grid_cell_changed)
        builder_layout.addWidget(self.grid, stretch=1)

        self.tabs.addTab(self.tab_builder, "Visual Builder & Masking")

        # ---------------- Tab 2: SQL & Live Preview ----------------
        self.tab_preview = QWidget()
        preview_layout = QVBoxLayout(self.tab_preview)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(10)

        sql_lbl = QLabel("Generated SQL View Definition:")
        sql_lbl.setStyleSheet("font-weight: 600; color: #1f2937;")
        preview_layout.addWidget(sql_lbl)

        self.sql_editor = QTextEdit()
        self.sql_editor.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9.5pt;
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #d1d5db;
                border-radius: 5px;
            }
        """)
        preview_layout.addWidget(self.sql_editor, stretch=1)

        # Live Data Preview Section
        prev_toolbar = QHBoxLayout()
        self.btn_preview_data = SecondaryButton("Preview Sample Masked Data")
        self.btn_preview_data.setIcon(qta.icon("fa5s.eye", color="#0078d4"))
        self.btn_preview_data.clicked.connect(self._preview_masked_data)
        prev_toolbar.addWidget(self.btn_preview_data)
        prev_toolbar.addStretch()

        preview_layout.addLayout(prev_toolbar)

        self.preview_table = QTableWidget()
        self.preview_table.verticalHeader().setVisible(False)
        preview_layout.addWidget(self.preview_table, stretch=1)

        self.tabs.addTab(self.tab_preview, "SQL & Live Data Preview")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Bottom Action Buttons
        self.worksheet_btn = SecondaryButton("Open in SQL Worksheet")
        self.worksheet_btn.setIcon(qta.icon("fa5s.code", color="#0078d4"))
        self.worksheet_btn.clicked.connect(self.open_in_worksheet)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = PrimaryButton("Create View")
        self.save_btn.setIcon(qta.icon("fa5s.save", color="#ffffff"))
        self.save_btn.clicked.connect(self.create_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.worksheet_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addWidget(self.tabs, stretch=1)
        layout.addLayout(button_layout)

        # Load foreign tables from host
        self._load_available_foreign_tables()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1f2937; }
            QLabel#dialogSubtitle { color: #6b7280; margin-bottom: 2px; }
            QTabWidget::pane { border: 1px solid #d1d5db; border-radius: 6px; background-color: #ffffff; top: -1px; }
            QTabBar::tab {
                background: #f3f4f6; border: 1px solid #d1d5db; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 16px; margin-right: 2px; font-size: 9pt; color: #4b5563;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: 600; color: #0078d4; border-bottom: 1px solid #ffffff; }
            QTabBar::tab:hover:!selected { background: #e5e7eb; }
            QLineEdit, QComboBox { min-height: 28px; border: 1px solid #d1d5db; border-radius: 5px; background: white; padding: 2px 8px; color: #1f2937; }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #0078d4; }
            QTableWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #e2e8f0;
                color: #1e293b;
                font-size: 9pt;
                outline: 0;
            }
            QTableWidget::item {
                padding: 4px 8px;
                color: #1e293b;
            }
            QTableWidget::item:selected {
                background-color: #e0f2fe;
                color: #0369a1;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #1e293b;
                padding: 6px 10px;
                font-weight: 600;
                font-size: 9pt;
                border: none;
                border-bottom: 2px solid #cbd5e1;
                border-right: 1px solid #e2e8f0;
            }
            QTableWidget QComboBox {
                min-height: 24px;
                max-height: 26px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: #ffffff;
                padding: 1px 6px;
                font-size: 8.5pt;
                color: #1e293b;
            }
            QTableWidget QComboBox:hover {
                border-color: #0078d4;
            }
            QTableWidget QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1e293b;
                selection-background-color: #e0f2fe;
                selection-color: #0369a1;
                border: 1px solid #cbd5e1;
            }
        """)

    def _load_available_foreign_tables(self):
        if not self.host_conn_data:
            return

        try:
            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Fetch UDS Tables)",
                bypass_cooldown=True
            )
            if not conn:
                return

            cur = conn.cursor()
            # Fetch all foreign tables and their schemas
            cur.execute("""
                SELECT n.nspname, c.relname
                FROM pg_foreign_table ft
                JOIN pg_class c ON c.oid = ft.ftrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                ORDER BY n.nspname, c.relname;
            """)
            rows = cur.fetchall()

            self.foreign_tables = []
            for schema_name, table_name in rows:
                # Fetch columns for table
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema_name, table_name))
                cols = [r[0] for r in cur.fetchall()]

                self.foreign_tables.append({
                    'schema': schema_name,
                    'table': table_name,
                    'full_name': f'"{schema_name}"."{table_name}"',
                    'columns': cols
                })

            cur.close()
            conn.close()

            # Populate primary table combo
            self.primary_table_combo.blockSignals(True)
            self.primary_table_combo.clear()
            for ft in self.foreign_tables:
                self.primary_table_combo.addItem(ft['full_name'], ft)
            self.primary_table_combo.blockSignals(False)

            if self.foreign_tables:
                # Set initial table if provided
                if self.initial_table:
                    for i in range(self.primary_table_combo.count()):
                        if self.initial_table.lower() in self.primary_table_combo.itemText(i).lower():
                            self.primary_table_combo.setCurrentIndex(i)
                            break

                self._on_primary_table_changed()

        except Exception as e:
            print(f"Notice: Could not load foreign tables for virtual view dialog: {e}")

    def _on_primary_table_changed(self):
        primary_ft = self.primary_table_combo.currentData()
        if not primary_ft and self.foreign_tables:
            primary_ft = self.foreign_tables[0]

        if not self.view_name_input.text().strip() and primary_ft:
            self.view_name_input.setText(f"v_masked_{primary_ft['table']}")

        self._rebuild_grid()

    def _add_join_row(self):
        join_widget = QWidget()
        h_layout = QHBoxLayout(join_widget)
        h_layout.setContentsMargins(0, 2, 0, 2)
        h_layout.setSpacing(8)

        join_type_combo = QComboBox()
        join_type_combo.addItems(["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN"])
        join_type_combo.setFixedWidth(110)

        join_table_combo = QComboBox()
        for ft in self.foreign_tables:
            join_table_combo.addItem(ft['full_name'], ft)

        on_label = QLabel("ON")
        on_label.setStyleSheet("font-weight: 600;")

        cond_input = QLineEdit()
        cond_input.setPlaceholderText("e.g. primary_col = join_col")
        cond_input.textChanged.connect(self._rebuild_grid)

        remove_btn = SecondaryButton("X")
        remove_btn.setFixedWidth(30)
        remove_btn.setStyleSheet("color: #ef4444; font-weight: bold;")

        h_layout.addWidget(join_type_combo)
        h_layout.addWidget(join_table_combo)
        h_layout.addWidget(on_label)
        h_layout.addWidget(cond_input, stretch=1)
        h_layout.addWidget(remove_btn)

        self.joins_container.addWidget(join_widget)

        join_info = {
            'widget': join_widget,
            'type_combo': join_type_combo,
            'table_combo': join_table_combo,
            'cond_input': cond_input
        }
        self.joins.append(join_info)

        remove_btn.clicked.connect(lambda: self._remove_join_row(join_info))
        join_type_combo.currentIndexChanged.connect(self._rebuild_grid)
        join_table_combo.currentIndexChanged.connect(self._rebuild_grid)

        self._rebuild_grid()

    def _remove_join_row(self, join_info):
        if join_info in self.joins:
            self.joins.remove(join_info)
            join_info['widget'].deleteLater()
            self._rebuild_grid()

    def _rebuild_grid(self):
        self.grid.blockSignals(True)
        self.grid.setRowCount(0)

        # Collect active tables: primary table + joined tables
        tables_to_include = []
        p_data = self.primary_table_combo.currentData()
        if p_data:
            tables_to_include.append(p_data)

        for j in self.joins:
            j_data = j['table_combo'].currentData()
            if j_data and j_data not in tables_to_include:
                tables_to_include.append(j_data)

        row_idx = 0
        for ft in tables_to_include:
            schema_tbl = ft['full_name']
            for col in ft['columns']:
                self.grid.insertRow(row_idx)
                self.grid.setRowHeight(row_idx, 36)

                # 0. Include Checkbox
                chk = QCheckBox()
                chk.setChecked(True)
                chk.stateChanged.connect(self._on_grid_cell_changed)
                chk_container = QWidget()
                chk_lay = QHBoxLayout(chk_container)
                chk_lay.addWidget(chk)
                chk_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                chk_lay.setContentsMargins(0, 0, 0, 0)
                self.grid.setCellWidget(row_idx, 0, chk_container)

                # 1. Source Table
                item_src = QTableWidgetItem(schema_tbl)
                item_src.setFlags(item_src.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(row_idx, 1, item_src)

                # 2. Column Name
                item_col = QTableWidgetItem(col)
                item_col.setFlags(item_col.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(row_idx, 2, item_col)

                # 3. Output Alias
                item_alias = QTableWidgetItem(col)
                self.grid.setItem(row_idx, 3, item_alias)

                # 4. Masking Rule Combo
                rule_combo = QComboBox()
                rule_combo.addItems([
                    "None (Raw Data)",
                    "Email Masking (e.g. j***n@domain.com)",
                    "Phone / SSN Masking (e.g. ***-***-1234)",
                    "Partial Text (First 2 Chars)",
                    "Full Redaction ('[REDACTED]')",
                    "MD5 / SHA256 Hash",
                    "Numeric Noise (Round 100)",
                    "Custom Expression"
                ])
                rule_combo.currentIndexChanged.connect(lambda idx, r=row_idx: self._on_rule_changed(r))
                self.grid.setCellWidget(row_idx, 4, rule_combo)

                # 5. Generated Expression
                expr_item = QTableWidgetItem(f'{schema_tbl}."{col}"')
                self.grid.setItem(row_idx, 5, expr_item)

                row_idx += 1

        self.grid.blockSignals(False)
        self._generate_sql()

    def _on_rule_changed(self, row):
        combo = self.grid.cellWidget(row, 4)
        if not combo:
            return

        rule = combo.currentText()
        src_tbl = self.grid.item(row, 1).text()
        col_name = self.grid.item(row, 2).text()
        col_ref = f'{src_tbl}."{col_name}"'

        expr = col_ref
        if "Email" in rule:
            expr = f"regexp_replace({col_ref}::text, '^(.)[^@]*@', '\\1***@')"
        elif "Phone" in rule or "SSN" in rule:
            expr = f"regexp_replace({col_ref}::text, '^.*(.{{4}})$', '***-***-\\1')"
        elif "Partial Text" in rule:
            expr = f"substr({col_ref}::text, 1, 2) || '***'"
        elif "Full Redaction" in rule:
            expr = "'[REDACTED]'"
        elif "MD5" in rule:
            expr = f"md5({col_ref}::text)"
        elif "Numeric Noise" in rule:
            expr = f"round({col_ref}::numeric, -2)"

        expr_item = self.grid.item(row, 5)
        if expr_item:
            expr_item.setText(expr)

        self._generate_sql()

    def _on_grid_cell_changed(self, *args):
        self._generate_sql()

    def _select_all_columns(self):
        for r in range(self.grid.rowCount()):
            chk_container = self.grid.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk:
                    chk.setChecked(True)
        self._generate_sql()

    def _deselect_all_columns(self):
        for r in range(self.grid.rowCount()):
            chk_container = self.grid.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk:
                    chk.setChecked(False)
        self._generate_sql()

    def _auto_detect_masking(self):
        sensitive_keywords = ["email", "mail", "ssn", "phone", "mobile", "salary", "password", "secret", "tax_id"]
        for r in range(self.grid.rowCount()):
            col_name = self.grid.item(r, 2).text().lower()
            combo = self.grid.cellWidget(r, 4)
            if combo:
                if "email" in col_name or "mail" in col_name:
                    combo.setCurrentText("Email Masking (e.g. j***n@domain.com)")
                elif "ssn" in col_name or "phone" in col_name or "mobile" in col_name:
                    combo.setCurrentText("Phone / SSN Masking (e.g. ***-***-1234)")
                elif "salary" in col_name or "tax" in col_name:
                    combo.setCurrentText("Numeric Noise (Round 100)")
                elif "password" in col_name or "secret" in col_name:
                    combo.setCurrentText("MD5 / SHA256 Hash")
        self._generate_sql()

    def _generate_sql(self):
        view_name = self.view_name_input.text().strip() or "v_uds_masked_view"
        schema_name = self.target_schema_combo.currentText()
        is_mat = "MATERIALIZED" in self.view_type_combo.currentText()

        p_data = self.primary_table_combo.currentData()
        if not p_data:
            self.sql_editor.setText("-- Select a primary table to generate SQL view definition.")
            return

        select_cols = []
        for r in range(self.grid.rowCount()):
            chk_container = self.grid.cellWidget(r, 0)
            if chk_container:
                chk = chk_container.findChild(QCheckBox)
                if chk and chk.isChecked():
                    alias = self.grid.item(r, 3).text().strip() or self.grid.item(r, 2).text()
                    expr = self.grid.item(r, 5).text().strip()
                    select_cols.append(f"  {expr} AS \"{alias}\"")

        if not select_cols:
            self.sql_editor.setText("-- Check at least one column to build view.")
            return

        cols_str = ",\n".join(select_cols)
        from_str = f"FROM {p_data['full_name']}"

        join_strs = []
        for j in self.joins:
            j_data = j['table_combo'].currentData()
            j_type = j['type_combo'].currentText()
            j_cond = j['cond_input'].text().strip()
            if j_data:
                if j_cond:
                    join_strs.append(f"{j_type} {j_data['full_name']} ON {j_cond}")
                else:
                    join_strs.append(f"{j_type} {j_data['full_name']}")

        joins_str = ("\n" + "\n".join(join_strs)) if join_strs else ""

        mat_kw = "MATERIALIZED VIEW" if is_mat else "VIEW"
        sql = f'CREATE OR REPLACE {mat_kw} "{schema_name}"."{view_name}" AS\nSELECT\n{cols_str}\n{from_str}{joins_str};'

        self.sql_editor.setText(sql)

    def _on_tab_changed(self, index):
        if index == 1:
            self._generate_sql()

    def _preview_masked_data(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql or sql.startswith("--"):
            QMessageBox.warning(self, "Preview Error", "Please configure columns and view name first.")
            return

        try:
            # Extract SELECT body
            select_idx = sql.upper().find("SELECT")
            if select_idx == -1:
                return

            inner_select = sql[select_idx:].rstrip(";")
            preview_query = f"SELECT * FROM ({inner_select}) AS sub_preview LIMIT 10;"

            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Preview Masked View)",
                bypass_cooldown=True
            )
            if not conn:
                QMessageBox.critical(self, "Connection Error", "Could not connect to host PostgreSQL database.")
                return

            cur = conn.cursor()
            cur.execute(preview_query)
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            cur.close()
            conn.close()

            self.preview_table.setColumnCount(len(col_names))
            self.preview_table.setHorizontalHeaderLabels(col_names)
            self.preview_table.setRowCount(len(rows))

            for r_idx, row in enumerate(rows):
                for c_idx, val in enumerate(row):
                    cell_item = QTableWidgetItem(str(val) if val is not None else "NULL")
                    self.preview_table.setItem(r_idx, c_idx, cell_item)

            self.preview_table.resizeColumnsToContents()

        except Exception as e:
            QMessageBox.critical(self, "Preview Query Error", f"Could not execute preview query:\n{e}")

    def create_view(self):
        view_name = self.view_name_input.text().strip()
        if not view_name:
            QMessageBox.warning(self, "Missing Info", "Please provide a View Name.")
            return

        sql_body = self.sql_editor.toPlainText().strip()
        if not sql_body or sql_body.startswith("--"):
            QMessageBox.warning(self, "Missing Info", "Please configure columns for the view.")
            return

        schema_name = self.target_schema_combo.currentText()

        try:
            conn = db.create_postgres_connection(
                self.host_conn_data,
                application_name="Universal SQL Client (Create UDS Virtual View)",
                bypass_cooldown=True
            )
            if not conn:
                QMessageBox.critical(self, "Connection Error", "Could not connect to host PostgreSQL database.")
                return

            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";')
            cur.execute(sql_body)
            cur.close()
            conn.close()

            QMessageBox.information(
                self,
                "Success",
                f"Virtual View '{schema_name}.{view_name}' created successfully!"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Could not create Virtual View on host database:\n{e}")

    def open_in_worksheet(self):
        sql = self.sql_editor.toPlainText().strip()
        if not sql or sql.startswith("--"):
            QMessageBox.warning(self, "Warning", "Please configure columns for the view query first.")
            return

        main_window = self.parent()
        if main_window and hasattr(main_window, "add_tab"):
            new_tab = main_window.add_tab()
            query_editor = getattr(new_tab, "editor", None) or new_tab.findChild(QTextEdit, "query_editor")
            if query_editor:
                query_editor.setPlainText(sql)
            self.accept()
        elif main_window and hasattr(main_window, "tab_widget"):
            new_tab = main_window.tab_widget.add_tab()
            query_editor = getattr(new_tab, "editor", None) or new_tab.findChild(QTextEdit, "query_editor")
            if query_editor:
                query_editor.setPlainText(sql)
            self.accept()
