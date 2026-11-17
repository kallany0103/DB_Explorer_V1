# widgets/backup_and_restore/core.py
import re
from PySide6.QtCore import QProcessEnvironment

class BackupRestoreBase:
    """Base class for shared backup and restore utilities."""
    def __init__(self, main_window):
        self.main_window = main_window

    def get_pg_binary(self, binary_name):
        """Finds the full path to a pg binary."""
        if getattr(self.main_window, "use_wsl", False):
            return "wsl"

        settings_path = getattr(self.main_window, "pg_bin_path", "")
        from widgets.psql_tool.discovery import find_pg_binary
        found = find_pg_binary(binary_name, settings_path)
        if found:
            return found

        return binary_name

    def to_wsl_path(self, win_path):
        """Converts a Windows path to a WSL path."""
        if not win_path or ":" not in win_path:
            return win_path
        path = win_path.replace("\\", "/")
        path = re.sub(r'^([a-zA-Z]):', lambda m: f"/mnt/{m.group(1).lower()}", path)
        return path

    def get_pg_environment(self, conn_data):
        """Creates a QProcessEnvironment with PGPASSWORD set."""
        env = QProcessEnvironment.systemEnvironment()
        if "password" in conn_data:
            password = conn_data["password"]
            env.insert("PGPASSWORD", password)
            
            if getattr(self.main_window, "use_wsl", False):
                wsl_env = env.value("WSLENV", "")
                if "PGPASSWORD" not in wsl_env:
                    new_wsl_env = f"{wsl_env}:PGPASSWORD/u" if wsl_env else "PGPASSWORD/u"
                    env.insert("WSLENV", new_wsl_env)
        return env
