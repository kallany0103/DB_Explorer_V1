# Dialogs Package

Reusable PyQt dialogs used across connection management and results workflows.

## Purpose
- Encapsulate user input forms and dialog-specific validation/UI.
- Keep dialog logic separate from manager orchestration.

## Structure
- Connection dialogs: `postgres_dialog.py`, `sqlite_dialog.py`, `oracle_dialog.py`, `csv_dialog.py`, `servicenow_dialog.py`
- Object dialogs: `create_table_dialog.py`, `create_view_dialog.py`, `table_properties.py`
- Export dialog: `export_dialog.py`
- `__init__.py`: package API exports

## Usage Guidelines
- Managers open dialogs and handle outcomes.
- Dialogs collect/validate user input and return structured data.
- Dialogs should not perform long-running database operations.
- Keep side effects minimal and explicit.

## File Tree
```text
dialogs/
├── __init__.py
├── README.md
├── postgres_dialog.py
├── sqlite_dialog.py
├── oracle_dialog.py
├── csv_dialog.py
├── servicenow_dialog.py
├── create_table_dialog.py
├── create_view_dialog.py
├── export_dialog.py
└── table_properties.py
```
