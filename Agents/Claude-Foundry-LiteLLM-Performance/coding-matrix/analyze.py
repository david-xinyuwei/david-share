"""Summarise a matrix run: success, first-text latency, cost and test pass rate per cell.

Denominators: every measured attempt that was sent counts, failures included.
Latency percentiles use requests that returned visible text (nearest rank).
Pass-rate intervals resample the problems, not the requests: the three repeats of
one problem are not independent, so a request-level interval would be too narrow.
"""
import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

MODEL_ORDER = {"opus": 0, "sonnet": 1, "haiku": 2}
MODE_ORDER = {"adaptive": 0, "between_tools": 1, "disabled": 1}
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}
BOOTSTRAP_SAMPLES = 5000
BOOTSTRAP_SEED = 20261026


def read_jsonl(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[max(math.ceil(q / 100 * len(values)) - 1, 0)]


def cell_key(cell_id):
    model, mode, effort = cell_id.split("|")
    return (MODEL_ORDER[model], MODE_ORDER[mode], EFFORT_ORDER[effort])


def is_final(row):
    return row.get("final", row.get("http_status") != 429)


def summarize(run_dir):
    all_rows = [r for path in sorted(run_dir.glob("responses_*.jsonl")) for r in read_jsonl(path)]
    responses = [r for r in all_rows if is_final(r)]
    throttled = [r for r in all_rows if r.get("http_status") == 429]
    judged = {f"{row['task_id']}#{row.get('attempt') or 1}": row for row in read_jsonl(run_dir / "judged.jsonl")}
    state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    planned_measured = len(state["config"]["problem_ids"]) * state["config"]["repeats"]
    throttled_by_cell = defaultdict(int)
    for row in throttled:
        throttled_by_cell[row["cell_id"]] += 1
    cells = defaultdict(list)
    for row in responses:
        if row["kind"] == "measured":
            row["_judge_key"] = f"{row['task_id']}#{row.get('attempt') or 1}"
            cells[row["cell_id"]].append(row)
    summary, by_language, by_problem = [], defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for cell_id in sorted(cells, key=cell_key):
        rows = cells[cell_id]
        statuses = defaultdict(int)
        for row in rows:
            statuses[row["status"]] += 1
        texted = [r for r in rows if (r.get("timing") or {}).get("first_text") is not None]
        usage = [r.get("usage") or {} for r in rows]
        thinking = [((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0) for u in usage]
        output = [u.get("output_tokens") or 0 for u in usage]
        verdicts = defaultdict(int)
        passed = 0
        for row in rows:
            verdict = judged.get(row["_judge_key"])
            if verdict is None:
                verdicts["not_judged"] += 1
                continue
            verdicts[verdict["verdict"]] += 1
            if verdict["passed"]:
                passed += 1
            key = (cell_id, row["language"])
            by_language[key][0] += int(verdict["passed"])
            by_language[key][1] += 1
            by_problem[(cell_id, row["problem_id"])][0] += int(verdict["passed"])
            by_problem[(cell_id, row["problem_id"])][1] += 1
        judged_n = sum(v for k, v in verdicts.items() if k != "not_judged")
        costs = [r.get("cost_usd") or 0.0 for r in rows]
        e2e = [(r.get("timing") or {}).get("end") for r in rows if r["status"] == "completed"]
        model, mode, effort = cell_id.split("|")
        summary.append({
            "cell_id": cell_id, "model": model, "mode": mode, "effort": effort,
            "planned": planned_measured, "attempted": len(rows),
            "completed": statuses.get("completed", 0), "statuses": dict(statuses),
            "success_rate": statuses.get("completed", 0) / len(rows) if rows else None,
            "first_text_p50_s": pct([r["timing"]["first_text"] for r in texted], 50),
            "first_text_p95_s": pct([r["timing"]["first_text"] for r in texted], 95),
            "first_event_p50_s": pct([(r.get("timing") or {}).get("first_event") for r in rows], 50),
            "e2e_p50_s": pct(e2e, 50), "e2e_p95_s": pct(e2e, 95),
            "thinking_tokens_p50": pct(thinking, 50), "thinking_requests": sum(1 for t in thinking if t > 0),
            "output_tokens_p50": pct(output, 50),
            "cost_per_request_usd": sum(costs) / len(costs) if costs else None,
            "cost_per_1k_requests_usd": 1000 * sum(costs) / len(costs) if costs else None,
            "cost_total_usd": sum(costs),
            "judged": judged_n, "passed": passed, "verdicts": dict(verdicts),
            "accuracy": passed / len(rows) if rows else None,
            "throttled_attempts": throttled_by_cell.get(cell_id, 0),
        })
    totals = defaultdict(lambda: defaultdict(int))
    for row in all_rows:
        key = row["status"] + ("_429_resent" if row.get("http_status") == 429 and not is_final(row) else "")
        totals[row["model"]][key] += 1
        totals[row["model"]]["http_" + str(row.get("http_status"))] += 1
    problem_rows = [{"cell_id": c, "problem_id": p, "passed": v[0], "n": v[1]} for (c, p), v in sorted(by_problem.items())]
    return {"run": run_dir.name, "state": state, "cells": summary,
            "per_model_status": {m: dict(v) for m, v in totals.items()},
            "by_language": [{"cell_id": c, "language": l, "passed": v[0], "n": v[1]} for (c, l), v in sorted(by_language.items())],
            "by_problem": problem_rows,
            "intervals": intervals(problem_rows, [cell["cell_id"] for cell in summary]),
            "requests_total": len(all_rows), "tasks_final": len(responses), "throttled_attempts": len(throttled),
            "cost_total_usd": sum(r.get("cost_usd") or 0 for r in all_rows)}


def intervals(problem_rows, cell_ids):
    """95% percentile-bootstrap intervals that resample the problems.

    'thinking' compares a model's adaptive cells with its thinking-off cells at the
    same effort levels (low, medium, high), so both sides share problems and efforts.
    """
    table = {(r["cell_id"], r["problem_id"]): (r["passed"], r["n"]) for r in problem_rows}
    problems = sorted({r["problem_id"] for r in problem_rows})
    rng = random.Random(BOOTSTRAP_SEED)
    samples = [[rng.choice(problems) for _ in problems] for _ in range(BOOTSTRAP_SAMPLES)]

    def share(cells, sample):
        passed = sum(table[(c, p)][0] for c in cells for p in sample)
        return passed / sum(table[(c, p)][1] for c in cells for p in sample)

    def bounds(values):
        values = sorted(values)
        return [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]

    result = {"method": "percentile bootstrap over problems", "samples": BOOTSTRAP_SAMPLES,
              "seed": BOOTSTRAP_SEED, "problems": len(problems), "cells": {}, "thinking": {}}
    for cell in cell_ids:
        result["cells"][cell] = {"share": share([cell], problems), "ci95": bounds(share([cell], s) for s in samples)}
    for model in MODEL_ORDER:
        on = [c for c in cell_ids if c.startswith(model + "|adaptive|") and c.split("|")[2] in ("low", "medium", "high")]
        off = [c for c in cell_ids if c.startswith(model + "|") and c.split("|")[1] != "adaptive"]
        if not off:
            continue
        on_share, off_share = share(on, problems), share(off, problems)
        per_problem = {p: share(on, [p]) - share(off, [p]) for p in problems}
        result["thinking"][model] = {
            "on_cells": on, "off_cells": off, "on_share": on_share, "off_share": off_share,
            "difference": on_share - off_share,
            "difference_ci95": bounds(share(on, s) - share(off, s) for s in samples),
            "problems_better_on": sum(1 for v in per_problem.values() if v > 0),
            "problems_better_off": sum(1 for v in per_problem.values() if v < 0),
            "problems_equal": sum(1 for v in per_problem.values() if v == 0)}
    return result


def fmt(value, digits=2, suffix=""):
    return "—" if value is None else f"{value:.{digits}f}{suffix}"


def markdown(facts):
    lines = ["| Cell | Attempted | Completed | First text P50 | E2E P50 | Thinking P50 | $ / 1k req | Pass |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cell in facts["cells"]:
        lines.append(f"| {cell['cell_id']} | {cell['attempted']}/{cell['planned']} | {cell['completed']} | "
                     f"{fmt(cell['first_text_p50_s'], 2, ' s')} | {fmt(cell['e2e_p50_s'], 1, ' s')} | "
                     f"{cell['thinking_tokens_p50']} | {fmt(cell['cost_per_1k_requests_usd'], 1)} | "
                     f"{cell['passed']}/{cell['attempted']} ({fmt(100 * cell['accuracy'] if cell['accuracy'] is not None else None, 0, '%')}) |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--check", action="store_true", help="recompute and compare with facts.json; write nothing")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    facts = summarize(run_dir)
    if args.check:
        saved = json.loads((run_dir / "facts.json").read_text(encoding="utf-8"))
        if saved != json.loads(json.dumps(facts)):
            sys.exit(f"facts.json in {run_dir} differs from a fresh analysis of the run records")
        print(json.dumps({"status": "PASS", "run": facts["run"], "requests_total": facts["requests_total"],
                          "cells": len(facts["cells"])}))
        return
    (run_dir / "facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8", newline="\n")
    with (run_dir / "cells.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [k for k in facts["cells"][0] if k not in ("statuses", "verdicts")] if facts["cells"] else []
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(facts["cells"])
    table = markdown(facts)
    (run_dir / "cells.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print(json.dumps({"requests_total": facts["requests_total"], "cost_total_usd": round(facts["cost_total_usd"], 4),
                      "per_model_status": facts["per_model_status"]}, indent=1))


if __name__ == "__main__":
    main()
