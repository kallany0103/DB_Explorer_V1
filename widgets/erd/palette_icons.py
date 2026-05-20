"""Palette icon rendering: tile icons and drag-preview pixmaps for ERD element types."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QPen, QPolygonF, QImage
)


# ERD shape types that get a custom-painted tile icon instead of a font icon
_ERD_TILE_SHAPE_TYPES: frozenset = frozenset({
    "entity", "weak_entity", "relationship_diamond",
    "attribute", "attribute_key", "attribute_partial",
    "attribute_multi", "attribute_derived",
    "relationship:one-to-one", "relationship:one-to-many",
    "relationship:many-to-one", "relationship:many-to-many",
    "relationship:none",
})


def _canvas(w: int = 120, h: int = 60) -> QImage:
    """Return a transparent ARGB32 QImage of the given dimensions."""
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    return img


def _to_pix(img: QImage) -> QPixmap:
    return QPixmap.fromImage(img)


# ---------------------------------------------------------------------------
# Shape preview (drag cursor / hover popup)
# ---------------------------------------------------------------------------

def _preview_table(ct: str) -> QPixmap:
    W, H, ALPHA = 120, 80, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(232, 240, 254, ALPHA))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, W, 26, 4, 4)
    p.setBrush(QColor(255, 255, 255, ALPHA))
    p.drawRoundedRect(0, 0, W, H, 4, 4)
    p.setPen(QPen(QColor("#1A73E8"), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(1, 1, W - 2, H - 2, 4, 4)
    p.setPen(QPen(QColor("#DFE1E5"), 1))
    p.drawLine(0, 26, W, 26)
    p.setPen(QPen(QColor("#9CA3AF"), 1))
    p.setFont(QFont("Segoe UI", 7))
    p.drawText(10, 16, "id  INTEGER  PK")
    p.setPen(QPen(QColor("#374151"), 1))
    p.drawText(10, 42, "name  VARCHAR")
    if ct == "table_fk":
        p.drawText(10, 58, "parent_id  FK")
    p.end()
    return _to_pix(img)


def _preview_entity(ct: str) -> QPixmap:
    W, H, ALPHA = 120, 60, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if ct == "weak_entity":
        p.setBrush(QColor(238, 242, 255, ALPHA))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
        p.setPen(QPen(QColor("#818CF8"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
        p.drawRoundedRect(7, 7, W - 14, H - 14, 2, 2)
        p.setPen(QPen(QColor("#1E293B")))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "WeakEntity")
    else:
        p.setBrush(QColor(232, 240, 254, ALPHA))
        p.setPen(QPen(QColor("#4A90D9"), 2))
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
        p.setPen(QPen(QColor("#1E3A5F")))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Entity")
    p.end()
    return _to_pix(img)


def _preview_attribute(ct: str) -> QPixmap:
    W, H, ALPHA = 120, 60, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(240, 253, 244, ALPHA))
    if ct == "attribute_derived":
        p.setPen(QPen(QColor("#4ADE80"), 1.5, Qt.PenStyle.DashLine))
    elif ct == "attribute_multi":
        p.setPen(QPen(QColor("#16A34A"), 1.5))
        p.drawEllipse(2, 2, W - 4, H - 4)
        p.drawEllipse(7, 7, W - 14, H - 14)
        p.setPen(QPen(QColor("#166534")))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Multi-valued")
        p.end()
        return _to_pix(img)
    else:
        p.setPen(QPen(QColor("#22C55E"), 1.5))
    p.drawEllipse(2, 2, W - 4, H - 4)
    p.setPen(QPen(QColor("#166534")))
    font = QFont("Segoe UI", 9)
    if ct == "attribute_key":
        font.setUnderline(True)
    p.setFont(font)
    label_map = {"attribute_key": "Key", "attribute_partial": "Partial", "attribute_derived": "Derived"}
    p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, label_map.get(ct, "Attribute"))
    if ct == "attribute_partial":
        p.setPen(QPen(QColor("#166534"), 1, Qt.PenStyle.DashLine))
        p.drawLine(30, 42, 90, 42)
    p.end()
    return _to_pix(img)


def _preview_relationship_diamond() -> QPixmap:
    W, H, ALPHA = 120, 70, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    diamond = QPolygonF([QPointF(W / 2, 2), QPointF(W - 2, 35), QPointF(W / 2, 68), QPointF(2, 35)])
    p.setBrush(QColor(255, 247, 237, ALPHA))
    p.setPen(QPen(QColor("#F59E0B"), 1.5))
    p.drawPolygon(diamond)
    p.setPen(QPen(QColor("#92400E")))
    p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Relation")
    p.end()
    return _to_pix(img)


def _preview_note() -> QPixmap:
    W, H, ALPHA = 120, 70, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(255, 247, 214, ALPHA))
    p.setPen(QPen(QColor("#D4B106"), 1))
    p.drawRoundedRect(2, 2, W - 4, 66, 3, 3)
    p.setPen(QPen(QColor("#4B5563")))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(8, 20, "Note")
    p.setPen(QPen(QColor("#9CA3AF")))
    p.setFont(QFont("Segoe UI", 7))
    p.drawText(8, 36, "Type your note...")
    p.end()
    return _to_pix(img)


def _preview_subject_area() -> QPixmap:
    W, H, ALPHA = 120, 70, 80
    img = _canvas(W, H)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(219, 234, 254, ALPHA))
    p.setPen(QPen(QColor("#3B82F6"), 1.5, Qt.PenStyle.DashLine))
    p.drawRoundedRect(2, 2, W - 4, 66, 6, 6)
    p.setPen(QPen(QColor("#1D4ED8")))
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    p.drawText(10, 18, "Subject Area")
    p.end()
    return _to_pix(img)


def _preview_column() -> QPixmap:
    W, ALPHA = 120, 210
    img = _canvas(W, 28)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(255, 255, 255, ALPHA))
    p.setPen(QPen(QColor("#D1D5DB"), 1))
    p.drawRect(0, 0, W, 28)
    p.setPen(QPen(QColor("#34A853")))
    p.setFont(QFont("Segoe UI", 8))
    p.drawText(8, 18, "\u2b1c  new_column  VARCHAR")
    p.end()
    return _to_pix(img)


def _preview_relationship_line(ct: str) -> QPixmap:
    W = 120
    img = _canvas(W, 40)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#5F6368"), 1.5))
    p.drawLine(10, 20, W - 10, 20)
    rel = ct.split(":")[1]
    if rel != "none":
        _draw_cf_marker(p, QPointF(10, 20), 1, 0, rel.split("-to-")[0])
        _draw_cf_marker(p, QPointF(W - 10, 20), -1, 0, rel.split("-to-")[1])
    p.setPen(QPen(QColor("#374151")))
    p.setFont(QFont("Segoe UI", 7))
    labels = {
        "one-to-one": "1 — 1", "one-to-many": "1 — M",
        "many-to-one": "M — 1", "many-to-many": "M — M", "none": "Plain Link",
    }
    p.drawText(QRectF(0, 22, W, 18), Qt.AlignmentFlag.AlignCenter, labels.get(rel, rel))
    p.end()
    return _to_pix(img)


def _preview_fallback() -> QPixmap:
    W, H, ALPHA = 120, 60, 210
    img = _canvas(W, H)
    p = QPainter(img)
    p.setBrush(QColor(200, 200, 200, ALPHA))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
    p.end()
    return _to_pix(img)


def _make_shape_preview(comp_type: str) -> QPixmap:
    """Return a realistic drag-preview pixmap for the given ERD component type."""
    ct = comp_type
    if ct in ("table", "table_fk"):
        return _preview_table(ct)
    if ct in ("entity", "weak_entity"):
        return _preview_entity(ct)
    if ct in ("attribute", "attribute_key", "attribute_partial", "attribute_multi", "attribute_derived"):
        return _preview_attribute(ct)
    if ct == "relationship_diamond":
        return _preview_relationship_diamond()
    if ct == "note":
        return _preview_note()
    if ct == "subject_area":
        return _preview_subject_area()
    if ct == "column":
        return _preview_column()
    if ct.startswith("relationship:"):
        return _preview_relationship_line(ct)
    return _preview_fallback()


# ---------------------------------------------------------------------------
# Tile icon (small, used inside palette buttons)
# ---------------------------------------------------------------------------

def _make_tile_icon(comp_type: str, size: int = 22) -> QPixmap:
    """Return a miniature ERD symbol pixmap for the palette tile icon label."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size
    rx, ry, rw, rh = 1, s // 4, s - 2, s // 2
    ex, ey, ew, eh = 1, s // 4, s - 2, s // 2

    if comp_type == "entity":
        p.setPen(QPen(QColor("#1A73E8"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rx, ry, rw, rh)
    elif comp_type == "weak_entity":
        p.setPen(QPen(QColor("#6366F1"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rx, ry, rw, rh)
        im = max(2, s // 8)
        p.drawRect(rx + im, ry + im, rw - im * 2, rh - im * 2)
    elif comp_type == "relationship_diamond":
        cx, cy = s // 2, s // 2
        mg = 1
        diamond = QPolygonF([QPointF(cx, mg), QPointF(s - mg, cy), QPointF(cx, s - mg), QPointF(mg, cy)])
        p.setPen(QPen(QColor("#F59E0B"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(diamond)
    elif comp_type == "attribute":
        p.setPen(QPen(QColor("#16A34A"), 1.5))
        p.setBrush(QColor("#22C55E"))
        p.drawEllipse(ex, ey, ew, eh)
    elif comp_type == "attribute_key":
        ey2, eh2 = s // 5, s * 2 // 5
        p.setPen(QPen(QColor("#16A34A"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ex, ey2, ew, eh2)
        ul_y = ey2 + eh2 + 3
        p.drawLine(ex + 2, ul_y, ex + ew - 2, ul_y)
    elif comp_type == "attribute_partial":
        ey2, eh2 = s // 5, s * 2 // 5
        p.setPen(QPen(QColor("#15803D"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ex, ey2, ew, eh2)
        pen_d = QPen(QColor("#15803D"), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen_d)
        ul_y = ey2 + eh2 + 3
        p.drawLine(ex + 2, ul_y, ex + ew - 2, ul_y)
    elif comp_type == "attribute_multi":
        p.setPen(QPen(QColor("#16A34A"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ex, ey, ew, eh)
        im = max(2, s // 8)
        p.drawEllipse(ex + im, ey + im, ew - im * 2, eh - im * 2)
    elif comp_type == "attribute_derived":
        pen_d = QPen(QColor("#4ADE80"), 2.0, Qt.PenStyle.DashLine)
        pen_d.setDashPattern([3.0, 2.0])
        p.setPen(pen_d)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(ex, ey, ew, eh)
    elif comp_type.startswith("relationship:"):
        _draw_tile_relationship(p, comp_type, s)

    p.end()
    return QPixmap.fromImage(img)


def _draw_tile_relationship(painter: QPainter, comp_type: str, s: int) -> None:
    """Draw a mini crow's-foot line for relationship tile icons."""
    rel = comp_type.split(":")[1]
    cy = s // 2
    lx, rx_end = 3, s - 3
    pen = QPen(QColor("#5F6368"), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(lx, cy, rx_end, cy)
    if rel == "none":
        return
    left_part, right_part = rel.split("-to-")

    def _mini_marker(x: int, nx: int, part: str) -> None:
        if part == "one":
            bx = x + nx * 3
            painter.drawLine(bx, cy - 3, bx, cy + 3)
        elif part == "many":
            sx = x + nx * 1
            tx = x + nx * 6
            painter.drawLine(sx, cy, tx, cy - 3)
            painter.drawLine(sx, cy, tx, cy + 3)

    _mini_marker(lx, +1, left_part)
    _mini_marker(rx_end, -1, right_part)


# ---------------------------------------------------------------------------
# Crow's foot marker helper (used by both preview and tile renderers)
# ---------------------------------------------------------------------------

def _draw_cf_marker(painter: QPainter, P: QPointF, nx: float, ny: float, part: str) -> None:
    """Draw a mini crow's foot marker at point P facing direction (nx, ny)."""
    px, py = -ny, nx
    painter.setPen(QPen(QColor("#5F6368"), 1.3))

    def bar(offset: float) -> None:
        c = QPointF(P.x() + nx * offset, P.y() + ny * offset)
        painter.drawLine(
            QPointF(c.x() + px * 5, c.y() + py * 5),
            QPointF(c.x() - px * 5, c.y() - py * 5),
        )

    def crows_foot() -> None:
        start = QPointF(P.x() + nx * 2, P.y() + ny * 2)
        tip = QPointF(P.x() + nx * 12, P.y() + ny * 12)
        painter.drawLine(start, QPointF(tip.x() + px * 5, tip.y() + py * 5))
        painter.drawLine(start, QPointF(tip.x() - px * 5, tip.y() - py * 5))

    if part == "one":
        bar(5)
        bar(12)
    elif part == "many":
        crows_foot()
        bar(13)
