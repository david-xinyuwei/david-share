"""Cold versus warm results of the gateway prompt-cache matrix.

Request 1 of each (cell, problem) group writes the 1-hour cache and the identical request 2
reads it, so a group compares the same prompt without and with a cache hit. A group counts
only when both requests completed. Times are client-side seconds from just before the request
is written; P50 and P95 use the nearest rank, as in coding-matrix/analyze.py.
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coding-matrix"))
from pricing import PRICES  # noqa: E402

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
MODES = ("adaptive", "between_tools", "disabled")
EFFORTS = ("low", "medium", "high", "xhigh", "max", "default")
PUBLIC_FIELDS = ("task_id", "cell_id", "problem_id", "model", "mode", "effort", "kind", "repeat", "attempt",
                 "final", "sent_utc", "status", "http_status", "stop_reason", "message_id", "response_model",
                 "request_sha256", "prompt_chars", "usage", "timing", "cost_usd", "paced_wait_s")
PUBLIC_CONFIG = ("started_utc", "resumed_utc", "path", "cache_control", "cache_design", "max_tokens", "repeats",
                 "seed", "budget_usd", "tpm", "otpm_assumed", "max_attempts_on_429", "cells", "problem_ids",
                 "problems_source", "problems_sha256", "system_prompt_sha256", "tcp_connect_median_ms",
                 "tasks_already_final")


def nearest_rank(values, q):
    ordered = sorted(v for v in values if v is not None)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines(keepends=True)
            if line.endswith("\n") and line.strip()]


def load(run_dir):
    rows = [row for path in sorted(Path(run_dir).glob("responses_*.jsonl"))
            for row in read_records(path) if row["final"]]
    identities = [row["task_id"] for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate final task_id in snapshot")
    return rows


def prompt_tokens(usage):
    return sum(usage.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))


def uncached_cost(row):
    usage, price = row["usage"], PRICES[row["model"]]
    return (prompt_tokens(usage) * price["input"] + (usage.get("output_tokens", 0) or 0) * price["output"]) / 1_000_000


def side(rows):
    usage = [r["usage"] for r in rows]
    read = sum(u.get("cache_read_input_tokens", 0) or 0 for u in usage)
    total = sum(prompt_tokens(u) for u in usage)
    times = {k: [r["timing"].get(k) for r in rows] for k in ("first_event", "first_text", "end")}
    return {"first_event_p50": nearest_rank(times["first_event"], 0.5),
            "first_text_p50": nearest_rank(times["first_text"], 0.5),
            "first_text_p95": nearest_rank(times["first_text"], 0.95),
            "end_p50": nearest_rank(times["end"], 0.5),
            "end_p95": nearest_rank(times["end"], 0.95),
            "read_share": round(read / total, 4) if total else None,
            "written_tokens": sum(u.get("cache_creation_input_tokens", 0) or 0 for u in usage),
            "read_tokens": read,
            "output_tokens_p50": nearest_rank([u.get("output_tokens") for u in usage], 0.5),
            "cost_usd_per_request": round(sum(r["cost_usd"] for r in rows) / len(rows), 6),
            "uncached_cost_usd_per_request": round(sum(uncached_cost(r) for r in rows) / len(rows), 6)}


def summarize(pairs):
    if not pairs:
        return {"groups": 0}
    cold, warm = [p[0] for p in pairs], [p[1] for p in pairs]
    delta = [w["timing"]["first_text"] - c["timing"]["first_text"] for c, w in pairs
             if c["timing"].get("first_text") is not None and w["timing"].get("first_text") is not None]
    cold_cost = sum(r["cost_usd"] for r in cold)
    return {"groups": len(pairs), "prompt_tokens_p50": nearest_rank([prompt_tokens(r["usage"]) for r in cold], 0.5),
            "cold": side(cold), "warm": side(warm),
            "first_text_change_p50": round(nearest_rank(delta, 0.5), 4) if delta else None,
            "warm_cost_over_cold": round(sum(r["cost_usd"] for r in warm) / cold_cost, 4) if cold_cost else None,
            "pair_cost_over_uncached": round((cold_cost + sum(r["cost_usd"] for r in warm))
                                              / sum(uncached_cost(r) for r in cold + warm), 4)}


def analyze(run_dir):
    rows = load(run_dir)
    run = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    cells = {entry["cell_id"]: entry for entry in run["config"]["cells"]}
    if len(cells) != len(run["config"]["cells"]) or any(row["cell_id"] not in cells for row in rows):
        raise ValueError("Snapshot cells do not match the run configuration")
    expected = sum(run["planned"].values())
    if len(rows) > expected:
        raise ValueError("Snapshot exceeds the planned request count")
    problems = len(run["config"]["problem_ids"])
    measured_per_cell = problems * run["config"]["repeats"]
    measured = [r for r in rows if r["kind"] == "measured"]
    groups = defaultdict(dict)
    for row in measured:
        groups[(row["cell_id"], row["problem_id"])][row["repeat"]] = row
    pairs = {key: (g[1], g[2]) for key, g in groups.items()
             if 1 in g and 2 in g and g[1]["status"] == "completed" and g[2]["status"] == "completed"}
    by_cell, by_model = defaultdict(list), defaultdict(list)
    for (cell, _), pair in pairs.items():
        by_cell[cell].append(pair)
        by_model[pair[0]["model"]].append(pair)
    def cell_order(cell):
        model, mode, effort = cell.split("|")
        return ([m.split("-")[1] for m in MODELS].index(model), MODES.index(mode), EFFORTS.index(effort))

    coverage = {}
    for cell in sorted(cells, key=cell_order):
        records = [row for row in rows if row["cell_id"] == cell]
        coverage[cell] = {**summarize(by_cell[cell]), "requests": len(records),
                          "measured_requests": sum(row["kind"] == "measured" for row in records),
                          "warmups": sum(row["kind"] == "warmup" for row in records),
                          "statuses": Counter(row["status"] for row in records),
                          "planned_requests": measured_per_cell + 1,
                          "planned_measured_requests": measured_per_cell, "planned_groups": problems}
    cold_prompts = [prompt_tokens(c["usage"]) for c, _ in pairs.values()]
    return {
        "status": run["status"], "started_utc": run["config"]["started_utc"],
        "snapshot_utc": max(r["sent_utc"] for r in rows),
        "run_updated_utc": run["updated_utc"],
        "coverage": {"observed_requests": len(rows), "planned_requests": expected,
                     "missing_from_snapshot": expected - len(rows), "observed_measured": len(measured),
                     "planned_measured": measured_per_cell * len(cells),
                     "observed_warmups": sum(row["kind"] == "warmup" for row in rows),
                     "planned_warmups": len(cells), "collection_complete": len(rows) == expected},
        "planned": run["planned"], "final_requests": Counter(r["model"] for r in rows),
        "prompt_tokens_range": [min(cold_prompts), max(cold_prompts)] if cold_prompts else None,
        "statuses": Counter(f"{r['status']} http={r['http_status']}" for r in rows),
        "attempts_over_one": sum(1 for r in rows if r["attempt"] > 1),
        "groups_complete": len(pairs),
        "same_message_id_groups": sum(1 for c, w in pairs.values() if c.get("message_id") == w.get("message_id")),
        "warm_read_over_cold_write_min": min((w["usage"]["cache_read_input_tokens"] / c["usage"]["cache_creation_input_tokens"]
                                              for c, w in pairs.values() if c["usage"].get("cache_creation_input_tokens")),
                                             default=None),
        "cold_reads_max": max((c["usage"].get("cache_read_input_tokens", 0) for c, _ in pairs.values()), default=None),
        "inference_geo": Counter((r["usage"] or {}).get("inference_geo") for r in rows),
        "served_region": Counter((r.get("headers") or {}).get("llm_provider-x-ms-region") for r in rows),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
        "by_model": {m: summarize(by_model[m]) for m in MODELS if by_model[m]},
        "by_cell": coverage,
    }


def export_snapshot(run_dir, destination):
    run_dir, destination = Path(run_dir), Path(destination)
    if run_dir.resolve() == destination.resolve():
        raise ValueError("Public export must not replace the original run")
    facts = analyze(run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    public_run = {key: run[key] for key in ("status", "updated_utc", "cost_usd", "budget_usd", "counts", "planned")}
    public_run["config"] = {key: run["config"][key] for key in PUBLIC_CONFIG if key in run["config"]}
    artifacts = {"run.json": json.dumps(public_run, ensure_ascii=False, indent=1) + "\n"}
    sources = []
    for path in [run_dir / "run.json", *sorted(run_dir.glob("responses_*.jsonl"))]:
        sources.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        if path.name == "run.json":
            continue
        exported = []
        for row in read_records(path):
            public = {key: row[key] for key in PUBLIC_FIELDS if key in row}
            public["headers"] = {key: value for key, value in (row.get("headers") or {}).items()
                                 if key == "llm_provider-x-ms-region"}
            public["request_params"] = {key: value for key, value in row.get("request_params", {}).items()
                                        if key in ("model", "max_tokens", "stream", "thinking", "output_config", "cache_control")}
            public["text_chars"] = len(row.get("text") or "")
            public["text_sha256"] = hashlib.sha256((row.get("text") or "").encode("utf-8")).hexdigest()
            exported.append(json.dumps(public, ensure_ascii=False))
        artifacts[path.name] = "\n".join(exported) + "\n"
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in artifacts.items():
        path = destination / name
        if path.exists() and path.read_bytes() != content.encode("utf-8"):
            raise ValueError(f"Refusing to replace a different exported snapshot: {name}")
        path.write_text(content, encoding="utf-8", newline="\n")
    if analyze(destination) != facts:
        raise ValueError("Public projection changed the measured facts")
    (destination / "interim-facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
    manifest = {
        "projection": "Metrics-only projection; original numeric usage, timing and status fields are unchanged.",
        "omitted": ["request and response bodies", "thinking signatures and stream events", "private endpoints",
                    "headers other than served region", "group nonce"],
        "source_files": sources,
        "files": [{"file": name, "sha256": hashlib.sha256((destination / name).read_bytes()).hexdigest()}
                  for name in [*artifacts, "interim-facts.json"]],
    }
    (destination / "_export_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                                     encoding="utf-8", newline="\n")
    return facts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out", help="write the facts here")
    parser.add_argument("--check", action="store_true", help="fail unless --out already holds these facts")
    parser.add_argument("--export-dir", help="export a metrics-only snapshot without changing the original run")
    args = parser.parse_args()
    if args.export_dir:
        if args.out or args.check:
            parser.error("--export-dir cannot be combined with --out or --check")
        facts = export_snapshot(args.run_dir, args.export_dir)
        print(json.dumps(facts["coverage"]))
        return
    facts = json.loads(json.dumps(analyze(args.run_dir)))
    if args.check:
        if json.loads(Path(args.out).read_text(encoding="utf-8")) != facts:
            raise SystemExit(f"{args.out} does not match the run records")
        print("facts match")
        return
    text = json.dumps(facts, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({k: facts[k] for k in ("status", "snapshot_utc", "final_requests", "statuses", "groups_complete",
                                             "same_message_id_groups", "warm_read_over_cold_write_min", "cold_reads_max",
                                             "inference_geo", "served_region", "cost_usd")}, ensure_ascii=False))
    for model, s in facts["by_model"].items():
        print(model, s["groups"], "cold", s["cold"]["first_text_p50"], s["cold"]["end_p50"], s["cold"]["cost_usd_per_request"],
              "warm", s["warm"]["first_text_p50"], s["warm"]["end_p50"], s["warm"]["cost_usd_per_request"],
              "read", s["warm"]["read_share"], "ratio", s["warm_cost_over_cold"], "dft", s["first_text_change_p50"],
              "uncached", s["cold"]["uncached_cost_usd_per_request"], s["warm"]["uncached_cost_usd_per_request"],
              "pair/uncached", s["pair_cost_over_uncached"], "prompt", s["prompt_tokens_p50"])


if __name__ == "__main__":
    main()
