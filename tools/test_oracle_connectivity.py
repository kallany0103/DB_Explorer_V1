"""Oracle connectivity testing and diagnostic tool.

Use this script to diagnose client libraries, test Oracle connections across all modes
(Basic Service Name, Basic SID, TNS, Custom DSN, Thin vs Thick driver modes),
and identify compatibility issues with older Oracle versions.

Usage examples:
  # 1. Run local environment & client diagnostics
  python tools/test_oracle_connectivity.py --diagnose

  # 2. Test Basic connection (Service Name)
  python tools/test_oracle_connectivity.py --host 192.168.1.50 --port 1521 --service ORCLPDB1 --user system --password manager

  # 3. Test Basic connection (SID - typical for Oracle 10g/11g)
  python tools/test_oracle_connectivity.py --host 192.168.1.50 --port 1521 --sid XE --user scott --password tiger

  # 4. Test TNS alias
  python tools/test_oracle_connectivity.py --tns-alias PROD_DB --user scott --password tiger

  # 5. Test with custom Oracle Client directory (e.g. for Oracle 10g/9i requiring Instant Client 11.2)
  python tools/test_oracle_connectivity.py --host localhost --sid XE --user scott --password tiger --client-dir C:\\oracle\\instantclient_11_2
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import oracledb  # noqa: E402

from db.oracle_utils import (  # noqa: E402
    build_oracle_dsn,
    diagnose_oracle_error,
    find_default_tns_admin_dir,
    find_oracle_client_dir,
    get_oracle_auth_mode,
    get_tns_names,
    init_oracle_thick_mode,
    scan_oracle_client_dirs,
)


def print_header(title: str) -> None:
    print(f"\n{'=' * 65}\n  {title}\n{'=' * 65}")


def print_status(label: str, value: Any, ok: bool | None = None) -> None:
    status_indicator = ""
    if ok is True:
        status_indicator = " [OK]"
    elif ok is False:
        status_indicator = " [WARN/FAIL]"
    print(f"  * {label:<32}: {value}{status_indicator}")


def run_diagnostics(custom_client_dir: str | None = None) -> None:
    """Run comprehensive local environment and Oracle driver diagnostics."""
    print_header("ORACLE CLIENT & DRIVER DIAGNOSTICS")

    # 1. Python environment
    bitness = "64-bit" if sys.maxsize > 2**32 else "32-bit"
    print_status("Python Version", f"{platform.python_version()} ({bitness})", ok=True)
    print_status("Operating System", f"{platform.system()} {platform.release()}", ok=True)
    print_status("python-oracledb version", oracledb.__version__, ok=True)

    # 2. Bundled & Scanned Client Detections
    scanned_clients = scan_oracle_client_dirs()
    print_status("Scanned Oracle Clients", f"Found {len(scanned_clients)} installation(s)", ok=bool(scanned_clients))
    for idx, sc in enumerate(scanned_clients, 1):
        bundled_tag = " [Bundled]" if sc.get("is_bundled") else " [External]"
        legacy_tag = " (Supports 10g/9i)" if sc.get("supports_10g") else ""
        print(f"      [{idx}] Instant Client {sc['version']}{bundled_tag}{legacy_tag}: {sc['path']}")

    client_dir = find_oracle_client_dir(custom_client_dir)
    print_status("Active Target Client Dir", client_dir or "Not detected", ok=bool(client_dir))

    if client_dir:
        oci_path = Path(client_dir) / ("oci.dll" if sys.platform == "win32" else "libclntsh.so")
        print_status("OCI Library Present", str(oci_path.is_file()), ok=oci_path.is_file())

    # 3. Windows Visual C++ Runtime Check
    if sys.platform == "win32":
        sys32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
        vc_runtime = sys32 / "vcruntime140.dll"
        print_status("VC++ Runtime (vcruntime140.dll)", str(vc_runtime.is_file()), ok=vc_runtime.is_file())

    # 4. TNS Configuration
    tns_admin = find_default_tns_admin_dir()
    print_status("Default TNS_ADMIN Dir", tns_admin or "None", ok=bool(tns_admin))
    if tns_admin:
        aliases = get_tns_names(tns_admin)
        print_status("TNS Aliases Found", f"{len(aliases)} ({', '.join(aliases[:5])}{'...' if len(aliases) > 5 else ''})")

    # 5. Thick Mode Initialization Test
    print_header("DRIVER MODE INITIALIZATION")
    init_oracle_thick_mode(custom_client_dir)
    is_thin = oracledb.is_thin_mode()
    print_status("Thick Mode Active", str(not is_thin), ok=not is_thin)
    print_status("Thin Mode Active", str(is_thin))

    # 6. Version Compatibility Matrix
    print_header("ORACLE DATABASE VERSION COMPATIBILITY MATRIX")
    print("  Version           Thin Mode    Thick Mode (19c)   Thick Mode (11.2)")
    print("  ----------------  -----------  -----------------  -----------------")
    print("  Oracle 23ai       YES          YES                YES")
    print("  Oracle 21c        YES          YES                YES")
    print("  Oracle 19c        YES          YES                YES")
    print("  Oracle 18c        YES          YES                YES")
    print("  Oracle 12.1/12.2  YES          YES                YES")
    print("  Oracle 11.2       NO (DPY-3010)YES                YES")
    print("  Oracle 10g / 9i   NO (DPY-3010)NO (ORA-03134)     YES (Required)")
    print("=" * 65)


def test_oracle_connection(
    host: str = "",
    port: int = 1521,
    service_name: str = "",
    sid: str = "",
    tns_alias: str = "",
    dsn: str = "",
    user: str = "",
    password: str = "",
    role: str = "Normal",
    client_dir: str | None = None,
    thick: bool = False,
) -> bool:
    """Execute a connection test and output query results or diagnostic failure advice."""
    print_header("ORACLE CONNECTION TEST")

    # 1. Driver Mode Setup: defaults to Thin mode (no client library needed)
    if thick or client_dir:
        init_oracle_thick_mode(client_dir)
    print_status(
        "Driver Engine",
        "Thick Mode (Instant Client)" if not oracledb.is_thin_mode() else "Thin Mode (Pure Python - No Client Needed)",
    )

    # 2. DSN Resolution
    effective_dsn = dsn.strip()
    if not effective_dsn:
        if tns_alias.strip():
            effective_dsn = tns_alias.strip()
        elif sid.strip():
            effective_dsn = build_oracle_dsn(host, port, sid.strip(), db_type="sid")
        elif service_name.strip():
            effective_dsn = build_oracle_dsn(host, port, service_name.strip(), db_type="service_name")
        else:
            print("\n[ERROR] No target specified. Please provide --service, --sid, --tns-alias, or --dsn.")
            return False

    print_status("Target DSN", effective_dsn)
    print_status("User", user or "(none)")
    print_status("Role", role)

    # 3. Connect Attempt
    connect_kwargs: dict[str, Any] = {
        "user": user,
        "password": password,
        "dsn": effective_dsn,
    }
    mode = get_oracle_auth_mode(role)
    if mode != oracledb.AUTH_MODE_DEFAULT:
        connect_kwargs["mode"] = mode

    tns_dir = find_default_tns_admin_dir()
    if tns_dir and oracledb.is_thin_mode():
        connect_kwargs["config_dir"] = tns_dir

    print("\nAttempting connection...")
    try:
        conn = oracledb.connect(**connect_kwargs)
        cursor = conn.cursor()

        # Query Database banner / version
        try:
            cursor.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
            row = cursor.fetchone()
            db_banner = row[0] if row else "Unknown"
        except Exception:
            db_banner = "Connected (version query restricted)"

        # Query connected user
        try:
            cursor.execute("SELECT USER FROM dual")
            current_user = cursor.fetchone()[0]
        except Exception:
            current_user = user

        cursor.close()
        conn.close()

        print("\n[SUCCESS] Connected successfully to Oracle Database!")
        print_status("Server Banner", db_banner, ok=True)
        print_status("Connected User", current_user, ok=True)
        return True

    except Exception as exc:
        print(f"\n[FAILURE] Connection failed:\n{exc}")
        advice = diagnose_oracle_error(exc)
        if advice:
            print_header("TROUBLESHOOTING & ACTIONABLE ADVICE")
            print(advice)
            print("=" * 65)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Oracle connections and diagnose client configurations.")
    parser.add_argument("--diagnose", action="store_true", help="Run local environment and client library diagnostics")
    parser.add_argument("--host", default="", help="Database server hostname or IP")
    parser.add_argument("--port", type=int, default=1521, help="Listener port (default: 1521)")
    parser.add_argument("--service", default="", help="Oracle Service Name (e.g. ORCLPDB1)")
    parser.add_argument("--sid", default="", help="Oracle SID (e.g. XE, ORCL - common in older versions)")
    parser.add_argument("--tns-alias", default="", help="TNS network alias from tnsnames.ora")
    parser.add_argument("--dsn", default="", help="Custom DSN or Easy Connect string")
    parser.add_argument("--user", default="", help="Database username")
    parser.add_argument("--password", default="", help="Database password")
    parser.add_argument("--role", default="Normal", choices=["Normal", "SYSDBA", "SYSOPER", "SYSASM"], help="Auth role")
    parser.add_argument("--thick", action="store_true", help="Use Thick Mode with Oracle Instant Client (for older DBs)")
    parser.add_argument("--client-dir", default=None, help="Custom Oracle Instant Client directory path")

    args = parser.parse_args()

    if args.diagnose or not any([args.service, args.sid, args.tns_alias, args.dsn]):
        run_diagnostics(args.client_dir)
        if not any([args.service, args.sid, args.tns_alias, args.dsn]):
            print("\nTip: To test a connection, run with --host, --user, --password, and --service or --sid.")
            return

    test_oracle_connection(
        host=args.host,
        port=args.port,
        service_name=args.service,
        sid=args.sid,
        tns_alias=args.tns_alias,
        dsn=args.dsn,
        user=args.user,
        password=args.password,
        role=args.role,
        client_dir=args.client_dir,
        thick=args.thick,
    )


if __name__ == "__main__":
    main()
