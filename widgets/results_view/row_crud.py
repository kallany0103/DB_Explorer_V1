import pandas as pd
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QFileDialog, QMessageBox

import db


def delete_selected_row(manager):
    current_tab = manager.tab_widget.currentWidget()
    if not current_tab:
        return

    table_view = manager._get_result_table_for_tab(current_tab)
    if not table_view:
        return

    output_state = table_view.property("output_state") or {}
    table_name = output_state.get("table_name")

    if not table_name:
        QMessageBox.warning(manager.main_window, "Warning", "Cannot determine table name. Please run a SELECT query first.")
        return

    display_model = table_view.model()
    selection_model = table_view.selectionModel()
    if not display_model or not selection_model:
        return

    if isinstance(display_model, QSortFilterProxyModel):
        source_model = display_model.sourceModel()
    else:
        source_model = display_model

    selected_source_rows = set()

    for idx in selection_model.selectedRows():
        if isinstance(display_model, QSortFilterProxyModel):
            idx = display_model.mapToSource(idx)
        selected_source_rows.add(idx.row())

    if not selected_source_rows:
        for idx in selection_model.selectedIndexes():
            if isinstance(display_model, QSortFilterProxyModel):
                idx = display_model.mapToSource(idx)
            selected_source_rows.add(idx.row())

    if not selected_source_rows:
        QMessageBox.warning(manager.main_window, "Warning", "Please select a row to delete.")
        return

    reply = QMessageBox.question(
        manager.main_window,
        "Confirm Deletion",
        f"Are you sure you want to delete {len(selected_source_rows)} row(s)?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )

    if reply == QMessageBox.StandardButton.No:
        return

    db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
    conn_data = db_combo_box.currentData()
    if not conn_data:
        QMessageBox.critical(manager.main_window, "Error", "No active database connection found.")
        return

    db_code = (conn_data.get("code") or conn_data.get("db_type", "")).upper()
    deleted_count = 0
    errors = []

    conn = None
    try:
        if db_code == "POSTGRES":
            conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ["host", "port", "database", "user", "password"]})
        elif "SQLITE" in str(db_code):
            conn = db.create_sqlite_connection(conn_data.get("db_path"))
        elif "SERVICENOW" in str(db_code):
            conn = db.create_servicenow_connection(conn_data)

        if not conn:
            QMessageBox.critical(manager.main_window, "Error", "Could not create database connection.")
            return

        cursor = conn.cursor()

        for row_idx in sorted(selected_source_rows, reverse=True):
            item = source_model.item(row_idx, 0)
            if not item:
                continue

            item_data = item.data(Qt.ItemDataRole.UserRole)
            pk_col = item_data.get("pk_col")
            pk_val = item_data.get("pk_val")

            if not pk_col or pk_val is None:
                errors.append(f"Row {row_idx + 1}: No Primary Key found. Cannot delete safely.")
                continue

            try:
                if db_code == "POSTGRES":
                    sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = %s'
                    cursor.execute(sql, (pk_val,))
                elif "SQLITE" in str(db_code):
                    sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = ?'
                    cursor.execute(sql, (pk_val,))
                elif "SERVICENOW" in str(db_code):
                    sql = f"DELETE FROM {table_name} WHERE {pk_col} = '{pk_val}'"
                    cursor.execute(sql)

                source_model.removeRow(row_idx)
                deleted_count += 1

            except Exception as inner_e:
                errors.append(f"Row {row_idx + 1} Error: {str(inner_e)}")

        conn.commit()
        conn.close()

    except Exception as e:
        QMessageBox.critical(manager.main_window, "Database Error", str(e))
        if conn:
            conn.close()
        return

    if deleted_count > 0:
        manager.status.showMessage(f"Successfully deleted {deleted_count} row(s).", 3000)
        QMessageBox.information(manager.main_window, "Success", f"Successfully deleted {deleted_count} row(s).")

    if errors:
        QMessageBox.warning(manager.main_window, "Deletion Errors", "\n".join(errors[:5]))


def model_to_dataframe(manager, model):
    rows = model.rowCount()
    cols = model.columnCount()

    headers = [
        model.headerData(c, Qt.Orientation.Horizontal)
        for c in range(cols)
    ]

    data = []
    for r in range(rows):
        row = []
        for c in range(cols):
            index = model.index(r, c)
            row.append(model.data(index))
        data.append(row)

    return pd.DataFrame(data, columns=headers)


def download_result(manager, tab_content):
    table = manager._get_result_table_for_tab(tab_content)
    if not table or not table.model():
        QMessageBox.warning(manager.main_window, "No Data", "No result data to download")
        return

    model = table.model()
    df = model_to_dataframe(manager, model)

    if df.empty:
        QMessageBox.warning(manager.main_window, "No Data", "Result is empty")
        return

    file_path, selected_filter = QFileDialog.getSaveFileName(
        manager.main_window,
        "Download Result",
        "query_result",
        "CSV (*.csv);;Excel (*.xlsx)",
    )

    if not file_path:
        return

    try:
        if file_path.endswith(".csv"):
            df.to_csv(file_path, index=False)
        elif file_path.endswith(".xlsx"):
            df.to_excel(file_path, index=False)

        QMessageBox.information(
            manager.main_window,
            "Success",
            f"Result downloaded successfully:\n{file_path}",
        )

    except Exception as e:
        QMessageBox.critical(manager.main_window, "Error", str(e))


def add_empty_row(manager):
    tab = manager.tab_widget.currentWidget()
    if not tab:
        return

    table = manager._get_result_table_for_tab(tab)
    if not table:
        return
    model = table.model()
    if isinstance(model, QSortFilterProxyModel):
        model = model.sourceModel()

    if not model:
        return

    row = model.rowCount()
    model.insertRow(row)

    output_state = table.property("output_state") or {}
    output_state["new_row_index"] = row
    table.setProperty("output_state", output_state)

    table.scrollToBottom()
    table.setCurrentIndex(model.index(row, 0))
    table.edit(model.index(row, 0))


def save_new_row(manager):
    tab = manager.tab_widget.currentWidget()
    if not tab:
        return

    saved_any = False
    update_popup_shown = False
    db_combo_box = tab.findChild(QComboBox, "db_combo_box")
    conn_data = db_combo_box.currentData()
    if not conn_data:
        return

    table = manager._get_result_table_for_tab(tab)
    if not table:
        return
    output_state = table.property("output_state") or {}
    model = table.model()
    if isinstance(model, QSortFilterProxyModel):
        model = model.sourceModel()

    if output_state.get("new_row_index") is not None:
        if not output_state.get("table_name") or not output_state.get("column_names"):
            QMessageBox.warning(manager.main_window, "Error", "Table context missing.")
        else:
            row_idx = output_state["new_row_index"]
            values = []
            for col_idx in range(model.columnCount()):
                item = model.item(row_idx, col_idx)
                val = item.text() if item else None
                if val == "":
                    val = None
                values.append(val)

            cols_str = ", ".join([f'"{c}"' for c in output_state["column_names"]])
            db_code = (conn_data.get("code") or conn_data.get("db_type", "")).upper()

            conn = None

            try:
                if db_code == "POSTGRES":
                    placeholders = ", ".join(["%s"] * len(values))
                    sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                    conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ["host", "port", "database", "user", "password"]})

                elif "SQLITE" in str(db_code):
                    placeholders = ", ".join(["?"] * len(values))
                    sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                    conn = db.create_sqlite_connection(conn_data.get("db_path"))

                elif "SERVICENOW" in str(db_code):
                    placeholders = ", ".join(["?"] * len(values))
                    sql = f'INSERT INTO {output_state["table_name"]} ({cols_str}) VALUES ({placeholders})'
                    conn = db.create_servicenow_connection(conn_data)
                if conn:
                    cursor = conn.cursor()
                    cursor.execute(sql, values)
                    conn.commit()
                    conn.close()
                    output_state["new_row_index"] = None
                    table.setProperty("output_state", output_state)
                    saved_any = True

            except Exception as e:
                QMessageBox.critical(manager.main_window, "Insert Error", f"Failed to insert row:\n{str(e)}")

    modified_coords = output_state.get("modified_coords", set())
    updates_count = 0
    update_errors = []
    if modified_coords:
        coords_to_process = list(modified_coords)
        db_code = (conn_data.get("code") or conn_data.get("db_type", "")).upper()
        conn = None

        try:
            if db_code == "POSTGRES":
                conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ["host", "port", "database", "user", "password"]})
            elif "SQLITE" in str(db_code):
                conn = db.create_sqlite_connection(conn_data.get("db_path"))
            elif "SERVICENOW" in str(db_code):
                conn = db.create_servicenow_connection(conn_data)

            if not conn:
                raise Exception("Could not create database connection for updates.")

            cursor = conn.cursor()
            table_name_for_update = output_state.get("table_name")

            for row, col in coords_to_process:
                item = model.item(row, col)
                if not item:
                    continue

                edit_data = item.data(Qt.ItemDataRole.UserRole) or {}
                pk_col = edit_data.get("pk_col")
                pk_val = edit_data.get("pk_val")
                col_name = edit_data.get("col_name")
                new_val = item.text()
                val_to_update = None if new_val == "" else new_val

                if not table_name_for_update:
                    update_errors.append("Missing table context for update.")
                    continue
                if not pk_col or pk_val is None:
                    update_errors.append(f"Missing PK for column {col_name}")
                    continue

                try:
                    if db_code == "POSTGRES":
                        sql = f'UPDATE {table_name_for_update} SET "{col_name}" = %s WHERE "{pk_col}" = %s'
                        cursor.execute(sql, (val_to_update, pk_val))
                    elif "SQLITE" in str(db_code):
                        sql = f'UPDATE {table_name_for_update} SET "{col_name}" = ? WHERE "{pk_col}" = ?'
                        cursor.execute(sql, (val_to_update, pk_val))
                    elif "SERVICENOW" in str(db_code):
                        sql = f"UPDATE {table_name_for_update} SET {col_name} = ? WHERE {pk_col} = ?"
                        cursor.execute(sql, (val_to_update, pk_val))
                    else:
                        update_errors.append(f"Unsupported DB type for updates: {db_code}")
                        continue

                    if hasattr(cursor, "rowcount") and cursor.rowcount == 0:
                        update_errors.append(f"No row updated for PK '{pk_col}'={pk_val}")
                        continue

                    edit_data["orig_val"] = new_val
                    item.setData(edit_data, Qt.ItemDataRole.UserRole)
                    item.setBackground(QColor(Qt.GlobalColor.white))
                    if (row, col) in modified_coords:
                        modified_coords.remove((row, col))
                    updates_count += 1
                except Exception as inner_e:
                    update_errors.append(str(inner_e))

            conn.commit()
            if updates_count > 0:
                saved_any = True

        except Exception as e:
            QMessageBox.critical(manager.main_window, "Connection Error", f"Failed to update rows:\n{str(e)}")
        finally:
            if conn:
                conn.close()

        output_state["modified_coords"] = modified_coords
        table.setProperty("output_state", output_state)

        if updates_count > 0:
            update_popup_shown = True
            QMessageBox.information(manager.main_window, "Update Success", f"Updated {updates_count} value(s) successfully.")
        elif coords_to_process:
            QMessageBox.warning(manager.main_window, "Update Failed", "Update failed. No values were updated.")

        if update_errors:
            QMessageBox.warning(manager.main_window, "Update Details", "\n".join(update_errors[:8]))

    if saved_any:
        manager.status.showMessage("Changes saved successfully!", 3000)
        if not update_popup_shown:
            QMessageBox.information(manager.main_window, "Success", "Changes saved successfully!")
    elif output_state.get("new_row_index") is None and not modified_coords:
        manager.status.showMessage("No changes to save.", 3000)
