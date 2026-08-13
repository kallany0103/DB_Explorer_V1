import sqlite3
import os

def dump_db(path):
    print(f"=== Database: {path} ===")
    if not os.path.exists(path):
        print("Does not exist!")
        return
    try:
        conn = sqlite3.connect(path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in c.fetchall()]
        print("Tables:", tables)
        
        if 'usf_connection_types' in tables:
            c.execute("SELECT id, code, name FROM usf_connection_types")
            print("Types:", c.fetchall())
        
        if 'usf_connection_groups' in tables:
            c.execute("SELECT id, name, connection_type_id FROM usf_connection_groups")
            print("Groups:", c.fetchall())
            
        if 'usf_connections' in tables:
            c.execute("SELECT id, name, short_name, connection_group_id FROM usf_connections")
            print("Connections:", c.fetchall())
            
        if 'usf_data_sources' in tables:
            c.execute("SELECT id, connection_id, source_name, display_name, server_name FROM usf_data_sources")
            print("Data Sources:", c.fetchall())
            
        conn.close()
    except Exception as e:
        print("Error reading DB:", e)

dump_db("databases/hierarchy.db")
appdata_path = os.path.join(os.environ.get("APPDATA", ""), "Universal SQL Client", "databases", "hierarchy.db")
dump_db(appdata_path)
