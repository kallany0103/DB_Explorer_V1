import os
import sqlite3 as sqlite

import psycopg2
from PySide6.QtCore import QObject, QRunnable, Signal


class SchemaWorkerSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class SQLiteSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        db_path = self.conn_data.get("db_path")
        if not db_path or not os.path.exists(db_path):
            try:
                self.signals.error.emit(f"SQLite DB path not found: {db_path}")
            except RuntimeError:
                pass
            return

        conn = None
        try:
            conn = sqlite.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, type FROM sqlite_master "
                "WHERE type IN ('table', 'view') "
                "AND name NOT LIKE 'sqlite_%' "
                "ORDER BY type, name;"
            )
            rows = cursor.fetchall()
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "rows": rows})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                conn.close()


class PostgresSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.conn_data["host"],
                database=self.conn_data["database"],
                user=self.conn_data["user"],
                password=self.conn_data["password"],
                port=int(self.conn_data["port"]),
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%%' "
                "AND nspname != 'information_schema' "
                "ORDER BY nspname;"
            )
            schemas = [row[0] for row in cursor.fetchall()]
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "schemas": schemas})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
        finally:
            if conn:
                conn.close()


class CsvSchemaWorker(QRunnable):
    def __init__(self, conn_data):
        super().__init__()
        self.conn_data = conn_data
        self.signals = SchemaWorkerSignals()

    def run(self):
        folder_path = self.conn_data.get("db_path")
        if not folder_path or not os.path.exists(folder_path):
            try:
                self.signals.error.emit(f"CSV folder not found: {folder_path}")
            except RuntimeError:
                pass
            return

        try:
            csv_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".csv")]
            csv_files.sort()
            try:
                self.signals.finished.emit({"conn_data": self.conn_data, "files": csv_files})
            except RuntimeError:
                pass
        except Exception as exc:
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass
