# Technical Documentation — Universal SQL Client

## 1. System Overview
Universal SQL Client is a desktop multi-database client and management workstation built with Python and PySide6 (Qt6). It delivers a unified interface for connecting to, exploring, querying, and visualizing data across diverse relational and non-relational database sources.


## 2. Directory Structure & Code Organization

```
DB_Explorer_V1/
├── assets/                 # Icons, SVG vectors, and UI images
├── auth/                   # Authentication handlers and session storage
├── databases/              # Local SQLite stores (connections, history, state)
├── dialogs/                # Modal dialogs, wizards, and properties editors
├── drivers/                # CData connector wheels for external engines
├── db/                     # DB abstraction layer, connection pool, metadata
├── ui/                     # Design system: QSS stylesheet, themes, title bar
├── widgets/                # Modular UI components:
│   ├── app_shell/          # Menus, global action builders, session saver
│   ├── connection_manager/ # Object explorer and context menus
│   ├── dashboard/          # Metrics, state, and server overview widgets
│   ├── erd/                # Visual ERD diagram canvas and models
│   ├── inspector/          # Object properties and database statistics
│   ├── results_view/       # Results grid, explain plan, messages
│   ├── usql_tool/          # Embedded USQL terminal integration
│   └── worksheet/          # Multi-tab SQL editors and tab managers
├── workers/                # Thread workers, runnables, and typed signals
├── main_window.py          # Central QMainWindow and docking manager
├── main.py                 # Application bootstrapper and splash screen
├── README.md               # User quick-start and setup guide
├── RELEASE_NOTES.md        # Change log and release history
└── TECHNICAL_DOCUMENTATION.md # Technical specifications and architecture
```

---

## 3. Runtime Requirements & Development Setup

### 3.1 Prerequisites
- Python 3.10+ (64-bit recommended)
- Windows 10/11

### 3.2 Virtual Environment & Dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```