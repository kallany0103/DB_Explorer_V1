"""Oracle database connection utilities for DSN building, parsing, and TNS discovery."""

from __future__ import annotations

import logging
import os
import re
import string
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)



DEFAULT_ORACLE_PORT: int = 1521

_SKIP_DIR_NAMES: set[str] = {
    "windows", "$recycle.bin", "system volume information", "node_modules",
    ".git", ".gemini", ".vscode", "winsxs", "microsoft", "recovery", "msocache"
}
_ORACLE_DIR_KEYWORDS: tuple[str, ...] = (
    "oracle", "instant", "client", "db", "tool", "app", "software", "programs"
)

_oracle_thick_mode_attempted = False
_active_oracle_client_dir: str | None = None
_last_thick_mode_error: str | None = None


def get_active_oracle_client_dir() -> str | None:
    """Return the currently loaded Oracle Client directory, if thick mode is active."""
    return _active_oracle_client_dir


def get_last_thick_mode_error() -> str | None:
    """Return the last error message recorded during init_oracle_thick_mode, if any."""
    return _last_thick_mode_error


def detect_oracle_client_version(dir_path: Path | str) -> str:
    """Infer the Oracle client version from files in the directory."""
    p = Path(dir_path)
    if not p.is_dir():
        return "Unknown"

    try:
        files = {f.name.lower() for f in p.iterdir() if f.is_file()}
    except Exception:
        return "Unknown"

    if any("23" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "23ai"
    if any("21" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "21c"
    if any("19" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "19c"
    if any("18" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "18c"
    if any("12" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "12c"
    if any("11" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "11.2"
    if any("10" in f for f in files if f.startswith("orasql") or f.startswith("orannz")):
        return "10g"

    return "Custom"


def is_valid_oracle_client_dir(dir_path: Path | str) -> tuple[bool, list[str]]:
    """Verify that all required Oracle Instant Client files exist in the directory.

    Returns (is_valid, missing_files_list).
    """
    p = Path(dir_path)
    if not p.is_dir():
        return False, ["Directory does not exist"]

    try:
        files = {f.name.lower() for f in p.iterdir() if f.is_file()}
    except Exception as e:
        return False, [f"Cannot read directory: {e}"]

    missing: list[str] = []
    if sys.platform == "win32":
        if "oci.dll" not in files:
            missing.append("oci.dll (Oracle Call Interface)")
        has_engine = any(
            f.startswith("oraociei") or f.startswith("oraociicus") or f.startswith("orasql")
            for f in files
        )
        if not has_engine:
            missing.append("oraociei*.dll / oraociicus*.dll (OCI Data / Client Engine)")
        has_security = any(f.startswith("orannz") for f in files)
        if not has_security:
            missing.append("orannzsbb*.dll (Network Security Library)")
    else:
        has_oci = any(f.startswith("libclntsh") for f in files)
        if not has_oci:
            missing.append("libclntsh (Client Library)")
        has_engine = any(f.startswith("libociei") or f.startswith("libociicus") for f in files)
        if not has_engine:
            missing.append("libociei / libociicus (Client Engine)")
        has_nnz = any(f.startswith("libnnz") for f in files)
        if not has_nnz:
            missing.append("libnnz (Security Library)")

    return len(missing) == 0, missing


def normalize_client_path(path: str | Path | None) -> str:
    """Normalize an Oracle client directory path to a canonical, resolved string."""
    if not path:
        return ""
    try:
        p = Path(path).resolve()
        return os.path.normpath(str(p))
    except Exception:
        return os.path.normpath(str(path))


def _find_env_candidates() -> list[Path]:
    """Find candidate directories specified in environment variables."""
    candidates: list[Path] = []
    for env_var in ("ORACLE_CLIENT_LIB_DIR", "ORACLE_HOME", "TNS_ADMIN"):
        val = os.environ.get(env_var)
        if val and Path(val).is_dir():
            p = Path(val)
            candidates.append(p)
            if (p / "bin").is_dir():
                candidates.append(p / "bin")
    return candidates


def _find_path_candidates() -> list[Path]:
    """Find candidate directories on the system PATH."""
    candidates: list[Path] = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry_s = entry.strip().strip('"')
        if entry_s:
            p = Path(entry_s)
            if p.is_dir() and any(k in entry_s.lower() for k in ("oracle", "instant", "client")):
                candidates.append(p)
    return candidates


def _find_user_dir_candidates() -> list[Path]:
    """Find candidate directories in standard user profile folders."""
    candidates: list[Path] = []
    try:
        user_home = Path.home()
        if not user_home.is_dir():
            return candidates
        for sub_name in ("Downloads", "Documents", "Desktop", "tools", "oracle"):
            user_sub = user_home / sub_name
            if not user_sub.is_dir():
                continue
            candidates.append(user_sub)
            try:
                for child in user_sub.iterdir():
                    if child.is_dir() and any(k in child.name.lower() for k in ("oracle", "instant", "client")):
                        candidates.append(child)
            except Exception:
                pass
    except Exception:
        pass
    return candidates


def _scan_dir_tree(root: Path, max_depth: int = 2) -> list[Path]:
    """Recursively search for Oracle client candidate directories up to max_depth."""
    candidates: list[Path] = []
    queue: list[tuple[Path, int]] = [(root, 0)]

    while queue:
        current, depth = queue.pop(0)
        try:
            for child in current.iterdir():
                if not child.is_dir():
                    continue
                name_lower = child.name.lower()
                if name_lower in _SKIP_DIR_NAMES or name_lower.startswith("$"):
                    continue
                if any(k in name_lower for k in ("oracle", "instant", "client")):
                    candidates.append(child)
                if depth < max_depth and any(k in name_lower for k in _ORACLE_DIR_KEYWORDS):
                    queue.append((child, depth + 1))
        except Exception:
            continue

    return candidates


def _find_drive_candidates() -> list[Path]:
    """Scan root directories of available drives for Oracle client candidates."""
    if sys.platform == "win32":
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    else:
        drives = ["/opt", "/usr/lib", "/usr/local/lib"]

    candidates: list[Path] = []
    for drive_str in drives:
        try:
            drive_path = Path(drive_str)
            for item in drive_path.iterdir():
                if not item.is_dir():
                    continue
                name_lower = item.name.lower()
                if name_lower in _SKIP_DIR_NAMES or name_lower.startswith("$"):
                    continue
                if any(k in name_lower for k in _ORACLE_DIR_KEYWORDS):
                    candidates.extend(_scan_dir_tree(item, max_depth=2))
        except Exception:
            continue
    return candidates


def scan_oracle_client_dirs() -> list[dict[str, Any]]:
    """Scan the system for installed Oracle Instant Client directories.

    Scans all available drives, environment variables, PATH, and user directories.
    Verifies that all required files (oci.dll, oraociei/oraociicus DLL, and orannzsbb DLL)
    are present.

    Returns a list of dicts with client metadata (path, version, label, supports_10g).
    """
    candidates = (
        _find_env_candidates()
        + _find_path_candidates()
        + _find_user_dir_candidates()
        + _find_drive_candidates()
    )
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for cand in candidates:
        try:
            resolved = normalize_client_path(cand)
        except Exception:
            continue
        if not resolved:
            continue
        norm_key = os.path.normcase(resolved)
        if norm_key in seen:
            continue
        seen.add(norm_key)

        is_valid, _ = is_valid_oracle_client_dir(cand)
        if not is_valid:
            continue

        ver = detect_oracle_client_version(cand)
        label = f"Oracle Instant Client {ver} - {resolved}"

        results.append({
            "path": resolved,
            "version": ver,
            "label": label,
            "supports_10g": ver in ("11.2", "10g"),
        })

    results.sort(key=lambda r: (r["version"] == "Unknown", r["path"]))
    return results


def find_oracle_client_dir(custom_dir: str | None = None) -> str | None:
    """Locate an installed Oracle Instant Client directory."""
    if custom_dir and Path(custom_dir).is_dir():
        is_valid, _ = is_valid_oracle_client_dir(custom_dir)
        if is_valid:
            return str(Path(custom_dir).resolve())

    env_client = os.environ.get("ORACLE_CLIENT_LIB_DIR")
    if env_client and Path(env_client).is_dir():
        is_valid, _ = is_valid_oracle_client_dir(env_client)
        if is_valid:
            return str(Path(env_client).resolve())

    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home and Path(oracle_home).is_dir():
        bin_dir = Path(oracle_home) / "bin"
        if bin_dir.is_dir() and (bin_dir / "oci.dll").is_file():
            return str(bin_dir)
        if (Path(oracle_home) / "oci.dll").is_file():
            return str(Path(oracle_home).resolve())

    scanned = scan_oracle_client_dirs()
    if scanned:
        return scanned[0]["path"]

    return None


def init_oracle_thick_mode(lib_dir: str | None = None) -> bool:
    """Attempt to initialize Oracle thick mode using bundled, custom, or system client.

    Returns True if Thick mode is active, False otherwise.
    """
    import oracledb as _oracledb  # noqa: PLC0415  lazy — must not move to top-level

    global _oracle_thick_mode_attempted, _active_oracle_client_dir, _last_thick_mode_error
    if not _oracledb.is_thin_mode():
        return True

    target_dir = find_oracle_client_dir(lib_dir)
    try:
        if target_dir:
            _oracledb.init_oracle_client(lib_dir=target_dir)
            _active_oracle_client_dir = target_dir
        else:
            _oracledb.init_oracle_client()
            _active_oracle_client_dir = "system"
        _oracle_thick_mode_attempted = True
        _last_thick_mode_error = None
        return True
    except Exception as exc:
        _oracle_thick_mode_attempted = True
        _last_thick_mode_error = str(exc)
        logger.warning(f"Failed to initialize Oracle thick mode with client dir '{target_dir}': {exc}")
        return False


def diagnose_oracle_error(error: str | Exception) -> str:
    """Analyze an Oracle connection error and return actionable diagnostic advice."""
    msg = str(error)
    diagnostics: list[str] = []

    if "DPY-3010" in msg:
        diagnostics.append(
            "DPY-3010: python-oracledb Thin mode does not support connecting to Oracle Database 11.2 or older. "
            "To connect to Oracle 11g, Thick mode must be enabled with Oracle Instant Client 19c or 11.2."
        )
    elif "DPY-3015" in msg:
        diagnostics.append(
            "DPY-3015: The database uses a legacy 10G password verifier which is not supported in Thin mode. "
            "Thick mode with Oracle Instant Client is required, or update the database user password verifier."
        )

    if "ORA-03134" in msg:
        diagnostics.append(
            "ORA-03134: Connections to this server version are no longer supported by Oracle 19c Client. "
            "You are trying to connect to Oracle 10g or older. Oracle 19c client only supports 11.2.0.4 and newer. "
            "To connect to Oracle 10g/9i, configure Oracle Instant Client 11.2."
        )

    if "ORA-28040" in msg:
        diagnostics.append(
            "ORA-28040: No matching authentication protocol. "
            "The database server rejects the client authentication version. Add "
            "'SQLNET.ALLOWED_LOGON_VERSION_CLIENT=8' or '11' in sqlnet.ora on the server/client."
        )

    if "DPI-1072" in msg or "DPI-1047" in msg:
        diagnostics.append(
            "DPI error: The 64-bit Oracle Client library cannot be loaded. "
            "Ensure the Microsoft Visual C++ 2015-2022 Redistributable (vcruntime140.dll) is installed, "
            "and that the client architecture matches 64-bit Python."
        )

    if "ORA-12514" in msg:
        diagnostics.append(
            "ORA-12514: TNS listener does not know of the requested SERVICE_NAME. "
            "If this is an older Oracle version (such as 10g, 11g XE), try switching Database Type to 'SID'."
        )

    if "ORA-12505" in msg:
        diagnostics.append(
            "ORA-12505: TNS listener does not know of the requested SID. "
            "If this is a pluggable database (12c+), try switching Database Type to 'Service Name'."
        )

    if "ORA-01017" in msg:
        diagnostics.append(
            "ORA-01017: Invalid username or password, or user is not authorized to log on. "
            "Verify your username, password, and the selected Role (e.g. Normal vs SYSDBA)."
        )

    if "DPY-2019" in msg:
        diagnostics.append(
            "DPY-2019: python-oracledb Thick mode cannot be enabled because a Thin mode connection has already been created in this application session. "
            "Please restart the application to use Thick mode."
        )

    return "\n\n".join(diagnostics)


def find_default_tns_admin_dir() -> str | None:
    """Locate the default directory containing tnsnames.ora, if one exists."""
    # 1. Environment variable TNS_ADMIN
    tns_admin_env = os.environ.get("TNS_ADMIN")
    if tns_admin_env and Path(tns_admin_env).is_dir():
        return tns_admin_env

    # 2. Environment variable ORACLE_HOME/network/admin
    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home:
        candidate = Path(oracle_home) / "network" / "admin"
        if candidate.is_dir():
            return str(candidate)

    # 3. Bundled instant client network/admin
    client_dir = find_oracle_client_dir()
    if client_dir:
        admin_candidate = Path(client_dir) / "network" / "admin"
        if admin_candidate.is_dir():
            return str(admin_candidate)

    return None


def get_tns_names(admin_dir: str | None = None) -> list[str]:
    """Parse alias names from tnsnames.ora in the specified or default admin directory."""
    target_dir = admin_dir or find_default_tns_admin_dir()
    if not target_dir:
        return []

    tns_file = Path(target_dir) / "tnsnames.ora"
    if not tns_file.is_file():
        return []

    aliases: list[str] = []
    try:
        with open(tns_file, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                # Match alias definition lines before '='
                if "=" in line:
                    prefix = line.split("=")[0].strip()
                    # Skip sub-tokens like (DESCRIPTION or (ADDRESS
                    if "(" in prefix or ")" in prefix:
                        continue
                    for part in prefix.split(","):
                        clean_alias = part.strip()
                        if clean_alias and re.match(r"^[A-Za-z0-9_.-]+$", clean_alias):
                            if clean_alias not in aliases:
                                aliases.append(clean_alias)
    except Exception as exc:
        logger.warning(f"Failed to read tnsnames.ora from {tns_file}: {exc}")

    aliases.sort()
    return aliases


def build_oracle_dsn(
    host: str,
    port: int | str | None,
    database: str,
    db_type: str = "service_name"
) -> str:
    """Build an Oracle Easy Connect string without touching oracledb's API.

    Using oracledb.makedsn() would silently enable Thin Mode before a connection
    is ever attempted, making Thick Mode impossible for that session.
    The Easy Connect format accepted by oracledb is identical to what makedsn produced.
    """
    clean_host = (host or "").strip()
    clean_port = int(port) if str(port).strip().isdigit() else DEFAULT_ORACLE_PORT
    clean_db = (database or "").strip()

    if not clean_host or not clean_db:
        return ""

    if db_type == "sid":
        # (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=h)(PORT=p))(CONNECT_DATA=(SID=s)))
        return (
            f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={clean_host})(PORT={clean_port}))"
            f"(CONNECT_DATA=(SID={clean_db})))"
        )
    # host:port/service_name  — Easy Connect format
    return f"{clean_host}:{clean_port}/{clean_db}"


def parse_oracle_dsn(dsn_str: str) -> dict[str, Any]:
    """Parse a DSN string into its constituent components (host, port, db, mode)."""
    raw = (dsn_str or "").strip()
    result: dict[str, Any] = {
        "mode": "basic",
        "host": "",
        "port": DEFAULT_ORACLE_PORT,
        "database": "",
        "db_type": "service_name",
        "dsn": raw,
    }

    if not raw:
        return result

    # Check if raw is a pure TNS alias (e.g. no slashes, colons, or parentheses)
    if not any(ch in raw for ch in "()/\\:") and re.match(r"^[A-Za-z0-9_.-]+$", raw):
        result["mode"] = "tns"
        result["database"] = raw
        return result

    # NOTE: oracledb.ConnectParams() was removed here.
    # Instantiating ConnectParams enables Thin Mode in the current process,
    # making Thick Mode (Instant Client) impossible for the rest of the session.
    # The regex fallbacks below cover all Easy Connect formats we support.

    # Fallback regex for Easy Connect host:port:sid or host:port/service
    m_sid = re.match(r"^(?://)?([^:/]+):(\d+):([^:/]+)$", raw)
    if m_sid:
        host, port_str, sid = m_sid.groups()
        result["host"] = host
        result["port"] = int(port_str)
        result["database"] = sid.strip()
        result["db_type"] = "sid"
        result["mode"] = "basic"
        return result

    m_svc = re.match(r"^(?://)?([^:/]+)(?::(\d+))?/(.+)$", raw)
    if m_svc:
        host, port_str, svc = m_svc.groups()
        result["host"] = host
        result["port"] = int(port_str) if port_str else DEFAULT_ORACLE_PORT
        result["database"] = svc.strip()
        result["db_type"] = "service_name"
        result["mode"] = "basic"
        return result

    result["mode"] = "custom"
    return result


def get_oracle_auth_mode(role_name: str | None) -> int:
    """Return the oracledb authentication mode integer for the given role string.

    We import oracledb lazily inside this function so that merely importing
    oracle_utils does not touch oracledb's C layer and lock Thin Mode.
    """
    import oracledb as _oracledb  # noqa: PLC0415  lazy — must not move to top-level

    if not role_name:
        return _oracledb.AUTH_MODE_DEFAULT

    r = str(role_name).strip().upper()
    if r == "SYSDBA":
        return _oracledb.AUTH_MODE_SYSDBA
    if r == "SYSOPER":
        return _oracledb.AUTH_MODE_SYSOPER
    if r == "SYSASM":
        return _oracledb.AUTH_MODE_SYSASM

    return _oracledb.AUTH_MODE_DEFAULT


def test_oracle_connection_isolated(conn_data: dict[str, Any]) -> tuple[bool, str]:
    """Test Oracle database connectivity inside an isolated subprocess.

    Running the test in a separate subprocess guarantees that testing Thin mode
    or testing Thick mode never mutates or locks the main application process's
    python-oracledb C-driver state (preventing DPY-2019 errors).
    """
    import json
    import subprocess
    import sys

    tester_script = Path(__file__).resolve().parent.parent / "utils" / "oracle_connection_tester.py"

    try:
        proc = subprocess.run(
            [sys.executable, str(tester_script), json.dumps(conn_data)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        output = stdout or stderr
        if proc.returncode == 0:
            return True, output or "Connected successfully to Oracle database!"
        return False, output or "Failed to connect to Oracle database."
    except subprocess.TimeoutExpired:
        return False, "Connection test timed out after 30 seconds."
    except Exception as exc:
        return False, f"Failed to run connection test process:\n{exc}"


def enable_dbms_output(cursor: Any, buffer_size: int | None = None) -> None:
    """Enable Oracle DBMS_OUTPUT message buffer on the given cursor.

    buffer_size: None sets unlimited buffer (Oracle 10g+).
    """
    try:
        if buffer_size is not None:
            cursor.callproc("dbms_output.enable", (buffer_size,))
        else:
            cursor.callproc("dbms_output.enable")
    except Exception as e:
        logger.debug(f"Failed to enable DBMS_OUTPUT: {e}")


def fetch_dbms_output(cursor: Any, chunk_size: int = 100) -> str | None:
    """Fetch all pending DBMS_OUTPUT lines from the Oracle session buffer.

    Returns the concatenated string of lines or None if buffer was empty.
    """
    lines: list[str] = []
    try:
        import oracledb

        lines_var = cursor.arrayvar(oracledb.STRING, chunk_size)
        num_lines_var = cursor.var(int)
        while True:
            num_lines_var.setvalue(0, chunk_size)
            cursor.callproc("dbms_output.get_lines", (lines_var, num_lines_var))
            num_lines = num_lines_var.getvalue()
            if not num_lines:
                break
            chunk = lines_var.getvalue()[:num_lines]
            lines.extend(chunk)
            if num_lines < chunk_size:
                break
    except Exception as e:
        logger.debug(f"Failed to fetch DBMS_OUTPUT: {e}")

    return "\n".join(lines) if lines else None


def is_oracle_plsql(query: str) -> bool:
    """Return True if the query string is a PL/SQL block or procedure call."""
    if not query:
        return False
    # Strip single line comments -- ...
    q = re.sub(r"--[^\n]*", "", query)
    # Strip block comments /* ... */
    q = re.sub(r"/\*.*?\*/", "", q, flags=re.DOTALL).strip()
    if not q:
        return False
    first_token = q.split()[0].upper()
    return first_token in ("BEGIN", "DECLARE", "CALL")

