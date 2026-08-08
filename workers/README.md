# Workers Package

Background task runnables and signal contracts for asynchronous operations.

## Purpose

- Run long-running operations off the UI thread.
- Publish progress, results, and errors through typed signal containers.
- Provide normalized emit helpers to keep producer/consumer contracts stable.

## Structure

| Module | Responsibility |
| :--- | :--- |
| `workers.py` | Core worker runnables: `RunnableQuery`, `RunnableExport`, `RunnableExportFromModel`, `FetchMetadataWorker` |
| `signals.py` | Signal classes: `QuerySignals`, `ProcessSignals`, `MetadataSignals` |
| `connection_workers.py` | Workers for connection testing, schema refresh, and connection-level operations |
| `inspector_workers.py` | Workers for Inspector domain — server stats polling and session log retrieval |
| `inspector_stats.py` | Stats computation helpers used by Inspector workers |
| `process_worker.py` | Worker for process-lifecycle tracking and `usf_processes` persistence |
| `__init__.py` | Package API exports |

## Signal Contract Normalization

`signals.py` includes emit helper functions that normalize payload types before signal emission:
- `emit_process_started`, `emit_process_finished`, `emit_process_error`
- `emit_query_finished`, `emit_query_error`
- `emit_metadata_finished`, `emit_metadata_error`

These helpers reduce runtime type-mismatch failures and keep producer/consumer contracts stable.

## Usage Guidelines

- Place blocking I/O and heavy compute in workers.
- Keep workers UI-agnostic; communicate via signals only.
- Start workers from managers through `QThreadPool` and connect signals in manager modules.
- Prefer normalized emit helpers over direct `.emit(...)` calls in worker paths.

## Reliability Rules

- Emit success/error deterministically — never silently swallow exceptions.
- Include enough context in emitted payloads for manager-side handling.
- Never access or modify Qt widgets from inside a worker.

## File Tree

```text
workers/
├── __init__.py
├── README.md
├── workers.py
├── signals.py
├── connection_workers.py
├── inspector_workers.py
├── inspector_stats.py
└── process_worker.py
```
