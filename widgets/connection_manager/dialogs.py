from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QFormLayout,
)

import db
from dialogs import (
    CSVConnectionDialog,
    OracleConnectionDialog,
    PostgresConnectionDialog,
    SQLiteConnectionDialog,
    ServiceNowConnectionDialog,
)


class ConnectionDialogs:
    def __init__(self, manager):
        self.manager = manager

    def show_connection_details(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            QMessageBox.warning(self.manager, "Error", "Could not retrieve connection data.")
            return

        parent = item.parent()
        grandparent = parent.parent() if parent else None
        code = grandparent.data(Qt.ItemDataRole.UserRole) if grandparent else None

        details_title = f"Connection Details: {conn_data.get('name')}"

        if conn_data.get("host"):
            details_text = (
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> PostgreSQL<br>"
                f"<b>Host:</b> {conn_data.get('host', 'N/A')}<br>"
                f"<b>Port:</b> {conn_data.get('port', 'N/A')}<br>"
                f"<b>Database:</b> {conn_data.get('database', 'N/A')}<br>"
                f"<b>User:</b> {conn_data.get('user', 'N/A')}"
            )
        elif conn_data.get("db_path"):
            if code == 'CSV':
                db_type_str = "CSV"
                path_label = "Folder Path"
            else:
                db_type_str = "SQLite"
                path_label = "Database Path"

            details_text = (
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> {db_type_str}<br>"
                f"<b>{path_label}:</b> {conn_data.get('db_path', 'N/A')}"
            )
        elif conn_data.get("instance_url"):
            details_text = (
                f"<b>Name:</b> {conn_data.get('name', 'N/A')}<br>"
                f"<b>Short Name:</b> {conn_data.get('short_name', 'N/A')}<br>"
                f"<b>Type:</b> ServiceNow<br>"
                f"<b>Instance URL:</b> {conn_data.get('instance_url', 'N/A')}<br>"
                f"<b>User:</b> {conn_data.get('user', 'N/A')}"
            )
        else:
            details_text = "Could not determine connection type or details."

        msg = QMessageBox(self.manager)
        msg.setWindowTitle(details_title)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)

        label = QLabel(details_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMinimumSize(400, 200)
        msg.layout().addWidget(label, 0, 1)

        msg.exec()

    def add_connection_group(self, parent_item):
        dialog = QDialog(self.manager)
        dialog.setWindowTitle("New Connection Group")
        dialog.resize(460, 220)
        dialog.setSizeGripEnabled(True)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.Dialog)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("New Connection Group")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Enter a group name for organizing connections.")
        subtitle_label.setObjectName("dialogSubtitle")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Group name")

        save_btn = QPushButton("Create")
        save_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(22, 20, 22, 18)
        dialog_layout.setSpacing(14)
        dialog_layout.addWidget(title_label)
        dialog_layout.addWidget(subtitle_label)
        dialog_layout.addWidget(name_input)
        dialog_layout.addLayout(button_layout)

        cancel_btn.clicked.connect(dialog.reject)

        def _validate_and_accept():
            if not name_input.text().strip():
                QMessageBox.warning(dialog, "Missing Info", "Group name is required.")
                return
            dialog.accept()

        save_btn.clicked.connect(_validate_and_accept)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            parent_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
            try:
                db.add_connection_group(name, parent_id)
                self.manager.load_data()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to add group:\n{e}")

    def edit_connection_group(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole + 1)
        current_name = item.text()

        dialog = QDialog(self.manager)
        dialog.setWindowTitle("Edit Connection Group")
        dialog.resize(460, 220)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("Edit Connection Group")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Update the name for this group.")
        subtitle_label.setObjectName("dialogSubtitle")
        
        name_input = QLineEdit()
        name_input.setText(current_name)
        name_input.setPlaceholderText("Group name")

        save_btn = QPushButton("Update")
        save_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(22, 20, 22, 18)
        dialog_layout.setSpacing(14)
        dialog_layout.addWidget(title_label)
        dialog_layout.addWidget(subtitle_label)
        dialog_layout.addWidget(name_input)
        dialog_layout.addLayout(button_layout)

        cancel_btn.clicked.connect(dialog.reject)

        def _on_save():
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(dialog, "Missing Info", "Group name is required.")
                return
            try:
                db.update_connection_group(group_id, name)
                dialog.accept()
                self.manager.load_data()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update group:\n{e}")

        save_btn.clicked.connect(_on_save)
        dialog.exec()

    def delete_connection_group(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole + 1)
        group_name = item.text()
        
        reply = QMessageBox.question(
            self.manager,
            "Delete Connection Group",
            f"Are you sure you want to delete the group '{group_name}'?\nThis will also delete ALL connections within this group.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection_group(group_id)
                self.manager.load_data()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to delete group:\n{e}")

    def edit_connection_type(self, item):
        type_id = item.data(Qt.ItemDataRole.UserRole + 1)
        current_name = item.text()
        current_code = item.data(Qt.ItemDataRole.UserRole)

        dialog = QDialog(self.manager)
        dialog.setWindowTitle("Edit Connection Type")
        dialog.resize(460, 260)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("Edit Connection Type")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Update the display name and code for this category.")
        subtitle_label.setObjectName("dialogSubtitle")
        
        name_input = QLineEdit()
        name_input.setText(current_name)
        name_input.setPlaceholderText("Display Name")
        
        code_input = QLineEdit()
        code_input.setText(current_code)
        code_input.setPlaceholderText("Type (e.g. SQLITE)")

        save_btn = QPushButton("Update")
        save_btn.setObjectName("primaryButton")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        form = QFormLayout()
        form.addRow("Name:", name_input)
        form.addRow("Type:", code_input)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(22, 20, 22, 18)
        dialog_layout.setSpacing(14)
        dialog_layout.addWidget(title_label)
        dialog_layout.addWidget(subtitle_label)
        dialog_layout.addLayout(form)
        dialog_layout.addLayout(button_layout)

        cancel_btn.clicked.connect(dialog.reject)

        def _on_save():
            name = name_input.text().strip()
            code = code_input.text().strip().upper()
            if not name or not code:
                QMessageBox.warning(dialog, "Missing Info", "Both Name and Type are required.")
                return
            try:
                db.update_connection_type(type_id, name, code)
                dialog.accept()
                self.manager.load_data()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update type:\n{e}")

        save_btn.clicked.connect(_on_save)
        dialog.exec()

    def delete_connection_type(self, item):
        type_id = item.data(Qt.ItemDataRole.UserRole + 1)
        type_name = item.text()
        
        reply = QMessageBox.question(
            self.manager,
            "Delete Connection Type",
            f"Are you sure you want to delete the type '{type_name}'?\nThis will also delete ALL groups and connections within this type.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection_type(type_id)
                self.manager.load_data()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to delete type:\n{e}")

    def add_postgres_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = PostgresConnectionDialog(self.manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save PostgreSQL connection:\n{e}")

    def add_sqlite_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = SQLiteConnectionDialog(self.manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save SQLite connection:\n{e}")

    def add_oracle_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = OracleConnectionDialog(self.manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save Oracle connection:\n{e}")

    def edit_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if conn_data and conn_data.get("db_path"):
            dialog = SQLiteConnectionDialog(self.manager, conn_data=conn_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.getData()
                try:
                    db.update_connection(new_data)
                    self.manager._save_tree_expansion_state()
                    self.manager.load_data()
                    self.manager._restore_tree_expansion_state()
                    self.manager.refresh_all_comboboxes()
                except Exception as e:
                    QMessageBox.critical(self.manager, "Error", f"Failed to update SQLite connection:\n{e}")

    def edit_pg_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return
        dialog = PostgresConnectionDialog(self.manager, is_editing=True)
        dialog.name_input.setText(conn_data.get("name", ""))
        dialog.short_name_input.setText(conn_data.get("short_name", ""))
        dialog.host_input.setText(conn_data.get("host", ""))
        dialog.port_input.setText(str(conn_data.get("port", "")))
        dialog.db_input.setText(conn_data.get("database", ""))
        dialog.user_input.setText(conn_data.get("user", ""))
        dialog.password_input.setText(conn_data.get("password", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            new_data["id"] = conn_data.get("id")
            try:
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update PostgreSQL connection:\n{e}")

    def edit_oracle_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return
        dialog = OracleConnectionDialog(self.manager, is_editing=True)
        dialog.name_input.setText(conn_data.get("name", ""))
        dialog.user_input.setText(conn_data.get("user", ""))
        dialog.password_input.setText(conn_data.get("password", ""))
        dialog.dsn_input.setText(conn_data.get("dsn", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            new_data["id"] = conn_data.get("id")
            try:
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update Oracle connection:\n{e}")

    def add_servicenow_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = ServiceNowConnectionDialog(self.manager)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save ServiceNow connection:\n{e}")

    def edit_servicenow_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return

        dialog = ServiceNowConnectionDialog(self.manager, conn_data=conn_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update ServiceNow connection:\n{e}")

    def add_csv_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        dialog = CSVConnectionDialog(self.manager)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                db.add_connection(data, connection_group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save CSV connection:\n{e}")

    def edit_csv_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)

        if not conn_data or not conn_data.get("db_path"):
            QMessageBox.warning(self.manager, "Invalid", "This is not a CSV connection.")
            return

        dialog = CSVConnectionDialog(self.manager, conn_data=conn_data)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update CSV connection:\n{e}")
