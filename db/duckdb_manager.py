"""DuckDB connection and session management for flat files (CSV) and analytical sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import duckdb


class _ServiceNowConnectionProxy:
    """Wraps a DuckDB connection so every cursor() inherits the target search_path."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, search_path: str) -> None:
        self._conn = conn
        self._search_path = search_path
        self._conn.execute(f"SET search_path = '{search_path}'")

    def cursor(self) -> duckdb.DuckDBPyConnection:
        cur = self._conn.cursor()
        cur.execute(f"SET search_path = '{self._search_path}'")
        return cur

    def execute(self, *args: Any, **kwargs: Any) -> duckdb.DuckDBPyConnection:
        return self._conn.execute(*args, **kwargs)

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def _sanitize_table_name(filename: str) -> str:
    """Sanitizes a file basename into a valid SQL view/table identifier."""
    base = os.path.splitext(filename)[0]
    sanitized = "".join(c if (c.isalnum() or c == "_") else "_" for c in base).strip("_").lower()
    return sanitized or "table_data"


class DuckDBManager:
    """Manages embedded DuckDB sessions for CSV directories and analytical caches."""

    @staticmethod
    def create_csv_session(path_str: str) -> duckdb.DuckDBPyConnection:
        """
        Creates an in-memory DuckDB connection with views mounted for all .csv files.

        Args:
            path_str: Path to a CSV file or a folder containing .csv files.

        Returns:
            duckdb.DuckDBPyConnection: Active connection with registered views.
        """
        if not path_str or not os.path.exists(path_str):
            raise FileNotFoundError(f"CSV path does not exist: {path_str}")

        conn = duckdb.connect(database=":memory:")
        target_path = Path(path_str)

        if target_path.is_file() and target_path.suffix.lower() == ".csv":
            view_name = _sanitize_table_name(target_path.name)
            escaped_path = str(target_path.resolve()).replace("\\", "/")
            conn.execute(
                f'CREATE OR REPLACE VIEW "{view_name}" AS '
                f"SELECT * FROM read_csv_auto('{escaped_path}', all_varchar=false, sample_size=2048)"
            )
            if view_name != target_path.name:
                conn.execute(
                    f'CREATE OR REPLACE VIEW "{target_path.name}" AS '
                    f"SELECT * FROM read_csv_auto('{escaped_path}', all_varchar=false, sample_size=2048)"
                )
        elif target_path.is_dir():
            for item in target_path.iterdir():
                if item.is_file() and item.suffix.lower() == ".csv":
                    view_name = _sanitize_table_name(item.name)
                    escaped_path = str(item.resolve()).replace("\\", "/")
                    try:
                        conn.execute(
                            f'CREATE OR REPLACE VIEW "{view_name}" AS '
                            f"SELECT * FROM read_csv_auto('{escaped_path}', all_varchar=false, sample_size=2048)"
                        )
                    except Exception:
                        # Fallback for irregular CSVs: all_varchar=true
                        conn.execute(
                            f'CREATE OR REPLACE VIEW "{view_name}" AS '
                            f"SELECT * FROM read_csv_auto('{escaped_path}', all_varchar=true)"
                        )
                    if view_name != item.name:
                        try:
                            conn.execute(
                                f'CREATE OR REPLACE VIEW "{item.name}" AS '
                                f'SELECT * FROM "{view_name}"'
                            )
                        except Exception:
                            pass
        return conn

    @staticmethod
    def get_servicenow_duckdb_path(conn_id: str | int) -> str:
        """Returns the local DuckDB database path for a ServiceNow connection."""
        from db.db_connections import user_data_path
        db_file = user_data_path(f"databases/servicenow_{conn_id}.duckdb")
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        return str(Path(db_file).resolve())

    @staticmethod
    def create_servicenow_session(
        conn_id: str | int,
        use_display_values: bool = True,
    ) -> duckdb.DuckDBPyConnection:
        """
        Opens a connection to the local persistent DuckDB database for ServiceNow.

        Args:
            conn_id: Unique identifier for the ServiceNow connection.
            use_display_values: When False, routes queries to raw value views.

        Returns:
            duckdb.DuckDBPyConnection
        """
        db_path = DuckDBManager.get_servicenow_duckdb_path(conn_id)
        if not os.path.exists(db_path):
            init_conn = duckdb.connect(database=db_path)
            init_conn.close()
        conn = duckdb.connect(database=db_path, read_only=True)
        if not use_display_values:
            has_raw_schema = conn.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = '_sn_raw_vals'"
            ).fetchone()
            if has_raw_schema:
                return _ServiceNowConnectionProxy(conn, "_sn_raw_vals")
        return conn
