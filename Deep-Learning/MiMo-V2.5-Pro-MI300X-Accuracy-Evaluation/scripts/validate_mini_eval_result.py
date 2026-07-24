#!/usr/bin/env python3
"""Fail closed unless the customer evaluator produced a complete result set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_MODEL_CONFIGS = {
    "aime": {
        "temperature": 1.0,
        "top_p": 0.95,
        "max_tokens": 65536,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
    },
    "cmmlu": {"temperature": 0, "top_p": 1, "max_tokens": 16384},
    "minerva_math": {"temperature": 0.0, "top_p": 1, "max_tokens": 16384},
    "mmlu_pro": {"temperature": 0, "top_p": 1, "max_tokens": 16384},
    "mmlu_redux": {"temperature": 0.0, "top_p": 1, "max_tokens": 16384},
    "supergpqa": {"temperature": 0.0, "top_p": 1, "max_tokens": 16384},
}


def newest(
    path: Path, pattern: str, min_mtime: float, min_mtime_ns: int | None
) -> Path:
    candidates = [
        candidate
        for candidate in path.glob(pattern)
        if (
            candidate.stat().st_mtime_ns >= min_mtime_ns
            if min_mtime_ns is not None
            else candidate.stat().st_mtime >= min_mtime
        )
    ]
    if not candidates:
        raise RuntimeError(f"no fresh file matched {pattern}")
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected exactly one fresh file for {pattern}, found {len(candidates)}: "
            + ", ".join(sorted(candidate.name for candidate in candidates))
        )
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("task", choices=sorted(EXPECTED_MODEL_CONFIGS))
    parser.add_argument("expected_samples", type=int)
    parser.add_argument("expected_repeats", type=int)
    parser.add_argument("min_mtime", type=float)
    parser.add_argument("--sample-offset", type=int, default=0)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--configured-repeats", type=int)
    parser.add_argument("--repeat-offset", type=int, default=0)
    parser.add_argument("--min-mtime-ns", type=int)
    args = parser.parse_args()

    result_path = newest(
        args.output_dir,
        f"{args.task}_results_*.jsonl",
        args.min_mtime,
        args.min_mtime_ns,
    )
    summary_path = newest(
        args.output_dir,
        f"{args.task}_summary_*.json",
        args.min_mtime,
        args.min_mtime_ns,
    )

    rows = [
        json.loads(line)
        for line in result_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != args.expected_samples:
        raise RuntimeError(
            f"expected {args.expected_samples} rows, found {len(rows)} in {result_path}"
        )

    row_ids = [int(row["id"]) for row in rows]
    if len(set(row_ids)) != len(row_ids):
        raise RuntimeError("result contains duplicate row ids")
    if args.shard_count == 1 or args.task != "supergpqa":
        expected_ids = set(
            range(args.sample_offset, args.sample_offset + args.expected_samples)
        )
        if set(row_ids) != expected_ids:
            raise RuntimeError("result row ids do not match expected coverage")

    expected_repeat_indices = None
    if args.task == "aime":
        configured_repeats = args.configured_repeats or args.expected_repeats
        expected_repeat_indices = {
            repeat_idx
            for repeat_idx in range(configured_repeats)
            if repeat_idx % args.shard_count == args.shard_index
        }
        if len(expected_repeat_indices) != args.expected_repeats:
            raise RuntimeError("AIME shard repeat count does not match the contract")

    empty_responses = 0
    calculated_metrics = []
    for row in rows:
        responses = row.get("model_responses", [])
        predictions = row.get("extracted_preds", [])
        metrics = row.get("metrics", [])
        repeat_indices = row.get("repeat_indices")
        response_metadata = row.get("response_metadata")
        if len(responses) != args.expected_repeats:
            raise RuntimeError(
                f"row {row.get('id')} has {len(responses)} responses, expected {args.expected_repeats}"
            )
        if len(metrics) != args.expected_repeats:
            raise RuntimeError(
                f"row {row.get('id')} has {len(metrics)} metrics, expected {args.expected_repeats}"
            )
        if len(predictions) != args.expected_repeats:
            raise RuntimeError(
                f"row {row.get('id')} has {len(predictions)} predictions, expected {args.expected_repeats}"
            )
        if any(metric not in (0, 1) for metric in metrics):
            raise RuntimeError(f"row {row.get('id')} contains non-binary metrics")
        if args.task == "aime":
            if repeat_indices is None:
                raise RuntimeError(f"AIME row {row.get('id')} has no repeat provenance")
            normalized_repeat_indices = [int(value) for value in repeat_indices]
            if len(normalized_repeat_indices) != args.expected_repeats:
                raise RuntimeError(
                    f"AIME row {row.get('id')} has an invalid repeat provenance length"
                )
            if len(set(normalized_repeat_indices)) != len(normalized_repeat_indices):
                raise RuntimeError(
                    f"AIME row {row.get('id')} has duplicate repeat provenance"
                )
            if set(normalized_repeat_indices) != expected_repeat_indices:
                raise RuntimeError(
                    f"AIME row {row.get('id')} repeat provenance does not match the shard contract"
                )
        else:
            if response_metadata is None or len(response_metadata) != args.expected_repeats:
                raise RuntimeError(
                    f"row {row.get('id')} has no complete repeat provenance"
                )
            actual_repeat_indices = [
                int(metadata.get("repeat_idx")) for metadata in response_metadata
            ]
            expected_non_aime_repeats = set(
                range(args.repeat_offset, args.repeat_offset + args.expected_repeats)
            )
            if len(set(actual_repeat_indices)) != len(actual_repeat_indices):
                raise RuntimeError(
                    f"row {row.get('id')} has duplicate repeat provenance"
                )
            if set(actual_repeat_indices) != expected_non_aime_repeats:
                raise RuntimeError(
                    f"row {row.get('id')} repeat provenance does not match "
                    f"the expected range {sorted(expected_non_aime_repeats)}"
                )
        for index, response in enumerate(responses):
            if response:
                continue
            empty_responses += 1
            if response_metadata is None or len(response_metadata) != len(responses):
                raise RuntimeError(
                    f"row {row.get('id')} has an unexplained empty response"
                )
            metadata = response_metadata[index]
            if not (
                metadata.get("finish_reason") == "length"
                and metadata.get("completion_tokens")
                == EXPECTED_MODEL_CONFIGS[args.task]["max_tokens"]
                and int(metrics[index]) == 0
            ):
                raise RuntimeError(
                    f"row {row.get('id')} has an invalid empty response"
                )
        calculated_metrics.extend(metrics)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("repeats") != args.expected_repeats:
        raise RuntimeError("summary repeat count does not match the run contract")
    if summary.get("model_config") != EXPECTED_MODEL_CONFIGS[args.task]:
        raise RuntimeError("summary model_config does not match the customer contract")
    calculated_accuracy = sum(calculated_metrics) / len(calculated_metrics)
    if abs(float(summary.get("accuracy")) - calculated_accuracy) > 1e-12:
        raise RuntimeError("summary accuracy does not match recomputed metrics")

    print(
        "MINI_EVAL_RESULT=PASS "
        f"task={args.task} samples={len(rows)} repeats={args.expected_repeats} "
        f"empty_responses={empty_responses} accuracy={calculated_accuracy}"
    )


if __name__ == "__main__":
    main()
