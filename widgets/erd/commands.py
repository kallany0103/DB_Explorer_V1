import copy
from PySide6.QtGui import QUndoCommand

from widgets.erd.model import DEFAULT_SCHEMA, full_name, normalize_entity, normalize_foreign_key


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


class ResizeItemCommand(QUndoCommand):
    """Records full geometry changes for resizable ERD items."""

    def __init__(self, item, old_state, new_state):
        item_name = getattr(item, "table_name", None) or getattr(item, "text", lambda: "Item")()
        super().__init__(f"Resize {item_name}")
        self.item = item
        self.old_state = copy.deepcopy(old_state)
        self.new_state = copy.deepcopy(new_state)

    def undo(self):
        self.item.apply_geometry_state(self.old_state)

    def redo(self):
        self.item.apply_geometry_state(self.new_state)


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
    """Records removal with full undo/redo support."""
    def __init__(self, scene, items_to_delete):
        super().__init__(f"Delete {len(items_to_delete)} Item(s)")
        self.scene = scene
        self.items_to_delete = list(items_to_delete)

    def undo(self):
        for item in self.items_to_delete:
            self.scene.addItem(item)
            if hasattr(item, "source_item") and hasattr(item, "target_item"):
                if item not in item.source_item.connections:
                    item.source_item.connections.append(item)
                if item not in item.target_item.connections:
                    item.target_item.connections.append(item)
                item.updatePath()

    def redo(self):
        for item in self.items_to_delete:
            if hasattr(item, "source_item") and hasattr(item, "target_item"):
                if item in item.source_item.connections:
                    item.source_item.connections.remove(item)
                if item in item.target_item.connections:
                    item.target_item.connections.remove(item)
            self.scene.removeItem(item)


class AddTableCommand(QUndoCommand):
    """Records new entity creation."""
    def __init__(self, widget, table_name, columns, pos, schema_name=None, foreign_keys=None, notes=None):
        super().__init__(f"Add Table {table_name}")
        self.widget = widget
        self.scene = widget.scene
        self.table_name = table_name
        self.schema_name = schema_name or DEFAULT_SCHEMA
        self.columns = copy.deepcopy(columns or [])
        self.pos = pos
        self.foreign_keys = copy.deepcopy(foreign_keys or [])
        self.notes = copy.deepcopy(notes or [])
        self.item = None

    def redo(self):
        from widgets.erd.items.table_item import ERDTableItem

        if not self.item:
            self.item = ERDTableItem(self.table_name, self.columns, schema_name=self.schema_name)
            self.item.setPos(self.pos)

        self.scene.addItem(self.item)
        entity_full_name = full_name(self.item.schema_name, self.item.table_name)
        self.scene.tables[entity_full_name] = self.item

        entity_data = normalize_entity({
            "table": self.table_name,
            "schema": self.item.schema_name or DEFAULT_SCHEMA,
            "columns": self.columns,
            "foreign_keys": self.foreign_keys,
            "notes": self.notes,
        })
        self.widget.schema_data[entity_full_name] = entity_data

        fk_cols = {fk["from"] for fk in entity_data.get("foreign_keys", []) if fk.get("from")}
        for col in self.item.columns:
            if col["name"] in fk_cols:
                col["fk"] = True
        self.item.update_geometry()
        self.item.update()

    def undo(self):
        if self.item:
            entity_full_name = full_name(self.item.schema_name, self.item.table_name)
            if entity_full_name in self.scene.tables:
                del self.scene.tables[entity_full_name]
            if entity_full_name in self.widget.schema_data:
                del self.widget.schema_data[entity_full_name]
            self.scene.removeItem(self.item)


class AddConnectionCommand(QUndoCommand):
    """Records manual connection creation."""
    def __init__(self, widget, source_table_name, source_col, target_table_name, target_col, relation_type, fk_meta=None):
        super().__init__(f"Add Relation {source_table_name} -> {target_table_name}")
        self.widget = widget
        self.scene = widget.scene

        self.source_table_name = source_table_name
        self.source_col = source_col
        self.target_table_name = target_table_name
        self.target_col = target_col
        self.relation_type = relation_type
        self.fk_meta = normalize_foreign_key(fk_meta or {})
        if not self.fk_meta.get("from"):
            self.fk_meta["from"] = source_col
        if not self.fk_meta.get("table"):
            self.fk_meta["table"] = target_table_name
        if not self.fk_meta.get("to"):
            self.fk_meta["to"] = target_col
        if not self.fk_meta.get("type"):
            self.fk_meta["type"] = relation_type

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
                self.source_col, self.target_col,
                fk_meta=self.fk_meta
            )
            self.item._apply_relation_type(self.relation_type)

        self.scene.addItem(self.item)

        if self.item not in self.item.source_item.connections:
            self.item.source_item.connections.append(self.item)
        if self.item not in self.item.target_item.connections:
            self.item.target_item.connections.append(self.item)

        if self.source_table_name in self.widget.schema_data:
            fk_list = self.widget.schema_data[self.source_table_name].setdefault("foreign_keys", [])
            exists = any(fk['from'] == self.source_col and fk['table'] == self.target_table_name for fk in fk_list)
            if not exists:
                fk_list.append(normalize_foreign_key({
                    "from": self.source_col,
                    "table": self.target_table_name,
                    "to": self.target_col,
                    "type": self.relation_type,
                    "name": self.fk_meta.get("name", f"fk_{self.source_table_name.replace('.', '_')}_{self.source_col}"),
                    "on_delete": self.fk_meta.get("on_delete", "NO ACTION"),
                    "on_update": self.fk_meta.get("on_update", "NO ACTION"),
                    "identifying": self.fk_meta.get("identifying", False),
                    "nullable": self.fk_meta.get("nullable", True),
                }))

        self.item.updatePath()

    def undo(self):
        if self.item:
            if self.item in self.item.source_item.connections:
                self.item.source_item.connections.remove(self.item)
            if self.item in self.item.target_item.connections:
                self.item.target_item.connections.remove(self.item)

            if self.source_table_name in self.widget.schema_data:
                fk_list = self.widget.schema_data[self.source_table_name].get("foreign_keys", [])
                self.widget.schema_data[self.source_table_name]["foreign_keys"] = [
                    fk for fk in fk_list
                    if not (fk['from'] == self.source_col and fk['table'] == self.target_table_name)
                ]

            self.scene.removeItem(self.item)


class DetachConnectionCommand(QUndoCommand):
    """Records detaching a connection into a floating connection."""
    def __init__(self, widget, connection_item, floating_item):
        super().__init__("Detach Relationship")
        self.widget = widget
        self.scene = widget.scene

        self.connection_item = connection_item
        self.floating_item = floating_item

        self.source_table_name = connection_item.source_item.table_name
        self.source_col = connection_item.source_col
        self.target_table_name = connection_item.target_item.table_name

    def redo(self):
        if self.connection_item in self.connection_item.source_item.connections:
            self.connection_item.source_item.connections.remove(self.connection_item)
        if self.connection_item in self.connection_item.target_item.connections:
            self.connection_item.target_item.connections.remove(self.connection_item)

        full_source = f"{self.connection_item.source_item.schema_name or DEFAULT_SCHEMA}.{self.connection_item.source_item.table_name}"
        if full_source in self.widget.schema_data:
            fk_list = self.widget.schema_data[full_source].get("foreign_keys", [])
            self.widget.schema_data[full_source]["foreign_keys"] = [
                fk for fk in fk_list
                if not (fk['from'] == self.source_col and fk['table'] == self.target_table_name)
            ]

        self.scene.removeItem(self.connection_item)
        self.scene.addItem(self.floating_item)

    def undo(self):
        self.scene.removeItem(self.floating_item)
        self.scene.addItem(self.connection_item)

        if self.connection_item not in self.connection_item.source_item.connections:
            self.connection_item.source_item.connections.append(self.connection_item)
        if self.connection_item not in self.connection_item.target_item.connections:
            self.connection_item.target_item.connections.append(self.connection_item)

        full_source = f"{self.connection_item.source_item.schema_name or DEFAULT_SCHEMA}.{self.connection_item.source_item.table_name}"
        if full_source in self.widget.schema_data:
            fk_list = self.widget.schema_data[full_source].setdefault("foreign_keys", [])
            exists = any(fk['from'] == self.source_col and fk['table'] == self.target_table_name for fk in fk_list)
            if not exists:
                fk_list.append(normalize_foreign_key({
                    "from": self.source_col,
                    "table": self.target_table_name,
                    "to": self.connection_item.target_col,
                    "type": self.connection_item.relation_type,
                }))
        self.connection_item.updatePath()


class AddNoteCommand(QUndoCommand):
    """Records adding a diagram note."""
    def __init__(self, widget, note_text, pos):
        super().__init__("Add Note")
        self.widget = widget
        self.scene = widget.scene
        self.note_text = note_text
        self.pos = pos
        self.item = None

    def redo(self):
        from widgets.erd.items.note_item import ERDNoteItem

        if not self.item:
            self.item = ERDNoteItem(self.note_text)
            self.item.setPos(self.pos)
        self.scene.addItem(self.item)

    def undo(self):
        if self.item:
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

        entity_full_name = full_name(self.table_item.schema_name, self.table_item.table_name)
        if entity_full_name in self.widget.schema_data:
            if self.widget.schema_data[entity_full_name]["columns"] is not self.table_item.columns:
                self.widget.schema_data[entity_full_name]["columns"].append(self.col_data)

    def undo(self):
        if self.col_data in self.table_item.columns:
            self.table_item.columns.remove(self.col_data)
            self.table_item.update_geometry()
            self.table_item.update()

            entity_full_name = full_name(self.table_item.schema_name, self.table_item.table_name)
            if entity_full_name in self.widget.schema_data:
                if self.widget.schema_data[entity_full_name]["columns"] is not self.table_item.columns:
                    if self.col_data in self.widget.schema_data[entity_full_name]["columns"]:
                        self.widget.schema_data[entity_full_name]["columns"].remove(self.col_data)


class UpdateTableCommand(QUndoCommand):
    """Records updating an existing table structure."""
    def __init__(self, widget, table_item, new_name, new_columns, foreign_keys=None, notes=None):
        super().__init__(f"Update Table {table_item.table_name}")
        self.widget = widget
        self.scene = widget.scene
        self.table_item = table_item

        self.old_name = table_item.table_name
        self.old_schema_name = table_item.schema_name
        self.old_columns = copy.deepcopy(table_item.columns)
        old_full_name = full_name(table_item.schema_name, table_item.table_name)
        old_data = self.widget.schema_data.get(old_full_name, {})
        self.old_foreign_keys = copy.deepcopy(old_data.get("foreign_keys", []))
        self.old_notes = copy.deepcopy(old_data.get("notes", []))

        self.new_name = new_name
        self.new_columns = copy.deepcopy(new_columns or [])
        self.new_foreign_keys = copy.deepcopy(foreign_keys if foreign_keys is not None else self.old_foreign_keys)
        self.new_notes = copy.deepcopy(notes if notes is not None else self.old_notes)

    def redo(self):
        self._apply(self.new_name, self.new_columns, self.new_foreign_keys, self.new_notes, self.table_item.schema_name)

    def undo(self):
        self._apply(self.old_name, self.old_columns, self.old_foreign_keys, self.old_notes, self.old_schema_name)

    def _apply(self, name, columns, foreign_keys, notes, schema_name):
        old_full_name = full_name(self.table_item.schema_name, self.table_item.table_name)

        self.table_item.table_name = name
        self.table_item.schema_name = schema_name
        self.table_item.columns = columns
        self.table_item.update_geometry()
        self.table_item.update()

        new_full_name = full_name(self.table_item.schema_name, name)

        if old_full_name in self.scene.tables:
            del self.scene.tables[old_full_name]
        self.scene.tables[new_full_name] = self.table_item

        if old_full_name in self.widget.schema_data:
            data = self.widget.schema_data.pop(old_full_name)
            data["table"] = name
            data["schema"] = self.table_item.schema_name or DEFAULT_SCHEMA
            data["columns"] = columns
            data["foreign_keys"] = copy.deepcopy(foreign_keys)
            data["notes"] = copy.deepcopy(notes)
            self.widget.schema_data[new_full_name] = data
