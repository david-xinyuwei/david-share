#!/usr/bin/env python3
"""Build evidence/measurements.json from projected logs and evidence/runs.json.

    python tools/build_evidence.py          # rewrite evidence/measurements.json
    python tools/build_evidence.py --check  # fail if the committed file is stale

Every comparison is MI300X against MI300X. A pair is accepted only when the two
runs used the same workload arguments and every request succeeded; otherwise
the build fails instead of silently skipping the point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_log import parse  # noqa: E402

PAIR_KEYS = ("dataset_name", "random_input_len", "random_output_len", "max_concurrency",
             "num_prompts", "warmup_requests", "flush_cache", "seed", "pd_separated",
             "random_range_ratio", "tokenize_prompt", "fake_prefill", "request_rate")


def _pct(after: float, before: float) -> float:
    return round((after - before) / before * 100.0, 2)


def _load_runs() -> dict:
    return json.loads((EVIDENCE / "runs.json").read_text(encoding="utf-8"))


def _verify_manifest(meta: dict) -> None:
    manifest = json.loads((EVIDENCE / "raw-manifest.json").read_text(encoding="utf-8"))
    listed = {item["projected_file"] for item in manifest["files"]}
    on_disk = {p.name for p in (EVIDENCE / "raw").iterdir() if p.is_file()}
    if listed != on_disk:
        raise SystemExit(f"MANIFEST_MISMATCH listed-only {sorted(listed - on_disk)} disk-only {sorted(on_disk - listed)}")
    for item in manifest["files"]:
        path = EVIDENCE / "raw" / item["projected_file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["projected_sha256"]:
            raise SystemExit(f"HASH_MISMATCH {path.name}: {digest} != {item['projected_sha256']}")
    used = {name for run in meta["runs"].values() for name in run.get("raw", [])}
    if used - listed:
        raise SystemExit(f"UNLISTED_SOURCE {sorted(used - listed)}")


def _raw_json(name: str) -> dict:
    return json.loads((EVIDENCE / "raw" / name).read_text(encoding="utf-8"))


def _parsed(names: list[str]) -> list[dict]:
    runs = []
    for name in names:
        for run in parse((EVIDENCE / "raw" / name).read_text(encoding="utf-8")):
            run["source"] = name
            runs.append(run)
    return runs


def _key(run: dict) -> tuple:
    return tuple(run["args"].get(k) for k in PAIR_KEYS)


def _check_success(run: dict) -> None:
    expected = run["args"]["num_prompts"]
    got = run["metrics"].get("successful_requests")
    if got != expected:
        raise SystemExit(f"INCOMPLETE_RUN {run['source']}: {got}/{expected} requests succeeded")


def _fits_context(run: dict, stage: dict) -> bool:
    a = run["args"]
    need = a["random_input_len"] + stage["special_tokens_per_request"] + a["random_output_len"]
    return need <= stage["server_context_length"]


def tuned_moe_stage(meta: dict) -> dict:
    stage_before = meta["runs"]["stage-20260707-ck"]
    stage_after = meta["runs"]["stage-20260713-tuned-moe"]
    if stage_before["server_context_length"] != stage_after["server_context_length"]:
        raise SystemExit("CONTEXT_LENGTH_DIFFERS between the two stages")
    before = _parsed(stage_before["raw"])
    after = _parsed(stage_after["raw"])
    by_key = {}
    for run in before:
        by_key.setdefault(_key(run), []).append(run)
    decode, prefill, excluded = [], [], []
    for run in after:
        matches = by_key.get(_key(run), [])
        if len(matches) != 1:
            raise SystemExit(f"UNPAIRED_RUN {run['source']}: {len(matches)} matching baseline runs")
        base = matches[0]
        _check_success(run)
        _check_success(base)
        a, b = run["args"], run["metrics"]
        m0 = base["metrics"]
        if not (_fits_context(run, stage_after) and _fits_context(base, stage_before)):
            ctx = stage_after["server_context_length"]
            excluded.append({
                "input_tokens": a["random_input_len"],
                "concurrency": a["max_concurrency"],
                "reason": (f"input {a['random_input_len']} + {stage_after['special_tokens_per_request']} special tokens + "
                           f"{a['random_output_len']} output token(s) exceeds --context-length {ctx}; the server can "
                           "return error payloads that the client counts as successes"),
            })
            continue
        if a["random_output_len"] == 1:
            prefill.append({
                "input_tokens": a["random_input_len"], "concurrency": a["max_concurrency"],
                "requests": a["num_prompts"],
                "before_input_tok_s": m0["input_tok_s"], "after_input_tok_s": b["input_tok_s"],
                "input_tok_s_delta_pct": _pct(b["input_tok_s"], m0["input_tok_s"]),
                "before_mean_ttft_ms": m0["mean_ttft_ms"], "after_mean_ttft_ms": b["mean_ttft_ms"],
                "mean_ttft_delta_pct": _pct(b["mean_ttft_ms"], m0["mean_ttft_ms"]),
            })
        else:
            decode.append({
                "input_tokens": a["random_input_len"], "output_tokens": a["random_output_len"],
                "concurrency": a["max_concurrency"], "requests": a["num_prompts"],
                "before_output_tok_s": m0["output_tok_s"], "after_output_tok_s": b["output_tok_s"],
                "output_tok_s_delta_pct": _pct(b["output_tok_s"], m0["output_tok_s"]),
                "before_mean_tpot_ms": m0["mean_tpot_ms"], "after_mean_tpot_ms": b["mean_tpot_ms"],
                "mean_tpot_delta_pct": _pct(b["mean_tpot_ms"], m0["mean_tpot_ms"]),
            })
    decode.sort(key=lambda r: r["concurrency"])
    prefill.sort(key=lambda r: r["input_tokens"])
    return {"decode": decode, "prefill": prefill, "excluded": excluded}


def concurrency_ladder(meta: dict) -> list[dict]:
    rows = []
    for run in _parsed(meta["runs"]["ladder-20260708-ck"]["raw"]):
        _check_success(run)
        m = run["metrics"]
        rows.append({
            "concurrency": run["args"]["max_concurrency"],
            "observed_concurrency": m["observed_concurrency"],
            "output_tok_s": m["output_tok_s"], "mean_tpot_ms": m["mean_tpot_ms"],
            "mean_ttft_ms": m["mean_ttft_ms"], "p99_ttft_ms": m["p99_ttft_ms"],
        })
    rows.sort(key=lambda r: r["concurrency"])
    return rows


def ab_64k(meta: dict) -> dict:
    raw = _raw_json(meta["runs"]["ab-20260718-64k-bs16"]["raw"][0])
    if len(raw["baseline"]["runs"]) != 2 or len(raw["optimized"]["runs"]) != 2:
        raise SystemExit("AB_REPETITIONS each arm must have exactly two fresh-service runs")
    base_runs = [statistics.fmean(s) for s in raw["baseline"]["runs"]]
    opt_runs = [statistics.fmean(s) for s in raw["optimized"]["runs"]]
    base, opt = statistics.fmean(base_runs), statistics.fmean(opt_runs)
    batch = 16
    return {
        "batch": batch,
        "switches_added": raw["optimized"]["env_added"],
        "baseline_run_means_tok_s": [round(x, 2) for x in base_runs],
        "optimized_run_means_tok_s": [round(x, 2) for x in opt_runs],
        "baseline_mean_tok_s": round(base, 2),
        "optimized_mean_tok_s": round(opt, 2),
        "throughput_delta_pct": _pct(opt, base),
        "baseline_implied_tpot_ms": round(1000.0 * batch / base, 2),
        "optimized_implied_tpot_ms": round(1000.0 * batch / opt, 2),
        "implied_tpot_delta_pct": _pct(1000.0 * batch / opt, 1000.0 * batch / base),
        "baseline_repeatability_pct": _pct(base_runs[1], base_runs[0]),
        "optimized_repeatability_pct": _pct(opt_runs[1], opt_runs[0]),
    }


def _factor(after: float, before: float) -> float:
    return round(after / before, 2)


def cumulative(meta: dict, stage: dict) -> dict:
    """Bring-up (May) against the optimized stack (July) on the same MI300X VMs and 1P1D layout."""
    may8 = _raw_json(meta["runs"]["bringup-20260508-pd"]["raw"][0])
    may10 = _raw_json(meta["runs"]["bringup-20260510-pd"]["raw"][0])
    long128 = _raw_json(meta["runs"]["long-20260720-128k"]["raw"][0])

    ab = may8["graph_capture_ab"]
    off, on = ab["graph_off"], ab["graph_on"]
    if off["failed"] or on["failed"]:
        raise SystemExit("GRAPH_AB_FAILED_REQUESTS")
    graph = {
        "run": "bringup-20260508-pd", "workload": ab["workload"],
        "off_output_tok_s": off["output_tok_s"], "on_output_tok_s": on["output_tok_s"],
        "output_tok_s_factor": _factor(on["output_tok_s"], off["output_tok_s"]),
        "off_p50_latency_s": off["p50_latency_s"], "on_p50_latency_s": on["p50_latency_s"],
        "p50_latency_factor": _factor(off["p50_latency_s"], on["p50_latency_s"]),
    }

    late_prefill = {r["input_tokens"]: r for r in stage["prefill"]}
    prefill = []
    for early in may8["prefill"]:
        n = early["input_len_target"]
        late = late_prefill.get(n)
        if late is None or late["concurrency"] != early["concurrency"] or early["failed"]:
            raise SystemExit(f"CUMULATIVE_PREFILL_UNPAIRED {n}")
        # the bring-up client sampled prompt lengths below the target; keep the pair only while the gap stays small
        if not 0.9 * n <= early["avg_prompt_tokens"] <= n:
            raise SystemExit(f"CUMULATIVE_PREFILL_LENGTH {n}: early prompts averaged {early['avg_prompt_tokens']}")
        prefill.append({
            "input_tokens": n, "concurrency": early["concurrency"],
            "early_avg_prompt_tokens": early["avg_prompt_tokens"],
            "early_run": "bringup-20260508-pd", "early_input_tok_s": early["input_tok_s"],
            "late_run": "stage-20260713-tuned-moe", "late_input_tok_s": late["after_input_tok_s"],
            "factor": _factor(late["after_input_tok_s"], early["input_tok_s"]),
        })
    rng = may10["single_vm_prefill_range"]
    point = next(p for p in long128["points"] if p["concurrency"] == 1)
    if point["status"] != "VALIDATED" or point["successful_requests"] != long128["workload"]["requests_per_point"]:
        raise SystemExit("LONG_128K_POINT_NOT_VALIDATED")
    if rng["input_tokens_high"] != long128["workload"]["input_tokens"]:
        raise SystemExit("LONG_128K_INPUT_DIFFERS")
    prefill.append({
        "input_tokens": rng["input_tokens_high"], "concurrency": 1,
        "early_topology": "one VM, TP8, prefill and decode in one server",
        "late_topology": "1P1D prefill server, TP8",
        "early_run": "bringup-20260510-pd", "early_input_tok_s": rng["input_tok_s_high"],
        "late_run": "long-20260720-128k", "late_input_tok_s": point["input_tok_s"],
        "factor": _factor(point["input_tok_s"], rng["input_tok_s_high"]),
    })

    real = {}
    for run in _parsed(meta["runs"]["realacc-20260714"]["raw"]):
        _check_success(run)
        a = run["args"]
        if (a["random_input_len"], a["random_output_len"]) != (8192, 1024):
            raise SystemExit(f"REALACC_WORKLOAD {run['source']}")
        real[a["max_concurrency"]] = run["metrics"]
    fixed = {r["concurrency"]: r for r in stage["decode"]}
    decode = []
    for early in may10["pd_decode"]:
        c = early["concurrency"]
        if c not in real or c not in fixed:
            continue
        r, f = real[c], fixed[c]
        decode.append({
            "concurrency": c,
            "early_mean_tpot_ms": early["mean_tpot_ms"], "early_output_tok_s": early["output_tok_s"],
            "real_mean_tpot_ms": r["mean_tpot_ms"], "real_output_tok_s": r["output_tok_s"],
            "fixed_mean_tpot_ms": f["after_mean_tpot_ms"], "fixed_output_tok_s": f["after_output_tok_s"],
            "real_tpot_factor": _factor(early["mean_tpot_ms"], r["mean_tpot_ms"]),
            "fixed_tpot_factor": _factor(early["mean_tpot_ms"], f["after_mean_tpot_ms"]),
            "real_output_factor": _factor(r["output_tok_s"], early["output_tok_s"]),
            "fixed_output_factor": _factor(f["after_output_tok_s"], early["output_tok_s"]),
        })
    if [d["concurrency"] for d in decode] != [32, 64]:
        raise SystemExit(f"CUMULATIVE_DECODE_POINTS {[d['concurrency'] for d in decode]}")
    return {
        "early_decode_workload": may10["decode_workload"],
        "late_decode_workload": {"input_tokens": 8192, "output_tokens": 1024},
        "graph_capture": graph, "prefill": prefill, "decode": decode,
    }


def build() -> dict:
    meta = _load_runs()
    _verify_manifest(meta)
    stage = tuned_moe_stage(meta)
    return {
        "schema": 1,
        "generated_by": "tools/build_evidence.py",
        "tuned_moe_stage": stage,
        "ab_ck_unified_verify_64k": ab_64k(meta),
        "concurrency_ladder_8k1k": concurrency_ladder(meta),
        "cumulative": cumulative(meta, stage),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if evidence/measurements.json is stale")
    args = ap.parse_args(argv)
    text = json.dumps(build(), indent=2) + "\n"
    target = EVIDENCE / "measurements.json"
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            print("STALE evidence/measurements.json; run tools/build_evidence.py")
            return 1
        print("PASS evidence/measurements.json is current")
        return 0
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
