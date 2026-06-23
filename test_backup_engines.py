import sys
import os

sys.path.append(r"e:\C\Documents\CODES\Projects\PyQt6\DB_Explorer_V1")

from widgets.backup_and_restore.backup.engine import BackupEngine
from widgets.backup_and_restore.restore.engine import RestoreEngine

class DummyMainWindow:
    use_wsl = False
    pg_bin_path = ""

main_window = DummyMainWindow()
backup_engine = BackupEngine(main_window)
restore_engine = RestoreEngine(main_window)

conn_data = {
    "host": "localhost",
    "port": 5432,
    "user": "test_user",
    "database": "test_db",
    "password": "pass"
}

print("Testing BackupEngine pg_dump args...")
options = {
    "format": "custom",
    "content": "Only Data",
    "no_owner": True,
    "selected_objects": [{"type": "table", "schema": "public", "name": "users"}],
    "compress": 5
}
try:
    args = backup_engine.build_pg_dump_args(conn_data, "out.backup", options=options)
    print("Backup args:", args)
except Exception as e:
    print("Backup Engine Error:", e)

print("Testing RestoreEngine pg_restore args...")
try:
    args = restore_engine.build_pg_restore_args(conn_data, "in.backup", options=options)
    print("Restore args:", args)
except Exception as e:
    print("Restore Engine Error:", e)
