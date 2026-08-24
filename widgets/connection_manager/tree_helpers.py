import os
import sys
from PySide6.QtCore import Qt, QEvent, QModelIndex, QItemSelectionModel
from PySide6.QtGui import QIcon
import qtawesome as qta


class TreeHelpers:
    # Class-level icon cache — shared across all instances so qta.icon() is
    # called once per unique key for the lifetime of the process.
    _icon_cache: dict = {}

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
        cache_key = (level, code)
        cached = TreeHelpers._icon_cache.get(cache_key)
        if cached is not None:
            item.setIcon(cached)
            return

        icon = self._build_icon(level, code)
        TreeHelpers._icon_cache[cache_key] = icon
        item.setIcon(icon)

    def _build_icon(self, level, code=""):
        """Create the QIcon for the given level/code. Called once per unique key."""
        if level == "DATA_SOURCE":
            return qta.icon("mdi.server-network", color="#0078D4")
        if level == "GROUP":
            return qta.icon("fa6s.folder", color="#C49102")
        if level == "GROUP_SCHEMAS":
            return qta.icon("fa6s.layer-group", color="#C49102")
        if level == "GROUP_TABLES":
            return qta.icon("mdi.table-multiple", color="#C49102")
        if level == "GROUP_VIEWS":
            return qta.icon("mdi6.folder-eye", color="#C49102")
        if level == "GROUP_FOREIGN_TABLES":
            return qta.icon("mdi.folder-network", color="#C49102")
        if level == "GROUP_MATERIALIZED_VIEWS":
            return qta.icon("mdi.folder-table", color="#C49102")
        if level == "GROUP_FUNCTIONS":
            return qta.icon("mdi.code-braces", color="#E91E63")
        if level == "GROUP_TRIGGER_FUNCTIONS":
            return qta.icon('mdi.code-braces', 'mdi.flash', options=[{'color': '#C49102'}, {'color': '#C49102', 'scale_factor': 0.5}])
        if level == "GROUP_SEQUENCES":
            return qta.icon("mdi.numeric", color="#BF7200")
        if level == "POLICIES_GROUP":
            return qta.icon("mdi.folder-lock-outline", color="#9E9E9E")
        if level == "SCHEMA":
            return qta.icon("mdi.cube-outline", color="#C49102")
        if level == "TABLE":
            return qta.icon("mdi.table", color="#4CAF50")
        if level == "VIEW":
            return qta.icon("mdi.table-eye", color="#2196F3")
        if level == "MATERIALIZED_VIEW":
            return qta.icon("mdi.table-eye", color="#00BCD4")
        if level == "COLUMN":
            return qta.icon("mdi.table-column", color="#607D8B")
        if level == "TRIGGER":
            if code == "D":
                return qta.icon("mdi.lightning-bolt-outline", color="#9E9E9E")
            return qta.icon("mdi.lightning-bolt", color="#FF9800")
        if level == "POLICY":
            return qta.icon("mdi.shield-lock-outline", color="#FF5722")
        if level == "FDW_ROOT":
            return qta.icon("mdi.server-network", color="#9E9E9E")
        if level == "FDW":
            return qta.icon("mdi.server-network", color="#9E9E9E")
        if level == "SERVER":
            return qta.icon("fa5s.database", color="#9E9E9E")
        if level == "FOREIGN_TABLE":
            return qta.icon("mdi.table-network", color="#4CAF50")
        if level == "EXTENSION_ROOT":
            return qta.icon("mdi.puzzle", color="#8340A1")
        if level == "EXTENSION":
            return qta.icon("mdi.puzzle", color="#8340A1")
        if level == "LANGUAGE_ROOT":
            return qta.icon("fa5s.code", color="#795548")
        if level == "LANGUAGE":
            return qta.icon("fa5s.code", color="#795548")
        if level == "SEQUENCE":
            return qta.icon("mdi.numeric", color="#BF7200")
        if level == "FUNCTION":
            return qta.icon("mdi.code-braces", color="#E91E63")
        if level == "TRIGGER_FUNCTION":
            return qta.icon('mdi.code-braces', 'mdi.flash', options=[{'color': '#C49102'}, {'color': '#C49102', 'scale_factor': 0.5}])
        if level == "USER":
            return qta.icon("fa5s.user", color="#607D8B")

        # TYPE-level — SVG file icon
        icon_map = {
            "POSTGRES":    "assets/postgresql.svg",
            "SQLITE":      "assets/sqlite.svg",
            "ORACLE":      "assets/oracle.svg",
            "ORACLE_DB":   "assets/oracle.svg",
            "ORACLE_FA":   "assets/oracle_fusion.svg",
            "SERVICENOW":  "assets/servicenow.svg",
            "UDS":         "assets/unified_data_source.svg",
            "CSV":         "assets/csv.svg",
        }
        icon_path = icon_map.get(code, "assets/database.svg")
        if hasattr(sys, '_MEIPASS'):
            abs_icon_path = os.path.join(sys._MEIPASS, icon_path)
        else:
            abs_icon_path = os.path.join(os.path.abspath("."), icon_path)
        return QIcon(abs_icon_path)



    def save_tree_expansion_state(self):
        saved_paths = set()          # set → O(1) membership checks in restore
        proxy = self.manager.proxy_model
        tree = self.manager.tree

        for row in range(proxy.rowCount()):
            proxy_index = proxy.index(row, 0)
            if tree.isExpanded(proxy_index):
                type_name = proxy_index.data(Qt.ItemDataRole.DisplayRole)
                saved_paths.add((type_name, None, None))

                for group_row in range(proxy.rowCount(proxy_index)):
                    group_index = proxy.index(group_row, 0, proxy_index)
                    if tree.isExpanded(group_index):
                        group_name = group_index.data(Qt.ItemDataRole.DisplayRole)
                        saved_paths.add((type_name, group_name, None))

                        for conn_row in range(proxy.rowCount(group_index)):
                            conn_index = proxy.index(conn_row, 0, group_index)
                            if tree.isExpanded(conn_index):
                                conn_name = conn_index.data(Qt.ItemDataRole.DisplayRole)
                                saved_paths.add((type_name, group_name, conn_name))

        self.manager._saved_tree_paths = saved_paths

        # Save selected connection or data source
        selection = tree.selectionModel().selectedIndexes()
        if selection:
            source_index = proxy.mapToSource(selection[0])
            item = self.manager.model.itemFromIndex(source_index)
            if item:
                depth = self.get_item_depth(item)
                if depth == 3:
                    self.manager._saved_selection_info = ("CONNECTION", item.text())
                elif depth == 4:
                    parent_text = item.parent().text() if item.parent() else ""
                    self.manager._saved_selection_info = ("DATA_SOURCE", parent_text, item.text())
                else:
                    self.manager._saved_selection_info = None
            else:
                self.manager._saved_selection_info = None
        else:
            self.manager._saved_selection_info = None

    def restore_tree_expansion_state(self):
        saved = getattr(self.manager, '_saved_tree_paths', None)
        if not saved:
            return

        proxy = self.manager.proxy_model
        tree = self.manager.tree
        sel_info = getattr(self.manager, '_saved_selection_info', None)

        # Keep updates disabled for the entire operation — expansion + selection
        # — so Qt only repaints once at the very end.
        tree.setUpdatesEnabled(False)
        try:
            for row in range(proxy.rowCount()):
                proxy_index = proxy.index(row, 0)
                type_name = proxy_index.data(Qt.ItemDataRole.DisplayRole)

                # O(1) set lookup instead of O(n) list scan
                if (type_name, None, None) not in saved:
                    continue
                tree.expand(proxy_index)

                for group_row in range(proxy.rowCount(proxy_index)):
                    group_index = proxy.index(group_row, 0, proxy_index)
                    group_name = group_index.data(Qt.ItemDataRole.DisplayRole)

                    if (type_name, group_name, None) not in saved:
                        continue
                    tree.expand(group_index)

                    for conn_row in range(proxy.rowCount(group_index)):
                        conn_index = proxy.index(conn_row, 0, group_index)
                        conn_name = conn_index.data(Qt.ItemDataRole.DisplayRole)

                        if (type_name, group_name, conn_name) in saved:
                            tree.expand(conn_index)

            # Restore selection — still inside setUpdatesEnabled(False)
            if sel_info:
                sm = tree.selectionModel()
                select_flag = sm.SelectionFlag.ClearAndSelect
                if sel_info[0] == "CONNECTION":
                    target_name = sel_info[1]
                    for r in range(proxy.rowCount()):
                        p_idx = proxy.index(r, 0)
                        for gr in range(proxy.rowCount(p_idx)):
                            g_idx = proxy.index(gr, 0, p_idx)
                            for cr in range(proxy.rowCount(g_idx)):
                                c_idx = proxy.index(cr, 0, g_idx)
                                if c_idx.data(Qt.ItemDataRole.DisplayRole) == target_name:
                                    sm.select(c_idx, select_flag)
                                    tree.setCurrentIndex(c_idx)
                                    break
                elif sel_info[0] == "DATA_SOURCE":
                    parent_target, ds_target = sel_info[1], sel_info[2]
                    for r in range(proxy.rowCount()):
                        p_idx = proxy.index(r, 0)
                        for gr in range(proxy.rowCount(p_idx)):
                            g_idx = proxy.index(gr, 0, p_idx)
                            for cr in range(proxy.rowCount(g_idx)):
                                c_idx = proxy.index(cr, 0, g_idx)
                                if c_idx.data(Qt.ItemDataRole.DisplayRole) == parent_target:
                                    for dr in range(proxy.rowCount(c_idx)):
                                        d_idx = proxy.index(dr, 0, c_idx)
                                        if d_idx.data(Qt.ItemDataRole.DisplayRole) == ds_target:
                                            sm.select(d_idx, select_flag)
                                            tree.setCurrentIndex(d_idx)
                                            break
        finally:
            tree.setUpdatesEnabled(True)
            self.manager._saved_tree_paths = set()   # clear to empty set
            self.manager._saved_selection_info = None
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
