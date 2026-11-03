# Release Notes — Universal SQL Client

## [v1.44.4] — Latest Update

### 📅 Last Update
October 31, 2026

### Features & Fixes in Last Update
- **Toad-Grade SQL Optimizer**: Multi-variant execution plan benchmarking, deterministic rewrites (EXISTS, ANSI JOIN, Sargable ranges, UNION ALL), and procedural code awareness.
- **Visual Plan Diff & Benchmarking**: Side-by-side execution plan comparison trees and safe empirical execution benchmarks.
- **Risk-Free Virtual Index Simulator**: Test candidate index adoption virtually without physical disk space allocation.
- **Batch Workload Optimizer**: Bulk multi-statement script optimizer with AST analysis, progress tracking, and optimization metrics.
- **Card-Based Messages View**: Redesigned query feedback stream with accent brackets, execution metrics, and one-click copy.
- **Oracle & PostgreSQL Script Generation**: Non-blocking asynchronous CREATE, INSERT, and UPDATE script generators with live progress feedback and sequence/identity detection.
- **Oracle Client Architecture Guard**: Added PE binary bitness verification to prevent 32-bit/64-bit client mismatches with clear diagnostic guidance.
- **Connection UX Enhancements**: Streamlined Oracle Client toggle, improved SQLNET status indicators, and normalized host connectivity.

---

## [v1.44.0] — Latest Update

### 📅 Last Update
October 15, 2026

### Features Added in Last Update
- **Cross-Source Query & Join Helper**: Visual cross-source querying and multi-database joining for PostgreSQL, Oracle, SQLite, CSV, and ServiceNow.
- **Schema Diff & Synchronization Tool**: Compare structure between databases and generate migration scripts.
- **Automated Metadata & State Widget**: Real-time server and session health metrics visualization.
- **Enhanced Terminal Tool (USQL)**: Improved embedded terminal interaction and session stability.

---

### Key Features
- **Multi-Source Connections**: Full support for PostgreSQL, Oracle, SQLite, CSV, and ServiceNow.
- **Advanced SQL Worksheet**: Multi-tab query editor with syntax highlighting, auto-completion, formatting, and query history.
- **Object Browser**: Tree explorer for schemas, tables, views, procedures, sequences, and triggers.
- **Results View**: Paginated data grid with inline CRUD editing, column metadata, explain plan analysis, and query message logs.
- **Visual ERD Designer**: Entity-relationship diagram builder with SQL export and diagram serialization.
- **Database Inspector & Dashboard**: Live session tracking, server metrics, and detailed object properties.
- **Backup & Encryption Tools**: Native database backup workflows and encrypted SQLite connection support.
- **Export Capabilities**: Streaming export to CSV and XLSX formats.
