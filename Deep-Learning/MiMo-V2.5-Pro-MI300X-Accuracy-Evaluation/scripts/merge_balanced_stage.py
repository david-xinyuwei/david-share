#!/usr/bin/env python3
"""Merge a variable-size balanced-stage task using validated chunk markers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from merge_chunked_eval import artifact, load_jsonl, merge_aime, merge_sample_chunks, read_marker


TASK_NAMES = {
    "aime": "AIME_24_25",
    "cmmlu": "CMMLU",
    "minerva_math": "Minerva Math",
    "mmlu_pro": "MMLU-Pro",
    "mmlu_redux": "MMLU-Redux",
    "supergpqa": "SuperGPQA",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=sorted(TASK_NAMES))
    parser.add_argument("marker_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("samples", type=int)
    parser.add_argument("repeats", type=int)
    args = parser.parse_args()

    markers = sorted(args.marker_dir.glob("*.done"))
    if not markers:
        raise RuntimeError("no completed stage chunk markers found")
    prefixes = [read_marker(marker) for marker in markers]
    result_paths = [artifact(prefix, f"{args.task}_results_") for prefix in prefixes]
    summary_paths = [artifact(prefix, f"{args.task}_summary_") for prefix in prefixes]
    model_configs = {
        json.dumps(
            json.loads(path.read_text(encoding="utf-8"))["model_config"],
            sort_keys=True,
        )
        for path in summary_paths
    }
    if len(model_configs) != 1:
        raise RuntimeError("stage chunk sampling configurations do not match")
    model_config = json.loads(model_configs.pop())

    if args.task == "aime":
        rows = merge_aime(result_paths, args.samples, args.repeats)
    else:
        rows = merge_sample_chunks(result_paths, args.samples, args.repeats)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / f"{args.task}_results_merged.jsonl"
    summary_path = args.output_dir / f"{args.task}_summary_merged.json"
    with result_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    metrics = [metric for row in rows for metric in row["metrics"]]
    responses = [response for row in rows for response in row["model_responses"]]
    summary = {
        "task": TASK_NAMES[args.task],
        "model": "MiMo-V2.5-Pro",
        "scope": "balanced_interim_coverage_not_xiaomi_final_contract",
        "model_config": model_config,
        "repeats": args.repeats,
        "samples": args.samples,
        "chunks": len(markers),
        "total_responses": len(metrics),
        "correct": sum(metrics),
        "empty_responses": sum(not response for response in responses),
        "accuracy": sum(metrics) / len(metrics),
        "eval_time": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"BALANCED_STAGE_MERGE=PASS task={args.task} chunks={len(markers)} "
        f"samples={args.samples} repeats={args.repeats} responses={len(metrics)} "
        f"accuracy={summary['accuracy']:.8f}"
    )


if __name__ == "__main__":
    main()
