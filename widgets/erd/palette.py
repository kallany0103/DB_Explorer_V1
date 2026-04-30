"""
ERD Elements Palette
====================
A collapsible, 3-column grid of draggable tile buttons.
Each tile initiates a drag with MIME type "application/x-erd-component",
which is handled by ERDView.dropEvent / _handle_component_drop.
"""

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton
)
from PySide6.QtCore import Qt, QSize, QMimeData, QPoint, QRectF, QPointF
from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont, QPen, QPolygonF


# ---------------------------------------------------------------------------
# Tile definition
# ---------------------------------------------------------------------------

ELEMENTS = [
    # (label,           comp_type,              icon_name,                   icon_color,  row, col)
    ("Table",           "table",                "fa5s.table",                "#1A73E8",   0,   0),
    ("Table + FK",      "table_fk",             "mdi.table-key",             "#1A73E8",   0,   1),
    ("Entity",          "entity",               "fa5s.square",               "#2563EB",   0,   2),
    ("Weak Entity",     "weak_entity",          "fa5s.border-all",           "#6366F1",   1,   0),
    ("Attribute",       "attribute",            "fa5s.circle",               "#22C55E",   1,   1),
    ("Key Attribute",   "attribute_key",        "mdi.circle-edit-outline",   "#16A34A",   1,   2),
    ("Partial Key",     "attribute_partial",    "mdi.circle-double",         "#15803D",   2,   0),
    ("Multi-valued",    "attribute_multi",      "fa5s.dot-circle",           "#16A34A",   2,   1),
    ("Derived Attr",    "attribute_derived",    "fa5s.circle-notch",         "#4ADE80",   2,   2),
    ("Relationship",    "relationship_diamond", "fa5s.square",               "#F59E0B",   3,   0),
    ("Subject Area",    "subject_area",         "fa5s.object-group",         "#8B5CF6",   3,   1),
    ("Note",            "note",                 "fa5s.sticky-note",          "#D4A100",   3,   2),
    ("Column",          "column",               "fa5s.columns",              "#34A853",   4,   0),
    ("1-1 Relation",    "relationship:one-to-one",   "mdi6.relation-one-to-one",   "#5F6368", 4, 1),
    ("1-M Relation",    "relationship:one-to-many",  "mdi6.relation-one-to-many",  "#5F6368", 4, 2),
    ("M-1 Relation",    "relationship:many-to-one",  "mdi6.relation-many-to-one",  "#5F6368", 5, 0),
    ("M-M Relation",    "relationship:many-to-many", "mdi6.relation-many-to-many", "#5F6368", 5, 1),
    ("Plain Link",      "relationship:none",         "mdi6.minus",                "#64748B", 5, 2),
]

TILE_W = 88
TILE_H = 64
ICON_SIZE = 22
EXPANDED_W = 288
COLLAPSED_W = 36


# ---------------------------------------------------------------------------
# Draggable tile button
# ---------------------------------------------------------------------------

class ElementTile(QPushButton):
    """A small tile button that starts a drag on press-and-move."""

    def __init__(self, label: str, comp_type: str, icon_name: str,
                 icon_color: str, palette=None, parent=None):
        super().__init__(parent)
        self.palette = palette
        self.setToolTip("") # Ensure no default OS tooltip interferes
        self._comp_type = comp_type
        self._drag_start: QPoint | None = None

        self.setFixedSize(TILE_W, TILE_H)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(label)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCheckable(False)

        self.setStyleSheet("""
            QPushButton {
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                background: #FFFFFF;
                padding: 0px;
            }
            QPushButton:hover {
                background: #EEF2FF;
                border-color: #818CF8;
            }
            QPushButton:pressed {
                background: #E0E7FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 6)
        layout.setSpacing(4)

        icon_lbl = QLabel()
        try:
            pix = qta.icon(icon_name, color=icon_color).pixmap(ICON_SIZE, ICON_SIZE)
        except Exception:
            pix = QPixmap(ICON_SIZE, ICON_SIZE)
            pix.fill(Qt.GlobalColor.transparent)
        icon_lbl.setPixmap(pix)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_lbl = QLabel(label)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet("color: #374151; font-size: 10px; background: transparent; border: none;")
        text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)

    # ------------------------------------------------------------------
    # Hover / Preview Support
    # ------------------------------------------------------------------

    def event(self, event):
        # Explicitly block all native tooltip events to prevent "black box" bar
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ToolTip:
            return True
        return super().event(event)

    def enterEvent(self, event):
        """Show the realistic shape preview on hover (draw.io style)."""
        if self.palette:
            self.palette.show_preview(self._comp_type, self.mapToGlobal(QPoint(self.width() + 10, 0)))
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide the preview."""
        if self.palette:
            self.palette.hide_preview()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_start is not None
            and (event.pos() - self._drag_start).manhattanLength() > 8
        ):
            self._drag_start = None
            # Hide preview when drag starts
            palette = self.window().findChild(ERDPalette)
            if palette:
                palette.hide_preview()
            self._start_drag()
            return
        super().mouseMoveEvent(event)

    def _start_drag(self):
        mime = QMimeData()
        mime.setData(
            "application/x-erd-component",
            self._comp_type.encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)

        pix = _make_shape_preview(self._comp_type)
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())

        drag.exec(Qt.DropAction.CopyAction)
        
        # Ensure preview is hidden and state is refreshed after drag
        palette = self.window().findChild(ERDPalette)
        if palette:
            palette.hide_preview()
        self.update()


def _make_shape_preview(comp_type: str) -> "QPixmap":
    """
    Draws the actual ERD shape onto a QPixmap so the drag cursor shows
    a realistic preview of what will be dropped — like draw.io.
    """
    from PySide6.QtGui import QImage

    W, H = 120, 60   # default canvas size
    ALPHA = 210       # overall opacity of preview

    def _canvas(w=W, h=H):
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        return img

    def _to_pix(img):
        return QPixmap.fromImage(img)

    ct = comp_type

    # ── Table ──────────────────────────────────────────────────────────
    if ct in ("table", "table_fk"):
        img = _canvas(W, 80)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # header
        p.setBrush(QColor(232, 240, 254, ALPHA))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, W, 26, 4, 4)
        # body
        p.setBrush(QColor(255, 255, 255, ALPHA))
        p.drawRoundedRect(0, 0, W, 80, 4, 4)
        # border
        p.setPen(QPen(QColor("#1A73E8"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, W - 2, 78, 4, 4)
        # header separator
        p.setPen(QPen(QColor("#DFE1E5"), 1))
        p.drawLine(0, 26, W, 26)
        # fake rows
        p.setPen(QPen(QColor("#9CA3AF"), 1))
        f = QFont("Segoe UI", 7)
        p.setFont(f)
        p.drawText(10, 16, "id  INTEGER  PK")
        p.setPen(QPen(QColor("#374151"), 1))
        p.drawText(10, 42, "name  VARCHAR")
        if ct == "table_fk":
            p.drawText(10, 58, "parent_id  FK")
        p.end()
        return _to_pix(img)

    # ── Entity (Chen single border) ─────────────────────────────────────
    if ct == "entity":
        img = _canvas()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(232, 240, 254, ALPHA))
        p.setPen(QPen(QColor("#4A90D9"), 2))
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
        p.setPen(QPen(QColor("#1E3A5F")))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Entity")
        p.end()
        return _to_pix(img)

    # ── Weak Entity (double border) ─────────────────────────────────────
    if ct == "weak_entity":
        img = _canvas()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(238, 242, 255, ALPHA))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
        p.setPen(QPen(QColor("#818CF8"), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)   # outer
        p.drawRoundedRect(7, 7, W - 14, H - 14, 2, 2)  # inner
        p.setPen(QPen(QColor("#1E293B")))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "WeakEntity")
        p.end()
        return _to_pix(img)

    # ── Attribute (oval) ────────────────────────────────────────────────
    if ct in ("attribute", "attribute_key", "attribute_partial"):
        img = _canvas()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(240, 253, 244, ALPHA))
        p.setPen(QPen(QColor("#22C55E"), 1.5))
        p.drawEllipse(2, 2, W - 4, H - 4)
        p.setPen(QPen(QColor("#166534")))
        font = QFont("Segoe UI", 9)
        if ct == "attribute_key":
            font.setUnderline(True)
        p.setFont(font)
        label = "Key" if ct == "attribute_key" else ("Partial" if ct == "attribute_partial" else "Attribute")
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, label)
        
        if ct == "attribute_partial":
            # draw manual dashed underline for preview
            p.setPen(QPen(QColor("#166534"), 1, Qt.PenStyle.DashLine))
            p.drawLine(30, 42, 90, 42)
            
        p.end()
        return _to_pix(img)

    # ── Multi-valued (double oval) ──────────────────────────────────────
    if ct == "attribute_multi":
        img = _canvas()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(240, 253, 244, ALPHA))
        p.setPen(QPen(QColor("#16A34A"), 1.5))
        p.drawEllipse(2, 2, W - 4, H - 4)   # outer
        p.drawEllipse(7, 7, W - 14, H - 14) # inner
        p.setPen(QPen(QColor("#166534")))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Multi-valued")
        p.end()
        return _to_pix(img)

    # ── Derived (dashed oval) ───────────────────────────────────────────
    if ct == "attribute_derived":
        img = _canvas()
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(240, 253, 244, ALPHA))
        pen = QPen(QColor("#4ADE80"), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawEllipse(2, 2, W - 4, H - 4)
        p.setPen(QPen(QColor("#166534")))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "Derived")
        p.end()
        return _to_pix(img)

    # ── Relationship Diamond ────────────────────────────────────────────
    if ct == "relationship_diamond":
        img = _canvas(W, 70)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        diamond = QPolygonF([
            QPointF(W / 2, 2),
            QPointF(W - 2, 35),
            QPointF(W / 2, 68),
            QPointF(2, 35),
        ])
        p.setBrush(QColor(255, 247, 237, ALPHA))
        p.setPen(QPen(QColor("#F59E0B"), 1.5))
        p.drawPolygon(diamond)
        p.setPen(QPen(QColor("#92400E")))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, W, 70), Qt.AlignmentFlag.AlignCenter, "Relation")
        p.end()
        return _to_pix(img)

    # ── Note ────────────────────────────────────────────────────────────
    if ct == "note":
        img = _canvas(W, 70)
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

    # ── Subject Area ────────────────────────────────────────────────────
    if ct == "subject_area":
        img = _canvas(W, 70)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(219, 234, 254, 80)
        p.setBrush(fill)
        pen = QPen(QColor("#3B82F6"), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(2, 2, W - 4, 66, 6, 6)
        p.setPen(QPen(QColor("#1D4ED8")))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.drawText(10, 18, "Subject Area")
        p.end()
        return _to_pix(img)

    # ── Column ──────────────────────────────────────────────────────────
    if ct == "column":
        img = _canvas(W, 28)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(255, 255, 255, ALPHA))
        p.setPen(QPen(QColor("#D1D5DB"), 1))
        p.drawRect(0, 0, W, 28)
        p.setPen(QPen(QColor("#34A853")))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(8, 18, "⬜  new_column  VARCHAR")
        p.end()
        return _to_pix(img)

    # ── Crow's Foot / Plain Relationships ───────────────────────────────
    if ct.startswith("relationship:"):
        rel = ct.split(":")[1]
        img = _canvas(W, 40)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#5F6368"), 1.5)
        p.setPen(pen)
        # Main line
        p.drawLine(10, 20, W - 10, 20)
        
        if rel != "none":
            # Left end marker
            _draw_cf_marker(p, QPointF(10, 20), 1, 0, rel.split("-to-")[0])
            # Right end marker
            _draw_cf_marker(p, QPointF(W - 10, 20), -1, 0, rel.split("-to-")[1])
            
        # Label
        p.setPen(QPen(QColor("#374151")))
        p.setFont(QFont("Segoe UI", 7))
        labels = {"one-to-one": "1 — 1", "one-to-many": "1 — M",
                  "many-to-one": "M — 1", "many-to-many": "M — M",
                  "none": "Plain Link"}
        p.drawText(QRectF(0, 22, W, 18), Qt.AlignmentFlag.AlignCenter,
                   labels.get(rel, rel))
        p.end()
        return _to_pix(img)

    # ── Fallback ────────────────────────────────────────────────────────
    img = _canvas()
    p = QPainter(img)
    p.setBrush(QColor(200, 200, 200, ALPHA))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, W - 4, H - 4, 4, 4)
    p.end()
    return _to_pix(img)


def _draw_cf_marker(painter, P: "QPointF", nx: float, ny: float, part: str):
    """Draw a mini crow's foot marker at point P facing direction (nx, ny)."""
    px, py = -ny, nx
    pen = QPen(QColor("#5F6368"), 1.3)
    painter.setPen(pen)

    def bar(offset):
        c = QPointF(P.x() + nx * offset, P.y() + ny * offset)
        painter.drawLine(
            QPointF(c.x() + px * 5, c.y() + py * 5),
            QPointF(c.x() - px * 5, c.y() - py * 5),
        )

    def crows_foot():
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



class ShapePreviewPopup(QFrame):
    """
    Floating popup that shows a large, realistic preview of an ERD shape.
    Used for the draw.io-style hover feature.
    """
    def __init__(self, parent=None):
        # Use ToolTip flag instead of Window to ensure it stays on top and is transient
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(160, 120)
        self.setStyleSheet("""
            ShapePreviewPopup {
                background: white;
                border: 1px solid #94A3B8;
                border-radius: 4px;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.img_label)
        
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")
        self.layout.addWidget(self.title_label)

    def set_preview(self, comp_type, label_text):
        self.title_label.setText(label_text)
        pix = _make_shape_preview(comp_type)
        # Scale it up slightly for the preview popup
        scaled = pix.scaled(140, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.img_label.setPixmap(scaled)


# ---------------------------------------------------------------------------
# Palette panel
# ---------------------------------------------------------------------------

class ERDPalette(QFrame):
    """
    Collapsible vertical panel containing a 3-column grid of ElementTiles.

    Collapsed: shows only a chevron icon (36 px wide).
    Expanded:  shows "Elements" header + full grid (288 px wide).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(COLLAPSED_W)
        
        # Hover Preview Popup - parent it to this palette for correct lifecycle
        self._preview_popup = ShapePreviewPopup(parent=self)
        
        self.setStyleSheet("""
            ERDPalette {
                background-color: #F8FAFC;
                border-right: 1px solid #E2E8F0;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Header button ---
        self.header_btn = QPushButton()
        self.header_btn.setObjectName("headerBtn")
        self.header_btn.setIcon(qta.icon("fa5s.chevron-right", color="#374151"))
        self.header_btn.setIconSize(QSize(12, 12))
        self.header_btn.setFixedHeight(36)
        self.header_btn.clicked.connect(self.toggle_collapse)
        self.header_btn.setStyleSheet("""
            QPushButton#headerBtn {
                text-align: left;
                font-weight: bold;
                font-size: 12px;
                padding: 0px 8px;
                color: #1E293B;
                border: none;
                border-bottom: 1px solid #E2E8F0;
                background: #F1F5F9;
                border-radius: 0px;
            }
            QPushButton#headerBtn:hover { background: #E2E8F0; }
        """)
        outer.addWidget(self.header_btn)

        # --- Scroll area for the grid ---
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(self._grid_container)
        grid_layout.setContentsMargins(6, 8, 6, 8)
        grid_layout.setSpacing(6)

        for label, comp_type, icon_name, icon_color, row, col in ELEMENTS:
            tile = ElementTile(label, comp_type, icon_name, icon_color, palette=self)
            grid_layout.addWidget(tile, row, col)

        self._grid_container.hide()
        outer.addWidget(self._grid_container)
        outer.addStretch()

    # ------------------------------------------------------------------

    def toggle_collapse(self):
        if self._grid_container.isVisible():
            self._grid_container.hide()
            self.setFixedWidth(COLLAPSED_W)
            self.header_btn.setText("")
            self.header_btn.setIcon(qta.icon("fa5s.chevron-right", color="#374151"))
        else:
            self._grid_container.show()
            self.setFixedWidth(EXPANDED_W)
            self.header_btn.setText("  Elements")
            self.header_btn.setIcon(qta.icon("fa5s.chevron-down", color="#374151"))

    # ------------------------------------------------------------------
    # Preview Popup Management
    # ------------------------------------------------------------------

    def show_preview(self, comp_type, pos):
        """Called by tiles to trigger the draw.io-style preview."""
        # Find label for the comp_type
        label = comp_type.replace("_", " ").title()
        for element_label, ct, *_ in ELEMENTS:
            if ct == comp_type:
                label = element_label
                break
        
        self._preview_popup.set_preview(comp_type, label)
        self._preview_popup.move(pos)
        self._preview_popup.show()

    def hide_preview(self):
        self._preview_popup.hide()
