import json
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from .config import DemoConfig, utc_timestamp

type Json = None | bool | int | float | str | list[Json] | dict[str, Json]


def make_event(
    *,
    config: DemoConfig,
    run_id: str,
    sequence: int,
    tick: int,
    sim_time: datetime,
    wall_time: datetime,
    event_type: str,
    data: dict[str, Json],
) -> dict[str, Json]:
    if not run_id.strip() or type(sequence) is not int or sequence < 1:
        raise ValueError("An event needs a run ID and a positive sequence number.")
    if type(tick) is not int or tick < 0:
        raise ValueError("An event tick must be a non-negative integer.")
    if not event_type.startswith("lab.") or len(event_type.split(".")) < 3:
        raise ValueError("The local foundation emits lab events only.")
    return _envelope(
        config, run_id, sequence, tick, sim_time, wall_time, event_type, data, "/chronos", "lab",
    )


def make_business_event(
    *, config: DemoConfig, run_id: str, sequence: int, tick: int, sim_time: datetime,
    wall_time: datetime, event_type: str, data: dict[str, Json], source: str,
    visibility: str = "enterprise",
) -> dict[str, Json]:
    if source not in {"world", "market", "retail", "trade", "logistics", "factory", "supply", "planning", "finance", "agents"}:
        raise ValueError("Unknown business event source.")
    if visibility not in {"enterprise", "truth"} or len(event_type.split(".")) < 3 or event_type.startswith("lab."):
        raise ValueError("Invalid business event classification.")
    if not run_id.strip() or type(sequence) is not int or sequence < 1 or type(tick) is not int or tick < 0:
        raise ValueError("Invalid business event identity.")
    return _envelope(
        config, run_id, sequence, tick, sim_time, wall_time, event_type, data, f"/{source}", visibility,
    )


def _envelope(
    config: DemoConfig, run_id: str, sequence: int, tick: int, sim_time: datetime,
    wall_time: datetime, event_type: str, data: dict[str, Json], source: str, visibility: str,
) -> dict[str, Json]:
    identity = json.dumps(["urn:giandoria:events:v1", run_id, source, sequence], separators=(",", ":"))
    event: dict[str, Json] = {
        "specversion": "1.0",
        "id": str(uuid5(NAMESPACE_URL, identity)),
        "source": source,
        "type": event_type,
        "time": utc_timestamp(sim_time),
        "datacontenttype": "application/json",
        "dataschema": f"urn:giandoria:schema:{event_type}:1",
        "runid": run_id,
        "scenario": config.scenario,
        "seq": sequence,
        "tick": tick,
        "simlocaldate": sim_time.astimezone(ZoneInfo(config.business_timezone)).date().isoformat(),
        "walltime": utc_timestamp(wall_time),
        "speed": config.speed,
        "visibility": visibility,
        "actor": f"engine:{source.removeprefix('/')}",
        "data": data,
    }
    # Validate and detach mutable caller data before it enters the persistent log.
    return json.loads(json.dumps(event, allow_nan=False))
