# Widgets Package

This package contains all primary UI layers and managers.

## Purpose

- Compose and manage the application UI.
- Coordinate user actions with database/services/workers.
- Keep feature responsibilities separated by subpackage.

## Structure

| Subpackage | Responsibility |
| :--- | :--- |
| `app_shell/` | Actions, menus, session persistence, window/file operations |
| `connection_manager/` | Connection tree, schema loading, context menus, connection actions/dialog wiring |
| `worksheet/` | SQL editor tabs, query execution orchestration, history, auto-complete, toolbar actions |
| `results_view/` | Output tabs, result rendering, row CRUD, explain/messages/notifications/processes |
| `erd/` | ERD scene/view/item graph, SQL generation, serialization, palette |
| `dashboard/` | At-a-glance connection and schema state overview |
| `inspector/` | Live server stats, session logs, state monitoring |
| `backup_and_restore/` | Database backup and restore workflows |
| `encryption/` | Encrypted SQLite database connections |
| `test_cases/` | SQL test suite management and execution |
| `usql_tool/` | Integrated terminal emulator for direct PostgreSQL interaction |

## Key Entrypoints

- `WorksheetManager` (`worksheet/manager.py`)
- `ResultsManager` (`results_view/manager.py`)
- `ConnectionManager` (`connection_manager/manager.py`)
- `ERDWidget` (`erd/widget.py`)

## Worksheet Query Orchestration

Query orchestration helpers are grouped under `worksheet/query/`:
- `query_dispatch.py`
- `query_explain.py`
- `query_feedback.py`
- `query_preparation.py`
- `query_runtime.py`
- `query_termination.py`
- `query_view_state.py`

## Connection Context Menus

Context menu modules are split into `connection_manager/context_menus/`:
- `explorer_menus.py` — connection-level and database-level actions
- `schema_menus.py` — schema object actions (tables, views, functions, etc.)
- `mview_menus.py` — materialized view actions
- `trigger_menus.py` — trigger actions
- `_helpers.py` — shared menu-building utilities

## Design Boundaries

- Keep **UI assembly** in `ui.py`/`tab_builder.py`/`context_menu.py`.
- Keep **actions/behavior** in action modules (`editor_actions.py`, `row_crud.py`, etc.).
- Keep **manager classes** as orchestration facades that delegate to focused modules.
- Use **direct internal imports** (module-to-module) inside a package.
- Use package `__init__.py` exports for external consumers.
- Keep QSS styling in `ui/` — not in widget files.

## Adding New Code (Quick Rules)

- New worksheet editor command → `worksheet/editor_actions.py`
- New worksheet toolbar action → `worksheet/toolbar_actions.py`
- New worksheet context-menu entry → `worksheet/context_menu.py`
- New results tab behavior → `results_view/output_tabs.py` or specific tab module
- New process-table behavior → `results_view/processes.py`
- New connection-tree action → `connection_manager/actions.py`
- New connection-tree context menu → `connection_manager/context_menus/`

## Notes

- Avoid reintroducing monoliths in manager files.
- Prefer small feature modules with explicit responsibilities.

## File Tree

```text
widgets/
├── __init__.py
├── README.md
├── splash_screen.py
├── app_shell/
│   ├── actions.py
│   ├── file_ops.py
│   ├── menus.py
│   ├── session.py
│   └── window_ops.py
├── connection_manager/
│   ├── manager.py
│   ├── ui.py
│   ├── actions.py
│   ├── dialogs.py
│   ├── schema_loaders.py
│   ├── scripting.py
│   ├── spinner.py
│   ├── table_details.py
│   ├── tree_helpers.py
│   └── context_menus/
│       ├── __init__.py
│       ├── explorer_menus.py
│       ├── schema_menus.py
│       ├── mview_menus.py
│       ├── trigger_menus.py
│       └── _helpers.py
├── worksheet/
│   ├── manager.py
│   ├── tab_builder.py
│   ├── query_executor.py
│   ├── code_editor.py
│   ├── autocomplete.py
│   ├── editor_actions.py
│   ├── toolbar_actions.py
│   ├── context_menu.py
│   ├── history.py
│   ├── connections.py
│   ├── utils.py
│   └── query/
│       ├── query_dispatch.py
│       ├── query_explain.py
│       ├── query_feedback.py
│       ├── query_preparation.py
│       ├── query_runtime.py
│       ├── query_termination.py
│       └── query_view_state.py
├── results_view/
│   ├── manager.py
│   ├── ui.py
│   ├── output_tabs.py
│   ├── query_handler.py
│   ├── row_crud.py
│   ├── processes.py
│   ├── notifications.py
│   ├── messages.py
│   ├── explain.py
│   ├── clipboard.py
│   ├── perf_metrics.py
│   └── value_state.py
├── erd/
│   ├── widget.py
│   ├── view.py
│   ├── scene.py
│   ├── routing.py
│   ├── path_planner.py
│   ├── layout_engine.py
│   ├── commands.py
│   ├── property_panel.py
│   ├── serialization.py
│   ├── sql_generator.py
│   ├── model.py
│   ├── palette.py
│   ├── palette_icons.py
│   ├── constants.py
│   ├── dialogs.py
│   └── items/
│       ├── table_item.py
│       └── connection_item.py
├── dashboard/
├── inspector/
│   ├── widget.py
│   ├── logs_widget.py
│   └── state_widget.py
├── backup_and_restore/
│   ├── backup/
│   ├── restore/
│   └── core/
├── encryption/
│   └── secure_sqlite.py
├── test_cases/
│   └── test_cases_widget.py
└── usql_tool/
    ├── editor.py
    ├── terminal_widget.py
    ├── constants.py
    └── discovery.py
```

## Query Lifecycle (End-to-End)

1. User writes SQL in `worksheet/code_editor.py` and executes via `WorksheetManager` (`worksheet/manager.py`).
2. `worksheet/query_executor.py` orchestrates query flow using helper modules under `worksheet/query/` and routes async signals back to manager.
3. `ResultsManager` (`results_view/manager.py`) delegates rendering/behavior to:
   - `query_handler.py` (result models, metadata, status updates)
   - `output_tabs.py` (output tab creation/selection/title)
   - `row_crud.py` (insert/update/delete and export helpers)
   - `processes.py` (process status table and lifecycle)
4. Data access and schema/history persistence flow through the `db/` package.
5. Background tasks use `workers/` runnables and signal classes; UI remains responsive.
