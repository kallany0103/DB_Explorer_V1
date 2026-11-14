"""Centralized feature catalog and feature-flag helpers for Universal SQL Client."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureSpec:
    """Metadata describing an individually toggleable application feature."""

    key: str
    name: str
    category: str
    description: str
    default_enabled: bool = True


FEATURE_CATALOG: tuple[FeatureSpec, ...] = (
    # AI & Query Intelligence
    FeatureSpec(
        key="ai_assistant",
        name="AI SQL Assistant",
        category="AI & Query Intelligence",
        description="Explain queries, inspect SQL logic, and open the AI assistant side panel.",
    ),
    FeatureSpec(
        key="sql_optimizer",
        name="SQL Query Optimizer",
        category="AI & Query Intelligence",
        description="Analyze single queries and multi-statement SQL scripts for tuning recommendations.",
    ),
    FeatureSpec(
        key="execution_plan",
        name="Execution Plan (Explain / Analyze)",
        category="AI & Query Intelligence",
        description="Generate and visualize database EXPLAIN and EXPLAIN ANALYZE plans.",
    ),
    # Visual Modeling & Analytics
    FeatureSpec(
        key="erd_designer",
        name="Entity-Relationship Diagram (ERD)",
        category="Visual Modeling & Analytics",
        description="Generate schema/table ER diagrams and open interactive ERD modeling tabs.",
    ),
    FeatureSpec(
        key="workspace_dashboard",
        name="Monitoring & Workspace Dashboard",
        category="Visual Modeling & Analytics",
        description="Display connection metrics, session activity, and query logs in the Dashboard.",
    ),
    FeatureSpec(
        key="object_inspector",
        name="Object Inspector (Properties & Statistics)",
        category="Visual Modeling & Analytics",
        description="Open DDL Properties and runtime Statistics workbenches for database objects.",
    ),
    # Database Administration & Tools
    FeatureSpec(
        key="schema_compare",
        name="Schema Compare & Diff",
        category="Database Administration & Tools",
        description="Compare schemas across connections and generate synchronization DDL.",
    ),
    FeatureSpec(
        key="backup_restore",
        name="Backup & Restore",
        category="Database Administration & Tools",
        description="Back up and restore databases, schemas, tables, and materialized views.",
    ),
    FeatureSpec(
        key="native_terminals",
        name="Integrated CLI Terminals",
        category="Database Administration & Tools",
        description="Launch native psql, SQL*Plus, and usql shells and execute scripts via CLI.",
    ),
    # Data Federation & Connectors
    FeatureSpec(
        key="data_virtualization",
        name="Data Virtualization & Cross-Source Joins (UDS)",
        category="Data Federation & Connectors",
        description="Create Unified Data Sources, virtual views, and cross-source federated queries.",
    ),
    FeatureSpec(
        key="connector_oracle",
        name="Oracle Database Connector",
        category="Data Federation & Connectors",
        description="Enable Oracle Database and Oracle Fusion Cloud connection types and explorers.",
    ),
    FeatureSpec(
        key="connector_servicenow",
        name="ServiceNow Connector",
        category="Data Federation & Connectors",
        description="Connect to ServiceNow tables via REST API with local sync.",
    ),
    FeatureSpec(
        key="connector_csv",
        name="CSV Connector",
        category="Data Federation & Connectors",
        description="Query local CSV directories with SQL.",
    ),
)

FEATURE_SPEC_BY_KEY: dict[str, FeatureSpec] = {spec.key: spec for spec in FEATURE_CATALOG}

CONNECTOR_FEATURE_KEYS: tuple[str, ...] = (
    "data_virtualization",
    "connector_oracle",
    "connector_servicenow",
    "connector_csv",
)

CONNECTION_TYPE_TO_FEATURE: dict[str, str] = {
    "ORACLE": "connector_oracle",
    "ORACLE_DB": "connector_oracle",
    "ORACLE_FA": "connector_oracle",
    "SERVICENOW": "connector_servicenow",
    "CSV": "connector_csv",
    "UDS": "data_virtualization",
}


def default_feature_flags() -> dict[str, bool]:
    """Return a fresh dictionary mapping every feature key to its default state."""
    return {spec.key: spec.default_enabled for spec in FEATURE_CATALOG}


def normalize_feature_flags(raw_flags: Any) -> dict[str, bool]:
    """Merge persisted or partial flags with defaults, keeping only known keys."""
    flags = default_feature_flags()
    if isinstance(raw_flags, dict):
        for key in flags:
            if key in raw_flags:
                flags[key] = bool(raw_flags[key])
    return flags


def extract_feature_flags(source: Any) -> dict[str, bool] | None:
    """Resolve a feature_flags dict from a dict, MainWindow, manager, or widget."""
    if source is None:
        return None
    if isinstance(source, dict):
        return source

    visited: set[int] = set()
    current = source
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        flags = getattr(current, "feature_flags", None)
        if isinstance(flags, dict):
            return flags

        main_win = getattr(current, "main_window", None)
        if main_win is not None and id(main_win) not in visited:
            flags = getattr(main_win, "feature_flags", None)
            if isinstance(flags, dict):
                return flags

        mgr = getattr(current, "manager", None)
        if mgr is not None and id(mgr) not in visited:
            current = mgr
            continue

        parent_fn = getattr(current, "parent", None)
        if callable(parent_fn):
            try:
                current = parent_fn()
                continue
            except Exception:
                break
        break

    return None


def is_feature_enabled(source: Any, key: str) -> bool:
    """Return True if the given feature key is enabled on source (default True)."""
    flags = extract_feature_flags(source)
    if flags is None:
        spec = FEATURE_SPEC_BY_KEY.get(key)
        return spec.default_enabled if spec else True
    if key in flags:
        return bool(flags[key])
    spec = FEATURE_SPEC_BY_KEY.get(key)
    return spec.default_enabled if spec else True


def is_connection_type_enabled(source: Any, type_code: str | None) -> bool:
    """Return True if the connection type code (or core engine) is enabled."""
    if not type_code:
        return True
    feature_key = CONNECTION_TYPE_TO_FEATURE.get(str(type_code).strip().upper())
    if not feature_key:
        return True
    return is_feature_enabled(source, feature_key)

