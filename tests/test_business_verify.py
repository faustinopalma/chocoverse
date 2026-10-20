import tempfile
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from azure.core.credentials import AccessToken

from giandoria.business_verify import (
    VerificationCredential, bucket_digests, compare_buckets, compare_rows, load_archive, query,
    verify, verify_ledger_continuation,
)


class VerificationTests(unittest.TestCase):
    def test_previous_ledger_is_utf8_even_with_windows_locale(self):
        ledger = {"calls": 104, "records": {"original": {
            "state": "Complete", "decision": {"mode": "llm", "reason": "Backlog 1\u20132 kg"},
        }}}
        read_text = Path.read_text

        def locale_read(path, *args, **kwargs):
            kwargs.setdefault("encoding", "cp1252")
            return read_text(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / ".local"
            local.mkdir()
            (local / "business-fabric.json").write_text(
                '{"queryServiceUri":"https://demo.kusto.fabric.microsoft.com"}', encoding="utf-8",
            )
            previous = local / "previous.json"
            previous.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
            with patch("giandoria.business_verify.VerificationCredential"), patch(
                "giandoria.business_verify.BusinessEngine",
            ) as engine, patch("giandoria.business_verify.BlobStore") as store, patch(
                "giandoria.business_verify.RecordedHttp",
            ) as http, patch(
                "giandoria.business_verify.DemoConfig.load",
            ), patch("giandoria.business_verify.BusinessConfig.load"), patch.dict(
                "os.environ", {"GIANDORIA_STATE_ACCOUNT": "stgiandoriatest"},
            ), patch.object(Path, "read_text", locale_read):
                engine.return_value.assert_invariants = Mock()
                engine.return_value.summary.return_value = {}
                store.return_value.get_json.side_effect = [{"tick": 1, "outbox": []}, {}, ledger]
                http.return_value.request.side_effect = RuntimeError("Archive listing reached")
                with self.assertRaisesRegex(RuntimeError, "Archive listing reached"):
                    verify(root, 1, previous)

    def test_continuation_retains_legacy_decisions_and_durable_session_limits(self):
        previous = {"calls": 104, "records": {"original": {"mode": "llm"}}}
        current = {"calls": 112, "records": copy.deepcopy(previous["records"]),
                   "session_budgets": {"live": {"calls": 8, "reserved_tokens": 80000}}}
        verify_ledger_continuation(current, previous)
        for mutation in ("legacy_limit", "session_limit", "changed_decision", "reset_budget"):
            with self.subTest(mutation=mutation):
                invalid = copy.deepcopy(current)
                baseline = previous
                if mutation == "legacy_limit":
                    invalid["calls"] = 119
                elif mutation == "session_limit":
                    invalid["session_budgets"]["live"]["reserved_tokens"] = 2_000_001
                elif mutation == "changed_decision":
                    invalid["records"]["original"] = {"mode": "fallback"}
                else:
                    baseline = current
                    invalid["session_budgets"] = {}
                with self.assertRaises(ValueError):
                    verify_ledger_continuation(invalid, baseline)

    def test_archive_transport_retries_are_bounded_and_recorded(self):
        store = Mock()
        with tempfile.TemporaryDirectory() as directory, patch("giandoria.business_verify.time.sleep"):
            cache = Path(directory)
            store.get_json.side_effect = [requests.ConnectTimeout("offline"), {"events": []}]
            self.assertEqual(load_archive(store, cache, "run/1-1.json"), {"events": []})
            self.assertEqual(store.get_json.call_count, 2)
            store.http.record.assert_called_once()
            store.get_json.reset_mock()
            store.get_json.side_effect = requests.ConnectTimeout("offline")
            with self.assertRaises(requests.ConnectTimeout):
                load_archive(store, cache, "run/2-2.json")
            self.assertEqual(store.get_json.call_count, 3)
            store.get_json.reset_mock()
            store.get_json.side_effect = RuntimeError("HTTP 403")
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                load_archive(store, cache, "run/2-2.json")
            self.assertEqual(store.get_json.call_count, 1)

    def test_archive_cache_is_atomic_and_reused_without_remote_reads(self):
        store = Mock()
        store.get_json.return_value = {"events": [{"id": "a"}]}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            self.assertEqual(load_archive(store, cache, "run/1-1.json"), store.get_json.return_value)
            store.get_json.reset_mock()
            self.assertEqual(load_archive(store, cache, "run/1-1.json"), {"events": [{"id": "a"}]})
            store.get_json.assert_not_called()
            self.assertFalse((cache / "1-1.tmp").exists())
            store.get_json.return_value = None
            with self.assertRaisesRegex(ValueError, "archive is missing"):
                load_archive(store, cache, "run/2-2.json")

    def test_query_rejects_partial_failure_with_numbered_status_table(self):
        http = Mock()
        http.request.return_value.json.return_value = {"Tables": [
            {"TableName": "Table_0", "Columns": [{"ColumnName": "value"}], "Rows": [[1]]},
            {"TableName": "Table_2", "Columns": [{"ColumnName": "Severity"}, {"ColumnName": "StatusCode"}],
             "Rows": [[2, 1]]},
        ]}
        with self.assertRaisesRegex(RuntimeError, "partial query failure"):
            query(http, "https://demo.kusto.fabric.microsoft.com", "database", "print value=1")
        http.request.return_value.json.return_value["Tables"][1]["Rows"] = [[4, 0], [6, 0]]
        self.assertEqual(query(http, "https://demo.kusto.fabric.microsoft.com", "database", "print value=1"), [[1]])

    def test_verification_tokens_are_cached_until_near_expiry(self):
        with patch("giandoria.business_verify.AzureCliCredential") as cli, patch(
            "giandoria.business_verify.time.time", return_value=100,
        ):
            cli.return_value.get_token.return_value = AccessToken("offline", 1000)
            credential = VerificationCredential()
            scope = "https://storage.azure.com/.default"
            self.assertEqual(credential.get_token(scope), credential.get_token(scope))
            self.assertEqual(cli.return_value.get_token.call_count, 1)
            with patch("giandoria.business_verify.time.time", return_value=900):
                credential.get_token(scope)
            self.assertEqual(cli.return_value.get_token.call_count, 2)
            with self.assertRaises(ValueError):
                credential.get_token("https://foreign.invalid/.default")
            credential.close()

    def test_digest_buckets_are_order_independent_and_detect_corruption(self):
        expected = bucket_digests({0: {"a:hash", "b:hash"}})
        count, digest = expected[0]
        self.assertTrue(compare_buckets(expected, [[0, count, digest, 0, 3]]))
        self.assertFalse(compare_buckets(expected, [[0, 1, "partial", 0, 1]]))
        for row in ([0, count, "changed", 0, 2], [0, count, digest, 1, 2], [1, 1, digest, 0, 1]):
            with self.assertRaises(ValueError):
                compare_buckets(expected, [row])

    def test_complete_exact_events_allow_identical_replays(self):
        self.assertTrue(compare_rows({"a": "hash"}, [["a", '["hash"]', '["enterprise"]', 2]]))

    def test_incomplete_destination_is_not_success(self):
        self.assertFalse(compare_rows({"a": "hash"}, []))

    def test_truth_conflicting_raw_and_extra_events_are_rejected(self):
        for rows in (
            [["a", ["hash"], ["truth"], 1]],
            [["a", ["hash", "other"], ["enterprise"], 2]],
            [["b", ["hash"], ["enterprise"], 1]],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                compare_rows({"a": "hash"}, rows)


if __name__ == "__main__":
    unittest.main()
