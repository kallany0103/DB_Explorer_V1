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

    # Common Oracle root directories (shallow check to avoid slow recursive filesystem traversals)
    search_roots = [
        Path(r"C:\oracle"),
        Path(r"C:\app"),
        Path(r"C:\instantclient"),
        Path(r"C:\Program Files\Oracle"),
    ]
    for root in search_roots:
        if not root.is_dir():
            continue
        if (root / "sqlplus.exe").is_file():
            candidates.append(root)
        elif (root / "bin" / "sqlplus.exe").is_file():
            candidates.append(root / "bin")
        else:
            try:
                for sub in root.iterdir():
                    if sub.is_dir():
                        if (sub / "sqlplus.exe").is_file():
                            candidates.append(sub)
                        elif (sub / "bin" / "sqlplus.exe").is_file():
                            candidates.append(sub / "bin")
            except Exception:
                pass

    # Root drive instantclient directories (e.g. X:\Oracle instantclient, C:\instantclient_19_8)
    for drive in ("C", "D", "E", "X"):
        drive_path = Path(f"{drive}:\\")
        if drive_path.exists():
            try:
                for d in drive_path.iterdir():
                    if d.is_dir() and "instantclient" in d.name.lower():
                        if (d / "sqlplus.exe").is_file():
                            candidates.append(d)
                        elif (d / "bin" / "sqlplus.exe").is_file():
                            candidates.append(d / "bin")
            except Exception:
                pass

    return candidates


def find_sqlplus(custom_path: str | Path | None = None) -> str | None:
    """Return the path to sqlplus.exe following custom path -> PATH -> standard installs."""
    # 1. Custom user-specified setting from Preferences
    if custom_path:
        if str(custom_path).strip().lower() in ("none", "__none__"):
            return None
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
    if custom_path:
        p = Path(custom_path)
        if (p / "oci.dll").is_file():
            return str(p.resolve())
        if (p / "bin" / "oci.dll").is_file():
            return str((p / "bin").resolve())
    sqlplus = find_sqlplus(custom_path)
    if sqlplus:
        return str(Path(sqlplus).parent)
    return None


def admin_dir(custom_path: str | Path | None = None) -> str | None:
    """Return the network/admin dir (TNS_ADMIN), if it exists."""
    tns_admin = os.environ.get("TNS_ADMIN")
    if tns_admin and Path(tns_admin).is_dir():
        return tns_admin

    if custom_path:
        p = Path(custom_path)
        candidate = p / "network" / "admin"
        if candidate.is_dir():
            return str(candidate)
        candidate_parent = p.parent / "network" / "admin"
        if candidate_parent.is_dir():
            return str(candidate_parent)

    ic = instantclient_dir(custom_path)
    if ic:
        admin = Path(ic) / "network" / "admin"
        if admin.is_dir():
            return str(admin)
    return None


def get_sqlplus_candidates() -> list[dict[str, str]]:
    """Scan and return unique detected Oracle client installations on the machine.

    Each candidate dict has:
    - 'name': display name, e.g. 'Oracle Client for Microsoft Tools' or 'Oracle instantclient'
    - 'path': path to sqlplus.exe or oci.dll
    - 'dir': client directory
    """
    candidates: list[dict[str, str]] = []
    seen_dirs: set[str] = set()

    def _add(dir_path: Path | str, exe_path: Path | str, name_hint: str = "") -> None:
        try:
            resolved_dir = str(Path(dir_path).resolve())
        except Exception:
            resolved_dir = str(dir_path)
        norm_dir = resolved_dir.lower()
        if norm_dir in seen_dirs:
            return
        seen_dirs.add(norm_dir)

        p = Path(resolved_dir)
        base_name = name_hint
        if not base_name:
            if p.name.lower() in ("bin", "runtime"):
                base_name = p.parent.name or "Oracle Client"
            else:
                base_name = p.name or "Oracle Client"

        name = base_name
        existing_names = {c["name"] for c in candidates}
        if name in existing_names:
            drive = p.drive
            if drive:
                name = f"{base_name} ({drive})"
            else:
                name = f"{base_name} ({len(candidates) + 1})"

        candidates.append({"name": name, "path": str(exe_path), "dir": resolved_dir})

    # 1. Direct sqlplus executables
    which = shutil.which("sqlplus")
    if which:
        wp = Path(which).resolve()
        _add(wp.parent, wp, wp.parent.parent.name if wp.parent.name.lower() == "bin" else wp.parent.name)

    for ora_dir in _common_oracle_paths():
        found = _check_binary_in_path(ora_dir, "sqlplus")
        if found:
            fp = Path(found).resolve()
            _add(fp.parent, fp, fp.parent.parent.name if fp.parent.name.lower() == "bin" else fp.parent.name)

    return candidates
