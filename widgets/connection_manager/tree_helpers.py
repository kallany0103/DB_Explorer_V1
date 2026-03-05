from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QIcon


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
            item.setIcon(QIcon("assets/folder-open.svg"))
            return

        if level == "SCHEMA":
            item.setIcon(QIcon("assets/schema.svg"))
            return

        if level == "TABLE":
            item.setIcon(QIcon("assets/table.svg"))
            return
        if level == "VIEW":
            item.setIcon(QIcon("assets/view_icon.png"))
            return

        if level == "COLUMN":
            item.setIcon(QIcon("assets/column_icon.png"))
            return

        if level in ["FDW_ROOT", "FDW", "SERVER", "FOREIGN_TABLE", "EXTENSION_ROOT", "EXTENSION", "LANGUAGE_ROOT", "LANGUAGE", "SEQUENCE", "FUNCTION", "TRIGGER_FUNCTION"]:
            if level == "FDW_ROOT":
                item.setIcon(QIcon("assets/server.svg"))
            elif level == "FDW":
                item.setIcon(QIcon("assets/plug.svg"))
            elif level == "SERVER":
                item.setIcon(QIcon("assets/database.svg"))
            elif level == "FOREIGN_TABLE":
                item.setIcon(QIcon("assets/table.svg"))
            elif level == "EXTENSION_ROOT":
                item.setIcon(QIcon("assets/plug.svg"))
            elif level == "EXTENSION":
                item.setIcon(QIcon("assets/plug.svg"))
            elif level == "LANGUAGE_ROOT":
                item.setIcon(QIcon("assets/code.svg"))
            elif level == "LANGUAGE":
                item.setIcon(QIcon("assets/code.svg"))
            elif level == "SEQUENCE":
                item.setIcon(QIcon("assets/list.svg"))
            elif level == "FUNCTION":
                item.setIcon(QIcon("assets/function.svg"))
            elif level == "TRIGGER_FUNCTION":
                item.setIcon(QIcon("assets/function.svg"))
            elif level == "USER":
                item.setIcon(QIcon("assets/plus.svg"))
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
        model = self.manager.model
        tree = self.manager.tree

        for row in range(model.rowCount()):
            type_index = model.index(row, 0)
            if tree.isExpanded(type_index):
                type_name = type_index.data(Qt.ItemDataRole.DisplayRole)
                saved_paths.append((type_name, None))

                for group_row in range(model.rowCount(type_index)):
                    group_index = model.index(group_row, 0, type_index)
                    if tree.isExpanded(group_index):
                        group_name = group_index.data(Qt.ItemDataRole.DisplayRole)
                        saved_paths.append((type_name, group_name))

        self.manager._saved_tree_paths = saved_paths

    def restore_tree_expansion_state(self):
        if not hasattr(self.manager, '_saved_tree_paths') or not self.manager._saved_tree_paths:
            return

        model = self.manager.model
        tree = self.manager.tree

        for row in range(model.rowCount()):
            type_index = model.index(row, 0)
            type_name = type_index.data(Qt.ItemDataRole.DisplayRole)

            if (type_name, None) in self.manager._saved_tree_paths:
                tree.expand(type_index)

            for group_row in range(model.rowCount(type_index)):
                group_index = model.index(group_row, 0, type_index)
                group_name = group_index.data(Qt.ItemDataRole.DisplayRole)

                if (type_name, group_name) in self.manager._saved_tree_paths:
                    tree.expand(group_index)

        self.manager._saved_tree_paths = []

    def get_item_depth(self, item):
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        return depth + 1
