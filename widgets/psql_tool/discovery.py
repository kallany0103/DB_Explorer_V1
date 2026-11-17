# widgets/psql_tool/discovery.py
"""Locate PostgreSQL client executables (psql, pg_dump, pg_restore).

Follows a 3-tier discovery hierarchy:
1. User-configured custom binary directory or executable path from Settings.
2. System PATH (via shutil.which).
3. Standard Windows PostgreSQL installation paths (e.g. C:\\Program Files\\PostgreSQL\\<version>\\bin).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _check_binary_in_path(base_path: Path | str, binary_name: str) -> str | None:
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


def _common_pg_paths() -> list[Path]:
    """Scan standard PostgreSQL installation directories on Windows."""
    candidates: list[Path] = []
    base_dirs = [
        Path(r"C:\Program Files\PostgreSQL"),
        Path(r"C:\Program Files (x86)\PostgreSQL"),
    ]
    for b in base_dirs:
        if b.is_dir():
            try:
                for v in sorted(b.iterdir(), reverse=True):
                    bin_dir = v / "bin"
                    if bin_dir.is_dir():
                        candidates.append(bin_dir)
            except Exception:
                pass
    return candidates


def find_pg_binary(binary_name: str, custom_path: str | Path | None = None) -> str | None:
    """Find a PostgreSQL binary following custom path -> PATH -> standard installs."""
    # 1. User-configured setting from Preferences
    if custom_path:
        found = _check_binary_in_path(custom_path, binary_name)
        if found:
            return found

    # 2. System PATH
    which_bin = shutil.which(binary_name)
    if which_bin:
        return which_bin

    # 3. Standard Windows install locations
    for pg_dir in _common_pg_paths():
        found = _check_binary_in_path(pg_dir, binary_name)
        if found:
            return found

    return None


def find_psql(custom_path: str | Path | None = None) -> str | None:
    """Return the absolute path to psql executable, or None if not found."""
    return find_pg_binary("psql", custom_path)


def find_pg_dump(custom_path: str | Path | None = None) -> str | None:
    """Return the absolute path to pg_dump executable, or None if not found."""
    return find_pg_binary("pg_dump", custom_path)


def find_pg_restore(custom_path: str | Path | None = None) -> str | None:
    """Return the absolute path to pg_restore executable, or None if not found."""
    return find_pg_binary("pg_restore", custom_path)
