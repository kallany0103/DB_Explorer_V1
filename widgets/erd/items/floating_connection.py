import math
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsItem, QGraphicsSceneMouseEvent
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath
from PySide6.QtCore import Qt, QPointF

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem

class ConnectionHandle(QGraphicsEllipseItem):
    def __init__(self, parent, is_start_handle=True):
        # Center the ellipse on its coordinate
        super().__init__(-6, -6, 12, 12, parent)
        self.parent_conn = parent
        self.is_start_handle = is_start_handle
        
        self.setBrush(QBrush(QColor("#1A73E8")))
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        self.anchored_table = None
        self.anchored_col = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.parent_conn.updatePath()
            self._update_hover_highlight(self.scenePos())
        return super().itemChange(change, value)

    def _update_hover_highlight(self, scene_pos):
        if not self.scene():
            return
            
        # Clean previous highlights
        for item in self.scene().items():
            if isinstance(item, ERDTableItem):
                if hasattr(item, '_drag_highlighted_col') and item._drag_highlighted_col:
                    if item._drag_highlighted_col in item.highlighted_cols:
                        item.highlighted_cols.remove(item._drag_highlighted_col)
                    item._drag_highlighted_col = None
                    item.update()
        
        # Highlight new one
        items_under = self.scene().items(scene_pos)
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

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        super().mouseReleaseEvent(event)
        if not self.scene():
            return
            
        scene_pos = self.scenePos()
        items_under = self.scene().items(scene_pos)
        target_table_item = next((it for it in items_under if isinstance(it, ERDTableItem)), None)
        
        self.anchored_table = None
        self.anchored_col = None
        
        if target_table_item:
            self.anchored_table = f"{target_table_item.schema_name or 'public'}.{target_table_item.table_name}"
            
            local_pos = target_table_item.mapFromScene(scene_pos)
            if target_table_item.show_columns and local_pos.y() >= target_table_item.header_height:
                idx = int((local_pos.y() - target_table_item.header_height) // target_table_item.row_height)
                if 0 <= idx < len(target_table_item.columns):
                    self.anchored_col = target_table_item.columns[idx]['name']
                    # Snap to anchor
                    snap_pos = target_table_item.get_column_anchor_pos(self.anchored_col, "left")
                    if local_pos.x() > target_table_item.width / 2:
                        snap_pos = target_table_item.get_column_anchor_pos(self.anchored_col, "right")
                    self.setPos(self.parent_conn.mapFromScene(snap_pos))
                else:
                    self.setPos(self.parent_conn.mapFromScene(target_table_item.get_column_anchor_pos(None, "left" if local_pos.x() < target_table_item.width/2 else "right")))
            else:
                # Snap to table itself
                self.setPos(self.parent_conn.mapFromScene(target_table_item.get_column_anchor_pos(None, "left" if local_pos.x() < target_table_item.width/2 else "right")))

        # Clean drag highlighting
        for item in self.scene().items():
            if isinstance(item, ERDTableItem):
                if hasattr(item, '_drag_highlighted_col') and item._drag_highlighted_col:
                    if item._drag_highlighted_col in item.highlighted_cols:
                        item.highlighted_cols.remove(item._drag_highlighted_col)
                    item._drag_highlighted_col = None
                    item.update()

        # Check if both handles are anchored
        self.parent_conn.check_anchors()

class ERDFloatingConnectionItem(QGraphicsPathItem):
    def __init__(self, relation_type):
        super().__init__()
        self.relation_type = relation_type
        
        pen = QPen(QColor("#1A73E8"), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.setZValue(9)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        self.start_handle = ConnectionHandle(self, is_start_handle=True)
        self.end_handle = ConnectionHandle(self, is_start_handle=False)
        
    def set_handles(self, p1, p2):
        self.start_handle.setPos(p1)
        self.end_handle.setPos(p2)
        self.updatePath()
        
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # Emulate dropping handles individually to see if they landed on valid anchors
        self.start_handle.mouseReleaseEvent(event)
        self.end_handle.mouseReleaseEvent(event)
        
    def updatePath(self):
        p1 = self.start_handle.pos()
        p2 = self.end_handle.pos()
        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        self.setPath(path)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        path = self.path()
        if path.elementCount() < 2:
            return
            
        # Draw crow's feet using ERDConnectionItem's helper
        # We need a temporary stand-in to reuse the drawing logic
        class DummyConn:
            RELATION_TYPES = ERDConnectionItem.RELATION_TYPES
        
        rel_info = DummyConn.RELATION_TYPES.get(self.relation_type, DummyConn.RELATION_TYPES['many-to-one'])
        source_type = rel_info.get('source', 'many')
        target_type = rel_info.get('target', 'one')
        
        p0 = path.elementAt(0)
        p1 = path.elementAt(path.elementCount() - 1)
        dx_s, dy_s = p1.x - p0.x, p1.y - p0.y
        dx_t, dy_t = p0.x - p1.x, p0.y - p1.y
        
        # Re-implement the draw logic directly to avoid messy dependencies
        self._draw_crows_foot(painter, QPointF(p0.x, p0.y), dx_s, dy_s, source_type)
        self._draw_crows_foot(painter, QPointF(p1.x, p1.y), dx_t, dy_t, target_type)

    def _draw_crows_foot(self, painter, P, dx, dy, rel_part):
        length = math.hypot(dx, dy)
        if length < 1e-5: 
            return
        
        nx, ny = dx / length, dy / length
        px, py = -ny, nx
        
        pen = QPen(QColor("#1A73E8"))
        pen.setWidthF(1.7)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        
        def draw_bar(offset):
            c = QPointF(P.x() + nx * offset, P.y() + ny * offset)
            p1 = QPointF(c.x() + px * 6, c.y() + py * 6)
            p2 = QPointF(c.x() - px * 6, c.y() - py * 6)
            painter.drawLine(p1, p2)
            
        def draw_circle(offset):
            c = QPointF(P.x() + nx * offset, P.y() + ny * offset)
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            painter.drawEllipse(c, 3.5, 3.5)
            painter.setBrush(Qt.GlobalColor.transparent)
            
        def draw_crows_foot(start_offset, spread_offset, spread_width):
            start = QPointF(P.x() + nx * start_offset, P.y() + ny * start_offset)
            end_center = QPointF(P.x() + nx * spread_offset, P.y() + ny * spread_offset)
            p1 = QPointF(end_center.x() + px * spread_width, end_center.y() + py * spread_width)
            p2 = QPointF(end_center.x() - px * spread_width, end_center.y() - py * spread_width)
            painter.drawLine(start, p1)
            painter.drawLine(start, p2)

        if rel_part == 'one':
            draw_bar(5)
            draw_bar(13)
        elif rel_part == 'many':
            draw_crows_foot(0, 12, 6)
            draw_bar(13)
        elif rel_part == 'zero_or_one':
            draw_bar(5)
            draw_circle(14)
        elif rel_part == 'zero_or_many':
            draw_crows_foot(0, 12, 6)
            draw_circle(16)

    def check_anchors(self):
        if self.start_handle.anchored_table and self.end_handle.anchored_table:
            # Prevent self-loop on the SAME COLUMN
            if self.start_handle.anchored_table == self.end_handle.anchored_table and self.start_handle.anchored_col == self.end_handle.anchored_col:
                return

            from widgets.erd.commands import AddConnectionCommand
            scene = self.scene()
            if not scene:
                return
            
            widget = scene.parent()
            
            cmd = AddConnectionCommand(
                widget, 
                self.start_handle.anchored_table, 
                self.start_handle.anchored_col, 
                self.end_handle.anchored_table, 
                self.end_handle.anchored_col, 
                self.relation_type
            )
            
            # Remove self
            scene.removeItem(self)
            
            if hasattr(scene, 'undo_stack'):
                scene.undo_stack.push(cmd)
