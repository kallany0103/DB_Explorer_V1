import json
import os
import psycopg2
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QTabWidget, QWidget, QListWidget, QListWidgetItem,
    QAbstractItemView
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

        self.setWindowTitle(
            "Edit Data Source" if is_editing else "New Data Source"
        )
        self.setMinimumSize(600, 600)

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

        header_subtitle = QLabel("Configure connection details and selectively choose tables to import.")
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
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("5432")
        self.db_input = QLineEdit()
        self.user_input = QLineEdit()
        self.schema_input = QLineEdit()
        self.schema_input.setPlaceholderText("public")

        self.password_input = PasswordBox()

        form.addRow("Data Source Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Database:", self.db_input)
        form.addRow("Remote Schema:", self.schema_input)
        form.addRow("User:", self.user_input)
        form.addRow("Password:", self.password_input)

        self.tabs.addTab(self.tab_general, "General")

        # ---------------- Tab 2: Selective Table Import ----------------
        self.tab_tables = QWidget()
        tables_layout = QVBoxLayout(self.tab_tables)
        tables_layout.setContentsMargins(16, 16, 16, 16)
        tables_layout.setSpacing(10)

        tables_info = QLabel("Choose remote tables to import as foreign tables. (Leave all checked to import all tables)")
        tables_info.setObjectName("tabInfoLabel")
        tables_layout.addWidget(tables_info)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.search_input = SearchBox(placeholder="Filter tables...")
        self.search_input.textChanged.connect(self._filter_tables)
        toolbar_layout.addWidget(self.search_input, stretch=1)

        self.select_all_btn = SecondaryButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_tables)
        toolbar_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = SecondaryButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all_tables)
        toolbar_layout.addWidget(self.deselect_all_btn)

        self.fetch_btn = SecondaryButton("Fetch Tables", qta.icon("fa5s.sync-alt", color="#374151"))
        self.fetch_btn.clicked.connect(lambda: self._fetch_remote_tables(show_popup=True))
        toolbar_layout.addWidget(self.fetch_btn)

        tables_layout.addLayout(toolbar_layout)

        # List Widget
        self.table_list = QListWidget()
        self.table_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_list.itemChanged.connect(self._update_count_label)
        tables_layout.addWidget(self.table_list, stretch=1)

        # Count summary footer
        self.table_count_label = QLabel("Switch to this tab or click 'Fetch Tables' to view and select remote tables.")
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
            self.schema_input.setText(self.conn_data.get("schema") or self.conn_data.get("schema_name", "public"))
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

            QLabel#dialogTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
            }

            QLabel#dialogSubtitle {
                color: #6b7280;
                margin-bottom: 2px;
            }

            QLabel#tabInfoLabel {
                color: #4b5563;
                font-size: 9pt;
            }

            QLabel#tabSummaryLabel {
                color: #6b7280;
                font-size: 8.5pt;
                padding-top: 4px;
            }

            QTabWidget::pane {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: #ffffff;
                top: -1px;
            }

            QTabBar::tab {
                background: #f3f4f6;
                border: 1px solid #d1d5db;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 16px;
                margin-right: 2px;
                font-size: 9pt;
                color: #4b5563;
            }

            QTabBar::tab:selected {
                background: #ffffff;
                font-weight: 600;
                color: #0078d4;
                border-bottom: 1px solid #ffffff;
            }

            QTabBar::tab:hover:!selected {
                background: #e5e7eb;
            }

            QLineEdit {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 5px;
                background: white;
                padding: 2px 8px;
                color: #1f2937;
            }

            QLineEdit:focus {
                border: 1px solid #0078d4;
            }

            QListWidget {
                border: 1px solid #d1d5db;
                border-radius: 5px;
                background-color: #ffffff;
                padding: 4px;
            }

            QListWidget::item {
                padding: 4px 6px;
                border-radius: 4px;
                color: #1f2937;
            }

            QListWidget::item:hover {
                background-color: #f0f7ff;
            }
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
        schema = self.schema_input.text().strip() or "public"

        _cloud_domains = ["aivencloud.com", "elephantsql.com", "amazonaws.com", "heroku.com", "cloud.google.com"]
        is_cloud = any(d in host.lower() for d in _cloud_domains)
        extra = {"sslmode": "require"} if is_cloud else {}

        return host, port, database, user, password, schema, extra

    def testConnection(self):
        try:
            host, port, database, user, password, schema, extra = self._get_connection_params()
            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
                **extra
            )
            conn.close()
            QMessageBox.information(self, "Success", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def _fetch_remote_tables(self, show_popup=True):
        try:
            host, port, database, user, password, schema, extra = self._get_connection_params()
            self.table_count_label.setText("Connecting and fetching remote tables...")
            self.table_count_label.repaint()

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
                **extra
            )
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type IN ('BASE TABLE', 'VIEW', 'FOREIGN')
                ORDER BY table_name;
            """, (schema,))

            rows = cur.fetchall()
            cur.close()
            conn.close()

            self.table_list.clear()
            table_icon = qta.icon("fa5s.table", color="#0078d4")

            preselected_set = set(self._preselected_tables) if self._preselected_tables is not None else None

            for (tbl_name,) in rows:
                item = QListWidgetItem(tbl_name)
                item.setIcon(table_icon)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                # If preselected list exists, match against it. Otherwise check all.
                if preselected_set is not None:
                    is_checked = tbl_name in preselected_set
                else:
                    is_checked = True

                item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                self.table_list.addItem(item)

            self._tables_fetched = True
            self._update_count_label()

        except Exception as e:
            err_msg = str(e)
            if "Connection refused" in err_msg:
                self.table_count_label.setText(f"Connection refused on {host}:{port}. Verify connection settings.")
            else:
                self.table_count_label.setText(f"Could not fetch tables: {err_msg[:80]}...")

            if show_popup:
                QMessageBox.warning(self, "Fetch Error", f"Could not fetch tables from remote database:\n{e}")

    def _filter_tables(self, text):
        query = text.strip().lower()
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            item.setHidden(query not in item.text().lower())

    def _select_all_tables(self):
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)
        self._update_count_label()

    def _deselect_all_tables(self):
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_count_label()

    def _update_count_label(self):
        total = self.table_list.count()
        if total == 0:
            if self._tables_fetched:
                self.table_count_label.setText("No tables found in remote schema.")
            return

        checked = sum(1 for i in range(total) if self.table_list.item(i).checkState() == Qt.CheckState.Checked)
        if checked == total:
            self.table_count_label.setText(f"{total} tables available | All {total} selected (Full schema will be imported)")
        else:
            self.table_count_label.setText(f"{checked} of {total} tables selected for import")

    def saveConnection(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Data Source Name is required.")
            return

        if not self.short_name_input.text().strip():
            self.short_name_input.setText(self.name_input.text().strip())

        self.accept()

    def getData(self):
        total = self.table_list.count()
        selected_tables = None

        if self._tables_fetched and total > 0:
            checked_tables = [
                self.table_list.item(i).text()
                for i in range(total)
                if self.table_list.item(i).checkState() == Qt.CheckState.Checked
            ]
            # If all tables are checked, selected_tables remains None (import full schema)
            if len(checked_tables) < total:
                selected_tables = checked_tables
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
            "schema": self.schema_input.text().strip() or "public",
            "schema_name": self.schema_input.text().strip() or "public",
            "user": self.user_input.text().strip() or "postgres",
            "username": self.user_input.text().strip() or "postgres",
            "password": self.password_input.text(),
            "selected_tables": selected_tables,
            "config_json": json.dumps(config_data) if config_data else None
        }