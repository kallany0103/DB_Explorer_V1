"""User favorite/pinned table management."""

from __future__ import annotations

from typing import Set
from PySide6.QtCore import QSettings


def get_favorite_tables(conn_id: str | int) -> Set[str]:
    """Retrieves the set of pinned table names (in lowercase) for a connection."""
    settings = QSettings("UniversalSQLClient", "Favorites")
    raw = settings.value(f"favs_{conn_id}", [])
    if isinstance(raw, list):
        return {str(x).lower() for x in raw}
    return set()


def is_table_favorite(conn_id: str | int, table_name: str) -> bool:
    """Checks whether a table is in the favorites list."""
    favs = get_favorite_tables(conn_id)
    return table_name.lower() in favs


def toggle_favorite_table(conn_id: str | int, table_name: str) -> bool:
    """
    Toggles favorite status for a table.

    Returns:
        bool: True if now favorited, False if unfavorited.
    """
    settings = QSettings("UniversalSQLClient", "Favorites")
    favs = get_favorite_tables(conn_id)
    t_lower = table_name.lower()
    if t_lower in favs:
        favs.remove(t_lower)
        is_fav = False
    else:
        favs.add(t_lower)
        is_fav = True
    settings.setValue(f"favs_{conn_id}", sorted(favs))
    return is_fav
