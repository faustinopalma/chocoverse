"""Authenticate as a dedicated Entra application using the runtime managed identity."""

import argparse
import base64
import json
import os
import re
from contextlib import contextmanager
from typing import Generator
from uuid import UUID, uuid4

from azure.core.credentials import AccessToken
from azure.identity import ClientAssertionCredential, ManagedIdentityCredential

from .cloud_io import BlobStore, RecordedHttp
from .data_agent import DataAgentClient, SCOPE, digest, evaluate_answer
from .showcase import dax

EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def validate_config(config: dict) -> None:
    for field in ("tenantId", "clientId", "principalId", "managedIdentityClientId",
                  "workspaceId", "agentId", "modelId", "originalWorkspaceId"):
        UUID(config[field])
    if config["workspaceId"] == config["originalWorkspaceId"]:
        raise ValueError("Application must not receive access to the original truth-containing workspace.")
    if config["role"] != "Contributor":
        raise ValueError("Unexpected application workspace role.")


def token_identity(token: AccessToken, config: dict, scope: str = SCOPE) -> dict:
    """Check diagnostic identity claims; Entra/Fabric perform cryptographic token validation."""
    payload = token.token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    audiences = {
        SCOPE: {"https://api.fabric.microsoft.com", "https://api.fabric.microsoft.com/"},
        POWER_BI_SCOPE: {"https://analysis.windows.net/powerbi/api", "00000009-0000-0000-c000-000000000000"},
    }
    if (scope not in audiences or claims.get("tid") != config["tenantId"] or claims.get("oid") != config["principalId"]
            or claims.get("appid", claims.get("azp")) != config["clientId"]
            or claims.get("aud") not in audiences[scope]):
        raise ValueError("Token does not represent the dedicated application for the requested analytical audience.")
    return {field: claims.get(field) for field in ("tid", "oid", "appid", "azp", "aud")}


class FabricApplicationCredential:
    def __init__(self, credential: ClientAssertionCredential, config: dict) -> None:
        self.credential, self.config = credential, config

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        if len(scopes) != 1 or scopes[0] not in (SCOPE, POWER_BI_SCOPE) or kwargs:
            raise ValueError("Application credential is restricted to the Fabric and Power BI API scopes.")
        token = self.credential.get_token(scopes[0])
        token_identity(token, self.config, scopes[0])
        return token


@contextmanager
def federated_credential(managed: ManagedIdentityCredential, config: dict) -> Generator[FabricApplicationCredential, None, None]:
    validate_config(config)

    def assertion() -> str:
        return managed.get_token(EXCHANGE_SCOPE).token

    with ClientAssertionCredential(config["tenantId"], config["clientId"], assertion) as application:
        yield FabricApplicationCredential(application, config)


def probe(store: BlobStore, managed: ManagedIdentityCredential, config: dict) -> dict:
    validate_config(config)
    with federated_credential(managed, config) as credential:
        http = RecordedHttp(credential, {"api.fabric.microsoft.com", "api.powerbi.com"})
        credential.get_token(SCOPE)
        http.record({"operation": "data_agent.application_auth", "status": "Succeeded",
                     "method": "ManagedIdentityFederation"})
        # Prove the dedicated application cannot enumerate the workspace containing truth.
        denied = http.request("GET", f"https://api.fabric.microsoft.com/v1/workspaces/{config['originalWorkspaceId']}/items",
                              SCOPE, expected=(401, 403, 404))
        items = http.request("GET", f"https://api.fabric.microsoft.com/v1/workspaces/{config['workspaceId']}/items",
                             SCOPE).json()
        if items.get("continuationToken") or {i["id"] for i in items["value"]} != {config["agentId"], config["modelId"]}:
            raise ValueError("Application workspace contains unexpected or missing sources.")
        rows = dax(http, config["workspaceId"], config["modelId"],
                   'EVALUATE ROW("sold_kg", [Sold kg], "revenue_eur", [Revenue EUR])')
        source_totals = {key.strip("[]"): value for key, value in rows[0].items()}
        evaluate_answer(json.dumps(source_totals), config["probeExpected"])
        question = (
            "Across the entire snapshot return total Sold kg and Revenue EUR. Start with the virtual snapshot "
            "cutoff header and state whether this is live. Then return exactly one JSON object with keys "
            "sold_kg and revenue_eur, using JSON numbers, not strings, and full cents for revenue."
        )
        evidence_path = f"data-agent-auth-check/{uuid4()}.json"
        record = {"state": "Reserved", "authentication": "ManagedIdentityFederation", "appliedToLab": False,
                  "contract": config["contract"], "expected": config["probeExpected"]}
        store.put_json("lab-state", evidence_path, record)
        answer = DataAgentClient(http, config["workspaceId"], config["agentId"]).ask(question)
        record.update(state="Answered", answer=answer, originalWorkspaceDenied=denied.status_code,
                      answerDigest=digest(answer), audit=http.audit)
        store.put_json("lab-state", evidence_path, record)
        actual = evaluate_answer(answer["text"], config["probeExpected"])
        first_date = re.search(r"\d{4}-\d{2}-\d{2}", answer["text"])
        if not first_date or first_date.group() != config["contract"]["throughDate"]:
            raise RuntimeError("Application answer has an incorrect or missing virtual snapshot cutoff.")
        record.update(state="Complete", actual=actual)
        store.put_json("lab-state", evidence_path, record)
        print(json.dumps({"operation": "data_agent.auth_probe", "status": "Succeeded",
                          "originalWorkspaceDenied": denied.status_code, "text": answer["text"]}), flush=True)
        return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe",))
    parser.parse_args()
    account = os.environ["GIANDORIA_STATE_ACCOUNT"]
    with ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"]) as managed:
        http = RecordedHttp(managed, {f"{account}.blob.core.windows.net"})
        store = BlobStore(http, account)
        config = store.get_json("lab-state", "data-agent-service.json")
        if config is None:
            raise RuntimeError("Data Agent service configuration has not been deployed.")
        if config["managedIdentityClientId"] != os.environ["AZURE_CLIENT_ID"]:
            raise ValueError("Data Agent configuration belongs to a different runtime managed identity.")
        probe(store, managed, config)


if __name__ == "__main__":
    main()
