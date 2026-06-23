# dialogs/properties/schema_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QTableView, QHeaderView, QAbstractItemView, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from .base_properties import BasePropertiesDialog
from . import pg_queries

class LeftAlignedHeaderModel(QStandardItemModel):
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.TextAlignmentRole and orientation == Qt.Orientation.Horizontal:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return super().headerData(section, orientation, role)

class SchemaPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, schema_name, parent=None):
        super().__init__(item_data, schema_name, parent)
        self.setWindowTitle(f"Schema Properties - {self.schema_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        self.name_edit = QLineEdit(self.schema_name)
        self.owner_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(100)
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # Security Tab
        self.security_tab = QWidget()
        sec_layout = QVBoxLayout(self.security_tab)
        self.security_model = LeftAlignedHeaderModel()
        self.security_model.setHorizontalHeaderLabels(["Grantee", "Privileges", "Grantor"])
        self.security_view = QTableView()
        self.security_view.setModel(self.security_model)
        self.security_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.security_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        sec_layout.addWidget(self.security_view)
        self.tab_widget.addTab(self.security_tab, "Security")

        # Default Privileges Tab
        self.default_privs_tab = QWidget()
        def_layout = QVBoxLayout(self.default_privs_tab)
        self.default_privs_model = LeftAlignedHeaderModel()
        self.default_privs_model.setHorizontalHeaderLabels(["Owner", "Object Type", "Privileges"])
        self.default_privs_view = QTableView()
        self.default_privs_view.setModel(self.default_privs_model)
        self.default_privs_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.default_privs_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        def_layout.addWidget(self.default_privs_view)
        self.tab_widget.addTab(self.default_privs_tab, "Default Privileges")

        # SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        if self.db_type != 'postgres':
            return

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Fetch General Details
            cursor.execute(pg_queries.GET_SCHEMA_DETAILS, (self.schema_name,))
            res = cursor.fetchone()
            if res:
                owner = res[0]
                comment = res[1]
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner
                self.original_comment = comment or ""
            else:
                self.original_owner = ""
                self.original_comment = ""

            # Fetch roles for combo
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Fetch Security
            cursor.execute(pg_queries.GET_SCHEMA_PRIVILEGES, (self.schema_name,))
            for grantee, privs, grantor in cursor.fetchall():
                self.security_model.appendRow([QStandardItem(grantee), QStandardItem(privs), QStandardItem(grantor)])

            # 3. Fetch Default Privileges
            cursor.execute(pg_queries.GET_DEFAULT_PRIVILEGES, (self.schema_name,))
            for d_owner, obj_type, privs in cursor.fetchall():
                self.default_privs_model.appendRow([QStandardItem(d_owner), QStandardItem(obj_type), QStandardItem(privs)])

            # 4. Generate SQL
            self._generate_sql(cursor)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load schema properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self, cursor):
        owner = self.owner_combo.currentText()
        comment = self.comment_edit.toPlainText().strip()
        
        sql = f'-- Schema: {self.schema_name}\n\n'
        sql += f'-- DROP SCHEMA IF EXISTS "{self.schema_name}";\n\n'
        sql += f'CREATE SCHEMA IF NOT EXISTS "{self.schema_name}"\n'
        sql += f'    AUTHORIZATION "{owner}";\n'
        
        if comment:
            escaped_comment = comment.replace("'", "''")
            sql += f'\nCOMMENT ON SCHEMA "{self.schema_name}"\n    IS \'{escaped_comment}\';\n'
        
        # Add privileges to SQL (commented for now as we don't have full GRANT generation yet)
        sql += "\n-- Check Security tab for detailed privileges\n"
        
        self.sql_display.setText(sql)

    def save_properties(self):
        if self.db_type != 'postgres':
            self.accept()
            return

        new_name = self.name_edit.text().strip()
        new_owner = self.owner_combo.currentText()
        new_comment = self.comment_edit.toPlainText().strip()

        queries = []
        if new_name != self.schema_name:
            queries.append(f'ALTER SCHEMA "{self.schema_name}" RENAME TO "{new_name}";')
            current_name = new_name
        else:
            current_name = self.schema_name

        if new_owner != getattr(self, 'original_owner', ''):
            queries.append(f'ALTER SCHEMA "{current_name}" OWNER TO "{new_owner}";')

        if new_comment != getattr(self, 'original_comment', ''):
            if new_comment:
                escaped_comment = new_comment.replace("'", "''")
                queries.append(f'COMMENT ON SCHEMA "{current_name}" IS \'{escaped_comment}\';')
            else:
                queries.append(f'COMMENT ON SCHEMA "{current_name}" IS NULL;')

        if not queries:
            self.accept()
            return

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            for q in queries:
                cursor.execute(q)
            conn.commit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save schema properties:\n{e}")
        finally:
            if conn:
                conn.close()
