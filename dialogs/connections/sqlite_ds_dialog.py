# dialogs/connections/sqlite_ds_dialog.py

import json
import os
import sqlite3 as sqlite
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QLabel, QWidget, QTabWidget, QListWidget,
    QListWidgetItem, QAbstractItemView
)
from ui.components import SearchBox, SecondaryButton, PrimaryButton


class SQLiteDataSourceDialog(QDialog):
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
            "Edit SQLite Data Source" if is_editing else "New SQLite Data Source"
        )
        self.setMinimumSize(600, 560)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Header
        header_title = QLabel("Configure SQLite Data Source" if not is_editing else "Edit SQLite Data Source")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel("Configure SQLite database file path and choose tables to import.")
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
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("e.g. C:/data/app.db")

        self.browse_btn = SecondaryButton("Browse")
        self.browse_btn.setFixedWidth(85)
        self.browse_btn.clicked.connect(self.browse_file)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        form.addRow("Data Source Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Database Path:", path_layout)

        self.tabs.addTab(self.tab_general, "General")

        # ---------------- Tab 2: Selective Table Import ----------------
        self.tab_tables = QWidget()
        tables_layout = QVBoxLayout(self.tab_tables)
        tables_layout.setContentsMargins(16, 16, 16, 16)
        tables_layout.setSpacing(10)

        tables_info = QLabel("Choose SQLite tables to import as foreign tables. (Leave all checked to import all tables)")
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
        self.fetch_btn.clicked.connect(lambda: self._fetch_tables(show_popup=True))
        toolbar_layout.addWidget(self.fetch_btn)

        tables_layout.addLayout(toolbar_layout)

        # List Widget
        self.table_list = QListWidget()
        self.table_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_list.itemChanged.connect(self._update_count_label)
        tables_layout.addWidget(self.table_list, stretch=1)

        # Count summary footer
        self.table_count_label = QLabel("Switch to this tab or click 'Fetch Tables' to view and select SQLite tables.")
        self.table_count_label.setObjectName("tabSummaryLabel")
        tables_layout.addWidget(self.table_count_label)

        self.tabs.addTab(self.tab_tables, "Import Tables")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Pre-fill if editing
        if self.conn_data:
            self.name_input.setText(self.conn_data.get("name") or self.conn_data.get("display_name", ""))
            self.short_name_input.setText(self.conn_data.get("short_name") or self.conn_data.get("source_name", ""))
            self.path_input.setText(self.conn_data.get("db_path") or self.conn_data.get("file_path", ""))

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

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            "",
            "SQLite Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)
            self._tables_fetched = False
            # Automatically set name if empty
            if not self.name_input.text().strip():
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                self.name_input.setText(base_name.title())
                self.short_name_input.setText(base_name.lower())

    def _on_tab_changed(self, index):
        if index == 1 and not self._tables_fetched:
            if self.path_input.text().strip():
                self._fetch_tables(show_popup=False)

    def testConnection(self):
        path = self.path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Test Connection", "Please provide a database path.")
            return

        if not os.path.exists(path):
            QMessageBox.critical(self, "Error", f"SQLite database file not found at:\n{path}")
            return

        try:
            conn = sqlite.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            count = cur.fetchone()[0]
            conn.close()
            QMessageBox.information(self, "Success", f"Connection successful!\nFound {count} table(s) in SQLite database.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{e}")

    def _fetch_tables(self, show_popup=True):
        path = self.path_input.text().strip()
        if not path:
            self.table_count_label.setText("Please specify a database path in the General tab first.")
            if show_popup:
                QMessageBox.warning(self, "Fetch Tables", "Please enter a database path first.")
            return

        if not os.path.exists(path):
            self.table_count_label.setText(f"File not found: {path}")
            if show_popup:
                QMessageBox.critical(self, "File Not Found", f"Database file does not exist:\n{path}")
            return

        try:
            self.table_count_label.setText("Reading tables from SQLite database...")
            self.table_count_label.repaint()

            conn = sqlite.connect(path)
            cur = conn.cursor()
            cur.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """)
            rows = cur.fetchall()
            conn.close()

            self.table_list.clear()
            table_icon = qta.icon("fa5s.table", color="#0078d4")
            preselected_set = set(self._preselected_tables) if self._preselected_tables is not None else None

            for (tbl_name,) in rows:
                item = QListWidgetItem(tbl_name)
                item.setIcon(table_icon)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                if preselected_set is not None:
                    is_checked = tbl_name in preselected_set
                else:
                    is_checked = True

                item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                self.table_list.addItem(item)

            self._tables_fetched = True
            self._update_count_label()

        except Exception as e:
            self.table_count_label.setText(f"Could not read tables: {e}")
            if show_popup:
                QMessageBox.warning(self, "Error", f"Failed to read SQLite tables:\n{e}")

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
                self.table_count_label.setText("No user tables found in SQLite database.")
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

        if not self.path_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "Database path is required.")
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
            if len(checked_tables) < total:
                selected_tables = checked_tables
        elif self._preselected_tables is not None:
            selected_tables = self._preselected_tables

        config_data = {}
        if selected_tables is not None:
            config_data["selected_tables"] = selected_tables

        path = self.path_input.text().strip()

        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "db_path": path,
            "file_path": path,
            "source_type": "SQLITE",
            "selected_tables": selected_tables,
            "config_json": json.dumps(config_data) if config_data else None,
            "id": self.conn_data.get("id") if self.conn_data else None
        }