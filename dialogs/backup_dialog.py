# dialogs/backup_dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, 
    QLabel, QComboBox, QCheckBox, QTabWidget, QWidget,
    QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from datetime import datetime

class BackupDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.item_data = item_data or {}
        self.db_type = self.item_data.get("db_type", "postgres")
        self.object_type = self.item_data.get("type", "database") # 'database', 'schema', 'table'
        self.display_name = self.item_data.get("table_name") or self.item_data.get("schema_name") or self.item_data.get("database") or "backup"
        
        self.setWindowTitle(f"Backup - {self.display_name}")
        self.setMinimumWidth(550)
        self.resize(600, 450)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- General Tab ---
        general_tab = QWidget()
        self.tabs.addTab(general_tab, "General")
        general_layout = QFormLayout(general_tab)
        
        # Output File
        self.filename_edit = QLineEdit()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if self.db_type == "postgres":
            default_ext = ".backup" # Default to Custom format extension
        else:
            default_ext = ".db"
            
        home_dir = os.path.expanduser("~")
        desktop_dir = os.path.join(home_dir, "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = home_dir
            
        default_path = os.path.join(desktop_dir, f"{self.display_name}_{timestamp}{default_ext}")
        self.filename_edit.setText(default_path)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.filename_edit)
        file_layout.addWidget(browse_btn)
        general_layout.addRow("Filename:", file_layout)
        
        # Format (Postgres Specific)
        if self.db_type == "postgres":
            self.format_combo = QComboBox()
            self.format_combo.addItems(["Custom", "Plain", "Tar", "Directory"])
            self.format_combo.setCurrentText("Custom")
            self.format_combo.currentTextChanged.connect(self.update_extension)
            general_layout.addRow("Format:", self.format_combo)
            
            self.encoding_combo = QComboBox()
            self.encoding_combo.addItems(["UTF8", "SQL_ASCII", "LATIN1"])
            self.encoding_combo.setEditable(True)
            general_layout.addRow("Encoding:", self.encoding_combo)
            
            self.role_edit = QLineEdit()
            general_layout.addRow("Role Name:", self.role_edit)
        
        # --- Options Tab ---
        options_tab = QWidget()
        self.tabs.addTab(options_tab, "Options")
        options_layout = QFormLayout(options_tab)
        
        if self.db_type == "postgres":
            # Type of objects
            self.content_combo = QComboBox()
            self.content_combo.addItems(["Only Data", "Only Schema", "Both"])
            self.content_combo.setCurrentText("Both")
            options_layout.addRow("Type of objects:", self.content_combo)
            
            self.no_owner_check = QCheckBox("Don't save owner")
            self.no_privs_check = QCheckBox("Don't save privileges")
            self.clean_check = QCheckBox("Include DROP statements (Clean)")
            self.inserts_check = QCheckBox("Use INSERT commands")
            
            options_layout.addRow("", self.no_owner_check)
            options_layout.addRow("", self.no_privs_check)
            options_layout.addRow("", self.clean_check)
            options_layout.addRow("", self.inserts_check)
            
        elif self.db_type == "sqlite":
            options_layout.addRow(QLabel("SQLite backups are direct file copies."))
        
        # --- Objects Tab (Postgres Only) ---
        if self.db_type == "postgres":
            self.objects_tab = QWidget()
            self.tabs.addTab(self.objects_tab, "Objects")
            objects_layout = QVBoxLayout(self.objects_tab)
            
            info_label = QLabel("Select schemas or tables to backup. If nothing is selected, the whole database will be backed up.")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 5px;")
            objects_layout.addWidget(info_label)
            
            self.objects_tree = QTreeWidget()
            self.objects_tree.setHeaderHidden(True)
            self.objects_tree.itemChanged.connect(self.handle_item_changed)
            objects_layout.addWidget(self.objects_tree)
            
            # Populate lazily if needed, but for now we'll do it on init if we have conn_data
            self.populate_objects_tree()
        
        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def handle_accept(self):
        # Ensure extension is present if missing
        path = self.filename_edit.text().strip()
        if not path:
            return

        if self.db_type == "postgres":
            _, ext = os.path.splitext(path)
            if not ext:
                format_text = self.format_combo.currentText()
                ext_map = {"Plain": ".sql", "Custom": ".backup", "Tar": ".tar"}
                new_ext = ext_map.get(format_text, "")
                if new_ext:
                    self.filename_edit.setText(path + new_ext)
        
        self.accept()

    def browse_file(self):
        file_filter = "Backup Files (*.backup *.sql *.tar);;All Files (*)"
        path, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.filename_edit.text(), file_filter)
        if path:
            self.filename_edit.setText(path)

    def update_extension(self, format_text):
        path = self.filename_edit.text()
        base, _ = os.path.splitext(path)
        if format_text == "Plain":
            self.filename_edit.setText(base + ".sql")
        elif format_text == "Custom":
            self.filename_edit.setText(base + ".backup")
        elif format_text == "Tar":
            self.filename_edit.setText(base + ".tar")
        # Directory doesn't strictly need extension but user might prefer none

    def populate_objects_tree(self):
        conn_data = self.item_data.get("conn_data")
        if not conn_data or self.db_type != "postgres":
            return
            
        import db
        try:
            conn = db.create_postgres_connection(
                host=conn_data["host"],
                database=conn_data["database"],
                user=conn_data["user"],
                password=conn_data["password"],
                port=int(conn_data.get("port", 5432))
            )
            if not conn:
                return
                
            cursor = conn.cursor()
            
            # Fetch Schemas
            cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY nspname")
            schemas = [row[0] for row in cursor.fetchall()]
            
            for schema in schemas:
                schema_item = QTreeWidgetItem(self.objects_tree)
                schema_item.setText(0, schema)
                schema_item.setData(0, Qt.UserRole, {"type": "schema", "name": schema})
                schema_item.setFlags(schema_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                schema_item.setCheckState(0, Qt.Unchecked)
                
                # Fetch Tables for this schema
                cursor.execute("""
                    SELECT tablename FROM pg_tables WHERE schemaname = %s
                    UNION
                    SELECT viewname FROM pg_views WHERE schemaname = %s
                    ORDER BY 1
                """, (schema, schema))
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    table_item = QTreeWidgetItem(schema_item)
                    table_item.setText(0, table)
                    table_item.setData(0, Qt.UserRole, {"type": "table", "schema": schema, "name": table})
                    table_item.setFlags(table_item.flags() | Qt.ItemIsUserCheckable)
                    table_item.setCheckState(0, Qt.Unchecked)
            
            conn.close()
        except Exception as e:
            print(f"Error populating objects tree: {e}")

    def handle_item_changed(self, item, column):
        # Prevent recursion while we update children
        self.objects_tree.blockSignals(True)
        
        state = item.checkState(column)
        
        # If a schema (parent) is changed, update all its tables (children)
        for i in range(item.childCount()):
            item.child(i).setCheckState(column, state)
            
        self.objects_tree.blockSignals(False)

    def get_options(self):
        opts = {
            "filename": self.filename_edit.text(),
            "db_type": self.db_type,
            "object_type": self.object_type,
        }
        
        if self.db_type == "postgres":
            # Get selected objects
            selected = []
            root = self.objects_tree.invisibleRootItem()
            for i in range(root.childCount()):
                schema_item = root.child(i)
                if schema_item.checkState(0) == Qt.Checked:
                    # Entire schema selected
                    selected.append(schema_item.data(0, Qt.UserRole))
                elif schema_item.checkState(0) == Qt.PartiallyChecked:
                    # Specific tables selected
                    for j in range(schema_item.childCount()):
                        table_item = schema_item.child(j)
                        if table_item.checkState(0) == Qt.Checked:
                            selected.append(table_item.data(0, Qt.UserRole))
            
            opts.update({
                "format": self.format_combo.currentText().lower(),
                "encoding": self.encoding_combo.currentText(),
                "role": self.role_edit.text().strip(),
                "content": self.content_combo.currentText(),
                "no_owner": self.no_owner_check.isChecked(),
                "no_privileges": self.no_privs_check.isChecked(),
                "clean": self.clean_check.isChecked(),
                "inserts": self.inserts_check.isChecked(),
                "selected_objects": selected
            })
            
        return opts
