import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from giandoria.agent_comparison import Study, briefing, cases, execute_query, query_cases, schema_context, score


def snapshot():
    return {"firstDate": "2033-08-01", "throughDate": "2034-09-03",
            "tables": {
                "Sales": [["2033-08-01", "campaigns", "dark70", "centre", 7],
                          ["2034-08-05", "campaigns", "dark70", "centre", 11],
                          ["2034-08-05", "export", "dark70", "north", 23]],
                "Finance": [["2034-08-05", 10000]],
                "Balances": [["2034-08-05", 0, 37, 0, 10000]],
            }}


class ComparisonTests(unittest.TestCase):
    def test_rubric_uses_virtual_complete_month_and_exact_slice(self):
        suite = cases(snapshot())
        self.assertEqual(list(suite), ["calendar", "slice", "scenario", "boundaries"])
        self.assertEqual(suite["slice"]["expected"], {"slice_sold_kg": 11, "sold_kg": 34})
        self.assertEqual(suite["calendar"]["expected"], {"sold_kg": 34, "sold_py_kg": 7, "ytd_kg": 34})
        self.assertIn("2034-08-01 through 2034-08-31", suite["slice"]["question"])

    def test_briefing_does_not_leak_granular_answers(self):
        overview = json.loads(briefing(snapshot()))
        self.assertEqual(overview["lifetime_sold_kg"], 41)
        self.assertNotIn("expected", overview)
        self.assertNotIn("slice_sold_kg", overview)
        self.assertNotIn("sold_py_kg", overview)

    def test_numeric_scoring_rejects_guesses_strings_booleans_nonfinite_and_wrong_keys(self):
        answer = {"metrics": {"kg": 11}, "virtual_cutoff": "2034-09-03", "data_status": "snapshot"}
        self.assertTrue(score(answer, {"kg": 11}, "2034-09-03")["passed"])
        for wrong in (None, 12, True, "11", float("nan"), float("inf")):
            actual = copy.deepcopy(answer)
            actual["metrics"]["kg"] = wrong
            self.assertFalse(score(actual, {"kg": 11}, "2034-09-03")["passed"])
        self.assertFalse(score(answer, {"other": 11}, "2034-09-03")["passed"])
        self.assertFalse(score(answer, {"kg": 11}, "2034-09-04")["passed"])
        answer["metrics"]["kg"] = None
        self.assertTrue(score(answer, {"kg": None}, "2034-09-03")["passed"])

    def test_limits_are_reserved_before_calls_and_names_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial"
            study = Study(path, Mock(), {}, {})
            for _ in range(4):
                study.reserve("dataAgentCalls", 4)
            with self.assertRaises(RuntimeError):
                study.reserve("dataAgentCalls", 4)
            saved = json.loads((path / "result.json").read_text())
            self.assertEqual(saved["dataAgentCalls"], 4)
            with self.assertRaises(FileExistsError):
                Study(path, Mock(), {}, {})

    def test_checkpoint_retries_only_transient_windows_replace_locks_without_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            http = Mock()
            study = Study(Path(directory) / "trial", http, {}, {})
            locked = PermissionError("Observed Windows destination lock")
            locked.winerror = 5
            with patch.object(Path, "replace", side_effect=[locked, None]) as replace, patch(
                    "giandoria.agent_comparison.time.sleep"):
                study.save()
                self.assertEqual(replace.call_count, 2)
            http.request.assert_not_called()
            http.record.assert_called_once_with({"operation": "comparison.checkpoint", "status": "Retrying",
                                                  "winerror": 5, "attempt": 1})
            with patch.object(Path, "replace", side_effect=PermissionError("Permanent denial")) as replace:
                with self.assertRaises(PermissionError):
                    study.save()
                replace.assert_called_once()
            with patch.object(Path, "replace", side_effect=locked) as replace, patch(
                    "giandoria.agent_comparison.time.sleep"):
                with self.assertRaises(PermissionError):
                    study.save()
                self.assertEqual(replace.call_count, 5)

    def test_delegation_is_real_tool_call_and_control_uses_same_evidence_not_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            study = Study(Path(directory) / "trial", Mock(), {},
                          {"briefing": "overview", "contract": {"throughDate": "2034-09-03"}})
            final = {"content": json.dumps({"metrics": {"kg": 11}, "virtual_cutoff": "2034-09-03",
                                            "data_status": "snapshot"})}
            request = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "ask_fabric_data_agent", "arguments": '{"question":"measure kg"}'},
            }]}
            study.complete = Mock(side_effect=[final, request, final, final])
            client = Mock()
            client.ask.return_value = {"text": "Actual specialist evidence"}
            study.run_case("example", {"question": "How much?", "expected": {"kg": 11}}, client)
            client.ask.assert_called_once_with("measure kg")
            calls = study.complete.call_args_list
            self.assertEqual(calls[2].args[0][-1]["content"], "Actual specialist evidence")
            self.assertIn("Actual specialist evidence", calls[3].args[0][-1]["content"])
            self.assertNotIn('"kg": 11', calls[3].args[0][-1]["content"])

    def test_non_delegating_generalist_is_retained_not_forced_or_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            study = Study(Path(directory) / "trial", Mock(), {},
                          {"briefing": "", "contract": {"throughDate": "2034-09-03"}})
            answer = {"content": '{"metrics":{"kg":null},"virtual_cutoff":"2034-09-03","data_status":"snapshot"}'}
            study.complete = Mock(return_value=answer)
            client = Mock()
            study.run_case("example", {"question": "How much?", "expected": {"kg": 11}}, client)
            client.ask.assert_not_called()
            self.assertFalse(study.record["attempts"][0]["arms"]["delegated"]["score"]["passed"])

    def test_oversized_input_rejected_before_model_reservation_or_http(self):
        with tempfile.TemporaryDirectory() as directory:
            http = Mock()
            study = Study(Path(directory) / "trial", http, {"deployment": "test"}, {})
            with self.assertRaises(ValueError):
                study.complete([{"role": "user", "content": "x" * 32_000}], ["kg"])
            http.request.assert_not_called()
            self.assertEqual(study.record["modelCalls"], 0)

    def test_failed_tool_retains_direct_answer_request_and_billable_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial"
            study = Study(path, Mock(), {},
                          {"briefing": "", "contract": {"throughDate": "2034-09-03"}})
            direct = {"content": '{"metrics":{"kg":null},"virtual_cutoff":"2034-09-03","data_status":"snapshot"}'}
            request = {"tool_calls": [{
                "id": "call-1", "function": {"name": "ask_fabric_data_agent", "arguments": '{"question":"kg?"}'},
            }]}
            study.complete = Mock(side_effect=[direct, request])
            client = Mock()
            client.ask.side_effect = TimeoutError("Observed slow analytical request")
            with self.assertRaises(TimeoutError):
                study.run_case("example", {"question": "How much?", "expected": {"kg": 11}}, client)
            saved = json.loads((path / "result.json").read_text())
            self.assertEqual(saved["dataAgentCalls"], 1)
            self.assertEqual(saved["attempts"][0]["delegationRequest"], request)
            self.assertFalse(saved["attempts"][0]["arms"]["direct"]["score"]["passed"])
            client.ask.assert_called_once()

    def test_incomplete_model_output_is_retained_and_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trial"
            http = Mock()
            raw = {"choices": [{"finish_reason": "length", "message": {"content": ""}}]}
            http.request.return_value.json.return_value = raw
            study = Study(path, http, {"deployment": "test", "endpoint": "https://test.openai.azure.com"}, {})
            with self.assertRaises(RuntimeError):
                study.complete([{"role": "user", "content": "question"}], ["kg"])
            saved = json.loads((path / "result.json").read_text())
            self.assertEqual(saved["modelResponses"], [raw])
            self.assertEqual(saved["modelRequests"][0]["messages"], [{"role": "user", "content": "question"}])
            self.assertEqual(saved["modelCalls"], 1)
            http.request.assert_called_once()
            http.request.return_value.close.assert_called_once()

    def test_query_oracle_respects_grains_and_missing_observations(self):
        suite = query_cases(snapshot())
        self.assertEqual(suite["cash_close"]["expected"],
                         {"cash_eur": 100, "observation_days": 1, "calendar_days": 31})
        self.assertEqual(suite["cross_grain"]["expected"],
                         {"sold_kg": 11, "released_kg": None, "cash_eur": None})
        self.assertEqual(suite["policy_multiselect"]["expected"]["cover_days"], 3)
        self.assertEqual(suite["missing_observations"]["expected"],
                         {"sold_kg": 7, "cash_eur": None, "observation_days": 0, "calendar_days": 31})
        changed = snapshot()
        changed["tables"]["Balances"].append(["2033-08-02", 0, 0, 0, 500])
        with self.assertRaises(ValueError):
            query_cases(changed)

    def test_schema_exposes_all_facts_and_measure_expressions_without_embedded_rows(self):
        parts = {"model.bim": {"model": {
            "tables": [{"name": "Finance", "columns": [{"name": "Cash", "dataType": "int64"}],
                        "partitions": [{"secret": "embedded rows"}],
                        "measures": [{"name": "Balance", "expression": "MAX(Cash)", "description": "Latest"}]}],
            "relationships": [{"name": "relation"}],
        }}}
        context = schema_context(parts)
        self.assertEqual(context["tables"][0]["name"], "Finance")
        self.assertEqual(context["tables"][0]["measures"][0]["expression"], "MAX(Cash)")
        self.assertNotIn("partitions", json.dumps(context))
        self.assertEqual(context["relationships"], [{"name": "relation"}])
        raw = schema_context(parts, raw=True)
        self.assertEqual(raw["tables"][0]["columns"], context["tables"][0]["columns"])
        self.assertEqual(raw["relationships"], context["relationships"])
        self.assertNotIn("measures", raw["tables"][0])

    def test_execute_query_preserves_blanks_records_server_errors_and_requires_exact_shape(self):
        http = Mock()
        response = http.request.return_value
        response.status_code = 200
        response.json.return_value = {"results": [{"tables": [{"rows": [{"[kg]": None}]}]}]}
        result = execute_query(http, "workspace", "model", 'EVALUATE ROW("kg", BLANK())', ["kg"])
        self.assertEqual(result["metrics"], {"kg": None})
        self.assertIn("/datasets/model/executeQueries", http.request.call_args.args[1])
        response.status_code = 400
        response.json.return_value = {"error": {"message": "Query compilation failed"}}
        self.assertEqual(execute_query(http, "w", "m", "EVALUATE bad", ["kg"])["state"], "QueryFailed")
        http.record.assert_called_once()
        response.status_code = 200
        response.json.return_value = {"results": [{"tables": [{"rows": [{"[other]": 0}]}]}]}
        self.assertEqual(execute_query(http, "w", "m", "EVALUATE bad", ["kg"])["state"], "ShapeFailed")
        with self.assertRaises(ValueError):
            execute_query(http, "w", "m", "```dax\nEVALUATE bad\n```", ["kg"])

    def test_equal_access_changes_only_specialist_instructions_and_scores_real_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"contract": {"firstDate": "2033-08-01", "throughDate": "2034-09-03"},
                    "schema": {"all_tables": True}, "specialistInstructions": "Do not allocate company cash."}
            http = Mock()
            response = http.request.return_value
            response.status_code = 200
            response.json.return_value = {"results": [{"tables": [{"rows": [{"[cash]": None}]}]}]}
            study = Study(Path(directory) / "trial", http, {"deployment": "test"}, plan)
            study.request = Mock(return_value={"content": '{"query":"EVALUATE ROW(\\"cash\\", BLANK())","reason":"grain"}'})
            client = Mock()
            client.ask.return_value = {"text": 'Snapshot through 2034-09-03, not live.\n{"cash":null}'}
            study.run_query_case("grain", {"question": "Cash by product?", "expected": {"cash": None}},
                                 client, "workspace", "model")
            first, second = [call.args[0] for call in study.request.call_args_list]
            self.assertEqual(first["messages"][1], second["messages"][1])
            self.assertNotIn(plan["specialistInstructions"], first["messages"][0]["content"])
            self.assertIn(plan["specialistInstructions"], second["messages"][0]["content"])
            self.assertTrue(all(arm["score"]["passed"] for arm in study.record["attempts"][0]["arms"].values()))
            self.assertEqual(http.request.call_count, 2)

    def test_ablation_removes_only_semantic_catalogue_not_query_access_or_question(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = {"contract": {"firstDate": "2033-08-01", "throughDate": "2034-09-03"},
                    "schema": {"tables": ["all_facts"], "measures": ["curated"]},
                    "rawSchema": {"tables": ["all_facts"]}, "specialistInstructions": "Business rules",
                    "queryArms": ["raw_schema", "schema_only", "schema_plus_instructions"]}
            http = Mock()
            response = http.request.return_value
            response.status_code = 200
            response.json.return_value = {"results": [{"tables": [{"rows": [{"[kg]": 11}]}]}]}
            study = Study(Path(directory) / "trial", http, {"deployment": "test"}, plan)
            study.request = Mock(return_value={"content": '{"query":"EVALUATE ROW(\\"kg\\", 11)","reason":"example"}'})
            client = Mock()
            client.ask.return_value = {"text": 'Snapshot through 2034-09-03\n{"kg":11}'}
            study.run_query_case("example", {"question": "How much?", "expected": {"kg": 11}}, client, "w", "m")
            prompts = [call.args[0]["messages"] for call in study.request.call_args_list]
            contexts = [json.loads(prompt[1]["content"]) for prompt in prompts]
            self.assertEqual(contexts[0]["question"], contexts[1]["question"])
            self.assertEqual(contexts[0]["model"], plan["rawSchema"])
            self.assertEqual(contexts[1]["model"], plan["schema"])
            self.assertEqual(prompts[0][0], prompts[1][0])
            self.assertEqual({call.args[1] for call in http.request.call_args_list},
                             {"https://api.powerbi.com/v1.0/myorg/groups/w/datasets/m/executeQueries"})
