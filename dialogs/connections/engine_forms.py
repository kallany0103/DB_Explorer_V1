from __future__ import annotations

import os
import json
import sqlite3
from typing import Any
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import db
from db.db_retrieval import get_groups_by_type
from db.oracle_utils import (
    build_oracle_dsn,
    find_default_tns_admin_dir,
    get_tns_names,
)
from ui.components import CompactButton, PasswordBox


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
        if not self.type_id and self.code:
            from db.db_retrieval import get_connection_types
            for t in get_connection_types():
                t_code = str(t.get("code", "")).upper()
                c_code = str(self.code).upper()
                if t_code == c_code or (c_code.startswith("ORACLE") and t_code.startswith("ORACLE")):
                    self.type_id = t.get("id")
                    break
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
        data: dict[str, Any] = {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "connection_group_id": self.group_combo.currentData(),
            "code": self.code,
        }
        if hasattr(self, "_conn_id") and self._conn_id is not None:
            data["id"] = self._conn_id
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        self._conn_id = data.get("id")
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
    """Configuration form for Oracle (Direct and TNS)."""

    code = "ORACLE_DB"
    title_text = "Oracle"
    subtitle_text = "Direct (Host, Port, Service/SID) or TNS"
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
            "Direct",
            "TNS",
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
        self.db_input.setPlaceholderText("e.g. XEPDB1, FREEPDB1, ORCL (use PDB for local XE/FREE)")

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
        self.tns_editor_btn = CompactButton("TNSNames Editor")
        self.tns_editor_btn.clicked.connect(self._open_tns_editor)
        self.tns_file_status_lbl = QLabel()
        self.tns_file_status_lbl.setFixedSize(20, 20)
        self.tns_file_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tns_alias_layout.addWidget(self.tns_alias_combo, stretch=1)
        tns_alias_layout.addWidget(self.tns_editor_btn)
        tns_alias_layout.addWidget(self.tns_file_status_lbl)

        self.server_form.addRow(make_field_label("TNS Folder"), self.tns_dir_widget)
        self.server_form.addRow(make_field_label("Database"), self.tns_alias_widget)
        self.tns_dir_input.textChanged.connect(self._populate_tns_aliases)
        self._populate_tns_aliases()

        # Mode row grouping for visibility toggling
        self.basic_rows = [self.host_input, self.port_input, self.db_type_widget]
        self.tns_rows = [self.tns_dir_widget, self.tns_alias_widget]

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

        # ── ORACLE CLIENT section ────────────────────────────────────────
        self.main_layout.addWidget(create_static_header("ORACLE CLIENT"))

        self.use_client_chk = QCheckBox("Connect using Oracle Client")
        self.use_client_chk.setObjectName("oracleClientCheckbox")
        self.use_client_chk.toggled.connect(self._on_client_toggled)
        self.main_layout.addWidget(self.use_client_chk)

        # Group box — hidden until checkbox is checked
        self.client_group = QGroupBox("Installed Clients")
        self.client_group.setObjectName("oracleClientGroup")
        cg_layout = QVBoxLayout(self.client_group)
        cg_layout.setContentsMargins(12, 16, 12, 10)
        cg_layout.setSpacing(8)

        # Row 1: client dropdown + "..." browse button
        client_row = QWidget()
        client_row_layout = QHBoxLayout(client_row)
        client_row_layout.setContentsMargins(0, 0, 0, 0)
        client_row_layout.setSpacing(6)

        self.client_combo = QComboBox()
        self.client_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.client_combo.currentIndexChanged.connect(self._update_sqlnet_status)

        self.client_browse_btn = CompactButton("...")
        self.client_browse_btn.setFixedWidth(28)
        self.client_browse_btn.setToolTip("Browse for a custom Oracle Client directory")
        self.client_browse_btn.clicked.connect(self._on_browse_client)

        client_row_layout.addWidget(self.client_combo, 1)
        client_row_layout.addWidget(self.client_browse_btn)
        cg_layout.addWidget(client_row)

        # Row 2: "Use this client by default"
        self.use_default_chk = QCheckBox("Use this client by default")
        self.use_default_chk.setObjectName("oracleUseDefaultChk")
        self.use_default_chk.toggled.connect(self._on_use_default_toggled)
        cg_layout.addWidget(self.use_default_chk)

        # Row 3: SQLNET Editor button + live status icon
        sqlnet_row = QWidget()
        sqlnet_row_layout = QHBoxLayout(sqlnet_row)
        sqlnet_row_layout.setContentsMargins(0, 0, 0, 0)
        sqlnet_row_layout.setSpacing(8)

        self.sqlnet_btn = CompactButton("SQLNET Editor")
        self.sqlnet_btn.clicked.connect(self._open_sqlnet_editor)

        self.sqlnet_status_lbl = QLabel()
        self.sqlnet_status_lbl.setObjectName("sqlnetStatusIcon")
        self.sqlnet_status_lbl.setFixedSize(20, 20)
        self.sqlnet_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sqlnet_row_layout.addWidget(self.sqlnet_btn)
        sqlnet_row_layout.addWidget(self.sqlnet_status_lbl)
        sqlnet_row_layout.addStretch()
        cg_layout.addWidget(sqlnet_row)

        self.main_layout.addWidget(self.client_group)
        self.client_group.hide()

        # Populate detected clients lazily (fast env/PATH scan at form open)
        self._scan_worker = None  # holds WorkerThread ref to prevent GC
        self._populate_clients()

        # Connect preview triggers
        self.radio_service.toggled.connect(self._on_db_type_toggled)
        self.host_input.textChanged.connect(self._update_preview)
        self.port_input.textChanged.connect(self._update_preview)
        self.db_input.textChanged.connect(self._update_preview)
        self.tns_alias_combo.editTextChanged.connect(self._update_preview)
        self.tns_alias_combo.currentIndexChanged.connect(self._update_preview)
        self.role_combo.currentIndexChanged.connect(self._update_preview)
        self._on_mode_changed(self.conn_type_combo.currentIndex())
        self._update_preview()
        self._initialized = True

    def _on_mode_changed(self, index: int) -> None:
        is_direct = (index == 0)
        is_tns = (index == 1)

        for w in self.basic_rows:
            self.server_form.setRowVisible(w, is_direct)
        for w in self.tns_rows:
            self.server_form.setRowVisible(w, is_tns)

        self._update_preview()

    def _on_db_type_toggled(self) -> None:
        if hasattr(self, "db_input"):
            self.db_input.setPlaceholderText(
                "e.g. XEPDB1, FREEPDB1, ORCL (use PDB for local XE/FREE)"
                if self.radio_service.isChecked()
                else "e.g. XE, ORCL (older SID-based instances)"
            )
        self._update_preview()

    def _browse_tns_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select TNS Admin Directory", self.tns_dir_input.text())
        if folder:
            self.tns_dir_input.setText(folder)
            self._populate_tns_aliases()

    def _populate_tns_aliases(self) -> None:
        from pathlib import Path as _Path
        self.tns_alias_combo.clear()
        tns_dir = self.tns_dir_input.text().strip()
        tns_file_exists = bool(tns_dir) and (_Path(tns_dir) / "tnsnames.ora").is_file()
        if tns_file_exists:
            self.tns_file_status_lbl.setText("✔")
            self.tns_file_status_lbl.setStyleSheet("color: #22c55e; font-size: 13px; font-weight: bold;")
            self.tns_file_status_lbl.setToolTip(f"tnsnames.ora found in {tns_dir}")
        else:
            self.tns_file_status_lbl.setText("✘")
            self.tns_file_status_lbl.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: bold;")
            tip = f"tnsnames.ora not found in {tns_dir}" if tns_dir else "No TNS folder set"
            self.tns_file_status_lbl.setToolTip(tip)
        aliases = get_tns_names(tns_dir)
        if aliases:
            self.tns_alias_combo.addItems(aliases)

    def _open_tns_editor(self) -> None:
        """Open tnsnames.ora in the system default text editor, or reveal the folder."""
        import subprocess
        from pathlib import Path as _Path
        tns_dir = self.tns_dir_input.text().strip()
        if not tns_dir:
            return
        tns_file = _Path(tns_dir) / "tnsnames.ora"
        if tns_file.is_file():
            subprocess.Popen(["notepad.exe", str(tns_file)])
        else:
            # File missing — open the folder so the user can create it
            subprocess.Popen(["explorer.exe", str(_Path(tns_dir))])

    def _update_preview(self) -> None:
        mode = self.conn_type_combo.currentIndex()
        if mode == 0:
            db_type = "service_name" if self.radio_service.isChecked() else "sid"
            target = build_oracle_dsn(self.host_input.text(), self.port_input.text(), self.db_input.text(), db_type)
        else:
            target = self.tns_alias_combo.currentText().strip()
        self.preview_lbl.setText(target or "(None)")

    def get_data(self) -> dict[str, Any]:
        data = super().get_data()
        mode_idx = self.conn_type_combo.currentIndex()
        conn_mode = "direct" if mode_idx == 0 else "tns"

        use_thick = self.use_client_chk.isChecked()
        driver_mode = "thick" if use_thick else "thin"
        oracle_client_dir = self.client_combo.currentData() or "" if use_thick else ""

        config_dict = {
            "driver_mode": driver_mode,
            "oracle_client_dir": oracle_client_dir,
            "database_type": "service_name" if self.radio_service.isChecked() else "sid",
            "tns_admin": self.tns_dir_input.text().strip(),
            "tns_alias": self.tns_alias_combo.currentText().strip(),
            "connection_mode": conn_mode,
        }

        data.update({
            "connection_mode": conn_mode,
            "host": self.host_input.text().strip(),
            "port": self.port_input.text().strip(),
            "database": self.db_input.text().strip() if mode_idx == 0 else self.tns_alias_combo.currentText().strip(),
            "database_type": "service_name" if self.radio_service.isChecked() else "sid",
            "tns_admin": self.tns_dir_input.text().strip(),
            "tns_alias": self.tns_alias_combo.currentText().strip(),
            "dsn": self.preview_lbl.text().strip(),
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "role": self.role_combo.currentText(),
            "driver_mode": driver_mode,
            "oracle_client_dir": oracle_client_dir,
            "config_json": json.dumps(config_dict),
        })
        return data

    def load_data(self, data: dict[str, Any]) -> None:
        super().load_data(data)
        if "config_json" in data and isinstance(data["config_json"], str) and data["config_json"].strip():
            try:
                cfg = json.loads(data["config_json"])
                if isinstance(cfg, dict):
                    merged = dict(cfg)
                    merged.update(data)
                    data = merged
            except Exception:
                pass
        self.host_input.setText(data.get("host", "localhost"))
        self.port_input.setText(str(data.get("port") or 1521))
        self.db_input.setText(data.get("database", ""))
        self.user_input.setText(data.get("user", ""))
        self.password_input.setText(data.get("password", ""))

        if data.get("database_type") == "sid" or data.get("oracle_db_type") == "sid":
            self.radio_sid.setChecked(True)
        else:
            self.radio_service.setChecked(True)

        role = data.get("role", "Normal")
        ridx = self.role_combo.findText(role)
        if ridx >= 0:
            self.role_combo.setCurrentIndex(ridx)

        mode = data.get("connection_mode")
        dsn = data.get("dsn", "")
        if not mode and dsn:
            from db.oracle_utils import parse_oracle_dsn
            parsed = parse_oracle_dsn(dsn)
            parsed_mode = parsed.get("mode", "basic")
            if parsed_mode == "basic" and parsed.get("host"):
                mode = "direct"
                self.host_input.setText(parsed["host"])
                self.port_input.setText(str(parsed.get("port") or 1521))
                self.db_input.setText(parsed.get("database") or "")
                if parsed.get("db_type") == "sid":
                    self.radio_sid.setChecked(True)
                else:
                    self.radio_service.setChecked(True)
            elif parsed_mode == "tns":
                mode = "tns"
                self.tns_alias_combo.setEditText(parsed.get("database") or dsn)
            else:
                mode = "direct"

        if not mode:
            mode = "direct"

        if mode == "tns":
            self.conn_type_combo.setCurrentIndex(1)
            tns_dir = data.get("tns_admin") or data.get("config_dir") or ""
            if tns_dir:
                self.tns_dir_input.setText(tns_dir)
            tns_alias = data.get("tns_alias") or (data.get("database") if data.get("connection_mode") == "tns" else "")
            if tns_alias:
                self.tns_alias_combo.setEditText(tns_alias)
        else:
            self.conn_type_combo.setCurrentIndex(0)
        self._update_preview()

        # Restore Oracle Client selection
        driver_mode = data.get("driver_mode", "thin")
        oracle_client_dir = data.get("oracle_client_dir", "")
        if driver_mode == "thick" or oracle_client_dir:
            self.use_client_chk.setChecked(True)
            if oracle_client_dir:
                self._select_or_add_client(oracle_client_dir)
            # Check if saved dir matches the persisted default
            settings = QSettings("DBExplorer", "OracleClient")
            default_dir = settings.value("default_client_dir", "")
            if oracle_client_dir and oracle_client_dir == default_dir:
                self.use_default_chk.setChecked(True)

    def get_effective_dsn(self) -> str:
        return self.preview_lbl.text().strip()

    # ------------------------------------------------------------------
    # Oracle Client helpers
    # ------------------------------------------------------------------

    def _on_client_toggled(self, checked: bool) -> None:
        """Show/hide the Installed Clients group box and auto-expand / scroll into view."""
        self.client_group.setVisible(checked)
        self._update_sqlnet_status()
        if checked:
            QTimer.singleShot(50, self._ensure_client_section_visible)

    def _ensure_client_section_visible(self) -> None:
        """Auto-expand dialog window if space allows, and scroll client section into view."""
        if not self.use_client_chk.isChecked():
            return

        # 1. Auto-expand dialog window height if there is available screen space
        top_win = self.window()
        if top_win and top_win.isWidgetType() and not top_win.isMaximized():
            screen = top_win.screen() or QApplication.primaryScreen()
            screen_h = screen.availableGeometry().height() if screen else 900
            max_h = screen_h - 60
            if hasattr(top_win, "maximumHeight"):
                max_h = min(max_h, top_win.maximumHeight())

            needed_h = top_win.sizeHint().height()
            current_h = top_win.height()
            if needed_h > current_h and current_h < max_h:
                expand_h = self.client_group.sizeHint().height() or 130
                target_h = min(max_h, max(needed_h, current_h + expand_h + 16))
                top_win.resize(top_win.width(), target_h)

        # 2. Scroll containing QScrollArea (FitScrollArea or standard QScrollArea) into view
        parent = self.parentWidget()
        scroll_area = None
        while parent:
            if isinstance(parent, QScrollArea):
                scroll_area = parent
                break
            parent = parent.parentWidget()

        if scroll_area:
            scroll_area.ensureWidgetVisible(self.client_group, 0, 20)

    def _populate_clients(self) -> None:
        """Scan for installed Oracle clients and fill the combo.

        Uses WorkerThread so the slow drive-scan does not block the UI.
        Shows a placeholder item while scanning.
        """
        from db.oracle_utils import scan_oracle_client_dirs
        from workers.workers import WorkerThread

        self.client_combo.clear()
        self.client_combo.addItem("Scanning…", None)
        self.client_combo.setEnabled(False)
        self.client_browse_btn.setEnabled(False)

        self._scan_worker = WorkerThread(scan_oracle_client_dirs)
        self._scan_worker.finished_signal.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, clients: list | None, error: Exception | None) -> None:
        """Populate the combo once the background scan has finished."""
        from db.oracle_utils import normalize_client_path

        self.client_combo.clear()
        self.client_combo.setEnabled(True)
        self.client_browse_btn.setEnabled(True)

        if error or not clients:
            self.client_combo.addItem("(No Oracle clients detected)", None)
            return

        settings = QSettings("DBExplorer", "OracleClient")
        default_dir = settings.value("default_client_dir", "")
        default_idx = -1

        for i, c in enumerate(clients):
            label = c["label"]
            self.client_combo.addItem(label, c["path"])
            if default_dir and normalize_client_path(c["path"]) == normalize_client_path(default_dir):
                default_idx = i

        if default_idx >= 0:
            self.client_combo.setCurrentIndex(default_idx)
            self.use_default_chk.setChecked(True)

        self._update_sqlnet_status()

    def _select_or_add_client(self, client_dir: str) -> None:
        """Select a client dir in the combo, adding it as a custom entry if not found."""
        from db.oracle_utils import get_oci_dll_version, normalize_client_path

        norm_target = normalize_client_path(client_dir)
        for i in range(self.client_combo.count()):
            data = self.client_combo.itemData(i)
            if data and normalize_client_path(data) == norm_target:
                self.client_combo.setCurrentIndex(i)
                return

        # Not found — add as custom entry
        from db.oracle_utils import get_registered_oracle_homes
        norm_target = normalize_client_path(client_dir)
        reg_label = next(
            (h["home_name"] for h in get_registered_oracle_homes()
             if normalize_client_path(h["path"]) == norm_target),
            None,
        )
        if reg_label:
            label = reg_label
        else:
            dll_ver = get_oci_dll_version(client_dir) or "Custom"
            label = f"Instant Client - {dll_ver}"
        self.client_combo.insertItem(0, label, client_dir)
        self.client_combo.setCurrentIndex(0)

    def _on_browse_client(self) -> None:
        """Let the user browse for a custom Oracle Client directory."""
        from db.oracle_utils import is_valid_oracle_client_dir

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Oracle Client Directory",
            self.client_combo.currentData() or "",
        )
        if not folder:
            return

        is_valid, missing = is_valid_oracle_client_dir(folder)
        if not is_valid:
            QMessageBox.warning(
                self,
                "Invalid Oracle Client Directory",
                "The selected directory does not appear to be a valid Oracle Client.\n\nMissing:\n"
                + "\n".join(missing),
            )
            return

        self._select_or_add_client(folder)
        self._update_sqlnet_status()

    def _on_use_default_toggled(self, checked: bool) -> None:
        """Persist or remove the default Oracle Client path in QSettings."""
        settings = QSettings("DBExplorer", "OracleClient")
        if checked:
            path = self.client_combo.currentData() or ""
            settings.setValue("default_client_dir", path)
        else:
            settings.remove("default_client_dir")

    def _get_current_client_dir(self) -> str:
        """Return the selected client directory, or empty string if thick mode is off."""
        if not self.use_client_chk.isChecked():
            return ""
        return self.client_combo.currentData() or ""

    def _update_sqlnet_status(self) -> None:
        """Update the ✔/✘ icon based on whether sqlnet.ora exists for the selected client."""
        if not hasattr(self, "sqlnet_status_lbl") or not self.use_client_chk.isChecked():
            return
        from db.oracle_utils import get_client_sqlnet_path

        client_dir = self._get_current_client_dir()
        if not client_dir:
            self.sqlnet_status_lbl.setText("")
            return

        sqlnet_path = get_client_sqlnet_path(client_dir)
        if sqlnet_path.is_file():
            self.sqlnet_status_lbl.setText("✔")
            self.sqlnet_status_lbl.setStyleSheet(
                "color: #16a34a; font-size: 13px; font-weight: bold;"
            )
            self.sqlnet_status_lbl.setToolTip(f"sqlnet.ora found:\n{sqlnet_path}")
        else:
            self.sqlnet_status_lbl.setText("✘")
            self.sqlnet_status_lbl.setStyleSheet(
                "color: #dc2626; font-size: 13px; font-weight: bold;"
            )
            self.sqlnet_status_lbl.setToolTip(
                f"sqlnet.ora not found.\nExpected: {sqlnet_path}\nClick SQLNET Editor to create it."
            )

    def _open_sqlnet_editor(self) -> None:
        """Open the SQLNET Editor dialog for the currently selected client."""
        from dialogs.connections.sqlnet_editor_dialog import SqlnetEditorDialog
        from db.oracle_utils import get_client_sqlnet_path

        client_dir = self._get_current_client_dir()
        if not client_dir:
            QMessageBox.warning(
                self, "No Client Selected", "Please select an Oracle Client directory first."
            )
            return

        sqlnet_path = get_client_sqlnet_path(client_dir)
        dlg = SqlnetEditorDialog(sqlnet_path, parent=self)
        if dlg.exec():
            self._update_sqlnet_status()

    def validate_inputs(self) -> tuple[bool, str]:
        ok, msg = super().validate_inputs()
        if not ok:
            return ok, msg
        if not self.preview_lbl.text().strip():
            return False, "Target connection string or host/service name is required."
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
