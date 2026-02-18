# workers.py
import os
import time
import pandas as pd
import re
import cdata.csv as mod  # CData CSV connector
from PyQt6.QtCore import QRunnable, Qt
import db

def transform_csv_query(query, folder_path):
    """
    Convert table name in SELECT query into CSV file reference.
    e.g. "SELECT * FROM test" -> "SELECT * FROM [test.csv]"
    Only applies if test.csv exists in folder_path.
    """
    q = query.strip().rstrip(";")
    pattern = r"from\s+([a-zA-Z0-9_]+)"  # simple table name
    match = re.search(pattern, q, re.IGNORECASE)

    if not match:
        return query  # no FROM found

    table_name = match.group(1)
    csv_file = f"{table_name}.csv"
    csv_path = os.path.join(folder_path, csv_file)

    if os.path.exists(csv_path):
        return re.sub(pattern, f"FROM [{csv_file}]", q, flags=re.IGNORECASE) + ";"

    return query

# =========================================================
# 1. RunnableExport (For Large Data / Direct Export)
# =========================================================
class RunnableExport(QRunnable):
    def __init__(self, process_id, item_data, table_name, export_options, signals):
        super().__init__()
        self.process_id = process_id
        self.item_data = item_data
        self.table_name = table_name
        self.export_options = export_options
        self.signals = signals

    def run(self):
        start_time = time.time()
        conn = None
        try:
            conn_data = self.item_data['conn_data']
            # Ensure 'code' exists
            code = (conn_data.get('code') or self.item_data.get('db_type') or '').upper()
            
            # --- Connection Logic ---
            if code == 'SQLITE':
                conn = db.create_sqlite_connection(conn_data["db_path"])
                query = f'SELECT * FROM "{self.table_name}"'
            elif code == 'POSTGRES':
                conn = db.create_postgres_connection(
                    host=conn_data["host"], database=conn_data["database"], 
                    user=conn_data["user"], password=conn_data["password"], 
                    port=int(conn_data["port"])
                )
                schema_name = self.item_data.get("schema_name")
                query = f'SELECT * FROM "{schema_name}"."{self.table_name}"'
            elif code == 'CSV':
                 folder_path = conn_data.get("db_path")
                 conn = mod.connect(f"URI={folder_path};")
                 query = f'SELECT * FROM [{self.table_name}]'
            else:
                 raise ValueError(f"Unsupported database type: {code}")

            if not conn:
                raise ConnectionError("Failed to connect to the database for export.")

            cursor = conn.cursor()
            cursor.execute(query)
            
            # Get headers
            headers = [desc[0] for desc in cursor.description] if cursor.description else []

            file_path = self.export_options['filename']
            file_format = os.path.splitext(file_path)[1].lower()
            delimiter = self.export_options.get('delimiter', ',')
            if not delimiter: delimiter = ','
            
            # --- Check Semicolon for CSV/TXT ---
            # Restriction removed to allow user selected delimiter


            # --- CHUNKING LOGIC (To Fix Memory Issues) ---
            chunk_size = 10000  # Process 10k rows at a time
            row_count = 0
            is_first_chunk = True
            
            while True:
                # Fetch small amount of data
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                
                df = pd.DataFrame(rows, columns=headers)
                
                # Append mode ('a') vs Write mode ('w')
                mode = 'w' if is_first_chunk else 'a'
                header = is_first_chunk if is_first_chunk else False
                
                if file_format == '.xlsx':
                    # Excel append is tricky, better to use CSV for huge data.
                    # Simple workaround for first chunk:
                    if is_first_chunk:
                         df.to_excel(file_path, index=False, header=self.export_options['header'])
                    else:
                        # Append to existing excel (requires openpyxl)
                        with pd.ExcelWriter(file_path, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
                             # Write without header, offset by row_count + 1 (for header)
                             df.to_excel(writer, index=False, header=False, startrow=row_count+1)
                else:
                    # CSV/TXT Handling
                    df.to_csv(file_path, mode=mode, index=False, header=self.export_options['header'] and header, 
                              sep=delimiter, encoding=self.export_options['encoding'], 
                              quotechar=self.export_options['quote'])
                
                row_count += len(rows)
                is_first_chunk = False
            
            time_taken = time.time() - start_time
            success_message = f"Successfully exported {row_count} rows to {os.path.basename(file_path)}"
            
            self.signals.finished.emit(self.process_id, success_message, time_taken, row_count)
                
        except Exception as e:
            error_msg = f"An error occurred during export: {str(e)}"
            self.signals.error.emit(self.process_id, error_msg)

        finally:
            if conn:
                conn.close()

# =========================================================
# 2. RunnableExportFromModel (Fixed __init__)
# =========================================================
class RunnableExportFromModel(QRunnable):
    # FIX: Changed arguments to accept 'model'
    def __init__(self, process_id, model, export_options, signals):
        super().__init__()
        self.process_id = process_id
        self.model = model  # FIX: Assign model correctly
        self.export_options = export_options
        self.signals = signals

    def run(self):
        start_time = time.time()
        try:
            # Check if model exists
            if self.model is None:
                raise ValueError("Model is None. Cannot export.")

            rows, cols = self.model.rowCount(), self.model.columnCount()
            headers = [self.model.headerData(c, Qt.Orientation.Horizontal) for c in range(cols)]
            data = []
            
            # Extract data from QAbstractItemModel
            for r in range(rows):
                row_data = []
                for c in range(cols):
                    index = self.model.index(r, c)
                    row_data.append(self.model.data(index))
                data.append(row_data)
                
            df = pd.DataFrame(data, columns=headers)

            file_path = self.export_options['filename']
            file_format = os.path.splitext(file_path)[1].lower()

            if file_format == ".xlsx":
                df.to_excel(file_path, index=False, header=self.export_options['header'])
            else:
                delimiter = self.export_options.get('delimiter', ',')
                
                # --- Enforce Semicolon (;) ---
                # Restriction removed to allow user selected delimiter
 
                
                if not delimiter: delimiter = ','
                
                df.to_csv(
                    file_path,
                    index=False,
                    header=self.export_options['header'],
                    sep=delimiter,
                    encoding=self.export_options['encoding'],
                    quotechar=self.export_options['quote']
                )

            time_taken = time.time() - start_time
            row_count = len(df)
            msg = f"Exported {row_count} rows to {os.path.basename(file_path)}"
             
            self.signals.finished.emit(self.process_id, msg, time_taken, row_count)

        except Exception as e:
            self.signals.error.emit(self.process_id, str(e))


# =========================================================
# 3. RunnableQuery (Existing Query Worker)
# =========================================================
class RunnableQuery(QRunnable):
    def __init__(self, conn_data, query, signals):
        super().__init__()
        self.conn_data = conn_data
        self.query = query
        self.signals = signals
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        conn = None
        cursor = None
        start_time = time.time()

        try:
            if not self.conn_data:
                raise ConnectionError("Incomplete connection information.")

            code = (self.conn_data.get("code") or "").upper()
            if not code:
                if "host" in self.conn_data:
                    code = "POSTGRES"
                elif "db_path" in self.conn_data:
                    code = "SQLITE"

            # --- DB Execution ---
            if code == "SERVICENOW":
                conn = db.create_servicenow_connection(self.conn_data)
                if not conn:
                    raise ConnectionError("Failed to connect to ServiceNow")
                cursor = conn.cursor()
                cursor.execute(self.query)
            elif code == "CSV":
                folder_path = self.conn_data.get("db_path")
                if not folder_path:
                    raise ValueError("CSV folder path missing.")
                self.query = transform_csv_query(self.query, folder_path)
                conn = mod.connect(f"URI={folder_path};")
                cursor = conn.cursor()
                cursor.execute(self.query)
            elif code == "SQLITE":
                db_path = self.conn_data.get("db_path")
                if not db_path:
                    raise ValueError("SQLite database path missing.")
                conn = db.create_sqlite_connection(db_path)
                cursor = conn.cursor()
                cursor.execute(self.query)
            elif code == "POSTGRES":
                conn = db.create_postgres_connection(
                    host=self.conn_data["host"],
                    database=self.conn_data["database"],
                    user=self.conn_data["user"],
                    password=self.conn_data["password"],
                    port=int(self.conn_data["port"]) if self.conn_data.get("port") else 5432
                )
                cursor = conn.cursor()
                cursor.execute(self.query)
            else:
                if self.conn_data.get("db_path"):
                    conn = db.create_sqlite_connection(self.conn_data["db_path"])
                    cursor = conn.cursor()
                    cursor.execute(self.query)
                else:
                    raise ValueError(f"Unsupported database type: {code}")

            if self._is_cancelled:
                return

            # --- Handle Results ---
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = cursor.fetchall() if cursor.description else []
            row_count = len(results) if cursor.description else (cursor.rowcount if hasattr(cursor, 'rowcount') else 0)
            
            elapsed_time = time.time() - start_time
            
            # Treat as "select-like" if it returns data columns
            is_returning_results = bool(columns)
            
            # Commit only for mutation queries that didn't automatically commit
            q_lower = self.query.lower().strip()
            is_mutation = any(q_lower.startswith(x) for x in ["insert", "update", "delete", "create", "drop", "alter", "truncate"])
            if is_mutation and conn:
                conn.commit()

            self.signals.finished.emit(
                self.conn_data, self.query, results, columns, row_count, elapsed_time, is_returning_results
            )
        except Exception as e:
            if not self._is_cancelled:
                if conn:
                    try: conn.rollback()
                    except: pass
                elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e))

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
