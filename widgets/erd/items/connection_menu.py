"""Context-menu builder for ERDConnectionItem.

Extracted to satisfy the SRP.  This module owns exclusively the construction
of the right-click QMenu; it has no awareness of path routing or painting.
"""
import qtawesome as qta
from PySide6.QtWidgets import QMenu


_CONTEXT_MENU_STYLE = """
    QMenu {
        min-width: 220px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 4px;
        font-family: 'Segoe UI';
    }
    QMenu::item {
        padding: 7px 16px 7px 10px;
        font-size: 10pt;
        color: #1f2937;
        border-radius: 4px;
        margin: 1px 4px;
    }
    QMenu::item:selected  { background: #eff6ff; color: #1d4ed8; }
    QMenu::item:checked   { background: #dbeafe; color: #1d4ed8; font-weight: 600; }
    QMenu::item:disabled  {
        color: #9ca3af;
        font-size: 8pt;
        font-weight: 700;
        padding: 6px 16px 2px 10px;
        background: transparent;
        margin: 0px 4px;
    }
    QMenu::separator { height: 1px; background: #e5e7eb; margin: 4px 8px; }
    QMenu::right-arrow { width: 8px; height: 8px; }
"""


def _make_menu(parent=None) -> QMenu:
    m = QMenu(parent)
    m.setStyleSheet(_CONTEXT_MENU_STYLE)
    return m


def _add_header(menu: QMenu, text: str) -> None:
    action = menu.addAction(text.upper())
    action.setEnabled(False)


def build_connection_context_menu(item) -> QMenu:
    """Build and return the context QMenu for an ERDConnectionItem.

    Parameters
    ----------
    item:
        The ``ERDConnectionItem`` instance the menu is being built for.

    Returns
    -------
    QMenu
        A fully populated, styled QMenu ready for ``menu.exec()``.
    """
    menu = _make_menu()

    # ── Section: Cardinality ──────────────────────────────────────
    _add_header(menu, "Cardinality")
    for type_key, info in item.RELATION_TYPES.items():
        action = menu.addAction(qta.icon(info['icon'], color='#5F6368'), info['label'])
        action.setCheckable(True)
        action.setChecked(type_key == item.relation_type)
        action.triggered.connect(lambda checked, k=type_key: item.set_relation_type(k))

    # ── Section: Label ────────────────────────────────────────────
    menu.addSeparator()
    _add_header(menu, "Label")
    if item._label.isVisible():
        menu.addAction(
            qta.icon('fa5s.edit', color='#374151'), "Edit Label"
        ).triggered.connect(item._open_label_editor)
        menu.addAction(
            qta.icon('fa5s.times', color='#374151'), "Clear Label"
        ).triggered.connect(lambda: item.set_label(""))
    else:
        menu.addAction(
            qta.icon('fa5s.tag', color='#374151'), "Add Label"
        ).triggered.connect(item._open_label_editor)

    # ── Section: Actions ──────────────────────────────────────────
    menu.addSeparator()
    _add_header(menu, "Actions")
    menu.addAction(
        qta.icon('mdi.link-off', color='#374151'), "Detach Relationship"
    ).triggered.connect(item.detach_relationship)

    # ── Section: Style & Animation ────────────────────────────────
    menu.addSeparator()
    _add_header(menu, "Style & Animation")

    style_menu = _make_menu(menu)
    style_menu.setTitle("Line Style")
    style_menu.setIcon(qta.icon('mdi.format-line-style', color='#374151'))
    _style_icons = {
        'solid':  ('mdi.minus',                          '#374151'),
        'dashed': ('mdi.dots-horizontal',                '#374151'),
        'dotted': ('mdi.dots-horizontal-circle-outline', '#374151'),
    }
    for style in ['solid', 'dashed', 'dotted']:
        ico, col = _style_icons[style]
        act = style_menu.addAction(qta.icon(ico, color=col), style.capitalize())
        act.setCheckable(True)
        act.setChecked(item._line_style == style)
        act.triggered.connect(lambda checked, s=style: item.set_line_style(s))
    menu.addMenu(style_menu)

    flow_menu = _make_menu(menu)
    flow_menu.setTitle("Flow Direction")
    flow_menu.setIcon(qta.icon('mdi.transit-connection-variant', color='#374151'))
    _flow_icons = {
        'none':          ('mdi.block-helper',               '#374151'),
        'forward':       ('mdi.arrow-right',                '#374151'),
        'backward':      ('mdi.arrow-left',                 '#374151'),
        'bidirectional': ('mdi.arrow-left-right',           '#374151'),
    }
    for mode in ['none', 'forward', 'backward', 'bidirectional']:
        ico, col = _flow_icons[mode]
        act = flow_menu.addAction(qta.icon(ico, color=col), mode.capitalize())
        act.setCheckable(True)
        act.setChecked(item._flow_mode == mode)
        act.triggered.connect(lambda checked, m=mode: item.set_flow_mode(m))
    menu.addMenu(flow_menu)

    anim_icon = 'fa5s.pause' if item._is_animated else 'fa5s.play'
    anim_act = menu.addAction(qta.icon(anim_icon, color='#374151'), "Animate Flow")
    anim_act.setCheckable(True)
    anim_act.setChecked(item._is_animated)
    anim_act.triggered.connect(item.set_animated)

    # ── Destructive ───────────────────────────────────────────────
    menu.addSeparator()
    remove_act = menu.addAction(
        qta.icon("fa5s.trash-alt", color="#DC2626"), "Remove Relationship"
    )
    remove_act.triggered.connect(item._remove_self)

    return menu
