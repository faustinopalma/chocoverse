import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from giandoria.report_narratives import (
    GUIDANCE, VERSION, digest, evidence, generate, load_commentary, validate_commentary, verify_report,
)
from giandoria.showcase import report_definition
from tests.test_showcase import sample


def commentary():
    return {page: "Read the displayed measures in their virtual calendar context. Compare flows with flows and "
            "balances with balances, and do not infer a cause or a complete business outcome from a single chart."
            for page in GUIDANCE}


def record(snapshot):
    return {"state": "Complete", "version": VERSION, "snapshotDigest": digest(snapshot),
            "guidanceDigest": digest(GUIDANCE), "commentary": commentary(), "evidence": evidence(snapshot)}


class ReportNarrativeTests(unittest.TestCase):
    def test_evidence_is_independent_enterprise_snapshot_arithmetic(self):
        result = evidence(sample())
        self.assertEqual(result["soldKg"], 10)
        self.assertEqual(result["revenueEUR"], 100)
        self.assertEqual(result["cashMovementEUR"], 90)
        self.assertEqual(result["lastCashEUR"], 130)
        self.assertEqual(result["lastObservationDate"], "2032-03-01")
        self.assertEqual(result["channelSoldKg"], {"export": 10})
        self.assertIn("no report slicers", result["scope"])

    def test_all_pages_have_native_dynamic_summary_and_static_guide_after_charts(self):
        for commercial in (True, False):
            parts = report_definition("same-model", commercial)
            pages = {path: value for path, value in parts.items() if path.endswith("/page.json")}
            self.assertEqual(len(pages), 3)
            for path, page in pages.items():
                prefix = path.removesuffix("page.json")
                visuals = [value for name, value in parts.items()
                           if name.startswith(prefix) and name.endswith("/visual.json")]
                boxes = [value for value in visuals if value["visual"]["visualType"] == "textbox"]
                self.assertEqual(len(boxes), 2)
                text = json.dumps(boxes)
                self.assertIn(GUIDANCE[page["displayName"]], text)
                self.assertIn("Native Smart narrative", text)
                self.assertIn("ChangeSummary", text)
                self.assertNotIn("Entire snapshot:", text)
                guide = next(v for v in boxes if GUIDANCE[page["displayName"]] in json.dumps(v))
                charts = [v for v in visuals if v["visual"]["visualType"] not in ("textbox", "card", "slicer")]
                self.assertTrue(all(v["position"]["y"] + v["position"]["height"] < guide["position"]["y"]
                                    for v in charts))
                for visual in visuals:
                    pos = visual["position"]
                    self.assertLessEqual(pos["y"] + pos["height"], page["height"])
                for left_index, left in enumerate(visuals):
                    for right in visuals[left_index + 1:]:
                        a, b = left["position"], right["position"]
                        self.assertFalse(a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
                                         and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"])

    def test_commentary_rejects_missing_pages_fabricated_numbers_and_markup(self):
        validate_commentary(commentary())
        for mutate in ("missing", "number", "markup", "short"):
            value = commentary()
            page = next(iter(value))
            if mutate == "missing":
                value.pop(page)
            elif mutate == "number":
                value[page] += " Sales grew 50%."
            elif mutate == "markup":
                value[page] += "<script>"
            else:
                value[page] = "too short"
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                validate_commentary(value)

    def test_readback_allows_only_verified_model_connection_expansion(self):
        expected = report_definition("model-id", True)
        actual = copy.deepcopy(expected)
        connection = actual["definition.pbir"]["datasetReference"]["byConnection"]
        connection["connectionString"] = (
            "Data Source=powerbi://api.powerbi.com/v1.0/myorg/ws-giandoria-demo;"
            "initial catalog=sm_giandoria_showcase;integrated security=ClaimsToken;semanticmodelid=model-id")
        verify_report(actual, expected, "model-id")
        connection["connectionString"] += ";semanticmodelid=other-model"
        with self.assertRaises(ValueError):
            verify_report(actual, expected, "model-id")
        changed = copy.deepcopy(expected)
        changed["definition/report.json"]["themeCollection"] = {"unexpected": True}
        with self.assertRaises(RuntimeError):
            verify_report(changed, expected, "model-id")

    def test_replay_is_nonbillable_and_stale_snapshot_or_guidance_is_rejected(self):
        snapshot = sample()
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            (local / "report-narratives.json").write_text(json.dumps(record(snapshot)))
            http = Mock()
            generate(http, "https://example.openai.azure.com", "model", "version", snapshot, local)
            http.request.assert_not_called()
            changed = copy.deepcopy(snapshot)
            changed["sequence"] += 1
            with self.assertRaises(ValueError):
                load_commentary(local, changed)
            stale = record(snapshot)
            stale["guidanceDigest"] = "changed"
            (local / "report-narratives.json").write_text(json.dumps(stale))
            with self.assertRaises(ValueError):
                load_commentary(local, snapshot)

    def test_generation_reserves_before_one_call_and_persists_real_model_provenance(self):
        snapshot = sample()
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            http = Mock()

            def request(*_args, **kwargs):
                self.assertEqual(_args[0], "POST")
                self.assertEqual(_args[2], "https://cognitiveservices.azure.com/.default")
                state = json.loads((local / "report-narratives.json").read_text())
                self.assertEqual(state["state"], "Reserved")
                body = json.loads(kwargs["body"])
                self.assertEqual(body["max_completion_tokens"], 4096)
                self.assertNotIn("truth", body["messages"][1]["content"])
                return Mock(json=lambda: {"choices": [{"finish_reason": "stop",
                    "message": {"content": json.dumps(commentary())}}], "usage": {"completion_tokens": 500}})

            http.request.side_effect = request
            result = generate(http, "https://example.openai.azure.com", "model", "version", snapshot, local)
            self.assertEqual(result["state"], "Complete")
            self.assertEqual(result["deployment"], "model")
            http.request.assert_called_once()
            self.assertEqual(load_commentary(local, snapshot), result)

    def test_failed_or_interrupted_attempt_is_not_automatically_reissued(self):
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            http = Mock()
            http.request.return_value.json.return_value = {
                "choices": [{"finish_reason": "length"}], "usage": {"completion_tokens": 4096}}
            with self.assertRaises(ValueError):
                generate(http, "https://example.openai.azure.com", "model", "version", sample(), local)
            self.assertEqual(json.loads((local / "report-narratives.json").read_text())["state"], "Answered")
            with self.assertRaises(ValueError):
                generate(http, "https://example.openai.azure.com", "model", "version", sample(), local)
            http.request.assert_called_once()
