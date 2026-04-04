import math
# from PyQt6.QtWidgets import QGraphicsScene
# from PyQt6.QtGui import QBrush, QColor, QPen
# from PyQt6.QtCore import QLineF, Qt

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtCore import QLineF, Qt

from widgets.erd.items.table_item import ERDTableItem
from widgets.erd.items.connection_item import ERDConnectionItem
from widgets.erd.routing import ERDRouter
from widgets.erd.commands import DeleteItemCommand

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
            self._router_cache = None # invalidate router on resize
            
    def get_router(self):
        if self._router_cache is None:  
            obstacles = []
            for item in self.items():
                if isinstance(item, ERDTableItem):
                    obstacles.append(item.sceneBoundingRect())
            self._router_cache = ERDRouter(self.sceneRect(), obstacles)
        return self._router_cache

    def update_alignment_guides(self):
        self.update() # Force redraw to show/hide lines

    def delete_selected_items(self):
        # Only support deleting connections for now
        
        items_to_delete = []
        for item in self.selectedItems():
            if isinstance(item, ERDConnectionItem):
                items_to_delete.append(item)
                
        if items_to_delete and hasattr(self, 'undo_stack'):  
            cmd = DeleteItemCommand(self, items_to_delete)
            self.undo_stack.push(cmd)

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

    def drawForeground(self, painter, rect):
        if not painter.isActive() or not self.alignment_lines:
            return
            
        pen = QPen(QColor(26, 115, 232, 180)) # Blue color
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        # Limit lines to the current viewport rect for clean rendering
        adjusted_lines = []
        for line in self.alignment_lines:
            # If vertical
            if abs(line.x1() - line.x2()) < 0.1:
                adjusted_lines.append(QLineF(line.x1(), rect.top(), line.x2(), rect.bottom()))
            # If horizontal
            elif abs(line.y1() - line.y2()) < 0.1:
                adjusted_lines.append(QLineF(rect.left(), line.y1(), rect.right(), line.y2()))
        
        painter.drawLines(adjusted_lines)
