# from PyQt6.QtCore import Qt, QEvent
# from PyQt6.QtGui import QIcon

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QIcon
import qtawesome as qta


class TreeHelpers:
    def __init__(self, manager):
        self.manager = manager

    def handle_event_filter(self, obj, event):
        if obj == self.manager.explorer_search_box and event.type() == QEvent.Type.FocusOut:
            if not self.manager.explorer_search_box.text().strip():
                self.manager.explorer_search_box.hide()
                self.manager.explorer_search_btn.show()
                return True
        return False

    def toggle_explorer_search(self):
        self.manager.explorer_search_btn.hide()
        self.manager.explorer_search_box.show()
        self.manager.explorer_search_box.setFocus()

    def filter_object_explorer(self, text):
        self.manager.proxy_model.setFilterFixedString(text)
        if text:
            self.manager.tree.expandAll()
        else:
            self.manager.tree.collapseAll()

    def set_tree_item_icon(self, item, level, code=""):
        if level == "GROUP":
            item.setIcon(qta.icon("fa6s.folder", color="#C49102"))
            return
        if level == "GROUP_SCHEMAS":
            item.setIcon(qta.icon("fa6s.layer-group", color="#C49102"))
            return
        if level == "GROUP_TABLES":
            item.setIcon(qta.icon("mdi.table-multiple", color="#C49102"))
            return
        if level == "GROUP_VIEWS":
            item.setIcon(qta.icon("mdi6.folder-eye", color="#C49102"))
            return
        if level == "GROUP_FOREIGN_TABLES":
            item.setIcon(qta.icon("mdi.folder-network", color="#C49102"))
            return
        if level == "GROUP_MATERIALIZED_VIEWS":
            item.setIcon(qta.icon("mdi.folder-table", color="#C49102"))
            return
        if level == "GROUP_FUNCTIONS":
            item.setIcon(qta.icon("mdi.code-braces", color="#E91E63"))
            return
        if level == "GROUP_TRIGGER_FUNCTIONS":
            item.setIcon(qta.icon('mdi.code-braces', 'mdi.flash', options=[{'color': '#C49102'}, {'color': '#C49102', 'scale_factor': 0.5}]))
            return
        if level == "GROUP_SEQUENCES":
            item.setIcon(qta.icon("mdi.numeric", color="#BF7200"))
            return

        if level == "SCHEMA":
            item.setIcon(qta.icon("mdi.cube-outline", color="#C49102"))
            return

        if level == "TABLE":
            item.setIcon(qta.icon("mdi.table", color="#4CAF50"))
            return
        if level == "VIEW":
            item.setIcon(qta.icon("mdi.table-eye", color="#2196F3"))
            return
        if level == "MATERIALIZED_VIEW":
            item.setIcon(qta.icon("mdi.table-eye", color="#00BCD4"))
            return

        if level == "COLUMN":
            item.setIcon(QIcon("assets/column_icon.png"))
            return

        if level in ["FDW_ROOT", "FDW", "SERVER", "FOREIGN_TABLE", "EXTENSION_ROOT", "EXTENSION", "LANGUAGE_ROOT", "LANGUAGE", "SEQUENCE", "FUNCTION", "TRIGGER_FUNCTION"]:
            if level == "FDW_ROOT":
                item.setIcon(qta.icon("mdi.server-network", color="#9E9E9E"))
            elif level == "FDW":
                item.setIcon(qta.icon("mdi.server-network", color="#9E9E9E"))
            elif level == "SERVER":
                item.setIcon(qta.icon("fa5s.database", color="#9E9E9E"))
            elif level == "FOREIGN_TABLE":
                item.setIcon(qta.icon("mdi.table-network", color="#4CAF50"))
            elif level == "EXTENSION_ROOT":
                item.setIcon(qta.icon("mdi.puzzle", color="#8340A1"))
            elif level == "EXTENSION":
                item.setIcon(qta.icon("mdi.puzzle", color="#8340A1"))
            elif level == "LANGUAGE_ROOT":
                item.setIcon(qta.icon("fa5s.code", color="#795548"))
            elif level == "LANGUAGE":
                item.setIcon(qta.icon("fa5s.code", color="#795548"))
            elif level == "SEQUENCE":
                item.setIcon(qta.icon("mdi.numeric", color="#BF7200"))
            elif level == "FUNCTION":
                item.setIcon(qta.icon("mdi.code-braces", color="#E91E63"))
            elif level == "TRIGGER_FUNCTION":
                item.setIcon(qta.icon('mdi.code-braces', 'mdi.flash', options=[{'color': '#C49102'}, {'color': '#C49102', 'scale_factor': 0.5}]))
            elif level == "USER":
                item.setIcon(qta.icon("fa5s.user", color="#607D8B"))
            return

        icon_map = {
            "POSTGRES": "assets/postgresql.svg",
            "SQLITE": "assets/sqlite.svg",
            "ORACLE_DB": "assets/oracle.svg",
            "ORACLE_FA": "assets/oracle_fusion.svg",
            "SERVICENOW": "assets/servicenow.svg",
            "CSV": "assets/csv.svg"
        }

        icon_path = icon_map.get(code, "assets/database.svg")
        item.setIcon(QIcon(icon_path))


    def save_tree_expansion_state(self):
        saved_paths = []
        proxy = self.manager.proxy_model
        tree = self.manager.tree

        for row in range(proxy.rowCount()):
            proxy_index = proxy.index(row, 0)
            if tree.isExpanded(proxy_index):
                type_name = proxy_index.data(Qt.ItemDataRole.DisplayRole)
                saved_paths.append((type_name, None))

                for group_row in range(proxy.rowCount(proxy_index)):
                    group_index = proxy.index(group_row, 0, proxy_index)
                    if tree.isExpanded(group_index):
                        group_name = group_index.data(Qt.ItemDataRole.DisplayRole)
                        saved_paths.append((type_name, group_name))

        self.manager._saved_tree_paths = saved_paths

        # Save selected connection short_name
        selection = tree.selectionModel().selectedIndexes()
        if selection:
            source_index = proxy.mapToSource(selection[0])
            item = self.manager.model.itemFromIndex(source_index)
            if item and self.get_item_depth(item) == 3:
                self.manager._saved_selection_name = item.text()
            else:
                self.manager._saved_selection_name = None
        else:
            self.manager._saved_selection_name = None

    def restore_tree_expansion_state(self):
        if not hasattr(self.manager, '_saved_tree_paths') or not self.manager._saved_tree_paths:
            return

        proxy = self.manager.proxy_model
        tree = self.manager.tree

        tree.setUpdatesEnabled(False)
        try:
            for row in range(proxy.rowCount()):
                proxy_index = proxy.index(row, 0)
                type_name = proxy_index.data(Qt.ItemDataRole.DisplayRole)

                if (type_name, None) in self.manager._saved_tree_paths:
                    tree.expand(proxy_index)

                    for group_row in range(proxy.rowCount(proxy_index)):
                        group_index = proxy.index(group_row, 0, proxy_index)
                        group_name = group_index.data(Qt.ItemDataRole.DisplayRole)

                        if (type_name, group_name) in self.manager._saved_tree_paths:
                            tree.expand(group_index)
                            
                            if hasattr(self.manager, '_saved_selection_name') and self.manager._saved_selection_name:
                                for conn_row in range(proxy.rowCount(group_index)):
                                    conn_index = proxy.index(conn_row, 0, group_index)
                                    if conn_index.data(Qt.ItemDataRole.DisplayRole) == self.manager._saved_selection_name:
                                        tree.selectionModel().select(conn_index, tree.selectionModel().SelectionFlag.ClearAndSelect)
                                        tree.setCurrentIndex(conn_index)
                                        break
        finally:
            tree.setUpdatesEnabled(True)
            self.manager._saved_tree_paths = []
            self.manager._saved_selection_name = None

    def get_item_depth(self, item):
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        return depth + 1
