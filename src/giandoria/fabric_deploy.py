import base64
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import UUID, uuid4

from azure.core.credentials import AccessToken
import requests


MARKER = "Giandoria demo; managed by fabric-cicd from fabric/; synthetic data only."
EXPECTED = {"eh_giandoria": "Eventhouse", "kqldb_giandoria": "KQLDatabase"}


class SessionCredential:
    def __init__(self, token: str, expires_on: int) -> None:
        self.token = AccessToken(token, expires_on)

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        if scopes != ("https://api.fabric.microsoft.com/.default",):
            raise ValueError("The deployment credential is restricted to the Fabric API.")
        if self.token.expires_on <= time.time() + 30:
            raise ValueError("Deployment credential expired; acquire a new token through the recorded wrapper.")
        return self.token


class RecordedRequests:
    exceptions = requests.exceptions

    def __init__(self, root: Path, workspace_id: str, deadline: float, expected: dict[str, str] | None = None,
                 *, marker: str = MARKER) -> None:
        UUID(workspace_id)
        self.root = root
        self.workspace_id = workspace_id
        self.base = f"/v1/workspaces/{workspace_id}"
        self.deadline = deadline
        self.expected = dict(EXPECTED if expected is None else expected)
        self.marker = marker
        self.registry_path = root / ".local" / "demo-fabric-items.json"
        self.pending: set[str] = set()
        self.receipts: dict[str, str] = {}
        self.pending_path = root / ".local" / "demo-fabric-pending.json"
        if self.pending_path.exists():
            pending = json.loads(self.pending_path.read_text(encoding="utf-8"))
            if pending["workspaceId"] != workspace_id:
                raise ValueError("Pending publication belongs to another workspace.")
            self.pending = set(pending["items"])
            self.receipts = pending.get("receipts", {})
        self.registry: dict[str, str] = {}
        if self.registry_path.exists():
            record = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if record["workspaceId"] != workspace_id:
                raise ValueError("Fabric item registry belongs to another workspace.")
            self.registry = record["items"]
        self.journal_path = root / ".local" / "command-journal" / f"{os.getpid()}.jsonl"
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, invocation_id: str, operation: str, status: str, details: dict[str, object]) -> None:
        operation = re.sub(r"(?i)[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", "<id>", operation)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "processId": os.getpid(),
            "invocationId": invocation_id,
            "operation": operation,
            "status": status,
            "details": details,
        }
        with self.journal_path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\r\n")
            stream.flush()
            os.fsync(stream.fileno())

    def preflight(self, headers: dict[str, str]) -> None:
        url = f"https://api.fabric.microsoft.com{self.base}/items"
        while url:
            response = self.request("GET", url, headers=headers)
            response.raise_for_status()
            page = response.json()
            for item in page["value"]:
                if item["displayName"] in self.expected:
                    name = item["displayName"]
                    if item["type"] == "SQLEndpoint" and self.expected[name] == "Lakehouse":
                        lakehouse_id = self.registry.get(name)
                        if lakehouse_id is None:
                            raise ValueError("SQL endpoint companion requires a registered Lakehouse.")
                        parent = self.request("GET", f"https://api.fabric.microsoft.com{self.base}/lakehouses/{lakehouse_id}",
                                              headers=headers)
                        parent.raise_for_status()
                        lakehouse = parent.json()
                        if (lakehouse["id"] != lakehouse_id or lakehouse["type"] != "Lakehouse"
                                or lakehouse["displayName"] != name or lakehouse.get("description") != self.marker
                                or lakehouse["properties"]["sqlEndpointProperties"]["id"] != item["id"]):
                            raise ValueError("SQL endpoint is not the exact registered Lakehouse companion.")
                        continue
                    if (name in self.receipts and self.registry.get(name) is None
                            and item["type"] == self.expected[name] and item.get("description") == self.marker):
                        if item["type"] != "Eventhouse":
                            raise ValueError("Interrupted non-Eventhouse creation requires explicit identity recovery.")
                        definition = self.request("POST", f"{url.split('?')[0]}/{item['id']}/getDefinition", headers=headers)
                        definition = self.complete_response(definition, headers)
                        if definition.status_code != 200:
                            raise ValueError("Partial-item recovery needs a completed definition response.")
                        parts = definition.json()["definition"]["parts"]
                        platform = next(part for part in parts if part["path"] == ".platform")
                        actual = json.loads(base64.b64decode(platform["payload"]))
                        expected = json.loads((self.root / "fabric" / f"{name}.{self.expected[name]}" / ".platform").read_text())
                        if (actual["metadata"]["type"] != expected["metadata"]["type"]
                                or actual["metadata"]["displayName"] != expected["metadata"]["displayName"]):
                            raise ValueError("Partial item metadata differs from the exact accepted source creation.")
                        properties = next(part for part in parts if part["path"] == "EventhouseProperties.json")
                        if json.loads(base64.b64decode(properties["payload"])) != {}:
                            raise ValueError("Partial Eventhouse properties differ from the accepted definition.")
                        self.registry[name] = item["id"]
                        self.persist_registry()
                        self.pending.discard(name)
                        self.persist_pending()
                    if (item["type"] != self.expected[item["displayName"]] or item.get("description") != self.marker
                            or self.registry.get(item["displayName"]) != item["id"]):
                        raise ValueError("Refusing to adopt a conflicting or unrecorded Fabric item.")
            url = page.get("continuationUri")
            if page.get("continuationToken") and not url:
                raise ValueError("Fabric item pagination did not include a continuation URI.")

    def complete_response(self, response: requests.Response, headers: dict[str, str]) -> requests.Response:
        while True:
            body = response.json() if response.content else {}
            if response.status_code == 202 and body is None:
                body = {}
            if not isinstance(body, dict):
                raise ValueError("Fabric operation did not return an object or an accepted empty response.")
            status = body.get("status")
            if status in ("Failed", "Undefined"):
                raise RuntimeError(f"Fabric definition operation failed: {json.dumps(body.get('error', body))}")
            location = response.headers.get("Location")
            if response.status_code in (200, 201) and status is None:
                return response
            if response.status_code == 200 and status == "Succeeded" and not location:
                return response
            if not location:
                raise ValueError("Fabric definition operation omitted its next location.")
            delay = float(response.headers.get("Retry-After", "1"))
            if not 0 <= delay < self.deadline - time.monotonic():
                raise TimeoutError("Fabric definition polling exceeds the publishing deadline.")
            time.sleep(delay)
            response = self.request("GET", location, headers=headers)
            response.raise_for_status()

    def persist_registry(self) -> None:
        self.registry_path.write_text(json.dumps({
            "workspaceId": self.workspace_id, "items": self.registry,
        }, indent=2) + "\n", encoding="utf-8")

    def recover_eventhouse_receipt(self) -> None:
        if "eh_giandoria" in self.registry:
            return
        directory = self.root / "fabric" / "eh_giandoria.Eventhouse"
        if not directory.exists():
            return
        parts = [{
            "path": path.name, "payloadType": "InlineBase64",
            "payload": base64.b64encode(path.read_text(encoding="utf-8").encode()).decode(),
        } for path in (directory / ".platform", directory / "EventhouseProperties.json")]
        digests = set()
        for ordered in (parts, list(reversed(parts))):
            body = {
                "displayName": "eh_giandoria", "type": "Eventhouse", "description": MARKER,
                "folderId": "", "definition": {"parts": list(ordered)},
            }
            digests.add(hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest())
        for path in self.journal_path.parent.glob("*.jsonl"):
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            starts = {record["invocationId"]: record for record in records if record["status"] == "Started"}
            for record in records:
                start = starts.get(record["invocationId"])
                if (record["status"] == "Succeeded" and record["details"].get("httpStatus") in (201, 202)
                        and start and start["operation"] == "POST https://api.fabric.microsoft.com/v1/workspaces/<id>/items"
                        and start["details"].get("bodySha256") in digests):
                    self.pending.add("eh_giandoria")
                    self.receipts["eh_giandoria"] = record["invocationId"]
                    self.persist_pending()
                    return

    def persist_pending(self) -> None:
        self.pending_path.write_text(json.dumps({
            "workspaceId": self.workspace_id, "items": sorted(self.pending), "receipts": self.receipts,
        }, indent=2) + "\n", encoding="utf-8")

    def request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "api.fabric.microsoft.com":
            raise ValueError("The publishing transport is restricted to api.fabric.microsoft.com.")
        if parsed.query and not re.fullmatch(r"(?:continuationToken=[^&]+|updateMetadata=True|format=TMSL)", parsed.query):
            raise ValueError("Unsupported Fabric query parameters.")
        if parsed.query == "format=TMSL" and not parsed.path.endswith("/getDefinition"):
            raise ValueError("TMSL format applies only to definition readback.")
        path = parsed.path
        if not (path == self.base or path.startswith(self.base + "/") or path.startswith("/v1/operations/")):
            raise ValueError("Fabric request is outside the recorded demo workspace.")
        if method not in ("GET", "POST"):
            raise ValueError("Deletion, moves and unplanned metadata mutations are not permitted.")
        body = kwargs.get("json")
        if method == "POST":
            if path == self.base + "/items":
                if not isinstance(body, dict):
                    raise ValueError("Fabric creation needs a JSON object.")
                name = body.get("displayName")
                if name not in self.expected or body.get("type") != self.expected[name] or body.get("description") != self.marker:
                    raise ValueError("Unplanned Fabric item creation.")
                self.pending.add(name)
                self.persist_pending()
            elif not (
                path in {f"{self.base}/items/{item_id}/{operation}"
                         for name, item_id in self.registry.items() if name in self.expected
                         for operation in ("updateDefinition", "getDefinition")}
                or path.endswith("/getDefinition") and self.pending
            ):
                raise ValueError("Unplanned Fabric mutation.")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Fabric publishing deadline exceeded.")
        invocation_id = str(uuid4())
        operation = f"{method} {url}"
        encoded = json.dumps(body, sort_keys=True).encode()
        self.record(invocation_id, operation, "Started", {
            "bodySha256": hashlib.sha256(encoded).hexdigest(), "bodyBytes": len(encoded),
        })
        kwargs["timeout"] = min(60, remaining)
        kwargs["allow_redirects"] = False
        try:
            response = requests.request(method, url, **kwargs)
        except requests.RequestException as error:
            self.record(invocation_id, operation, "Failed", {"errorType": type(error).__name__})
            raise
        succeeded = 200 <= response.status_code < 300
        self.record(invocation_id, operation, "Succeeded" if succeeded else "Failed", {
            "httpStatus": response.status_code,
        })
        if succeeded and method == "POST" and path == self.base + "/items":
            self.receipts[body["displayName"]] = invocation_id
            self.persist_pending()
        location = response.headers.get("Location")
        if location:
            resolved = urlsplit(urljoin(url, location))
            if not re.fullmatch(r"/v1/operations/[0-9a-fA-F-]{36}(?:/result)?", resolved.path):
                raise ValueError(f"Unexpected Fabric operation route on host {resolved.netloc!r}.")
            response.headers["Location"] = f"https://api.fabric.microsoft.com{resolved.path}"
        if succeeded and "application/json" in response.headers.get("Content-Type", ""):
            result = response.json()
            name = result.get("displayName") if isinstance(result, dict) else None
            if name in self.pending and name in self.expected and result.get("type") == self.expected[name] and result.get("id"):
                self.registry[name] = result["id"]
                self.persist_registry()
                self.pending.remove(name)
                self.persist_pending()
        return response


def main() -> None:
    os.environ["FABRIC_CICD_FILE_LOGGING_ENABLED"] = "false"
    os.environ["FABRIC_CICD_HTTP_TRACE_ENABLED"] = "false"
    os.environ["FABRIC_CICD_RETRY_API_MAX_DURATION_SECONDS"] = "180"
    os.environ["DEFAULT_API_ROOT_URL"] = "https://api.fabric.microsoft.com"
    from fabric_cicd import FabricWorkspace, publish_all_items

    root = Path(__file__).resolve().parents[2]
    workspace = json.loads((root / ".local" / "demo-workspace.json").read_text(encoding="utf-8"))
    if workspace["displayName"] != "ws-giandoria-demo":
        raise ValueError("Unexpected recorded workspace name.")
    token = os.environ.pop("GIANDORIA_FABRIC_TOKEN")
    credential = SessionCredential(token, int(os.environ.pop("GIANDORIA_FABRIC_TOKEN_EXPIRES")))
    business = os.environ.pop("GIANDORIA_PUBLISH_BUSINESS", "") == "1"
    expected = {"es_giandoria_business": "Eventstream"} if business else EXPECTED
    repository = root / "fabric"
    if business:
        registry = json.loads((root / ".local" / "demo-fabric-items.json").read_text(encoding="utf-8"))
        if registry["workspaceId"] != workspace["id"]:
            raise ValueError("Fabric registry workspace mismatch.")
        repository = root / ".local" / "fabric-business-source"
        source = root / "fabric" / "es_giandoria_business.Eventstream"
        destination = repository / source.name
        destination.mkdir(parents=True, exist_ok=True)
        for path in source.iterdir():
            if path.is_file():
                text = path.read_text(encoding="utf-8").replace("<workspace-id>", workspace["id"]).replace(
                    "<database-id>", registry["items"]["kqldb_giandoria"],
                )
                (destination / path.name).write_text(text, encoding="utf-8")
    transport = RecordedRequests(root, workspace["id"], time.monotonic() + 300, expected)
    transport.recover_eventhouse_receipt()
    transport.preflight({"Authorization": f"Bearer {token}"})
    target = FabricWorkspace(
        workspace_id=workspace["id"],
        repository_directory=str(repository),
        item_type_in_scope=list(expected.values()),
        environment="demo",
        token_credential=credential,
        skip_parameterization=True,
    )
    # Pinned fabric-cicd exposes its endpoint transport for dependency injection.
    target.endpoint.requests = transport
    publish_all_items(target)
    if not set(expected).issubset(transport.registry):
        raise RuntimeError("Publishing did not return the expected item identities.")
    print("Fabric definitions published; no orphan deletion or unrelated item mutation.")


if __name__ == "__main__":
    main()
