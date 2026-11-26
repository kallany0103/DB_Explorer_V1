# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

from features import ENABLED_FEATURES


FEATURE_DEPENDENCIES = {
    'terminal_psql': 'connector_postgres',
    'terminal_sqlplus': 'connector_oracle',
}


def _is_enabled(feature_key: str) -> bool:
    if not bool(ENABLED_FEATURES.get(feature_key, True)):
        return False
    parent_key = FEATURE_DEPENDENCIES.get(feature_key)
    if parent_key and not _is_enabled(parent_key):
        return False
    return True


def collect_enabled_packages(enabled_features: dict[str, bool]) -> tuple[list, list, list]:
    """Collect datas, binaries, and hiddenimports only for compiled-in features."""
    pkg_names = ['PySide6', 'qtawesome']
    if _is_enabled('connector_oracle'):
        # oracledb thin mode requires the full cryptography package (x509,
        # hazmat bindings, _rust extension).
        pkg_names.extend(['oracledb', 'cryptography', 'cffi'])
    if _is_enabled('connector_servicenow') or _is_enabled('unified_data_source'):
        pkg_names.extend(['dlt', 'duckdb', 'httpx', 'httpcore'])
    elif _is_enabled('ai_assistant') or _is_enabled('auth_sso'):
        pkg_names.extend(['httpx', 'httpcore'])
    if _is_enabled('terminal_psql') or _is_enabled('terminal_sqlplus'):
        pkg_names.append('winpty')

    collected_datas, collected_binaries, collected_hidden = [], [], []
    for pkg in dict.fromkeys(pkg_names):
        tmp_datas, tmp_bins, tmp_hidden = collect_all(pkg)
        collected_datas += tmp_datas
        collected_binaries += tmp_bins
        collected_hidden += tmp_hidden
    return collected_datas, collected_binaries, collected_hidden


def excluded_modules_for_disabled_features(enabled_features: dict[str, bool]) -> list[str]:
    """Return module/package names to strip from the frozen executable."""
    feature_module_map: dict[str, list[str]] = {
        'connector_postgres': ['psycopg2', 'db.postgres_utils', 'dialogs.connections.postgres_dialog', 'dialogs.connections.postgres_ds_dialog'],
        'connector_sqlite': ['dialogs.connections.sqlite_dialog', 'dialogs.connections.sqlite_ds_dialog'],
        'connector_oracle': ['oracledb', 'db.oracle_utils', 'dialogs.connections.oracle_dialog', 'dialogs.connections.oracle_ds_dialog', 'dialogs.connections.sqlnet_editor_dialog', 'utils.oracle_connection_tester'],
        'connector_servicenow': ['dlt', 'db.servicenow_dlt', 'db.servicenow_metadata', 'dialogs.connections.servicenow_dialog', 'dialogs.connections.servicenow_ds_dialog'],
        'connector_csv': ['dialogs.connections.csv_dialog', 'dialogs.connections.csv_ds_dialog'],
        'unified_data_source': ['dialogs.connections.uds_dialog', 'dialogs.cross_source_query_dialog', 'dialogs.uds_virtual_view_dialog'],
        'ai_assistant': ['widgets.ai_assistant'],
        'sql_optimizer': ['db.optimizer', 'workers.optimizer_worker', 'widgets.worksheet.optimize_dialog', 'widgets.worksheet.batch_optimize_dialog', 'widgets.worksheet.plan_diff_view'],
        'erd_designer': ['widgets.erd'],
        'workspace_dashboard': ['widgets.dashboard'],
        'object_inspector': ['widgets.inspector', 'dialogs.properties', 'dialogs.statistics', 'workers.inspector_workers', 'workers.inspector_stats'],
        'schema_compare': ['db.schema_diff_engine', 'dialogs.schema_diff_dialog', 'workers.schema_diff_worker'],
        'backup_restore': ['widgets.backup_and_restore'],
        'terminal_psql': ['widgets.psql_tool', 'widgets.usql_tool'],
        'terminal_sqlplus': ['widgets.sqlplus_tool'],
        'object_describe': ['db.object_describe', 'db.query_describe', 'dialogs.tools.describe_prompt_dialog', 'dialogs.tools.object_describe_dialog', 'dialogs.tools.query_describe_dialog', 'dialogs.tools.quick_describe_dialog'],
        'auth_sso': ['auth', 'ui.account_menu', 'widgets.login_dialog', 'workers.google_login_worker', 'workers.avatar_worker'],
    }
    excludes: list[str] = []
    for key, modules in feature_module_map.items():
        if not _is_enabled(key):
            excludes.extend(modules)
    if not _is_enabled('connector_servicenow') and not _is_enabled('unified_data_source'):
        excludes.extend(['duckdb', 'db.duckdb_manager'])
    if not _is_enabled('terminal_psql') and not _is_enabled('terminal_sqlplus'):
        excludes.extend(['winpty', 'widgets.tools.cli_launcher'])
    return sorted(set(excludes))


def hiddenimports_for_enabled_features(enabled_features: dict[str, bool]) -> list[str]:
    """Return dynamically imported modules (via import_feature_symbol) for enabled features."""
    feature_hidden_map: dict[str, list[str]] = {
        'connector_postgres': ['psycopg2'],
        'connector_servicenow': [
            'dlt.destinations.impl.duckdb',
            'dlt.destinations.impl.duckdb.factory',
            'dlt.sources.rest_api',
        ],
        'unified_data_source': [
            'dialogs.connections.uds_dialog',
            'dialogs.uds_virtual_view_dialog',
        ],
        'ai_assistant': ['widgets.ai_assistant'],
        'erd_designer': ['widgets.erd', 'widgets.erd.widget'],
        'workspace_dashboard': ['widgets.dashboard'],
        'object_inspector': [
            'widgets.inspector.properties_view',
            'widgets.inspector.statistics_view',
        ],
        'terminal_psql': [
            'widgets.usql_tool.terminal_widget',
            'widgets.psql_tool.discovery',
        ],
        'terminal_sqlplus': ['widgets.sqlplus_tool.discovery'],
        'auth_sso': [
            'widgets.login_dialog',
            'ui.account_menu',
            'auth.session',
            'workers.google_login_worker',
        ],
    }
    extra: list[str] = []
    for key, modules in feature_hidden_map.items():
        if _is_enabled(key):
            extra.extend(modules)
    return list(dict.fromkeys(extra))


datas = [
    ('assets', 'assets'),
    ('databases', 'databases'),
    ('ui', 'ui'),
]
binaries = []
hiddenimports = [
    'pandas',
    'openpyxl',
    'sqlglot',
    'keyring.backends.Windows',
    'PySide6.QtSvg',
]
hiddenimports.extend(hiddenimports_for_enabled_features(ENABLED_FEATURES))

_pkg_datas, _pkg_binaries, _pkg_hidden = collect_enabled_packages(ENABLED_FEATURES)
datas += _pkg_datas
binaries += _pkg_binaries
hiddenimports += _pkg_hidden
excludes = excluded_modules_for_disabled_features(ENABLED_FEATURES)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Universal SQL Client',
    icon='assets/app_icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='file_version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=['Qt6*.dll', 'PySide6*.dll', 'python*.dll'],
    name='Universal SQL Client',
)
