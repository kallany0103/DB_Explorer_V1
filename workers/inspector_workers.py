# workers/inspector_workers.py

import datetime
from PySide6.QtCore import QObject, Signal, QRunnable
import db
from dialogs.properties import pg_queries, oracle_queries
from workers.inspector_stats import fetch_statistics_results

_INT64_MAX = 9223372036854775807
_INT64_MIN = -9223372036854775808


def _sanitize_for_qt(val):
    """Recursively convert large integers, datetimes, and LOBs so Shiboken won't fail marshaling."""
    if isinstance(val, dict):
        return {str(k): _sanitize_for_qt(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_sanitize_for_qt(v) for v in val]
    elif isinstance(val, tuple):
        return tuple(_sanitize_for_qt(v) for v in val)
    elif isinstance(val, int) and not isinstance(val, bool):
        if val > _INT64_MAX or val < _INT64_MIN:
            return str(val)
        return val
    elif hasattr(val, "read") and callable(getattr(val, "read", None)):
        try:
            return val.read()
        except Exception:
            return str(val)
    elif isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return val


class InspectorSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)

class InspectorWorker(QRunnable):
    def __init__(self, item_data, obj_name, task_type="properties"):
        super().__init__()
        self.item_data = item_data
        self.obj_name = obj_name
        self.task_type = task_type
        self.signals = InspectorSignals()

    def _is_oracle(self):
        conn_data = self.item_data.get('conn_data') or self.item_data
        db_type = (self.item_data.get('db_type') or conn_data.get('db_type') or '').lower()
        if 'oracle' in db_type:
            return True
        node_type = str(self.item_data.get('type', '')).lower()
        if 'oracle' in node_type:
            return True
        if (
            conn_data.get('service_name')
            or conn_data.get('oracle_db_type')
            or 'oracle' in str(conn_data.get('db_type', '')).lower()
            or conn_data.get('driver_mode')
            or conn_data.get('oracle_client_dir')
        ):
            return True
        return False

    def run(self):
        conn = None
        try:
            conn_data = self.item_data.get('conn_data') or self.item_data
            if self._is_oracle():
                conn = db.get_pooled_oracle_connection(conn_data=conn_data)
                if not conn:
                    raise ConnectionError("Failed to establish Oracle database connection. The server might be unreachable or connection parameters are incorrect.")
                cursor = conn.cursor()
                result = {}
                if self.task_type == "properties":
                    result = self._fetch_oracle_properties(cursor, conn_data)
                else:
                    result = self._fetch_oracle_statistics(cursor)
                result = _sanitize_for_qt(result)
                self.signals.finished.emit(result)
            else:
                pg_conn_data = {key: conn_data.get(key) for key in ['host', 'port', 'database', 'user', 'password']}
                conn = db.create_postgres_connection(**pg_conn_data, bypass_cooldown=True)
                
                if not conn:
                    raise ConnectionError("Failed to establish database connection. The server might be unreachable or the connection parameters are incorrect.")
                    
                cursor = conn.cursor()
                
                result = {}
                if self.task_type == "properties":
                    result = self._fetch_properties(cursor)
                else:
                    result = self._fetch_statistics(cursor)
                result = _sanitize_for_qt(result)
                self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def _fetch_properties(self, cursor):
        obj_type = self.item_data.get('type')
        table_type = str(self.item_data.get('table_type', '')).upper()
        table_name = self.item_data.get('table_name')
        if table_name:
            if "TRIGGER" in table_type:
                obj_type = "trigger_function"
            elif "FUNCTION" in table_type:
                obj_type = "function"
            elif "SEQUENCE" in table_type:
                obj_type = "sequence"
            elif "MATERIALIZED" in table_type:
                obj_type = "materialized_view"
            elif "VIEW" in table_type:
                obj_type = "view"
            elif obj_type in ("schema_group", "group"):
                obj_type = "table"

        group_name = self.item_data.get('group_name')
        schema_name = self.item_data.get('schema_name', 'public')
        
        # Auto-detect group from type if group_name is missing (for root nodes)
        if not group_name and obj_type and obj_type.endswith('_root'):
            if obj_type == 'schemas_root':
                group_name = "Schemas"
            elif obj_type == 'tables_root':
                group_name = "Tables"
            elif obj_type == 'views_root':
                group_name = "Views"
            elif obj_type == 'functions_root':
                group_name = "Functions"
            elif obj_type == 'fdw_root':
                group_name = "Foreign Data Wrappers"
            elif obj_type == 'extension_root':
                group_name = "Extensions"
            elif obj_type == 'language_root':
                group_name = "Languages"

        data = {"type": "object", "details": {}, "sql": ""}
        
        is_specific_object = obj_type in [
            'table', 'view', 'materialized_view', 'matview', 'schema',
            'function', 'trigger_function', 'sequence', 'connection',
            'extension', 'language', 'fdw', 'foreign_server', 'user_mapping', 'trigger'
        ]
        
        if group_name and not is_specific_object:
            data["type"] = "group"
            data["group_name"] = group_name
            query = None
            if group_name == "Schemas":
                query = pg_queries.LIST_SCHEMAS
            elif group_name == "Tables":
                query = pg_queries.LIST_TABLES
            elif group_name == "Views":
                query = pg_queries.LIST_VIEWS
            elif group_name == "Materialized Views":
                query = pg_queries.LIST_MATVIEWS
            elif group_name == "Functions":
                query = pg_queries.LIST_FUNCTIONS
            elif group_name == "Trigger Functions":
                query = pg_queries.LIST_TRIGGER_FUNCTIONS
            elif group_name in ("Foreign Data Wrappers", "FDW") or obj_type == "fdw_root":
                query = pg_queries.LIST_FDWS
            elif group_name == "Languages" or obj_type == "language_root":
                query = pg_queries.LIST_LANGUAGES
            elif group_name == "Sequences":
                query = pg_queries.LIST_SEQUENCES
            elif group_name.startswith("Columns"):
                query = pg_queries.LIST_COLUMNS
            elif group_name.startswith("Constraints"):
                query = pg_queries.LIST_CONSTRAINTS
            elif group_name.startswith("Indexes"):
                query = pg_queries.LIST_INDEXES
            elif group_name == "Triggers":
                query = pg_queries.LIST_TRIGGERS
            
            if query:
                table_name = self.item_data.get('table_name')
                params = []
                if "%s" in query:
                    params.append(schema_name)
                    if query.count("%s") > 1 and table_name:
                        params.append(table_name)
                
                cursor.execute(query, tuple(params))
                data["columns"] = [desc[0] for desc in cursor.description]
                data["rows"] = cursor.fetchall()
            return data

        # Single Object Properties
        if obj_type in ('table', 'view', 'materialized_view', 'matview'):
            cursor.execute(pg_queries.GET_TABLE_DETAILS, (schema_name, self.obj_name))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
            
            # Fetch columns
            cursor.execute(pg_queries.GET_TABLE_COLUMNS, (schema_name, self.obj_name))
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[0],
                    "data_type": row[1],
                    "is_pk": row[2],
                    "nullable": row[3],
                    "default_value": row[4],
                    "comment": row[5]
                })
            data["columns"] = columns
            
            # Fetch constraints
            cursor.execute(pg_queries.GET_TABLE_CONSTRAINTS, (schema_name, self.obj_name))
            constraints = []
            for row in cursor.fetchall():
                constraints.append({
                    "name": row[0],
                    "type": row[1],
                    "definition": row[2]
                })
            data["constraints"] = constraints
            
            # Generate SQL
            is_matview = (
                data["details"].get("Object type") == "Materialized view"
                or obj_type in ("materialized_view", "matview")
                or "MATERIALIZED" in table_type
            )
            is_view = (
                data["details"].get("Object type") == "View"
                or obj_type == "view"
                or ("VIEW" in table_type and not is_matview)
            )

            if is_matview or is_view:
                try:
                    cursor.execute(pg_queries.GET_VIEW_DEF, (schema_name, self.obj_name))
                    v_row = cursor.fetchone()
                    if v_row and v_row[0]:
                        v_def = v_row[0].strip()
                        if not v_def.endswith(";"):
                            v_def += ";"
                        if is_matview:
                            data["sql"] = f'CREATE MATERIALIZED VIEW "{schema_name}"."{self.obj_name}" AS\n{v_def}'
                        else:
                            data["sql"] = f'CREATE OR REPLACE VIEW "{schema_name}"."{self.obj_name}" AS\n{v_def}'
                        comment = data["details"].get("Comment")
                        if comment:
                            target = "MATERIALIZED VIEW" if is_matview else "VIEW"
                            data["sql"] += f'\n\nCOMMENT ON {target} "{schema_name}"."{self.obj_name}" IS \'{comment}\';'
                    else:
                        data["sql"] = f"-- Definition not found for {self.obj_name}"
                except Exception as e:
                    data["sql"] = f"-- Error fetching view definition for {self.obj_name}: {e}"
            else:
                sql_parts = []
                sql_parts.append(f"-- Table: {schema_name}.{self.obj_name}")
                sql_parts.append(f"CREATE TABLE {schema_name}.{self.obj_name} (")
                col_defs = []
                for col in columns:
                    col_def = f"    {col['name']} {col['data_type']}"
                    if not col['nullable']:
                        col_def += " NOT NULL"
                    if col['default_value']:
                        col_def += f" DEFAULT {col['default_value']}"
                    col_defs.append(col_def)
                sql_parts.append(",\n".join(col_defs))
                sql_parts.append(");")
                data["sql"] = "\n".join(sql_parts)
            
        elif obj_type == 'schema':
            cursor.execute(pg_queries.GET_SCHEMA_DETAILS, (self.obj_name,))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
            owner = data["details"].get("Owner") or data["details"].get("owner", "postgres")
            sql_parts = [f"CREATE SCHEMA {self.obj_name}\n    AUTHORIZATION {owner};"]
            comment = data["details"].get("Comment")
            if comment:
                sql_parts.append(f"\nCOMMENT ON SCHEMA {self.obj_name} IS '{comment}';")
            data["sql"] = "\n".join(sql_parts)

            try:
                cursor.execute(pg_queries.LIST_TABLES, (self.obj_name,))
                data["tables"] = {
                    "columns": [desc[0] for desc in cursor.description],
                    "rows": cursor.fetchall()
                }
            except Exception:
                data["tables"] = {"columns": [], "rows": []}
            
        elif obj_type in ('function', 'trigger_function'):
            cursor.execute(pg_queries.GET_FUNCTION_DETAILS, (schema_name, self.obj_name, self.obj_name))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                sql_def = data["details"].pop("Definition", None) or data["details"].pop("definition", "")
                if sql_def:
                    data["sql"] = sql_def.strip() if sql_def.strip().endswith(";") else sql_def.strip() + ";"
                else:
                    data["sql"] = f"-- Function: {schema_name}.{self.obj_name}\n-- Definition not found."
                
        elif obj_type == 'fdw':
            cursor.execute(pg_queries.GET_FDW_DETAILS, (self.obj_name,))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                handler = data["details"].get("handler")
                validator = data["details"].get("validator")
                options = data["details"].get("options")
                sql_parts = [f"CREATE FOREIGN DATA WRAPPER {self.obj_name}"]
                if handler:
                    sql_parts.append(f"    HANDLER {handler}")
                if validator:
                    sql_parts.append(f"    VALIDATOR {validator}")
                if options:
                    sql_parts.append(f"    OPTIONS ({options})")
                data["sql"] = "\n".join(sql_parts) + ";"

        elif obj_type == 'language':
            cursor.execute(pg_queries.GET_LANGUAGE_DETAILS, (self.obj_name,))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                trusted = "TRUSTED " if data["details"].get("is_trusted") else ""
                procedural = "PROCEDURAL " if data["details"].get("is_pl") else ""
                data["sql"] = f"CREATE {trusted}{procedural}LANGUAGE {self.obj_name};"

        elif obj_type == 'extension':
            cursor.execute(pg_queries.GET_EXTENSION_DETAILS, (self.obj_name,))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                ver = data["details"].get("extversion")
                ver_clause = f" VERSION '{ver}'" if ver else ""
                data["sql"] = f"CREATE EXTENSION {self.obj_name}{ver_clause};"
                
        elif obj_type == 'sequence':
            cursor.execute(pg_queries.GET_SEQUENCE_DETAILS, (schema_name, self.obj_name))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
            data["sql"] = f"-- Sequence: {schema_name}.{self.obj_name}\n\nCREATE SEQUENCE {schema_name}.{self.obj_name} ...;"
            
        elif obj_type == 'connection':
            cursor.execute("SELECT version(), current_database(), current_user, inet_server_addr(), inet_server_port();")
            row = cursor.fetchone()
            if row:
                data["details"] = {
                    "Version": row[0],
                    "Database": row[1],
                    "User": row[2],
                    "Server Address": row[3],
                    "Server Port": row[4],
                    "Connection Name": self.item_data.get('name', ''),
                    "Short Name": self.item_data.get('short_name', '')
                }
            data["sql"] = ""

        elif obj_type == 'trigger':
            trigger_name = self.item_data.get('trigger_name') or self.obj_name
            cursor.execute(pg_queries.GET_TRIGGER_DETAILS, (schema_name, trigger_name))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                row_dict = dict(zip(cols, row))
                
                # Format enabled status (O=origin/enabled, D=disabled, A=always, R=replica)
                status_map = {
                    'O': 'Enabled (fires normally)',
                    't': 'Enabled',
                    'D': 'Disabled',
                    'A': 'Enabled (always)',
                    'R': 'Enabled (replica only)'
                }
                enabled_val = row_dict.get('enabled')
                row_dict['status'] = status_map.get(enabled_val, f"Unknown ({enabled_val})")
                
                # SQL definition formatting
                definition = row_dict.get('definition')
                table_name = row_dict.get('table_name')
                if definition:
                    data["sql"] = f"-- Trigger: {trigger_name} on {schema_name}.{table_name}\n\n{definition};"
                else:
                    data["sql"] = "-- Definition not found."
                
                # Remove fields that shouldn't clutter the properties grid
                for k in ['enabled', 'definition', 'name']:
                    if k in row_dict:
                        del row_dict[k]
                
                data["details"] = row_dict

        return data

    def _fetch_statistics(self, cursor):
        return fetch_statistics_results(cursor, self.item_data, self.obj_name)

    def _fetch_oracle_properties(self, cursor, conn_data):
        obj_type = self.item_data.get('type', '')
        table_type = str(self.item_data.get('table_type', '')).upper()
        group_name = self.item_data.get('group_name')
        if not group_name and obj_type in ('oracle_schema_group', 'schema_group'):
            group_name = self.obj_name
        schema_name = (self.item_data.get('schema_name') or conn_data.get('user') or '').upper()
        eff_obj = self.obj_name.upper()

        if obj_type == 'oracle_schemas_root':
            group_name = "Schemas"
        elif obj_type == 'oracle_schema':
            obj_type = 'schema'
        elif obj_type == 'oracle_public_dblinks_root':
            group_name = "Database Links"
        elif obj_type == 'oracle_public_synonyms_root':
            group_name = "Synonyms"
        elif "MATERIALIZED" in table_type:
            obj_type = "materialized_view"
        elif "VIEW" in table_type:
            obj_type = "view"
        elif "TABLE" in table_type:
            obj_type = "table"
        elif "PROCEDURE" in table_type:
            obj_type = "procedure"
        elif "FUNCTION" in table_type:
            obj_type = "function"
        elif "PACKAGE" in table_type:
            obj_type = "package"
        elif "SEQUENCE" in table_type:
            obj_type = "sequence"
        elif "TRIGGER" in table_type:
            obj_type = "trigger"
        elif "SYNONYM" in table_type:
            obj_type = "synonym"
        elif "DATABASE LINK" in table_type:
            obj_type = "oracle_dblink"

        data = {"type": "object", "details": {}, "sql": ""}

        is_specific_object = obj_type in [
            'table', 'view', 'materialized_view', 'matview', 'schema',
            'function', 'procedure', 'package', 'sequence', 'connection',
            'synonym', 'oracle_dblink', 'trigger'
        ]

        if group_name and not is_specific_object:
            data["type"] = "group"
            data["group_name"] = group_name
            query = None

            if group_name == "Schemas":
                query = oracle_queries.LIST_SCHEMAS
            elif group_name == "Tables":
                query = oracle_queries.LIST_TABLES
            elif group_name == "Views":
                query = oracle_queries.LIST_VIEWS
            elif group_name.startswith("Materializ"):
                query = oracle_queries.LIST_MATVIEWS
            elif group_name == "Procedures":
                query = oracle_queries.LIST_PROCEDURES
            elif group_name == "Functions":
                query = oracle_queries.LIST_FUNCTIONS
            elif group_name == "Packages":
                query = oracle_queries.LIST_PACKAGES
            elif group_name == "Sequences":
                query = oracle_queries.LIST_SEQUENCES
            elif group_name == "Triggers":
                query = oracle_queries.LIST_TRIGGERS
            elif group_name == "Synonyms":
                query = oracle_queries.LIST_SYNONYMS
            elif group_name.startswith("Database"):
                query = oracle_queries.LIST_DBLINKS
            elif group_name == "Java":
                query = oracle_queries.LIST_JAVA
            elif group_name.startswith("Columns"):
                query = oracle_queries.LIST_COLUMNS
            elif group_name.startswith("Constraints"):
                query = oracle_queries.LIST_CONSTRAINTS
            elif group_name.startswith("Indexes"):
                query = oracle_queries.LIST_INDEXES

            if query:
                params = {}
                if ":own" in query:
                    params["own"] = schema_name
                if ":obj" in query:
                    params["obj"] = (self.item_data.get('table_name') or self.obj_name).upper()

                cursor.execute(query, params)
                data["columns"] = [desc[0] for desc in cursor.description]
                raw_rows = cursor.fetchall()
                clean_rows = []
                for r in raw_rows:
                    clean_row = []
                    for val in r:
                        if hasattr(val, "read"):
                            clean_row.append(val.read())
                        else:
                            clean_row.append(val)
                    clean_rows.append(tuple(clean_row))
                data["rows"] = clean_rows
            return data

        # Single Object Properties
        if obj_type in ('table', 'view', 'materialized_view', 'matview'):
            try:
                if obj_type in ('materialized_view', 'matview') or "MATERIALIZED" in table_type:
                    cursor.execute(oracle_queries.GET_MATVIEW_DETAILS, {"own": schema_name, "obj": eff_obj})
                elif obj_type == 'view' or "VIEW" in table_type:
                    cursor.execute(oracle_queries.GET_VIEW_DETAILS, {"own": schema_name, "obj": eff_obj})
                else:
                    cursor.execute(oracle_queries.GET_TABLE_DETAILS, {"own": schema_name, "obj": eff_obj})

                row = cursor.fetchone()
                if row:
                    cols = [desc[0] for desc in cursor.description]
                    clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                    data["details"] = dict(zip(cols, clean_vals))
            except Exception as e:
                data["details"] = {"Name": self.obj_name, "Owner": schema_name, "Error": str(e)}

            # Fetch columns
            columns = []
            try:
                cursor.execute(oracle_queries.GET_TABLE_COLUMNS, {"own": schema_name, "obj": eff_obj})
                raw_cols = cursor.fetchall()

                pk_set = set()
                try:
                    cursor.execute(oracle_queries.GET_PRIMARY_KEYS, {"own": schema_name, "obj": eff_obj})
                    for pk_row in cursor.fetchall():
                        if pk_row and pk_row[0]:
                            pk_set.add(str(pk_row[0]).upper())
                except Exception:
                    pass

                for r in raw_cols:
                    col_name = str(r[0]) if len(r) > 0 and r[0] is not None else ""
                    dtype = str(r[1]) if len(r) > 1 and r[1] is not None else ""
                    dlen = r[2] if len(r) > 2 else None
                    dprec = r[3] if len(r) > 3 else None
                    dscale = r[4] if len(r) > 4 else None
                    nullable = (str(r[5]).upper() == 'Y') if len(r) > 5 else True
                    ddef = str(r[6]).strip() if len(r) > 6 and r[6] is not None else None
                    comment = r[7] if len(r) > 7 else None

                    if dtype == "NUMBER":
                        if dprec is not None and dscale is not None and dscale > 0:
                            dtype_str = f"NUMBER({dprec},{dscale})"
                        elif dprec is not None:
                            dtype_str = f"NUMBER({dprec})"
                        else:
                            dtype_str = "NUMBER"
                    elif dtype in ("VARCHAR2", "CHAR", "RAW") and dlen:
                        dtype_str = f"{dtype}({dlen})"
                    else:
                        dtype_str = dtype

                    columns.append({
                        "name": col_name,
                        "data_type": dtype_str,
                        "is_pk": (col_name.upper() in pk_set),
                        "nullable": nullable,
                        "default_value": ddef,
                        "comment": comment
                    })
            except Exception:
                pass
            data["columns"] = columns

            # Fetch constraints
            constraints = []
            try:
                cursor.execute(oracle_queries.GET_TABLE_CONSTRAINTS, {"own": schema_name, "obj": eff_obj})
                for r in cursor.fetchall():
                    constraints.append({
                        "name": r[0] if len(r) > 0 else "",
                        "type": r[1] if len(r) > 1 else "",
                        "definition": str(r[2]) if len(r) > 2 and r[2] is not None else ""
                    })
            except Exception:
                pass
            data["constraints"] = constraints

            # DDL Generation
            try:
                from db.oracle_utils import generate_oracle_table_ddl
                oracle_target_type = "TABLE"
                if obj_type in ('materialized_view', 'matview') or "MATERIALIZED" in table_type:
                    oracle_target_type = "MATERIALIZED VIEW"
                elif obj_type == "view" or "VIEW" in table_type:
                    oracle_target_type = "VIEW"
                data["sql"] = generate_oracle_table_ddl(conn_data, schema_name, self.obj_name, obj_type=oracle_target_type)
            except Exception as e:
                data["sql"] = f"-- Error generating Oracle DDL for {self.obj_name}: {e}"

        elif obj_type == 'schema':
            cursor.execute(oracle_queries.GET_SCHEMA_DETAILS, {"own": eff_obj})
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                data["details"] = dict(zip(cols, clean_vals))
            data["sql"] = f"-- Oracle Schema: {eff_obj}\n-- Default Tablespace: {data['details'].get('Default Tablespace', 'N/A')};"
            try:
                cursor.execute(oracle_queries.LIST_TABLES, {"own": eff_obj})
                data["tables"] = {
                    "columns": [desc[0] for desc in cursor.description],
                    "rows": cursor.fetchall()
                }
            except Exception:
                data["tables"] = {"columns": [], "rows": []}

        elif obj_type in ('procedure', 'function', 'package'):
            cursor.execute(oracle_queries.GET_PROCEDURE_OR_FUNCTION_DETAILS, {"own": schema_name, "obj": eff_obj})
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                data["details"] = dict(zip(cols, clean_vals))
            try:
                from db.oracle_utils import generate_oracle_object_source
                data["sql"] = generate_oracle_object_source(conn_data, schema_name, self.obj_name, obj_type=obj_type.upper())
            except Exception as e:
                data["sql"] = f"-- Error generating source for {self.obj_name}: {e}"

        elif obj_type == 'sequence':
            cursor.execute(oracle_queries.GET_SEQUENCE_DETAILS, {"own": schema_name, "obj": eff_obj})
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                data["details"] = dict(zip(cols, clean_vals))
            try:
                from db.oracle_utils import generate_oracle_object_source
                data["sql"] = generate_oracle_object_source(conn_data, schema_name, self.obj_name, obj_type='SEQUENCE')
            except Exception:
                data["sql"] = f"-- Sequence: {schema_name}.{eff_obj}\nCREATE SEQUENCE {schema_name}.{eff_obj};"

        elif obj_type == 'trigger':
            cursor.execute(oracle_queries.GET_TRIGGER_DETAILS, {"own": schema_name, "obj": eff_obj})
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                data["details"] = dict(zip(cols, clean_vals))
            try:
                from db.oracle_utils import generate_oracle_object_source
                data["sql"] = generate_oracle_object_source(conn_data, schema_name, self.obj_name, obj_type='TRIGGER')
            except Exception as e:
                data["sql"] = f"-- Trigger: {schema_name}.{eff_obj}\n-- Error: {e}"

        elif obj_type == 'synonym':
            cursor.execute(oracle_queries.GET_SYNONYM_DETAILS, {"own": schema_name, "obj": eff_obj})
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                clean_vals = [val.read() if hasattr(val, "read") else val for val in row]
                data["details"] = dict(zip(cols, clean_vals))
            try:
                from db.oracle_utils import generate_oracle_object_source
                data["sql"] = generate_oracle_object_source(conn_data, schema_name, self.obj_name, obj_type='SYNONYM')
            except Exception:
                target_owner = data["details"].get("Target owner", "")
                target_table = data["details"].get("Target name", "")
                data["sql"] = f"CREATE OR REPLACE SYNONYM {eff_obj} FOR {target_owner}.{target_table};"

        elif obj_type == 'connection':
            version_str = "Oracle Database"
            for ver_q in (
                "SELECT BANNER FROM v$version WHERE ROWNUM = 1",
                "SELECT BANNER_FULL FROM v$version WHERE ROWNUM = 1",
                "SELECT PRODUCT || ' ' || VERSION FROM product_component_version WHERE ROWNUM = 1",
            ):
                try:
                    cursor.execute(ver_q)
                    v_row = cursor.fetchone()
                    if v_row and v_row[0]:
                        version_str = str(v_row[0])
                        break
                except Exception:
                    continue

            conn_name = self.item_data.get('name') or self.item_data.get('short_name') or self.obj_name
            data["details"] = {
                "Version": version_str,
                "Connection Name": conn_name,
                "Host": str(conn_data.get('host') or ''),
                "Port": str(conn_data.get('port') or 1521),
                "Service Name / SID": str(conn_data.get('service_name') or conn_data.get('database') or ''),
                "User": str(conn_data.get('user') or '')
            }
            data["sql"] = ""

        return data

    def _fetch_oracle_statistics(self, cursor):
        return fetch_statistics_results(cursor, self.item_data, self.obj_name)
