"""ServiceNow REST API metadata and connection testing using httpx."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
import httpx

logger = logging.getLogger(__name__)

# ServiceNow core platform REST contract paths & dictionary tables
SERVICENOW_TABLE_API_PATH = "/api/now/table"
SERVICENOW_OAUTH_TOKEN_PATH = "/oauth_token.do"
SERVICENOW_CATALOG_TABLE = "sys_db_object"
SERVICENOW_DICTIONARY_TABLE = "sys_dictionary"
SERVICENOW_CONNECTIVITY_PROBES: Tuple[str, ...] = ("sys_db_object", "incident")
_MAX_COLUMN_PAGE_SIZE = 1000
_MAX_COLUMN_PAGES = 5

# Standard core ServiceNow tables to always guarantee in discovery
CORE_SERVICENOW_TABLES: List[Tuple[str, str]] = [
    ("incident", "Incident"),
    ("incident_task", "Incident Task"),
    ("problem", "Problem"),
    ("problem_task", "Problem Task"),
    ("change_request", "Change Request"),
    ("change_task", "Change Task"),
    ("task", "Task"),
    ("sys_user", "User"),
    ("sys_user_group", "User Group"),
    ("sys_user_grmember", "Group Member"),
    ("sys_user_role", "User Role"),
    ("cmdb_ci", "Configuration Item"),
    ("cmdb_ci_server", "Server"),
    ("cmdb_ci_database", "Database"),
    ("sc_request", "Request"),
    ("sc_req_item", "Requested Item"),
    ("sc_task", "Catalog Task"),
    ("kb_knowledge", "Knowledge Article"),
    ("sys_audit", "Audit Log"),
    ("syslog", "System Log"),
    ("sys_dictionary", "Dictionary Entry"),
    ("sys_db_object", "Table Definition"),
    ("sys_attachment", "Attachment"),
]

# Backward compatibility alias
DEFAULT_SERVICENOW_TABLES = CORE_SERVICENOW_TABLES

# Common ServiceNow table inheritance shortcuts (unknown tables resolve dynamically via sys_db_object)
_KNOWN_PARENT_TABLES: Dict[str, str] = {
    "incident": "task",
    "problem": "task",
    "change_request": "task",
    "change_task": "task",
    "incident_task": "task",
    "problem_task": "task",
    "sc_task": "task",
    "sc_req_item": "task",
    "sc_request": "task",
    "asset_task": "task",
    "cmdb_ci_server": "cmdb_ci_computer",
    "cmdb_ci_computer": "cmdb_ci_hardware",
    "cmdb_ci_hardware": "cmdb_ci",
    "cmdb_ci_database": "cmdb_ci",
}


def _normalize_instance_url(url: str) -> str:
    """Normalize a user-entered ServiceNow URL or instance name into a base HTTPS URL."""
    raw = (url or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        if "." not in raw:
            raw = f"{raw}.service-now.com"
        raw = f"https://{raw}"
    return raw


# Public alias for normalization
normalize_instance_url = _normalize_instance_url


def build_table_api_url(
    instance_url: str,
    table_name: str = "",
    api_path: str = SERVICENOW_TABLE_API_PATH,
) -> str:
    """Build a Table API URL for a given instance, optional custom gateway prefix, and table."""
    base = _normalize_instance_url(instance_url)
    prefix = "/" + (api_path or SERVICENOW_TABLE_API_PATH).strip("/")
    url = f"{base}{prefix}/"
    if table_name:
        return f"{url}{table_name.lstrip('/')}"
    return url


def _table_query_params(
    limit: int,
    fields: str = "",
    query: str = "",
    offset: int | None = None,
) -> Dict[str, str]:
    """Build standard read-optimized ServiceNow Table API query parameters."""
    params: Dict[str, str] = {
        "sysparm_limit": str(limit),
        "sysparm_exclude_reference_link": "true",
        "sysparm_no_count": "true",
    }
    if fields:
        params["sysparm_fields"] = fields
    if query:
        params["sysparm_query"] = query
    if offset is not None and offset > 0:
        params["sysparm_offset"] = str(offset)
    return params


def _extract_str(val: Any, default: str = "") -> str:
    """Safely extract a string from a ServiceNow JSON scalar or display/value dict."""
    if val is None:
        return default
    if isinstance(val, dict):
        return str(val.get("value") or val.get("display_value") or default)
    return str(val)


def _fetch_oauth_token(
    instance_url: str,
    client_id: str,
    client_secret: str,
    user: str = "",
    password: str = "",
    timeout: float = 15.0,
) -> str:
    """Fetch an OAuth 2.0 Bearer access token from ServiceNow."""
    norm_url = _normalize_instance_url(instance_url)
    token_url = f"{norm_url}{SERVICENOW_OAUTH_TOKEN_PATH}"

    if user and password:
        data = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": user,
            "password": password,
        }
    else:
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

    with httpx.Client(verify=False, timeout=timeout) as client:
        resp = client.post(token_url, data=data)
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                return token
            raise ValueError("No access_token found in ServiceNow OAuth response.")

        err_msg = resp.text
        try:
            err_json = resp.json()
            err_msg = err_json.get("error_description") or err_json.get("error") or err_msg
        except Exception:
            pass
        raise ValueError(f"OAuth authentication failed (HTTP {resp.status_code}): {err_msg}")


def _build_client(conn_data: Dict[str, Any], timeout: float = 15.0) -> Tuple[httpx.Client, str, str]:
    """Create an authenticated httpx.Client plus normalized base URL and Table API prefix."""
    instance_url = _normalize_instance_url(conn_data.get("instance_url") or "")
    if not instance_url:
        raise ValueError("ServiceNow instance URL is required.")

    auth_type = (conn_data.get("auth_type") or "basic").lower()
    headers = {"Accept": "application/json"}
    auth = None

    if "oauth" in auth_type:
        token = _fetch_oauth_token(
            instance_url,
            conn_data.get("client_id") or "",
            conn_data.get("client_secret") or "",
            user=conn_data.get("user") or "",
            password=conn_data.get("password") or "",
            timeout=timeout,
        )
        headers["Authorization"] = f"Bearer {token}"
    else:
        user = conn_data.get("user") or ""
        password = conn_data.get("password") or ""
        if user or password:
            auth = (user, password)

    client = httpx.Client(
        auth=auth,
        headers=headers,
        timeout=timeout,
        verify=False,  # Allow corporate enterprise self-signed certificates
    )
    api_path = conn_data.get("table_api_path") or SERVICENOW_TABLE_API_PATH
    return client, instance_url, api_path


def test_servicenow_connection(conn_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate ServiceNow credentials and connectivity via standard probe tables."""
    try:
        client, instance_url, api_path = _build_client(conn_data, timeout=10.0)
        with client:
            last_resp = None
            for probe_table in SERVICENOW_CONNECTIVITY_PROBES:
                url = build_table_api_url(instance_url, probe_table, api_path=api_path)
                params = _table_query_params(limit=1, fields="name" if probe_table == SERVICENOW_CATALOG_TABLE else "")
                resp = client.get(url, params=params)
                last_resp = resp
                if resp.status_code == 200:
                    return True, "Connected successfully to ServiceNow!"
                if resp.status_code == 401:
                    break
                if resp.status_code != 403:
                    break

            if last_resp is not None and last_resp.status_code in (401, 403):
                auth_type = (conn_data.get("auth_type") or "basic").lower()
                cred_type = "OAuth credentials" if "oauth" in auth_type else "username or password"
                return False, f"Authentication failed ({last_resp.status_code}): Invalid {cred_type}."
            if last_resp is not None:
                return False, f"ServiceNow returned HTTP {last_resp.status_code}: {last_resp.text[:200]}"
            return False, "ServiceNow connection test received no response."
    except Exception as exc:
        return False, f"Connection error: {exc}"


def _get_table_hierarchy(table_name: str) -> List[str]:
    """Return the inheritance hierarchy for a table (e.g. ['incident', 'task'])."""
    chain = [table_name]
    current = table_name.lower()
    while current in _KNOWN_PARENT_TABLES:
        parent = _KNOWN_PARENT_TABLES[current]
        if parent not in chain:
            chain.append(parent)
        current = parent
    return chain


def fetch_servicenow_tables(conn_data: Dict[str, Any], limit: int = 5000) -> List[Tuple[str, str]]:
    """Retrieve available table names and labels from ServiceNow sys_db_object."""
    table_map: Dict[str, str] = {name: label for name, label in CORE_SERVICENOW_TABLES}

    try:
        client, base_url, api_path = _build_client(conn_data, timeout=25.0)
        with client:
            url = build_table_api_url(base_url, SERVICENOW_CATALOG_TABLE, api_path=api_path)
            params = _table_query_params(
                limit=limit,
                fields="name,label",
                query="nameISNOTEMPTY^ORDERBYname",
            )
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "ServiceNow table catalog returned HTTP %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                for item in resp.json().get("result", []):
                    name = _extract_str(item.get("name")).strip()
                    label = _extract_str(item.get("label"), default=name).strip()
                    if name:
                        table_map[name] = label
    except Exception as exc:
        logger.warning("Could not fetch tables from %s: %s", SERVICENOW_CATALOG_TABLE, exc)

    return sorted(table_map.items(), key=lambda x: x[0].lower())


def _resolve_dynamic_hierarchy(
    client: httpx.Client,
    base_url: str,
    table_name: str,
    api_path: str = SERVICENOW_TABLE_API_PATH,
) -> List[str]:
    """Walk ServiceNow sys_db_object.super_class chain for tables not in _KNOWN_PARENT_TABLES."""
    chain = _get_table_hierarchy(table_name)
    if len(chain) > 1:
        return chain
    base_tables = {"task", "cmdb_ci", "sys_user", "sys_user_group", SERVICENOW_DICTIONARY_TABLE, SERVICENOW_CATALOG_TABLE}
    current = table_name.lower()
    if current in base_tables:
        return chain

    url = build_table_api_url(base_url, SERVICENOW_CATALOG_TABLE, api_path=api_path)
    for _ in range(5):
        try:
            resp = client.get(
                url,
                params=_table_query_params(limit=1, fields="super_class.name", query=f"name={current}"),
            )
            if resp.status_code != 200:
                break
            rows = resp.json().get("result", [])
            parent = _extract_str(rows[0].get("super_class.name")).strip().lower() if rows else ""
            if not parent or parent in chain:
                break
            chain.extend(p for p in _get_table_hierarchy(parent) if p not in chain)
            current = chain[-1]
        except Exception:
            break
    return chain


def fetch_servicenow_columns(conn_data: Dict[str, Any], table_name: str) -> List[Dict[str, Any]]:
    """Fetch column metadata from sys_dictionary for a table and its inheritance chain."""
    columns: List[Dict[str, Any]] = []
    seen_columns = set()

    try:
        client, base_url, api_path = _build_client(conn_data, timeout=20.0)
        with client:
            chain = _resolve_dynamic_hierarchy(client, base_url, table_name, api_path=api_path)
            chain_query = f"nameIN{','.join(chain)}^elementISNOTEMPTY"
            url = build_table_api_url(base_url, SERVICENOW_DICTIONARY_TABLE, api_path=api_path)

            for page_idx in range(_MAX_COLUMN_PAGES):
                offset = page_idx * _MAX_COLUMN_PAGE_SIZE
                params = _table_query_params(
                    limit=_MAX_COLUMN_PAGE_SIZE,
                    fields="name,element,column_label,internal_type,reference",
                    query=chain_query,
                    offset=offset,
                )
                resp = client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "ServiceNow column dictionary for %s returned HTTP %s: %s",
                        table_name,
                        resp.status_code,
                        resp.text[:200],
                    )
                    break

                batch = resp.json().get("result", [])
                for row in batch:
                    col_name = _extract_str(row.get("element")).strip()
                    if col_name and col_name not in seen_columns:
                        seen_columns.add(col_name)
                        columns.append({
                            "name": col_name,
                            "label": _extract_str(row.get("column_label"), default=col_name).strip(),
                            "type": _extract_str(row.get("internal_type"), default="string").upper().strip(),
                            "reference": _extract_str(row.get("reference")).strip(),
                            "pk": col_name == "sys_id",
                        })

                if len(batch) < _MAX_COLUMN_PAGE_SIZE:
                    break
    except Exception as exc:
        logger.warning("Could not fetch columns from %s for %s: %s", SERVICENOW_DICTIONARY_TABLE, table_name, exc)

    return columns
