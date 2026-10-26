"""Read the 2026-10-26 run records and facts, and derive every number the pages quote."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence/coding-matrix-20261026"
MODELS = ("opus", "sonnet", "haiku")
NAME = {"opus": "Opus 5.5", "sonnet": "Sonnet 5.5", "haiku": "Haiku 5.5"}
DEPLOYMENT = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
ROWS = (("opus", "adaptive"), ("sonnet", "adaptive"), ("sonnet", "between_tools"),
        ("haiku", "adaptive"), ("haiku", "disabled"))
OFF_MODE = {"sonnet": "between_tools", "haiku": "disabled"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def nearest_rank(values, q):
    values = sorted(v for v in values if v is not None)
    return values[max(math.ceil(q / 100 * len(values)) - 1, 0)] if values else None


def short(model):
    return model.removeprefix("claude-").split("-")[0]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load():
    facts = read_json(EV / "matrix/facts.json")
    cache = read_json(EV / "cache/cache_facts.json")
    problems = read_json(EV / "matrix/problems.json")
    listed = read_json(ROOT / "data/coding-problems.json")
    require([p["id"] for p in problems["problems"]] == [p["id"] for p in listed["problems"]],
            "data/coding-problems.json does not list the measured problems")
    responses = [r for path in sorted((EV / "matrix").glob("responses_*.jsonl")) for r in read_jsonl(path)]
    measured = [r for r in responses if r["kind"] == "measured"]
    cells = {c["cell_id"]: c for c in facts["cells"]}
    require(len(cells) == 21 and facts["requests_total"] == len(responses), "matrix facts do not match the records")
    probe = read_jsonl(EV / "probe/probe_results.jsonl")
    runs = {}
    for name in ("smoke", "pilot-32k", "matrix"):
        rows = [r for path in sorted((EV / name).glob("responses_*.jsonl")) for r in read_jsonl(path)]
        state = read_json(EV / name / "run.json")
        runs[name] = {"requests": len(rows), "statuses": Counter(r["status"] for r in rows),
                      "http": Counter(r.get("http_status") for r in rows), "cost": sum(r.get("cost_usd") or 0 for r in rows),
                      "first": min(r["sent_utc"] for r in rows), "last": max(r["sent_utc"] for r in rows),
                      "max_tokens": state["config"]["max_tokens"], "state": state["status"]}
    pricing = _pricing()
    runs["probe"] = {"requests": len(probe), "http": Counter(r["http_status"] for r in probe),
                     "cost": sum(pricing.cost_usd(r["model"], r.get("usage")) or 0 for r in probe),
                     "first": min(r["sent_utc"] for r in probe), "last": max(r["sent_utc"] for r in probe)}
    cache_rows = read_jsonl(EV / "cache/cache_results.jsonl")
    runs["cache"] = {"requests": len(cache_rows), "http": Counter(r.get("http_status") for r in cache_rows),
                     "cost": cache["cost_total_usd"], "first": min(r["sent_utc"] for r in cache_rows),
                     "last": max(r["sent_utc"] for r in cache_rows)}
    require(abs(runs["matrix"]["cost"] - facts["cost_total_usd"]) < 1e-9, "matrix cost mismatch")
    environment = (EV / "matrix/environment.txt").read_text(encoding="utf-8").splitlines()
    return {"facts": facts, "cells": cells, "cache": cache, "problems": problems, "listed": listed,
            "measured": measured, "responses": responses, "probe": probe, "runs": runs,
            "environment": environment, "provenance": read_json(EV / "provenance.json"),
            "probe_summary": read_json(EV / "probe/probe_summary.json"), "cache_rows": cache_rows}


def _pricing():
    import importlib.util
    spec = importlib.util.spec_from_file_location("coding_pricing", ROOT / "coding-matrix/pricing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cell(d, model, mode, effort):
    return d["cells"].get(f"{model}|{mode}|{effort}")


def model_cells(d, model, mode=None):
    return [c for c in d["facts"]["cells"] if c["model"] == model and (mode is None or c["mode"] == mode)]


def matrix_numbers(d):
    """Headline numbers of the matrix, each computed from the records."""
    facts, measured = d["facts"], d["measured"]
    off = [r["timing"]["first_text"] for r in measured
           if r["mode"] != "adaptive" and (r.get("timing") or {}).get("first_text") is not None]
    first_event = [(r.get("timing") or {}).get("first_event") for r in measured]
    thought = [r for r in measured if (((r.get("usage") or {}).get("output_tokens_details") or {}).get("thinking_tokens") or 0) > 0]
    statuses = Counter(r["status"] for r in measured)
    failures = [r for r in measured if r["status"] != "completed"]
    per_problem = defaultdict(lambda: [0, 0])
    for row in facts["by_problem"]:
        key = (row["cell_id"].split("|")[0], row["problem_id"])
        per_problem[key][0] += row["passed"]
        per_problem[key][1] += row["n"]
    per_language = defaultdict(lambda: [0, 0])
    for row in facts["by_language"]:
        key = (row["cell_id"].split("|")[0], row["language"])
        per_language[key][0] += row["passed"]
        per_language[key][1] += row["n"]
    http = Counter(r.get("http_status") for r in d["responses"])
    geo = Counter((r.get("usage") or {}).get("inference_geo") for r in d["responses"])
    require(len(geo) == 1, "responses report more than one inference_geo")
    regions = Counter((r.get("headers") or {}).get("x-ms-region") for r in d["responses"])
    spilled = Counter((r.get("headers") or {}).get("x-ms-is-spilled-over") for r in d["responses"])
    return {
        "geo": geo, "geo_value": next(iter(geo)), "regions": regions, "spilled": spilled,
        "requests": facts["requests_total"], "measured": len(measured),
        "warmups": facts["requests_total"] - len(measured), "completed": statuses["completed"],
        "http": http, "throttled": facts["throttled_attempts"],
        "off_p50": nearest_rank(off, 50), "off_p95": nearest_rank(off, 95), "off_n": len(off),
        "first_event_p50": nearest_rank(first_event, 50), "first_event_p95": nearest_rank(first_event, 95),
        "thought": len(thought),
        "thought_streamed": sum(1 for r in thought if (r.get("timing") or {}).get("first_thinking_text") is not None),
        "failures": failures, "per_problem": per_problem, "per_language": per_language,
        "problems": [p["id"] for p in d["problems"]["problems"]], "repeats": facts["state"]["config"]["repeats"],
        "tcp_ms": facts["state"]["config"]["tcp_connect_median_ms"],
        "started": facts["state"]["config"]["started_utc"], "updated": facts["state"]["updated_utc"],
    }


def cache_numbers(d):
    cache = d["cache"]
    turns = {(t["model"], t["scenario"], t["turn"]): t for t in cache["per_turn"]}
    sessions = {(s["model"], s["scenario"]): s for s in cache["sessions"]}
    pairs = {(p["model"], p["scenario"]): p for p in cache["ttft_pairs"]}
    require(all(t["ok"] == t["n"] for t in cache["per_turn"]), "a cache request failed")

    def rng(values):
        values = [v for v in values if v is not None]
        return min(values), max(values)

    def share(scenario, turns_wanted, models=MODELS):
        return rng(turns[(DEPLOYMENT[m], scenario, t)]["read_share"] for m in models for t in turns_wanted
                   if (DEPLOYMENT[m], scenario, t) in turns)

    def saving(scenarios, models=MODELS):
        return rng(sessions[(DEPLOYMENT[m], s)]["saving_vs_no_cache"] for m in models for s in scenarios
                   if (DEPLOYMENT[m], s) in sessions)

    def tokens(scenario, turn, field, models=MODELS):
        return rng(turns[(DEPLOYMENT[m], scenario, turn)]["tokens_mean"][field] for m in models
                   if (DEPLOYMENT[m], scenario, turn) in turns)

    off_models = ("sonnet", "haiku")
    return {
        "turns": turns, "sessions": sessions, "pairs": pairs,
        "auto_share": share("auto", (2, 3, 4)), "auto_saving": saving(["auto"]),
        "second_saving": saving(["system_only_second", "system_plus_auto_second"]),
        "second_read": tokens("system_only_second", 1, "read"),
        "second_share": share("system_only_second", (1,)),
        "auto_second_read": tokens("auto_second", 1, "read"), "auto_second_saving": saving(["auto_second"]),
        "effort_share": share("effort_switch", (3,)), "message_share": share("effort_switch_message", (3,)),
        "mode_read": tokens("mode_switch", 3, "read", off_models),
        "mode_write": tokens("mode_switch", 3, "write", off_models),
        "mode_t4_share": share("mode_switch", (4,), off_models),
        "idle5_read": tokens("idle_5m", 2, "read"), "idle5_write": tokens("idle_5m", 2, "write"),
        "idle5_saving": saving(["idle_5m"]),
        "idle1h_read": tokens("idle_1h", 2, "read"), "idle1h_saving": saving(["idle_1h"]),
        "prewarm_read": tokens("prewarm", 2, "read"), "prewarm_share": share("prewarm", (2,)),
        "system_only_saving": saving(["system_only"]),
        "warm_cost_ratio": rng(p["warm_cost_mean_usd"] / p["cold_cost_mean_usd"] for p in cache["ttft_pairs"]),
        "context": cache["context"], "requests": cache["requests_sent"], "throttled": cache["throttled_attempts"],
        "cost": cache["cost_total_usd"],
    }


def thinking(d, model):
    return d["facts"]["intervals"]["thinking"][model]


def probe_outcomes(d):
    """(probe name, model) -> (HTTP status, 400 message or None, thinking tokens); every probe appears once per model."""
    outcomes = {}
    for row in d["probe"]:
        key = (row["probe"], short(row["model"]))
        require(key not in outcomes, f"duplicate probe {key}")
        usage = row.get("usage") or {}
        outcomes[key] = (row["http_status"], None if row["http_status"] == 200 else (row.get("error_message") or ""),
                         (usage.get("output_tokens_details") or {}).get("thinking_tokens"))
    return outcomes
