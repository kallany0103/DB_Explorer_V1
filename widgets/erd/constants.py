# Relationship types and notations used throughout the ERD diagram
RELATION_TYPES = {
    'one-to-one': {'label': '1-1', 'icon': 'mdi6.relation-one-to-one', 'source': 'one', 'target': 'one'},
    'one-to-many': {'label': '1-M', 'icon': 'mdi6.relation-one-to-many', 'source': 'one', 'target': 'many'},
    'many-to-one': {'label': 'M-1', 'icon': 'mdi6.relation-many-to-one', 'source': 'many', 'target': 'one'},
    'many-to-many': {'label': 'M-M', 'icon': 'mdi6.relation-many-to-many', 'source': 'many', 'target': 'many'},
    'none': {'label': 'None', 'icon': 'mdi6.minus', 'source': 'none', 'target': 'none'},
}
