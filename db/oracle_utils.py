"""Oracle database connection utilities for DSN building, parsing, and TNS discovery."""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)



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


def scan_oracle_client_dirs() -> list[dict[str, Any]]:
    """Scan the system for installed Oracle Instant Client directories.

    Scans all available drives, environment variables, PATH, and user directories.
    Verifies that all required files (oci.dll, oraociei/oraociicus DLL, and orannzsbb DLL)
    are present.

    Returns a list of dicts with client metadata (path, version, label, supports_10g).
    """
    candidates: list[Path] = []
    seen: set[str] = set()

    # 1. Environment variables
    for env_var in ("ORACLE_CLIENT_LIB_DIR", "ORACLE_HOME", "TNS_ADMIN"):
        val = os.environ.get(env_var)
        if val and Path(val).is_dir():
            p = Path(val)
            candidates.append(p)
            if (p / "bin").is_dir():
                candidates.append(p / "bin")

    # 2. System PATH entries
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry_s = entry.strip().strip('"')
        if entry_s:
            p = Path(entry_s)
            if p.is_dir() and any(k in entry_s.lower() for k in ("oracle", "instant", "client")):
                candidates.append(p)

    # 3. User profile directories (Downloads, Documents, Desktop, tools, oracle)
    try:
        user_home = Path.home()
        if user_home.is_dir():
            for sub_name in ("Downloads", "Documents", "Desktop", "tools", "oracle"):
                user_sub = user_home / sub_name
                if user_sub.is_dir():
                    candidates.append(user_sub)
                    try:
                        for child in user_sub.iterdir():
                            if child.is_dir() and any(k in child.name.lower() for k in ("oracle", "instant", "client")):
                                candidates.append(child)
                    except Exception:
                        pass
    except Exception:
        pass

    # 4. Search all available drives on Windows or system roots on Unix
    if sys.platform == "win32":
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    else:
        drives = ["/opt", "/usr/lib", "/usr/local/lib"]

    skip_names = {
        "windows", "$recycle.bin", "system volume information", "node_modules",
        ".git", ".gemini", ".vscode", "winsxs", "microsoft", "recovery", "msocache"
    }

    for drive_str in drives:
        drive_path = Path(drive_str)
        try:
            for item in drive_path.iterdir():
                if not item.is_dir():
                    continue
                name_lower = item.name.lower()
                if name_lower in skip_names or name_lower.startswith("$"):
                    continue
                candidates.append(item)

                # If directory name suggests oracle, client, tools, db, app, scan down up to depth 3
                if any(k in name_lower for k in ("oracle", "instant", "client", "db", "tool", "app", "software", "programs")):
                    try:
                        for sub in item.iterdir():
                            if sub.is_dir() and sub.name.lower() not in skip_names:
                                candidates.append(sub)
                                if any(k in sub.name.lower() for k in ("oracle", "instant", "client", "bin", "x64")):
                                    try:
                                        for sub2 in sub.iterdir():
                                            if sub2.is_dir() and sub2.name.lower() not in skip_names:
                                                candidates.append(sub2)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
        except Exception:
            pass

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
    clean_port = int(port) if str(port).strip().isdigit() else 1521
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
        "port": 1521,
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
        result["port"] = int(port_str) if port_str else 1521
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

    runner_script = (
        "import sys, json\n"
        "data = json.loads(sys.argv[1])\n"
        "driver_mode = str(data.get('driver_mode', '')).lower()\n"
        "client_dir = data.get('oracle_client_dir')\n\n"
        "if driver_mode == 'thick' or client_dir:\n"
        "    from db.oracle_utils import init_oracle_thick_mode, get_last_thick_mode_error\n"
        "    if not init_oracle_thick_mode(client_dir):\n"
        "        err = get_last_thick_mode_error() or 'Unknown error initializing Oracle Instant Client'\n"
        "        target = client_dir or 'system default'\n"
        "        print(f'Oracle Thick Mode (Instant Client) failed to initialize with client directory \"{target}\":\\n\\n{err}')\n"
        "        sys.exit(2)\n\n"
        "import oracledb\n"
        "from db.oracle_utils import build_oracle_dsn, get_oracle_auth_mode, diagnose_oracle_error\n\n"
        "dsn = data.get('dsn')\n"
        "if not dsn:\n"
        "    host = data.get('host', 'localhost')\n"
        "    port = data.get('port') or 1521\n"
        "    db_name = data.get('database') or data.get('service_name', '')\n"
        "    db_type = data.get('oracle_db_type') or data.get('database_type', 'service_name')\n"
        "    dsn = build_oracle_dsn(host, port, db_name, db_type=db_type)\n\n"
        "kwargs = {'user': data.get('user', ''), 'password': data.get('password', ''), 'dsn': dsn}\n"
        "mode = get_oracle_auth_mode(data.get('role'))\n"
        "if mode != oracledb.AUTH_MODE_DEFAULT:\n"
        "    kwargs['mode'] = mode\n"
        "if data.get('config_dir') or data.get('tns_admin'):\n"
        "    kwargs['config_dir'] = data.get('config_dir') or data.get('tns_admin')\n\n"
        "try:\n"
        "    conn = oracledb.connect(**kwargs)\n"
        "    is_thin = oracledb.is_thin_mode()\n"
        "    conn.close()\n"
        "    mode_str = 'Thin Mode' if is_thin else 'Thick Mode (Instant Client)'\n"
        "    print(f'Connected successfully to Oracle database using {mode_str}!')\n"
        "    sys.exit(0)\n"
        "except Exception as e:\n"
        "    advice = diagnose_oracle_error(e)\n"
        "    msg = f'Oracle connection error: {e}'\n"
        "    if advice:\n"
        "        msg += f'\\n\\nDiagnostic advice:\\n{advice}'\n"
        "    print(msg)\n"
        "    sys.exit(1)\n"
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner_script, json.dumps(conn_data)],
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
