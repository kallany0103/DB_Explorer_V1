# dialogs/connections/servicenow_dialog.py
"""ServiceNow connection dialog hosting ServiceNowEngineForm."""

from __future__ import annotations

from typing import Any
from .base_connection_dialog import BaseConnectionDialog
from .engine_forms import ServiceNowEngineForm


class ServiceNowConnectionDialog(BaseConnectionDialog):
    """Modern standalone ServiceNow connection dialog hosting ServiceNowEngineForm."""

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
            title="ServiceNow",
            subtitle="Import data from ServiceNow instance via REST / OAuth.",
            min_size=(620, 500),
            form_cls=ServiceNowEngineForm,
        )