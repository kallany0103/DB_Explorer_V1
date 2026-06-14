# dialogs/properties/table_properties.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QTextEdit, 
    QTableView, QHeaderView, QAbstractItemView, QMessageBox, QLabel, QPushButton,
    QHBoxLayout, QToolButton, QStyledItemDelegate
)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt
from .base_properties import BasePropertiesDialog
from . import pg_queries

class DataTypeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data_types = [
            "integer", "bigint", "smallint", "boolean", "character varying", "character",
            "text", "date", "timestamp", "timestamp without time zone", "timestamp with time zone",
            "time", "time without time zone", "numeric", "double precision", "real",
            "json", "jsonb", "uuid", "bytea", "serial", "bigserial", "smallserial"
        ]

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(self.data_types)
        editor.setEditable(True)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setCurrentText(value)

    def setModelData(self, editor, model, index):
        value = editor.currentText()
        model.setData(index, value, Qt.ItemDataRole.EditRole)

class LeftAlignedHeaderModel(QStandardItemModel):
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.TextAlignmentRole and orientation == Qt.Orientation.Horizontal:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return super().headerData(section, orientation, role)

class TablePropertiesDialog(BasePropertiesDialog):
    def __init__(self, item_data, table_name, parent=None):
        super().__init__(item_data, table_name, parent)
        self.table_name = table_name
        self.table_type = self.item_data.get("table_type", "TABLE").upper()
        self.is_view = "VIEW" in self.table_type
        self.is_mview = "MATERIALIZED VIEW" in self.table_type
        
        self.setWindowTitle(f"{self.table_type.title()} Properties - {self.table_name}")
        self.init_tabs()
        self.load_data()

    def init_tabs(self):
        # 1. General Tab
        self.general_tab = QWidget()
        gen_layout = QFormLayout(self.general_tab)
        self.name_edit = QLineEdit(self.table_name)
        self.owner_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setMaximumHeight(80)
        gen_layout.addRow("Name:", self.name_edit)
        gen_layout.addRow("Owner:", self.owner_combo)
        gen_layout.addRow("Comment:", self.comment_edit)
        self.tab_widget.addTab(self.general_tab, "General")

        # 2. Definition Tab (for Views)
        if self.is_view or self.is_mview:
            self.definition_tab = QWidget()
            def_layout = QVBoxLayout(self.definition_tab)
            self.definition_display = QTextEdit()
            self.definition_display.setReadOnly(True)
            self.definition_display.setStyleSheet("font-family: 'Consolas', monospace;")
            def_layout.addWidget(self.definition_display)
            self.tab_widget.addTab(self.definition_tab, "Definition")

        # 3. Columns Tab
        self.columns_tab = QWidget()
        col_layout = QVBoxLayout(self.columns_tab)
        self.columns_model = LeftAlignedHeaderModel()
        self.columns_model.setHorizontalHeaderLabels(["Name", "Data Type", "PK", "Not Null", "Default", "Comment"])
        self.columns_view = QTableView()
        self.columns_view.setModel(self.columns_model)
        self.columns_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.columns_view.setItemDelegateForColumn(1, DataTypeDelegate(self.columns_view))
        col_layout.addWidget(self.columns_view)
        self.tab_widget.addTab(self.columns_tab, "Columns")

        # 4. Constraints Tab (not for regular views)
        if not self.is_view or self.is_mview:
            self.constraints_tab = QWidget()
            cons_layout = QVBoxLayout(self.constraints_tab)
            self.constraints_model = LeftAlignedHeaderModel()
            self.constraints_model.setHorizontalHeaderLabels(["Name", "Type", "Definition"])
            self.constraints_view = QTableView()
            self.constraints_view.setModel(self.constraints_model)
            self.constraints_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            cons_layout.addWidget(self.constraints_view)
            self.tab_widget.addTab(self.constraints_tab, "Constraints")

        # 5. Security Tab (Postgres only)
        if self.db_type == 'postgres':
            self.security_tab = QWidget()
            sec_layout = QVBoxLayout(self.security_tab)
            self.security_model = LeftAlignedHeaderModel()
            self.security_model.setHorizontalHeaderLabels(["Grantee", "Privileges", "Grantor"])
            self.security_view = QTableView()
            self.security_view.setModel(self.security_model)
            self.security_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            sec_layout.addWidget(self.security_view)
            self.tab_widget.addTab(self.security_tab, "Security")

        # 6. SQL Tab
        self.sql_tab = self._create_sql_tab()
        self.tab_widget.addTab(self.sql_tab, "SQL")

    def load_data(self):
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if self.db_type == 'postgres':
                # 1. Fetch General Details
                cursor.execute(pg_queries.GET_TABLE_DETAILS, (self.schema_name, self.table_name))
                res = cursor.fetchone()
                if res:
                    oid, owner, schema, comment, relkind, *rest = res
                    self.comment_edit.setPlainText(comment or "")
                    self.original_owner = owner
                    
                    # 2. Definition for Views
                    if relkind in ('v', 'm'):
                        cursor.execute("SELECT pg_get_viewdef(c.oid, true) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relname = %s", (self.schema_name, self.table_name))
                        def_res = cursor.fetchone()
                        if def_res:
                            self.definition_display.setPlainText(def_res[0])

                # Fetch roles
                cursor.execute(pg_queries.GET_ROLES)
                roles = [r[0] for r in cursor.fetchall()]
                self.owner_combo.addItems(roles)
                if hasattr(self, 'original_owner'):
                    self.owner_combo.setCurrentText(self.original_owner)

                # 3. Fetch Columns
                cursor.execute(pg_queries.GET_TABLE_COLUMNS, (self.schema_name, self.table_name))
                for row in cursor.fetchall():
                    name_item = QStandardItem(str(row[0]) if row[0] is not None else "")
                    type_item = QStandardItem(str(row[1]) if row[1] is not None else "")
                    
                    pk_item = QStandardItem()
                    pk_item.setCheckable(True)
                    pk_item.setEditable(False)
                    pk_item.setCheckState(Qt.CheckState.Checked if row[2] else Qt.CheckState.Unchecked)
                    
                    not_null_item = QStandardItem()
                    not_null_item.setCheckable(True)
                    not_null_item.setEditable(False)
                    not_null_item.setCheckState(Qt.CheckState.Checked if not row[3] else Qt.CheckState.Unchecked)
                    
                    default_item = QStandardItem(str(row[4]) if row[4] is not None else "")
                    comment_item = QStandardItem(str(row[5]) if row[5] is not None else "")
                    
                    self.columns_model.appendRow([name_item, type_item, pk_item, not_null_item, default_item, comment_item])

                # 4. Fetch Constraints
                if not self.is_view or self.is_mview:
                    cursor.execute(pg_queries.GET_TABLE_CONSTRAINTS, (self.schema_name, self.table_name))
                    for row in cursor.fetchall():
                        items = [QStandardItem(str(c)) for c in row]
                        self.constraints_model.appendRow(items)

                # 5. Fetch Security
                cursor.execute(pg_queries.GET_TABLE_PRIVILEGES, (self.schema_name, self.table_name))
                for row in cursor.fetchall():
                    items = [QStandardItem(str(c)) for c in row]
                    self.security_model.appendRow(items)

                # 6. Generate SQL
                self._generate_sql_postgres(cursor)

            elif self.db_type == 'sqlite':
                # Simpler SQLite loading
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (self.table_name,))
                row = cursor.fetchone()
                if row:
                    self.sql_display.setText(row[0] + ";")
                
                # Fetch columns
                cursor.execute(f"PRAGMA table_info('{self.table_name}')")
                for row in cursor.fetchall():
                    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
                    name_item = QStandardItem(str(row[1]))
                    type_item = QStandardItem(str(row[2]))
                    
                    pk_item = QStandardItem()
                    pk_item.setCheckable(True)
                    pk_item.setEditable(False)
                    pk_item.setCheckState(Qt.CheckState.Checked if row[5] else Qt.CheckState.Unchecked)
                    
                    not_null_item = QStandardItem()
                    not_null_item.setCheckable(True)
                    not_null_item.setEditable(False)
                    not_null_item.setCheckState(Qt.CheckState.Checked if row[3] else Qt.CheckState.Unchecked)
                    
                    default_item = QStandardItem(str(row[4]) if row[4] is not None else "")
                    comment_item = QStandardItem("")
                    
                    self.columns_model.appendRow([name_item, type_item, pk_item, not_null_item, default_item, comment_item])

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load table properties:\n{e}")
        finally:
            if conn:
                conn.close()

    def _generate_sql_postgres(self, cursor):
        # This is a simplified version of DDL generation
        # In a real app, you might use pg_dump or a more complex library
        sql = f"-- DDL for {self.table_type} {self.schema_name}.{self.table_name}\n\n"
        
        if self.is_view:
            sql += f"CREATE OR REPLACE VIEW {self.schema_name}.{self.table_name} AS\n"
            sql += self.definition_display.toPlainText()
        elif self.is_mview:
            sql += f"CREATE MATERIALIZED VIEW {self.schema_name}.{self.table_name} AS\n"
            sql += self.definition_display.toPlainText()
        else:
            sql += f"CREATE TABLE {self.schema_name}.{self.table_name} (\n"
            cols = []
            for row in range(self.columns_model.rowCount()):
                name = self.columns_model.item(row, 0).text()
                dtype = self.columns_model.item(row, 1).text()
                null = " NOT NULL" if self.columns_model.item(row, 2).text() == "False" else ""
                cols.append(f"    {name} {dtype}{null}")
            sql += ",\n".join(cols)
            sql += "\n);"

        self.sql_display.setText(sql)

    def save_properties(self):
        # Implementation for saving changes
        self.accept()
