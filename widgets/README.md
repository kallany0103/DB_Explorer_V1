# Widgets Package

This package contains all primary UI layers and managers.

## Purpose
- Compose and manage the application UI.
- Coordinate user actions with database/services/workers.
- Keep feature responsibilities separated by subpackage.

## Structure
- `worksheet/`: SQL editor tabs, editor actions, query execution orchestration, history helpers.
- `results_view/`: query output tabs, messages/notifications/processes/explain views, row CRUD, result rendering.
- `connection_manager/`: connection tree, schema loading, context menus, connection actions/dialog wiring.
- `erd/`: ERD scene/view/widget and ERD graphics items.
- `__init__.py`: top-level API exports consumed by `main_window.py`.

Worksheet query orchestration modules are grouped under `worksheet/query/`:
- `query_dispatch.py`
- `query_explain.py`
- `query_feedback.py`
- `query_preparation.py`
- `query_runtime.py`
- `query_termination.py`
- `query_view_state.py`

## Key Entrypoints
- `WorksheetManager` (`worksheet/manager.py`)
- `ResultsManager` (`results_view/manager.py`)
- `ConnectionManager` (`connection_manager/manager.py`)
- `ERDWidget` (`erd/widget.py`)

## Design Boundaries
- Keep **UI assembly** in `ui.py`/`tab_builder.py`/`context_menu.py`.
- Keep **actions/behavior** in action modules (`editor_actions.py`, `row_crud.py`, etc.).
- Keep **manager classes** as orchestration facades that delegate to focused modules.
- Use **direct internal imports** (module-to-module) inside a package.
- Use package `__init__.py` exports for external consumers.

## Adding New Code (Quick Rules)
- New worksheet editor command -> `worksheet/editor_actions.py`.
- New worksheet context-menu entry -> `worksheet/context_menu.py`.
- New results tab behavior -> `results_view/output_tabs.py` or specific tab module.
- New process-table behavior -> `results_view/processes.py`.
- New connection-tree action -> `connection_manager/actions.py`.

## Notes
- Avoid reintroducing monoliths in manager files.
- Prefer small feature modules with explicit responsibilities.

## File Tree
```text
widgets/
├── __init__.py
├── README.md
├── worksheet/
│   ├── __init__.py
│   ├── manager.py
│   ├── tab_builder.py
│   ├── query_executor.py
│   ├── query/
│   │   ├── __init__.py
│   │   ├── query_dispatch.py
│   │   ├── query_explain.py
│   │   ├── query_feedback.py
│   │   ├── query_preparation.py
│   │   ├── query_runtime.py
│   │   ├── query_termination.py
│   │   └── query_view_state.py
│   ├── editor_actions.py
│   ├── context_menu.py
│   ├── code_editor.py
│   ├── history.py
│   ├── connections.py
│   └── utils.py
├── results_view/
│   ├── __init__.py
│   ├── manager.py
│   ├── ui.py
│   ├── output_tabs.py
│   ├── query_handler.py
│   ├── row_crud.py
│   ├── processes.py
│   ├── notifications.py
│   ├── messages.py
│   ├── explain.py
│   └── clipboard.py
├── connection_manager/
│   ├── __init__.py
│   ├── manager.py
│   ├── ui.py
│   ├── actions.py
│   ├── dialogs.py
│   ├── schema_loaders.py
│   ├── context_menus.py
│   ├── scripting.py
│   ├── table_details.py
│   └── tree_helpers.py
└── erd/
	├── __init__.py
	├── widget.py
	├── view.py
	├── scene.py
	├── routing.py
	├── property_panel.py
	├── commands.py
	└── items/
		├── __init__.py
		├── table_item.py
		└── connection_item.py
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
