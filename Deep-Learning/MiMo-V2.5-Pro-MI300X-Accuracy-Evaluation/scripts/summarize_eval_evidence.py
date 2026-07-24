#!/usr/bin/env python3
"""Summarize one evaluation evidence bundle without replacing raw artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean, median


DECODE_PATTERN = re.compile(
    r"accept len: (?P<accept_length>[0-9.]+), "
    r"accept rate: (?P<accept_rate>[0-9.]+).*?"
    r"gen throughput \(token/s\): (?P<throughput>[0-9.]+)"
)


def percentile(values: list[int], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = fraction * (len(ordered) - 1)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def find_artifact(prefix: Path, marker: str) -> Path | None:
    matches = sorted(prefix.parent.glob(f"{prefix.name}.artifact.*{marker}*"))
    return matches[-1] if matches else None


def load_rows(path: Path | None) -> list[dict]:
    if path is None:
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_key_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


def summarize_repeats(prefix: Path, rows: list[dict], metrics: list[int]) -> tuple[dict, list[dict]]:
    env = parse_key_values(prefix.with_suffix(".env"))
    live_path = Path(env["live_progress_file"])
    if live_path.is_file():
        repeat_records = load_rows(live_path)
        repeat_source = "live_progress"
    else:
        repeat_records = []
        for row in rows:
            metadata = row.get("response_metadata") or []
            row_metrics = row.get("metrics") or []
            responses = row.get("model_responses") or []
            if not (
                len(metadata) == len(row_metrics) == len(responses)
                and all(item.get("repeat_idx") is not None for item in metadata)
            ):
                repeat_records = []
                break
            repeat_records.extend(
                {
                    "repeat_idx": int(item["repeat_idx"]),
                    "metric": metric,
                    "response_empty": not response,
                }
                for item, metric, response in zip(metadata, row_metrics, responses)
            )
        repeat_source = "response_metadata"

    expected_repeats = int(env.get("expected_repeats", env["repeats"]))
    contract = {
        "dataset_samples": int(env.get("dataset_samples", len(rows))),
        "executed_unique_samples": len(rows),
        "configured_repeats": int(env["repeats"]),
        "executed_repeats": expected_repeats,
        "expected_total_responses": len(rows) * expected_repeats,
        "actual_total_responses": len(metrics),
    }
    if contract["expected_total_responses"] != contract["actual_total_responses"]:
        raise RuntimeError("expected/actual response mismatch")
    if not repeat_records:
        contract.update(
            {
                "repeat_results_available": False,
                "repeat_results_unavailable_reason": (
                    "run predates repeat_idx provenance; configured repeat count and "
                    "aggregate result are verified, but per-repeat attribution is not provable"
                ),
            }
        )
        return contract, []
    if len(repeat_records) != len(metrics):
        raise RuntimeError(
            f"repeat/result response count mismatch: {len(repeat_records)} != {len(metrics)}"
        )
    if sum(int(record["metric"]) for record in repeat_records) != sum(metrics):
        raise RuntimeError("repeat/result correct-count mismatch")

    grouped: dict[int, list[dict]] = {}
    for record in repeat_records:
        grouped.setdefault(int(record["repeat_idx"]), []).append(record)
    if len(grouped) != expected_repeats:
        raise RuntimeError(f"repeat coverage mismatch: {len(grouped)} != {expected_repeats}")

    repeat_results = []
    cumulative_responses = cumulative_correct = 0
    for repeat_idx in sorted(grouped):
        records = grouped[repeat_idx]
        if len(records) != len(rows):
            raise RuntimeError(
                f"repeat {repeat_idx} has {len(records)} responses, expected {len(rows)}"
            )
        correct = sum(int(record["metric"]) for record in records)
        empty = sum(bool(record.get("response_empty")) for record in records)
        cumulative_responses += len(records)
        cumulative_correct += correct
        repeat_results.append(
            {
                "repeat_index_zero_based": repeat_idx,
                "repeat_number": repeat_idx + 1,
                "responses": len(records),
                "correct": correct,
                "empty_responses": empty,
                "accuracy": correct / len(records),
                "cumulative_responses": cumulative_responses,
                "cumulative_correct": cumulative_correct,
                "cumulative_accuracy": cumulative_correct / cumulative_responses,
            }
        )

    contract.update(
        {
            "repeat_results_available": True,
            "repeat_result_source": repeat_source,
            "repeat_indices_zero_based": sorted(grouped),
        }
    )
    return contract, repeat_results


def parse_server_window(path: Path) -> dict:
    samples = []
    for match in DECODE_PATTERN.finditer(path.read_text(encoding="utf-8", errors="replace")):
        samples.append(
            {
                "accept_length": float(match.group("accept_length")),
                "accept_rate": float(match.group("accept_rate")),
                "generation_throughput_tokens_per_second": float(
                    match.group("throughput")
                ),
            }
        )
    if not samples:
        return {"decode_log_samples": 0}
    return {
        "decode_log_samples": len(samples),
        "accept_length_mean": mean(item["accept_length"] for item in samples),
        "accept_length_min": min(item["accept_length"] for item in samples),
        "accept_length_max": max(item["accept_length"] for item in samples),
        "accept_rate_mean": mean(item["accept_rate"] for item in samples),
        "accept_rate_min": min(item["accept_rate"] for item in samples),
        "accept_rate_max": max(item["accept_rate"] for item in samples),
        "generation_throughput_mean_tokens_per_second": mean(
            item["generation_throughput_tokens_per_second"] for item in samples
        ),
        "note": "Unweighted decode-log interval summary; raw server window is authoritative.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", type=Path)
    args = parser.parse_args()
    prefix = args.prefix

    result_path = find_artifact(prefix, "_results_")
    summary_path = find_artifact(prefix, "_summary_")
    rows = load_rows(result_path)
    responses = [response for row in rows for response in row.get("model_responses", [])]
    metrics = [metric for row in rows for metric in row.get("metrics", [])]
    response_chars = [len(response) for response in responses]
    contract, repeat_results = summarize_repeats(prefix, rows, metrics)

    report = {
        "evidence_prefix": str(prefix),
        "raw_result": str(result_path) if result_path else None,
        "raw_summary": str(summary_path) if summary_path else None,
        "samples": len(rows),
        "responses": len(responses),
        "correct": sum(metrics) if metrics else None,
        "empty_responses": sum(not response for response in responses),
        "accuracy": sum(metrics) / len(metrics) if metrics else None,
        "run_contract": contract,
        "repeat_results": repeat_results,
        "response_chars": {
            "total": sum(response_chars),
            "min": min(response_chars) if response_chars else None,
            "p50": median(response_chars) if response_chars else None,
            "p90": percentile(response_chars, 0.9),
            "p95": percentile(response_chars, 0.95),
            "max": max(response_chars) if response_chars else None,
        },
    }

    server_window = prefix.with_suffix(".server-window.log")
    report["speculative_decoding"] = (
        parse_server_window(server_window)
        if server_window.exists()
        else {"decode_log_samples": 0}
    )
    report["sampling_config"] = (
        json.loads(summary_path.read_text(encoding="utf-8")).get("model_config")
        if summary_path
        else None
    )
    prefix.with_suffix(".evidence-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()