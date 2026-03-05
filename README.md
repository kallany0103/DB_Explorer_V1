# DB Explorer

DB Explorer is a desktop SQL client built with Python and PyQt6 for working across PostgreSQL, Oracle, SQLite, CSV, and ServiceNow from one responsive interface.

## Features

- Connect to PostgreSQL, Oracle, SQLite, CSV files, and ServiceNow
- SQL editor with syntax highlighting, formatting, and query history
- Object browser for exploring database schemas and tables
- Multi-tab workspace with session restore
- Export query results to CSV/XLSX with progress tracking
- Visual ERD (Entity-Relationship Diagram) designer

## Architecture

- Composition root: `main_window.py`
- Feature managers:
  - `widgets/connection_manager/manager.py`
  - `widgets/worksheet/manager.py`
  - `widgets/results_view/manager.py`
- Query orchestration helpers are grouped under `widgets/worksheet/query/`.
- Worker contracts and emit normalization are defined in `workers/signals.py`.

See `ARCHITECTURE.md` for full system design.

## Project Structure

| Directory | Responsibility |
| :--- | :--- |
| `db/` | connection creation, retrieval, schema introspection, modifications/history persistence |
| `widgets/` | UI feature domains (worksheet, results, connections, ERD, app shell) |
| `dialogs/` | input/config dialogs used by managers |
| `workers/` | background runnables and signal contracts |
| `assets/` | icons and UI resources |
| `databases/` | local SQLite app metadata/state |

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install CData wheel connectors from root directory when required by your target sources.

4. Run app:

```bash
python main.py
```

## Documentation Map

- `ARCHITECTURE.md`
- `PERFORMANCE_SCALABILITY_PLAN.md`
- `widgets/README.md`
- `workers/README.md`
- `db/README.md`
- `dialogs/README.md`
