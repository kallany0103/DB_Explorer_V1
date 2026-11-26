"""Master build-time feature switchboard for Universal SQL Client.

Set any feature to ``False`` here before running ``build.bat`` (or launching
from source) to completely exclude its code, UI entrypoints, and third-party
dependencies from the application and compiled PyInstaller executable.
"""

ENABLED_FEATURES: dict[str, bool] = {
    # Database Connectors
    "connector_postgres": True,
    "connector_sqlite": True,
    "connector_oracle": True,
    "connector_servicenow": True,
    "connector_csv": True,
    "unified_data_source": False,

    # AI & Query Intelligence
    "ai_assistant": False,
    "sql_optimizer": True,
    "execution_plan": True,

    # Visual Modeling & Analytics
    "erd_designer": True,
    "workspace_dashboard": True,
    "object_inspector": True,

    # Database Administration & Tools
    "schema_compare": True,
    "backup_restore": True,
    "terminal_psql": True,
    "terminal_sqlplus": True,
    "object_describe": True,

    # App Shell & Auth
    "auth_sso": False,
}
