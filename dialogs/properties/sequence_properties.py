# dialogs/properties/sequence_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QTableView, QHeaderView, QMessageBox, QCheckBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from .base_properties import BasePropertiesDialog
from . import pg_queries

class SequencePropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, sequence_name, parent=None):
        super().__init__(item_data, sequence_name, parent)
        self.sequence_name = sequence_name
        self.setWindowTitle(f"Sequence Properties - {self.sequence_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.sequence_name)
        self.owner_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(80)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. Definition Tab
        self.definition_tab = QWidget()
        def_layout = QFormLayout(self.definition_tab)
        
        self.current_val_edit = QLineEdit()
        self.current_val_edit.setReadOnly(True)
        self.increment_edit = QLineEdit()
        self.increment_edit.setReadOnly(True)
        self.min_val_edit = QLineEdit()
        self.min_val_edit.setReadOnly(True)
        self.max_val_edit = QLineEdit()
        self.max_val_edit.setReadOnly(True)
        self.cache_edit = QLineEdit()
        self.cache_edit.setReadOnly(True)
        self.cycled_check = QCheckBox("Cycled")
        self.cycled_check.setEnabled(False)
        
        def_layout.addRow("Increment By:", self.increment_edit)
        def_layout.addRow("Minimum Value:", self.min_val_edit)
        def_layout.addRow("Maximum Value:", self.max_val_edit)
        def_layout.addRow("Cache Size:", self.cache_edit)
        def_layout.addRow("Cycle?", self.cycled_check)
        
        self.tab_widget.addTab(self.definition_tab, "Definition")

        # 3. Security Tab (Postgres only)
        if self.db_type == 'postgres':
            self.security_tab = QWidget()
            sec_layout = QVBoxLayout(self.security_tab)
            self.security_model = QStandardItemModel()
            self.security_model.setHorizontalHeaderLabels(["Grantee", "Privileges", "Grantor"])
            self.security_view = QTableView()
            self.security_view.setModel(self.security_model)
            self.security_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            sec_layout.addWidget(self.security_view)
            self.tab_widget.addTab(self.security_tab, "Security")

        # 4. SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        if self.db_type != 'postgres':
            return

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Fetch Details
            cursor.execute(pg_queries.GET_SEQUENCE_DETAILS, (self.schema_name, self.sequence_name))
            res = cursor.fetchone()
            if res:
                owner, comment, start, min_v, max_v, inc, cache, cycled = res
                self.increment_edit.setText(str(inc))
                self.min_val_edit.setText(str(min_v))
                self.max_val_edit.setText(str(max_v))
                self.cache_edit.setText(str(cache))
                self.cycled_check.setChecked(bool(cycled))
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner

            # Fetch roles
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Fetch Security
            cursor.execute(pg_queries.GET_SEQUENCE_PRIVILEGES, (self.schema_name, self.sequence_name))
            for row in cursor.fetchall():
                items = [QStandardItem(str(c)) for c in row]
                self.security_model.appendRow(items)

            # 3. Generate SQL
            self._generate_sql(cursor)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load sequence properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self, cursor):
        # Retrieve full DDL
        # For Sequences, we can construct it or use some system function if available (pg_get_sequencedef is not standard in old PG)
        # We'll construct a basic one
        try:
            sql = f"-- Sequence: {self.schema_name}.{self.sequence_name}\n\n"
            sql += f"CREATE SEQUENCE {self.schema_name}.{self.sequence_name}\n"
            sql += f"    INCREMENT BY {self.increment_edit.text()}\n"
            sql += f"    MINVALUE {self.min_val_edit.text()}\n"
            sql += f"    MAXVALUE {self.max_val_edit.text()}\n"
            sql += f"    CACHE {self.cache_edit.text()}"
            if self.cycled_check.isChecked():
                sql += "\n    CYCLE"
            sql += ";"
            
            if self.owner_combo.currentText():
                sql += f"\n\nALTER SEQUENCE {self.schema_name}.{self.sequence_name} OWNER TO {self.owner_combo.currentText()};"
                
            self.sql_display.setText(sql)
        except Exception as e:
            self.sql_display.setText(f"-- Error generating DDL: {e}")

    def save_properties(self):
        self.accept()
