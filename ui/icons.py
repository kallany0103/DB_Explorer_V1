from __future__ import annotations

from typing import Any, Optional, Union
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication
import qtawesome as qta


# --- Semantic Palette Constants ---
COLOR_PRIMARY_BLUE = "#2563EB"    # Database roots, active connections
COLOR_AMBER = "#D97706"           # Schemas, namespaces, group folders
COLOR_EMERALD_GREEN = "#16A34A"   # Tables, Execute / Run, Commit
COLOR_TEAL = "#0D9488"            # Views, virtual data objects
COLOR_GOLD = "#EAB308"            # Primary Keys, highlights
COLOR_SLATE = "#64748B"           # Foreign Keys, columns, neutral meta
COLOR_INDIGO = "#6366F1"          # Indexes, query optimization
COLOR_PURPLE = "#8B5CF6"          # Routines, Functions, AI assistants
COLOR_CRIMSON = "#DC2626"         # Stop / Cancel, Rollback, Delete / Clear
COLOR_TEXT_NEUTRAL = "#475569"    # Default toolbar icon color (slate-600)
COLOR_TEXT_DARK = "#94A3B8"       # Dark mode toolbar icon color (slate-400)


class AppIcons:
    """Canonical catalog of application icon identifiers and default colors.

    Each entry is a tuple of (icon_identifier, optional_color).
    """

    # File & Worksheet Actions
    OPEN_FILE = ("msc.folder-opened", None)
    SAVE = ("msc.save", None)
    EXECUTE = ("msc.play", COLOR_EMERALD_GREEN)
    EXECUTE_NEW_TAB = ("msc.run-all", COLOR_EMERALD_GREEN)
    CANCEL = ("msc.debug-stop", COLOR_CRIMSON)
    DESCRIBE_OBJECT = ("msc.info", None)
    QUICK_DESCRIBE = ("msc.zoom-in", None)
    DESCRIBE_QUERY = ("msc.table", None)
    EXPLAIN_AI = ("msc.sparkle", COLOR_PURPLE)
    OPTIMIZE_QUERY = ("msc.zap", COLOR_INDIGO)
    OPTIMIZE_BATCH = ("msc.list-tree", COLOR_INDIGO)
    FORMAT_SQL = ("msc.code", None)

    # Edit & Clipboard Actions
    UNDO = ("msc.discard", None)
    REDO = ("msc.redo", None)
    CUT = ("ph.scissors", None)
    COPY = ("msc.copy", None)
    PASTE = ("msc.clippy", None)
    SELECT_ALL = ("msc.selection", None)
    FIND = ("msc.search", None)
    REPLACE = ("msc.replace", None)
    GOTO_LINE = ("msc.go-to-file", None)
    COMMENT = ("msc.comment", None)
    UNCOMMENT = ("msc.comment-unresolved", None)
    UPPERCASE = ("msc.case-sensitive", None)
    LOWERCASE = ("msc.whole-word", None)
    INITIAL_CAPS = ("msc.text-size", None)
    CLEAR_ALL = ("msc.trash", COLOR_CRIMSON)

    # Transaction Actions
    COMMIT = ("msc.check", COLOR_EMERALD_GREEN)
    ROLLBACK = ("msc.debug-restart", COLOR_CRIMSON)
    AUTOCOMMIT = ("msc.unlock", None)

    # Database & Schema Tree Objects
    DATABASE = ("msc.database", COLOR_PRIMARY_BLUE)
    SCHEMA = ("msc.folder-library", COLOR_AMBER)
    TABLE = ("msc.table", COLOR_EMERALD_GREEN)
    VIEW = ("msc.eye", COLOR_TEAL)
    COLUMN = ("msc.symbol-variable", COLOR_SLATE)
    PRIMARY_KEY = ("msc.key", COLOR_GOLD)
    FOREIGN_KEY = ("msc.link", COLOR_SLATE)
    INDEX = ("msc.zap", COLOR_INDIGO)
    FUNCTION = ("msc.symbol-method", COLOR_PURPLE)
    REFRESH = ("msc.refresh", None)
    FILTER = ("msc.filter", None)
    SETTINGS = ("msc.gear", None)


_icon_cache: dict[tuple[str, str], QIcon] = {}

_FALLBACK_GLYPHS: dict[str, str] = {
    "msc.scissors": "ph.scissors",
    "ph.scissors": "mdi6.content-cut",
    "msc.selection": "msc.checklist",
}


def is_dark_theme() -> bool:
    """Determines if the active UI theme has a dark background."""
    app = QApplication.instance()
    if not app:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def get_icon(
    spec: Union[tuple[str, Optional[str]], str],
    color: Optional[str] = None,
    is_dark: Optional[bool] = None,
    **kwargs: Any,
) -> QIcon:
    """Returns a theme-adaptive vector QIcon.

    Args:
        spec: A tuple of (icon_name, default_color) from AppIcons, or a glyph string.
        color: Optional override color. If None, uses spec's default color or theme neutral.
        is_dark: Optional theme override. If None, auto-detected from the application palette.
        **kwargs: Additional parameters passed to `qtawesome.icon`.
    """
    if isinstance(spec, tuple):
        glyph_name, default_color = spec
    else:
        glyph_name, default_color = spec, None

    resolved_color = color or default_color
    if resolved_color is None:
        dark_active = is_dark if is_dark is not None else is_dark_theme()
        resolved_color = COLOR_TEXT_DARK if dark_active else COLOR_TEXT_NEUTRAL

    cache_key = (glyph_name, resolved_color)
    if not kwargs and cache_key in _icon_cache:
        return _icon_cache[cache_key]

    try:
        icon = qta.icon(glyph_name, color=resolved_color, **kwargs)
    except Exception:
        fallback = _FALLBACK_GLYPHS.get(glyph_name)
        if fallback:
            try:
                icon = qta.icon(fallback, color=resolved_color, **kwargs)
            except Exception:
                icon = QIcon()
        else:
            icon = QIcon()

    if not kwargs:
        _icon_cache[cache_key] = icon
    return icon
