# dialogs/connections/__init__.py

from ui.feature_flags import import_feature_symbol

from .base_connection_dialog import BaseConnectionDialog
from .postgres_dialog import PostgresConnectionDialog
from .sqlite_dialog import SQLiteConnectionDialog
from .oracle_dialog import OracleConnectionDialog
from .csv_dialog import CSVConnectionDialog
from .servicenow_dialog import ServiceNowConnectionDialog
UDSConnectionDialog = import_feature_symbol(
    "unified_data_source",
    "dialogs.connections.uds_dialog",
    "UDSConnectionDialog",
)
from .unified_connection_dialog import UnifiedConnectionDialog

from .postgres_ds_dialog import PostgresDataSourceDialog
from .sqlite_ds_dialog import SQLiteDataSourceDialog
from .oracle_ds_dialog import OracleDataSourceDialog
from .csv_ds_dialog import CSVDataSourceDialog
from .servicenow_ds_dialog import ServiceNowDataSourceDialog
from .sqlnet_editor_dialog import SqlnetEditorDialog

__all__ = [
    "BaseConnectionDialog",
    "PostgresConnectionDialog",
    "SQLiteConnectionDialog",
    "OracleConnectionDialog",
    "CSVConnectionDialog",
    "ServiceNowConnectionDialog",
    "UDSConnectionDialog",
    "UnifiedConnectionDialog",
    "PostgresDataSourceDialog",
    "SQLiteDataSourceDialog",
    "OracleDataSourceDialog",
    "CSVDataSourceDialog",
    "ServiceNowDataSourceDialog",
    "SqlnetEditorDialog",
]
