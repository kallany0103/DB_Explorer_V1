import sqlite3 as sqlite
from .db_connections import DB_FILE 
 
def get_all_connections_from_db():
    """Returns a list of dicts with full hierarchical connection info from usf_connections table."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                i.id, c.name, c.code, sc.name, i.name, i.short_name, i.host, i.port, 
                i."database", i.db_path, i.user, i.password,instance_url
            FROM usf_connections i
            LEFT JOIN usf_connection_groups sc ON i.connection_group_id = sc.id
            LEFT JOIN usf_connection_types c ON sc.connection_type_id = c.id
            ORDER BY i.usage_count DESC, c.name, sc.name, i.name
        """)
        rows = c.fetchall()

    connections = []
    for row in rows:
        (connection_id, connection_type_name, code, connection_group_name, connection_name, short_name, host,
         port, dbname, db_path, user, password,instance_url) = row
        full_name = f"{connection_type_name} -> {connection_group_name} -> {connection_name} ({short_name})"
        connections.append({
            "id": connection_id,
            "display_name": full_name,
            "code":code,
            "name": connection_name,
            "short_name": short_name,
            "host": host,
            "port": port,
            "database": dbname,
            "db_path": db_path,
            "user": user,
            "password": password,
            "instance_url": instance_url

        })
    return connections

# def get_hierarchy_data():
#     """Returns all usf_connection_types, usf_connection_groups, and usf_connections for the main tree view."""
#     with sqlite.connect(DB_FILE) as conn:
#         c = conn.cursor()
#         c.execute("SELECT id, name FROM usf_connection_types")
#         usf_connection_types = c.fetchall()

#         data = []
#         for connection_type_id, connection_type_name in usf_connection_types:
#             connection_type_data = {'id': connection_type_id, 'name': connection_type_name, 'usf_connection_groups': []}
#             c.execute(
#                 "SELECT id, name FROM usf_connection_groups WHERE connection_type_id=?", (connection_type_id,))
#             connection_groups = c.fetchall()

#             for connection_group_id, connection_group_name in connection_groups:
#                 connection_group_data = {'id': connection_group_id,
#                                'name': connection_group_name, 'usf_connections': []}
#                 c.execute(
#                     "SELECT id, name, short_name, host, \"database\", \"user\", password, port, db_path FROM usf_connections WHERE connection_group_id=?", (connection_group_id,))
#                 usf_connections = c.fetchall()
#                 for connections in usf_connections:
#                     connection_id, name, short_name, host, db, user, pwd, port, db_path = connections
#                     conn_data = {"id": connection_id, "name": name, "short_name": short_name, "host": host, "database": db,
#                                  "user": user, "password": pwd, "port": port, "db_path": db_path}
#                     connection_group_data['usf_connections'].append(conn_data)
#                 connection_type_data['usf_connection_groups'].append(connection_group_data)
#             data.append(connection_type_data)
#     return data


def get_hierarchy_data():
    """Returns all usf_connection_types, usf_connection_groups, and usf_connections for the main tree view."""
    with sqlite.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT id, code, name FROM usf_connection_types")
        usf_connection_types = c.fetchall()

        data = []
        for connection_type_id, code, connection_type_name in usf_connection_types:
            connection_type_data = {'id': connection_type_id,'code': code, 'name': connection_type_name, 'usf_connection_groups': []}
            c.execute(
                "SELECT id, name FROM usf_connection_groups WHERE connection_type_id=?", (connection_type_id,))
            connection_groups = c.fetchall()

            for connection_group_id, connection_group_name in connection_groups:
                connection_group_data = {'id': connection_group_id,
                               'name': connection_group_name, 'usf_connections': []}
                c.execute(
                    "SELECT id, name, short_name, host, \"database\", \"user\", password, port, dsn, db_path, instance_url FROM usf_connections WHERE connection_group_id=?", (connection_group_id,))
                usf_connections = c.fetchall()
                for connections in usf_connections:
                    connection_id, name, short_name, host, db, user, pwd, port, dsn, db_path, instance_url = connections
                    conn_data = {"id": connection_id, "name": name, "short_name": short_name, "host": host, "database": db,
                                 "user": user, "password": pwd, "port": port, "dsn": dsn,"db_path": db_path, "instance_url": instance_url}
                    connection_group_data['usf_connections'].append(conn_data)
                connection_type_data['usf_connection_groups'].append(connection_group_data)
            data.append(connection_type_data)
    return data

