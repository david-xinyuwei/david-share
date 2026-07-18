#!/usr/bin/env python3
"""Recompute the public 128K/192K controlled-ISL evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/evidence/controlled-isl-128k-192k"
RESULTS = ROOT / "data/controlled-isl-results.tsv"
AUDIT = ROOT / "data/validation/controlled-isl-evidence.json"
SCHEDULER_PATTERN = re.compile(
    r"Decode batch, #running-req: (?P<running>\d+), #full token: (?P<full>\d+), "
    r"full token usage: (?P<usage>[0-9.]+), .*?accept len: (?P<accept_len>[0-9.]+), "
    r"accept rate: (?P<accept_rate>[0-9.]+), .*?gen throughput \(token/s\): "
    r"(?P<throughput>[0-9.]+), #queue-req: (?P<queued>\d+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute 128K/192K Prefill and steady-BS4 Decode evidence."
    )
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(directory: Path) -> None:
    manifest = directory / "SHA256SUMS.txt"
    covered = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        covered.add(name)
        actual = sha256(directory / name)
        if actual != expected:
            raise ValueError(f"SHA mismatch: {name}")
    expected_files = {
        "README.md",
        "prefill-128k.client.txt",
        "prefill-192k.client.txt",
        "decode-128k.client.txt",
        "decode-192k.client.txt",
        "decode-128k.scheduler.txt",
        "decode-192k.scheduler.txt",
        "optimized-kernel-marker.txt",
    }
    if covered != expected_files:
        raise ValueError(f"Evidence manifest coverage mismatch: {covered}")


def parse_client(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def parse_scheduler(path: Path) -> dict[str, object]:
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = SCHEDULER_PATTERN.search(line)
        if not match:
            raise ValueError(f"Unrecognized scheduler line: {line}")
        samples.append(
            {
                "running": int(match.group("running")),
                "full_tokens": int(match.group("full")),
                "full_token_usage": float(match.group("usage")),
                "accept_len": float(match.group("accept_len")),
                "accept_rate": float(match.group("accept_rate")),
                "gen_tok_s": float(match.group("throughput")),
                "queued": int(match.group("queued")),
            }
        )
    if len(samples) != 8:
        raise ValueError(f"Expected 8 full-BS4 samples in {path}, found {len(samples)}")
    if {sample["running"] for sample in samples} != {4}:
        raise ValueError("Expected actual Decode batch 4")
    if {sample["accept_len"] for sample in samples} != {3.0}:
        raise ValueError("Expected simulated accept length 3.00")
    if {sample["accept_rate"] for sample in samples} != {0.67}:
        raise ValueError("Expected scheduler-reported accept rate 0.67")
    if {sample["queued"] for sample in samples} != {0}:
        raise ValueError("Expected zero queued requests in full-BS4 samples")

    subsequent = [sample["gen_tok_s"] for sample in samples[1:]]
    subsequent_median = statistics.median(subsequent)
    exclude_first = samples[0]["gen_tok_s"] < 0.5 * subsequent_median
    used = samples[1:] if exclude_first else samples
    if len(used) < 2:
        raise ValueError("Insufficient steady full-BS4 samples")
    values = [sample["gen_tok_s"] for sample in used]
    mean_gen_tok_s = round(statistics.mean(values), 2)
    return {
        "raw_full_batch_samples": len(samples),
        "transition_first_sample_tok_s": samples[0]["gen_tok_s"],
        "subsequent_median_tok_s": round(subsequent_median, 2),
        "transition_sample_excluded": exclude_first,
        "samples_used": len(used),
        "used_gen_tok_s": values,
        "mean_gen_tok_s": mean_gen_tok_s,
        "median_gen_tok_s": round(statistics.median(values), 2),
        "stdev_gen_tok_s": round(statistics.pstdev(values), 2),
        "implied_tpot_ms": round(1000 / (mean_gen_tok_s / 4), 2),
        "full_token_usage_min": min(sample["full_token_usage"] for sample in used),
        "full_token_usage_max": max(sample["full_token_usage"] for sample in used),
    }


def load_results(path: Path) -> dict[tuple[str, int], dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 4 or any(None in row for row in rows):
        raise ValueError("Expected exactly four valid result rows")
    return {(row["surface"], int(row["input_tokens"])): row for row in rows}


def analyze_prefill(evidence: Path, input_tokens: int) -> dict[str, object]:
    label = input_tokens // 1024
    client = parse_client(evidence / f"prefill-{label}k.client.txt")
    if client["surface"] != "prefill":
        raise ValueError("Expected Prefill evidence")
    if int(client["input_tokens_per_request"]) != input_tokens:
        raise ValueError("Prefill input mismatch")
    if int(client["requested_output_tokens_per_request"]) != 1:
        raise ValueError("Expected Prefill OSL 1")
    if int(client["client_concurrency"]) != 4 or int(client["num_prompts"]) != 16:
        raise ValueError("Expected Prefill c4 and 16 prompts")
    if int(client["successful_requests"]) != 16:
        raise ValueError("Expected 16 successful Prefill requests")
    if int(client["total_input_tokens"]) != input_tokens * 16:
        raise ValueError("Prefill input-token total mismatch")
    if int(client["total_generated_tokens"]) != 16:
        raise ValueError("Prefill server-accounted output mismatch")
    if int(client["total_generated_tokens_retokenized"]) != 16:
        raise ValueError("Prefill retokenized output mismatch")
    duration = float(client["benchmark_duration_s"])
    throughput = float(client["input_token_throughput_tok_s"])
    if not math.isclose(input_tokens * 16 / duration, throughput, rel_tol=0.001):
        raise ValueError("Prefill input-throughput arithmetic mismatch")
    return {
        "surface": "prefill",
        "input_tokens": input_tokens,
        "input_tok_s": throughput,
        "mean_ttft_ms": float(client["mean_ttft_ms"]),
        "measurement_repetitions": int(client["measurement_repetitions"]),
    }


def analyze_decode(evidence: Path, input_tokens: int) -> dict[str, object]:
    label = input_tokens // 1024
    client = parse_client(evidence / f"decode-{label}k.client.txt")
    if client["surface"] != "decode":
        raise ValueError("Expected Decode evidence")
    if int(client["input_tokens_per_request"]) != input_tokens:
        raise ValueError("Decode input mismatch")
    if int(client["requested_output_tokens_per_request"]) != 1024:
        raise ValueError("Expected Decode OSL 1024")
    if int(client["client_concurrency"]) != 4 or int(client["num_prompts"]) != 4:
        raise ValueError("Expected client c4 and four prompts")
    if int(client["successful_requests"]) != 4:
        raise ValueError("Expected four successful Decode requests")
    if int(client["total_input_tokens"]) != input_tokens * 4:
        raise ValueError("Decode input-token total mismatch")
    if int(client["total_generated_tokens"]) != 4096:
        raise ValueError("Decode server-accounted output mismatch")
    if int(client["total_generated_tokens_retokenized"]) <= 0:
        raise ValueError("Missing Decode retokenized output accounting")
    if client["acceptance_mode"] != "simulated_match_expected":
        raise ValueError("Expected fixed simulated acceptance")
    duration = float(client["benchmark_duration_s"])
    output_tok_s = float(client["output_token_throughput_tok_s"])
    if not math.isclose(4096 / duration, output_tok_s, rel_tol=0.001, abs_tol=0.005):
        raise ValueError("Decode client-output arithmetic mismatch")
    scheduler = parse_scheduler(evidence / f"decode-{label}k.scheduler.txt")
    return {
        "surface": "decode",
        "input_tokens": input_tokens,
        "client_output_tok_s": output_tok_s,
        "mean_ttft_ms": float(client["mean_ttft_ms"]),
        "mean_tpot_ms": float(client["mean_tpot_ms"]),
        "measurement_repetitions": int(client["measurement_repetitions"]),
        "scheduler": scheduler,
    }


def main() -> None:
    args = parse_args()
    check_manifest(args.evidence)
    marker = (args.evidence / "optimized-kernel-marker.txt").read_text(encoding="utf-8")
    if "module_gemm_a8w8_blockscale_bpreshuffle" not in marker:
        raise ValueError("Optimized CK marker missing")

    points = {
        ("prefill", 131072): analyze_prefill(args.evidence, 131072),
        ("prefill", 196608): analyze_prefill(args.evidence, 196608),
        ("decode", 131072): analyze_decode(args.evidence, 131072),
        ("decode", 196608): analyze_decode(args.evidence, 196608),
    }
    published = load_results(args.results)
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    if audit["status"] != "VALIDATED" or audit["measurement_repetitions_per_point"] != 1:
        raise ValueError("Published audit status mismatch")
    fixed = audit["method"]["fixed_acceptance"]
    if fixed["validates_natural_acceptance"] or fixed["validates_output_quality"]:
        raise ValueError("Fixed-acceptance scope is overstated")
    if audit["scope"]["historical_202606_bs1_included"]:
        raise ValueError("Historical BS1 data must not enter this result family")

    audit_points = {
        (point["surface"], point["input_tokens"]): point for point in audit["points"]
    }
    for key, point in points.items():
        row = published[key]
        if row["measurement_date"] != "2026-07-19":
            raise ValueError("Measurement date mismatch")
        if row["measurement_repetitions"] != "1" or row["status"] != "VALIDATED":
            raise ValueError("Result repetition/status mismatch")
        if "202606" in row["source_run"] or "bs1" in row["source_run"].lower():
            raise ValueError("Historical BS1 source contamination")
        if key[0] == "prefill":
            headline = point["input_tok_s"]
            if row["headline_metric"] != "input_tok_s":
                raise ValueError("Prefill headline metric mismatch")
        else:
            headline = point["scheduler"]["mean_gen_tok_s"]
            if row["headline_metric"] != "steady_bs4_scheduler_gen_tok_s":
                raise ValueError("Decode headline metric mismatch")
            if row["actual_decode_batch"] != "4":
                raise ValueError("Decode batch mismatch")
        if float(row["headline_value"]) != headline:
            raise ValueError(f"TSV headline mismatch for {key}")
        if audit_points[key]["headline_value"] != headline:
            raise ValueError(f"Audit headline mismatch for {key}")

    prefill_delta = round(
        (points[("prefill", 196608)]["input_tok_s"]
         / points[("prefill", 131072)]["input_tok_s"] - 1) * 100,
        1,
    )
    decode_delta = round(
        (points[("decode", 196608)]["scheduler"]["mean_gen_tok_s"]
         / points[("decode", 131072)]["scheduler"]["mean_gen_tok_s"] - 1) * 100,
        1,
    )
    tpot_delta = round(
        (points[("decode", 196608)]["mean_tpot_ms"]
         / points[("decode", 131072)]["mean_tpot_ms"] - 1) * 100,
        1,
    )
    ttft_delta = round(
        (points[("decode", 196608)]["mean_ttft_ms"]
         / points[("decode", 131072)]["mean_ttft_ms"] - 1) * 100,
        1,
    )
    computed_deltas = {
        "prefill_input_tok_s_pct": prefill_delta,
        "decode_scheduler_gen_tok_s_pct": decode_delta,
        "decode_mean_tpot_pct": tpot_delta,
        "decode_mean_ttft_pct": ttft_delta,
    }
    if audit["deltas_128k_to_192k"] != computed_deltas:
        raise ValueError("Published delta mismatch")

    result = {
        "status": "PASS",
        "method_identity": "controlled_128k_192k_fixed_acceptance_performance_measurement",
        "evidence_scope": {
            "independently_recomputes_disclosed_sanitized_records": True,
            "checks_consistency_with_published_tsv_and_audit": True,
            "proves_private_full_log_provenance_or_completeness": False,
        },
        "acceptance_configuration": {
            "SGLANG_SIMULATE_ACC_LEN": 3,
            "SGLANG_SIMULATE_ACC_METHOD": "match-expected",
            "validates_natural_acceptance": False,
            "validates_output_quality": False,
        },
        "points": [points[key] for key in sorted(points)],
        "deltas_128k_to_192k": computed_deltas,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()