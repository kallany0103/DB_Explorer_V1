import os
import sys
sys.path.insert(0, os.path.abspath("."))
import sqlite3
from widgets.encryption.secure_sqlite import enable_transparent_encryption
enable_transparent_encryption("mysecretpassword")

import db

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
        import traceback
        traceback.print_exc()

dump_db("databases/hierarchy.db")
appdata_path = os.path.join(os.environ.get("APPDATA", ""), "Universal SQL Client", "databases", "hierarchy.db")
dump_db(appdata_path)

print("\n=== Hierarchy Data via db.get_hierarchy_data() ===")
for t in db.get_hierarchy_data():
    print(f"Type: {t['code']} ({t['name']}), Groups: {len(t['usf_connection_groups'])}")
    for g in t['usf_connection_groups']:
        print(f"  Group: {g['name']}, Connections: {len(g['usf_connections'])}")
        for conn in g['usf_connections']:
            print(f"    Connection: {conn['short_name']} (id={conn['id']}), Data Sources: {len(conn['usf_data_sources'])}")
            for ds in conn['usf_data_sources']:
                print(f"      Data Source: {ds['short_name']} (server={ds.get('server_name')})")
