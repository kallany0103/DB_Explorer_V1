"""widgets/tools/cli_launcher.py

Handles launching native database CLI tools (psql, sqlplus) in a separate
Windows terminal window. Extracted from main_window to keep the app shell thin.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from widgets.worksheet.query.query_preparation import get_query_editor, get_tab_connection_data

if TYPE_CHECKING:
    from main_window import MainWindow


def execute_via_native_cli(main_window: "MainWindow", cli_type: str) -> None:
    """Write the current SQL to a temp file and open a new terminal running
    the appropriate CLI tool (psql or sqlplus) against it.

    Args:
        main_window: The application's main window instance.
        cli_type: Either ``"psql"`` (PostgreSQL) or ``"sqlplus"`` (Oracle).
    """
    current_tab = main_window.tab_widget.currentWidget()
    if not current_tab:
        return

    conn_data = get_tab_connection_data(current_tab)
    if not conn_data:
        main_window.worksheet_manager.show_info("No connection selected.")
        return

    editor = get_query_editor(current_tab)
    if not editor:
        return

    # Prefer selected text; fall back to full editor content.
    sql = editor.textCursor().selectedText()
    if not sql:
        sql = editor.toPlainText()

    if not sql.strip():
        main_window.worksheet_manager.show_info("Please enter a valid query.")
        return

    # Resolve the CLI executable path from preferences.
    cli_path = _resolve_cli_path(main_window, cli_type)

    # Write SQL to a temp file; the terminal process reads it then deletes it.
    fd, temp_path = tempfile.mkstemp(suffix=".sql", prefix=f"usql_{cli_type}_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(sql)
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to write temp SQL file: {exc}")
        return

    if cli_type == "psql":
        _launch_psql(main_window, conn_data, cli_path, temp_path)
    elif cli_type == "sqlplus":
        _launch_sqlplus(main_window, conn_data, cli_path, temp_path)
    else:
        main_window.worksheet_manager.show_info(f"Unknown CLI type: {cli_type}")


def update_cli_action_states(main_window: "MainWindow", index: object = None) -> None:
    """Enable or disable the CLI toolbar actions based on the active tab's
    connection type.

    Args:
        main_window: The application's main window instance.
        index: Ignored; accepted so this can be connected to Qt index-changed signals.
    """
    if not hasattr(main_window, "execute_usql_action") or not hasattr(main_window, "execute_sqlplus_action"):
        return

    current_tab = main_window.tab_widget.currentWidget()
    if not current_tab:
        main_window.execute_usql_action.setEnabled(False)
        main_window.execute_sqlplus_action.setEnabled(False)
        return

    conn_data = get_tab_connection_data(current_tab)
    if not conn_data:
        main_window.execute_usql_action.setEnabled(False)
        main_window.execute_sqlplus_action.setEnabled(False)
        return

    conn_code = (conn_data.get("code") or conn_data.get("db_type") or "").upper()
    if conn_code == "POSTGRES":
        main_window.execute_usql_action.setEnabled(True)
        main_window.execute_sqlplus_action.setEnabled(False)
    elif conn_code in ("ORACLE", "ORACLE_DB"):
        main_window.execute_usql_action.setEnabled(False)
        main_window.execute_sqlplus_action.setEnabled(True)
    else:
        main_window.execute_usql_action.setEnabled(False)
        main_window.execute_sqlplus_action.setEnabled(False)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_cli_path(main_window: "MainWindow", cli_type: str) -> str:
    """Return the full path to the CLI executable, or just the bare name so
    that the OS PATH is used as a fallback."""
    if cli_type == "psql":
        pg_bin = getattr(main_window, "pg_bin_path", "")
        return str(Path(pg_bin) / "psql.exe") if pg_bin else "psql"
    if cli_type == "sqlplus":
        oracle_bin = getattr(main_window, "oracle_bin_path", "")
        return str(Path(oracle_bin) / "sqlplus.exe") if oracle_bin else "sqlplus"
    return cli_type


def _open_terminal(cmd_args: list[str], env: dict | None = None) -> None:
    """Spawn a detached cmd.exe window and run *cmd_args* inside it.

    Uses ``CREATE_NEW_CONSOLE`` so the window is independent of the
    application's own console (if any).
    """
    subprocess.Popen(
        cmd_args,
        shell=False,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        env=env,
    )


def _launch_psql(
    main_window: "MainWindow",
    conn_data: dict,
    cli_path: str,
    temp_path: str,
) -> None:
    """Build the psql argument list and open a terminal window."""
    password = conn_data.get("password", "") or ""

    # Build the psql argument list — list2cmdline handles all quoting for cmd.
    psql_args: list[str] = [cli_path, "-f", temp_path]
    if conn_data.get("host"):
        psql_args.extend(["-h", conn_data["host"]])
    if conn_data.get("port"):
        psql_args.extend(["-p", str(conn_data["port"])])
    if conn_data.get("user"):
        psql_args.extend(["-U", conn_data["user"]])
    db = conn_data.get("database") or conn_data.get("db")
    if db:
        psql_args.extend(["-d", db])

    # Build connection args shared by both the file-run call and the interactive call.
    conn_args: list[str] = []
    if conn_data.get("host"):
        conn_args.extend(["-h", conn_data["host"]])
    if conn_data.get("port"):
        conn_args.extend(["-p", str(conn_data["port"])])
    if conn_data.get("user"):
        conn_args.extend(["-U", conn_data["user"]])
    db = conn_data.get("database") or conn_data.get("db")
    if db:
        conn_args.extend(["-d", db])

    # 1st call: run the SQL file and print results.
    run_args: list[str] = [cli_path, "-f", temp_path] + conn_args
    # 2nd call: drop into an interactive psql session with the same connection.
    interactive_args: list[str] = [cli_path] + conn_args

    run_cmd = subprocess.list2cmdline(run_args)
    interactive_cmd = subprocess.list2cmdline(interactive_args)
    cleanup = subprocess.list2cmdline(["del", "/q", temp_path])

    # Inject PGPASSWORD via the child environment — no shell quoting needed.
    child_env = os.environ.copy()
    child_env["PGPASSWORD"] = password

    # Sequence: run file → interactive session → delete temp file.
    # cmd /k keeps the window open after everything finishes so the user can
    # review the output even after closing the interactive session.
    cmd_args = ["cmd", "/k", f"{run_cmd} & {interactive_cmd} & {cleanup}"]
    try:
        _open_terminal(cmd_args, env=child_env)
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to launch psql terminal: {exc}")


def _launch_sqlplus(
    main_window: "MainWindow",
    conn_data: dict,
    cli_path: str,
    temp_path: str,
) -> None:
    """Build the sqlplus connection string and open a terminal window."""
    user = conn_data.get("user", "")
    password = conn_data.get("password", "")
    host = conn_data.get("host", "localhost")
    port = conn_data.get("port", "1521")
    sid = conn_data.get("database") or conn_data.get("db") or ""
    conn_str = f"{user}/{password}@{host}:{port}/{sid}"

    run_args: list[str] = [cli_path, conn_str, f"@{temp_path}"]
    interactive_args: list[str] = [cli_path, conn_str]

    run_cmd = subprocess.list2cmdline(run_args)
    interactive_cmd = subprocess.list2cmdline(interactive_args)
    cleanup = subprocess.list2cmdline(["del", "/q", temp_path])

    # Sequence: run file → interactive session → delete temp file.
    cmd_args = ["cmd", "/k", f"{run_cmd} & {interactive_cmd} & {cleanup}"]
    try:
        _open_terminal(cmd_args)
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to launch sqlplus terminal: {exc}")
