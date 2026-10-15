# dialogs/connections/uds_dialog.py
"""Unified Data Source connection dialog."""

from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import QLabel
from .postgres_dialog import PostgresConnectionDialog


class UDSConnectionDialog(PostgresConnectionDialog):
    """Unified Data Source connection dialog."""

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
            title="Unified Data Source",
            subtitle="Configure Unified Data Source details and test before saving.",
        )

        form_title = self.findChild(QLabel, "formHeaderTitle")
        if form_title:
            form_title.setText("Unified Data Source")
        form_subtitle = self.findChild(QLabel, "formHeaderSubtitle")
        if form_subtitle:
            form_subtitle.setText("PostgreSQL-compatible data virtualization layer")