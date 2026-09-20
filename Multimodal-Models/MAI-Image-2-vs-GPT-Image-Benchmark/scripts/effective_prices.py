"""Effective billed price per model, derived from an archived Azure Cost Management response.

The measurement archives record tokens, never money, so a price change can never invalidate a
measurement. Money enters the report at exactly one point: this script, which reads the invoice
this account actually received and divides billed cost by billed token quantity per meter.

  --check  recompute effective-prices.json from cost-query-response.json and confirm it matches
  --query  run the Cost Management query for your own account (needs `az` logged in) and write a
           fresh archive; the report then reads your invoice instead of ours

Cost Management queries run at subscription scope with the resource as a filter; a resource-scope
query returns Not Found. The API rate-limits per tenant with HTTP 429 and no usable Retry-After.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Output-image meters and the model each bills for. Meter names come from the invoice itself.
IMAGE_METERS = {
    "Image 2.6 Image Output Glbl 1M Tokens": "MAI-Image-2.6",
    "Image 2 img opt Gl 1M Tokens": "gpt-image-2",
    "Image-2.5-flare img opt Gl 1M Tokens": "gpt-image-2.5-flare",
    "Image-2.5-sunburst img opt Gl 1M Tokens": "gpt-image-2.5-sunburst",
}
# Output tokens per 1024x1024 image: constant per configuration across every run in this repository.
TOKENS_PER_IMAGE = {
    "MAI-Image-2.6": 1024,
    "gpt-image-2 low": 196, "gpt-image-2 medium": 1756, "gpt-image-2 high": 7024,
    "gpt-image-2.5 low": 196, "gpt-image-2.5 medium": 439, "gpt-image-2.5 high": 1756,
    "gpt-image-2.5 xhigh": 3122, "gpt-image-2.5 max": 7024,
}


def derive(response):
    columns = [c["name"] for c in response["properties"]["columns"]]
    prices = {}
    for raw in response["properties"]["rows"]:
        record = dict(zip(columns, raw))
        meter = str(record.get("Meter", ""))
        if meter in IMAGE_METERS:
            quantity = float(record["UsageQuantity"])
            if quantity:
                prices[IMAGE_METERS[meter]] = round(float(record["PreTaxCost"]) / quantity, 2)
    per_image = {}
    for config, tokens in TOKENS_PER_IMAGE.items():
        family = ("MAI-Image-2.6" if config.startswith("MAI") else
                  "gpt-image-2.5-flare" if config.startswith("gpt-image-2.5") else "gpt-image-2")
        if family in prices:
            per_image[config] = round(tokens * prices[family] / 1_000_000 * 1000, 2)
    return prices, per_image


def check(archive):
    response = json.loads((archive / "cost-query-response.json").read_text("utf-8"))
    stored = json.loads((archive / "effective-prices.json").read_text("utf-8"))
    prices, per_image = derive(response)
    problems = []
    if prices != stored["usd_per_million_output_image_tokens"]:
        problems.append(f"prices differ: derived {prices} stored {stored['usd_per_million_output_image_tokens']}")
    if per_image != stored["usd_per_1000_images"]:
        problems.append("per-1000-image costs do not reproduce")
    flare, sunburst = prices.get("gpt-image-2.5-flare"), prices.get("gpt-image-2.5-sunburst")
    if flare is not None and sunburst is not None and flare != sunburst:
        problems.append(f"flare and sunburst bill at different rates ({flare} vs {sunburst}); "
                        "the per-image table assumes one 2.5 rate")
    print(json.dumps({"validation": "PASS" if not problems else "FAIL", "prices": prices,
                      "problems": problems}, indent=2))
    return 0 if not problems else 1


def query(archive, subscription, resource_group, account, days):
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        raise SystemExit("az CLI not found on PATH")
    resource_id = (f"/subscriptions/{subscription}/resourceGroups/{resource_group}"
                   f"/providers/Microsoft.CognitiveServices/accounts/{account}").lower()
    end, start = date.today(), date.today() - timedelta(days=days)
    body = {"type": "ActualCost", "timeframe": "Custom",
            "timePeriod": {"from": start.isoformat(), "to": end.isoformat()},
            "dataset": {"granularity": "None",
                        "aggregation": {"cost": {"name": "PreTaxCost", "function": "Sum"},
                                        "qty": {"name": "UsageQuantity", "function": "Sum"}},
                        "grouping": [{"type": "Dimension", "name": "MeterSubCategory"},
                                     {"type": "Dimension", "name": "Meter"},
                                     {"type": "Dimension", "name": "UnitOfMeasure"}],
                        "filter": {"dimensions": {"name": "ResourceId", "operator": "In", "values": [resource_id]}}}}
    archive.mkdir(parents=True, exist_ok=True)
    body_path = archive / "query-body.json"
    body_path.write_text(json.dumps(body), encoding="utf-8")
    command = [az, "rest", "--method", "post",
               "--url", f"https://management.azure.com/subscriptions/{subscription}/providers/Microsoft.CostManagement/query",
               "--url-parameters", "api-version=2023-11-01", "--body", f"@{body_path}", "--output", "json", "--only-show-errors"]
    for wait in (0, 20, 45, 90):
        if wait:
            print(f"429 from Cost Management, waiting {wait}s", flush=True)
            time.sleep(wait)
        proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode == 0:
            break
        if "429" not in proc.stderr:
            raise SystemExit("query failed: " + proc.stderr[-800:])
    else:
        raise SystemExit("query failed after retries: " + proc.stderr[-400:])
    body_path.unlink()
    response = json.loads(proc.stdout)
    (archive / "cost-query-response.json").write_text(json.dumps(response, indent=2), encoding="utf-8")
    prices, per_image = derive(response)
    (archive / "effective-prices.json").write_text(json.dumps({
        "period": f"{start}..{end}", "source": "Azure Cost Management ActualCost, PreTaxCost",
        "usd_per_million_output_image_tokens": prices, "tokens_per_1024_image": TOKENS_PER_IMAGE,
        "usd_per_1000_images": per_image}, indent=2), encoding="utf-8")
    print(json.dumps({"archive": str(archive), "prices": prices}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Effective prices from an Azure Cost Management invoice.")
    parser.add_argument("archive", type=Path, help="Billing archive directory, e.g. data/billing-20260920")
    parser.add_argument("--check", action="store_true", help="Recompute and compare; no network.")
    parser.add_argument("--query", action="store_true", help="Query Cost Management for your own account.")
    parser.add_argument("--subscription")
    parser.add_argument("--resource-group")
    parser.add_argument("--account")
    parser.add_argument("--days", type=int, default=16)
    arguments = parser.parse_args()
    if arguments.query:
        if not (arguments.subscription and arguments.resource_group and arguments.account):
            parser.error("--query needs --subscription, --resource-group and --account")
        return query(arguments.archive, arguments.subscription, arguments.resource_group,
                     arguments.account, arguments.days)
    return check(arguments.archive)


if __name__ == "__main__":
    sys.exit(main())
