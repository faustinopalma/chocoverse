import base64
import json
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from azure.core.credentials import AccessToken

from giandoria.data_agent import SCOPE
from giandoria.data_agent_auth import (
    EXCHANGE_SCOPE, POWER_BI_SCOPE, FabricApplicationCredential, federated_credential, probe, token_identity, validate_config,
)


def config():
    result: dict = {field: str(uuid4()) for field in (
        "tenantId", "clientId", "principalId", "managedIdentityClientId",
        "workspaceId", "agentId", "modelId", "originalWorkspaceId",
    )}
    result.update(role="Contributor", contract={"throughDate": "2034-09-03"},
                  probeExpected={"sold_kg": 10, "revenue_eur": 100})
    return result


def token(settings, **changes):
    claims = {"tid": settings["tenantId"], "oid": settings["principalId"], "appid": settings["clientId"],
              "aud": "https://api.fabric.microsoft.com", **changes}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return AccessToken(f"header.{payload}.signature", 9999999999)


class DataAgentAuthTests(unittest.TestCase):
    def test_config_rejects_truth_workspace_invalid_ids_and_privileged_roles(self):
        settings = config()
        validate_config(settings)
        for change in ({"workspaceId": settings["originalWorkspaceId"]}, {"clientId": "not-a-guid"},
                       {"role": "Admin"}, {"role": "Viewer"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_config({**settings, **change})

    def test_token_identity_must_be_dedicated_app_not_managed_identity_or_user(self):
        settings = config()
        self.assertEqual(token_identity(token(settings), settings)["oid"], settings["principalId"])
        self.assertEqual(token_identity(token(settings, aud="https://analysis.windows.net/powerbi/api"),
                                        settings, POWER_BI_SCOPE)["oid"], settings["principalId"])
        for changes in ({"oid": str(uuid4())}, {"appid": str(uuid4())}, {"tid": str(uuid4())},
                        {"aud": "https://graph.microsoft.com"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                token_identity(token(settings, **changes), settings)

    def test_application_scope_is_restricted_and_tokens_are_validated(self):
        settings, underlying = config(), Mock()
        underlying.get_token.return_value = token(settings)
        credential = FabricApplicationCredential(underlying, settings)
        self.assertEqual(credential.get_token(SCOPE), underlying.get_token.return_value)
        for scope in ("https://graph.microsoft.com/.default", EXCHANGE_SCOPE):
            with self.assertRaises(ValueError):
                credential.get_token(scope)
        with self.assertRaises(ValueError):
            credential.get_token(SCOPE, tenant_id=str(uuid4()))
        underlying.get_token.assert_called_once_with(SCOPE)

    def test_federation_requests_exchange_assertion_from_only_supplied_managed_identity(self):
        managed, settings = Mock(), config()
        managed.get_token.return_value = AccessToken("ephemeral-assertion", 123)
        with patch("giandoria.data_agent_auth.ClientAssertionCredential") as factory:
            with federated_credential(managed, settings) as credential:
                self.assertIsInstance(credential, FabricApplicationCredential)
                self.assertEqual(factory.call_args.args[:2], (settings["tenantId"], settings["clientId"]))
                self.assertEqual(factory.call_args.args[2](), "ephemeral-assertion")
            managed.get_token.assert_called_once_with(EXCHANGE_SCOPE)
            factory.return_value.__exit__.assert_called_once()

    def test_probe_denies_original_workspace_checks_only_enterprise_items_and_persists_answer(self):
        settings, store = config(), Mock()
        with patch("giandoria.data_agent_auth.federated_credential") as federation, \
                patch("giandoria.data_agent_auth.RecordedHttp") as http_factory, \
                patch("giandoria.data_agent_auth.DataAgentClient") as client, \
                patch("giandoria.data_agent_auth.dax", return_value=[{"[sold_kg]": 10, "[revenue_eur]": 100}]):
            federation.return_value.__enter__.return_value = Mock()
            http = http_factory.return_value
            http.request.side_effect = [
                Mock(status_code=403),
                Mock(json=lambda: {"value": [{"id": settings["agentId"]}, {"id": settings["modelId"]}]}),
            ]
            http.audit = []
            client.return_value.ask.return_value = {
                "text": 'Snapshot through 2034-09-03, not live.\n{"sold_kg":10,"revenue_eur":100}'}
            result = probe(store, Mock(), settings)
            self.assertFalse(result["appliedToLab"])
            self.assertEqual(result["originalWorkspaceDenied"], 403)
            self.assertEqual(http.request.call_args_list[0].kwargs["expected"], (401, 403, 404))
            self.assertEqual(store.put_json.call_args.args[0], "lab-state")
            self.assertTrue(store.put_json.call_args.args[1].startswith("data-agent-auth-check/"))
            client.return_value.ask.assert_called_once()

    def test_probe_refuses_unexpected_sources_before_billable_query(self):
        settings = config()
        with patch("giandoria.data_agent_auth.federated_credential"), \
                patch("giandoria.data_agent_auth.RecordedHttp") as http_factory, \
                patch("giandoria.data_agent_auth.DataAgentClient") as client, \
                patch("giandoria.data_agent_auth.dax", return_value=[{"[sold_kg]": 10, "[revenue_eur]": 100}]):
            http_factory.return_value.request.side_effect = [
                Mock(status_code=404), Mock(json=lambda: {"value": [{"id": str(uuid4())}]}),
            ]
            with self.assertRaises(ValueError):
                probe(Mock(), Mock(), settings)
            client.assert_not_called()

    def test_probe_preserves_answered_evidence_and_fails_for_invented_numbers_or_cutoff(self):
        settings = config()
        for text in ('Snapshot 2034-09-03 {"sold_kg":99,"revenue_eur":100}',
                     'Snapshot 2025-01-31 {"sold_kg":10,"revenue_eur":100}', "No query access"):
            with self.subTest(text=text), patch("giandoria.data_agent_auth.federated_credential"), \
                    patch("giandoria.data_agent_auth.RecordedHttp") as http_factory, \
                    patch("giandoria.data_agent_auth.DataAgentClient") as client, \
                    patch("giandoria.data_agent_auth.dax", return_value=[{"[sold_kg]": 10, "[revenue_eur]": 100}]):
                http = http_factory.return_value
                http.request.side_effect = [
                    Mock(status_code=401),
                    Mock(json=lambda: {"value": [{"id": settings["agentId"]}, {"id": settings["modelId"]}]}),
                ]
                http.audit = []
                client.return_value.ask.return_value = {"text": text}
                store = Mock()
                with self.assertRaises((ValueError, RuntimeError)):
                    probe(store, Mock(), settings)
                self.assertEqual(store.put_json.call_args.args[2]["state"], "Answered")


if __name__ == "__main__":
    unittest.main()
