# widgets/backup_and_restore/restore/engine.py
from ..core import BackupRestoreBase

class RestoreEngine(BackupRestoreBase):
    """Engine for generating restore commands."""

    def build_pg_restore_args(self, conn_data, input_file, format="custom", options=None):
        """Builds arguments for pg_restore."""
        use_wsl = getattr(self.main_window, "use_wsl", False)
        final_input = self.to_wsl_path(input_file) if use_wsl else input_file

        options = options or {}
        args = [
            "-h", conn_data.get("host", "localhost"),
            "-p", str(conn_data.get("port", 5432)),
            "-U", conn_data.get("user", "postgres"),
            "-w", 
            "-d", conn_data.get("database", "postgres"),
        ]
        
        selected_objects = options.get("selected_objects", [])
        if selected_objects:
            for obj in selected_objects:
                if obj["type"] == "schema":
                    args.extend(["-n", obj["name"]])
                elif obj["type"] == "table":
                    args.extend(["-t", obj["name"]])
        else:
            if granularity == "schema" and object_name:
                args.extend(["-n", object_name])
            elif granularity == "table" and object_name:
                args.extend(["-t", object_name])
            
        format_map = {"custom": "c", "directory": "d", "tar": "t"}
        if format in format_map:
            args.extend(["-F", format_map[format]])
            
        if options.get("role"):
            args.extend(["--role", options["role"]])
        if options.get("content") == "Only Data":
            args.append("-a")
        elif options.get("content") == "Only Schema":
            args.append("-s")
            
        if options.get("no_owner"): args.append("--no-owner")
        if options.get("no_privileges"): args.append("--no-privileges")
        if options.get("no_tablespaces"): args.append("--no-tablespaces")
        if options.get("no_comments"): args.append("--no-comments")
        if options.get("clean"): args.append("--clean")
        if options.get("single_transaction"): args.append("--single-transaction")
        if options.get("exit_on_error"): args.append("--exit-on-error")
        if options.get("verbose"): args.append("--verbose")

        args.append(final_input)
        
        if use_wsl:
            return ["pg_restore"] + args
        return args
