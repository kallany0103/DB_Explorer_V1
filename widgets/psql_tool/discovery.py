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
from typing import Any


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
        if str(custom_path).strip().lower() in ("none", "__none__"):
            return None
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


def get_psql_candidates() -> list[dict[str, str]]:
    """Scan and return unique detected psql installations on the machine.

    Each candidate dict has:
    - 'name': display name, e.g. 'pgAdmin 4' or 'PostgreSQL 16'
    - 'path': path to psql.exe
    - 'dir': directory containing psql.exe
    """
    candidates: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    def _determine_name(resolved_path: str, hint: str = "") -> str:
        if hint:
            return hint
        p = Path(resolved_path)
        parts = p.parts
        p_low = resolved_path.lower()
        if "pgadmin" in p_low:
            return "pgAdmin 4"
        for i, part in enumerate(parts):
            if part.lower() == "postgresql" and i + 1 < len(parts) and parts[i + 1].isdigit():
                return f"PostgreSQL {parts[i + 1]}"
        parent = p.parent
        install_dir = parent.parent if parent.name.lower() in ("bin", "runtime") else parent
        if install_dir.name:
            return install_dir.name
        return "System PATH"

    def _add(path_str: str, name_hint: str = "") -> None:
        try:
            resolved = str(Path(path_str).resolve())
        except Exception:
            resolved = str(path_str)
        if resolved.lower() in seen_paths:
            return
        seen_paths.add(resolved.lower())
        base_name = _determine_name(resolved, name_hint)
        name = base_name
        existing_names = {c["name"] for c in candidates}
        if name in existing_names:
            drive = Path(resolved).drive
            if drive:
                name = f"{base_name} ({drive})"
            else:
                name = f"{base_name} ({len(candidates) + 1})"
        candidates.append({"name": name, "path": resolved, "dir": str(Path(resolved).parent)})

    which = shutil.which("psql")
    if which:
        _add(which)

    for pg_dir in _common_pg_paths():
        found = _check_binary_in_path(pg_dir, "psql")
        if found:
            _add(found)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        pa = Path(local_app_data) / "Programs" / "pgAdmin 4" / "runtime" / "psql.exe"
        if pa.is_file():
            _add(str(pa), "pgAdmin 4")

    for prog in [
        Path(r"C:\Program Files\pgAdmin 4\runtime\psql.exe"),
        Path(r"C:\Program Files (x86)\pgAdmin 4\runtime\psql.exe"),
    ]:
        if prog.is_file():
            _add(str(prog), "pgAdmin 4")

    return candidates


def get_all_postgres_candidates() -> list[dict[str, Any]]:
    """Scan and return all detected PostgreSQL client candidates across Windows and WSL."""
    candidates = get_psql_candidates()
    for c in candidates:
        c["kind"] = "windows"

    try:
        from widgets.psql_tool.wsl_discovery import get_wsl_distributions, check_wsl_postgres
        distros = get_wsl_distributions()
        has_any_wsl_pg = False
        wsl_candidates: list[dict[str, Any]] = []

        for d in distros:
            info = check_wsl_postgres(d["name"])
            if info.get("available"):
                has_any_wsl_pg = True
                wsl_candidates.append({
                    "name": f"WSL: {d['name']}",
                    "path": info.get("path") or "/usr/bin/psql",
                    "dir": f"wsl:{d['name']}",
                    "kind": "wsl",
                    "distro": d["name"],
                    "version": info.get("version", ""),
                    "available": True,
                })

        # If WSL exists but no distro has psql, show the default distro as not installed
        if not has_any_wsl_pg and distros:
            default_distro = next((d for d in distros if d.get("is_default")), distros[0])
            wsl_candidates.append({
                "name": f"WSL: {default_distro['name']} (psql not installed)",
                "path": "",
                "dir": f"wsl:{default_distro['name']}",
                "kind": "wsl",
                "distro": default_distro["name"],
                "version": "",
                "available": False,
            })

        candidates.extend(wsl_candidates)
    except Exception:
        pass

    return candidates
