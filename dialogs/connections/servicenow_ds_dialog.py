from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Qt
from ui.components import PasswordBox
from db.servicenow_metadata import _normalize_instance_url
import db

class ServiceNowDataSourceDialog(QDialog):
    def __init__(self, parent=None, conn_data=None):
        super().__init__(parent)

        self.conn_data = conn_data
        is_editing = conn_data is not None

        self.setWindowTitle(
            "Edit New Data Source" if is_editing else "New Data Source"
        )
        self.setMinimumSize(580, 500)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._apply_styles()

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        # Header
        header_title = QLabel("Configure ServiceNow connection")
        header_title.setObjectName("dialogTitle")

        header_subtitle = QLabel(
            "Import data from ServiceNow by URL and credentials via REST / OAuth."
        )
        header_subtitle.setObjectName("dialogSubtitle")

        layout.addWidget(header_title)
        layout.addWidget(header_subtitle)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        # Inputs
        self.name_input = QLineEdit()
        self.short_name_input = QLineEdit()

        self.instance_url_input = QLineEdit()
        self.instance_url_input.setPlaceholderText(
            "e.g. dev12345 or https://dev12345.service-now.com"
        )
        self.instance_url_input.editingFinished.connect(self._format_instance_url)

        self.auth_type_combo = QComboBox()
        self.auth_type_combo.addItem("Basic Authentication (User / Password)", "basic")
        self.auth_type_combo.addItem("OAuth 2.0 (Client ID / Client Secret)", "oauth")
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)

        self.user_label = QLabel("User:")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Instance admin or integration user")

        self.password_label = QLabel("Password:")
        self.password_input = PasswordBox()

        self.client_id_label = QLabel("Client ID:")
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("OAuth Client ID from ServiceNow instance")

        self.client_secret_label = QLabel("Client Secret:")
        self.client_secret_input = PasswordBox()

        # Form rows
        form.addRow("Connection Name:", self.name_input)
        form.addRow("Short Name:", self.short_name_input)
        form.addRow("Instance URL:", self.instance_url_input)
        form.addRow("Auth Method:", self.auth_type_combo)
        form.addRow(self.user_label, self.user_input)
        form.addRow(self.password_label, self.password_input)
        form.addRow(self.client_id_label, self.client_id_input)
        form.addRow(self.client_secret_label, self.client_secret_input)

        layout.addLayout(form)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondaryButton")
        self.test_btn.clicked.connect(self._test_connection)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Update" if is_editing else "Save")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._on_save)

        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Fill edit data
        if is_editing:
            self.name_input.setText(conn_data.get("name", ""))
            self.short_name_input.setText(conn_data.get("short_name", ""))
            self.instance_url_input.setText(conn_data.get("instance_url", ""))
            auth_type = (conn_data.get("auth_type") or "basic").lower()
            idx = self.auth_type_combo.findData(auth_type)
            if idx >= 0:
                self.auth_type_combo.setCurrentIndex(idx)
            self.user_input.setText(conn_data.get("user", ""))
            self.password_input.setText(conn_data.get("password", ""))
            self.client_id_input.setText(conn_data.get("client_id", ""))
            self.client_secret_input.setText(conn_data.get("client_secret", ""))

        self._on_auth_type_changed()

    def _format_instance_url(self):
        raw = self.instance_url_input.text().strip()
        if raw:
            self.instance_url_input.setText(_normalize_instance_url(raw))

    def _on_auth_type_changed(self):
        is_oauth = self.auth_type_combo.currentData() == "oauth"
        self.user_label.setVisible(not is_oauth)
        self.user_input.setVisible(not is_oauth)
        self.password_label.setVisible(not is_oauth)
        self.password_input.setVisible(not is_oauth)
        self.client_id_label.setVisible(is_oauth)
        self.client_id_input.setVisible(is_oauth)
        self.client_secret_label.setVisible(is_oauth)
        self.client_secret_input.setVisible(is_oauth)

    # ---------------- UI ----------------

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
                margin-bottom: 8px;
            }

            QLineEdit {
                min-height: 30px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                background: white;
            }

            QLineEdit:focus {
                border: 1px solid #0078d4;
            }

            QPushButton {
                min-height: 32px;
                padding: 4px 14px;
                border-radius: 6px;
                background-color: #eef1f6;
                border: 1px solid #c4c9d4;
            }

            QPushButton#primaryButton {
                background-color: #0078d4;
                color: white;
                font-weight: 600;
            }
        """)

    # ---------------- Actions ----------------

    def _test_connection(self):
        conn_data = self.getData()

        if not conn_data.get("instance_url"):
            QMessageBox.warning(self, "Validation", "Please provide an instance URL.")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText("Testing...")
        QApplication.processEvents()

        try:
            ok, msg = db.test_servicenow_connection(conn_data)
            if ok:
                QMessageBox.information(self, "Success", msg)
            else:
                QMessageBox.critical(self, "Error", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed:\n{e}")
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText("Test Connection")

    def _on_save(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide a connection name.")
            return

        if not self.instance_url_input.text().strip():
            QMessageBox.warning(self, "Validation", "Please provide an instance URL.")
            return

        auth_type = self.auth_type_combo.currentData() or "basic"
        if auth_type == "oauth":
            if not self.client_id_input.text().strip():
                QMessageBox.warning(self, "Validation", "Please provide an OAuth Client ID.")
                return
            if not self.client_secret_input.text():
                QMessageBox.warning(self, "Validation", "Please provide an OAuth Client Secret.")
                return
        else:
            if not self.user_input.text().strip():
                QMessageBox.warning(self, "Validation", "Please provide a ServiceNow username.")
                return

        self.accept()

    # ---------------- Data ----------------

    def getData(self):
        auth_type = self.auth_type_combo.currentData() or "basic"
        return {
            "name": self.name_input.text().strip(),
            "short_name": self.short_name_input.text().strip(),
            "instance_url": _normalize_instance_url(self.instance_url_input.text().strip()),
            "auth_type": auth_type,
            "user": self.user_input.text().strip(),
            "password": self.password_input.text(),
            "client_id": self.client_id_input.text().strip(),
            "client_secret": self.client_secret_input.text(),
            "id": self.conn_data.get("id") if self.conn_data else None,
        }