from copy import deepcopy

DEFAULT_SCHEMA = "public"


def full_name(schema_name, table_name):
    schema = schema_name or DEFAULT_SCHEMA
    return f"{schema}.{table_name}"


def normalize_column(column):
    col = deepcopy(column or {})
    col.setdefault("name", "")
    col.setdefault("type", "TEXT")
    col["pk"] = bool(col.get("pk", False))
    col["nullable"] = bool(col.get("nullable", True))
    col["unique"] = bool(col.get("unique", False))
    col["fk"] = bool(col.get("fk", False))
    if col.get("default") is None and "default" in col:
        col["default"] = None
    return col


def normalize_foreign_key(fk):
    item = deepcopy(fk or {})
    item.setdefault("name", "")
    item.setdefault("from", "")
    item.setdefault("table", "")
    item.setdefault("to", "id")
    item.setdefault("type", "many-to-one")
    item.setdefault("on_delete", "NO ACTION")
    item.setdefault("on_update", "NO ACTION")
    item["identifying"] = bool(item.get("identifying", False))
    item["nullable"] = bool(item.get("nullable", True))
    return item


def normalize_entity(entity_data):
    data = deepcopy(entity_data or {})
    data.setdefault("table", "")
    data.setdefault("schema", DEFAULT_SCHEMA)
    data["columns"] = [normalize_column(col) for col in data.get("columns", [])]
    data["foreign_keys"] = [normalize_foreign_key(fk) for fk in data.get("foreign_keys", [])]
    data["notes"] = list(data.get("notes", []))
    return data


def apply_fk_flags(columns, foreign_keys):
    fk_cols = {fk.get("from") for fk in foreign_keys if fk.get("from")}
    normalized = []
    for col in columns:
        item = normalize_column(col)
        item["fk"] = item.get("fk", False) or item["name"] in fk_cols
        normalized.append(item)
    return normalized
