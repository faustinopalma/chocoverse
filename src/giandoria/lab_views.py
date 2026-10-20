import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from azure.identity import AzureCliCredential

from .fabric_deploy import RecordedRequests

MARKER = "Giandoria demo; managed by lab_views from fabric/queries; synthetic data only."
ITEMS = {"rt_giandoria": "KQLDashboard", "qs_giandoria": "KQLQueryset"}
PANELS = (
    ("company-now", "Company state - latest virtual instant", "Overview", "table"),
    ("business-history", "Sales, production and shipments (kg) - complete virtual days", "Overview", "line"),
    ("manager-decisions", "Strategic decisions - virtual time (UTC)", "Overview", "table"),
    ("sales-trend", "Sales by channel (kg) - 90 complete virtual days", "Sales", "line"),
    ("channels", "Channel mix (kg) - 90 complete virtual days", "Sales", "bar"),
    ("products", "Product mix (kg) - 90 complete virtual days", "Sales", "bar"),
    ("territories", "Territory mix (kg) - 90 complete virtual days", "Sales", "bar"),
    ("operations-trend", "Stock, backlog and WIP (kg) - last daily virtual observation, 90 days", "Operations", "line"),
    ("recent-business", "Sales, production and shipments (kg) - 90 complete virtual days", "Operations", "line"),
    ("finance-balances", "Cash, receivables and payables (EUR) - last daily virtual observation, 90 days", "Finance", "line"),
    ("finance-flows", "Revenue, purchases and conversion (EUR) - 90 complete virtual days", "Finance", "line"),
    ("monthly-finance", "Revenue, purchases and conversion (EUR) - complete virtual months", "Finance", "line"),
    ("lab-health", "Technical health - last REAL update, not business time", "Diagnostics", "table"),
    ("live-flow", "Event arrivals - REAL UTC time, not business performance", "Diagnostics", "line"),
    ("latest-events", "Latest business activity - virtual time (UTC)", "Diagnostics", "table"),
)


def identity(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"giandoria:lab-views:{name}"))


def definitions(root: Path, endpoint: str, database: str) -> dict[str, dict]:
    host = urlsplit(endpoint)
    if (host.scheme != "https" or not re.fullmatch(r"[a-z0-9.-]+\.kusto\.fabric\.microsoft\.com", host.netloc)
            or host.path not in ("", "/") or host.query):
        raise ValueError("Views require the existing Fabric Kusto endpoint.")
    source_id = identity("source")
    dashboard = {
        "schema_version": "52", "title": "Giandoria - business performance in virtual time",
        "autoRefresh": {"enabled": True, "defaultInterval": "10s", "minInterval": "10s"},
        "baseQueries": [], "parameters": [], "queries": [], "tiles": [],
        "pages": [{"name": name, "id": identity(name)} for name in dict.fromkeys(p[2] for p in PANELS)],
        "dataSources": [{"id": source_id, "name": "Giandoria enterprise", "kind": "manual-kusto",
                         "scopeId": "kusto", "clusterUri": endpoint, "database": database}],
    }
    queryset = {"queryset": {
        "version": "1.0.0",
        "dataSources": [{"id": source_id, "clusterUri": endpoint, "type": "AzureDataExplorer",
                         "databaseName": database}], "tabs": [],
    }}
    positions = {panel[2]: 0 for panel in PANELS}
    for name, title, page, visual in PANELS:
        text = (root / "fabric" / "queries" / f"{name}.kql").read_text(encoding="utf-8")
        query_id = identity(name)
        dashboard["queries"].append({
            "id": query_id, "text": text, "usedVariables": [],
            "dataSource": {"kind": "inline", "dataSourceId": source_id},
        })
        dashboard["tiles"].append({
            "id": identity(f"tile:{name}"), "title": title, "pageId": identity(page),
            "queryRef": {"kind": "query", "queryId": query_id}, "visualType": visual, "visualOptions": {},
            "layout": {"x": 0, "y": positions[page], "width": 12, "height": 5},
        })
        positions[page] += 5
        queryset["queryset"]["tabs"].append({
            "id": query_id, "title": title, "content": text, "dataSourceId": source_id,
        })
    return {"rt_giandoria": dashboard, "qs_giandoria": queryset}


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    local = root / ".local"
    workspace = json.loads((local / "demo-workspace.json").read_text())
    fabric = json.loads((local / "business-fabric.json").read_text())
    if workspace["displayName"] != "ws-giandoria-demo" or workspace["id"] != fabric["workspaceId"]:
        raise ValueError("Lab views require the recorded Giandoria workspace.")
    documents = definitions(root, fabric["queryServiceUri"], fabric["databaseId"])
    transport = RecordedRequests(root, workspace["id"], time.monotonic() + 300, ITEMS, marker=MARKER)
    credential = AzureCliCredential()
    try:
        headers = {"Authorization": f"Bearer {credential.get_token('https://api.fabric.microsoft.com/.default').token}"}
        transport.preflight(headers)
        for name, document in documents.items():
            part = "RealTimeDashboard.json" if ITEMS[name] == "KQLDashboard" else "RealTimeQueryset.json"
            definition = {"parts": [{
                "path": part, "payloadType": "InlineBase64",
                "payload": base64.b64encode(json.dumps(document).encode()).decode(),
            }]}
            body: dict[str, object] = {"definition": definition}
            item_id = transport.registry.get(name)
            path = f"/items/{item_id}/updateDefinition" if item_id else "/items"
            if not item_id:
                body.update({"displayName": name, "type": ITEMS[name], "description": MARKER})
            response = transport.request("POST", f"https://api.fabric.microsoft.com{transport.base}{path}",
                                         headers=headers, json=body)
            response.raise_for_status()
            transport.complete_response(response, headers)
            if name not in transport.registry:
                raise RuntimeError("View publication did not return the accepted item identity.")
            item_id = transport.registry[name]
            readback = transport.request(
                "POST", f"https://api.fabric.microsoft.com{transport.base}/items/{item_id}/getDefinition",
                headers=headers,
            )
            readback.raise_for_status()
            result = transport.complete_response(readback, headers).json()
            actual = next(p for p in result["definition"]["parts"] if p["path"] == part)
            if json.loads(base64.b64decode(actual["payload"])) != document:
                raise RuntimeError("Published view definition differs from the requested source.")
            (local / f"{name}-definition.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    finally:
        credential.close()
    print("Live dashboard and historical queryset published and read back; no source data changed.")


if __name__ == "__main__":
    main()
