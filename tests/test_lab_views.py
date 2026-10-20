import unittest
from pathlib import Path
from unittest.mock import Mock

from giandoria.fabric_deploy import RecordedRequests
from giandoria.lab_views import ITEMS, PANELS, definitions

ROOT = Path(__file__).resolve().parents[1]


class LabViewsTests(unittest.TestCase):
    def test_dashboard_and_queryset_share_source_owned_queries(self):
        documents = definitions(ROOT, "https://demo.kusto.fabric.microsoft.com", "database")
        dashboard = documents["rt_giandoria"]
        queryset = documents["qs_giandoria"]["queryset"]
        self.assertEqual(set(documents), set(ITEMS))
        self.assertEqual(dashboard["autoRefresh"]["defaultInterval"], "10s")
        self.assertEqual(len(dashboard["tiles"]), 15)
        self.assertEqual({p["name"] for p in dashboard["pages"]},
                         {"Overview", "Sales", "Operations", "Finance", "Diagnostics"})
        self.assertEqual([q["text"] for q in dashboard["queries"]], [q["content"] for q in queryset["tabs"]])
        self.assertEqual(len({q["id"] for q in dashboard["queries"]}), 15)
        self.assertEqual({t["queryRef"]["queryId"] for t in dashboard["tiles"]},
                         {q["id"] for q in dashboard["queries"]})
        self.assertTrue(all(t["pageId"] in {p["id"] for p in dashboard["pages"]} for t in dashboard["tiles"]))
        self.assertEqual(documents, definitions(ROOT, "https://demo.kusto.fabric.microsoft.com", "database"))

    def test_history_uses_simulation_clock_and_live_uses_wall_clock(self):
        history = (ROOT / "fabric" / "queries" / "business-history.kql").read_text()
        live = (ROOT / "fabric" / "queries" / "live-flow.kql").read_text()
        self.assertIn("simlocaldate", history)
        self.assertNotIn("ago(", history)
        self.assertIn("wall_ts > ago(15m)", live)
        for query in (history, live):
            self.assertIn("by event_id", query)
            self.assertIn("bronze_business", query)
        for document in definitions(ROOT, "https://demo.kusto.fabric.microsoft.com", "database").values():
            self.assertNotIn("bronze_truth", str(document))

    def test_wall_clock_is_isolated_from_business_pages(self):
        for name, _, page, _ in PANELS:
            text = (ROOT / "fabric" / "queries" / f"{name}.kql").read_text()
            with self.subTest(query=name):
                self.assertIn('run_id == "business-demo-001"', text)
                if page != "Diagnostics":
                    for forbidden in ("wall_ts", "now(", "ago(", "ingestion_time(", "event.speed"):
                        self.assertNotIn(forbidden, text)
                    self.assertTrue("sim_ts" in text or "simlocaldate" in text)

    def test_visible_labels_and_date_columns_are_english(self):
        dashboard = definitions(ROOT, "https://demo.kusto.fabric.microsoft.com", "database")["rt_giandoria"]
        self.assertEqual(dashboard["title"], "Giandoria - business performance in virtual time")
        self.assertEqual([tile["title"] for tile in dashboard["tiles"]], [
            "Company state - latest virtual instant",
            "Sales, production and shipments (kg) - complete virtual days",
            "Strategic decisions - virtual time (UTC)",
            "Sales by channel (kg) - 90 complete virtual days",
            "Channel mix (kg) - 90 complete virtual days",
            "Product mix (kg) - 90 complete virtual days",
            "Territory mix (kg) - 90 complete virtual days",
            "Stock, backlog and WIP (kg) - last daily virtual observation, 90 days",
            "Sales, production and shipments (kg) - 90 complete virtual days",
            "Cash, receivables and payables (EUR) - last daily virtual observation, 90 days",
            "Revenue, purchases and conversion (EUR) - 90 complete virtual days",
            "Revenue, purchases and conversion (EUR) - complete virtual months",
            "Technical health - last REAL update, not business time",
            "Event arrivals - REAL UTC time, not business performance",
            "Latest business activity - virtual time (UTC)",
        ])
        for name in ("company-now", "latest-events"):
            text = (ROOT / "fabric" / "queries" / f"{name}.kql").read_text()
            self.assertIn("virtual_date_rome=", text)
            self.assertNotIn("giorno_virtuale", text)
        for name in ("company-now", "lab-health"):
            text = (ROOT / "fabric" / "queries" / f"{name}.kql").read_text()
            self.assertIn("virtual_time_utc=", text)
            self.assertNotIn("tempo_virtuale", text)

    def test_complete_periods_follow_virtual_observation_not_latest_sale(self):
        for name in ("business-history", "channels", "sales-trend", "products", "territories",
                     "operations-trend", "recent-business", "finance-balances", "finance-flows"):
            text = (ROOT / "fabric" / "queries" / f"{name}.kql").read_text()
            with self.subTest(query=name):
                self.assertIn('event_type == "world.business.observed"', text)
                self.assertIn("simlocaldate", text)
                self.assertIn("< end_day", text)
                if name != "business-history":
                    self.assertIn(">= end_day - 90d", text)
                self.assertTrue("by event_id" in text or "arg_max(sequence, *) by sim_day" in text)
        monthly = (ROOT / "fabric" / "queries" / "monthly-finance.kql").read_text()
        self.assertIn("startofmonth(todatetime(event.simlocaldate))", monthly)
        self.assertIn("< end_month", monthly)

    def test_balances_are_latest_snapshots_not_summed(self):
        for name in ("operations-trend", "finance-balances"):
            text = (ROOT / "fabric" / "queries" / f"{name}.kql").read_text()
            self.assertIn("arg_max(sequence, *) by sim_day", text)
            self.assertNotIn("sum(", text)

    def test_views_reject_foreign_endpoints(self):
        for endpoint in ("http://demo.kusto.fabric.microsoft.com", "https://foreign.invalid",
                         "https://demo.kusto.fabric.microsoft.com/other"):
            with self.assertRaises(ValueError):
                definitions(ROOT, endpoint, "database")

    def test_completed_fabric_creation_accepts_201(self):
        response = Mock(status_code=201, content=b"{}")
        response.json.return_value = {"id": "created"}
        transport = object.__new__(RecordedRequests)
        self.assertIs(transport.complete_response(response, {}), response)


if __name__ == "__main__":
    unittest.main()
