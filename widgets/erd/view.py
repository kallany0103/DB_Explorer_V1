# from PyQt6.QtWidgets import QGraphicsView, QFrame
# from PyQt6.QtCore import pyqtSignal, Qt, QPointF, QTimeLine
# from PyQt6.QtGui import QPainter, QTransform

import copy

from PySide6.QtWidgets import QGraphicsView, QFrame
from PySide6.QtCore import Signal, Qt, QPointF, QTimeLine
from PySide6.QtGui import QPainter, QTransform


from widgets.erd.commands import MoveTableCommand
from widgets.erd.items.table_item import ERDTableItem

class ERDView(QGraphicsView):
    viewport_changed = Signal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        # Smooth Zoom Setup
        self._zoom_anim = QTimeLine(150, self)
        self._zoom_anim.setUpdateInterval(10)
        self._zoom_anim.valueChanged.connect(self._on_zoom_animate)
        self._target_scale = 1.0
        self._base_scale = 1.0

    def _setup_zoom(self, factor):
        if self._zoom_anim.state() == QTimeLine.State.Running:
            self._zoom_anim.stop()
        self._base_scale = self.transform().m11()
        self._target_scale = self._base_scale * factor
        self._zoom_anim.start()

    def _on_zoom_animate(self, value):
        current_m11 = self.transform().m11()
        if current_m11 > 0:
            target = self._base_scale + (self._target_scale - self._base_scale) * value
            step_factor = target / current_m11
            self.scale(step_factor, step_factor)
            self.viewport_changed.emit()
        
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            event.accept()
            return
            
        if event.key() == Qt.Key.Key_A and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            for item in self.scene().items():
                if type(item).__name__ == "ERDTableItem":
                    item.setSelected(True)
            event.accept()
            return
            
        if event.key() == Qt.Key.Key_Escape:
            self.scene().clearSelection()
            event.accept()
            return
            
        if event.key() == Qt.Key.Key_Delete:
            # Tell scene to delete selected connections
            if hasattr(self.scene(), "delete_selected_items"):
                self.scene().delete_selected_items()
            event.accept()
            return
            
        # Arrow Keys (Nudge 20px)
        if event.key() in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right]:
            dx, dy = 0, 0
            if event.key() == Qt.Key.Key_Left:
                dx = -20
            elif event.key() == Qt.Key.Key_Right:
                dx = 20
            elif event.key() == Qt.Key.Key_Up:
                dy = -20
            elif event.key() == Qt.Key.Key_Down:
                dy = 20
            
            moved = False
            items_to_move = []
            for item in self.scene().selectedItems():
                if type(item).__name__ == "ERDTableItem":
                    items_to_move.append((item, item.pos(), item.pos() + QPointF(dx, dy)))
                    moved = True
            
            if moved and hasattr(self.scene(), "undo_stack"):
                self.scene().undo_stack.beginMacro("Nudge Tables")
                for item, old_pos, new_pos in items_to_move:
                    cmd = MoveTableCommand(item, old_pos, new_pos)
                    self.scene().undo_stack.push(cmd)
                self.scene().undo_stack.endMacro()
            event.accept()
            return
            
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom In/Out
            if event.key() == Qt.Key.Key_Equal or event.key() == Qt.Key.Key_Plus:
                self._setup_zoom(1.25)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self._setup_zoom(1/1.25)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_0:
                if self._zoom_anim.state() == QTimeLine.State.Running:
                    self._zoom_anim.stop()
                # Delegate to parent widget's fit-to-screen if available
                parent_widget = self.parent()
                if parent_widget is not None and hasattr(parent_widget, '_zoom_to_fit'):
                    parent_widget._zoom_to_fit()
                else:
                    self.setTransform(QTransform())
                    self._target_scale = 1.0
                    self.viewport_changed.emit()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_D:
                self._duplicate_selected_tables()
                event.accept()
                return
            
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self._setup_zoom(1.25)
            else:
                self._setup_zoom(1 / 1.25)
        else:
            super().wheelEvent(event)

    def _duplicate_selected_tables(self):
        # Find which items are selected
        tables_to_dup = []
        for item in self.scene().selectedItems():
            if type(item).__name__ == "ERDTableItem":
                tables_to_dup.append(item)
                
        if not tables_to_dup:
            return
            
        # Deselect old
        self.scene().clearSelection()
        
        # Determine a safe offset
        offset = 40
        
        for item in tables_to_dup:
            original_name = item.table_name
            # generate new name
            new_name = original_name + "_copy"
            counter = 1
            while f"{item.schema_name or 'public'}.{new_name}" in self.scene().tables:
                new_name = f"{original_name}_copy{counter}"
                counter += 1
                
            
            new_item = ERDTableItem(new_name, copy.deepcopy(item.columns), item.schema_name)
            self.scene().addItem(new_item)
            
            full_name = f"{new_item.schema_name or 'public'}.{new_item.table_name}"
            self.scene().tables[full_name] = new_item
            
            new_item.setPos(item.pos().x() + offset, item.pos().y() + offset)
            new_item.setSelected(True)
            
        self.viewport_changed.emit()
