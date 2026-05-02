# widgets/backup_and_restore/core.py
import os
import shutil
import sys
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
        
        # Check Local 'bin' folder
        app_root = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__)) if '__main__' in sys.modules else os.getcwd()
        local_bin = os.path.join(app_root, "bin")

        search_paths = []
        if settings_path: search_paths.append(settings_path)
        if os.path.exists(local_bin): search_paths.append(local_bin)

        for path in search_paths:
            if path and os.path.exists(path):
                full_path = os.path.join(path, binary_name)
                for ext in ["", ".exe"]:
                    if os.path.exists(full_path + ext):
                        return full_path + ext

        path_binary = shutil.which(binary_name)
        if path_binary:
            return path_binary

        if os.name == "nt":
            base_dir = r"C:\Program Files\PostgreSQL"
            if os.path.exists(base_dir):
                try:
                    versions = sorted(os.listdir(base_dir), reverse=True)
                    for v in versions:
                        bin_path = os.path.join(base_dir, v, "bin")
                        full_path = os.path.join(bin_path, binary_name + ".exe")
                        if os.path.exists(full_path):
                            return full_path
                except Exception:
                    pass

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
