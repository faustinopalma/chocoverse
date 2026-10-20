"""Deploy an enterprise-only Data Agent workspace on the existing demo capacity."""

import argparse
import base64
import json
import time
from pathlib import Path

from azure.identity import AzureCliCredential

from .cloud_io import RecordedHttp
from .data_agent import (
    MARKER as AGENT_MARKER, NAME, SCOPE, assert_agent_source, definition, evaluation_cases, model_contract, read_definition,
)
from .fabric_deploy import RecordedRequests
from .showcase import ROOT, MARKER as MODEL_MARKER, model_definition, refresh, validate_snapshot, verify

WORKSPACE_NAME = "ws-giandoria-agent-demo"
WORKSPACE_MARKER = "Giandoria demo; enterprise-only Data Agent boundary; managed by data_agent_service."
SERVICE_ROOT = ROOT / ".local" / "data-agent-service"
MODEL_NAME = "sm_giandoria_showcase"


def ensure_workspace(http: RecordedHttp, original: dict, local: Path) -> dict:
    original_url = f"https://api.fabric.microsoft.com/v1/workspaces/{original['id']}"
    parent = http.request("GET", original_url, SCOPE).json()
    if parent["displayName"] != "ws-giandoria-demo" or not parent.get("capacityId"):
        raise ValueError("Original demo workspace or paid capacity identity changed.")
    path = local / "workspace.json"
    record = json.loads(path.read_text()) if path.exists() else None
    url = "https://api.fabric.microsoft.com/v1/workspaces"
    matches = []
    while url:
        page = http.request("GET", url, SCOPE).json()
        matches.extend(w for w in page["value"] if w["displayName"] == WORKSPACE_NAME)
        if page.get("continuationToken") and not page.get("continuationUri"):
            raise ValueError("Incomplete workspace discovery.")
        url = page.get("continuationUri")
    if len(matches) > 1 or matches and (not record or matches[0]["id"] != record["id"]):
        raise ValueError("Refusing to adopt an unrecorded or ambiguous service workspace.")
    if not matches:
        if record:
            raise ValueError("Recorded service workspace disappeared.")
        record = http.request("POST", "https://api.fabric.microsoft.com/v1/workspaces", SCOPE, body=json.dumps({
            "displayName": WORKSPACE_NAME, "description": WORKSPACE_MARKER, "capacityId": parent["capacityId"],
        }).encode(), headers={"Content-Type": "application/json"}).json()
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if record is None:
        raise ValueError("Service workspace identity missing.")
    actual = http.request("GET", f"https://api.fabric.microsoft.com/v1/workspaces/{record['id']}", SCOPE).json()
    if (actual.get("description") != WORKSPACE_MARKER or actual.get("capacityId") != parent["capacityId"]
            or actual["id"] == parent["id"]):
        raise ValueError("Service workspace boundary or capacity changed.")
    return actual


def publish(transport: RecordedRequests, headers: dict, name: str, parts: dict) -> str:
    transport.preflight(headers)
    item_id = transport.registry.get(name)
    body: dict = {"definition": {"parts": [
        {"path": p, "payloadType": "InlineBase64", "payload": base64.b64encode(json.dumps(v).encode()).decode()}
        for p, v in parts.items()]}}
    if not item_id:
        body.update(displayName=name, type=transport.expected[name], description=transport.marker)
    suffix = f"/items/{item_id}/updateDefinition" if item_id else "/items"
    response = transport.request("POST", f"https://api.fabric.microsoft.com{transport.base}{suffix}",
                                 headers=headers, json=body)
    response.raise_for_status()
    transport.complete_response(response, headers)
    return transport.registry[name]


def ensure_role(http: RecordedHttp, workspace: str, principal: str, *, upgrade_viewer: bool = False) -> None:
    role = "Contributor"
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace}/roleAssignments"
    page = http.request("GET", url, SCOPE).json()
    if page.get("continuationToken"):
        raise ValueError("Workspace roles need pagination review.")
    roles = [r for r in page["value"] if r["principal"]["id"] == principal]
    if len(roles) > 1:
        raise ValueError("Multiple service principal workspace roles.")
    if roles and roles[0]["role"] != role:
        if not upgrade_viewer or roles[0]["role"] != "Viewer":
            raise ValueError("Existing service principal role differs; no automatic privilege escalation.")
        http.request("PATCH", url + f"/{roles[0]['id']}", SCOPE, body=json.dumps({"role": role}).encode(),
                     headers={"Content-Type": "application/json"})
    if not roles:
        http.request("POST", url, SCOPE, body=json.dumps({
            "principal": {"id": principal, "type": "ServicePrincipal"}, "role": role,
        }).encode(), headers={"Content-Type": "application/json"})
    actual = http.request("GET", url, SCOPE).json()
    if not any(r["principal"]["id"] == principal and r["role"] == role for r in actual["value"]):
        raise RuntimeError("Service principal role readback failed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-only", action="store_true", help="Check existing sources and reconcile access without republishing.")
    parser.add_argument("--upgrade-viewer", action="store_true",
                        help="Explicitly replace a non-working Viewer role with the documented Contributor minimum.")
    args = parser.parse_args()
    local = ROOT / ".local"
    identity = json.loads((local / "data-agent-identity.json").read_text())
    original = json.loads((local / "demo-workspace.json").read_text())
    snapshot = json.loads((local / "showcase-snapshot.json").read_text())
    config = json.loads((ROOT / "config" / "business.json").read_text())
    validate_snapshot(snapshot, config)
    SERVICE_ROOT.mkdir(parents=True, exist_ok=True)
    with AzureCliCredential() as credential:
        http = RecordedHttp(credential, {"api.fabric.microsoft.com", "api.powerbi.com"})
        workspace = ensure_workspace(http, original, SERVICE_ROOT)
        headers = {"Authorization": "Bearer " + credential.get_token(SCOPE).token}
        model_transport = RecordedRequests(SERVICE_ROOT, workspace["id"], time.monotonic() + 900,
                                           {MODEL_NAME: "SemanticModel"}, marker=MODEL_MARKER)
        model_transport.preflight(headers)
        if args.access_only:
            model_id = model_transport.registry[MODEL_NAME]
        else:
            model = model_definition(snapshot, config)
            model_id = publish(model_transport, headers, MODEL_NAME,
                               {"model.bim": model, "definition.pbism": {"version": "1.0", "settings": {}}})
        contract = model_contract(read_definition(model_transport, headers, model_id, model=True), snapshot)
        if not args.access_only:
            refresh(http, workspace["id"], model_id)
            results = verify(http, workspace["id"], model_id, snapshot)
            (SERVICE_ROOT / "verification.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        agent_transport = RecordedRequests(SERVICE_ROOT, workspace["id"], time.monotonic() + 600,
                                           {NAME: "DataAgent"}, marker=AGENT_MARKER)
        agent_transport.preflight(headers)
        agent_id = (agent_transport.registry[NAME] if args.access_only else
                    publish(agent_transport, headers, NAME, definition(workspace["id"], model_id)))
        assert_agent_source(read_definition(agent_transport, headers, agent_id), workspace["id"], model_id)
        items = http.request("GET", f"https://api.fabric.microsoft.com/v1/workspaces/{workspace['id']}/items", SCOPE).json()
        if items.get("continuationToken") or {i["id"] for i in items["value"]} != {model_id, agent_id}:
            raise ValueError("Service workspace must contain only its enterprise model and Data Agent.")
        ensure_role(http, workspace["id"], identity["principalId"], upgrade_viewer=args.upgrade_viewer)
        record = {
            "tenantId": identity["tenantId"], "clientId": identity["clientId"], "principalId": identity["principalId"],
            "managedIdentityClientId": identity["managedIdentityClientId"],
            "workspaceId": workspace["id"], "agentId": agent_id, "modelId": model_id,
            "role": "Contributor", "contract": contract, "originalWorkspaceId": original["id"],
            "probeExpected": {k: v for k, v in evaluation_cases(snapshot)["totals"]["expected"].items()
                              if k in ("sold_kg", "revenue_eur")},
        }
        (local / "data-agent-service.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print("Enterprise-only service workspace and dedicated principal access verified on the existing capacity.")


if __name__ == "__main__":
    main()
