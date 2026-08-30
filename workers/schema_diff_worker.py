from PySide6.QtCore import QRunnable, QObject, Signal
from db.schema_diff_engine import (
    introspect_schema_metadata,
    compare_schemas,
    generate_ddl_migration_script
)


class SchemaDiffSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class SchemaDiffWorker(QRunnable):
    """
    Background worker to introspect and compare two database schemas asynchronously.
    """

    def __init__(self, source_conn: dict, source_schema: str, target_conn: dict, target_schema: str):
        super().__init__()
        self.source_conn = source_conn
        self.source_schema = source_schema
        self.target_conn = target_conn
        self.target_schema = target_schema
        self.signals = SchemaDiffSignals()

    def run(self):
        try:
            source_meta = introspect_schema_metadata(self.source_conn, self.source_schema)
            target_meta = introspect_schema_metadata(self.target_conn, self.target_schema)

            diff_result = compare_schemas(source_meta, target_meta)
            ddl_script = generate_ddl_migration_script(diff_result, target_schema=self.target_schema or "public")

            result = {
                "source_conn": self.source_conn,
                "source_schema": self.source_schema,
                "target_conn": self.target_conn,
                "target_schema": self.target_schema,
                "source_meta": source_meta,
                "target_meta": target_meta,
                "diff_result": diff_result,
                "ddl_script": ddl_script
            }
            self.signals.finished.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
