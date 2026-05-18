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
            conn = db.create_postgres_connection(**pg_conn_data)
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
        
        if group_name:
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
            
            cursor.execute(f"SELECT pg_get_tabledef(%s, %s)", (schema_name, self.obj_name))
            res = cursor.fetchone()
            if res: data["sql"] = res[0]
            
        elif obj_type == 'schema':
            cursor.execute(pg_queries.GET_SCHEMA_DETAILS, (self.obj_name,))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
            data["sql"] = f"CREATE SCHEMA {self.obj_name}\n    AUTHORIZATION {data['details'].get('owner', 'postgres')};"
            
        elif obj_type == 'function':
            cursor.execute(pg_queries.GET_FUNCTION_DETAILS, (schema_name, self.obj_name))
            row = cursor.fetchone()
            if row:
                data["details"] = dict(zip([d[0] for d in cursor.description], row))
                data["sql"] = data["details"].get('definition', '')
                
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

        return data

    def _fetch_statistics(self, cursor):
        from dialogs.properties import pg_queries
        obj_type = self.item_data.get('type')
        table_type = self.item_data.get('table_type', '').upper()
        schema_name = self.item_data.get('schema_name', 'public')
        group_name = self.item_data.get('group_name')

        if not group_name and obj_type == 'schemas_root':
             group_name = "Schemas"

        stats_data = []
        
        if obj_type == 'connection':
            db_name = self.item_data.get('database')
            if db_name:
                cursor.execute(pg_queries.GET_DATABASE_STATS, (db_name,))
                stats_data.append({"query": pg_queries.GET_DATABASE_STATS, "params": (db_name,)})
        elif obj_type == 'table' or 'TABLE' in table_type or 'VIEW' in table_type:
            stats_data.append({"query": pg_queries.GET_TABLE_SIZE_STATS, "params": (schema_name, self.obj_name)})
            stats_data.append({"query": pg_queries.GET_TABLE_STATS, "params": (schema_name, self.obj_name)})
        elif obj_type == 'schema' or group_name == 'Schemas':
            stats_data.append({"query": pg_queries.GET_SCHEMA_STATS, "params": (self.obj_name, self.obj_name, self.obj_name)})
        elif 'FUNCTION' in table_type:
            func_name = self.obj_name.split('(')[0]
            stats_data.append({"query": pg_queries.GET_FUNCTION_STATS, "params": (schema_name, func_name)})
        elif 'SEQUENCE' in table_type:
            stats_data.append({"query": pg_queries.GET_SEQUENCE_STATS, "params": (schema_name, self.obj_name)})
            
        # Actually fetch the data to avoid cursor issues in main thread
        final_results = []
        for item in stats_data:
            cursor.execute(item["query"], item["params"])
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            final_results.append({"columns": cols, "rows": rows})
            
        return {"stats": final_results}
