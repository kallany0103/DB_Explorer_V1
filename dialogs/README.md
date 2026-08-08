# Dialogs Package

Modal dialogs used across connection management, object creation, schema properties, export, and statistics workflows.

## Purpose

- Encapsulate user input forms and dialog-specific validation.
- Keep dialog logic separate from manager orchestration.
- Provide a base class (`properties/base_properties.py`) for all schema-properties panels.

## Structure

### Connection Dialogs
- `base_connection_dialog.py` — shared base for all connection forms
- `postgres_dialog.py`, `sqlite_dialog.py`, `oracle_dialog.py`, `csv_dialog.py`, `servicenow_dialog.py`

### Object-Creation Dialogs
- `create_table_dialog.py`, `create_view_dialog.py`, `create_materialized_view_dialog.py`
- `create_function_dialog.py`, `create_trigger_dialog.py`, `create_trigger_function_dialog.py`
- `create_sequence_dialog.py`, `create_foreign_table_dialog.py`, `create_policy_dialog.py`

### Utility Dialogs
- `export_dialog.py` — CSV/XLSX export configuration
- `preferences_dialog.py` — application preferences
- `search_objects_dialog.py` — cross-schema object search
- `database_statistics_dialog.py` — high-level database statistics view

### Properties Sub-package (`dialogs/properties/`)

Rich property panels for viewing and editing existing schema objects. All panels subclass `base_properties.py`.

| File | Coverage |
| :--- | :--- |
| `base_properties.py` | Abstract base for all property panels |
| `table_properties.py` | Table columns, indexes, constraints, triggers |
| `function_properties.py` | Function definition and volatility |
| `schema_properties.py` | Schema ownership and privileges |
| `sequence_properties.py` | Sequence parameters and current value |
| `trigger_properties.py` | Trigger definition and timing |
| `extension_properties.py` | Installed extension metadata |
| `language_properties.py` | Procedural language details |
| `foreign_data_properties.py` | Foreign data wrappers and servers |
| `pg_queries.py` | Shared PostgreSQL introspection queries used by property panels |

### Statistics Sub-package (`dialogs/statistics/`)
- `stats_dialog.py` — statistics dialog container
- `stats_tab.py` — per-table statistics tab rendering

## Usage Guidelines

- Managers open dialogs and handle outcomes.
- Dialogs collect/validate user input and return structured data.
- Dialogs must **not** perform long-running database operations.
- All new schema-property panels must subclass `dialogs/properties/base_properties.py`.
- Keep side effects minimal and explicit.

## File Tree

```text
dialogs/
├── __init__.py
├── README.md
├── base_connection_dialog.py
├── postgres_dialog.py
├── sqlite_dialog.py
├── oracle_dialog.py
├── csv_dialog.py
├── servicenow_dialog.py
├── export_dialog.py
├── preferences_dialog.py
├── search_objects_dialog.py
├── database_statistics_dialog.py
├── create_table_dialog.py
├── create_view_dialog.py
├── create_materialized_view_dialog.py
├── create_function_dialog.py
├── create_trigger_dialog.py
├── create_trigger_function_dialog.py
├── create_sequence_dialog.py
├── create_foreign_table_dialog.py
├── create_policy_dialog.py
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
└── statistics/
    ├── stats_dialog.py
    └── stats_tab.py
```
