# dialogs/properties/foreign_data_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QMessageBox, QLabel
)
from .base_properties import BasePropertiesDialog
from . import pg_queries

class FDWPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, fdw_name, parent=None):
        super().__init__(item_data, fdw_name, parent)
        self.fdw_name = fdw_name
        self.setWindowTitle(f"FDW Properties - {self.fdw_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.fdw_name)
        self.owner_combo = QComboBox()
        self.handler_edit = QLineEdit()
        self.handler_edit.setReadOnly(True)
        self.validator_edit = QLineEdit()
        self.validator_edit.setReadOnly(True)
        self.options_edit = QLineEdit()
        self.options_edit.setReadOnly(True)
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(80)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Handler:", self.handler_edit)
        gen_layout.addRow("Validator:", self.validator_edit)
        gen_layout.addRow("Options:", self.options_edit)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. SQL Tab
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
            cursor.execute(pg_queries.GET_FDW_DETAILS, (self.fdw_name,))
            res = cursor.fetchone()
            if res:
                name, owner, handler, validator, options, comment = res
                self.handler_edit.setText(handler or "-")
                self.validator_edit.setText(validator or "-")
                self.options_edit.setText(options or "")
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner

            # Fetch roles
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Generate SQL
            self._generate_sql()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load FDW properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self):
        sql = f"-- Foreign Data Wrapper: {self.fdw_name}\n\n"
        sql += f"CREATE FOREIGN DATA WRAPPER {self.fdw_name}"
        if self.handler_edit.text() != "-":
            sql += f"\n    HANDLER {self.handler_edit.text()}"
        if self.validator_edit.text() != "-":
            sql += f"\n    VALIDATOR {self.validator_edit.text()}"
        
        opts = self.options_edit.text()
        if opts:
            # Simple parsing for display, assume comma-separated
            sql += f"\n    OPTIONS ({opts})"
        sql += ";"
            
        self.sql_display.setText(sql)

    def save_properties(self):
        self.accept()

class ForeignServerPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, srv_name, parent=None):
        super().__init__(item_data, srv_name, parent)
        self.srv_name = srv_name
        self.setWindowTitle(f"Foreign Server Properties - {self.srv_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.name_edit = QLineEdit(self.srv_name)
        self.owner_combo = QComboBox()
        self.type_edit = QLineEdit()
        self.type_edit.setReadOnly(True)
        self.version_edit = QLineEdit()
        self.version_edit.setReadOnly(True)
        self.options_edit = QLineEdit()
        self.options_edit.setReadOnly(True)
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(80)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Type:", self.type_edit)
        gen_layout.addRow("Version:", self.version_edit)
        gen_layout.addRow("Options:", self.options_edit)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. SQL Tab
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
            cursor.execute(pg_queries.GET_FOREIGN_SERVER_DETAILS, (self.srv_name,))
            res = cursor.fetchone()
            if res:
                name, owner, srv_type, version, options, comment = res
                self.type_edit.setText(srv_type or "")
                self.version_edit.setText(version or "")
                self.options_edit.setText(options or "")
                self.comment_edit.setPlainText(comment or "")
                self.original_owner = owner

            # Fetch roles
            cursor.execute(pg_queries.GET_ROLES)
            roles = [r[0] for r in cursor.fetchall()]
            self.owner_combo.addItems(roles)
            if hasattr(self, 'original_owner'):
                self.owner_combo.setCurrentText(self.original_owner)

            # 2. Generate SQL
            self._generate_sql()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Foreign Server properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self):
        sql = f"-- Foreign Server: {self.srv_name}\n\n"
        sql += f"CREATE SERVER {self.srv_name}"
        if self.type_edit.text():
            sql += f"\n    TYPE '{self.type_edit.text()}'"
        if self.version_edit.text():
            sql += f"\n    VERSION '{self.version_edit.text()}'"
        
        # We need the FDW name for CREATE SERVER, usually stored in item_data if expanding
        fdw_name = self.item_data.get('fdw_name', 'fdw_name_here')
        sql += f"\n    FOREIGN DATA WRAPPER {fdw_name}"
        
        opts = self.options_edit.text()
        if opts:
            sql += f"\n    OPTIONS ({opts})"
        sql += ";"
            
        self.sql_display.setText(sql)

    def save_properties(self):
        self.accept()

class UserMappingPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, user_name, parent=None):
        super().__init__(item_data, user_name, parent)
        self.user_name = user_name
        self.setWindowTitle(f"User Mapping Properties - {self.user_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        
        self.user_edit = QLineEdit(self.user_name)
        self.user_edit.setReadOnly(True)
        self.server_edit = QLineEdit()
        self.server_edit.setReadOnly(True)
        self.options_edit = QLineEdit()
        self.options_edit.setReadOnly(True)
        
        gen_layout.addRow("User:", self.user_edit)
        gen_layout.addRow("Server:", self.server_edit)
        gen_layout.addRow("Options:", self.options_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        if self.db_type != 'postgres':
            return

        # User mappings are identified by user AND server
        server_name = self.item_data.get('server_name')
        if not server_name:
            # Try to get it from the tree if possible, but for now we expect it in item_data
            pass

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # 1. Fetch Details
            cursor.execute(pg_queries.GET_USER_MAPPING_DETAILS, (self.user_name, server_name))
            res = cursor.fetchone()
            if res:
                user, server, options = res
                self.server_edit.setText(server)
                self.options_edit.setText(options or "")

            # 2. Generate SQL
            self._generate_sql()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load User Mapping properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql(self):
        sql = f"-- User Mapping: {self.user_name} on {self.server_edit.text()}\n\n"
        sql += f"CREATE USER MAPPING FOR \"{self.user_name}\"\n"
        sql += f"    SERVER {self.server_edit.text()}"
        
        opts = self.options_edit.text()
        if opts:
            sql += f"\n    OPTIONS ({opts})"
        sql += ";"
            
        self.sql_display.setText(sql)

    def save_properties(self):
        self.accept()
