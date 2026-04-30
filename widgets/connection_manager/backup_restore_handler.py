# widgets/connection_manager/backup_restore_handler.py
import os
from PySide6.QtCore import QProcessEnvironment

class BackupRestoreHandler:
    """
    Handles the logic for constructing backup and restore commands
    for various database types.
    """
    def __init__(self, main_window):
        self.main_window = main_window

    def get_pg_binary(self, binary_name):
        """
        Returns the full path to a pg binary using a multi-stage search:
        1. User settings (highest priority)
        2. System PATH
        3. Common PostgreSQL installation folders on Windows
        
        Note: If use_wsl is active, we return 'wsl' as the binary to execute.
        """
        if getattr(self.main_window, "use_wsl", False):
            return "wsl"

        # 1. Check User Settings
        settings_path = getattr(self.main_window, "pg_bin_path", "")
        
        # 2. Check Local 'bin' folder (Standalone Experience)
        # Search in the app's root directory
        local_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "bin")
        # Wait, that's too many parents. Let's use a more robust way.
        import sys
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

        # 2. Check System PATH
        import shutil
        path_binary = shutil.which(binary_name)
        if path_binary:
            return path_binary

        # 3. Search Common Windows Paths
        if os.name == "nt":
            # Search C:\Program Files\PostgreSQL\*\bin
            base_dir = r"C:\Program Files\PostgreSQL"
            if os.path.exists(base_dir):
                # Get all subdirectories (versions), sort descending to get latest
                try:
                    versions = sorted(os.listdir(base_dir), reverse=True)
                    for v in versions:
                        bin_path = os.path.join(base_dir, v, "bin")
                        full_path = os.path.join(bin_path, binary_name + ".exe")
                        if os.path.exists(full_path):
                            return full_path
                except Exception:
                    pass

        return binary_name # Fallback to naked command name

    def to_wsl_path(self, win_path):
        """Converts a Windows path to a WSL path (e.g. C:\\temp -> /mnt/c/temp)"""
        if not win_path or ":" not in win_path:
            return win_path
        
        # Replace backslashes
        path = win_path.replace("\\", "/")
        # Convert drive letter C: -> /mnt/c
        import re
        path = re.sub(r'^([a-zA-Z]):', lambda m: f"/mnt/{m.group(1).lower()}", path)
        return path

    def build_pg_dump_args(self, conn_data, output_file, format="custom", granularity="database", object_name=None, schema_name=None, options=None):
        """
        Builds arguments for pg_dump.
        granularity: 'database', 'schema', 'table'
        """
        use_wsl = getattr(self.main_window, "use_wsl", False)
        
        # If WSL is used, the output path must be converted
        final_output = self.to_wsl_path(output_file) if use_wsl else output_file

        options = options or {}
        args = [
            "-h", conn_data["host"],
            "-p", str(conn_data["port"]),
            "-U", conn_data["user"],
            "-w", # Never prompt for password, fail immediately if needed
            "-f", final_output
        ]
        
        # Format
        format_map = {"plain": "p", "custom": "c", "directory": "d", "tar": "t"}
        args.extend(["-F", format_map.get(format, "c")])
        
        # Granularity / Object Selection
        selected_objects = options.get("selected_objects", [])
        if selected_objects:
            # If specific objects are selected, use them instead of the default granularity
            for obj in selected_objects:
                if obj["type"] == "schema":
                    args.extend(["-n", obj["name"]])
                elif obj["type"] == "table":
                    args.extend(["-t", f'"{obj["schema"]}"."{obj["name"]}"'])
        else:
            # Fallback to existing granularity logic
            if granularity == "schema" and object_name:
                args.extend(["-n", object_name])
            elif granularity == "table" and object_name:
                if schema_name:
                    args.extend(["-t", f'"{schema_name}"."{object_name}"'])
                else:
                    args.extend(["-t", object_name])
        
        # Additional Options
        if options.get("role"):
            args.extend(["--role", options["role"]])
        if options.get("encoding"):
            args.extend(["-E", options["encoding"]])
        if options.get("content") == "Only Data":
            args.append("-a")
        elif options.get("content") == "Only Schema":
            args.append("-s")
            
        if options.get("no_owner"):
            args.append("--no-owner")
        if options.get("no_privileges"):
            args.append("--no-privileges")
        if options.get("clean"):
            args.append("--clean")
        if options.get("inserts"):
            args.append("--inserts")
            
        args.append(conn_data["database"])

        # If WSL, prefix the whole thing
        if use_wsl:
            return ["pg_dump"] + args
        return args

    def build_pg_restore_args(self, conn_data, input_file, format="custom", options=None):
        """Builds arguments for pg_restore."""
        use_wsl = getattr(self.main_window, "use_wsl", False)
        final_input = self.to_wsl_path(input_file) if use_wsl else input_file

        options = options or {}
        args = [
            "-h", conn_data["host"],
            "-p", str(conn_data["port"]),
            "-U", conn_data["user"],
            "-w", # Never prompt for password
            "-d", conn_data["database"],
        ]
        
        # Format
        format_map = {"custom": "c", "directory": "d", "tar": "t"}
        if format in format_map:
            args.extend(["-F", format_map[format]])
            
        # Additional Options
        if options.get("role"):
            args.extend(["--role", options["role"]])
        if options.get("content") == "Only Data":
            args.append("-a")
        elif options.get("content") == "Only Schema":
            args.append("-s")
            
        if options.get("no_owner"):
            args.append("--no-owner")
        if options.get("no_privileges"):
            args.append("--no-privileges")
        if options.get("clean"):
            args.append("--clean")
        if options.get("exit_on_error"):
            args.append("--exit-on-error")

        args.append(final_input)
        
        if use_wsl:
            return ["pg_restore"] + args
        return args

    def get_pg_environment(self, conn_data):
        """Creates a QProcessEnvironment with PGPASSWORD set."""
        env = QProcessEnvironment.systemEnvironment()
        if "password" in conn_data:
            password = conn_data["password"]
            env.insert("PGPASSWORD", password)
            
            # If using WSL, we must tell WSL to inherit this variable
            if getattr(self.main_window, "use_wsl", False):
                # /u flag means 'use when invoking WSL from Win'
                # We append to existing WSLENV if present
                wsl_env = env.value("WSLENV", "")
                if "PGPASSWORD" not in wsl_env:
                    new_wsl_env = f"{wsl_env}:PGPASSWORD/u" if wsl_env else "PGPASSWORD/u"
                    env.insert("WSLENV", new_wsl_env)
        return env

    def perform_sqlite_backup(self, db_path, target_path):
        """
        Performs a backup of a SQLite database file.
        Returns (success, message).
        """
        import shutil
        try:
            if not os.path.exists(db_path):
                return False, f"Source database not found: {db_path}"
            
            shutil.copy2(db_path, target_path)
            return True, f"Database backed up successfully to {target_path}"
        except Exception as e:
            return False, f"Backup failed: {str(e)}"
