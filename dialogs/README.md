# Dialogs Package

Modal dialogs used across connection management, object creation, schema properties, export, and statistics workflows.

## Purpose

- Encapsulate user input forms and dialog-specific validation.
- Keep dialog logic separate from manager orchestration.
- Provide sub-packages organized by domain (connections, schema objects, properties, statistics, tools).
- Re-export all dialogs at the top-level `dialogs` package for full backward compatibility.

## Sub-Packages

### 1. Connection Dialogs (`dialogs/connections/`)
Handles connection creation, editing, and data source configuration:
- `base_connection_dialog.py` — shared base for all connection forms
- `postgres_dialog.py`, `sqlite_dialog.py`, `oracle_dialog.py`, `csv_dialog.py`, `servicenow_dialog.py`, `uds_dialog.py`
- `postgres_ds_dialog.py`, `sqlite_ds_dialog.py`, `oracle_ds_dialog.py`, `csv_ds_dialog.py`, `servicenow_ds_dialog.py`

### 2. Schema Object Creators (`dialogs/schema_objects/`)
DDL wizards and creation dialogs:
- `create_table_dialog.py` — Table creator
- `create_view_dialog.py` — View creator
- `create_materialized_view_dialog.py` — Materialized View creator
- `create_function_dialog.py` — Function creator
- `create_trigger_dialog.py` — Trigger creator
- `create_trigger_function_dialog.py` — Trigger Function creator
- `create_sequence_dialog.py` — Sequence creator
- `create_foreign_table_dialog.py` — Foreign Table creator
- `create_policy_dialog.py` — Row Level Security (RLS) Policy creator

### 3. Properties Sub-package (`dialogs/properties/`)
Rich property panels for inspecting schema objects:
- `base_properties.py` — Abstract base for property panels
- `table_properties.py`, `schema_properties.py`, `function_properties.py`
- `sequence_properties.py`, `trigger_properties.py`, `extension_properties.py`, `language_properties.py`
- `foreign_data_properties.py`
- `pg_queries.py` — Shared PostgreSQL introspection queries

### 4. Statistics Sub-package (`dialogs/statistics/`)
Database performance, object statistics, and inspector tab views:
- `database_statistics_dialog.py` — high-level database statistics view
- `stats_dialog.py` — statistics dialog container
- `stats_tab.py` — per-table statistics tab rendering

### 5. Tools Sub-package (`dialogs/tools/`)
Application tools and settings:
- `export_dialog.py` — CSV/XLSX export configuration
- `search_objects_dialog.py` — cross-schema object search
- `preferences_dialog.py` — application preferences

## Usage Guidelines

- Managers open dialogs and handle outcomes.
- Dialogs collect/validate user input and return structured data.
- Dialogs must **not** perform long-running database operations.
- All new schema-property panels must subclass `dialogs.properties.BasePropertyDialog`.
- Keep side effects minimal and explicit.

## File Tree

```text
dialogs/
├── __init__.py
├── README.md
├── connections/
│   ├── __init__.py
│   ├── base_connection_dialog.py
│   ├── postgres_dialog.py
│   ├── sqlite_dialog.py
│   ├── oracle_dialog.py
│   ├── csv_dialog.py
│   ├── servicenow_dialog.py
│   ├── uds_dialog.py
│   ├── postgres_ds_dialog.py
│   ├── sqlite_ds_dialog.py
│   ├── oracle_ds_dialog.py
│   ├── csv_ds_dialog.py
│   └── servicenow_ds_dialog.py
├── schema_objects/
│   ├── __init__.py
│   ├── create_table_dialog.py
│   ├── create_view_dialog.py
│   ├── create_materialized_view_dialog.py
│   ├── create_function_dialog.py
│   ├── create_trigger_dialog.py
│   ├── create_trigger_function_dialog.py
│   ├── create_sequence_dialog.py
│   ├── create_foreign_table_dialog.py
│   └── create_policy_dialog.py
├── properties/
│   ├── __init__.py
│   ├── base_properties.py
│   ├── table_properties.py
│   ├── function_properties.py
│   ├── schema_properties.py
│   ├── sequence_properties.py
│   ├── trigger_properties.py
│   ├── extension_properties.py
│   ├── language_properties.py
│   ├── foreign_data_properties.py
│   └── pg_queries.py
├── statistics/
│   ├── __init__.py
│   ├── database_statistics_dialog.py
│   ├── stats_dialog.py
│   └── stats_tab.py
└── tools/
    ├── __init__.py
    ├── export_dialog.py
    ├── search_objects_dialog.py
    └── preferences_dialog.py
```
