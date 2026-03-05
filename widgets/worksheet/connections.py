import db
from PyQt6.QtWidgets import QComboBox


def refresh_all_comboboxes(manager):
    for i in range(manager.tab_widget.count()):
        tab = manager.tab_widget.widget(i)
        combo = tab.findChild(QComboBox, "db_combo_box")
        if combo:
            load_joined_connections(manager, combo)


def load_joined_connections(manager, combo_box):
    try:
        current_data = combo_box.currentData()
        combo_box.clear()
        connections = db.get_all_connections_from_db()
        for connection in connections:
            conn_data = {key: connection[key] for key in connection if key != "display_name"}
            combo_box.addItem(connection["display_name"], conn_data)

        if current_data:
            for i in range(combo_box.count()):
                item_data = combo_box.itemData(i)
                if item_data and item_data.get("id") == current_data.get("id"):
                    combo_box.setCurrentIndex(i)
                    break
    except Exception as error:
        print(f"Error refreshing combobox: {error}")
