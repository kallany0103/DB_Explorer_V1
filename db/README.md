# DB Package

Database access, schema retrieval, connection pooling, and persistence helpers.

## Purpose

- Centralize all DB connection creation and data operations.
- Manage connection pooling for efficient reuse across the application.
- Provide read/write helpers for app state (connections, hierarchy, query history).
- Keep all SQL and data-layer logic isolated from UI modules.

## Structure

| Module | Responsibility |
| :--- | :--- |
| `db_connections.py` | Connection factory for PostgreSQL, Oracle, SQLite, CSV, and ServiceNow; shared DB constants |
| `connection_pool.py` | Centralized connection pool — all connections must be obtained via this module |
| `db_retrieval.py` | Read operations for connections, hierarchy, and app state |
| `db_modifications.py` | Insert/update/delete operations and query-history persistence |
| `schema_retrieval.py` | Schema introspection — tables, columns, indexes, constraints, functions, triggers, etc. |
| `result_metadata.py` | Column metadata resolution for PostgreSQL and SQLite query outputs |
| `query_context.py` | Per-query context data (connection info, run tokens, cancellation state) |
| `transaction_session.py` | Explicit transaction session management for multi-statement workflows |
| `type_utils.py` | Type normalization and mapping utilities for query result columns |
| `db_bootstrap.py` | App-startup SQLite schema creation and migration for local metadata DBs |
| `__init__.py` | Package API — public exports consumed by `widgets/` and `workers/` |

## Usage Guidelines

- **Never** open ad-hoc connections in widgets or workers. Use `connection_pool.py`.
- Keep return shapes stable for callers in `widgets/`.
- Add provider-specific retrieval/modification helpers in focused files, then export from `__init__.py`.
- Keep connection payload assumptions explicit (`code`, host/db fields, or db_path).

## Error Handling

- Raise/return clear error information to UI managers via exceptions or typed result objects.
- Avoid UI-side concerns (dialogs/widgets) in this package.

## File Tree

```text
db/
├── __init__.py
├── README.md
├── connection_pool.py
├── db_connections.py
├── db_retrieval.py
├── db_modifications.py
├── schema_retrieval.py
├── result_metadata.py
├── query_context.py
├── transaction_session.py
├── type_utils.py
└── db_bootstrap.py
```
