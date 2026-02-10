import math
import json
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsPathItem, QGraphicsTextItem, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QStyle, QMenu, QFileDialog, QFrame, QMessageBox, QDialog,
    QTextEdit, QDialogButtonBox, QPushButton, QToolButton, QLineEdit
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QAction,
    QIcon, QTransform, QPixmap, QFontMetrics, QPolygonF
)
from PyQt6.QtCore import (
    Qt, QRectF, QPointF, pyqtSignal, QSize, QLineF, QEvent, QTimer
)

class ERDTableItem(QGraphicsRectItem):
    def __init__(self, table_name, columns, schema_name=None, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.schema_name = schema_name
        self.columns = columns
        self.width = 180
        self.header_height = 40 if schema_name else 30
        self.row_height = 20
        self.show_columns = True
        self.show_types = True
        self.connections = []
        self.highlighted_cols = set() # Columns to visually highlight
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.group_color = QColor("#E8F0FE") # Default
        self.is_dimmed = False
        self.is_highlighted = False
        
        self.setAcceptHoverEvents(True) 
        
        # Sort columns: PK -> FK -> Name
        def col_sort_key(c):
            # Priority: PK (0), FK (1), Other (2)
            p = 2
            if c.get('pk'): p = 0
            elif c.get('fk'): p = 1
            return (p, c['name'])
            
        self.columns.sort(key=col_sort_key)
        
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
            # Draw schema diamond icon - Adjusted Y for more space
            schema_rect = QRectF(10, 6, 12, 12)
            painter.setPen(QPen(QColor("#D93025"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            diamond = QPainterPath()
            diamond.moveTo(schema_rect.center().x(), schema_rect.top())
            diamond.lineTo(schema_rect.right(), schema_rect.center().y())
            diamond.lineTo(schema_rect.center().x(), schema_rect.bottom())
            diamond.lineTo(schema_rect.left(), schema_rect.center().y())
            diamond.closeSubpath()
            painter.drawPath(diamond)
            
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(QColor("#666666")))
            painter.drawText(header_rect.adjusted(28, 4, -10, -20), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.schema_name)
            
            # Draw table icon (grid) - Adjusted Y to 24 for more gap
            table_icon_rect = QRectF(10, 24, 14, 12)
            painter.setPen(QPen(QColor("#1A73E8"), 1.5))
            painter.drawRect(table_icon_rect)
            # Use QPointF to avoid float to int conversion errors
            painter.drawLine(QPointF(table_icon_rect.left() + 7, table_icon_rect.top()), 
                             QPointF(table_icon_rect.left() + 7, table_icon_rect.bottom()))
            painter.drawLine(QPointF(table_icon_rect.left(), table_icon_rect.top() + 6), 
                             QPointF(table_icon_rect.right(), table_icon_rect.top() + 6))
            
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.drawText(header_rect.adjusted(28, 16, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.table_name)
        else:
            # Table icon for simple header
            table_icon_rect = QRectF(10, (self.header_height-12)/2, 14, 12)
            painter.setPen(QPen(QColor("#1A73E8"), 1.5))
            painter.drawRect(table_icon_rect)
            painter.drawLine(QPointF(table_icon_rect.left() + 7, table_icon_rect.top()), 
                             QPointF(table_icon_rect.left() + 7, table_icon_rect.bottom()))
            painter.drawLine(QPointF(table_icon_rect.left(), table_icon_rect.top() + 6), 
                             QPointF(table_icon_rect.right(), table_icon_rect.top() + 6))
            
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
                    painter.setBrush(QColor(26, 115, 232, 40)) # Light blue highlight
                    painter.drawRect(highlight_rect)
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                if is_pk:
                    # Gold Key
                    painter.setPen(QPen(QColor("#F9AB00"), 1.5))
                    painter.drawEllipse(icon_rect.adjusted(0,0,-4,-4))
                    painter.drawLine(QPointF(icon_rect.right()-4, icon_rect.bottom()-4), 
                                     QPointF(icon_rect.right(), icon_rect.bottom()))
                    painter.drawLine(QPointF(icon_rect.right()-2, icon_rect.bottom()-3), 
                                     QPointF(icon_rect.right()-1, icon_rect.bottom()-4))
                elif is_fk:
                    # Blue Key for FK
                    painter.setPen(QPen(QColor("#1A73E8"), 1.5))
                    painter.drawEllipse(icon_rect.adjusted(0,0,-4,-4))
                    painter.drawLine(QPointF(icon_rect.right()-4, icon_rect.bottom()-4), 
                                     QPointF(icon_rect.right(), icon_rect.bottom()))
                    painter.drawLine(QPointF(icon_rect.right()-2, icon_rect.bottom()-3), 
                                     QPointF(icon_rect.right()-1, icon_rect.bottom()-4))
                else:
                    # Column Grid Icon (Green)
                    painter.setPen(QPen(QColor("#34A853"), 1.5))
                    painter.drawRect(icon_rect.adjusted(1, 1, -1, -1))
                    painter.drawLine(QPointF(icon_rect.left() + 6, icon_rect.top()+1), 
                                     QPointF(icon_rect.left()+6, icon_rect.bottom()-1))

                painter.setFont(QFont("Segoe UI", 9))
                painter.setPen(QPen(QColor("#D93025") if is_pk else Qt.GlobalColor.black))
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

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Snap to grid (20px)
            # This makes it easy for the user to align tables perfectly "middle-to-middle"
            new_pos = value
            x = round(new_pos.x() / 20.0) * 20.0
            y = round(new_pos.y() / 20.0) * 20.0
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

    def get_anchor_side(self, other_pos):
        rect = self.sceneBoundingRect()
        center = rect.center()
        
        # Decide which side to use based on relative position
        if other_pos.x() > rect.right():
            return "right"
        elif other_pos.x() < rect.left():
            return "left"
        return "left"  # Default 

class ERDConnectionItem(QGraphicsPathItem):
    def boundingRect(self):
        # IMPORTANT: Connection markers (crow's feet) draw outside the path.
        # If we don't include them in the bounding rect, SmartViewportUpdate
        # or other optimizations will corrupt the painter state during redraws.
        return super().boundingRect().adjusted(-40, -40, 40, 40)

    def __init__(self, source_item, target_item, source_col, target_col, is_identifying=False, is_unique=False, relation_name=None):
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self.source_col = source_col
        self.target_col = target_col
        self.is_identifying = is_identifying
        self.is_unique = is_unique
        
        # Determine Plain-English Cardinality
        # Source (FK side) is usually Many, Target (PK side) is One
        if is_unique:
            self.cardinality_desc = f"One {target_item.table_name} refers to exactly one {source_item.table_name}"
            self.cardinality_label = "One-to-One"
        else:
            self.cardinality_desc = f"One {target_item.table_name} can have many {source_item.table_name}s"
            self.cardinality_label = "Many-to-One"

        self.tooltip_text = (
            f"<b>{self.cardinality_label}</b><br/>"
            f"{self.cardinality_desc}<br/>"
            f"<code>{source_item.table_name}.{source_col}</code> → <code>{target_item.table_name}.{target_col}</code>"
        )
        
        # Enterprise Styling: Identifying (Solid) vs Non-Identifying (Dashed)
        pen = QPen(QColor("#5F6368"), 1.5)
        if not is_identifying:
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setDashPattern([4, 4])
        self.setPen(pen)
        
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self.setToolTip(self.tooltip_text)
        
        source_item.connections.append(self)
        target_item.connections.append(self)
        
        self.updatePath()

    def hoverEnterEvent(self, event):
        # 1. Glow Line
        self.setZValue(10) # Bring to front
        self.update()
        
        # 2. Highlight Source/Target Columns
        self.source_item.highlighted_cols.add(self.source_col)
        self.target_item.highlighted_cols.add(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # 1. Unglow
        self.setZValue(-1)
        self.update()
        
        # 2. Unhighlight Columns
        if self.source_col in self.source_item.highlighted_cols:
            self.source_item.highlighted_cols.remove(self.source_col)
        if self.target_col in self.target_item.highlighted_cols:
            self.target_item.highlighted_cols.remove(self.target_col)
        self.source_item.update()
        self.target_item.update()
        super().hoverLeaveEvent(event)
        
    def updatePath(self):
        # 0. Safeguard: Prevent recursive updates
        if getattr(self, "_updating", False):
            return
        self._updating = True
        
        try:
            # 1. Handle Self-Reference (Loop)
            if self.source_item == self.target_item:
                self.updateSelfLoopPath()
                return

            # 2. Dynamic Table Anchoring
            # We ignore specific column rows for the main line to prevent Z-shapes.
            # Instead, we find the optimal connection points on the table perimeters.
            
            s_rect = self.source_item.sceneBoundingRect()
            t_rect = self.target_item.sceneBoundingRect()
            
            # Candidates now include Top/Bottom since we are allowed to connect anywhere
            candidates = [
                ("right", "left"), 
                ("left", "right"), 
                ("bottom", "top"),
                ("top", "bottom"),
                ("right", "right"), 
                ("left", "left")
            ]
            
            best_points = []
            min_cost = float('inf')
            
            for s_side, t_side in candidates:
                # 1. Start with exact centers (Best for grouped trunk exit)
                start = self.get_dynamic_anchor(self.source_item, s_side, t_rect)
                end = self.get_dynamic_anchor(self.target_item, t_side, s_rect)
                
                # 2. Straight-Line Snapping (The "Z-Shape Killer")
                # If they are almost aligned (within grid tolerance), force a straight line.
                # We snap the TARGET to match the SOURCE to maintain a uniform exit point.
                tolerance = 25 
                if s_side in ["left", "right"]:
                    if abs(start.y() - end.y()) < tolerance:
                        # Ensure the snapped point is still within child's vertical bounds
                        if t_rect.top() + 10 < start.y() < t_rect.bottom() - 10:
                            end.setY(start.y())
                elif s_side in ["top", "bottom"]:
                    if abs(start.x() - end.x()) < tolerance:
                        if t_rect.left() + 10 < start.x() < t_rect.right() - 10:
                            end.setX(start.x())

                points = self.calculate_route_points(start, s_side, end, t_side, s_rect, t_rect)
                
                # Identify obstacles: All other tables in the scene
                obstacles = []
                if self.scene():
                    for item in self.scene().items():
                        if isinstance(item, ERDTableItem) and item != self.source_item and item != self.target_item:
                            obstacles.append(item.sceneBoundingRect())

                cost = self.calculate_path_cost(points, s_rect, t_rect, obstacles)
                
                # If it's a direct straight line, add a small bonus to prefer it, 
                # but ONLY if it doesn't collide.
                if len(points) == 2 and cost < 100000:
                    cost -= 100 # Strategy: prefer straight if clear
                
                if cost < min_cost:
                    min_cost = cost
                    best_points = points
            
            # 3. CLAMP PATH POINTS to prevent lines extending too far
            # Limit: Intermediate points should NOT extend beyond the connection points
            if best_points and len(best_points) > 2:
                MARGIN = 15  # Small margin for visual breathing room
                
                # Get actual connection point positions (start and end of path)
                start_pt = best_points[0]
                end_pt = best_points[-1]
                
                # Calculate bounds based on CONNECTION POINTS, not table bounds
                # This ensures the line only goes between where it actually connects
                min_x = min(start_pt.x(), end_pt.x()) - MARGIN
                max_x = max(start_pt.x(), end_pt.x()) + MARGIN
                min_y = min(start_pt.y(), end_pt.y()) - MARGIN
                max_y = max(start_pt.y(), end_pt.y()) + MARGIN
                
                # Clamp intermediate points (corners) to stay within connection bounds
                for i in range(1, len(best_points) - 1):
                    pt = best_points[i]
                    clamped_x = max(min_x, min(max_x, pt.x()))
                    clamped_y = max(min_y, min(max_y, pt.y()))
                    best_points[i] = QPointF(clamped_x, clamped_y)
            
            # 4. Draw Best Path
            path = QPainterPath()
            if best_points:
                path.moveTo(best_points[0])
                for i in range(1, len(best_points)):
                    path.lineTo(best_points[i])
            
            self.setPath(path)
            
        finally:
             self._updating = False

    def get_dynamic_anchor(self, item, side, other_rect):
        # Implementation of "Fixed Center" logic for cleaner hierarchy.
        # This ensures multiple connections from/to the same table share a 
        # common entry/exit point, creating a 'trunk and branch' visual style.
        rect = item.sceneBoundingRect()
        
        if side == "left" or side == "right":
            x = rect.left() if side == "left" else rect.right()
            # Return the vertical center of the table side
            return QPointF(x, rect.top() + rect.height() / 2)
                    
        elif side == "top" or side == "bottom":
             y = rect.top() if side == "top" else rect.bottom()
             # Return the horizontal center of the table side
             return QPointF(rect.left() + rect.width() / 2, y)
            
        return rect.center()

    def get_scene_bounds(self, margin=100):
        """Calculate reasonable bounds for routing based on all tables in the scene.
        
        Returns a QRectF that encompasses all tables with a margin.
        Lines should not extend beyond these bounds.
        """
        if not self.scene():
            return QRectF(-1000, -1000, 3000, 3000)  # Default fallback
        
        # Get all table items
        tables = [item for item in self.scene().items() if isinstance(item, ERDTableItem)]
        if not tables:
            return QRectF(-1000, -1000, 3000, 3000)
        
        # Calculate bounding box of all tables
        min_x = min(t.sceneBoundingRect().left() for t in tables)
        max_x = max(t.sceneBoundingRect().right() for t in tables)
        min_y = min(t.sceneBoundingRect().top() for t in tables)
        max_y = max(t.sceneBoundingRect().bottom() for t in tables)
        
        # Add margin
        return QRectF(min_x - margin, min_y - margin, 
                      (max_x - min_x) + 2 * margin, 
                      (max_y - min_y) + 2 * margin)

    def calculate_route_points(self, start, s_side, end, t_side, s_rect, t_rect):
        """
        Minimal Orthogonal Routing - Guaranteed No-Overshoot.
        """
        # 1. Constants (Synchronized with paint TRIM)
        stub_len = 40 
        
        def get_stub(pt, side, length):
            if side == "left": return QPointF(pt.x() - length, pt.y())
            if side == "right": return QPointF(pt.x() + length, pt.y())
            if side == "top": return QPointF(pt.x(), pt.y() - length)
            return QPointF(pt.x(), pt.y() + length)

        s_stub = get_stub(start, s_side, stub_len)
        t_stub = get_stub(end, t_side, stub_len)
        
        x1, y1 = s_stub.x(), s_stub.y()
        x2, y2 = t_stub.x(), t_stub.y()
        
        s_horiz = s_side in ["left", "right"]
        t_horiz = t_side in ["left", "right"]
        
        # Start points
        pts = [start, s_stub]
        
        # 2. Logic: Minimal segments ONLY
        if s_horiz == t_horiz:
            if s_side != t_side: # Facing (Z-Shape)
                # Midpoint X for horizontal, Y for vertical
                m_x = (x1 + x2) / 2 if s_horiz else x1
                m_y = y1 if s_horiz else (y1 + y2) / 2
                pts.append(QPointF(m_x, m_y))
                
                # Turn point
                m_x2 = m_x if s_horiz else x2
                m_y2 = y2 if s_horiz else m_y
                pts.append(QPointF(m_x2, m_y2))
            else: # U-Shape (Around)
                if s_horiz:
                    ext = max(x1, x2) + 20 if s_side == "right" else min(x1, x2) - 20
                    pts.append(QPointF(ext, y1))
                    pts.append(QPointF(ext, y2))
                else:
                    ext = max(y1, y2) + 20 if s_side == "bottom" else min(y1, y2) - 20
                    pts.append(QPointF(x1, ext))
                    pts.append(QPointF(x2, ext))
        else: # L-Shape
             if s_horiz: pts.append(QPointF(x2, y1))
             else:       pts.append(QPointF(x1, y2))
            
        pts.extend([t_stub, end])
        
        # 3. Final Normalization (Deduplication and Collinear check)
        final = [pts[0]]
        for i in range(1, len(pts)):
            p = pts[i]
            prev = final[-1]
            if (p - prev).manhattanLength() < 0.5: continue
            
            if len(final) >= 2:
                p_prev = final[-2]
                # If segments A-B and B-C are both horizontal or both vertical, merge to A-C
                is_h = abs(p_prev.y() - prev.y()) < 0.1 and abs(prev.y() - p.y()) < 0.1
                is_v = abs(p_prev.x() - prev.x()) < 0.1 and abs(prev.x() - p.x()) < 0.1
                if is_h or is_v:
                    final[-1] = p
                    continue
            final.append(p)
            
        return final

    def calculate_path_cost(self, points, s_rect, t_rect, obstacles):
        if not points: return float('inf')
        
        total_len = 0
        collision_penalty = 0
        
        # Helper to check if a point is inside a rect
        def is_inside(pt, rect, pad=2):
            return rect.adjusted(-pad, -pad, pad, pad).contains(pt)

        for i in range(len(points) - 1):
            p_a = points[i]
            p_b = points[i+1]
            total_len += (p_a - p_b).manhattanLength()
            
            # HUGE penalty for segments that cross through the start or end tables
            # (Excluding the very first and last segments which are stubs)
            if i > 0 and i < len(points) - 2:
                if self.segment_intersects_rect(p_a, p_b, s_rect, padding=-2) or \
                   self.segment_intersects_rect(p_a, p_b, t_rect, padding=-2):
                    collision_penalty += 2000000

            # Obstacle Collisions
            for obs_rect in obstacles:
                if self.segment_intersects_rect(p_a, p_b, obs_rect, padding=-5):
                    collision_penalty += 1000000 
                
        bends = max(0, len(points) - 2)
        return total_len + (bends * 100) + collision_penalty

    def segment_intersects_rect(self, p1, p2, rect, padding=0):
        # Padding > 0 shrinks the rect (more permissive), < 0 expands it (stricter)
        r_x, r_y = rect.x() + padding, rect.y() + padding
        r_w, r_h = rect.width() - 2*padding, rect.height() - 2*padding
        
        min_x, max_x = min(p1.x(), p2.x()), max(p1.x(), p2.x())
        min_y, max_y = min(p1.y(), p2.y()), max(p1.y(), p2.y())
        
        # AABB Intersection
        if max_x < r_x or min_x > r_x + r_w: return False
        if max_y < r_y or min_y > r_y + r_h: return False
        return True             
    def calculate_connection_cost(self, s_side, t_side):
        return 0 # Unused now

    def calculate_stub(self, anchor, side, length):
        if side == "right": return QPointF(anchor.x() + length, anchor.y())
        if side == "left": return QPointF(anchor.x() - length, anchor.y())
        if side == "top": return QPointF(anchor.x(), anchor.y() - length)
        return QPointF(anchor.x(), anchor.y() + length)

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
        # Safeguard: Skip if painter is not active
        if not painter.isActive():
            return
        
        path = self.path()
        if path.elementCount() < 2:
            return
            
        # Draw Crow's Foot Symbols FIRST (they handle connection to table edge)
        self.draw_markers(painter)

        # Draw the main line, but TRIMmed to avoid overlapping markers
        # Markers cover roughly 36px from the anchor.
        TRIM = 36
        
        trimmed_path = QPainterPath()
        
        # We need to find the points on the path at TRIM distance from ends
        # Simplified: We'll adjust the first and last points of our visual path
        points = []
        for i in range(path.elementCount()):
            points.append(QPointF(path.elementAt(i).x, path.elementAt(i).y))
            
        if len(points) >= 2:
            # Adjust start
            p0, p1 = points[0], points[1]
            vec = p1 - p0
            dist = math.sqrt(vec.x()**2 + vec.y()**2)
            if dist > TRIM:
                points[0] = p0 + (vec / dist) * TRIM
            
            # Adjust end
            pn, pn_1 = points[-1], points[-2]
            vec = pn_1 - pn
            dist = math.sqrt(vec.x()**2 + vec.y()**2)
            if dist > TRIM:
                points[-1] = pn + (vec / dist) * TRIM
                
        # Build the visual path
        trimmed_path.moveTo(points[0])
        for i in range(1, len(points)):
            trimmed_path.lineTo(points[i])
            
        pen = QPen(self.pen())
        if option.state & QStyle.StateFlag.State_MouseOver:
            pen.setColor(QColor("#1A73E8"))
            pen.setWidthF(2.5)
            pen.setStyle(Qt.PenStyle.SolidLine)
        
        painter.setPen(pen)
        painter.drawPath(trimmed_path)

    def draw_markers(self, painter):
        # We'll use the path's first and last segments to orient the markers
        path = self.path()
        if path.elementCount() < 2: return
        
        # Pen for markers
        pen = QPen(self.pen().color(), 1.5)
        painter.setPen(pen)
        
        # Source End (a1) - This IS THE MANY SIDE (FK side)
        a1 = path.elementAt(0)
        p1 = path.elementAt(1)
        self.draw_many_marker(painter, QPointF(a1.x, a1.y), QPointF(p1.x, p1.y))
        
        # Target End (a2) - This IS THE ONE SIDE (PK side)
        count = path.elementCount()
        a2 = path.elementAt(count - 1)
        p2 = path.elementAt(count - 2)
        self.draw_one_marker(painter, QPointF(a2.x, a2.y), QPointF(p2.x, p2.y))

    def draw_one_marker(self, painter, anchor, point):
        # Mandatory ONE (||) - Professional Implementation
        dist_outer = 8
        dist_inner = 14
        size = 10
        
        dx = point.x() - anchor.x()
        dy = point.y() - anchor.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0: return
        
        ux, uy = dx/length, dy/length
        px, py = -uy, ux

        # 1. SOLID STUB CONNECTIVITY
        # We draw solid stubs to ensure markers look attached even for dashed lines.
        # Stub 1: Anchor to first bar
        painter.drawLine(anchor, QPointF(anchor.x() + ux * 8, anchor.y() + uy * 8))
        # Stub 2: Beyond second bar (extends to meet the trimmed path at MARKER_ZONE=28+)
        painter.drawLine(QPointF(anchor.x() + ux * 14, anchor.y() + uy * 14), 
                         QPointF(anchor.x() + ux * 30, anchor.y() + uy * 30))

        # 2. SURGICAL MASKING (Breaks the "H" artifact)
        # We only mask the tiny gap between the bars.
        if self.scene() and self.scene().backgroundBrush().color().isValid() and painter.isActive():
            mask_pen = QPen(self.scene().backgroundBrush().color(), 4)
            painter.save()
            painter.setPen(mask_pen)
            # Mask exactly between bars (9 to 13)
            painter.drawLine(QPointF(anchor.x() + ux * 13.5, anchor.y() + uy * 13.5),
                             QPointF(anchor.x() + ux * 8.5, anchor.y() + uy * 8.5))
            painter.restore()
        
        # 3. VERTICAL BARS
        for d in [dist_outer, dist_inner]:
            base = QPointF(anchor.x() + ux * d, anchor.y() + uy * d)
            painter.drawLine(
                QPointF(base.x() + px * size/2, base.y() + py * size/2),
                QPointF(base.x() - px * size/2, base.y() - py * size/2)
            )

    def draw_many_marker(self, painter, anchor, point):
        # Mandatory MANY (|<) - Professional Implementation
        dist_bar = 20
        fork_depth = 12
        fork_width = 12
        
        dx = point.x() - anchor.x()
        dy = point.y() - anchor.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0: return
        
        ux, uy = dx/length, dy/length
        px, py = -uy, ux

        # Ensure a solid stub under the markers (extends to meet trimmed path at MARKER_ZONE=28+)
        painter.drawLine(anchor, QPointF(anchor.x() + ux * 30, anchor.y() + uy * 30))
        
        # 1. Mandatory Vertical Bar
        base_bar = QPointF(anchor.x() + ux * dist_bar, anchor.y() + uy * dist_bar)
        painter.drawLine(
            QPointF(base_bar.x() + px * fork_width/2, base_bar.y() + py * fork_width/2),
            QPointF(base_bar.x() - px * fork_width/2, base_bar.y() - py * fork_width/2)
        )
        
        # 2. The Fork Toes
        base_fork = QPointF(anchor.x() + ux * fork_depth, anchor.y() + uy * fork_depth)
        
        # Three lines meeting at base_fork:
        painter.drawLine(base_fork, anchor)
        painter.drawLine(base_fork, QPointF(anchor.x() + px * fork_width/2, anchor.y() + py * fork_width/2))
        painter.drawLine(base_fork, QPointF(anchor.x() - px * fork_width/2, anchor.y() - py * fork_width/2))

class ERDScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QBrush(QColor("#F8F9FA")))
        self.tables = {}
        self.setSceneRect(0, 0, 2000, 2000)
        
    def update_scene_rect(self):
        # Calculate the bounding box of all items and add a 500px margin
        rect = self.itemsBoundingRect()
        if not rect.isNull():
            margin = 500
            self.setSceneRect(rect.adjusted(-margin, -margin, margin, margin))

    def highlight_related(self, table_item):
        for item in self.items():
            if isinstance(item, ERDTableItem):
                item.is_highlighted = item == table_item
                item.update()
        self.update() # Force scene update for minimap

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
                    # Match against table name or schema name
                    match_name = text in item.table_name.lower()
                    match_schema = item.schema_name and text in item.schema_name.lower()
                    item.is_dimmed = not (match_name or match_schema)
                item.update()

    def find_table_item(self, text):
        text = text.strip().lower()
        if not text: return None
        
        # Return the first best match
        # defined as: starts with text -> contains text
        candidates = []
        for item in self.items():
            if isinstance(item, ERDTableItem):
                name = item.table_name.lower()
                if name == text: return item # Exact match
                if name.startswith(text):
                    candidates.insert(0, item) # Priority to prefix match
                elif text in name:
                    candidates.append(item)
        
        return candidates[0] if candidates else None
        
    def drawBackground(self, painter, rect):
        if not painter.isActive():
            return
        # Fill with background color
        painter.fillRect(rect, QBrush(QColor("#F8F9FA")))
        
        # Optimization: Do not draw grid for very small views (like MiniMap)
        # to prevent thousands of lines causing QPainter session failures.
        if rect.width() < 500: 
            return

        # Draw grid
        grid_size = 20
        
        # Calculate grid boundaries
        left = math.floor(rect.left() / grid_size) * grid_size
        top = math.floor(rect.top() / grid_size) * grid_size
        right = rect.right()
        bottom = rect.bottom()
        
        # Use a thin pen for the grid
        pen = QPen(QColor("#E0E0E0"), 0) # Width 0 is a 1-pixel cosmetic pen
        painter.setPen(pen)
        
        # Draw vertical lines
        lines = []
        x = float(left)
        while x <= right:
            lines.append(QLineF(x, top, x, bottom))
            x += grid_size
            
        # Draw horizontal lines
        y = float(top)
        while y <= bottom:
            lines.append(QLineF(left, y, right, y))
            y += grid_size
            
        if lines:
            painter.drawLines(lines)

class ERDView(QGraphicsView):
    viewport_changed = pyqtSignal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
    def mousePressEvent(self, event):
        # Claim focus when user clicks on the view (clears focus from search bar)
        self.setFocus()
        super().mousePressEvent(event)
        
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor
            if event.angleDelta().y() > 0:
                self.scale(zoom_in_factor, zoom_in_factor)
            else:
                self.scale(zoom_out_factor, zoom_out_factor)
            self.viewport_changed.emit()
        else:
            super().wheelEvent(event)

class ERDMiniMap(QGraphicsView):
    minimized_changed = pyqtSignal(bool)

    def __init__(self, scene, main_view, parent=None):
        super().__init__(scene, parent)
        self.main_view = main_view
        self.is_minimized = False
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setInteractive(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.Box)
        
        # Use NoViewportUpdate to prevent QPainter engine failures from frequent repaints.
        # We manually trigger viewport updates in drawForeground when needed.
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
        
        # Cache the rendered scene to avoid constant QPainter repaints
        self._cache_pixmap = None
        self._cache_valid = False
        self._last_items_rect = QRectF()
        
        # Style the minimap
        self.setBackgroundBrush(QBrush(QColor(255, 255, 255, 220)))
        
        # Style the border only via stylesheet
        self.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #1A73E8;
                background-color: #FFFFFF;
            }
        """)
        
        # Toggle Button
        self.btn_toggle = QPushButton(self)
        self.btn_toggle.setFixedSize(24, 24)
        self.btn_toggle.setText("−") # Unicode minus sign
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #1A73E8;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1557B0;
            }
        """)
        self.btn_toggle.clicked.connect(self.toggle_minimized)
        self.btn_toggle.raise_()
        # The button will be positioned by resizeEvent when setFixedSize is called in initUI

        # Handle viewport changes from main view
        self.main_view.viewport_changed.connect(self.update_view_rect)
        self.view_rect_item = None
        
    def toggle_minimized(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.setFixedSize(34, 34)
            self.btn_toggle.setText("+")
            # Stop the viewport from updating visually
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setStyleSheet("ERDMiniMap { background: transparent; border: none; }")
        else:
            self.setFixedSize(220, 160)
            self.btn_toggle.setText("−")
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.setStyleSheet("""
                ERDMiniMap {
                    border: 2px solid #1A73E8;
                    background-color: #FFFFFF;
                }
            """)
        
        self.reposition_button()
        self.btn_toggle.raise_()
        
        # Emit signal so parent moves us
        self.minimized_changed.emit(self.is_minimized)
        
        # USE A TIMER: Give the OS/Qt event loop 50ms to finish moving/resizing the widget
        # before we force a refresh of the parent area. This prevents 'ghosting'.
        QTimer.singleShot(50, self.force_refresh)

    def force_refresh(self):
        self.update()
        if self.parentWidget():
            self.parentWidget().update()
        if self.main_view and self.main_view.viewport():
            self.main_view.viewport().update()

    def reposition_button(self):
        # Always keep the button in the bottom-right corner of the minimap
        # so it stays near the corner of the screen during toggle
        margin = 5
        btn_x = self.width() - self.btn_toggle.width() - margin
        btn_y = self.height() - self.btn_toggle.height() - margin
        # Ensure coordinates are at least margin
        self.btn_toggle.move(max(margin, btn_x), max(margin, btn_y))

    def update_view_rect(self):
        if self.is_minimized or not self.isVisible() or not self.scene() or self.width() <= 20: 
            return
        items_rect = self.scene().itemsBoundingRect()
        if items_rect.isNull():
            return
            
        # Only refitView if items rect changed significantly
        # This avoids constant fitInView calls that cause QPainter churn
        if self._last_items_rect != items_rect:
            self._last_items_rect = items_rect
            self._cache_valid = False
            self.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        # Request a repaint of the viewport widget (not the scene)
        if self.viewport() and self.isVisible():
            self.viewport().update()

    def drawBackground(self, painter, rect):
        if self.is_minimized:
            return
        if not painter.isActive():
            return
        painter.fillRect(rect, QColor("#F8F9FA"))

    def drawForeground(self, painter, rect):
        if self.is_minimized or not self.main_view or not self.main_view.isVisible(): 
            return
        
        # Ensure painter is active before drawing
        if not painter.isActive():
            return
        
        try:
            # Draw the visible area of the main view
            painter.setPen(QPen(QColor(26, 115, 232, 180), 2))
            painter.setBrush(QColor(26, 115, 232, 30))
            
            # SAFEGUARD: check if main_view viewport is valid
            if not self.main_view.viewport() or not self.main_view.viewport().isVisible():
                return
                
            # Get visible area in scene coordinates
            visible_rect = self.main_view.mapToScene(self.main_view.viewport().rect()).boundingRect()
            painter.drawRect(visible_rect)
        except Exception:
            pass  # Gracefully ignore any paint errors

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_button()

    def mousePressEvent(self, event):
        # Let child widgets (like the toggle button) handle events first
        super().mousePressEvent(event)
        if event.isAccepted():
            return

        if self.is_minimized: return
        # Click to jump main view
        scene_pos = self.mapToScene(event.pos())
        self.main_view.centerOn(scene_pos)

class SQLPreviewDialog(QDialog):
    def __init__(self, sql_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SQL Script")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(sql_text)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.accepted.connect(self.save_sql)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_sql(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SQL Script", "schema.sql", "SQL Files (*.sql)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "Success", "SQL script saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save script: {str(e)}")

class ERDWidget(QWidget):
    def __init__(self, schema_data, parent=None):
        super().__init__(parent)
        self.schema_data = schema_data
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar Container to hold the styled toolbar
        toolbar_container = QWidget()
        toolbar_container.setObjectName("erdToolbarContainer")
        toolbar_container.setStyleSheet("""
            #erdToolbarContainer {
                background-color: #D3D3D3;
                border-bottom: 1px solid #A9A9A9;
                padding: 4px;
            }
            QToolBar {
                background: transparent;
                border: none;
                spacing: 8px;
            }
            QToolButton {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                color: #333333;
            }
            QToolButton:hover {
                background-color: #f0f2f5;
                border: 1px solid #adb5bd;
            }
            QToolButton:pressed {
                background-color: #e8eaed;
            }
            QToolBar::separator {
                width: 1px;
                background-color: #A9A9A9;
                margin: 4px 8px;
            }
        """)
        
        container_layout = QHBoxLayout(toolbar_container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        
        # Group 1: File Operations
        open_action = QAction(QIcon("assets/bright_folder_icon.svg"), "Open ERD (.erd)", self)
        open_action.triggered.connect(self.load_erd_file)
        self.toolbar.addAction(open_action)
        
        save_action = QAction(QIcon("assets/bright_save_icon.svg"), "Save ERD (.erd)", self)
        save_action.triggered.connect(self.save_erd)
        self.toolbar.addAction(save_action)

        export_action = QAction(QIcon("assets/erd_image.svg"), "Export as Image", self)
        export_action.setShortcut("Alt+Ctrl+I")
        export_action.triggered.connect(self.save_as_image)
        self.toolbar.addAction(export_action)
        
        self.toolbar.addSeparator()
        
        # Group 2: View Controls
        zoom_in_action = QAction(QIcon("assets/zoom_in.svg"), "Zoom In", self)
        zoom_in_action.setShortcut("Ctrl++")
        zoom_in_action.triggered.connect(lambda: self.view.scale(1.2, 1.2))
        self.toolbar.addAction(zoom_in_action)
        
        zoom_out_action = QAction(QIcon("assets/zoom_out.svg"), "Zoom Out", self)
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.view.scale(0.8, 0.8))
        self.toolbar.addAction(zoom_out_action)
        
        reset_zoom_action = QAction(QIcon("assets/erd_zoom_fit.svg"), "Zoom to Fit", self)
        reset_zoom_action.setShortcut("Alt+Shift+F")
        reset_zoom_action.triggered.connect(lambda: self.view.setTransform(QTransform()))
        self.toolbar.addAction(reset_zoom_action)
        
        self.toolbar.addSeparator()
        
        # Group 3: Layout & Visibility
        align_action = QAction(QIcon("assets/erd_auto_align.svg"), "Auto Align", self)
        align_action.setShortcut("Alt+Ctrl+L")
        align_action.triggered.connect(self.auto_layout)
        self.toolbar.addAction(align_action)

        self.show_details_action = QAction(QIcon("assets/eye.svg"), "Show Details", self)
        self.show_details_action.setShortcut("Alt+Ctrl+T")
        self.show_details_action.setCheckable(True)
        self.show_details_action.setChecked(True)
        self.show_details_action.triggered.connect(self.toggle_details)
        self.toolbar.addAction(self.show_details_action)

        self.show_types_action = QAction(QIcon("assets/format.svg"), "Show Data Types", self)
        self.show_types_action.setShortcut("Alt+Ctrl+D")
        self.show_types_action.setCheckable(True)
        self.show_types_action.setChecked(True)
        self.show_types_action.triggered.connect(self.toggle_types)
        self.toolbar.addAction(self.show_types_action)
        
        self.toolbar.addSeparator()
        
        # Group 4: Advanced Tools
        self.sql_btn = QToolButton()
        self.sql_btn.setIcon(QIcon("assets/sql_icon.svg"))
        self.sql_btn.setIconSize(QSize(20, 20))
        self.sql_btn.setToolTip("Generate SQL Script (Alt+Ctrl+S)")
        
        # Connection
        self.sql_btn.clicked.connect(self.generate_forward_sql)
        self.toolbar.addWidget(self.sql_btn)
        
        # Add a shortcut too
        self.sql_shortcut = QAction(self)
        self.sql_shortcut.setShortcut("Alt+Ctrl+S")
        self.sql_shortcut.triggered.connect(self.generate_forward_sql)
        self.addAction(self.sql_shortcut)
        
        container_layout.addWidget(self.toolbar)
        container_layout.addStretch()
        
        # Search Bar (Right Aligned)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tables... (Ctrl+F)")
        self.search_input.setFixedWidth(200)
        
        # Add Search Icon
        self.search_input.addAction(QIcon("assets/search.svg"), QLineEdit.ActionPosition.LeadingPosition)
        
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 14px;
                padding: 4px 12px; /* Qt adds space for the action icon automatically */
                font-size: 9pt;
                color: #333333;
            }
            QLineEdit:focus {
                border: 1px solid #1A73E8;
            }
        """)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_input.returnPressed.connect(self.on_search_return_pressed)
        
        search_action = QAction(self)
        search_action.setShortcut("Ctrl+F")
        search_action.triggered.connect(self.search_input.setFocus)
        self.addAction(search_action)

        container_layout.addWidget(self.search_input)

        layout.addWidget(toolbar_container)
        
        # Scene and View
        self.scene = ERDScene(self)
        self.view = ERDView(self.scene, self)
        
        # Main Area with MiniMap Overlay
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        self.view_layout.addWidget(self.view)
        
        # MiniMap overlay (Fixed size in corner)
        # We set view_container as the parent so it floats over the view
        self.minimap = ERDMiniMap(self.scene, self.view, self.view_container)
        self.minimap.setFixedSize(220, 160)
        self.minimap.minimized_changed.connect(lambda _: self.update_minimap_pos())
        self.minimap.show()
        self.minimap.raise_()
        
        layout.addWidget(self.view_container)
        
        self.load_schema()
        self.auto_layout()
        if hasattr(self, "minimap"):
            self.minimap.update_view_rect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_minimap_pos()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_minimap_pos()

    def update_minimap_pos(self):
        # Keep minimap in bottom right of the view_container
        if hasattr(self, "minimap") and hasattr(self, "view_container"):
            m_width = self.minimap.width()
            m_height = self.minimap.height()
            # Position relative to view_container
            self.minimap.move(
                self.view_container.width() - m_width - 20,
                self.view_container.height() - m_height - 20
            )
            self.minimap.raise_()
            
            # Refresh the area under the minimap to prevent ghosting
            if hasattr(self, "view") and self.view.viewport():
                self.view.viewport().update()

    def generate_forward_sql(self):
        # 1. Topological Sort for Table Creation (Parents first)
        adj = {name: [] for name in self.schema_data.keys()}
        in_degree = {name: 0 for name in self.schema_data.keys()}
        for name, info in self.schema_data.items():
            for fk in info.get('foreign_keys', []):
                target = fk['table']
                if target in in_degree:
                    adj[target].append(name)
                    in_degree[name] += 1
        
        queue = [n for n in self.schema_data.keys() if in_degree[n] == 0]
        ordered_tables = []
        while queue:
            queue.sort()
            u = queue.pop(0)
            ordered_tables.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
        
        # Force add any cycles (to not lose tables)
        for name in self.schema_data.keys():
            if name not in ordered_tables: ordered_tables.append(name)

        from datetime import datetime
        gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sql_lines = [
            "-- ===========================================================================",
            "-- ENTERPRISE DATA MODEL EXPORT",
            f"-- Generated on: {gen_time}",
            "-- Engine: PostgreSQL / Standard SQL Compatibility",
            "-- Description: Forward-Engineered Schema DDL",
            "-- ===========================================================================\n",
            "BEGIN TRANSACTION;\n"
        ]

        # 2. Generate CREATE statements
        for full_table_name in ordered_tables:
            info = self.schema_data[full_table_name]
            
            # Format Schema and Table Name
            schema = info.get('schema', 'public')
            table_name = info.get('table', full_table_name.split('.')[-1])
            qualified_name = f"{schema}.{table_name}"
            
            sql_lines.append(f"CREATE TABLE IF NOT EXISTS {qualified_name}")
            sql_lines.append("(")
            
            col_lines = []
            pk_cols = []
            
            # 2a. Column Definitions
            for col in info['columns']:
                col_name = col['name']
                data_type = col['type'].lower()
                
                # Enterprise Serial / Identity detection
                is_pk = col.get('pk')
                if is_pk:
                    pk_cols.append(col_name)
                    # Convert common ID types to serial for modern UX
                    if "int" in data_type:
                        data_type = "serial"
                
                # Robust Character Varying format
                if "varchar" in data_type or "varying" in data_type or "text" in data_type:
                    if "(" not in data_type and "text" not in data_type:
                        data_type = "character varying(255)"
                    data_type += ' COLLATE pg_catalog."default"'

                col_def = f"    {col_name} {data_type}"
                
                # Constraints
                if col.get('nullable') is False or is_pk:
                    col_def += " NOT NULL"
                
                if col.get('default'):
                    d_val = col['default']
                    if '::' not in d_val and (not d_val.startswith("'")):
                        # Simple heuristic for postgres defaults
                        pass 
                    col_def += f" DEFAULT {d_val}"
                
                col_lines.append(col_def)
            
            # 2b. Table Constraints (PK)
            if pk_cols:
                pk_name = f"{table_name}_pkey"
                col_lines.append(f"    CONSTRAINT {pk_name} PRIMARY KEY ({', '.join(pk_cols)})")
                
            # 2c. Table Constraints (FK)
            for fk in info.get('foreign_keys', []):
                fk_name = fk.get('name', f"fk_{table_name}_{fk['from']}")
                target_schema = self.schema_data.get(fk['table'], {}).get('schema', 'public')
                target_table = fk['table'].split('.')[-1]
                
                col_lines.append(
                    f"    CONSTRAINT {fk_name} FOREIGN KEY ({fk['from']}) "
                    f"REFERENCES {target_schema}.{target_table}({fk['to']})"
                )
                
            sql_lines.append(",\n".join(col_lines))
            sql_lines.append(");\n")

        sql_lines.append("COMMIT;")
        
        # Show Dialog
        dialog = SQLPreviewDialog("\n".join(sql_lines), self)
        dialog.exec()
        
    def load_schema(self):
        # Color palette for Subject Areas
        GROUP_COLORS = [
            QColor("#E8F0FE"), # Blue
            QColor("#FCE8E6"), # Red
            QColor("#E6F4EA"), # Green
            QColor("#FEF7E0"), # Yellow
            QColor("#F3E5F5"), # Purple
            QColor("#E0F7FA"), # Cyan
            QColor("#FFF0E0"), # Orange
            QColor("#F0F0F0"), # Gray
        ]

        # 1. Create table items
        for full_name, table_info in self.schema_data.items():
            table_name = table_info.get('table', full_name)
            schema_name = table_info.get('schema')
            
            columns = table_info['columns']
            fk_cols = {fk['from'] for fk in table_info.get('foreign_keys', [])}
            for col in columns:
                if col['name'] in fk_cols:
                    col['fk'] = True
            
            table_item = ERDTableItem(table_name, columns, schema_name=schema_name)
            self.scene.addItem(table_item)
            self.scene.tables[full_name] = table_item

        # 2. Detect Subject Areas (Connected Components)
        adj = {name: [] for name in self.schema_data.keys()}
        for full_name, table_info in self.schema_data.items():
            for fk in table_info.get('foreign_keys', []):
                target = fk['table']
                if target in adj:
                    adj[full_name].append(target)
                    adj[target].append(full_name)
        
        visited = set()
        group_idx = 0
        for name in self.schema_data.keys():
            if name not in visited:
                # New Group
                component = []
                stack = [name]
                while stack:
                    curr = stack.pop()
                    if curr not in visited:
                        visited.add(curr)
                        component.append(curr)
                        stack.extend(adj[curr])
                
                # Assign color to this component
                color = GROUP_COLORS[group_idx % len(GROUP_COLORS)]
                for comp_name in component:
                    if comp_name in self.scene.tables:
                        self.scene.tables[comp_name].group_color = color
                group_idx += 1
            
        # 3. Create connection items
        for full_name, table_info in self.schema_data.items():
            source_item = self.scene.tables.get(full_name)
            if not source_item: continue
            
            # Get PK info for source table to detect Identifying relationships
            pk_cols = {col['name'] for col in table_info['columns'] if col.get('pk')}
            
            for fk in table_info.get('foreign_keys', []):
                target_full_name = fk['table']
                target_item = self.scene.tables.get(target_full_name)
                if target_item:
                    # Logic 1: Identifying? If the FK column is part of the PK
                    is_identifying = fk['from'] in pk_cols
                    
                    # Logic 2: Cardinality? Check if the FK column is also marked unique
                    # (Note: In simple schema retrieval, we'll assume uniqueness if it's a 1:1 join)
                    # For now, if the FK itself is the PK, we treat it as potentially 1:1
                    is_unique = (fk['from'] in pk_cols and len(pk_cols) == 1)
                    
                    conn_item = ERDConnectionItem(
                        source_item, target_item, 
                        fk['from'], fk['to'],
                        is_identifying=is_identifying,
                        is_unique=is_unique
                    )
                    self.scene.addItem(conn_item)
        
        self.scene.update_scene_rect()

    def auto_layout(self):
        items = [item for item in self.scene.items() if isinstance(item, ERDTableItem)]
        if not items: return
        
    def auto_layout(self):
        items = [item for item in self.scene.items() if isinstance(item, ERDTableItem)]
        if not items: return
        
        # 1. Component Detection (Disjoint Subgraphs)
        adj_bi = {name: [] for name in self.schema_data.keys()}
        for full_name, table_info in self.schema_data.items():
            for fk in table_info.get('foreign_keys', []):
                target = fk['table']
                if target in self.schema_data:
                    adj_bi[full_name].append(target)
                    adj_bi[target].append(full_name)
        
        visited = set()
        components = []
        for name in self.schema_data.keys():
            if name not in visited:
                comp = []
                stack = [name]
                while stack:
                    u = stack.pop()
                    if u not in visited:
                        visited.add(u)
                        comp.append(u)
                        stack.extend([v for v in adj_bi[u] if v not in visited])
                if comp: components.append(comp)

        components.sort(key=len, reverse=True)
        
        item_map = self.scene.tables
        current_y_offset = 100
        
        # 2. Layout each component independently (Left-to-Right Flow)
        for comp_nodes in components:
            sub_adj = {n: [] for n in comp_nodes}
            sub_in_degree = {n: 0 for n in comp_nodes}
            sub_total_degree = {n: 0 for n in comp_nodes}
            
            for u in comp_nodes:
                info = self.schema_data[u]
                for fk in info.get('foreign_keys', []):
                    target = fk['table']
                    if target in sub_adj and target != u:
                        sub_adj[target].append(u)
                        sub_in_degree[u] += 1
                        sub_total_degree[u] += 1
                        sub_total_degree[target] += 1

            # Sugiyama Layering (Ranks)
            ranks = {n: 0 for n in comp_nodes}
            queue = [n for n in comp_nodes if sub_in_degree[n] == 0]
            
            while queue:
                u = queue.pop(0)
                for v in sub_adj[u]:
                    sub_in_degree[v] -= 1
                    ranks[v] = max(ranks[v], ranks[u] + 1)
                    if sub_in_degree[v] == 0:
                        queue.append(v)
            
            layers = {}
            for n in comp_nodes:
                r = ranks[n]
                if r not in layers: layers[r] = []
                layers[r].append(n)
                
            sorted_ranks = sorted(layers.keys())
            
            # Sub-Sort using Centrality within Layer
            for r in sorted_ranks:
                nodes = layers[r]
                nodes.sort(key=lambda n: sub_total_degree[n], reverse=True)
                central = []
                left = True
                for node in nodes:
                    if left: central.insert(0, node)
                    else:    central.append(node)
                    left = not left
                layers[r] = central
            
            # Position this component with Left-to-Right flow
            padding_x = 180  # More horizontal space for relationship symbols
            padding_y = 60
            
            # Calculate total component height to center it vertically
            layer_heights = []
            max_comp_height = 0
            for r in sorted_ranks:
                h = sum(item_map[n].rect().height() + padding_y for n in layers[r]) - padding_y
                layer_heights.append(h)
                max_comp_height = max(max_comp_height, h)
            
            current_x = 100
            for i, r in enumerate(sorted_ranks):
                nodes = layers[r]
                max_w = max(item_map[n].rect().width() for n in nodes)
                
                # Starting Y to center this layer relative to the component
                layer_h = layer_heights[i]
                start_y = current_y_offset + (max_comp_height - layer_h) / 2
                
                local_y = start_y
                for name in nodes:
                    item = item_map[name]
                    item.setPos(current_x, local_y)
                    local_y += item.rect().height() + padding_y
                
                current_x += max_w + padding_x
                
            current_y_offset += max_comp_height + 150 # Gap between subgraphs

        self.scene.update_scene_rect()
            
        self.scene.update_scene_rect()

    def toggle_details(self, checked):
        icon_name = "eye.svg" if checked else "eye-off.svg"
        self.show_details_action.setIcon(QIcon(f"assets/{icon_name}"))
        
        for item in self.scene.items():
            if isinstance(item, ERDTableItem):
                item.show_columns = checked
                item.update_geometry()
                item.update()
        
        # Update connections
        for item in self.scene.items():
            if isinstance(item, ERDConnectionItem):
                item.updatePath()
                
    def toggle_types(self, checked):
        for item in self.scene.items():
            if isinstance(item, ERDTableItem):
                item.show_types = checked
                item.update_geometry()
                item.update()
        
        # Update connections
        for item in self.scene.items():
            if isinstance(item, ERDConnectionItem):
                item.updatePath()
                
    def save_erd(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save ERD State", "", "ERD Files (*.erd)")
        if not file_path:
            return
            
        state = {
            "version": 1,
            "schema_data": self.schema_data,
            "positions": {}
        }
        
        for full_name, item in self.scene.tables.items():
            pos = item.pos()
            state["positions"][full_name] = {"x": pos.x(), "y": pos.y()}
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save ERD: {str(e)}")

    def load_erd_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open ERD State", "", "ERD Files (*.erd)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
            if "schema_data" in state:
                self.schema_data = state["schema_data"]
                self.scene.clear()
                self.scene.tables = {}
                self.load_schema()
                
                # Restore positions
                positions = state.get("positions", {})
                for full_name, pos_data in positions.items():
                    if full_name in self.scene.tables:
                        item = self.scene.tables[full_name]
                        item.setPos(pos_data["x"], pos_data["y"])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ERD: {str(e)}")

    def save_as_image(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export ERD as Image", "", "PNG Files (*.png);;JPG Files (*.jpg)")
        if not file_path:
            return
            
        # Adjust scene rect to bounding rect of all items
        local_rect = self.scene.itemsBoundingRect()
        if local_rect.isNull() or local_rect.width() <= 0 or local_rect.height() <= 0:
            QMessageBox.warning(self, "Empty Diagram", "The diagram is empty or invalid.")
            return

        items_rect = local_rect.adjusted(-50, -50, 50, 50)
        
        # High quality export logic
        scale_factor = 2.0  # 2x scale for higher resolution
        
        w = int(items_rect.width() * scale_factor)
        h = int(items_rect.height() * scale_factor)
        
        # Limit max size to avoid OOM or Paint Engine failure (Approx 20k x 20k limit)
        MAX_DIM = 20000
        if w > MAX_DIM or h > MAX_DIM:
             scale_factor = min(MAX_DIM / items_rect.width(), MAX_DIM / items_rect.height())
             w = int(items_rect.width() * scale_factor)
             h = int(items_rect.height() * scale_factor)
             print(f"Warning: Diagram too large, downscaling to {scale_factor:.2f}x")

        # Create high-res pixmap
        img = QPixmap(w, h)
        
        if img.isNull():
             QMessageBox.critical(self, "Error", "Failed to create image buffer (Out of Memory?).")
             return

        img.fill(Qt.GlobalColor.white)
        
        painter = QPainter(img)
        if not painter.isActive():
             QMessageBox.critical(self, "Error", "Painter failed to activate.")
             return
             
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Scale the painter to draw high-res
        painter.scale(scale_factor, scale_factor)
        
        # Render the scene rect to the high-res pixmap
        # QGraphicsScene.render maps the 'source' rect to the 'target' rect automatically
        self.scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
        painter.end()
        
        if img.save(file_path, quality=100):
            QMessageBox.information(self, "Success", f"ERD exported successfully to {file_path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to save image.")

    def on_search_text_changed(self, text):
        if hasattr(self, 'scene') and self.scene:
            self.scene.apply_search_filter(text)

    def on_search_return_pressed(self):
        text = self.search_input.text()
        if hasattr(self, 'scene') and self.scene:
            item = self.scene.find_table_item(text)
            if item:
                self.view.centerOn(item)
                # Optional: Select it too
                self.scene.clearSelection()
                item.setSelected(True)

