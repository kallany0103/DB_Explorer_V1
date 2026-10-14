from __future__ import annotations

import os
import sqlite3
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import db
from db.db_retrieval import get_groups_by_type
from db.oracle_utils import (
    build_oracle_dsn,
    detect_oracle_client_version,
    find_default_tns_admin_dir,
    find_oracle_client_dir,
    get_tns_names,
    is_valid_oracle_client_dir,
    normalize_client_path,
    scan_oracle_client_dirs,
)
from ui.components import CompactButton, PasswordBox, ToastNotification
from workers.workers import WorkerThread


def create_static_header(title: str) -> QWidget:
    """Creates a permanent form section header with divider line."""
    container = QWidget()
    container.setObjectName("formSectionHeaderContainer")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 8, 0, 4)
    layout.setSpacing(8)

    lbl = QLabel(title)
    lbl.setObjectName("configStaticSectionHeader")

    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Plain)
    line.setObjectName("formSectionLine")

    layout.addWidget(lbl)
    layout.addWidget(line, 1)
    return container


def make_field_label(text: str) -> QLabel:
    """Creates a consistent, right-aligned form field label."""
    lbl = QLabel(text)
    lbl.setObjectName("formFieldLabel")
    lbl.setFixedWidth(105)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


class BaseEngineForm(QWidget):
    """Base class for engine-specific configuration forms."""

    code: str = ""
    title_text: str = ""
    subtitle_text: str = ""
    icon_path: str = ""

    def __init__(
        self,
        type_id: int | None = None,
        group_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.type_id = type_id
        self.group_id = group_id

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 4, 16, 8)
        self.main_layout.setSpacing(6)

        self._build_header()
        self._build_general_section()
        self.setup_fields()
        self.main_layout.addStretch()

        if self.type_id:
            self.populate_groups()

    def _build_header(self) -> None:
        header_widget = QWidget()
        header_widget.setObjectName("formTopHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        if self.icon_path:
            icon_lbl = QLabel()
            icon_lbl.setObjectName("formHeaderIcon")
            icon_lbl.setFixedSize(24, 24)
            icon_lbl.setScaledContents(True)
            res_icon = db.resource_path(self.icon_path)
            if os.path.exists(res_icon):
                icon_lbl.setPixmap(QIcon(res_icon).pixmap(24, 24))
            header_layout.addWidget(icon_lbl)

        title_lbl = QLabel(self.title_text)
        title_lbl.setObjectName("formHeaderTitle")
        header_layout.addWidget(title_lbl)

        if self.subtitle_text:
            sub_lbl = QLabel(self.subtitle_text)
            sub_lbl.setObjectName("formHeaderSubtitle")
            header_layout.addWidget(sub_lbl)

        header_layout.addStretch()
        self.main_layout.addWidget(header_widget)

    def _build_general_section(self) -> None:
        self.main_layout.addWidget(create_static_header("GENERAL"))

        self.general_form = QFormLayout()
        self.general_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.general_form.setContentsMargins(0, 0, 0, 0)
        self.general_form.setHorizontalSpacing(14)
        self.general_form.setVerticalSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(f"e.g. {self.code.lower()}-prod")

        self.short_name_input = QLineEdit()
        self.short_name_input.setPlaceholderText(f"e.g. {self.code.lower()}_db")

        # Group dropdown + New Group
        group_widget = QWidget()
        group_layout = QHBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)

        self.group_combo = QComboBox()
        self.group_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.group_combo.setMinimumContentsLength(10)
        self.group_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.new_group_btn = CompactButton("New Group")
        self.new_group_btn.clicked.connect(self._create_new_group)

        group_layout.addWidget(self.group_combo, stretch=1)
        group_layout.addWidget(self.new_group_btn)

        self.general_form.addRow(make_field_label("Name"), self.name_input)
        self.general_form.addRow(make_field_label("Short Name"), self.short_name_input)
        self.general_form.addRow(make_field_label("Group"), group_widget)

        self.main_layout.addLayout(self.general_form)

    def set_type_context(self, type_id: int | None, group_id: int | None = None) -> None:
        self.type_id = type_id
        if group_id is not None:
            self.group_id = group_id
        self.populate_groups()

    def populate_groups(self) -> None:
        self.group_combo.clear()
        if not self.type_id:
            return
        groups = get_groups_by_type(self.type_id)
        for g in groups:
            self.group_combo.addItem(g["name"], g["id"])
        if self.group_id:
            idx = self.group_combo.findData(self.group_id)
            if idx >= 0:
                self.group_combo.setCurrentIndex(idx)

    def _create_new_group(self) -> None:
        if not self.type_id:
            QMessageBox.warning(self, "Warning", "Connection type not defined.")
            return
        name, ok = QInputDialog.getText(self, "New Group", "Enter group name:")
        if ok and name.strip():
            try:
                db.add_connection_group(name.strip(), self.type_id)
                self.populate_groups()
                idx = self.group_combo.findText(name.strip())
                if idx >= 0:
                    self.group_combo.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create group:\n{e}")

    def setup_fields(self) -> None:
        pass

    def get_data(self) -> dict[str, Any]:
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "connection_group_id": self.group_combo.currentData(),
            "code": self.code,
        }

    def load_data(self, data: dict[str, Any]) -> None:
        self.name_input.setText(data.get("name", ""))
        self.short_name_input.setText(data.get("short_name", ""))
        gid = data.get("connection_group_id")
        if gid:
            idx = self.group_combo.findData(gid)
            if idx >= 0:
                self.group_combo.setCurrentIndex(idx)

    def validate_inputs(self) -> tuple[bool, str]:
        if not self.name_input.text().strip():
            return False, "Connection Name is required."
        if self.group_combo.currentIndex() == -1:
            return False, "Please select or create a connection group."
        return True, ""

    def test_connection(self) -> tuple[bool, str]:
        return True, "Success"


class OracleEngineForm(BaseEngineForm):
    """Configuration form for Oracle (Basic, TNS, Custom + Thin/Thick Driver Engine)."""

    code = "ORACLE_DB"
    title_text = "Oracle"
    subtitle_text = "Service name, SID, TNS alias or descriptor"
    icon_path = "assets/oracle.svg"

    def setup_fields(self) -> None:
        self.main_layout.addWidget(create_static_header("SERVER & CREDENTIALS"))

        self.server_form = QFormLayout()
        self.server_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server_form.setContentsMargins(0, 0, 0, 0)
        self.server_form.setHorizontalSpacing(14)
        self.server_form.setVerticalSpacing(8)

        # Connection Mode
        self.conn_type_combo = QComboBox()
        self.conn_type_combo.addItems([
            "EZConnect (host, port and service name)",
            "TNS alias",
            "Custom Connection String / DSN",
        ])
        self.conn_type_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.server_form.addRow(make_field_label("Connect by"), self.conn_type_combo)

        # Mode 0: Basic Mode
        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("1521")
        self.port_input.setFixedWidth(100)

        # Database Type and Name on 1 clean row
        self.db_type_widget = QWidget()
        db_type_layout = QHBoxLayout(self.db_type_widget)
        db_type_layout.setContentsMargins(0, 0, 0, 0)
        db_type_layout.setSpacing(10)

        self.radio_service = QRadioButton("Service Name")
        self.radio_sid = QRadioButton("SID")
        self.radio_service.setChecked(True)
        self.db_type_group = QButtonGroup(self)
        self.db_type_group.addButton(self.radio_service, 0)
        self.db_type_group.addButton(self.radio_sid, 1)

        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("e.g. ORCL, XEPDB1")

        db_type_layout.addWidget(self.radio_service)
        db_type_layout.addWidget(self.radio_sid)
        db_type_layout.addWidget(self.db_input, stretch=1)

        self.server_form.addRow(make_field_label("Host"), self.host_input)
        self.server_form.addRow(make_field_label("Port"), self.port_input)
        self.server_form.addRow(make_field_label("Database"), self.db_type_widget)

        # Mode 1: TNS Mode
        self.tns_dir_widget = QWidget()
        tns_dir_layout = QHBoxLayout(self.tns_dir_widget)
        tns_dir_layout.setContentsMargins(0, 0, 0, 0)
        tns_dir_layout.setSpacing(6)
        self.tns_dir_input = QLineEdit(find_default_tns_admin_dir())
        self.tns_browse_btn = CompactButton("Browse...")
        self.tns_browse_btn.setFixedWidth(74)
        self.tns_browse_btn.clicked.connect(self._browse_tns_dir)
        tns_dir_layout.addWidget(self.tns_dir_input, stretch=1)
        tns_dir_layout.addWidget(self.tns_browse_btn)

        self.tns_alias_widget = QWidget()
        tns_alias_layout = QHBoxLayout(self.tns_alias_widget)
        tns_alias_layout.setContentsMargins(0, 0, 0, 0)
        tns_alias_layout.setSpacing(6)
        self.tns_alias_combo = QComboBox()
        self.tns_alias_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.tns_alias_combo.setMinimumContentsLength(15)
        self.tns_alias_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tns_alias_combo.setEditable(True)
        self.tns_refresh_btn = CompactButton("Refresh")
        self.tns_refresh_btn.setFixedWidth(74)
        self.tns_refresh_btn.clicked.connect(self._populate_tns_aliases)
        tns_alias_layout.addWidget(self.tns_alias_combo, stretch=1)
        tns_alias_layout.addWidget(self.tns_refresh_btn)

        self.server_form.addRow(make_field_label("TNS Folder"), self.tns_dir_widget)
        self.server_form.addRow(make_field_label("Network Alias"), self.tns_alias_widget)
        self._populate_tns_aliases()

        # Mode 2: Custom Mode
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("e.g. host:1521/service_name or (DESCRIPTION=...)")
        self.server_form.addRow(make_field_label("Connection String"), self.dsn_input)

        # Mode row grouping for visibility toggling
        self.basic_rows = [self.host_input, self.port_input, self.db_type_widget]
        self.tns_rows = [self.tns_dir_widget, self.tns_alias_widget]
        self.custom_rows = [self.dsn_input]

        # Credentials & Role
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Database username (e.g. SYSTEM)")
        self.password_input = PasswordBox()

        self.role_combo = QComboBox()
        self.role_combo.addItems(["Normal", "SYSDBA", "SYSOPER", "SYSASM"])

        self.server_form.addRow(make_field_label("Username"), self.user_input)
        self.server_form.addRow(make_field_label("Password"), self.password_input)
        self.server_form.addRow(make_field_label("Role"), self.role_combo)

        # Target Preview (kept in memory for dsn generation and testing)
        self.preview_lbl = QLabel()
        self.preview_lbl.setStyleSheet("color: #64748B; font-size: 8pt;")
        self.preview_lbl.setWordWrap(True)

        self.main_layout.addLayout(self.server_form)

        # Driver Engine Section
        self.main_layout.addWidget(create_static_header("DRIVER ENGINE"))

        self.driver_form = QFormLayout()
        self.driver_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.driver_form.setContentsMargins(0, 0, 0, 0)
        self.driver_form.setHorizontalSpacing(14)
        self.driver_form.setVerticalSpacing(8)

        self.driver_mode_group = QButtonGroup(self)
        self.radio_thin = QRadioButton("Thin mode (Default)")
        self.radio_thick = QRadioButton("Thick mode (Instant Client)")
        self.radio_thin.setChecked(True)
        self.driver_mode_group.addButton(self.radio_thin, 0)
        self.driver_mode_group.addButton(self.radio_thick, 1)

        driver_mode_layout = QHBoxLayout()
        driver_mode_layout.setContentsMargins(0, 0, 0, 0)
        driver_mode_layout.setSpacing(14)
        driver_mode_layout.addWidget(self.radio_thin)
        driver_mode_layout.addWidget(self.radio_thick)
        driver_mode_layout.addStretch()

        self.driver_form.addRow(make_field_label("Driver Engine"), driver_mode_layout)

        # Instant Client Widget
        self.client_widget = QWidget()
        client_layout = QHBoxLayout(self.client_widget)
        client_layout.setContentsMargins(0, 0, 0, 0)
        client_layout.setSpacing(6)

        self.client_dir_combo = QComboBox()
        self.client_dir_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.client_dir_combo.setMinimumContentsLength(15)
        self.client_dir_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.client_dir_combo.view().setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.client_dir_combo.setToolTip("Select or scan Oracle Instant Client library.")

        self.client_browse_btn = CompactButton("Browse...")
        self.client_browse_btn.setFixedWidth(74)
        self.client_browse_btn.clicked.connect(self._browse_custom_client_dir)

        self.client_scan_btn = CompactButton("Scan")
        self.client_scan_btn.setFixedWidth(74)
        self.client_scan_btn.clicked.connect(self._scan_for_clients)

        client_layout.addWidget(self.client_dir_combo, stretch=1)
        client_layout.addWidget(self.client_browse_btn)
        client_layout.addWidget(self.client_scan_btn)

        self.client_row_label = make_field_label("Oracle Client")
        self.driver_form.addRow(self.client_row_label, self.client_widget)
        self.main_layout.addLayout(self.driver_form)

        self._populate_client_dirs()

        # Connect toggles & preview triggers
        self.radio_thin.toggled.connect(self._on_driver_mode_toggled)
        self.radio_thick.toggled.connect(self._on_driver_mode_toggled)
        self._on_driver_mode_toggled()

        self.host_input.textChanged.connect(self._update_preview)
        self.port_input.textChanged.connect(self._update_preview)
        self.db_input.textChanged.connect(self._update_preview)
        self.dsn_input.textChanged.connect(self._update_preview)
        self.tns_alias_combo.editTextChanged.connect(self._update_preview)
        self.tns_alias_combo.currentIndexChanged.connect(self._update_preview)
        self.role_combo.currentIndexChanged.connect(self._update_preview)
        self._on_mode_changed(self.conn_type_combo.currentIndex())
        self._update_preview()

    def _on_mode_changed(self, index: int) -> None:
        is_basic = (index == 0)
        is_tns = (index == 1)
        is_custom = (index == 2)

        for w in self.basic_rows:
            self.server_form.setRowVisible(w, is_basic)
        for w in self.tns_rows:
            self.server_form.setRowVisible(w, is_tns)
        for w in self.custom_rows:
            self.server_form.setRowVisible(w, is_custom)

        self._update_preview()

    def _on_db_type_toggled(self) -> None:
        if hasattr(self, "db_label"):
            self.db_label.setText("Service Name:" if self.radio_service.isChecked() else "SID:")
        self._update_preview()

    def _on_driver_mode_toggled(self) -> None:
        is_thick = self.radio_thick.isChecked()
        self.client_widget.setVisible(is_thick)
        self.client_row_label.setVisible(is_thick)

    def _browse_tns_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select TNS Admin Directory", self.tns_dir_input.text())
        if folder:
            self.tns_dir_input.setText(folder)
            self._populate_tns_aliases()

    def _populate_tns_aliases(self) -> None:
        self.tns_alias_combo.clear()
        aliases = get_tns_names(self.tns_dir_input.text().strip())
        if aliases:
            self.tns_alias_combo.addItems(aliases)

    def _browse_custom_client_dir(self) -> None:
        initial_dir = self.client_dir_combo.currentData() or ""
        folder = QFileDialog.getExistingDirectory(self, "Select Oracle Instant Client Directory", initial_dir)
        if not folder:
            return

        is_valid, missing = is_valid_oracle_client_dir(folder)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Incomplete Oracle Client",
                "The selected directory is missing required Oracle Instant Client files:\n\n"
                + "\n".join(f"• {m}" for m in missing)
                + "\n\nPlease select an extracted Oracle Instant Client directory containing all required libraries (oci.dll, oraociei/oraociicus DLL, and orannzsbb DLL).",
            )
            return

        norm_folder = normalize_client_path(folder)
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

        def _do_scan() -> list[dict[str, Any]]:
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

    def _on_scan_finished(
        self, results: list[dict[str, Any]] | None, error: Exception | None, previous_selection: str | None
    ) -> None:
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

    def _apply_detected_clients(
        self, detected: list[dict[str, Any]], previous_selection: str | None = None
    ) -> None:
        self.client_dir_combo.clear()
        if not detected:
            self.client_dir_combo.addItem("(No Oracle Instant Client detected - Click Browse to select)", "")
            return

        seen_norm: set[str] = set()
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

        # Restore previous selection if valid
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
        detected = scan_oracle_client_dirs()
        self._apply_detected_clients(detected)

    def _update_preview(self) -> None:
        mode = self.conn_type_combo.currentIndex()
        if mode == 0:
            db_type = "service_name" if self.radio_service.isChecked() else "sid"
            target = build_oracle_dsn(self.host_input.text(), self.port_input.text(), self.db_input.text(), db_type)
        elif mode == 1:
            target = self.tns_alias_combo.currentText().strip()
        else:
            target = self.dsn_input.text().strip()
        self.preview_lbl.setText(target or "(None)")

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        mode_idx = self.conn_type_combo.currentIndex()
        is_thick = self.radio_thick.isChecked()
        client_dir = self.client_dir_combo.currentData() if is_thick else ""

        data.update({
            "connection_mode": ["basic", "tns", "custom"][mode_idx],
            "host": self.host_input.text().strip(),
            "port": self.port_input.text().strip(),
            "database": self.db_input.text().strip(),
            "database_type": "service_name" if self.radio_service.isChecked() else "sid",
            "tns_admin": self.tns_dir_input.text().strip(),
            "tns_alias": self.tns_alias_combo.currentText().strip(),
            "dsn": self.preview_lbl.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "role": self.role_combo.currentText(),
            "driver_mode": "thick" if is_thick else "thin",
            "oracle_client_dir": client_dir,
        })
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        self.host_input.setText(data.get("host", "localhost"))
        self.port_input.setText(str(data.get("port") or 1521))
        self.db_input.setText(data.get("database", ""))
        self.user_input.setText(data.get("user", ""))
        self.password_input.setText(data.get("password", ""))

        if data.get("database_type") == "sid":
            self.radio_sid.setChecked(True)
        else:
            self.radio_service.setChecked(True)

        if data.get("driver_mode") == "thick" or data.get("oracle_client_dir"):
            self.radio_thick.setChecked(True)
            cd = data.get("oracle_client_dir", "")
            if cd:
                idx = self.client_dir_combo.findData(cd)
                if idx >= 0:
                    self.client_dir_combo.setCurrentIndex(idx)
                else:
                    self.client_dir_combo.insertItem(0, cd, cd)
                    self.client_dir_combo.setCurrentIndex(0)
        else:
            self.radio_thin.setChecked(True)

        role = data.get("role", "Normal")
        ridx = self.role_combo.findText(role)
        if ridx >= 0:
            self.role_combo.setCurrentIndex(ridx)

        mode = data.get("connection_mode", "basic")
        if mode == "tns":
            self.conn_type_combo.setCurrentIndex(1)
            self.tns_dir_input.setText(data.get("tns_admin", ""))
            self.tns_alias_combo.setEditText(data.get("tns_alias", ""))
        elif mode == "custom":
            self.conn_type_combo.setCurrentIndex(2)
            self.dsn_input.setText(data.get("dsn", ""))
        else:
            self.conn_type_combo.setCurrentIndex(0)
        self._update_preview()

    def validate_inputs(self) -> tuple[bool, str]:
        ok, msg = super().validate_inputs()
        if not ok:
            return ok, msg
        if not self.preview_lbl.text().strip():
            return False, "Target connection string or host/service name is required."
        if self.radio_thick.isChecked():
            client_dir = self.client_dir_combo.currentData() or ""
            if not client_dir:
                return False, "Thick mode requires a valid Oracle Instant Client directory. Please browse and select an extracted Instant Client folder."
            is_valid, missing = is_valid_oracle_client_dir(client_dir)
            if not is_valid:
                return False, f"The selected Oracle Instant Client directory is incomplete:\n- {', '.join(missing)}"
        return True, ""

    def test_connection(self) -> tuple[bool, str]:
        d = self.get_data()
        from db.oracle_utils import test_oracle_connection_isolated
        return test_oracle_connection_isolated(d)


class PostgresEngineForm(BaseEngineForm):
    """Configuration form for PostgreSQL."""

    code = "POSTGRES"
    title_text = "PostgreSQL"
    subtitle_text = "Host, port, user and password"
    icon_path = "assets/postgresql.svg"

    def setup_fields(self) -> None:
        self.main_layout.addWidget(create_static_header("SERVER & CREDENTIALS"))

        self.server_form = QFormLayout()
        self.server_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server_form.setContentsMargins(0, 0, 0, 0)
        self.server_form.setHorizontalSpacing(14)
        self.server_form.setVerticalSpacing(8)

        self.host_input = QLineEdit("localhost")
        self.port_input = QLineEdit("5432")
        self.port_input.setFixedWidth(100)

        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("e.g. postgres, app_db")
        self.user_input = QLineEdit("postgres")
        self.password_input = PasswordBox()

        self.server_form.addRow(make_field_label("Host"), self.host_input)
        self.server_form.addRow(make_field_label("Port"), self.port_input)
        self.server_form.addRow(make_field_label("Database"), self.db_input)
        self.server_form.addRow(make_field_label("User"), self.user_input)
        self.server_form.addRow(make_field_label("Password"), self.password_input)

        self.main_layout.addLayout(self.server_form)

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        data.update({
            "host": self.host_input.text().strip(),
            "port": self.port_input.text().strip(),
            "database": self.db_input.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
        })
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        self.host_input.setText(data.get("host", "localhost"))
        self.port_input.setText(str(data.get("port") or 5432))
        self.db_input.setText(data.get("database", ""))
        self.user_input.setText(data.get("user", "postgres"))
        self.password_input.setText(data.get("password", ""))

    def test_connection(self) -> tuple[bool, str]:
        import psycopg2
        d = self.get_data()
        try:
            conn = psycopg2.connect(
                host=d["host"],
                port=int(d["port"] or 5432),
                database=d["database"] or "postgres",
                user=d["user"],
                password=d["password"],
                connect_timeout=5,
            )
            conn.close()
            return True, "Connected successfully to PostgreSQL!"
        except Exception as e:
            return False, str(e)


class SQLiteEngineForm(BaseEngineForm):
    """Configuration form for SQLite."""

    code = "SQLITE"
    title_text = "SQLite"
    subtitle_text = "Local file database (.db, .sqlite, .sqlite3)"
    icon_path = "assets/sqlite.svg"

    def setup_fields(self) -> None:
        self.main_layout.addWidget(create_static_header("DATABASE FILE"))

        self.server_form = QFormLayout()
        self.server_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server_form.setContentsMargins(0, 0, 0, 0)
        self.server_form.setHorizontalSpacing(14)
        self.server_form.setVerticalSpacing(8)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Full path to .db, .sqlite, or .sqlite3 file")
        self.browse_btn = CompactButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)

        path_layout.addWidget(self.path_input, stretch=1)
        path_layout.addWidget(self.browse_btn)

        self.server_form.addRow(make_field_label("Database Path"), path_widget)
        self.main_layout.addLayout(self.server_form)

    def _browse_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SQLite Database",
            "",
            "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if file_path:
            self.path_input.setText(file_path)

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        data.update({"db_path": self.path_input.text().strip()})
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        self.path_input.setText(data.get("db_path", ""))

    def validate_inputs(self) -> tuple[bool, str]:
        ok, msg = super().validate_inputs()
        if not ok:
            return ok, msg
        if not self.path_input.text().strip():
            return False, "Database file path is required."
        return True, ""

    def test_connection(self) -> tuple[bool, str]:
        path = self.path_input.text().strip()
        if not os.path.exists(path):
            return False, f"File does not exist: {path}"
        try:
            conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
            conn.close()
            return True, "Connected successfully to SQLite database!"
        except Exception as e:
            return False, str(e)


class ServiceNowEngineForm(BaseEngineForm):
    """Configuration form for ServiceNow."""

    code = "SERVICENOW"
    title_text = "ServiceNow"
    subtitle_text = "Instance tables via REST / OAuth"
    icon_path = "assets/servicenow.svg"

    def setup_fields(self) -> None:
        self.main_layout.addWidget(create_static_header("SERVER & CREDENTIALS"))

        self.server_form = QFormLayout()
        self.server_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server_form.setContentsMargins(0, 0, 0, 0)
        self.server_form.setHorizontalSpacing(14)
        self.server_form.setVerticalSpacing(8)

        self.instance_url_input = QLineEdit()
        self.instance_url_input.setPlaceholderText("e.g. https://dev12345.service-now.com")
        self.user_input = QLineEdit()
        self.password_input = PasswordBox()

        self.server_form.addRow(make_field_label("Instance URL"), self.instance_url_input)
        self.server_form.addRow(make_field_label("User"), self.user_input)
        self.server_form.addRow(make_field_label("Password"), self.password_input)

        self.main_layout.addLayout(self.server_form)

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        data.update({
            "instance_url": self.instance_url_input.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
        })
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        self.instance_url_input.setText(data.get("instance_url", ""))
        self.user_input.setText(data.get("user", ""))
        self.password_input.setText(data.get("password", ""))

    def validate_inputs(self) -> tuple[bool, str]:
        ok, msg = super().validate_inputs()
        if not ok:
            return ok, msg
        if not self.instance_url_input.text().strip():
            return False, "Instance URL is required."
        return True, ""

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = db.create_servicenow_connection(self.get_data())
            if conn:
                return True, "Connected successfully to ServiceNow!"
            return False, "Failed to connect to ServiceNow."
        except Exception as e:
            return False, str(e)


class CSVEngineForm(BaseEngineForm):
    """Configuration form for CSV DataStore."""

    code = "CSV"
    title_text = "CSV / Flat Files"
    subtitle_text = "Local directory of CSV, TSV or text files"
    icon_path = "assets/csv.svg"

    def setup_fields(self) -> None:
        self.main_layout.addWidget(create_static_header("DATASTORE DIRECTORY"))

        self.server_form = QFormLayout()
        self.server_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.server_form.setContentsMargins(0, 0, 0, 0)
        self.server_form.setHorizontalSpacing(14)
        self.server_form.setVerticalSpacing(8)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Directory containing .csv files")
        self.browse_btn = CompactButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_folder)

        path_layout.addWidget(self.path_input, stretch=1)
        path_layout.addWidget(self.browse_btn)

        self.server_form.addRow(make_field_label("CSV Folder"), path_widget)
        self.main_layout.addLayout(self.server_form)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select CSV Folder")
        if folder:
            self.path_input.setText(folder)

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        data.update({"db_path": self.path_input.text().strip()})
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        self.path_input.setText(data.get("db_path", ""))

    def validate_inputs(self) -> tuple[bool, str]:
        ok, msg = super().validate_inputs()
        if not ok:
            return ok, msg
        if not self.path_input.text().strip():
            return False, "CSV directory path is required."
        return True, ""

    def test_connection(self) -> tuple[bool, str]:
        try:
            conn = db.create_csv_connection(self.get_data())
            if conn:
                conn.close()
                return True, "CSV connection verified successfully!"
            return False, "Failed to verify CSV connection."
        except Exception as e:
            return False, str(e)
