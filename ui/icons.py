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
    DESCRIBE_OBJECT = ("msc.inspect", None)
    QUICK_DESCRIBE = ("msc.eye", None)
    DESCRIBE_QUERY = ("msc.symbol-structure", None)
    EXPLAIN_AI = ("msc.robot", COLOR_PURPLE)
    AI_ASSISTANT = ("msc.robot", COLOR_PURPLE)
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
    SEARCH = ("msc.search", None)
    FIND = SEARCH
    REPLACE = ("msc.replace", None)
    GOTO_LINE = ("msc.go-to-file", None)
    COMMENT = ("msc.comment", None)
    UNCOMMENT = ("msc.comment-unresolved", None)
    UPPERCASE = ("msc.case-sensitive", None)
    LOWERCASE = ("msc.whole-word", None)
    INITIAL_CAPS = ("msc.text-size", None)
    CLEAR_ALL = ("msc.trash", COLOR_CRIMSON)

    # Transaction Actions
    COMMIT = ("mdi6.database-check-outline", COLOR_EMERALD_GREEN)
    ROLLBACK = ("mdi6.database-arrow-left-outline", COLOR_CRIMSON)
    AUTOCOMMIT = ("msc.unlock", None)
    EXECUTING = ("ph.hourglass-medium", COLOR_AMBER)
    STATUS_EXECUTING = EXECUTING

    # Database & Schema Tree Objects
    NEW_CONNECTION = ("msc.plug", COLOR_PRIMARY_BLUE)
    ADD_CONNECTION = NEW_CONNECTION
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

_LEGACY_MAP: dict[str, str] = {
    # MDI to Codicon / Phosphor
    "mdi.pencil-outline": "msc.edit",
    "mdi.square-edit-outline": "msc.edit",
    "mdi.delete-outline": "msc.trash",
    "mdi.delete-sweep-outline": "msc.trash",
    "mdi.folder-plus-outline": "msc.new-folder",
    "mdi.folder-edit-outline": "msc.edit",
    "mdi.folder-remove-outline": "msc.trash",
    "mdi.file-plus-outline": "msc.new-file",
    "mdi.database-plus": "msc.database",
    "mdi.cloud-plus-outline": "msc.cloud",
    "mdi.database-search": "msc.search",
    "mdi.console": "msc.terminal",
    "mdi.magnify": "msc.search",
    "mdi.refresh": "msc.sync",
    "mdi.sync": "msc.sync",
    "mdi.arrow-collapse-all": "msc.collapse-all",
    "mdi.database-cog": "msc.settings",
    "mdi.eye-plus": "msc.eye",
    "mdi.script-text-outline": "msc.file-code",
    "mdi.lightning-bolt": "msc.zap",
    "mdi.lightning-bolt-outline": "msc.zap",
    "mdi.connection": "msc.link",
    "mdi.plus-circle-outline": "msc.plus",
    "mdi.table": "msc.table",
    "mdi.table-column": "msc.symbol-variable",
    "mdi.key": "msc.key",
    "mdi.link-variant": "msc.link",
    "mdi.link-off": "msc.debug-disconnect",
    "mdi.star": "msc.star-full",
    "mdi.download": "msc.cloud-download",
    "mdi.chart-line": "msc.pulse",
    "mdi.text-box-outline": "msc.file-text",
    "mdi.clipboard-text-outline": "msc.checklist",
    "mdi.server-network": "msc.server",
    "mdi.account-group": "msc.organization",
    "mdi.domain": "msc.extensions",
    "mdi.database": "msc.database",
    "mdi.label-outline": "msc.tag",
    "mdi.card-text-outline": "msc.layout-sidebar-right",
    "mdi.format-line-style": "msc.dash",
    "mdi.transit-connection-variant": "msc.git-commit",
    "mdi.block-helper": "msc.circle-slash",
    "mdi.arrow-right": "msc.arrow-right",
    "mdi.arrow-left": "msc.arrow-left",
    "mdi.arrow-left-right": "msc.arrow-both",
    "mdi.minus": "msc.dash",
    "mdi.dots-horizontal": "ph.dots-three-outline",
    "mdi.dots-horizontal-circle-outline": "ph.dots-three",
    "mdi6.relation-one-to-one": "msc.arrow-both",
    "mdi6.relation-one-to-many": "msc.arrow-right",
    "mdi6.relation-many-to-one": "msc.arrow-left",
    "mdi6.relation-many-to-many": "msc.git-compare",
    "mdi6.minus": "msc.dash",
    # FA5 to Codicon / Phosphor
    "fa5s.search": "msc.search",
    "fa5s.search-plus": "msc.zoom-in",
    "fa5s.search-minus": "msc.zoom-out",
    "fa5s.expand-arrows-alt": "msc.screen-full",
    "fa5s.eye": "msc.eye",
    "fa5s.eye-slash": "msc.eye-closed",
    "fa5s.check-circle": "msc.check",
    "fa5s.check-square": "msc.check",
    "fa5.square": "ph.square",
    "fa5s.circle": "ph.circle",
    "fa5s.dot-circle": "ph.circles-three",
    "fa5s.circle-notch": "ph.circle-notch",
    "fa5s.times-circle": "msc.error",
    "fa5s.info-circle": "msc.info",
    "fa5s.exclamation-circle": "msc.warning",
    "fa5s.exclamation-triangle": "msc.warning",
    "fa5s.trash-alt": "msc.trash",
    "fa5s.question-circle": "msc.question",
    "fa5s.file-alt": "msc.file-text",
    "fa5s.file-pdf": "msc.file-pdf",
    "fa5s.file-export": "msc.cloud-download",
    "fa5s.file-code": "msc.file-code",
    "fa5s.folder-open": "msc.folder-opened",
    "fa5s.database": "msc.database",
    "fa5s.server": "msc.server",
    "fa5s.terminal": "msc.terminal",
    "fa5s.sliders-h": "msc.settings",
    "fa5s.sitemap": "msc.type-hierarchy",
    "fa5s.magic": "msc.sparkle",
    "fa5s.plus": "msc.plus",
    "fa5s.history": "msc.history",
    "fa5s.copy": "msc.copy",
    "fa5s.times": "msc.close",
    "fa5s.arrow-up": "msc.arrow-up",
    "fa5s.comment-dots": "msc.comment-discussion",
    "fa5s.undo": "msc.discard",
    "fa5s.redo": "msc.redo",
    "fa5s.save": "msc.save",
    "fa5s.code": "msc.code",
    "fa5s.key": "msc.key",
    "fa5s.columns": "msc.symbol-variable",
    "fa5s.table": "msc.table",
    "fa5s.layer-group": "msc.folder-library",
    "fa5s.tag": "msc.tag",
    "fa5s.edit": "msc.edit",
    "fa5s.stop": "msc.debug-stop",
    "fa5s.pause": "msc.debug-pause",
    "fa5s.play": "msc.play",
    "fa5s.chevron-right": "msc.chevron-right",
    "fa5s.chevron-down": "msc.chevron-down",
    "fa5s.chevron-left": "msc.chevron-left",
    "fa5s.thumbtack": "msc.pin",
    "fa5s.image": "msc.file-media",
    "fa5s.vector-square": "msc.symbol-misc",
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

    if glyph_name in _LEGACY_MAP:
        glyph_name = _LEGACY_MAP[glyph_name]

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
