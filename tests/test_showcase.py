import base64
import copy
import json
import re
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

from giandoria.fabric_deploy import RecordedRequests
from giandoria.showcase import (
    FACTS, extract_snapshot, imported_table, measures, model_definition, publish, report_definition, validate_snapshot, verify,
)

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return {
        "run": "business-demo-001", "firstDate": "2032-02-28", "throughDate": "2032-03-01", "sequence": 100,
        "tables": {
            "Sales": [["2032-02-28", "export", "dark70", "north", 10]],
            "Production": [["2032-02-28", "dark70", 20, 15, 12]],
            "Finance": [["2032-02-28", 10000, 1000, 500, 500, 10000, 1000]],
            "Balances": [["2032-02-28", 10, 2, 3, 12000, 1000, 500], ["2032-03-01", 15, 1, 2, 13000, 500, 0]],
        },
    }


class ShowcaseTests(unittest.TestCase):
    @patch("giandoria.showcase.dax")
    def test_reconciliation_keeps_absent_prior_year_sales_blank(self, dax):
        dax.side_effect = [
            [{"[Sold]": 10, "[Revenue]": 100, "[Purchases]": 10, "[Started]": 20, "[Released]": 15,
              "[Shipped]": 12, "[Cash]": 130, "[Days]": 3, "[ChannelFinance]": None,
              "[Target2]": 20, "[Target4]": 40}],
            [{"[DefaultCover]": 3, "[MultipleCover]": 3, "[ProductFinance]": None,
              "[TerritoryBalance]": None, "[ChannelProduction]": None}],
            [{"[Sold]": 10, "[PY]": None, "[YoY]": None, "[YTD]": 10, "[Rolling]": 10}],
            [{"Channel[Channel]": "export", "[Sold]": 10, "[Share]": 1, "[Rank]": 1}],
            [{"[Amount]": 90}],
            [{"[Stock]": None, "[Gap]": None}],
        ]
        result = verify(Mock(), "workspace", "model", sample())
        self.assertIsNone(result["virtualPeriod"]["[PY]"])
        self.assertEqual(dax.call_count, 6)

    @patch("giandoria.showcase.query")
    def test_bounded_episode_uses_one_sequence_and_start_for_every_fact(self, query):
        snapshot = sample()
        query.side_effect = [[["2032-03-02", 100]], *snapshot["tables"].values()]
        result = extract_snapshot(Mock(), {"queryServiceUri": "test", "databaseId": "db"},
                                  from_date="20320228")
        self.assertEqual(result, snapshot)
        for call in query.call_args_list[1:]:
            text = call.args[3]
            self.assertIn("let upper_sequence=long(100);", text)
            self.assertIn("let cutoff=datetime(2032-03-02);", text)
            self.assertIn("todatetime(event.simlocaldate) >= datetime(2032-02-28)", text)
            self.assertIn("< cutoff", text)
        query.reset_mock(side_effect=True)
        query.return_value = [["2032-03-02", 100]]
        for start in ("2032-03-02", "2032-04-01", "not-a-date"):
            with self.subTest(start=start), self.assertRaises(ValueError):
                extract_snapshot(Mock(), {"queryServiceUri": "test", "databaseId": "db"}, from_date=start)

    def setUp(self):
        self.config = json.loads((ROOT / "config" / "business.json").read_text())
        self.snapshot = sample()

    def test_snapshot_grains_and_known_members(self):
        validate_snapshot(self.snapshot, self.config)
        for mutation in ("duplicate", "unknown", "future", "shape", "negative"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.snapshot)
                row = changed["tables"]["Sales"][0]
                if mutation == "duplicate":
                    changed["tables"]["Sales"].append(row.copy())
                elif mutation == "unknown":
                    row[2] = "unknown"
                elif mutation == "future":
                    row[0] = "2032-03-02"
                elif mutation == "shape":
                    row.append(0)
                else:
                    row[4] = -1
                with self.assertRaises(ValueError):
                    validate_snapshot(changed, self.config)

    def test_negative_cash_is_a_valid_observation(self):
        self.snapshot["tables"]["Balances"][0][4] = -100
        validate_snapshot(self.snapshot, self.config)

    def test_import_payload_roundtrip_without_external_sources(self):
        table = imported_table("Sales", FACTS["Sales"], self.snapshot["tables"]["Sales"])
        expression = table["partitions"][0]["source"]["expression"]
        match = re.search(r'Binary.FromText\("([^"]+)"', expression)
        assert match is not None
        encoded = match.group(1)
        self.assertEqual(json.loads(zlib.decompress(base64.b64decode(encoded), -15)),
                         self.snapshot["tables"]["Sales"])
        for forbidden in ("Web.Contents", "AzureDataExplorer", "File.Contents", "DateTime.LocalNow"):
            self.assertNotIn(forbidden, expression)

    def test_calendar_contains_leap_day_and_has_ordering(self):
        model = model_definition(self.snapshot, self.config)
        table = model["model"]["tables"][0]
        expression = table["partitions"][0]["source"]["expression"]
        match = re.search(r'Binary.FromText\("([^"]+)"', expression)
        assert match is not None
        encoded = match.group(1)
        rows = json.loads(zlib.decompress(base64.b64decode(encoded), -15))
        self.assertEqual([r[0] for r in rows], ["2032-02-28", "2032-02-29", "2032-03-01"])
        self.assertEqual(table["dataCategory"], "Time")
        self.assertTrue(table["columns"][0]["isKey"])
        columns = {c["name"]: c for c in table["columns"]}
        self.assertEqual(columns["YearMonth"]["sortByColumn"], "MonthIndex")
        self.assertEqual(len(table["hierarchies"][0]["levels"]), 3)

    def test_constellation_has_one_way_relationships_and_no_false_grain(self):
        model = model_definition(self.snapshot, self.config)["model"]
        relations = model["relationships"]
        self.assertEqual(len(relations), 8)
        for relation in relations:
            self.assertEqual(relation["fromCardinality"], "many")
            self.assertEqual(relation["toCardinality"], "one")
            self.assertEqual(relation["crossFilteringBehavior"], "oneDirection")
            self.assertNotIn(relation["toTable"], ("Cover policy", "Cash flow", "Snapshot"))
        self.assertEqual([r["toTable"] for r in relations if r["fromTable"] == "Finance"], ["Date"])
        self.assertTrue(all(t["isHidden"] for t in model["tables"] if t["name"] in FACTS))

    def test_measures_teach_time_grain_and_semi_additivity(self):
        all_measures = {m["name"]: m for m in measures()}
        self.assertGreaterEqual(len(all_measures), 25)
        self.assertIn("DATEADD", all_measures["Sold kg PY"]["expression"])
        self.assertIn("REMOVEFILTERS('Channel')", all_measures["Channel share %"]["expression"])
        self.assertIn("ALLSELECTED", all_measures["Channel rank"]["expression"])
        self.assertIn("MAX('Balances'[Date])", all_measures["Cash as observed EUR"]["expression"])
        self.assertIn("ISCROSSFILTERED('Product')", all_measures["Revenue EUR"]["expression"])
        self.assertIn("ISBLANK", all_measures["Illustrative gap kg"]["expression"])
        for measure in all_measures.values():
            self.assertTrue(measure["description"])
            for forbidden in ("TODAY(", "NOW(", "wall_ts"):
                self.assertNotIn(forbidden, measure["expression"])

    def test_reports_are_thin_deterministic_and_bind_valid_fields(self):
        tables = {t["name"]: {c["name"] for c in t["columns"]}
                  for t in model_definition(self.snapshot, self.config)["model"]["tables"]}
        tables["Metrics"].update(m["name"] for m in measures())
        for commercial in (False, True):
            parts = report_definition("model-id", commercial)
            self.assertEqual(parts, report_definition("model-id", commercial))
            self.assertEqual(parts["definition.pbir"]["datasetReference"]["byConnection"]["connectionString"],
                             "semanticmodelid=model-id")
            self.assertEqual(len(parts["definition/pages/pages.json"]["pageOrder"]), 3)
            visuals = [v for p, v in parts.items() if p.endswith("/visual.json")]
            self.assertEqual(len(visuals), 31 if commercial else 22)
            for visual in visuals:
                self.assertIn(visual["visual"]["visualType"], {
                    "card", "slicer", "lineChart", "clusteredBarChart", "donutChart",
                    "pivotTable", "scatterChart", "columnChart", "clusteredColumnChart", "waterfallChart", "textbox",
                })
                for state in visual["visual"].get("query", {}).get("queryState", {}).values():
                    for projection in state["projections"]:
                        field = next(iter(projection["field"].values()))
                        self.assertIn(field["Property"], tables[field["Expression"]["SourceRef"]["Entity"]])
            self.assertNotIn("model.bim", parts)

    def test_extraction_queries_deduplicate_and_share_cutoff(self):
        for name in FACTS:
            text = (ROOT / "fabric" / "showcase" / f"{name.lower()}.kql").read_text()
            self.assertIn('run_id == "business-demo-001"', text)
            self.assertIn("sequence <= upper_sequence", text)
            self.assertIn("< cutoff", text)
            self.assertTrue("by event_id" in text or "arg_max(sequence, *) by Date" in text)
            for forbidden in ("now(", "ago(", "wall_ts", "bronze_truth"):
                self.assertNotIn(forbidden, text)

    def test_completed_definition_update_has_no_result_location(self):
        transport = object.__new__(RecordedRequests)
        response = Mock(status_code=200, content=b'{"status":"Succeeded"}', headers={})
        response.json.return_value = {"status": "Succeeded"}
        self.assertIs(transport.complete_response(response, {}), response)

    def test_definition_failures_preserve_service_diagnostics(self):
        transport = object.__new__(RecordedRequests)
        response = Mock(status_code=200, content=b"{}", headers={})
        response.json.return_value = {"status": "Failed", "error": {"errorCode": "InvalidModel", "message": "Bad table"}}
        with self.assertRaisesRegex(RuntimeError, "InvalidModel"):
            transport.complete_response(response, {})

    def test_readback_accepts_service_defaults_but_rejects_semantic_changes(self):
        model = model_definition(self.snapshot, self.config)
        normalized = copy.deepcopy(model)
        for relation in normalized["model"]["relationships"]:
            for field in ("fromCardinality", "toCardinality", "crossFilteringBehavior"):
                relation.pop(field)
        for changed in (False, True):
            with self.subTest(changed=changed):
                observed = copy.deepcopy(normalized)
                if changed:
                    observed["model"]["relationships"][0]["crossFilteringBehavior"] = "bothDirections"
                if changed:
                    with self.assertRaisesRegex(RuntimeError, "crossFilteringBehavior"):
                        self.publish_fixture("sm_giandoria_showcase", {"model.bim": model}, {"model.bim": observed})
                else:
                    self.publish_fixture("sm_giandoria_showcase", {"model.bim": model}, {"model.bim": observed})

    def test_report_readback_keeps_model_identity_and_exact_visuals(self):
        parts = report_definition("model-id", True)
        for mutation in ("expanded", "foreign-model", "changed-visual"):
            with self.subTest(mutation=mutation):
                actual = copy.deepcopy(parts)
                actual["definition.pbir"]["datasetReference"]["byConnection"]["connectionString"] = (
                    "Data Source=powerbi://api.powerbi.com/v1.0/myorg/ws-giandoria-demo;"
                    "initial catalog=sm_giandoria_showcase;integrated security=ClaimsToken;"
                    f"semanticmodelid={'other-id' if mutation == 'foreign-model' else 'model-id'}"
                )
                if mutation == "changed-visual":
                    path = next(p for p in actual if p.endswith("/visual.json"))
                    actual[path]["visual"]["visualType"] = "unsupported"
                if mutation == "expanded":
                    self.publish_fixture("rp_giandoria_commercial", parts, actual)
                else:
                    with self.assertRaises(RuntimeError):
                        self.publish_fixture("rp_giandoria_commercial", parts, actual)

    def publish_fixture(self, name, parts, actual):
        transport = Mock(registry={name: "item-id"}, base="/v1/workspaces/workspace-id")
        response = Mock()
        response.json.return_value = {"definition": {"parts": [
            {"path": path, "payload": base64.b64encode(json.dumps(doc).encode()).decode()}
            for path, doc in actual.items()]}}
        transport.request.return_value = response
        transport.complete_response.return_value = response
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".local").mkdir()
            with patch("giandoria.showcase.ROOT", root):
                self.assertEqual(publish(transport, {}, name, parts), "item-id")


if __name__ == "__main__":
    unittest.main()
