import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QHeaderView, QLabel, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem,
    QGraphicsTextItem, QGraphicsLineItem, QToolBar, QPushButton, QFrame,
    QProgressBar, QStyledItemDelegate, QStyle, QStyleOptionProgressBar, QApplication
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QIcon, QPainter, QPixmap

class AnalysisItemDelegate(QStyledItemDelegate):
    """Custom delegate to render timing columns with inline progress bars like pgAdmin."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.max_exclusive = 0
        self.max_inclusive = 0
    
    def paint(self, painter, option, index):
        if index.column() in (2, 3):  # Exclusive or Inclusive columns
            # Get the timing value
            value = index.data(Qt.ItemDataRole.UserRole)
            text = index.data(Qt.ItemDataRole.DisplayRole)
            
            if value is not None and value > 0:
                # Calculate percentage (0-100)
                max_val = self.max_exclusive if index.column() == 2 else self.max_inclusive
                percentage = int((value / max_val * 100)) if max_val > 0 else 0

                # Draw progress bar
                progressBarOption = QStyleOptionProgressBar()
                progressBarOption.rect = option.rect.adjusted(2, 2, -2, -2)
                progressBarOption.minimum = 0
                progressBarOption.maximum = 100
                progressBarOption.progress = percentage
                progressBarOption.text = text
                progressBarOption.textVisible = True
                progressBarOption.textAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                
                # Set color based on percentage (red gradient like pgAdmin)
                if percentage > 75:
                    progressBarOption.palette.setColor(progressBarOption.palette.ColorRole.Highlight, QColor(180, 0, 0))
                elif percentage > 50:
                    progressBarOption.palette.setColor(progressBarOption.palette.ColorRole.Highlight, QColor(200, 60, 0))
                elif percentage > 25:
                    progressBarOption.palette.setColor(progressBarOption.palette.ColorRole.Highlight, QColor(220, 100, 0))
                else:
                    progressBarOption.palette.setColor(progressBarOption.palette.ColorRole.Highlight, QColor(240, 140, 0))
                
                QApplication.style().drawControl(QStyle.ControlElement.CE_ProgressBar, progressBarOption, painter)
            else:
                super().paint(painter, option, index)
        else:
            super().paint(painter, option, index)

class ExplainVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header Info
        self.summary_label = QLabel("Run EXPLAIN on a query to see the plan here.")
        self.summary_label.setStyleSheet("padding: 5px; background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; font-weight: bold;")
        self.layout.addWidget(self.summary_label)

        # Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border-top: 1px solid #dee2e6; }")
        
        # 1. Graphical Tab
        graphics_tab = QWidget()
        graphics_layout = QVBoxLayout(graphics_tab)
        graphics_layout.setContentsMargins(0, 0, 0, 0)
        graphics_layout.setSpacing(0)
        
        # Graphical Toolbar
        self.graph_toolbar = QToolBar()
        self.graph_toolbar.setMovable(False)
        self.graph_toolbar.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6;")
        
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(24, 24)
        self.btn_zoom_in.clicked.connect(lambda: self.graph_view.scale(1.2, 1.2))
        
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedSize(24, 24)
        self.btn_zoom_out.clicked.connect(lambda: self.graph_view.scale(0.8, 0.8))
        
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(lambda: self.graph_view.reset_view())
        
        self.graph_toolbar.addWidget(self.btn_zoom_in)
        self.graph_toolbar.addWidget(self.btn_zoom_out)
        self.graph_toolbar.addWidget(self.btn_reset)
        graphics_layout.addWidget(self.graph_toolbar)
        
        # Splitter for Graph | Details
        self.graph_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.graph_view = ExplainGraphView()
        self.graph_view.nodeSelected.connect(self._show_details)
        self.graph_splitter.addWidget(self.graph_view)
        
        # Side Details Panel
        self.details_container = QFrame()
        self.details_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.details_container.setStyleSheet("background-color: white; border-left: 1px solid #dee2e6;")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)
        
        # Details Header
        details_header = QWidget()
        details_header.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; font-weight: bold;")
        header_layout = QHBoxLayout(details_header)
        header_layout.setContentsMargins(10, 5, 5, 5)
        
        self.details_title = QLabel("Node Details")
        header_layout.addWidget(self.details_title)
        
        btn_close = QPushButton("×")
        btn_close.setFlat(True)
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("font-size: 16px; font-weight: bold;")
        btn_close.clicked.connect(lambda: self.details_container.hide())
        header_layout.addWidget(btn_close)
        
        details_layout.addWidget(details_header)
        
        # Details Table
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.details_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.details_table.verticalHeader().hide()
        self.details_table.setShowGrid(False)
        self.details_table.setStyleSheet("border: none;")
        details_layout.addWidget(self.details_table)
        
        self.graph_splitter.addWidget(self.details_container)
        self.details_container.hide() # Hidden by default
        
        graphics_layout.addWidget(self.graph_splitter)
        self.tabs.addTab(graphics_tab, "Graphical")
        
        # 2. Analysis Tab
        self.analysis_tree = QTreeWidget()
        self.analysis_tree.setHeaderLabels([
            "#", "Node", "Exclusive", "Inclusive", "Rows X", "Actual", "Plan", "Loops"
        ])
        self.analysis_tree.setAlternatingRowColors(True)
        # Set custom delegate for progress bar columns
        self.analysis_delegate = AnalysisItemDelegate(self.analysis_tree)
        self.analysis_tree.setItemDelegateForColumn(2, self.analysis_delegate)  # Exclusive
        self.analysis_tree.setItemDelegateForColumn(3, self.analysis_delegate)  # Inclusive
        self.tabs.addTab(self.analysis_tree, "Analysis")
        
        # 3. Statistics Tab
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        
        stats_layout.addWidget(QLabel("<b>Statistics per Node Type</b>"))
        self.node_stats_table = QTableWidget()
        self.node_stats_table.setColumnCount(4)
        self.node_stats_table.setHorizontalHeaderLabels(["Node type", "Count", "Time spent", "% of query"])
        self.node_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        stats_layout.addWidget(self.node_stats_table)
        
        stats_layout.addWidget(QLabel("<b>Statistics per Relation</b>"))
        self.rel_stats_tree = QTreeWidget()
        self.rel_stats_tree.setHeaderLabels(["Relation name", "Scan count", "Total time", "% of query"])
        self.rel_stats_tree.setAlternatingRowColors(True)
        self.rel_stats_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        stats_layout.addWidget(self.rel_stats_tree)
        
        self.tabs.addTab(stats_widget, "Statistics")
        
        self.layout.addWidget(self.tabs)

    def load_plan(self, plan_json):
        self.graph_view.scene().clear()
        self.analysis_tree.clear()
        self.node_stats_table.setRowCount(0)
        self.rel_stats_tree.clear()
        self.details_table.setRowCount(0)
        self.details_container.hide()
        
        if not plan_json:
            self.summary_label.setText("No plan to display.")
            return

        try:
            if isinstance(plan_json, str):
                data = json.loads(plan_json)
            else:
                data = plan_json
            
            if isinstance(data, list) and len(data) > 0:
                root_plan = data[0].get('Plan')
                total_runtime = data[0].get('Execution Time') or data[0].get('Total Runtime')
                if total_runtime:
                     self.summary_label.setText(f"Total Execution Time: {total_runtime} ms")
                else:
                    self.summary_label.setText(f"Plan Cost: {root_plan.get('Total Cost', 'N/A')}")
                
                # 0. Enrich Plan Data (Calculate derived metrics)
                self._enrich_plan_data(root_plan)

                # 1. Populate Graphical
                self.graph_view.load_plan(root_plan)
                
                # 2. Populate Analysis
                self._populate_analysis(root_plan, self.analysis_tree.invisibleRootItem())
                self.analysis_tree.expandAll()
                self._apply_analysis_heatmap()
                
                # 3. Populate Statistics
                self._populate_statistics(root_plan, total_runtime)
            
        except Exception as e:
            self.summary_label.setText(f"Error parsing plan: {str(e)}")

    def _populate_analysis(self, plan_node, parent_item, row_num=1):
        node_type = plan_node.get("Node Type", "Unknown")
        relation = plan_node.get("Relation Name")
        alias = plan_node.get("Alias")
        index_name = plan_node.get("Index Name")
        
        # Build node description exactly like pgAdmin
        operation_text = f"➞ {node_type}"
        
        if index_name:
            operation_text += f" using {index_name}"
        
        if relation:
            operation_text += f" on {relation}"
            if alias and alias != relation:
                operation_text += f" as {alias}"
        
        # Add cost info in pgAdmin format: (cost=0.15...23.25...)
        startup_cost = plan_node.get("Startup Cost", 0)
        total_cost = plan_node.get("Total Cost", 0)
        plan_rows = plan_node.get("Plan Rows", 0)
        plan_width = plan_node.get("Plan Width", 0)
        operation_text += f" (cost={startup_cost:.2f}..{total_cost:.2f} rows={plan_rows} width={plan_width})"
        
        # Timing - Inclusive/Exclusive
        inclusive = plan_node.get("Actual Total Time", 0)
        children_inclusive = 0
        if "Plans" in plan_node:
            for child in plan_node["Plans"]:
                children_inclusive += child.get("Actual Total Time", 0)
        exclusive = max(0, inclusive - children_inclusive)
        
        # Rows
        actual_rows = plan_node.get("Actual Rows", 0)
        rows_x = ""
        if plan_rows > 0:
            ratio = actual_rows / plan_rows
            rows_x = f"{ratio:.2f}"
        
        loops = plan_node.get("Actual Loops", 1)

        item = QTreeWidgetItem(parent_item)
        item.setText(0, str(row_num))
        item.setText(1, operation_text)
        item.setText(2, f"{exclusive:.2f} ms")
        item.setText(3, f"{inclusive:.2f} ms")
        item.setText(4, rows_x)
        item.setText(5, str(int(actual_rows)))
        item.setText(6, str(int(plan_rows)))
        item.setText(7, str(loops))
        
        # Store raw timing values for delegate
        item.setData(2, Qt.ItemDataRole.UserRole, exclusive)
        item.setData(3, Qt.ItemDataRole.UserRole, inclusive)
        
        # Store node data
        item.setData(0, Qt.ItemDataRole.UserRole + 1, plan_node)
        
        # Color Rows X if > 1 (yellow)
        if rows_x:
            try:
                if float(rows_x) > 1.0:
                    item.setForeground(4, QBrush(QColor(180, 120, 0)))
            except: pass
        
        current_row = row_num
        if "Plans" in plan_node:
            for child_plan in plan_node["Plans"]:
                current_row = self._populate_analysis(child_plan, item, current_row + 1)
        
        return current_row

    def _apply_analysis_heatmap(self):
        # Find max inclusive and exclusive times for delegate normalization
        max_incl = 0
        max_excl = 0
        
        def find_max(item):
            nonlocal max_incl, max_excl
            try:
                excl = item.data(2, Qt.ItemDataRole.UserRole)
                incl = item.data(3, Qt.ItemDataRole.UserRole)
                if excl:
                    max_excl = max(max_excl, excl)
                if incl:
                    max_incl = max(max_incl, incl)
            except: pass
            for i in range(item.childCount()):
                find_max(item.child(i))
                
        for i in range(self.analysis_tree.topLevelItemCount()):
            find_max(self.analysis_tree.topLevelItem(i))
        
        # Store max values in delegate
        if hasattr(self, 'analysis_delegate'):
            self.analysis_delegate.max_exclusive = max_excl
            self.analysis_delegate.max_inclusive = max_incl

    def _populate_statistics(self, root_plan, total_runtime):
        node_stats = {}  # {node_type: {count, time}}
        rel_node_stats = {}  # {rel_name: {node_type: {count, time}}}
        
        def traverse(node):
            ntype = node.get("Node Type")
            rel = node.get("Relation Name")
            time = node.get("Actual Total Time", 0)
            
            # Calculate exclusive time
            children_time = 0
            if "Plans" in node:
                for c in node["Plans"]:
                    children_time += c.get("Actual Total Time", 0)
            excl_time = max(0, time - children_time)
            
            # Node Stats
            if ntype not in node_stats:
                node_stats[ntype] = {"count": 0, "time": 0}
            node_stats[ntype]["count"] += 1
            node_stats[ntype]["time"] += excl_time
            
            # Relation Stats - hierarchical
            if rel:
                if rel not in rel_node_stats:
                    rel_node_stats[rel] = {}
                if ntype not in rel_node_stats[rel]:
                    rel_node_stats[rel][ntype] = {"count": 0, "time": 0}
                rel_node_stats[rel][ntype]["count"] += 1
                rel_node_stats[rel][ntype]["time"] += excl_time
                
            if "Plans" in node:
                for c in node["Plans"]:
                    traverse(c)
                    
        traverse(root_plan)
        
        # Populate Node Stats Table
        total_time = sum(s["time"] for s in node_stats.values())
        self.node_stats_table.setRowCount(len(node_stats))
        for i, (ntype, stats) in enumerate(sorted(node_stats.items(), key=lambda x: x[1]["time"], reverse=True)):
            self.node_stats_table.setItem(i, 0, QTableWidgetItem(ntype))
            self.node_stats_table.setItem(i, 1, QTableWidgetItem(str(stats["count"])))
            self.node_stats_table.setItem(i, 2, QTableWidgetItem(f"{stats['time']:.2f} ms"))
            perc = (stats['time'] / total_time * 100) if total_time > 0 else 0
            self.node_stats_table.setItem(i, 3, QTableWidgetItem(f"{perc:.1f}%"))
            
        # Populate Relation Stats Tree (hierarchical)
        self.rel_stats_tree.clear()
        for rel_name in sorted(rel_node_stats.keys()):
            # Calculate total for this relation
            rel_total_count = sum(s["count"] for s in rel_node_stats[rel_name].values())
            rel_total_time = sum(s["time"] for s in rel_node_stats[rel_name].values())
            rel_perc = (rel_total_time / total_time * 100) if total_time > 0 else 0
            
            # Create parent item for relation
            rel_item = QTreeWidgetItem(self.rel_stats_tree)
            rel_item.setText(0, rel_name)
            rel_item.setText(1, str(rel_total_count))
            rel_item.setText(2, f"{rel_total_time:.2f} ms")
            rel_item.setText(3, f"{rel_perc:.1f}%")
            
            # Add child items for each node type
            for ntype, stats in sorted(rel_node_stats[rel_name].items(), key=lambda x: x[1]["time"], reverse=True):
                child_item = QTreeWidgetItem(rel_item)
                child_item.setText(0, ntype)  # Node type as child
                child_item.setText(1, str(stats["count"]))
                child_item.setText(2, f"{stats['time']:.2f} ms")
                perc = (stats['time'] / rel_total_time * 100) if rel_total_time > 0 else 0
                child_item.setText(3, f"{perc:.1f}%")
        
        self.rel_stats_tree.expandAll()

    def _enrich_plan_data(self, node):
        """
        Recursively calculates and adds derived metrics (inclusive, exclusive, rowsx)
        to the plan node dictionary, matching pgAdmin's display fields.
        """
        # 1. Inclusive Time (Actual Total Time)
        inclusive = node.get("Actual Total Time", 0)
        node["inclusive"] = inclusive

        # 2. Exclusive Time (Inclusive - Children Inclusive)
        children_inclusive = 0
        if "Plans" in node:
            for child in node["Plans"]:
                # Recurse first so children have their times calculated
                self._enrich_plan_data(child)
                children_inclusive += child.get("Actual Total Time", 0)
        
        exclusive = max(0, inclusive - children_inclusive)
        node["exclusive"] = exclusive

        # 3. Rows X (Actual / Plan)
        plan_rows = node.get("Plan Rows", 0)
        actual_rows = node.get("Actual Rows", 0)
        rows_x = 0
        if plan_rows > 0:
            rows_x = actual_rows / plan_rows
        
        # Determine direction
        rows_x_direction = "none"
        if rows_x > 1: rows_x_direction = "underestimation" # Plan was lower than actual
        elif rows_x < 1 and rows_x > 0: rows_x_direction = "overestimation" 
        
        node["rowsx"] = rows_x
        node["rowsx_direction"] = rows_x_direction

        # 4. Other Aliases/Format matches
        if "Actual Loops" in node:
            node["loops"] = node["Actual Loops"]
        
        # Add exact fields user requested if available or calculated
        # (Some flags/factors are pgAdmin specific internals, we can try to approximate or just leave 0/1)
        node["inclusive_factor"] = 1 # Placeholder
        node["exclusive_factor"] = 1 # Placeholder
        node["inclusive_flag"] = 4 # Placeholder (pgAdmin enum?)
        node["exclusive_flag"] = 4 # Placeholder
        node["rowsx_flag"] = 2 if rows_x > 1 else 0 # Placeholder approximation


    def _show_details(self, plan_node):
        self.details_table.setRowCount(0)
        if not plan_node:
            self.details_container.hide()
            return
            
        self.details_container.show()
        row = 0
        for key, value in plan_node.items():
            if key == "Plans": continue
            self.details_table.insertRow(row)
            self.details_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.details_table.setItem(row, 1, QTableWidgetItem(str(value)))
            row += 1
        self.details_table.resizeRowsToContents()

class PlanNodeItem(QGraphicsItem):
    """A graphical representation of a plan node."""
    # Icon atlas mapping (x, y coordinates in grid)
    ICON_MAP = {
        "Seq Scan": (0, 0),
        "Index Scan": (1, 0),
        "Index Only Scan": (1, 0),
        "Bitmap Index Scan": (1, 0),
        "Hash Join": (2, 0),
        "Hash": (2, 0),
        "Nested Loop": (0, 1),
        "Merge Join": (0, 1),
        "Aggregate": (1, 1),
        "Group": (1, 1),
        "Sort": (2, 1),
        "Limit": (2, 1)
    }
    
    _atlas = None

    def __init__(self, plan_node, parent=None):
        super().__init__(parent)
        self.plan_node = plan_node
        self.node_type = plan_node.get("Node Type", "Unknown")
        self.width = 200
        self.height = 80
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        if PlanNodeItem._atlas is None:
            atlas_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "plan_icons.png")
            if os.path.exists(atlas_path):
                PlanNodeItem._atlas = QPixmap(atlas_path)
        
        # Determine cost color
        self.total_cost = plan_node.get("Total Cost", 0)
        
        # Set Tooltip
        relation = plan_node.get("Relation Name")
        tooltip = f"<b>{self.node_type}</b><br/>"
        if relation: tooltip += f"Relation: {relation}<br/>"
        tooltip += f"Cost: {self.total_cost}<br/>"
        actual_rows = plan_node.get("Actual Rows")
        if actual_rows is not None:
            tooltip += f"Actual Rows: {actual_rows}<br/>"
        actual_time = plan_node.get("Actual Total Time")
        if actual_time is not None:
            tooltip += f"Actual Time: {actual_time} ms"
        self.setToolTip(tooltip)
        
    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)
        
    def paint(self, painter, option, widget):
        # Draw background
        color = QColor(255, 255, 255)
        if self.isSelected():
            color = QColor(230, 240, 255)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRoundedRect(0, 0, self.width, self.height, 4, 4)
        
        # Draw Icon
        if PlanNodeItem._atlas and not PlanNodeItem._atlas.isNull():
            grid_pos = self.ICON_MAP.get(self.node_type, (1, 1))
            icon_size = PlanNodeItem._atlas.width() // 3
            icon_pixmap = PlanNodeItem._atlas.copy(grid_pos[0] * icon_size, grid_pos[1] * icon_size, icon_size, icon_size)
            painter.drawPixmap(8, 8, 32, 32, icon_pixmap)
        
        # Draw text
        painter.setPen(Qt.GlobalColor.black)
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(48, 8, self.width-56, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.node_type)
        
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        relation = self.plan_node.get("Relation Name")
        if relation:
            painter.drawText(QRectF(8, 45, self.width-16, 15), Qt.AlignmentFlag.AlignLeft, f"Relation: {relation}")
            
        cost_text = f"Cost: {self.total_cost}"
        painter.drawText(QRectF(8, 62, self.width-16, 15), Qt.AlignmentFlag.AlignLeft, cost_text)

class ExplainGraphView(QGraphicsView):
    nodeSelected = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj = QGraphicsScene(self)
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor(245, 245, 245)))
        
    def reset_view(self):
        self.resetTransform()
        if self.scene_obj.items():
            self.fitInView(self.scene_obj.itemsBoundingRect().adjusted(-50, -50, 50, 50), Qt.AspectRatioMode.KeepAspectRatio)

    def load_plan(self, root_plan):
        self.scene_obj.clear()
        if not root_plan:
            return
            
        # Layout parameters
        self.node_spacing_x = 240
        self.node_spacing_y = 120
        
        self._draw_plan_recursive(root_plan, 0, 0)
        
        # Center the plan
        rect = self.scene_obj.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        self.setSceneRect(rect)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        
    def _draw_plan_recursive(self, node, x, y):
        # Create the node item
        item = PlanNodeItem(node)
        item.setPos(x - item.width/2, y)
        self.scene_obj.addItem(item)
        
        child_plans = node.get("Plans", [])
        if not child_plans:
            return item
            
        # Draw children below
        num_children = len(child_plans)
        total_width = (num_children - 1) * self.node_spacing_x
        start_x = x - total_width / 2
        
        for i, child in enumerate(child_plans):
            child_x = start_x + i * self.node_spacing_x
            child_y = y + self.node_spacing_y
            child_item = self._draw_plan_recursive(child, child_x, child_y)
            
            # Draw line/arrow from parent to child (bottom of parent to top of child)
            line = QGraphicsLineItem(x, y + 80, child_x, child_y)
            line.setZValue(-1)
            pen = QPen(QColor(150, 150, 150), 2)
            line.setPen(pen)
            self.scene_obj.addItem(line)
            
        return item

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, PlanNodeItem):
            self.nodeSelected.emit(item.plan_node)
        else:
            # Deselect current if clicking background
            for i in self.scene_obj.selectedItems():
                i.setSelected(False)
            self.nodeSelected.emit(None)
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        self.scale(zoom_factor, zoom_factor)
