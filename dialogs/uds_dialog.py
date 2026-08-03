from dialogs.postgres_dialog import PostgresConnectionDialog
from PySide6.QtWidgets import QLabel

class UDSConnectionDialog(PostgresConnectionDialog):

    def __init__(self,
                 parent=None,
                 is_editing=False,
                 type_id=None,
                 group_id=None):

        super().__init__(
            parent=parent,
            is_editing=is_editing,
            type_id=type_id,
            group_id=group_id
        )

        self.setWindowTitle(
            "Edit Unified Data Source"
            if is_editing
            else
            "New Unified Data Source"
        )

        self.findChild(QLabel, "dialogTitle").setText(
            "Unified Data Source"
        )

        self.findChild(QLabel, "dialogSubtitle").setText(
            "Configure Unified Data Source details and test before saving."
        )