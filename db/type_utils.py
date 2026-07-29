"""db/type_utils.py

Standalone type-normalization utilities.

This module has NO imports from within the project so it can be safely
imported by any layer (db, workers, widgets) without creating circular
import cycles.
"""


def normalize_type(raw_type: str) -> str:
    """Standardizes database types for human-readable display."""
    if not raw_type:
        return ""
    t = raw_type.lower().strip()

    mapping = {
        'character varying': 'VARCHAR',
        'character': 'CHAR',
        'integer': 'INT',
        'bigint': 'BIGINT',
        'smallint': 'SMALLINT',
        'boolean': 'BOOL',
        'double precision': 'FLOAT8',
        'real': 'FLOAT4',
        'timestamp without time zone': 'TIMESTAMP',
        'timestamp with time zone': 'TIMESTAMPTZ',
        'time without time zone': 'TIME',
        'numeric': 'DECIMAL',
        'jsonb': 'JSONB',
        'json': 'JSON',
        'uuid': 'UUID',
        'text': 'TEXT',
    }

    for key in sorted(mapping.keys(), key=len, reverse=True):
        if t.startswith(key):
            return t.replace(key, mapping[key]).upper()

    return raw_type.upper()
