import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from giandoria.data_agent import definition
from giandoria.decision_room import contract_digest, prepare
from giandoria.showcase import ROOT, model_definition
from tests.test_data_agent import snapshot


class DecisionRoomTests(unittest.TestCase):
    def test_canonical_contract_digest_is_order_independent_and_utf8(self):
        self.assertEqual(contract_digest({"z": "cacao", "a": 1}),
                         contract_digest({"a": 1, "z": "cacao"}))
        self.assertNotEqual(contract_digest({"a": 1}), contract_digest({"a": 2}))

    def fixture(self, root):
        local = root / ".local"
        local.mkdir()
        (root / "config").mkdir()
        (root / "apps" / "giandoria-decision-room" / "packages" / "shared" / "src").mkdir(parents=True)
        (root / "apps" / "giandoria-decision-room" / "rayfin").mkdir()
        config = json.loads((ROOT / "config" / "business.json").read_text())
        company = snapshot()
        workspace, model, agent = str(uuid4()), str(uuid4()), str(uuid4())
        files = {
            "showcase-snapshot.json": company,
            "data-agent.json": {"workspaceId": workspace, "modelId": model, "agentId": agent},
            "sm_giandoria_showcase-readback.json": {"model.bim": model_definition(company, config)},
            "data-agent-readback.json": definition(workspace, model),
            "showcase-verification.json": {"modelId": model, "items": {
                "rp_giandoria_commercial": str(uuid4()), "rp_giandoria_operations": str(uuid4())}},
            "ontology-verification.json": {"snapshotDigest": contract_digest(company), "ontologyId": str(uuid4())},
        }
        (root / "config" / "business.json").write_text(json.dumps(config))
        for name, value in files.items():
            (local / name).write_text(json.dumps(value))
        return files

    def test_provenance_uses_verified_sources_and_preserves_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = self.fixture(root)
            env = root / "apps" / "giandoria-decision-room" / "rayfin" / ".env"
            env.write_text("RAYFIN_PUBLIC_SERVICE_MODE=rayfin\nGIANDORIA_MODEL_ID=stale\n")
            context = prepare(root)
            generated = env.read_text()
            self.assertEqual(generated.count("GIANDORIA_MODEL_ID="), 1)
            self.assertIn(f"GIANDORIA_MODEL_ID={files['data-agent.json']['modelId']}", generated)
            self.assertIn("RAYFIN_PUBLIC_SERVICE_MODE=rayfin", generated)
            self.assertEqual(context["throughDate"], files["showcase-snapshot.json"]["throughDate"])
            prepare(root)
            self.assertEqual(env.read_text(), generated)
            self.assertNotIn("truth", json.dumps(context).lower())

    def test_different_model_or_ontology_snapshot_blocks_preparation(self):
        for receipt in ("showcase-verification.json", "ontology-verification.json"):
            with self.subTest(receipt=receipt), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                files = self.fixture(root)
                key = "modelId" if receipt.startswith("showcase") else "snapshotDigest"
                files[receipt][key] = "different"
                (root / ".local" / receipt).write_text(json.dumps(files[receipt]))
                with self.assertRaises(ValueError):
                    prepare(root)
                self.assertFalse((root / "apps" / "giandoria-decision-room" / "packages" /
                                  "shared" / "src" / "source-context.ts").exists())
