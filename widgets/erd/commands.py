# from PyQt6.QtGui import QUndoCommand
import copy
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

class AddTableCommand(QUndoCommand):
    """Records new table creation."""
    def __init__(self, widget, table_name, columns, pos):
        super().__init__(f"Add Table {table_name}")
        self.widget = widget
        self.scene = widget.scene
        self.table_name = table_name
        self.columns = columns
        self.pos = pos
        self.item = None

    def redo(self):
        from widgets.erd.items.table_item import ERDTableItem
        if not self.item:
            self.item = ERDTableItem(self.table_name, self.columns)
            self.item.setPos(self.pos)
        
        self.scene.addItem(self.item)
        full_name = f"{self.item.schema_name or 'public'}.{self.item.table_name}"
        self.scene.tables[full_name] = self.item
        # Sync widget's schema_data
        self.widget.schema_data[full_name] = {
            "table": self.table_name,
            "schema": self.item.schema_name or 'public',
            "columns": self.columns,
            "foreign_keys": []
        }

    def undo(self):
        if self.item:
            full_name = f"{self.item.schema_name or 'public'}.{self.item.table_name}"
            if full_name in self.scene.tables:
                del self.scene.tables[full_name]
            if full_name in self.widget.schema_data:
                del self.widget.schema_data[full_name]
            self.scene.removeItem(self.item)

class AddConnectionCommand(QUndoCommand):
    """Records manual connection creation."""
    def __init__(self, widget, source_table_name, source_col, target_table_name, target_col, relation_type):
        super().__init__(f"Add Relation {source_table_name} -> {target_table_name}")
        self.widget = widget
        self.scene = widget.scene
        
        self.source_table_name = source_table_name
        self.source_col = source_col
        self.target_table_name = target_table_name
        self.target_col = target_col
        self.relation_type = relation_type
        
        self.item = None

    def redo(self):
        from widgets.erd.items.connection_item import ERDConnectionItem
        if not self.item:
            source_item = self.scene.tables.get(self.source_table_name)
            target_item = self.scene.tables.get(self.target_table_name)
            
            if not source_item or not target_item:
                return
            
            self.item = ERDConnectionItem(
                source_item, target_item,
                self.source_col, self.target_col
            )
            # Apply relation type
            self.item._apply_relation_type(self.relation_type)
            
        self.scene.addItem(self.item)
        
        # Add to endpoint tables
        if self.item not in self.item.source_item.connections:
            self.item.source_item.connections.append(self.item)
        if self.item not in self.item.target_item.connections:
            self.item.target_item.connections.append(self.item)
            
        # Sync with widget's schema_data
        if self.source_table_name in self.widget.schema_data:
            fk_list = self.widget.schema_data[self.source_table_name].setdefault("foreign_keys", [])
            # Avoid duplicates
            exists = any(fk['from'] == self.source_col and fk['table'] == self.target_table_name for fk in fk_list)
            if not exists:
                fk_list.append({
                    "from": self.source_col,
                    "table": self.target_table_name,
                    "to": self.target_col,
                    "type": self.relation_type
                })
        
        self.item.updatePath()

    def undo(self):
        if self.item:
            if self.item in self.item.source_item.connections:
                self.item.source_item.connections.remove(self.item)
            if self.item in self.item.target_item.connections:
                self.item.target_item.connections.remove(self.item)
            
            # Remove from schema_data
            if self.source_table_name in self.widget.schema_data:
                fk_list = self.widget.schema_data[self.source_table_name].get("foreign_keys", [])
                self.widget.schema_data[self.source_table_name]["foreign_keys"] = [
                    fk for fk in fk_list 
                    if not (fk['from'] == self.source_col and fk['table'] == self.target_table_name)
                ]
                
            self.scene.removeItem(self.item)

class AddColumnCommand(QUndoCommand):
    """Records adding a column to an existing table."""
    def __init__(self, widget, table_item, col_data):
        super().__init__(f"Add Column to {table_item.table_name}")
        self.widget = widget
        self.table_item = table_item
        self.col_data = col_data
        
    def redo(self):
        self.table_item.columns.append(self.col_data)
        self.table_item.update_geometry()
        self.table_item.update()
        
        # Sync widget schema_data if they are different lists
        full_name = f"{self.table_item.schema_name or 'public'}.{self.table_item.table_name}"
        if full_name in self.widget.schema_data:
            if self.widget.schema_data[full_name]["columns"] is not self.table_item.columns:
                self.widget.schema_data[full_name]["columns"].append(self.col_data)

    def undo(self):
        if self.col_data in self.table_item.columns:
            self.table_item.columns.remove(self.col_data)
            self.table_item.update_geometry()
            self.table_item.update()
            
            full_name = f"{self.table_item.schema_name or 'public'}.{self.table_item.table_name}"
            if full_name in self.widget.schema_data:
                if self.widget.schema_data[full_name]["columns"] is not self.table_item.columns:
                    if self.col_data in self.widget.schema_data[full_name]["columns"]:
                        self.widget.schema_data[full_name]["columns"].remove(self.col_data)

class UpdateTableCommand(QUndoCommand):
    """Records updating an existing table structure."""
    def __init__(self, widget, table_item, new_name, new_columns):
        super().__init__(f"Update Table {table_item.table_name}")
        self.widget = widget
        self.scene = widget.scene
        self.table_item = table_item
        
        self.old_name = table_item.table_name
        self.old_columns = copy.deepcopy(table_item.columns)
        
        self.new_name = new_name
        self.new_columns = new_columns

    def redo(self):
        self._apply(self.new_name, self.new_columns)

    def undo(self):
        self._apply(self.old_name, self.old_columns)

    def _apply(self, name, columns):
        old_full_name = f"{self.table_item.schema_name or 'public'}.{self.table_item.table_name}"
        
        # Update Item
        self.table_item.table_name = name
        self.table_item.columns = columns
        self.table_item.update_geometry()
        self.table_item.update()
        
        new_full_name = f"{self.table_item.schema_name or 'public'}.{name}"
        
        # Update Scene Registry
        if old_full_name in self.scene.tables:
            del self.scene.tables[old_full_name]
        self.scene.tables[new_full_name] = self.table_item
        
        # Update widget schema_data
        if old_full_name in self.widget.schema_data:
            data = self.widget.schema_data.pop(old_full_name)
            data["table"] = name
            data["columns"] = columns
            self.widget.schema_data[new_full_name] = data
