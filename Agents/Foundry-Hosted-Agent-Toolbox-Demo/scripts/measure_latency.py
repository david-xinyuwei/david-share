"""Measure end-to-end latency for the hosted agent's two main paths.

Runs N iterations of each path against the running local Responses server,
prints p50 / p95 / mean / max in milliseconds. Intentionally simple: one
file, no external deps beyond what main.py already needs.

Prerequisite:
    python main.py    # start the server (Terminal 1)

Then in another terminal:
    python scripts/measure_latency.py --iterations 5

Use --iterations 10 for tighter numbers; each iteration costs one Foundry
billing round-trip plus tool execution.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import httpx


REQUEST_DIR = Path(__file__).resolve().parents[1] / "examples" / "requests"


def load_request(name: str) -> dict[str, str]:
    return json.loads((REQUEST_DIR / name).read_text(encoding="utf-8"))


def time_one_call(client: httpx.Client, base_url: str, body: dict[str, str]) -> tuple[float, str]:
    """Return (elapsed_seconds, completion_status)."""
    start = time.perf_counter()
    response = client.post(f"{base_url.rstrip('/')}/responses", json=body)
    elapsed = time.perf_counter() - start
    response.raise_for_status()
    payload = response.json()
    return elapsed, payload.get("status", "unknown")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] * (c - k) + s[c] * (k - f)


def summarize(label: str, durations_s: list[float]) -> None:
    ms = [d * 1000 for d in durations_s]
    print(f"\n=== {label} ===")
    print(f"  iterations : {len(ms)}")
    print(f"  mean (ms)  : {statistics.mean(ms):8.1f}")
    print(f"  p50 (ms)   : {percentile(ms, 50):8.1f}")
    print(f"  p95 (ms)   : {percentile(ms, 95):8.1f}")
    print(f"  max (ms)   : {max(ms):8.1f}")
    print(f"  min (ms)   : {min(ms):8.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8088")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--skip-web", action="store_true")
    args = parser.parse_args()

    code_body = load_request("code_interpreter.json")
    web_body = load_request("direct_web_search.json")

    code_times: list[float] = []
    web_times: list[float] = []

    with httpx.Client(timeout=args.timeout) as client:
        for i in range(args.iterations):
            elapsed, status = time_one_call(client, args.base_url, code_body)
            print(f"[code] iter {i+1}/{args.iterations}: {elapsed*1000:7.1f} ms (status={status})")
            code_times.append(elapsed)

        if not args.skip_web:
            for i in range(args.iterations):
                elapsed, status = time_one_call(client, args.base_url, web_body)
                print(f"[web]  iter {i+1}/{args.iterations}: {elapsed*1000:7.1f} ms (status={status})")
                web_times.append(elapsed)

    summarize("code_interpreter via Toolbox MCP", code_times)
    if web_times:
        summarize("direct_web_search via Responses API", web_times)


if __name__ == "__main__":
    main()
