# dialogs/properties/trigger_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, 
    QMessageBox
)
from .base_properties import BasePropertiesDialog
from . import pg_queries

class TriggerPropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, trigger_name, parent=None):
        super().__init__(item_data, trigger_name, parent)
        self.trigger_name = trigger_name
        self.setWindowTitle(f"Trigger Properties - {self.trigger_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)

        self.name_edit = QLineEdit(self.trigger_name)
        self.name_edit.setReadOnly(True)

        self.table_edit = QLineEdit()
        self.table_edit.setReadOnly(True)

        self.schema_edit = QLineEdit()
        self.schema_edit.setReadOnly(True)

        self.status_edit = QLineEdit()
        self.status_edit.setReadOnly(True)
        
        self.comment_edit = QTextEdit()
        self.comment_edit.setReadOnly(True)
        self.comment_edit.setMaximumHeight(80)
        
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Table:", self.table_edit)
        gen_layout.addRow("Schema:", self.schema_edit)
        gen_layout.addRow("Status:", self.status_edit)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. Definition Tab
        self.definition_tab = QWidget()
        def_layout = QFormLayout(self.definition_tab)
        
        self.func_edit = QLineEdit()
        self.func_edit.setReadOnly(True)
        
        self.timing_edit = QLineEdit()
        self.timing_edit.setReadOnly(True)
        
        self.events_edit = QLineEdit()
        self.events_edit.setReadOnly(True)
        
        self.level_edit = QLineEdit()
        self.level_edit.setReadOnly(True)
        
        def_layout.addRow("Trigger Function:", self.func_edit)
        def_layout.addRow("Timing:", self.timing_edit)
        def_layout.addRow("Events:", self.events_edit)
        def_layout.addRow("Level:", self.level_edit)
        self.tab_widget.addTab(self.definition_tab, "Definition")

        # 3. SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        if self.db_type != 'postgres':
            return

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Fetch trigger details
            cursor.execute(pg_queries.GET_TRIGGER_DETAILS, (self.schema_name, self.trigger_name))
            res = cursor.fetchone()
            if res:
                name, table_name, schema_name, enabled, func_name, timing, events, level, definition, comment = res
                
                self.table_edit.setText(table_name)
                self.schema_edit.setText(schema_name)
                
                # Format enabled status (O=origin/enabled, D=disabled, A=always, R=replica)
                status_map = {
                    'O': 'Enabled (fires normally)',
                    't': 'Enabled',
                    'D': 'Disabled',
                    'A': 'Enabled (always)',
                    'R': 'Enabled (replica only)'
                }
                status_text = status_map.get(enabled, f"Unknown ({enabled})")
                self.status_edit.setText(status_text)
                
                self.func_edit.setText(func_name)
                self.timing_edit.setText(timing)
                self.events_edit.setText(events)
                self.level_edit.setText(level)
                self.comment_edit.setPlainText(comment or "")
                
                # SQL definition formatting
                if definition:
                    sql_text = f"-- Trigger: {self.trigger_name} on {schema_name}.{table_name}\n\n"
                    sql_text += f"{definition};"
                    self.sql_display.setText(sql_text)
                else:
                    self.sql_display.setText("-- Definition not found.")
            else:
                QMessageBox.warning(self, "Warning", "Trigger details could not be retrieved.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load trigger properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def save_properties(self):
        self.accept()
