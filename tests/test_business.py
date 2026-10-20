import json
import unittest
from pathlib import Path

from giandoria.business import BusinessConfig, BusinessEngine, Channels, Factory, Logistics, OperationalReports, OPTIONS
from giandoria.config import DemoConfig

ROOT = Path(__file__).resolve().parents[1]


class RecordedManager:
    def __init__(self):
        self.calls = []

    def decide(self, key, report):
        self.calls.append((key, report))
        return {"option": "resilient", "reason": "Protect observed service and constrained supply.", "mode": "test"}


class BusinessTests(unittest.TestCase):
    def test_two_calendar_years_with_monthly_restarts(self):
        engine = self.make_engine()
        for tick in range(17544):
            engine.step()
            if engine.tick % 24 == 0:
                engine.outbox = []
            if engine.tick % 744 == 0:
                snapshot = engine.snapshot()
                engine = self.make_engine()
                engine.restore(snapshot)
        self.assertEqual(engine.tick, 17544)
        self.assertEqual(engine.summary()["observations"]["planning"]["reviews_applied"], 104)
        engine.assert_invariants()

    def make_engine(self, manager=None):
        return BusinessEngine(
            DemoConfig.load(ROOT / "config" / "demo.json"), BusinessConfig.load(ROOT / "config" / "business.json"),
            "business-test", manager or RecordedManager(),
        )

    def advance(self, engine, hours):
        for _ in range(hours):
            engine.step()

    def normalized(self, events):
        return [{k: v for k, v in e.items() if k != "walltime"} for e in events]

    def test_complete_causal_flow_and_invariants(self):
        manager = RecordedManager()
        engine = self.make_engine(manager)
        self.advance(engine, 24 * 24)
        counts = engine.event_counts
        for kind in (
            "market.purchase.intent", "retail.sellout.recorded", "trade.sellout.recorded",
            "commerce.salesorder.placed", "logistics.shipment.dispatched", "factory.production.started",
            "factory.quality.released", "planning.purchase.placed", "supply.purchase.confirmed",
            "factory.material.received", "finance.cash.settled", "planning.strategy.applied",
        ):
            self.assertGreater(counts.get(kind, 0), 0, kind)
        shipped = {e["data"]["channel"] for e in engine.outbox if e["type"] == "logistics.shipment.dispatched"}
        self.assertEqual(shipped, set(engine.business.channels))
        self.assertEqual(len(manager.calls), 3)
        changes = [e for e in engine.outbox if e["type"] == "planning.strategy.applied"]
        self.assertEqual(changes[0]["data"]["before"], "lean")
        self.assertEqual(changes[0]["data"]["option"], "resilient")
        engine.assert_invariants()
        self.assertEqual(len({e["id"] for e in engine.outbox}), len(engine.outbox))
        self.assertTrue(all(m.deliver_tick > m.sent_tick for m in engine.pending))
        for event in engine.outbox:
            if event["source"] == "/market":
                self.assertEqual(event["visibility"], "truth")
        for event in engine.outbox:
            if event["type"] == "factory.production.started":
                correlation = event["data"]["correlation"]
                released = [e for e in engine.outbox if e["type"] == "factory.quality.released" and e["data"]["correlation"] == correlation]
                if released:
                    self.assertGreaterEqual(released[0]["tick"] - event["tick"], 30)

    def test_snapshot_restart_is_deterministic(self):
        continuous = self.make_engine()
        self.advance(continuous, 240)
        partial = self.make_engine()
        self.advance(partial, 130)
        snapshot = partial.snapshot()
        self.advance(partial, 5)
        restored = self.make_engine()
        restored.restore(snapshot)
        self.advance(restored, 110)
        self.assertEqual(self.normalized(continuous.outbox), self.normalized(restored.outbox))
        self.assertEqual(continuous.summary(), restored.summary())

    def test_truth_cannot_enter_briefing(self):
        engine = self.make_engine()
        self.advance(engine, 25)
        report = OperationalReports(engine.modules).briefing("sop_chair", engine.tick)
        text = json.dumps(report)
        self.assertNotIn("latent", text)
        self.assertNotIn("market", text)
        self.assertNotIn("purchase.intent", text)
        self.assertEqual(set(report["reports"]), {"planning", "logistics", "factory", "finance"})
        with self.assertRaises(PermissionError):
            OperationalReports(engine.modules).briefing("competitor", engine.tick)
        with self.assertRaises(PermissionError):
            engine.modules["market"].observe()

    def test_corrupt_snapshot_or_stock_is_rejected(self):
        engine = self.make_engine()
        snapshot = engine.snapshot()
        snapshot["fingerprint"] = "different"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            engine.restore(snapshot)
        factory = engine.modules["factory"]
        self.assertIsInstance(factory, Factory)
        factory.materials["sugar"] = -1
        with self.assertRaisesRegex(ValueError, "conservation"):
            engine.assert_invariants()

    def test_factory_has_no_free_or_unbounded_production(self):
        engine = self.make_engine()
        self.advance(engine, 100)
        factory = engine.modules["factory"]
        self.assertIsInstance(factory, Factory)
        for material in factory.materials:
            self.assertEqual(factory.initial[material] + factory.received[material] - factory.consumed[material],
                             factory.materials[material])
        for sku, product in engine.business.products.items():
            self.assertGreaterEqual(factory.consumed[f"pack:{sku}"], factory.produced[sku])
        for line, use in factory.line_use.items():
            self.assertLessEqual(use, engine.business.lines[line])

    def test_sim_time_not_wall_time_drives_season(self):
        first, second = self.make_engine(), self.make_engine()
        self.advance(first, 72)
        self.advance(second, 72)
        self.assertEqual(self.normalized(first.outbox), self.normalized(second.outbox))


if __name__ == "__main__":
    unittest.main()
