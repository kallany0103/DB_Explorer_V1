# dialogs/__init__.py

from dialogs.tools import (
    ExportDialog,
    SearchObjectsDialog,
    PreferencesDialog,
)

from dialogs.connections import (
    BaseConnectionDialog,
    PostgresConnectionDialog,
    SQLiteConnectionDialog,
    OracleConnectionDialog,
    CSVConnectionDialog,
    ServiceNowConnectionDialog,
    UDSConnectionDialog,
    PostgresDataSourceDialog,
    SQLiteDataSourceDialog,
    OracleDataSourceDialog,
    CSVDataSourceDialog,
    ServiceNowDataSourceDialog,
)

from dialogs.schema_objects import (
    CreateTableDialog,
    CreateViewDialog,
    CreateMaterializedViewDialog,
    CreateFunctionDialog,
    CreateTriggerDialog,
    CreateTriggerFunctionDialog,
    CreateSequenceDialog,
    CreateForeignTableDialog,
    CreatePolicyDialog,
)

from dialogs.properties import (
    TablePropertiesDialog,
    SchemaPropertiesDialog,
    FunctionPropertiesDialog,
    SequencePropertiesDialog,
    ExtensionPropertiesDialog,
    LanguagePropertiesDialog,
    FDWPropertiesDialog,
    ForeignServerPropertiesDialog,
    UserMappingPropertiesDialog,
    TriggerPropertiesDialog,
)

from dialogs.statistics import (
    DatabaseStatisticsDialog,
    ObjectStatisticsDialog,
    StatisticsTab,
)

__all__ = [
    # Tools
    "ExportDialog",
    "SearchObjectsDialog",
    "PreferencesDialog",

    # Connections
    "BaseConnectionDialog",
    "PostgresConnectionDialog",
    "SQLiteConnectionDialog",
    "OracleConnectionDialog",
    "CSVConnectionDialog",
    "ServiceNowConnectionDialog",
    "UDSConnectionDialog",
    "PostgresDataSourceDialog",
    "SQLiteDataSourceDialog",
    "OracleDataSourceDialog",
    "CSVDataSourceDialog",
    "ServiceNowDataSourceDialog",

    # Schema Objects
    "CreateTableDialog",
    "CreateViewDialog",
    "CreateMaterializedViewDialog",
    "CreateFunctionDialog",
    "CreateTriggerDialog",
    "CreateTriggerFunctionDialog",
    "CreateSequenceDialog",
    "CreateForeignTableDialog",
    "CreatePolicyDialog",

    # Properties
    "TablePropertiesDialog",
    "SchemaPropertiesDialog",
    "FunctionPropertiesDialog",
    "SequencePropertiesDialog",
    "ExtensionPropertiesDialog",
    "LanguagePropertiesDialog",
    "FDWPropertiesDialog",
    "ForeignServerPropertiesDialog",
    "UserMappingPropertiesDialog",
    "TriggerPropertiesDialog",

    # Statistics
    "DatabaseStatisticsDialog",
    "ObjectStatisticsDialog",
    "StatisticsTab",
]
