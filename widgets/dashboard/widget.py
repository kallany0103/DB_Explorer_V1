from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QGridLayout, QGraphicsLineItem, QGraphicsEllipseItem,
                               QTabWidget)
from PySide6.QtCore import Qt, QTimer, QRunnable, QObject, Signal, Slot, QPointF, QThread
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush  # QBrush kept for marker ellipses
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from widgets.dashboard.state_widget import StateWidget, StateWorker
import qtawesome as qta
import db
from datetime import datetime
import time

class ChartTooltip(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(4)
        
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff !important;
                border: 1px solid #d1d5db !important;
                border-radius: 4px !important;
            }
            QLabel {
                color: #111827 !important;
                font-family: 'Segoe UI', Arial, sans-serif !important;
                border: none !important;
                background: transparent !important;
            }
        """)
        
        self.time_label = QLabel()
        self.time_label.setStyleSheet("font-size: 11px !important; color: #6b7280 !important; font-weight: bold !important;")
        self.layout.addWidget(self.time_label)
        
        self.items_layout = QVBoxLayout()
        self.items_layout.setSpacing(3)
        self.layout.addLayout(self.items_layout)

    def update_content(self, time_text, data_items):
        self.time_label.setText(time_text)
        
        # Clear existing rows
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            
        for name, value, color in data_items:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            
            lbl = QLabel(f"<b>{name}:</b> <span style='font-size: 13px; font-weight: bold;'>{value}</span>")
            lbl.setStyleSheet("font-size: 12px !important; color: #111827 !important;")
            
            h.addWidget(dot)
            h.addWidget(lbl)
            h.addStretch()
            self.items_layout.addWidget(row)
        
        self.adjustSize()

class DashboardWorkerSignals(QObject):
    finished = Signal(object, object) # stats, conn_data
    error = Signal(object)

class DashboardWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, conn_data, current_db_only, parent=None):
        super().__init__(parent)
        self.conn_data = conn_data
        self.current_db_only = current_db_only
        self._is_running = True
        self._needs_reconnect = False

    def update_connection(self, conn_data, current_db_only):
        """Safely update the connection parameters without restarting the thread."""
        if self.conn_data != conn_data or self.current_db_only != current_db_only:
            self.conn_data = conn_data
            self.current_db_only = current_db_only
            self._needs_reconnect = True

    def stop(self):
        self._is_running = False

    def run(self):
        conn = None
        while self._is_running:
            try:
                # If parameters changed, force a reconnection
                if self._needs_reconnect:
                    if conn:
                        try:
                            db.return_pooled_postgres_connection(self.conn_data, conn=conn)
                        except:
                            pass
                    conn = None
                    self._needs_reconnect = False

                db_type = str(self.conn_data.get("db_type", "")).lower()
                if "sqlite" in db_type:
                    stats = db.get_sqlite_session_stats(self.conn_data)
                else:
                    # Use pooled connection for PostgreSQL (more efficient)
                    if conn is None:
                        db_name = self.conn_data.get("database", "postgres")
                        app_name = f"Universal SQL Client (Dashboard) - {db_name}"
                        conn = db.get_pooled_postgres_connection(
                            self.conn_data, 
                            application_name=app_name,
                            use_pool=True
                        )
                        if conn:
                            conn.set_session(readonly=True, autocommit=True)
                    
                    stats = db.get_postgres_session_stats(self.conn_data, self.current_db_only, conn=conn)
                
                if self._is_running and not self._needs_reconnect:
                    self.finished.emit(stats, self.conn_data)
            except Exception as e:
                err_msg = str(e).lower()
                # If connection dropped, clear conn so it reconnects on next loop.
                if "closed" in err_msg or "connection" in err_msg or "timeout" in err_msg or "terminated" in err_msg:
                    if conn:
                        try:
                            db.return_pooled_postgres_connection(self.conn_data, conn=conn)
                        except:
                            pass
                    conn = None

                if self._is_running and not self._needs_reconnect:
                    if "timeout" not in err_msg and "connection" not in err_msg and "unreachable" not in err_msg:
                        self.error.emit(str(e))
            
            # Sleep for 1 second, but check for stop/reconnect signals frequently
            for _ in range(10):
                if not self._is_running or self._needs_reconnect:
                    break
                self.msleep(100)

        # Cleanup connection on thread exit
        if conn:
            try:
                db.return_pooled_postgres_connection(self.conn_data, conn=conn)
            except: pass

class LiveChartView(QChartView):
    def __init__(self, series_names, colors, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)

        self.chart_obj = QChart()
        self.chart_obj.legend().setVisible(False)
        self.chart_obj.layout().setContentsMargins(0, 0, 0, 0)
        self.chart_obj.setBackgroundRoundness(0)

        self.series_list = []

        for name, color in zip(series_names, colors):
            qcolor = QColor(color)

            line = QLineSeries()
            line.setName(name)
            line_pen = QPen(qcolor)
            line_pen.setWidth(2)
            line.setPen(line_pen)

            self.series_list.append(line)
            self.chart_obj.addSeries(line)

        self.max_points = 60
        self.x_counter = 0

        for series in self.series_list:
            for i in range(self.max_points):
                series.append(i, 0)
        self.x_counter = self.max_points - 1

        self.axis_x = QValueAxis()
        self.axis_x.setLineVisible(False)
        self.axis_x.setLabelsVisible(False)
        self.axis_x.setGridLineVisible(False)
        self.axis_x.setRange(0, self.max_points - 1)
        self.chart_obj.addAxis(self.axis_x, Qt.AlignmentFlag.AlignBottom)

        for series in self.series_list:
            series.attachAxis(self.axis_x)

        self.axis_y = QValueAxis()
        self.axis_y.setRange(0, 5)
        self.axis_y.setTickCount(6)
        self.axis_y.setLabelFormat("%d")

        grid_pen = QPen(QColor("#e5e7eb"))
        grid_pen.setWidth(1)
        self.axis_y.setGridLinePen(grid_pen)
        self.axis_y.setLineVisible(False)
        self.axis_y.setLabelsColor(QColor("#4b5563"))

        font = QFont()
        font.setPointSize(9)
        self.axis_y.setLabelsFont(font)

        self.chart_obj.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        for series in self.series_list:
            series.attachAxis(self.axis_y)

        self.setChart(self.chart_obj)
        self.setStyleSheet("background-color: transparent;")

        # Custom Tooltip and Crosshair elements
        self.v_line = QGraphicsLineItem()
        self.v_line.setPen(QPen(QColor("#6b7280"), 1, Qt.PenStyle.DashLine))
        self.chart().scene().addItem(self.v_line)
        self.v_line.hide()

        self.marker_items = []  # Circles on series
        self.floating_tooltip = ChartTooltip(self)

    def reset_series(self, _=None):
        """Clears all data points from the series and resets the counters."""
        self.x_counter = 0
        for series in self.series_list:
            series.clear()
            # Re-fill with initial zeros to maintain the scroll effect
            for i in range(self.max_points):
                series.append(i, 0)
        self.x_counter = self.max_points - 1
        self.axis_x.setRange(0, self.max_points - 1)
        self.axis_y.setRange(0, 5)

    def update_values(self, values):
        self.x_counter += 1
        for series, val in zip(self.series_list, values):
            series.append(self.x_counter, val)
            if series.count() > self.max_points + 20:
                series.remove(0)

        self.axis_x.setRange(self.x_counter - self.max_points + 1, self.x_counter)

        # Compute the true max across ALL visible points in the window,
        # not just the current tick. This prevents the axis from snapping
        # back down one tick after a spike while the spike is still visible.
        visible_min_x = self.x_counter - self.max_points + 1
        window_max = 0
        for series in self.series_list:
            for p in series.pointsVector():
                if p.x() >= visible_min_x:
                    window_max = max(window_max, p.y())

        max_val = max(window_max, 5)
        current_max_y = self.axis_y.max()

        # Grow axis if any visible data exceeds 90% of current range
        if max_val > current_max_y * 0.9:
            new_max = max(max_val * 1.2, 10)
            self.axis_y.setRange(0, new_max)
        # Only shrink once ALL visible points drop well below the current range
        elif max_val < current_max_y * 0.15 and current_max_y > 10:
            new_max = max(max_val * 2, 5)
            self.axis_y.setRange(0, new_max)

    def mouseMoveEvent(self, event):
        if not self.series_list:
            super().mouseMoveEvent(event)
            return

        # Map mouse position to value
        val = self.chart().mapToValue(event.position())
        x_val = int(round(val.x()))
        
        # Check if x_val is within the visible range
        if x_val < self.axis_x.min() or x_val > self.axis_x.max():
            self.toggle_custom_tooltip(False)
            super().mouseMoveEvent(event)
            return

        data_items = []
        marker_positions = []
        
        for series in self.series_list:
            points = series.pointsVector()
            target_p = None
            for p in points:
                if int(round(p.x())) == x_val:
                    target_p = p
                    break
            
            if target_p:
                val_y = target_p.y()
                # Use float with 1 decimal for rates, but if it's very close to an int, show int
                if abs(val_y - round(val_y)) < 0.01:
                    formatted_val = f"{int(round(val_y))}"
                else:
                    formatted_val = f"{val_y:.1f}"
                color = series.pen().color().name()
                data_items.append((series.name(), formatted_val, color))
                
                # Screen position for marker
                screen_pos = self.chart().mapToPosition(target_p)
                marker_positions.append((screen_pos, color))

        if data_items:
            # 1. Update Tooltip
            diff = int(self.x_counter - x_val)
            time_text = f"{diff} seconds ago" if diff > 0 else "Just now"
            self.floating_tooltip.update_content(time_text, data_items)
            
            # Position tooltip near cursor
            t_pos = event.globalPosition().toPoint()
            self.floating_tooltip.move(t_pos.x() + 15, t_pos.y() + 15)
            self.floating_tooltip.show()
            
            # 2. Update Vertical Line
            # Get chart plot area
            plot_rect = self.chart().plotArea()
            line_x = self.chart().mapToPosition(QPointF(x_val, 0)).x()
            self.v_line.setLine(line_x, plot_rect.top(), line_x, plot_rect.bottom())
            self.v_line.show()
            
            # 3. Update Markers
            # Clear old markers
            for m in self.marker_items:
                self.chart().scene().removeItem(m)
            self.marker_items.clear()
            
            for pos, color in marker_positions:
                r = 4
                ellipse = QGraphicsEllipseItem(pos.x() - r, pos.y() - r, r*2, r*2)
                ellipse.setBrush(QBrush(QColor(color)))
                ellipse.setPen(QPen(Qt.GlobalColor.white, 1))
                self.chart().scene().addItem(ellipse)
                self.marker_items.append(ellipse)
        else:
            self.toggle_custom_tooltip(False)

        super().mouseMoveEvent(event)

    def toggle_custom_tooltip(self, visible):
        if not visible:
            self.floating_tooltip.hide()
            self.v_line.hide()
            for m in self.marker_items:
                self.chart().scene().removeItem(m)
            self.marker_items.clear()

    def leaveEvent(self, event):
        self.toggle_custom_tooltip(False)
        super().leaveEvent(event)

class LiveChartWidget(QFrame):
    def __init__(self, title, series_names, colors, parent=None, hide_legends=False):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet("background-color: #f8f9fb; border: none; border-bottom: 1px solid #e0e0e0; border-top-left-radius: 4px; border-top-right-radius: 4px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #111111; border: none; background: transparent;")
        h_layout.addWidget(self.title_lbl)
        h_layout.addStretch()
        
        for name, color in zip(series_names, colors):
            item = QWidget()
            item.setStyleSheet("border: none;")
            legend_layout = QHBoxLayout(item)
            legend_layout.setContentsMargins(4, 0, 4, 0)
            sq = QLabel()
            sq.setFixedSize(10, 10)
            sq.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: none;")
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 13px !important; color: #111111 !important; font-weight: bold !important; border: none !important; background: transparent !important;")
            legend_layout.addWidget(sq)
            legend_layout.addWidget(lbl)
            if not hide_legends:
                h_layout.addWidget(item)
            else:
                item.hide() # Keep the widget but hide it if requested
            
        # Extra info container for labels like "Worksheets: 0"
        self.extra_info_layout = QHBoxLayout()
        self.extra_info_layout.setSpacing(15)
        self.extra_info_layout.setContentsMargins(15, 0, 0, 0)
        h_layout.addLayout(self.extra_info_layout)
        self.extra_labels = {}
            
        self.chart_view = LiveChartView(series_names, colors)
        self.chart_view.setStyleSheet("border: none; border-radius: 0px;")
        
        layout.addWidget(header)
        layout.addWidget(self.chart_view)

    def set_extra_info(self, key, label_text, value, color="#6366f1"):
        """Adds or updates a text label in the header."""
        if key not in self.extra_labels:
            lbl = QLabel(f"{label_text}: {value}")
            lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color}; border: none; background: transparent; margin-left: 15px;")
            lbl.setMinimumWidth(200) # Ensure enough space for 'Universal SQL Client'
            self.extra_info_layout.addWidget(lbl)
            self.extra_labels[key] = (lbl, label_text)
        else:
            lbl, base_label = self.extra_labels[key]
            lbl.setText(f"{base_label}: {value}")

class DashboardWidget(QWidget):
    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def _retire_worker(self, worker):
        """Gracefully stop a worker, keeping it alive until its thread exits."""
        if worker is None:
            return
        self._dying_workers.append(worker)
        worker.stop()
        # Once the thread finishes Qt will call deleteLater; we also remove
        # the Python reference from _dying_workers so it can be collected.
        try:
            worker.finished.disconnect()
        except Exception:
            pass
        worker.finished.connect(lambda *_: self._dying_workers.remove(worker)
                                if worker in self._dying_workers else None)
        worker.finished.connect(worker.deleteLater)

    def cleanup(self):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        
        # Stop active worker and wait for it to exit cleanly
        if hasattr(self, 'dashboard_worker') and self.dashboard_worker.isRunning():
            self.dashboard_worker.stop()
            self.dashboard_worker.wait(5000)  # Wait up to 5 seconds
        
        # Also wait for any retiring workers that haven't finished yet
        for w in list(self._dying_workers):
            if w.isRunning():
                w.wait(3000)

    def hideEvent(self, event):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.start(1000)
    def refresh_requested(self, *args):
        """Triggered by the manual refresh button or state tab refresh."""
        self.request_stats_update(manual=True)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #ffffff;")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.request_stats_update)
        
        self.prev_stats = None
        # Holds workers that are stopping — keeps Python reference alive until
        # the thread finishes so Qt never destroys a running QThread.
        self._dying_workers = []
        self.setup_ui()
        self.request_stats_update() # Initial call to set labels immediately
        self.refresh_timer.start(1000) # 1 second refresh for activity
        
        # Ensure cleanup on app exit
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanup)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { 
                border-top: 1px solid #B8BEC6;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #ECEFF3;
                color: #111827;
                padding: 6px 12px;
                border: 1px solid #B8BEC6;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 9pt;
            }
            QTabBar::tab:selected {
                background: #8E959E;
                color: #ffffff;
                border-bottom: 2px solid #8E959E;
            }
            QTabBar::tab:hover {
                background: #DDE2E8;
            }
        """)

        # 1. Activity Tab
        self.activity_tab = QWidget()
        self.setup_activity_ui()
        self.tabs.addTab(self.activity_tab, qta.icon('mdi.chart-line', color="#121213"), "Activity")

        # 2. State Tab
        self.state_widget = StateWidget()
        self.state_widget.refresh_requested.connect(self.refresh_requested)
        self.tabs.addTab(self.state_widget, qta.icon('mdi.database-search', color="#121213"), "State")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) == self.state_widget:
            self.request_stats_update(manual=True)

    def setup_activity_ui(self):
        main_layout = QVBoxLayout(self.activity_tab)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # Grid for charts - 6 column grid to allow 2-chart and 3-chart rows
        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        
        # Sessions chart - show Total/Active/Idle legends
        self.sessions_chart = LiveChartWidget(
            "Database sessions",
            ["Total", "Active", "Idle"],
            ["#3b82f6", "#f59e0b", "#10b981"]
        )
        self.tps_chart = LiveChartWidget(
            "Transactions", 
            ["Transactions", "Commits", "Rollbacks"], 
            ["#1f77b4", "#f59e0b", "#ef4444"] # blue, orange, red
        )


        
        # Delta counts instead of rates for better row-level visibility
        self.tuples_in_chart = LiveChartWidget("Tuples In", ["Inserts", "Updates", "Deletes"], ["#1f77b4", "#f59e0b", "#10b981"])
        self.tuples_out_chart = LiveChartWidget("Tuples Out", ["Fetched", "Returned"], ["#1f77b4", "#f59e0b"])
        self.block_io_chart = LiveChartWidget("Block I/O (Count)", ["Reads", "Hits"], ["#1f77b4", "#f59e0b"])

        
        self.no_connection_lbl = QLabel("Please select a PostgreSQL connection in the Explorer to see live metrics.")
        self.no_connection_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_connection_lbl.setStyleSheet("color: #64748b; font-style: italic; font-size: 13px; padding: 10px; background: #f8fafc; border-radius: 4px; border: 1px dashed #cbd5e1;")
        self.no_connection_lbl.hide()
        
        # Row 0: 2 charts (each spans 3 columns)
        grid_layout.addWidget(self.sessions_chart, 0, 0, 1, 3)
        grid_layout.addWidget(self.tps_chart, 0, 3, 1, 3)
        
        # Row 1: 3 charts (each spans 2 columns)
        grid_layout.addWidget(self.tuples_in_chart, 1, 0, 1, 2)
        grid_layout.addWidget(self.tuples_out_chart, 1, 2, 1, 2)
        grid_layout.addWidget(self.block_io_chart, 1, 4, 1, 2)
        
        # Grid for charts ... (code removed for brevity, will replace carefully)
        
        main_layout.addWidget(self.no_connection_lbl)
        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

    def request_stats_update(self, manual=False):
        # Activity (charts) always refresh every 1s for "live" feel
        # State (tables) refresh every 3s OR if manual is requested
        
        # Locate the MainWindow
        main_window = None
        curr = self
        while curr:
            if curr.__class__.__name__ == "MainWindow":
                main_window = curr
                break
            curr = curr.parent()
        
        if not main_window or not hasattr(main_window, "connection_manager"):
            return

        cm = main_window.connection_manager
        
        # 1. Detect Selection Type and get conn_data
        index = cm.tree.currentIndex()
        if not index.isValid():
            return

        source_idx = cm.proxy_model.mapToSource(index)
        item = cm.model.itemFromIndex(source_idx)
        if not item:
            return

        # Determine level:
        # Depth 1: Type (e.g. PostgreSQL Databases)
        # Depth 2: Group (e.g. aiven.io)
        # Depth 3: Connection (e.g. AIVEN_TEST_DATABASE)
        depth = cm.get_item_depth(item)
        
        conn_data = None
        current_db_only = False

        if depth == 3:
            # Connection level
            conn_data = item.data(Qt.ItemDataRole.UserRole)
            self.current_conn_data = conn_data
            current_db_only = True
        elif depth == 2:
            # Group level -> Show server-wide for the first connection in group
            if item.hasChildren():
                child = item.child(0)
                conn_data = child.data(Qt.ItemDataRole.UserRole)
                self.current_conn_data = conn_data
            current_db_only = False
        else:
            # depth 1 or unknown -> placeholder state
            conn_data = None

        # Always ensure charts are visible
        self.sessions_chart.setVisible(True)
        self.tps_chart.setVisible(True)
        self.tuples_in_chart.setVisible(True)
        self.tuples_out_chart.setVisible(True)
        self.block_io_chart.setVisible(True)
        self.no_connection_lbl.setVisible(False)

        if not conn_data:
            self.sessions_chart.title_lbl.setText("Sessions")
            self.tps_chart.title_lbl.setText("Transactions")
            self.reset_all_charts()
            return

        # Show/Hide State tab based on connection type
        db_type_val = str(conn_data.get("db_type", "")).lower()
        is_postgres = "postgres" in db_type_val
        is_sqlite = "sqlite" in db_type_val
        
        self.state_widget.set_db_type(db_type_val)
        
        # Track connection change to clear charts
        if not hasattr(self, 'last_processed_conn') or self.last_processed_conn != conn_data:
            self.last_processed_conn = conn_data
            self.prev_stats = None
            self.prev_time = None
            self.reset_all_charts()
            manual = True # Force a state refresh for the new connection

        # Live metrics are currently supported for Postgres and SQLite
        has_live_metrics = is_postgres or is_sqlite
        
        # Note: We keep them visible as per user request to avoid UI "jumping"
        
        if not has_live_metrics:
            if db_type_val in ["servicenow", "csv"]:
                self.no_connection_lbl.setText(f"Dashboard is not supported for {db_type_val.upper()} connections.")
            else:
                self.no_connection_lbl.setText("Please select a PostgreSQL or SQLite connection to see live metrics.")
            return

        # State tab is now supported for both PostgreSQL and SQLite
        self.tabs.setTabVisible(1, True)

        # 2. Activity Stats Update (Use persistent worker)
        if hasattr(self, 'dashboard_worker') and self.dashboard_worker.isRunning():
            # Simply update the existing worker's targets
            self.dashboard_worker.update_connection(conn_data, current_db_only)
        else:
            # Retire the old worker safely before replacing it.
            # _retire_worker() keeps the Python reference alive via _dying_workers
            # until the thread finishes, preventing the "destroyed while running" crash.
            if hasattr(self, 'dashboard_worker'):
                self._retire_worker(self.dashboard_worker)
                self.dashboard_worker = None
            # Start a fresh worker (no Qt parent — lifetime managed by self)
            self.dashboard_worker = DashboardWorker(conn_data, current_db_only)
            self.dashboard_worker.finished.connect(self.update_dashboard_stats)
            self.dashboard_worker.start()

        # 3. State Details Update 
        # Only if: (State tab is active AND manual requested)
        now_ts = time.time()
        
        is_state_active = self.tabs.currentWidget() == self.state_widget
        # Disable automatic refresh as per user request (only refresh when manual is True)
        should_refresh_state = manual

        if should_refresh_state and is_state_active:
            self.last_state_refresh = now_ts
            self.state_widget.conn_data = conn_data
            
            local_sessions = None
            if is_sqlite:
                local_sessions = self.get_sqlite_session_details_list(conn_data.get("db_path"))
            
            state_worker = StateWorker(conn_data, self.state_widget.active_checkbox.isChecked(), local_sessions=local_sessions)
            state_worker.signals.finished.connect(self.state_widget.update_state)
            state_worker.signals.error.connect(lambda err: print(f"Dashboard state worker error: {err}"))
            main_window.thread_pool.start(state_worker)
        
        # Update chart titles dynamically
        prefix = "Sessions"
        tps_prefix = "Transactions"
        if depth == 3:
            prefix = f"Sessions for: {item.text()}"
            tps_prefix = f"TPS for: {item.text()}"
        elif depth == 2:
            prefix = f"Server Sessions: {item.text()}"
            tps_prefix = f"Server TPS: {item.text()}"
            
        self.sessions_chart.title_lbl.setText(prefix)
        self.tps_chart.title_lbl.setText(tps_prefix)
        
            
    def get_local_postgres_sessions(self, db_name):
        """Counts open and active worksheets for a specific PostgreSQL database."""
        main_window = self._get_main_window()
        if not main_window or not hasattr(main_window, 'tab_widget'):
            return 0, 0
            
        total = 0
        active = 0
        target_db = str(db_name).lower().strip() if db_name else ""
        
        from PySide6.QtWidgets import QComboBox
        for i in range(main_window.tab_widget.count()):
            tab = main_window.tab_widget.widget(i)
            # Search for the combo box specifically in the worksheet tab
            combo = tab.findChild(QComboBox, "db_combo_box")
            if combo:
                data = combo.currentData()
                if isinstance(data, dict):
                    tab_db = str(data.get('database', '')).lower().strip()
                    if tab_db == target_db:
                        total += 1
                        # Check if query is running in this tab
                        if hasattr(main_window, 'worksheet_manager'):
                            if tab in main_window.worksheet_manager.running_queries:
                                active += 1
        return total, active

    def reset_all_charts(self):
        """Wipes all data from charts and tables when switching databases."""
        charts = [
            self.sessions_chart, self.tps_chart, 
            self.tuples_in_chart, self.tuples_out_chart, self.block_io_chart
        ]
        for chart_widget in charts:
            if hasattr(chart_widget, 'chart_view'):
                chart_widget.chart_view.reset_series()
        
        # Also clear the State tab tables
        if hasattr(self, 'state_widget'):
            self.state_widget.clear_state()
        

    def get_local_sqlite_sessions(self, db_path):
        """Calculates session counts for SQLite based on open worksheets in the app."""
        main_window = self._get_main_window()
        if not main_window or not hasattr(main_window, 'tab_widget'):
            return 1, 1, 0
            
        total = 0
        active = 0
        
        import os
        target_path = os.path.normpath(db_path).lower() if db_path else ""
        
        from PySide6.QtWidgets import QComboBox
        for i in range(main_window.tab_widget.count()):
            tab = main_window.tab_widget.widget(i)
            # Find the connection combo in this tab
            combo = tab.findChild(QComboBox, "db_combo_box")
            if combo:
                data = combo.currentData()
                if isinstance(data, dict):
                    path = data.get('db_path')
                    if path and os.path.normpath(path).lower() == target_path:
                        total += 1
                        # Check if this tab is running a query in WorksheetManager
                        if hasattr(main_window, 'worksheet_manager'):
                            if tab in main_window.worksheet_manager.running_queries:
                                active += 1
        
        # Return exact counts based on open worksheets
        return total, active, max(total - active, 0)

    def get_sqlite_session_details_list(self, db_path):
        """Collects detailed session info for SQLite worksheets to show in the State tab."""
        main_window = self._get_main_window()
        if not main_window or not hasattr(main_window, 'tab_widget'):
            return []
            
        sessions = []
        import os
        target_path = os.path.normpath(db_path).lower() if db_path else ""
        
        from PySide6.QtWidgets import QComboBox
        for i in range(main_window.tab_widget.count()):
            tab = main_window.tab_widget.widget(i)
            # Find the connection combo in this tab
            combo = tab.findChild(QComboBox, "db_combo_box")
            if combo:
                data = combo.currentData()
                if isinstance(data, dict):
                    path = data.get('db_path')
                    if path and os.path.normpath(path).lower() == target_path:
                        pid = os.getpid() # Current app process
                        source = main_window.tab_widget.tabText(i)
                        
                        is_running = False
                        if hasattr(main_window, 'worksheet_manager'):
                            if tab in main_window.worksheet_manager.running_queries:
                                is_running = True
                                
                        state = "Active" if is_running else "Idle"
                        
                        # Try to get query text if available
                        last_query = ""
                        # Searching for the editor in the worksheet
                        from PySide6.QtWidgets import QPlainTextEdit
                        editor = tab.findChild(QPlainTextEdit)
                        if editor:
                            last_query = editor.toPlainText()[:200]
                        
                        # Columns: ["PID", "Source", "State", "Database", "SQL"]
                        sessions.append([
                            pid, 
                            source, 
                            state, 
                            os.path.basename(db_path), 
                            last_query
                        ])
        
        return sessions

    def _get_main_window(self):
        curr = self.parent()
        while curr:
            if curr.__class__.__name__ == "MainWindow":
                return curr
            curr = curr.parent()
        return None

    def update_dashboard_stats(self, stats, worker_conn_data=None):
        if worker_conn_data and hasattr(self, "current_conn_data"):
            if self.current_conn_data != worker_conn_data:
                return # Ignore stale stats from previous connection

        is_sqlite = False
        if hasattr(self, "current_conn_data") and self.current_conn_data:
            db_type = str(self.current_conn_data.get("db_type", "")).lower()
            is_sqlite = "sqlite" in db_type

        if stats is None:
            if is_sqlite:
                stats = {
                    "sessions_total": 1, "sessions_active": 0, "sessions_idle": 1,
                    "xact_commit": 0, "xact_rollback": 0, "app_tup_ins": 0, "app_tup_upd": 0,
                    "app_tup_del": 0, "app_tup_fet": 0, "app_tup_ret": 0, "app_exec_time": 0
                }
            else:
                return

        if is_sqlite and self.current_conn_data:
            db_path = self.current_conn_data.get("db_path")
            if db_path:
                t, a, i = self.get_local_sqlite_sessions(db_path)
                stats["sessions_total"] = t
                stats["sessions_active"] = a
                stats["sessions_idle"] = i

        try:
            now = datetime.now()
            
            # 1. Update Sessions Chart
            if hasattr(self, "sessions_chart"):
                if is_sqlite:
                    t, a, i = self.get_local_sqlite_sessions(self.current_conn_data.get("db_path"))
                    self.sessions_chart.chart_view.update_values([t, a, i])
                else:
                    ws_total, _ = self.get_local_postgres_sessions(self.current_conn_data.get("database"))
                    other_total_sql = stats.get("other_total", 0)
                    total_active_sql = stats.get("total_active", 0)
                    graph_total = ws_total + other_total_sql
                    graph_active = total_active_sql
                    graph_idle = max(0, graph_total - graph_active)
                    self.sessions_chart.chart_view.update_values([graph_total, graph_active, graph_idle])
            
            # 2. Update Other Charts
            if self.prev_stats and self.prev_time:
                dt = (now - self.prev_time).total_seconds()
                if dt > 0:
                    # TPS (Your Activity)
                    if hasattr(self, "tps_chart"):
                        app_c_diff = stats.get("app_commit", 0) - self.prev_stats.get("app_commit", 0)
                        app_r_diff = stats.get("app_rollback", 0) - self.prev_stats.get("app_rollback", 0)
                        self.tps_chart.chart_view.update_values([
                            max(0, app_c_diff + app_r_diff), 
                            max(0, app_c_diff), 
                            max(0, app_r_diff)
                        ])
                    
                    # Tuples In (Your Activity)
                    if hasattr(self, "tuples_in_chart"):
                        t_ins = stats.get("app_tup_ins", 0) - self.prev_stats.get("app_tup_ins", 0)
                        t_upd = stats.get("app_tup_upd", 0) - self.prev_stats.get("app_tup_upd", 0)
                        t_del = stats.get("app_tup_del", 0) - self.prev_stats.get("app_tup_del", 0)
                        self.tuples_in_chart.chart_view.update_values([max(0, t_ins), max(0, t_upd), max(0, t_del)])
                    
                    # Tuples Out (Your Activity)
                    if hasattr(self, "tuples_out_chart"):
                        t_fet = stats.get("app_tup_fet", 0) - self.prev_stats.get("app_tup_fet", 0)
                        t_ret = stats.get("app_tup_ret", 0) - self.prev_stats.get("app_tup_ret", 0)
                        self.tuples_out_chart.chart_view.update_values([max(0, t_fet), max(0, t_ret)])
                    
                    # Block I/O (Filtered to hide noise)
                    if hasattr(self, "block_io_chart"):
                        b_read_global = stats.get("blks_read", 0) - self.prev_stats.get("blks_read", 0)
                        b_hit_global = stats.get("blks_hit", 0) - self.prev_stats.get("blks_hit", 0)
                        
                        # Show only if we had app activity
                        app_work = (
                            (stats.get("app_commit", 0) != self.prev_stats.get("app_commit", 0)) or
                            (stats.get("app_rollback", 0) != self.prev_stats.get("app_rollback", 0)) or
                            (stats.get("app_tup_fet", 0) != self.prev_stats.get("app_tup_fet", 0)) or
                            (stats.get("app_tup_ins", 0) != self.prev_stats.get("app_tup_ins", 0))
                        )
                        
                        if app_work:
                            self.block_io_chart.chart_view.update_values([max(0, b_read_global), max(0, b_hit_global)])
                        else:
                            self.block_io_chart.chart_view.update_values([0, 0])
                    
            self.prev_stats = stats
            self.prev_time = now
        except Exception as e:
            print(f"Error updating dashboard UI: {e}")
