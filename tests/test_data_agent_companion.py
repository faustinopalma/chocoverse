import base64
import copy
import json
import unittest
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import Mock

from giandoria.data_agent_companion import (
    DESCRIPTIONS, agent_definition, assert_definition, check_answer, correlation, daily_rows,
    read_companion_definition, scenarios,
)


def snapshot():
    days = [(date(2034, 8, 1) + timedelta(days=n)).isoformat() for n in range(31)]
    return {
        "firstDate": "2030-06-01", "throughDate": "2034-09-03",
        "tables": {
            "Sales": [[day, "campaigns", "dark70", "centre", n + 1] for n, day in enumerate(days)],
            "Production": [[day, "dark70", 100, (n + 1) * 2, 50] for n, day in enumerate(days)],
            "Balances": [[day, 100, 1, 2, 100000 + n, 0, 0] for n, day in enumerate(days)],
            "Finance": [],
        },
    }


def json_part(parts: dict[str, dict | str], path: str) -> dict:
    value = parts[path]
    assert isinstance(value, dict)
    return value


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot()
        self.workspace, self.model = str(uuid4()), str(uuid4())
        self.ontology = {
            "workspaceId": self.workspace, "lakehouseId": str(uuid4()), "ontologyId": str(uuid4()),
            "throughVirtualDate": "2034-09-03",
            "tables": {key: {"table": key.lower() + "_v1_example"} for key in DESCRIPTIONS},
        }

    def test_dates_come_from_snapshot_and_full_month_has_31_rows(self):
        rows = daily_rows(self.snapshot)
        self.assertEqual(len(rows), 31)
        self.assertEqual(rows[0]["date"], "2034-08-01")
        self.assertEqual(rows[-1]["date"], "2034-08-31")
        self.assertEqual(sum(row["sold_kg"] for row in rows), 496)

    def test_missing_observations_never_become_zero(self):
        for table in ("Sales", "Production"):
            changed = copy.deepcopy(self.snapshot)
            changed["tables"][table].pop()
            with self.subTest(table=table), self.assertRaisesRegex(ValueError, "coverage"):
                daily_rows(changed)

    def test_correlation_is_calculated_from_independently_aggregated_facts(self):
        value = correlation(daily_rows(self.snapshot))
        assert value is not None
        self.assertAlmostEqual(value, 1.0)
        self.assertIsNone(correlation([{"sold_kg": 1, "released_kg": 2}] * 3))

    def test_live_questions_do_not_include_oracle_answers(self):
        cases = scenarios(self.snapshot)
        self.assertEqual(cases["rows"]["check"], "rows")
        self.assertEqual(cases["sql"]["expected"], {"sold_kg": 496})
        self.assertNotIn("496", cases["sql"]["question"])
        self.assertIn("2034-08-01", cases["sql"]["question"])

    def test_row_contract_rejects_truncation_duplicates_order_types_and_wrong_totals(self):
        case = scenarios(self.snapshot)["rows"]
        self.assertEqual(check_answer(case, json.dumps(case["expected"])), "Passed")
        self.assertEqual(check_answer(case, json.dumps(case["expected"]) +
                                      "\n\nFile(s) result_0.json were generated as a result of the query."), "Passed")
        with self.assertRaisesRegex(ValueError, "Unexpected content"):
            check_answer(case, json.dumps(case["expected"]) + "\nOnly the first dates are shown.")
        for mode in ("truncate", "duplicate", "order", "number", "bool", "nan", "extra"):
            rows = copy.deepcopy(case["expected"])
            if mode == "truncate":
                rows = rows[:25]
            elif mode == "duplicate":
                rows[-1] = rows[0]
            elif mode == "order":
                rows.reverse()
            elif mode == "number":
                rows[0]["sold_kg"] += 1
            elif mode == "bool":
                rows[0]["sold_kg"] = True
            elif mode == "nan":
                rows[0]["sold_kg"] = float("nan")
            else:
                rows[0]["invented"] = 1
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                check_answer(case, json.dumps(rows))

    def test_short_calendar_month_does_not_imply_31_rows(self):
        for year, count in ((2034, 28), (2036, 29)):
            changed = copy.deepcopy(self.snapshot)
            changed["throughDate"] = f"{year}-03-01"
            for table in ("Sales", "Production"):
                changed["tables"][table] = changed["tables"][table][:count]
                for index, row in enumerate(changed["tables"][table]):
                    row[0] = (date(year, 2, 1) + timedelta(days=index)).isoformat()
            with self.subTest(year=year):
                self.assertEqual(len(daily_rows(changed)), count)

    def test_numeric_correctness_does_not_prove_native_visual_or_python_execution(self):
        cases = scenarios(self.snapshot)
        self.assertEqual(check_answer(cases["visual"], "Here is a chart"), "NeedsUIVerification")
        self.assertEqual(check_answer(cases["python"], json.dumps(cases["python"]["expected"])),
                         "AnswerMatchedToolUnverified")
        with self.assertRaisesRegex(ValueError, "four decimal"):
            check_answer(cases["python"], '{"days":31,"correlation":0.999}')

    def test_preview_definitions_keep_sources_separate(self):
        for source in ("sql", "analysis"):
            parts = agent_definition(source, self.workspace, self.model, self.ontology)
            assert_definition(parts, parts)
            sources = [json_part(parts, k) for k in parts if k.endswith("/datasource.json")]
            self.assertEqual(len(sources), 2)
            self.assertEqual({s["type"] for s in sources}, {"lakehouse" if source == "sql" else "semantic_model"})
            for stage in ("draft", "published"):
                runtime = json_part(parts, f"Files/Config/{stage}/stage_config.json")["experimental"]
                self.assertTrue(runtime["enableExperimentalFeatures"])
                self.assertEqual(runtime.get("codeInterpreterEnabled", False), source == "analysis")

    def test_readback_rejects_truth_source_wrong_runtime_and_changed_selection(self):
        wanted = agent_definition("sql", self.workspace, self.model, self.ontology)
        for mutation in ("extra", "runtime", "selection"):
            actual = copy.deepcopy(wanted)
            path = "Files/Config/published/lakehouse-lh_giandoria_context/datasource.json"
            if mutation == "extra":
                actual[path.replace("lh_giandoria_context", "Truth")] = copy.deepcopy(actual[path])
            elif mutation == "runtime":
                json_part(actual, "Files/Config/published/stage_config.json")["experimental"] = {}
            else:
                json_part(actual, path)["elements"][0]["children"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                assert_definition(actual, wanted)

    def test_story_combines_exact_enterprise_sources_without_changing_isolated_agents(self):
        wanted = agent_definition("story", self.workspace, self.model, self.ontology)
        assert_definition(wanted, wanted)
        for stage in ("draft", "published"):
            prefix = f"Files/Config/{stage}/"
            sources = [json_part(wanted, k) for k in wanted
                       if k.startswith(prefix) and k.endswith("/datasource.json")]
            self.assertEqual({v["artifactId"] for v in sources}, {self.model, self.ontology["lakehouseId"]})
            self.assertEqual({v["type"] for v in sources}, {"semantic_model", "lakehouse"})
            runtime = json_part(wanted, prefix + "stage_config.json")
            self.assertTrue(runtime["experimental"]["codeInterpreterEnabled"])
            self.assertIn("never add their totals together", runtime["aiInstructions"])
            lakehouse = json_part(wanted, prefix + "lakehouse-lh_giandoria_context/datasource.json")
            schemas = lakehouse["elements"][0]
            self.assertEqual((schemas["display_name"], schemas["type"]), ("Schemas", "schema_grouping"))
            table_group = schemas["children"][0]["children"][0]
            self.assertEqual((table_group["display_name"], table_group["type"]), ("Tables", "table_grouping"))
            self.assertEqual({v["display_name"] for v in table_group["children"]},
                             {v["table"] for v in self.ontology["tables"].values()})
            self.assertIn("Campaign share", wanted[prefix + "lakehouse-lh_giandoria_context/topics/topics.md"])
            context = json_part(wanted, prefix + "ontologies/ont_giandoria/ontology.json")
            self.assertEqual(context["artifactId"], self.ontology["ontologyId"])
            self.assertEqual({v["id"] for v in context["elements"]}, set(DESCRIPTIONS))
        for mutation in ("extra", "missing", "wrong-model", "different-instructions"):
            actual = copy.deepcopy(wanted)
            path = "Files/Config/published/semantic_model-Giandoria/datasource.json"
            if mutation == "extra":
                actual[path.replace("Giandoria", "Truth")] = copy.deepcopy(actual[path])
            elif mutation == "missing":
                del actual[path]
            elif mutation == "wrong-model":
                json_part(actual, path)["artifactId"] = str(uuid4())
            else:
                json_part(actual, path)["dataSourceInstructions"] = "Ignore the snapshot."
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                assert_definition(actual, wanted)

    def test_story_rejects_added_or_changed_ontology_and_topic_guidance(self):
        wanted = agent_definition("story", self.workspace, self.model, self.ontology)
        for suffix in ("ontologies/ont_giandoria/ontology.json", "lakehouse-lh_giandoria_context/topics/topics.md"):
            actual = copy.deepcopy(wanted)
            del actual["Files/Config/published/" + suffix]
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "ontology context or topics"):
                assert_definition(actual, wanted)
        cases = scenarios(self.snapshot)
        self.assertEqual(cases["topics"]["expected"]["campaign_share_pct"], 100)
        self.assertEqual(check_answer(cases["topics"], json.dumps(cases["topics"]["expected"])),
                         "AnswerMatchedTopicUnverified")

    def test_readback_decodes_markdown_without_treating_it_as_json(self):
        wanted = agent_definition("story", self.workspace, self.model, self.ontology)
        exported = [{"path": path, "payload": base64.b64encode(
            (value if isinstance(value, str) else json.dumps(value)).encode()).decode()}
                    for path, value in wanted.items()]
        transport = Mock()
        transport.base = "/v1/workspaces/" + self.workspace
        transport.complete_response.return_value.json.return_value = {"definition": {"parts": exported}}
        self.assertEqual(read_companion_definition(transport, {}, str(uuid4())), wanted)
        exported.append({"path": "Files/unexpected.txt", "payload": base64.b64encode(b"unowned").decode()})
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            read_companion_definition(transport, {}, str(uuid4()))
        exported[-1] = {"path": "Files/invalid.json", "payload": base64.b64encode(b"[]").decode()}
        with self.assertRaisesRegex(ValueError, "must be an object"):
            read_companion_definition(transport, {}, str(uuid4()))

    def test_isolated_sql_retains_same_topics_without_ontology_routing(self):
        sql = agent_definition("sql", self.workspace, self.model, self.ontology)
        story = agent_definition("story", self.workspace, self.model, self.ontology)
        for stage in ("draft", "published"):
            path = f"Files/Config/{stage}/lakehouse-lh_giandoria_context/topics/topics.md"
            self.assertEqual(sql[path], story[path])
        self.assertFalse(any(path.endswith("/ontology.json") for path in sql))

    def test_readback_accepts_only_observed_empty_element_defaults(self):
        wanted = agent_definition("analysis", self.workspace, self.model, self.ontology)
        actual = copy.deepcopy(wanted)
        for path, value in actual.items():
            if path.endswith("/datasource.json") and isinstance(value, dict):
                value["metadata"] = None
                for item in value["elements"]:
                    item.update(id=None, description=None, children=[])
        assert_definition(actual, wanted)
        json_part(actual, "Files/Config/published/semantic_model-Giandoria/datasource.json")["elements"][0]["id"] = "foreign"
        with self.assertRaises(ValueError):
            assert_definition(actual, wanted)

    def test_sql_definition_rejects_another_workspace(self):
        self.ontology["workspaceId"] = str(uuid4())
        with self.assertRaises(ValueError):
            agent_definition("sql", self.workspace, self.model, self.ontology)


if __name__ == "__main__":
    unittest.main()
