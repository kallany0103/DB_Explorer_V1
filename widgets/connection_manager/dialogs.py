import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QFormLayout,
    QGridLayout,
    QToolButton,
    QScrollArea,
    QWidget,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

from ui.components import PrimaryButton, SecondaryButton, ToastNotification
import db
from dialogs.connections import (
    CSVConnectionDialog,
    OracleConnectionDialog,
    PostgresConnectionDialog,
    SQLiteConnectionDialog,
    ServiceNowConnectionDialog,
    UDSConnectionDialog,
    PostgresDataSourceDialog,
	SQLiteDataSourceDialog,
	OracleDataSourceDialog,
	CSVDataSourceDialog,
	ServiceNowDataSourceDialog,
)
from db.db_retrieval import get_connection_types

class ConnectionTypeSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Connection Type")
        self.resize(600, 450)
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        self.setStyleSheet(self._get_style())
        
        self.selected_type = None
        self.init_ui()

    def _get_style(self):
        return """
            QDialog {
                background-color: #f6f8fb;
            }
            QLabel#dialogTitle {
                font-size: 18px;
                font-weight: 600;
                color: #1f2937;
            }
            QLabel#dialogSubtitle {
                color: #6b7280;
                margin-bottom: 12px;
            }
            QScrollArea {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                background-color: white;
            }
            #typeButton {
                border: 1px solid transparent;
                border-radius: 8px;
                background-color: transparent;
                padding: 10px;
                font-weight: 500;
                color: #374151;
            }
            #typeButton:hover {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
            }
            #typeButton[selected="true"] {
                background-color: #eff6ff;
                border: 2px solid #3b82f6;
                color: #1d4ed8;
            }
        """

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title_label = QLabel("Select a connection type")
        title_label.setObjectName("dialogTitle")
        
        subtitle_label = QLabel("Choose the database system you want to connect to.")
        subtitle_label.setObjectName("dialogSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        # Grid of types
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)

        self.type_buttons = []
        types = get_connection_types()
        
        row, col = 0, 0
        for t in types:
            btn = QToolButton()
            btn.setObjectName("typeButton")
            btn.setText(t["name"])
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIconSize(QSize(56, 56))
            
            # Allow multi-line text for long connection type names
            display_name = t["name"]
            if "Oracle Fusion" in display_name:
                display_name = display_name.replace("Oracle Fusion ", "Oracle Fusion\n")
            elif len(display_name) > 15:
                # Fallback for any other long names: try to break at last space
                last_space = display_name.rfind(" ")
                if last_space != -1:
                    display_name = display_name[:last_space] + "\n" + display_name[last_space+1:]
            
            btn.setText(display_name)
            
            # Ultra-robust Map code to icon logic
            raw_name = t.get("name", "").lower().strip()
            raw_code = t.get("code", "").lower().strip()
            lookup = f"{raw_name} {raw_code}"
            
            code = None
            # Check for Oracle Fusion first (more specific)
            if any(x in lookup for x in ['fusion', 'fuision', 'erp']):
                if any(x in lookup for x in ['oracle', 'oracel', 'orace']):
                    code = "oracle_fusion"
            # Check for standard Oracle
            if not code and any(x in lookup for x in ['oracle', 'oracel', 'orace']):
                code = "oracle"
            
            # Check for other types
            if not code:
                if 'postgres' in lookup:
                    code = "postgresql"
                elif 'servicenow' in lookup:
                    code = "servicenow"
                elif 'sqlite' in lookup:
                    code = "sqlite"
                elif 'csv' in lookup:
                    code = "csv"
                elif 'uds' in lookup or 'unified' in lookup:
                    code = "unified_data_source"
                else:
                    # Generic cleanup
                    code = raw_code.replace(" ", "_") if raw_code else raw_name.replace(" ", "_")
            
            icon_path = db.resource_path(f"assets/{code}.svg")
            
            # Final fallback: if specifically mapped as oracle but file missing, try to find it
            if not os.path.exists(icon_path):
                # Try relative as secondary fallback
                if os.path.exists(f"assets/{code}.svg"):
                    icon_path = f"assets/{code}.svg"

            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
            else:
                # If everything fails, try one more time with the code directly
                alt_path = db.resource_path(f"assets/{raw_code}.svg")
                if os.path.exists(alt_path):
                    btn.setIcon(QIcon(alt_path))
                else:
                    btn.setIcon(QIcon(db.resource_path("assets/database.svg"))) # Fallback

            btn.setFixedSize(150, 120)
            btn.clicked.connect(lambda checked, type_info=t: self._on_type_selected(type_info))
            
            self.grid_layout.addWidget(btn, row, col)
            self.type_buttons.append((btn, t))
            
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        container.setLayout(self.grid_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        self.next_btn = PrimaryButton("Next")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.accept)
        
        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.next_btn)
        layout.addLayout(btn_layout)

    def _on_type_selected(self, type_info):
        self.selected_type = type_info
        for btn, t in self.type_buttons:
            if t["id"] == type_info["id"]:
                btn.setProperty("selected", "true")
            else:
                btn.setProperty("selected", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        
        self.next_btn.setEnabled(True)



class ConnectionDialogs:

    def __init__(self, manager):
        self.manager = manager

    def _reload_and_expand_group(self, parent_item):
        type_item = parent_item.parent()
        type_name = type_item.text() if type_item else None
        group_name = parent_item.text()

        self.manager._save_tree_expansion_state()
        
        if type_name and group_name:
            if not hasattr(self.manager, '_saved_tree_paths'):
                self.manager._saved_tree_paths = set()
            if isinstance(self.manager._saved_tree_paths, list):
                self.manager._saved_tree_paths = set(self.manager._saved_tree_paths)
            self.manager._saved_tree_paths.add((type_name, None, None))
            self.manager._saved_tree_paths.add((type_name, group_name, None))

        self.manager.load_data()
        self.manager._restore_tree_expansion_state()
        self.manager.refresh_all_comboboxes()

    def add_data_source(self, parent_item=None):
        selector = ConnectionTypeSelectorDialog(self.manager)

        if selector.exec() != QDialog.DialogCode.Accepted:
            return

        type_info = selector.selected_type
        if not type_info:
            return

        code = type_info["code"].upper()

        if not parent_item:
            # Fallback to active UDS connection if available
            if hasattr(self.manager, "active_postgres_conn") and self.manager.active_postgres_conn:
                host_conn_data = self.manager.active_postgres_conn
                connection_id = host_conn_data.get("id")
            else:
                QMessageBox.warning(
                    self.manager,
                    "Missing Context",
                    "Please select a Connection first."
                )
                return
        else:
            item_data = parent_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(item_data, dict) and item_data.get("conn_data"):
                host_conn_data = item_data.get("conn_data")
                connection_id = host_conn_data.get("id") or item_data.get("connection_id")
            else:
                connection_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
                host_conn_data = item_data if isinstance(item_data, dict) else self.manager.active_postgres_conn

        if not connection_id or not host_conn_data:
            QMessageBox.warning(
                self.manager,
                "Invalid Selection",
                "Invalid connection node."
            )
            return

        if code == "POSTGRES":
            dialog = PostgresDataSourceDialog(self.manager)
        elif code == "SQLITE":
            dialog = SQLiteDataSourceDialog(self.manager)
        elif code == "ORACLE":
            dialog = OracleDataSourceDialog(self.manager)
        elif code == "CSV":
            dialog = CSVDataSourceDialog(self.manager)
        elif code == "SERVICENOW":
            dialog = ServiceNowDataSourceDialog(self.manager)
        elif code in ("CSV", "FILE"):
            from dialogs.connections.csv_ds_dialog import CSVDataSourceDialog
            dialog = CSVDataSourceDialog(self.manager)
        else:
            QMessageBox.warning(
                self.manager,
                "Unsupported Type",
                f"{code} not supported"
            )
            return

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.getData()

        try:
            server_name = None
            local_schema = None

            # Automatically ensure necessary FDW extensions exist on host database
            if host_conn_data:
                try:
                    db.ensure_host_fdw_extensions(host_conn_data)
                except Exception as ext_err:
                    print(f"Notice: Background FDW extension initialization notice: {ext_err}")

            # Automatically provision Foreign Data Wrapper in the background on host PostgreSQL
            fdw_name = "postgres_fdw"
            if code == "POSTGRES" and host_conn_data:
                server_name, local_schema = db.create_postgres_fdw_source(host_conn_data, data)
                data["server_name"] = server_name
                data["schema_name"] = local_schema
                data["fdw_name"] = "postgres_fdw"
                fdw_name = "postgres_fdw"
            elif code == "SQLITE" and host_conn_data:
                server_name, local_schema = db.create_sqlite_fdw_source(host_conn_data, data)
                data["server_name"] = server_name
                data["schema_name"] = local_schema
                data["fdw_name"] = "sqlite_fdw"
                fdw_name = "sqlite_fdw"
            elif code in ("CSV", "FILE") and host_conn_data:
                server_name, local_schema, table_count = db.create_file_fdw_source(host_conn_data, data)
                data["server_name"] = server_name
                data["schema_name"] = local_schema
                data["fdw_name"] = "file_fdw"
                fdw_name = "file_fdw"

            db.add_data_source(
                connection_id=connection_id,
                source_type=code,
                data=data,
                server_name=server_name,
                fdw_name=fdw_name
            )

            # Ensure parent item path is saved for auto-expansion
            self.manager._save_tree_expansion_state()
            self.manager.load_data()
            self.manager._restore_tree_expansion_state()
            self.manager.refresh_all_comboboxes()

            # Refresh Schema Tree for the current UDS connection
            current_index = self.manager.tree.currentIndex()
            if current_index.isValid():
                self.manager.item_clicked(current_index, skip_restore=False)

            self.manager.status.showMessage(f"Data Source '{data.get('name')}' created successfully.", 4000)

        except Exception as e:
            QMessageBox.critical(
                self.manager,
                "Error",
                f"Failed to create data source:\n{e}"
            )

    def edit_data_source(self, item):
        ds_data = item.data(Qt.ItemDataRole.UserRole)
        if not ds_data:
            return

        source_type = (ds_data.get("source_type") or "POSTGRES").upper()
        host_conn_data = ds_data.get("conn_data") or getattr(self.manager, "active_postgres_conn", None)

        if source_type == "POSTGRES":
            dialog = PostgresDataSourceDialog(self.manager, is_editing=True, conn_data=ds_data)
        elif source_type == "SQLITE":
            dialog = SQLiteDataSourceDialog(self.manager, is_editing=True, conn_data=ds_data)
        elif source_type == "ORACLE":
            dialog = OracleDataSourceDialog(self.manager, conn_data=ds_data)
        elif source_type == "CSV":
            dialog = CSVDataSourceDialog(self.manager, conn_data=ds_data)
        elif source_type == "SERVICENOW":
            dialog = ServiceNowDataSourceDialog(self.manager, conn_data=ds_data)
        else:
            QMessageBox.warning(self.manager, "Unsupported Type", f"{source_type} editing not supported")
            return


        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_data = dialog.getData()

        try:
            server_name = ds_data.get("server_name")
            if source_type == "POSTGRES" and host_conn_data:
                server_name, local_schema = db.edit_postgres_fdw_source(host_conn_data, new_data)
                new_data["server_name"] = server_name
                new_data["schema_name"] = local_schema
            elif source_type == "SQLITE" and host_conn_data:
                server_name, local_schema, _ = db.sync_sqlite_fdw_schema(host_conn_data, new_data)
                new_data["server_name"] = server_name
                new_data["schema_name"] = local_schema

            db.update_data_source(ds_data.get("id"), new_data, server_name=server_name)

            self.manager._save_tree_expansion_state()
            self.manager.load_data()
            self.manager._restore_tree_expansion_state()
            self.manager.refresh_all_comboboxes()

            # Refresh Schema Tree for active connection
            if hasattr(self.manager, "active_postgres_conn") and self.manager.active_postgres_conn:
                active_conn_id = self.manager.active_postgres_conn.get("id")
                for row in range(self.manager.model.rowCount()):
                    t_item = self.manager.model.item(row, 0)
                    if t_item:
                        for g_row in range(t_item.rowCount()):
                            g_item = t_item.child(g_row, 0)
                            if g_item:
                                for c_row in range(g_item.rowCount()):
                                    c_item = g_item.child(c_row, 0)
                                    c_data = c_item.data(Qt.ItemDataRole.UserRole)
                                    if c_data and c_data.get("id") == active_conn_id:
                                        p_idx = self.manager.proxy_model.mapFromSource(c_item.index())
                                        if p_idx.isValid():
                                            self.manager.tree.setCurrentIndex(p_idx)
                                            self.manager.item_clicked(p_idx, skip_restore=False)
                                            break
            else:
                current_index = self.manager.tree.currentIndex()
                if current_index.isValid():
                    self.manager.item_clicked(current_index, skip_restore=False)

            self.manager.status.showMessage(f"Data Source '{new_data.get('name')}' updated successfully.", 4000)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to update data source:\n{e}")

    def delete_data_source(self, item):
        ds_data = item.data(Qt.ItemDataRole.UserRole)
        if not ds_data:
            return

        ds_id = ds_data.get("id")
        ds_name = item.text()

        msg = QMessageBox(self.manager)
        msg.setWindowTitle("Delete Data Source")
        msg.setText(f"Are you sure you want to delete Data Source '{ds_name}'?")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )
        msg.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        if msg.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            host_conn_data = ds_data.get("conn_data") or getattr(self.manager, "active_postgres_conn", None)
            server_name = ds_data.get("server_name")
            schema_name = ds_data.get("schema_name")

            if host_conn_data and server_name:
                db.drop_postgres_fdw_source(host_conn_data, server_name, schema_name)

            db.delete_data_source(ds_id)

            self.manager._save_tree_expansion_state()
            self.manager.load_data()
            self.manager._restore_tree_expansion_state()
            self.manager.refresh_all_comboboxes()

            # Refresh Schema Tree for current connection
            current_index = self.manager.tree.currentIndex()
            if current_index.isValid():
                self.manager.item_clicked(current_index, skip_restore=False)

            self.manager.status.showMessage(f"Data Source '{ds_name}' deleted.", 3000)

        except Exception as e:
            QMessageBox.critical(self.manager, "Error", f"Failed to delete data source:\n{e}")

    def sync_foreign_schema(self, item):
        """Re-runs IMPORT FOREIGN SCHEMA to sync remote tables for the selected data source/foreign server."""
        if not item:
            return
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data or not isinstance(item_data, dict):
            return

        ds_data = item_data.get("ds_data") or item_data
        host_conn_data = item_data.get("conn_data") or ds_data.get("conn_data") or getattr(self.manager, "active_postgres_conn", None)

        if not host_conn_data:
            QMessageBox.warning(self.manager, "Sync Schema", "Could not identify host database connection.")
            return

        ds_name = ds_data.get("name") or ds_data.get("display_name") or ds_data.get("short_name") or item.text()
        source_type = (ds_data.get("source_type") or "POSTGRES").upper()

        self.manager.status.showMessage(f"Syncing foreign schema for '{ds_name}'...", 4000)
        try:
            if source_type == "SQLITE":
                server_name, local_schema, count = db.sync_sqlite_fdw_schema(host_conn_data, ds_data)
            else:
                server_name, local_schema, count = db.sync_postgres_fdw_schema(host_conn_data, ds_data)

            # Refresh Schema Tree for current connection
            current_index = self.manager.tree.currentIndex()
            if current_index.isValid():
                self.manager.item_clicked(current_index, skip_restore=False)

            self.manager.status.showMessage(f"Foreign schema for '{ds_name}' synced successfully ({count} foreign tables).", 5000)
            QMessageBox.information(
                self.manager,
                "Sync Complete",
                f"Foreign schema synchronization completed for '{ds_name}'.\n\n"
                f"• Server: {server_name}\n"
                f"• Schema: {local_schema}\n"
                f"• Imported Foreign Tables: {count}"
            )
        except Exception as e:
            self.manager.status.showMessage(f"Failed to sync foreign schema: {e}", 5000)
            QMessageBox.critical(self.manager, "Sync Failed", f"Failed to sync foreign schema for '{ds_name}':\n{e}")
                
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
        msg.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)

        msg.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        label = QLabel(details_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMinimumSize(400, 200)
        msg.layout().addWidget(label, 0, 1)

        msg.exec()

    def add_connection_group(self, parent_item):
        dialog = QDialog(self.manager)
        dialog.setWindowTitle("New Connection Group")
        dialog.setFixedSize(460, 220)
        dialog.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        dialog.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("New Connection Group")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Enter a group name for organizing connections.")
        subtitle_label.setObjectName("dialogSubtitle")

        name_input = QLineEdit()
        name_input.setPlaceholderText("Group name")

        save_btn = PrimaryButton("Create")
        cancel_btn = SecondaryButton("Cancel")

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
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                ToastNotification.show_toast(self.manager, f"✦  Group '{name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to add group:\n{e}")

    def edit_connection_group(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole + 1)
        current_name = item.text()

        dialog = QDialog(self.manager)
        dialog.setWindowTitle("Edit Connection Group")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        dialog.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        dialog.setFixedSize(460, 220)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("Edit Connection Group")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Update the name for this group.")
        subtitle_label.setObjectName("dialogSubtitle")

        name_input = QLineEdit()
        name_input.setText(current_name)
        name_input.setPlaceholderText("Group name")

        save_btn = PrimaryButton("Update")
        cancel_btn = SecondaryButton("Cancel")

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
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update group:\n{e}")

        save_btn.clicked.connect(_on_save)
        dialog.exec()

    def delete_connection_group(self, item):
        group_id = item.data(Qt.ItemDataRole.UserRole + 1)
        group_name = item.text()
        
        msg = QMessageBox(self.manager)
        msg.setWindowTitle("Delete Connection Group")
        msg.setText(f"Are you sure you want to delete the group '{group_name}'?\nThis will also delete ALL connections within this group.")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)

        msg.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection_group(group_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                ToastNotification.show_toast(self.manager, f"✦  Group '{group_name}' deleted successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to delete group:\n{e}")

    def add_new_connection_flow(self):
        selector = ConnectionTypeSelectorDialog(self.manager)
        if selector.exec() == QDialog.DialogCode.Accepted:
            type_info = selector.selected_type
            if not type_info:
                return
            
            code = type_info["code"].upper()
            type_id = type_info["id"]

            if code == "POSTGRES":
                dialog = PostgresConnectionDialog(self.manager, type_id=type_id)
            elif code == "SQLITE":
                dialog = SQLiteConnectionDialog(self.manager, type_id=type_id)
            elif code == "CSV":
                dialog = CSVConnectionDialog(self.manager, type_id=type_id)
            elif code == "SERVICENOW":
                dialog = ServiceNowConnectionDialog(self.manager, type_id=type_id)
            elif code in ("ORACLE", "ORACLE_DB", "ORACLE_FA") or code.startswith("ORACLE"):
                dialog = OracleConnectionDialog(self.manager, type_id=type_id)
            else:
                QMessageBox.warning(self.manager, "Not Supported", f"Connection type {code} is not yet supported.")
                return

            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.getData()
                group_id = data.get("connection_group_id")
                try:
                    conn_name = data.get("name", "Connection")
                    db.add_connection(data, group_id)
                    self.manager._save_tree_expansion_state()
                    self.manager.load_data()
                    self.manager._restore_tree_expansion_state()
                    self.manager.refresh_all_comboboxes()
                    ToastNotification.show_toast(
                        self.manager,
                        f"✦  '{conn_name}' created successfully!",
                        kind="success",
                    )
                except Exception as e:
                    QMessageBox.critical(self.manager, "Error", f"Failed to save connection:\n{e}")


    def edit_connection_type(self, item):
        type_id = item.data(Qt.ItemDataRole.UserRole + 1)
        current_name = item.text()
        current_code = item.data(Qt.ItemDataRole.UserRole)

        dialog = QDialog(self.manager)
        dialog.setWindowTitle("Edit Connection Type")
        dialog.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowTitleHint | 
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.CustomizeWindowHint
        )

        dialog.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        dialog.setFixedSize(460, 260)
        dialog.setStyleSheet(self.manager._get_dialog_style())

        title_label = QLabel("Edit Connection Type")
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel("Update the display name for this category.")
        subtitle_label.setObjectName("dialogSubtitle")
        
        name_input = QLineEdit()
        name_input.setText(current_name)
        name_input.setPlaceholderText("Display Name")
        
        code_input = QLineEdit()
        code_input.setText(current_code)
        code_input.setPlaceholderText("Type (e.g. SQLITE)")
        code_input.setReadOnly(True)
        code_input.setStyleSheet("background-color: #f0f0f0; color: #6b7280; border: 1px solid #d1d5db; border-radius: 6px; padding: 3px 8px;")

        save_btn = PrimaryButton("Update")
        cancel_btn = SecondaryButton("Cancel")

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
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                ToastNotification.show_toast(self.manager, f"✦  Type '{name}' updated successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update type:\n{e}")

        save_btn.clicked.connect(_on_save)
        dialog.exec()

    def delete_connection_type(self, item):
        type_id = item.data(Qt.ItemDataRole.UserRole + 1)
        type_name = item.text()
        
        msg = QMessageBox(self.manager)
        msg.setWindowTitle("Delete Connection Type")
        msg.setText(f"Are you sure you want to delete the type '{type_name}'?\nThis will also delete ALL groups and connections within this type.")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint)

        msg.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_connection_type(type_id)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                ToastNotification.show_toast(self.manager, f"✦  Type '{type_name}' deleted successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to delete type:\n{e}")

    def add_postgres_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
        
        dialog = PostgresConnectionDialog(self.manager, type_id=type_id, group_id=connection_group_id)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save PostgreSQL connection:\n{e}")

    def add_sqlite_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
        
        dialog = SQLiteConnectionDialog(self.manager, type_id=type_id, group_id=connection_group_id)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save SQLite connection:\n{e}")

    def add_oracle_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
        
        dialog = OracleConnectionDialog(self.manager, type_id=type_id, group_id=connection_group_id)
            
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save Oracle connection:\n{e}")


    def add_uds_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)

        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None

        dialog = UDSConnectionDialog(
            self.manager,
            type_id=type_id,
            group_id=connection_group_id
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()

            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")

                # Automatically enable essential FDW extensions (postgres_fdw, sqlite_fdw, oracle_fdw, file_fdw)
                try:
                    db.ensure_host_fdw_extensions(data)
                except Exception as ext_err:
                    print(f"Notice: Background FDW extension initialization notice: {ext_err}")

            except Exception as e:
                QMessageBox.critical(
                    self.manager,
                    "Error",
                    f"Failed to save Unified Data Source:\n{e}"
                )

    def edit_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        group_item = item.parent()
        group_id = group_item.data(Qt.ItemDataRole.UserRole + 1) if group_item else None
        type_item = group_item.parent() if group_item else None
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None

        if conn_data and conn_data.get("db_path"):
            dialog = SQLiteConnectionDialog(self.manager, conn_data=conn_data, type_id=type_id, group_id=group_id)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.getData()
                try:
                    conn_name = new_data.get("name", "Connection")
                    db.update_connection(new_data)
                    self._reload_and_expand_group(group_item)
                    ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")
                except Exception as e:
                    QMessageBox.critical(self.manager, "Error", f"Failed to update SQLite connection:\n{e}")

    def edit_pg_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return
            
        group_item = item.parent()
        group_id = group_item.data(Qt.ItemDataRole.UserRole + 1) if group_item else None
        type_item = group_item.parent() if group_item else None
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
            
        dialog = PostgresConnectionDialog(self.manager, is_editing=True, type_id=type_id, group_id=group_id)
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
                conn_name = new_data.get("name", "Connection")
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update PostgreSQL connection:\n{e}")

    def edit_oracle_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return

        group_item = item.parent()
        group_id = group_item.data(Qt.ItemDataRole.UserRole + 1) if group_item else None
        type_item = group_item.parent() if group_item else None
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None

        dialog = OracleConnectionDialog(self.manager, is_editing=True, type_id=type_id, group_id=group_id)
        dialog.name_input.setText(conn_data.get("name", ""))
        dialog.user_input.setText(conn_data.get("user", ""))
        dialog.password_input.setText(conn_data.get("password", ""))
        dialog.dsn_input.setText(conn_data.get("dsn", ""))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            new_data["id"] = conn_data.get("id")
            try:
                conn_name = new_data.get("name", "Connection")
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update Oracle connection:\n{e}")



    def add_servicenow_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
        
        dialog = ServiceNowConnectionDialog(self.manager, type_id=type_id, group_id=connection_group_id)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save ServiceNow connection:\n{e}")

   
    def edit_uds_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)

        if not conn_data:
            return

        group_item = item.parent()
        group_id = (
            group_item.data(Qt.ItemDataRole.UserRole + 1)
            if group_item else None
        )

        type_item = group_item.parent() if group_item else None
        type_id = (
            type_item.data(Qt.ItemDataRole.UserRole + 1)
            if type_item else None
        )

        dialog = UDSConnectionDialog(
            self.manager,
            is_editing=True,
            type_id=type_id,
            group_id=group_id
        )

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
                conn_name = new_data.get("name", "Connection")
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")

            except Exception as e:
                QMessageBox.critical(
                    self.manager,
                    "Error",
                    f"Failed to update Unified Data Source:\n{e}"
                )

    def edit_servicenow_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)
        if not conn_data:
            return

        group_item = item.parent()
        group_id = group_item.data(Qt.ItemDataRole.UserRole + 1) if group_item else None
        type_item = group_item.parent() if group_item else None
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None

        dialog = ServiceNowConnectionDialog(self.manager, conn_data=conn_data, type_id=type_id, group_id=group_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                conn_name = new_data.get("name", "Connection")
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update ServiceNow connection:\n{e}")

    def add_csv_connection(self, parent_item):
        connection_group_id = parent_item.data(Qt.ItemDataRole.UserRole + 1)
        type_item = parent_item.parent()
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None
        
        dialog = CSVConnectionDialog(self.manager, type_id=type_id, group_id=connection_group_id)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.getData()
            try:
                conn_name = data.get("name", "Connection")
                db.add_connection(data, connection_group_id)
                self._reload_and_expand_group(parent_item)
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' created successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to save CSV connection:\n{e}")

    def edit_csv_connection(self, item):
        conn_data = item.data(Qt.ItemDataRole.UserRole)

        if not conn_data or not conn_data.get("db_path"):
            QMessageBox.warning(self.manager, "Invalid", "This is not a CSV connection.")
            return

        group_item = item.parent()
        group_id = group_item.data(Qt.ItemDataRole.UserRole + 1) if group_item else None
        type_item = group_item.parent() if group_item else None
        type_id = type_item.data(Qt.ItemDataRole.UserRole + 1) if type_item else None

        dialog = CSVConnectionDialog(self.manager, conn_data=conn_data, type_id=type_id, group_id=group_id)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.getData()
            try:
                conn_name = new_data.get("name", "Connection")
                db.update_connection(new_data)
                self.manager._save_tree_expansion_state()
                self.manager.load_data()
                self.manager._restore_tree_expansion_state()
                self.manager.refresh_all_comboboxes()
                ToastNotification.show_toast(self.manager, f"✦  '{conn_name}' updated successfully!", kind="success")
            except Exception as e:
                QMessageBox.critical(self.manager, "Error", f"Failed to update CSV connection:\n{e}")
    
    
    
                
    