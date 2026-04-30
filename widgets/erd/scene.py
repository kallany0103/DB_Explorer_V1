import math
from PySide6.QtWidgets import QGraphicsScene, QDialog
from PySide6.QtGui import QBrush, QColor, QPen, QTransform
from PySide6.QtCore import QLineF, Qt

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem
from widgets.erd.items.note_item import ERDNoteItem
from widgets.erd.items.entity_item import ERDEntityItem
from widgets.erd.items.weak_entity_item import ERDWeakEntityItem
from widgets.erd.items.attribute_item import ERDAttributeItem
from widgets.erd.items.relationship_diamond_item import ERDRelationshipDiamondItem
from widgets.erd.items.subject_area_item import ERDSubjectAreaItem
from widgets.erd.items.floating_connection import ERDFloatingConnectionItem, ConnectionHandle
from widgets.erd.items.resizable import item_visual_scene_rect
from widgets.erd.routing import ERDRouter
from widgets.erd.commands import DeleteItemCommand, UpdateTableCommand

# All non-table items that can be deleted with the Delete key
_DELETABLE_TYPES = (
    ERDTableItem, ERDConnectionItem, ERDNoteItem,
    ERDEntityItem, ERDWeakEntityItem, ERDAttributeItem,
    ERDRelationshipDiamondItem, ERDSubjectAreaItem,
    ERDFloatingConnectionItem, ConnectionHandle,
)

_ROUTING_OBSTACLE_TYPES = (
    ERDTableItem, ERDNoteItem, ERDEntityItem, ERDWeakEntityItem,
    ERDAttributeItem, ERDRelationshipDiamondItem, ERDSubjectAreaItem,
)

class ERDScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#F8F9FA")))
        self.tables = {}
        self.setSceneRect(0, 0, 2000, 2000)
        self.alignment_lines = []
        self._router_cache = None
        
    def update_scene_rect(self):
        # Calculate the bounding box of all items and add a 500px margin
        rect = self.itemsBoundingRect()
        if not rect.isNull():
            margin = 500
            self.setSceneRect(rect.adjusted(-margin, -margin, margin, margin))
            self._router_cache = None 
            
    def get_router(self):
        if self._router_cache is None:  
            obstacles = []
            for item in self.items():
                if isinstance(item, _ROUTING_OBSTACLE_TYPES):
                    obstacles.append(item_visual_scene_rect(item))
            self._router_cache = ERDRouter(self.sceneRect(), obstacles)
        return self._router_cache

    def update_alignment_guides(self):
        self.update() 

    def delete_selected_items(self):
        items_to_delete = []
        for item in self.selectedItems():
            if isinstance(item, _DELETABLE_TYPES):
                items_to_delete.append(item)
                
        if items_to_delete and hasattr(self, 'undo_stack'):  
            cmd = DeleteItemCommand(self, items_to_delete)
            self.undo_stack.push(cmd)


    def highlight_related(self, table_item):
        for item in self.items():
            if isinstance(item, ERDTableItem):
                item.is_highlighted = item == table_item
                item.update()
        self.update()

    def clear_highlight(self):
        for item in self.items():
            if isinstance(item, ERDTableItem):
                item.is_highlighted = False
                item.update()
        self.update()

    def apply_search_filter(self, text):
        text = text.strip().lower()
        for item in self.items():
            if isinstance(item, ERDTableItem):
                if not text:
                    item.is_dimmed = False
                else:
                    match_name = text in item.table_name.lower()
                    match_schema = item.schema_name and text in item.schema_name.lower()
                    item.is_dimmed = not (match_name or match_schema)
                item.update()

    def find_table_item(self, text):
        text = text.strip().lower()
        if not text:
            return None
        
        candidates = []
        for item in self.items():
            if isinstance(item, ERDTableItem):
                name = item.table_name.lower()
                if name == text:
                    return item 
                if name.startswith(text):
                    candidates.insert(0, item)
                elif text in name:
                    candidates.append(item)
        
        return candidates[0] if candidates else None
        
    def drawBackground(self, painter, rect):
        if not painter.isActive():
            return
        painter.fillRect(rect, QBrush(QColor("#F8F9FA")))
        if rect.width() < 500: 
            return

        grid_size = 20
        left = math.floor(rect.left() / grid_size) * grid_size
        top = math.floor(rect.top() / grid_size) * grid_size
        right = rect.right()
        bottom = rect.bottom()
        
        pen = QPen(QColor("#E0E0E0"), 0) 
        painter.setPen(pen)
        
        lines = []
        x = float(left)
        while x <= right:
            lines.append(QLineF(x, top, x, bottom))
            x += grid_size
            
        y = float(top)
        while y <= bottom:
            lines.append(QLineF(left, y, right, y))
            y += grid_size
            
        if lines:
            painter.drawLines(lines)

    def drawForeground(self, painter, rect):
        if not painter.isActive() or not self.alignment_lines:
            return
            
        pen = QPen(QColor(26, 115, 232, 180)) 
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        adjusted_lines = []
        for line in self.alignment_lines:
            if abs(line.x1() - line.x2()) < 0.1:
                adjusted_lines.append(QLineF(line.x1(), rect.top(), line.x2(), rect.bottom()))
            elif abs(line.y1() - line.y2()) < 0.1:
                adjusted_lines.append(QLineF(rect.left(), line.y1(), rect.right(), line.y2()))
        
        if adjusted_lines:
            painter.drawLines(adjusted_lines)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, ERDTableItem):
            from widgets.erd.dialogs import TableDesignerDialog
            widget = self.parent() 
            dialog = TableDesignerDialog(
                widget,
                item.table_name,
                item.columns,
                schema_name=item.schema_name or "public",
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_name, new_cols = dialog.get_result()
                cmd = UpdateTableCommand(
                    widget,
                    item,
                    new_name,
                    new_cols,
                )
                widget.undo_stack.push(cmd)
        
        super().mouseDoubleClickEvent(event)

    def start_connection(self, source_table_name, source_col_name, start_scene_pos):
        self._temp_conn_start = (source_table_name, source_col_name)
        self._temp_line = self.addLine(QLineF(start_scene_pos, start_scene_pos), QPen(QColor("#1A73E8"), 2, Qt.PenStyle.DashLine))

    def update_connection_drag(self, scene_pos):
        if hasattr(self, '_temp_line') and self._temp_line:
            line = self._temp_line.line()
            line.setP2(scene_pos)
            self._temp_line.setLine(line)

            # Clear previous drag highlights
            for item in self.items():
                if isinstance(item, ERDTableItem):
                    if hasattr(item, '_drag_highlighted_col') and item._drag_highlighted_col:
                        if item._drag_highlighted_col in item.highlighted_cols:
                            item.highlighted_cols.remove(item._drag_highlighted_col)
                        item._drag_highlighted_col = None
                        item.update()
            
            # Find table item under cursor and highlight column
            items_under = self.items(scene_pos)
            target_table_item = next((it for it in items_under if isinstance(it, ERDTableItem)), None)
            
            if target_table_item and target_table_item.show_columns:
                local_pos = target_table_item.mapFromScene(scene_pos)
                if local_pos.y() >= target_table_item.header_height:
                    idx = int((local_pos.y() - target_table_item.header_height) // target_table_item.row_height)
                    if 0 <= idx < len(target_table_item.columns):
                        target_col = target_table_item.columns[idx]['name']
                        target_table_item.highlighted_cols.add(target_col)
                        target_table_item._drag_highlighted_col = target_col
                        target_table_item.update()

    def finish_connection_drag(self, scene_pos):
        if hasattr(self, '_temp_line') and self._temp_line:
            self.removeItem(self._temp_line)
            source_table_name, source_col_name = self._temp_conn_start
            self._temp_line = None
            self._temp_conn_start = None

            # Clean up drag highlighting
            for table_item in self.items():
                if isinstance(table_item, ERDTableItem) and getattr(table_item, '_drag_highlighted_col', None):
                    if table_item._drag_highlighted_col in table_item.highlighted_cols:
                        table_item.highlighted_cols.remove(table_item._drag_highlighted_col)
                    table_item._drag_highlighted_col = None
                    table_item.update()

            item = self.itemAt(scene_pos, QTransform())
            if isinstance(item, ERDTableItem):
                local_pos = item.mapFromScene(scene_pos)
                target_col = None
                if item.show_columns and local_pos.y() >= item.header_height:
                    idx = int((local_pos.y() - item.header_height) // item.row_height)
                    if 0 <= idx < len(item.columns):
                        target_col = item.columns[idx]['name']
                
                target_full_name = f"{item.schema_name or 'public'}.{item.table_name}"
                if target_col and (target_full_name != source_table_name or target_col != source_col_name):
                    from widgets.erd.commands import AddConnectionCommand
                    widget = self.parent()
                    cmd = AddConnectionCommand(widget, source_table_name, source_col_name, target_full_name, target_col, "many-to-one")
                    if hasattr(self, 'undo_stack'):
                        self.undo_stack.push(cmd)

    def mouseMoveEvent(self, event):
        self.update_connection_drag(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.finish_connection_drag(event.scenePos())
        super().mouseReleaseEvent(event)
