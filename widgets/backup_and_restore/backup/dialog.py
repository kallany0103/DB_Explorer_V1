# widgets/backup_and_restore/backup/dialog.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
    QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, 
    QLabel, QComboBox, QCheckBox, QTabWidget, QWidget,
    QTreeWidget, QTreeWidgetItem, QSpinBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from datetime import datetime
import qtawesome as qta

class BackupDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.item_data = item_data or {}
        self.db_type = self.item_data.get("db_type", "postgres")
        self.object_type = self.item_data.get("type", "database") # 'database', 'schema', 'table'
        self.display_name = self.item_data.get("table_name") or self.item_data.get("schema_name") or self.item_data.get("database") or "backup"
        
        self.setWindowTitle(f"Backup - {self.display_name}")
        self.setMinimumWidth(650)
        self.resize(700, 550)
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # --- 1. General Tab ---
        general_tab = QWidget()
        self.tabs.addTab(general_tab, qta.icon("fa5s.file-alt", color="#555"), "General")
        general_layout = QFormLayout(general_tab)
        general_layout.setContentsMargins(15, 15, 15, 15)
        general_layout.setSpacing(10)
        
        # Output File
        self.filename_edit = QLineEdit()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        if self.db_type == "postgres":
            default_ext = ".backup"
        else:
            default_ext = ".db"
            
        home_dir = os.path.expanduser("~")
        desktop_dir = os.path.join(home_dir, "Desktop")
        if not os.path.exists(desktop_dir):
            desktop_dir = home_dir
            
        default_path = os.path.join(desktop_dir, f"{self.display_name}_{timestamp}{default_ext}")
        self.filename_edit.setText(default_path)
        
        browse_btn = QPushButton(qta.icon("fa5s.folder-open"), "")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self.browse_file)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.filename_edit)
        file_layout.addWidget(browse_btn)
        general_layout.addRow("Filename:", file_layout)
        
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

        # --- 2. Data Options Tab ---
        data_tab = QWidget()
        self.tabs.addTab(data_tab, qta.icon("fa5s.database", color="#555"), "Data Options")
        data_layout = QFormLayout(data_tab)
        data_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.content_combo = QComboBox()
            self.content_combo.addItems(["Both", "Only Data", "Only Schema"])
            self.content_combo.setCurrentText("Both")
            data_layout.addRow("Type of objects:", self.content_combo)
            
            data_layout.addRow(QLabel("<b>Do not save:</b>"))
            self.no_owner_check = QCheckBox("Owner")
            self.no_privs_check = QCheckBox("Privileges")
            self.no_tablespaces_check = QCheckBox("Tablespaces")
            
            data_layout.addRow("", self.no_owner_check)
            data_layout.addRow("", self.no_privs_check)
            data_layout.addRow("", self.no_tablespaces_check)

        # --- 3. Query Options Tab ---
        query_tab = QWidget()
        self.tabs.addTab(query_tab, qta.icon("fa5s.terminal", color="#555"), "Query Options")
        query_layout = QFormLayout(query_tab)
        query_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.clean_check = QCheckBox("Include DROP statements (Clean)")
            self.inserts_check = QCheckBox("Use INSERT commands")
            self.column_inserts_check = QCheckBox("Use Column Inserts")
            
            query_layout.addRow("", self.clean_check)
            query_layout.addRow("", self.inserts_check)
            query_layout.addRow("", self.column_inserts_check)

        # --- 4. Options Tab ---
        misc_tab = QWidget()
        self.tabs.addTab(misc_tab, qta.icon("fa5s.sliders-h", color="#555"), "Options")
        misc_layout = QFormLayout(misc_tab)
        misc_layout.setContentsMargins(15, 15, 15, 15)
        
        if self.db_type == "postgres":
            self.verbose_check = QCheckBox("Verbose messages")
            self.verbose_check.setChecked(True)
            self.no_comments_check = QCheckBox("Do not save comments")
            
            misc_layout.addRow("", self.verbose_check)
            misc_layout.addRow("", self.no_comments_check)
            
            self.compression_spin = QSpinBox()
            self.compression_spin.setRange(0, 9)
            self.compression_spin.setValue(0)
            misc_layout.addRow("Compression (0-9):", self.compression_spin)
            
        elif self.db_type == "sqlite":
            misc_layout.addRow(QLabel("SQLite backups are direct file copies."))

        # --- 5. Objects Tab (Postgres Only) ---
        if self.db_type == "postgres":
            self.objects_tab = QWidget()
            self.tabs.addTab(self.objects_tab, qta.icon("fa5s.sitemap", color="#555"), "Objects")
            objects_layout = QVBoxLayout(self.objects_tab)
            
            info_label = QLabel("Select schemas or tables to backup. If nothing is selected, the whole database will be backed up.")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 5px;")
            objects_layout.addWidget(info_label)
            
            self.objects_tree = QTreeWidget()
            self.objects_tree.setHeaderHidden(True)
            self.objects_tree.itemChanged.connect(self.handle_item_changed)
            objects_layout.addWidget(self.objects_tree)
            
            self.populate_objects_tree()

        # Footer Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Apply Styles
        self.setStyleSheet("""
            QDialog {
                background-color: #f6f8fb;
            }
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                background: white;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #eef1f6;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #555;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #d1d5db;
                border-bottom: none;
                color: #1f2937;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QSpinBox, QTreeWidget {
                min-height: 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background: white;
                padding-left: 6px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTreeWidget:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 15px;
                border: 1px solid #c4c9d4;
                background-color: #eef1f6;
                border-radius: 6px;
                color: #1f2937;
            }
            QPushButton:hover {
                background-color: #e3e8f2;
            }
            QPushButton[text="OK"] {
                background-color: #0078d4;
                color: white;
                border: 1px solid #006cbe;
                font-weight: bold;
            }
            QPushButton[text="OK"]:hover {
                background-color: #006cbe;
            }
        """)

    def handle_accept(self):
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
            cursor.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema' ORDER BY nspname")
            schemas = [row[0] for row in cursor.fetchall()]
            
            for schema in schemas:
                schema_item = QTreeWidgetItem(self.objects_tree)
                schema_item.setText(0, schema)
                schema_item.setData(0, Qt.UserRole, {"type": "schema", "name": schema})
                schema_item.setFlags(schema_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                schema_item.setCheckState(0, Qt.Unchecked)
                
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
        self.objects_tree.blockSignals(True)
        state = item.checkState(column)
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
            selected = []
            root = self.objects_tree.invisibleRootItem()
            for i in range(root.childCount()):
                schema_item = root.child(i)
                if schema_item.checkState(0) == Qt.Checked:
                    selected.append(schema_item.data(0, Qt.UserRole))
                elif schema_item.checkState(0) == Qt.PartiallyChecked:
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
                "no_tablespaces": self.no_tablespaces_check.isChecked(),
                "clean": self.clean_check.isChecked(),
                "inserts": self.inserts_check.isChecked(),
                "column_inserts": self.column_inserts_check.isChecked(),
                "verbose": self.verbose_check.isChecked(),
                "no_comments": self.no_comments_check.isChecked(),
                "compress": self.compression_spin.value(),
                "selected_objects": selected
            })
            
        return opts
