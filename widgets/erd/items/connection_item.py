import math
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem, QStyle, QMenu
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath
from PySide6.QtCore import Qt, QPointF
from widgets.erd.routing import ERDConnectionPathPlanner
from widgets.erd.commands import ChangeRelationTypeCommand

class ERDConnectionItem(QGraphicsPathItem):
    # ── Relationship Types Registry ──
    # Keep core relationship options for MVP editing.
    RELATION_TYPES = {
        'one-to-one': {'label': '1-1', 'icon': 'mdi6.relation-one-to-one', 'source': 'one', 'target': 'one'},
        'one-to-many': {'label': '1-M', 'icon': 'mdi6.relation-one-to-many', 'source': 'one', 'target': 'many'},
        'many-to-one': {'label': 'M-1', 'icon': 'mdi6.relation-many-to-one', 'source': 'many', 'target': 'one'},
        'many-to-many': {'label': 'M-M', 'icon': 'mdi6.relation-many-to-many', 'source': 'many', 'target': 'many'},
    }
    def boundingRect(self):
        # IMPORTANT: Connection markers (crow's feet) draw outside the path.
        # If we don't include them in the bounding rect, SmartViewportUpdate
        # or other optimizations will corrupt the painter state during redraws.
        return super().boundingRect().adjusted(-40, -40, 40, 40)

    def __init__(self, source_item, target_item, source_col, target_col, is_identifying=False, is_unique=False, relation_name=None, fk_meta=None):
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.source_col = source_col
        self.target_col = target_col
        self.is_identifying = is_identifying
        self.is_unique = is_unique
        self.fk_meta = fk_meta or {}
        
        # Determine Plain-English Cardinality
        # Source (FK side) is usually Many, Target (PK side) is One
        if is_unique:
            self.cardinality_desc = f"One {target_item.table_name} refers to exactly one {source_item.table_name}"
            self.cardinality_label = "One-to-One"
        else:
            self.cardinality_desc = f"One {target_item.table_name} can have many {source_item.table_name}s"
            self.cardinality_label = "Many-to-One"

        source_str = f"{source_item.table_name}.{source_col}" if source_col else source_item.table_name
        target_str = f"{target_item.table_name}.{target_col}" if target_col else target_item.table_name

        self.tooltip_text = (
            f"<b>{self.cardinality_label}</b><br/>"
            f"{self.cardinality_desc}<br/>"
            f"<code>{source_str}</code> → <code>{target_str}</code>"
        )
        if self.fk_meta.get("on_delete") or self.fk_meta.get("on_update"):
            self.tooltip_text += (
                f"<br/><small>ON DELETE {self.fk_meta.get('on_delete', 'NO ACTION')} | "
                f"ON UPDATE {self.fk_meta.get('on_update', 'NO ACTION')}</small>"
            )
        
        # Line styling
        pen = QPen(QColor("#5F6368"), 1.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)

        self.relation_type = 'one-to-one' if is_unique else 'many-to-one'
        self._last_source_side = None
        self._last_target_side = None
        self.path_planner = ERDConnectionPathPlanner(self)
        
        self.setZValue(2) # Above tables (0) to ensure handles are always grabable
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip(self.tooltip_text)
        
        source_item.connections.append(self)
        target_item.connections.append(self)
        
        self.updatePath()

    def hoverEnterEvent(self, event):
        # Highlight Source/Target Columns
        self.source_item.highlighted_cols.add(self.source_col)
        self.target_item.highlighted_cols.add(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # Unhighlight Columns
        if self.source_col in self.source_item.highlighted_cols:
            self.source_item.highlighted_cols.remove(self.source_col)
        if self.target_col in self.target_item.highlighted_cols:
            self.target_item.highlighted_cols.remove(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        path = self.path()
        if path.elementCount() >= 2:
            p0 = path.elementAt(0)
            pn = path.elementAt(path.elementCount() - 1)
            dist_start = (event.scenePos() - self.mapToScene(QPointF(p0.x, p0.y))).manhattanLength()
            dist_end = (event.scenePos() - self.mapToScene(QPointF(pn.x, pn.y))).manhattanLength()
            
            if dist_start < 25:
                self._drag_side = "start"
                self._current_mouse_pos = event.scenePos()
                self.setSelected(True)
                event.accept()
                return
            elif dist_end < 25:
                self._drag_side = "end"
                self._current_mouse_pos = event.scenePos()
                self.setSelected(True)
                event.accept()
                return
                
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_side', None):
            self._current_mouse_pos = event.scenePos()
            self.updatePath()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, '_drag_side', None):
            from widgets.erd.commands import DetachConnectionCommand
            from widgets.erd.items.floating_connection import ERDFloatingConnectionItem
            
            if self._drag_side == "start":
                 p1 = event.scenePos()
                 p2 = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
                 trigger_handle = "start"
            else:
                 p1 = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
                 p2 = event.scenePos()
                 trigger_handle = "end"
                 
            self._drag_side = None
            
            widget = self.scene().parent()
            while widget and getattr(widget, '__class__', None).__name__ != 'ERDWidget':
                widget = widget.parent()
                
            floating = ERDFloatingConnectionItem(self.relation_type)
            floating.set_handles(p1, p2)
            
            cmd = DetachConnectionCommand(widget, self, floating)
            self.scene().undo_stack.push(cmd)
            
            # Fake drop to allow immediate connection to new table
            handle = floating.start_handle if trigger_handle == "start" else floating.end_handle
            handle._update_hover_highlight(event.scenePos())
            handle.mouseReleaseEvent(event)
            
            event.accept()
            return
            
        super().mouseReleaseEvent(event)
        
    def updatePath(self):
        # Temporary drawing for drag detaching
        if getattr(self, '_drag_side', None):
            path = QPainterPath()
            if self._drag_side == "start":
                p1 = self.mapFromScene(self._current_mouse_pos)
                p2_scene = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
                p2 = self.mapFromScene(p2_scene)
            else:
                p1_scene = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
                p1 = self.mapFromScene(p1_scene)
                p2 = self.mapFromScene(self._current_mouse_pos)
                
            path.moveTo(p1)
            path.lineTo(p2)
            self.prepareGeometryChange()
            self.setPath(path)
            self.update()
            return

        # 0. Safeguard: Prevent recursive updates
        if getattr(self, "_updating", False):
            return
        self._updating = True
        
        try:
            # 1. Handle Self-Reference (Loop)
            if self.source_item == self.target_item:
                self.updateSelfLoopPath()
                return

            best_points, best_s_side, best_t_side = self.path_planner.compute_best_path()
            self._last_source_side = best_s_side
            self._last_target_side = best_t_side
            
            # 4. Draw Best Path
            path = QPainterPath()
            if best_points:
                path.moveTo(best_points[0])
                for i in range(1, len(best_points)):
                    path.lineTo(best_points[i])
            
            self.prepareGeometryChange()
            self.setPath(path)
            
        finally:
             self._updating = False

    def updateSelfLoopPath(self):
        # Professional circular self-loop
        col_idx = -1
        for i, col in enumerate(self.source_item.columns):
            if col['name'] == self.source_col:
                col_idx = i
                break
        
        a1 = self.source_item.get_column_anchor_pos(self.source_col, "right")
        a2 = self.target_item.get_column_anchor_pos(self.target_col, "right")
        
        path = QPainterPath()
        path.moveTo(a1)
        
        stub_len = 30
        s_stub = QPointF(a1.x() + stub_len, a1.y())
        t_stub = QPointF(a2.x() + stub_len, a2.y())
        
        path.lineTo(s_stub)
        
        # Loop bulge
        loop_dist = 30 + (col_idx * 10)
        cp1 = QPointF(s_stub.x() + loop_dist, s_stub.y())
        cp2 = QPointF(t_stub.x() + loop_dist, t_stub.y())
        
        path.cubicTo(cp1, cp2, t_stub)
        path.lineTo(a2)
        
        self.setPath(path)

    def paint(self, painter, option, widget):
        if not painter.isActive():
            return
        path = self.path()
        if path.elementCount() < 2:
            return

        # 1. Draw the connection line
        pen = QPen(self.pen())
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver
        if is_hovered:
            pen.setColor(QColor("#1A73E8"))
            pen.setWidthF(2.5)
            pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.drawPath(path)

        # 2. Draw Crow's foot ends
        self._draw_crows_foot_ends(painter, path, is_hovered)

    def _draw_crows_foot_ends(self, painter, path, is_hovered):
        if path.elementCount() < 2:
            return
            
        rel_info = self.RELATION_TYPES.get(self.relation_type, self.RELATION_TYPES['many-to-one'])
        source_type = rel_info.get('source', 'many')
        target_type = rel_info.get('target', 'one')
        
        # Source is element 0 (on table) and element 1 (first hinge)
        p0 = path.elementAt(0)
        p1 = path.elementAt(1)
        dx_s, dy_s = p1.x - p0.x, p1.y - p0.y
        self._draw_crows_foot(painter, QPointF(p0.x, p0.y), dx_s, dy_s, source_type, is_hovered)
        
        # Target is last element (on table) and second to last element
        pn_1 = path.elementAt(path.elementCount() - 2)
        pn = path.elementAt(path.elementCount() - 1)
        dx_t, dy_t = pn_1.x - pn.x, pn_1.y - pn.y
        self._draw_crows_foot(painter, QPointF(pn.x, pn.y), dx_t, dy_t, target_type, is_hovered)

    def _draw_crows_foot(self, painter, P, dx, dy, rel_part, is_hovered):
        
        length = math.hypot(dx, dy)
        if length < 1e-5: 
            return
        
        nx, ny = dx / length, dy / length
        px, py = -ny, nx
        
        pen = QPen(QColor("#1A73E8") if is_hovered else QColor("#5F6368"))
        pen.setWidthF(1.7 if is_hovered else 1.3)
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

        # Draw symbols based on standard Crow's Foot ERD mapping
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

    def _apply_relation_type(self, type_key):
        """Applies a relationship type locally and re-renders."""
        self.relation_type = type_key
        rel_info = self.RELATION_TYPES[type_key]

        # Update cardinality label and tooltip
        self.cardinality_label = rel_info['label']
        source_str = f"{self.source_item.table_name}.{self.source_col}" if self.source_col else self.source_item.table_name
        target_str = f"{self.target_item.table_name}.{self.target_col}" if self.target_col else self.target_item.table_name
        
        self.tooltip_text = (
            f"<b>{self.cardinality_label}</b><br/>"
            f"<code>{source_str}</code> → "
            f"<code>{target_str}</code>"
        )
        self.setToolTip(self.tooltip_text)

        # Update marker drawing logic
        self.is_unique = type_key in ('one-to-one',)
        self.prepareGeometryChange()
        self.update()

    def set_relation_type(self, type_key):
        """Changes the relationship type and updates the visual."""
        if type_key not in self.RELATION_TYPES or type_key == self.relation_type:
            return
            
        if self.scene() and hasattr(self.scene(), 'undo_stack'):
            cmd = ChangeRelationTypeCommand(self, self.relation_type, type_key)
            self.scene().undo_stack.push(cmd)
        else:
            self._apply_relation_type(type_key)

    def contextMenuEvent(self, event):
        """Right-click context menu to change relationship type."""
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
            QMenu::separator { height: 1px; background: #e5e7eb; margin: 4px 8px; }
        """)

        for type_key, info in self.RELATION_TYPES.items():
            action = menu.addAction(info['label'])
            action.setCheckable(True)
            action.setChecked(type_key == self.relation_type)
            action.triggered.connect(lambda checked, k=type_key: self.set_relation_type(k))

        menu.addSeparator()
        detach_action = menu.addAction("Detach Relationship")
        detach_action.triggered.connect(self.detach_relationship)

        menu.exec(event.screenPos())
        
    def detach_relationship(self):
        if not self.scene() or not hasattr(self.scene(), 'undo_stack'):
            return
            
        from widgets.erd.commands import DetachConnectionCommand
        from widgets.erd.items.floating_connection import ERDFloatingConnectionItem
        widget = self.scene().parent()
        while widget and getattr(widget, '__class__', None).__name__ != 'ERDWidget':
            widget = widget.parent()
            
        floating = ERDFloatingConnectionItem(self.relation_type)
        
        # Determine endpoints based on current anchors
        p1 = self.source_item.get_column_anchor_pos(self.source_col, self._last_source_side or "right")
        p2 = self.target_item.get_column_anchor_pos(self.target_col, self._last_target_side or "left")
        floating.set_handles(p1, p2)
        
        cmd = DetachConnectionCommand(widget, self, floating)
        self.scene().undo_stack.push(cmd)
