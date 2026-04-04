import math
import qtawesome as qta
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QStyle, QGraphicsDropShadowEffect
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QFontMetrics
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF


from widgets.erd.commands import MoveTableCommand

class ERDTableItem(QGraphicsRectItem):
    def __init__(self, table_name, columns, schema_name=None, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.schema_name = schema_name
        self.columns = columns
        self.header_height = 40 if schema_name else 30
        self.row_height = 20
        self.show_columns = True
        self.show_types = True
        self.connections = []
        self.highlighted_cols = set() # Columns to visually highlight
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        
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
            if c.get('pk'): p = 0
            elif c.get('fk'): p = 1
            return (p, c['name'])
            
        self.columns.sort(key=col_sort_key)
        
        # Cache icons for performance and look
        self.icon_schema = qta.icon('fa5s.layer-group', color='#D93025')
        self.icon_table = qta.icon('fa5s.table', color='#1A73E8')
        self.icon_pk = qta.icon('fa5s.key', color='#F9AB00')
        self.icon_fk = qta.icon('fa5s.key', color='#1A73E8')
        self.icon_col = qta.icon('mdi.table-column', color='#34A853')
        
        self.update_geometry()
        
    def boundingRect(self):
        # Override to include the pen width
        return self.rect().adjusted(-2, -2, 2, 2)
        
    def update_geometry(self):
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
                # Space for icon (25px) + text
                content_width = 30 + fm_col.horizontalAdvance(col_name)
                
                if self.show_types:
                    type_name = col.get('type', '')
                    # Name Width + Type Width + Minimum Spacing (30px) + Icons/Padding
                    content_width += fm_col.horizontalAdvance(type_name) + 40
                
                max_width = max(max_width, content_width + 20)
        
        self.width = max(180, max_width)
        
        # Calculate height
        content_height = (len(self.columns) * self.row_height) if self.show_columns else 0
        total_height = self.header_height + content_height
        # Pad up to the nearest multiple of 20 (Grid Size) for perfect alignment
        self.height = math.ceil(total_height / 20.0) * 20.0
        
        self.setRect(0, 0, self.width, self.height)
        for conn in self.connections:
            conn.updatePath()
        
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
            for i, col in enumerate(self.columns):
                y = self.header_height + (i * self.row_height)
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
                    painter.drawText(col_rect.adjusted(0, 0, -5, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, type_text)

        # 4. Draw FINAL UNIFORM BORDER (Always on top)
        border_color = QColor("#1A73E8") if (is_selected or self.is_highlighted) else QColor("#D1D1D1")
        border_width = 2 if (is_selected or self.is_highlighted) else 1
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect(), 4, 4)

        # 5. Dimming Overlay (Search Focus)
        if self.is_dimmed and not is_selected and not self.is_highlighted:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 200)) # Semi-transparent white
            painter.drawRoundedRect(self.rect(), 4, 4)

    def hoverEnterEvent(self, event):
        if hasattr(self.scene(), "highlight_related"):
            self.scene().highlight_related(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if hasattr(self.scene(), "clear_highlight"):
            self.scene().clear_highlight()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self.scene():
            self.scene()._drag_start_positions = {
                item: item.pos() for item in self.scene().selectedItems() 
                if isinstance(item, ERDTableItem)
            }

    def mouseReleaseEvent(self, event):
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
        return super().itemChange(change, value)

    def get_column_anchor_pos(self, column_name, side="left"):
        # Find column index
        col_idx = -1
        for i, col in enumerate(self.columns):
            if col['name'] == column_name:
                col_idx = i
                break
        
        rect = self.sceneBoundingRect()
        if not self.show_columns or col_idx == -1:
            # Fallback to center side anchor if column not shown or not found
            y = rect.top() + self.header_height / 2
        else:
            y = rect.top() + self.header_height + (col_idx * self.row_height) + (self.row_height / 2)
            
        if side == "left":
            return QPointF(rect.left(), y)
        elif side == "right":
            return QPointF(rect.right(), y)
        elif side == "top":
            return QPointF(rect.left() + rect.width()/2, rect.top())
        else: # bottom
            return QPointF(rect.left() + rect.width()/2, rect.bottom())
