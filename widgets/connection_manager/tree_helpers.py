# from PyQt6.QtCore import Qt, QEvent
# from PyQt6.QtGui import QIcon

from PySide6.QtCore import Qt, QEvent, QModelIndex
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

    def save_schema_tree_expansion_state(self, conn_id):
        saved_paths = []
        if not hasattr(self.manager, 'schema_tree') or not hasattr(self.manager, 'schema_model'):
            return
            
        tree = self.manager.schema_tree
        model = self.manager.schema_model

        def traverse(parent_index, current_path):
            for row in range(model.rowCount(parent_index)):
                index = model.index(row, 0, parent_index)
                if tree.isExpanded(index):
                    item_text = index.data(Qt.ItemDataRole.DisplayRole)
                    new_path = current_path + [item_text]
                    saved_paths.append(tuple(new_path))
                    traverse(index, new_path)

        traverse(QModelIndex(), [])
        
        if not hasattr(self.manager, '_schema_states'):
            self.manager._schema_states = {}
            
        # Save both paths and selection
        state = {
            'paths': saved_paths,
            'selection': None
        }
        
        # Save selected schema item path if any
        selection = tree.selectionModel().selectedIndexes()
        if selection:
            sel_index = selection[0]
            if sel_index.column() != 0:
                sel_index = sel_index.siblingAtColumn(0)
            
            sel_path = []
            curr = sel_index
            while curr.isValid():
                sel_path.insert(0, curr.data(Qt.ItemDataRole.DisplayRole))
                curr = curr.parent()
            state['selection'] = tuple(sel_path)
            
        if conn_id:
            self.manager._schema_states[conn_id] = state

    def restore_schema_tree_expansion_state(self, conn_id):
        if not conn_id or not hasattr(self.manager, '_schema_states'):
            return
            
        state = self.manager._schema_states.get(conn_id)
        if not state:
            return

        tree = self.manager.schema_tree
        model = self.manager.schema_model

        tree.setUpdatesEnabled(False)
        try:
            def expand_path(path_tuple):
                parent_index = QModelIndex()
                for part in path_tuple:
                    found = False
                    for row in range(model.rowCount(parent_index)):
                        index = model.index(row, 0, parent_index)
                        if index.data(Qt.ItemDataRole.DisplayRole) == part:
                            tree.expand(index)
                            parent_index = index
                            found = True
                            break
                    if not found:
                        break

            # Sort paths by length so we expand parents before children
            paths = sorted(state.get('paths', []), key=len)
            for path in paths:
                expand_path(path)
                
            # Restore selection
            sel_path = state.get('selection')
            if sel_path:
                parent_index = QModelIndex()
                final_index = None
                for part in sel_path:
                    found = False
                    for row in range(model.rowCount(parent_index)):
                        index = model.index(row, 0, parent_index)
                        if index.data(Qt.ItemDataRole.DisplayRole) == part:
                            parent_index = index
                            final_index = index
                            found = True
                            break
                    if not found:
                        final_index = None
                        break
                        
                if final_index and final_index.isValid():
                    from PySide6.QtCore import QItemSelectionModel
                    tree.selectionModel().select(final_index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
                    tree.setCurrentIndex(final_index)
                    
        finally:
            tree.setUpdatesEnabled(True)

    def get_item_depth(self, item):
        depth = 0
        parent = item.parent()
        while parent is not None:
            depth += 1
            parent = parent.parent()
        return depth + 1
