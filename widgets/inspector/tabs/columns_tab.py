from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QAbstractItemView,
    QHeaderView, QMessageBox, QToolButton, QStyledItemDelegate, QApplication
)
from PySide6.QtCore import Qt, QSize, QEvent, QModelIndex
from PySide6.QtGui import QStandardItemModel, QStandardItem
from ui.icons import get_icon
import db
from dialogs.properties import oracle_queries, pg_queries
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

    @property
    def db_type(self) -> str:
        item = self.item_data or {}
        conn_data = item.get("conn_data") or {}
        code = str(conn_data.get("code") or item.get("code") or "").upper()
        dt = str(item.get("db_type") or conn_data.get("db_type") or "").upper()
        nt = str(item.get("type") or "").lower()
        if (
            "ORACLE" in code
            or "ORACLE" in dt
            or "oracle" in nt
            or conn_data.get("service_name")
            or conn_data.get("oracle_db_type")
        ):
            return "oracle"
        if "SQLITE" in code or "SQLITE" in dt or "sqlite" in nt or conn_data.get("db_path"):
            return "sqlite"
        return "postgres"

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
            self.db_type == 'sqlite'
            or 'MATERIALIZED' in table_type
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
            self.columns_table.setItemDelegateForColumn(
                1, DataTypeDelegate(self.columns_table, db_type=self.db_type)
            )
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
                                    str(col.get("data_type", "")).strip().upper(),
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
        default_type = "VARCHAR2(255)" if self.db_type == "oracle" else "INTEGER"
        row = self._append_column_row("new_column", default_type, False, False, "", "", orig_name="")
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

    def _open_db_connection(self, conn_data: dict):
        """Open a database connection matching the current tab's dialect."""
        if self.db_type == "oracle":
            conn = db.get_pooled_oracle_connection(conn_data=conn_data)
        else:
            pg_conn_data = {
                key: conn_data.get(key)
                for key in ('host', 'port', 'database', 'user', 'password')
            }
            conn = db.create_postgres_connection(**pg_conn_data)
        if not conn:
            raise ConnectionError("Failed to establish database connection.")
        return conn

    def _format_ddl(self, stmt: str) -> str:
        """Normalize statement terminator for the active database dialect."""
        stripped = stmt.rstrip(";")
        return stripped if self.db_type == "oracle" else f"{stripped};"

    def _build_column_alter_statements(self, schema_name: str, table_name: str):
        """Compute DDL statements, PK lists, and dropped columns from grid edits."""
        target = f'"{schema_name}"."{table_name}"'
        is_oracle = self.db_type == "oracle"
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
                    alter_statements.append(self._format_ddl(
                        f'ALTER TABLE {target} RENAME COLUMN "{orig_name}" TO "{name}"'
                    ))

                if data_type.upper() != str(orig.get('data_type', '')).strip().upper():
                    if is_oracle:
                        stmt = f'ALTER TABLE {target} MODIFY ("{name}" {data_type})'
                    else:
                        stmt = f'ALTER TABLE {target} ALTER COLUMN "{name}" TYPE {data_type} USING "{name}"::{data_type}'
                    alter_statements.append(self._format_ddl(stmt))

                if not_null != (not orig.get('nullable', True)):
                    if is_oracle:
                        clause = "NOT NULL" if not_null else "NULL"
                        stmt = f'ALTER TABLE {target} MODIFY ("{name}" {clause})'
                    else:
                        action = "SET NOT NULL" if not_null else "DROP NOT NULL"
                        stmt = f'ALTER TABLE {target} ALTER COLUMN "{name}" {action}'
                    alter_statements.append(self._format_ddl(stmt))

                orig_default = str(orig.get('default_value', '')) if orig.get('default_value') else ""
                if default_val != orig_default:
                    if is_oracle:
                        dval = default_val if default_val else "NULL"
                        stmt = f'ALTER TABLE {target} MODIFY ("{name}" DEFAULT {dval})'
                    elif default_val:
                        stmt = f'ALTER TABLE {target} ALTER COLUMN "{name}" SET DEFAULT {default_val}'
                    else:
                        stmt = f'ALTER TABLE {target} ALTER COLUMN "{name}" DROP DEFAULT'
                    alter_statements.append(self._format_ddl(stmt))

                orig_comment = str(orig.get('comment', '')) if orig.get('comment') else ""
                if comment != orig_comment:
                    safe_comment = comment.replace("'", "''")
                    alter_statements.append(self._format_ddl(
                        f"COMMENT ON COLUMN {target}.\"{name}\" IS '{safe_comment}'"
                    ))
            else:
                if not name:
                    continue
                if is_oracle:
                    parts = [f'"{name}" {data_type}']
                    if default_val:
                        parts.append(f"DEFAULT {default_val}")
                    if not_null:
                        parts.append("NOT NULL")
                    stmt = f"ALTER TABLE {target} ADD ({' '.join(parts)})"
                else:
                    stmt = f'ALTER TABLE {target} ADD COLUMN "{name}" {data_type}'
                    if not_null:
                        stmt += " NOT NULL"
                    if default_val:
                        stmt += f" DEFAULT {default_val}"
                alter_statements.append(self._format_ddl(stmt))
                if comment:
                    safe_comment = comment.replace("'", "''")
                    alter_statements.append(self._format_ddl(
                        f"COMMENT ON COLUMN {target}.\"{name}\" IS '{safe_comment}'"
                    ))

        dropped_cols = orig_names_set - grid_orig_names
        return alter_statements, new_pk_columns, old_pk_columns, dropped_cols

    def _save_column_changes(self):
        self.save_btn.start_loading()
        QApplication.processEvents()

        conn_data = self.item_data.get('conn_data') or self.item_data
        if self.db_type == "oracle":
            schema_name = self.item_data.get('schema_name') or (conn_data.get('user') or '').upper()
        else:
            schema_name = self.item_data.get('schema_name', 'public')
        table_name = self.obj_name
        target = f'"{schema_name}"."{table_name}"'

        alter_statements, new_pk_columns, old_pk_columns, dropped_cols = self._build_column_alter_statements(
            schema_name, table_name
        )

        # Fast in-memory check: if nothing changed, exit immediately without network overhead
        if not alter_statements and not dropped_cols and sorted(new_pk_columns) == sorted(old_pk_columns):
            self.save_btn.stop_loading()
            ToastNotification.show_toast(self, "No column changes detected.", kind="info")
            return

        try:
            conn = self._open_db_connection(conn_data)
            cursor = conn.cursor()
        except Exception as e:
            self.save_btn.stop_loading()
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to database:\n{e}")
            return

        queries_mod = oracle_queries if self.db_type == "oracle" else pg_queries
        cascade_kw = "CASCADE CONSTRAINTS" if self.db_type == "oracle" else "CASCADE"

        for col_name in dropped_cols:
            deps = queries_mod.check_column_dependencies(cursor, schema_name, table_name, col_name)
            if deps:
                dep_lines = "\n".join(f"  • Constraint '{d[0]}' on table '{d[1]}'" for d in deps)
                msg = QMessageBox(self)
                msg.setWindowTitle("Drop Cascade Required")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setText(f'Column <b>"{col_name}"</b> cannot be dropped without {cascade_kw}.')
                msg.setInformativeText(
                    f"The following dependent objects will also be dropped:\n\n{dep_lines}\n\n"
                    f"Do you want to proceed with DROP {cascade_kw}?"
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                msg.button(QMessageBox.StandardButton.Ok).setText(f"Drop {cascade_kw}")
                msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
                if msg.exec() == QMessageBox.StandardButton.Ok:
                    alter_statements.append(self._format_ddl(
                        f'ALTER TABLE {target} DROP COLUMN "{col_name}" {cascade_kw}'
                    ))
                else:
                    conn.close()
                    self.save_btn.stop_loading()
                    return
            else:
                alter_statements.append(self._format_ddl(
                    f'ALTER TABLE {target} DROP COLUMN "{col_name}"'
                ))

        if sorted(new_pk_columns) != sorted(old_pk_columns):
            pk_res = queries_mod.get_primary_key_constraint(cursor, schema_name, table_name)
            if pk_res:
                alter_statements.append(self._format_ddl(
                    f'ALTER TABLE {target} DROP CONSTRAINT "{pk_res}"'
                ))
            if new_pk_columns:
                pk_cols_str = ", ".join([f'"{c}"' for c in new_pk_columns])
                alter_statements.append(self._format_ddl(
                    f'ALTER TABLE {target} ADD PRIMARY KEY ({pk_cols_str})'
                ))

        conn.close()

        if not alter_statements:
            self.save_btn.stop_loading()
            ToastNotification.show_toast(self, "No column changes detected.", kind="info")
            return

        def _worker_execute():
            exec_conn = self._open_db_connection(conn_data)
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

    def _collect_type_changes(self) -> list[tuple[str, str, str]]:
        """Return list of (column_name, old_type, new_type) for modified column types."""
        orig_by_name = {col['name']: col for col in self.original_columns_data}
        changes = []
        for row in range(self.columns_model.rowCount()):
            name = self.columns_model.item(row, 0).text().strip()
            new_type = self.columns_model.item(row, 1).text().strip()
            orig_name = self.columns_model.item(row, 0).data(Qt.ItemDataRole.UserRole) or ""
            if orig_name in orig_by_name:
                old_type = str(orig_by_name[orig_name].get('data_type', '')).strip().upper()
                if new_type.upper() != old_type:
                    changes.append((name, old_type, new_type.upper()))
        return changes

    def _format_save_error(self, error: str) -> tuple[str, str]:
        """Return a user-friendly (title, message) pair for DDL execution errors."""
        err_str = str(error)
        type_changes = self._collect_type_changes()
        change_desc = (
            f'column "{type_changes[0][0]}" from {type_changes[0][1]} to {type_changes[0][2]}'
            if len(type_changes) == 1
            else "the selected column data type"
        )

        if "ORA-01440" in err_str:
            return (
                "Cannot Reduce Precision or Scale",
                f"Cannot change {change_desc} because the column contains existing data.\n\n"
                "Oracle does not allow decreasing numeric precision or scale on a populated column.\n\n"
                "Recommended options:\n"
                "  • Choose a data type with equal or greater precision/scale (e.g., NUMBER or NUMBER(38)).\n"
                "  • Clear the column values (set to NULL) before modifying the type.\n"
                "  • Add a new column with the target type, copy/convert the data, and drop the old column.\n\n"
                f"Details: {err_str}",
            )
        if "ORA-01439" in err_str:
            return (
                "Incompatible Data Type Change",
                f"Cannot change {change_desc} because the column contains existing data.\n\n"
                "Oracle does not allow converting between incompatible data types while rows contain non-null values.\n\n"
                "Recommended options:\n"
                "  • Clear the column values (set to NULL) before modifying the type.\n"
                "  • Add a new column with the target type, migrate the data, and drop the old column.\n\n"
                f"Details: {err_str}",
            )
        if "ORA-01441" in err_str:
            return (
                "Cannot Reduce Column Length",
                f"Cannot change {change_desc} because existing values exceed the new maximum length.\n\n"
                "Choose a larger length or shorten the existing values before saving.\n\n"
                f"Details: {err_str}",
            )
        if "ORA-00902" in err_str or "ORA-00906" in err_str:
            return (
                "Invalid Data Type",
                "The specified data type is invalid for this Oracle version or is missing a required length/precision "
                "(for example, VARCHAR2(255) instead of VARCHAR2).\n\n"
                f"Details: {err_str}",
            )

        if self.db_type == "oracle":
            return ("Execution Error", f"Failed to execute changes:\n{err_str}")
        return ("Execution Error", f"Failed to execute changes:\n{err_str}\n\nTransaction rolled back.")

    def _on_save_finished(self, _result, error):
        self.save_btn.stop_loading()
        if error:
            title, message = self._format_save_error(error)
            QMessageBox.critical(self, title, message)
            return

        ToastNotification.show_toast(self, "Table columns updated successfully.", kind="success")
        wb = getattr(self, "workbench", None)
        if wb and hasattr(wb, "refresh_properties"):
            wb.refresh_properties(silent=True)
