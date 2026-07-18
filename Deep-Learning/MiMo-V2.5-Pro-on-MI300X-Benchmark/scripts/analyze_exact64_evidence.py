#!/usr/bin/env python3
"""Recompute the public exact-64K fixed-acceptance Decode evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/evidence/exact64-fixed-acceptance"
AUDIT = ROOT / "data/validation/decode-fixed-batch-audit.json"
SCHEDULER_PATTERN = re.compile(
    r"Decode batch, #running-req: (?P<running>\d+), #full token: (?P<full>\d+), "
    r".*?accept len: (?P<accept_len>[0-9.]+), accept rate: (?P<accept_rate>[0-9.]+), "
    r".*?gen throughput \(token/s\): (?P<throughput>[0-9.]+), "
    r"#queue-req: (?P<queued>\d+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute exact 64K/1K BS16 fixed-acceptance evidence."
    )
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    return parser.parse_args()


def check_manifest(directory: Path) -> None:
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"SHA mismatch: {name}")


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
        sample = {
            "running_requests": int(match.group("running")),
            "full_tokens": int(match.group("full")),
            "accept_length": float(match.group("accept_len")),
            "accept_rate": float(match.group("accept_rate")),
            "gen_tok_s": float(match.group("throughput")),
            "queued_requests": int(match.group("queued")),
        }
        samples.append(sample)

    if len(samples) != 8:
        raise ValueError(f"Expected 8 full-batch samples in {path}, found {len(samples)}")
    if {sample["running_requests"] for sample in samples} != {16}:
        raise ValueError("Expected fixed batch 16")
    if {sample["accept_length"] for sample in samples} != {3.0}:
        raise ValueError("Expected simulated accept length 3.00")
    if {sample["accept_rate"] for sample in samples} != {0.67}:
        raise ValueError("Expected scheduler-reported rate 0.67")
    if {sample["queued_requests"] for sample in samples} != {0}:
        raise ValueError("Expected zero queued requests")

    subsequent = [sample["gen_tok_s"] for sample in samples[1:]]
    subsequent_median = statistics.median(subsequent)
    exclude_first = samples[0]["gen_tok_s"] < 0.5 * subsequent_median
    used = samples[1:] if exclude_first else samples
    throughputs = [sample["gen_tok_s"] for sample in used]
    mean_gen_tok_s = round(statistics.mean(throughputs), 2)
    return {
        "raw_full_batch_samples": len(samples),
        "transition_first_sample_tok_s": samples[0]["gen_tok_s"],
        "subsequent_median_tok_s": round(subsequent_median, 2),
        "transition_sample_excluded": exclude_first,
        "samples_used": len(used),
        "used_gen_tok_s": throughputs,
        "mean_gen_tok_s": mean_gen_tok_s,
        "median_gen_tok_s": round(statistics.median(throughputs), 2),
        "stdev_gen_tok_s": round(statistics.pstdev(throughputs), 2),
        "implied_tpot_ms": round(1000 / (mean_gen_tok_s / 16), 2),
    }


def analyze_variant(evidence: Path, prefix: str) -> list[dict[str, object]]:
    results = []
    for repetition in (1, 2):
        client = parse_client(evidence / f"{prefix}-rep{repetition}.client.txt")
        if int(client["successful_requests"]) != 16:
            raise ValueError("Expected 16 successful requests")
        if int(client["total_input_tokens"]) != 65536 * 16:
            raise ValueError("Input-token total mismatch")
        if int(client["total_generated_tokens"]) != 1024 * 16:
            raise ValueError("Server-accounted output-token total mismatch")
        if int(client["total_generated_tokens_retokenized"]) != 4112:
            raise ValueError("Retokenized generated-text total mismatch")
        if client["acceptance_mode"] != "simulated_match_expected":
            raise ValueError("Expected fixed simulated acceptance")
        results.append(
            {
                "repetition": repetition,
                "client": {
                    "successful_requests": int(client["successful_requests"]),
                    "total_input_tokens": int(client["total_input_tokens"]),
                    "total_generated_tokens": int(client["total_generated_tokens"]),
                    "total_generated_tokens_retokenized": int(
                        client["total_generated_tokens_retokenized"]
                    ),
                    "output_token_throughput_tok_s": float(
                        client["output_token_throughput_tok_s"]
                    ),
                },
                "scheduler": parse_scheduler(
                    evidence / f"{prefix}-rep{repetition}.scheduler.txt"
                ),
            }
        )
    return results


def main() -> None:
    args = parse_args()
    check_manifest(args.evidence)
    marker = (args.evidence / "optimized-kernel-marker.txt").read_text(
        encoding="utf-8"
    )
    if "module_gemm_a8w8_blockscale_bpreshuffle" not in marker:
        raise ValueError("Optimized-kernel marker missing")

    optimized = analyze_variant(args.evidence, "optimized")
    baseline = analyze_variant(args.evidence, "baseline")
    optimized_means = [point["scheduler"]["mean_gen_tok_s"] for point in optimized]
    baseline_means = [point["scheduler"]["mean_gen_tok_s"] for point in baseline]
    optimized_mean = round(statistics.mean(optimized_means), 2)
    baseline_mean = round(statistics.mean(baseline_means), 2)
    aggregate = {
        "optimized_run_means_tok_s": optimized_means,
        "optimized_mean_tok_s": optimized_mean,
        "optimized_repeat_delta_pct": round(
            (optimized_means[1] / optimized_means[0] - 1) * 100, 2
        ),
        "optimized_implied_tpot_ms": round(1000 / (optimized_mean / 16), 2),
        "baseline_run_means_tok_s": baseline_means,
        "baseline_mean_tok_s": baseline_mean,
        "baseline_repeat_delta_pct": round(
            (baseline_means[1] / baseline_means[0] - 1) * 100, 2
        ),
        "baseline_implied_tpot_ms": round(1000 / (baseline_mean / 16), 2),
        "optimized_uplift_pct": round((optimized_mean / baseline_mean - 1) * 100, 1),
    }

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    published = audit["headline_exact"]["aggregate"]
    expected = {
        "optimized_mean_tok_s": published["mean_of_fresh_runs_tok_s"],
        "optimized_repeat_delta_pct": published[
            "repeatability_delta_pct_run2_vs_run1"
        ],
        "optimized_implied_tpot_ms": published["implied_tpot_ms_at_batch"],
        "baseline_mean_tok_s": published["same_image_exact_no_ck_baseline_tok_s"],
        "optimized_uplift_pct": published["optimized_path_improvement_pct"],
    }
    for key, value in expected.items():
        if aggregate[key] != value:
            raise ValueError(f"Published audit mismatch for {key}: {aggregate[key]} != {value}")

    result = {
        "status": "PASS",
        "method_identity": "fixed_acceptance_performance_benchmark",
        "evidence_scope": {
            "independently_recomputes_disclosed_sanitized_windows": True,
            "checks_consistency_with_published_audit": True,
            "proves_private_full_log_provenance_or_completeness": False,
        },
        "acceptance_configuration": {
            "SGLANG_SIMULATE_ACC_LEN": 3,
            "SGLANG_SIMULATE_ACC_METHOD": "match-expected",
            "validates_natural_acceptance": False,
            "validates_output_quality": False,
        },
        "output_accounting": {
            "server_accounted_output_tokens_per_repetition": 16384,
            "retokenized_generated_text_tokens_per_repetition": 4112,
            "definition": "retokenized is tokenizer.encode(generated_text) length",
        },
        "optimized": optimized,
        "baseline_no_ck": baseline,
        "aggregate": aggregate,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()