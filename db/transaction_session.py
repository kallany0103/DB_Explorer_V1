# db/transaction_session.py
"""
Per-tab transaction session manager.

Holds a single dedicated (non-pooled) connection for a worksheet tab so
the user can accumulate DML/DDL statements and commit or roll back as a unit —
exactly the way DBeaver, DataGrip, and pgAdmin handle manual transactions.

Supported DB types: POSTGRES, ORACLE / ORACLE_DB.
All others raise UnsupportedTransactionError.
"""

from __future__ import annotations

import logging
import db

logger = logging.getLogger(__name__)


# Public exception

class UnsupportedTransactionError(Exception):
    """Raised when the connected DB does not support manual transactions."""

# Session

class TransactionSession:
    """
    A dedicated connection that lives across multiple query executions
    until the user explicitly commits or rolls back.

    Usage (from the Qt main thread — actual query execution must happen in a
    worker thread; the *connection object* is created here but queries are
    sent via RunnableTransactionQuery):

        session = TransactionSession(conn_data)
        session.open()          # opens connection, sets autocommit=False
        conn = session.connection  # pass to RunnableTransactionQuery
        ...
        session.commit()        # or session.rollback()
        session.close()
    """

    #: DB codes that support manual transaction sessions.
    SUPPORTED_CODES = frozenset({"POSTGRES", "ORACLE", "ORACLE_DB"})

    def __init__(self, conn_data: dict) -> None:
        self._conn_data = conn_data
        self._conn = None
        self._code: str = (
            conn_data.get("code") or conn_data.get("db_type") or ""
        ).upper()
        self.has_pending_changes = False

    # Properties


    @property
    def connection(self):
        """Return the raw DB-API connection, or None if not open."""
        return self._conn

    @property
    def is_open(self) -> bool:
        """True when a live connection is held."""
        if self._conn is None:
            return False
        try:
            # psycopg2 / sqlite3 expose .closed; oracledb exposes .is_healthy()
            if hasattr(self._conn, "closed"):
                return self._conn.closed == 0
            if hasattr(self._conn, "is_healthy"):
                return self._conn.is_healthy()
        except Exception:
            pass
        return True

    # Lifecycle


    def open(self) -> None:
        """
        Open a dedicated connection for the transaction session.

        Raises:
            UnsupportedTransactionError: if the DB type is not supported.
            ConnectionError: if the connection cannot be established.
        """
        if self._code not in self.SUPPORTED_CODES:
            raise UnsupportedTransactionError(
                f"Manual transaction control is not supported for '{self._code}' connections.\n"
                "Supported databases: PostgreSQL, Oracle."
            )

        if self.is_open:
            return  # already open — reuse

        if self._code == "POSTGRES":
            db_name = self._conn_data.get("database", "postgres")
            app_name = f"Universal SQL Client (Transaction) - {db_name}"
            conn = db.create_postgres_connection(
                self._conn_data,
                application_name=app_name,
                bypass_cooldown=True,
            )
            if not conn:
                raise ConnectionError("Failed to open PostgreSQL transaction connection.")
            # psycopg2 starts in autocommit=False by default; make it explicit.
            conn.autocommit = False
            self._conn = conn

        elif self._code in ("ORACLE", "ORACLE_DB"):
            conn = db.get_pooled_oracle_connection(conn_data=self._conn_data)
            if not conn:
                raise ConnectionError("Failed to open Oracle transaction connection.")
            # oracledb defaults to autocommit=False — no change needed.
            self._conn = conn

    def commit(self) -> None:
        """Commit the current transaction and close the session connection."""
        if self._conn is not None:
            try:
                self._conn.commit()
                self.has_pending_changes = False
                logger.debug("TransactionSession: committed.")
            finally:
                self.close()

    def rollback(self) -> None:
        """Roll back the current transaction and close the session connection."""
        if self._conn is not None:
            try:
                self._conn.rollback()
                self.has_pending_changes = False
                logger.debug("TransactionSession: rolled back.")
            finally:
                self.close()

    def close(self) -> None:
        """Close the underlying connection without committing."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None
