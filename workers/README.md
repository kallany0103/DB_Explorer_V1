# Workers Package

Background task runnables and signal contracts for asynchronous operations.

## Purpose
- Run long operations off the UI thread.
- Publish progress/results/errors through typed signal containers.

## Structure
- `workers.py`: worker runnables (`RunnableQuery`, `RunnableExport`, `RunnableExportFromModel`, `FetchMetadataWorker`)
- `signals.py`: signal classes (`QuerySignals`, `ProcessSignals`, `MetadataSignals`)
- `__init__.py`: package API exports

## Signal Contract Normalization

`signals.py` now includes emit helper functions that normalize payload types before signal emission:
- `emit_process_started`, `emit_process_finished`, `emit_process_error`
- `emit_query_finished`, `emit_query_error`
- `emit_metadata_finished`, `emit_metadata_error`

These helpers reduce runtime type-mismatch failures and keep producer/consumer contracts stable.

## Usage Guidelines
- Place blocking I/O and heavy compute in workers.
- Keep workers UI-agnostic; communicate via signals only.
- Start workers from managers through `QThreadPool` and connect signals in manager modules.

## Reliability Rules
- Emit success/error deterministically.
- Include enough context in emitted payloads for manager-side handling.
- Prefer normalized emit helpers over direct `.emit(...)` calls in worker paths.

## File Tree
```text
workers/
├── __init__.py
├── README.md
├── workers.py
└── signals.py
```
