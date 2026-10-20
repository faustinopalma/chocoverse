import copy
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from giandoria.business import BusinessConfig, BusinessEngine, OperationalReports
from giandoria.cloud_io import RuntimeLease
from giandoria.config import DemoConfig
from giandoria.managers import DecisionUnavailable, StrategicManager
from giandoria.runtime import CheckpointRunner, execution_target, main, run_loop, stream_row

ROOT = Path(__file__).resolve().parents[1]


class MemoryStore:
    def __init__(self):
        self.values = {}

    def get_json(self, container, name):
        return copy.deepcopy(self.values.get((container, name)))

    def put_json(self, container, name, value):
        self.values[container, name] = copy.deepcopy(value)


class FakeModel:
    deployment, version = "fake-model", "test-version"

    def __init__(self, answer=None, error=None):
        self.calls = 0
        self.answer = answer or {"option": "resilient", "reason": "Observed service requires more buffer."}
        self.error = error

    def choose(self, report, max_output_tokens):
        self.calls += 1
        if self.error:
            raise self.error
        return self.answer, {"prompt_tokens": 400, "completion_tokens": 100, "total_tokens": 500}


class FakePublisher:
    def __init__(self):
        self.events = []
        self.fail = False

    def send(self, events):
        self.events.extend(copy.deepcopy(events))
        if self.fail:
            raise RuntimeError("Injected uncertain delivery.")


class ManagerRuntimeTests(unittest.TestCase):
    def test_existing_lock_allows_acquisition_but_not_other_conflicts(self):
        for status, code in ((409, "BlobAlreadyExists"), (412, "ConditionNotMet")):
            store = Mock()
            store.request.side_effect = [Mock(status_code=status, headers={"x-ms-error-code": code}), Mock(), Mock()]
            with RuntimeLease(store):
                pass
            self.assertEqual(store.request.call_count, 3)
        store = Mock()
        store.request.return_value = Mock(status_code=409, headers={"x-ms-error-code": "LeaseAlreadyPresent"})
        with self.assertRaisesRegex(RuntimeError, "Unexpected conflict"):
            with RuntimeLease(store):
                pass
        self.assertEqual(store.request.call_count, 1)

    def test_calendar_collection_stops_at_exact_target(self):
        self.assertEqual(execution_target(17000, 744, 17544), 17544)
        self.assertEqual(execution_target(17544, 744, 17544), 17544)
        self.assertEqual(execution_target(24, 744, 17544), 768)
        for hours, target in ((745, 17544), (744, 17545), (0, None)):
            with self.assertRaises(ValueError):
                execution_target(0, hours, target)

    def engine(self, store, model):
        manager = StrategicManager(store, model, "runtime-test")
        return BusinessEngine(DemoConfig.load(ROOT / "config" / "demo.json"),
                              BusinessConfig.load(ROOT / "config" / "business.json"), "runtime-test", manager)

    def test_recorded_decisions_replay_without_calls(self):
        store, model = MemoryStore(), FakeModel()
        engine = self.engine(store, model)
        report = OperationalReports(engine.modules).briefing("sop_chair", 168)
        manager = StrategicManager(store, model, "runtime-test")
        first = manager.decide("review-1", report)
        second = StrategicManager(store, FakeModel(error=AssertionError("Must not call")), "runtime-test").decide("review-1", report)
        self.assertEqual(first, second)
        self.assertEqual(first["mode"], "llm")
        self.assertEqual(model.calls, 1)
        with self.assertRaisesRegex(ValueError, "differs"):
            manager.decide("review-1", {"different": True})

    def test_session_model_budgets_survive_restart_without_resetting_history(self):
        store, model = MemoryStore(), FakeModel()
        StrategicManager(store, model, "sessions", max_calls=1, budget_scope="first").decide("one", {})
        resumed = StrategicManager(store, model, "sessions", max_calls=1, budget_scope="first")
        self.assertEqual(resumed.decide("one", {})["mode"], "llm")
        self.assertEqual(resumed.decide("two", {})["reason"], "RequestLimit")
        next_session = StrategicManager(store, model, "sessions", max_calls=1, budget_scope="second")
        self.assertEqual(next_session.decide("three", {})["mode"], "llm")
        ledger = store.get_json("decisions", "sessions/ledger.json")
        self.assertEqual(ledger["calls"], 2)
        self.assertEqual(len(ledger["records"]), 3)
        self.assertEqual(ledger["session_budgets"]["first"]["calls"], 1)
        self.assertEqual(model.calls, 2)

    def test_continuous_mode_paces_past_collection_horizon_and_stops_promptly(self):
        store, model, publisher = MemoryStore(), FakeModel(), FakePublisher()
        engine = self.engine(store, model)
        engine.tick = 17544
        runner, lease = CheckpointRunner(engine, store, publisher), Mock(spec=RuntimeLease)
        store.put_json("lab-state", "active-session.json", {
            "id": "live", "desired": "Running", "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })
        clock = [0.0]
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        fingerprint = engine.fingerprint
        with patch("giandoria.runtime.time.monotonic", side_effect=lambda: clock[0]):
            run_loop(runner, lease, store, stop, "live", 12, speed=3600, continuous=True, hours=744, target=17544)
        self.assertEqual(engine.tick, 17556)
        self.assertEqual(engine.fingerprint, fingerprint)
        self.assertTrue(stop.wait.called)
        self.assertTrue(all(e["speed"] == 3600 for e in publisher.events))
        pulse = next(e for e in publisher.events if e["type"] == "world.business.observed")
        self.assertNotIn("market", pulse["data"]["observations"])
        self.assertEqual(store.get_json("snapshots", "runtime-test/current.json")["tick"], engine.tick)

    def test_slow_live_clock_publishes_observations_without_fast_forwarding(self):
        store, publisher = MemoryStore(), FakePublisher()
        engine = self.engine(store, FakeModel())
        store.put_json("lab-state", "active-session.json", {
            "id": "slow", "desired": "Running", "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })
        clock = [0.0]
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        with patch("giandoria.runtime.time.monotonic", side_effect=lambda: clock[0]):
            run_loop(CheckpointRunner(engine, store, publisher), Mock(spec=RuntimeLease), store, stop, "slow", 12,
                     speed=1, continuous=True, hours=744, target=17544)
        self.assertEqual(engine.tick, 1)
        self.assertGreaterEqual(sum(e["type"] == "world.business.observed" for e in publisher.events), 3)

    def test_continuous_loop_rechecks_stop_session_before_next_tick(self):
        store, publisher = MemoryStore(), FakePublisher()
        engine = self.engine(store, FakeModel())
        store.put_json("lab-state", "active-session.json", {
            "id": "live", "desired": "Stopped", "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        })
        run_loop(CheckpointRunner(engine, store, publisher), Mock(), store, threading.Event(), "live",
                 float("inf"), speed=8760, continuous=True, hours=744, target=17544)
        self.assertEqual(engine.tick, 0)
        for speed in (0, 8761, True, 1.5):
            with self.assertRaises(ValueError):
                run_loop(CheckpointRunner(engine, store, publisher), Mock(), store, threading.Event(), "live",
                         0, speed=speed, continuous=True, hours=744, target=17544)

    def test_speed_change_resumes_checkpoint_without_rewriting_archives(self):
        store, model, publisher = MemoryStore(), FakeModel(), FakePublisher()
        engine = self.engine(store, model)
        for session, speed, expected_ticks in (("first", 3600, 2), ("second", 720, 3)):
            engine = self.engine(store, model)
            runner = CheckpointRunner(engine, store, publisher)
            runner.restore()
            before = {key: copy.deepcopy(value) for key, value in store.values.items() if key[0] == "outbox"}
            store.put_json("lab-state", "active-session.json", {
                "id": session, "desired": "Running", "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            })
            clock = [0.0]
            stop = Mock()
            stop.is_set.return_value = False
            stop.wait.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
            with patch("giandoria.runtime.time.monotonic", side_effect=lambda: clock[0]):
                run_loop(runner, Mock(spec=RuntimeLease), store, stop, session, 2, speed=speed,
                         continuous=True, hours=744, target=17544)
            self.assertEqual(engine.tick, expected_ticks)
            self.assertTrue(all(store.values[key] == value for key, value in before.items()))
        self.assertEqual(len({event["id"] for event in publisher.events}), len(publisher.events))
        self.assertEqual(publisher.events[-1]["speed"], 720)

    def test_expired_or_superseded_session_cannot_advance_business(self):
        for session_id, expiry in (("other", datetime.now(UTC) + timedelta(minutes=1)),
                                   ("live", datetime.now(UTC) - timedelta(seconds=1))):
            with self.subTest(session_id=session_id):
                store, publisher = MemoryStore(), FakePublisher()
                engine = self.engine(store, FakeModel())
                store.put_json("lab-state", "active-session.json", {
                    "id": session_id, "desired": "Running", "expiresAt": expiry.isoformat(),
                })
                run_loop(CheckpointRunner(engine, store, publisher), Mock(spec=RuntimeLease), store,
                         threading.Event(), "live", float("inf"), speed=8760,
                         continuous=True, hours=744, target=17544)
                self.assertEqual(engine.tick, 0)

    def test_extended_worker_generation_checkpoints_without_advancing(self):
        store, publisher = MemoryStore(), FakePublisher()
        engine = self.engine(store, FakeModel())
        engine.step()
        original_tick, original_ids = engine.tick, [event["id"] for event in engine.outbox]
        store.put_json("lab-state", "active-session.json", {
            "id": "same-session", "desired": "Running", "workerGeneration": "replacement",
            "expiresAt": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        })
        run_loop(CheckpointRunner(engine, store, publisher), Mock(spec=RuntimeLease), store,
                 threading.Event(), "same-session", float("inf"), speed=8760, continuous=True,
                 hours=744, target=17544, generation="original")
        self.assertEqual(engine.tick, original_tick)
        self.assertFalse(engine.outbox)
        snapshot = store.get_json("snapshots", "runtime-test/current.json")
        self.assertEqual(snapshot["tick"], original_tick)
        archived_ids = {event["id"] for (container, _), value in store.values.items() if container == "outbox"
                        for event in value["events"]}
        self.assertTrue(set(original_ids).issubset(archived_ids))

    def test_cloud_entrypoint_allows_full_four_hour_session_not_old_two_hour_limit(self):
        session = {"id": "four-hours", "desired": "Running", "state": "Running", "mode": "Continuous",
                   "workerGeneration": "worker", "speed": 8760,
                   "expiresAt": (datetime.now(UTC) + timedelta(hours=4)).isoformat()}
        environment = {"GIANDORIA_STATE_ACCOUNT": "stgiandoriatest",
                       "GIANDORIA_FOUNDRY_ENDPOINT": "https://test.openai.azure.com",
                       "GIANDORIA_STREAM_NAMESPACE": "test.servicebus.windows.net",
                       "GIANDORIA_STREAM_HUB": "test", "AZURE_CLIENT_ID": "test",
                       "GIANDORIA_MODEL": "test", "GIANDORIA_MODEL_VERSION": "test"}
        with patch.dict("os.environ", environment), patch(
            "giandoria.runtime.ManagedIdentityCredential",
        ), patch("giandoria.runtime.RecordedHttp") as http, patch(
            "giandoria.runtime.BlobStore",
        ) as store, patch("giandoria.runtime.EventstreamPublisher"), patch(
            "giandoria.runtime.RuntimeLease",
        ), patch("giandoria.runtime.StrategicManager"), patch(
            "giandoria.runtime.BusinessEngine",
        ) as engine, patch("giandoria.runtime.CheckpointRunner"), patch(
            "giandoria.runtime.run_loop",
        ) as loop, patch("giandoria.runtime.time.monotonic", return_value=1000):
            http.return_value._audit_lock = threading.Lock()
            http.return_value.audit = []
            engine.return_value.summary.return_value = {"tick": 1}
            store.return_value.get_json.return_value = session
            main()
        deadline = loop.call_args.args[5]
        self.assertGreater(deadline - 1000, 4 * 3600 - 35)
        self.assertLessEqual(deadline - 1000, 4 * 3600 - 30)
        self.assertEqual(loop.call_args.kwargs["generation"], "worker")

    def test_call_and_token_limits_fail_explicitly_to_rules(self):
        store, model = MemoryStore(), FakeModel()
        manager = StrategicManager(store, model, "limited", max_calls=1)
        manager.decide("one", {})
        result = manager.decide("two", {})
        self.assertEqual(model.calls, 1)
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["reason"], "RequestLimit")
        manager = StrategicManager(MemoryStore(), model, "tokens", max_reserved_tokens=1)
        self.assertEqual(manager.decide("one", {})["reason"], "TokenReservationLimit")
        self.assertEqual(model.calls, 1)

    def test_invalid_or_unavailable_model_is_logged_fallback(self):
        for model in (FakeModel(answer={"option": "unsafe", "reason": "Do anything"}),
                      FakeModel(error=DecisionUnavailable("ModelHttp429"))):
            manager = StrategicManager(MemoryStore(), model, "fallback")
            result = manager.decide("one", {})
            self.assertEqual(result["mode"], "fallback")
            self.assertEqual(result["option"], "balanced")

    def test_interrupted_reserved_call_is_not_reissued(self):
        store, model = MemoryStore(), FakeModel(error=KeyboardInterrupt())
        manager = StrategicManager(store, model, "interrupted")
        with self.assertRaises(KeyboardInterrupt):
            manager.decide("one", {})
        result = StrategicManager(store, FakeModel(error=AssertionError("Must not call")), "interrupted").decide("one", {})
        self.assertEqual(result["reason"], "InterruptedAttempt")

    def test_outbox_survives_uncertain_delivery_and_replays_same_ids(self):
        store, model, publisher = MemoryStore(), FakeModel(), FakePublisher()
        engine = self.engine(store, model)
        for _ in range(48):
            engine.step()
        runner = CheckpointRunner(engine, store, publisher)
        publisher.fail = True
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            runner.flush()
        first_ids = [e["id"] for e in publisher.events]
        restored = self.engine(store, model)
        publisher.fail = False
        CheckpointRunner(restored, store, publisher).restore()
        self.assertEqual(first_ids, [e["id"] for e in publisher.events[len(first_ids):]])
        self.assertEqual(restored.tick, 48)
        self.assertFalse(restored.outbox)
        self.assertTrue(all(e["visibility"] == "enterprise" for e in publisher.events))
        archives = [v for (container, _), v in store.values.items() if container == "outbox"]
        self.assertTrue(any(e["visibility"] == "truth" for e in archives[0]["events"]))

    def test_stream_mapping_preserves_raw_envelope_and_blocks_truth(self):
        store, model = MemoryStore(), FakeModel()
        engine = self.engine(store, model)
        engine.step()
        truth = next(e for e in engine.outbox if e["visibility"] == "truth")
        with self.assertRaises(PermissionError):
            stream_row(truth)
        event = next(e for e in engine.outbox if e["visibility"] == "enterprise")
        row = stream_row(event)
        import json
        self.assertEqual(json.loads(row["raw_event"]), event)
        self.assertEqual(row["event"], event)


if __name__ == "__main__":
    unittest.main()
