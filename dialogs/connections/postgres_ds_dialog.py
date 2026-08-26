import json
import os
import psycopg2
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView
)
from ui.components import PasswordBox, SearchBox, SecondaryButton, PrimaryButton


class PostgresDataSourceDialog(QDialog):
    def __init__(self, parent=None, is_editing=False, conn_data=None):
        super().__init__(parent)

        self.conn_data = conn_data or {}
        is_editing = is_editing or bool(conn_data)
        self.is_editing = is_editing
        self._tables_fetched = False

        # Parse preselected tables if editing
        self._preselected_tables = None
        if self.conn_data:
            cfg = self.conn_data.get("config_json")
            if cfg and isinstance(cfg, str):
                try:
                    cfg_obj = json.loads(cfg)
                    self._preselected_tables = cfg_obj.get("selected_tables")
                except Exception:
                    pass
            elif self.conn_data.get("selected_tables"):
                self._preselected_tables = self.conn_data.get("selected_tables")

        self.setWindowTitle("Edit Data Source" if is_editing else "New Data Source")
        self.setMinimumSize(640, 620)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Header
        header_title = QLabel("Configure PostgreSQL Data Source" if not is_editing else "Edit PostgreSQL Data Source")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel("Configure connection details and selectively choose schemas/tables to import.")
        header_subtitle.setObjectName("dialogSubtitle")

        # Tabs
        self.tabs = QTabWidget()

        # ---------------- Tab 1: General Connection ----------------
        self.tab_general = QWidget()
        form = QFormLayout(self.tab_general)
        form.setContentsMargins(16, 16, 16, 16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)

        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("e.g. commerce, hr, sales")
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("5432")
        self.db_input = QLineEdit()
        self.user_input = QLineEdit()

        self.password_input = PasswordBox()

        form.addRow("Connection Name:", self.name_input)
        form.addRow("Data Source Short Name:", self.short_name_input)
        form.addRow("Host / IP Address:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Database Name:", self.db_input)
        form.addRow("Username:", self.user_input)
        form.addRow("Password:", self.password_input)

        self.tabs.addTab(self.tab_general, "General")

        # ---------------- Tab 2: Selective Table Import Tree ----------------
        self.tab_tables = QWidget()
        tables_layout = QVBoxLayout(self.tab_tables)
        tables_layout.setContentsMargins(16, 16, 16, 16)
        tables_layout.setSpacing(10)

        info_label = QLabel("Choose remote schemas and tables to import as foreign tables.")
        info_label.setObjectName("tabInfoLabel")
        tables_layout.addWidget(info_label)

        # Toolbar: Filter search box + Selection buttons + Fetch
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.search_box = SearchBox(placeholder="Filter schemas & tables...")
        self.search_box.textChanged.connect(self._filter_tables)
        toolbar_layout.addWidget(self.search_box, stretch=1)

        self.btn_select_all = SecondaryButton("Select All")
        self.btn_select_all.clicked.connect(self._select_all_tables)
        toolbar_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = SecondaryButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self._deselect_all_tables)
        toolbar_layout.addWidget(self.btn_deselect_all)

        self.fetch_btn = SecondaryButton("Fetch Schemas && Tables")
        self.fetch_btn.clicked.connect(lambda: self._fetch_remote_tables(show_popup=True))
        toolbar_layout.addWidget(self.fetch_btn)

        tables_layout.addLayout(toolbar_layout)

        # Tree Widget for Schema -> Tables
        self.table_tree = QTreeWidget()
        self.table_tree.setHeaderHidden(True)
        self.table_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_tree.itemChanged.connect(self._on_tree_item_changed)
        tables_layout.addWidget(self.table_tree, stretch=1)

        # Count summary footer
        self.table_count_label = QLabel("Switch to this tab or click 'Fetch Schemas & Tables' to view and select tables.")
        self.table_count_label.setObjectName("tabSummaryLabel")
        tables_layout.addWidget(self.table_count_label)

        self.tabs.addTab(self.tab_tables, "Import Tables")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Pre-fill if editing
        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name") or self.conn_data.get("display_name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name") or self.conn_data.get("source_name", ""))
            self.host_input.setText(str(self.conn_data.get("host", "")))
            self.port_input.setText(str(self.conn_data.get("port", "")))
            self.db_input.setText(self.conn_data.get("database") or self.conn_data.get("database_name", ""))
            self.user_input.setText(self.conn_data.get("user") or self.conn_data.get("username", ""))
            self.password_input.setText(self.conn_data.get("password", ""))

        # Bottom Buttons
        self.test_btn = SecondaryButton("Test Connection")
        self.test_btn.clicked.connect(self.testConnection)

        self.cancel_btn = SecondaryButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = PrimaryButton("Update" if is_editing else "Save")
        self.save_btn.clicked.connect(self.saveConnection)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)
        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addWidget(self.tabs, stretch=1)
        layout.addLayout(button_layout)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f6f8fb; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1f2937; }
            QLabel#dialogSubtitle { color: #6b7280; margin-bottom: 2px; }
            QLabel#tabInfoLabel { color: #4b5563; font-size: 9pt; }
            QLabel#tabSummaryLabel { color: #6b7280; font-size: 8.5pt; font-weight: 500; }
            QTabWidget::pane { border: 1px solid #d1d5db; border-radius: 6px; background-color: #ffffff; top: -1px; }
            QTabBar::tab {
                background: #f3f4f6; border: 1px solid #d1d5db; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 16px; margin-right: 2px; font-size: 9pt; color: #4b5563;
            }
            QTabBar::tab:selected { background: #ffffff; font-weight: 600; color: #0078d4; border-bottom: 1px solid #ffffff; }
            QTabBar::tab:hover:!selected { background: #e5e7eb; }
            QLineEdit { min-height: 28px; border: 1px solid #d1d5db; border-radius: 5px; background: white; padding: 2px 8px; color: #1f2937; }
            QLineEdit:focus { border: 1px solid #0078d4; }
            QTreeWidget { border: 1px solid #d1d5db; border-radius: 5px; background-color: #ffffff; padding: 4px; }
            QTreeWidget::item { padding: 4px 6px; border-radius: 4px; color: #1f2937; }
            QTreeWidget::item:hover { background-color: #f0f7ff; }
        """)

    def _on_tab_changed(self, index):
        if index == 1 and not self._tables_fetched:
            if self.host_input.text().strip() and self.db_input.text().strip():
                self._fetch_remote_tables(show_popup=False)

    def _get_connection_params(self):
        host = self.host_input.text().strip() or "localhost"
        port = int(self.port_input.text().strip() or 5432)
        database = self.db_input.text().strip() or "postgres"
        user = self.user_input.text().strip() or "postgres"
        password = self.password_input.text()
        schema = "public"

        _cloud_domains = ["aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"]
        is_cloud = any(d in host.lower() for d in _cloud_domains)
        extra = {"sslmode": "require"} if is_cloud else {}

        return host, port, database, user, password, schema, extra

    def testConnection(self):
        try:
            host, port, database, user, password, schema, extra = self._get_connection_params()
            conn = psycopg2.connect(
                host=host, port=port, database=database, user=user, password=password, connect_timeout=5, **extra
            )
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def _fetch_remote_tables(self, show_popup=True):
        try:
            host, port, database, user, password, default_schema, extra = self._get_connection_params()
            self.table_count_label.setText("Connecting and fetching remote schemas & tables...")
            self.table_count_label.repaint()

            conn = psycopg2.connect(
                host=host, port=port, database=database, user=user, password=password, connect_timeout=5, **extra
            )
            cur = conn.cursor()

            # Query non-system schemas
            cur.execute("""
                SELECT nspname FROM pg_namespace
                WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'
                ORDER BY nspname;
            """)
            schemas = [row[0] for row in cur.fetchall()]

            self.table_tree.blockSignals(True)
            self.table_tree.clear()

            schema_icon = qta.icon("fa5s.database", color="#0078d4")
            table_icon = qta.icon("fa5s.table", color="#10b981")

            # Match preselected items
            preselected_objs = self._preselected_tables or []
            preselected_set = set()
            for item in preselected_objs:
                if isinstance(item, dict):
                    preselected_set.add(f"{item.get('schema')}.{item.get('name')}")
                    preselected_set.add(item.get('name'))
                elif isinstance(item, str):
                    preselected_set.add(item)

            has_preselection = self._preselected_tables is not None

            for schema in schemas:
                schema_item = QTreeWidgetItem(self.table_tree)
                schema_item.setText(0, schema)
                schema_item.setIcon(0, schema_icon)
                schema_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "schema", "name": schema})
                schema_item.setFlags(schema_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
                schema_item.setCheckState(0, Qt.CheckState.Unchecked)

                cur.execute("""
                    SELECT tablename FROM pg_tables WHERE schemaname = %s
                    UNION
                    SELECT viewname FROM pg_views WHERE schemaname = %s
                    ORDER BY 1;
                """, (schema, schema))
                tables = [row[0] for row in cur.fetchall()]

                for table in tables:
                    table_item = QTreeWidgetItem(schema_item)
                    table_item.setText(0, table)
                    table_item.setIcon(0, table_icon)
                    table_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "table", "schema": schema, "name": table})
                    table_item.setFlags(table_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                    # Determine check state
                    full_key = f"{schema}.{table}"
                    if has_preselection:
                        is_checked = (full_key in preselected_set) or (table in preselected_set)
                    else:
                        is_checked = (schema == default_schema or default_schema == "public")

                    table_item.setCheckState(0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)

                schema_item.setExpanded(True)

            cur.close()
            conn.close()

            self.table_tree.blockSignals(False)
            self._tables_fetched = True
            self._update_count_label()

        except Exception as e:
            self.table_tree.blockSignals(False)
            err_msg = str(e)
            if "Connection refused" in err_msg:
                self.table_count_label.setText(f"Connection refused on {host}:{port}. Verify connection settings.")
            else:
                self.table_count_label.setText(f"Could not fetch tables: {err_msg[:80]}...")

            if show_popup:
                QMessageBox.warning(self, "Fetch Error", f"Could not fetch schemas & tables from remote database:\n{e}")

    def _on_tree_item_changed(self, item, column):
        self._update_count_label()

    def _filter_tables(self, text):
        query = text.strip().lower()
        root = self.table_tree.invisibleRootItem()
        for i in range(root.childCount()):
            schema_item = root.child(i)
            schema_match = query in schema_item.text(0).lower()
            child_match = False
            for j in range(schema_item.childCount()):
                child = schema_item.child(j)
                matches = query in child.text(0).lower() or schema_match
                child.setHidden(not matches)
                if matches:
                    child_match = True
            schema_item.setHidden(not (schema_match or child_match))

    def _select_all_tables(self):
        self.table_tree.blockSignals(True)
        root = self.table_tree.invisibleRootItem()
        for i in range(root.childCount()):
            schema_item = root.child(i)
            if not schema_item.isHidden():
                schema_item.setCheckState(0, Qt.CheckState.Checked)
                for j in range(schema_item.childCount()):
                    schema_item.child(j).setCheckState(0, Qt.CheckState.Checked)
        self.table_tree.blockSignals(False)
        self._update_count_label()

    def _deselect_all_tables(self):
        self.table_tree.blockSignals(True)
        root = self.table_tree.invisibleRootItem()
        for i in range(root.childCount()):
            schema_item = root.child(i)
            if not schema_item.isHidden():
                schema_item.setCheckState(0, Qt.CheckState.Unchecked)
                for j in range(schema_item.childCount()):
                    schema_item.child(j).setCheckState(0, Qt.CheckState.Unchecked)
        self.table_tree.blockSignals(False)
        self._update_count_label()

    def _update_count_label(self):
        root = self.table_tree.invisibleRootItem()
        total_tables = 0
        checked_tables = 0

        for i in range(root.childCount()):
            schema_item = root.child(i)
            for j in range(schema_item.childCount()):
                total_tables += 1
                if schema_item.child(j).checkState(0) == Qt.CheckState.Checked:
                    checked_tables += 1

        if total_tables == 0:
            if self._tables_fetched:
                self.table_count_label.setText("No tables found in remote database.")
            return

        if checked_tables == total_tables:
            self.table_count_label.setText(f"{total_tables} tables available across schemas | All {total_tables} selected for import")
        else:
            self.table_count_label.setText(f"{checked_tables} of {total_tables} tables selected for import")

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Data Source Name is required.")
            return

        if not self.short_name_input.text().strip():
            self.short_name_input.setText(self.name_input.text().strip())

        self.accept()

    def getData(self):
        selected_tables = []
        if self._tables_fetched:
            root = self.table_tree.invisibleRootItem()
            for i in range(root.childCount()):
                schema_item = root.child(i)
                for j in range(schema_item.childCount()):
                    table_item = schema_item.child(j)
                    if table_item.checkState(0) == Qt.CheckState.Checked:
                        data = table_item.data(0, Qt.ItemDataRole.UserRole)
                        if data and isinstance(data, dict):
                            selected_tables.append({
                                "schema": data.get("schema"),
                                "name": data.get("name")
                            })
        elif self._preselected_tables is not None:
            selected_tables = self._preselected_tables

        config_data = {}
        if selected_tables is not None:
            config_data["selected_tables"] = selected_tables

        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "host": self.host_input.text().strip() or "localhost",
            "port": int(self.port_input.text().strip() or 5432),
            "database": self.db_input.text().strip(),
            "database_name": self.db_input.text().strip(),
            "schema": "public",
            "schema_name": "public",
            "user": self.user_input.text().strip() or "postgres",
            "username": self.user_input.text().strip() or "postgres",
            "password": self.password_input.text(),
            "selected_tables": selected_tables,
            "config_json": json.dumps(config_data) if config_data else None
        }