# DB Explorer

A powerful, high-performance universal SQL client and database management tool built with **Python** and **PyQt6**. Designed for developers and DBA who need a unified, responsive interface for diverse data sources.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![PyQt6](https://img.shields.io/badge/ui-PyQt6-green.svg)

## 🚀 Key Features

*   **🔌 Universal Connectivity**: Unified support for PostgreSQL, Oracle, SQLite, ServiceNow, and CSV files.
*   **📝 Professional SQL Editor**: 
    *   Multi-tabbed interface with persistent worksheet sessions.
    *   Syntax highlighting, SQL formatting, and advanced Find/Replace.
    *   Query history preservation.
*   **🏗️ Object Explorer**: Tree-based navigation of database schemas, tables, views, and columns with context-sensitive actions.
*   **📊 Results & Export**:
    *   High-performance data grid for multi-million row result sets.
    *   Asynchronous background exports to Excel and CSV.
*   **🎨 Visual Diagnostics**:
    *   **ERD Visualizer**: Generates interactive Entity-Relationship Diagrams.
    *   **Explain Visualizer**: Deep-dive execution plan visualization for Postgres optimization.
*   **⚡ Async Performance**: All database operations and queries run in background threads (`QThreadPool`) ensuring a lag-free UI experience.
*   **💾 Session Intelligence**: Automatically restores your workspace, including window geometry, open tabs, and query content.

## 🛠️ Technology Stack

*   **Core**: Python 3.11+
*   **UI Framework**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
*   **Database Engines**: 
    *   PostgreSQL (`psycopg2-binary`)
    *   Oracle (`oracledb`)
    *   SQLite (built-in)
    *   ServiceNow & CSV (via CData Connectors)
*   **Data Processing**: Pandas, Openpyxl, SQLParse
*   **Architecture**: Model-View-Controller (MVC) with specialized Manager pattern for UI components.

## 📂 Project Structure

| Directory | Description |
| :--- | :--- |
| `db/` | Database abstraction layer (connection logic, metadata retrieval). |
| `widgets/` | Custom UI components (Connection Manager, SQL Editor, ERD Visualizer). |
| `dialogs/` | Interactive windows for connection settings and data exports. |
| `workers/` | Multithreaded execution logic for background tasks. |
| `assets/` | Icons, SVGs, and visual resources. |
| `databases/` | local SQLite storage for application configuration/metadata. |

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/kallany0103/DB_Explorer_V1.git
    cd DB_Explorer_V1
    ```

2.  **Create and activate a virtual environment**:
    ```bash
    python -m venv db_venv
    source db_venv/bin/activate  # On Windows: db_venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: CData connectors (.whl files) provided in the root directory should be installed manually if not handled by requirements.*

4.  **Run the application**:
    ```bash
    python main.py
    ```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.
