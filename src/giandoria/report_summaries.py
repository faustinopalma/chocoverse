"""Native Power BI Smart narrative expressions, evaluated in the report filter context."""

import copy


PAGE_METRICS = {
    "Virtual calendar": ("Sold kg", ("Sold kg", "Sold kg PY", "Sales YoY %")),
    "Mix and concentration": ("Sold kg", ("Sold kg", "Sold kg PY")),
    "Territory and seasonality": ("Sold kg", ("Sold kg", "Sold kg PY")),
    "Flows versus stocks": ("Released kg", ("Started kg", "Released kg", "Shipped kg",
                                               "Finished as observed kg", "Backlog as observed kg")),
    "Cash versus revenue": ("Revenue EUR", ("Revenue EUR", "Cash movement EUR", "Cash as observed EUR")),
    "Stock policy sandbox": ("Illustrative target kg", ("Scenario cover days", "Illustrative target kg",
                                                        "Finished as observed kg", "Illustrative gap kg")),
}


def value_ref(name: str) -> dict:
    return {"propertyIdentifier": {"objectName": "values", "propertyName": "expr"}, "selector": {"id": name}}


def summary_objects(page: str) -> dict:
    trend, metrics = PAGE_METRICS[page]
    output_names = [f"V{i}" for i in range(1, 28)] + ["TemplateIdColumnRole"]
    query = {
        "Version": 2,
        "From": [{"Name": "d", "Entity": "Date", "Type": 0}, {"Name": "m", "Entity": "Metrics", "Type": 0}],
        "Select": [{"Column": {"Expression": {"TransformTableRef": {"Source": "ChangeOutput"}},
                               "Property": name}, "Name": name} for name in output_names],
        "Transform": [{
            "Name": "OverallChange", "Algorithm": "ChangeSummary",
            "Input": {
                "Parameters": [{"Literal": {"Value": "1000L"}, "Name": "initialTemplateId"},
                               {"Literal": {"Value": "'OverallChange'"}, "Name": "changeType"}],
                "Table": {"Name": "ChangeInput", "Columns": [
                    {"Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "Date"},
                                    "Name": "date"}, "Role": "PrimarySeriesColumnRole"},
                    {"Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": trend},
                                    "Name": "value"}, "Role": "PrimaryValueColumnRole"},
                ]}},
            "Output": {"Table": {"Name": "ChangeOutput", "Columns": [
                {"Expression": {"TransformOutputRoleRef": {"Role": name}, "Name": name}, "Role": name}
                for name in output_names]}},
        }],
    }
    values = []
    for name in ("V1", "V2", "V3", "TemplateIdColumnRole"):
        expression = {"Aggregation": {"Expression": {"Column": {
            "Expression": {"Subquery": {"Query": copy.deepcopy(query)}}, "Property": name}}, "Function": 3}}
        values.append({"selector": {"id": name}, "properties": {
            "expr": {"expr": expression},
            "formatString": {"expr": {"Literal": {"Value": "'0.0%'" if name == "V1" else "'yyyy-MM-dd'"}}}
            if name != "TemplateIdColumnRole" else {"expr": {"Literal": {"Value": "'0'"}}},
        }})
    cases = []
    for template, direction in ((1001, "increased"), (1002, "decreased"), (1003, "remained relatively stable")):
        runs: list[dict] = [{"value": f"{trend} {direction}"}]
        if template != 1003:
            runs.extend([{"value": " by "}, {"value": value_ref("V1")}])
        runs.extend([{"value": " between "}, {"value": value_ref("V2")},
                     {"value": " and "}, {"value": value_ref("V3")}, {"value": " in the selected virtual period."}])
        cases.append({"pattern": {"expr": {"Literal": {"Value": f"{template}L"}}}, "textRuns": runs})
    paragraphs = [
        {"textRuns": [{"value": "Current selection | Native Smart narrative. Virtual dates only; "
                                "data remains the fixed enterprise snapshot, not the live simulator."}]},
        {"textRuns": [{"cases": cases, "defaultCase": {"textRuns": []},
                       "expression": value_ref("TemplateIdColumnRole")}]},
    ]
    for index, metric in enumerate(metrics):
        name = f"metric{index}"
        values.append({"selector": {"id": name}, "properties": {"expr": {"expr": {
            "Measure": {"Expression": {"SourceRef": {"Entity": "Metrics"}}, "Property": metric}}}}})
        paragraphs.append({"textRuns": [{"value": f"{metric}: "}, {"value": value_ref(name)}]})
    paragraphs.append({"textRuns": [{"value": "Blank values mean unavailable or unsupported context, not zero. "
                                             "Trend compares endpoints, not causality or annual growth."}]})
    for paragraph in paragraphs:
        paragraph["textRuns"][0]["textStyle"] = {"fontFamily": "Segoe UI", "fontSize": "12pt"}
    return {"general": [{"properties": {"paragraphs": paragraphs}}], "values": values}
