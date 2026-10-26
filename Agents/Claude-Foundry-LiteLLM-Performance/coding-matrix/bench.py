"""Coding matrix: every accepted thinking-mode x effort cell of the three
standard Claude 5.5 deployments on the same problems (Qira method).

One request in flight per deployment; the three deployments run side by side.
Within a model, rounds interleave problems and cells in a seeded order so a
slow hour affects every cell alike. One warm-up per cell is discarded:
these requests send no cache_control, so Claude caches nothing between them.

Our test deployments have small quotas (Opus 40K TPM; Sonnet and Haiku 80K TPM,
each with an output-token limit of one fifth of that per minute, observed as
'UserByModelByMinuteOutputTokens'). The client paces on both so the quota of
this test subscription does not masquerade as a platform failure. A 429 that
still happens is recorded as its own attempt and the same task is sent again
after Retry-After; every other outcome is final (no retries).

max_tokens is 128,000 in every cell: the Claude effort guide says to set a large
max_tokens at the higher effort levels (thinking counts toward it) and 128,000
for agentic coding on Sonnet 5.5. A 32,000 pilot cut off answers at effort max.
"""
import argparse
import json
import random
import socket
import statistics
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from claude_api import BASE, TokenProvider, cost_usd, new_client, sha256_json, stream_message, utcnow

TPM = {"claude-opus-5-5": 40000, "claude-sonnet-5-5": 80000, "claude-haiku-5-5": 80000}
OTPM = {model: limit // 5 for model, limit in TPM.items()}
SHORT = {"claude-opus-5-5": "opus", "claude-sonnet-5-5": "sonnet", "claude-haiku-5-5": "haiku"}
WARMUP_PROMPT = "Write a Python function add(a, b) that returns the sum of two numbers. Reply with the code only."
MAX_ATTEMPTS = 4


class Shared:
    def __init__(self, budget):
        self.lock = threading.Lock()
        self.budget = budget
        self.cost = 0.0
        self.stopped = False
        self.inflight = 0
        self.counts = {}

    def add_cost(self, value):
        with self.lock:
            self.cost += value or 0.0
            if self.cost >= self.budget:
                self.stopped = True


class Window:
    """Tokens counted when a request completes, kept for 60 s."""

    def __init__(self):
        self.events = deque()

    def used(self):
        cutoff = time.time() - 60
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        return sum(tokens for _, tokens in self.events)

    def add(self, tokens):
        if tokens:
            self.events.append((time.time(), tokens))


def pace(total, output, model, estimate):
    """Wait until both windows leave room; returns seconds waited."""
    waited = 0
    while waited < 120 and (total.used() + estimate > 0.85 * TPM[model] or output.used() > 0.85 * OTPM[model]):
        time.sleep(1)
        waited += 1
    return waited


def tcp_connect_ms():
    host = urlparse(BASE).hostname
    start = time.perf_counter()
    with socket.create_connection((host, 443), timeout=5):
        pass
    return (time.perf_counter() - start) * 1000


def cells_from_probe(summary, models):
    cells = []
    for model in models:
        for mode, efforts in summary[model]["accepted"].items():
            for effort in efforts:
                cells.append({"cell_id": f"{SHORT[model]}|{mode}|{effort}", "model": model,
                              "mode": mode, "effort": effort})
    return cells


def plan(model, cells, problems, repeats, seed, warmup):
    rng = random.Random(f"{seed}-{model}")
    mine = [c for c in cells if c["model"] == model]
    tasks = [{"kind": "warmup", "cell": c, "problem": None, "repeat": 0} for c in mine] if warmup else []
    for repeat in range(1, repeats + 1):
        order = problems[:]
        rng.shuffle(order)
        for problem in order:
            shuffled = mine[:]
            rng.shuffle(shuffled)
            for cell in shuffled:
                tasks.append({"kind": "measured", "cell": cell, "problem": problem, "repeat": repeat})
    return tasks


def task_id(task):
    if task["kind"] == "warmup":
        return f"{task['cell']['cell_id']}|warmup"
    return f"{task['cell']['cell_id']}|{task['problem']['id']}|r{task['repeat']}"


def usage_tokens(usage):
    if not usage:
        return 0, 0
    total = sum((usage.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                               "cache_read_input_tokens", "output_tokens"))
    return total, usage.get("output_tokens") or 0


def append(path, row, lock):
    with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def worker(model, tasks, run_dir, shared, attempts_done, system_prompt, max_tokens):
    client, tokens = new_client(), TokenProvider()
    total_window, output_window = Window(), Window()
    out_path = run_dir / f"responses_{SHORT[model]}.jsonl"
    log_path = run_dir / "progress.log"
    estimates = {}
    for count, task in enumerate(tasks):
        if shared.stopped:
            break
        tid = task_id(task)
        state = attempts_done.get(tid)
        if state and state["final"]:
            continue
        attempt = (state["attempts"] if state else 0) + 1
        cell, problem = task["cell"], task["problem"]
        user_message = WARMUP_PROMPT if problem is None else problem["user_message"]
        body = {"model": model, "max_tokens": max_tokens, "stream": True,
                "thinking": {"type": cell["mode"]}, "output_config": {"effort": cell["effort"]},
                "system": system_prompt, "messages": [{"role": "user", "content": user_message}]}
        while attempt <= MAX_ATTEMPTS and not shared.stopped:
            paced = pace(total_window, output_window, model, estimates.get(cell["cell_id"], 6000))
            with shared.lock:
                shared.inflight += 1
                inflight = shared.inflight
            try:
                record = stream_message(client, tokens, body)
            except Exception as exc:  # harness-side failure (e.g. token fetch); kept apart from platform outcomes
                record = {"sent_utc": utcnow(), "status": "client_exception", "http_status": None,
                          "error": {"type": type(exc).__name__, "message": str(exc)[:500]}, "timing": {},
                          "usage": None, "text": ""}
                time.sleep(5)
            finally:
                with shared.lock:
                    shared.inflight -= 1
            total, output = usage_tokens(record.get("usage"))
            total_window.add(total)
            output_window.add(output)
            if total:
                previous = estimates.get(cell["cell_id"])
                estimates[cell["cell_id"]] = total if previous is None else 0.7 * previous + 0.3 * total
            cost = cost_usd(model, record.get("usage")) if record.get("usage") else 0.0
            shared.add_cost(cost)
            throttled = record.get("http_status") == 429
            row = {"task_id": tid, "attempt": attempt, "final": not throttled or attempt == MAX_ATTEMPTS,
                   "kind": task["kind"], "model": model, "cell_id": cell["cell_id"],
                   "mode": cell["mode"], "effort": cell["effort"],
                   "problem_id": problem["id"] if problem else None,
                   "language": problem["language"] if problem else None, "repeat": task["repeat"],
                   "request_params": {k: body[k] for k in ("model", "max_tokens", "stream", "thinking", "output_config")},
                   "request_sha256": sha256_json(body), "inflight_at_send": inflight,
                   "paced_wait_s": paced, "cost_usd": cost}
            row.update(record)
            append(out_path, row, shared.lock)
            timing = record.get("timing") or {}
            with shared.lock:
                counts = shared.counts.setdefault(model, {})
                key = record["status"] + ("_429" if throttled else "")
                counts[key] = counts.get(key, 0) + 1
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{utcnow()} {tid} a{attempt} {record['status']} http={record['http_status']} "
                                 f"text={timing.get('first_text')} end={timing.get('end')} out={output} "
                                 f"paced={paced} cost={cost:.4f} total={shared.cost:.2f}\n")
            if not throttled:
                break
            time.sleep(float((record.get("headers") or {}).get("retry-after", 30)) + 1)
            attempt += 1
        if count % 50 == 0:
            try:
                sample = {"utc": utcnow(), "model": model, "tcp_connect_ms": round(tcp_connect_ms(), 2)}
                append(run_dir / "network.jsonl", sample, shared.lock)
            except OSError:
                pass
    client.close()


def load_attempts(run_dir):
    """task_id -> {'attempts': n, 'final': bool}; a task whose rows are all 429 is not final."""
    state = {}
    for path in run_dir.glob("responses_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            entry = state.setdefault(row["task_id"], {"attempts": 0, "final": False})
            entry["attempts"] = max(entry["attempts"], row.get("attempt", 1))
            if row.get("http_status") != 429 or row.get("final"):
                entry["final"] = True
    return state


def write_state(run_dir, shared, status, config, planned):
    with shared.lock:
        state = {"status": status, "updated_utc": utcnow(), "cost_usd": round(shared.cost, 4),
                 "budget_usd": shared.budget, "counts": shared.counts, "planned": planned, "config": config}
    (run_dir / "run.json").write_text(json.dumps(state, indent=1), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--problems", required=True)
    parser.add_argument("--probe-summary", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=128000)
    parser.add_argument("--budget-usd", type=float, default=150.0)
    parser.add_argument("--seed", default="20261026")
    parser.add_argument("--only-problems", default="")
    parser.add_argument("--no-warmup", action="store_true")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(args.problems).read_text(encoding="utf-8"))
    problems = spec["problems"]
    if args.only_problems:
        wanted = set(args.only_problems.split(","))
        problems = [p for p in problems if p["id"] in wanted]
    summary = json.loads(Path(args.probe_summary).read_text(encoding="utf-8"))
    models = list(SHORT)
    cells = cells_from_probe(summary, models)
    samples = sorted(tcp_connect_ms() for _ in range(10))
    median_ms = statistics.median(samples)
    append(run_dir / "network.jsonl", {"utc": utcnow(), "phase": "preflight", "tcp_connect_ms": samples},
           threading.Lock())
    if median_ms >= 50:
        raise SystemExit(f"TCP connect median {median_ms:.1f} ms >= 50 ms: not a same-region path")
    attempts_done = load_attempts(run_dir)
    plans = {m: plan(m, cells, problems, args.repeats, args.seed, not args.no_warmup) for m in models}
    planned = {m: len(t) for m, t in plans.items()}
    previous = {}
    state_path = run_dir / "run.json"
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8")).get("config", {})
    config = {"started_utc": previous.get("started_utc", utcnow()), "resumed_utc": utcnow() if previous else None,
              "max_tokens": args.max_tokens, "repeats": args.repeats,
              "seed": args.seed, "warmup_per_cell": not args.no_warmup, "budget_usd": args.budget_usd,
              "tpm": TPM, "otpm_assumed": OTPM, "max_attempts_on_429": MAX_ATTEMPTS,
              "cells": cells, "problem_ids": [p["id"] for p in problems],
              "problems_sha256": sha256_json(problems), "system_prompt_sha256": spec["system_prompt_sha256"],
              "tcp_connect_median_ms": round(median_ms, 2), "endpoint_host": urlparse(BASE).hostname,
              "tasks_already_final": sum(1 for v in attempts_done.values() if v["final"])}
    shared = Shared(args.budget_usd)
    for path in run_dir.glob("responses_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                shared.cost += json.loads(line).get("cost_usd") or 0.0
    write_state(run_dir, shared, "RUNNING", config, planned)
    threads = [threading.Thread(target=worker, args=(m, plans[m], run_dir, shared, attempts_done,
                                                     spec["system_prompt"], args.max_tokens), daemon=True)
               for m in models]
    for thread in threads:
        thread.start()
    while any(thread.is_alive() for thread in threads):
        time.sleep(15)
        write_state(run_dir, shared, "RUNNING", config, planned)
    write_state(run_dir, shared, "BUDGET_STOP" if shared.stopped else "COMPLETED", config, planned)


if __name__ == "__main__":
    main()
