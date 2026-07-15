from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QAbstractItemView,
    QHeaderView, QMessageBox, QToolButton, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QStandardItemModel, QStandardItem
import qtawesome as qta
import db
from dialogs.properties import pg_queries
from ui.components import PrimaryButton, SecondaryButton
from widgets.inspector.properties_ui import PropertyTable, DataTypeDelegate

class ColumnsTab(QWidget):
    def __init__(self, data, workbench):
        super().__init__()
        self.workbench = workbench
        self.item_data = workbench.item_data
        self.obj_name = workbench.obj_name
        self.original_columns_data = data.get("columns", [])
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        col_count_label = QLabel()
        col_count_label.setStyleSheet("color: #6b7280; font-weight: 500;")
        toolbar_layout.addWidget(col_count_label)
        toolbar_layout.addStretch()

        add_col_btn = SecondaryButton(" Add Column")
        add_col_btn.setIcon(qta.icon('mdi.plus', color='#334155'))
        add_col_btn.clicked.connect(self._add_column)
        
        save_btn = PrimaryButton(" Save Changes")
        save_btn.setIcon(qta.icon('mdi.content-save', color='white'))
        save_btn.clicked.connect(self._save_column_changes)

        toolbar_layout.addWidget(add_col_btn)
        toolbar_layout.addWidget(save_btn)
        layout.addWidget(toolbar)

        # Table
        self.columns_table = PropertyTable()
        self.columns_table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.columns_table.horizontalHeader().setStretchLastSection(False)

        self.columns_model = QStandardItemModel()
        self.columns_model.setHorizontalHeaderLabels(["Name", "Data Type", "PK", "Not Null", "Default", "", "Comment"])

        for col in self.original_columns_data:
            self._append_column_row(col.get("name", ""),
                                    col.get("data_type", ""),
                                    col.get("is_pk", False),
                                    not col.get("nullable", True),
                                    col.get("default_value") or "",
                                    col.get("comment") or "",
                                    orig_name=col.get("name", ""))

        self.columns_table.setModel(self.columns_model)
        self.columns_table.setItemDelegateForColumn(1, DataTypeDelegate(self.columns_table))

        hh = self.columns_table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.columns_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.columns_table.setColumnWidth(0, 200)
        self.columns_table.setColumnWidth(1, 180)
        self.columns_table.setColumnWidth(2, 60)
        self.columns_table.setColumnWidth(3, 80)
        self.columns_table.setColumnWidth(4, 150)
        self.columns_table.setColumnWidth(5, 40)

        for row in range(self.columns_model.rowCount()):
            self.columns_table.setIndexWidget(
                self.columns_model.index(row, 5),
                self._make_delete_btn(row)
            )

        layout.addWidget(self.columns_table)

        def _update_count():
            n = self.columns_model.rowCount()
            col_count_label.setText(f"{n} column{'s' if n != 1 else ''}")
            
        self.columns_model.rowsInserted.connect(_update_count)
        self.columns_model.rowsRemoved.connect(_update_count)
        _update_count()


    def _make_delete_btn(self, row):
        btn = QToolButton()
        btn.setIcon(qta.icon('mdi.trash-can-outline', color='#000000'))
        btn.setIconSize(QSize(20, 20))
        btn.setFixedSize(32, 32)
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Delete this column")
        btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 4px;
                background: transparent;
            }
            QToolButton:hover {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
            }
        """)

        def _delete():
            for r in range(self.columns_model.rowCount()):
                w = self.columns_table.indexWidget(self.columns_model.index(r, 5))
                if w is btn:
                    self.columns_model.removeRow(r)
                    break
        btn.clicked.connect(_delete)
        return btn

    def _append_column_row(self, name, data_type, is_pk, not_null, default_val, comment, orig_name=None):
        name_item = QStandardItem(name)
        name_item.setData(orig_name if orig_name is not None else "", Qt.ItemDataRole.UserRole)
        type_item = QStandardItem(data_type)

        pk_item = QStandardItem()
        pk_item.setCheckable(True)
        pk_item.setEditable(False)
        pk_item.setCheckState(Qt.CheckState.Checked if is_pk else Qt.CheckState.Unchecked)
        pk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        nn_item = QStandardItem()
        nn_item.setCheckable(True)
        nn_item.setEditable(False)
        nn_item.setCheckState(Qt.CheckState.Checked if not_null else Qt.CheckState.Unchecked)
        nn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        default_item = QStandardItem(str(default_val) if default_val else "")
        comment_item = QStandardItem(str(comment) if comment else "")
        action_item  = QStandardItem()
        action_item.setEditable(False)

        self.columns_model.appendRow([name_item, type_item, pk_item, nn_item, default_item, action_item, comment_item])
        return self.columns_model.rowCount() - 1

    def _add_column(self):
        row = self._append_column_row("new_column", "integer", False, False, "", "", orig_name="")
        if hasattr(self, 'columns_table'):
            self.columns_table.setIndexWidget(
                self.columns_model.index(row, 5),
                self._make_delete_btn(row)
            )
            self.columns_table.scrollToBottom()

    def _save_column_changes(self):
        self.workbench.progress.setVisible(True)
        QApplication.processEvents()

        conn_data = self.item_data.get('conn_data') or self.item_data
        pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
        try:
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to database:\n{e}")
            self.workbench.progress.setVisible(False)
            return

        schema_name = self.item_data.get('schema_name', 'public')
        table_name = self.obj_name

        alter_statements = []
        new_pk_columns = []
        old_pk_columns = [col['name'] for col in self.original_columns_data if col.get('is_pk')]

        orig_names_set = {col['name'] for col in self.original_columns_data}
        orig_by_name   = {col['name']: col for col in self.original_columns_data}
        grid_orig_names = set()

        for row in range(self.columns_model.rowCount()):
            name       = self.columns_model.item(row, 0).text().strip()
            data_type  = self.columns_model.item(row, 1).text().strip()
            is_pk      = self.columns_model.item(row, 2).checkState() == Qt.CheckState.Checked
            not_null   = self.columns_model.item(row, 3).checkState() == Qt.CheckState.Checked
            default_val = self.columns_model.item(row, 4).text().strip()
            comment    = self.columns_model.item(row, 6).text().strip()
            orig_name  = self.columns_model.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""

            if is_pk:
                new_pk_columns.append(name)

            if orig_name and orig_name in orig_names_set:
                grid_orig_names.add(orig_name)
                orig = orig_by_name[orig_name]

                if name != orig_name:
                    alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" RENAME COLUMN "{orig_name}" TO "{name}";')

                if data_type != orig.get('data_type', ''):
                    alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" TYPE {data_type} USING "{name}"::{data_type};')

                if not_null != (not orig.get('nullable', True)):
                    action = "SET NOT NULL" if not_null else "DROP NOT NULL"
                    alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" {action};')

                orig_default = str(orig.get('default_value', '')) if orig.get('default_value') else ""
                if default_val != orig_default:
                    if default_val:
                        alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" SET DEFAULT {default_val};')
                    else:
                        alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ALTER COLUMN "{name}" DROP DEFAULT;')

                orig_comment = str(orig.get('comment', '')) if orig.get('comment') else ""
                if comment != orig_comment:
                    alter_statements.append(f"COMMENT ON COLUMN \"{schema_name}\".\"{table_name}\".\"{name}\" IS '{comment}';")
            else:
                if not name:
                    continue
                stmt = f'ALTER TABLE "{schema_name}"."{table_name}" ADD COLUMN "{name}" {data_type}'
                if not_null:
                    stmt += " NOT NULL"
                if default_val:
                    stmt += f" DEFAULT {default_val}"
                stmt += ";"
                alter_statements.append(stmt)
                if comment:
                    alter_statements.append(f"COMMENT ON COLUMN \"{schema_name}\".\"{table_name}\".\"{name}\" IS '{comment}';")

        dropped_cols = orig_names_set - grid_orig_names
        for col_name in dropped_cols:
            deps = pg_queries.check_column_dependencies(cursor, schema_name, table_name, col_name)
            if deps:
                dep_lines = "\n".join(f"  • Constraint '{d[0]}' on table '{d[1]}'" for d in deps)
                msg = QMessageBox(self)
                msg.setWindowTitle("Drop Cascade Required")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText(f'Column <b>"{col_name}"</b> cannot be dropped without CASCADE.')
                msg.setInformativeText(
                    f"The following dependent objects will also be dropped:\n\n{dep_lines}\n\n"
                    "Do you want to proceed with DROP CASCADE?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                msg.button(QMessageBox.StandardButton.Ok).setText("Drop CASCADE")
                msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
                if msg.exec() == QMessageBox.StandardButton.Ok:
                    alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" DROP COLUMN "{col_name}" CASCADE;')
            else:
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" DROP COLUMN "{col_name}";')

        if sorted(new_pk_columns) != sorted(old_pk_columns):
            pk_res = pg_queries.get_primary_key_constraint(cursor, schema_name, table_name)
            if pk_res:
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" DROP CONSTRAINT "{pk_res}";')
            if new_pk_columns:
                pk_cols_str = ", ".join([f'"{c}"' for c in new_pk_columns])
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ADD PRIMARY KEY ({pk_cols_str});')

        if not alter_statements:
            QMessageBox.information(self, "No Changes", "No column changes detected.")
            conn.close()
            self.workbench.progress.setVisible(False)
            return

        try:
            for stmt in alter_statements:
                cursor.execute(stmt)
            conn.commit()
            QMessageBox.information(self, "Success", "Table columns updated successfully.")
            self.workbench.refresh_properties()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Execution Error", f"Failed to execute changes:\n{e}\n\nTransaction rolled back.")
        finally:
            conn.close()
            self.workbench.progress.setVisible(False)
