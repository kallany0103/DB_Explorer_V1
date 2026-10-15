# dialogs/connections/sqlite_dialog.py
"""SQLite connection dialog hosting SQLiteEngineForm."""

from __future__ import annotations

from typing import Any
from .base_connection_dialog import BaseConnectionDialog
from .engine_forms import SQLiteEngineForm


class SQLiteConnectionDialog(BaseConnectionDialog):
    """Modern standalone SQLite connection dialog hosting SQLiteEngineForm."""

    def __init__(
        self,
        parent=None,
        conn_data: dict[str, Any] | None = None,
        is_editing: bool = False,
        type_id: int | None = None,
        group_id: int | None = None,
    ) -> None:
        super().__init__(
            parent=parent,
            conn_data=conn_data,
            is_editing=is_editing,
            type_id=type_id,
            group_id=group_id,
            title="SQLite",
            subtitle="Configure connection details for your local database file.",
            min_size=(600, 420),
            form_cls=SQLiteEngineForm,
        )