"""Subprocess runner for testing Oracle connectivity in isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: Missing connection payload JSON argument.", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
    except Exception as exc:
        print(f"Error: Invalid JSON connection data: {exc}", file=sys.stderr)
        sys.exit(1)

    driver_mode = str(data.get("driver_mode", "")).lower()
    client_dir = data.get("oracle_client_dir")

    if driver_mode == "thick" or client_dir:
        from db.oracle_utils import get_last_thick_mode_error, init_oracle_thick_mode

        if not init_oracle_thick_mode(client_dir):
            err = get_last_thick_mode_error() or "Unknown error initializing Oracle Instant Client"
            target = client_dir or "system default"
            print(
                f'Oracle Thick Mode (Instant Client) failed to initialize with client directory "{target}":\n\n{err}'
            )
            sys.exit(2)

    import oracledb
    from db.oracle_utils import (
        DEFAULT_ORACLE_PORT,
        build_oracle_dsn,
        diagnose_oracle_error,
        get_oracle_auth_mode,
    )

    dsn = data.get("dsn")
    if not dsn:
        host = data.get("host", "localhost")
        port = data.get("port") or DEFAULT_ORACLE_PORT
        db_name = data.get("database") or data.get("service_name", "")
        db_type = data.get("oracle_db_type") or data.get("database_type", "service_name")
        dsn = build_oracle_dsn(host, port, db_name, db_type=db_type)

    kwargs = {
        "user": data.get("user", ""),
        "password": data.get("password", ""),
        "dsn": dsn,
    }
    mode = get_oracle_auth_mode(data.get("role"))
    if mode != oracledb.AUTH_MODE_DEFAULT:
        kwargs["mode"] = mode
    if data.get("config_dir") or data.get("tns_admin"):
        kwargs["config_dir"] = data.get("config_dir") or data.get("tns_admin")

    try:
        conn = oracledb.connect(**kwargs)
        is_thin = oracledb.is_thin_mode()
        conn.close()
        mode_str = "Thin Mode" if is_thin else "Thick Mode (Instant Client)"
        print(f"Connected successfully to Oracle database using {mode_str}!")
        sys.exit(0)
    except Exception as e:
        advice = diagnose_oracle_error(e)
        msg = f"Oracle connection error: {e}"
        if advice:
            msg += f"\n\nDiagnostic advice:\n{advice}"
        print(msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
