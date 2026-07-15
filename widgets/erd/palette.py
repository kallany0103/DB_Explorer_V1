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
from PySide6.QtCore import Qt, QSize, QMimeData, QPoint
from PySide6.QtGui import QDrag, QPixmap
from widgets.erd.palette_icons import _make_shape_preview, _make_tile_icon, _ERD_TILE_SHAPE_TYPES


# ---------------------------------------------------------------------------
# Tile definition
# ---------------------------------------------------------------------------

ELEMENTS = [
    # (label,           comp_type,              icon_name,                   icon_color,  row, col)
    ("Table",           "table",                "fa5s.table",                "#1A73E8",   0,   0),
    ("Table + FK",      "table_fk",             "mdi.table-key",             "#1A73E8",   0,   1),
    ("Column",          "column",               "mdi.table-column",          "#34A853",   0,   2),
    ("Entity",          "entity",               "fa5s.square",               "#2563EB",   1,   0),
    ("Weak Entity",     "weak_entity",          "fa5s.border-all",           "#6366F1",   1,   1),
    ("Attribute",       "attribute",            "fa5s.circle",               "#22C55E",   1,   2),
    ("Key Attribute",   "attribute_key",        "mdi.circle-edit-outline",   "#16A34A",   2,   0),
    ("Partial Key",     "attribute_partial",    "mdi.circle-double",         "#15803D",   2,   1),
    ("Multi-valued",    "attribute_multi",      "fa5s.dot-circle",           "#16A34A",   2,   2),
    ("Derived Attr",    "attribute_derived",    "fa5s.circle-notch",         "#4ADE80",   3,   0),
    ("Relationship",    "relationship_diamond", "fa5s.square",               "#F59E0B",   3,   1),
    ("Subject Area",    "subject_area",         "fa5s.object-group",         "#8B5CF6",   3,   2),
    ("Note",            "note",                 "fa5s.sticky-note",          "#D4A100",   4,   0),
    ("1-1 Relation",    "relationship:one-to-one",   "mdi6.relation-one-to-one",   "#5F6368", 4, 1),
    ("1-M Relation",    "relationship:one-to-many",  "mdi6.relation-one-to-many",  "#5F6368", 4, 2),
    ("M-1 Relation",    "relationship:many-to-one",  "mdi6.relation-many-to-one",  "#5F6368", 5, 0),
    ("M-M Relation",    "relationship:many-to-many", "mdi6.relation-many-to-many", "#5F6368", 5, 1),
    ("Plain Link",      "relationship:none",         "mdi6.minus",                "#64748B", 5, 2),
]

TILE_W = 88
TILE_H = 44
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



        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        if comp_type in _ERD_TILE_SHAPE_TYPES:
            pix = _make_tile_icon(comp_type, ICON_SIZE)
        else:
            try:
                scale = 1.2 if comp_type == "table_fk" else 1.0
                pix = qta.icon(icon_name, color=icon_color, scale_factor=scale).pixmap(ICON_SIZE, ICON_SIZE)
            except Exception:
                pix = QPixmap(ICON_SIZE, ICON_SIZE)
                pix.fill(Qt.GlobalColor.transparent)
        icon_lbl.setPixmap(pix)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(icon_lbl)

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
        self.update()




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

