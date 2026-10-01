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
from widgets.psql_tool.discovery import find_psql
from widgets.sqlplus_tool.discovery import find_sqlplus, instantclient_dir

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
            # SQL*Plus requires a terminator to execute the buffer and return to prompt
            if cli_type == "sqlplus" and not sql.strip().endswith((";", "/")):
                f.write("\n/\n")
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
        if pg_bin:
            return str(Path(pg_bin) / "psql.exe")
        return find_psql() or "psql"
    if cli_type == "sqlplus":
        oracle_bin = getattr(main_window, "oracle_bin_path", "")
        if oracle_bin:
            return str(Path(oracle_bin) / "sqlplus.exe")
        return find_sqlplus() or "sqlplus"
    return cli_type


def _open_terminal(
    cmd_args: list[str] | str, env: dict | None = None
) -> subprocess.Popen | None:
    """Spawn a detached cmd.exe window and run *cmd_args* inside it.

    Uses ``CREATE_NEW_CONSOLE`` so the window is independent of the
    application's own console (if any). Returns the process handle so the
    caller can register it for cleanup when the app exits.
    """
    try:
        return subprocess.Popen(
            cmd_args,
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            env=env,
        )
    except OSError:
        return None


def register_cli_terminal(
    main_window: "MainWindow", proc: subprocess.Popen | None, temp_files: list[str]
) -> None:
    """Track an external CLI terminal so it can be closed with the app."""
    if proc is None:
        return
    tracked = getattr(main_window, "_cli_terminals", None)
    if tracked is None:
        tracked = []
        main_window._cli_terminals = tracked
    tracked.append((proc, list(temp_files)))


def close_cli_terminals(main_window: "MainWindow") -> None:
    """Terminate all tracked external CLI terminals and clean up temp files.

    Best effort: failures are ignored so application shutdown never blocks.
    """
    tracked = getattr(main_window, "_cli_terminals", None) or []
    main_window._cli_terminals = []
    for proc, temp_files in tracked:
        try:
            if proc.poll() is None:
                try:
                    # Tree-kill takes down cmd.exe together with its
                    # sqlplus/psql children; hidden so no window flashes.
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=10,
                    )
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass
        for path in temp_files:
            try:
                os.remove(path)
            except OSError:
                pass


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
    # cmd /c closes the window once the interactive session exits and the
    # temp file is deleted.
    # We pass a string to prevent subprocess from escaping quotes for cmd.exe
    cmd_args = f'cmd /c "{run_cmd} & {interactive_cmd} & {cleanup}"'
    try:
        register_cli_terminal(
            main_window, _open_terminal(cmd_args, env=child_env), [temp_path]
        )
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to launch psql terminal: {exc}")


# Display width for the external SQL*Plus window: wide enough for typical
# result sets, narrow enough to fit a normal console without scrolling.
_SQLPLUS_LINESIZE = 200
# Text columns wider than this get a COLUMN FORMAT cap so a single
# VARCHAR2(80+) cannot stretch every row past the window width.
_SQLPLUS_CHAR_WIDTH_CAP = 40


def _launch_sqlplus(
    main_window: "MainWindow",
    conn_data: dict,
    cli_path: str,
    temp_path: str,
) -> None:
    """Build the sqlplus connection string and open a terminal window.

    Uses ``/NOLOG`` + a wrapper login script so credentials are never passed on
    the command line.  The login script CONNECTs, runs the user's query, then
    SQL*Plus stays alive at the interactive ``SQL>`` prompt.
    """
    user = conn_data.get("user") or conn_data.get("username") or ""
    password = conn_data.get("password") or ""
    
    # If the user specified a custom DSN string in connection settings, use it directly.
    # Otherwise, build the Easy Connect string.
    dsn = conn_data.get("dsn")
    if dsn:
        easy_connect = f"{user}/{password}@{dsn}"
    else:
        host = conn_data.get("host") or "localhost"
        port = conn_data.get("port") or "1521"
        sid = conn_data.get("service_name") or conn_data.get("database") or conn_data.get("db") or ""
        easy_connect = f"{user}/{password}@//{host}:{port}/{sid}"

    # Login script: CONNECT → set formatting → run query → stay at SQL>.
    # Wide text columns are narrowed inside the session itself (SPOOL a
    # generated COLUMN FORMAT script, then run it): no extra DB round-trip
    # from Python, so launching stays instant. Formats persist for the rest
    # of the interactive session; overlong values wrap, never truncate.
    fmt_fd, fmt_path = tempfile.mkstemp(suffix=".sql", prefix="usql_sqlplus_fmt_")
    os.close(fmt_fd)
    login_fd, login_path = tempfile.mkstemp(suffix=".sql", prefix="usql_sqlplus_login_")
    try:
        with os.fdopen(login_fd, "w", encoding="utf-8") as lf:
            lf.write(f"CONNECT {easy_connect}\n")
            lf.write(f"SET LINESIZE {_SQLPLUS_LINESIZE}\n")
            lf.write("SET PAGESIZE 100\n")
            lf.write("SET TAB OFF\n")
            lf.write("SET TRIMSPOOL ON\n")
            lf.write("SET TRIMOUT ON\n")
            lf.write("SET HEADING OFF\n")
            lf.write("SET FEEDBACK OFF\n")
            lf.write("SET DEFINE OFF\n")
            # TERMOUT OFF hides the generated COLUMN lines from the screen;
            # SPOOL still captures them into the format script.
            lf.write("SET TERMOUT OFF\n")
            lf.write(f"SPOOL {fmt_path}\n")
            lf.write(
                "SELECT 'COLUMN \"' || column_name || '\" FORMAT "
                f"A{_SQLPLUS_CHAR_WIDTH_CAP}' FROM user_tab_columns "
                "WHERE data_type LIKE '%CHAR%' "
                f"AND char_length > {_SQLPLUS_CHAR_WIDTH_CAP};\n"
            )
            lf.write("SPOOL OFF\n")
            lf.write("SET TERMOUT ON\n")
            lf.write("SET HEADING ON\n")
            lf.write("SET FEEDBACK ON\n")
            lf.write(f"@{fmt_path}\n")
            lf.write(f"@{temp_path}\n")
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to write SQL*Plus login script: {exc}")
        return

    child_env = os.environ.copy()
    ic_dir = instantclient_dir()

    bundled_admin = (
        Path(__file__).parent.parent.parent
        / "resources" / "oracle" / "instantclient" / "network" / "admin"
    )
    if bundled_admin.is_dir():
        child_env["TNS_ADMIN"] = str(bundled_admin)

    if ic_dir:
        env_path = child_env.get("PATH", "")
        if ic_dir not in env_path:
            child_env["PATH"] = ic_dir + os.pathsep + env_path
        child_env["TNS_ADMIN"] = os.path.join(ic_dir, "network", "admin")

    # Write a .bat launcher to avoid nested-quote hell in cmd /c "...".
    # The bat: runs sqlplus (/NOLOG + login script) → user gets SQL> prompt
    # → after EXIT, temp files are deleted.
    bat_fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="usql_sqlplus_run_")
    try:
        with os.fdopen(bat_fd, "w", encoding="ascii") as bf:
            bf.write("@echo off\n")
            # Force the Windows console buffer to be extremely wide so it generates
            # a horizontal scrollbar instead of aggressively wrapping text to the next line.
            bf.write("mode con cols=1000\n")
            bf.write(f'"{cli_path}" /NOLOG @"{login_path}"\n')
            bf.write(f'del /q "{temp_path}" "{login_path}" "{fmt_path}"\n')
            bf.write('del /q "%~f0"\n')
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to write SQL*Plus launcher: {exc}")
        return

    try:
        # Pass as a single string to let Popen handle cmd.exe's weird quoting
        # /c closes the window once EXIT in SQL*Plus ends the session.
        register_cli_terminal(
            main_window,
            _open_terminal(f'cmd.exe /c "{bat_path}"', env=child_env),
            [temp_path, login_path, fmt_path, bat_path],
        )
    except OSError as exc:
        main_window.worksheet_manager.show_info(f"Failed to launch sqlplus terminal: {exc}")

