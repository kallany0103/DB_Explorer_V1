# Relationship types and notations used throughout the ERD diagram
RELATION_TYPES = {
    'one-to-one': {'label': '1-1', 'icon': 'mdi6.relation-one-to-one', 'source': 'one', 'target': 'one'},
    'one-to-many': {'label': '1-M', 'icon': 'mdi6.relation-one-to-many', 'source': 'one', 'target': 'many'},
    'many-to-one': {'label': 'M-1', 'icon': 'mdi6.relation-many-to-one', 'source': 'many', 'target': 'one'},
    'many-to-many': {'label': 'M-M', 'icon': 'mdi6.relation-many-to-many', 'source': 'many', 'target': 'many'},
    'none': {'label': 'None', 'icon': 'mdi6.minus', 'source': 'none', 'target': 'none'},
}

# Crow's-foot notation geometry — pixel offsets used when drawing end markers.
# "origin" is the point where the line meets the table edge.
CF_BAR_NEAR: int = 5        # distance from origin to the near perpendicular bar
CF_BAR_FAR: int = 13        # distance from origin to the far perpendicular bar
CF_FOOT_TIP: int = 0        # distance from origin to the crow's-foot prong tip
CF_FOOT_SPREAD: int = 12    # distance from origin to the crow's-foot prong base
CF_FOOT_WIDTH: int = 6      # half-width of the crow's-foot spread (each side)
CF_CIRCLE_ONE: int = 14     # distance from origin to the "zero-or-one" circle centre
CF_CIRCLE_MANY: int = 16    # distance from origin to the "zero-or-many" circle centre
CF_CIRCLE_RADIUS: float = 3.5   # radius of the optional-participation circle

# Hit-test constants
PORT_HIT_RADIUS_SQ: int = 400   # squared radius for port click detection (20 px radius)
DRAG_ENDPOINT_RADIUS: int = 25  # pixel radius for drag-endpoint hit detection at connection ends

# View interaction constants
NUDGE_STEP: int = 20            # arrow-key nudge delta in pixels
DUPLICATE_OFFSET: int = 40      # pixel offset applied when duplicating a table item

# Self-loop path geometry
SELF_LOOP_STUB: int = 30            # stub length before the loop curve starts
SELF_LOOP_LOOP_DIST_BASE: int = 30  # base lateral offset of the loop control points
SELF_LOOP_LOOP_DIST_STEP: int = 10  # additional offset per column index

# Animation constants for flow-mode marching dashes
FLOW_ANIM_DURATION_MS: int = 800    # full dash-cycle duration in milliseconds
FLOW_ANIM_END_VALUE: float = 14.0   # one full dash-cycle offset (dash=8 + gap=6)
