"""ERD diagram serialization: save/load .erd files and image/PDF export."""
import json
import base64
from widgets.erd.items.note_item import ERDNoteItem
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QPixmap, QPainter, QPdfWriter, QPageSize, QPageLayout
from PySide6.QtCore import Qt, QRectF, QSizeF, QMarginsF, QBuffer, QIODevice


# ---------------------------------------------------------------------------
# View-state serialization helpers
# ---------------------------------------------------------------------------

def serialize_free_item(item) -> dict | None:
    """Return serialized state dict for a single free (non-table) item."""
    if hasattr(item, "serialize_view_state"):
        return item.serialize_view_state()
    return None


def serialize_view_state(scene, free_item_types: tuple) -> dict:
    """Build a full view-state snapshot of scene tables and free items."""
    view_state: dict = {"tables": {}, "free_items": []}
    for full_name, item in scene.tables.items():
        data = item.serialize_view_state() if hasattr(item, "serialize_view_state") else {
            "x": item.pos().x(),
            "y": item.pos().y(),
            "width": item.rect().width(),
            "height": item.rect().height(),
            "size_mode": getattr(item, "size_mode", "auto"),
        }
        view_state["tables"][full_name] = data

    for item in reversed(scene.items()):
        if isinstance(item, free_item_types):
            data = serialize_free_item(item)
            if data:
                view_state["free_items"].append(data)
    return view_state


def create_free_item_from_state(data: dict, scene):
    """Instantiate and add a free item from its serialized state dict."""
    from widgets.erd.items.note_item import ERDNoteItem
    from widgets.erd.items.entity_item import ERDEntityItem
    from widgets.erd.items.weak_entity_item import ERDWeakEntityItem
    from widgets.erd.items.attribute_item import ERDAttributeItem
    from widgets.erd.items.relationship_diamond_item import ERDRelationshipDiamondItem
    from widgets.erd.items.subject_area_item import ERDSubjectAreaItem

    item_type = data.get("type")
    item = None
    if item_type == "note":
        item = ERDNoteItem(data.get("text", "Note"))
    elif item_type == "entity":
        item = ERDEntityItem(data.get("label", "Entity"))
    elif item_type == "weak_entity":
        item = ERDWeakEntityItem(data.get("label", "WeakEntity"))
    elif item_type == "attribute":
        item = ERDAttributeItem(data.get("label", "Attribute"), kind=data.get("kind", "normal"))
    elif item_type == "relationship_diamond":
        item = ERDRelationshipDiamondItem(
            data.get("label", "Relationship"),
            is_identifying=data.get("is_identifying", False),
        )
    elif item_type == "subject_area":
        item = ERDSubjectAreaItem(
            data.get("title", "Subject Area"),
            color_idx=data.get("color_idx"),
        )

    if item is None:
        return None

    item.setPos(data.get("x", 0), data.get("y", 0))
    if hasattr(item, "restore_view_state"):
        item.restore_view_state(data)
    scene.addItem(item)
    return item


def restore_view_state(state: dict, scene, free_item_types: tuple) -> None:
    """Apply a saved view-state snapshot back onto the scene."""
    if not state:
        return
    for full_name, item_state in state.get("tables", {}).items():
        item = scene.tables.get(full_name)
        if item and hasattr(item, "restore_view_state"):
            item.restore_view_state(item_state)
    for item_state in state.get("free_items", []):
        create_free_item_from_state(item_state, scene)


# ---------------------------------------------------------------------------
# .erd file save / load
# ---------------------------------------------------------------------------

def save_erd(widget) -> None:
    """Prompt for a file path and save the full ERD state as JSON."""
    from widgets.erd.items.floating_connection import ERDFloatingConnectionItem
    from widgets.erd.items.note_item import ERDNoteItem

    floating = any(isinstance(i, ERDFloatingConnectionItem) for i in widget.scene.items())
    if floating:
        reply = QMessageBox.warning(
            widget,
            "Unconnected Lines",
            "These lines are not connected. Do you want to save anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return

    file_path, _ = QFileDialog.getSaveFileName(widget, "Save ERD State", "", "ERD Files (*.erd)")
    if not file_path:
        return

    state = {
        "version": 3,
        "schema_data": widget.schema_data,
        "view_state": widget._serialize_view_state(),
        "positions": {},
        "notes": [],
    }
    for full_name, item in widget.scene.tables.items():
        pos = item.pos()
        state["positions"][full_name] = {"x": pos.x(), "y": pos.y()}
    for item in widget.scene.items():
        if isinstance(item, ERDNoteItem):
            pos = item.pos()
            state["notes"].append({"text": item.text(), "x": pos.x(), "y": pos.y()})

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        QMessageBox.critical(widget, "Error", f"Failed to save ERD: {str(e)}")


def load_erd_file(widget, file_path: str | None = None) -> None:
    """Prompt (if no path given) and load an ERD state file into the widget."""
   
    if not file_path:
        file_path, _ = QFileDialog.getOpenFileName(widget, "Open ERD State", "", "ERD Files (*.erd)")
    if not file_path:
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            state = json.load(f)

        if "schema_data" in state:
            widget.schema_data = state["schema_data"]
            widget.notes_data = state.get("notes", [])
            widget.view_state_data = state.get("view_state")
            widget.scene.clear()
            widget.undo_stack.clear()
            widget.scene.tables = {}
            widget.load_schema()
            if widget.view_state_data:
                widget._restore_view_state(widget.view_state_data)
            else:
                positions = state.get("positions", {})
                for full_name, pos in positions.items():
                    if full_name in widget.scene.tables:
                        widget.scene.tables[full_name].setPos(pos["x"], pos["y"])
                for note in widget.notes_data:
                    note_item = ERDNoteItem(note.get("text", "Note"))
                    note_item.setPos(note.get("x", 0), note.get("y", 0))
                    widget.scene.addItem(note_item)
            widget.scene.update_scene_rect()

        widget.status_message(f"ERD Loaded: {file_path}")
    except Exception as e:
        QMessageBox.critical(widget, "Error", f"Failed to load ERD: {str(e)}")


# ---------------------------------------------------------------------------
# Image / PDF export
# ---------------------------------------------------------------------------

def _render_to_pixmap(scene, items_rect: QRectF, scale_factor: float) -> QPixmap:
    """Render the scene area into a high-res QPixmap."""
    w = int(items_rect.width() * scale_factor)
    h = int(items_rect.height() * scale_factor)
    pixmap = QPixmap(w, h)
    pixmap.fill(Qt.GlobalColor.white)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.scale(scale_factor, scale_factor)
    scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
    painter.end()
    return pixmap


def _export_svg(scene, items_rect: QRectF, file_path: str) -> None:
    """Export scene as an SVG wrapping a base64-encoded PNG raster."""
    pixmap = _render_to_pixmap(scene, items_rect, scale_factor=2.0)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    png_b64 = base64.b64encode(buf.data().data()).decode("utf-8")
    buf.close()
    svg_w = int(items_rect.width())
    svg_h = int(items_rect.height())
    svg_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}">\n'
        f'  <title>Database ERD Diagram</title>\n'
        f'  <image width="{svg_w}" height="{svg_h}" '
        f'xlink:href="data:image/png;base64,{png_b64}"/>\n'
        '</svg>'
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg_content)


def _export_pdf(scene, items_rect: QRectF, file_path: str) -> None:
    """Export scene to a PDF page sized to match the diagram."""
    scale_factor = 3.0
    pixmap = _render_to_pixmap(scene, items_rect, scale_factor)
    base_dpi = 96
    width_mm = items_rect.width() * 25.4 / base_dpi
    height_mm = items_rect.height() * 25.4 / base_dpi
    printer = QPdfWriter(file_path)
    printer.setResolution(int(base_dpi * scale_factor))
    custom_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter)
    layout = QPageLayout(custom_size, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0))
    printer.setPageLayout(layout)
    pdf_painter = QPainter()
    pdf_painter.begin(printer)
    pdf_painter.drawPixmap(0, 0, printer.width(), printer.height(), pixmap)
    pdf_painter.end()


def _export_raster(scene, items_rect: QRectF, file_path: str, widget) -> None:
    """Export scene to PNG or JPG with OOM guard."""
    MAX_DIM = 16000
    scale_factor = 2.0
    w = int(items_rect.width() * scale_factor)
    h = int(items_rect.height() * scale_factor)
    if w > MAX_DIM or h > MAX_DIM:
        scale_factor = min(MAX_DIM / items_rect.width(), MAX_DIM / items_rect.height())
        w = int(items_rect.width() * scale_factor)
        h = int(items_rect.height() * scale_factor)
    img = QPixmap(w, h)
    if img.isNull():
        QMessageBox.critical(widget, "Error", "Failed to create image buffer (Out of Memory?).")
        return
    if file_path.endswith('.png'):
        img.fill(Qt.GlobalColor.transparent)
    else:
        img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(scale_factor, scale_factor)
    scene.render(painter, QRectF(0, 0, items_rect.width(), items_rect.height()), items_rect)
    painter.end()
    img.save(file_path)


def save_as_image(widget, ext: str = "png") -> None:
    """Prompt for file path and export the ERD as PNG, SVG, or PDF."""
    filter_map = {
        "svg": "SVG Vector (*.svg)",
        "pdf": "PDF Document (*.pdf)",
    }
    filter_str = filter_map.get(ext, "PNG Image (*.png);;JPG Image (*.jpg)")
    file_path, _ = QFileDialog.getSaveFileName(
        widget,
        f"Export ERD Diagram as {ext.upper()}",
        "",
        filter_str,
    )
    if not file_path:
        return

    local_rect = widget.scene.itemsBoundingRect()
    if local_rect.isNull() or local_rect.width() <= 0 or local_rect.height() <= 0:
        QMessageBox.warning(widget, "Empty Diagram", "The diagram is empty or invalid.")
        return

    items_rect = local_rect.adjusted(-50, -50, 50, 50)
    try:
        if file_path.endswith('.svg'):
            _export_svg(widget.scene, items_rect, file_path)
        elif file_path.endswith('.pdf'):
            _export_pdf(widget.scene, items_rect, file_path)
        else:
            _export_raster(widget.scene, items_rect, file_path, widget)
        QMessageBox.information(widget, "Success", f"ERD successfully exported to {file_path}")
    except Exception as e:
        QMessageBox.critical(widget, "Error", f"Failed to export diagram: {str(e)}")
