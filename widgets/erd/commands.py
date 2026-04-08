# from PyQt6.QtGui import QUndoCommand
from PySide6.QtGui import QUndoCommand

class MoveTableCommand(QUndoCommand):
    """Records table position before/after drag."""
    def __init__(self, table_item, old_pos, new_pos):
        super().__init__(f"Move Table {table_item.table_name}")
        self.item = table_item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.item.setPos(self.old_pos)

    def redo(self):
        self.item.setPos(self.new_pos)

class ChangeRelationTypeCommand(QUndoCommand):
    """Records connection type before/after change."""
    def __init__(self, connection_item, old_type, new_type):
        super().__init__("Change Relationship Type")
        self.item = connection_item
        self.old_type = old_type
        self.new_type = new_type

    def undo(self):
        self.item._apply_relation_type(self.old_type)

    def redo(self):
        self.item._apply_relation_type(self.new_type)

class DeleteItemCommand(QUndoCommand):
    """Records connection removal + re-insertion with full undo/redo support.

    Qt's undo framework calls redo() immediately when the command is pushed onto
    the stack, so the actual scene removal happens inside redo(), not __init__.
    undo() reverses that by re-adding each connection and restoring the endpoint
    table's .connections lists so hover-highlights and routing continue to work.
    """
    def __init__(self, scene, items_to_delete):
        super().__init__(f"Delete {len(items_to_delete)} Connection(s)")
        self.scene = scene
        # Take a snapshot — the list passed in may be mutated by the caller.
        self.items_to_delete = list(items_to_delete)

    def undo(self):
        """Re-add all deleted connections back to the scene."""
        for item in self.items_to_delete:
            self.scene.addItem(item)
            # Restore this connection in both endpoint tables' lists so that
            # hover-highlight and anchor/routing logic work correctly.
            if item not in item.source_item.connections:
                item.source_item.connections.append(item)
            if item not in item.target_item.connections:
                item.target_item.connections.append(item)
            # Force the path to redraw from current table positions.
            item.updatePath()

    def redo(self):
        """Remove all connections from the scene."""
        for item in self.items_to_delete:
            # Clean up endpoint table connection lists first.
            if item in item.source_item.connections:
                item.source_item.connections.remove(item)
            if item in item.target_item.connections:
                item.target_item.connections.remove(item)
            self.scene.removeItem(item)
