import os
import sqlite3
import tempfile
import unittest
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtTest import QTest

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from widgets.encryption.secure_sqlite import enable_transparent_encryption
enable_transparent_encryption("mysecretpassword")

from workers.signals import tracker, emit_query_finished, emit_query_error, QuerySignals
from db.db_retrieval import get_sqlite_session_stats, get_sqlite_state_details
from main_window import MainWindow

# Initialize PySide6 QApplication exactly once for all GUI tests
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)


class TestAppTransactionTracker(unittest.TestCase):
    """
    Unit tests for workers.signals.AppTransactionTracker (tracker)
    to ensure worksheet transaction commits, rollbacks, and tuple updates
    are accurately aggregated at the application level.
    """

    def setUp(self):
        # Reset tracker stats before each test
        tracker.commits = 0
        tracker.rollbacks = 0
        tracker.tup_ins = 0
        tracker.tup_upd = 0
        tracker.tup_del = 0
        tracker.tup_fet = 0
        tracker.tup_ret = 0
        tracker.exec_time = 0.0
        self.signals = QuerySignals()

    def test_tracker_stat_accumulation(self):
        """Test basic manual increments of the app tracker."""
        tracker.add_commit()
        tracker.add_rollback()
        tracker.add_tuples(ins=5, upd=3, delt=2, fet=10, ret=10)
        tracker.add_exec_time(15.5)

        stats = tracker.get_stats()
        self.assertEqual(stats["commits"], 1)
        self.assertEqual(stats["rollbacks"], 1)
        self.assertEqual(stats["tup_ins"], 5)
        self.assertEqual(stats["tup_upd"], 3)
        self.assertEqual(stats["tup_del"], 2)
        self.assertEqual(stats["tup_fet"], 10)
        self.assertEqual(stats["tup_ret"], 10)
        self.assertEqual(stats["exec_time"], 15.5)

    def test_emit_query_finished_select(self):
        """Test that running a SELECT query increments read tuples but not commits/rollbacks."""
        emit_query_finished(
            signals=self.signals,
            conn_data={"db_type": "sqlite"},
            query="SELECT * FROM test_table;",
            results=[(1, "Alice"), (2, "Bob")],
            columns=["id", "name"],
            column_specs=[],
            row_count=2,
            elapsed_time=5.0,
            is_select_query=True
        )

        stats = tracker.get_stats()
        self.assertEqual(stats["commits"], 0)
        self.assertEqual(stats["rollbacks"], 0)
        self.assertEqual(stats["tup_ins"], 0)
        self.assertEqual(stats["tup_fet"], 2)
        self.assertEqual(stats["tup_ret"], 2)
        self.assertEqual(stats["exec_time"], 5.0)

    def test_emit_query_finished_insert(self):
        """Test that running an INSERT query increments commits and tuple inserts."""
        emit_query_finished(
            signals=self.signals,
            conn_data={"db_type": "sqlite"},
            query="INSERT INTO test_table (id, name) VALUES (3, 'Charlie');",
            results=[],
            columns=[],
            column_specs=[],
            row_count=1,
            elapsed_time=2.3,
            is_select_query=False
        )

        stats = tracker.get_stats()
        self.assertEqual(stats["commits"], 1)
        self.assertEqual(stats["rollbacks"], 0)
        self.assertEqual(stats["tup_ins"], 1)
        self.assertEqual(stats["tup_upd"], 0)

    def test_emit_query_finished_explicit_commit_rollback(self):
        """Test that explicit COMMIT and ROLLBACK queries increment the correct tracker stats."""
        # Test explicit COMMIT
        emit_query_finished(self.signals, {}, "COMMIT;", [], [], [], 0, 1.0, True)
        self.assertEqual(tracker.get_stats()["commits"], 1)

        # Test explicit ROLLBACK
        emit_query_finished(self.signals, {}, "ROLLBACK TRANSACTION;", [], [], [], 0, 1.2, True)
        self.assertEqual(tracker.get_stats()["rollbacks"], 1)

    def test_emit_query_error(self):
        """Test that a query failure correctly increments the rollback and execution time trackers."""
        emit_query_error(
            signals=self.signals,
            conn_data={"db_type": "sqlite"},
            query="INVALID SQL QUERY",
            row_count=0,
            elapsed_time=4.1,
            error_message="Syntax Error"
        )

        stats = tracker.get_stats()
        self.assertEqual(stats["rollbacks"], 1)
        self.assertEqual(stats["exec_time"], 4.1)


class TestSQLiteStatsRetrieval(unittest.TestCase):
    """
    Unit tests for SQLite metadata and real-time monitoring retrieval
    functions inside db/db_retrieval.py.
    """

    def setUp(self):
        # Create a temporary SQLite database file for testing
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)  # Close OS file descriptor lock immediately so SQLite can access it!
        self.conn_data = {"db_type": "sqlite", "db_path": self.temp_db_path}

        # Initialize the temporary database with a test table and a few records
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, stock INTEGER)")
        cursor.execute("INSERT INTO products (name, stock) VALUES ('Laptop', 15)")
        cursor.execute("INSERT INTO products (name, stock) VALUES ('Phone', 50)")
        conn.commit()
        conn.close()

        # Reset application-level tracker
        tracker.commits = 12
        tracker.rollbacks = 2
        tracker.tup_ins = 2
        tracker.tup_upd = 1
        tracker.tup_del = 0
        tracker.tup_fet = 10
        tracker.tup_ret = 8
        tracker.exec_time = 45.0

    def tearDown(self):
        # Clean up temporary SQLite database file safely
        try:
            os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_get_sqlite_session_stats(self):
        """
        Verify that get_sqlite_session_stats returns both physical database
        level indicators (freelist, pages) and correctly propagates
        application worksheet level stats (app_commit, app_rollback, etc.).
        """
        stats = get_sqlite_session_stats(self.conn_data)
        self.assertIsNotNone(stats)

        # 1. Physical DB stats validation
        self.assertIn("tup_ins", stats)
        self.assertEqual(stats["tup_ins"], 2)  # Exact row count in 'products' table
        self.assertGreaterEqual(stats["blks_read"], 1)
        self.assertGreaterEqual(stats["blks_hit"], 1)

        # 2. Application Worksheet stats validation (our fix!)
        self.assertEqual(stats["app_commit"], 12)
        self.assertEqual(stats["app_rollback"], 2)
        self.assertEqual(stats["app_tup_ins"], 2)
        self.assertEqual(stats["app_tup_upd"], 1)
        self.assertEqual(stats["app_tup_del"], 0)
        self.assertEqual(stats["app_tup_fet"], 10)
        self.assertEqual(stats["app_tup_ret"], 8)
        self.assertEqual(stats["app_exec_time"], 45.0)

    def test_get_sqlite_state_details(self):
        """Verify get_sqlite_state_details simulates active worksheet sessions and retrieves lock status."""
        local_sessions = [
            [101, "Worksheet 1", "Active", "temp.db", "SELECT * FROM products;"]
        ]
        state = get_sqlite_state_details(self.conn_data, local_sessions=local_sessions)

        self.assertIn("sessions", state)
        self.assertIn("locks", state)

        # Verify simulated session propagation
        session_data = state["sessions"]["data"]
        self.assertEqual(len(session_data), 1)
        self.assertEqual(session_data[0][1], "Worksheet 1")
        self.assertEqual(session_data[0][2], "Active")

        # Verify Lock Status retrieval fallback or real status
        lock_data = state["locks"]["data"]
        self.assertGreaterEqual(len(lock_data), 1)
        self.assertEqual(lock_data[0][0], "main")


class TestMainWindowAndDashboard(unittest.TestCase):
    """
    Integration tests for the MainWindow GUI interface, tab management,
    and safe dashboard worker thread updates.
    """

    def setUp(self):
        self.window = MainWindow()
        # Direct closeEvent to accept without popping up a confirmation QMessageBox
        self.window.closeEvent = lambda event: event.accept()

    def tearDown(self):
        # Force stop active timers and threads on tab widgets (e.g. DashboardWidget) to avoid leaks
        for i in range(self.window.tab_widget.count()):
            widget = self.window.tab_widget.widget(i)
            if hasattr(widget, "cleanup"):
                widget.cleanup()
        self.window.close()
        QCoreApplication.processEvents()

    def test_main_window_initialization(self):
        """Verify key components and managers are initialized correctly in the Main Window."""
        self.assertIsNotNone(self.window.tab_widget)
        self.assertIsNotNone(self.window.connection_manager)
        self.assertIsNotNone(self.window.worksheet_manager)
        self.assertIsNotNone(self.window.results_manager)
        self.assertEqual(self.window.windowTitle(), "Universal SQL Client")

    def test_add_close_worksheet_tabs(self):
        """Test adding and closing worksheet tabs dynamically updates the tab widget."""
        initial_count = self.window.tab_widget.count()

        # Add 3 worksheets
        self.window.add_tab()
        self.window.add_tab()
        self.window.add_tab()
        QCoreApplication.processEvents()
        
        self.assertEqual(self.window.tab_widget.count(), initial_count + 3)

        # Close the last tab
        self.window.close_tab(self.window.tab_widget.count() - 1)
        QCoreApplication.processEvents()
        self.assertEqual(self.window.tab_widget.count(), initial_count + 2)

    def test_add_dashboard_tab_is_singleton(self):
        """Verify the add_dashboard_tab prevents multiple dashboard tabs from opening."""
        self.window.add_dashboard_tab()
        self.window.add_dashboard_tab()
        QCoreApplication.processEvents()

        dashboard_tab_count = 0
        for i in range(self.window.tab_widget.count()):
            if self.window.tab_widget.tabText(i) == "Dashboard":
                dashboard_tab_count += 1
        
        self.assertEqual(dashboard_tab_count, 1)

    def test_safe_dashboard_worker_retirement(self):
        """
        Verify that changing connection paths updates or retires DashboardWorker
        safely without triggering QThread lifecycle crashes.
        """
        self.window.add_dashboard_tab()
        dashboard = None
        for i in range(self.window.tab_widget.count()):
            widget = self.window.tab_widget.widget(i)
            if widget.__class__.__name__ == "DashboardWidget":
                dashboard = widget
                break
        
        self.assertIsNotNone(dashboard)

        # Trigger simulated SQLite connection selections
        conn_a = {"db_type": "sqlite", "db_path": "first.db"}
        conn_b = {"db_type": "sqlite", "db_path": "second.db"}

        # Mock ConnectionManager active selection
        from PySide6.QtGui import QStandardItem
        
        cm = self.window.connection_manager
        
        # Ensure there is at least one item to get a valid index from
        if cm.model.rowCount() == 0:
            cm.model.appendRow(QStandardItem("Dummy"))
        valid_index = cm.model.index(0, 0)
        
        mock_item = QStandardItem("Test SQLite")
        mock_item.setData(conn_a, Qt.ItemDataRole.UserRole)
        
        original_currentIndex = cm.tree.currentIndex
        original_mapToSource = cm.proxy_model.mapToSource
        original_itemFromIndex = cm.model.itemFromIndex
        original_get_depth = cm.get_item_depth
        
        cm.tree.currentIndex = lambda: valid_index
        cm.proxy_model.mapToSource = lambda idx: valid_index
        cm.model.itemFromIndex = lambda idx: mock_item
        cm.get_item_depth = lambda item: 3

        # Mock DashboardWorker to prevent running real background OS threads
        from widgets.dashboard.widget import DashboardWorker
        original_start = DashboardWorker.start
        original_isRunning = DashboardWorker.isRunning
        
        DashboardWorker.start = lambda self: None
        DashboardWorker.isRunning = lambda self: True

        try:
            # Simulate connection A update
            dashboard.current_conn_data = conn_a
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()

            self.assertTrue(hasattr(dashboard, "dashboard_worker"))
            self.assertIsNotNone(dashboard.dashboard_worker)

            worker_a = dashboard.dashboard_worker
            self.assertTrue(worker_a.isRunning())

            # Mark the first worker as stopped to trigger retirement logic on new connection
            worker_a.isRunning = lambda: False

            # Change to connection B
            mock_item.setData(conn_b, Qt.ItemDataRole.UserRole)
            dashboard.current_conn_data = conn_b
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()

            # The old worker should have been sent to dying list for safe garbage collection
            self.assertIn(worker_a, dashboard._dying_workers)
            self.assertNotEqual(dashboard.dashboard_worker, worker_a)
        finally:
            # Restore original methods
            cm.tree.currentIndex = original_currentIndex
            cm.proxy_model.mapToSource = original_mapToSource
            cm.model.itemFromIndex = original_itemFromIndex
            cm.get_item_depth = original_get_depth
            DashboardWorker.start = original_start
            DashboardWorker.isRunning = original_isRunning


    def test_dashboard_restricted_to_connection_depth(self):
        """Verify that selecting database type (depth 1) or group (depth 2) does not start the worker, resets the charts, and stops active worker."""
        self.window.add_dashboard_tab()
        dashboard = None
        for i in range(self.window.tab_widget.count()):
            widget = self.window.tab_widget.widget(i)
            if widget.__class__.__name__ == "DashboardWidget":
                dashboard = widget
                break
        
        self.assertIsNotNone(dashboard)

        conn_a = {"db_type": "sqlite", "db_path": "first.db"}

        # Mock ConnectionManager active selection
        from PySide6.QtGui import QStandardItem
        
        cm = self.window.connection_manager
        
        # Ensure there is at least one item to get a valid index from
        if cm.model.rowCount() == 0:
            cm.model.appendRow(QStandardItem("Dummy"))
        valid_index = cm.model.index(0, 0)
        
        mock_item = QStandardItem("Test SQLite")
        mock_item.setData(conn_a, Qt.ItemDataRole.UserRole)
        
        original_currentIndex = cm.tree.currentIndex
        original_mapToSource = cm.proxy_model.mapToSource
        original_itemFromIndex = cm.model.itemFromIndex
        original_get_depth = cm.get_item_depth
        
        cm.tree.currentIndex = lambda: valid_index
        cm.proxy_model.mapToSource = lambda idx: valid_index
        cm.model.itemFromIndex = lambda idx: mock_item
        
        # Mock DashboardWorker to prevent running real background OS threads
        from widgets.dashboard.widget import DashboardWorker
        original_start = DashboardWorker.start
        original_isRunning = DashboardWorker.isRunning
        
        DashboardWorker.start = lambda self: None
        DashboardWorker.isRunning = lambda self: True

        try:
            # 1. Depth == 3: should start worker
            cm.get_item_depth = lambda item: 3
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()
            self.assertIsNotNone(dashboard.dashboard_worker)
            self.assertIsNotNone(dashboard.current_conn_data)
            
            # Mock the worker isRunning state to True for retirement check
            dashboard.dashboard_worker.isRunning = lambda: True

            # 2. Depth == 2 (Group level): should retire worker and reset
            cm.get_item_depth = lambda item: 2
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()
            self.assertIsNone(dashboard.dashboard_worker)
            self.assertIsNone(dashboard.current_conn_data)
            
            # 3. Repeat for Depth == 1 (Type level)
            cm.get_item_depth = lambda item: 3
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()
            self.assertIsNotNone(dashboard.dashboard_worker)
            dashboard.dashboard_worker.isRunning = lambda: True
            
            cm.get_item_depth = lambda item: 1
            dashboard.request_stats_update(manual=True)
            QCoreApplication.processEvents()
            self.assertIsNone(dashboard.dashboard_worker)
            self.assertIsNone(dashboard.current_conn_data)
            
        finally:
            cm.tree.currentIndex = original_currentIndex
            cm.proxy_model.mapToSource = original_mapToSource
            cm.model.itemFromIndex = original_itemFromIndex
            cm.get_item_depth = original_get_depth
            DashboardWorker.start = original_start
            DashboardWorker.isRunning = original_isRunning


class TestDashboardStateTables(unittest.TestCase):
    """
    Unit tests for the dashboard table views (Sessions & Locks tables)
    inside widgets.dashboard.state_widget.StateWidget.
    """

    def setUp(self):
        from widgets.dashboard.state_widget import StateWidget
        self.state_widget = StateWidget()

    def tearDown(self):
        self.state_widget.deleteLater()
        QCoreApplication.processEvents()

    def test_sqlite_tables_initialization_and_headers(self):
        """Verify that SQLite connection type hides locks and initializes sessions correctly."""
        self.state_widget.set_db_type("sqlite")
        self.assertTrue(self.state_widget.locks_frame.isHidden())
        self.assertFalse(self.state_widget.sessions_frame.isHidden())

        sqlite_state_data = {
            "sessions": {
                "columns": ["PID", "Source", "State", "Database", "SQL"],
                "data": [
                    [5678, "Worksheet 1", "Idle", "sqlite_db.db", "SELECT * FROM sqlite_master;"]
                ]
            },
            "locks": {
                "columns": ["Database", "Lock Status"],
                "data": [
                    ["main", "unlocked"]
                ]
            }
        }

        self.state_widget.update_state(sqlite_state_data)

        # Verify sessions table columns and headers
        table = self.state_widget.sessions_table
        self.assertEqual(table.rowCount(), 1)
        self.assertEqual(table.columnCount(), 7) # Terminate, Cancel, Details + 4 display columns (PID, Source, State, Database)
        
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        expected_headers = ["Terminate", "Cancel", "Details", "PID", "Source", "State", "Database"]
        self.assertEqual(headers, expected_headers)

        # Verify cell values
        self.assertEqual(table.item(0, 3).text(), "5678")
        self.assertEqual(table.item(0, 4).text(), "Worksheet 1")
        self.assertEqual(table.item(0, 5).text(), "Idle")
        self.assertEqual(table.item(0, 6).text(), "sqlite_db.db")

        # Verify locks table (even if hidden, check it was filled)
        locks_table = self.state_widget.locks_table
        self.assertEqual(locks_table.rowCount(), 1)
        self.assertEqual(locks_table.columnCount(), 2)
        locks_headers = [locks_table.horizontalHeaderItem(i).text() for i in range(locks_table.columnCount())]
        self.assertEqual(locks_headers, ["Database", "Lock Status"])
        self.assertEqual(locks_table.item(0, 0).text(), "main")
        self.assertEqual(locks_table.item(0, 1).text(), "unlocked")

    def test_postgres_tables_initialization_and_headers(self):
        """Verify that PostgreSQL connection type shows locks and sets up headers correctly."""
        self.state_widget.set_db_type("postgres")
        self.assertFalse(self.state_widget.locks_frame.isHidden())

        postgre_state_data = {
            "sessions": {
                "columns": ["pid", "Database", "User", "Application", "Client", "Backend start", "Transaction start", "State", "Wait event", "Blocking PIDs", "Backend type", "Query start", "State change", "SQL"],
                "data": [
                    [1234, "test_db", "test_user", "App1", "127.0.0.1:5432", "2026-05-21 10:00:00", None, "active", None, [], "client backend", "2026-05-21 10:01:00", "2026-05-21 10:01:05", "SELECT * FROM test_table;"]
                ]
            },
            "locks": {
                "columns": ["pid", "Lock type", "Target relation", "Mode", "Granted?"],
                "data": [
                    [1234, "relation", "test_table", "AccessShareLock", True]
                ]
            }
        }

        self.state_widget.update_state(postgre_state_data)

        # Verify sessions table columns and headers
        table = self.state_widget.sessions_table
        self.assertEqual(table.rowCount(), 1)
        # 14 columns total, 4 are detail_cols -> 10 display columns + 3 action columns = 13 columns total
        self.assertEqual(table.columnCount(), 13)
        
        headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
        expected_headers = ["Terminate", "Cancel", "Details", "pid", "Database", "User", "Application", "Client", "Backend start", "Transaction start", "State", "Wait event", "Blocking PIDs"]
        self.assertEqual(headers, expected_headers)

        self.assertEqual(table.item(0, 3).text(), "1234")
        self.assertEqual(table.item(0, 4).text(), "test_db")
        self.assertEqual(table.item(0, 5).text(), "test_user")

        # Verify locks table columns and headers
        locks_table = self.state_widget.locks_table
        self.assertEqual(locks_table.rowCount(), 1)
        self.assertEqual(locks_table.columnCount(), 5)
        locks_headers = [locks_table.horizontalHeaderItem(i).text() for i in range(locks_table.columnCount())]
        self.assertEqual(locks_headers, ["pid", "Lock type", "Target relation", "Mode", "Granted?"])

    def test_filtering_and_searching(self):
        """Verify search filtering filters the rows displayed in the tables."""
        self.state_widget.set_db_type("postgres")
        postgre_state_data = {
            "sessions": {
                "columns": ["pid", "Database", "User", "Application", "SQL"],
                "data": [
                    [111, "db_one", "user_a", "AppA", "SELECT 1;"],
                    [222, "db_two", "user_b", "AppB", "SELECT 2;"]
                ]
            },
            "locks": {
                "columns": ["pid", "Lock type", "Mode"],
                "data": [
                    [111, "relation", "Exclusive"],
                    [222, "tuple", "Shared"]
                ]
            }
        }

        self.state_widget.update_state(postgre_state_data)
        self.assertEqual(self.state_widget.sessions_table.rowCount(), 2)
        self.assertEqual(self.state_widget.locks_table.rowCount(), 2)

        # Apply search filter on sessions
        self.state_widget.sessions_frame.search_input.setText("db_one")
        self.state_widget._on_search()
        self.assertEqual(self.state_widget.sessions_table.rowCount(), 1)
        self.assertEqual(self.state_widget.sessions_table.item(0, 4).text(), "db_one")

        # Clear search filter on sessions
        self.state_widget.sessions_frame.search_input.setText("")
        self.state_widget._on_search()
        self.assertEqual(self.state_widget.sessions_table.rowCount(), 2)

        # Apply search filter on locks
        self.state_widget.locks_frame.search_input.setText("Shared")
        self.state_widget._on_search()
        self.assertEqual(self.state_widget.locks_table.rowCount(), 1)
        self.assertEqual(self.state_widget.locks_table.item(0, 2).text(), "Shared")

    def test_toggle_details_and_panel(self):
        """Verify that toggling the details expands/collapses the row and displays DetailsPanel."""
        from widgets.dashboard.state_widget import DetailsPanel
        self.state_widget.set_db_type("postgres")
        postgre_state_data = {
            "sessions": {
                "columns": ["pid", "Database", "User", "Application", "Backend type", "Query start", "State change", "SQL"],
                "data": [
                    [1234, "test_db", "test_user", "App1", "client backend", "2026-05-21 10:01:00", "2026-05-21 10:01:05", "SELECT * FROM test_table;"]
                ]
            },
            "locks": {
                "columns": ["pid", "Lock type"],
                "data": []
            }
        }

        self.state_widget.update_state(postgre_state_data)
        table = self.state_widget.sessions_table
        self.assertEqual(table.rowCount(), 1)

        # Toggle details ON
        self.state_widget.toggle_details(1234)
        # Row count increases by 1 to show detail panel
        self.assertEqual(table.rowCount(), 2)
        
        # Check details panel exists
        panel_widget = table.cellWidget(1, 0)
        self.assertIsNotNone(panel_widget)
        self.assertIsInstance(panel_widget, DetailsPanel)
        self.assertEqual(panel_widget.sql_view.toPlainText(), "SELECT * FROM test_table;")

        # Toggle details OFF
        self.state_widget.toggle_details(1234)
        self.assertEqual(table.rowCount(), 1)

    def test_clear_state(self):
        """Verify calling clear_state wipes table rows and cached data."""
        self.state_widget.set_db_type("postgres")
        postgre_state_data = {
            "sessions": {
                "columns": ["pid", "Database"],
                "data": [[1234, "test_db"]]
            },
            "locks": {
                "columns": ["pid", "Lock type"],
                "data": [[1234, "relation"]]
            }
        }

        self.state_widget.update_state(postgre_state_data)
        self.assertEqual(self.state_widget.sessions_table.rowCount(), 1)
        self.assertEqual(self.state_widget.locks_table.rowCount(), 1)

        self.state_widget.clear_state()
        self.assertEqual(self.state_widget.sessions_table.rowCount(), 0)
        self.assertEqual(self.state_widget.locks_table.rowCount(), 0)
        self.assertIsNone(self.state_widget.last_state_data)

    def test_action_buttons_and_callbacks(self):
        """Verify clicking action buttons calls the respective terminate/cancel handlers."""
        self.state_widget.set_db_type("postgres")
        postgre_state_data = {
            "sessions": {
                "columns": ["pid", "Database", "User", "Application"],
                "data": [
                    [9999, "test_db", "test_user", "App1"]
                ]
            },
            "locks": {
                "columns": ["pid"],
                "data": []
            }
        }
        # Mock handlers BEFORE updating state so that callback references connect to the mocks
        import unittest.mock as mock
        self.state_widget.handle_terminate = mock.MagicMock()
        self.state_widget.handle_cancel = mock.MagicMock()
        self.state_widget.toggle_details = mock.MagicMock()

        self.state_widget.update_state(postgre_state_data)

        # Get buttons from cells
        # Columns: 0 = Terminate, 1 = Cancel, 2 = Details
        term_widget = self.state_widget.sessions_table.cellWidget(0, 0)
        cancel_widget = self.state_widget.sessions_table.cellWidget(0, 1)
        details_widget = self.state_widget.sessions_table.cellWidget(0, 2)

        from PySide6.QtWidgets import QPushButton

        # Click Terminate
        term_btn = term_widget.findChild(QPushButton)
        term_btn.click()
        self.state_widget.handle_terminate.assert_called_once_with(9999)

        # Click Cancel
        cancel_btn = cancel_widget.findChild(QPushButton)
        cancel_btn.click()
        self.state_widget.handle_cancel.assert_called_once_with(9999)

        # Click Details
        details_btn = details_widget.findChild(QPushButton)
        details_btn.click()
        self.state_widget.toggle_details.assert_called_once_with(9999)


if __name__ == "__main__":
    print("[TEST] Running Universal SQL Client Test Suite...\n")
    unittest.main()
