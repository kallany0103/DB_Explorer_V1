from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QAbstractItemView,
    QHeaderView, QMessageBox, QToolButton, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QSize, QEvent, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem
from ui.icons import get_icon
import db
from dialogs.properties import pg_queries
from ui.components import IconButton, PrimaryIconButton, ToastNotification
from workers.workers import WorkerThread
from widgets.inspector.properties_ui import (
    PropertyTable,
    DataTypeDelegate,
    CheckboxDelegate,
    PropertyCellDelegate,
)


class ActionCellDelegate(QStyledItemDelegate):
    """Delegate for action/button column: suppresses focus rects, selection, and hover highlights, and sizes index widget to cell."""
    def paint(self, painter, option, index):
        pass

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def editorEvent(self, event, model, option, index):
        if event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            return True
        return super().editorEvent(event, model, option, index)


class ColumnsTab(QWidget):
    def __init__(self, data, workbench):
        super().__init__()
        self.workbench = workbench
        self.item_data = (workbench.item_data or {}) if workbench else {}
        self.obj_name = (workbench.obj_name or "") if workbench else ""
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

        table_type = (self.item_data.get('table_type') or '').upper()
        self.is_read_only = bool(
            'MATERIALIZED' in table_type
            or 'VIEW' in table_type
            or self.item_data.get('type') in ('materialized_view', 'matview', 'view')
        )

        self.add_col_btn = IconButton(get_icon('msc.plus', color='#334155'), tooltip="Add Column")
        self.add_col_btn.clicked.connect(self._add_column)

        self.save_btn = PrimaryIconButton(get_icon('msc.save', color='white'), tooltip="Save Changes")
        self.save_btn.clicked.connect(self._save_column_changes)

        if not self.is_read_only:
            toolbar_layout.addWidget(self.add_col_btn)
            toolbar_layout.addWidget(self.save_btn)
        layout.addWidget(toolbar)

        # Table
        self.columns_table = PropertyTable()
        self.columns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.columns_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.columns_table.verticalHeader().setDefaultSectionSize(32)
        if self.is_read_only:
            self.columns_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        else:
            self.columns_table.setEditTriggers(
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.SelectedClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
            )
        self.columns_table.setItemDelegate(PropertyCellDelegate(self.columns_table))
        self.columns_table.setItemDelegateForColumn(5, ActionCellDelegate(self.columns_table))
        if not self.is_read_only:
            self.columns_table.setItemDelegateForColumn(1, DataTypeDelegate(self.columns_table))
            self.columns_table.setItemDelegateForColumn(2, CheckboxDelegate(self.columns_table))
            self.columns_table.setItemDelegateForColumn(3, CheckboxDelegate(self.columns_table))
        else:
            self.columns_table.setItemDelegateForColumn(2, CheckboxDelegate(self.columns_table))
            self.columns_table.setItemDelegateForColumn(3, CheckboxDelegate(self.columns_table))
        self.columns_table.horizontalHeader().setStretchLastSection(False)
        self.columns_table.viewport().installEventFilter(self)

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
        self.columns_table.clearSelection()
        self.columns_table.setCurrentIndex(QModelIndex())

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

        if not self.is_read_only:
            for row in range(self.columns_model.rowCount()):
                self.columns_table.setIndexWidget(
                    self.columns_model.index(row, 5),
                    self._make_delete_btn(row)
                )
        else:
            self.columns_table.setColumnHidden(5, True)

        layout.addWidget(self.columns_table)

        def _update_count():
            n = self.columns_model.rowCount()
            col_count_label.setText(f"{n} column{'s' if n != 1 else ''}")
            
        self.columns_model.rowsInserted.connect(_update_count)
        self.columns_model.rowsRemoved.connect(_update_count)
        _update_count()

    def eventFilter(self, obj, event):
        if hasattr(self, 'columns_table') and obj == self.columns_table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                idx = self.columns_table.indexAt(event.pos())
                if idx.isValid() and idx.column() in (2, 3):
                    self.columns_table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.columns_table.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)

    def _make_delete_btn(self, row):
        container = QWidget()
        container.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        container.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn = QToolButton(container)
        btn.setIcon(get_icon('msc.trash', color='#64748b'))
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(24, 24)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Delete this column")
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QToolButton:hover {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
            }
            QToolTip {
                background-color: #ffffff;
                color: #1f2937;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)

        def _delete():
            for r in range(self.columns_model.rowCount()):
                w = self.columns_table.indexWidget(self.columns_model.index(r, 5))
                if w is container or (w and w.findChild(QToolButton) is btn):
                    self.columns_model.removeRow(r)
                    break

        btn.clicked.connect(_delete)
        layout.addWidget(btn)
        return container

    def _append_column_row(self, name, data_type, is_pk, not_null, default_val, comment, orig_name=None):
        name_item = QStandardItem(name)
        name_item.setData(orig_name if orig_name is not None else "", Qt.ItemDataRole.UserRole)
        type_item = QStandardItem(data_type)

        pk_item = QStandardItem()
        pk_item.setEditable(False)
        pk_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        pk_item.setData(bool(is_pk), Qt.ItemDataRole.UserRole)

        nn_item = QStandardItem()
        nn_item.setEditable(False)
        nn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        nn_item.setData(bool(not_null), Qt.ItemDataRole.UserRole)

        default_item = QStandardItem(str(default_val) if default_val else "")
        comment_item = QStandardItem(str(comment) if comment else "")
        action_item = QStandardItem()
        action_item.setFlags(Qt.ItemFlag.NoItemFlags)

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

    def _set_progress(self, visible: bool):
        wb = getattr(self, "workbench", None)
        if not wb:
            return
        if hasattr(wb, "progress_container"):
            wb.progress_container.setVisible(visible)
            if hasattr(wb, "loading_icon"):
                wb.loading_icon.setVisible(visible)
            if hasattr(wb, "scroll"):
                wb.scroll.setVisible(not visible)
        elif hasattr(wb, "progress"):
            wb.progress.setVisible(visible)

    def _save_column_changes(self):
        conn_data = self.item_data.get('conn_data') or self.item_data
        pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
        try:
            conn = db.create_postgres_connection(**pg_conn_data)
            cursor = conn.cursor()
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to database:\n{e}")
            return

        schema_name = self.item_data.get('schema_name', 'public')
        table_name = self.obj_name

        alter_statements = []
        new_pk_columns = []
        old_pk_columns = [col['name'] for col in self.original_columns_data if col.get('is_pk')]

        orig_names_set = {col['name'] for col in self.original_columns_data}
        orig_by_name = {col['name']: col for col in self.original_columns_data}
        grid_orig_names = set()

        for row in range(self.columns_model.rowCount()):
            name = self.columns_model.item(row, 0).text().strip()
            data_type = self.columns_model.item(row, 1).text().strip()
            is_pk = bool(self.columns_model.item(row, 2).data(Qt.ItemDataRole.UserRole))
            not_null = bool(self.columns_model.item(row, 3).data(Qt.ItemDataRole.UserRole))
            default_val = self.columns_model.item(row, 4).text().strip()
            comment = self.columns_model.item(row, 6).text().strip()
            orig_name = self.columns_model.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""

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
                    conn.close()
                    return
            else:
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" DROP COLUMN "{col_name}";')

        if sorted(new_pk_columns) != sorted(old_pk_columns):
            pk_res = pg_queries.get_primary_key_constraint(cursor, schema_name, table_name)
            if pk_res:
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" DROP CONSTRAINT "{pk_res}";')
            if new_pk_columns:
                pk_cols_str = ", ".join([f'"{c}"' for c in new_pk_columns])
                alter_statements.append(f'ALTER TABLE "{schema_name}"."{table_name}" ADD PRIMARY KEY ({pk_cols_str});')

        conn.close()

        if not alter_statements:
            ToastNotification.show_toast(self, "No column changes detected.", kind="info")
            return

        self.save_btn.start_loading("")

        def _worker_execute():
            exec_conn = db.create_postgres_connection(**pg_conn_data)
            try:
                cur = exec_conn.cursor()
                for stmt in alter_statements:
                    cur.execute(stmt)
                exec_conn.commit()
            except Exception:
                exec_conn.rollback()
                raise
            finally:
                exec_conn.close()

        self._save_worker = WorkerThread(_worker_execute)
        self._save_worker.finished_signal.connect(self._on_save_finished)
        self._save_worker.start()

    def _on_save_finished(self, _result, error):
        self.save_btn.stop_loading()
        if error:
            QMessageBox.critical(self, "Execution Error", f"Failed to execute changes:\n{error}\n\nTransaction rolled back.")
            return

        ToastNotification.show_toast(self, "Table columns updated successfully.", kind="success")
        wb = getattr(self, "workbench", None)
        if wb and hasattr(wb, "refresh_properties"):
            wb.refresh_properties(silent=True)
