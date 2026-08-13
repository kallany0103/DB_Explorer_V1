import sys, os
sys.path.insert(0, os.path.abspath("."))
import sqlite3
from widgets.encryption.secure_sqlite import enable_transparent_encryption
enable_transparent_encryption("mysecretpassword")

conn = sqlite3.connect("databases/hierarchy.db")
c = conn.cursor()
c.execute("SELECT * FROM usf_connection_groups WHERE connection_type_id IS NULL")
print("Orphaned groups:", c.fetchall())

c.execute("SELECT * FROM usf_connections WHERE connection_group_id IS NULL")
print("Orphaned connections:", c.fetchall())

c.execute("SELECT * FROM usf_connections")
print("\nAll connections:")
for row in c.fetchall():
    print(row)

conn.close()
