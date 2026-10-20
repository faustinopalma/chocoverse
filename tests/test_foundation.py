import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from giandoria.clock import Clock, State
from giandoria.config import DemoConfig, parse_timestamp
from giandoria.events import make_event
from giandoria.store import RunStore

CONFIG = Path(__file__).resolve().parents[1] / "config" / "demo.json"


class ConfigTests(unittest.TestCase):
    def test_agreed_demo_configuration(self) -> None:
        config = DemoConfig.load(CONFIG)
        self.assertEqual(config.epoch, datetime(2030, 5, 31, 22, tzinfo=UTC))
        self.assertEqual(config.business_timezone, "Europe/Rome")
        data = json.loads(CONFIG.read_text())
        self.assertEqual(data["storageAccess"], "public-with-resource-policy-exemption")

    def test_rejects_unapproved_resource_choices(self) -> None:
        for key, value in (
            ("environment", "dev"), ("location", "italynorth"), ("fabricSku", "F8"),
            ("networking", "anonymous"), ("storageAccess", "public"),
            ("storageAccess", "perimeter-pending-check-29"),
        ):
            with self.subTest(key=key):
                data = json.loads(CONFIG.read_text())
                data[key] = value
                with self.assertRaisesRegex(ValueError, key):
                    DemoConfig.from_json(json.dumps(data))

    def test_rejects_invalid_numeric_settings(self) -> None:
        for key, values in (
            ("seed", [-1, True, 1.5, "42"]),
            ("tickSeconds", [0, -1, False, 1.5]),
            ("speed", [0, -1, True, None]),
        ):
            for value in values:
                with self.subTest(key=key, value=value):
                    data = json.loads(CONFIG.read_text())
                    data[key] = value
                    with self.assertRaisesRegex(ValueError, key):
                        DemoConfig.from_json(json.dumps(data))

    def test_rejects_naive_and_submillisecond_timestamps(self) -> None:
        for value in ("2030-06-01T00:00:00", "2030-06-01T00:00:00.000001Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timestamp(value)

    def test_normalizes_offset_to_utc(self) -> None:
        self.assertEqual(parse_timestamp("2030-06-01T00:00:00+02:00"), DemoConfig.load(CONFIG).epoch)


class ClockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock(datetime(2030, 6, 1, tzinfo=UTC))

    def test_only_running_can_advance(self) -> None:
        for state in (State.CREATED, State.PAUSED, State.HIBERNATED, State.STOPPED):
            self.clock.state = state
            with self.subTest(state=state), self.assertRaises(ValueError):
                self.clock.advance(3600)

    def test_pause_hibernate_resume_without_time_gap(self) -> None:
        self.clock.transition("start")
        self.clock.advance(3600)
        frozen = self.clock.sim_time
        self.clock.transition("pause")
        self.clock.transition("hibernate")
        self.assertEqual(self.clock.sim_time, frozen)
        self.clock.transition("resume")
        before, after = self.clock.advance(3600)
        self.assertEqual(before, frozen)
        self.assertEqual(after - before, timedelta(hours=1))
        self.assertEqual(self.clock.tick, 2)

    def test_stopped_is_terminal(self) -> None:
        self.clock.transition("start")
        self.clock.transition("pause")
        self.clock.transition("stop")
        for action in ("resume", "start", "pause", "hibernate", "stop"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.clock.transition(action)

    def test_invalid_tick_never_changes_time(self) -> None:
        self.clock.transition("start")
        before = self.clock.sim_time
        for seconds in (0, -1, True, 0.5):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.clock.advance(seconds)  # type: ignore[arg-type]
            self.assertEqual(self.clock.sim_time, before)
            self.assertEqual(self.clock.tick, 0)


class EventTests(unittest.TestCase):
    def event(self, **changes: object) -> dict:
        arguments = {
            "config": DemoConfig.load(CONFIG), "run_id": "r-0001", "sequence": 1, "tick": 0,
            "sim_time": DemoConfig.load(CONFIG).epoch,
            "wall_time": datetime(2026, 10, 18, tzinfo=UTC),
            "event_type": "lab.run.created", "data": {"seed": 42},
        }
        arguments.update(changes)
        return make_event(**arguments)

    def test_cloud_event_shape_and_business_date(self) -> None:
        event = self.event()
        self.assertEqual(event["specversion"], "1.0")
        self.assertEqual(event["simlocaldate"], "2030-06-01")
        self.assertEqual(event["visibility"], "lab")
        self.assertEqual(event["dataschema"], "urn:giandoria:schema:lab.run.created:1")
        for name in event:
            self.assertRegex(name, r"^[a-z0-9]+$")

    def test_identity_excludes_wall_clock(self) -> None:
        event = self.event()
        later = self.event(wall_time=datetime(2040, 1, 1, tzinfo=UTC))
        self.assertEqual(event["id"], later["id"])
        self.assertEqual(event["time"], later["time"])
        self.assertNotEqual(event["walltime"], later["walltime"])
        self.assertNotEqual(event["id"], self.event(sequence=2)["id"])
        self.assertNotEqual(event["id"], self.event(run_id="r-0002")["id"])

    def test_daylight_saving_uses_rome_not_cloud_region(self) -> None:
        event = self.event(sim_time=datetime(2026, 3, 29, 22, 30, tzinfo=UTC))
        self.assertEqual(event["simlocaldate"], "2026-03-30")

    def test_invalid_event_is_rejected(self) -> None:
        for change in (
            {"sequence": 0}, {"sequence": True}, {"tick": -1}, {"run_id": ""},
            {"event_type": "mes.machine.changed"}, {"data": {"bad": math.nan}},
            {"sim_time": datetime(2030, 1, 1)},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.event(**change)

    def test_payload_is_detached(self) -> None:
        payload = {"nested": {"value": 1}}
        event = self.event(data=payload)
        payload["nested"]["value"] = 2
        self.assertEqual(event["data"]["nested"]["value"], 1)


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "demo.sqlite3"
        self.store = RunStore(self.path)
        self.store.create(CONFIG, "r-0001")

    def events(self) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as connection:
            return [json.loads(row[0]) for row in connection.execute("SELECT body FROM events ORDER BY sequence")]

    def test_persistent_resume_preserves_data_and_sequences(self) -> None:
        self.store.apply("start")
        self.store.apply("advance", 3)
        self.store.apply("hibernate")
        before = self.store.status()
        original = self.events()
        reopened = RunStore(self.path)
        self.assertEqual(reopened.status(), before)
        reopened.apply("resume")
        reopened.apply("advance", 2)
        self.assertEqual(reopened.status()["tick"], 5)
        events = self.events()
        self.assertEqual(events[:len(original)], original)
        self.assertEqual([event["seq"] for event in events], list(range(1, len(events) + 1)))
        self.assertEqual(len({event["id"] for event in events}), len(events))
        self.assertEqual(
            reopened.status()["sim_time"], "2030-06-01T03:00:00.000Z",
        )

    def test_wall_clock_change_does_not_advance_sim_time(self) -> None:
        self.store.apply("start")
        self.store.apply("hibernate")
        frozen = self.store.status()["sim_time"]
        with patch("giandoria.store.datetime") as clock:
            clock.now.return_value = datetime(2050, 1, 1, tzinfo=UTC)
            self.store.apply("resume")
        self.assertEqual(self.store.status()["sim_time"], frozen)

    def test_failed_batch_rolls_back_events_and_clock(self) -> None:
        self.store.apply("start")
        before = self.store.status()
        original = self.events()
        append = self.store._append
        calls = 0

        def failing_append(connection: sqlite3.Connection, event: dict) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Injected write failure")
            append(connection, event)

        with patch.object(self.store, "_append", side_effect=failing_append):
            with self.assertRaisesRegex(RuntimeError, "Injected"):
                self.store.apply("advance", 3)
        self.assertEqual(self.store.status(), before)
        self.assertEqual(self.events(), original)

    def test_refuses_reinitialization_and_export_overwrite(self) -> None:
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.store.create(CONFIG, "different-run")
        self.assertEqual(self.path.read_bytes(), before)
        output = Path(self.temp.name) / "events.jsonl"
        self.assertEqual(self.store.export(output), 1)
        with self.assertRaises(FileExistsError):
            self.store.export(output)
        with self.assertRaises(ValueError):
            self.store.export(self.path)

    def test_invalid_actions_never_write(self) -> None:
        before = self.store.status()
        for action, ticks in (("advance", 1), ("resume", 1), ("unknown", 1), ("start", 0)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.store.apply(action, ticks)
            self.assertEqual(self.store.status(), before)
        self.assertEqual(len(self.events()), 1)

    def test_missing_database_is_not_created_by_status(self) -> None:
        missing = Path(self.temp.name) / "missing.sqlite3"
        with self.assertRaises(FileNotFoundError):
            RunStore(missing).status()
        self.assertFalse(missing.exists())

    def test_concurrent_writers_keep_contiguous_ticks_and_sequences(self) -> None:
        self.store.apply("start")
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = [workers.submit(RunStore(self.path).apply, "advance", 10) for _ in range(2)]
            for result in results:
                result.result()
        self.assertEqual(self.store.status()["tick"], 20)
        events = self.events()
        self.assertEqual([event["seq"] for event in events], list(range(1, 23)))
        self.assertEqual([event["tick"] for event in events[2:]], list(range(1, 21)))

    def test_replay_preserves_event_identity_and_simulation_state(self) -> None:
        other = RunStore(Path(self.temp.name) / "replay.sqlite3")
        other.create(CONFIG, "r-0001")
        for store in (self.store, other):
            store.apply("start")
            store.apply("advance", 24)
            store.apply("hibernate")
        self.assertEqual(self.store.status(), other.status())
        output = Path(self.temp.name) / "replay.jsonl"
        other.export(output)
        replay = [json.loads(line) for line in output.read_text().splitlines()]
        for original, repeated in zip(self.events(), replay, strict=True):
            for key in ("id", "type", "time", "simlocaldate", "runid", "scenario", "seq", "tick"):
                self.assertEqual(original[key], repeated[key])

    def test_export_round_trip_matches_persisted_envelopes(self) -> None:
        self.store.apply("start")
        self.store.apply("advance", 5)
        output = Path(self.temp.name) / "events.jsonl"
        self.assertEqual(self.store.export(output), 7)
        self.assertEqual([json.loads(line) for line in output.read_text().splitlines()], self.events())

    def test_cli_reports_failure_and_nonzero_exit(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "giandoria", "--database", str(self.path), "advance"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Only a running clock", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
