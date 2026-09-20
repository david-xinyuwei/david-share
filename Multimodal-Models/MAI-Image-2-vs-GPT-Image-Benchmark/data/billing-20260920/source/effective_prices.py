"""Effective billed price per million output-image tokens, per model, from this account's invoice.

Quantity is billed in millions of tokens and the query rounds it in display, so read the raw
response and divide cost by quantity at full precision. Cross-check the result against the tokens
we counted in our own runs: if invoice quantity and measured tokens agree, the per-token price is
trustworthy and independent of any published price sheet.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJECT = Path(__file__).resolve().parent
RESPONSE = PROJECT / "runs" / "billing-20260920" / "cost-query-response.json"
REPORT = Path("c:/david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark")

# Output-image meters, and the model family they belong to.
IMAGE_METERS = {
    "Image 2.6 Image Output Glbl 1M Tokens": "MAI-Image-2.6",
    "Image 2 img opt Gl 1M Tokens": "gpt-image-2",
    "Image-2.5-flare img opt Gl 1M Tokens": "gpt-image-2.5-flare",
    "Image-2.5-sunburst img opt Gl 1M Tokens": "gpt-image-2.5-sunburst",
}
# Measured tokens per 1024x1024 image, constant per configuration across every run here.
TOKENS_PER_IMAGE = {
    "MAI-Image-2.6": 1024,
    "gpt-image-2 low": 196, "gpt-image-2 medium": 1756, "gpt-image-2 high": 7024,
    "gpt-image-2.5 low": 196, "gpt-image-2.5 medium": 439, "gpt-image-2.5 high": 1756,
    "gpt-image-2.5 xhigh": 3122, "gpt-image-2.5 max": 7024,
}


def measured_output_tokens():
    """Sum of output-image tokens this account actually generated, per model, from our own runs."""
    totals = {}
    for results in list((PROJECT / "runs").rglob("5way_v2_results.json")):
        if "superseded" in str(results) or "unpaced" in str(results) or "smoke" in str(results):
            continue
        data = json.loads(results.read_text(encoding="utf-8"))
        for row in data.get("raw_data", []) + data.get("warmup", []):
            if not row.get("ok"):
                continue
            group = row["group"]
            family = ("MAI-Image-2.6" if group.startswith("mai") else
                      "gpt-image-2.5-flare" if "flare" in group else
                      "gpt-image-2.5-sunburst" if "sunburst" in group else
                      "gpt-image-2" if group.startswith("gpt-image-2-") else None)
            if not family:
                continue
            info = row.get("token_info") or {}
            tokens = info.get("output_tokens") or info.get("num_output_tokens") or 0
            totals[family] = totals.get(family, 0) + tokens
    return totals


def main() -> int:
    payload = json.loads(RESPONSE.read_text(encoding="utf-8"))
    columns = [c["name"] for c in payload["properties"]["columns"]]
    rows = [dict(zip(columns, r)) for r in payload["properties"]["rows"]]

    measured = measured_output_tokens()
    print("Effective billed price for output-image tokens, from this account's own invoice\n")
    print(f"{'model':<24} {'billed tokens':>15} {'measured tokens':>16} {'match':>7} "
          f"{'USD billed':>11} {'USD / 1M tokens':>16}")
    print("-" * 96)
    prices = {}
    for record in rows:
        meter = str(record.get("Meter", ""))
        if meter not in IMAGE_METERS:
            continue
        family = IMAGE_METERS[meter]
        qty_millions = float(record["UsageQuantity"])
        cost = float(record["PreTaxCost"])
        billed_tokens = qty_millions * 1_000_000
        price = cost / qty_millions if qty_millions else float("nan")
        prices[family] = price
        ours = measured.get(family, 0)
        # Billing may include calls outside these runs (canaries, probes), so ours is a floor.
        ratio = billed_tokens / ours if ours else float("nan")
        match = f"{ratio:.2f}x" if ours else "n/a"
        print(f"{family:<24} {billed_tokens:>15,.0f} {ours:>16,} {match:>7} {cost:>11.4f} {price:>16.2f}")

    print("\nCost per 1,000 images at 1024x1024, using billed price x measured tokens")
    print("-" * 96)
    print(f"{'configuration':<24} {'tokens/img':>11} {'USD / 1,000 images':>20} {'vs MAI':>9}")
    mai_price = prices.get("MAI-Image-2.6")
    mai_cost = TOKENS_PER_IMAGE["MAI-Image-2.6"] * mai_price / 1_000_000 * 1000 if mai_price else None
    table = []
    for config, tokens in TOKENS_PER_IMAGE.items():
        if config.startswith("MAI"):
            price = mai_price
        elif config.startswith("gpt-image-2.5"):
            # Flare and sunburst bill at the same rate; confirm below and use flare.
            price = prices.get("gpt-image-2.5-flare")
        else:
            price = prices.get("gpt-image-2")
        if price is None:
            continue
        cost = tokens * price / 1_000_000 * 1000
        table.append((config, tokens, cost))
    for config, tokens, cost in sorted(table, key=lambda t: t[2]):
        rel = f"{cost / mai_cost:.2f}x" if mai_cost else ""
        marker = "  <-- MAI" if config.startswith("MAI") else ""
        print(f"{config:<24} {tokens:>11,} {cost:>20.2f} {rel:>9}{marker}")

    flare, sun = prices.get("gpt-image-2.5-flare"), prices.get("gpt-image-2.5-sunburst")
    if flare and sun:
        print(f"\n2.5 flare vs sunburst billed rate: {flare:.2f} vs {sun:.2f} USD/1M "
              f"({'same' if abs(flare - sun) < 0.5 else 'DIFFERENT'})")
    gpt2 = prices.get("gpt-image-2")
    if gpt2:
        print(f"gpt-image-2 billed {gpt2:.2f} USD/1M vs published list price 30.00 "
              f"({'matches' if abs(gpt2 - 30) < 0.5 else 'differs'})")

    (PROJECT / "runs" / "billing-20260920" / "effective-prices.json").write_text(json.dumps(
        {"period": "2026-09-04..2026-09-20", "source": "Azure Cost Management ActualCost, PreTaxCost",
         "usd_per_million_output_image_tokens": prices,
         "measured_output_tokens_in_our_runs": measured,
         "tokens_per_1024_image": TOKENS_PER_IMAGE,
         "usd_per_1000_images": {c: round(v, 2) for c, _, v in table}},
        indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
