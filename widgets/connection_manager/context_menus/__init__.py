# widgets/connection_manager/context_menus/__init__.py
"""Context menu package.

The public API is unchanged: ContextMenuHandler with
  .show_context_menu(pos)       — Object Explorer tree
  .show_schema_context_menu(pos) — Schema tree

Internally the logic is split into:
  _helpers.py        — shared action / submenu factory helpers
  explorer_menus.py  — ExplorerMenuBuilder (Object Explorer tree)
  schema_menus.py    — SchemaMenuBuilder   (Schema tree)
"""

from widgets.connection_manager.context_menus.explorer_menus import ExplorerMenuBuilder
from widgets.connection_manager.context_menus.schema_menus import SchemaMenuBuilder


class ContextMenuHandler:
    """Thin facade that wires ExplorerMenuBuilder and SchemaMenuBuilder to the manager."""

    def __init__(self, manager):
        self.manager = manager
        self._explorer = ExplorerMenuBuilder(manager)
        self._schema   = SchemaMenuBuilder(manager)

    def show_context_menu(self, pos):
        """Right-click menu for the Object Explorer tree."""
        self._explorer.show(pos)

    def show_schema_context_menu(self, position):
        """Right-click menu for the Schema tree."""
        self._schema.show(position)
