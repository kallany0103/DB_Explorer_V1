# widgets/sqlplus_tool/discovery.py
"""Locate sqlplus.exe and Oracle client libraries.

Follows a 3-tier discovery hierarchy:
1. User-configured custom binary directory or executable path from Settings.
2. System PATH (via shutil.which) and ORACLE_HOME environment variable.
3. Standard Windows Oracle client and Instant Client directories.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _check_binary_in_path(base_path: Path | str, binary_name: str = "sqlplus") -> str | None:
    """Check if base_path is or contains the target executable."""
    try:
        p = Path(base_path)
        ext = ".exe" if os.name == "nt" else ""
        target_name = f"{binary_name.lower()}{ext}"

        if p.is_file() and p.name.lower() == target_name:
            return str(p)
        if p.is_dir():
            cand = p / f"{binary_name}{ext}"
            if cand.is_file():
                return str(cand)
            cand_bin = p / "bin" / f"{binary_name}{ext}"
            if cand_bin.is_file():
                return str(cand_bin)
    except Exception:
        pass
    return None


def _common_oracle_paths() -> list[Path]:
    """Scan standard Oracle Instant Client and Oracle Home locations on Windows."""
    candidates: list[Path] = []

    # ORACLE_HOME environment variable
    oracle_home = os.environ.get("ORACLE_HOME")
    if oracle_home:
        candidates.append(Path(oracle_home))
        candidates.append(Path(oracle_home) / "bin")

    # Common Oracle root directories
    search_roots = [
        Path(r"C:\oracle"),
        Path(r"C:\app"),
        Path(r"C:\instantclient"),
        Path(r"C:\Program Files\Oracle"),
    ]
    for root in search_roots:
        if root.is_dir():
            try:
                for entry in sorted(root.glob("**/sqlplus.exe")):
                    candidates.append(entry.parent)
            except Exception:
                pass

    return candidates


def find_sqlplus(custom_path: str | Path | None = None) -> str | None:
    """Return the path to sqlplus.exe following custom path -> PATH -> standard installs."""
    # 1. Custom user-specified setting from Preferences
    if custom_path:
        found = _check_binary_in_path(custom_path, "sqlplus")
        if found:
            return found

    # 2. System PATH
    which_bin = shutil.which("sqlplus")
    if which_bin:
        return which_bin

    # 3. Standard Windows install locations
    for ora_dir in _common_oracle_paths():
        found = _check_binary_in_path(ora_dir, "sqlplus")
        if found:
            return found

    return None


def instantclient_dir(custom_path: str | Path | None = None) -> str | None:
    """Return the client directory containing sqlplus and OCI DLLs (needed for PATH injection)."""
    sqlplus = find_sqlplus(custom_path)
    if sqlplus:
        return str(Path(sqlplus).parent)
    return None


def admin_dir(custom_path: str | Path | None = None) -> str | None:
    """Return the network/admin dir (TNS_ADMIN), if it exists."""
    tns_admin = os.environ.get("TNS_ADMIN")
    if tns_admin and Path(tns_admin).is_dir():
        return tns_admin

    ic = instantclient_dir(custom_path)
    if ic:
        admin = Path(ic) / "network" / "admin"
        return str(admin)
    return None
