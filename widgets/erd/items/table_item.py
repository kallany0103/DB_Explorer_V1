import math
import qtawesome as qta
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QStyle, QGraphicsDropShadowEffect, QMenu
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, QSizeF


from widgets.erd.commands import MoveTableCommand, ResizeItemCommand
from widgets.erd.items.resizable import ResizableItemMixin, item_visual_scene_rect


class ERDTableItem(QGraphicsRectItem, ResizableItemMixin):
    def __init__(self, table_name, columns, schema_name=None, parent=None):
        super().__init__(parent)
        self._init_resizable()
        self.table_name = table_name
        self.schema_name = schema_name
        self.columns = columns
        self.header_height = 40 if schema_name else 30
        self.row_height = 20
        self.show_columns = True
        self.show_types = True
        self.connections = []
        self.highlighted_cols = set() # Columns to visually highlight
        self.target_highlight = False
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.setZValue(1)
        
        self.group_color = QColor("#E8F0FE") # Default
        self.is_dimmed = False
        self.is_highlighted = False
        
        # Drop Shadow
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.shadow.setOffset(0, 4)
        self.shadow.setEnabled(False)
        self.setGraphicsEffect(self.shadow)
        
        self.setAcceptHoverEvents(True) 
        
        # Sort columns: PK -> FK -> Name
        def col_sort_key(c):
            # Priority: PK (0), FK (1), Other (2)
            p = 2
            if c.get('pk'):
                p = 0
            elif c.get('fk'):
                p = 1
            return (p, c['name'])
            
        self.columns.sort(key=col_sort_key)
        
        # Cache icons for performance and look
        self.icon_schema = qta.icon('fa5s.layer-group', color='#D93025')
        self.icon_table = qta.icon('fa5s.table', color='#1A73E8')
        self.icon_pk = qta.icon('fa5s.key', color='#F9AB00')
        self.icon_fk = qta.icon('fa5s.key', color='#1A73E8')
        self.icon_col = qta.icon('mdi.table-column', color='#34A853')
        
        self.update_geometry()

    def minimum_size(self):
        min_height = self.header_height + (self.row_height if self.show_columns else 20)
        return QSizeF(180.0, float(min_height))

    def resize_bounds(self):
        return self.rect()

    def get_size(self):
        return QSizeF(float(self.width), float(self.height))

    def apply_size(self, width, height):
        self.prepareGeometryChange()
        self.width = max(self.minimum_size().width(), width)
        self.height = max(self.minimum_size().height(), height)
        self.setRect(0, 0, self.width, self.height)

    def compute_auto_size(self):
        # Calculate width
        font_header = QFont("Segoe UI", 10, QFont.Weight.Bold)
        fm_header = QFontMetrics(font_header)
        max_width = fm_header.horizontalAdvance(self.table_name) + 40
        
        if self.schema_name:
            font_schema = QFont("Segoe UI", 8, QFont.Weight.Normal)
            fm_schema = QFontMetrics(font_schema)
            max_width = max(max_width, fm_schema.horizontalAdvance(self.schema_name) + 40)
            
        if self.show_columns:
            font_col = QFont("Segoe UI", 9, QFont.Weight.Normal)
            fm_col = QFontMetrics(font_col)
            
            for col in self.columns:
                col_name = col['name']
                content_width = 30 + fm_col.horizontalAdvance(col_name)
                
                if self.show_types:
                    type_name = col.get('type', '')
                    content_width += fm_col.horizontalAdvance(type_name) + 40
                
                max_width = max(max_width, content_width + 20)
        
        width = max(self.minimum_size().width(), max_width)
        
        content_height = (len(self.columns) * self.row_height) if self.show_columns else 0
        total_height = self.header_height + content_height
        height = math.ceil(total_height / 20.0) * 20.0
        return float(width), float(max(self.minimum_size().height(), height))
        
    def boundingRect(self):
        # Override to include the pen width
        pad = self.resize_padding()
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        # When selected, expand the hit-test area to cover the resize handles
        # which extend outside rect(); otherwise hover/click events near the
        # handles never reach this item, making them hard to grab.
        if self.isSelected():
            return self.resize_shape_path()
        return super().shape()

    def update_geometry(self):
        if self.size_mode == "auto":
            width, height = self.compute_auto_size()
            self.apply_size(width, height)
        else:
            self.apply_size(self.width, self.height)
        self._after_geometry_changed()

    def auto_size(self):
        self.size_mode = "auto"
        self.update_geometry()

    def _visible_row_limit(self):
        if not self.show_columns:
            return 0
        visible_rows = int(max(0, (self.height - self.header_height) // self.row_height))
        return min(len(self.columns), visible_rows)
        
    def paint(self, painter, option, widget):
        # Safeguard: Skip if painter is not active
        if not painter.isActive():
            return
            
        # Selection highlight
        is_selected = option.state & QStyle.StateFlag.State_Selected
        
        # 1. Draw Background Body (Fill only)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.drawRoundedRect(self.rect(), 4, 4)
        
        # Draw header
        header_rect = QRectF(0, 0, self.width, self.header_height)
        header_bg = self.group_color
        if self.is_highlighted:
            header_bg = header_bg.darker(110)
            
        painter.setBrush(QBrush(header_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        # Only round top corners
        path = QPainterPath()
        path.addRoundedRect(header_rect, 4, 4)
        painter.drawPath(path)
        
        # Draw Header separator (use a lighter color)
        painter.setPen(QPen(QColor("#DFE1E5"), 1))
        painter.drawLine(0, int(self.header_height), int(self.width), int(self.header_height))

        # Icons and Text
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.schema_name:
            # Draw schema icon
            schema_rect = QRectF(10, 6, 12, 12)
            self.icon_schema.paint(painter, schema_rect.toRect())
            
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(QColor("#666666")))
            painter.drawText(header_rect.adjusted(28, 4, -10, -20), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.schema_name)
            
            # Draw table icon
            table_icon_rect = QRectF(10, 24, 14, 12)
            self.icon_table.paint(painter, table_icon_rect.toRect())
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(header_rect.adjusted(28, 16, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.table_name)
        else:
            # Table icon for simple header
            table_icon_rect = QRectF(10, (self.header_height-12)/2, 14, 12)
            self.icon_table.paint(painter, table_icon_rect.toRect())
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(header_rect.adjusted(28, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, self.table_name)
        
        if self.show_columns:
            rows_bottom = self.header_height + (self._visible_row_limit() * self.row_height)
            painter.save()
            painter.setClipRect(QRectF(0, self.header_height, self.width, max(0, rows_bottom - self.header_height)))
            for i, col in enumerate(self.columns):
                y = self.header_height + (i * self.row_height)
                if y + self.row_height > self.height + 0.1:
                    break
                col_rect = QRectF(10, y, self.width - 20, self.row_height)
                
                is_pk = col.get('pk')
                is_fk = col.get('fk') # Assuming 'fk' key might exist
                
                icon_rect = QRectF(10, y + 4, 12, 12)
                
                # Column Highlight Background (for connection hover)
                if col['name'] in self.highlighted_cols:
                    highlight_rect = QRectF(0, y, self.width, self.row_height)
                    
                    # 1. Subtle Background Fill only
                    painter.setBrush(QColor(26, 115, 232, 25)) # Very light blue highlight
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(highlight_rect)
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                if is_pk:
                    self.icon_pk.paint(painter, icon_rect.toRect())
                elif is_fk:
                    self.icon_fk.paint(painter, icon_rect.toRect())
                else:
                    self.icon_col.paint(painter, icon_rect.toRect())

                painter.setFont(QFont("Segoe UI", 9))
                # Only use a neutral dark grey for text
                text_color = QColor("#D93025") if is_pk else Qt.GlobalColor.black
                painter.setPen(QPen(text_color))
                painter.drawText(col_rect.adjusted(20, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, col['name'])
                    
                if self.show_types:
                    painter.setPen(QPen(QColor("#70757A")))
                    type_text = col.get('type', '')
                    painter.drawText(col_rect.adjusted(0, 0, -20, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, type_text)

                # Draw connection port dot on hovering table
                if self.isUnderMouse():
                    port_radius = 4
                    painter.setBrush(QColor("#1A73E8"))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QRectF(self.width - 12 - port_radius, y + self.row_height/2 - port_radius, port_radius*2, port_radius*2))
                    painter.drawEllipse(QRectF(12 - port_radius, y + self.row_height/2 - port_radius, port_radius*2, port_radius*2))
            painter.restore()

        # 4. Draw FINAL UNIFORM BORDER (Always on top)
        if self.target_highlight:
            border_color = QColor("#10B981") # Green for target
            border_width = 3
        else:
            border_color = QColor("#1A73E8") if (is_selected or self.is_highlighted) else QColor("#D1D1D1")
            border_width = 2 if (is_selected or self.is_highlighted) else 1
            
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect(), 4, 4)
        self.draw_resize_handles(painter)

        # 5. Dimming Overlay (Search Focus)
        if self.is_dimmed and not is_selected and not self.is_highlighted:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 200)) # Semi-transparent white
            painter.drawRoundedRect(self.rect(), 4, 4)

    def hoverEnterEvent(self, event):
        if hasattr(self.scene(), "highlight_related"):
            self.scene().highlight_related(self)
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        self.update_resize_cursor(event.pos())
        self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.clear_resize_cursor()
        if hasattr(self.scene(), "clear_highlight"):
            self.scene().clear_highlight()
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        handle = self.handle_at(event.pos())
        if handle:
            self.begin_resize(handle, event.scenePos())
            event.accept()
            return
        from widgets.erd.items.connection_item import ERDConnectionItem
        # Defensive: If clicking near a connection handle, let the connection catch it
        for item in self.scene().items(event.scenePos()):
            if isinstance(item, ERDConnectionItem):
                path = item.path()
                if path.elementCount() >= 2:
                    p0 = item.mapToScene(QPointF(path.elementAt(0).x, path.elementAt(0).y))
                    pn = item.mapToScene(QPointF(path.elementAt(path.elementCount()-1).x, path.elementAt(path.elementCount()-1).y))
                    if (event.scenePos() - p0).manhattanLength() < 25 or (event.scenePos() - pn).manhattanLength() < 25:
                        event.ignore()
                        return

        pos = event.pos()
        if self.show_columns and self.scene():
            for i, col in enumerate(self.columns[:self._visible_row_limit()]):
                y = self.header_height + (i * self.row_height)
                port_rect_right = QRectF(self.width - 20, y, 20, self.row_height)
                port_rect_left = QRectF(0, y, 20, self.row_height)
                if port_rect_right.contains(pos) or port_rect_left.contains(pos):
                    # Arm a pending connection drag; the floating connection is
                    # only created in mouseMoveEvent once the cursor moves past
                    # the platform drag threshold. A plain click no longer
                    # spawns a dangling connection line.
                    from widgets.erd.items.floating_connection import arm_port_drag
                    arm_port_drag(
                        self,
                        event.scenePos(),
                        col=col['name'],
                        relation_type="many-to-one",
                    )
                    event.accept()
                    return

        super().mousePressEvent(event)
        if self.scene():
            self.scene()._drag_start_positions = {
                item: item.pos() for item in self.scene().selectedItems() 
                if isinstance(item, ERDTableItem)
            }

    def mouseMoveEvent(self, event):
        if self._resizing:
            self.update_resize(event.scenePos())
            event.accept()
            return
        if getattr(self, "_pending_port_drag", None) is not None:
            from widgets.erd.items.floating_connection import maybe_start_port_drag
            if maybe_start_port_drag(self, event.scenePos()) is not None:
                event.accept()
                return
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing:
            changed = self.finish_resize()
            if changed and self.scene() and hasattr(self.scene(), "undo_stack"):
                self.scene().undo_stack.push(
                    ResizeItemCommand(self, self._resize_start_state, self.capture_geometry_state())
                )
            event.accept()
            return
        if getattr(self, "_pending_port_drag", None) is not None:
            # Plain click on a port (no drag) - cancel and treat as selection.
            from widgets.erd.items.floating_connection import cancel_port_drag
            cancel_port_drag(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if hasattr(self.scene(), '_drag_start_positions'):
            starts = self.scene()._drag_start_positions
            
            # Check if any moved
            moved = False
            for item, start_pos in starts.items():
                if item.pos() != start_pos:
                    moved = True
                    break
            
            if moved and hasattr(self.scene(), 'undo_stack'):
                self.scene().undo_stack.beginMacro("Move Items")
                
                for item, start_pos in starts.items():
                    if item.pos() != start_pos:
                        cmd = MoveTableCommand(item, start_pos, item.pos())
                        self.scene().undo_stack.push(cmd)
                self.scene().undo_stack.endMacro()
            
            # Clear snap lines from scene
            if hasattr(self.scene(), 'alignment_lines'):
                self.scene().alignment_lines = []
                self.scene().update_alignment_guides()
                
            del self.scene()._drag_start_positions

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.shadow.setEnabled(self.isSelected())
            return value
            
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Only the user-grabbed item triggers snap guide logic
            is_grabber = self.scene().mouseGrabberItem() == self
            new_pos = value
            x, y = new_pos.x(), new_pos.y()
            
            if is_grabber:
                snap_x, snap_y = x, y
                lines = []
                tolerance = 5.0
                
                my_w = self.width
                my_h = self.height
                
                for item in self.scene().items():
                    if isinstance(item, ERDTableItem) and item != self and not item.isSelected():
                        other_pos = item.pos()
                        other_w = item.width
                        other_h = item.height
                        
                        # Left Edge
                        if abs(x - other_pos.x()) < tolerance:
                            snap_x = other_pos.x()
                            lines.append(QLineF(snap_x, 0, snap_x, 1))
                            
                        # Top Edge
                        if abs(y - other_pos.y()) < tolerance:
                            snap_y = other_pos.y()
                            lines.append(QLineF(0, snap_y, 1, snap_y))
                            
                        # Horizontal Center
                        if abs((x + my_w/2) - (other_pos.x() + other_w/2)) < tolerance:
                            snap_x = other_pos.x() + other_w/2 - my_w/2
                            center_x = snap_x + my_w/2
                            lines.append(QLineF(center_x, 0, center_x, 1))
                            
                        # Vertical Center
                        if abs((y + my_h/2) - (other_pos.y() + other_h/2)) < tolerance:
                            snap_y = other_pos.y() + other_h/2 - my_h/2
                            center_y = snap_y + my_h/2
                            lines.append(QLineF(0, center_y, 1, center_y))

                if lines:
                    x, y = snap_x, snap_y
                    self.scene().alignment_lines = lines
                else:
                    self.scene().alignment_lines = []
                    # Snap to grid fallback
                    x = round(x / 20.0) * 20.0
                    y = round(y / 20.0) * 20.0
                
                if hasattr(self.scene(), "update_alignment_guides"):
                    self.scene().update_alignment_guides()
            else:
                # Still snap followers to grid for consistent spacing
                x = round(x / 20.0) * 20.0
                y = round(y / 20.0) * 20.0
                
            return QPointF(x, y)
            
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for conn in self.connections:
                conn.updatePath()
            if self.scene() and hasattr(self.scene(), 'update_scene_rect'):
                self.scene().update_scene_rect()
            if self.scene() and hasattr(self.scene(), '_router_cache'):
                self.scene()._router_cache = None
        return super().itemChange(change, value)

    def get_column_anchor_pos(self, column_name, side="left"):
        # Find column index
        col_idx = -1
        for i, col in enumerate(self.columns):
            if col['name'] == column_name:
                col_idx = i
                break
        
        rect = item_visual_scene_rect(self)
        if not self.show_columns or col_idx == -1:
            # Fallback to center side anchor if column not shown or not found
            y = rect.top() + self.header_height / 2
        else:
            visible_limit = max(1, self._visible_row_limit())
            visible_idx = min(col_idx, visible_limit - 1)
            y = rect.top() + self.header_height + (visible_idx * self.row_height) + (self.row_height / 2)
            
        if side == "left":
            return QPointF(rect.left(), y)
        elif side == "right":
            return QPointF(rect.right(), y)
        elif side == "top":
            return QPointF(rect.left() + rect.width()/2, rect.top())
        else: # bottom
            return QPointF(rect.left() + rect.width()/2, rect.bottom())
    def contextMenuEvent(self, event):
        self.show_context_menu(event.screenPos())
        event.accept()

    def show_context_menu(self, screen_pos):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 16px; font-size: 9pt; }
            QMenu::item:selected { background: #e8f0fe; color: #1a73e8; border-radius: 4px; }
        """)
        
        menu.addAction(
            qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Table"
        ).triggered.connect(self._remove_self)
        if self.size_mode == "manual":
            menu.addSeparator()
            menu.addAction("Auto Size").triggered.connect(self._auto_size_from_menu)
        
        menu.exec(screen_pos)

    def _remove_self(self):
        scene = self.scene()
        if not scene:
            return
        self.setSelected(True)
        if hasattr(scene, "undo_stack"):
            from widgets.erd.commands import DeleteItemCommand
            scene.undo_stack.push(DeleteItemCommand(scene, [self]))
        else:
            scene.removeItem(self)

    def serialize_view_state(self):
        return self.capture_geometry_state()

    def restore_view_state(self, state):
        self.apply_geometry_state(state)

    def _auto_size_from_menu(self):
        if not self.scene() or not hasattr(self.scene(), "undo_stack"):
            self.auto_size()
            return
        old_state = self.capture_geometry_state()
        self.auto_size()
        self.scene().undo_stack.push(ResizeItemCommand(self, old_state, self.capture_geometry_state()))
