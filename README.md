# Universal SQL Client

Universal SQL Client is a desktop multi-database SQL client built with Python and PySide6. It provides a unified, responsive workspace for exploring and querying PostgreSQL, Oracle, SQLite, CSV files, and ServiceNow from a single application.

## Features

- **Multi-source connections** — PostgreSQL, Oracle, SQLite, CSV, and ServiceNow
- **SQL editor** — syntax highlighting, auto-complete, formatting, and per-connection query history
- **Object browser** — explore schemas, tables, views, functions, sequences, triggers, and more
- **Multi-tab worksheet** — multiple simultaneous editor sessions with session restore on relaunch
- **Results view** — paginated output, column metadata, row-level CRUD, explain-plan viewer, messages, notifications, and process tracker
- **ERD designer** — visual entity-relationship diagram builder with SQL generation and serialization
- **USQL terminal tool** — integrated terminal for direct PostgreSQL interaction
- **Dashboard** — at-a-glance connection and schema state overview
- **Inspector** — live server stats, session logs, and state monitoring
- **Backup & Restore** — database backup and restore workflows
- **Encryption** — encrypted SQLite connections via `widgets/encryption/`
- **Test Cases Widget** — manage and execute SQL query test suites
- **Schema properties dialogs** — rich property panels for tables, views, functions, sequences, triggers, extensions, and foreign data wrappers
- **Context menus** — modular, registry-driven context menus for every schema object type
- **Connection pooling** — managed pool in `db/connection_pool.py` for efficient reuse
- **Export** — query results to CSV/XLSX with progress tracking

## Architecture

```
main.py
└── main_window.py
    └── widgets/          ← UI panels, trees, editors
        └── dialogs/      ← modal dialogs
            └── workers/  ← QThread / ProcessPoolExecutor tasks
                └── db/   ← all DB I/O (SQLite metadata + live connections)
```

- **Composition root:** `main_window.py`
- **Feature managers:** `widgets/connection_manager/manager.py`, `widgets/worksheet/manager.py`, `widgets/results_view/manager.py`
- **Worker contracts:** `workers/signals.py`
- **Styling:** `ui/style.qss`, `ui/theme.py`, `ui/components.py`, `ui/toolbars.py`

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full system design.

## Project Structure

| Directory | Responsibility |
| :--- | :--- |
| `db/` | Connection creation, connection pooling, schema introspection, retrieval, modification, history, and metadata |
| `widgets/` | All UI feature domains — worksheet, results, connections, ERD, dashboard, inspector, backup/restore, encryption, test cases, USQL |
| `dialogs/` | Connection dialogs, object-creation dialogs, schema properties panels, export and statistics dialogs |
| `workers/` | Background runnables (`QThread`/`ProcessPoolExecutor`) and typed signal contracts |
| `ui/` | Global QSS stylesheet, theme tokens, shared UI components, and toolbar builders |
| `assets/` | Icons and UI resources |
| `databases/` | Local SQLite app metadata — connections, hierarchy, session state, and process history |
| `docs/` | Architecture deep-dives, performance plans, ERD guides, and implementation notes |
| `drivers/` | CData connector wheels for CSV and ServiceNow |

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** `requirements.txt` includes CData connector wheels from the `drivers/` directory. Ensure the wheel files are present before running `pip install`.

3. Run the application:

```bash
python main.py
```

## Documentation Map

| Document | Description |
| :--- | :--- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Full system design, domain boundaries, and engineering rules |
| [`db/README.md`](db/README.md) | Data access layer — modules, patterns, and usage guidelines |
| [`widgets/README.md`](widgets/README.md) | UI package structure, feature domains, and design boundaries |
| [`workers/README.md`](workers/README.md) | Background workers, signal contracts, and concurrency rules |
| [`dialogs/README.md`](dialogs/README.md) | Dialog catalog and usage guidelines |
| [`docs/PERFORMANCE_SCALABILITY_PLAN.md`](docs/PERFORMANCE_SCALABILITY_PLAN.md) | Performance phases and scalability roadmap |
| [`docs/CONNECTION_POOLING_IMPLEMENTATION.md`](docs/CONNECTION_POOLING_IMPLEMENTATION.md) | Connection pool design and implementation details |
| [`docs/THREADING_MULTIPROCESSING_REPORT.md`](docs/THREADING_MULTIPROCESSING_REPORT.md) | Concurrency analysis and threading report |

## Requirements

| Dependency | Purpose |
| :--- | :--- |
| PySide6 | Qt6 GUI framework |
| psycopg2-binary | PostgreSQL driver |
| oracledb | Oracle driver |
| pandas | Data processing and export |
| openpyxl | XLSX export |
| sqlparse | SQL formatting |
| qtawesome ≥ 1.4.0 | Icon library |
| pywinpty | Terminal emulation (USQL tool) |
| CData CSV connector | CSV data source (wheel in `drivers/`) |
| CData ServiceNow connector | ServiceNow data source (wheel in `drivers/`) |
