import os
import uuid
import datetime
import re
import sqlite3 as sqlite
import pandas as pd
import sqlparse
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QTableView, QMessageBox, QMenu, QComboBox, 
    QDialog, QFileDialog, QLineEdit, QToolButton, QStackedWidget,
    QWidget, QLabel, QPushButton, QTextEdit, QTreeView
)
from PyQt6.QtCore import (
    Qt, QObject, QTimer, QSize, QSortFilterProxyModel
)
from PyQt6.QtGui import (
    QAction, QColor, QBrush, QStandardItemModel, QStandardItem, QMovie, QFont
)

import db
from .explain_visualizer import ExplainVisualizer
from dialogs import ExportDialog
from workers import RunnableExportFromModel, ProcessSignals

class ResultsManager(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        # Proxies to main window attributes
        self.tab_widget = main_window.tab_widget
        self.status = main_window.status
        self.thread_pool = main_window.thread_pool
        self.status_message_label = main_window.status_message_label
        self.cancel_action = main_window.cancel_action
        
        # Internal state
        self.tab_timers = {}
        self.running_queries = {}
        self.QUERY_TIMEOUT = 300000  # Default 5 minutes

    def copy_current_result_table(self):
        tab = self.tab_widget.currentWidget()
        if not tab:
           return

        table_view = tab.findChild(QTableView, "results_table")
        if not table_view:
           return

        self.copy_result_with_header(table_view)


    def copy_result_with_header(self, table_view: QTableView):
        model = table_view.model()
        sel = table_view.selectionModel()

        if not model or not sel:
           return

        rows = []

        selected_rows = sel.selectedRows()
        selected_indexes = sel.selectedIndexes()

    # ---------- ROW SELECTION (pgAdmin default) ----------
        if selected_rows:
           columns = range(model.columnCount())

        # Header
           header = [
               str(model.headerData(col, Qt.Orientation.Horizontal) or "")
               for col in columns
            ]
           rows.append("\t".join(header))

        # Data
           for r in selected_rows:
               row = r.row()
               row_data = [
                str(model.index(row, col).data() or "")
                for col in columns
            ]
               rows.append("\t".join(row_data))

    # ---------- CELL SELECTION ----------
        elif selected_indexes:
            selected_indexes = sorted(
             selected_indexes, key=lambda x: (x.row(), x.column())
           )

            columns = sorted({i.column() for i in selected_indexes})

            header = [
            str(model.headerData(col, Qt.Orientation.Horizontal) or "")
            for col in columns
        ]
            rows.append("\t".join(header))

            current_row = selected_indexes[0].row()
            row_data = []

            for idx in selected_indexes:
                if idx.row() != current_row:
                  rows.append("\t".join(row_data))
                  row_data = []
                  current_row = idx.row()

                row_data.append(str(idx.data() or ""))

            rows.append("\t".join(row_data))

        else:
           return

    # 🔥 THIS LINE IS THE MAGIC
        QApplication.clipboard().setText("\n".join(rows))


    def paste_to_editor(self):
        editor = self._get_current_editor()
        if editor:
           editor.paste()

    def _get_current_editor(self):
        """Helper to get the current editor from the active tab."""
        # This was not in the snippet but implies existence.
        # Assuming it tries to find 'query_editor'
        current_tab = self.tab_widget.currentWidget()
        if not current_tab: return None
        # Try finding CodeEditor first if imported, else QPlainTextEdit
        editor = current_tab.findChild(QTextEdit, "query_editor") # simplified
        if not editor:
             # Try other types if needed, or check how main window does it
             # For now return None or look for 'query_editor' by object name
             pass
        return editor

    def delete_selected_row(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            return

        table_name = getattr(current_tab, 'table_name', None)
        
        if not table_name:
            QMessageBox.warning(self.main_window, "Warning", "Cannot determine table name. Please run a SELECT query first.")
            return

        table_view = current_tab.findChild(QTableView, "results_table")
        if not table_view:
            return
        model = table_view.model()
        selection_model = table_view.selectionModel()
        proxy_rows = selection_model.selectedRows()

        selected_rows = []
        
        
        if isinstance(model, QSortFilterProxyModel):
            source_model = model.sourceModel()
            for proxy_index in proxy_rows:
               
                source_index = model.mapToSource(proxy_index)
                selected_rows.append(source_index)
           
            model = source_model 
        else:
            selected_rows = proxy_rows

        selection_model = table_view.selectionModel()
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            indexes = selection_model.selectedIndexes()
            rows_set = set(index.row() for index in indexes)
            model = table_view.model()
            selected_rows = [model.index(r, 0) for r in rows_set]

        if not selected_rows:
            QMessageBox.warning(self.main_window, "Warning", "Please select a row to delete.")
            return

        reply = QMessageBox.question(
            self.main_window, 
            'Confirm Deletion',
            f"Are you sure you want to delete {len(selected_rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.No:
            return

        
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.critical(self.main_window, "Error", "No active database connection found.")
            return

        db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
        model = table_view.model()
        deleted_count = 0
        errors = []

        conn = None
        try:
            
            if db_code == 'POSTGRES':
                conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
            elif 'SQLITE' in str(db_code):
                conn = db.create_sqlite_connection(conn_data.get('db_path'))
            elif 'SERVICENOW' in str(db_code):
                conn = db.create_servicenow_connection(conn_data)
            
            if not conn:
                QMessageBox.critical(self.main_window, "Error", "Could not create database connection.")
                return

            cursor = conn.cursor()

            for index in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
                row_idx = index.row()
                
                item = model.item(row_idx, 0) 
                if not item: continue
                
                item_data = item.data(Qt.ItemDataRole.UserRole)
                pk_col = item_data.get("pk_col")
                pk_val = item_data.get("pk_val")

                if not pk_col or pk_val is None:
                    errors.append(f"Row {row_idx + 1}: No Primary Key found. Cannot delete safely.")
                    continue

                try:
                    sql = ""
                    if db_code == 'POSTGRES':
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = %s'
                        cursor.execute(sql, (pk_val,))
                    elif 'SQLITE' in str(db_code):
                        sql = f'DELETE FROM {table_name} WHERE "{pk_col}" = ?'
                        cursor.execute(sql, (pk_val,))
                    elif 'SERVICENOW' in str(db_code):
                        sql = f"DELETE FROM {table_name} WHERE {pk_col} = '{pk_val}'"
                        cursor.execute(sql)
                    
                    
                    model.removeRow(row_idx)
                    deleted_count += 1

                except Exception as inner_e:
                    errors.append(f"Row {row_idx + 1} Error: {str(inner_e)}")

            conn.commit()
            conn.close()

        except Exception as e:
            QMessageBox.critical(self.main_window, "Database Error", str(e))
            if conn: conn.close()
            return

        
        if deleted_count > 0:
            self.status.showMessage(f"Successfully deleted {deleted_count} row(s).", 3000)
            QMessageBox.information(self.main_window, "Success", f"Successfully deleted {deleted_count} row(s).")
            
        
        if errors:
            QMessageBox.warning(self.main_window, "Deletion Errors", "\n".join(errors[:5]))


    def model_to_dataframe(self, model):
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

    def download_result(self, tab_content):
        table = tab_content.findChild(QTableView, "results_table")
        if not table or not table.model():
           QMessageBox.warning(self.main_window, "No Data", "No result data to download")
           return

        model = table.model()
        df = self.model_to_dataframe(model)

        if df.empty:
           QMessageBox.warning(self.main_window, "No Data", "Result is empty")
           return

        file_path, selected_filter = QFileDialog.getSaveFileName(
           self.main_window,
           "Download Result",
           "query_result",
           "CSV (*.csv);;Excel (*.xlsx)"
           )

        if not file_path:
           return

        try:
           if file_path.endswith(".csv"):
              df.to_csv(file_path, index=False)
           elif file_path.endswith(".xlsx"):
              df.to_excel(file_path, index=False)

           QMessageBox.information(
              self.main_window,
              "Success",
              f"Result downloaded successfully:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", str(e))



    def add_empty_row(self):
        tab = self.tab_widget.currentWidget()
        if not tab: return

        table = tab.findChild(QTableView, "results_table")
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()
        

        if not model:
           return

        row = model.rowCount()
        model.insertRow(row)
        
        # --- NEW: new row index tracking ---
        tab.new_row_index = row 
        # ----------------------------------------

        table.scrollToBottom()
        table.setCurrentIndex(model.index(row, 0))
        table.edit(model.index(row, 0))


    
    def save_new_row(self):
        """
        Handles saving BOTH new rows (INSERT) and modified cells (UPDATE).
        """
        tab = self.tab_widget.currentWidget()
        if not tab: return
        
        saved_any = False
        db_combo_box = tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        
        table = tab.findChild(QTableView, "results_table")
        model = table.model()
        if isinstance(model, QSortFilterProxyModel):
            model = model.sourceModel()

        # ---------------------------------------------------------
        # PART 1: Handle INSERT (New Rows)
        # ---------------------------------------------------------
        if hasattr(tab, "new_row_index"):
            if not hasattr(tab, "table_name") or not hasattr(tab, "column_names"):
                 QMessageBox.warning(self.main_window, "Error", "Table context missing.")
            else:
                row_idx = tab.new_row_index
                values = []
                for col_idx in range(model.columnCount()):
                    item = model.item(row_idx, col_idx)
                    val = item.text() if item else None
                    if val == '': val = None
                    values.append(val)

                cols_str = ", ".join([f'"{c}"' for c in tab.column_names])
                db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
                
                sql = ""
                conn = None

                try:
                    if db_code == 'POSTGRES':
                        placeholders = ", ".join(["%s"] * len(values))
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                        
                    elif 'SQLITE' in str(db_code): 
                        placeholders = ", ".join(["?"] * len(values))
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_sqlite_connection(conn_data.get('db_path'))
                    

                    elif 'SERVICENOW' in str(db_code):
                        placeholders = ", ".join(["?"] * len(values))
                        # ServiceNow-
                        sql = f'INSERT INTO {tab.table_name} ({cols_str}) VALUES ({placeholders})'
                        conn = db.create_servicenow_connection(conn_data)
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute(sql, values)
                        conn.commit()
                        conn.close()
                        del tab.new_row_index
                        saved_any = True
                        
                except Exception as e:
                    QMessageBox.critical(self.main_window, "Insert Error", f"Failed to insert row:\n{str(e)}")

        # ---------------------------------------------------------
        # PART 2: Handle UPDATE (Modified Cells)
        # ---------------------------------------------------------
        if hasattr(tab, "modified_coords") and tab.modified_coords:
            updates_count = 0
            errors = []
            
            coords_to_process = list(tab.modified_coords)
            
            db_code = (conn_data.get('code') or conn_data.get('db_type', '')).upper()
            conn = None
            
            try:
                if db_code == 'POSTGRES':
                    conn = db.create_postgres_connection(**{k: v for k, v in conn_data.items() if k in ['host', 'port', 'database', 'user', 'password']})
                elif 'SQLITE' in str(db_code):
                    conn = db.create_sqlite_connection(conn_data.get('db_path'))
                
                elif 'SERVICENOW' in str(db_code):
                    conn = db.create_servicenow_connection(conn_data)
                if conn:
                    cursor = conn.cursor()
                    
                    for row, col in coords_to_process:
                        item = model.item(row, col)
                        if not item: continue
                        
                        edit_data = item.data(Qt.ItemDataRole.UserRole)
                        pk_col = edit_data.get("pk_col")
                        pk_val = edit_data.get("pk_val")
                        col_name = edit_data.get("col_name")
                        new_val = item.text()
                        
                        val_to_update = None if new_val == '' else new_val

                        if not pk_col or pk_val is None:
                            if 'SERVICENOW' in str(db_code):
                                # fallback: 
                                pass
                            errors.append(f"Missing PK for column {col_name}")
                            continue

                        if db_code == 'POSTGRES':
                             sql = f'UPDATE {tab.table_name} SET "{col_name}" = %s WHERE "{pk_col}" = %s'
                        elif 'SQLITE' in str(db_code):
                             sql = f'UPDATE {tab.table_name} SET "{col_name}" = ? WHERE "{pk_col}" = ?'
                        else:
                            continue

                        try:
                            cursor.execute(sql, (val_to_update, pk_val))
                            
                            # Success: Update original value and clear background
                            edit_data['orig_val'] = new_val
                            item.setData(edit_data, Qt.ItemDataRole.UserRole)
                            item.setBackground(QColor(Qt.GlobalColor.white))
                            
                            if (row, col) in tab.modified_coords:
                                tab.modified_coords.remove((row, col))
                                
                            updates_count += 1
                        except Exception as inner_e:
                            errors.append(str(inner_e))

                    conn.commit()
                    conn.close()
                    
                    if updates_count > 0:
                        saved_any = True

            except Exception as e:
                 QMessageBox.critical(self.main_window, "Connection Error", f"Failed to connect for updates:\n{str(e)}")

            if errors:
                QMessageBox.warning(self.main_window, "Update Warnings", f"Some updates failed:\n" + "\n".join(errors[:5]))

        # ---------------------------------------------------------
        # Final Feedback
        # ---------------------------------------------------------
        if saved_any:
            self.status.showMessage("Changes saved successfully!", 3000)
            QMessageBox.information(self.main_window, "Success", "Changes saved successfully!")
        elif not hasattr(tab, "new_row_index") and (not hasattr(tab, "modified_coords") or not tab.modified_coords):
            self.status.showMessage("No changes to save.", 3000)

    def toggle_table_search(self):
        """Show/expand the table search box and hide the button."""
        tab = self.tab_widget.currentWidget()
        if not tab: return
        
        search_box = tab.findChild(QLineEdit, "table_search_box")
        search_btn = tab.findChild(QToolButton, "table_search_btn")
        
        if search_box and search_btn:
            search_btn.hide()
            search_box.show()
            search_box.setFocus()


    def handle_query_result(self, target_tab, conn_data, query, results, columns, row_count, elapsed_time, is_select_query):
        
        # Stop timers
        if target_tab in self.tab_timers:
            self.tab_timers[target_tab]["timer"].stop()
            self.tab_timers[target_tab]["timeout_timer"].stop()
            del self.tab_timers[target_tab]

        self.save_query_to_history(conn_data, query, "Success", row_count, elapsed_time)

        # Get widgets
        table_view = target_tab.findChild(QTableView, "results_table")
        message_view = target_tab.findChild(QTextEdit, "message_view")
        tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
        rows_info_label = target_tab.findChild(QLabel, "rows_info_label")
        
        # Access Result Stack
        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        results_info_bar = target_tab.findChild(QWidget, "resultsInfoBar")

        if message_view:
            message_view.clear()

        if is_select_query:
             # Check for Explain Analyze Result
            if query.upper().strip().startswith("EXPLAIN (ANALYZE,"):
                try:
                    # Result is usually [[json_data]]
                    if results and len(results) > 0 and len(results[0]) > 0:
                        json_data = results[0][0]
                        # Get visualizer
                        results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
                        explain_visualizer = results_stack.findChild(ExplainVisualizer)
                        if explain_visualizer:
                            explain_visualizer.load_plan(json_data)
                        
                        self.stop_spinner(target_tab, success=True, target_index=5) # Explain tab
                        
                        msg = f"Explain Analyze executed successfully.\nTime: {elapsed_time:.2f} sec"
                        status = f"Explain Analyze executed | Time: {elapsed_time:.2f} sec"
                        
                        # Update message view and status
                        if message_view:
                            previous_text = message_view.toPlainText()
                            if previous_text: message_view.append("\n" + "-"*50 + "\n")
                            message_view.append(msg)
                        if tab_status_label: tab_status_label.setText(status)
                        self.status_message_label.setText("Ready")

                        # Cleanup
                        if target_tab in self.running_queries: del self.running_queries[target_tab]
                        if not self.running_queries: self.cancel_action.setEnabled(False)
                        return
                except Exception as e:
                    print(f"Error parsing explain result: {e}")
                    # Fall through to normal display if parsing fails


        # --- Robust Query Type Detection ---
        match_query = re.sub(r'--.*?\n|/\*.*?\*/', '', query, flags=re.DOTALL).strip().upper()
        first_word = match_query.split()[0] if match_query.split() else ""
        
        q_type_parsed = ""
        parsed = sqlparse.parse(query)
        if parsed:
            for statement in parsed:
                t = statement.get_type().upper()
                if t != 'UNKNOWN':
                    q_type_parsed = t
                    break
        
        q_type = q_type_parsed if q_type_parsed and q_type_parsed != 'UNKNOWN' else first_word
        
        # Structural commands (DDL)
        is_structural = q_type in ["CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COMMENT", "RENAME"]
        
        # SELECT check
        is_select = q_type == "SELECT" or first_word == "SELECT"
        
        # --- DECIDE WHICH TAB TO OPEN ---
        final_tab_index = 0 # Default to Output

        # Condition: If it is NOT structural AND (it is Select OR has columns) -> Show Output Tab (0)
        if not is_structural and (is_select or (columns and len(columns) > 0)):
            final_tab_index = 0
            
            target_tab.column_names = columns
            target_tab.modified_coords = set() 

            # Extract table name logic
            match = re.search(r"FROM\s+([\"\[\]\w\.]+)", query, re.IGNORECASE)
            if match:
                extracted_table = match.group(1)
                target_tab.table_name = extracted_table.replace('"', '').replace('[', '').replace(']', '')
                if "." in target_tab.table_name:
                    parts = target_tab.table_name.split('.')
                    target_tab.schema_name = parts[0]
                    target_tab.real_table_name = parts[1]
                else:
                    target_tab.real_table_name = target_tab.table_name
            else:
                if hasattr(target_tab, 'table_name'): del target_tab.table_name

            # Row count logic
            current_offset = getattr(target_tab, 'current_offset', 0)
            if rows_info_label:
                if row_count > 0:
                    start_row = current_offset + 1
                    end_row = current_offset + row_count
                    rows_info_label.setText(f"Showing rows {start_row} - {end_row}")
                else:
                    rows_info_label.setText("No rows returned")
            
            page_label = target_tab.findChild(QLabel, "page_label")
            if page_label:
                self.update_page_label(target_tab, row_count)

            # Populate Model
            model = QStandardItemModel(table_view)
            model.setColumnCount(len(columns))
            model.setRowCount(len(results))
            
            meta_columns = None
            pk_indices = [] 
            if hasattr(target_tab, 'real_table_name'):
                meta_columns = self.get_table_column_metadata(conn_data, target_tab.real_table_name)

            headers = []
            if meta_columns and len(meta_columns) == len(columns):
                for idx, col in enumerate(meta_columns):
                    col_str = str(col)
                    if "[PK]" in col_str:
                        pk_indices.append(idx)
                    if isinstance(col, str):
                        parts = col.split(maxsplit=1)
                        col_name = parts[0]
                        data_type = parts[1] if len(parts) > 1 else ""
                    else:
                        col_name = str(col)
                        data_type = ""
                    headers.append(f"{col_name}\n{data_type}")
            else:
                headers = [f"{col}\n" for col in columns]
                if columns and any(x in columns[0].lower() for x in ['id', 'uuid', 'pk']):
                    pk_indices.append(0)

            for col_idx, header_text in enumerate(headers):
                model.setHeaderData(col_idx, Qt.Orientation.Horizontal, header_text)

            # Fill Data
            for row_idx, row in enumerate(results):
                pk_val = None
                pk_col_name = None
                if pk_indices:
                    pk_idx = pk_indices[0] 
                    pk_val = row[pk_idx]
                    pk_col_name = columns[pk_idx]

                for col_idx, cell in enumerate(row):
                    item = QStandardItem(str(cell))
                    edit_data = {
                        "pk_col": pk_col_name,
                        "pk_val": pk_val,
                        "orig_val": cell,
                        "col_name": columns[col_idx]
                    }
                    item.setData(edit_data, Qt.ItemDataRole.UserRole)
                    model.setItem(row_idx, col_idx, item)

            # Proxy Model
            try: model.itemChanged.disconnect() 
            except: pass
            model.itemChanged.connect(lambda item: self.handle_cell_edit(item, target_tab))

            proxy_model = QSortFilterProxyModel(table_view)
            proxy_model.setSourceModel(model)
            proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            proxy_model.setFilterKeyColumn(-1)
            
            table_view.setModel(proxy_model)
            search_box = target_tab.findChild(QLineEdit, "table_search_box")
            if search_box and search_box.text():
                proxy_model.setFilterFixedString(search_box.text())
            
            msg = f"Query executed successfully.\n\nTotal rows: {row_count}\nTime: {elapsed_time:.2f} sec"
            status = f"Query executed successfully | Total rows: {row_count} | Time: {elapsed_time:.2f} sec"
            
            if results_info_bar: results_info_bar.show()

        else:
            # --- Non-result-set query (DDL/DML) -> Show Messages Tab (1) ---
            final_tab_index = 1
            
            table_view.setModel(QStandardItemModel(table_view))
            should_refresh_tree = False

            if q_type.startswith("INSERT"):
                msg = f"INSERT 0 {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"INSERT 0 {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("UPDATE"):
                msg = f"UPDATE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"UPDATE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("DELETE"):
                msg = f"DELETE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
                status = f"DELETE {row_count} | Time: {elapsed_time:.2f} sec"
            elif q_type.startswith("CREATE"):
                msg = f"CREATE TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"Table Created | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            elif q_type.startswith("DROP"):
                msg = f"DROP TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
                status = f"DROP success | Time: {elapsed_time:.2f} sec"
                should_refresh_tree = True
            # elif q_type.startswith("ALTER"):
            #     msg = f"ALTER COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"ALTER success | Time: {elapsed_time:.2f} sec"
            #     should_refresh_tree = True
            # elif q_type.startswith("TRUNCATE"):
            #     msg = f"TRUNCATE COMMAND executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            #     status = f"TRUNCATE success | Time: {elapsed_time:.2f} sec"
            else:
                msg = f"Query executed successfully.\n\nRows affected: {row_count}\nTime: {elapsed_time:.2f} sec"
                status = f"Rows affected: {row_count} | Time: {elapsed_time:.2f} sec"

            if should_refresh_tree:
                self.main_window.refresh_object_explorer()

            if results_info_bar: results_info_bar.hide()

        if message_view:
            message_view.append(msg)
            sb = message_view.verticalScrollBar()
            sb.setValue(sb.maximum())

        if tab_status_label:
            tab_status_label.setText(status)

        self.status_message_label.setText("Ready")
        
        # --- CRITICAL FIX: Pass the calculated final_tab_index ---
        self.stop_spinner(target_tab, success=True, target_index=final_tab_index) 

        if target_tab in self.running_queries:
            del self.running_queries[target_tab]
        if not self.running_queries:
            self.cancel_action.setEnabled(False)

    def handle_cell_edit(self, item, tab):
        """
        Track changes locally using coordinates (row, col).
        """
        # 1. Retrieve Context Data
        edit_data = item.data(Qt.ItemDataRole.UserRole)
        if not edit_data:
            return 

        orig_val = edit_data.get("orig_val")
        new_val = item.text()

        # Initialize tracking set if missing
        if not hasattr(tab, "modified_coords"):
            tab.modified_coords = set()

        # 2. Check if value actually changed
        val_changed = str(orig_val) != str(new_val)
        if str(orig_val) == 'None' and new_val == '': val_changed = False

        row, col = item.row(), item.column()

        if val_changed:
            # Change background to indicate unsaved change
            item.setBackground(QColor("#FFFDD0")) 
            # Store Coordinate (Hashable)
            tab.modified_coords.add((row, col))
            self.status.showMessage("Cell modified")
        else:
            # Revert background
            item.setBackground(QColor(Qt.GlobalColor.white))
            if (row, col) in tab.modified_coords:
                tab.modified_coords.remove((row, col))


    def stop_spinner(self, target_tab, success=True, target_index=0):
        if not target_tab: return
        stacked_widget = target_tab.findChild(QStackedWidget, "results_stacked_widget")
        if stacked_widget:
            spinner_label = stacked_widget.findChild(QLabel, "spinner_label")
            if spinner_label and spinner_label.movie():
                spinner_label.movie().stop()
            header = target_tab.findChild(QWidget, "resultsHeader")
            buttons = header.findChildren(QPushButton)
            if success:
                stacked_widget.setCurrentIndex(target_index)
                if buttons: 
                    buttons[0].setChecked(target_index == 0) 
                    buttons[1].setChecked(target_index == 1) 
                    buttons[2].setChecked(target_index == 2)
                    buttons[3].setChecked(target_index == 3)
            else:
                stacked_widget.setCurrentIndex(1)
                if buttons: 
                    buttons[0].setChecked(False) 
                    buttons[1].setChecked(True)
                    buttons[2].setChecked(False)
                    buttons[3].setChecked(False)


    def update_page_label(self, target_tab, row_count):
        page_label = target_tab.findChild(QLabel, "page_label")
        if not page_label:
           return

        limit_val = getattr(target_tab, 'current_limit', 1000)
        offset_val = getattr(target_tab, 'current_offset', 0)

        if row_count <= 0 or limit_val == 0:
           page_label.setText("Page 1")
           return

           current_page = (offset_val // limit_val) + 1
           page_label.setText(f"Page {current_page}")



    def show_results_context_menu(self, position):
        results_table = self.sender()
        if not results_table or not results_table.model():
          return

        menu = QMenu()
        export_action = QAction("Export Rows", self.main_window)
        export_action.triggered.connect(lambda: self.export_result_rows(results_table))
        menu.addAction(export_action)

        menu.exec(results_table.viewport().mapToGlobal(position))

    def load_connection_history(self, target_tab):
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Connection History'])
        history_list_view.setModel(model)
        history_details_view.clear()
        conn_data = db_combo_box.currentData()
        if not conn_data: return
        conn_id = conn_data.get("id")
        try:
            history = db.get_query_history(conn_id)
            for row in history:
                history_id, query, ts, status, rows, duration = row
                short_query = ' '.join(query.split())[:70] + ('...' if len(query) > 70 else '')
                dt = datetime.datetime.fromisoformat(ts)
                display_text = f"{short_query}\n{dt.strftime('%Y-%m-%d %H:%M:%S')}"
                item = QStandardItem(display_text)
                item.setData({"id": history_id, "query": query, "timestamp": dt.strftime('%Y-%m-%d %H:%M:%S'), "status": status, "rows": rows, "duration": f"{duration:.3f} sec"}, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load query history:\n{e}")

    def display_history_details(self, index, target_tab):
        history_details_view = target_tab.findChild(QTextEdit, "history_details_view")
        if not index.isValid() or not history_details_view: return
        data = index.model().itemFromIndex(index).data(Qt.ItemDataRole.UserRole)
        details_text = f"Timestamp: {data['timestamp']}\nStatus: {data['status']}\nDuration: {data['duration']}\nRows: {data['rows']}\n\n-- Query --\n{data['query']}"
        history_details_view.setText(details_text)

    def _get_selected_history_item(self, target_tab):
        """Helper to get the selected item's data from the history list."""
        history_list_view = target_tab.findChild(QTreeView, "history_list_view")
        selected_indexes = history_list_view.selectionModel().selectedIndexes()
        if not selected_indexes:
            QMessageBox.information(self.main_window, "No Selection", "Please select a history item first.")
            return None
        item = selected_indexes[0].model().itemFromIndex(selected_indexes[0])
        return item.data(Qt.ItemDataRole.UserRole)

    def copy_history_query(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            clipboard = QApplication.clipboard()
            clipboard.setText(history_data['query'])
            self.main_window.status_message_label.setText("Query copied to clipboard.")

    def copy_history_to_editor(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if history_data:
            editor_stack = target_tab.findChild(QStackedWidget, "editor_stack")
            query_editor = target_tab.findChild(CodeEditor, "query_editor")
            query_editor.setPlainText(history_data['query'])
            
            # Switch back to the query editor view
            editor_stack.setCurrentIndex(0)
            query_view_btn = target_tab.findChild(QPushButton, "Query")
            history_view_btn = target_tab.findChild(QPushButton, "Query History")
            if query_view_btn: query_view_btn.setChecked(True)
            if history_view_btn: history_view_btn.setChecked(False)
            
            self.main_window.status_message_label.setText("Query copied to editor.")

    def remove_selected_history(self, target_tab):
        history_data = self._get_selected_history_item(target_tab)
        if not history_data: return
        
        history_id = history_data['id']
        reply = QMessageBox.question(self.main_window, "Remove History", "Are you sure you want to remove the selected query history?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_history(history_id)
                self.load_connection_history(target_tab) # Refresh the view
                target_tab.findChild(QTextEdit, "history_details_view").clear()
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to remove history item:\n{e}")

    def remove_all_history_for_connection(self, target_tab):
        db_combo_box = target_tab.findChild(QComboBox, "db_combo_box")
        conn_data = db_combo_box.currentData()
        if not conn_data:
            QMessageBox.warning(self.main_window, "No Connection", "Please select a connection first.")
            return
        conn_id = conn_data.get("id")
        conn_name = db_combo_box.currentText()
        reply = QMessageBox.question(self.main_window, "Remove All History", f"Are you sure you want to remove all history for the connection:\n'{conn_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db.delete_all_history(conn_id)
                self.load_connection_history(target_tab)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to clear history for this connection:\n{e}")

      
    def export_result_rows(self, table_view):
        model = table_view.model()
        if not model:
          QMessageBox.warning(self.main_window, "No Data", "No results available to export.")
          return

        dialog = ExportDialog(self.main_window, "query_results.csv")
        if dialog.exec() != QDialog.DialogCode.Accepted:
          return

        options = dialog.get_options()
        
        if not options['filename']:
          QMessageBox.warning(self.main_window, "No Filename", "Export cancelled. No filename specified.")
          return
        # 🧪 Force an invalid export option to simulate an error
        # options["delimiter"] = None   # invalid delimiter will break df.to_csv()

        # if options["delimiter"] == ',':
        #     options["delimiter"] = None

        # --- Find connection name dynamically ---
        current_tab = self.tab_widget.currentWidget()
        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        conn_name = "Unknown"
        conn_id = None # --- MODIFICATION: (Previous change)
        
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
              conn_data = db_combo_box.itemData(index)
              conn_name = conn_data.get("short_name", "Unknown")
              conn_id = conn_data.get("id") # --- MODIFICATION: (Previous change)

        # --- Create Process info ---
        full_process_id = str(uuid.uuid4())
        short_id = full_process_id[:8]
        initial_data = {
           "pid": short_id,
           "type": "Export Data",
           "status": "Running",
           "server": conn_name,
           "object": "Query Results",
           "time_taken": "...",
           "start_time": datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
           "details": f"Exporting to {os.path.basename(options['filename'])}",
           # --- START MODIFICATION (Previous change) ---
           "_conn_id": conn_id
           # --- END MODIFICATION ---
        }

        signals = ProcessSignals()
        signals.started.connect(self.handle_process_started)
        signals.finished.connect(self.handle_process_finished)
        signals.error.connect(self.handle_process_error)
        signals.started.emit(short_id, initial_data)

        self.thread_pool.start(
          RunnableExportFromModel(short_id, model, options, signals)
        )
     
    def _initialize_processes_model(self, tab_content):
        processes_view = tab_content.findChild(QTableView, "processes_view")
        if not processes_view:
          return

        tab_content.processes_model = QStandardItemModel()
        tab_content.processes_model.setHorizontalHeaderLabels(
           ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
       )
        processes_view.setModel(tab_content.processes_model)
        # processes_view.resizeColumnsToContents()

            
    def switch_to_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        results_stack = current_tab.findChild(QStackedWidget, "results_stacked_widget")
        header = current_tab.findChild(QWidget, "resultsHeader")
        buttons = header.findChildren(QPushButton)

        if results_stack and len(buttons) >= 4:
          results_stack.setCurrentIndex(3)
          for i, btn in enumerate(buttons[:4]):
            btn.setChecked(i == 3)
    
    

    
    def handle_process_started(self, process_id, data):
        # --- START MODIFICATION (Previous change) ---
        target_conn_id = data.get("_conn_id")
        if target_conn_id:
            current_tab = self.tab_widget.currentWidget()
            if current_tab:
                db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
                if db_combo_box:
                    for i in range(db_combo_box.count()):
                        item_data = db_combo_box.itemData(i)
                        if item_data and item_data.get('id') == target_conn_id:
                            # --- Check if index is already selected ---
                            if db_combo_box.currentIndex() != i:
                                db_combo_box.setCurrentIndex(i)
                            else:
                                # If already selected, manually trigger refresh
                                # because currentIndexChanged won't fire
                                self.refresh_processes_view()
                            break
        # --- END MODIFICATION ---

        self.switch_to_processes_view()

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        if target_conn_id:
           cursor.execute("""
            DELETE FROM usf_processes
            WHERE status = 'Running'
              AND server = (
                  SELECT short_name FROM usf_connections WHERE id = ?
               )
          """, (target_conn_id,))

        cursor.execute("""
          INSERT OR REPLACE INTO usf_processes
          (pid, type, status, server, object, time_taken, start_time, end_time, details)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      """, (
          data.get("pid", ""),
          data.get("type", ""),
          "Running",
          data.get("server", ""),
          data.get("object", ""),
          0.0,
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          "",
          data.get("details", "")
      ))
        conn.commit()
        conn.close()

        # refresh_processes_view is now called by the combobox signal
        # OR manually if the combobox was already on the right connection
        if not target_conn_id:
             self.refresh_processes_view()
    # change
    def handle_process_finished(self, process_id, message, time_taken, row_count):
        status = "Successfull" if row_count == 0 else "Successfull"
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        # if "0 rows" in message.lower() or "no data" in message.lower() or "empty" in message.lower():
        #     status = "Warning"
        # else:
        #     status = "Successfull"
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, time_taken = ?, end_time = ?, details = ?
          WHERE pid = ?
     """, (
           status,
          time_taken,
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #   datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()

    def handle_process_error(self, process_id, error_message):
        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()
        cursor.execute("""
          UPDATE usf_processes
          SET status = ?, end_time = ?, details = ?
          WHERE pid = ?
      """, (
          "Error",
          datetime.datetime.now().strftime("%Y-%m-%d, %I:%M:%S %p"),
          error_message,
          process_id
      ))
        conn.commit()
        conn.close()
        self.refresh_processes_view()
    
    
    def refresh_processes_view(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
          return

        db_combo_box = current_tab.findChild(QComboBox, "db_combo_box")
        selected_server = None
        if db_combo_box:
          index = db_combo_box.currentIndex()
          if index >= 0:
            data = db_combo_box.itemData(index)
            # --- Use short_name for filtering ---
            selected_server = data.get("short_name") if data else None

        processes_view = current_tab.findChild(QTableView, "processes_view")
        model = getattr(current_tab, "processes_model", None)
        if not processes_view or not model:
          return

        conn = sqlite.connect("databases/hierarchy.db")
        cursor = conn.cursor()

        if selected_server:
          # --- Filter by the selected server (short_name) ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            WHERE server = ?
            ORDER BY start_time DESC
        """, (selected_server,))
        else:
          # --- If no server selected, show all ---
          cursor.execute("""
            SELECT pid, type, status, server, object, time_taken, start_time, end_time, details
            FROM usf_processes
            ORDER BY start_time DESC
          """)

        data = cursor.fetchall()
        conn.close()

        model.clear()
        model.setHorizontalHeaderLabels(
          ["PID", "Type", "Status", "Server", "Object", "Time Taken (sec)", "Start Time", "End Time", "Details"]
        )

        for row_index, row in enumerate(data):
            items = [QStandardItem(str(col)) for col in row]

            status_text = row[2]  # 3rd column: Status
            brush = None
            if status_text == "Error":
               brush = QBrush(QColor("#BD3020"))      # 🔴 
            elif status_text == "Successfull":
                brush = QBrush(QColor("#28a745"))  # 🟢 Successful
            elif status_text == "Running":
                brush = QBrush(QColor("#ffc107"))      # 🟡 Running
            elif status_text == "Warning":
                brush = QBrush(QColor("#fd7e14"))      # 🟠 Warning
            # elif row_index == latest_row_index:
            #     brush = QBrush(QColor("#d1ecf1"))      # 🔵  (latest row highlight)
            else:
                brush = QBrush(QColor("#ffffff"))      # ⚪  (default white)

        #  Apply background color to all cells of this row
            for item in items:
              item.setBackground(brush)

            model.appendRow(items)
        
        # --- MODIFICATION: resizeColumnsToContents moved here ---
        processes_view.resizeColumnsToContents()
        processes_view.horizontalHeader().setStretchLastSection(True)

    def get_table_column_metadata(self, conn_data, table_name):
      """
        Returns a list of column headers with pgAdmin-style info like:
        emp_id [PK] integer, emp_name character varying(100)
        Uses create_postgres_connection() for consistent DB connection handling.
      """
      headers = []
      conn = None
      try:
        # ✅ Use your reusable connection function
        conn = db.create_postgres_connection(
            host=conn_data["host"],
            port=conn_data["port"],
            database=conn_data["database"],
            user=conn_data["user"],
            password=conn_data["password"]
        )
        if not conn:
            print("Failed to establish connection for metadata fetch.")
            return []

        cur = conn.cursor()
        # NOTE: Using a simple query for metadata. 
        # In worksheet.py, a complex query was used. 
        # I copied the valid logic from there.
        cur.execute("""
            SELECT
                a.attname AS column_name,
                format_type(a.atttypid, a.atttypmod) AS data_type,
                CASE WHEN ct.contype = 'p' THEN '[PK]'
                     WHEN ct.contype = 'f' THEN '[FK]'
                     ELSE ''
                END AS constraint_type
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_constraint ct 
              ON ct.conrelid = c.oid 
             AND a.attnum = ANY(ct.conkey)
            WHERE c.relname = %s 
              AND a.attnum > 0 
              AND NOT a.attisdropped
            ORDER BY a.attnum;
        """, (table_name,))
        rows = cur.fetchall()
        for col, dtype, constraint in rows:
            headers.append(f"{col} {constraint} {dtype}".strip())
      except Exception as e:
        print(f"Metadata fetch error for table '{table_name}': {e}")
      finally:
        if conn:
            conn.close()
      return headers

    def save_query_to_history(self, conn_data, query, status, rows, duration):
        conn_id = conn_data.get("id")
        if not conn_id: return
        try:
            db.save_query_history(conn_id, query, status, rows, duration)
        except Exception as e:
            self.status.showMessage(f"Could not save query to history: {e}", 4000)