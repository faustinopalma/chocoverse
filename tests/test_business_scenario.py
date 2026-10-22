import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from giandoria.business import BusinessConfig, BusinessEngine
from giandoria.business_scenario import RehearsalManager, engine_from, rehearse, stage, validate_control

ROOT = Path(__file__).resolve().parents[1]


class Store:
    def __init__(self, snapshot):
        self.values = {
            ("snapshots", "business-demo-001/current.json"): snapshot,
            ("lab-state", "active-session.json"): {"state": "Stopped", "desired": "Stopped"},
        }

    def get_json(self, container, name):
        return copy.deepcopy(self.values.get((container, name)))

    def put_json(self, container, name, value):
        self.values[container, name] = copy.deepcopy(value)


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        from giandoria.config import DemoConfig
        self.engine = BusinessEngine(DemoConfig.load(ROOT / "config" / "demo.json"),
                                     BusinessConfig.load(ROOT / "config" / "business.json"),
                                     "business-demo-001", RehearsalManager())
        for _ in range(72):
            self.engine.step()
        self.control = {
            "version": 1, "run_id": "business-demo-001",
            "changes": [{"id": "growth", "tick": 96, "reason": "Third-party channel expansion.",
                         "demand_percent": {"modern_trade": 180}, "line_capacity_kg": {}}],
        }

    def test_rehearsals_leave_checkpoint_untouched(self):
        snapshot = self.engine.snapshot()
        before = json.dumps(snapshot, sort_keys=True)
        first = engine_from(snapshot)
        first.set_scenario(self.control["changes"])
        rows = rehearse(first, 168)
        second = engine_from(snapshot)
        second.set_scenario(self.control["changes"])
        self.assertEqual(rows, rehearse(second, 168))
        self.assertEqual(before, json.dumps(snapshot, sort_keys=True))
        self.assertEqual(len(rows), 7)
        self.assertNotIn("market", rows[-1]["observations"])
        for invalid in (0, 17545, True):
            with self.assertRaises(ValueError):
                rehearse(first, invalid)

    @patch("giandoria.business_scenario.RuntimeLease")
    def test_staging_requires_stopped_lab_and_preserves_saved_plan(self, lease):
        store = Store(self.engine.snapshot())
        self.assertEqual(stage(store, self.control), 72)
        self.assertEqual(store.values["lab-state", "business-scenario.json"], self.control)
        changed = copy.deepcopy(self.control)
        changed["changes"][0]["demand_percent"]["modern_trade"] = 200
        with self.assertRaisesRegex(ValueError, "append-only"):
            stage(store, changed)
        store.values["lab-state", "active-session.json"]["state"] = "Running"
        with self.assertRaisesRegex(RuntimeError, "Stop and verify"):
            stage(store, self.control)
        self.assertEqual(store.values["snapshots", "business-demo-001/current.json"], self.engine.snapshot())

    def test_control_rejects_other_run_and_boolean_version(self):
        for field, value in (("version", True), ("run_id", "another-run")):
            control = {**self.control, field: value}
            with self.assertRaises(ValueError):
                validate_control(control, "business-demo-001")


if __name__ == "__main__":
    unittest.main()
