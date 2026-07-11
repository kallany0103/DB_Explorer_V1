import copy

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QFrame, QToolTip, QWidget
from PySide6.QtCore import Signal, Qt, QPointF, QTimeLine, QTimer
from PySide6.QtGui import QPainter, QTransform
from widgets.erd.items.floating_connection import ERDFloatingConnectionItem

from widgets.erd.commands import MoveTableCommand, AddTableCommand, AddColumnCommand
from widgets.erd.constants import NUDGE_STEP, DUPLICATE_OFFSET, DRAG_ENDPOINT_RADIUS
from widgets.erd.items.table_item import ERDTableItem

class ERDView(QGraphicsView):
    viewport_changed = Signal()
    tree_item_dropped = Signal(object)  # view_pos (QPointF); receiver resolves item_data from selection

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setAcceptDrops(True)
        self.viewport().setMouseTracking(True)
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
        self._last_tooltip_item = None
        self._is_drag_active = False
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(400)
        self._tooltip_timer.timeout.connect(self._show_pending_tooltip)
        self._pending_tooltip_pos = None

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
        
    def _show_pending_tooltip(self) -> None:
        if self._pending_tooltip_pos is not None:
            QToolTip.showText(self._pending_tooltip_pos, "Double-click to edit", self)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.pos())
        idle = (
            event.buttons() == Qt.MouseButton.NoButton
            and not self._is_drag_active
        )
        if isinstance(item, ERDTableItem) and idle:
            if item is not self._last_tooltip_item:
                self._last_tooltip_item = item
                self._tooltip_timer.stop()
                self._pending_tooltip_pos = event.globalPosition().toPoint()
                self._tooltip_timer.start()
        else:
            self._tooltip_timer.stop()
            self._pending_tooltip_pos = None
            if self._last_tooltip_item is not None:
                self._last_tooltip_item = None
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # Claim focus when user clicks on the view (clears focus from search bar)
        self.setFocus()
        self._tooltip_timer.stop()
        self._pending_tooltip_pos = None
        self._last_tooltip_item = None
        QToolTip.hideText()
        super().mousePressEvent(event)
        
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def _nudge_selected_tables(self, dx: int, dy: int) -> None:
        """Push a nudge macro onto the undo stack for all selected table items."""
        items_to_move = [
            (item, item.pos(), item.pos() + QPointF(dx, dy))
            for item in self.scene().selectedItems()
            if isinstance(item, ERDTableItem)
        ]
        if items_to_move and hasattr(self.scene(), "undo_stack"):
            self.scene().undo_stack.beginMacro("Nudge Tables")
            for item, old_pos, new_pos in items_to_move:
                self.scene().undo_stack.push(MoveTableCommand(item, old_pos, new_pos))
            self.scene().undo_stack.endMacro()

    def _handle_ctrl_key(self, event) -> bool:
        """Handle Ctrl+key shortcuts. Returns True if the event was consumed."""
        key = event.key()
        if key in (Qt.Key.Key_Equal, Qt.Key.Key_Plus):
            self._setup_zoom(1.25)
        elif key == Qt.Key.Key_Minus:
            self._setup_zoom(1 / 1.25)
        elif key == Qt.Key.Key_0:
            if self._zoom_anim.state() == QTimeLine.State.Running:
                self._zoom_anim.stop()
            parent_widget = self.parent()
            if parent_widget is not None and hasattr(parent_widget, '_zoom_to_fit'):
                parent_widget._zoom_to_fit()
            else:
                self.setTransform(QTransform())
                self._target_scale = 1.0
                self.viewport_changed.emit()
        elif key == Qt.Key.Key_A:
            for item in self.scene().items():
                if isinstance(item, ERDTableItem):
                    item.setSelected(True)
        elif key == Qt.Key.Key_D:
            self._duplicate_selected_tables()
        else:
            return False
        return True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Shift and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.scene().clearSelection()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Delete:
            if hasattr(self.scene(), "delete_selected_items"):
                self.scene().delete_selected_items()
            event.accept()
            return
        _arrow_delta = {
            Qt.Key.Key_Left: (-NUDGE_STEP, 0), Qt.Key.Key_Right: (NUDGE_STEP, 0),
            Qt.Key.Key_Up: (0, -NUDGE_STEP), Qt.Key.Key_Down: (0, NUDGE_STEP),
        }
        if event.key() in _arrow_delta:
            dx, dy = _arrow_delta[event.key()]
            self._nudge_selected_tables(dx, dy)
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self._handle_ctrl_key(event):
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

    def dragEnterEvent(self, event):
        self._is_drag_active = True
        self._tooltip_timer.stop()
        self._pending_tooltip_pos = None
        self._last_tooltip_item = None
        QToolTip.hideText()
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-erd-component"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-erd-component"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        # Properly handle drag leaving the view without dropping
        # This prevents the "drag leave received before drag enter" warning
        self._is_drag_active = False
        event.ignore()

    def dropEvent(self, event):
        self._is_drag_active = False
        if event.mimeData().hasFormat("application/x-erd-component"):
            comp_type = event.mimeData().data("application/x-erd-component").data().decode('utf-8')
            self._handle_component_drop(comp_type, event.position())
            event.acceptProposedAction()
            return

        if event.mimeData().hasFormat("application/x-qabstractitemmodeldatalist"):
            self.tree_item_dropped.emit(event.position())
            event.acceptProposedAction()
            return

        super().dropEvent(event)

    def _find_erd_widget(self):
        """Walk up the parent chain and return the first ERDWidget found."""
        from widgets.erd.widget import ERDWidget
        widget = self.parent()
        while widget and not isinstance(widget, ERDWidget):
            widget = widget.parent()
        return widget

    def _create_chen_item(self, comp_type: str, scene_pos: QPointF) -> bool:
        """Instantiate a Chen ERD item and add it to the scene. Returns True if handled."""
        from widgets.erd.items.entity_item import ERDEntityItem
        from widgets.erd.items.weak_entity_item import ERDWeakEntityItem
        from widgets.erd.items.attribute_item import ERDAttributeItem
        from widgets.erd.items.relationship_diamond_item import ERDRelationshipDiamondItem
        from widgets.erd.items.subject_area_item import ERDSubjectAreaItem

        _attr_kind_map = {
            "attribute": "normal", "attribute_key": "key",
            "attribute_partial": "partial", "attribute_multi": "multivalued",
            "attribute_derived": "derived",
        }
        if comp_type == "entity":
            item = ERDEntityItem("Entity")
        elif comp_type == "weak_entity":
            item = ERDWeakEntityItem("WeakEntity")
        elif comp_type in _attr_kind_map:
            item = ERDAttributeItem("Attribute", kind=_attr_kind_map[comp_type])
        elif comp_type == "relationship_diamond":
            item = ERDRelationshipDiamondItem("Relationship")
            item.setPos(scene_pos - QPointF(80, 35))
            self.scene().addItem(item)
            return True
        elif comp_type == "subject_area":
            item = ERDSubjectAreaItem("Subject Area")
            item.setPos(scene_pos - QPointF(200, 150))
            self.scene().addItem(item)
            return True
        else:
            return False
        item.setPos(scene_pos)
        self.scene().addItem(item)
        return True

    def _drop_column_onto_table(self, view_pos: QPointF, widget) -> None:
        """Add a uniquely-named column to the table under the drop position."""
        item = self.itemAt(view_pos.toPoint())
        if not isinstance(item, ERDTableItem):
            return
        col_name = "new_column"
        counter = 1
        existing_names = [c['name'] for c in item.columns]
        while col_name in existing_names:
            col_name = f"new_column_{counter}"
            counter += 1
        cmd = AddColumnCommand(widget, item, {"name": col_name, "type": "VARCHAR(255)"})
        widget.undo_stack.push(cmd)

    def _drop_relationship_line(self, comp_type: str, scene_pos: QPointF) -> None:
        """Place a floating connection line at the drop position."""
        rel_type = comp_type.split(":")[1]
        floating_conn = ERDFloatingConnectionItem(rel_type)
        floating_conn.set_handles(scene_pos - QPointF(50, 0), scene_pos + QPointF(50, 0))
        self.scene().addItem(floating_conn)

    def _handle_component_drop(self, comp_type: str, view_pos: QPointF) -> None:
        scene_pos = self.mapToScene(view_pos.toPoint())
        widget = self._find_erd_widget()
        if not widget:
            return
        if comp_type == "table":
            widget._create_default_entity(scene_pos)
        elif comp_type == "table_fk":
            widget._create_entity_with_fk(scene_pos)
        elif comp_type == "column":
            self._drop_column_onto_table(view_pos, widget)
        elif comp_type == "note":
            widget._create_note_at("Note", scene_pos)
        elif comp_type.startswith("relationship:"):
            self._drop_relationship_line(comp_type, scene_pos)
        else:
            self._create_chen_item(comp_type, scene_pos)


    def _duplicate_selected_tables(self) -> None:
        tables_to_dup = [
            item for item in self.scene().selectedItems()
            if isinstance(item, ERDTableItem)
        ]
        if not tables_to_dup:
            return

        widget = self._find_erd_widget()
        if not widget:
            return

        self.scene().clearSelection()
        widget.undo_stack.beginMacro("Duplicate Tables")
        for item in tables_to_dup:
            new_name = item.table_name + "_copy"
            counter = 1
            while f"{item.schema_name or 'public'}.{new_name}" in self.scene().tables:
                new_name = f"{item.table_name}_copy{counter}"
                counter += 1
            new_pos = QPointF(item.pos().x() + DUPLICATE_OFFSET, item.pos().y() + DUPLICATE_OFFSET)
            widget.undo_stack.push(AddTableCommand(
                widget,
                new_name,
                copy.deepcopy(item.columns),
                new_pos,
                schema_name=item.schema_name,
            ))
        widget.undo_stack.endMacro()
        self.viewport_changed.emit()
