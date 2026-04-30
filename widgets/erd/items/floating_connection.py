import math
from PySide6.QtWidgets import QApplication, QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsItem, QGraphicsSceneMouseEvent, QMenu
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath
from PySide6.QtCore import Qt, QPointF

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.constants import RELATION_TYPES


def arm_port_drag(item, scene_pos, *, col=None, relation_type="none"):
    """Record a pending port-drag intent on ``item``.

    No floating connection is created yet; the connection is only spawned
    if the cursor later moves past the platform drag threshold (see
    ``maybe_start_port_drag``). This prevents a plain click on a port from
    instantly producing a dangling connection line.
    """
    item._pending_port_drag = {
        "scene_pos": QPointF(scene_pos),
        "col": col,
        "relation_type": relation_type,
    }


def maybe_start_port_drag(item, current_scene_pos):
    """Promote a pending port drag into a real floating connection once the
    cursor has moved past ``QApplication.startDragDistance()`` (~4 px).

    Returns the new ``ERDFloatingConnectionItem`` if started, else ``None``.
    """
    info = getattr(item, "_pending_port_drag", None)
    if not info or item.scene() is None:
        return None
    if (current_scene_pos - info["scene_pos"]).manhattanLength() < QApplication.startDragDistance():
        return None

    floating = ERDFloatingConnectionItem(info["relation_type"])
    item.scene().addItem(floating)
    floating.start_handle.anchored_item = item
    if info["col"] is not None:
        floating.start_handle.anchored_col = info["col"]
    floating.set_handles(info["scene_pos"], current_scene_pos)
    floating.end_handle.grabMouse()
    item._pending_port_drag = None
    return floating


def cancel_port_drag(item):
    """Clear any pending port-drag intent on ``item``."""
    if getattr(item, "_pending_port_drag", None) is not None:
        item._pending_port_drag = None
        return True
    return False

class ConnectionHandle(QGraphicsEllipseItem):
    def __init__(self, parent, is_start_handle=True):
        # Center the ellipse on its coordinate
        super().__init__(-4, -4, 8, 8, parent)
        self.parent_conn = parent
        self.is_start_handle = is_start_handle
        
        self.setBrush(QBrush(QColor("#1A73E8")))
        self.setPen(Qt.PenStyle.NoPen)
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        self.anchored_item = None
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
            if hasattr(item, "target_highlight") and item.target_highlight:
                item.target_highlight = False
                item.update()
            if isinstance(item, ERDTableItem):
                if hasattr(item, '_drag_highlighted_col') and item._drag_highlighted_col:
                    if item._drag_highlighted_col in item.highlighted_cols:
                        item.highlighted_cols.remove(item._drag_highlighted_col)
                    item._drag_highlighted_col = None
                    item.update()
        
        # Highlight new one
        items_under = self.scene().items(scene_pos)
        # Find any item with connection ports
        target_item = next((it for it in items_under if hasattr(it, "get_column_anchor_pos") and it != self.parent_conn), None)
        
        if target_item and isinstance(target_item, ERDTableItem) and target_item.show_columns:
            local_pos = target_item.mapFromScene(scene_pos)
            if local_pos.y() >= target_item.header_height:
                idx = int((local_pos.y() - target_item.header_height) // target_item.row_height)
                if 0 <= idx < len(target_item.columns):
                    target_col = target_item.columns[idx]['name']
                    target_item.highlighted_cols.add(target_col)
                    target_item._drag_highlighted_col = target_col
                    target_item.update()
        
        # New Shape-level highlighting
        if target_item:
            target_item.target_highlight = True
            target_item.update()
            # Store it so we can clean it up later
            self._current_target_item = target_item
        else:
            self._current_target_item = None

    def contextMenuEvent(self, event: QGraphicsSceneMouseEvent):
        self.parent_conn.contextMenuEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        # Crucial: Grab the mouse so we get move/release events
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable:
            super().mouseMoveEvent(event)
        else:
            # Manual move using delta for stability
            delta = event.scenePos() - event.lastScenePos()
            if not delta.isNull():
                self.setPos(self.pos() + delta)
            event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        # Crucial: Release the mouse grab safely
        if self.scene() and self.scene().mouseGrabberItem() == self:
            self.ungrabMouse()
        super().mouseReleaseEvent(event)
        if not self.scene():
            return
            
        scene_pos = self.scenePos()
        items_under = self.scene().items(scene_pos)
        
        # Avoid finding the handles or the connection line itself
        target_item = next((
            it for it in items_under 
            if hasattr(it, "get_column_anchor_pos") 
            and it != self.parent_conn 
            and not isinstance(it, ConnectionHandle)
        ), None)
        
        self.anchored_item = None
        self.anchored_col = None
        
        if target_item:
            self.anchored_item = target_item
            
            local_pos = target_item.mapFromScene(scene_pos)
            if isinstance(target_item, ERDTableItem) and target_item.show_columns and local_pos.y() >= target_item.header_height:
                idx = int((local_pos.y() - target_item.header_height) // target_item.row_height)
                if 0 <= idx < len(target_item.columns):
                    self.anchored_col = target_item.columns[idx]['name']
                    # Snap to anchor
                    snap_pos = target_item.get_column_anchor_pos(self.anchored_col, "left")
                    if local_pos.x() > target_item.width / 2:
                        snap_pos = target_item.get_column_anchor_pos(self.anchored_col, "right")
                    self.setPos(self.parent_conn.mapFromScene(snap_pos))
                else:
                    self.setPos(self.parent_conn.mapFromScene(target_item.get_column_anchor_pos(None, "left" if local_pos.x() < target_item.rect().width()/2 else "right")))
            else:
                # Snap to shape itself
                w = target_item.rect().width() if hasattr(target_item, "rect") else target_item.boundingRect().width()
                side = "left" if local_pos.x() < w/2 else "right"
                self.setPos(self.parent_conn.mapFromScene(target_item.get_column_anchor_pos(None, side)))

        # Clean drag highlighting
        for item in self.scene().items():
            if hasattr(item, "target_highlight") and item.target_highlight:
                item.target_highlight = False
                item.update()
            if isinstance(item, ERDTableItem):
                if hasattr(item, '_drag_highlighted_col') and item._drag_highlighted_col:
                    if item._drag_highlighted_col in item.highlighted_cols:
                        item.highlighted_cols.remove(item._drag_highlighted_col)
                    item._drag_highlighted_col = None
                    item.update()

        # Check if both handles are now anchored to finish the connection
        self.parent_conn.check_anchors()

class ERDFloatingConnectionItem(QGraphicsPathItem):
    def __init__(self, relation_type):
        super().__init__()
        self.relation_type = relation_type
        
        # Align with ERDConnectionItem style: Solid line, grey color
        pen = QPen(QColor("#5F6368"), 1.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)
        self.setZValue(9)
        
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
        self.check_anchors()
        
    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
        """)
        import qtawesome as qta
        menu.addAction(qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Connection").triggered.connect(self._remove_self)
        menu.exec(event.screenPos())
        event.accept()

    def _remove_self(self):
        if self.scene():
            self.scene().removeItem(self)

    def updatePath(self):
        p1 = self.start_handle.pos()
        p2 = self.end_handle.pos()
        path = QPainterPath()
        path.moveTo(p1)
        
        # Determine start side for orthogonal routing
        start_side = "right"
        if self.start_handle.anchored_item:
            item = self.start_handle.anchored_item
            scene_p1 = self.mapToScene(p1)
            # Use the un-padded visible rect; sceneBoundingRect() now includes
            # the resize-handle padding which would make edge detection wrong.
            from widgets.erd.items.resizable import item_visual_scene_rect
            rect = item_visual_scene_rect(item)
            
            # Use small epsilon for floating point comparison
            eps = 5.0
            if abs(scene_p1.x() - rect.left()) < eps:
                start_side = "left"
            elif abs(scene_p1.x() - rect.right()) < eps:
                start_side = "right"
            elif abs(scene_p1.y() - rect.top()) < eps:
                start_side = "top"
            elif abs(scene_p1.y() - rect.bottom()) < eps:
                start_side = "bottom"
                
        # Simple orthogonal routing (stepped line)
        if start_side in ("left", "right"):
            mid_x = (p1.x() + p2.x()) / 2
            path.lineTo(mid_x, p1.y())
            path.lineTo(mid_x, p2.y())
        else:
            mid_y = (p1.y() + p2.y()) / 2
            path.lineTo(p1.x(), mid_y)
            path.lineTo(p2.x(), mid_y)
            
        path.lineTo(p2)
        self.prepareGeometryChange()
        self.setPath(path)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        path = self.path()
        if path.elementCount() < 2:
            return
            
        # Draw crow's feet using ERDConnectionItem's helper
        rel_info = RELATION_TYPES.get(self.relation_type, RELATION_TYPES['many-to-one'])
        source_type = rel_info.get('source', 'many')
        target_type = rel_info.get('target', 'one')
        
        # Use the same grey color as the line
        line_color = self.pen().color()
        
        p0 = path.elementAt(0)
        p1_node = path.elementAt(1) # First hinge point
        dx_s, dy_s = p1_node.x - p0.x, p1_node.y - p0.y
        
        pn = path.elementAt(path.elementCount() - 1)
        pn_1 = path.elementAt(path.elementCount() - 2) # Last hinge point
        dx_t, dy_t = pn_1.x - pn.x, pn_1.y - pn.y
        
        self._draw_crows_foot(painter, QPointF(p0.x, p0.y), dx_s, dy_s, source_type, line_color)
        self._draw_crows_foot(painter, QPointF(pn.x, pn.y), dx_t, dy_t, target_type, line_color)

    def _draw_crows_foot(self, painter, P, dx, dy, rel_part, color):
        length = math.hypot(dx, dy)
        if length < 1e-5: 
            return
        
        nx, ny = dx / length, dy / length
        px, py = -ny, nx
        
        pen = QPen(color)
        pen.setWidthF(1.7)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        
        # Backbone to bridge gap (using ~18px like connection_item)
        backbone_len = 18
        painter.drawLine(P, QPointF(P.x() + nx * backbone_len, P.y() + ny * backbone_len))
        
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
        if self.start_handle.anchored_item and self.end_handle.anchored_item:
            # Prevent self-loop on the SAME COLUMN
            if self.start_handle.anchored_item == self.end_handle.anchored_item and self.start_handle.anchored_col == self.end_handle.anchored_col:
                return

            scene = self.scene()
            if not scene:
                return
            
            # --- Logic: If both are tables, we can use AddConnectionCommand ---
            # --- Logic: If one or both are Chen shapes, we create a direct link ---
            s_item = self.start_handle.anchored_item
            e_item = self.end_handle.anchored_item
            
            if isinstance(s_item, ERDTableItem) and isinstance(e_item, ERDTableItem):
                from widgets.erd.commands import AddConnectionCommand
                widget = scene.parent()
                s_name = f"{s_item.schema_name or 'public'}.{s_item.table_name}"
                e_name = f"{e_item.schema_name or 'public'}.{e_item.table_name}"
                cmd = AddConnectionCommand(widget, s_name, self.start_handle.anchored_col, e_name, self.end_handle.anchored_col, self.relation_type)
                scene.removeItem(self)
                if hasattr(scene, 'undo_stack'):
                    scene.undo_stack.push(cmd)
            else:
                # Generic connection between non-table shapes
                from widgets.erd.items.connection_item import ERDConnectionItem
                new_conn = ERDConnectionItem(s_item, e_item, self.start_handle.anchored_col, self.end_handle.anchored_col)
                new_conn.relation_type = self.relation_type
                scene.addItem(new_conn)
                scene.removeItem(self)
