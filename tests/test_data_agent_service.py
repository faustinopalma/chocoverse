import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from giandoria.data_agent_service import (
    WORKSPACE_MARKER, WORKSPACE_NAME, ensure_role, ensure_workspace,
)


def response(value):
    return Mock(json=lambda: value)


class DataAgentServiceTests(unittest.TestCase):
    def test_workspace_creation_uses_only_original_capacity_and_records_identity(self):
        parent, capacity, created = str(uuid4()), str(uuid4()), str(uuid4())
        original = {"id": parent}
        workspace = {"id": created, "displayName": WORKSPACE_NAME, "description": WORKSPACE_MARKER,
                     "capacityId": capacity}
        http = Mock()
        http.request.side_effect = [
            response({"id": parent, "displayName": "ws-giandoria-demo", "capacityId": capacity}),
            response({"value": []}), response(workspace), response(workspace),
        ]
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory)
            self.assertEqual(ensure_workspace(http, original, local)["id"], created)
            self.assertEqual(json.loads((local / "workspace.json").read_text())["id"], created)
        posted = json.loads(http.request.call_args_list[2].kwargs["body"])
        self.assertEqual(posted["capacityId"], capacity)
        self.assertEqual(posted["description"], WORKSPACE_MARKER)

    def test_workspace_rejects_unrecorded_names_and_wrong_capacity(self):
        parent, capacity, created = str(uuid4()), str(uuid4()), str(uuid4())
        http = Mock()
        http.request.side_effect = [
            response({"displayName": "ws-giandoria-demo", "capacityId": capacity}),
            response({"value": [{"id": created, "displayName": WORKSPACE_NAME}]}),
        ]
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            ensure_workspace(http, {"id": parent}, Path(directory))
        self.assertTrue(all(c.args[0] == "GET" for c in http.request.call_args_list))

    def test_role_is_documented_minimum_and_never_silently_escalated(self):
        principal = str(uuid4())
        role = {"id": str(uuid4()), "principal": {"id": principal}, "role": "Contributor"}
        http = Mock()
        http.request.side_effect = [response({"value": []}), response({}), response({"value": [role]})]
        ensure_role(http, str(uuid4()), principal)
        self.assertEqual(json.loads(http.request.call_args_list[1].kwargs["body"])["role"], "Contributor")
        http = Mock()
        http.request.return_value = response({"value": [{**role, "role": "Viewer"}]})
        with self.assertRaises(ValueError):
            ensure_role(http, str(uuid4()), principal)
        self.assertEqual(http.request.call_count, 1)

    def test_viewer_upgrade_requires_explicit_flag_and_cannot_upgrade_admin_or_member(self):
        principal = str(uuid4())
        role = {"id": str(uuid4()), "principal": {"id": principal}, "role": "Viewer"}
        http = Mock()
        http.request.side_effect = [
            response({"value": [role]}), response({}), response({"value": [{**role, "role": "Contributor"}]}),
        ]
        ensure_role(http, str(uuid4()), principal, upgrade_viewer=True)
        self.assertEqual(http.request.call_args_list[1].args[0], "PATCH")
        for existing in ("Member", "Admin"):
            http = Mock()
            http.request.return_value = response({"value": [{**role, "role": existing}]})
            with self.assertRaises(ValueError):
                ensure_role(http, str(uuid4()), principal, upgrade_viewer=True)


if __name__ == "__main__":
    unittest.main()
