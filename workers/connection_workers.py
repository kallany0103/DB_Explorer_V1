import os
import re
import sqlite3 as sqlite
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, QRunnable, QThread, Signal

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
                            WHERE s.srvname = %s
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

                data_sources_result.append({
                    "ds_data": ds,
                    "server_info": server_info,
                    "foreign_tables": foreign_tables,
                })

            try:
                self.signals.finished.emit({
                    "conn_data": self.conn_data,
                    "data_sources": data_sources_result,
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


