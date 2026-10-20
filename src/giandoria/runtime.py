import json
import os
import re
import signal
import sys
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from azure.eventhub import EventData, EventHubProducerClient, TransportType
from azure.eventhub.exceptions import EventHubError
from azure.identity import ManagedIdentityCredential

from .business import BusinessConfig, BusinessEngine
from .cloud_io import BlobStore, FoundryChat, RecordedHttp, RuntimeLease
from .config import DemoConfig
from .events import Json
from .managers import JsonStore, StrategicManager


class Publisher(Protocol):
    def send(self, events: list[dict[str, Json]]) -> None: ...


def stream_row(event: dict[str, Json]) -> dict[str, Json]:
    if event["visibility"] != "enterprise":
        raise PermissionError("Truth cannot enter the enterprise Eventstream.")
    return {
        "event_id": event["id"], "run_id": event["runid"], "sequence": event["seq"],
        "sim_ts": event["time"], "wall_ts": event["walltime"], "event_type": event["type"],
        "event": event, "raw_event": json.dumps(event, separators=(",", ":"), allow_nan=False),
    }


class EventstreamPublisher:
    def __init__(self, credential: ManagedIdentityCredential, namespace: str, hub: str, http: RecordedHttp) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9.-]+\.servicebus\.windows\.net", namespace) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", hub):
            raise ValueError("Unexpected Eventstream custom endpoint.")
        self.http = http
        self.client = EventHubProducerClient(
            fully_qualified_namespace=namespace, eventhub_name=hub, credential=credential,
            transport_type=TransportType.AmqpOverWebsocket, auth_timeout=30, send_timeout=30,
            retry_total=1, logging_enable=False,
        )

    def send(self, events: list[dict[str, Json]]) -> None:
        if not events:
            return
        invocation = str(uuid4())
        self.http.record({"operation": "eventstream.send", "id": invocation, "status": "Started", "events": len(events)})
        try:
            batch = self.client.create_batch(max_size_in_bytes=256_000)
            for event in events:
                data = EventData(json.dumps(stream_row(event), separators=(",", ":"), allow_nan=False))
                try:
                    batch.add(data)
                except ValueError:
                    if not len(batch):
                        raise
                    self.client.send_batch(batch)
                    batch = self.client.create_batch(max_size_in_bytes=256_000)
                    batch.add(data)
            if len(batch):
                self.client.send_batch(batch)
        except (EventHubError, ValueError) as error:
            self.http.record({"operation": "eventstream.send", "id": invocation, "status": "Failed", "error_type": type(error).__name__})
            raise
        self.http.record({"operation": "eventstream.send", "id": invocation, "status": "Succeeded", "events": len(events)})

    def close(self) -> None:
        self.client.close()


class CheckpointRunner:
    def __init__(self, engine: BusinessEngine, store: JsonStore, publisher: Publisher) -> None:
        self.engine, self.store, self.publisher = engine, store, publisher
        self.path = f"{engine.run_id}/current.json"

    def restore(self) -> None:
        snapshot = self.store.get_json("snapshots", self.path)
        if snapshot is not None:
            self.engine.restore(snapshot)
        if self.engine.outbox:
            self.flush()

    def flush(self, *, observe: bool = False) -> None:
        if observe:
            self.engine.event("world", "world.business.observed", self.engine.summary())
        self.store.put_json("snapshots", self.path, self.engine.snapshot())
        events = self.engine.outbox
        if events:
            first, last = events[0]["seq"], events[-1]["seq"]
            self.store.put_json("outbox", f"{self.engine.run_id}/{first}-{last}.json", {"version": 1, "events": events})
            self.publisher.send([event for event in events if event["visibility"] == "enterprise"])
            self.engine.outbox = []
            self.store.put_json("snapshots", self.path, self.engine.snapshot())
        self.store.put_json("lab-state", "business-summary.json", self.engine.summary())
        print(json.dumps({"operation": "business.progress", "tick": self.engine.tick,
                          "events": self.engine.sequence}), flush=True)


def execution_target(tick: int, hours: int, target: int | None) -> int:
    if not 1 <= hours <= 744 or target is not None and not 1 <= target <= 17544:
        raise ValueError("Execution must cover 1-744 hours within the two-year collection envelope.")
    return min(tick + hours, target) if target is not None else tick + hours


def run_loop(
    runner: CheckpointRunner, lease: RuntimeLease, store: JsonStore, stop: threading.Event,
    session_id: str, deadline: float, *, speed: int, continuous: bool, hours: int, target: int | None,
    generation: str | None = None,
) -> None:
    if type(speed) is not int or not 1 <= speed <= 8760:
        raise ValueError("Speed must be an integer between 1 and 8760.")
    engine = runner.engine
    engine.speed = speed
    until_tick = None if continuous else execution_target(engine.tick, hours, target)
    next_tick = next_poll = time.monotonic()
    next_flush = next_tick + 5
    if continuous:
        engine.event("world", "world.session.started", {"session_id": session_id, "speed": speed})
    while not stop.is_set() and time.monotonic() < deadline:
        now = time.monotonic()
        if until_tick is not None and engine.tick >= until_tick:
            break
        if now >= next_poll:
            current = store.get_json("lab-state", "active-session.json")
            if current is None or current["id"] != session_id or current["desired"] != "Running":
                break
            if current.get("workerGeneration") != generation:
                break
            if datetime.fromisoformat(current["expiresAt"]) <= datetime.now(UTC):
                break
            next_poll = time.monotonic() + 5
        lease.assert_owned()
        if continuous and now >= next_flush:
            runner.flush(observe=True)
            next_flush = time.monotonic() + 5
        if continuous and now < next_tick:
            stop.wait(max(0, min(next_tick, next_poll, next_flush, deadline) - time.monotonic()))
            continue
        engine.step()
        if continuous:
            next_tick = max(next_tick + 3600 / speed, time.monotonic())
        elif engine.tick % 24 == 0:
            runner.flush()
    runner.flush(observe=continuous)


def main() -> None:
    root = Path(os.environ.get("GIANDORIA_ROOT", "."))
    account = os.environ["GIANDORIA_STATE_ACCOUNT"]
    endpoint = os.environ["GIANDORIA_FOUNDRY_ENDPOINT"]
    namespace = os.environ["GIANDORIA_STREAM_NAMESPACE"]
    hub = os.environ["GIANDORIA_STREAM_HUB"]
    run_id = os.environ.get("GIANDORIA_RUN_ID", "business-demo-001")
    hours = int(os.environ.get("GIANDORIA_HOURS", "384"))
    target = int(os.environ["GIANDORIA_TARGET_TICK"]) if os.environ.get("GIANDORIA_TARGET_TICK") else None
    execution_target(0, hours, target)
    credential = ManagedIdentityCredential(client_id=os.environ["AZURE_CLIENT_ID"])
    host = endpoint.split("://", 1)[-1].rstrip("/")
    http = RecordedHttp(credential, {f"{account}.blob.core.windows.net", host})
    store = BlobStore(http, account)
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    publisher = EventstreamPublisher(credential, namespace, hub, http)
    execution_id = str(uuid4())
    try:
        with RuntimeLease(store) as lease:
            session = store.get_json("lab-state", "active-session.json")
            if session is None or session["desired"] != "Running" or session["state"] not in ("Starting", "Running"):
                raise RuntimeError("No active lab session for this runtime.")
            session_id = session["id"]
            mode = session.get("mode", "Batch")
            if mode not in ("Continuous", "Batch"):
                raise ValueError("Runtime requires an explicit business execution mode.")
            continuous = mode == "Continuous"
            speed = session.get("speed", 8760)
            expires = datetime.fromisoformat(session["expiresAt"])
            deadline = min(time.monotonic() + (86400 if continuous else 600),
                           time.monotonic() + (expires - datetime.now(UTC)).total_seconds() - 30)
            model = FoundryChat(http, endpoint, os.environ["GIANDORIA_MODEL"], os.environ["GIANDORIA_MODEL_VERSION"])
            manager = StrategicManager(
                store, model, run_id, max_calls=int(os.environ.get("GIANDORIA_MAX_MODEL_CALLS", "2")),
                max_reserved_tokens=int(os.environ.get("GIANDORIA_MAX_RESERVED_TOKENS", "24000")),
                budget_scope=session_id if continuous else None,
            )
            engine = BusinessEngine(DemoConfig.load(root / "config" / "demo.json"),
                                    BusinessConfig.load(root / "config" / "business.json"), run_id, manager)
            runner = CheckpointRunner(engine, store, publisher)
            runner.restore()
            run_loop(runner, lease, store, stop, session_id, deadline, speed=speed, continuous=continuous,
                     hours=hours, target=target, generation=session.get("workerGeneration"))
            print(json.dumps({"operation": "business.completed", "summary": engine.summary()}), flush=True)
    finally:
        failure = sys.exception()
        with http._audit_lock:
            audit = http.audit.copy()
        try:
            record = {"records": audit, "error_type": type(failure).__name__ if failure else None,
                      "frames": [{"file": frame.filename, "line": frame.lineno, "function": frame.name}
                                 for frame in traceback.extract_tb(failure.__traceback__)] if failure else []}
            store.request("PUT", "outbox", f"{run_id}/operations/{execution_id}.json",
                          body=json.dumps(record, separators=(",", ":")).encode(),
                          headers={"x-ms-blob-type": "BlockBlob", "Content-Type": "application/json"})
        finally:
            publisher.close()
            credential.close()


if __name__ == "__main__":
    main()
