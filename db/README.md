# DB Package

Database access, schema retrieval, and persistence helpers.

## Purpose
- Centralize DB connection creation and DB operations.
- Provide read/write helpers for app state (connections, hierarchy, history).

## Structure
- `db_connections.py`: creates SQLite/Postgres/Oracle/ServiceNow connections and shared DB constants.
- `db_retrieval.py`: read operations for connections/hierarchy.
- `result_metadata.py`: result-set column metadata resolution for PostgreSQL/SQLite query outputs.
- `schema_retrieval.py`: schema introspection functions.
- `db_modifications.py`: insert/update/delete operations and query-history persistence.
- `__init__.py`: package API exports.

## Usage Guidelines
- Keep SQL/data operations in this package (not in UI modules).
- Keep return shapes stable for callers in `widgets/`.
- Add provider-specific retrieval/modification helpers in focused files, then export from `__init__.py`.
- Keep connection payload assumptions explicit (`code`, host/db fields, or db_path).

## Error Handling
- Raise/return clear error information to UI managers.
- Avoid UI-side concerns (dialogs/widgets) in this package.

## File Tree
```text
db/
├── __init__.py
├── README.md
├── db_connections.py
├── db_retrieval.py
├── db_modifications.py
├── result_metadata.py
└── schema_retrieval.py
```
