import json
import os
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QFormLayout, QPushButton, QHBoxLayout, QVBoxLayout,
    QMessageBox, QLabel, QTabWidget, QWidget, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QRadioButton, QButtonGroup,
    QFileDialog
)
from ui.components import PasswordBox, SearchBox, SecondaryButton, ToastNotification
from workers.workers import WorkerThread
from db.db_connections import get_pooled_oracle_connection
from db.oracle_utils import (
    build_oracle_dsn,
    detect_oracle_client_version,
    find_oracle_client_dir,
    is_valid_oracle_client_dir,
    normalize_client_path,
    parse_oracle_dsn,
    scan_oracle_client_dirs,
)


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

        self.db_type_group = QButtonGroup(self)
        self.radio_service = QRadioButton("Service Name")
        self.radio_sid = QRadioButton("SID")
        self.radio_service.setChecked(True)
        self.db_type_group.addButton(self.radio_service, 0)
        self.db_type_group.addButton(self.radio_sid, 1)

        radio_layout = QHBoxLayout()
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(16)
        radio_layout.addWidget(self.radio_service)
        radio_layout.addWidget(self.radio_sid)
        radio_layout.addStretch()

        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("ORCL / Service Name")
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Normal", "SYSDBA", "SYSOPER", "SYSASM"])

        form.addRow("Role:", self.role_combo)

        # Driver Engine: Thin vs Thick
        self.driver_mode_group = QButtonGroup(self)
        self.radio_thin = QRadioButton("Thin Mode (Pure Python - No Client Needed)")
        self.radio_thick = QRadioButton("Thick Mode (Instant Client - Older DBs)")
        self.radio_thin.setChecked(True)
        self.driver_mode_group.addButton(self.radio_thin, 0)
        self.driver_mode_group.addButton(self.radio_thick, 1)

        driver_mode_layout = QHBoxLayout()
        driver_mode_layout.setContentsMargins(0, 0, 0, 0)
        driver_mode_layout.setSpacing(16)
        driver_mode_layout.addWidget(self.radio_thin)
        driver_mode_layout.addWidget(self.radio_thick)
        driver_mode_layout.addStretch()

        form.addRow("Driver Engine:", driver_mode_layout)

        # Oracle Client / Driver selector widget
        self.client_widget = QWidget()
        client_layout = QHBoxLayout(self.client_widget)
        client_layout.setContentsMargins(0, 0, 0, 0)
        client_layout.setSpacing(8)

        self.client_dir_combo = QComboBox()
        self.client_dir_combo.setToolTip("Select or scan Oracle Instant Client library. Bundled client supports Oracle 11.2+.")

        self.client_browse_btn = SecondaryButton("Browse...")
        self.client_browse_btn.setFixedWidth(80)
        self.client_browse_btn.clicked.connect(self._browse_custom_client_dir)

        self.client_scan_btn = SecondaryButton("Scan")
        self.client_scan_btn.setFixedWidth(80)
        self.client_scan_btn.clicked.connect(self._scan_for_clients)

        client_layout.addWidget(self.client_dir_combo)
        client_layout.addWidget(self.client_browse_btn)
        client_layout.addWidget(self.client_scan_btn)

        self.client_row_label = QLabel("Oracle Client:")
        form.addRow(self.client_row_label, self.client_widget)
        self._populate_client_dirs()

        self.radio_thin.toggled.connect(self._on_driver_mode_toggled)
        self.radio_thick.toggled.connect(self._on_driver_mode_toggled)
        self._on_driver_mode_toggled()

        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("Optional TNS Name / Easy Connect string")

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

            role = self.conn_data.get("role", "Normal") or "Normal"
            role_idx = self.role_combo.findText(role)
            if role_idx >= 0:
                self.role_combo.setCurrentIndex(role_idx)

            dsn_val = self.conn_data.get("dsn") or ""
            if dsn_val:
                parsed = parse_oracle_dsn(dsn_val)
                if parsed.get("db_type") == "sid":
                    self.radio_sid.setChecked(True)
                else:
                    self.radio_service.setChecked(True)

            driver_mode = str(self.conn_data.get("driver_mode", "")).lower()
            if driver_mode == "thick" or self.conn_data.get("oracle_client_dir"):
                self.radio_thick.setChecked(True)
            else:
                self.radio_thin.setChecked(True)

            saved_client = self.conn_data.get("oracle_client_dir")
            if saved_client:
                idx = self.client_dir_combo.findData(saved_client)
                if idx >= 0:
                    self.client_dir_combo.setCurrentIndex(idx)
                else:
                    ver = detect_oracle_client_version(saved_client)
                    self.client_dir_combo.addItem(f"[Custom] Instant Client {ver} - {saved_client}", saved_client)
                    self.client_dir_combo.setCurrentIndex(self.client_dir_combo.count() - 1)

            if self._preselected_tables:
                self.fetchRemoteTables(auto_check_preselected=True)

    def _on_driver_mode_toggled(self) -> None:
        is_thick = self.radio_thick.isChecked()
        self.client_widget.setVisible(is_thick)
        self.client_row_label.setVisible(is_thick)

    def _browse_custom_client_dir(self) -> None:
        current_path = self.client_dir_combo.currentData() or ""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Oracle Instant Client Directory", current_path
        )
        if not directory:
            return

        is_valid, missing = is_valid_oracle_client_dir(directory)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Incomplete Oracle Client",
                "The selected directory is missing required Oracle Instant Client files:\n\n"
                + "\n".join(f"• {m}" for m in missing)
                + "\n\nPlease select an extracted Oracle Instant Client directory containing all required libraries (oci.dll, oraociei/oraociicus DLL, and orannzsbb DLL).",
            )
            return

        norm_folder = normalize_client_path(directory)
        ver = detect_oracle_client_version(norm_folder)
        label = f"Oracle Instant Client {ver} - {norm_folder}"

        target_norm = os.path.normcase(norm_folder)
        existing_idx = -1
        for i in range(self.client_dir_combo.count()):
            item_data = self.client_dir_combo.itemData(i)
            if item_data and os.path.normcase(normalize_client_path(str(item_data))) == target_norm:
                existing_idx = i
                break

        if existing_idx >= 0:
            self.client_dir_combo.setCurrentIndex(existing_idx)
            ToastNotification.show_toast(self, "Client directory is already selected.", kind="info")
        else:
            if self.client_dir_combo.count() == 1 and not self.client_dir_combo.itemData(0):
                self.client_dir_combo.clear()
            self.client_dir_combo.insertItem(0, label, norm_folder)
            self.client_dir_combo.setItemData(0, norm_folder, Qt.ItemDataRole.ToolTipRole)
            self.client_dir_combo.setCurrentIndex(0)
            ToastNotification.show_toast(self, f"Selected Oracle Instant Client {ver}.", kind="success")

    def _scan_for_clients(self) -> None:
        self.client_scan_btn.start_loading("Scanning")
        current_data = self.client_dir_combo.currentData()

        import time

        def _do_scan():
            t0 = time.time()
            results = scan_oracle_client_dirs()
            elapsed = time.time() - t0
            if elapsed < 0.35:
                time.sleep(0.35 - elapsed)
            return results

        self._scan_worker = WorkerThread(_do_scan)
        self._scan_worker.finished_signal.connect(
            lambda res, err: self._on_scan_finished(res, err, current_data)
        )
        self._scan_worker.start()

    def _on_scan_finished(self, results, error, previous_selection) -> None:
        self.client_scan_btn.stop_loading()
        if error:
            ToastNotification.show_toast(self, f"Scan failed: {error}", kind="error")
            return

        detected = results or []
        self._apply_detected_clients(detected, previous_selection=previous_selection)
        count = len(detected)
        if count > 0:
            ToastNotification.show_toast(self, f"Found {count} Oracle Instant Client(s).", kind="success")
        else:
            ToastNotification.show_toast(
                self, "No Oracle Instant Client detected. Click Browse to select.", kind="warning"
            )

    def _apply_detected_clients(self, detected: list, previous_selection: str | None = None) -> None:
        self.client_dir_combo.clear()
        if not detected:
            self.client_dir_combo.addItem("(No Oracle Instant Client detected - Click Browse to select)", "")
            return

        seen_norm = set()
        for item in detected:
            raw_path = item.get("path") or ""
            path = normalize_client_path(raw_path)
            if not path:
                continue
            norm_k = os.path.normcase(path)
            if norm_k in seen_norm:
                continue
            seen_norm.add(norm_k)
            label = item.get("label") or f"Oracle Instant Client - {path}"
            self.client_dir_combo.addItem(label, path)
            self.client_dir_combo.setItemData(self.client_dir_combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)

        selected_idx = -1
        if previous_selection:
            prev_norm = os.path.normcase(normalize_client_path(previous_selection))
            for i in range(self.client_dir_combo.count()):
                data = self.client_dir_combo.itemData(i)
                if data and os.path.normcase(normalize_client_path(str(data))) == prev_norm:
                    selected_idx = i
                    break

        if selected_idx >= 0:
            self.client_dir_combo.setCurrentIndex(selected_idx)
        else:
            best = find_oracle_client_dir()
            if best:
                best_norm = os.path.normcase(normalize_client_path(best))
                for i in range(self.client_dir_combo.count()):
                    data = self.client_dir_combo.itemData(i)
                    if data and os.path.normcase(normalize_client_path(str(data))) == best_norm:
                        self.client_dir_combo.setCurrentIndex(i)
                        break
            if self.client_dir_combo.currentIndex() < 0 and self.client_dir_combo.count() > 0:
                self.client_dir_combo.setCurrentIndex(0)

    def _populate_client_dirs(self) -> None:
        """Scan and populate available Oracle Client directories."""
        detected = scan_oracle_client_dirs()
        self._apply_detected_clients(detected)

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
        host = self.host_input.text().strip() or "localhost"
        port = self.port_input.text().strip() or "1521"
        service_name = self.db_input.text().strip() or "ORCL"
        db_type = "service_name" if self.radio_service.isChecked() else "sid"
        return build_oracle_dsn(host, port, service_name, db_type=db_type)

    def testConnection(self):
        try:
            conn = get_pooled_oracle_connection(
                conn_data={
                    "user": self.user_input.text().strip(),
                    "password": self.password_input.text().strip(),
                    "dsn": self._get_dsn(),
                    "role": self.role_combo.currentText(),
                },
                use_pool=False
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
            conn = get_pooled_oracle_connection(
                conn_data={
                    "user": user,
                    "password": pwd,
                    "dsn": dsn,
                    "role": self.role_combo.currentText(),
                },
                use_pool=False
            )
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
            "role": self.role_combo.currentText(),
            "oracle_db_type": "service_name" if self.radio_service.isChecked() else "sid",
            "driver_mode": "thick" if self.radio_thick.isChecked() else "thin",
            "oracle_client_dir": (self.client_dir_combo.currentData() or None) if self.radio_thick.isChecked() else None,
            "dsn": dsn,
            "schema_name": f"{short_name}_schema",
            "remote_schema": user.upper() if user else "SYSTEM",
            "selected_tables": selected_tables
        }