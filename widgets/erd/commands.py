from PyQt6.QtGui import QUndoCommand

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
        self.item.relation_type = self.old_type
        self._update_item()

    def redo(self):
        self.item.relation_type = self.new_type
        self._update_item()

    def _update_item(self):
        rel_info = self.item.RELATION_TYPES[self.item.relation_type]
        self.item.cardinality_label = rel_info['label']
        self.item.tooltip_text = (
            f"<b>{self.item.cardinality_label}</b><br/>"
            f"<code>{self.item.source_item.table_name}.{self.item.source_col}</code> → "
            f"<code>{self.item.target_item.table_name}.{self.item.target_col}</code>"
        )
        self.item.setToolTip(self.item.tooltip_text)
        self.item.is_unique = self.item.relation_type in ('one-to-one',)
        self.item.prepareGeometryChange()
        self.item.update()

class DeleteItemCommand(QUndoCommand):
    """Records item removal + re-insertion."""
    def __init__(self, scene, items_to_delete):
        super().__init__("Delete Items")
        self.scene = scene
        self.items_to_delete = items_to_delete
        self.connections = [] # We need to handle connections properly if deleting tables
        
    def undo(self):
        pass

    def redo(self):
        pass
