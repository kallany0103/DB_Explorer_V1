import shutil
from pathlib import Path

def _bundled_root() -> Path:
    return Path(__file__).parent.parent.parent / "resources" / "pg_client"

def find_psql() -> str | None:
    # 1. Bundled binary (primary)
    bundled = _bundled_root() / "win64" / "psql.exe"
    if bundled.exists():
        return str(bundled)
    
    # 2. System PATH (dev machine fallback)
    return shutil.which("psql")

def find_pg_dump() -> str | None:
    bundled = _bundled_root() / "win64" / "pg_dump.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("pg_dump")
