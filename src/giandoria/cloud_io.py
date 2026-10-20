import hashlib
import json
import re
import threading
import time
from datetime import UTC, datetime
from typing import Callable
from urllib.parse import quote, urlsplit
from uuid import uuid4

import requests
from azure.core.credentials import TokenCredential
from azure.core.exceptions import AzureError

from .managers import DecisionUnavailable


class RecordedHttp:
    def __init__(self, credential: TokenCredential, hosts: set[str]) -> None:
        self.credential, self.hosts = credential, hosts
        self.audit: list[dict] = []
        self._audit_lock = threading.Lock()

    def record(self, value: dict) -> None:
        value = {"timestamp": datetime.now(UTC).isoformat(), **value}
        print(json.dumps(value, separators=(",", ":")), flush=True)
        with self._audit_lock:
            self.audit.append(value)

    def request(
        self, method: str, url: str, audience: str, *, body: bytes | None = None,
        headers: dict[str, str] | None = None, expected: tuple[int, ...] = (200, 201, 202, 204),
        stream: bool = False,
        read_timeout: float = 60,
    ) -> requests.Response:
        if not 0 < read_timeout <= 180:
            raise ValueError("HTTP read timeout must be in (0, 180] seconds.")
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname not in self.hosts or target.username or target.port not in (None, 443):
            raise ValueError("HTTP target outside configured endpoints.")
        correlation = str(uuid4())
        path = re.sub(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", "<id>", target.path)
        self.record({"operation": "http", "id": correlation, "method": method, "path": path, "status": "Started",
                     "body_bytes": len(body or b""), "body_sha256": hashlib.sha256(body or b"").hexdigest()})
        try:
            auth = {"Authorization": f"Bearer {self.credential.get_token(audience).token}", **(headers or {})}
            response = requests.request(method, url, data=body, headers=auth, timeout=(10, read_timeout),
                                        allow_redirects=False, stream=stream)
        except (requests.RequestException, AzureError) as error:
            self.record({"operation": "http", "id": correlation, "status": "Failed", "error_type": type(error).__name__})
            raise
        self.record({"operation": "http", "id": correlation, "status": "Succeeded" if response.status_code < 400 else "Failed",
                     "code": response.status_code})
        if response.status_code not in expected:
            raise RuntimeError(f"HTTP {response.status_code} during {method} {path}.")
        return response


class BlobStore:
    def __init__(self, http: RecordedHttp, account: str) -> None:
        if not re.fullmatch(r"stgiandoria[a-z0-9]+", account):
            raise ValueError("Unexpected demo Storage account.")
        self.http, self.base = http, f"https://{account}.blob.core.windows.net"
        self.assert_owned: Callable[[], None] = lambda: None

    def request(self, method: str, container: str, name: str, *, body: bytes | None = None,
                headers: dict[str, str] | None = None, expected: tuple[int, ...] = (200, 201, 202, 204),
                query: str = "") -> requests.Response:
        if container not in {"lab-state", "snapshots", "decisions", "outbox"} or ".." in name.split("/"):
            raise ValueError("Storage path outside runtime containers.")
        return self.http.request(
            method, f"{self.base}/{container}/{quote(name, safe='/')}{query}", "https://storage.azure.com/.default",
            body=body, headers={"x-ms-version": "2023-11-03", **(headers or {})}, expected=expected,
        )

    def get_json(self, container: str, name: str) -> dict | None:
        response = self.request("GET", container, name, expected=(200, 404))
        if response.status_code == 404:
            return None
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("Stored JSON must be an object.")
        return value

    def put_json(self, container: str, name: str, value: dict) -> None:
        self.assert_owned()
        self.request("PUT", container, name, body=json.dumps(value, allow_nan=False, separators=(",", ":")).encode(),
                     headers={"x-ms-blob-type": "BlockBlob", "Content-Type": "application/json"})


class RuntimeLease:
    def __init__(self, store: BlobStore) -> None:
        self.store, self.id = store, str(uuid4())
        self.stop = threading.Event()
        self.failure: Exception | None = None
        self.renewed_at = 0.0
        self.thread = threading.Thread(target=self._renew, daemon=True)

    def _request(self, action: str) -> None:
        headers = {"x-ms-lease-action": action}
        if action == "acquire":
            headers.update({"x-ms-proposed-lease-id": self.id, "x-ms-lease-duration": "60"})
        else:
            headers["x-ms-lease-id"] = self.id
        self.store.request("PUT", "lab-state", "business-runtime.lock", headers=headers, query="?comp=lease")

    def __enter__(self) -> "RuntimeLease":
        response = self.store.request(
            "PUT", "lab-state", "business-runtime.lock", body=b"{}", expected=(201, 409, 412),
            headers={"x-ms-blob-type": "BlockBlob", "If-None-Match": "*", "Content-Type": "application/json"},
        )
        if response.status_code != 201 and response.headers.get("x-ms-error-code") not in {
            "BlobAlreadyExists", "ConditionNotMet",
        }:
            raise RuntimeError("Unexpected conflict creating the runtime lock; refusing acquisition.")
        self._request("acquire")
        self.renewed_at = time.monotonic()
        self.store.assert_owned = self.assert_owned
        self.thread.start()
        return self

    def _renew(self) -> None:
        while not self.stop.wait(15):
            try:
                self._request("renew")
                self.renewed_at = time.monotonic()
            except (requests.RequestException, RuntimeError) as error:
                self.failure = error
                return

    def assert_owned(self) -> None:
        if self.failure is not None or time.monotonic() - self.renewed_at > 50:
            raise RuntimeError("Runtime lease lost; refusing further state writes.") from self.failure

    def __exit__(self, *exc: object) -> None:
        self.stop.set()
        self.thread.join(timeout=75)
        self.assert_owned()
        self._request("release")


class FoundryChat:
    def __init__(self, http: RecordedHttp, endpoint: str, deployment: str, version: str) -> None:
        target = urlsplit(endpoint)
        if target.scheme != "https" or not target.hostname or not target.hostname.endswith(".openai.azure.com") or target.path not in ("", "/"):
            raise ValueError("Expected an explicitly configured Azure OpenAI endpoint.")
        self.http, self.endpoint = http, endpoint.rstrip("/")
        self.deployment, self.version = deployment, version

    def choose(self, report: str, max_output_tokens: int) -> tuple[dict, dict]:
        body = {
            "model": self.deployment, "max_completion_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": (
                    "You are the Giandoria S&OP chair in a synthetic business simulation. "
                    "Use only the supplied enterprise reports. Choose exactly one provided option. "
                    "Balance observed service/backlog, constrained capacity and working capital. "
                    "Explain the strategic trade-off in at most 400 characters. You cannot execute tools or invent options."
                )},
                {"role": "user", "content": report},
            ],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "sop_strategy", "strict": True, "schema": {
                    "type": "object", "additionalProperties": False,
                    "properties": {"option": {"type": "string", "enum": ["lean", "balanced", "resilient"]},
                                   "reason": {"type": "string"}}, "required": ["option", "reason"],
                },
            }},
        }
        try:
            response = self.http.request("POST", f"{self.endpoint}/openai/v1/chat/completions",
                                         "https://cognitiveservices.azure.com/.default",
                                         body=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
                                         expected=(200, 400, 401, 403, 408, 429, 500, 502, 503, 504))
        except (requests.Timeout, requests.ConnectionError) as error:
            raise DecisionUnavailable(type(error).__name__) from error
        if response.status_code != 200:
            raise DecisionUnavailable(f"ModelHttp{response.status_code}")
        try:
            result = response.json()
            choice = result["choices"][0]
            if choice["finish_reason"] != "stop":
                raise DecisionUnavailable("IncompleteOrFilteredResponse")
            answer = json.loads(choice["message"]["content"])
            if not isinstance(answer, dict):
                raise DecisionUnavailable("NonObjectResponse")
            return answer, result["usage"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise DecisionUnavailable("InvalidModelResponse") from error
