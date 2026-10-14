# dialogs/connections/oracle_dialog.py
"""Oracle database connection dialog supporting Basic, TNS, and Custom DSN modes."""

from __future__ import annotations

import logging
import os
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSizePolicy,
    QWidget,
)

from db.oracle_utils import (
    build_oracle_dsn,
    detect_oracle_client_version,
    find_default_tns_admin_dir,
    find_oracle_client_dir,
    get_tns_names,
    is_valid_oracle_client_dir,
    normalize_client_path,
    parse_oracle_dsn,
    scan_oracle_client_dirs,
)
from ui.components import PasswordBox, SecondaryButton, ToastNotification
from workers.workers import WorkerThread
from .base_connection_dialog import BaseConnectionDialog

logger = logging.getLogger(__name__)


class OracleConnectionDialog(BaseConnectionDialog):
    """Industry-standard Oracle connection dialog supporting Basic, TNS, and Custom DSN."""

    def __init__(
        self,
        parent=None,
        is_editing: bool = False,
        type_id: int | None = None,
        group_id: int | None = None,
    ) -> None:
        super().__init__(
            parent=parent,
            is_editing=is_editing,
            type_id=type_id,
            group_id=group_id,
            title="Oracle",
            subtitle="Configure Oracle connection using Basic (Service/SID), TNS, or Custom DSN.",
            min_size=(560, 420),
        )

    def setup_inputs(self) -> None:
        # 1. Connection metadata
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Oracle Production, Dev PDB")
        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText("e.g. orcl_prod, finance_db")

        self.form.addRow("Connection Name:", self.name_input)
        self.form.addRow("Short Name:", self.short_name_input)

        # 2. Connection Type Mode Selector
        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems(["Basic", "TNS", "Custom / Connection String"])
        self.conn_type_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.form.addRow("Connection Type:", self.conn_type_combo)

        # --- Mode 0: Basic Fields ---
        self.host_input = QLineEdit()
        self.host_input.setText("localhost")
        self.port_input = QLineEdit()
        self.port_input.setText("1521")

        # Database Type: Service Name vs SID radio group
        self.db_type_group = QButtonGroup(self)
        self.radio_service = QRadioButton("Service Name")
        self.radio_sid = QRadioButton("SID")
        self.radio_service.setChecked(True)
        self.db_type_group.addButton(self.radio_service, 0)
        self.db_type_group.addButton(self.radio_sid, 1)

        self.db_type_widget = QWidget()
        radio_layout = QHBoxLayout(self.db_type_widget)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(16)
        radio_layout.addWidget(self.radio_service)
        radio_layout.addWidget(self.radio_sid)
        radio_layout.addStretch()

        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("e.g. ORCL, XEPDB1, FREEPDB1")
        self.db_label = QLabel("Service Name:")

        self.radio_service.toggled.connect(self._on_db_type_toggled)

        self.form.addRow("Host / IP Address:", self.host_input)
        self.form.addRow("Port:", self.port_input)
        self.form.addRow("Database Type:", self.db_type_widget)
        self.form.addRow(self.db_label, self.db_input)

        # --- Mode 1: TNS Fields ---
        self.tns_admin_input = QLineEdit()
        default_tns_dir = find_default_tns_admin_dir() or ""
        self.tns_admin_input.setText(default_tns_dir)
        self.tns_admin_input.setPlaceholderText("Path to directory containing tnsnames.ora")

        self.tns_browse_btn = SecondaryButton("Browse...")
        self.tns_browse_btn.setFixedWidth(80)
        self.tns_browse_btn.clicked.connect(self._browse_tns_admin)

        self.tns_dir_widget = QWidget()
        tns_dir_layout = QHBoxLayout(self.tns_dir_widget)
        tns_dir_layout.setContentsMargins(0, 0, 0, 0)
        tns_dir_layout.setSpacing(8)
        tns_dir_layout.addWidget(self.tns_admin_input, stretch=1)
        tns_dir_layout.addWidget(self.tns_browse_btn)

        self.tns_alias_combo = QComboBox()
        self.tns_alias_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tns_alias_combo.setMinimumContentsLength(15)
        self.tns_alias_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tns_alias_combo.setEditable(True)
        self.tns_alias_combo.setPlaceholderText("Select or enter TNS network alias")

        self.tns_refresh_btn = SecondaryButton("Refresh")
        self.tns_refresh_btn.setFixedWidth(80)
        self.tns_refresh_btn.clicked.connect(self._populate_tns_aliases)

        self.tns_alias_widget = QWidget()
        tns_alias_layout = QHBoxLayout(self.tns_alias_widget)
        tns_alias_layout.setContentsMargins(0, 0, 0, 0)
        tns_alias_layout.setSpacing(8)
        tns_alias_layout.addWidget(self.tns_alias_combo, stretch=1)
        tns_alias_layout.addWidget(self.tns_refresh_btn)

        self._populate_tns_aliases()

        self.tns_dir_label = QLabel("TNS Folder:")
        self.tns_alias_label = QLabel("Network Alias:")
        self.form.addRow(self.tns_dir_label, self.tns_dir_widget)
        self.form.addRow(self.tns_alias_label, self.tns_alias_widget)

        # --- Mode 2: Custom / Connection String Fields ---
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. host:port/service_name or (DESCRIPTION=...)")
        self.dsn_label = QLabel("Connection String:")
        self.form.addRow(self.dsn_label, self.dsn_input)

        # Track rows by mode for visibility toggling
        self.basic_rows = [self.host_input, self.port_input, self.db_type_widget, self.db_input]
        self.tns_rows = [self.tns_dir_widget, self.tns_alias_widget]
        self.custom_rows = [self.dsn_input]

        # 4. Shared Credentials and Role
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Database username (e.g. SYSTEM)")
        self.password_input = PasswordBox()

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Normal", "SYSDBA", "SYSOPER", "SYSASM"])

        self.form.addRow("Username:", self.user_input)
        self.form.addRow("Password:", self.password_input)
        self.form.addRow("Role:", self.role_combo)

        # 5. Driver Engine (Thin Mode vs Thick Mode)
        self.driver_mode_group = QButtonGroup(self)
        self.radio_thin = QRadioButton("Thin Mode (Pure Python)")
        self.radio_thick = QRadioButton("Thick Mode (Instant Client)")
        self.radio_thin.setToolTip("Thin Mode: Pure Python - No Oracle Instant Client required.")
        self.radio_thick.setToolTip("Thick Mode: Uses Oracle Instant Client - Required for legacy Oracle 10g/11g.")
        self.radio_thin.setChecked(True)
        self.driver_mode_group.addButton(self.radio_thin, 0)
        self.driver_mode_group.addButton(self.radio_thick, 1)

        driver_mode_widget = QWidget()
        driver_mode_layout = QHBoxLayout(driver_mode_widget)
        driver_mode_layout.setContentsMargins(0, 0, 0, 0)
        driver_mode_layout.setSpacing(16)
        driver_mode_layout.addWidget(self.radio_thin)
        driver_mode_layout.addWidget(self.radio_thick)
        driver_mode_layout.addStretch()

        self.form.addRow("Driver Engine:", driver_mode_widget)

        # 6. Oracle Driver / Client selector (only shown when Thick mode is chosen)
        self.client_widget = QWidget()
        client_layout = QHBoxLayout(self.client_widget)
        client_layout.setContentsMargins(0, 0, 0, 0)
        client_layout.setSpacing(8)

        self.client_dir_combo = QComboBox()
        self.client_dir_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.client_dir_combo.setMinimumContentsLength(15)
        self.client_dir_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.client_dir_combo.view().setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.client_dir_combo.setToolTip("Select or scan Oracle Instant Client library.")

        self.client_browse_btn = SecondaryButton("Browse...")
        self.client_browse_btn.setFixedWidth(80)
        self.client_browse_btn.clicked.connect(self._browse_custom_client_dir)

        self.client_scan_btn = SecondaryButton("Scan")
        self.client_scan_btn.setFixedWidth(80)
        self.client_scan_btn.clicked.connect(self._scan_for_clients)

        client_layout.addWidget(self.client_dir_combo, stretch=1)
        client_layout.addWidget(self.client_browse_btn)
        client_layout.addWidget(self.client_scan_btn)

        self.client_row_label = QLabel("Oracle Client:")
        self.form.addRow(self.client_row_label, self.client_widget)
        self._populate_client_dirs()

        # 7. Live target preview label
        self.preview_lbl = QLabel()
        self.preview_lbl.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        self.preview_lbl.setWordWrap(True)
        self.form.addRow("Resolved Target:", self.preview_lbl)

        self.radio_thin.toggled.connect(self._on_driver_mode_toggled)
        self.radio_thick.toggled.connect(self._on_driver_mode_toggled)
        self._on_driver_mode_toggled()

        # Wire live preview updates
        self.host_input.textChanged.connect(self._update_preview)
        self.port_input.textChanged.connect(self._update_preview)
        self.db_input.textChanged.connect(self._update_preview)
        self.dsn_input.textChanged.connect(self._update_preview)
        self.tns_alias_combo.editTextChanged.connect(self._update_preview)
        self.tns_alias_combo.currentIndexChanged.connect(self._update_preview)
        self.role_combo.currentIndexChanged.connect(self._update_preview)

        # Initialize mode row visibility
        self._on_mode_changed(self.conn_type_combo.currentIndex())
        self._update_preview()

    def _on_mode_changed(self, index: int) -> None:
        is_basic = (index == 0)
        is_tns = (index == 1)
        is_custom = (index == 2)

        for w in self.basic_rows:
            self.form.setRowVisible(w, is_basic)
        for w in self.tns_rows:
            self.form.setRowVisible(w, is_tns)
        for w in self.custom_rows:
            self.form.setRowVisible(w, is_custom)

        self._update_preview()

    def _on_db_type_toggled(self) -> None:
        if self.radio_service.isChecked():
            self.db_label.setText("Service Name:")
            self.db_input.setPlaceholderText("e.g. ORCL, XEPDB1, FREEPDB1")
        else:
            self.db_label.setText("SID:")
            self.db_input.setPlaceholderText("e.g. ORCL, XE")
        self._update_preview()

    def _on_driver_mode_toggled(self) -> None:
        is_thick = self.radio_thick.isChecked()
        self.form.setRowVisible(self.client_widget, is_thick)
        self._update_preview()

    def _browse_tns_admin(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select TNS Admin Directory", self.tns_admin_input.text()
        )
        if directory:
            self.tns_admin_input.setText(directory)
            self._populate_tns_aliases()

    def _populate_tns_aliases(self) -> None:
        current_text = self.tns_alias_combo.currentText()
        self.tns_alias_combo.clear()
        aliases = get_tns_names(self.tns_admin_input.text().strip())
        for alias in aliases:
            self.tns_alias_combo.addItem(alias)
        if current_text:
            idx = self.tns_alias_combo.findText(current_text)
            if idx >= 0:
                self.tns_alias_combo.setCurrentIndex(idx)
            else:
                self.tns_alias_combo.setEditText(current_text)

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

    def get_effective_dsn(self) -> str:
        """Compute the effective DSN string based on active mode."""
        mode_idx = self.conn_type_combo.currentIndex()
        if mode_idx == 0:  # Basic
            host = self.host_input.text().strip()
            port = self.port_input.text().strip() or "1521"
            db = self.db_input.text().strip()
            db_type = "service_name" if self.radio_service.isChecked() else "sid"
            return build_oracle_dsn(host, port, db, db_type=db_type)
        if mode_idx == 1:  # TNS
            return self.tns_alias_combo.currentText().strip()
        # Custom
        return self.dsn_input.text().strip()

    def _update_preview(self) -> None:
        if not hasattr(self, "preview_lbl") or not hasattr(self, "radio_thin"):
            return
        dsn = self.get_effective_dsn()
        role = self.role_combo.currentText()
        role_str = f" [as {role}]" if role != "Normal" else ""
        engine_str = " (Thin Mode)" if self.radio_thin.isChecked() else " (Thick Mode)"
        if dsn:
            self.preview_lbl.setText(f"{dsn}{role_str}{engine_str}")
        else:
            self.preview_lbl.setText("(incomplete connection details)")

    def populate_from_conn_data(self, conn_data: dict) -> None:
        """Pre-populate dialog fields when editing an existing connection."""
        self.name_input.setText(conn_data.get("name", "") or "")
        self.short_name_input.setText(conn_data.get("short_name", "") or "")
        self.user_input.setText(conn_data.get("user", "") or "")
        self.password_input.setText(str(conn_data.get("password", "") or ""))

        # Role
        role = conn_data.get("role", "Normal") or "Normal"
        role_idx = self.role_combo.findText(role)
        if role_idx >= 0:
            self.role_combo.setCurrentIndex(role_idx)

        # Inspect connection mode
        host = conn_data.get("host") or ""
        database = conn_data.get("database") or ""
        dsn = conn_data.get("dsn") or ""

        if host and database:
            self.conn_type_combo.setCurrentIndex(0)
            self.host_input.setText(host)
            self.port_input.setText(str(conn_data.get("port") or 1521))
            self.db_input.setText(database)
            # Check if DSN indicates SID
            parsed = parse_oracle_dsn(dsn) if dsn else {}
            if parsed.get("db_type") == "sid":
                self.radio_sid.setChecked(True)
            else:
                self.radio_service.setChecked(True)
        elif dsn:
            parsed = parse_oracle_dsn(dsn)
            if parsed.get("mode") == "basic" and parsed.get("host"):
                self.conn_type_combo.setCurrentIndex(0)
                self.host_input.setText(parsed["host"])
                self.port_input.setText(str(parsed.get("port") or 1521))
                self.db_input.setText(parsed.get("database") or "")
                if parsed.get("db_type") == "sid":
                    self.radio_sid.setChecked(True)
                else:
                    self.radio_service.setChecked(True)
            elif parsed.get("mode") == "tns":
                self.conn_type_combo.setCurrentIndex(1)
                self.tns_alias_combo.setEditText(parsed.get("database") or dsn)
            else:
                self.conn_type_combo.setCurrentIndex(2)
                self.dsn_input.setText(dsn)

        # Driver mode: Thin vs Thick
        driver_mode = str(conn_data.get("driver_mode", "")).lower()
        if driver_mode == "thick" or conn_data.get("oracle_client_dir"):
            self.radio_thick.setChecked(True)
        else:
            self.radio_thin.setChecked(True)

        # Oracle client directory
        saved_client = conn_data.get("oracle_client_dir")
        if saved_client:
            idx = self.client_dir_combo.findData(saved_client)
            if idx >= 0:
                self.client_dir_combo.setCurrentIndex(idx)
            else:
                ver = detect_oracle_client_version(saved_client)
                self.client_dir_combo.addItem(f"[Custom] Instant Client {ver} - {saved_client}", saved_client)
                self.client_dir_combo.setCurrentIndex(self.client_dir_combo.count() - 1)

        self._update_preview()

    def test_connection_impl(self) -> None:
        data = self.getData()
        if not data.get("dsn") and not (data.get("host") and data.get("database")):
            QMessageBox.warning(self, "Validation", "Please specify database host & name or DSN.")
            return

        self.test_btn.start_loading("Testing")

        def _do_test():
            from db.oracle_utils import test_oracle_connection_isolated
            return test_oracle_connection_isolated(data)

        self._test_worker = WorkerThread(_do_test)
        self._test_worker.finished_signal.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, result: Any, error: Exception | str | None) -> None:
        self.test_btn.stop_loading()
        if error:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to Oracle:\n{error}")
            return
        success, msg = result if isinstance(result, tuple) else (False, str(result))
        if success:
            QMessageBox.information(self, "Connection Test", msg or "Connection successful!")
        else:
            QMessageBox.critical(self, "Connection Test Failed", msg or "Failed to connect.")

    def save_connection_impl(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return
        if not self.get_effective_dsn():
            QMessageBox.warning(self, "Validation", "Please provide database connection details.")
            return
        self.accept()

    def getData(self) -> dict:
        mode_idx = self.conn_type_combo.currentIndex()
        host = self.host_input.text().strip() if mode_idx == 0 else ""
        port = (
            int(self.port_input.text().strip())
            if (mode_idx == 0 and self.port_input.text().strip().isdigit())
            else (1521 if mode_idx == 0 else None)
        )
        database = (
            self.db_input.text().strip()
            if mode_idx == 0
            else (self.tns_alias_combo.currentText().strip() if mode_idx == 1 else "")
        )
        oracle_db_type = "service_name" if (mode_idx != 0 or self.radio_service.isChecked()) else "sid"
        config_dir = self.tns_admin_input.text().strip() if mode_idx == 1 else None

        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip() or self.name_input.text().strip(),
            "host": host,
            "port": port,
            "database": database,
            "oracle_db_type": oracle_db_type,
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "role": self.role_combo.currentText(),
            "dsn": self.get_effective_dsn(),
            "config_dir": config_dir,
            "driver_mode": "thick" if self.radio_thick.isChecked() else "thin",
            "oracle_client_dir": (self.client_dir_combo.currentData() or None) if self.radio_thick.isChecked() else None,
            "connection_group_id": self.group_combo.currentData(),
        }