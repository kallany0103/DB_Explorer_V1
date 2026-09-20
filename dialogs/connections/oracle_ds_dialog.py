import json
import os
import oracledb
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView
)
from ui.components import PasswordBox, SearchBox, SecondaryButton, PrimaryButton


class OracleDataSourceDialog(QDialog):
    """
    Dialog for creating and editing Oracle Data Sources in Unified Data Source (UDS).
    Supports Tab 1 (General Connection) and Tab 2 (Selective Table Import Tree).
    """

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

        self.setWindowTitle("Edit Oracle Data Source" if is_editing else "New Oracle Data Source")
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
        header_title = QLabel("Configure Oracle Data Source" if not is_editing else "Edit Oracle Data Source")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel("Configure Oracle connection details and choose tables to import into Unified Data Source.")
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
        self.short_name_input.setPlaceholderText("e.g. oracle_hr, finance")
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("1521")
        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("ORCL / Service Name")
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("Optional TNS Name / Easy Connect string")

        form.addRow("Connection Name:", self.name_input)
        form.addRow("Data Source Short Name:", self.short_name_input)
        form.addRow("Host / IP Address:", self.host_input)
        form.addRow("Port:", self.port_input)
        form.addRow("Database / Service Name:", self.db_input)
        form.addRow("Username:", self.user_input)
        form.addRow("Password:", self.password_input)
        form.addRow("DSN (Optional):", self.dsn_input)

        self.tabs.addTab(self.tab_general, "General")

        # ---------------- Tab 2: Selective Table Import Tree ----------------
        self.tab_tables = QWidget()
        tables_layout = QVBoxLayout(self.tab_tables)
        tables_layout.setContentsMargins(16, 16, 16, 16)
        tables_layout.setSpacing(10)

        info_label = QLabel("Choose remote Oracle tables to import as foreign tables into Unified Data Source.")
        info_label.setObjectName("tabInfoLabel")
        tables_layout.addWidget(info_label)

        # Toolbar: Filter search box + Selection buttons + Fetch
        toolbar_layout = QHBoxLayout()
        self.search_box = SearchBox()
        self.search_box.setPlaceholderText("Filter tables...")
        self.search_box.textChanged.connect(self._filter_table_tree)

        self.check_all_btn = QPushButton("Check All")
        self.check_all_btn.setObjectName("secondaryButton")
        self.check_all_btn.clicked.connect(lambda: self._set_all_checked(True))

        self.uncheck_all_btn = QPushButton("Uncheck All")
        self.uncheck_all_btn.setObjectName("secondaryButton")
        self.uncheck_all_btn.clicked.connect(lambda: self._set_all_checked(False))

        self.fetch_tables_btn = QPushButton("Fetch Tables")
        self.fetch_tables_btn.setObjectName("primaryButton")
        self.fetch_tables_btn.setIcon(qta.icon("fa5s.sync", color="white"))
        self.fetch_tables_btn.clicked.connect(self.fetchRemoteTables)

        toolbar_layout.addWidget(self.search_box)
        toolbar_layout.addWidget(self.check_all_btn)
        toolbar_layout.addWidget(self.uncheck_all_btn)
        toolbar_layout.addWidget(self.fetch_tables_btn)
        tables_layout.addLayout(toolbar_layout)

        # Table Tree Widget
        self.table_tree = QTreeWidget()
        self.table_tree.setHeaderLabels(["Schema / Table", "Type"])
        self.table_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_tree.itemChanged.connect(self._on_tree_item_changed)
        tables_layout.addWidget(self.table_tree)

        self.tabs.addTab(self.tab_tables, "Import Tables (0)")

        # ---------------- Bottom Action Buttons ----------------
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self.testConnection)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.saveConnection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.test_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        # Main Layout Assembly
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)

        # Populate pre-existing data if editing
        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name") or self.conn_data.get("display_name") or "")
            self.short_name_input.setText(self.conn_data.get("short_name") or self.conn_data.get("source_name") or "")
            self.host_input.setText(self.conn_data.get("host") or "")
            self.port_input.setText(str(self.conn_data.get("port") or "1521"))
            self.db_input.setText(self.conn_data.get("database") or self.conn_data.get("database_name") or "")
            self.user_input.setText(self.conn_data.get("user") or self.conn_data.get("username") or "")
            self.password_input.setText(self.conn_data.get("password") or "")
            self.dsn_input.setText(self.conn_data.get("dsn") or "")

            if self._preselected_tables:
                self.fetchRemoteTables(auto_check_preselected=True)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; }
            QLabel#dialogTitle { font-size: 16px; font-weight: 600; color: #1e293b; }
            QLabel#dialogSubtitle { color: #64748b; font-size: 12px; margin-bottom: 4px; }
            QLabel#tabInfoLabel { color: #475569; font-size: 12px; font-weight: 500; }
            QLineEdit { min-height: 30px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px 8px; background: white; }
            QLineEdit:focus { border: 1px solid #0284c7; }
            QPushButton { min-height: 32px; padding: 4px 14px; border-radius: 6px; background-color: #f1f5f9; border: 1px solid #cbd5e1; font-weight: 500; }
            QPushButton#primaryButton { background-color: #0284c7; color: white; border: none; font-weight: 600; }
            QPushButton#primaryButton:hover { background-color: #0369a1; }
            QTabWidget::pane { border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
            QTabBar::tab { background: #f1f5f9; color: #475569; padding: 8px 16px; font-weight: 500; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: white; color: #0284c7; font-weight: 600; border-bottom: 2px solid #0284c7; }
            QTreeWidget { border: none; background: white; gridline-color: #f1f5f9; }
        """)

    def _get_dsn(self):
        dsn = self.dsn_input.text().strip()
        if dsn:
            return dsn
        host = self.host_input.text().strip()
        port = self.port_input.text().strip() or "1521"
        service_name = self.db_input.text().strip() or "ORCL"
        return f"//{host}:{port}/{service_name}"

    def testConnection(self):
        try:
            conn = oracledb.connect(
                user=self.user_input.text().strip(),
                password=self.password_input.text().strip(),
                dsn=self._get_dsn()
            )
            conn.close()
            QMessageBox.information(self, "Success", "Oracle connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", f"Failed to connect to Oracle:\n{e}")

    def fetchRemoteTables(self, auto_check_preselected=False):
        user = self.user_input.text().strip()
        pwd = self.password_input.text().strip()
        dsn = self._get_dsn()

        if not user or not dsn:
            QMessageBox.warning(self, "Validation", "Please specify User and Host/DSN on the General tab first.")
            return

        self.table_tree.blockSignals(True)
        self.table_tree.clear()

        try:
            conn = oracledb.connect(user=user, password=pwd, dsn=dsn)
            cur = conn.cursor()
            cur.execute("SELECT table_name FROM user_tables ORDER BY table_name")
            tables = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()

            schema_item = QTreeWidgetItem(self.table_tree)
            schema_item.setText(0, user.upper())
            schema_item.setText(1, "Schema Owner")
            schema_item.setFlags(schema_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            schema_item.setCheckState(0, Qt.CheckState.Unchecked)

            preselected_set = set(self._preselected_tables) if self._preselected_tables is not None else None

            for tbl in tables:
                child = QTreeWidgetItem(schema_item)
                child.setText(0, tbl)
                child.setText(1, "Table")
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                if auto_check_preselected and preselected_set is not None:
                    if tbl in preselected_set:
                        child.setCheckState(0, Qt.CheckState.Checked)
                    else:
                        child.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    child.setCheckState(0, Qt.CheckState.Unchecked)

            schema_item.setExpanded(True)
            self._tables_fetched = True
            self._update_tab_title()
        except Exception as e:
            QMessageBox.critical(self, "Fetch Failed", f"Failed to fetch Oracle tables:\n{e}")
        finally:
            self.table_tree.blockSignals(False)

    def _set_all_checked(self, checked: bool):
        self.table_tree.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for idx in range(self.table_tree.topLevelItemCount()):
            root = self.table_tree.topLevelItem(idx)
            root.setCheckState(0, state)
            for c_idx in range(root.childCount()):
                root.child(c_idx).setCheckState(0, state)
        self.table_tree.blockSignals(False)
        self._update_tab_title()

    def _filter_table_tree(self, text: str):
        query = text.strip().lower()
        for i in range(self.table_tree.topLevelItemCount()):
            root = self.table_tree.topLevelItem(i)
            root_match = query in root.text(0).lower()
            any_child_match = False
            for j in range(root.childCount()):
                child = root.child(j)
                match = query in child.text(0).lower()
                child.setHidden(not (match or root_match))
                if match:
                    any_child_match = True
            root.setHidden(not (root_match or any_child_match))

    def _on_tree_item_changed(self, item, column):
        self._update_tab_title()

    def _get_selected_tables(self):
        if not self._tables_fetched and self._preselected_tables is not None:
            return self._preselected_tables

        if not self._tables_fetched:
            return []

        selected = []
        for i in range(self.table_tree.topLevelItemCount()):
            root = self.table_tree.topLevelItem(i)
            for j in range(root.childCount()):
                child = root.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    selected.append(child.text(0))
        return selected

    def _update_tab_title(self):
        sel_count = len(self._get_selected_tables())
        self.tabs.setTabText(1, f"Import Tables ({sel_count})")

    def saveConnection(self):
        name = self.name_input.text().strip()
        short_name = self.short_name_input.text().strip() or name.lower().replace(" ", "_")

        if not name:
            QMessageBox.warning(self, "Validation", "Please specify a Connection Name.")
            return

        self.accept()

    def getData(self):
        name = self.name_input.text().strip()
        short_name = self.short_name_input.text().strip() or name.lower().replace(" ", "_")
        host = self.host_input.text().strip() or "localhost"
        port = int(self.port_input.text().strip() or "1521")
        database = self.db_input.text().strip() or "ORCL"
        user = self.user_input.text().strip()
        password = self.password_input.text().strip()
        dsn = self._get_dsn()

        selected_tables = self._get_selected_tables()

        return {
            "name": name,
            "short_name": short_name,
            "source_name": short_name,
            "display_name": name,
            "source_type": "ORACLE",
            "host": host,
            "port": port,
            "database": database,
            "database_name": database,
            "user": user,
            "username": user,
            "password": password,
            "dsn": dsn,
            "schema_name": f"{short_name}_schema",
            "remote_schema": user.upper() if user else "SYSTEM",
            "selected_tables": selected_tables
        }