# workers.py
import os
import time
import pandas as pd
import cdata.csv as mod  # CData CSV connector
from PyQt6.QtCore import QRunnable, Qt
import db

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
            # Step 1: Database connection and query setup 
            conn_data = self.item_data['conn_data']
            db_type = self.item_data.get('db_type')
            
            if db_type == 'sqlite':
                conn = db.create_sqlite_connection(conn_data["db_path"])
                query = f'SELECT * FROM "{self.table_name}"'
            elif db_type == 'postgres':
                conn = db.create_postgres_connection(
                    host=conn_data["host"], database=conn_data["database"], user=conn_data["user"], password=conn_data["password"], port=int(conn_data["port"]))
                schema_name = self.item_data.get("schema_name")
                query = f'SELECT * FROM "{schema_name}"."{self.table_name}"'
            else:
                raise ValueError("Unsupported database type for export.")
            
            if not conn:
                raise ConnectionError("Failed to connect to the database for export.")

            # Step 2: Manually create DataFrame 
            cursor = conn.cursor()
            cursor.execute(query)
            
            # get column name
            headers = [desc[0] for desc in cursor.description]
            
            # fetches all rows from the execute query result
            data = cursor.fetchall()
            
            # DataFrame 
            df = pd.DataFrame(data, columns=headers)
            
        
            file_path = self.export_options['filename']
            file_format = os.path.splitext(file_path)[1].lower()
            # file_format = self.export_options['format']
            if file_format == 'xlsx':
                df.to_excel(file_path, index=False,
                            header=self.export_options['header'])
            else:
                df.to_csv(file_path, index=False, header=self.export_options['header'], sep=self.export_options[
                          'delimiter'], encoding=self.export_options['encoding'], quotechar=self.export_options['quote'])
            
            time_taken = time.time() - start_time
            success_message = f"Successfully exported {len(df)} rows to {os.path.basename(file_path)}"
            self.signals.finished.emit(
                self.process_id, success_message, time_taken)
                
        except Exception as e:
            error_msg = f"An error occurred during export: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            self.signals.error.emit(self.process_id, error_msg)

        finally:
            if conn:
                conn.close()


class RunnableExportFromModel(QRunnable):
    def __init__(self, process_id, model, export_options, signals):
        super().__init__()
        self.process_id = process_id
        self.model = model
        self.export_options = export_options
        self.signals = signals

    def run(self):
        start_time = time.time()
        try:
            rows, cols = self.model.rowCount(), self.model.columnCount()
            headers = [self.model.headerData(c, Qt.Orientation.Horizontal) for c in range(cols)]
            data = []
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
                df.to_csv(
                    file_path,
                    index=False,
                    header=self.export_options['header'],
                    sep=self.export_options['delimiter'],
                    encoding=self.export_options['encoding'],
                    quotechar=self.export_options['quote']
                )

            time_taken = time.time() - start_time
            msg = f"Exported {len(df)} rows to {os.path.basename(file_path)}"
            self.signals.finished.emit(self.process_id, msg, time_taken)
        except Exception as e:
            self.signals.error.emit(self.process_id, str(e))


# --- Worker now inherits from QRunnable for use with QThreadPool ---
# class RunnableQuery(QRunnable):
#     def __init__(self, conn_data, query, signals):
#         super().__init__()
#         self.conn_data = conn_data
#         self.query = query
#         self.signals = signals
#         self._is_cancelled = False

#     def cancel(self):
#         self._is_cancelled = True

#     def run(self):
#         conn = None
#         try:
#             start_time = time.time()
#             if not self.conn_data:
#                 raise ConnectionError("Incomplete connection information.")

#             if "db_path" in self.conn_data and self.conn_data["db_path"]:
#                 conn = db.create_sqlite_connection(self.conn_data["db_path"])
#             else:
#                 conn = db.create_postgres_connection(
#                     host=self.conn_data["host"], database=self.conn_data["database"],
#                     user=self.conn_data["user"], password=self.conn_data["password"],
#                     port=int(self.conn_data["port"])
#                 )
            
#             if not conn:
#                 raise ConnectionError("Failed to establish database connection.")

#             cursor = conn.cursor()
#             cursor.execute(self.query)

#             if self._is_cancelled:
#                 conn.close()
#                 return

#             row_count = 0
#             is_select_query = self.query.lower().strip().startswith("select")
#             results = []
#             columns = []

#             if is_select_query:
#                 if cursor.description:
#                     columns = [desc[0] for desc in cursor.description]
#                     if not self._is_cancelled:
#                         results = cursor.fetchall()
#                         row_count = len(results)
#                 else:
#                     row_count = 0
#             else:
#                 conn.commit()
#                 row_count = cursor.rowcount if cursor.rowcount != -1 else 0

#             if self._is_cancelled:
#                 conn.close()
#                 return

#             elapsed_time = time.time() - start_time
#             self.signals.finished.emit(
#                 self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query)

#         except Exception as e:
#             # if not self._is_cancelled:
#             #     self.signals.error.emit(str(e))
#             if not self._is_cancelled:
#                 elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
#                 self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )
#         finally:
#             if conn:
#                 conn.close()



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
                raise ValueError("Connection code missing.")

            # --- CSV via CData ---
            if code == "CSV":
                folder_path = self.conn_data.get("db_path")
                if not folder_path:
                    raise ValueError("CSV folder path missing.")

                conn = mod.connect(f"URI={folder_path};")
                cursor = conn.cursor()
                cursor.execute(self.query)

                columns = [d[0] for d in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results)
                
            # --- SQLite ---
            elif code == "SQLITE":
                import db  # your SQLite helper module
                db_path = self.conn_data.get("db_path")
                if not db_path:
                    raise ValueError("SQLite database path missing.")

                conn = db.create_sqlite_connection(db_path)
                cursor = conn.cursor()
                cursor.execute(self.query)

                if self._is_cancelled:
                    return

                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results) if cursor.description else cursor.rowcount

            # --- Postgres ---
            elif code == "POSTGRES":
                import db  # your Postgres helper module
                conn = db.create_postgres_connection(
                    host=self.conn_data["host"],
                    database=self.conn_data["database"],
                    user=self.conn_data["user"],
                    password=self.conn_data["password"],
                    port=int(self.conn_data["port"]) if self.conn_data.get("port") else 5432
                )
                cursor = conn.cursor()
                cursor.execute(self.query)

                if self._is_cancelled:
                    return

                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results) if cursor.description else cursor.rowcount

            else:
                raise ValueError(f"Unsupported db_type: {db_type}")

            if self._is_cancelled:
                return

            elapsed_time = time.time() - start_time
            is_select_query = self.query.lower().strip().startswith("select")

            # Emit results
            self.signals.finished.emit(
                self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query
            )

        except Exception as e:
             if not self._is_cancelled:
                elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )
            # if not self._is_cancelled:
            #     elapsed_time = time.time() - start_time
            #     self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e))

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
