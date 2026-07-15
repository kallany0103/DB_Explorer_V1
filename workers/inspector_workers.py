# workers/inspector_workers.py

from PySide6.QtCore import QObject, Signal, QRunnable
import db

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

    def run(self):
        conn = None
        try:
            conn_data = self.item_data.get('conn_data') or self.item_data
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
                
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            if conn: conn.close()

    def _fetch_properties(self, cursor):
        from dialogs.properties import pg_queries
        obj_type = self.item_data.get('type')
        group_name = self.item_data.get('group_name')
        schema_name = self.item_data.get('schema_name', 'public')
        
        # Auto-detect group from type if group_name is missing (for root nodes)
        if not group_name and obj_type and obj_type.endswith('_root'):
            if obj_type == 'schemas_root': group_name = "Schemas"
            elif obj_type == 'fdw_root': group_name = "Foreign Data Wrappers"
            elif obj_type == 'extension_root': group_name = "Extensions"
            elif obj_type == 'language_root': group_name = "Languages"

        data = {"type": "object", "details": {}, "sql": ""}
        
        # Only treat as group if type is explicitly a group type or if obj_type is not a specific object type
        # Prioritize explicit object types (table, view, schema, function, etc.) over group_name
        is_specific_object = obj_type in ['table', 'view', 'schema', 'function', 'sequence', 'connection', 'extension', 'language', 'fdw', 'foreign_server', 'user_mapping', 'trigger']
        
        if group_name and not is_specific_object:
            data["type"] = "group"
            data["group_name"] = group_name
            query = None
            if group_name == "Schemas": query = pg_queries.LIST_SCHEMAS
            elif group_name == "Tables": query = pg_queries.LIST_TABLES
            elif group_name == "Views": query = pg_queries.LIST_VIEWS
            elif group_name == "Functions": query = pg_queries.LIST_FUNCTIONS
            elif group_name == "Sequences": query = pg_queries.LIST_SEQUENCES
            elif group_name.startswith("Columns"): query = pg_queries.LIST_COLUMNS
            elif group_name.startswith("Constraints"): query = pg_queries.LIST_CONSTRAINTS
            elif group_name.startswith("Indexes"): query = pg_queries.LIST_INDEXES
            elif group_name == "Triggers": query = pg_queries.LIST_TRIGGERS
            
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
        if obj_type == 'table':
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
            
            # Generate SQL for table
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
            data["sql"] = f"CREATE SCHEMA {self.obj_name}\n    AUTHORIZATION {owner};"
            
        elif obj_type == 'function':
            cursor.execute(pg_queries.GET_FUNCTION_DETAILS, (schema_name, self.obj_name))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                data["sql"] = data["details"].get("definition") or data["details"].get("Definition", "")
                
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
            data["sql"] = "-- Connection details fetched directly from database connection parameters."

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
        from workers.inspector_stats import fetch_statistics_results
        return fetch_statistics_results(cursor, self.item_data, self.obj_name)
