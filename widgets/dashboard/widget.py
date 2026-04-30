from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QFrame, QGridLayout, QGraphicsLineItem, QGraphicsEllipseItem,
                               QTabWidget)
from PySide6.QtCore import Qt, QTimer, QRunnable, QObject, Signal, Slot, QPointF
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from widgets.dashboard.state_widget import StateWidget, StateWorker
import qtawesome as qta
import db
from datetime import datetime

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
    finished = Signal(dict)
    error = Signal(str)

class DashboardWorker(QRunnable):
    def __init__(self, conn_data, current_db_only=False):
        super().__init__()
        self.conn_data = conn_data
        self.current_db_only = current_db_only
        self.signals = DashboardWorkerSignals()

    @Slot()
    def run(self):
        try:
            stats = db.get_postgres_session_stats(self.conn_data, self.current_db_only)
            try:
                self.signals.finished.emit(stats)
            except RuntimeError:
                pass # Receiver already deleted
        except Exception as e:
            try:
                self.signals.error.emit(str(e))
            except RuntimeError:
                pass

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
            series = QLineSeries()
            series.setName(name)
            pen = QPen(QColor(color))
            pen.setWidth(2)
            series.setPen(pen)
            self.series_list.append(series)
            self.chart_obj.addSeries(series)
            
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
        self.axis_y.setLabelFormat("%.1f" if "sec" in series_names[0] else "%d")
        
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
        
        self.marker_items = [] # Circles on series
        self.floating_tooltip = ChartTooltip(self)

    def update_values(self, values):
        self.x_counter += 1
        for series, val in zip(self.series_list, values):
            series.append(self.x_counter, val)
            if series.count() > self.max_points + 20: 
                series.remove(0)
        
        self.axis_x.setRange(self.x_counter - self.max_points + 1, self.x_counter)
        
        max_val = max(max(values) if values else 0, 5)
        current_max_y = self.axis_y.max()
        
        # Grow axis if data exceeds 90% of current range
        if max_val > current_max_y * 0.9:
            self.axis_y.setRange(0, max_val * 1.2)
        # Snap axis down if data is significantly lower than current range
        elif max_val < current_max_y * 0.2 and current_max_y > 10:
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
    def __init__(self, title, series_names, colors, parent=None):
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
            h_layout.addWidget(item)
            
        self.chart_view = LiveChartView(series_names, colors)
        self.chart_view.setStyleSheet("border: none; border-radius: 0px;")
        
        layout.addWidget(header)
        layout.addWidget(self.chart_view)

class DashboardWidget(QWidget):
    def closeEvent(self, event):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().closeEvent(event)

    def hideEvent(self, event):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.start(1000)
        super().showEvent(event)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #ffffff;")
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.request_stats_update)
        
        self.prev_stats = None
        self.prev_time = None
        
        self.setup_ui()
        self.refresh_timer.start(1000) # 1 second refresh for "live" feel

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
        self.tabs.addTab(self.state_widget, qta.icon('mdi.database-search', color="#121213"), "State")

        layout.addWidget(self.tabs)

    def setup_activity_ui(self):
        main_layout = QVBoxLayout(self.activity_tab)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # Grid for charts - 6 column grid to allow 2-chart and 3-chart rows
        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        
        self.sessions_chart = LiveChartWidget("Database sessions", ["Total", "Active", "Idle"], ["#1f77b4", "#f59e0b", "#10b981"])
        self.tps_chart = LiveChartWidget("Transactions per second", ["Transactions", "Commits", "Rollbacks"], ["#1f77b4", "#f59e0b", "#ef4444"])
        
        # Delta counts instead of rates for better row-level visibility
        self.tuples_in_chart = LiveChartWidget("Tuples In (Count)", ["Inserts", "Updates", "Deletes"], ["#1f77b4", "#f59e0b", "#10b981"])
        self.tuples_out_chart = LiveChartWidget("Tuples Out (Count)", ["Fetched", "Returned"], ["#1f77b4", "#f59e0b"])
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
        
        self.status_label = QLabel("Monitoring: None")
        self.status_label.setStyleSheet("color: #2563eb; font-weight: bold; font-size: 13px; margin-bottom: 4px;")
        main_layout.addWidget(self.status_label)
        
        main_layout.addWidget(self.no_connection_lbl)
        main_layout.addLayout(grid_layout)
        main_layout.addStretch()

    def request_stats_update(self):
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
            current_db_only = True
        elif depth == 2:
            # Group level -> Show server-wide for the first connection in group
            if item.hasChildren():
                child = item.child(0)
                conn_data = child.data(Qt.ItemDataRole.UserRole)
            current_db_only = False
        else:
            # Fallback to active postgres conn if any
            if hasattr(cm, 'active_postgres_conn'):
                conn_data = cm.active_postgres_conn
                current_db_only = True # Usually we click connections to make them active

        if not conn_data:
            return

        # 2. Activity Stats Update
        activity_worker = DashboardWorker(conn_data, current_db_only)
        activity_worker.signals.finished.connect(self.update_dashboard_stats)
        activity_worker.signals.error.connect(lambda err: print(f"Dashboard activity worker error: {err}"))
        main_window.thread_pool.start(activity_worker)

        # 3. State Details Update (if State tab is active or just refresh it anyway)
        if self.tabs.currentWidget() == self.state_widget:
            state_worker = StateWorker(conn_data)
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
        self.status_label.setText(f"Monitoring: {conn_data.get('name', 'N/A')} ({conn_data.get('database', 'N/A')})")
        

    def _find_conn_data(self, cm, index):
        if not index.isValid():
            return None
        curr_index = index
        while curr_index.isValid():
            source_idx = cm.proxy_model.mapToSource(curr_index)
            item = cm.model.itemFromIndex(source_idx)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, dict) and ("host" in data or "dsn" in data) and "postgres" in str(data.get("db_type", "")).lower():
                    return data
            curr_index = curr_index.parent()
        return None

    def update_dashboard_stats(self, stats):
        try:
            now = datetime.now()
            
            # 1. Update Sessions Chart (Always exists)
            if hasattr(self, 'sessions_chart'):
                self.sessions_chart.chart_view.update_values([
                    stats.get("sessions_total", 0),
                    stats.get("sessions_active", 0),
                    stats.get("sessions_idle", 0)
                ])
            
            # 2. Update Other Charts only if they exist
            if self.prev_stats and self.prev_time:
                dt = (now - self.prev_time).total_seconds()
                if dt > 0:
                    # TPS
                    if hasattr(self, 'tps_chart'):
                        c_diff = stats.get("xact_commit", 0) - self.prev_stats.get("xact_commit", 0)
                        r_diff = stats.get("xact_rollback", 0) - self.prev_stats.get("xact_rollback", 0)
                        self.tps_chart.chart_view.update_values([
                            int(round(max(0, (c_diff + r_diff) / dt))),
                            int(round(max(0, c_diff / dt))),
                            int(round(max(0, r_diff / dt)))
                        ])
                    
                    # Tuples In (Using absolute delta count for responsiveness)
                    if hasattr(self, 'tuples_in_chart'):
                        t_ins = stats.get("tup_ins", 0) - self.prev_stats.get("tup_ins", 0)
                        t_upd = stats.get("tup_upd", 0) - self.prev_stats.get("tup_upd", 0)
                        t_del = stats.get("tup_del", 0) - self.prev_stats.get("tup_del", 0)
                        self.tuples_in_chart.chart_view.update_values([
                            max(0, t_ins),
                            max(0, t_upd),
                            max(0, t_del)
                        ])
                    
                    # Tuples Out (Using absolute delta count)
                    if hasattr(self, 'tuples_out_chart'):
                        t_fet = stats.get("tup_fet", 0) - self.prev_stats.get("tup_fet", 0)
                        t_ret = stats.get("tup_ret", 0) - self.prev_stats.get("tup_ret", 0)
                        self.tuples_out_chart.chart_view.update_values([
                            max(0, t_fet),
                            max(0, t_ret)
                        ])
                    
                    # Block I/O
                    if hasattr(self, 'block_io_chart'):
                        b_read = stats.get("blks_read", 0) - self.prev_stats.get("blks_read", 0)
                        b_hit = stats.get("blks_hit", 0) - self.prev_stats.get("blks_hit", 0)
                        self.block_io_chart.chart_view.update_values([
                            max(0, b_read),
                            max(0, b_hit)
                        ])
                    
            self.prev_stats = stats
            self.prev_time = now
        except Exception as e:
            print(f"Error updating dashboard UI: {e}")
