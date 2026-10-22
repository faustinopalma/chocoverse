"""Rehearse and stage append-only business interventions without resetting company history."""

import argparse
import copy
import json
from pathlib import Path

from azure.identity import AzureCliCredential

from .business import BusinessConfig, BusinessEngine
from .cloud_io import BlobStore, RecordedHttp, RuntimeLease
from .config import DemoConfig

ROOT = Path(__file__).resolve().parents[2]


class RehearsalManager:
    def decide(self, key: str, report: dict) -> dict:
        return {"option": "balanced", "reason": "Fixed rehearsal policy; cloud decisions remain model-driven.",
                "mode": "scenario-rehearsal"}


def engine_from(snapshot: dict) -> BusinessEngine:
    engine = BusinessEngine(
        DemoConfig.load(ROOT / "config" / "demo.json"),
        BusinessConfig.load(ROOT / "config" / "business.json"), snapshot["run_id"], RehearsalManager(),
    )
    engine.restore(copy.deepcopy(snapshot))
    return engine


def validate_control(control: dict, run_id: str) -> list[dict]:
    if (not isinstance(control, dict) or set(control) != {"version", "run_id", "changes"}
            or type(control["version"]) is not int or control["version"] != 1 or control["run_id"] != run_id):
        raise ValueError("Scenario control must match this business run and version.")
    return control["changes"]


def rehearse(engine: BusinessEngine, hours: int) -> list[dict]:
    if type(hours) is not int or not 1 <= hours <= 17544:
        raise ValueError("Rehearsals must cover 1-17544 hourly ticks.")
    rows = []
    sold: dict[str, int] = {}
    started: dict[str, int] = {}
    constrained = 0
    engine.outbox = []
    for _ in range(hours):
        engine.step()
        for event in engine.outbox:
            data = event["data"]
            if event["type"] in ("trade.sellout.recorded", "retail.sellout.recorded"):
                key = f'{data["channel"]}:{data["sku"]}'
                sold[key] = sold.get(key, 0) + data["quantity"]
            elif event["type"] == "factory.production.started":
                started[data["sku"]] = started.get(data["sku"], 0) + data["quantity"]
            elif event["type"] == "factory.production.constrained":
                constrained += data["requested"] - data["started"]
        engine.outbox = []
        if engine.tick % 24 == 0:
            rows.append({"tick": engine.tick, "sold_kg": sold, "started_kg": started,
                         "constrained_kg": constrained, "observations": engine.summary()["observations"]})
            sold, started, constrained = {}, {}, 0
    return rows


def stage(store: BlobStore, control: dict) -> int:
    with RuntimeLease(store):
        session = store.get_json("lab-state", "active-session.json")
        if session is None or session.get("desired") != "Stopped" or session.get("state") != "Stopped":
            raise RuntimeError("Stop and verify the saved lab session before staging an intervention.")
        snapshot = store.get_json("snapshots", "business-demo-001/current.json")
        if snapshot is None:
            raise RuntimeError("An existing company checkpoint is required.")
        engine = engine_from(snapshot)
        existing = store.get_json("lab-state", "business-scenario.json")
        if existing is not None:
            engine.set_scenario(validate_control(existing, engine.run_id))
        engine.set_scenario(validate_control(control, engine.run_id))
        store.put_json("lab-state", "business-scenario.json", control)
        if store.get_json("lab-state", "business-scenario.json") != control:
            raise RuntimeError("Staged scenario readback differs from the requested plan.")
        return engine.tick


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("rehearse", "stage"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--hours", type=int, default=4320)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--account")
    args = parser.parse_args()
    control = json.loads(args.plan.read_text(encoding="utf-8"))
    if args.command == "rehearse":
        if args.checkpoint is None or args.output is None:
            parser.error("rehearse requires --checkpoint and --output")
        engine = engine_from(json.loads(args.checkpoint.read_text(encoding="utf-8")))
        engine.set_scenario(validate_control(control, engine.run_id))
        rows = rehearse(engine, args.hours)
        args.output.write_text(json.dumps({"policy": "balanced (assumption)", "days": rows}), encoding="utf-8")
        print(json.dumps({"operation": "scenario.rehearsed", "tick": engine.tick, "days": len(rows)}))
        return
    if args.account is None:
        parser.error("stage requires --account")
    with AzureCliCredential(process_timeout=60) as credential:
        http = RecordedHttp(credential, {f"{args.account}.blob.core.windows.net"})
        tick = stage(BlobStore(http, args.account), control)
        print(json.dumps({"operation": "scenario.staged", "tick": tick, "changes": len(control["changes"])}))


if __name__ == "__main__":
    main()
