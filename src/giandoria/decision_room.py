"""Generate deployment-local Decision Room provenance from verified enterprise receipts."""

import hashlib
import json
import re
from pathlib import Path

from .data_agent import assert_agent_source, model_contract
from .showcase import ROOT, validate_snapshot


def contract_digest(parts: dict) -> str:
    value = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(value.encode()).hexdigest()


def prepare(root: Path = ROOT) -> dict:
    local = root / ".local"
    snapshot = json.loads((local / "showcase-snapshot.json").read_text())
    config = json.loads((root / "config" / "business.json").read_text())
    validate_snapshot(snapshot, config)
    agent = json.loads((local / "data-agent.json").read_text())
    model = json.loads((local / "sm_giandoria_showcase-readback.json").read_text())
    agent_parts = json.loads((local / "data-agent-readback.json").read_text())
    model_contract(model, snapshot)
    assert_agent_source(agent_parts, agent["workspaceId"], agent["modelId"])
    showcase = json.loads((local / "showcase-verification.json").read_text())
    if agent["modelId"] != showcase["modelId"]:
        raise ValueError("Decision Room and Data Agent must use the same verified semantic model.")
    base = f"https://app.fabric.microsoft.com/groups/{agent['workspaceId']}"
    ontology = json.loads((local / "ontology-verification.json").read_text())
    if ontology["snapshotDigest"] != contract_digest(snapshot):
        raise ValueError("Ontology and Decision Room snapshots differ.")
    context = {
        "run": snapshot["run"], "firstDate": snapshot["firstDate"],
        "throughDate": snapshot["throughDate"], "sequence": snapshot["sequence"],
        "snapshotDigest": contract_digest(snapshot), "modelDigest": contract_digest(model),
        "agentDigest": contract_digest(agent_parts),
        "workspaceId": agent["workspaceId"], "modelId": agent["modelId"], "agentId": agent["agentId"],
        "products": sorted(config["products"]), "channels": sorted(config["channels"]),
        "territories": sorted(config["territories"]),
        "ontologyUrl": f"{base}/ontologies/{ontology['ontologyId']}",
        "commercialUrl": f"{base}/reports/{showcase['items']['rp_giandoria_commercial']}",
        "operationsUrl": f"{base}/reports/{showcase['items']['rp_giandoria_operations']}",
        "agentUrl": f"{base}/aiskills/{agent['agentId']}",
    }
    destination = root / "apps" / "giandoria-decision-room" / "packages" / "shared" / "src" / "source-context.ts"
    destination.write_text("export const sourceContext = " + json.dumps(context, indent=2) + " as const;\n",
                           encoding="utf-8")
    env_path = root / "apps" / "giandoria-decision-room" / "rayfin" / ".env"
    environment = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    for key, value in {"GIANDORIA_MODEL_WORKSPACE_ID": agent["workspaceId"],
                       "GIANDORIA_MODEL_ID": agent["modelId"]}.items():
        environment = re.sub(rf"(?m)^{key}=.*\n?", "", environment)
        environment = environment.rstrip() + f"\n{key}={value}\n"
    env_path.write_text(environment, encoding="utf-8")
    print(json.dumps({"operation": "decision-room.prepare", "run": context["run"],
                      "throughVirtualDate": context["throughDate"], "output": str(destination)}))
    return context


if __name__ == "__main__":
    prepare()
