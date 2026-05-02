# widgets/backup_and_restore/backup/engine.py
import os
from ..core import BackupRestoreBase

class BackupEngine(BackupRestoreBase):
    """Engine for generating backup commands."""
    
    def build_pg_dump_args(self, conn_data, output_file, format="custom", granularity="database", object_name=None, schema_name=None, options=None):
        """Builds arguments for pg_dump."""
        use_wsl = getattr(self.main_window, "use_wsl", False)
        final_output = self.to_wsl_path(output_file) if use_wsl else output_file

        options = options or {}
        args = [
            "-h", conn_data["host"],
            "-p", str(conn_data["port"]),
            "-U", conn_data["user"],
            "-w", 
            "-f", final_output
        ]
        
        format_map = {"plain": "p", "custom": "c", "directory": "d", "tar": "t"}
        args.extend(["-F", format_map.get(format, "c")])
        
        selected_objects = options.get("selected_objects", [])
        if selected_objects:
            for obj in selected_objects:
                if obj["type"] == "schema":
                    args.extend(["-n", obj["name"]])
                elif obj["type"] == "table":
                    args.extend(["-t", f'"{obj["schema"]}"."{obj["name"]}"'])
        else:
            if granularity == "schema" and object_name:
                args.extend(["-n", object_name])
            elif granularity == "table" and object_name:
                if schema_name:
                    args.extend(["-t", f'"{schema_name}"."{object_name}"'])
                else:
                    args.extend(["-t", object_name])
        
        if options.get("role"):
            args.extend(["--role", options["role"]])
        if options.get("encoding"):
            args.extend(["-E", options["encoding"]])
        if options.get("content") == "Only Data":
            args.append("-a")
        elif options.get("content") == "Only Schema":
            args.append("-s")
            
        if options.get("no_owner"): args.append("--no-owner")
        if options.get("no_privileges"): args.append("--no-privileges")
        if options.get("no_tablespaces"): args.append("--no-tablespaces")
        if options.get("no_comments"): args.append("--no-comments")
        if options.get("clean"): args.append("--clean")
        if options.get("inserts"): args.append("--inserts")
        if options.get("column_inserts"): args.append("--column-inserts")
        if options.get("verbose"): args.append("--verbose")
        if options.get("compress") is not None and str(options.get("compress")) != "0":
            args.extend(["--compress", str(options["compress"])])
            
        args.append(conn_data["database"])

        if use_wsl:
            return ["pg_dump"] + args
        return args

    def perform_sqlite_backup(self, db_path, target_path):
        """Performs a backup of a SQLite database file."""
        import shutil
        try:
            if not os.path.exists(db_path):
                return False, f"Source database not found: {db_path}"
            shutil.copy2(db_path, target_path)
            return True, f"Database backed up successfully to {target_path}"
        except Exception as e:
            return False, f"Backup failed: {str(e)}"
