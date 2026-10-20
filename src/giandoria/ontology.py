"""Publish an enterprise-only, virtual-time Fabric ontology with immutable OneLake Delta bindings."""

import argparse
import base64
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import pyarrow as pa
from azure.identity import AzureCliCredential
from deltalake import DeltaTable, write_deltalake

from .cloud_io import RecordedHttp
from .data_agent import read_definition
from .fabric_deploy import RecordedRequests
from .report_narratives import digest
from .showcase import FACTS, ROOT, validate_snapshot

MARKER = "Giandoria; managed by ontology; synthetic enterprise snapshot only."
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/ontology"
ITEMS = {"lh_giandoria_context": "Lakehouse", "ont_giandoria": "Ontology"}
STORAGE_HOST = "swedencentral-onelake.blob.fabric.microsoft.com"
KEYS = {
    "Product": ("Product",), "Channel": ("Channel",), "Territory": ("Territory",),
    "VirtualDay": ("Date",), "SellOut": ("Date", "Channel", "Product", "Territory"),
    "ProductionFlow": ("Date", "Product"), "FinanceDay": ("Date",), "CompanyObservation": ("Date",),
}
FACT_ENTITIES = {"Sales": "SellOut", "Production": "ProductionFlow",
                 "Finance": "FinanceDay", "Balances": "CompanyObservation"}
RELATIONS = [
    ("SellOut", "Product", "Product"), ("SellOut", "Channel", "Channel"),
    ("SellOut", "Territory", "Territory"), ("SellOut", "VirtualDay", "Date"),
    ("ProductionFlow", "Product", "Product"), ("ProductionFlow", "VirtualDay", "Date"),
    ("FinanceDay", "VirtualDay", "Date"), ("CompanyObservation", "VirtualDay", "Date"),
]


def identifier(name: str) -> str:
    return str(int.from_bytes(hashlib.sha256(f"giandoria:ontology:{name}".encode()).digest()[:8], "big")
               % (2**63 - 1) + 1)


def property_id(entity: str, field: str) -> str:
    return identifier(f"{entity}:{field}")


def enterprise_tables(snapshot: dict, config: dict) -> dict[str, pa.Table]:
    validate_snapshot(snapshot, config)
    tables = {}
    for dimension, settings in (("Product", "products"), ("Channel", "channels"), ("Territory", "territories")):
        tables[dimension] = pa.table({dimension: sorted(config[settings])})
    days = []
    day, end = (date.fromisoformat(snapshot[key]) for key in ("firstDate", "throughDate"))
    while day <= end:
        days.append(day.isoformat())
        day += timedelta(days=1)
    tables["VirtualDay"] = pa.table({"Date": days})
    for source, entity in FACT_ENTITIES.items():
        columns = {}
        for index, (name, kind) in enumerate(FACTS[source]):
            values = [row[index] for row in snapshot["tables"][source]]
            arrow_type = {"dateTime": pa.string(), "int64": pa.int64(), "string": pa.string()}[kind]
            columns[name] = pa.array(values, type=arrow_type)
        tables[entity] = pa.table(columns)
    validate_tables(tables)
    return tables


def validate_tables(tables: dict[str, pa.Table]) -> None:
    if set(tables) != set(KEYS):
        raise ValueError("Ontology must contain exactly the eight enterprise entity tables.")
    for entity, table in tables.items():
        if any(not (pa.types.is_string(table.schema.field(key).type)
                    or pa.types.is_integer(table.schema.field(key).type)) for key in KEYS[entity]):
            raise ValueError(f"Ontology {entity} keys must use supported string or integer types.")
        rows = table.to_pylist()
        keys = [tuple(row[column] for column in KEYS[entity]) for row in rows]
        if not keys or len(keys) != len(set(keys)) or any(None in key for key in keys):
            raise ValueError(f"Ontology {entity} has missing or duplicate entity keys.")
    for source, target, field in RELATIONS:
        allowed = set(tables[target][field].to_pylist())
        if not set(tables[source][field].to_pylist()) <= allowed:
            raise ValueError(f"Ontology relationship {source} to {target} has orphan keys.")


def definition(workspace: str, lakehouse: str, tables: dict[str, pa.Table], snapshot_digest: str) -> dict:
    UUID(workspace)
    UUID(lakehouse)
    validate_tables(tables)
    parts = {"definition.json": {}}

    def source(entity: str) -> dict:
        return {"sourceType": "LakehouseTable", "workspaceId": workspace, "itemId": lakehouse,
                "sourceTableName": table_name(entity, snapshot_digest), "sourceSchema": None}

    for entity, table in tables.items():
        entity_id = identifier(entity)
        properties = []
        for field in table.schema:
            kind = "BigInt" if pa.types.is_integer(field.type) else "String"
            properties.append({"id": property_id(entity, field.name), "name": f"{entity}_{field.name}",
                               "valueType": kind, "redefines": None, "baseTypeNamespaceType": None})
        prefix = f"EntityTypes/{entity_id}"
        parts[f"{prefix}/definition.json"] = {
            "$schema": f"{SCHEMA}/entityType/1.0.0/schema.json",
            "id": entity_id, "namespace": "usertypes", "namespaceType": "Custom",
            "name": entity, "visibility": "Visible", "baseEntityTypeId": None,
            "entityIdParts": [property_id(entity, key) for key in KEYS[entity]],
            "displayNamePropertyId": property_id(entity, KEYS[entity][0]),
            "properties": properties, "timeseriesProperties": [], "untypedProperties": [],
        }
        binding_id = str(uuid5(NAMESPACE_URL, f"giandoria:ontology:binding:{entity}"))
        parts[f"{prefix}/DataBindings/{binding_id}.json"] = {
            "$schema": f"{SCHEMA}/dataBinding/1.0.0/schema.json",
            "id": binding_id, "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries", "sourceTableProperties": source(entity),
                "propertyBindings": [{"sourceColumnName": field.name,
                                      "targetPropertyId": property_id(entity, field.name)}
                                     for field in table.schema],
            }}
    for entity, target, field in RELATIONS:
        name = f"{entity}_for_{target}"
        prefix = f"RelationshipTypes/{identifier(name)}"
        parts[f"{prefix}/definition.json"] = {
            "$schema": f"{SCHEMA}/relationshipType/1.0.0/schema.json",
            "id": identifier(name), "namespace": "usertypes", "namespaceType": "Custom", "name": name,
            "source": {"entityTypeId": identifier(entity)}, "target": {"entityTypeId": identifier(target)},
        }
        binding_id = str(uuid5(NAMESPACE_URL, f"giandoria:ontology:relationship:{name}"))
        parts[f"{prefix}/Contextualizations/{binding_id}.json"] = {
            "$schema": f"{SCHEMA}/contextualization/1.0.0/schema.json",
            "id": binding_id, "dataBindingTable": source(entity),
            "sourceKeyRefBindings": [{"sourceColumnName": key, "targetPropertyId": property_id(entity, key)}
                                     for key in KEYS[entity]],
            "targetKeyRefBindings": [{"sourceColumnName": field, "targetPropertyId": property_id(target, field)}],
        }
    return parts


def table_name(entity: str, snapshot_digest: str) -> str:
    if len(snapshot_digest) != 64 or any(c not in "0123456789abcdef" for c in snapshot_digest):
        raise ValueError("Ontology tables require the complete validated snapshot digest.")
    return f"{entity.lower()}_v1_{snapshot_digest[:16]}"


def publish_item(transport: RecordedRequests, headers: dict, name: str, parts: dict | None = None) -> str:
    body = {}
    if parts is not None:
        platform = {"metadata": {"type": ITEMS[name], "displayName": name, "description": MARKER}}
        body["definition"] = {"parts": [
            {"path": path, "payloadType": "InlineBase64",
             "payload": base64.b64encode(json.dumps(value).encode()).decode()}
            for path, value in {".platform": platform, **parts}.items()
        ]}
    item_id = transport.registry.get(name)
    if item_id and parts is None:
        return item_id
    route = f"/items/{item_id}/updateDefinition" if item_id else "/items"
    if not item_id:
        body.update(displayName=name, type=ITEMS[name], description=MARKER)
    response = transport.request("POST", f"https://api.fabric.microsoft.com{transport.base}{route}",
                                 headers=headers, json=body)
    if response.status_code >= 400:
        raise RuntimeError(f"Fabric {name} publication failed: {response.status_code} {response.text[:2000]}")
    transport.complete_response(response, headers)
    if name not in transport.registry:
        raise RuntimeError("Fabric creation completed without the exact registered item identity.")
    return transport.registry[name]


def upload_tables(http: RecordedHttp, workspace: str, lakehouse: str, tables: dict[str, pa.Table],
                  snapshot_digest: str, directory: Path) -> dict:
    results = {}
    for entity, expected in tables.items():
        name = table_name(entity, snapshot_digest)
        path = directory / name
        if not path.exists():
            write_deltalake(path, expected)
        actual = DeltaTable(path).to_pyarrow_table()
        if not actual.equals(expected) or DeltaTable(path).version() != 0:
            raise ValueError(f"Local Delta data differs from exact enterprise {entity} snapshot.")
        files = sorted(p for p in path.rglob("*") if p.is_file())
        files.sort(key=lambda p: p.suffix == ".json")
        for file in files:
            relative = file.relative_to(path).as_posix()
            if ".." in relative:
                raise ValueError("Unsafe Delta path.")
            url = f"https://{STORAGE_HOST}/{workspace}/{lakehouse}/Tables/{name}/{relative}"
            body = file.read_bytes()
            read = http.request("GET", url, "https://storage.azure.com/.default", expected=(200, 404))
            if read.status_code == 404:
                http.request("PUT", url, "https://storage.azure.com/.default", body=body,
                             headers={"x-ms-blob-type": "BlockBlob", "x-ms-version": "2023-11-03",
                                      "If-None-Match": "*", "Content-Type": "application/octet-stream"})
                read = http.request("GET", url, "https://storage.azure.com/.default")
            if read.content != body:
                raise RuntimeError("OneLake readback differs from immutable enterprise Delta file.")
        results[entity] = {"table": name, "rows": expected.num_rows, "files": len(files)}
    return results


def verify_table_registration(transport: RecordedRequests, headers: dict, lakehouse: str,
                              receipts: dict) -> None:
    deadline = min(transport.deadline, time.monotonic() + 60)
    wanted = {record["table"] for record in receipts.values()}
    while True:
        url = f"https://api.fabric.microsoft.com{transport.base}/lakehouses/{lakehouse}/tables"
        observed = {}
        while url:
            response = transport.request("GET", url, headers=headers)
            response.raise_for_status()
            page = response.json()
            observed.update({table["name"]: table["format"] for table in page["data"]})
            url = page.get("continuationUri")
            if page.get("continuationToken") and not url:
                raise ValueError("Lakehouse table listing omitted the continuation URI.")
        if wanted <= observed.keys():
            if any(not isinstance(observed[name], str) or observed[name].casefold() != "delta"
                   for name in wanted):
                raise RuntimeError("An ontology source is not a registered Delta table.")
            return
        if time.monotonic() + 5 >= deadline:
            raise TimeoutError("Ontology source tables have not registered in the Lakehouse.")
        time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "publish"))
    args = parser.parse_args()
    local = ROOT / ".local"
    snapshot = json.loads((local / "showcase-snapshot.json").read_text())
    config = json.loads((ROOT / "config" / "business.json").read_text())
    tables = enterprise_tables(snapshot, config)
    stamp = digest(snapshot)
    if args.command == "prepare":
        print(json.dumps({"snapshotDigest": stamp, "entities": {k: v.num_rows for k, v in tables.items()},
                          "relationships": len(RELATIONS), "throughVirtualDate": snapshot["throughDate"]}, indent=2))
        return
    workspace = json.loads((local / "demo-workspace.json").read_text())
    if workspace["displayName"] != "ws-giandoria-demo":
        raise ValueError("Ontology requires the recorded enterprise workspace.")
    with AzureCliCredential(process_timeout=60) as credential:
        transport = RecordedRequests(ROOT, workspace["id"], time.monotonic() + 600, ITEMS, marker=MARKER)
        headers = {"Authorization": "Bearer " + credential.get_token("https://api.fabric.microsoft.com/.default").token}
        transport.preflight(headers)
        # Check feature availability before creating a data copy.
        ontology = transport.registry.get("ont_giandoria")
        if ontology is None:
            ontology = publish_item(transport, headers, "ont_giandoria", {"definition.json": {}})
        lakehouse = publish_item(transport, headers, "lh_giandoria_context")
        http = RecordedHttp(credential, {STORAGE_HOST, "api.fabric.microsoft.com"})
        directory = local / "ontology-delta" / stamp
        directory.mkdir(parents=True, exist_ok=True)
        receipts = upload_tables(http, workspace["id"], lakehouse, tables, stamp, directory)
        verify_table_registration(transport, headers, lakehouse, receipts)
        parts = definition(workspace["id"], lakehouse, tables, stamp)
        publish_item(transport, headers, "ont_giandoria", parts)
        actual = read_definition(transport, headers, ontology)
        (local / "ontology-readback.json").write_text(json.dumps(actual, indent=2))
        if actual != parts:
            raise RuntimeError("Ontology readback differs from source-owned entity definitions or bindings.")
        verification = {"workspaceId": workspace["id"], "ontologyId": ontology, "lakehouseId": lakehouse,
                        "snapshotDigest": stamp, "throughVirtualDate": snapshot["throughDate"],
                        "tables": receipts, "relationships": len(RELATIONS)}
        (local / "ontology-verification.json").write_text(json.dumps(verification, indent=2))
        print(json.dumps(verification, indent=2))


if __name__ == "__main__":
    main()
