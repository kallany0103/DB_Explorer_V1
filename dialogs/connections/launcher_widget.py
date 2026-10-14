from __future__ import annotations

import os
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QEnterEvent, QIcon, QKeyEvent, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import db
from ui.components import SecondaryButton


class EngineCard(QFrame):
    """Sleek, clickable card representing a database engine."""

    clicked = Signal(str)

    def __init__(
        self,
        code: str,
        title: str,
        subtitle: str,
        icon_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.code = code
        self.title_text = title
        self.subtitle_text = subtitle
        self.is_selected = False

        self.setObjectName("engineCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(72)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Engine Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(30, 30)
        self.icon_label.setScaledContents(True)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        resolved_icon = db.resource_path(icon_path)
        if os.path.exists(resolved_icon):
            self.icon_label.setPixmap(QIcon(resolved_icon).pixmap(30, 30))
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text Stack
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("engineCardTitle")
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_layout.addWidget(self.title_lbl)

        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setObjectName("engineCardSubtitle")
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_layout.addWidget(self.subtitle_lbl)

        layout.addLayout(text_layout, 1)

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)

    def set_card_selected(self, selected: bool) -> None:
        self.is_selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.code)
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.code)
        else:
            super().keyPressEvent(event)


class LauncherWidget(QWidget):
    """Screen 1: Minimalist Google-style engine launcher with search and cards."""

    engine_selected = Signal(str)
    cancelled = Signal()

    ENGINE_DEFS = [
        ("ORACLE", "Oracle", "Service name, SID, TNS or wallet", "assets/oracle.svg"),
        ("POSTGRES", "PostgreSQL", "Host, port, user and password", "assets/postgresql.svg"),
        ("SQLITE", "SQLite", "An existing database file on this machine", "assets/sqlite.svg"),
        ("SERVICENOW", "ServiceNow", "Instance URL, user and password", "assets/servicenow.svg"),
        ("CSV", "CSV / Flat Files", "A directory of CSV or TSV files on this machine", "assets/csv.svg"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cards: list[EngineCard] = []
        self.selected_index: int = -1

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 18)
        main_layout.setSpacing(14)

        # 1. Search Bar Frame (Google-style smooth pill search bar)
        self.search_frame = QFrame()
        self.search_frame.setObjectName("launcherSearchFrame")
        self.search_frame.mousePressEvent = lambda _e: self.search_input.setFocus()
        search_layout = QHBoxLayout(self.search_frame)
        search_layout.setContentsMargins(12, 0, 12, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel()
        search_icon.setFixedSize(16, 16)
        search_icon.setScaledContents(True)
        search_icon_path = db.resource_path("assets/search.svg")
        if os.path.exists(search_icon_path):
            search_icon.setPixmap(QIcon(search_icon_path).pixmap(16, 16))
        search_icon.mousePressEvent = lambda _e: self.search_input.setFocus()
        search_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("launcherSearchEdit")
        self.search_input.setPlaceholderText("Search database engines...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.installEventFilter(self)
        search_layout.addWidget(self.search_input)

        main_layout.addWidget(self.search_frame)

        # 2. Section Header: DATABASES with horizontal line
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 2, 0, 2)
        header_layout.setSpacing(10)

        db_header = QLabel("DATABASES")
        db_header.setObjectName("launcherSectionHeader")
        header_layout.addWidget(db_header)

        header_line = QFrame()
        header_line.setFrameShape(QFrame.Shape.HLine)
        header_line.setFrameShadow(QFrame.Shadow.Plain)
        header_line.setObjectName("launcherHeaderLine")
        header_layout.addWidget(header_line, 1)

        main_layout.addLayout(header_layout)

        # 3. Scrollable Grid Area (3 items per row)
        scroll = QScrollArea()
        scroll.setObjectName("launcherScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setObjectName("launcherScrollContent")
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        self.grid_widget = QWidget()
        self.grid_widget.setObjectName("launcherGridWidget")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setColumnStretch(2, 1)

        for i, (code, title, subtitle, icon) in enumerate(self.ENGINE_DEFS):
            card = EngineCard(code, title, subtitle, icon, self.grid_widget)
            card.clicked.connect(self.engine_selected.emit)
            row = i // 3
            col = i % 3
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)

        self.content_layout.addWidget(self.grid_widget)
        self.content_layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # 4. Footer
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.addStretch()

        cancel_btn = SecondaryButton("Cancel")
        cancel_btn.clicked.connect(self.cancelled.emit)
        footer_layout.addWidget(cancel_btn)

        main_layout.addLayout(footer_layout)

    def _select_card(self, index: int) -> None:
        visible_cards = [c for c in self.cards if not c.isHidden()]
        if not visible_cards or index < 0:
            self.selected_index = -1
            for card in self.cards:
                card.set_card_selected(False)
            return
        index = max(0, min(index, len(visible_cards) - 1))
        self.selected_index = index
        for i, card in enumerate(visible_cards):
            card.set_card_selected(i == index)

    def _on_search_text_changed(self, text: str) -> None:
        query = text.strip().lower()
        for card in self.cards:
            matches = (
                not query
                or query in card.code.lower()
                or query in card.title_text.lower()
                or query in card.subtitle_text.lower()
            )
            card.setVisible(matches)

        if query:
            self._select_card(0)
        else:
            self._select_card(-1)

    def _set_search_focused(self, focused: bool) -> None:
        if hasattr(self, "search_frame"):
            self.search_frame.setProperty("focused", "true" if focused else "false")
            self.search_frame.style().unpolish(self.search_frame)
            self.search_frame.style().polish(self.search_frame)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.search_input:
            if event.type() == QEvent.Type.FocusIn:
                self._set_search_focused(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_search_focused(False)
            elif event.type() == QEvent.Type.KeyPress:
                key_event = event
                key = key_event.key()

                visible_cards = [c for c in self.cards if not c.isHidden()]
                if key == Qt.Key.Key_Down:
                    if visible_cards:
                        if self.selected_index < 0:
                            next_idx = 0
                        else:
                            next_idx = (self.selected_index + 1) % len(visible_cards)
                        self._select_card(next_idx)
                    return True
                elif key == Qt.Key.Key_Up:
                    if visible_cards:
                        if self.selected_index < 0:
                            prev_idx = len(visible_cards) - 1
                        else:
                            prev_idx = (self.selected_index - 1) % len(visible_cards)
                        self._select_card(prev_idx)
                    return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if visible_cards and self.selected_index >= 0:
                        chosen = visible_cards[self.selected_index]
                        self.engine_selected.emit(chosen.code)
                        return True
                elif key == Qt.Key.Key_Escape:
                    if self.search_input.text():
                        self.search_input.clear()
                        return True
                    else:
                        self.cancelled.emit()
                        return True

        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.search_input.setFocus()
        self._set_search_focused(True)

    def reset_state(self) -> None:
        self.search_input.clear()
        self.search_input.setFocus()
        self._set_search_focused(True)
        self._select_card(-1)
