# dialogs/connections/postgres_dialog.py
"""PostgreSQL database connection dialog hosting PostgresEngineForm."""

from __future__ import annotations

from typing import Any
from .base_connection_dialog import BaseConnectionDialog
from .engine_forms import PostgresEngineForm


class PostgresConnectionDialog(BaseConnectionDialog):
    """Modern standalone PostgreSQL connection dialog hosting PostgresEngineForm."""

    def __init__(
        self,
        parent=None,
        conn_data: dict[str, Any] | None = None,
        is_editing: bool = False,
        type_id: int | None = None,
        group_id: int | None = None,
        title: str = "PostgreSQL",
        subtitle: str = "Configure PostgreSQL connection details and test before saving.",
        form_cls: Any = None,
    ) -> None:
        super().__init__(
            parent=parent,
            conn_data=conn_data,
            is_editing=is_editing,
            type_id=type_id,
            group_id=group_id,
            title=title,
            subtitle=subtitle,
            min_size=(620, 520),
            form_cls=form_cls or PostgresEngineForm,
        )