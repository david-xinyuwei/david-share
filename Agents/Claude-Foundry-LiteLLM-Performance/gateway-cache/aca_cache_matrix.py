"""Coding matrix with prompt caching, through the LiteLLM gateway on Azure Container Apps.

Every cell the probe accepted (thinking mode x effort, plus effort omitted) answers the
same long SWE-bench Lite prompts. Each (cell, problem) group puts its own nonce block in
front of the system prompt, so request 1 of the group writes the prompt cache and the
identical request 2 reads it. Caching is the top-level automatic breakpoint with a 1-hour
TTL, so a long first answer cannot let the entry expire before request 2 is sent.

The measured bench.py and claude_api.py are reused unchanged (same pacing, 429 handling,
timing points and prices); gateway_entry.py swaps only the URL, the gateway key and the
model alias, as in the cancelled 2026-10-26 gateway run.
"""
import argparse
import hashlib
import importlib
import json
import os
import random
import statistics
import sys
import threading
import time
from pathlib import Path


def load_modules(source, gateway_url):
    os.environ["FOUNDRY_ANTHROPIC_BASE"] = gateway_url  # claude_api reads it at import time
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(1, str(source))
    api = importlib.import_module("claude_api")
    gateway = importlib.import_module("gateway_entry")
    api.TokenProvider = gateway.GatewayTokenProvider
    api.new_client = gateway.new_gateway_client
    return api, importlib.import_module("bench")  # bench binds the patched names on import


def make_cells(bench, summary, with_default):
    cells = bench.cells_from_probe(summary, list(bench.SHORT))
    if with_default:
        for model in bench.SHORT:
            for mode, efforts in summary[model]["accepted"].items():
                if efforts:
                    cells.append({"cell_id": f"{bench.SHORT[model]}|{mode}|default", "model": model,
                                  "mode": mode, "effort": None})
    return cells


def plan(model, cells, problems, repeats, seed):
    rng = random.Random(f"{seed}-{model}")
    mine = [c for c in cells if c["model"] == model]
    tasks = [{"kind": "warmup", "cell": c, "problem": None, "repeat": 0, "nonce": None} for c in mine]
    groups = [(c, p) for c in mine for p in problems]
    rng.shuffle(groups)
    for cell, problem in groups:
        nonce = hashlib.sha256(f"{seed}|{cell['cell_id']}|{problem['id']}".encode()).hexdigest()[:12]
        for repeat in range(1, repeats + 1):
            tasks.append({"kind": "measured", "cell": cell, "problem": problem, "repeat": repeat, "nonce": nonce})
    return tasks


def task_id(task):
    if task["kind"] == "warmup":
        return f"{task['cell']['cell_id']}|warmup"
    return f"{task['cell']['cell_id']}|{task['problem']['id']}|r{task['repeat']}"


def build_body(model, cell, system_prompt, nonce, user_message, max_tokens, ttl):
    body = {"model": model, "max_tokens": max_tokens, "stream": True, "thinking": {"type": cell["mode"]}}
    if cell["effort"]:
        body["output_config"] = {"effort": cell["effort"]}
    body["cache_control"] = {"type": "ephemeral", "ttl": ttl}
    system = [{"type": "text", "text": system_prompt}]
    if nonce:
        system.insert(0, {"type": "text", "text": f"Request group {nonce}."})
    body["system"] = system
    body["messages"] = [{"role": "user", "content": user_message}]
    return body


def worker(api, bench, model, tasks, run_dir, shared, done, spec, args):
    client, tokens = api.new_client(), api.TokenProvider()
    total_window, output_window = bench.Window(), bench.Window()
    out_path = run_dir / f"responses_{bench.SHORT[model]}.jsonl"
    log_path = run_dir / "progress.log"
    estimates = {}
    for task in tasks:
        if shared.stopped:
            break
        tid = task_id(task)
        state = done.get(tid)
        if state and state["final"]:
            continue
        attempt = (state["attempts"] if state else 0) + 1
        cell, problem = task["cell"], task["problem"]
        user_message = bench.WARMUP_PROMPT if problem is None else problem["user_message"]
        body = build_body(model, cell, spec["system_prompt"], task["nonce"], user_message, args.max_tokens, args.ttl)
        key = problem["id"] if problem else "warmup"
        while attempt <= bench.MAX_ATTEMPTS and not shared.stopped:
            estimate = estimates.get(key, len(user_message) // 3 + 2000)
            paced = bench.pace(total_window, output_window, model, estimate)
            with shared.lock:
                shared.inflight += 1
                inflight = shared.inflight
            try:
                record = api.stream_message(client, tokens, body)
            except Exception as exc:  # harness-side failure, kept apart from platform outcomes
                record = {"sent_utc": api.utcnow(), "status": "client_exception", "http_status": None,
                          "error": {"type": type(exc).__name__, "message": str(exc)[:500]}, "timing": {},
                          "usage": None, "text": ""}
                time.sleep(5)
            finally:
                with shared.lock:
                    shared.inflight -= 1
            total, output = bench.usage_tokens(record.get("usage"))
            total_window.add(total)
            output_window.add(output)
            if total:
                estimates[key] = total
            cost = api.cost_usd(model, record.get("usage")) if record.get("usage") else 0.0
            shared.add_cost(cost)
            throttled = record.get("http_status") == 429
            row = {"task_id": tid, "attempt": attempt, "final": not throttled or attempt == bench.MAX_ATTEMPTS,
                   "kind": task["kind"], "model": model, "cell_id": cell["cell_id"], "mode": cell["mode"],
                   "effort": cell["effort"] or "default", "problem_id": problem["id"] if problem else None,
                   "repeat": task["repeat"], "group_nonce": task["nonce"],
                   "request_params": {k: body[k] for k in ("model", "max_tokens", "stream", "thinking",
                                                            "output_config", "cache_control") if k in body},
                   "request_sha256": api.sha256_json(body), "prompt_chars": len(json.dumps(body["system"])) + len(user_message),
                   "inflight_at_send": inflight, "paced_wait_s": paced, "cost_usd": cost}
            row.update(record)
            bench.append(out_path, row, shared.lock)
            timing, usage = record.get("timing") or {}, record.get("usage") or {}
            with shared.lock:
                counts = shared.counts.setdefault(model, {})
                status = record["status"] + ("_429" if throttled else "")
                counts[status] = counts.get(status, 0) + 1
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{api.utcnow()} {tid} a{attempt} {record['status']} http={record['http_status']} "
                                 f"text={timing.get('first_text')} end={timing.get('end')} "
                                 f"read={usage.get('cache_read_input_tokens')} write={usage.get('cache_creation_input_tokens')} "
                                 f"in={usage.get('input_tokens')} out={output} paced={paced} cost={cost:.4f} "
                                 f"total={shared.cost:.2f}\n")
            if not throttled:
                break
            time.sleep(float((record.get("headers") or {}).get("retry-after", 30)) + 1)
            attempt += 1
    client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source", required=True, help="directory with the measured bench.py and claude_api.py")
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--problems", required=True)
    parser.add_argument("--probe-summary", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=128000)
    parser.add_argument("--ttl", choices=("5m", "1h"), default="1h")
    parser.add_argument("--budget-usd", type=float, default=75.0)
    parser.add_argument("--seed", default="20261026")
    parser.add_argument("--no-default-effort", action="store_true")
    parser.add_argument("--only-cells", default="", help="comma-separated cell ids, for the gate")
    parser.add_argument("--only-problems", default="")
    args = parser.parse_args()
    if not os.environ.get("CLAUDE_GATEWAY_KEY"):
        raise SystemExit("CLAUDE_GATEWAY_KEY is required")
    api, bench = load_modules(Path(args.source).resolve(strict=True), args.gateway_url.rstrip("/"))
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(args.problems).read_text(encoding="utf-8"))
    problems = spec["problems"]
    if args.only_problems:
        wanted = args.only_problems.split(",")
        problems = [p for p in problems if p["id"] in wanted]
    summary = json.loads(Path(args.probe_summary).read_text(encoding="utf-8"))
    cells = make_cells(bench, summary, not args.no_default_effort)
    if args.only_cells:
        wanted = args.only_cells.split(",")
        cells = [c for c in cells if c["cell_id"] in wanted]
    samples = sorted(bench.tcp_connect_ms() for _ in range(10))
    median_ms = statistics.median(samples)
    bench.append(run_dir / "network.jsonl", {"utc": api.utcnow(), "phase": "preflight", "tcp_connect_ms": samples},
                 threading.Lock())
    if median_ms >= 50:
        raise SystemExit(f"TCP connect median {median_ms:.1f} ms >= 50 ms: not a same-region path")
    models = [m for m in bench.SHORT if any(c["model"] == m for c in cells)]
    plans = {m: plan(m, cells, problems, args.repeats, args.seed) for m in models}
    planned = {m: len(t) for m, t in plans.items()}
    done = bench.load_attempts(run_dir)
    state_path = run_dir / "run.json"
    previous = json.loads(state_path.read_text(encoding="utf-8")).get("config", {}) if state_path.exists() else {}
    config = {"started_utc": previous.get("started_utc", api.utcnow()), "resumed_utc": api.utcnow() if previous else None,
              "path": "VM -> LiteLLM gateway (Azure Container Apps, East US 2) -> Foundry",
              "endpoint_host": api.BASE.split("//", 1)[-1], "cache_control": {"type": "ephemeral", "ttl": args.ttl},
              "cache_design": "nonce block per (cell, problem); request 1 writes, identical request 2 reads",
              "max_tokens": args.max_tokens, "repeats": args.repeats, "seed": args.seed, "budget_usd": args.budget_usd,
              "tpm": bench.TPM, "otpm_assumed": bench.OTPM, "max_attempts_on_429": bench.MAX_ATTEMPTS,
              "cells": [dict(c, effort=c["effort"] or "default") for c in cells],
              "problem_ids": [p["id"] for p in problems], "problems_source": spec["source"],
              "problems_sha256": api.sha256_json(problems), "system_prompt_sha256": spec["system_prompt_sha256"],
              "tcp_connect_median_ms": round(median_ms, 2), "tasks_already_final": sum(1 for v in done.values() if v["final"])}
    shared = bench.Shared(args.budget_usd)
    for path in run_dir.glob("responses_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                shared.cost += json.loads(line).get("cost_usd") or 0.0
    bench.write_state(run_dir, shared, "RUNNING", config, planned)
    threads = [threading.Thread(target=worker, args=(api, bench, m, plans[m], run_dir, shared, done, spec, args),
                                daemon=True) for m in models]
    for thread in threads:
        thread.start()
    while any(thread.is_alive() for thread in threads):
        time.sleep(15)
        bench.write_state(run_dir, shared, "RUNNING", config, planned)
    bench.write_state(run_dir, shared, "BUDGET_STOP" if shared.stopped else "COMPLETED", config, planned)


if __name__ == "__main__":
    main()
