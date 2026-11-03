"""Oracle database connection utilities for DSN building, parsing, and TNS discovery."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeoutError
import ctypes
import ctypes.wintypes
import logging
import os
import re
import struct
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


def get_oci_dll_version(dir_path: Path | str) -> str | None:
    """Read the exact file version from oci.dll in the given directory.

    Returns a dotted version string like ``'19.32.0.0'`` on Windows,
    or ``None`` if the DLL is absent or the version cannot be read.
    """
    if sys.platform != "win32":
        return None
    p = Path(dir_path)
    oci = p / "oci.dll"
    if not oci.is_file():
        return None
    try:
        path_str = str(oci)
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path_str, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path_str, None, size, buf):
            return None
        u_len = ctypes.c_uint()
        lp_data = ctypes.c_void_p()
        if not ctypes.windll.version.VerQueryValueW(
            buf, r"\\", ctypes.byref(lp_data), ctypes.byref(u_len)
        ):
            return None
        raw = ctypes.string_at(lp_data, u_len.value)
        ms, ls = struct.unpack("<II", raw[8:16])
        ver_str = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
        return None if ver_str == "0.0.0.0" else ver_str
    except Exception:
        return None


def get_pe_architecture(file_path: Path | str) -> str | None:
    """Return '64-bit' or '32-bit' for a Windows PE binary (DLL/EXE), or None if unreadable."""
    try:
        with open(file_path, "rb") as f:
            if f.read(2) != b"MZ":
                return None
            f.seek(0x3C)
            pe_offset_bytes = f.read(4)
            if len(pe_offset_bytes) < 4:
                return None
            pe_offset = struct.unpack("<I", pe_offset_bytes)[0]
            f.seek(pe_offset)
            if f.read(4) != b"PE\x00\x00":
                return None
            machine_bytes = f.read(2)
            if len(machine_bytes) < 2:
                return None
            machine = struct.unpack("<H", machine_bytes)[0]
            if machine in (0x8664, 0xAA64):  # AMD64 or ARM64
                return "64-bit"
            if machine == 0x14C:  # i386
                return "32-bit"
    except Exception:
        return None
    return None


def get_client_sqlnet_path(client_dir: Path | str) -> Path:
    """Return the expected ``sqlnet.ora`` path for the given Oracle Client directory.

    The canonical location is ``<client_dir>/network/admin/sqlnet.ora``.
    """
    return Path(client_dir) / "network" / "admin" / "sqlnet.ora"


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
    """Verify that all required Oracle Instant Client or local Oracle client files exist in the directory.

    Returns (is_valid, missing_files_list).
    """
    p = Path(dir_path)
    if not p.is_dir():
        return False, ["Directory does not exist"]

    # If user selected an ORACLE_HOME root, resolve to its bin/ subfolder where oci.dll lives
    if (p / "bin" / "oci.dll").is_file() and not (p / "oci.dll").is_file():
        p = p / "bin"

    try:
        files = {f.name.lower() for f in p.iterdir() if f.is_file()}
    except Exception as e:
        return False, [f"Cannot read directory: {e}"]

    missing: list[str] = []
    if sys.platform == "win32":
        if "oci.dll" not in files:
            missing.append("oci.dll (Oracle Call Interface)")
        else:
            dll_arch = get_pe_architecture(p / "oci.dll")
            app_arch = "64-bit" if sys.maxsize > 2**32 else "32-bit"
            if dll_arch and dll_arch != app_arch:
                missing.append(
                    f"oci.dll is {dll_arch} (Universal SQL Client requires {app_arch})"
                )
        # Supports Oracle Instant Client (oraociei/oraociicus) and Full DB/Client (orasql/oraclient/oracommon)
        has_engine = any(
            f.startswith("oraociei")
            or f.startswith("oraociicus")
            or f.startswith("orasql")
            or f.startswith("oraclient")
            or f.startswith("oracommon")
            for f in files
        )
        if not has_engine:
            missing.append("oraociei*.dll / oraociicus*.dll / oraclient*.dll (OCI Client Engine)")
        # Supports Instant Client (orannzsbb*.dll) and Full Client/Home (orannz*.dll)
        has_security = any(f.startswith("orannz") for f in files)
        if not has_security:
            missing.append("orannz*.dll (Network Security Library)")
    else:
        has_oci = any(f.startswith("libclntsh") for f in files)
        if not has_oci:
            missing.append("libclntsh (Client Library)")
        has_engine = any(
            f.startswith("libociei")
            or f.startswith("libociicus")
            or f.startswith("libsql")
            or f.startswith("libclntshcore")
            for f in files
        )
        if not has_engine:
            missing.append("libociei / libociicus / libclntshcore (Client Engine)")
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
        if (p / "bin" / "oci.dll").is_file() and not (p / "oci.dll").is_file():
            p = p / "bin"
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
        for sub_name in ("Downloads", "Documents", "Desktop", "tools", "oracle", "app"):
            user_sub = user_home / sub_name
            if not user_sub.is_dir():
                continue
            candidates.append(user_sub)
            try:
                for child in user_sub.iterdir():
                    if child.is_dir():
                        candidates.append(child)
                        if any(k in child.name.lower() for k in _ORACLE_DIR_KEYWORDS):
                            candidates.extend(_scan_dir_tree(child, max_depth=2))
            except Exception:
                pass
    except Exception:
        pass
    return candidates


def _scan_dir_tree(root: Path, max_depth: int = 2) -> list[Path]:
    """Recursively search for Oracle client candidate directories up to max_depth."""
    candidates: list[Path] = [root]
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
                    candidates.append(item)
                    candidates.extend(_scan_dir_tree(item, max_depth=2))
        except Exception:
            continue
    return candidates


def get_registered_oracle_homes() -> list[dict[str, Any]]:
    """Read Oracle Homes registered in the Windows Registry by OUI (Oracle Universal Installer).

    OUI writes each installed Oracle Home under:
        HKLM\\SOFTWARE\\ORACLE\\KEY_<HomeName>   (64-bit clients)
        HKLM\\SOFTWARE\\Wow6432Node\\ORACLE\\KEY_<HomeName>  (32-bit clients)

    Returns a list of dicts with keys: path, home_name, label.
    Returns an empty list on non-Windows platforms or if the registry is unreadable.
    """
    if sys.platform != "win32":
        return []

    import winreg

    HIVE_PATHS: tuple[tuple[int, str], ...] = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ORACLE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\ORACLE"),
    )
    homes: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for hive, base_path in HIVE_PATHS:
        try:
            with winreg.OpenKey(hive, base_path) as base_key:
                idx = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(base_key, idx)
                        idx += 1
                    except OSError:
                        break
                    if not subkey_name.upper().startswith("KEY_"):
                        continue
                    try:
                        with winreg.OpenKey(base_key, subkey_name) as sk:
                            try:
                                oracle_home, _ = winreg.QueryValueEx(sk, "ORACLE_HOME")
                            except OSError:
                                continue
                            try:
                                home_name, _ = winreg.QueryValueEx(sk, "HOME_NAME")
                            except OSError:
                                # Fall back to the key suffix when HOME_NAME is absent
                                home_name = subkey_name[4:]  # strip "KEY_" prefix
                    except OSError:
                        continue

                    resolved = normalize_client_path(oracle_home)
                    if not resolved:
                        continue
                    norm_key = os.path.normcase(resolved)
                    if norm_key in seen_paths:
                        continue
                    seen_paths.add(norm_key)

                    homes.append({
                        "path": resolved,
                        "home_name": str(home_name),
                        "label": str(home_name),
                    })
        except OSError:
            continue

    return homes


def scan_oracle_client_dirs() -> list[dict[str, Any]]:
    """Scan the system for installed Oracle Client and Instant Client directories.

    Strategy:
    - OUI-registered homes (read from Windows Registry) are labelled with their
      HOME_NAME, matching TOAD's naming convention (e.g. ``OraClient19_home1``).
    - Instant Client directories found only via filesystem scan are labelled
      ``Instant Client - <version>``.

    Returns a list of dicts with client metadata (path, version, label, supports_10g).
    """
    # Build a registry home lookup keyed by normalised path
    registry_homes: dict[str, str] = {
        os.path.normcase(h["path"]): h["home_name"]
        for h in get_registered_oracle_homes()
    }

    candidates = (
        _find_env_candidates()
        + _find_path_candidates()
        + _find_user_dir_candidates()
        + _find_drive_candidates()
    )
    # Seed candidates with every registered home path so OUI homes are never missed
    for reg_path in registry_homes:
        candidates.append(Path(reg_path))

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
        dll_ver = get_oci_dll_version(cand)
        display_ver = dll_ver if dll_ver else ver

        arch_suffix = " (64-bit)" if sys.maxsize > 2**32 else " (32-bit)"
        home_name = registry_homes.get(norm_key)
        if home_name:
            # OUI-registered home: use HOME_NAME as label (TOAD convention)
            label = f"{home_name}{arch_suffix}"
        else:
            cand_path = Path(cand)
            cand_files = {f.name.lower() for f in cand_path.iterdir() if f.is_file()} if cand_path.is_dir() else set()
            is_instant = any(f.startswith("oraociei") or f.startswith("oraociicus") for f in cand_files)
            prefix = "Instant Client" if is_instant else "Oracle Client"
            label = f"{prefix} - {display_ver}{arch_suffix}"

        results.append({
            "path": resolved,
            "version": ver,
            "dll_version": dll_ver or "",
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
        if "not the correct architecture" in msg:
            diagnostics.append(
                "The Oracle Client in the selected directory is 32-bit and cannot be loaded by this 64-bit application.\n\n"
                "• Uncheck 'Connect using Oracle Client' — a local client is not required for most connections.\n"
                "• Or configure a 64-bit Oracle Client (e.g. 64-bit Oracle Instant Client)."
            )
        else:
            diagnostics.append(
                "The Oracle Client library could not be loaded.\n\n"
                "• Uncheck 'Connect using Oracle Client' — a local client is not required for most connections.\n"
                "• If a client is required: ensure the Microsoft Visual C++ 2015–2022 Redistributable is installed and the selected directory contains 64-bit Oracle libraries."
            )

    if "ORA-12514" in msg:
        diagnostics.append(
            "ORA-12514: TNS listener does not know of the requested SERVICE_NAME. "
            "If this is an older Oracle version (such as 10g, 11g XE), try switching Database Type to 'SID'. "
            "For local instances, run 'lsnrctl status' to verify registered service names."
        )

    if "ORA-12505" in msg:
        diagnostics.append(
            "ORA-12505: TNS listener does not know of the requested SID. "
            "If this is a pluggable database (12c+), try switching Database Type to 'Service Name'."
        )

    if "ORA-01017" in msg:
        diagnostics.append(
            "ORA-01017: Invalid username or password, or user is not authorized to log on. "
            "Note for local Oracle XE/FREE (18c+): User schemas exist inside the Pluggable Database "
            "(e.g. 'XEPDB1' or 'FREEPDB1'), not the root container ('XE' or 'FREE')."
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
        if (Path(client_dir) / "tnsnames.ora").is_file():
            return str(client_dir)

    # 4. Well-known "Oracle Client for Microsoft Tools" location (Power BI / Excel driver).
    #    This client does not expose oci.dll so it is never found by find_oracle_client_dir(),
    #    but its network/admin folder is a valid TNS admin directory.
    _MS_TOOLS_CLIENT_ROOTS: tuple[str, ...] = (
        r"C:\Program Files\Oracle Client for Microsoft Tools",
        r"C:\Program Files (x86)\Oracle Client for Microsoft Tools",
    )
    for ms_root in _MS_TOOLS_CLIENT_ROOTS:
        ms_admin = Path(ms_root) / "network" / "admin"
        if ms_admin.is_dir():
            return str(ms_admin)
        if (Path(ms_root) / "tnsnames.ora").is_file():
            return ms_root

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
    if clean_host.lower() == "localhost":
        clean_host = "127.0.0.1"
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


def _isolated_oracle_test_worker(conn_data: dict[str, Any]) -> tuple[bool, str]:
    """Worker function executed inside a separate child process for isolated connection testing."""
    driver_mode = str(conn_data.get("driver_mode", "")).lower()
    client_dir = conn_data.get("oracle_client_dir")

    if "thick" in driver_mode or client_dir:
        if not init_oracle_thick_mode(client_dir):
            err = get_last_thick_mode_error() or "Unknown error initializing Oracle Instant Client"
            target = client_dir or "system default"
            advice = diagnose_oracle_error(err)
            msg = f'Oracle Client failed to initialize (directory: "{target}"):\n\n{err}'
            if advice:
                msg += f"\n\n{advice}"
            return (False, msg)

    import oracledb

    dsn = conn_data.get("dsn")
    if not dsn:
        host = conn_data.get("host", "localhost")
        port = conn_data.get("port") or DEFAULT_ORACLE_PORT
        db_name = conn_data.get("database") or conn_data.get("service_name", "")
        db_type = conn_data.get("oracle_db_type") or conn_data.get("database_type", "service_name")
        dsn = build_oracle_dsn(host, port, db_name, db_type=db_type)

    kwargs: dict[str, Any] = {
        "user": conn_data.get("user", ""),
        "password": conn_data.get("password", ""),
        "dsn": dsn,
    }
    mode = get_oracle_auth_mode(conn_data.get("role"))
    if mode != oracledb.AUTH_MODE_DEFAULT:
        kwargs["mode"] = mode
    config_dir = conn_data.get("config_dir") or conn_data.get("tns_admin") or find_default_tns_admin_dir()
    if config_dir and oracledb.is_thin_mode():
        kwargs["config_dir"] = config_dir

    try:
        conn = oracledb.connect(**kwargs)
        conn.close()
        return True, "Connected successfully"
    except Exception as e:
        advice = diagnose_oracle_error(e)
        msg = f"Oracle connection error:\n{e}"
        if advice:
            msg += f"\n\nSuggested Fix:\n{advice}"
        return False, msg


def test_oracle_connection_isolated(conn_data: dict[str, Any]) -> tuple[bool, str]:
    """Test Oracle database connectivity inside an isolated subprocess.

    Running the test in a separate subprocess guarantees that testing Thin mode
    or testing Thick mode never mutates or locks the main application process's
    python-oracledb C-driver state (preventing DPY-2019 errors).
    """
    try:
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_isolated_oracle_test_worker, conn_data)
            return future.result(timeout=30)
    except FuturesTimeoutError:
        return False, "Connection test timed out after 30 seconds."
    except Exception as exc:
        logger.warning(
            f"ProcessPoolExecutor failed for Oracle connection test ({exc}), falling back to direct test"
        )
        return _isolated_oracle_test_worker(conn_data)


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


def disable_dbms_output(cursor: Any) -> None:
    """Disable Oracle DBMS_OUTPUT message buffer on the given cursor and purge messages."""
    try:
        cursor.callproc("dbms_output.disable")
    except Exception as e:
        logger.debug(f"Failed to disable DBMS_OUTPUT: {e}")


def fetch_dbms_output(cursor: Any, chunk_size: int = 100, on_chunk: Any = None) -> str | None:
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
            if on_chunk:
                try:
                    on_chunk("\n".join(chunk))
                except Exception:
                    pass
            if num_lines < chunk_size:
                break
    except Exception as e:
        logger.debug(f"Failed to fetch DBMS_OUTPUT: {e}")

    return "\n".join(lines) if lines else None


_ORACLE_PLSQL_BLOCK_KEYWORDS: set[str] = {"BEGIN", "DECLARE"}
_ORACLE_PLSQL_DDL_PATTERN: re.Pattern = re.compile(
    r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?(PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?|TRIGGER|TYPE(?:\s+BODY)?)\b",
    re.IGNORECASE,
)


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
    if first_token in _ORACLE_PLSQL_BLOCK_KEYWORDS:
        return True
    if first_token in ("EXEC", "EXECUTE"):
        return True
    if first_token == "CREATE" and _ORACLE_PLSQL_DDL_PATTERN.match(q):
        return True
    return False


def prepare_oracle_query(query: str) -> tuple[str, bool, bool]:
    """Prepare an Oracle query for execution by oracledb.

    Returns:
        tuple of (prepared_query, is_plsql, should_handle_dbms)
    """
    if not query:
        return "", False, False

    raw = query.strip()
    cleaned = re.sub(r"/\s*$", "", raw).strip()

    uncommented = re.sub(r"--[^\n]*", "", cleaned)
    uncommented = re.sub(r"/\*.*?\*/", "", uncommented, flags=re.DOTALL).strip()

    words = uncommented.split()
    first_token = words[0].upper() if words else ""

    if first_token in ("EXEC", "EXECUTE"):
        body = re.sub(r"^\s*(?:EXEC|EXECUTE)\s+", "", cleaned, flags=re.IGNORECASE).strip().rstrip(";")
        prepared = f"BEGIN {body}; END;"
        return prepared, True, True

    is_plsql = is_oracle_plsql(cleaned)
    is_call = first_token == "CALL"
    should_handle_dbms = is_plsql or is_call

    if is_plsql:
        prepared = cleaned if cleaned.endswith(";") else cleaned + ";"
    else:
        prepared = cleaned[:-1].rstrip() if cleaned.endswith(";") else cleaned

    return prepared, is_plsql, should_handle_dbms


def parse_oracle_ddl_target(query: str) -> tuple[str, str] | None:
    """Extract (object_type, object_name) from CREATE OR REPLACE statements."""
    if not query:
        return None
    q = re.sub(r"--[^\n]*", "", query)
    q = re.sub(r"/\*.*?\*/", "", q, flags=re.DOTALL).strip()
    match = re.search(
        r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?(PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?|TRIGGER|TYPE(?:\s+BODY)?|VIEW)\s+(?:\"?(\w+)\"?\.)?\"?(\w+)\"?",
        q,
        re.IGNORECASE,
    )
    if match:
        obj_type = re.sub(r"\s+", " ", match.group(1).upper().strip())
        obj_name = match.group(3).upper()
        return obj_type, obj_name
    return None


def fetch_oracle_compiler_errors(
    cursor: Any,
    object_name: str | None = None,
    object_type: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch compilation errors from USER_ERRORS.

    Returns a list of dicts: [{'name': ..., 'type': ..., 'line': ..., 'position': ..., 'text': ...}]
    """
    errors: list[dict[str, Any]] = []
    try:
        sql = "SELECT NAME, TYPE, LINE, POSITION, TEXT FROM USER_ERRORS"
        params: list[Any] = []
        clauses: list[str] = []
        if object_name:
            clauses.append("NAME = :name")
            params.append(object_name.upper())
        if object_type:
            clauses.append("TYPE = :type")
            params.append(object_type.upper())
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY SEQUENCE"

        cursor.execute(sql, params)
        rows = cursor.fetchall() or []
        for r in rows:
            errors.append({
                "name": str(r[0]) if len(r) > 0 and r[0] is not None else "",
                "type": str(r[1]) if len(r) > 1 and r[1] is not None else "",
                "line": int(r[2]) if len(r) > 2 and r[2] is not None else 1,
                "position": int(r[3]) if len(r) > 3 and r[3] is not None else 1,
                "text": str(r[4]) if len(r) > 4 and r[4] is not None else "",
            })
    except Exception as e:
        logger.debug(f"Failed to fetch USER_ERRORS: {e}")
    return errors



def _oracle_quote(ident: str) -> str:
    """Format an Oracle identifier, quoting only when lowercase or special characters are present."""
    if not ident:
        return ""
    if re.match(r"^[A-Z][A-Z0-9_$#]*$", ident):
        return ident
    return f'"{ident}"'


def _format_oracle_col_type(dtype: str, dlen: Any, dprec: Any, dscale: Any) -> str:
    """Format Oracle column type with precision/scale or length."""
    if dtype == "NUMBER":
        if dprec is not None and dscale is not None:
            return f"NUMBER({dprec},{dscale})"
        if dprec is not None:
            return f"NUMBER({dprec})"
        return "NUMBER"
    if dtype in ("VARCHAR2", "CHAR", "RAW", "NVARCHAR2", "NCHAR") and dlen:
        return f"{dtype}({dlen})"
    return dtype


def _build_oracle_table_ddl(cursor: Any, owner: str, table_name: str) -> str:
    """Build clean, developer-friendly CREATE TABLE DDL using catalog views without DBMS_METADATA bloat."""
    col_rows = []
    try:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                   NULLABLE, DATA_DEFAULT
            FROM ALL_TAB_COLS
            WHERE OWNER = :own AND TABLE_NAME = :tbl AND HIDDEN_COLUMN = 'NO'
            ORDER BY COLUMN_ID
            """,
            {"own": owner, "tbl": table_name},
        )
        col_rows = cursor.fetchall()
    except Exception:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                   NULLABLE, DATA_DEFAULT
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = :own AND TABLE_NAME = :tbl
            ORDER BY COLUMN_ID
            """,
            {"own": owner, "tbl": table_name},
        )
        col_rows = cursor.fetchall()

    if not col_rows:
        raise ValueError(f"Table '{owner}.{table_name}' has no accessible columns.")

    identity_cols: dict[str, str] = {}
    try:
        cursor.execute(
            """
            SELECT COLUMN_NAME, GENERATION_TYPE
            FROM ALL_TAB_IDENTITY_COLS
            WHERE OWNER = :own AND TABLE_NAME = :tbl
            """,
            {"own": owner, "tbl": table_name},
        )
        for cname, gen_type in cursor.fetchall():
            identity_cols[cname] = str(gen_type).strip().upper()
    except Exception:
        pass

    col_lines: list[str] = []
    for cname, dtype, dlen, dprec, dscale, nullable, ddef in col_rows:
        t_str = _format_oracle_col_type(dtype, dlen, dprec, dscale)
        col_def = f"    {_oracle_quote(cname)} {t_str}"

        if cname in identity_cols:
            gen_type = identity_cols[cname]
            if "ALWAYS" in gen_type:
                col_def += " GENERATED ALWAYS AS IDENTITY"
            else:
                col_def += " GENERATED BY DEFAULT AS IDENTITY"
        elif ddef and str(ddef).strip():
            def_str = str(ddef).strip()
            if "ISEQ$$" not in def_str:
                col_def += f" DEFAULT {def_str}"

        if nullable == "N":
            col_def += " NOT NULL"
        col_lines.append(col_def)

    try:
        cursor.execute(
            """
            SELECT c.CONSTRAINT_NAME, cc.COLUMN_NAME
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc
              ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
            WHERE c.OWNER = :own AND c.TABLE_NAME = :tbl AND c.CONSTRAINT_TYPE = 'P'
            ORDER BY cc.POSITION
            """,
            {"own": owner, "tbl": table_name},
        )
        pk_rows = cursor.fetchall()
        if pk_rows:
            pk_name = pk_rows[0][0]
            pk_cols = ", ".join(_oracle_quote(r[1]) for r in pk_rows)
            if pk_name.startswith("SYS_C"):
                col_lines.append(f"    PRIMARY KEY ({pk_cols})")
            else:
                col_lines.append(f"    CONSTRAINT {_oracle_quote(pk_name)} PRIMARY KEY ({pk_cols})")
    except Exception as e:
        logger.debug(f"Failed to fetch PK constraints: {e}")

    full_tbl = f"{_oracle_quote(owner)}.{_oracle_quote(table_name)}" if owner else _oracle_quote(table_name)
    ddl = f"-- Table: {owner}.{table_name}\n\nCREATE TABLE {full_tbl} (\n" + ",\n".join(col_lines) + "\n);"

    try:
        cursor.execute(
            """
            SELECT INDEX_NAME
            FROM ALL_INDEXES
            WHERE OWNER = :own AND TABLE_NAME = :tbl AND UNIQUENESS != 'UNIQUE'
            ORDER BY INDEX_NAME
            """,
            {"own": owner, "tbl": table_name},
        )
        for (idx_name,) in cursor.fetchall():
            cursor.execute(
                """
                SELECT COLUMN_NAME
                FROM ALL_IND_COLUMNS
                WHERE INDEX_OWNER = :own AND INDEX_NAME = :iname
                ORDER BY COLUMN_POSITION
                """,
                {"own": owner, "iname": idx_name},
            )
            icols = [r[0] for r in cursor.fetchall()]
            if icols:
                cols_str = ", ".join(_oracle_quote(c) for c in icols)
                ddl += f"\n\nCREATE INDEX {_oracle_quote(owner)}.{_oracle_quote(idx_name)} ON {full_tbl} ({cols_str});"
    except Exception as e:
        logger.debug(f"Failed to fetch indexes: {e}")

    return ddl


_build_oracle_fallback_table_ddl = _build_oracle_table_ddl


def _clean_oracle_ddl(ddl: str) -> str:
    """Format Oracle raw DDL from DBMS_METADATA into clean, developer-friendly SQL."""
    if not ddl:
        return ""

    # Simplify verbose identity sequence clauses
    ddl = re.sub(
        r'GENERATED\s+(ALWAYS|BY\s+DEFAULT(?:\s+ON\s+NULL)?)\s+AS\s+IDENTITY\s+MINVALUE\s+\d+.*?(?=\s+NOT\s+NULL|\s*,\s*$|\s*\))',
        r'GENERATED \1 AS IDENTITY',
        ddl,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Clean up redundant constraints/flags
    ddl = re.sub(r'\bNOT\s+NULL\s+ENABLE\b', 'NOT NULL', ddl, flags=re.IGNORECASE)
    ddl = re.sub(r'\s+USING\s+INDEX\s+ENABLE\b', '', ddl, flags=re.IGNORECASE)
    ddl = re.sub(r'\s+ENABLE\b', '', ddl, flags=re.IGNORECASE)
    ddl = re.sub(r'[ \t]{2,}', ' ', ddl)

    # Unquote standard uppercase identifiers
    def unquote_ident(m: re.Match) -> str:
        ident = m.group(1)
        if re.match(r'^[A-Z][A-Z0-9_$#]*$', ident):
            return ident
        return m.group(0)

    ddl = re.sub(r'"([^"]+)"', unquote_ident, ddl)

    # Normalize line indentation
    lines = ddl.splitlines()
    cleaned_lines = []
    for idx, line in enumerate(lines):
        line = line.replace('\t', '    ').rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if idx == 0:
            cleaned_lines.append(stripped)
        elif stripped.startswith('('):
            cleaned_lines[0] = cleaned_lines[0] + ' ('
            sub = stripped[1:].strip()
            if sub:
                cleaned_lines.append(f'    {sub}')
        elif stripped.startswith(')'):
            cleaned_lines.append(');' if ';' in stripped else ')')
        else:
            cleaned_lines.append(f'    {stripped}')

    result = '\n'.join(cleaned_lines)
    if not result.strip().endswith(';'):
        result += ';'
    return result


def generate_oracle_table_ddl(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
    obj_type: str = "TABLE",
) -> str:
    """Generate clean, developer-friendly DDL for an Oracle table, view, or materialized view."""
    from db.db_connections import get_pooled_oracle_connection

    owner = (schema_name or conn_data.get("user") or "").upper()
    tbl = table_name.upper()
    upper_type = obj_type.upper()

    conn = get_pooled_oracle_connection(conn_data=conn_data)
    try:
        conn.call_timeout = 8000
    except Exception:
        pass

    cursor = conn.cursor()
    try:
        full_name = f"{_oracle_quote(owner)}.{_oracle_quote(tbl)}" if owner else _oracle_quote(tbl)

        if "MATERIALIZED" in upper_type or "MVIEW" in upper_type:
            cursor.execute("SELECT QUERY FROM ALL_MVIEWS WHERE OWNER = :own AND MVIEW_NAME = :vname", {"own": owner, "vname": tbl})
            mvrow = cursor.fetchone()
            if mvrow and mvrow[0]:
                mvtext = mvrow[0].read() if hasattr(mvrow[0], "read") else str(mvrow[0])
                sql = f"-- Materialized View: {owner}.{tbl}\n\nCREATE MATERIALIZED VIEW {full_name} AS\n{mvtext.strip()}"
                return sql if sql.endswith(";") else sql + ";"

        if "VIEW" in upper_type:
            cursor.execute("SELECT TEXT FROM ALL_VIEWS WHERE OWNER = :own AND VIEW_NAME = :vname", {"own": owner, "vname": tbl})
            vrow = cursor.fetchone()
            if vrow and vrow[0]:
                vtext = vrow[0].read() if hasattr(vrow[0], "read") else str(vrow[0])
                sql = f"-- View: {owner}.{tbl}\n\nCREATE OR REPLACE VIEW {full_name} AS\n{vtext.strip()}"
                return sql if sql.endswith(";") else sql + ";"

        # For tables: fast (<50ms) direct catalog DDL avoids DBMS_METADATA locks and bloat
        try:
            return _build_oracle_table_ddl(cursor, owner, tbl)
        except Exception as e:
            logger.debug(f"Direct catalog DDL failed ({e}); attempting DBMS_METADATA fallback.")

        # Fallback to DBMS_METADATA if direct catalog generation had an issue
        try:
            cursor.execute(
                "SELECT DBMS_METADATA.GET_DDL('TABLE', :obj_name, :owner) FROM DUAL",
                {"obj_name": tbl, "owner": owner or None},
            )
            row = cursor.fetchone()
            if row and row[0]:
                val = row[0]
                ddl_str = val.read() if hasattr(val, "read") else str(val)
                ddl_str = ddl_str.strip()
                if ddl_str:
                    return _clean_oracle_ddl(ddl_str)
        except Exception as e:
            logger.debug(f"DBMS_METADATA fallback failed: {e}")

        raise ValueError(f"Could not generate DDL for '{owner}.{tbl}'. Object not found or access denied.")
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass


def _detect_oracle_sequences(
    cursor: Any,
    owner: str,
    table_name: str,
    columns: list[dict[str, Any]],
    pk_columns: list[str],
) -> dict[str, dict[str, str]]:
    """Detect sequences associated with table columns via Identity, DEFAULT, triggers, or naming conventions."""
    col_seq_map: dict[str, dict[str, str]] = {}

    # 1. Identity Columns (Oracle 12c+)
    try:
        cursor.execute(
            """
            SELECT COLUMN_NAME, GENERATION_TYPE, SEQUENCE_NAME
            FROM ALL_TAB_IDENTITY_COLS
            WHERE OWNER = :own AND TABLE_NAME = :tbl
            """,
            {"own": owner, "tbl": table_name},
        )
        for cname, gen_type, seq_name in cursor.fetchall():
            gen = (gen_type or "").upper()
            col_seq_map[cname] = {
                "sequence": seq_name or "IDENTITY",
                "type": f"Identity ({gen})",
                "value": "DEFAULT",
                "is_identity": True,
            }
    except Exception as e:
        logger.debug(f"Identity column check failed: {e}")

    # 2. Columns with DEFAULT containing .NEXTVAL
    for col in columns:
        cname = col["name"]
        ddef = col.get("default", "")
        if cname not in col_seq_map and ddef and "NEXTVAL" in ddef.upper():
            m = re.search(r'([A-Za-z0-9_".]+)\.NEXTVAL', ddef, re.IGNORECASE)
            seq_expr = m.group(0) if m else ddef
            seq_name = m.group(1).replace('"', '') if m else "SEQUENCE"
            if "ISEQ$$_" in seq_name.upper():
                col_seq_map[cname] = {
                    "sequence": seq_name,
                    "type": "Identity (DEFAULT)",
                    "value": "DEFAULT",
                    "is_identity": True,
                }
            else:
                col_seq_map[cname] = {
                    "sequence": seq_name,
                    "type": "Column DEFAULT",
                    "value": seq_expr,
                    "is_identity": False,
                }

    # 3. BEFORE INSERT triggers referencing a sequence
    try:
        cursor.execute(
            """
            SELECT d.REFERENCED_NAME, t.TRIGGER_NAME
            FROM ALL_DEPENDENCIES d
            JOIN ALL_TRIGGERS t ON d.NAME = t.TRIGGER_NAME AND d.OWNER = t.OWNER
            WHERE (t.TABLE_OWNER = :own OR t.OWNER = :own)
              AND t.TABLE_NAME = :tbl
              AND (t.TRIGGERING_EVENT LIKE '%INSERT%' OR t.TRIGGERING_EVENT = 'ALL')
              AND d.REFERENCED_TYPE = 'SEQUENCE'
            """,
            {"own": owner, "tbl": table_name},
        )
        for seq_name, trig_name in cursor.fetchall():
            target_col = None
            try:
                cursor.execute(
                    "SELECT TRIGGER_BODY FROM ALL_TRIGGERS WHERE OWNER = :own AND TRIGGER_NAME = :tname",
                    {"own": owner, "tname": trig_name},
                )
                tb_row = cursor.fetchone()
                if tb_row and tb_row[0]:
                    tbody = tb_row[0].read() if hasattr(tb_row[0], "read") else str(tb_row[0])
                    m1 = re.search(r":NEW\.([A-Za-z0-9_]+)\s*:=", tbody, re.I)
                    m2 = re.search(r"INTO\s+:NEW\.([A-Za-z0-9_]+)", tbody, re.I)
                    if m1:
                        target_col = m1.group(1).upper()
                    elif m2:
                        target_col = m2.group(1).upper()
            except Exception:
                target_col = None

            if not target_col and len(pk_columns) == 1:
                target_col = pk_columns[0]
            elif not target_col and pk_columns:
                for col in columns:
                    if col["name"] in pk_columns and "NUMBER" in col["data_type"]:
                        target_col = col["name"]
                        break

            if target_col and target_col not in col_seq_map:
                col_seq_map[target_col] = {
                    "sequence": seq_name,
                    "type": f"Trigger ({trig_name})",
                    "value": f"{_oracle_quote(owner)}.{_oracle_quote(seq_name)}.NEXTVAL" if owner else f"{_oracle_quote(seq_name)}.NEXTVAL",
                }
    except Exception as e:
        logger.debug(f"Trigger sequence check failed: {e}")

    # 4. Standard naming conventions in ALL_SEQUENCES
    if not col_seq_map and pk_columns:
        candidates = [
            f"{table_name}_SEQ",
            f"SEQ_{table_name}",
            f"{table_name}_ID_SEQ",
            f"SEQ_{table_name}_ID",
        ]
        try:
            placeholders = ", ".join(f":c{i}" for i in range(len(candidates)))
            params = {"own": owner}
            params.update({f"c{i}": c for i, c in enumerate(candidates)})
            cursor.execute(
                f"SELECT SEQUENCE_NAME FROM ALL_SEQUENCES WHERE SEQUENCE_OWNER = :own AND SEQUENCE_NAME IN ({placeholders})",
                params,
            )
            srow = cursor.fetchone()
            if srow and srow[0]:
                matched_seq = srow[0]
                target_col = pk_columns[0]
                col_seq_map[target_col] = {
                    "sequence": matched_seq,
                    "type": "Naming Convention",
                    "value": f"{_oracle_quote(owner)}.{_oracle_quote(matched_seq)}.NEXTVAL" if owner else f"{_oracle_quote(matched_seq)}.NEXTVAL",
                }
        except Exception as e:
            logger.debug(f"Naming convention sequence check failed: {e}")

    return col_seq_map


def _format_oracle_insert_value(col: dict[str, Any], col_seq_map: dict[str, dict[str, str]]) -> str:
    """Return appropriate placeholder or sequence expression for an Oracle column value."""
    cname = col["name"]
    raw_type = col.get("raw_type", "").upper()

    if cname in col_seq_map:
        return col_seq_map[cname]["value"]
    if "DATE" in raw_type:
        return "SYSDATE"
    if "TIMESTAMP" in raw_type:
        return "SYSTIMESTAMP"
    if any(t in raw_type for t in ("NUMBER", "FLOAT", "INTEGER", "INT", "SMALLINT", "DECIMAL")):
        return "1"
    if any(t in raw_type for t in ("VARCHAR", "CHAR", "CLOB", "NCHAR", "NVARCHAR")):
        return f"'{cname.title()}'"
    if "RAW" in raw_type:
        return "HEXTORAW('00')"
    if "BLOB" in raw_type:
        return "EMPTY_BLOB()"
    return "NULL"


def generate_oracle_insert_script(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
) -> str:
    """Generate an INSERT script for an Oracle table with actual column names and sequence detection."""
    from db.db_connections import get_pooled_oracle_connection

    owner = (schema_name or conn_data.get("user") or "").upper()
    tbl = table_name.upper()

    conn = get_pooled_oracle_connection(conn_data=conn_data)
    try:
        conn.call_timeout = 8000
    except Exception:
        pass
    cursor = conn.cursor()
    try:
        col_rows = []
        try:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                       NULLABLE, DATA_DEFAULT
                FROM ALL_TAB_COLS
                WHERE OWNER = :own AND TABLE_NAME = :tbl AND HIDDEN_COLUMN = 'NO'
                ORDER BY COLUMN_ID
                """,
                {"own": owner, "tbl": tbl},
            )
            col_rows = cursor.fetchall()
        except Exception:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                       NULLABLE, DATA_DEFAULT
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = :own AND TABLE_NAME = :tbl
                ORDER BY COLUMN_ID
                """,
                {"own": owner, "tbl": tbl},
            )
            col_rows = cursor.fetchall()

        if not col_rows:
            raise ValueError(f"Table '{owner}.{tbl}' not found or has no visible columns.")

        columns: list[dict[str, Any]] = []
        for cname, dtype, dlen, dprec, dscale, nullable, ddef in col_rows:
            dtype_str = _format_oracle_col_type(dtype, dlen, dprec, dscale)
            columns.append({
                "name": cname,
                "data_type": dtype_str,
                "raw_type": dtype,
                "nullable": (nullable == "Y"),
                "default": str(ddef).strip() if ddef else "",
            })

        pk_columns: list[str] = []
        try:
            cursor.execute(
                """
                SELECT cc.COLUMN_NAME
                FROM ALL_CONSTRAINTS c
                JOIN ALL_CONS_COLUMNS cc
                  ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.OWNER = :own AND c.TABLE_NAME = :tbl AND c.CONSTRAINT_TYPE = 'P'
                ORDER BY cc.POSITION
                """,
                {"own": owner, "tbl": tbl},
            )
            pk_columns = [r[0] for r in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"Failed to fetch PK columns: {e}")

        col_seq_map = _detect_oracle_sequences(cursor, owner, tbl, columns, pk_columns)

        col_names = [f"    {_oracle_quote(col['name'])}" for col in columns]
        val_exprs = [f"    {_format_oracle_insert_value(col, col_seq_map)}" for col in columns]

        full_tbl = f"{_oracle_quote(owner)}.{_oracle_quote(tbl)}" if owner else _oracle_quote(tbl)

        header_lines = [f"-- Insert Script for {full_tbl}"]
        if col_seq_map:
            for cname, sinfo in col_seq_map.items():
                if sinfo.get("is_identity"):
                    header_lines.append(
                        f"-- Identity column detected on {cname}: auto-generated (uses DEFAULT)"
                    )
                else:
                    header_lines.append(
                        f"-- Sequence detected on column {cname}: {sinfo['sequence']} via {sinfo['type']}"
                    )
        else:
            header_lines.append("-- No sequence detected for this table")

        header = "\n".join(header_lines)
        cols_block = ",\n".join(col_names)
        vals_block = ",\n".join(val_exprs)

        return f"{header}\n\nINSERT INTO {full_tbl} (\n{cols_block}\n)\nVALUES (\n{vals_block}\n);"
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass



def generate_oracle_update_script(
    conn_data: dict[str, Any],
    schema_name: str,
    table_name: str,
) -> str:
    """Generate an UPDATE script for an Oracle table with non-PK columns in SET and PK in WHERE."""
    from db.db_connections import get_pooled_oracle_connection

    owner = (schema_name or conn_data.get("user") or "").upper()
    tbl = table_name.upper()

    conn = get_pooled_oracle_connection(conn_data=conn_data)
    try:
        conn.call_timeout = 8000
    except Exception:
        pass
    cursor = conn.cursor()
    try:
        col_rows = []
        try:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                       NULLABLE, DATA_DEFAULT
                FROM ALL_TAB_COLS
                WHERE OWNER = :own AND TABLE_NAME = :tbl AND HIDDEN_COLUMN = 'NO'
                ORDER BY COLUMN_ID
                """,
                {"own": owner, "tbl": tbl},
            )
            col_rows = cursor.fetchall()
        except Exception:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE,
                       NULLABLE, DATA_DEFAULT
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = :own AND TABLE_NAME = :tbl
                ORDER BY COLUMN_ID
                """,
                {"own": owner, "tbl": tbl},
            )
            col_rows = cursor.fetchall()

        if not col_rows:
            raise ValueError(f"Table '{owner}.{tbl}' not found or has no visible columns.")

        columns: list[dict[str, Any]] = []
        for cname, dtype, dlen, dprec, dscale, nullable, ddef in col_rows:
            dtype_str = _format_oracle_col_type(dtype, dlen, dprec, dscale)
            columns.append({
                "name": cname,
                "data_type": dtype_str,
                "raw_type": dtype,
                "nullable": (nullable == "Y"),
                "default": str(ddef).strip() if ddef else "",
            })

        pk_columns: list[str] = []
        try:
            cursor.execute(
                """
                SELECT cc.COLUMN_NAME
                FROM ALL_CONSTRAINTS c
                JOIN ALL_CONS_COLUMNS cc
                  ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
                WHERE c.OWNER = :own AND c.TABLE_NAME = :tbl AND c.CONSTRAINT_TYPE = 'P'
                ORDER BY cc.POSITION
                """,
                {"own": owner, "tbl": tbl},
            )
            pk_columns = [r[0] for r in cursor.fetchall()]
        except Exception as e:
            logger.debug(f"Failed to fetch PK columns: {e}")

        col_seq_map = _detect_oracle_sequences(cursor, owner, tbl, columns, pk_columns)

        set_lines = []
        for col in columns:
            cname = col["name"]
            if cname in pk_columns:
                continue
            sinfo = col_seq_map.get(cname, {})
            if "ALWAYS" in sinfo.get("type", ""):
                continue
            val = _format_oracle_insert_value(col, col_seq_map)
            if val == "DEFAULT" or ".NEXTVAL" in val:
                raw_t = col.get("raw_type", "").upper()
                val = "1" if any(t in raw_t for t in ("NUMBER", "FLOAT", "INT")) else f"'{cname.title()}'"
            set_lines.append(f"    {_oracle_quote(cname)} = {val}")

        full_tbl = f"{_oracle_quote(owner)}.{_oracle_quote(tbl)}" if owner else _oracle_quote(tbl)

        if pk_columns:
            where_cond = " AND ".join(f"{_oracle_quote(pk)} = 1" for pk in pk_columns)
            where_line = f"WHERE {where_cond};"
            header = f"-- Update Script for {full_tbl}\n-- Primary Key: {', '.join(pk_columns)}"
        else:
            where_line = "WHERE <condition>;"
            header = f"-- Update Script for {full_tbl}\n-- Note: No primary key detected; specify WHERE condition"

        if not set_lines:
            set_lines = ["    -- No editable non-PK columns found"]

        set_block = ",\n".join(set_lines)
        return f"{header}\n\nUPDATE {full_tbl}\nSET\n{set_block}\n{where_line}"
    finally:
        cursor.close()
        try:
            conn.close()
        except Exception:
            pass
