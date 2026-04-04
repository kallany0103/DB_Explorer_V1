import re
from functools import partial

import sqlparse
from PySide6.QtCore import Qt, QSortFilterProxyModel, QTimer
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QLabel, QLineEdit, QStackedWidget, QTextEdit, QToolButton, QWidget, QTabWidget, QTableView

from widgets.results_view.explain import ExplainVisualizer
from widgets.results_view.perf_metrics import perf_elapsed_ms, perf_record, perf_take, perf_now
from workers import FetchMetadataWorker, MetadataSignals


DEFAULT_CHUNK_PROFILES = [
    {
        "max_rows": 2000,
        "initial_rows": 2000,
        "batch_rows": 2000,
    },
    {
        "max_rows": 20000,
        "initial_rows": 500,
        "batch_rows": 500,
    },
    {
        "max_rows": 100000,
        "initial_rows": 400,
        "batch_rows": 900,
    },
    {
        "max_rows": None,
        "initial_rows": 300,
        "batch_rows": 1200,
    },
]


def _resolve_chunk_profile(total_rows, manager):
    override = getattr(manager, "result_chunk_profiles", None)
    profiles = override if isinstance(override, list) and override else DEFAULT_CHUNK_PROFILES

    for profile in profiles:
        max_rows = profile.get("max_rows")
        if max_rows is None or total_rows <= int(max_rows):
            initial_rows = int(profile.get("initial_rows", 500))
            batch_rows = int(profile.get("batch_rows", 500))
            if initial_rows <= 0:
                initial_rows = 1
            if batch_rows <= 0:
                batch_rows = 1
            return initial_rows, batch_rows

    return 500, 500


def _stop_chunk_loader(output_state):
    timer = output_state.get("chunk_loader")
    if timer:
        try:
            timer.stop()
            timer.deleteLater()
        except Exception:
            pass
    output_state["chunk_loader"] = None


def _make_row_items(row, columns, pk_indices):
    pk_val = None
    pk_col_name = None
    if pk_indices:
        pk_idx = pk_indices[0]
        pk_val = row[pk_idx]
        pk_col_name = columns[pk_idx]

    items = []
    for col_idx, cell in enumerate(row):
        item = QStandardItem(str(cell))
        edit_data = {
            "pk_col": pk_col_name,
            "pk_val": pk_val,
            "orig_val": cell,
            "col_name": columns[col_idx],
        }
        item.setData(edit_data, Qt.ItemDataRole.UserRole)
        items.append(item)
    return items


def _append_rows_batch(model, results, columns, pk_indices, start_index, end_index):
    for row_index in range(start_index, end_index):
        model.appendRow(_make_row_items(results[row_index], columns, pk_indices))


def _is_user_interacting_during_load(table_view, search_box):
    if table_view is None:
        return False

    if table_view.state() == table_view.State.EditingState:
        return True

    selection_model = table_view.selectionModel()
    if selection_model and selection_model.hasSelection():
        return True

    if search_box is not None:
        if search_box.hasFocus():
            return True
        if search_box.text().strip():
            return True

    return False


def _is_table_visible_in_active_output_tab(table_view, target_tab):
    if table_view is None or target_tab is None:
        return True

    output_tabs = target_tab.findChild(QTabWidget, "output_tabs")
    if output_tabs is None:
        return True

    active_container = output_tabs.currentWidget()
    if active_container is None:
        return True

    active_table = active_container.findChild(QTableView, "results_table")
    return active_table is table_view


def toggle_table_search(manager):
    tab = manager.tab_widget.currentWidget()
    if not tab:
        return

    search_box = tab.findChild(QLineEdit, "table_search_box")
    search_btn = tab.findChild(QToolButton, "table_search_btn")

    if search_box and search_btn:
        search_btn.hide()
        search_box.show()
        search_box.setFocus()


def handle_query_result(
    manager,
    target_tab,
    conn_data,
    query,
    results,
    columns,
    row_count,
    elapsed_time,
    is_select_query,
    output_mode="current",
    output_tab_index=None,
):
    render_start = perf_now()
    if target_tab in manager.tab_timers:
        manager.tab_timers[target_tab]["timer"].stop()
        manager.tab_timers[target_tab]["timeout_timer"].stop()
        del manager.tab_timers[target_tab]

    manager.main_window.worksheet_manager.save_query_to_history(conn_data, query, "Success", row_count, elapsed_time)

    manager._ensure_at_least_one_output_tab(target_tab)
    if output_mode == "new" and output_tab_index is None:
        output_tab_index = manager.add_output_tab_with_table_name(target_tab, query=query, activate=True)

    if output_tab_index is not None:
        output_tabs = manager._get_output_tabs_widget(target_tab)
        if output_tabs and 0 <= output_tab_index < output_tabs.count():
            output_tabs.setCurrentIndex(output_tab_index)

    table_view, resolved_output_index = manager._ensure_result_table_for_tab(target_tab, output_tab_index)
    if not table_view:
        message_view = target_tab.findChild(QTextEdit, "message_view")
        if message_view:
            message_view.append("Error rendering query result:\n\nOutput table container is unavailable.")
        tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
        if tab_status_label:
            tab_status_label.setText("Error rendering query result")
        manager.stop_spinner(target_tab, success=False)
        return

    output_state = table_view.property("output_state") or {}
    _stop_chunk_loader(output_state)
    message_view = target_tab.findChild(QTextEdit, "message_view")
    tab_status_label = target_tab.findChild(QLabel, "tab_status_label")
    rows_info_label = target_tab.findChild(QLabel, "rows_info_label")

    results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
    results_info_bar = target_tab.findChild(QWidget, "resultsInfoBar")

    if message_view:
        message_view.clear()

    if is_select_query:
        if query.upper().strip().startswith("EXPLAIN (ANALYZE,"):
            try:
                if results and len(results) > 0 and len(results[0]) > 0:
                    json_data = results[0][0]
                    results_stack = target_tab.findChild(QStackedWidget, "results_stacked_widget")
                    explain_visualizer = results_stack.findChild(ExplainVisualizer)
                    if explain_visualizer:
                        explain_visualizer.load_plan(json_data)

                    manager.stop_spinner(target_tab, success=True, target_index=5)

                    msg = f"Explain Analyze executed successfully.\nTime: {elapsed_time:.2f} sec"
                    status = f"Explain Analyze executed | Time: {elapsed_time:.2f} sec"

                    if message_view:
                        previous_text = message_view.toPlainText()
                        if previous_text:
                            message_view.append("\n" + "-" * 50 + "\n")
                        message_view.append(msg)
                    if tab_status_label:
                        tab_status_label.setText(status)
                    manager.status_message_label.setText("Ready")

                    if target_tab in manager.running_queries:
                        del manager.running_queries[target_tab]
                    if not manager.running_queries:
                        manager.cancel_action.setEnabled(False)
                    perf_record(manager, "result_render_ms", perf_elapsed_ms(render_start))
                    execute_start = perf_take(manager, "query_execute_start")
                    perf_record(manager, "query_execute_to_render_ms", perf_elapsed_ms(execute_start))
                    return
            except Exception as e:
                print(f"Error parsing explain result: {e}")

    match_query = re.sub(r"--.*?\n|/\*.*?\*/", "", query, flags=re.DOTALL).strip().upper()
    first_word = match_query.split()[0] if match_query.split() else ""

    q_type_parsed = ""
    parsed = sqlparse.parse(query)
    if parsed:
        for statement in parsed:
            statement_type = statement.get_type().upper()
            if statement_type != "UNKNOWN":
                q_type_parsed = statement_type
                break

    q_type = q_type_parsed if q_type_parsed and q_type_parsed != "UNKNOWN" else first_word

    is_structural = q_type in ["CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE", "COMMENT", "RENAME"]
    is_select = q_type == "SELECT" or first_word == "SELECT"

    final_tab_index = 0

    if not is_structural and (is_select or (columns and len(columns) > 0)):
        final_tab_index = 0
        output_state["column_names"] = list(columns)
        output_state["modified_coords"] = set()
        output_state["new_row_index"] = None

        match = re.search(r"FROM\s+([\"\[\]\w\.]+)", query, re.IGNORECASE)
        if match:
            extracted_table = match.group(1)
            output_state["table_name"] = extracted_table.replace('"', "").replace("[", "").replace("]", "")
            if "." in output_state["table_name"]:
                parts = output_state["table_name"].split(".")
                output_state["schema_name"] = parts[0]
                output_state["real_table_name"] = parts[1]
            else:
                output_state["schema_name"] = None
                output_state["real_table_name"] = output_state["table_name"]
        else:
            output_state["table_name"] = None
            output_state["real_table_name"] = None
            output_state["schema_name"] = None

        current_offset = getattr(target_tab, "current_offset", 0)
        if rows_info_label:
            if row_count > 0:
                start_row = current_offset + 1
                end_row = current_offset + row_count
                rows_info_label.setText(f"Showing rows {start_row} - {end_row}")
            else:
                rows_info_label.setText("No rows returned")

        page_label = target_tab.findChild(QLabel, "page_label")
        if page_label:
            manager.update_page_label(target_tab, row_count)

        model = QStandardItemModel(table_view)
        model.setColumnCount(len(columns))

        headers = [str(col) for col in columns]
        pk_indices = []
        if columns and any(x in columns[0].lower() for x in ["id", "uuid", "pk"]):
            pk_indices.append(0)

        for col_idx, header_text in enumerate(headers):
            model.setHeaderData(col_idx, Qt.Orientation.Horizontal, header_text)

        total_rows = len(results)
        profile_initial_rows, profile_batch_rows = _resolve_chunk_profile(total_rows, manager)
        initial_rows = min(total_rows, profile_initial_rows)
        _append_rows_batch(model, results, columns, pk_indices, 0, initial_rows)

        pending_table_name = output_state.get("real_table_name")
        if pending_table_name and hasattr(manager, "main_window"):
            metadata_signals = MetadataSignals()
            metadata_signals.finished.connect(partial(manager.on_metadata_ready, model))
            metadata_signals.error.connect(partial(manager.on_metadata_error, target_tab))

            worker = FetchMetadataWorker(
                conn_data,
                pending_table_name,
                columns,
                metadata_signals,
            )
            manager.main_window.thread_pool.start(worker)

        proxy_model = output_state.get("cached_proxy_model")
        if proxy_model is None:
            proxy_model = QSortFilterProxyModel(table_view)
            proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            proxy_model.setFilterKeyColumn(-1)
            output_state["cached_proxy_model"] = proxy_model

        proxy_model.setSourceModel(model)
        table_view.setModel(proxy_model)
        search_box = target_tab.findChild(QLineEdit, "table_search_box")
        if search_box and search_box.text():
            proxy_model.setFilterFixedString(search_box.text())

        table_view.setProperty("output_state", output_state)
        current_output_index = output_tab_index
        if current_output_index is None:
            current_output_index = resolved_output_index
        manager._set_output_tab_title(target_tab, current_output_index, query)

        msg = f"Query executed successfully.\n\nTotal rows: {row_count}\nTime: {elapsed_time:.2f} sec"
        status = f"Query executed successfully | Total rows: {row_count} | Time: {elapsed_time:.2f} sec"

        def finalize_result_model():
            try:
                model.itemChanged.disconnect()
            except Exception:
                pass
            model.itemChanged.connect(lambda item: manager.handle_cell_edit(item, target_tab, table_view))

        if total_rows > initial_rows:
            if tab_status_label:
                tab_status_label.setText(f"Loading rows... {initial_rows}/{total_rows}")

            full_render_start = perf_now()
            chunk_timer = QTimer(table_view)
            idle_interval = int(getattr(manager, "result_chunk_idle_interval_ms", 0) or 0)
            chunk_timer.setInterval(max(0, idle_interval))
            search_box = target_tab.findChild(QLineEdit, "table_search_box")
            backpressure_interval = int(getattr(manager, "result_chunk_backpressure_ms", 30) or 30)
            inactive_tab_interval = int(getattr(manager, "result_chunk_inactive_tab_ms", 60) or 60)

            chunk_state = {
                "next_index": initial_rows,
                "total_rows": total_rows,
                "throttle_hits": 0,
                "inactive_tab_hits": 0,
                "batch_count": 0,
            }

            def append_next_chunk():
                if _is_user_interacting_during_load(table_view, search_box):
                    chunk_state["throttle_hits"] += 1
                    chunk_timer.setInterval(max(1, backpressure_interval))
                    return

                if not _is_table_visible_in_active_output_tab(table_view, target_tab):
                    chunk_state["inactive_tab_hits"] += 1
                    chunk_timer.setInterval(max(1, inactive_tab_interval))
                    return

                if chunk_state["throttle_hits"] > 0:
                    chunk_timer.setInterval(max(0, idle_interval))

                start_index = chunk_state["next_index"]
                end_index = min(start_index + profile_batch_rows, chunk_state["total_rows"])
                _append_rows_batch(model, results, columns, pk_indices, start_index, end_index)
                chunk_state["next_index"] = end_index
                chunk_state["batch_count"] += 1

                if end_index >= chunk_state["total_rows"]:
                    chunk_timer.stop()
                    output_state["chunk_loader"] = None
                    finalize_result_model()
                    if tab_status_label:
                        tab_status_label.setText(status)
                    perf_record(manager, "result_full_render_ms", perf_elapsed_ms(full_render_start))
                    perf_record(manager, "result_chunk_interaction_throttle_hits", chunk_state["throttle_hits"])
                    perf_record(manager, "result_chunk_inactive_tab_hits", chunk_state["inactive_tab_hits"])
                    perf_record(manager, "result_chunk_batch_count", chunk_state["batch_count"])
                    return

                if tab_status_label:
                    tab_status_label.setText(f"Loading rows... {end_index}/{chunk_state['total_rows']}")

            output_state["chunk_loader"] = chunk_timer
            chunk_timer.timeout.connect(append_next_chunk)
            chunk_timer.start()
        else:
            finalize_result_model()
            perf_record(manager, "result_full_render_ms", perf_elapsed_ms(render_start))

        if results_info_bar:
            results_info_bar.show()
    else:
        final_tab_index = 1

        table_view.setModel(QStandardItemModel(table_view))
        should_refresh_tree = False

        if q_type.startswith("INSERT"):
            msg = f"INSERT 0 {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
            status = f"INSERT 0 {row_count} | Time: {elapsed_time:.2f} sec"
        elif q_type.startswith("UPDATE"):
            msg = f"UPDATE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
            status = f"UPDATE {row_count} | Time: {elapsed_time:.2f} sec"
        elif q_type.startswith("DELETE"):
            msg = f"DELETE {row_count}\n\nQuery returned successfully in {elapsed_time:.2f} sec."
            status = f"DELETE {row_count} | Time: {elapsed_time:.2f} sec"
        elif q_type.startswith("CREATE"):
            msg = f"CREATE TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            status = f"Table Created | Time: {elapsed_time:.2f} sec"
            should_refresh_tree = True
        elif q_type.startswith("DROP"):
            msg = f"DROP TABLE executed successfully.\n\nTime: {elapsed_time:.2f} sec"
            status = f"DROP success | Time: {elapsed_time:.2f} sec"
            should_refresh_tree = True
        else:
            msg = f"Query executed successfully.\n\nRows affected: {row_count}\nTime: {elapsed_time:.2f} sec"
            status = f"Rows affected: {row_count} | Time: {elapsed_time:.2f} sec"

        if should_refresh_tree:
            manager.main_window.refresh_object_explorer()

        if results_info_bar:
            results_info_bar.hide()

    if message_view:
        message_view.append(msg)
        sb = message_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    if tab_status_label:
        tab_status_label.setText(status)

    manager.status_message_label.setText("Ready")
    manager.stop_spinner(target_tab, success=True, target_index=final_tab_index)
    perf_record(manager, "result_render_ms", perf_elapsed_ms(render_start))
    execute_start = perf_take(manager, "query_execute_start")
    perf_record(manager, "query_execute_to_render_ms", perf_elapsed_ms(execute_start))

    if target_tab in manager.running_queries:
        del manager.running_queries[target_tab]
    if not manager.running_queries:
        manager.cancel_action.setEnabled(False)


def handle_cell_edit(manager, item, tab, table_view=None):
    edit_data = item.data(Qt.ItemDataRole.UserRole)
    if not edit_data:
        return

    orig_val = edit_data.get("orig_val")
    new_val = item.text()

    if table_view is None:
        table_view = manager._get_result_table_for_tab(tab)
    if not table_view:
        return
    output_state = table_view.property("output_state") or {}
    modified_coords = output_state.get("modified_coords")
    if modified_coords is None:
        modified_coords = set()
        output_state["modified_coords"] = modified_coords

    val_changed = str(orig_val) != str(new_val)
    if str(orig_val) == "None" and new_val == "":
        val_changed = False

    row, col = item.row(), item.column()

    if val_changed:
        item.setBackground(QColor("#FFFDD0"))
        modified_coords.add((row, col))
        manager.status.showMessage("Cell modified")
    else:
        item.setBackground(QColor(Qt.GlobalColor.white))
        if (row, col) in modified_coords:
            modified_coords.remove((row, col))

    table_view.setProperty("output_state", output_state)


def on_metadata_ready(manager, model, metadata_dict, original_columns, table_name):
    try:
        if not model:
            return

        pk_indices = []

        for idx, col in enumerate(original_columns):
            col_lower = col.lower()
            meta = metadata_dict.get(col_lower, {})

            suffix = ""
            if meta.get("pk"):
                if meta.get("is_serial"):
                    suffix = " [Serial PK]"
                else:
                    suffix = " [PK]"
                pk_indices.append(idx)
            elif meta.get("nullable") is False:
                suffix = " *"

            data_type = meta.get("data_type", "")
            compact_type = compact_data_type_label(manager, data_type)
            header_text = f"{col}{suffix}\n{compact_type}" if compact_type else f"{col}{suffix}"
            model.setHeaderData(idx, Qt.Orientation.Horizontal, header_text)
            if data_type:
                model.setHeaderData(idx, Qt.Orientation.Horizontal, str(data_type), Qt.ItemDataRole.ToolTipRole)

    except Exception as e:
        print(f"Error updating metadata headers: {e}")


def compact_data_type_label(manager, data_type):
    text = str(data_type or "").strip()
    if not text:
        return ""

    compact = re.sub(r"\s+", " ", text.lower())
    replacements = [
        ("character varying", "varchar"),
        ("varying character", "varchar"),
        ("timestamp without time zone", "timestamp"),
        ("timestamp with time zone", "timestamptz"),
        ("time without time zone", "time"),
        ("time with time zone", "timetz"),
        ("double precision", "float8"),
        ("smallint", "int2"),
        ("int4", "integer"),
        ("bigint", "int8"),
        ("boolean", "bool"),
        ("character", "char"),
    ]

    for source, target in replacements:
        compact = compact.replace(source, target)

    if len(compact) > 20:
        compact = f"{compact[:19]}…"

    return compact


def on_metadata_error(manager, target_tab, error_message):
    print(f"Metadata fetch error for {target_tab}: {error_message}")
