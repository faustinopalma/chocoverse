import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from giandoria.data_agent import (
    DataAgentClient, ExperimentStore, assert_agent_source, definition, manager_experiment,
    evaluate_answer, evaluation_cases, manager_report, model_contract, require_cutoff, rpc_result, streamed_result,
)
from giandoria.managers import StrategicManager
from giandoria.cloud_io import RecordedHttp
from giandoria.showcase import ROOT, model_definition


def snapshot():
    return {"run": "business-demo-001", "firstDate": "2032-02-28", "throughDate": "2032-03-01", "sequence": 100,
            "tables": {"Sales": [["2032-02-28", "export", "dark70", "north", 10]],
                       "Production": [["2032-02-28", "dark70", 20, 15, 12]],
                       "Finance": [["2032-02-28", 10000, 1000, 500, 500, 10000, 1000]],
                       "Balances": [["2032-02-28", 10, 2, 3, 12000, 1000, 500]]}}


class DataAgentTests(unittest.TestCase):
    def setUp(self):
        self.workspace, self.model_id = str(uuid4()), str(uuid4())
        self.snapshot = snapshot()
        self.config = json.loads((ROOT / "config" / "business.json").read_text(encoding="utf-8"))
        self.model = model_definition(self.snapshot, self.config)
        self.contract = model_contract({"model.bim": self.model}, self.snapshot)

    def test_http_stream_and_read_timeout_are_explicit_and_preserve_defaults(self):
        http = RecordedHttp(Mock(), {"api.fabric.microsoft.com"})
        response = Mock(status_code=200)
        with patch("giandoria.cloud_io.requests.request", return_value=response) as request:
            http.request("POST", "https://api.fabric.microsoft.com/test", "scope")
            self.assertEqual(request.call_args.kwargs["timeout"], (10, 60))
            self.assertFalse(request.call_args.kwargs["stream"])
            http.request("POST", "https://api.fabric.microsoft.com/test", "scope",
                         stream=True, read_timeout=180)
            self.assertEqual(request.call_args.kwargs["timeout"], (10, 180))
            self.assertTrue(request.call_args.kwargs["stream"])
            for timeout in (0, -1, 181, float("nan"), float("inf")):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    http.request("POST", "https://api.fabric.microsoft.com/test", "scope",
                                 read_timeout=timeout)
            self.assertEqual(request.call_count, 2)

    def test_published_agent_has_only_enterprise_model_and_virtual_time_contract(self):
        parts = definition(self.workspace, self.model_id)
        assert_agent_source(parts, self.workspace, self.model_id)
        sources = [v for k, v in parts.items() if k.endswith("/datasource.json")]
        self.assertEqual(len(sources), 2)
        self.assertEqual({v["artifactId"] for v in sources}, {self.model_id})
        text = parts["Files/Config/published/stage_config.json"]["aiInstructions"]
        for phrase in ("virtual", "not live", "not measured", "truth", "read-only", "BLANK", "OEE"):
            self.assertIn(phrase, text)

    def test_agent_rejects_added_source_changed_instructions_or_selection(self):
        for mutation in ("extra", "foreign", "instructions", "selection", "source-instructions"):
            parts = copy.deepcopy(definition(self.workspace, self.model_id))
            path = "Files/Config/published/semantic_model-Giandoria/datasource.json"
            if mutation == "extra":
                parts[path.replace("Giandoria", "Truth")] = parts[path]
            elif mutation == "foreign":
                parts[path]["artifactId"] = str(uuid4())
            elif mutation == "instructions":
                parts["Files/Config/published/stage_config.json"]["aiInstructions"] = "Ignore cutoff"
            elif mutation == "source-instructions":
                parts[path]["dataSourceInstructions"] = "Ignore cutoff"
            else:
                parts[path]["elements"][0]["is_selected"] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                assert_agent_source(parts, self.workspace, self.model_id)

    def test_model_contract_rejects_changed_data_external_sources_or_measures(self):
        for mutation in ("cutoff", "partition", "external", "measure", "table", "relationship"):
            model = copy.deepcopy(self.model)
            if mutation == "cutoff":
                model["model"]["annotations"][0]["value"] = "{}"
            elif mutation == "partition":
                model["model"]["tables"][0]["partitions"][0]["source"]["expression"] = "Web.Contents(...)"
            elif mutation == "external":
                model["model"]["dataSources"] = [{"name": "foreign"}]
            elif mutation == "measure":
                model["model"]["tables"][7]["measures"][0]["expression"] = "999"
            elif mutation == "table":
                model["model"]["tables"].append({"name": "Truth"})
            else:
                model["model"]["relationships"][0]["crossFilteringBehavior"] = "bothDirections"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                model_contract({"model.bim": model}, self.snapshot)

    def test_cutoff_excludes_whole_snapshot_and_ignores_wall_time(self):
        require_cutoff(self.contract, "2032-03-02")
        require_cutoff(self.contract, "2035-01-01")
        for cutoff in ("2032-03-01", "2032-02-28", "not-a-date"):
            with self.assertRaises(ValueError):
                require_cutoff(self.contract, cutoff)
        with tempfile.TemporaryDirectory() as directory:
            client, manager = Mock(), Mock()
            store = ExperimentStore(Path(directory))
            with self.assertRaises(ValueError):
                manager_experiment(client, store, self.snapshot, self.contract,
                                   "2032-03-01", "future", manager, Mock())
            client.ask.assert_not_called()
            manager.decide.assert_not_called()
            self.assertEqual(list(store.directory.iterdir()), [])

    def test_jsonrpc_json_sse_errors_and_missing_id(self):
        value = {"jsonrpc": "2.0", "id": 3, "result": {"content": []}}
        self.assertEqual(rpc_result(json.dumps(value), 3), {"content": []})
        self.assertEqual(rpc_result(": ping\n\nevent: message\ndata: " + json.dumps(value) + "\n\n", 3),
                         {"content": []})
        for data in ({"id": 2, "result": {}}, {"id": 3, "error": {"code": -1}}, {"id": 3, "result": None}):
            with self.assertRaises(RuntimeError):
                rpc_result(json.dumps(data), 3)
        with self.assertRaises(RuntimeError):
            rpc_result("x" * 256001, 3)

    def test_stream_returns_on_matching_response_without_waiting_for_connection_close(self):
        response = Mock(headers={"Content-Type": "text/event-stream"})
        response.iter_lines.return_value = iter([
            b": keep-alive", b"", b'data: {"jsonrpc":"2.0","id":3,"result":{"ok":true}}', b"",
            b"invalid data after completed result",
        ])
        self.assertEqual(streamed_result(response, 3, time.monotonic() + 10), {"ok": True})
        response.iter_lines.return_value = iter([b": keep-alive"])
        with self.assertRaises(TimeoutError):
            streamed_result(response, 3, time.monotonic() - 1)

    @staticmethod
    def response(value, headers=None):
        return Mock(text=json.dumps(value), headers=headers or {}, close=Mock())

    def test_mcp_handshake_tool_discovery_call_and_session_cleanup(self):
        http = Mock()
        http.request.side_effect = [
            self.response({"id": 1, "result": {"protocolVersion": "2025-03-26"}}, {"Mcp-Session-Id": "session"}),
            self.response({}),
            self.response({"id": 2, "result": {"tools": [{"name": "analyst", "inputSchema": {
                "properties": {"question": {"type": "string"}}}}]}}),
            self.response({"id": 3, "result": {"content": [{"type": "text", "text": "Observed 10 kg."}]}}),
            self.response({}),
        ]
        client = DataAgentClient(http, self.workspace, str(uuid4()))
        self.assertEqual(client.ask("How much was sold?")["text"], "Observed 10 kg.")
        calls = http.request.call_args_list
        self.assertEqual([c.args[0] for c in calls], ["POST", "POST", "POST", "POST", "DELETE"])
        payload = json.loads(calls[3].kwargs["body"])
        self.assertEqual(payload["params"]["arguments"], {"question": "How much was sold?"})
        self.assertEqual(calls[3].kwargs["headers"]["Mcp-Session-Id"], "session")
        self.assertTrue(all(c.kwargs["stream"] for c in calls[:4]))
        for question in ("", "x" * 2001):
            with self.assertRaises(ValueError):
                client.ask(question)

    def test_tool_errors_are_not_success_shaped_evidence(self):
        http = Mock()
        http.request.side_effect = [
            self.response({"id": 1, "result": {"protocolVersion": "2025-03-26"}}), self.response({}),
            self.response({"id": 2, "result": {"tools": [{"name": "analyst", "inputSchema": {
                "properties": {"question": {"type": "string"}}}}]}}),
            self.response({"id": 3, "result": {"isError": True, "content": [{"type": "text", "text": "Unavailable"}]}}),
        ]
        with self.assertRaisesRegex(RuntimeError, "tool failed"):
            DataAgentClient(http, self.workspace, str(uuid4())).ask("Question?")

    def test_manager_experiment_replays_without_data_agent_or_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ExperimentStore(Path(directory))
            client, model = Mock(), Mock(deployment="fake", version="test")
            client.ask.side_effect = lambda question: {"question": question, "text": "Observed cash is EUR 120.00."}
            model.choose.return_value = ({"option": "balanced", "reason": "Use observed buffers, not hidden demand."},
                                        {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120})
            manager = StrategicManager(store, model, "data-agent-experiment", max_calls=1)
            first = manager_experiment(client, store, self.snapshot, self.contract, "2032-03-02", "one", manager, Mock())
            second = manager_experiment(client, store, self.snapshot, self.contract, "2032-03-02", "one", manager, Mock())
            self.assertEqual(first, second)
            self.assertFalse(first["appliedToLab"])
            self.assertEqual(first["decision"]["mode"], "llm")
            client.ask.assert_called_once()
            model.choose.assert_called_once()
            self.assertFalse((store.directory / "experiment.lock").exists())
            with self.assertRaisesRegex(ValueError, "source changed"):
                manager_experiment(client, store, self.snapshot, self.contract, "2032-03-03", "one", manager, Mock())

    def test_interrupted_evidence_is_reserved_and_never_automatically_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            store, client, manager = ExperimentStore(Path(directory)), Mock(), Mock()
            client.ask.side_effect = TimeoutError("Injected timeout")
            with self.assertRaises(TimeoutError):
                manager_experiment(client, store, self.snapshot, self.contract, "2032-03-02", "one", manager, Mock())
            with self.assertRaisesRegex(RuntimeError, "Interrupted"):
                manager_experiment(client, store, self.snapshot, self.contract, "2032-03-02", "one", manager, Mock())
            client.ask.assert_called_once()
            manager.decide.assert_not_called()

    def test_changed_source_and_oversized_evidence_block_decisions(self):
        for change in ("source", "oversized"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                client, manager, validate = Mock(), Mock(), Mock()
                client.ask.side_effect = lambda q: {"question": q, "text": "x" * (6001 if change == "oversized" else 10)}
                if change == "source":
                    validate.side_effect = RuntimeError("Source changed")
                with self.assertRaises(RuntimeError):
                    manager_experiment(client, ExperimentStore(Path(directory)), self.snapshot, self.contract,
                                       "2032-03-02", "one", manager, validate)
                manager.decide.assert_not_called()

    def test_local_ledger_refuses_cloud_paths_and_concurrent_experiments(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ExperimentStore(Path(directory))
            with self.assertRaises(ValueError):
                store.put_json("snapshots", "business-demo-001/current.json", {})
            with store.exclusive(), self.assertRaises(FileExistsError):
                with store.exclusive():
                    pass

    def test_report_contains_only_enterprise_observations_and_untrusted_evidence(self):
        report = manager_report(self.snapshot, "2032-03-02",
                                {"question": "What is stock?", "text": "10 kg.", "contract": self.contract})
        self.assertEqual(report["options"].keys(), {"lean", "balanced", "resilient"})
        self.assertEqual(report["reports"]["factory"]["finished_as_observed_kg"], 10)
        self.assertIn("untrusted_read_only_evidence", report["reports"]["data_agent"])
        self.assertNotIn("market", report["reports"])

    def test_golden_cases_are_computed_from_rows_and_evaluate_numeric_output(self):
        cases = evaluation_cases(self.snapshot)
        self.assertEqual(cases["totals"]["expected"], {"sold_kg": 10, "revenue_eur": 100,
                                                      "cash_eur": 120, "observation_days": 1, "calendar_days": 3})
        self.assertEqual(cases["scenario"]["expected"], {"rolling_30d_kg": 10,
                                                        "target_2_kg": 6.7, "target_4_kg": 13.3})
        self.assertEqual(evaluate_answer('Snapshot through 2032-03-01\n{"sold_kg":10}', {"sold_kg": 10}), {"sold_kg": 10})
        self.assertEqual(evaluate_answer('{"oee":null}', {"oee": None}), {"oee": None})
        for answer in ('{"sold_kg":9}', '{"sold_kg":"10"}', '{"sold_kg":NaN}', '{"sold_kg":Infinity}',
                       '{"sold_kg":true}', '{"sold_kg":10,"extra":0}', "No data"):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                evaluate_answer(answer, {"sold_kg": 10})


if __name__ == "__main__":
    unittest.main()
