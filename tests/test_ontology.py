import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pyarrow as pa

from giandoria.ontology import (
    KEYS, RELATIONS, definition, enterprise_tables, identifier, table_name, upload_tables, validate_tables,
    verify_table_registration,
)
from giandoria.report_narratives import digest
from giandoria.fabric_deploy import RecordedRequests
from tests.test_showcase import ROOT, sample


class OntologyTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = sample()
        self.config = json.loads((ROOT / "config" / "business.json").read_text())
        self.tables = enterprise_tables(self.snapshot, self.config)
        self.stamp = digest(self.snapshot)

    def test_enterprise_tables_have_exact_grains_and_virtual_dates(self):
        self.assertEqual(set(self.tables), set(KEYS))
        self.assertEqual(self.tables["VirtualDay"].num_rows, 3)
        self.assertEqual(self.tables["SellOut"]["SoldKg"].to_pylist(), [10])
        self.assertEqual(self.tables["CompanyObservation"]["CashCents"].to_pylist(), [12000, 13000])
        self.assertTrue(pa.types.is_string(self.tables["VirtualDay"].schema.field("Date").type))
        self.assertEqual(self.tables["VirtualDay"]["Date"].to_pylist(),
                         ["2032-02-28", "2032-02-29", "2032-03-01"])
        self.assertNotIn("wall_ts", str(self.tables))

    def test_orphans_duplicates_and_missing_entities_fail(self):
        changed = dict(self.tables)
        changed["Product"] = pa.table({"Product": ["missing"]})
        with self.assertRaises(ValueError):
            validate_tables(changed)
        changed = dict(self.tables)
        changed["SellOut"] = pa.concat_tables([changed["SellOut"], changed["SellOut"]])
        with self.assertRaises(ValueError):
            validate_tables(changed)
        changed.pop("Product")
        with self.assertRaises(ValueError):
            validate_tables(changed)

    def test_definition_has_real_bindings_and_composite_relationship_keys(self):
        parts = definition("11111111-1111-1111-1111-111111111111",
                           "22222222-2222-2222-2222-222222222222", self.tables, self.stamp)
        self.assertEqual(sum("/DataBindings/" in p for p in parts), 8)
        self.assertEqual(sum("/Contextualizations/" in p for p in parts), len(RELATIONS))
        ids = [v["id"] for p, v in parts.items() if p.endswith("/definition.json")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(0 < int(value) < 2**63 for value in ids))
        entities = [v for p, v in parts.items() if p.startswith("EntityTypes/") and p.endswith("/definition.json")]
        property_names = [prop["name"] for entity in entities for prop in entity["properties"]]
        self.assertEqual(len(property_names), len(set(property_names)))
        for entity in entities:
            self.assertTrue(entity["$schema"].endswith("/entityType/1.0.0/schema.json"))
            self.assertEqual(entity["untypedProperties"], [])
            properties = {p["id"]: p for p in entity["properties"]}
            self.assertTrue(all(prop["redefines"] is None and prop["baseTypeNamespaceType"] is None
                                for prop in properties.values()))
            self.assertTrue(all(properties[key]["valueType"] in ("String", "BigInt")
                                for key in entity["entityIdParts"]))
        for path, part in parts.items():
            if "/DataBindings/" in path:
                self.assertIsNone(part["dataBindingConfiguration"]["sourceTableProperties"]["sourceSchema"])
            elif "/Contextualizations/" in path:
                self.assertIsNone(part["dataBindingTable"]["sourceSchema"])
        relationships = [v for p, v in parts.items() if "/Contextualizations/" in p]
        self.assertEqual(sum(len(v["sourceKeyRefBindings"]) == 4 for v in relationships), 4)
        self.assertNotIn("truth", json.dumps(parts).lower())
        self.assertNotIn("Last1Hour", json.dumps(parts))
        self.assertEqual(identifier("Product"), identifier("Product"))
        with self.assertRaises(ValueError):
            table_name("SellOut", "../../unsafe")

    def test_delta_upload_is_verified_immutable_and_replayable(self):
        remote = {}
        http = Mock()

        def request(method, url, _audience, **kwargs):
            self.assertEqual(_audience, "https://storage.azure.com/.default")
            if method == "PUT":
                self.assertEqual(kwargs["headers"]["If-None-Match"], "*")
                self.assertNotIn(url, remote)
                remote[url] = kwargs["body"]
                return Mock(status_code=201)
            return Mock(status_code=200 if url in remote else 404, content=remote.get(url, b""))

        http.request.side_effect = request
        with tempfile.TemporaryDirectory() as tmp:
            first = upload_tables(http, "workspace", "lakehouse", self.tables, self.stamp, Path(tmp))
            count = len(remote)
            second = upload_tables(http, "workspace", "lakehouse", self.tables, self.stamp, Path(tmp))
            self.assertEqual(first, second)
            self.assertEqual(count, len(remote))
            self.assertEqual(first["SellOut"]["rows"], 1)
            url = next(iter(remote))
            remote[url] = b"changed"
            with self.assertRaises(RuntimeError):
                upload_tables(http, "workspace", "lakehouse", self.tables, self.stamp, Path(tmp))

    def test_registered_sources_must_be_delta(self):
        transport = Mock(base="/v1/workspaces/workspace", deadline=float("inf"))
        for format_name in ("Delta", "delta"):
            transport.request.return_value.json.return_value = {"data": [{"name": "expected", "format": format_name}]}
            verify_table_registration(transport, {}, "lakehouse", {"entity": {"table": "expected"}})
        for format_name in ("Csv", None):
            transport.request.return_value.json.return_value = {"data": [{"name": "expected", "format": format_name}]}
            with self.assertRaises(RuntimeError):
                verify_table_registration(transport, {}, "lakehouse", {"entity": {"table": "expected"}})

    def test_preflight_only_accepts_verified_lakehouse_sql_companion(self):
        transport = object.__new__(RecordedRequests)
        transport.base = "/v1/workspaces/workspace"
        transport.expected = {"context": "Lakehouse"}
        transport.registry = {"context": "lakehouse"}
        transport.marker = "owned"
        transport.receipts = {}
        item = {"displayName": "context", "type": "SQLEndpoint", "id": "endpoint"}
        parent = {"displayName": "context", "type": "Lakehouse", "id": "lakehouse", "description": "owned",
                  "properties": {"sqlEndpointProperties": {"id": "endpoint"}}}
        transport.request = Mock(side_effect=[
            Mock(json=lambda: {"value": [item]}), Mock(json=lambda: parent)])
        transport.preflight({})
        parent["properties"]["sqlEndpointProperties"]["id"] = "other"
        transport.request = Mock(side_effect=[
            Mock(json=lambda: {"value": [item]}), Mock(json=lambda: parent)])
        with self.assertRaises(ValueError):
            transport.preflight({})
