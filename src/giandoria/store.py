import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Iterator

from .clock import Clock, State
from .config import DemoConfig, parse_timestamp, utc_timestamp
from .events import Json, make_event


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.path.is_file():
            raise FileNotFoundError(f"No run database at {self.path}; create it with init first.")
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(self, config_path: Path, run_id: str) -> None:
        if not run_id.strip():
            raise ValueError("run_id must not be empty.")
        text = config_path.read_text(encoding="utf-8")
        config = DemoConfig.from_json(text)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=False)
        with self.connect() as connection:
            connection.execute(
                "CREATE TABLE run (singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "run_id TEXT NOT NULL, config TEXT NOT NULL, state TEXT NOT NULL, "
                "sim_time TEXT NOT NULL, tick INTEGER NOT NULL, sequence INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE events (sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO run VALUES (1, ?, ?, ?, ?, 0, 1)",
                (run_id, text, State.CREATED, utc_timestamp(config.epoch)),
            )
            event = make_event(
                config=config, run_id=run_id, sequence=1, tick=0, sim_time=config.epoch,
                wall_time=datetime.now(UTC), event_type="lab.run.created",
                data={"seed": config.seed, "mode": "offline-foundation"},
            )
            self._append(connection, event)

    @staticmethod
    def _append(connection: sqlite3.Connection, event: dict[str, Json]) -> None:
        connection.execute(
            "INSERT INTO events VALUES (?, ?, ?)",
            (event["seq"], event["id"], json.dumps(event, separators=(",", ":"), allow_nan=False)),
        )

    def apply(self, action: str, ticks: int = 1) -> None:
        if type(ticks) is not int or not 1 <= ticks <= 100_000:
            raise ValueError("ticks must be between 1 and 100000.")
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM run WHERE singleton=1").fetchone()
            if row is None:
                raise ValueError("The run database has no initialized run.")
            config = DemoConfig.from_json(row["config"])
            clock = Clock(parse_timestamp(row["sim_time"]), row["tick"], State(row["state"]))
            sequence = row["sequence"]
            for _ in range(ticks if action == "advance" else 1):
                started = perf_counter()
                data: dict[str, Json]
                if action == "advance":
                    before, after = clock.advance(config.tick_seconds)
                    elapsed = max(perf_counter() - started, 1e-9)
                    event_type = "lab.clock.tick"
                    data = {
                        "tick": clock.tick,
                        "sim_from_ts": utc_timestamp(before),
                        "sim_to_ts": utc_timestamp(after),
                        "speed_target": config.speed,
                        "speed_effective": config.tick_seconds / elapsed,
                        "lag_ms": max(0.0, elapsed - config.tick_seconds / config.speed) * 1000,
                        "mode": "offline-unpaced",
                    }
                else:
                    clock.transition(action)
                    verb = {
                        "start": "started", "resume": "resumed", "pause": "paused",
                        "hibernate": "hibernated", "stop": "stopped",
                    }[action]
                    event_type = f"lab.run.{verb}"
                    data = {"state": clock.state.value, "mode": "offline-foundation"}
                sequence += 1
                event = make_event(
                    config=config, run_id=row["run_id"], sequence=sequence, tick=clock.tick,
                    sim_time=clock.sim_time, wall_time=datetime.now(UTC), event_type=event_type, data=data,
                )
                self._append(connection, event)
            connection.execute(
                "UPDATE run SET state=?, sim_time=?, tick=?, sequence=? WHERE singleton=1",
                (clock.state, utc_timestamp(clock.sim_time), clock.tick, sequence),
            )

    def status(self) -> dict[str, Json]:
        with self.connect() as connection:
            row = connection.execute("SELECT run_id, state, sim_time, tick, sequence FROM run").fetchone()
            if row is None:
                raise ValueError("The run database has no initialized run.")
            return {
                "run_id": row["run_id"], "state": row["state"], "sim_time": row["sim_time"],
                "tick": row["tick"], "sequence": row["sequence"],
                "mode": "offline-foundation", "cloud_resources_modified": False,
            }

    def export(self, path: Path) -> int:
        if path.resolve() == self.path.resolve():
            raise ValueError("An export cannot replace the run database.")
        with self.connect() as connection:
            path.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            with path.open("x", encoding="utf-8", newline="\n") as output:
                for row in connection.execute("SELECT body FROM events ORDER BY sequence"):
                    output.write(row["body"] + "\n")
                    count += 1
            return count
