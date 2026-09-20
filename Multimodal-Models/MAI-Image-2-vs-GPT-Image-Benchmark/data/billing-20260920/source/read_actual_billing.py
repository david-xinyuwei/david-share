"""Actual billed cost per model from Azure Cost Management, for the account that ran every test.

The report's cost figures so far rest on a third-party reference price for MAI and the Azure list
price for GPT. Both are external. This account has generated over 700 images across four models
in the last two weeks, so the invoice line items give a measured price per token for each model
with no external source at all.
"""
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_paired_benchmark import AZ, PROVIDERS  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(__file__).resolve().parent / "runs" / "billing-20260920"


def main() -> int:
    provider = PROVIDERS[0]
    context = os.environ.copy()
    context["AZURE_CONFIG_DIR"] = str(Path.home() / provider["profile"])
    resource_id = (f"/subscriptions/{provider['subscription']}/resourceGroups/{provider['resource_group']}"
                   f"/providers/Microsoft.CognitiveServices/accounts/{provider['resource']}")
    # Cost Management queries run at subscription scope; the resource is a filter, not a scope.
    scope = f"/subscriptions/{provider['subscription']}"
    end = date.today()
    start = end - timedelta(days=16)
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
        "dataset": {
            "granularity": "None",
            "aggregation": {"cost": {"name": "PreTaxCost", "function": "Sum"},
                            "qty": {"name": "UsageQuantity", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": "MeterSubCategory"},
                         {"type": "Dimension", "name": "Meter"},
                         {"type": "Dimension", "name": "UnitOfMeasure"}],
            "filter": {"dimensions": {"name": "ResourceId", "operator": "In",
                                      "values": [resource_id.lower()]}},
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    body_path = OUT / "query-body.json"
    body_path.write_text(json.dumps(body), encoding="utf-8")
    print(f"resource: ...{resource_id[-60:]}\nperiod: {start} to {end}\n")

    command = [AZ, "rest", "--method", "post",
               "--url", f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query",
               "--url-parameters", "api-version=2023-11-01",
               "--body", f"@{body_path}", "--output", "json", "--only-show-errors"]
    # Cost Management rate-limits per tenant and answers 429 with no Retry-After we can read
    # through az; back off geometrically rather than guess.
    for attempt, wait in enumerate((0, 20, 45, 90), start=1):
        if wait:
            print(f"  429 from Cost Management, waiting {wait}s (attempt {attempt})", flush=True)
            time.sleep(wait)
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=context)
        if proc.returncode == 0:
            break
        if "429" not in proc.stderr:
            print("QUERY_FAILED\n" + proc.stderr[-1500:])
            return 1
    else:
        print("QUERY_FAILED after retries\n" + proc.stderr[-800:])
        return 1
    payload = json.loads(proc.stdout)
    (OUT / "cost-query-response.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    columns = [c["name"] for c in payload["properties"]["columns"]]
    rows = payload["properties"]["rows"]
    print(f"{len(rows)} billing rows\n")
    print(f"{'meter sub-category':<34} {'meter':<44} {'unit':<14} {'qty':>14} {'USD':>10}")
    print("-" * 120)
    totals = defaultdict(lambda: [0.0, 0.0])
    for row in sorted(rows, key=lambda r: -r[columns.index("PreTaxCost")]):
        record = dict(zip(columns, row))
        sub = str(record.get("MeterSubCategory", ""))
        meter = str(record.get("Meter", ""))
        unit = str(record.get("UnitOfMeasure", ""))
        qty = float(record.get("UsageQuantity", 0) or 0)
        cost = float(record.get("PreTaxCost", 0) or 0)
        totals[sub][0] += qty
        totals[sub][1] += cost
        print(f"{sub[:34]:<34} {meter[:44]:<44} {unit[:14]:<14} {qty:>14,.2f} {cost:>10.4f}")

    print("\nby model family:")
    for sub, (qty, cost) in sorted(totals.items(), key=lambda i: -i[1][1]):
        print(f"  {sub[:40]:<40} qty={qty:>14,.2f}  USD {cost:>9.4f}")
    print(f"\nTOTAL USD {sum(c for _, c in totals.values()):.4f}")
    print(f"\nraw response: {OUT / 'cost-query-response.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
