"""Probe GPT-6 family deployments on one exact-answer task (first run 2026-09-27, GPT-6.1 Sol 2026-10-03).

A subset-sum over invoices with exactly one valid answer, verified locally. Same Responses API path as the
benchmark harness (streamed, no tools, Entra ID), so the latency and token fields are comparable with the
rest of the study.

    AZURE_OPENAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com/ \
    python scripts/exact_answer_probe.py --models gpt-6.1-sol --efforts low,medium,high --repeats 3

Writes outputs/exact-answer-probe-<date>/probe.json. Evidence file, not a benchmark: one task, a few repeats,
list prices.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential, get_bearer_token_provider
from openai import AzureOpenAI

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://YOUR-ENDPOINT.cognitiveservices.azure.com/")
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
TENANT = os.environ.get("AZURE_TENANT_ID")

# USD per 1M tokens, Azure pricing page (short context, Global), read 2026-09-27 from the rendered page
PRICE = {
    "gpt-6-astra": {"input": 10.0, "cached": 1.0, "output": 50.0},
    "gpt-6-sol": {"input": 2.0, "cached": 0.2, "output": 10.0},
    "gpt-6-luna": {"input": 0.10, "cached": 0.01, "output": 0.50},
    # gpt-5.6-sol here is the Data Zone deployment gpt-5.6-sol-dz; the invoice bills it at 4.40 / 0.44 / 22, i.e.
    # Global 4 / 0.40 / 20 (pricing page, Sweden Central view, 2026-09-28). Every row here is priced at Global list.
    "gpt-5.6-sol": {"input": 4.0, "cached": 0.4, "output": 20.0},
    "gpt-5.6-luna": {"input": 0.20, "cached": 0.02, "output": 1.20},
    # GPT-6.1 Sol short context Global, Azure pricing page read 2026-10-03
    "gpt-6.1-sol": {"input": 2.0, "cached": 0.10, "output": 10.0},
}
DEPLOYMENTS = {"gpt-6-astra": "judge-astra", "gpt-6-sol": "gpt-6-sol-probe", "gpt-6-luna": "gpt-6-luna",
               "gpt-5.6-sol": "gpt-5.6-sol-dz", "gpt-5.6-luna": "gpt-5.6-luna", "gpt-6.1-sol": "gpt-6.1-sol"}

SYSTEM = ("You are a precise finance assistant. Return only the JSON object requested, with no prose, no "
          "markdown fences and no explanation.")


def make_task(seed: int = 20260927, n: int = 24, k: int = 9) -> dict:
    """Invoices in cents; exactly one k-subset sums to the payment (checked by brute force)."""
    rnd = random.Random(seed)
    while True:
        cents = sorted(rnd.sample(range(120_000, 9_800_000), n))
        chosen = rnd.sample(range(n), k)
        target = sum(cents[i] for i in chosen)
        hits = [c for c in itertools.combinations(range(n), k) if sum(cents[i] for i in c) == target]
        if len(hits) == 1:
            ids = [f"INV-{1001 + i}" for i in range(n)]
            return {"ids": ids, "cents": cents, "target": target,
                    "answer": sorted(ids[i] for i in hits[0])}


def prompt(task: dict) -> str:
    rows = "\n".join(f"{i}: {c}" for i, c in zip(task["ids"], task["cents"]))
    return (f"A bank transfer of exactly {task['target']} cents pays exactly 9 of the 24 open invoices below. "
            "No invoice is partially paid or used twice, and exactly one valid set exists. Values are integer cents.\n\n"
            f"Invoice ID: amount (cents)\n{rows}\n\n"
            'Return {"invoice_ids": [...], "total_cents": <integer>} with the 9 invoice IDs sorted ascending.')


def check(text: str, task: dict) -> tuple[bool, str]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    try:
        obj = json.loads(t[t.find("{"): t.rfind("}") + 1])
    except Exception as exc:  # noqa: BLE001
        return False, f"unparseable: {exc}"
    if not isinstance(obj, dict) or not isinstance(obj.get("invoice_ids"), list):
        return False, f"no invoice list: {t[:120]!r}"
    ids = sorted(str(i) for i in obj["invoice_ids"])
    total = obj.get("total_cents")
    by_id = dict(zip(task["ids"], task["cents"]))
    real = sum(by_id.get(i, 0) for i in ids)
    ok = ids == task["answer"] and total == task["target"] and real == task["target"]
    return ok, f"ids_ok={ids == task['answer']} total_claimed={total} actual={real} drift={real - task['target']}"


def run(client, deployment, effort, text, max_output_tokens=40_000):
    kwargs = {"model": deployment, "stream": True, "max_output_tokens": max_output_tokens,
              "input": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]}
    if effort:
        kwargs["reasoning"] = {"effort": effort}
    t0 = time.perf_counter()
    ttft = None
    parts, usage, status, err = [], None, None, None
    try:
        for ev in client.responses.create(**kwargs):
            et = getattr(ev, "type", None)
            if et == "response.output_text.delta":
                if ttft is None:
                    ttft = time.perf_counter() - t0
                parts.append(ev.delta or "")
            elif et in ("response.completed", "response.incomplete", "response.failed"):
                r = ev.response
                status = r.status
                u = r.usage
                usage = {"prompt": u.input_tokens, "cached": getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0,
                         "cache_write": getattr(getattr(u, "input_tokens_details", None), "cache_write_tokens", 0) or 0,
                         "output": u.output_tokens,
                         "reasoning": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0}
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"[:300]
    return {"ttft_s": round(ttft, 2) if ttft else None, "e2e_s": round(time.perf_counter() - t0, 2),
            "status": status, "usage": usage, "text": "".join(parts), "error": err}


def cost(model, usage):
    # GPT-5.6+ bills cache writes separately; every listed write rate is 1.25x input.
    p = PRICE[model]
    written = usage.get("cache_write", 0)
    return ((usage["prompt"] - usage["cached"] - written) * p["input"] + written * p["input"] * 1.25
            + usage["cached"] * p["cached"] + usage["output"] * p["output"]) / 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gpt-6-astra,gpt-6-sol,gpt-6-luna")
    ap.add_argument("--efforts", default="none,low")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-output-tokens", type=int, default=40_000, dest="max_output_tokens",
                    help="output budget per request (reasoning + answer); 40,000 is what the 09-27 and 10-03 runs used")
    a = ap.parse_args()

    # the bench VM has no az CLI; it authenticates with its managed identity like the harness does
    cred = ChainedTokenCredential(AzureCliCredential(tenant_id=TENANT, process_timeout=90), ManagedIdentityCredential())
    client = AzureOpenAI(azure_endpoint=ENDPOINT, api_version=API_VERSION, max_retries=0,
                         azure_ad_token_provider=get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default"))
    task = make_task()
    text = prompt(task)
    out_dir = Path(a.out) if a.out else ROOT / "outputs" / f"exact-answer-probe-{datetime.now():%Y%m%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    arms = [(m, e) for m in a.models.split(",") for e in a.efforts.split(",")]
    for rep in range(a.repeats):
        random.shuffle(arms)  # interleave so no tier always goes first
        for model, effort in arms:
            # "none" is sent explicitly, as the benchmark harness does; "default" omits the parameter
            eff = None if effort == "default" else effort
            r = run(client, DEPLOYMENTS[model], eff, text, a.max_output_tokens)
            ok, detail = (False, r["error"]) if r["error"] or not r["usage"] else check(r["text"], task)
            rec = {"model": model, "effort": effort, "repeat": rep + 1, "exact": ok, "detail": detail,
                   "ttft_s": r["ttft_s"], "e2e_s": r["e2e_s"], "status": r["status"], "usage": r["usage"],
                   "usd": round(cost(model, r["usage"]), 5) if r["usage"] else None, "error": r["error"],
                   "text": r["text"][:600],
                   "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            records.append(rec)
            print(f"{model:12} {effort:6} #{rep + 1} exact={ok!s:5} e2e={r['e2e_s']:>7}s "
                  f"out={(r['usage'] or {}).get('output', '-'):>6} reason={(r['usage'] or {}).get('reasoning', '-'):>6} "
                  f"usd={rec['usd']} {detail if not ok else ''}")
            sys.stdout.flush()
            # long reasoning runs: keep what we have if the process dies
            (out_dir / "records.partial.json").write_text(json.dumps(records, indent=1), encoding="utf-8")

    summary = {}
    for model, effort in sorted({(r["model"], r["effort"]) for r in records}):
        rs = [r for r in records if r["model"] == model and r["effort"] == effort]
        good = [r for r in rs if r["usage"]]
        summary[f"{model}@{effort}"] = {
            "exact": f"{sum(r['exact'] for r in rs)}/{len(rs)}",
            "median_e2e_s": round(statistics.median(r["e2e_s"] for r in good), 1) if good else None,
            "median_output_tokens": int(statistics.median(r["usage"]["output"] for r in good)) if good else None,
            "median_reasoning_tokens": int(statistics.median(r["usage"]["reasoning"] for r in good)) if good else None,
            "median_usd": round(statistics.median(r["usd"] for r in good), 4) if good else None,
            "errors": sum(1 for r in rs if r["error"]),
        }
    doc = {"meta": {"date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "endpoint_region": "swedencentral",
                    "api": "Responses, streamed, no tools, Entra ID", "api_version": API_VERSION,
                    "task": "exact reconciliation: 9 of 24 invoices, unique subset, integer cents",
                    "prices": "Azure pricing page, short context Global, read 2026-09-27", "repeats": a.repeats,
                    "max_output_tokens": a.max_output_tokens,
                    "deployments": {m: DEPLOYMENTS[m] for m in a.models.split(",")}},
           "task": {"target_cents": task["target"], "answer": task["answer"]},
           "summary": summary, "records": records}
    (out_dir / "probe.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"\nwrote {out_dir / 'probe.json'}")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
