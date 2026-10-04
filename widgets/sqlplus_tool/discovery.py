# widgets/sqlplus_tool/discovery.py
"""Locate the bundled sqlplus.exe inside resources/oracle/instantclient/."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _candidates() -> list[Path]:
    """All locations where the instantclient dir may live.

    Frozen layouts differ:
    - PyInstaller bundle: ``_MEIPASS/resources/oracle/instantclient``
    - dist run (oracle NOT in spec datas): ``<exe_dir>/resources/...``
    - Inno-installed app (iss ships oracle outside the bundle):
      ``<exe_dir>/resources/...`` while ``_MEIPASS`` is ``<exe_dir>/_internal``
    The old code returned only the ``_MEIPASS`` path, so the installed
    app never found sqlplus.exe (external cmd flashed and closed).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = Path(sys.executable).parent
        roots: list[Path] = []
        if meipass:
            roots.append(Path(meipass) / "resources" / "oracle" / "instantclient")
        roots.append(exe_dir / "resources" / "oracle" / "instantclient")
        roots.append(exe_dir / "_internal" / "resources" / "oracle" / "instantclient")
        return roots
    return [Path(__file__).parent.parent.parent / "resources" / "oracle" / "instantclient"]


def _bundled_root() -> Path:
    for root in _candidates():
        if (root / "sqlplus.exe").exists():
            return root
    # Nothing on disk — return the first candidate so callers keep a
    # deterministic path (find_* then falls back to system PATH).
    return _candidates()[0]


def find_sqlplus() -> str | None:
    """Return the path to sqlplus.exe, or None if not found."""
    for root in _candidates():
        bundled = root / "sqlplus.exe"
        if bundled.exists():
            return str(bundled)
    # Fallback: system PATH (user may have Oracle client installed globally)
    return shutil.which("sqlplus")


def instantclient_dir() -> str | None:
    """Return the instantclient directory path (needed for PATH injection)."""
    for root in _candidates():
        if (root / "sqlplus.exe").exists():
            return str(root)
    return None


def admin_dir() -> str | None:
    """Return the bundled network/admin dir (TNS_ADMIN), if it exists."""
    for root in _candidates():
        admin = root / "network" / "admin"
        if admin.is_dir():
            return str(admin)
    # Instant Client ships sqlnet.ora-less; return the conventional path
    # inside the found client dir so callers can still set TNS_ADMIN.
    ic = instantclient_dir()
    if ic:
        return os.path.join(ic, "network", "admin")
    return None
