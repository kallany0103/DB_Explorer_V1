# dialogs/connections/csv_dialog.py
"""CSV connection dialog hosting CSVEngineForm."""

from __future__ import annotations

from typing import Any
from .base_connection_dialog import BaseConnectionDialog
from .engine_forms import CSVEngineForm


class CSVConnectionDialog(BaseConnectionDialog):
    """Modern standalone CSV connection dialog hosting CSVEngineForm."""

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
            title="CSV",
            subtitle="Configure local folder containing CSV, TSV or flat files.",
            min_size=(600, 420),
            form_cls=CSVEngineForm,
        )