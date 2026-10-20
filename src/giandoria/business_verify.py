import argparse
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.etree import ElementTree

import requests
from azure.core.credentials import AccessToken
from azure.identity import AzureCliCredential

from .business import BusinessConfig, BusinessEngine
from .cloud_io import BlobStore, RecordedHttp
from .config import DemoConfig
from .events import Json


class VerificationManager:
    def decide(self, key: str, report: dict[str, Json]) -> dict[str, Json]:
        raise RuntimeError("Read-only verification must not request strategic decisions.")


class VerificationCredential:
    def __init__(self) -> None:
        self.credential = AzureCliCredential()
        self.tokens: dict[str, AccessToken] = {}
        self.lock = threading.Lock()

    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        if len(scopes) != 1 or scopes[0] not in {
            "https://storage.azure.com/.default", "https://api.kusto.windows.net/.default",
        } or kwargs:
            raise ValueError("Unexpected verification token request.")
        scope = scopes[0]
        with self.lock:
            token = self.tokens.get(scope)
            if token is None or token.expires_on <= time.time() + 120:
                token = self.credential.get_token(scope)
                self.tokens[scope] = token
            return token

    def close(self) -> None:
        self.credential.close()


def compare_rows(expected: dict[str, str], rows: list[list]) -> bool:
    actual = {}
    for event_id, hashes, visibilities, count in rows:
        hashes = json.loads(hashes) if isinstance(hashes, str) else hashes
        visibilities = json.loads(visibilities) if isinstance(visibilities, str) else visibilities
        if event_id in actual or count < 1 or visibilities != ["enterprise"]:
            raise ValueError("Invalid identity, visibility or count in business destination.")
        if event_id not in expected or hashes != [expected[event_id]]:
            raise ValueError("Unexpected or altered business event in destination.")
        actual[event_id] = hashes[0]
    return actual.keys() == expected.keys()


def bucket_digests(buckets: dict[int, set[str]]) -> dict[int, tuple[int, str]]:
    return {key: (len(values), hashlib.sha256("|".join(sorted(values)).encode()).hexdigest())
            for key, values in buckets.items()}


def compare_buckets(expected: dict[int, tuple[int, str]], rows: list[list]) -> bool:
    actual = {}
    for bucket, count, digest, invalid, copies in rows:
        if invalid or copies < count or bucket in actual or bucket not in expected:
            raise ValueError("Invalid or unexpected business destination bucket.")
        if count > expected[bucket][0] or count == expected[bucket][0] and digest != expected[bucket][1]:
            raise ValueError("Unexpected or altered raw event in business destination.")
        actual[bucket] = (count, digest)
    return actual == expected


def verify_ledger_continuation(ledger: dict, previous: dict) -> None:
    budgets = ledger.get("session_budgets", {})
    legacy_calls = ledger["calls"] - sum(budget["calls"] for budget in budgets.values())
    if (ledger["calls"] < previous["calls"] or not 0 <= legacy_calls <= 110
            or any(not 0 <= budget["calls"] <= 128 or not 0 <= budget["reserved_tokens"] <= 2_000_000
                   for budget in budgets.values())):
        raise ValueError("Continuation has an invalid model call or session token count.")
    if any(ledger["records"].get(key) != value for key, value in previous["records"].items()):
        raise ValueError("Continuation changed a recorded strategic decision.")
    for scope, budget in previous.get("session_budgets", {}).items():
        current = budgets.get(scope)
        if (current is None or current["calls"] < budget["calls"]
                or current["reserved_tokens"] < budget["reserved_tokens"]):
            raise ValueError("Continuation reset a recorded session budget.")


def query(http: RecordedHttp, endpoint: str, database: str, text: str) -> list[list]:
    result = http.request(
        "POST", f"{endpoint}/v1/rest/query", "https://api.kusto.windows.net/.default",
        body=json.dumps({"db": database, "csl": text}).encode(), headers={"Content-Type": "application/json"},
    ).json()
    if result.get("error") or result.get("Exceptions") or not result.get("Tables"):
        raise RuntimeError("Kusto returned an error or no result.")
    for table in result["Tables"]:
        names = [column["ColumnName"] for column in table["Columns"]]
        if "Severity" in names and "StatusCode" in names:
            if any(row[names.index("Severity")] <= 2 for row in table["Rows"]):
                raise RuntimeError("Kusto reported partial query failure.")
    return result["Tables"][0]["Rows"]


def load_archive(store: BlobStore, cache: Path, name: str) -> dict:
    cached = cache / name.split("/")[-1]
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    archive: dict | None = None
    for attempt in range(3):
        try:
            archive = store.get_json("outbox", name)
            break
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == 2:
                raise
            store.http.record({"operation": "verification.archive.retry", "archive": name,
                               "attempt": attempt + 1, "error_type": type(error).__name__})
            time.sleep(2 ** attempt)
    if archive is None:
        raise ValueError("Listed business archive is missing.")
    temporary = cached.with_suffix(".tmp")
    temporary.write_text(json.dumps(archive, separators=(",", ":")), encoding="utf-8")
    temporary.replace(cached)
    return archive


def verify(root: Path, minimum_tick: int, previous_ledger: Path | None = None) -> dict:
    local = root / ".local"
    fabric = json.loads((local / "business-fabric.json").read_text(encoding="utf-8"))
    endpoint = fabric["queryServiceUri"].rstrip("/")
    host = urlsplit(endpoint)
    if host.scheme != "https" or not re.fullmatch(r"[a-z0-9.-]+\.kusto\.fabric\.microsoft\.com", host.hostname or ""):
        raise ValueError("Unexpected verification endpoint.")
    account = os.environ["GIANDORIA_STATE_ACCOUNT"]
    run_id = "business-demo-001"
    credential = VerificationCredential()
    http = RecordedHttp(credential, {f"{account}.blob.core.windows.net", host.hostname})
    try:
        store = BlobStore(http, account)
        snapshot = store.get_json("snapshots", f"{run_id}/current.json")
        if snapshot is None or snapshot["tick"] < minimum_tick or snapshot["outbox"]:
            raise ValueError("Business runtime did not acknowledge the required completed progress.")
        engine = BusinessEngine(DemoConfig.load(root / "config" / "demo.json"),
                                BusinessConfig.load(root / "config" / "business.json"), run_id, VerificationManager())
        engine.restore(snapshot)
        engine.assert_invariants()
        summary = store.get_json("lab-state", "business-summary.json")
        if summary is None or summary != engine.summary():
            raise ValueError("Business summary differs from the retained checkpoint.")
        ledger = store.get_json("decisions", f"{run_id}/ledger.json")
        if ledger is None or not any(
            record["state"] == "Complete" and record["decision"]["mode"] == "llm"
            for record in ledger["records"].values()
        ):
            raise ValueError("No completed real model decision is recorded.")
        if previous_ledger is not None:
            previous = json.loads(previous_ledger.read_text(encoding="utf-8"))
            verify_ledger_continuation(ledger, previous)
        expected: dict[str, str] = {}
        buckets: dict[int, set[str]] = {}
        all_events = set()
        sequences = set()
        shipped, sold = set(), set()
        cache = local / "business-archive-cache"
        cache.mkdir(exist_ok=True)
        first_time, last_time = None, None
        marker = ""
        while True:
            response = http.request(
                "GET", f"{store.base}/outbox?restype=container&comp=list&prefix={run_id}/&marker={quote(marker)}",
                "https://storage.azure.com/.default", headers={"x-ms-version": "2023-11-03"},
            )
            listing = ElementTree.fromstring(response.content)
            names = [name.text for name in listing.findall("./Blobs/Blob/Name")
                     if name.text is not None and re.fullmatch(rf"{run_id}/\d+-\d+\.json", name.text)]
            with ThreadPoolExecutor(max_workers=8) as pool:
                for archive in pool.map(lambda name: load_archive(store, cache, name), names):
                    for event in archive["events"]:
                        all_events.add(event["id"])
                        sequences.add(event["seq"])
                        first_time = min(first_time or event["time"], event["time"])
                        last_time = max(last_time or event["time"], event["time"])
                        if event["type"] == "logistics.shipment.dispatched":
                            shipped.add(event["data"]["channel"])
                        if event["type"] in ("retail.sellout.recorded", "trade.sellout.recorded"):
                            sold.add(event["data"]["channel"])
                        if event["visibility"] == "enterprise":
                            raw = json.dumps(event, separators=(",", ":"), allow_nan=False).encode()
                            digest = hashlib.sha256(raw).hexdigest()
                            if event["id"] in expected and expected[event["id"]] != digest:
                                raise ValueError("Conflicting retained event identity.")
                            expected[event["id"]] = digest
                            buckets.setdefault((event["seq"] - 1) // 10000, set()).add(f'{event["id"]}:{digest}')
            marker = listing.findtext("NextMarker") or ""
            if not marker:
                break
        if (len(all_events) != snapshot["sequence"] or not expected
                or sequences != set(range(1, snapshot["sequence"] + 1))):
            raise ValueError("Retained archives do not cover the complete checkpoint event sequence.")
        if shipped != set(engine.business.channels) or sold != shipped:
            raise ValueError("Not all configured channels both sold and received shipments.")
        for kind in ("factory.production.started", "factory.quality.released", "planning.purchase.placed",
                     "supply.purchase.confirmed", "factory.material.received", "finance.cash.settled",
                     "planning.strategy.applied"):
            if engine.event_counts.get(kind, 0) < 1:
                raise ValueError(f"Missing causal business activity: {kind}.")
        text = (
            f"bronze_business | where run_id == '{run_id}' "
            "| summarize pairs=make_set(strcat(event_id, ':', hash_sha256(raw_event)), 20000), "
            "invalid=countif(tostring(event.visibility) != 'enterprise'), copies=count() "
            "by bucket=tolong((sequence - 1) / 10000) "
            "| project bucket, count=array_length(pairs), "
            "digest=hash_sha256(strcat_array(array_sort_asc(pairs), '|')), invalid, copies"
        )
        expected_buckets = bucket_digests(buckets)
        deadline = time.monotonic() + 180
        while True:
            rows = query(http, endpoint, fabric["databaseId"], text)
            if compare_buckets(expected_buckets, rows):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Destination incomplete: {sum(row[1] for row in rows)} of {len(expected)} events.")
            time.sleep(10)
        (local / "business-verified-ledger.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        proof = {"tick": engine.tick, "enterprise_events": len(expected), "all_events": len(all_events),
                 "destination_rows": sum(row[4] for row in rows), "channels": sorted(shipped),
                 "first_event_time": first_time, "last_event_time": last_time,
                 "model_calls": ledger["calls"], "invariants": "Passed", "exact_raw_json": "Passed",
                 "model_decisions": [record["decision"] for record in ledger["records"].values()],
                 "observations": summary["observations"]}
        (local / "business-verification.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
        print(json.dumps({"operation": "business.verified",
                          **{key: value for key, value in proof.items()
                             if key not in {"model_decisions", "observations"}}}), flush=True)
        return proof
    finally:
        credential.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum-tick", required=True, type=int)
    parser.add_argument("--previous-ledger", type=Path)
    args = parser.parse_args()
    verify(Path.cwd(), args.minimum_tick, args.previous_ledger)


if __name__ == "__main__":
    main()
