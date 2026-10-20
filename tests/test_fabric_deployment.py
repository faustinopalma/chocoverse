import importlib.util
import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


FABRIC_INSTALLED = importlib.util.find_spec("fabric_cicd") is not None
if FABRIC_INSTALLED:
    import requests
    from giandoria.fabric_deploy import EXPECTED, MARKER, RecordedRequests, SessionCredential


@unittest.skipUnless(FABRIC_INSTALLED, "Install the explicit [fabric] extra to test deployment tooling.")
class FabricDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.workspace_id = str(uuid4())
        self.transport = RecordedRequests(self.root, self.workspace_id, time.monotonic() + 30)
        self.url = f"https://api.fabric.microsoft.com/v1/workspaces/{self.workspace_id}/items"

    @staticmethod
    def response(body: dict[str, object] | None, status: int = 200) -> "requests.Response":
        response = requests.Response()
        response.status_code = status
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(body).encode()
        return response

    def test_credential_restricts_audience_and_expiry(self) -> None:
        credential = SessionCredential("secret-value", int(time.time()) + 60)
        self.assertEqual(credential.get_token("https://api.fabric.microsoft.com/.default").token, "secret-value")
        with self.assertRaises(ValueError):
            credential.get_token("https://management.azure.com/.default")
        with self.assertRaises(ValueError):
            SessionCredential("secret", 0).get_token("https://api.fabric.microsoft.com/.default")

    def test_rejects_foreign_hosts_workspaces_query_secrets_and_mutations(self) -> None:
        for method, url in (
            ("GET", "https://example.com/v1/workspaces"),
            ("GET", "http://api.fabric.microsoft.com/v1/workspaces"),
            ("GET", self.url.replace(self.workspace_id, str(uuid4()))),
            ("GET", self.url + "?access_token=secret"),
            ("DELETE", self.url),
            ("POST", self.url + "/unknown/updateDefinition"),
        ):
            with self.subTest(method=method, url=url), self.assertRaises(ValueError):
                self.transport.request(method, url)

    def test_records_status_without_headers_or_response_secrets(self) -> None:
        with patch("requests.request", return_value=self.response({"secret": "never-record"}, 403)) as send:
            result = self.transport.request("GET", self.url, headers={"Authorization": "Bearer never-record"})
        self.assertEqual(result.status_code, 403)
        self.assertLessEqual(send.call_args.kwargs["timeout"], 30)
        self.assertFalse(send.call_args.kwargs["allow_redirects"])
        text = self.transport.journal_path.read_text()
        self.assertNotIn("never-record", text)
        records = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([record["status"] for record in records], ["Started", "Failed"])
        self.assertEqual(records[0]["invocationId"], records[1]["invocationId"])
        self.assertEqual(records[1]["details"]["httpStatus"], 403)

    def test_connection_failure_is_recorded_and_propagated(self) -> None:
        with patch("requests.request", side_effect=requests.ConnectionError("never-record")):
            with self.assertRaises(requests.ConnectionError):
                self.transport.request("GET", self.url)
        text = self.transport.journal_path.read_text()
        self.assertNotIn("never-record", text)
        self.assertEqual(json.loads(text.splitlines()[-1])["status"], "Failed")

    def test_deadline_prevents_request(self) -> None:
        self.transport.deadline = time.monotonic() - 1
        with patch("requests.request") as send, self.assertRaises(TimeoutError):
            self.transport.request("GET", self.url)
        send.assert_not_called()

    def test_rejects_unrecorded_existing_item(self) -> None:
        item = {"id": str(uuid4()), "type": "Eventhouse", "displayName": "eh_giandoria", "description": MARKER}
        with patch("requests.request", return_value=self.response({"value": [item]})):
            with self.assertRaisesRegex(ValueError, "unrecorded"):
                self.transport.preflight({})

    def test_business_scope_cannot_mutate_other_recorded_items(self) -> None:
        transport = RecordedRequests(self.root, self.workspace_id, time.monotonic() + 30,
                                     {"es_giandoria_business": "Eventstream"})
        unrelated = str(uuid4())
        transport.registry["eh_giandoria"] = unrelated
        with self.assertRaisesRegex(ValueError, "Unplanned"):
            transport.request("POST", f"{self.url}/{unrelated}/updateDefinition", json={})
        body = {"displayName": "es_giandoria_business", "type": "Eventstream", "description": MARKER}
        with patch("requests.request", return_value=self.response({**body, "id": str(uuid4())}, 201)):
            transport.request("POST", self.url, json=body)
        self.assertIn("es_giandoria_business", transport.registry)

    def test_custom_view_marker_and_definition_readback_remain_item_scoped(self) -> None:
        marker = "Source-owned Giandoria views"
        transport = RecordedRequests(self.root, self.workspace_id, time.monotonic() + 30,
                                     {"rt_giandoria": "KQLDashboard"}, marker=marker)
        item = {"id": str(uuid4()), "type": "KQLDashboard", "displayName": "rt_giandoria", "description": marker}
        transport.registry["rt_giandoria"] = item["id"]
        with patch("requests.request", return_value=self.response({"value": [item]})):
            transport.preflight({})
        with patch("requests.request", return_value=self.response({})) as send:
            transport.request("POST", f"{self.url}/{item['id']}/getDefinition")
            send.assert_called_once()
        with patch("requests.request", return_value=self.response({})) as send:
            transport.request("POST", f"{self.url}/{item['id']}/getDefinition?format=TMSL")
            send.assert_called_once()
        for suffix in ("/updateDefinition?format=TMSL", "/getDefinition?format=Unknown"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                transport.request("POST", f"{self.url}/{item['id']}{suffix}")
        with self.assertRaises(ValueError):
            transport.request("POST", f"{self.url}/{uuid4()}/getDefinition")
        item["description"] = MARKER
        with patch("requests.request", return_value=self.response({"value": [item]})):
            with self.assertRaises(ValueError):
                transport.preflight({})

    def test_partial_recovery_requires_receipt_and_matching_exported_definition(self) -> None:
        name = "eh_giandoria"
        directory = self.root / "fabric" / f"{name}.Eventhouse"
        directory.mkdir(parents=True)
        metadata = {"metadata": {"type": "Eventhouse", "displayName": name}, "config": {"logicalId": str(uuid4())}}
        (directory / ".platform").write_text(json.dumps(metadata))
        exported = {**metadata, "config": {"logicalId": str(uuid4())}}
        item = {"id": str(uuid4()), "type": "Eventhouse", "displayName": name, "description": MARKER}
        parts = [{"path": path, "payload": base64.b64encode(json.dumps(body).encode()).decode()} for path, body in (
            (".platform", exported), ("EventhouseProperties.json", {}),
        )]
        self.transport.pending.add(name)
        self.transport.receipts[name] = "verified-accepted-create-receipt"
        with patch("requests.request", side_effect=[
            self.response({"value": [item]}), self.response({"definition": {"parts": parts}}),
        ]):
            self.transport.preflight({})
        self.assertEqual(self.transport.registry[name], item["id"])
        self.assertNotIn(name, self.transport.pending)

    def test_persists_creation_before_allowing_updates(self) -> None:
        item = {"id": str(uuid4()), "type": "Eventhouse", "displayName": "eh_giandoria", "description": MARKER}
        with patch("requests.request", return_value=self.response(item, 201)):
            self.transport.request("POST", self.url, json={key: value for key, value in item.items() if key != "id"})
        self.assertEqual(self.transport.registry["eh_giandoria"], item["id"])
        restarted = RecordedRequests(self.root, self.workspace_id, time.monotonic() + 10)
        self.assertEqual(restarted.registry, self.transport.registry)
        with patch("requests.request", return_value=self.response({})):
            restarted.request("POST", self.url + f"/{item['id']}/updateDefinition", json={"definition": {}})

    def test_canonicalizes_lro_location_without_sending_token_to_backend_host(self) -> None:
        response = self.response({}, 202)
        operation_id = str(uuid4())
        response.headers["Location"] = f"https://api.powerbi.com/v1/operations/{operation_id}"
        with patch("requests.request", return_value=response):
            result = self.transport.request("POST", self.url, json={
                "displayName": "eh_giandoria", "type": "Eventhouse", "description": MARKER,
            })
        self.assertEqual(result.headers["Location"], f"https://api.fabric.microsoft.com/v1/operations/{operation_id}")
        pending = json.loads(self.transport.pending_path.read_text())
        self.assertEqual(pending["items"], ["eh_giandoria"])

    def test_completes_async_definition_recovery(self) -> None:
        initial = self.response(None, 202)
        initial.headers["Location"] = "https://api.fabric.microsoft.com/v1/operations/" + str(uuid4())
        initial.headers["Retry-After"] = "0"
        running = self.response({"status": "Succeeded"})
        running.headers["Location"] = initial.headers["Location"] + "/result"
        running.headers["Retry-After"] = "0"
        final = self.response({"definition": {"parts": []}})
        with patch.object(self.transport, "request", side_effect=[running, final]) as send:
            self.assertIs(self.transport.complete_response(initial, {}), final)
        self.assertEqual(send.call_count, 2)

    def test_definitions_have_unique_logical_ids_and_exact_parent(self) -> None:
        directory = Path(__file__).resolve().parents[1] / "fabric"
        expected = {**EXPECTED, "es_giandoria_business": "Eventstream"}
        logical_ids: dict[str, str] = {}
        for path in directory.glob("*/.platform"):
            platform = json.loads(path.read_text())
            name = platform["metadata"]["displayName"]
            self.assertEqual(platform["metadata"]["type"], expected[name])
            self.assertEqual(platform["metadata"]["description"], MARKER)
            logical_ids[name] = platform["config"]["logicalId"]
        self.assertEqual(set(logical_ids), set(expected))
        self.assertEqual(len(set(logical_ids.values())), len(expected))
        properties = json.loads((directory / "kqldb_giandoria.KQLDatabase" / "DatabaseProperties.json").read_text())
        self.assertEqual(properties["parentEventhouseItemId"], logical_ids["eh_giandoria"])
        schema = (directory / "kqldb_giandoria.KQLDatabase" / "DatabaseSchema.kql").read_text()
        self.assertIn("raw_event:string", schema)


if __name__ == "__main__":
    unittest.main()
