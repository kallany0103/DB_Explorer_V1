# dialogs/connections/oracle_dialog.py
"""Oracle database connection dialog hosting OracleEngineForm."""

from __future__ import annotations

from typing import Any
from .base_connection_dialog import BaseConnectionDialog
from .engine_forms import OracleEngineForm


class OracleConnectionDialog(BaseConnectionDialog):
    """Modern standalone Oracle connection dialog hosting OracleEngineForm."""

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
            title="Oracle",
            subtitle="Configure Oracle connection using Basic (Service/SID), TNS, or Custom DSN.",
            min_size=(640, 560),
            form_cls=OracleEngineForm,
        )

    def get_effective_dsn(self) -> str:
        if hasattr(self, "engine_form") and hasattr(self.engine_form, "get_effective_dsn"):
            return self.engine_form.get_effective_dsn()
        return ""