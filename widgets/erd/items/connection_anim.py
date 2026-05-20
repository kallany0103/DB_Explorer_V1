"""Animation and line-style mixin for ERDConnectionItem.

Extracted to satisfy the SRP: ERDConnectionItem was ~935 lines because it
combined path routing, painting, interaction, animation, and menus.  This
module owns exclusively the animation state-machine and line-style management.
"""
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property, Qt
from PySide6.QtGui import QPen, QColor

from widgets.erd.constants import FLOW_ANIM_DURATION_MS, FLOW_ANIM_END_VALUE


class ERDConnectionAnimMixin:
    """Mixin that adds animation state, dash-offset property, and line-style
    management to a QGraphicsPathItem subclass.

    The host class must already have ``self.pen()`` / ``self.setPen()`` and
    ``self.update()`` (all provided by QGraphicsPathItem).
    """

    def _init_anim(self) -> None:
        """Call from the host ``__init__`` after QObject.__init__ completes."""
        self._line_style: str = "solid"
        self._flow_mode: str = "none"
        self._is_animated: bool = False
        self._dash_offset: float = 0.0

        self._animation = QPropertyAnimation(self, b"dash_offset")
        self._animation.setDuration(FLOW_ANIM_DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(FLOW_ANIM_END_VALUE)
        self._animation.setLoopCount(-1)
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)

    def get_dash_offset(self) -> float:
        return self._dash_offset

    def set_dash_offset(self, val: float) -> None:
        self._dash_offset = val
        self.update()

    dash_offset = Property(float, get_dash_offset, set_dash_offset)

    def set_animated(self, animated: bool) -> None:
        self._is_animated = animated
        if animated:
            self._animation.start()
        else:
            self._animation.stop()
            self._dash_offset = 0.0
        self.update()

    def set_flow_mode(self, mode: str) -> None:
        self._flow_mode = mode
        self.update()

    def set_line_style(self, style: str) -> None:
        self._line_style = style
        pen = self.pen()
        if style == "dashed":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif style == "dotted":
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)
        self.update()

    def _apply_line_style_to_pen(self, pen: QPen, hovered: bool = False) -> QPen:
        if self._line_style == "dashed":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif self._line_style == "dotted":
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)

        if hovered:
            pen.setColor(QColor("#1A73E8"))
            if self._line_style == "solid":
                pen.setWidthF(2.5)
        else:
            pen.setColor(self.pen().color())

        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        return pen
