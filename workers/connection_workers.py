import os
import re
import sqlite3 as sqlite
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, QRunnable, QThread, Signal
from db.db_connections import DB_FILE
import db
from db.schema_retrieval import _subprocess_fetch_servicenow_schema


class SchemaWorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(object)


class SQLiteSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        db_path = self.conn_data.get("db_path")
        if not db_path or not os.path.exists(db_path):
            try:
                self.signals.error.emit(f"SQLite DB path not found: {db_path}")
            except RuntimeError:
                pass
            return

        conn = None
        try:
            conn = sqlite.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type FROM sqlite_master "
                "WHERE type IN ('table', 'view') "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY type, name;"
            )
            rows = cursor.fetchall()
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "rows": rows})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


class PostgresSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            app_name = f"Universal SQL Client (Schema) - {self.conn_data.get('database', 'postgres')}"
            conn = db.get_pooled_postgres_connection(self.conn_data, application_name=app_name, use_pool=True)
            
            if not conn:
                # The connection failed, the error was already logged by the pool
                try:
                    self.signals.error.emit("Failed to establish database connection.")
                except RuntimeError:
                    pass
                return

            cursor = conn.cursor()
            cursor.execute(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%%' "
                "AND nspname != 'information_schema' "
                "ORDER BY nspname;"
            )
            schemas = [row[0] for row in cursor.fetchall()]
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "schemas": schemas})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                try:
                    db.return_pooled_postgres_connection(self.conn_data, conn=conn)
                except Exception:
                    pass


class CsvSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        folder_path = self.conn_data.get("db_path")
        if not folder_path or not os.path.exists(folder_path):
            try:
                self.signals.error.emit(f"CSV folder not found: {folder_path}")
            except RuntimeError:
                pass
            return

        try:
            csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]
            csv_files.sort()
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "files": csv_files})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass


class ServiceNowSchemaWorker(QRunnable):
    """Loads the ServiceNow table list off the GUI thread."""

    DEFAULT_TABLES = ["incident", "task", "change_request", "problem"]

    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            conn = db.create_servicenow_connection(self.conn_data)
            if not conn:
                try:
                    self.signals.error.emit("Unable to connect to ServiceNow")
                except RuntimeError:
                    pass
                return

            cursor = conn.cursor()
            try:
                cursor.execute("SELECT TableName FROM sys_tables")
                tables = [row[0] for row in cursor.fetchall()]
            except Exception:
                tables = list(self.DEFAULT_TABLES)

            try:
                self.signals.finished.emit(
                    {"conn_data": self.conn_data, "tables": tables}
                )
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


class ERDSchemaFetchWorker(QRunnable):
    """Fetches the complete filtered schema for ERD generation off the GUI thread."""

    def __init__(self, item_data):
        super().__init__()
        self.item_data = item_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        try:
            item_data = self.item_data
            db_type_val = (
                item_data.get("db_type") or item_data.get("type") or
                item_data.get("code") or ""
            ).upper()
            schema_name = item_data.get("schema_name")
            table_name  = item_data.get("table_name")
            conn_info   = item_data.get("conn_data") or item_data

            if "POSTGRES" in db_type_val:
                full_schema = db.get_postgres_schema(conn_info, schema_name=schema_name)
            elif "SQLITE" in db_type_val:
                sqlite_db_path = conn_info.get("db_path") if isinstance(conn_info, dict) else conn_info
                full_schema = db.get_sqlite_schema(sqlite_db_path)
            elif "CSV" in db_type_val:
                full_schema = db.get_csv_schema(conn_info)
            elif "SERVICENOW" in db_type_val:
                with ProcessPoolExecutor(max_workers=1) as executor:
                    full_schema = executor.submit(
                        _subprocess_fetch_servicenow_schema, conn_info, table_name
                    ).result(timeout=300)
            elif "ORACLE" in db_type_val:
                full_schema = db.get_oracle_schema(conn_info, schema_name=schema_name)
            else:
                try:
                    self.signals.error.emit(
                        f"ERD generation is not supported for {db_type_val or 'unknown type'}"
                    )
                except RuntimeError:
                    pass
                return

            if not full_schema:
                try:
                    self.signals.error.emit("Could not retrieve schema data for ERD.")
                except RuntimeError:
                    pass
                return

            # Filter to just the requested table + its FK neighbours
            filtered_schema = full_schema
            if table_name:
                target = (
                    f"{schema_name}.{table_name}"
                    if schema_name and "POSTGRES" in db_type_val
                    else table_name
                )
                if target in full_schema:
                    related = {target}
                    for fk in full_schema[target].get("foreign_keys", []):
                        related.add(fk["table"])
                    for t_name, t_info in full_schema.items():
                        for fk in t_info.get("foreign_keys", []):
                            if fk["table"] == target:
                                related.add(t_name)
                    filtered_schema = {n: v for n, v in full_schema.items() if n in related}

            if not filtered_schema:
                try:
                    self.signals.error.emit("No related tables found for ERD.")
                except RuntimeError:
                    pass
                return

            try:
                self.signals.finished.emit(filtered_schema)
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass


class AvailableSchemasWorker(QThread):
    """Fetches available Postgres schema names off the GUI thread."""

    schemas_ready = Signal(list)

    def __init__(self, conn_data: dict, schema_data: dict, parent=None):
        super().__init__(parent)
        self._conn_data = conn_data
        self._schema_data = schema_data

    def run(self):
        _default_schema = "public"
        schemas: list[str] = []
        if self._conn_data:
            db_type = self._conn_data.get('db_type', '')
            if db_type == 'postgres':
                schemas = db.get_postgres_available_schemas(self._conn_data)
        if not schemas:
            fallback = {
                v.get('schema', _default_schema)
                for v in self._schema_data.values()
                if isinstance(v, dict)
            }
            fallback.discard('')
            schemas = sorted(fallback)
        if _default_schema not in schemas:
            schemas.insert(0, _default_schema)
        self.schemas_ready.emit(schemas)


class ServiceNowTableDetailsWorker(QRunnable):
    """Loads column metadata for a single ServiceNow table off the GUI thread."""

    def __init__(self, conn_data, table_name):
        super().__init__()
        self.conn_data = conn_data
        self.table_name = table_name
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            conn = db.create_servicenow_connection(self.conn_data)
            if not conn:
                try:
                    self.signals.error.emit("Unable to connect to ServiceNow")
                except RuntimeError:
                    pass
                return

            cursor = conn.cursor()
            try:
                cursor.execute(f"SELECT * FROM {self.table_name} LIMIT 0")
            except Exception:
                cursor.execute(f"SELECT * FROM {self.table_name} WHERE 1=0")

            columns = [col[0] for col in (cursor.description or [])]

            try:
                self.signals.finished.emit(
                    {
                        "conn_data": self.conn_data,
                        "table_name": self.table_name,
                        "columns": columns,
                    }
                )
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass

class OracleSchemaWorker(QRunnable):
    """Fetches the list of accessible Oracle schema owners off the GUI thread.

    Emits ``{"conn_data": ..., "schemas": ["OWNER1", "OWNER2", ...]}`` so the
    UI can build a hierarchical Schemas → Owner → object-type groups tree, with
    per-group contents loaded lazily on expand.
    """

    # Object types we want to surface in the schema tree
    _OBJECT_TYPES = (
        "TABLE",
        "VIEW",
        "MATERIALIZED VIEW",
        "PROCEDURE",
        "FUNCTION",
        "SEQUENCE",
        "PACKAGE",
        "SYNONYM",
        "DATABASE LINK",
        "JAVA SOURCE",
        "JAVA CLASS",
    )

    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            conn = db.get_pooled_oracle_connection(conn_data=self.conn_data)
            if not conn:
                try:
                    self.signals.error.emit("Failed to establish Oracle connection.")
                except RuntimeError:
                    pass
                return

            cursor = conn.cursor()
            placeholders = ",".join(f"'{t}'" for t in self._OBJECT_TYPES)
            cursor.execute(
                f"SELECT DISTINCT owner FROM all_objects "
                f"WHERE object_type IN ({placeholders}) "
                f"ORDER BY owner"
            )
            schemas = [row[0] for row in cursor.fetchall()]

            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "schemas": schemas})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


class UDSSchemaWorker(QRunnable):
    """Fetches all data sources, foreign servers, and foreign tables for a UDS host connection off the GUI thread."""

    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            conn_id = self.conn_data.get("id")
            raw_data_sources = db.get_data_sources_by_connection(conn_id) if conn_id else []
            if not raw_data_sources:
                raw_data_sources = self.conn_data.get("usf_data_sources", [])

            app_name = f"Universal SQL Client (UDS Schema) - {self.conn_data.get('database', 'postgres')}"
            try:
                conn = db.get_pooled_postgres_connection(self.conn_data, application_name=app_name, use_pool=True)
                if conn:
                    try:
                        # Automatically ensure necessary FDW extensions on host database
                        db.ensure_host_fdw_extensions(self.conn_data)
                    except Exception as ext_init_err:
                        print(f"Notice: FDW auto-initialization notice: {ext_init_err}")
            except Exception as conn_err:
                print(f"Warning: could not connect to UDS host database: {conn_err}")
                conn = None

            cursor = conn.cursor() if conn else None
            data_sources_result = []

            for ds in raw_data_sources:
                server_name = ds.get("server_name")
                if not server_name:
                    raw_name = ds.get("short_name") or ds.get("source_name") or ds.get("name") or "foreign_source"
                    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', str(raw_name)).strip('_').lower()
                    server_name = f"srv_{cleaned}"

                server_info = {
                    "server_name": server_name,
                    "fdw_name": ds.get("fdw_name", "postgres_fdw"),
                    "user_mappings": [],
                }
                foreign_tables = []

                if cursor:
                    try:
                        # 1. Foreign Server details
                        cursor.execute("""
                            SELECT s.srvname, f.fdwname
                            FROM pg_foreign_server s
                            JOIN pg_foreign_data_wrapper f ON f.oid = s.srvfdw
                            WHERE s.srvname = %s;
                        """, (server_name,))
                        srv_row = cursor.fetchone()
                        if srv_row:
                            server_info["fdw_name"] = srv_row[1]

                        # User mappings
                        try:
                            cursor.execute("""
                                SELECT usename
                                FROM pg_user_mappings
                                WHERE srvname = %s
                                ORDER BY 1;
                            """, (server_name,))
                            server_info["user_mappings"] = [r[0] for r in cursor.fetchall() if r[0]]
                        except Exception:
                            try:
                                cursor.execute("""
                                    SELECT authorization_identifier
                                    FROM information_schema.user_mappings
                                    WHERE foreign_server_name = %s
                                    ORDER BY 1;
                                """, (server_name,))
                                server_info["user_mappings"] = [r[0] for r in cursor.fetchall() if r[0]]
                            except Exception:
                                server_info["user_mappings"] = []

                        # 2. Foreign Tables associated with this Foreign Server
                        cursor.execute("""
                            SELECT c.relname, n.nspname
                            FROM pg_foreign_table ft
                            JOIN pg_class c ON c.oid = ft.ftrelid
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            JOIN pg_foreign_server s ON s.oid = ft.ftserver
                            WHERE s.srvname = %s AND c.relname NOT IN ('emp_ft', 'epm_f', 'epm_foreign')
                            ORDER BY c.relname;
                        """, (server_name,))
                        foreign_tables = [
                            {"table_name": r[0], "schema_name": r[1]}
                            for r in cursor.fetchall()
                        ]
                    except Exception as ds_err:
                        print(f"Notice: error reading foreign objects for data source {server_name}: {ds_err}")

                # If SQLite data source and foreign_tables is empty (e.g. cloud host without sqlite_fdw extension),
                # introspect the local SQLite database file directly so all tables and columns appear seamlessly
                source_type = (ds.get("source_type") or "").upper()
                if source_type == "SQLITE" and not foreign_tables:
                    db_path = ds.get("db_path") or ds.get("file_path")
                    if db_path and os.path.exists(db_path):
                        try:
                            import sqlite3 as sqlite_reader
                            with sqlite_reader.connect(db_path) as s_conn:
                                s_cur = s_conn.cursor()
                                s_cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;")
                                foreign_tables = [{"table_name": r[0], "schema_name": "main"} for r in s_cur.fetchall()]
                        except Exception as s_err:
                            print(f"Notice: error reading SQLite tables for {db_path}: {s_err}")
                elif source_type in ("CSV", "FILE", "FLAT_FILE") and not foreign_tables:
                    f_path = ds.get("file_path") or ds.get("db_path")
                    csv_files = ds.get("csv_files") or []
                    if csv_files:
                        for cf in csv_files:
                            tbl_name = cf.get("table_name") or os.path.splitext(os.path.basename(cf.get("file_path", "")))[0]
                            if tbl_name:
                                foreign_tables.append({"table_name": tbl_name, "schema_name": "csv_main"})
                    elif f_path and os.path.exists(f_path):
                        if os.path.isfile(f_path):
                            tbl_name = os.path.splitext(os.path.basename(f_path))[0]
                            foreign_tables = [{"table_name": tbl_name, "schema_name": "csv_main"}]
                        elif os.path.isdir(f_path):
                            for root, _, files in os.walk(f_path):
                                for f in files:
                                    if f.lower().endswith(".csv"):
                                        tbl_name = os.path.splitext(f)[0]
                                        foreign_tables.append({"table_name": tbl_name, "schema_name": "csv_main"})

                try:
                    is_healthy, ping_msg, latency_ms = db.test_data_source_connection(ds, self.conn_data)
                    ds["is_healthy"] = is_healthy
                except Exception as ping_err:
                    print(f"Notice: ping error for data source {ds.get('short_name')}: {ping_err}")
                    ds["is_healthy"] = False

                data_sources_result.append({
                    "ds_data": ds,
                    "server_info": server_info,
                    "foreign_tables": foreign_tables,
                })

            unified_views = []
            if cursor:
                try:
                    cursor.execute("""
                        SELECT c.relname, n.nspname
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE c.relkind IN ('v', 'm')
                          AND (n.nspname = 'uds_views' OR (n.nspname = 'public' AND (c.relname LIKE 'v\_%' ESCAPE '\' OR c.relname LIKE 'uds\_%' ESCAPE '\')))
                        ORDER BY c.relname;
                    """)
                    unified_views = [
                        {"view_name": r[0], "schema_name": r[1]}
                        for r in cursor.fetchall()
                    ]
                except Exception as v_err:
                    print(f"Notice: error reading unified views on UDS host: {v_err}")

            try:
                self.signals.finished.emit({
                    "conn_data": self.conn_data,
                    "data_sources": data_sources_result,
                    "unified_views": unified_views,
                })
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                try:
                    db.return_pooled_postgres_connection(self.conn_data, conn=conn)
                except Exception:
                    pass



# Backward compatibility alias
UDSDataSourceSchemaWorker = UDSSchemaWorker


class DataSourcePingSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class DataSourcePingWorker(QRunnable):
    """Asynchronous background worker to test data source connection health."""

    def __init__(self, ds_data: dict, host_conn_data: dict = None):
        super().__init__()
        self.ds_data = ds_data
        self.host_conn_data = host_conn_data
        self.signals = DataSourcePingSignals()

    def run(self):
        try:
            is_connected, message, latency_ms = db.test_data_source_connection(
                self.ds_data, self.host_conn_data
            )
            self.signals.finished.emit({
                "ds_data": self.ds_data,
                "is_connected": is_connected,
                "message": message,
                "latency_ms": latency_ms
            })
        except Exception as exc:
            self.signals.error.emit(str(exc))

class ImportWorkerSignals(QObject):
    finished = Signal(list)   # emits hierarchy_data fetched on background thread
    error = Signal(str)

class ImportConnectionsWorker(QRunnable):
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.signals = ImportWorkerSignals()

    def _insert_connection(self, c, conn_data, group_id):
        if conn_data.get("db_path"):
            c.execute(
                "INSERT INTO usf_connections (name, short_name, connection_group_id, db_path) VALUES (?, ?, ?, ?)",
                (conn_data.get("name"), conn_data.get("short_name"), group_id, conn_data.get("db_path")),
            )
        elif conn_data.get("instance_url"):
            c.execute(
                'INSERT INTO usf_connections (name, short_name, connection_group_id, instance_url, "user", password) VALUES (?, ?, ?, ?, ?, ?)',
                (conn_data.get("name"), conn_data.get("short_name"), group_id,
                 conn_data.get("instance_url"), conn_data.get("user"), conn_data.get("password")),
            )
        else:
            c.execute(
                'INSERT INTO usf_connections (name, short_name, connection_group_id, host, "database", "user", password, port, dsn) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (conn_data.get("name"), conn_data.get("short_name"), group_id,
                 conn_data.get("host"), conn_data.get("database"), conn_data.get("user"),
                 conn_data.get("password"), conn_data.get("port"), conn_data.get("dsn")),
            )

    def _update_connection(self, c, conn_id, conn_data):
        if conn_data.get("db_path"):
            c.execute("UPDATE usf_connections SET short_name=?, db_path=? WHERE id=?",
                      (conn_data.get("short_name"), conn_data.get("db_path"), conn_id))
        elif conn_data.get("instance_url"):
            c.execute('UPDATE usf_connections SET short_name=?, instance_url=?, "user"=?, password=? WHERE id=?',
                      (conn_data.get("short_name"), conn_data.get("instance_url"), conn_data.get("user"), conn_data.get("password"), conn_id))
        else:
            c.execute('UPDATE usf_connections SET short_name=?, host=?, "database"=?, "user"=?, password=?, port=?, dsn=? WHERE id=?',
                      (conn_data.get("short_name"), conn_data.get("host"), conn_data.get("database"), conn_data.get("user"),
                       conn_data.get("password"), conn_data.get("port"), conn_data.get("dsn"), conn_id))

    def run(self):
       
        try:
            with sqlite.connect(DB_FILE) as conn:
                conn.isolation_level = "DEFERRED"  
                c = conn.cursor()
                c.execute("BEGIN")

                for type_data in self.data:
                    type_code = type_data.get('code')
                    c.execute("SELECT id FROM usf_connection_types WHERE code = ?", (type_code,))
                    type_row = c.fetchone()
                    if not type_row:
                        continue
                    type_id = type_row[0]

                    for group_data in type_data.get('usf_connection_groups', []):
                        group_name = group_data.get('name')
                        c.execute(
                            "SELECT id FROM usf_connection_groups WHERE name = ? AND connection_type_id = ?",
                            (group_name, type_id),
                        )
                        group_row = c.fetchone()
                        if group_row:
                            group_id = group_row[0]
                        else:
                            c.execute(
                                "INSERT INTO usf_connection_groups (name, connection_type_id) VALUES (?, ?)",
                                (group_name, type_id),
                            )
                            group_id = c.lastrowid

                        for conn_data in group_data.get('usf_connections', []):
                            if conn_data.get("db_path"):
                                c.execute(
                                    "SELECT id FROM usf_connections WHERE connection_group_id = ? AND name = ? AND short_name = ? AND db_path IS ?",
                                    (group_id, conn_data.get('name'), conn_data.get('short_name'), conn_data.get('db_path'))
                                )
                            elif conn_data.get("instance_url"):
                                c.execute(
                                    'SELECT id FROM usf_connections WHERE connection_group_id = ? AND name = ? AND short_name = ? AND instance_url IS ? AND "user" IS ?',
                                    (group_id, conn_data.get('name'), conn_data.get('short_name'), conn_data.get('instance_url'), conn_data.get('user'))
                                )
                            else:
                                c.execute(
                                    'SELECT id FROM usf_connections WHERE connection_group_id = ? AND name = ? AND short_name = ? AND host IS ? AND "database" IS ? AND "user" IS ? AND port IS ?',
                                    (group_id, conn_data.get('name'), conn_data.get('short_name'), conn_data.get('host'), conn_data.get('database'), conn_data.get('user'), conn_data.get('port'))
                                )
                                
                            row = c.fetchone()
                            if row:
                                self._update_connection(c, row[0], conn_data)
                            else:
                                self._insert_connection(c, conn_data, group_id)

                conn.commit()

                hierarchy_data = self._fetch_hierarchy(c)

            self.signals.finished.emit(hierarchy_data)
        except Exception as e:
            self.signals.error.emit(str(e))

    @staticmethod
    def _fetch_hierarchy(c):
        """Fetch full hierarchy using 3 flat queries instead of N+1 nested loops."""

        c.execute("SELECT id, code, name FROM usf_connection_types")
        type_rows = c.fetchall()

        types_by_id   = {r[0]: {'id': r[0], 'code': r[1], 'name': r[2], 'usf_connection_groups': {}} for r in type_rows}
        type_code_by_group_id = {}  

        c.execute("SELECT id, name, connection_type_id FROM usf_connection_groups")
        group_rows = c.fetchall()
        groups_by_id = {}
        for g_id, g_name, t_id in group_rows:
            t_code = types_by_id[t_id]['code'] if t_id in types_by_id else ''
            group_entry = {'id': g_id, 'name': g_name, 'usf_connections': {}}
            groups_by_id[g_id] = group_entry
            type_code_by_group_id[g_id] = t_code
            if t_id in types_by_id:
                types_by_id[t_id]['usf_connection_groups'][g_id] = group_entry

        c.execute(
            'SELECT id, name, short_name, host, "database", "user", password, port, dsn, '
            '       db_path, instance_url, connection_group_id '
            'FROM usf_connections'
        )
        conn_rows = c.fetchall()
        conns_by_id = {}
        for row in conn_rows:
            conn_id, name, short_name, host, db, user, pwd, port, dsn, db_path, instance_url, g_id = row
            code = type_code_by_group_id.get(g_id, '')
            conn_entry = {
                "id": conn_id, "name": name, "short_name": short_name,
                "host": host, "database": db, "user": user, "password": pwd,
                "port": port, "dsn": dsn, "db_path": db_path,
                "instance_url": instance_url, "db_type": code.lower(),
                "usf_data_sources": [],
            }
            conns_by_id[conn_id] = conn_entry
            if g_id in groups_by_id:
                groups_by_id[g_id]['usf_connections'][conn_id] = conn_entry

        c.execute(
            """SELECT id, source_name, display_name, source_type, host, port,
                      database_name, username, password, schema_name, service_url,
                      file_path, config_json, server_name, fdw_name, status, connection_id
               FROM usf_data_sources
               ORDER BY connection_id, source_name"""
        )
        for ds in c.fetchall():
            (ds_id, ds_src, ds_disp, ds_type, ds_host, ds_port, ds_db,
             ds_user, ds_pwd, ds_schema, ds_url, ds_fpath, ds_cfg,
             ds_srv, ds_fdw, ds_stat, conn_id) = ds
            if conn_id in conns_by_id:
                conns_by_id[conn_id]["usf_data_sources"].append({
                    "id": ds_id, "connection_id": conn_id,
                    "source_name": ds_src, "short_name": ds_src,
                    "name": ds_disp, "display_name": ds_disp,
                    "source_type": ds_type, "host": ds_host, "port": ds_port,
                    "database": ds_db, "database_name": ds_db,
                    "user": ds_user, "username": ds_user, "password": ds_pwd,
                    "schema": ds_schema, "schema_name": ds_schema,
                    "service_url": ds_url, "file_path": ds_fpath,
                    "config_json": ds_cfg, "server_name": ds_srv,
                    "fdw_name": ds_fdw or "postgres_fdw", "status": ds_stat,
                    "db_type": (ds_type or "postgres").lower(),
                })

        result = []
        for t_id, t_code, t_name in type_rows:
            type_out = {'id': t_id, 'code': t_code, 'name': t_name, 'usf_connection_groups': []}
            for g_id, g_name, g_type_id in group_rows:
                if g_type_id != t_id:
                    continue
                g_node = groups_by_id[g_id]
                type_out['usf_connection_groups'].append({
                    'id': g_id, 'name': g_name,
                    'usf_connections': list(g_node['usf_connections'].values()),
                })
            result.append(type_out)
        return result
