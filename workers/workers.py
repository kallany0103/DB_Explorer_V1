# # # workers.py
# # import os
# # import time
# # import pandas as pd
# # import re
# # import cdata.csv as mod  # CData CSV connector
# # from PyQt6.QtCore import QRunnable, Qt
# # import db

# # def transform_csv_query(query, folder_path):
# #     """
# #     Convert table name in SELECT query into CSV file reference.
# #     e.g. "SELECT * FROM test" -> "SELECT * FROM [test.csv]"
# #     Only applies if test.csv exists in folder_path.
# #     """
# #     q = query.strip().rstrip(";")
# #     pattern = r"from\s+([a-zA-Z0-9_]+)"  # simple table name
# #     match = re.search(pattern, q, re.IGNORECASE)

# #     if not match:
# #         return query  # no FROM found

# #     table_name = match.group(1)
# #     csv_file = f"{table_name}.csv"
# #     csv_path = os.path.join(folder_path, csv_file)

# #     if os.path.exists(csv_path):
# #         return re.sub(pattern, f"FROM [{csv_file}]", q, flags=re.IGNORECASE) + ";"

# #     return query

# # class RunnableExport(QRunnable):
# #     def __init__(self, process_id, item_data, table_name, export_options, signals):
# #         super().__init__()
# #         self.process_id = process_id
# #         self.item_data = item_data
# #         self.table_name = table_name
# #         self.export_options = export_options
# #         self.signals = signals

# #     def run(self):
# #         start_time = time.time()
# #         conn = None
# #         try:
# #             # Step 1: Database connection and query setup 
# #             conn_data = self.item_data['conn_data']
# #             db_type = self.item_data.get('db_type')
            
# #             if db_type == 'sqlite':
# #                 conn = db.create_sqlite_connection(conn_data["db_path"])
# #                 query = f'SELECT * FROM "{self.table_name}"'
# #             elif db_type == 'postgres':
# #                 conn = db.create_postgres_connection(
# #                     host=conn_data["host"], database=conn_data["database"], user=conn_data["user"], password=conn_data["password"], port=int(conn_data["port"]))
# #                 schema_name = self.item_data.get("schema_name")
# #                 query = f'SELECT * FROM "{schema_name}"."{self.table_name}"'
# #             else:
# #                 raise ValueError("Unsupported database type for export.")
            
# #             if not conn:
# #                 raise ConnectionError("Failed to connect to the database for export.")

# #             # Step 2: Manually create DataFrame 
# #             cursor = conn.cursor()
# #             cursor.execute(query)
            
# #             # get column name
# #             headers = [desc[0] for desc in cursor.description]
            
# #             # fetches all rows from the execute query result
# #             data = cursor.fetchall()
            
# #             # DataFrame 
# #             df = pd.DataFrame(data, columns=headers)
            
        
# #             file_path = self.export_options['filename']
# #             file_format = os.path.splitext(file_path)[1].lower()
# #             # file_format = self.export_options['format']
# #             if file_format == '.xlsx':
# #                 df.to_excel(file_path, index=False,
# #                             header=self.export_options['header'])
# #             else:
# #                 delimiter = self.export_options.get('delimiter', ',')
# #                 if file_format == " .csv" or file_format == " .txt":
# #                     if delimiter != ";":
# #                         self.signals.error.emit(self.process_id)
# #                         return
                

# #                 if not delimiter: delimiter = ','
# #                 df.to_csv(file_path, index=False, header=self.export_options['header'], sep=delimiter,
# #                        encoding=self.export_options['encoding'], quotechar=self.export_options['quote'])
            
# #             time_taken = time.time() - start_time
# #             if len(df) == 0:
# #                 success_message = f"Export completed with no data (0 rows) exported to {os.path.basename(file_path)}"
# #             else:
# #                 success_message = f"Successfully exported {len(df)} rows to {os.path.basename(file_path)}"
            
# #             self.signals.finished.emit(
# #                 self.process_id, success_message, time_taken)
# #             # success_message = f"Successfully exported {len(df)} rows to {os.path.basename(file_path)}"
# #             # self.signals.finished.emit(
# #             #     self.process_id, success_message, time_taken)
                
# #         except Exception as e:
# #             error_msg = f"An error occurred during export: {e}"
# #             print(error_msg)
# #             import traceback
# #             traceback.print_exc()
# #             self.signals.error.emit(self.process_id, error_msg)

# #         finally:
# #             if conn:
# #                 conn.close()


# # class RunnableExportFromModel(QRunnable):
# #     def __init__(self, process_id, model, export_options, signals):
# #         super().__init__()
# #         self.process_id = process_id
# #         self.model = model
# #         self.export_options = export_options
# #         self.signals = signals

# #     def run(self):
# #         start_time = time.time()
# #         try:
# #             rows, cols = self.model.rowCount(), self.model.columnCount()
# #             headers = [self.model.headerData(c, Qt.Orientation.Horizontal) for c in range(cols)]
# #             data = []
# #             for r in range(rows):
# #                 row_data = []
# #                 for c in range(cols):
# #                     index = self.model.index(r, c)
# #                     row_data.append(self.model.data(index))
# #                 data.append(row_data)
# #             df = pd.DataFrame(data, columns=headers)

# #             file_path = self.export_options['filename']
# #             file_format = os.path.splitext(file_path)[1].lower()

# #             if file_format == ".xlsx":
# #                 df.to_excel(file_path, index=False, header=self.export_options['header'])
# #             else:
# #                 delimiter = self.export_options.get('delimiter', ',')
# #                 # ---- CSV delimiter validation ----
# #                 if file_format == ".csv" or file_format == ".txt":
# #                   if delimiter != ";":
# #                      error_msg = (
# #             f"CSV Export Error: Only ';' (semicolon) is allowed.\n"
# #             f"You used: '{delimiter}'"
# #         )
# #                 self.signals.error.emit(self.process_id, error_msg)
# #                 return


# #                 if not delimiter: delimiter = ','
# #                 df.to_csv(
# #                     file_path,
# #                     index=False,
# #                     header=self.export_options['header'],
# #                     sep=delimiter,
# #                     encoding=self.export_options['encoding'],
# #                     quotechar=self.export_options['quote']
# #                 )

# #             time_taken = time.time() - start_time
# #             if len(df) == 0:
# #                 msg = f"Export completed with no data (0 rows) exported to {os.path.basename(file_path)}"
# #             else:
# #                 msg = f"Exported {len(df)} rows to {os.path.basename(file_path)}"
                
# #             self.signals.finished.emit(self.process_id, msg, time_taken)
# #             # msg = f"Exported {len(df)} rows to {os.path.basename(file_path)}"
# #             # self.signals.finished.emit(self.process_id, msg, time_taken)
# #         except Exception as e:
# #             self.signals.error.emit(self.process_id, str(e))


# # # --- Worker now inherits from QRunnable for use with QThreadPool ---
# # # class RunnableQuery(QRunnable):
# # #     def __init__(self, conn_data, query, signals):
# # #         super().__init__()
# # #         self.conn_data = conn_data
# # #         self.query = query
# # #         self.signals = signals
# # #         self._is_cancelled = False

# # #     def cancel(self):
# # #         self._is_cancelled = True

# # #     def run(self):
# # #         conn = None
# # #         try:
# # #             start_time = time.time()
# # #             if not self.conn_data:
# # #                 raise ConnectionError("Incomplete connection information.")

# # #             if "db_path" in self.conn_data and self.conn_data["db_path"]:
# # #                 conn = db.create_sqlite_connection(self.conn_data["db_path"])
# # #             else:
# # #                 conn = db.create_postgres_connection(
# # #                     host=self.conn_data["host"], database=self.conn_data["database"],
# # #                     user=self.conn_data["user"], password=self.conn_data["password"],
# # #                     port=int(self.conn_data["port"])
# # #                 )
            
# # #             if not conn:
# # #                 raise ConnectionError("Failed to establish database connection.")

# # #             cursor = conn.cursor()
# # #             cursor.execute(self.query)

# # #             if self._is_cancelled:
# # #                 conn.close()
# # #                 return

# # #             row_count = 0
# # #             is_select_query = self.query.lower().strip().startswith("select")
# # #             results = []
# # #             columns = []

# # #             if is_select_query:
# # #                 if cursor.description:
# # #                     columns = [desc[0] for desc in cursor.description]
# # #                     if not self._is_cancelled:
# # #                         results = cursor.fetchall()
# # #                         row_count = len(results)
# # #                 else:
# # #                     row_count = 0
# # #             else:
# # #                 conn.commit()
# # #                 row_count = cursor.rowcount if cursor.rowcount != -1 else 0

# # #             if self._is_cancelled:
# # #                 conn.close()
# # #                 return

# # #             elapsed_time = time.time() - start_time
# # #             self.signals.finished.emit(
# # #                 self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query)

# # #         except Exception as e:
# # #             # if not self._is_cancelled:
# # #             #     self.signals.error.emit(str(e))
# # #             if not self._is_cancelled:
# # #                 elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
# # #                 self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )
# # #         finally:
# # #             if conn:
# # #                 conn.close()



# # class RunnableQuery(QRunnable):
# #     def __init__(self, conn_data, query, signals):
# #         super().__init__()
# #         self.conn_data = conn_data
# #         self.query = query
# #         self.signals = signals
# #         self._is_cancelled = False

# #     def cancel(self):
# #         self._is_cancelled = True

# #     def run(self):
# #         conn = None
# #         cursor = None
# #         start_time = time.time()

# #         try:
# #             if not self.conn_data:
# #                 raise ConnectionError("Incomplete connection information.")

# #             code = (self.conn_data.get("code") or "").upper()
# #             if not code:
# #                 raise ValueError("Connection code missing.")

# #             # --- CSV via CData ---
# #             if code == "CSV":
# #                 folder_path = self.conn_data.get("db_path")
# #                 if not folder_path:
# #                     raise ValueError("CSV folder path missing.")
# #                 # Transform query for CSV tables
# #                 self.query = transform_csv_query(self.query, folder_path)

# #                 conn = mod.connect(f"URI={folder_path};")
# #                 cursor = conn.cursor()
# #                 cursor.execute(self.query)

# #                 columns = [d[0] for d in cursor.description] if cursor.description else []
# #                 results = cursor.fetchall() if cursor.description else []
# #                 row_count = len(results)
                
# #             # --- SQLite ---
# #             elif code == "SQLITE":
# #                 import db  # your SQLite helper module
# #                 db_path = self.conn_data.get("db_path")
# #                 if not db_path:
# #                     raise ValueError("SQLite database path missing.")

# #                 conn = db.create_sqlite_connection(db_path)
# #                 cursor = conn.cursor()
# #                 cursor.execute(self.query)

# #                 if self._is_cancelled:
# #                     return

# #                 columns = [desc[0] for desc in cursor.description] if cursor.description else []
# #                 results = cursor.fetchall() if cursor.description else []
# #                 row_count = len(results) if cursor.description else cursor.rowcount

# #             # --- Postgres ---
# #             elif code == "POSTGRES":
# #                 import db  # your Postgres helper module
# #                 conn = db.create_postgres_connection(
# #                     host=self.conn_data["host"],
# #                     database=self.conn_data["database"],
# #                     user=self.conn_data["user"],
# #                     password=self.conn_data["password"],
# #                     port=int(self.conn_data["port"]) if self.conn_data.get("port") else 5432
# #                 )
# #                 cursor = conn.cursor()
# #                 cursor.execute(self.query)

# #                 if self._is_cancelled:
# #                     return

# #                 columns = [desc[0] for desc in cursor.description] if cursor.description else []
# #                 results = cursor.fetchall() if cursor.description else []
# #                 row_count = len(results) if cursor.description else cursor.rowcount

# #             else:
# #                 raise ValueError(f"Unsupported database type")

# #             if self._is_cancelled:
# #                 return

# #             elapsed_time = time.time() - start_time
# #             is_select_query = self.query.lower().strip().startswith("select")

# #             # Emit results
# #             self.signals.finished.emit(
# #                 self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query
# #             )

# #         except Exception as e:
# #              if not self._is_cancelled:
# #                 elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
# #                 self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )
# #             # if not self._is_cancelled:
# #             #     elapsed_time = time.time() - start_time
# #             #     self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e))

# #         finally:
# #             if cursor:
# #                 cursor.close()
# #             if conn:
# #                 conn.close()

# # workers.py
# import os
# import time
# import pandas as pd
# import re
# import cdata.csv as mod  # CData CSV connector
# from PyQt6.QtCore import QRunnable, Qt
# import db

# def transform_csv_query(query, folder_path):
#     """
#     Convert table name in SELECT query into CSV file reference.
#     e.g. "SELECT * FROM test" -> "SELECT * FROM [test.csv]"
#     Only applies if test.csv exists in folder_path.
#     """
#     q = query.strip().rstrip(";")
#     pattern = r"from\s+([a-zA-Z0-9_]+)"  # simple table name
#     match = re.search(pattern, q, re.IGNORECASE)

#     if not match:
#         return query  # no FROM found

#     table_name = match.group(1)
#     csv_file = f"{table_name}.csv"
#     csv_path = os.path.join(folder_path, csv_file)

#     if os.path.exists(csv_path):
#         return re.sub(pattern, f"FROM [{csv_file}]", q, flags=re.IGNORECASE) + ";"

#     return query

# # workers.py এর RunnableExport ক্লাসটি এভাবে পরিবর্তন করুন:

# class RunnableExport(QRunnable):
#     def __init__(self, process_id, item_data, table_name, export_options, signals):
#         super().__init__()
#         self.process_id = process_id
#         self.item_data = item_data
#         self.table_name = table_name
#         self.export_options = export_options
#         self.signals = signals

#     def run(self):
#         start_time = time.time()
#         conn = None
#         try:
#             # Step 1: Database connection setup
#             conn_data = self.item_data['conn_data']
#             # Ensure 'code' exists (fix from your main_window logic)
#             code = (conn_data.get('code') or self.item_data.get('db_type') or '').upper()
            
#             # Connection Logic based on type
#             if code == 'SQLITE':
#                 conn = db.create_sqlite_connection(conn_data["db_path"])
#                 query = f'SELECT * FROM "{self.table_name}"'
#             elif code == 'POSTGRES':
#                 conn = db.create_postgres_connection(
#                     host=conn_data["host"], database=conn_data["database"], 
#                     user=conn_data["user"], password=conn_data["password"], 
#                     port=int(conn_data["port"])
#                 )
#                 schema_name = self.item_data.get("schema_name")
#                 query = f'SELECT * FROM "{schema_name}"."{self.table_name}"'
#             elif code == 'CSV':
#                  # Ensure CData logic is imported
#                  folder_path = conn_data.get("db_path")
#                  conn = mod.connect(f"URI={folder_path};")
#                  query = f'SELECT * FROM [{self.table_name}]'
#             else:
#                  # Fallback/Generic
#                  raise ValueError(f"Unsupported database type: {code}")

#             if not conn:
#                 raise ConnectionError("Failed to connect to the database for export.")

#             cursor = conn.cursor()
#             cursor.execute(query)
            
#             # Get headers
#             if cursor.description:
#                 headers = [desc[0] for desc in cursor.description]
#             else:
#                 headers = []

#             file_path = self.export_options['filename']
#             file_format = os.path.splitext(file_path)[1].lower()
#             delimiter = self.export_options.get('delimiter', ',')
#             if not delimiter: delimiter = ','
            
#             # --- CHUNKING LOGIC (Solution for large files) ---
#             chunk_size = 10000  # Process 10,000 rows at a time
#             row_count = 0
#             is_first_chunk = True
            
#             while True:
#                 # Fetch only a chunk, not everything
#                 rows = cursor.fetchmany(chunk_size)
#                 if not rows:
#                     break
                
#                 df = pd.DataFrame(rows, columns=headers)
                
#                 # Append mode ('a') setup
#                 mode = 'w' if is_first_chunk else 'a'
#                 header = is_first_chunk if is_first_chunk else False
                
#                 if file_format == '.xlsx':
#                     # Note: Appending to Excel is complex efficiently. 
#                     # For huge data, CSV is recommended. 
#                     # If strictly Excel, we might just write all at once if < 1M rows, 
#                     # but here implies CSV preference for large data.
#                     if is_first_chunk:
#                          df.to_excel(file_path, index=False, header=self.export_options['header'])
#                     else:
#                         # Simple append not supported natively by to_excel without loading existing.
#                         # For massive data, force CSV or warn user.
#                         # Using 'append' mode with ExcelWriter if needed, but keeping simple here:
#                         with pd.ExcelWriter(file_path, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
#                              df.to_excel(writer, index=False, header=False, startrow=row_count+1)

#                 else:
#                     # CSV/TXT Handling
#                     if file_format in [".csv", ".txt"] and delimiter != ';':
#                          # Enforce semicolon logic if needed as per your code
#                          pass 

#                     df.to_csv(file_path, mode=mode, index=False, header=self.export_options['header'] and header, 
#                               sep=delimiter, encoding=self.export_options['encoding'], 
#                               quotechar=self.export_options['quote'])
                
#                 row_count += len(rows)
#                 is_first_chunk = False
            
#             # -------------------------------------------------

#             time_taken = time.time() - start_time
#             if row_count == 0:
#                 success_message = f"Export completed with no data (0 rows)."
#             else:
#                 success_message = f"Successfully exported {row_count} rows to {os.path.basename(file_path)}"
            
#             self.signals.finished.emit(self.process_id, success_message, time_taken, row_count)
                
#         except Exception as e:
#             error_msg = f"An error occurred during export: {e}"
#             print(error_msg)
#             self.signals.error.emit(self.process_id, error_msg)

#         finally:
#             if conn:
#                 conn.close()

# # class RunnableExport(QRunnable):
# #     def __init__(self, process_id, item_data, table_name, export_options, signals):
# #         super().__init__()
# #         self.process_id = process_id
# #         self.item_data = item_data
# #         self.table_name = table_name
# #         self.export_options = export_options
# #         self.signals = signals

# #     def run(self):
# #         start_time = time.time()
# #         conn = None
# #         try:
# #             # Step 1: Database connection and query setup 
# #             conn_data = self.item_data['conn_data']
# #             type = (conn_data.get('code') or self.item_data.get('db_type') or '').upper()
# #             # db_type = self.item_data.get('db_type')
            
# #             if type == 'sqlite':
# #                 conn = db.create_sqlite_connection(conn_data["db_path"])
# #                 query = f'SELECT * FROM "{self.table_name}"'
# #             elif type == 'postgres':
# #                 conn = db.create_postgres_connection(
# #                     host=conn_data["host"], database=conn_data["database"], user=conn_data["user"], password=conn_data["password"], port=int(conn_data["port"]))
# #                 schema_name = self.item_data.get("schema_name")
# #                 query = f'SELECT * FROM "{schema_name}"."{self.table_name}"'
# #             else:
# #                 raise ValueError("Unsupported database type for export.")
            
# #             if not conn:
# #                 raise ConnectionError("Failed to connect to the database for export.")

# #             # Step 2: Manually create DataFrame 
# #             cursor = conn.cursor()
# #             cursor.execute(query)
            
# #             # get column name
# #             headers = [desc[0] for desc in cursor.description]
            
# #             # fetches all rows from the execute query result
# #             data = cursor.fetchall()
            
# #             # DataFrame 
# #             df = pd.DataFrame(data, columns=headers)
            
# #             file_path = self.export_options['filename']
# #             file_format = os.path.splitext(file_path)[1].lower()
            
# #             if file_format == '.xlsx':
# #                 df.to_excel(file_path, index=False,
# #                             header=self.export_options['header'])
# #             else:
# #                 delimiter = self.export_options.get('delimiter', ',')
                
# #                 # --- NEW LOGIC: Enforce Semicolon (;) ---
            
# #                 if file_format in [".csv", ".txt"]:
# #                     if delimiter != ';':
# #                         error_msg = (
# #                             f"Export Error: Comma (,) is not allowed.\n"
# #                             f"Please select Semicolon (;) to export successfully."
# #                         )
# #                         self.signals.error.emit(self.process_id, error_msg)
# #                         return # Stop execution here
# #                 # ----------------------------------------

# #                 if not delimiter: delimiter = ',' # Fallback just in case, though checked above
                
# #                 df.to_csv(file_path, index=False, header=self.export_options['header'], sep=delimiter,
# #                        encoding=self.export_options['encoding'], quotechar=self.export_options['quote'])
            
# #             time_taken = time.time() - start_time
# #             if len(df) == 0:
# #                 success_message = f"Export completed with no data (0 rows) exported to {os.path.basename(file_path)}"
# #             else:
# #                 success_message = f"Successfully exported {len(df)} rows to {os.path.basename(file_path)}"
            
# #             row_count = len(df)
# #             self.signals.finished.emit(
# #                 self.process_id, success_message, time_taken , row_count)
                
# #         except Exception as e:
# #             error_msg = f"An error occurred during export: {e}"
# #             print(error_msg)
# #             # import traceback
# #             # traceback.print_exc()
# #             self.signals.error.emit(self.process_id, error_msg)

# #         finally:
# #             if conn:
# #                 conn.close()


# class RunnableExportFromModel(QRunnable):
#     def __init__(self, process_id, item_data, table_name, export_options, signals):
#         super().__init__()
#         self.process_id = process_id
#         self.item_data = item_data
#         self.table_name = table_name
#         self.export_options = export_options
#         self.signals = signals

#     def run(self):
#         start_time = time.time()
#         try:
#             rows, cols = self.model.rowCount(), self.model.columnCount()
#             headers = [self.model.headerData(c, Qt.Orientation.Horizontal) for c in range(cols)]
#             data = []
#             for r in range(rows):
#                 row_data = []
#                 for c in range(cols):
#                     index = self.model.index(r, c)
#                     row_data.append(self.model.data(index))
#                 data.append(row_data)
#             df = pd.DataFrame(data, columns=headers)

#             file_path = self.export_options['filename']
#             file_format = os.path.splitext(file_path)[1].lower()

#             if file_format == ".xlsx":
#                 df.to_excel(file_path, index=False, header=self.export_options['header'])
#             else:
#                 delimiter = self.export_options.get('delimiter', ',')
                
#                 # --- NEW LOGIC: Enforce Semicolon (;) ---
                
#                 if file_format in [".csv", ".txt"]:
#                     if delimiter != ';':
#                         error_msg = (
#                             f"Export Error: Comma (,) is not allowed.\n"
#                             f"Please select Semicolon (;) to export successfully."
#                         )
#                         self.signals.error.emit(self.process_id, error_msg)
#                         return # Stop execution here
#                 # ----------------------------------------

#                 if not delimiter: delimiter = ','
                
#                 df.to_csv(
#                     file_path,
#                     index=False,
#                     header=self.export_options['header'],
#                     sep=delimiter,
#                     encoding=self.export_options['encoding'],
#                     quotechar=self.export_options['quote']
#                 )

#             time_taken = time.time() - start_time
#             if len(df) == 0:
#                 msg = f"Export completed with no data (0 rows) exported to {os.path.basename(file_path)}"
#             else:
#                 msg = f"Exported {len(df)} rows to {os.path.basename(file_path)}"

#             row_count = len(df)   
#             self.signals.finished.emit(self.process_id, msg, time_taken, row_count)

#         except Exception as e:
#             self.signals.error.emit(self.process_id, str(e))


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
#         cursor = None
#         start_time = time.time()

#         try:
#             if not self.conn_data:
#                 raise ConnectionError("Incomplete connection information.")

#             code = (self.conn_data.get("code") or "").upper()
#             if not code:
#                 # Fallback check based on keys if code isn't explicitly set
#                 if "host" in self.conn_data:
#                     code = "POSTGRES"
#                 elif "db_path" in self.conn_data:
#                     # Could be SQLite or CSV, simplistic check for now or assume SQLite
#                     # Ideally main_window passes 'code' correctly.
#                     code = "SQLITE" 

#             # --- CSV via CData ---
#             if code == "CSV":
#                 folder_path = self.conn_data.get("db_path")
#                 if not folder_path:
#                     raise ValueError("CSV folder path missing.")
#                 # Transform query for CSV tables
#                 self.query = transform_csv_query(self.query, folder_path)

#                 conn = mod.connect(f"URI={folder_path};")
#                 cursor = conn.cursor()
#                 cursor.execute(self.query)

#                 columns = [d[0] for d in cursor.description] if cursor.description else []
#                 results = cursor.fetchall() if cursor.description else []
#                 row_count = len(results)
                
#             # --- SQLite ---
#             elif code == "SQLITE":
#                 import db  # your SQLite helper module
#                 db_path = self.conn_data.get("db_path")
#                 if not db_path:
#                     raise ValueError("SQLite database path missing.")

#                 conn = db.create_sqlite_connection(db_path)
#                 cursor = conn.cursor()
#                 cursor.execute(self.query)

#                 if self._is_cancelled:
#                     return

#                 columns = [desc[0] for desc in cursor.description] if cursor.description else []
#                 results = cursor.fetchall() if cursor.description else []
#                 row_count = len(results) if cursor.description else cursor.rowcount

#             # --- Postgres ---
#             elif code == "POSTGRES":
#                 import db  # your Postgres helper module
#                 conn = db.create_postgres_connection(
#                     host=self.conn_data["host"],
#                     database=self.conn_data["database"],
#                     user=self.conn_data["user"],
#                     password=self.conn_data["password"],
#                     port=int(self.conn_data["port"]) if self.conn_data.get("port") else 5432
#                 )
#                 cursor = conn.cursor()
#                 cursor.execute(self.query)

#                 if self._is_cancelled:
#                     return

#                 columns = [desc[0] for desc in cursor.description] if cursor.description else []
#                 results = cursor.fetchall() if cursor.description else []
#                 row_count = len(results) if cursor.description else cursor.rowcount

#             else:
#                 # Generic fallback if code not matched but we have db_path (likely sqlite)
#                 if self.conn_data.get("db_path"):
#                      conn = db.create_sqlite_connection(self.conn_data["db_path"])
#                      cursor = conn.cursor()
#                      cursor.execute(self.query)
#                      columns = [desc[0] for desc in cursor.description] if cursor.description else []
#                      results = cursor.fetchall() if cursor.description else []
#                      row_count = len(results)
#                 else:
#                     raise ValueError(f"Unsupported database type: {code}")

#             if self._is_cancelled:
#                 return

#             elapsed_time = time.time() - start_time
#             is_select_query = self.query.lower().strip().startswith("select")

#             # Emit results
#             self.signals.finished.emit(
#                 self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query
#             )

#         except Exception as e:
#              if not self._is_cancelled:
#                 elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
#                 self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )

#         finally:
#             if cursor:
#                 cursor.close()
#             if conn:
#                 conn.close()

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
            if file_format in [".csv", ".txt"] and delimiter != ';':
                error_msg = "Export Error: Comma (,) is not allowed. Please select Semicolon (;) to export."
                self.signals.error.emit(self.process_id, error_msg)
                return

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
                if file_format in [".csv", ".txt"]:
                    if delimiter != ';':
                        error_msg = "Export Error: Only ';' (semicolon) is allowed."
                        self.signals.error.emit(self.process_id, error_msg)
                        return 
                
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
                # Fallback check
                if "host" in self.conn_data:
                    code = "POSTGRES"
                elif "db_path" in self.conn_data:
                    code = "SQLITE" 

            # --- CSV via CData ---
            if code == "CSV":
                folder_path = self.conn_data.get("db_path")
                if not folder_path:
                    raise ValueError("CSV folder path missing.")
                self.query = transform_csv_query(self.query, folder_path)
                conn = mod.connect(f"URI={folder_path};")
                cursor = conn.cursor()
                cursor.execute(self.query)
                columns = [d[0] for d in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results)
                
            # --- SQLite ---
            elif code == "SQLITE":
                db_path = self.conn_data.get("db_path")
                if not db_path:
                    raise ValueError("SQLite database path missing.")
                conn = db.create_sqlite_connection(db_path)
                cursor = conn.cursor()
                cursor.execute(self.query)
                if self._is_cancelled: return
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results) if cursor.description else cursor.rowcount

            # --- Postgres ---
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
                if self._is_cancelled: return
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                results = cursor.fetchall() if cursor.description else []
                row_count = len(results) if cursor.description else cursor.rowcount

            else:
                # Final Fallback
                if self.conn_data.get("db_path"):
                     conn = db.create_sqlite_connection(self.conn_data["db_path"])
                     cursor = conn.cursor()
                     cursor.execute(self.query)
                     columns = [desc[0] for desc in cursor.description] if cursor.description else []
                     results = cursor.fetchall() if cursor.description else []
                     row_count = len(results)
                else:
                    raise ValueError(f"Unsupported database type: {code}")

            if self._is_cancelled:
                return

            elapsed_time = time.time() - start_time
            is_select_query = self.query.lower().strip().startswith("select")
            
            if not is_select_query and conn:
                # INSERT, UPDATE, DELETE 
                conn.commit()
            self.signals.finished.emit(
                self.conn_data, self.query, results, columns, row_count, elapsed_time, is_select_query
            )

        except Exception as e:
             if not self._is_cancelled:
                if conn:
                    conn.rollback()
                elapsed_time = time.time() - start_time if 'start_time' in locals() else 0
                self.signals.error.emit(self.conn_data, self.query, 0, elapsed_time, str(e) )

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
