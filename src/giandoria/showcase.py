"""Build and publish an as-of Power BI teaching model and two thin PBIR reports."""

import argparse
import base64
import calendar
import json
import time
import zlib
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from azure.identity import AzureCliCredential

from .business_verify import query
from .cloud_io import RecordedHttp
from .fabric_deploy import RecordedRequests
from .report_narratives import GUIDANCE

ROOT = Path(__file__).resolve().parents[2]
MARKER = "Giandoria demo; managed by showcase; synthetic enterprise snapshot."
ITEMS = {"sm_giandoria_showcase": "SemanticModel",
         "rp_giandoria_commercial": "Report", "rp_giandoria_operations": "Report"}
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
FACTS = {
    "Sales": [("Date", "dateTime"), ("Channel", "string"), ("Product", "string"),
              ("Territory", "string"), ("SoldKg", "int64")],
    "Production": [("Date", "dateTime"), ("Product", "string"), ("StartedKg", "int64"),
                   ("ReleasedKg", "int64"), ("ShippedKg", "int64")],
    "Finance": [("Date", "dateTime"), ("RevenueCents", "int64"), ("PurchaseCents", "int64"),
                ("ConversionCents", "int64"), ("RetailCashCents", "int64"),
                ("CollectionCents", "int64"), ("PaymentCents", "int64")],
    "Balances": [("Date", "dateTime"), ("FinishedKg", "int64"), ("BacklogKg", "int64"),
                 ("WipKg", "int64"), ("CashCents", "int64"), ("ReceivableCents", "int64"),
                 ("PayableCents", "int64")],
}


def stable_id(name: str) -> str:
    return uuid5(NAMESPACE_URL, f"giandoria:showcase:{name}").hex[:20]


def imported_table(name: str, columns: list[tuple[str, str]], rows: list[list],
                   *, hidden: bool = False) -> dict:
    """Embed a bounded synthetic snapshot, with no external refresh credentials."""
    payload = base64.b64encode(zlib.compress(json.dumps(rows, separators=(",", ":")).encode())[2:-4]).decode()
    types = {"dateTime": "type date", "int64": "Int64.Type", "string": "type text"}
    transforms = ", ".join(f'{{"{n}", {types[t]}}}' for n, t in columns)
    expression = (
        f'let Rows = Json.Document(Binary.Decompress(Binary.FromText("{payload}", BinaryEncoding.Base64), '
        'Compression.Deflate)), '
        f'T = Table.FromRows(Rows, {json.dumps([n for n, _ in columns]).replace("[", "{").replace("]", "}")}) '
        f'in Table.TransformColumnTypes(T, {{{transforms}}}, "en-US")'
    )
    result = {
        "name": name, "isHidden": hidden,
        "columns": [{"name": n, "dataType": t, "sourceColumn": n, "summarizeBy": "none",
                     **({"formatString": "yyyy-MM-dd"} if t == "dateTime" else {})} for n, t in columns],
        "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}],
    }
    return result


def measures() -> list[dict]:
    sales_scope = "ISCROSSFILTERED('Product') || ISCROSSFILTERED('Channel') || ISCROSSFILTERED('Territory')"
    rows = [
        ("Sold kg", "SUM('Sales'[SoldKg])", "#,0", "Sales", "Additive sell-out quantity, not invoiced revenue."),
        ("Sold kg PY", "CALCULATE([Sold kg], DATEADD('Date'[Date], -1, YEAR))", "#,0", "Virtual time",
         "Same selected virtual calendar dates one year earlier; no real-clock dependency."),
        ("Sales YoY %", "DIVIDE([Sold kg] - [Sold kg PY], [Sold kg PY])", "0.0%;-0.0%;0.0%", "Virtual time",
         "Blank when the prior-period denominator is absent or zero."),
        ("Sales YTD kg", "TOTALYTD([Sold kg], 'Date'[Date])", "#,0", "Virtual time", "Virtual calendar year to date."),
        ("Sales rolling 30d kg",
         "CALCULATE([Sold kg], DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -30, DAY))",
         "#,0", "Virtual time", "Trailing thirty virtual calendar days ending at the current context's maximum date."),
        ("Channel share %", "DIVIDE([Sold kg], CALCULATE([Sold kg], REMOVEFILTERS('Channel')))",
         "0.0%", "Mix", "Share of all channels; retains date, product and territory filters."),
        ("Channel rank", "IF(ISINSCOPE('Channel'[Channel]), RANKX(ALLSELECTED('Channel'[Channel]), [Sold kg], , DESC, DENSE))",
         "0", "Mix", "Dense rank within selected channels; blank on totals."),
        ("Revenue EUR", f"IF({sales_scope}, BLANK(), DIVIDE(SUM('Finance'[RevenueCents]), 100))",
         "#,0.00", "Finance", "Enterprise revenue postings; cannot be allocated to sales product/channel/territory."),
        ("Purchases EUR", f"IF({sales_scope}, BLANK(), DIVIDE(SUM('Finance'[PurchaseCents]), 100))",
         "#,0.00", "Finance", "Purchases, not COGS."),
        ("Conversion EUR", f"IF({sales_scope}, BLANK(), DIVIDE(SUM('Finance'[ConversionCents]), 100))",
         "#,0.00", "Finance", "Conversion payments, not a full cost allocation."),
        ("Cash movement EUR",
         f"IF({sales_scope}, BLANK(), DIVIDE(SUM('Finance'[RetailCashCents]) + SUM('Finance'[CollectionCents]) "
         "- SUM('Finance'[PaymentCents]) - SUM('Finance'[ConversionCents]), 100))",
         "#,0.00", "Finance", "Signed retail receipts + trade collections - supplier payments - conversion."),
        ("Cash component EUR",
         f"IF({sales_scope}, BLANK(), SWITCH(SELECTEDVALUE('Cash flow'[Component]), "
         '"Retail receipts", DIVIDE(SUM(\'Finance\'[RetailCashCents]), 100), '
         '"Trade collections", DIVIDE(SUM(\'Finance\'[CollectionCents]), 100), '
         '"Supplier payments", -DIVIDE(SUM(\'Finance\'[PaymentCents]), 100), '
         '"Conversion payments", -DIVIDE(SUM(\'Finance\'[ConversionCents]), 100), [Cash movement EUR]))',
         "#,0.00", "Finance", "Disconnected waterfall categories map to signed cash flows, not profit."),
        ("Cash as observed EUR",
         f"VAR LastDay = MAX('Balances'[Date]) RETURN IF({sales_scope}, BLANK(), "
         "DIVIDE(CALCULATE(SUM('Balances'[CashCents]), KEEPFILTERS('Balances'[Date] = LastDay)), 100))",
         "#,0.00", "Snapshots", "Last available observation inside selected dates, not summed over days or carried forward."),
        ("Receivables as observed EUR",
         f"VAR LastDay = MAX('Balances'[Date]) RETURN IF({sales_scope}, BLANK(), "
         "DIVIDE(CALCULATE(SUM('Balances'[ReceivableCents]), KEEPFILTERS('Balances'[Date] = LastDay)), 100))",
         "#,0.00", "Snapshots", "Semi-additive: total is the last observed balance within context."),
        ("Payables as observed EUR",
         f"VAR LastDay = MAX('Balances'[Date]) RETURN IF({sales_scope}, BLANK(), "
         "DIVIDE(CALCULATE(SUM('Balances'[PayableCents]), KEEPFILTERS('Balances'[Date] = LastDay)), 100))",
         "#,0.00", "Snapshots", "Semi-additive, enterprise grain."),
        ("Finished as observed kg",
         f"VAR LastDay = MAX('Balances'[Date]) RETURN IF({sales_scope}, BLANK(), "
         "CALCULATE(SUM('Balances'[FinishedKg]), KEEPFILTERS('Balances'[Date] = LastDay)))",
         "#,0", "Snapshots", "Last sampled finished stock, not stock assigned to a SKU."),
        ("Backlog as observed kg",
         f"VAR LastDay = MAX('Balances'[Date]) RETURN IF({sales_scope}, BLANK(), "
         "CALCULATE(SUM('Balances'[BacklogKg]), KEEPFILTERS('Balances'[Date] = LastDay)))",
         "#,0", "Snapshots", "Last sampled enterprise backlog."),
        ("Observation days", f"IF({sales_scope}, BLANK(), COUNTROWS('Balances'))", "#,0", "Snapshots",
         "Sampling coverage; absent balance dates remain absent."),
        ("Selected virtual days", "COUNTROWS('Date')", "#,0", "Virtual time", "Calendar days, never real elapsed time."),
        ("Started kg", "IF(ISCROSSFILTERED('Channel') || ISCROSSFILTERED('Territory'), BLANK(), SUM('Production'[StartedKg]))",
         "#,0", "Operations", "Production starts at date x product grain."),
        ("Released kg", "IF(ISCROSSFILTERED('Channel') || ISCROSSFILTERED('Territory'), BLANK(), SUM('Production'[ReleasedKg]))",
         "#,0", "Operations", "Quality releases, which can follow starts in a later period."),
        ("Shipped kg", "IF(ISCROSSFILTERED('Channel') || ISCROSSFILTERED('Territory'), BLANK(), SUM('Production'[ShippedKg]))",
         "#,0", "Operations", "Dispatches aggregated by date and product; not channel-grained in this fact."),
        ("Daily sales 30d kg", "DIVIDE([Sales rolling 30d kg], COUNTROWS(DATESINPERIOD('Date'[Date], MAX('Date'[Date]), -30, DAY)))",
         "#,0.0", "Scenario", "Average includes no-sale calendar days; truncated to available calendar at start of history."),
        ("Scenario cover days", "SELECTEDVALUE('Cover policy'[Days], 3)", "0", "Scenario",
         "Disconnected teaching parameter; default three days. Does not change the simulator."),
        ("Illustrative target kg", f"IF({sales_scope}, BLANK(), [Daily sales 30d kg] * [Scenario cover days])",
         "#,0.0", "Scenario", "Illustrative enterprise stock target, not an optimized plan."),
        ("Illustrative gap kg", "IF(NOT ISBLANK([Finished as observed kg]), [Illustrative target kg] - [Finished as observed kg])",
         "#,0.0;-#,0.0", "Scenario", "Target minus last sampled stock; positive means below illustrative target."),
        ("Snapshot label", '"Snapshot through " & FORMAT(MAX(\'Snapshot\'[ThroughDate]), "yyyy-MM-dd") & " (virtual Rome date)"',
         "", "Provenance", "Common complete-day cutoff for all facts; not live."),
    ]
    return [{"name": n, "expression": e, **({"formatString": f} if f else {}),
             "displayFolder": folder, "description": d}
            for n, e, f, folder, d in rows]


def model_definition(snapshot: dict, config: dict) -> dict:
    end = date.fromisoformat(snapshot["throughDate"])
    start = date.fromisoformat(snapshot["firstDate"])
    dates = []
    current = start
    while current <= end:
        dates.append([current.isoformat(), current.year, current.month, current.strftime("%b"),
                      current.strftime("%Y-%m"), current.year * 100 + current.month,
                      current.isoweekday(), current.strftime("%A")])
        current += timedelta(days=1)
    tables = [
        imported_table("Date", [("Date", "dateTime"), ("Year", "int64"), ("MonthNumber", "int64"),
                                ("Month", "string"), ("YearMonth", "string"), ("MonthIndex", "int64"),
                                ("WeekdayNumber", "int64"), ("Weekday", "string")], dates),
        imported_table("Channel", [("Channel", "string")], [[c] for c in config["channels"]]),
        imported_table("Product", [("Product", "string"), ("Line", "string")],
                       [[p, v["line"]] for p, v in config["products"].items()]),
        imported_table("Territory", [("Territory", "string")], [[t] for t in config["territories"]]),
        imported_table("Cover policy", [("Days", "int64")], [[n] for n in (2, 3, 4, 5, 7)]),
        imported_table("Cash flow", [("Component", "string"), ("Order", "int64")],
                       [[name, i] for i, name in enumerate(
                           ("Retail receipts", "Trade collections", "Supplier payments", "Conversion payments"))]),
        imported_table("Snapshot", [("ThroughDate", "dateTime"), ("Sequence", "int64")],
                       [[snapshot["throughDate"], snapshot["sequence"]]]),
        imported_table("Metrics", [("Placeholder", "int64")], [[0]]),
    ]
    tables[0]["dataCategory"] = "Time"
    tables[0]["columns"][0]["isKey"] = True
    for column in tables[0]["columns"]:
        if column["name"] in ("MonthNumber", "MonthIndex", "WeekdayNumber"):
            column["isHidden"] = True
        if column["name"] in ("Month", "YearMonth", "Weekday"):
            column["sortByColumn"] = {"Month": "MonthNumber", "YearMonth": "MonthIndex", "Weekday": "WeekdayNumber"}[column["name"]]
    tables[0]["hierarchies"] = [{"name": "Virtual calendar", "levels": [
        {"name": "Year", "ordinal": 0, "column": "Year"},
        {"name": "Month", "ordinal": 1, "column": "YearMonth"},
        {"name": "Date", "ordinal": 2, "column": "Date"}]}]
    tables[5]["columns"][0]["sortByColumn"] = "Order"
    tables[5]["columns"][1]["isHidden"] = True
    tables[-1]["columns"][0]["isHidden"] = True
    tables[-1]["measures"] = measures()
    relations = []
    for name, columns in FACTS.items():
        table = imported_table(name, columns, snapshot["tables"][name], hidden=True)
        tables.append(table)
        dimensions = ["Date"] + (["Channel", "Product", "Territory"] if name == "Sales"
                                 else ["Product"] if name == "Production" else [])
        for dimension in dimensions:
            relations.append({"name": f"{name}_{dimension}", "fromTable": name, "fromColumn": dimension,
                              "toTable": dimension, "toColumn": dimension, "fromCardinality": "many",
                              "toCardinality": "one", "crossFilteringBehavior": "oneDirection"})
    return {"name": "sm_giandoria_showcase", "compatibilityLevel": 1600, "model": {
        "culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "tables": tables, "relationships": relations,
        "annotations": [{"name": "GiandoriaSnapshot", "value": json.dumps({
            k: snapshot[k] for k in ("run", "firstDate", "throughDate", "sequence")})}],
    }}


def projection(table: str, field: str, *, measure: bool = False) -> dict:
    return {"field": {"Measure" if measure else "Column": {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": field}},
        "queryRef": f"{table}.{field}", "nativeQueryRef": field}


def visual(name: str, kind: str, title: str, roles: dict[str, list[tuple[str, str]]],
           x: int, y: int, width: int, height: int) -> dict:
    return {"$schema": f"{SCHEMA}/visualContainer/2.1.0/schema.json", "name": stable_id(name),
            "position": {"x": x, "y": y, "z": y + x, "width": width, "height": height},
            "visual": {"visualType": kind, "query": {"queryState": {
                role: {"projections": [projection(t, c, measure=t == "Metrics") for t, c in fields]}
                for role, fields in roles.items()}},
                "visualContainerObjects": {"title": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": "'" + title.replace("'", "''") + "'"}}}}}]},
                "drillFilterOtherVisuals": True}}


def text_box(name: str, title: str, paragraphs: list[str], x: int, y: int, width: int, height: int) -> dict:
    item = visual(name, "textbox", title, {}, x, y, width, height)
    item["visual"].pop("query")
    item["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": {"fontFamily": "Segoe UI", "fontSize": "12pt"}}]}
        for text in paragraphs
    ]}}]}
    return item


def report_definition(model_id: str, commercial: bool) -> dict[str, dict]:
    from .report_summaries import summary_objects
    m = lambda name: ("Metrics", name)
    d = ("Date", "YearMonth")
    if commercial:
        pages = [
            ("Virtual calendar", [
                ("lineChart", "Sell-out vs prior virtual year", {"Category": [d], "Y": [m("Sold kg"), m("Sold kg PY")]}),
                ("lineChart", "Virtual YTD and rolling 30-day volume", {"Category": [("Date", "Date")], "Y": [m("Sales YTD kg"), m("Sales rolling 30d kg")]}),
                ("pivotTable", "Context-aware totals: month, volume and growth", {"Rows": [d], "Values": [m("Sold kg"), m("Sold kg PY"), m("Sales YoY %")]}),
            ]),
            ("Mix and concentration", [
                ("clusteredBarChart", "Channel volume: click to cross-filter", {"Category": [("Channel", "Channel")], "Y": [m("Sold kg")]}),
                ("donutChart", "Product mix (sell-out kg, not revenue)", {"Category": [("Product", "Product")], "Y": [m("Sold kg")]}),
                ("pivotTable", "Share denominator and selected-channel rank", {"Rows": [("Channel", "Channel")], "Values": [m("Sold kg"), m("Channel share %"), m("Channel rank")]}),
                ("scatterChart", "Channel portfolio: prior-year vs current kg; bubble = share",
                 {"Category": [("Channel", "Channel")], "X": [m("Sold kg PY")],
                  "Y": [m("Sold kg")], "Size": [m("Channel share %")]}),
            ]),
            ("Territory and seasonality", [
                ("columnChart", "Territory volume by virtual month", {"Category": [d], "Series": [("Territory", "Territory")], "Y": [m("Sold kg")]}),
                ("clusteredBarChart", "Weekday pattern in virtual Rome calendar", {"Category": [("Date", "Weekday")], "Y": [m("Sold kg")]}),
                ("pivotTable", "Product x territory: drill and filter context", {"Rows": [("Product", "Product")], "Columns": [("Territory", "Territory")], "Values": [m("Sold kg")]}),
            ]),
        ]
    else:
        pages = [
            ("Flows versus stocks", [
                ("lineChart", "Starts, releases and shipments are different flows", {"Category": [d], "Y": [m("Started kg"), m("Released kg"), m("Shipped kg")]}),
                ("lineChart", "Last sampled stock and backlog (not sums)", {"Category": [d], "Y": [m("Finished as observed kg"), m("Backlog as observed kg")]}),
                ("pivotTable", "Semi-additive totals and observation coverage", {"Rows": [d], "Values": [m("Finished as observed kg"), m("Observation days"), m("Selected virtual days")]}),
            ]),
            ("Cash versus revenue", [
                ("lineChart", "Revenue postings versus signed cash movement", {"Category": [d], "Y": [m("Revenue EUR"), m("Cash movement EUR")]}),
                ("clusteredColumnChart", "Purchases and conversion are not COGS", {"Category": [d], "Y": [m("Purchases EUR"), m("Conversion EUR")]}),
                ("pivotTable", "Last sampled balances: total is not a sum", {"Rows": [d], "Values": [m("Cash as observed EUR"), m("Receivables as observed EUR"), m("Payables as observed EUR")]}),
                ("waterfallChart", "Signed cash contributions - not a profit bridge",
                 {"Category": [("Cash flow", "Component")], "Y": [m("Cash component EUR")]}),
            ]),
            ("Stock policy sandbox", [
                ("slicer", "Illustrative cover days - does not control the simulator", {"Values": [("Cover policy", "Days")]}),
                ("lineChart", "Illustrative stock target vs last sampled stock", {"Category": [d], "Y": [m("Illustrative target kg"), m("Finished as observed kg")]}),
                ("pivotTable", "Scenario sensitivity, not an optimized production plan", {"Rows": [d], "Values": [m("Scenario cover days"), m("Daily sales 30d kg"), m("Illustrative target kg"), m("Illustrative gap kg")]}),
            ]),
        ]
    parts = {
        "definition.pbir": {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0", "datasetReference": {"byConnection": {
            "connectionString": f"semanticmodelid={model_id}"}}},
        "definition/report.json": {"$schema": f"{SCHEMA}/report/3.0.0/schema.json", "themeCollection": {}},
        "definition/version.json": {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
        "definition/pages/pages.json": {"$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [stable_id(p) for p, _ in pages], "activePageName": stable_id(pages[0][0])},
    }
    for page_name, charts in pages:
        page_id = stable_id(page_name)
        prefix = f"definition/pages/{page_id}"
        parts[f"{prefix}/page.json"] = {"$schema": f"{SCHEMA}/page/2.0.0/schema.json",
            "name": page_id, "displayName": page_name, "displayOption": "FitToWidth",
            "width": 1440, "height": 1930 if len(charts) == 4 else 1610}
        visuals = [
            visual(f"{page_name}:snapshot", "card", "Fixed enterprise snapshot - virtual time only",
                   {"Values": [m("Snapshot label")]}, 20, 10, 1000, 85),
            visual(f"{page_name}:date", "slicer", "Virtual year (select to compare complete periods)",
                   {"Values": [("Date", "Year")]}, 1040, 10, 380, 85),
        ]
        if commercial:
            visuals.extend([
                visual(f"{page_name}:channel", "slicer", "Channel", {"Values": [("Channel", "Channel")]}, 20, 100, 450, 120),
                visual(f"{page_name}:product", "slicer", "Product", {"Values": [("Product", "Product")]}, 490, 100, 450, 120),
                visual(f"{page_name}:territory", "slicer", "Territory", {"Values": [("Territory", "Territory")]}, 960, 100, 460, 120),
            ])
        visuals.append(text_box(f"{page_name}:guide", "KPI definitions - how to read this page",
                                [GUIDANCE[page_name]], 20, 1630 if len(charts) == 4 else 1310, 1400, 280))
        summary = text_box(f"{page_name}:narrative", "Smart narrative - current selection",
                           [], 20, 235, 1400, 390)
        summary["visual"]["objects"] = summary_objects(page_name)
        visuals.append(summary)
        for i, (kind, title, roles) in enumerate(charts):
            positions = [(20, 655, 690, 310), (730, 655, 690, 310),
                         (20, 985, 1400, 310), (20, 1315, 1400, 300)]
            visuals.append(visual(f"{page_name}:{i}", kind, title, roles, *positions[i]))
        for v in visuals:
            parts[f"{prefix}/visuals/{v['name']}/visual.json"] = v
    return parts


def extract_snapshot(http: RecordedHttp, fabric: dict, *, from_date: str | None = None) -> dict:
    endpoint, database = fabric["queryServiceUri"], fabric["databaseId"]
    anchor = query(http, endpoint, database, '''bronze_business
| where run_id == "business-demo-001" and event_type == "world.business.observed"
| top 1 by sequence desc
| project cutoff=format_datetime(todatetime(event.simlocaldate), "yyyy-MM-dd"), sequence''')
    if len(anchor) != 1:
        raise ValueError("A single enterprise observation is required to anchor the showcase.")
    cutoff, sequence = anchor[0]
    date.fromisoformat(cutoff)
    if from_date is not None:
        from_date = date.fromisoformat(from_date).isoformat()
        if date.fromisoformat(from_date) >= date.fromisoformat(cutoff):
            raise ValueError("Snapshot start must precede its exclusive virtual cutoff.")
    if type(sequence) is not int or sequence < 1:
        raise ValueError("Invalid showcase sequence anchor.")
    header = f"let cutoff=datetime({cutoff}); let upper_sequence=long({sequence});\n"
    tables = {}
    for name in FACTS:
        text = (ROOT / "fabric" / "showcase" / f"{name.lower()}.kql").read_text()
        if from_date is not None:
            text = text.replace("bronze_business\n", (
                f'bronze_business\n| where todatetime(event.simlocaldate) >= datetime({from_date})\n'
            ), 1)
        tables[name] = query(http, endpoint, database, header + text)
        if not tables[name]:
            raise ValueError(f"Showcase requires populated enterprise {name} facts.")
    first = min(row[0] for rows in tables.values() for row in rows)
    return {"run": "business-demo-001", "firstDate": first,
            "throughDate": (date.fromisoformat(cutoff) - timedelta(days=1)).isoformat(),
            "sequence": sequence, "tables": tables}


def validate_snapshot(snapshot: dict, config: dict) -> None:
    start, end = (date.fromisoformat(snapshot[k]) for k in ("firstDate", "throughDate"))
    if start > end or snapshot["run"] != "business-demo-001":
        raise ValueError("Invalid snapshot run or virtual-date range.")
    grains = {"Sales": 4, "Production": 2, "Finance": 1, "Balances": 1}
    for name, columns in FACTS.items():
        seen = set()
        for row in snapshot["tables"][name]:
            if len(row) != len(columns) or not start <= date.fromisoformat(row[0]) <= end:
                raise ValueError(f"{name} row violates the schema or virtual cutoff.")
            key = tuple(row[:grains[name]])
            if key in seen:
                raise ValueError(f"Duplicate {name} fact grain.")
            seen.add(key)
            for value, (column, kind) in zip(row, columns):
                if kind == "int64" and (type(value) is not int or value < 0 and column != "CashCents"):
                    raise ValueError(f"Invalid {name}.{column} quantity.")
            for column, allowed in (("Product", config["products"]), ("Channel", config["channels"]),
                                    ("Territory", config["territories"])):
                names = [n for n, _ in columns]
                if column in names and row[names.index(column)] not in allowed:
                    raise ValueError(f"Unmapped {name}.{column}; do not create an unknown member silently.")


def publish(transport: RecordedRequests, headers: dict, name: str, parts: dict[str, dict]) -> str:
    definition = {"parts": [{"path": path, "payloadType": "InlineBase64",
                            "payload": base64.b64encode(json.dumps(doc).encode()).decode()}
                           for path, doc in parts.items()]}
    item_id = transport.registry.get(name)
    path = f"/items/{item_id}/updateDefinition" if item_id else "/items"
    body: dict = {"definition": definition}
    if not item_id:
        body.update({"displayName": name, "type": ITEMS[name], "description": MARKER})
    response = transport.request("POST", f"https://api.fabric.microsoft.com{transport.base}{path}",
                                 headers=headers, json=body)
    response.raise_for_status()
    transport.complete_response(response, headers)
    if name not in transport.registry:
        raise RuntimeError("Publication did not return an accepted item identity.")
    item_id = transport.registry[name]
    read_path = f"https://api.fabric.microsoft.com{transport.base}/items/{item_id}/getDefinition"
    if ITEMS[name] == "SemanticModel":
        read_path += "?format=TMSL"
    response = transport.request("POST", read_path, headers=headers)
    response.raise_for_status()
    result = transport.complete_response(response, headers).json()
    actual = {part["path"]: json.loads(base64.b64decode(part["payload"]))
              for part in result["definition"]["parts"] if part["path"] in parts}
    (ROOT / ".local" / f"{name}-readback.json").write_text(json.dumps(actual, indent=2), encoding="utf-8")
    if set(actual) != set(parts):
        raise RuntimeError(f"{name} readback omitted requested definition parts.")
    if ITEMS[name] == "SemanticModel":
        expected_model, actual_model = parts["model.bim"]["model"], actual["model.bim"]["model"]
        expected_tables = {t["name"]: t for t in expected_model["tables"]}
        actual_tables = {t["name"]: t for t in actual_model["tables"]}
        if expected_tables.keys() != actual_tables.keys():
            raise RuntimeError("Semantic-model readback changed table identities.")
        for table_name, expected in expected_tables.items():
            table = actual_tables[table_name]
            for field in ("columns", "partitions", "measures", "hierarchies"):
                expected_members = {m["name"]: m for m in expected.get(field, [])}
                actual_members = {m["name"]: m for m in table.get(field, [])}
                if expected_members.keys() != actual_members.keys():
                    raise RuntimeError(f"Readback changed {table_name}.{field}.")
                for member, wanted in expected_members.items():
                    observed = actual_members[member]
                    for property_name, value in wanted.items():
                        actual_value = observed.get(property_name)
                        if property_name == "expression" and isinstance(actual_value, list):
                            actual_value = "\n".join(actual_value)
                        if property_name == "source" and isinstance(actual_value, dict):
                            actual_value = dict(actual_value)
                            if isinstance(actual_value.get("expression"), list):
                                actual_value["expression"] = "\n".join(actual_value["expression"])
                        if actual_value != value:
                            raise RuntimeError(f"Readback changed {table_name}.{member}.{property_name}.")
        for relation in expected_model["relationships"]:
            observed = next((r for r in actual_model["relationships"] if r["name"] == relation["name"]), {})
            defaults = {"fromCardinality": "many", "toCardinality": "one",
                        "crossFilteringBehavior": "oneDirection"}
            for key, value in relation.items():
                if observed.get(key, defaults.get(key)) != value:
                    raise RuntimeError(f"Readback changed relationship {relation['name']}.{key}.")
    else:
        connection = actual["definition.pbir"]["datasetReference"]["byConnection"]
        requested = parts["definition.pbir"]["datasetReference"]["byConnection"]
        tokens = connection["connectionString"].split(";")
        parsed = dict(token.split("=", 1) for token in tokens)
        if (len(parsed) != len(tokens) or parsed.get("semanticmodelid") != requested["connectionString"].removeprefix("semanticmodelid=")
                or set(parsed) - {"Data Source", "initial catalog", "integrated security", "semanticmodelid"}):
            raise RuntimeError("Report readback changed the shared semantic-model identity.")
        connection["connectionString"] = requested["connectionString"]
        if actual != parts:
            changed = [p for p in parts if actual[p] != parts[p]]
            raise RuntimeError(f"Report definition readback changed requested parts: {changed}.")
    return item_id


def dax(http: RecordedHttp, workspace: str, model_id: str, text: str) -> list[dict]:
    response = http.request("POST",
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace}/datasets/{model_id}/executeQueries",
        "https://analysis.windows.net/powerbi/api/.default",
        headers={"Content-Type": "application/json"},
        body=json.dumps({"queries": [{"query": text}], "serializerSettings": {"includeNulls": True}}).encode())
    result = response.json()
    if result.get("error") or any(r.get("error") for r in result.get("results", [])):
        raise RuntimeError(f"DAX execution failed: {json.dumps(result)}")
    return result["results"][0]["tables"][0]["rows"]


def refresh(http: RecordedHttp, workspace: str, model_id: str) -> None:
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace}/datasets/{model_id}/refreshes"
    audience = "https://analysis.windows.net/powerbi/api/.default"
    http.request("POST", url, audience, body=b'{"type":"full","commitMode":"transactional"}',
                 headers={"Content-Type": "application/json"}, expected=(202,))
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        time.sleep(5)
        result = http.request("GET", url + "?$top=1", audience).json()
        rows = result.get("value", [])
        if rows and rows[0]["status"] == "Completed":
            return
        if rows and rows[0]["status"] in ("Failed", "Disabled", "Cancelled"):
            raise RuntimeError(f"Showcase processing failed: {json.dumps(rows[0])}")
    raise TimeoutError("Showcase model processing exceeded ten minutes.")


def verify(http: RecordedHttp, workspace: str, model_id: str, snapshot: dict) -> dict:
    results = dax(http, workspace, model_id, '''EVALUATE ROW(
        "Sold", [Sold kg], "Revenue", [Revenue EUR], "Purchases", [Purchases EUR],
        "Started", [Started kg], "Released", [Released kg], "Shipped", [Shipped kg],
        "Cash", [Cash as observed EUR], "Days", [Selected virtual days],
        "ChannelFinance", CALCULATE([Revenue EUR], 'Channel'[Channel] = "export"),
        "Target2", CALCULATE([Illustrative target kg], 'Cover policy'[Days] = 2),
        "Target4", CALCULATE([Illustrative target kg], 'Cover policy'[Days] = 4))''')[0]
    expected = {
        "[Sold]": sum(r[4] for r in snapshot["tables"]["Sales"]),
        "[Revenue]": sum(r[1] for r in snapshot["tables"]["Finance"]) / 100,
        "[Purchases]": sum(r[2] for r in snapshot["tables"]["Finance"]) / 100,
        "[Started]": sum(r[2] for r in snapshot["tables"]["Production"]),
        "[Released]": sum(r[3] for r in snapshot["tables"]["Production"]),
        "[Shipped]": sum(r[4] for r in snapshot["tables"]["Production"]),
        "[Cash]": snapshot["tables"]["Balances"][-1][4] / 100,
        "[Days]": (date.fromisoformat(snapshot["throughDate"]) - date.fromisoformat(snapshot["firstDate"])).days + 1,
        "[ChannelFinance]": None,
    }
    for key, value in expected.items():
        actual = results.get(key)
        if (value is None and actual is not None
                or value is not None and (not isinstance(actual, (int, float)) or abs(actual - value) > 0.005)):
            raise RuntimeError(f"Model reconciliation failed for {key}: {actual!r} != {value!r}.")
    if results["[Target2]"] <= 0 or abs(results["[Target4]"] - 2 * results["[Target2]"]) > 0.001:
        raise RuntimeError("Disconnected stock-policy scenario does not respond correctly.")
    guards = dax(http, workspace, model_id, '''EVALUATE ROW(
        "DefaultCover", [Scenario cover days],
        "MultipleCover", CALCULATE([Scenario cover days], 'Cover policy'[Days] IN {2, 4}),
        "ProductFinance", CALCULATE([Revenue EUR], 'Product'[Product] = "dark70"),
        "TerritoryBalance", CALCULATE([Cash as observed EUR], 'Territory'[Territory] = "north"),
        "ChannelProduction", CALCULATE([Started kg], 'Channel'[Channel] = "export"))''')[0]
    if guards != {"[DefaultCover]": 3, "[MultipleCover]": 3, "[ProductFinance]": None,
                  "[TerritoryBalance]": None, "[ChannelProduction]": None}:
        raise RuntimeError(f"Model grain/scenario guards failed: {guards}.")
    last = date.fromisoformat(snapshot["throughDate"])
    previous_month_end = last.replace(day=1) - timedelta(days=1)
    month_start = previous_month_end.replace(day=1)
    prior_start = month_start.replace(year=month_start.year - 1)
    prior_end = date(prior_start.year, prior_start.month, calendar.monthrange(prior_start.year, prior_start.month)[1])

    def sold_between(start: date, end: date) -> int:
        return sum(row[4] for row in snapshot["tables"]["Sales"] if start.isoformat() <= row[0] <= end.isoformat())

    def dax_date(day: date) -> str:
        return f"DATE({day.year},{day.month},{day.day})"

    period = dax(http, workspace, model_id, f'''EVALUATE CALCULATETABLE(ROW(
        "Sold", [Sold kg], "PY", [Sold kg PY], "YoY", [Sales YoY %],
        "YTD", [Sales YTD kg], "Rolling", [Sales rolling 30d kg]),
        DATESBETWEEN('Date'[Date], {dax_date(month_start)}, {dax_date(previous_month_end)}))''')[0]
    py_sales = sold_between(prior_start, prior_end)
    py_observed = any(prior_start.isoformat() <= row[0] <= prior_end.isoformat()
                      for row in snapshot["tables"]["Sales"])
    current_sales = sold_between(month_start, previous_month_end)
    period_expected = {
        "[Sold]": current_sales, "[PY]": py_sales if py_observed else None,
        "[YoY]": current_sales / py_sales - 1 if py_sales else None,
        "[YTD]": sold_between(date(previous_month_end.year, 1, 1), previous_month_end),
        "[Rolling]": sold_between(previous_month_end - timedelta(days=29), previous_month_end),
    }
    for key, value in period_expected.items():
        if value is None and period.get(key) is not None or value is not None and abs(period.get(key, float("inf")) - value) > 0.005:
            raise RuntimeError(f"Virtual calendar reconciliation failed for {key}: {period}.")
    channels = dax(http, workspace, model_id, '''EVALUATE SUMMARIZECOLUMNS(
        'Channel'[Channel], "Sold", [Sold kg], "Share", [Channel share %], "Rank", [Channel rank])''')
    channel_totals = {name: sum(r[4] for r in snapshot["tables"]["Sales"] if r[1] == name)
                      for name in {r[1] for r in snapshot["tables"]["Sales"]}}
    ranks = sorted(set(channel_totals.values()), reverse=True)
    for row in channels:
        amount = channel_totals[row["Channel[Channel]"]]
        if row["[Sold]"] != amount or abs(row["[Share]"] - amount / expected["[Sold]"]) > 1e-9 or row["[Rank]"] != ranks.index(amount) + 1:
            raise RuntimeError(f"Channel share/rank reconciliation failed: {row}.")
    bridge = dax(http, workspace, model_id, '''EVALUATE SUMMARIZECOLUMNS(
        'Cash flow'[Component], "Amount", [Cash component EUR])''')
    cash_movement = sum(r["[Amount]"] for r in bridge)
    cash_expected = sum(r[4] + r[5] - r[6] - r[3] for r in snapshot["tables"]["Finance"]) / 100
    if abs(cash_movement - cash_expected) > 0.005:
        raise RuntimeError("Cash waterfall does not reconcile with signed cash movements.")
    observed_days = {r[0] for r in snapshot["tables"]["Balances"]}
    day = date.fromisoformat(snapshot["firstDate"])
    while day <= last and day.isoformat() in observed_days:
        day += timedelta(days=1)
    if day <= last:
        absent = dax(http, workspace, model_id, f'''EVALUATE CALCULATETABLE(ROW(
            "Stock", [Finished as observed kg], "Gap", [Illustrative gap kg]),
            'Date'[Date] = {dax_date(day)})''')[0]
        if absent != {"[Stock]": None, "[Gap]": None}:
            raise RuntimeError(f"Missing observations must remain blank: {absent}.")
    results["virtualPeriod"] = period
    results["guards"] = guards
    results["channels"] = channels
    results["cashComponents"] = bridge
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-snapshot", action="store_true", help="Republish the last extracted snapshot without querying Kusto.")
    parser.add_argument("--from-date", help="Inclusive virtual date for a bounded analytical episode (YYYY-MM-DD).")
    args = parser.parse_args()
    if args.reuse_snapshot and args.from_date is not None:
        parser.error("--from-date applies only to a fresh extraction")
    local = ROOT / ".local"
    workspace = json.loads((local / "demo-workspace.json").read_text())
    fabric = json.loads((local / "business-fabric.json").read_text())
    config = json.loads((ROOT / "config" / "business.json").read_text())
    if workspace["displayName"] != "ws-giandoria-demo" or workspace["id"] != fabric["workspaceId"]:
        raise ValueError("Showcase requires the recorded Giandoria workspace.")
    endpoint = urlsplit(fabric["queryServiceUri"])
    if endpoint.scheme != "https" or not endpoint.hostname or not endpoint.hostname.endswith(".kusto.fabric.microsoft.com"):
        raise ValueError("Showcase requires the recorded Fabric enterprise endpoint.")
    credential = AzureCliCredential()
    http = RecordedHttp(credential, {endpoint.hostname, "api.powerbi.com"})
    try:
        snapshot_path = local / "showcase-snapshot.json"
        snapshot = (json.loads(snapshot_path.read_text()) if args.reuse_snapshot else
                    extract_snapshot(http, fabric, from_date=args.from_date))
        validate_snapshot(snapshot, config)
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        transport = RecordedRequests(ROOT, workspace["id"], time.monotonic() + 900, ITEMS, marker=MARKER)
        headers = {"Authorization": f"Bearer {credential.get_token('https://api.fabric.microsoft.com/.default').token}"}
        transport.preflight(headers)
        model = model_definition(snapshot, config)
        (local / "showcase-model.bim").write_text(json.dumps(model, indent=2), encoding="utf-8")
        model_id = publish(transport, headers, "sm_giandoria_showcase",
                           {"model.bim": model, "definition.pbism": {"version": "1.0", "settings": {}}})
        refresh(http, workspace["id"], model_id)
        results = verify(http, workspace["id"], model_id, snapshot)
        for name, commercial in (("rp_giandoria_commercial", True), ("rp_giandoria_operations", False)):
            parts = report_definition(model_id, commercial)
            publish(transport, headers, name, parts)
        (local / "showcase-verification.json").write_text(json.dumps({
            "throughDate": snapshot["throughDate"], "modelId": model_id, "results": results,
            "items": {name: transport.registry[name] for name in ITEMS}}, indent=2), encoding="utf-8")
        print("Showcase model processed, DAX totals reconciled and two thin reports published.")
    finally:
        credential.close()


if __name__ == "__main__":
    main()
