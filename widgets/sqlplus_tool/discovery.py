# widgets/sqlplus_tool/discovery.py
"""Locate the bundled sqlplus.exe inside resources/oracle/instantclient/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _bundled_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "resources" / "oracle" / "instantclient"
        return Path(sys.executable).parent / "resources" / "oracle" / "instantclient"
    return Path(__file__).parent.parent.parent / "resources" / "oracle" / "instantclient"


def find_sqlplus() -> str | None:
    """Return the path to sqlplus.exe, or None if not found."""
    bundled = _bundled_root() / "sqlplus.exe"
    if bundled.exists():
        return str(bundled)
    # Fallback: system PATH (user may have Oracle client installed globally)
    return shutil.which("sqlplus")


def instantclient_dir() -> str | None:
    """Return the instantclient directory path (needed for PATH injection)."""
    bundled = _bundled_root()
    if (bundled / "sqlplus.exe").exists():
        return str(bundled)
    return None
