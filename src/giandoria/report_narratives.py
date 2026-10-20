"""Generate bounded, snapshot-grounded AI commentary and publish report-only guidance."""

import argparse
import calendar
import copy
import hashlib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from azure.identity import AzureCliCredential

from .cloud_io import RecordedHttp

VERSION = 2
GUIDANCE = {
    "Virtual calendar": (
        "Chocolate sell-out means goods bought by customers, not shipments sent to a distributor. "
        "Sold kg adds recorded sell-out weight. PY compares with the same virtual dates one year earlier; "
        "YoY = (current - PY) / PY and is blank when the denominator is unavailable or zero. "
        "YTD accumulates from virtual January; rolling 30 days is a moving window, not a monthly total. "
        "Select a complete comparable year: the first and last snapshot years are partial."
    ),
    "Mix and concentration": (
        "A channel is a route to market, such as modern trade (large retail chains), export or own retail. "
        "Product mix shows weight, not revenue or profit. Channel share = channel Sold kg / all-channel Sold kg "
        "with other filters retained; selected shares need not sum to the whole. Rank compares selected channels. "
        "Scatter: horizontal = prior-year kg, vertical = current kg, bubble size = share. "
        "Concentration describes reliance on channels; it does not prove customer risk or profitability."
    ),
    "Territory and seasonality": (
        "Territories are aggregate sales areas, not individual factories or stores. "
        "Sold kg is customer sell-out weight, grouped by virtual Rome month or weekday. "
        "Columns compare territory contributions; the matrix crosses product and territory. "
        "A larger weekday total may reflect more occurrences of that weekday, not higher sales per trading day. "
        "Seasonal patterns are descriptive: these visuals do not establish causes, hidden demand or lost sales."
    ),
    "Flows versus stocks": (
        "Started kg enters factory production; released kg completes processing and the quality hold; "
        "shipped kg leaves the warehouse. They occur at different virtual times and need not match per month. "
        "Finished stock is goods available at the warehouse; backlog is outstanding logistics demand. "
        "These are levels, not flows: a total uses the last sampled balance, never the sum of monthly stocks. "
        "Observation days counts sampled dates; selected virtual days counts calendar dates. "
        "Missing samples are not zero. Releases / starts is not a quality rate or OEE."
    ),
    "Cash versus revenue": (
        "Revenue records sales postings; cash movement records receipts minus supplier and conversion payments. "
        "Receivables are amounts customers owe; payables are amounts owed to suppliers. "
        "Cash and these balances use the last available sampled date in the selection, not a sum. "
        "Conversion is modeled factory processing expenditure; purchases are material buying, not cost of goods sold. "
        "The waterfall explains signed cash contributions, not profit. Product/channel/territory finance slicing "
        "is unsupported and returns blank rather than inventing allocations."
    ),
    "Stock policy sandbox": (
        "Cover days is an illustrative number of days of sales held as finished stock. "
        "Daily sales = trailing 30-calendar-day Sold kg / available calendar days, including no-sale dates. "
        "Target kg = daily sales x selected cover days; gap kg = target - last observed finished stock. "
        "A positive gap is below this illustrative target, not a production order. "
        "One cover-day selection is used; no selection or several selections means the three-day default. "
        "Target and stock can have different effective dates. This sandbox changes neither simulator nor manager."
    ),
}


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def evidence(snapshot: dict) -> dict:
    sales, production, finance, balances = (snapshot["tables"][name] for name in
                                           ("Sales", "Production", "Finance", "Balances"))
    channels = {name: sum(row[4] for row in sales if row[1] == name) for name in {row[1] for row in sales}}
    last = date.fromisoformat(snapshot["throughDate"])
    month_end = last.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)
    prior_start = month_start.replace(year=month_start.year - 1)
    prior_end = prior_start.replace(day=calendar.monthrange(prior_start.year, prior_start.month)[1])
    start = max(date.fromisoformat(snapshot["firstDate"]), last - timedelta(days=29))
    trailing = sum(row[4] for row in sales if start.isoformat() <= row[0] <= last.isoformat())
    periods_available = snapshot["firstDate"] <= prior_start.isoformat()
    return {
        "scope": "Entire fixed enterprise snapshot; no report slicers applied; not live.",
        "firstVirtualDate": snapshot["firstDate"], "throughVirtualDate": snapshot["throughDate"],
        "soldKg": sum(row[4] for row in sales), "channelSoldKg": channels,
        "territorySoldKg": {name: sum(row[4] for row in sales if row[3] == name)
                            for name in {row[3] for row in sales}},
        "lastCompleteMonthComparison": {
            "available": periods_available,
            "currentKg": sum(row[4] for row in sales if month_start.isoformat() <= row[0] <= month_end.isoformat()),
            "priorKg": sum(row[4] for row in sales if prior_start.isoformat() <= row[0] <= prior_end.isoformat()),
        },
        "defaultThreeDayTargetKg": trailing / ((last - start).days + 1) * 3,
        "startedKg": sum(row[2] for row in production), "releasedKg": sum(row[3] for row in production),
        "shippedKg": sum(row[4] for row in production),
        "revenueEUR": sum(row[1] for row in finance) / 100,
        "purchasesEUR": sum(row[2] for row in finance) / 100,
        "conversionEUR": sum(row[3] for row in finance) / 100,
        "cashMovementEUR": sum(row[4] + row[5] - row[6] - row[3] for row in finance) / 100,
        "lastObservationDate": balances[-1][0], "lastFinishedKg": balances[-1][1],
        "lastBacklogKg": balances[-1][2], "lastCashEUR": balances[-1][4] / 100,
        "observationDays": len(balances),
        "limits": "No OEE, first-pass quality, profit, COGS, hidden demand, causal proof or live completeness watermark.",
    }


def validate_commentary(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != set(GUIDANCE):
        raise ValueError("AI commentary must cover exactly the six known report pages.")
    for page, text in value.items():
        if (not isinstance(text, str) or not 100 <= len(text) <= 700 or re.search(r"\d|[<>]", text)
                or any(word in text.lower() for word in ("guaranteed", "proves that"))):
            raise ValueError(f"Invalid or unsupported AI commentary for {page}.")


def load_commentary(local: Path, snapshot: dict, *, required: bool = False) -> dict | None:
    path = local / "report-narratives.json"
    if not path.exists():
        if required:
            raise RuntimeError("Generate and inspect AI commentary before publishing.")
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if (record["state"] != "Complete" or record["version"] != VERSION
            or record["snapshotDigest"] != digest(snapshot) or record["guidanceDigest"] != digest(GUIDANCE)):
        raise ValueError("AI commentary is incomplete or stale. Review and generate it for the exact snapshot.")
    validate_commentary(record["commentary"])
    return record


def verify_report(actual: dict, expected: dict, model_id: str) -> None:
    normalized = copy.deepcopy(actual)
    connection = normalized["definition.pbir"]["datasetReference"]["byConnection"]
    allowed = {
        f"semanticmodelid={model_id}",
        "Data Source=powerbi://api.powerbi.com/v1.0/myorg/ws-giandoria-demo;"
        f"initial catalog=sm_giandoria_showcase;integrated security=ClaimsToken;semanticmodelid={model_id}",
    }
    if connection["connectionString"] not in allowed:
        raise ValueError("Published report connection does not reference the exact enterprise model.")
    connection["connectionString"] = f"semanticmodelid={model_id}"
    if normalized != expected:
        raise RuntimeError("Published report guidance differs from source.")


def generate(http: RecordedHttp, endpoint: str, deployment: str, version: str, snapshot: dict, local: Path) -> dict:
    target = urlsplit(endpoint)
    if target.scheme != "https" or not target.hostname or not target.hostname.endswith(".openai.azure.com") or target.path not in ("", "/"):
        raise ValueError("Narratives require the recorded Azure OpenAI endpoint.")
    existing = load_commentary(local, snapshot)
    if existing is not None:
        return existing
    path = local / "report-narratives.json"
    facts = evidence(snapshot)
    record = {"state": "Reserved", "version": VERSION, "snapshotDigest": digest(snapshot),
              "guidanceDigest": digest(GUIDANCE), "evidence": facts,
              "deployment": deployment, "modelVersion": version}
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    body = {
        "model": deployment, "max_completion_tokens": 4096,
        "messages": [
            {"role": "system", "content": (
                "Write English report commentary for a reader unfamiliar with chocolate manufacturing or finance. "
                "This is a fictional reduced-detail company. Return exactly one short paragraph per requested page, "
                "between one hundred and seven hundred characters each. Use only the supplied evidence and definitions. "
                "Explain what to notice, a practical interpretation and one limitation. Include a specific qualitative "
                "finding supported by the evidence on each page, not merely repeated KPI definitions. Examples: "
                "name the largest channel or territory; compare starts/releases/shipments; explain the sign of cash "
                "movement versus revenue; compare last finished stock with the default three-day target. "
                "For the calendar use lastCompleteMonthComparison only if available is true; never infer full-year "
                "growth from lifetime totals. Do not quote actual quantities, dates, ratios or written-out amounts. "
                "No invented causes, forecasts, "
                "profitability, service guarantees, OEE or quality claims. No numeric characters or quantitative claims "
                "without support: exact figures are displayed separately by the publisher. No markdown or HTML. "
                "The commentary describes the whole fixed snapshot, not current slicer selections or live conditions. "
                "Do not claim growth from partial-year totals. For seasonality, teach how to read the page rather "
                "than asserting a pattern not present in the evidence. For stock policy, explain sensitivity without "
                "claiming an optimized or operational recommendation."
            )},
            {"role": "user", "content": json.dumps({"evidence": facts, "pages": GUIDANCE}, sort_keys=True)},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "report_commentary", "strict": True, "schema": {
                "type": "object", "additionalProperties": False,
                "properties": {page: {"type": "string"} for page in GUIDANCE},
                "required": list(GUIDANCE),
            },
        }},
    }
    response = http.request("POST", endpoint.rstrip("/") + "/openai/v1/chat/completions",
                            "https://cognitiveservices.azure.com/.default",
                            body=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
                            read_timeout=180).json()
    record.update(state="Answered", response=response)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    choice, usage = response["choices"][0], response["usage"]
    if choice["finish_reason"] != "stop" or type(usage["completion_tokens"]) is not int or not 0 <= usage["completion_tokens"] <= 4096:
        raise ValueError("AI generation did not complete within the reserved output budget.")
    commentary = json.loads(choice["message"]["content"])
    validate_commentary(commentary)
    record.update(state="Complete", commentary=commentary)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main() -> None:
    from .data_agent import model_contract, read_definition
    from .fabric_deploy import RecordedRequests
    from .showcase import ROOT, MARKER, publish, report_definition, validate_snapshot
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "publish"))
    parser.add_argument("--new-attempt", action="store_true",
                        help="Explicitly preserve an earlier generation receipt and authorize one new attempt.")
    args = parser.parse_args()
    if args.new_attempt and args.command != "generate":
        parser.error("--new-attempt applies only to generate.")
    local = ROOT / ".local"
    snapshot = json.loads((local / "showcase-snapshot.json").read_text())
    validate_snapshot(snapshot, json.loads((ROOT / "config" / "business.json").read_text()))
    with AzureCliCredential(process_timeout=60) as credential:
        if args.command == "generate":
            target = json.loads((local / "business-foundry-target.json").read_text())
            params = json.loads((local / "runtime-deployment.json").read_text())["properties"]["parameters"]
            http = RecordedHttp(credential, {urlsplit(target["endpoint"]).hostname})
            credential.get_token("https://cognitiveservices.azure.com/.default")
            previous = local / "report-narratives.json"
            if args.new_attempt and previous.exists():
                history = local / "report-narrative-history"
                history.mkdir(exist_ok=True)
                previous.replace(history / f"{uuid4()}.json")
            record = generate(http, target["endpoint"], params["model"]["value"],
                              params["modelVersion"]["value"], snapshot, local)
            print(json.dumps(record["commentary"], indent=2))
            return
        workspace = json.loads((local / "demo-workspace.json").read_text())
        if workspace["displayName"] != "ws-giandoria-demo":
            raise ValueError("Report narratives require the recorded enterprise showcase workspace.")
        headers = {"Authorization": "Bearer " + credential.get_token("https://api.fabric.microsoft.com/.default").token}
        model = RecordedRequests(ROOT, workspace["id"], time.monotonic() + 300,
                                 {"sm_giandoria_showcase": "SemanticModel"}, marker=MARKER)
        model.preflight(headers)
        model_id = model.registry["sm_giandoria_showcase"]
        model_contract(read_definition(model, headers, model_id, model=True), snapshot)
        reports = RecordedRequests(ROOT, workspace["id"], time.monotonic() + 600, {
            "rp_giandoria_commercial": "Report", "rp_giandoria_operations": "Report",
        }, marker=MARKER)
        reports.preflight(headers)
        for name, commercial in (("rp_giandoria_commercial", True), ("rp_giandoria_operations", False)):
            if name not in reports.registry:
                raise ValueError("Narrative publication requires an existing owned report.")
            parts = report_definition(model_id, commercial)
            item_id = publish(reports, headers, name, parts)
            actual = read_definition(reports, headers, item_id)
            verify_report(actual, parts, model_id)
        print("Both existing reports updated and read back; model, snapshot and running simulation unchanged.")


if __name__ == "__main__":
    main()
