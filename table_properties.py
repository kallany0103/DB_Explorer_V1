# table_properties

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHBoxLayout, QPushButton, QMessageBox, QInputDialog, QFormLayout, QLabel, QComboBox, QCheckBox, 
    QLineEdit, QTextEdit, QGroupBox, QDialogButtonBox, QFrame, QSizePolicy, QTableView, QHeaderView, QStyle )
from PyQt6.QtGui import (
    QAction, QIcon, QStandardItemModel, QStandardItem, QFont, QMovie, QDesktopServices, QColor, QBrush, QPainter,
    QTextFormat, QPolygon
)
from functools import partial
from PyQt6.QtCore import Qt
import db


class ColumnEditDialog(QDialog):
    def __init__(self, db_type, column_data, parent=None):
        super().__init__(parent)
        self.db_type = db_type
        self.column_data = column_data
        self.setWindowTitle(f"Edit Column - {column_data.get('name', '')}")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit(column_data.get('name', ''))
        self.type_combo = QComboBox()
        self.length_edit = QLineEdit(str(column_data.get('length', '')))
        self.default_edit = QLineEdit(str(column_data.get('default', '')))
        self.not_null_check = QCheckBox()
        self.not_null_check.setChecked(column_data.get('not_null', False))

        layout.addRow("Name:", self.name_edit)
        layout.addRow("Data type:", self.type_combo)
        layout.addRow("Length/Precision:", self.length_edit)
        layout.addRow("Default value:", self.default_edit)
        layout.addRow("Not NULL?", self.not_null_check)

        self._populate_types()
        self.type_combo.setCurrentText(column_data.get('type', ''))

        if self.db_type == 'sqlite':
            self.type_combo.setEnabled(False)
            self.length_edit.setEnabled(False)
            self.default_edit.setEnabled(False)
            self.not_null_check.setEnabled(False)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def _populate_types(self):
        if self.db_type == 'postgres':
            types = [
                "bigint", "boolean", "character varying", "character", "date", "double precision",
                "integer", "json", "jsonb", "numeric", "real", "smallint", "text",
                "time", "timestamp", "uuid", "xml"
            ]
        else:  # SQLite
            types = ["TEXT", "NUMERIC", "INTEGER", "REAL", "BLOB"]

        self.type_combo.addItems(types)
        self.type_combo.setEditable(True)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "type": self.type_combo.currentText(),
            "length": self.length_edit.text(),
            "default": self.default_edit.text(),
            "not_null": self.not_null_check.isChecked()
        }


class TablePropertiesDialog(QDialog):
    def __init__(self, item_data, table_name, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.table_name = table_name
        self.conn_data = self.item_data['conn_data']
        self.db_type = self.item_data['db_type']
        self.schema_name = self.item_data.get('schema_name')
        self.qualified_table_name = f'"{self.schema_name}"."{self.table_name}"' if self.db_type == 'postgres' else f'"{self.table_name}"'

        self.setWindowTitle(f"Properties - {self.table_name}")
        self.setMinimumSize(850, 600)

        self.main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self.refresh_properties()

        button_box = QHBoxLayout()
        button_box.addStretch()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_box.addWidget(ok_button)
        self.main_layout.addLayout(button_box)

    # <<< MODIFIED >>> new method: UI refresh
    def refresh_properties(self):
        # Clear existing tabs
        while self.tab_widget.count() > 0:
            self.tab_widget.removeTab(0)

        try:
            general_tab = self._create_general_tab()
            columns_tab = self._create_columns_tab()
            constraints_tab = self._create_constraints_tab()

            self.tab_widget.addTab(general_tab, "General")
            self.tab_widget.addTab(columns_tab, "Columns")
            self.tab_widget.addTab(constraints_tab, "Constraints")
        except Exception as e:
            # If tabs are already gone, a simple label is fine
            if self.tab_widget.count() == 0:
                error_label = QLabel(f"Failed to load table properties:\n{e}")
                error_label.setWordWrap(True)
                self.main_layout.insertWidget(0, error_label)
            else:  # If error happens during creation, show it in the first tab
                error_label = QLabel(f"Failed to load table properties:\n{e}")
                error_label.setWordWrap(True)
                self.tab_widget.currentWidget().layout().addWidget(error_label)

    def _create_general_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(10)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        properties = {}
        if self.db_type == 'postgres':
            properties = self._fetch_postgres_general_properties()
        else:
            properties = self._fetch_sqlite_general_properties()
        self.name_field = QLineEdit(properties.get("Name", ""))
        self.name_field.setReadOnly(True)
        self.owner_combo = QComboBox()
        self.schema_field = QLineEdit(properties.get("Schema", ""))
        self.schema_field.setReadOnly(True)
        self.tablespace_combo = QComboBox()
        self.partitioned_check = QCheckBox()
        self.comment_edit = QTextEdit(properties.get("Comment", ""))
        if self.db_type == 'postgres':
            if "all_owners" in properties:
                self.owner_combo.addItems(properties.get("all_owners", []))
            if "all_tablespaces" in properties:
                self.tablespace_combo.addItems(
                    properties.get("all_tablespaces", []))
            self.owner_combo.setCurrentText(properties.get("Owner", ""))
            self.tablespace_combo.setCurrentText(
                properties.get("Table Space", "default"))
            self.partitioned_check.setChecked(
                properties.get("Is Partitioned", False))
        else:
            self.owner_combo.setEnabled(False)
            self.tablespace_combo.setEnabled(False)
            self.partitioned_check.setEnabled(False)
        layout.addRow("Name:", self.name_field)
        layout.addRow("Owner:", self.owner_combo)
        layout.addRow("Schema:", self.schema_field)
        layout.addRow("Tablespace:", self.tablespace_combo)
        layout.addRow("Partitioned table?:", self.partitioned_check)
        layout.addRow("Comment:", self.comment_edit)
        return widget

    def _create_tag_button(self, text):
        button = QPushButton(f"{text}  ×")
        button.setStyleSheet(
            "QPushButton { background-color: #e1e1e1; border: 1px solid #c1c1c1; border-radius: 4px; padding: 3px 6px; font-size: 9pt; text-align: center; } QPushButton:hover { background-color: #d1d1d1; } QPushButton:pressed { background-color: #c1c1c1; }")
        button.clicked.connect(lambda: self._remove_inheritance_tag(button))
        return button

    def _remove_inheritance_tag(self, button_to_remove):
        table_name = button_to_remove.text().split("  ×")[0]
        button_to_remove.deleteLater()
        current_items = [self.add_parent_combo.itemText(
            i) for i in range(self.add_parent_combo.count())]
        if table_name not in current_items:
            self.add_parent_combo.addItem(table_name)
            self.add_parent_combo.model().sort(0)

    def _add_inheritance_tag(self, index):
        table_to_add = self.add_parent_combo.itemText(index)
        if not table_to_add:
            return
        for i in range(self.inheritance_layout.count()):
            widget = self.inheritance_layout.itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.text().startswith(table_to_add):
                self.add_parent_combo.setCurrentIndex(0)
                return
        new_tag = self._create_tag_button(table_to_add)
        self.inheritance_layout.insertWidget(
            self.inheritance_layout.indexOf(self.add_parent_combo), new_tag)
        self.add_parent_combo.removeItem(index)
        self.add_parent_combo.setCurrentIndex(0)

    # <<< MODIFIED >>> Edit Column 
    def _edit_column(self, column_name):
        conn = None
        column_data = {}
        try:
            # Fetch current details for the specific column
            if self.db_type == 'postgres':
                pg_conn_data = {key: self.conn_data.get(
                    key) for key in ['host', 'port', 'database', 'user', 'password']}
                conn = db.create_postgres_connection(**pg_conn_data)
                cursor = conn.cursor()
                col_query = """
                    SELECT c.column_name, c.udt_name, c.character_maximum_length, c.numeric_precision,
                           c.is_nullable, c.column_default
                    FROM information_schema.columns AS c
                    WHERE c.table_schema = %s AND c.table_name = %s AND c.column_name = %s;
                """
                cursor.execute(col_query, (self.schema_name,
                               self.table_name, column_name))
                res = cursor.fetchone()
                if res:
                    column_data = {
                        "name": res[0], "type": res[1],
                        "length": res[2] if res[2] is not None else res[3],
                        "not_null": res[4] == "NO", "default": res[5] or ""
                    }
            else:  # SQLite
                conn = db.create_sqlite_connection(self.conn_data['db_path'])
                cursor = conn.cursor()
                cursor.execute(f'PRAGMA table_info("{self.table_name}");')
                for row in cursor.fetchall():
                    if row[1] == column_name:
                        column_data = {
                            "name": row[1], "type": row[2], "not_null": bool(row[3]),
                            "default": row[4] or "", "length": ""
                        }
                        break

            if not column_data:
                QMessageBox.critical(
                    self, "Error", f"Could not find details for column '{column_name}'.")
                return

            dialog = ColumnEditDialog(self.db_type, column_data, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_data = dialog.get_data()
                self._update_column_in_db(column_data, new_data)

        except Exception as e:
            QMessageBox.critical(
                self, "DB Error", f"Error editing column: {e}")
        finally:
            if conn:
                conn.close()

    def _update_column_in_db(self, old_data, new_data):
        queries = []
        if self.db_type == 'postgres':
            if old_data['name'] != new_data['name']:
                queries.append(
                    f'ALTER TABLE {self.qualified_table_name} RENAME COLUMN "{old_data["name"]}" TO "{new_data["name"]}";')

            type_str = new_data['type']
            if new_data['length'] and new_data['type'] in ['character varying', 'character', 'numeric']:
                type_str = f"{new_data['type']}({new_data['length']})"

            if old_data['type'] != new_data['type'] or str(old_data.get('length', '')) != new_data['length']:
                # Note: Type casting can be complex. This is a simplified approach.
                queries.append(
                    f'ALTER TABLE {self.qualified_table_name} ALTER COLUMN "{new_data["name"]}" TYPE {type_str} USING "{new_data["name"]}"::{type_str};')

            if old_data['not_null'] != new_data['not_null']:
                action = "SET NOT NULL" if new_data['not_null'] else "DROP NOT NULL"
                queries.append(
                    f'ALTER TABLE {self.qualified_table_name} ALTER COLUMN "{new_data["name"]}" {action};')

            if old_data['default'] != new_data['default']:
                action = f"SET DEFAULT '{new_data['default']}'" if new_data['default'] else "DROP DEFAULT"
                queries.append(
                    f'ALTER TABLE {self.qualified_table_name} ALTER COLUMN "{new_data["name"]}" {action};')

        elif self.db_type == 'sqlite':
            # SQLite only supports RENAME COLUMN easily.
            if old_data['name'] != new_data['name']:
                queries.append(
                    f'ALTER TABLE {self.qualified_table_name} RENAME COLUMN "{old_data["name"]}" TO "{new_data["name"]}";')

        if not queries:
            QMessageBox.information(
                self, "No Changes", "No changes were detected.")
            return

        conn = None
        try:
            if self.db_type == 'postgres':
                pg_conn_data = {key: self.conn_data.get(
                    key) for key in ['host', 'port', 'database', 'user', 'password']}
                conn = db.create_postgres_connection(**pg_conn_data)
            else:
                conn = db.create_sqlite_connection(self.conn_data['db_path'])

            cursor = conn.cursor()
            full_query = "\n".join(queries)
            cursor.execute(full_query)
            conn.commit()
            QMessageBox.information(
                self, "Success", "Column updated successfully.")
            self.refresh_properties()  # Refresh the view
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Query Error",
                                 f"Failed to update column:\n{e}")
        finally:
            if conn:
                conn.close()

    def _delete_column(self, column_name):
        reply = QMessageBox.question(
            self, "Delete Column", f"Are you sure you want to delete the column '{column_name}'?\nThis action cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        query = f'ALTER TABLE {self.qualified_table_name} DROP COLUMN "{column_name}";'
        conn = None
        try:
            if self.db_type == 'postgres':
                pg_conn_data = {key: self.conn_data.get(
                    key) for key in ['host', 'port', 'database', 'user', 'password']}
                conn = db.create_postgres_connection(**pg_conn_data)
            else:  # SQLite requires a more complex process not implemented here for safety
                QMessageBox.warning(
                    self, "Not Supported", "Deleting columns from SQLite tables is not directly supported via this tool.")
                return

            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            QMessageBox.information(
                self, "Success", f"Column '{column_name}' deleted successfully.")
            self.refresh_properties()
        except Exception as e:
            if conn:
                conn.rollback()
            QMessageBox.critical(self, "Query Error",
                                 f"Failed to delete column:\n{e}")
        finally:
            if conn:
                conn.close()

    def _create_columns_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 5, 0, 0)
        inheritance_group = QGroupBox("Inherited from table(s)")
        inheritance_frame = QFrame()
        inheritance_frame.setObjectName("inheritanceFrame")
        inheritance_frame.setStyleSheet(
            "#inheritanceFrame { border: 1px solid #a9a9a9; border-radius: 3px; }")
        self.inheritance_layout = QHBoxLayout(inheritance_frame)
        self.inheritance_layout.setContentsMargins(2, 2, 2, 2)
        self.inheritance_layout.setSpacing(6)
        group_layout = QVBoxLayout(inheritance_group)
        group_layout.addWidget(inheritance_frame)
        layout.addWidget(inheritance_group)
        if self.db_type == 'postgres':
            inherited_tables = self._fetch_postgres_inheritance()
            all_tables = self._fetch_all_connection_tables()
            possible_new_parents = sorted(
                [t for t in all_tables if t != self.qualified_table_name and t not in inherited_tables])
            for table_name in inherited_tables:
                tag = self._create_tag_button(table_name)
                self.inheritance_layout.addWidget(tag)
            self.add_parent_combo = QComboBox()
            self.add_parent_combo.addItems([""] + possible_new_parents)
            self.add_parent_combo.setMinimumWidth(200)
            self.add_parent_combo.setStyleSheet("QComboBox { border: none; }")
            self.add_parent_combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.add_parent_combo.activated.connect(self._add_inheritance_tag)
            self.inheritance_layout.addWidget(self.add_parent_combo)
            self.inheritance_layout.addStretch(0)
        else:
            inheritance_group.setEnabled(False)
        columns_group = QGroupBox("Columns")
        columns_layout = QVBoxLayout(columns_group)
        layout.addWidget(columns_group)
        table_view = QTableView()
        columns_layout.addWidget(table_view)
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(
            ['Edit', 'Delete', 'Name', 'Data type', 'Length/Precision', 'Scale', 'Not NULL?', 'Primary key?', 'Default'])
        table_view.setModel(model)
        table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        # Resize modes: icon columns fixed, name Stretch
        table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        table_view.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed)   # Edit
        table_view.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed)   # Delete
        table_view.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)  # Name
        table_view.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #e0e0e0; padding: 4px; }")

        # Header center + padding
        table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        table_view.horizontalHeader().setStretchLastSection(True)
        table_view.setColumnWidth(0, 56)
        table_view.setColumnWidth(1, 56)
        columns_data = self._fetch_postgres_columns(
        ) if self.db_type == 'postgres' else self._fetch_sqlite_columns()
        edit_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        delete_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogCancelButton)
        gray_brush = QBrush(QColor("gray"))
        for row_idx, row_data in enumerate(columns_data):
            is_local = row_data[7] if self.db_type == 'postgres' else True
            edit_item, delete_item = QStandardItem(""), QStandardItem("")
            name_text = f"{row_data[0]} (inherited)" if not is_local else str(
                row_data[0])
            name_item = QStandardItem(name_text)
            type_item, len_item, scale_item = QStandardItem(str(row_data[1])), QStandardItem(
                str(row_data[2])), QStandardItem(str(row_data[3]))
            default_item, not_null_item, pk_item = QStandardItem(
                str(row_data[6])), QStandardItem(""), QStandardItem("")
            all_items = [edit_item, delete_item, name_item, type_item,
                         len_item, scale_item, not_null_item, pk_item, default_item]
            if not is_local:
                for item in all_items:
                    item.setForeground(gray_brush)
                    flags = item.flags()
                    flags &= ~Qt.ItemFlag.ItemIsSelectable
                    item.setFlags(flags)
            edit_item.setEditable(False)
            delete_item.setEditable(False)
            not_null_item.setEditable(False)
            pk_item.setEditable(False)
            model.appendRow(all_items)
            edit_btn = QPushButton()
            edit_btn.setIcon(edit_icon)
            edit_btn.setFixedSize(22, 22)
            edit_btn.clicked.connect(partial(self._edit_column, row_data[0]))
            delete_btn = QPushButton()
            delete_btn.setIcon(delete_icon)
            delete_btn.setFixedSize(22, 22)
            delete_btn.clicked.connect(
                partial(self._delete_column, row_data[0]))
            if not is_local:
                edit_btn.setEnabled(False)
                delete_btn.setEnabled(False)
            table_view.setIndexWidget(model.index(row_idx, 0), edit_btn)
            table_view.setIndexWidget(model.index(row_idx, 1), delete_btn)
            is_not_null, is_pk = (row_data[4] == "✔"), (row_data[5] == "✔")
            not_null_switch, pk_switch = QCheckBox(), QCheckBox()
            not_null_switch.setChecked(is_not_null)
            not_null_switch.setEnabled(False)
            pk_switch.setChecked(is_pk)
            pk_switch.setEnabled(False)
            for col_idx, switch_widget in [(6, not_null_switch), (7, pk_switch)]:
                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.addWidget(switch_widget)
                h_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                h_layout.setContentsMargins(0, 0, 0, 0)
                table_view.setIndexWidget(
                    model.index(row_idx, col_idx), container)
        return widget

    # <<< MODIFIED >>> 
    def _create_constraints_tab(self):
        container_widget = QWidget()
        main_layout = QVBoxLayout(container_widget)
        main_layout.setContentsMargins(0, 5, 0, 0)
        constraints_tab_widget = QTabWidget()
        main_layout.addWidget(constraints_tab_widget)
        constraints_by_type = self._fetch_postgres_constraints(
        ) if self.db_type == 'postgres' else self._fetch_sqlite_constraints()
        tab_definitions = [
            ("Primary Key", 'PRIMARY KEY', ['Name', 'Columns']),
            ("Foreign Key", 'FOREIGN KEY', [
             'Name', 'Columns', 'Referenced Table', 'Referenced Columns']),
            ("Check", 'CHECK', ['Name', 'Definition']),
            ("Unique", 'UNIQUE', ['Name', 'Columns'])
        ]
        for title, key, headers in tab_definitions:
            data = constraints_by_type.get(key, [])
            table_view = QTableView()
            table_view.setEditTriggers(
                QAbstractItemView.EditTrigger.NoEditTriggers)
            table_view.setAlternatingRowColors(True)
            table_view.horizontalHeader().setStyleSheet(
                "QHeaderView::section { background-color: #e0e0e0; padding: 4px; }")
            table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

            # table_view 
            table_view.verticalHeader().setVisible(False)
            table_view.verticalHeader().setDefaultSectionSize(26)
            table_view.setWordWrap(False)

            model = QStandardItemModel()
            model.setHorizontalHeaderLabels(headers)
            table_view.setModel(model)

            for row_data in data:
                items = [QStandardItem(str(item)) for item in row_data]
                model.appendRow(items)

            for row in range(model.rowCount()):
                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

               # Header align + look
            table_view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

            
            for row in range(model.rowCount()):
                for col in range(model.columnCount()):
                    item = model.item(row, col)
                    if not item:
                        continue
                    if col == 0:  # Name
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    else:      
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Set resize modes for better display
            header = table_view.horizontalHeader()
            for col in range(model.columnCount()):
                header.setSectionResizeMode(
                    col, QHeaderView.ResizeMode.Interactive)
            # if model.columnCount() > 0:
            #     header.setSectionResizeMode(
            #         model.columnCount() - 1, QHeaderView.ResizeMode.Stretch)

            if model.columnCount() > 0:
                for c in range(model.columnCount()):
                    header.setSectionResizeMode(
                        c, QHeaderView.ResizeMode.Stretch)

            constraints_tab_widget.addTab(table_view, title)
        return container_widget

    def _fetch_sqlite_general_properties(self):
        return {"Name": self.table_name, "Owner": "N/A", "Schema": "main", "Table Space": "N/A", "Comment": "N/A"}

    def _fetch_all_connection_tables(self):
        tables = []
        if self.db_type != 'postgres':
            return tables
        conn = None
        try:
            pg_conn_data = {key: self.conn_data.get(
                key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            cursor.execute("SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast') AND table_type = 'BASE TABLE' ORDER BY table_schema, table_name;")
            tables = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            QMessageBox.critical(
                self, "DB Error", f"Error fetching connection tables:\n{e}")
        finally:
            if conn:
                conn.close()
        return tables

    def _fetch_postgres_inheritance(self):
        inherited_from = []
        conn = None
        try:
            pg_conn_data = {key: self.conn_data.get(
                key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            query = "SELECT pn.nspname || '.' || parent.relname FROM pg_inherits JOIN pg_class AS child ON pg_inherits.inhrelid = child.oid JOIN pg_namespace AS cns ON child.relnamespace = cns.oid JOIN pg_class AS parent ON pg_inherits.inhparent = parent.oid JOIN pg_namespace AS pn ON parent.relnamespace = pn.oid WHERE child.relname = %s AND cns.nspname = %s;"
            cursor.execute(query, (self.table_name, self.schema_name))
            inherited_from = [row[0] for row in cursor.fetchall()]
        finally:
            if conn:
                conn.close()
        return inherited_from

    def _fetch_postgres_general_properties(self):
        props = {"Name": self.table_name, "Schema": self.schema_name}
        conn = None
        try:
            pg_conn_data = {key: self.conn_data.get(
                key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            query = "SELECT u.usename as owner, ts.spcname as tablespace, d.description, c.relispartition FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace LEFT JOIN pg_user u ON u.usesysid = c.relowner LEFT JOIN pg_tablespace ts ON ts.oid = c.reltablespace LEFT JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = 0 WHERE n.nspname = %s AND c.relname = %s"
            cursor.execute(query, (self.schema_name, self.table_name))
            res = cursor.fetchone()
            if res:
                props["Owner"], props["Table Space"], props["Comment"], props[
                    "Is Partitioned"] = res[0] or "N/A", res[1] or "default", res[2] or "", res[3]
            cursor.execute(
                "SELECT rolname FROM pg_roles WHERE rolcanlogin = true ORDER BY rolname;")
            props["all_owners"] = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                "SELECT spcname FROM pg_tablespace ORDER BY spcname;")
            props["all_tablespaces"] = ["default"] + [row[0]
                                                      for row in cursor.fetchall()]
        finally:
            if conn:
                conn.close()
        return props

    def _fetch_sqlite_columns(self):
        columns = []
        conn = None
        try:
            conn = db.create_sqlite_connection(self.conn_data['db_path'])
            cursor = conn.cursor()
            cursor.execute(f'PRAGMA table_info("{self.table_name}");')
            pk_cols = {row[1] for row in cursor.fetchall() if row[5] > 0}
            cursor.execute(f'PRAGMA table_info("{self.table_name}");')
            for row in cursor.fetchall():
                columns.append([row[1], row[2], "", "", "✔" if row[3]
                               else "", "✔" if row[1] in pk_cols else "", row[4] or ""])
        finally:
            if conn:
                conn.close()
        return columns

    def _fetch_postgres_columns(self):
        columns = []
        conn = None
        try:
            pg_conn_data = {key: self.conn_data.get(
                key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            pk_query = "SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s AND tc.table_name = %s;"
            cursor.execute(pk_query, (self.schema_name, self.table_name))
            pk_columns = {row[0] for row in cursor.fetchall()}
            col_query = "SELECT c.column_name, c.udt_name, c.character_maximum_length, c.numeric_precision, c.numeric_scale, c.is_nullable, c.column_default, a.attislocal FROM information_schema.columns AS c JOIN pg_catalog.pg_class AS pc ON c.table_name = pc.relname JOIN pg_catalog.pg_namespace AS pn ON pc.relnamespace = pn.oid AND c.table_schema = pn.nspname JOIN pg_catalog.pg_attribute AS a ON a.attrelid = pc.oid AND a.attname = c.column_name WHERE c.table_schema = %s AND c.table_name = %s AND a.attnum > 0 AND NOT a.attisdropped ORDER BY c.ordinal_position;"
            cursor.execute(col_query, (self.schema_name, self.table_name))
            for row in cursor.fetchall():
                length_precision = row[2] if row[2] is not None else row[3]
                columns.append([row[0], row[1], length_precision or "", row[4] or "", "✔" if row[5]
                               == "NO" else "", "✔" if row[0] in pk_columns else "", row[6] or "", row[7]])
        finally:
            if conn:
                conn.close()
        return columns

    def _fetch_sqlite_constraints(self):
        constraints = {'PRIMARY KEY': [],
                       'FOREIGN KEY': [], 'UNIQUE': [], 'CHECK': []}
        conn = None
        try:
            conn = db.create_sqlite_connection(self.conn_data['db_path'])
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{self.table_name}';")
            sql_def_row = cursor.fetchone()
            sql_def = sql_def_row[0] if sql_def_row else ""
            cursor.execute(f'PRAGMA table_info("{self.table_name}");')
            pk_info = [row for row in cursor.fetchall() if row[5] > 0]
            if pk_info:
                pk_name = f"PK_{self.table_name}"
                if "CONSTRAINT" in sql_def.upper() and "PRIMARY KEY" in sql_def.upper():
                    for line in sql_def.split('\n'):
                        if "CONSTRAINT" in line.upper() and "PRIMARY KEY" in line.upper():
                            pk_name = line.split()[1].strip('`"')
                            break
                pk_cols = [row[1] for row in pk_info]
                constraints['PRIMARY KEY'].append(
                    [pk_name, ", ".join(pk_cols)])
            cursor.execute(f'PRAGMA foreign_key_list("{self.table_name}");')
            fks = {}
            for row in cursor.fetchall():
                fk_id, _, ref_table, from_col, to_col, _, _, _ = row
                if fk_id not in fks:
                    fks[fk_id] = {'from': [], 'to': [], 'ref_table': ref_table}
                fks[fk_id]['from'].append(from_col)
                fks[fk_id]['to'].append(to_col)
            fk_names = {}
            if sql_def:
                fk_counter = 0
                for line in sql_def.split('\n'):
                    if line.strip().upper().startswith("CONSTRAINT") and "FOREIGN KEY" in line.upper():
                        fk_names[fk_counter] = line.split()[1].strip('`"')
                        fk_counter += 1
            for i, fk_id in enumerate(fks):
                name = fk_names.get(
                    i, f"FK_{self.table_name}_{fks[fk_id]['ref_table']}_{fk_id}")
                constraints['FOREIGN KEY'].append([name, ", ".join(
                    fks[fk_id]['from']), fks[fk_id]['ref_table'], ", ".join(fks[fk_id]['to'])])
            cursor.execute(f'PRAGMA index_list("{self.table_name}")')
            for index in cursor.fetchall():
                if index[2] == 1 and "sqlite_autoindex" not in index[1]:
                    cursor.execute(f'PRAGMA index_info("{index[1]}")')
                    cols = ", ".join([info[2] for info in cursor.fetchall()])
                    constraints['UNIQUE'].append([index[1], cols])
            if sql_def:
                for line in sql_def.split('\n'):
                    line, upper_line = line.strip().rstrip(','), line.upper()
                    if upper_line.startswith("CONSTRAINT") and "CHECK" in upper_line:
                        constraints['CHECK'].append(
                            [line.split()[1].strip('`"'), line[line.find('('):].strip()])
                    elif upper_line.startswith("CHECK"):
                        constraints['CHECK'].append(
                            [f"CK_{self.table_name}", line[line.find('('):].strip()])
        finally:
            if conn:
                conn.close()
        return constraints

    def _fetch_postgres_constraints(self):
        constraints = {'PRIMARY KEY': [],
                       'FOREIGN KEY': [], 'UNIQUE': [], 'CHECK': []}
        conn = None
        try:
            pg_conn_data = {key: self.conn_data.get(
                key) for key in ['host', 'port', 'database', 'user', 'password']}
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
            query_key = "SELECT tc.constraint_name, tc.constraint_type, STRING_AGG(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) FROM information_schema.table_constraints AS tc JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema WHERE tc.table_name = %s AND tc.table_schema = %s AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE') GROUP BY tc.constraint_name, tc.constraint_type;"
            cursor.execute(query_key, (self.table_name, self.schema_name))
            for name, type, cols in cursor.fetchall():
                constraints[type].append([name, cols])
            query_fk = "SELECT rc.constraint_name, STRING_AGG(kcu.column_name, ', ' ORDER BY kcu.ordinal_position), ccu.table_schema, ccu.table_name, STRING_AGG(ccu.column_name, ', ' ORDER BY ccu.ordinal_position) FROM information_schema.referential_constraints AS rc JOIN information_schema.key_column_usage AS kcu ON kcu.constraint_name = rc.constraint_name AND kcu.table_schema = %s JOIN information_schema.key_column_usage AS ccu ON ccu.constraint_name = rc.unique_constraint_name AND ccu.table_schema = rc.unique_constraint_schema WHERE kcu.table_name = %s AND kcu.table_schema = %s GROUP BY rc.constraint_name, ccu.table_schema, ccu.table_name;"
            cursor.execute(query_fk, (self.schema_name,
                           self.table_name, self.schema_name))
            for name, f_cols, p_schema, p_table, p_cols in cursor.fetchall():
                constraints['FOREIGN KEY'].append(
                    [name, f_cols, f"{p_schema}.{p_table}", p_cols])
            query_check = "SELECT con.conname, pg_get_constraintdef(con.oid) FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relname = %s AND n.nspname = %s AND con.contype = 'c';"
            cursor.execute(query_check, (self.table_name, self.schema_name))
            for name, definition in cursor.fetchall():
                constraints['CHECK'].append([name, definition])
        finally:
            if conn:
                conn.close()
        return constraints


    