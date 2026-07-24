#!/usr/bin/env python3
"""Build a public, auditable accuracy snapshot without redistributing prompts.

The input directory is a private staging area containing validated evaluator
outputs. Public per-response records retain identifiers, metrics, finish
metadata, and content hashes, but omit benchmark prompt text, ground-truth text,
and generated response text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DATASET_SPECS = {
    "aime": {
        "display_name": "AIME24_25",
        "category": "competition mathematics reasoning",
        "total_questions": 60,
        "final_repeats": 32,
        "h200_reference_accuracy": 0.903,
        "phase": "validated canary",
    },
    "cmmlu": {
        "display_name": "CMMLU",
        "category": "Chinese multi-subject knowledge and reasoning",
        "total_questions": 11_582,
        "final_repeats": 3,
        "h200_reference_accuracy": 0.901,
        "phase": "validated canary plus repeat completion",
    },
    "minerva_math": {
        "display_name": "MinervaMath",
        "category": "mathematical problem solving",
        "total_questions": 5_000,
        "final_repeats": 3,
        "h200_reference_accuracy": 0.936,
        "phase": "validated interim subset",
    },
    "mmlu_pro": {
        "display_name": "MMLU-Pro",
        "category": "advanced multi-subject knowledge and reasoning",
        "total_questions": 12_032,
        "final_repeats": 2,
        "h200_reference_accuracy": 0.851,
        "phase": "validated interim subset",
    },
    "mmlu_redux": {
        "display_name": "MMLU-Redux",
        "category": "cleaned multi-subject evaluation",
        "total_questions": 5_330,
        "final_repeats": 6,
        "h200_reference_accuracy": 0.9497,
        "phase": "validated interim subset",
    },
    "supergpqa": {
        "display_name": "SuperGPQA",
        "category": "graduate and expert-level multi-domain QA",
        "total_questions": 26_529,
        "final_repeats": 1,
        "h200_reference_accuracy": 0.624,
        "phase": "validated interim subset",
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def result_path(root: Path, dataset: str) -> list[Path]:
    patterns = {
        "aime": [root / "aime" / "results.jsonl"],
        "cmmlu": [
            root / "cmmlu-r0" / "results.jsonl",
            *sorted((root / "cmmlu-r1-2").glob("*.artifact.cmmlu_results_*.jsonl")),
        ],
        "minerva_math": sorted((root / "minerva" / "raw" / "results").glob("*results*.jsonl")),
        "mmlu_pro": list((root / "mmlu-pro").rglob("*.artifact.mmlu_pro_results_*.jsonl")),
        "mmlu_redux": [root / "mmlu-redux" / "results.jsonl"],
        "supergpqa": [
            root
            / "supergpqa"
            / "balanced-stage"
            / "vm10"
            / "supergpqa"
            / "merged"
            / "supergpqa_results_merged.jsonl"
        ],
    }
    paths = patterns[dataset]
    if not paths or any(not path.is_file() for path in paths):
        raise RuntimeError(f"missing private result inputs for {dataset}: {paths}")
    return paths


def metadata_for(row: dict[str, Any], index: int) -> dict[str, Any]:
    metadata = row.get("response_metadata")
    if isinstance(metadata, list) and index < len(metadata):
        return metadata[index] or {}
    return {}


def response_repeat_ids(
    dataset: str,
    source_index: int,
    row: dict[str, Any],
) -> tuple[list[int | None], str]:
    metrics = row["metrics"]
    if dataset == "aime":
        ids = [int(value) for value in row.get("repeat_indices", [])]
        return ids, "explicit"
    metadata_ids = [metadata_for(row, index).get("repeat_idx") for index in range(len(metrics))]
    if all(value is not None for value in metadata_ids):
        return [int(value) for value in metadata_ids], "explicit"
    if dataset == "cmmlu" and source_index == 0 and len(metrics) == 1:
        return [0], "legacy-single-run-inferred"
    if dataset == "supergpqa" and len(metrics) == 1:
        return [0], "legacy-single-run-inferred"
    if dataset == "mmlu_pro":
        return [None] * len(metrics), "aggregate-only-repeat-attribution-unavailable"
    if dataset == "minerva_math" and len(metrics) == 3:
        return [None] * len(metrics), "aggregate-ordered-slots-repeat-attribution-unavailable"
    raise RuntimeError(f"repeat provenance unavailable for {dataset} row {row.get('id')}")


def audit_rows(dataset: str, paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    audit: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for source_index, path in enumerate(paths):
        rows = load_jsonl(path)
        sources.append(
            {
                "source_index": source_index,
                "private_artifact_basename": path.name,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "rows": len(rows),
            }
        )
        for row in rows:
            responses = row.get("model_responses", [])
            predictions = row.get("extracted_preds", [])
            metrics = [int(value) for value in row.get("metrics", [])]
            if not (len(responses) == len(predictions) == len(metrics)):
                raise RuntimeError(f"misaligned arrays for {dataset} id={row.get('id')}")
            repeat_ids, provenance = response_repeat_ids(dataset, source_index, row)
            if len(repeat_ids) != len(metrics):
                raise RuntimeError(f"repeat provenance mismatch for {dataset} id={row.get('id')}")
            for slot, (repeat_id, response, prediction, metric) in enumerate(
                zip(repeat_ids, responses, predictions, metrics)
            ):
                metadata = metadata_for(row, slot)
                audit.append(
                    {
                        "dataset": dataset,
                        "question_id": int(row["id"]),
                        "repeat_id": repeat_id,
                        "repeat_slot": slot,
                        "repeat_provenance": provenance,
                        "metric": metric,
                        "response_empty": not bool(response),
                        "finish_reason": metadata.get("finish_reason"),
                        "prompt_tokens": metadata.get("prompt_tokens"),
                        "completion_tokens": metadata.get("completion_tokens"),
                        "response_id_sha256": (
                            sha256_text(metadata.get("response_id"))
                            if metadata.get("response_id")
                            else None
                        ),
                        "prompt_sha256": sha256_text(row.get("input_msgs")),
                        "ground_truth_sha256": sha256_text(row.get("ground_truth")),
                        "prediction_sha256": sha256_text(prediction),
                        "response_sha256": sha256_text(response),
                        "source_index": source_index,
                    }
                )
    return audit, sources


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-input", type=Path, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    args = parser.parse_args()

    audit_dir = args.repo_dir / "data" / "raw-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    dataset_summaries: list[dict[str, Any]] = []
    all_source_artifacts: list[dict[str, Any]] = []
    total_validated_responses = 0
    total_correct = 0
    total_observed_questions = 0

    for dataset, spec in DATASET_SPECS.items():
        paths = result_path(args.private_input, dataset)
        audit, sources = audit_rows(dataset, paths)
        metrics = [row["metric"] for row in audit]
        question_ids = sorted({row["question_id"] for row in audit})
        if any(metric not in (0, 1) for metric in metrics):
            raise RuntimeError(f"non-binary metric in {dataset}")
        pair_keys = [
            (row["question_id"], row["repeat_id"], row["repeat_slot"], row["source_index"])
            for row in audit
        ]
        if len(pair_keys) != len(set(pair_keys)):
            raise RuntimeError(f"duplicate public audit pair in {dataset}")

        audit_path = audit_dir / f"{dataset}.jsonl"
        with audit_path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in sorted(
                audit,
                key=lambda value: (
                    value["question_id"],
                    value["repeat_id"] if value["repeat_id"] is not None else 10_000,
                    value["repeat_slot"],
                    value["source_index"],
                ),
            ):
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

        responses = len(metrics)
        correct = sum(metrics)
        questions = len(question_ids)
        expected_responses = spec["total_questions"] * spec["final_repeats"]
        summary = {
            "dataset": dataset,
            **spec,
            "validated_unique_questions": questions,
            "validated_responses": responses,
            "correct": correct,
            "mi300x_accuracy": correct / responses,
            "directional_delta_percentage_points": 100
            * (correct / responses - spec["h200_reference_accuracy"]),
            "question_coverage": questions / spec["total_questions"],
            "response_coverage": responses / expected_responses,
            "expected_final_responses": expected_responses,
            "comparison_scope": (
                "directional subset comparison; H200 reference was provided and was not independently reproduced"
            ),
            "audit_file": str(audit_path.relative_to(args.repo_dir)).replace("\\", "/"),
            "audit_sha256": sha256_file(audit_path),
            "source_artifacts": sources,
        }
        dataset_summaries.append(summary)
        for source in sources:
            all_source_artifacts.append({"dataset": dataset, **source})
        total_validated_responses += responses
        total_correct += correct
        total_observed_questions += questions

    final_questions = sum(spec["total_questions"] for spec in DATASET_SPECS.values())
    final_responses = sum(
        spec["total_questions"] * spec["final_repeats"] for spec in DATASET_SPECS.values()
    )
    if (final_questions, final_responses) != (60_533, 134_239):
        raise RuntimeError("final contract totals changed unexpectedly")
    if (total_observed_questions, total_validated_responses, total_correct) != (
        3_216,
        8_080,
        7_612,
    ):
        raise RuntimeError(
            "validated snapshot totals changed unexpectedly: "
            f"{total_observed_questions}/{total_validated_responses}/{total_correct}"
        )

    snapshot = {
        "schema_version": "1.0",
        "snapshot_id": "mi300x-accuracy-20260724-validated-8080",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "Xiaomi MiMo-V2.5-Pro",
        "hardware": "2 independent nodes, each with 8 AMD Instinct MI300X GPUs",
        "runtime_topology": "independent Unified TP8 / DP1 / EP1 / PP1 per node",
        "runtime": {
            "image_generation": "AMD 20260713-final",
            "image_id": "sha256:ffebe707eed74aa20994b7d0d81a967c65fe18c97e4c4626ccd8eb1dc1f02def",
            "sglang_commit": "2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0",
            "aiter_commit": "00e94abf15e1e09ab7cf481e989bca5d19a99b82",
            "attention_backend": "AITER",
            "quantization": "FP8",
            "speculative_decoding": "EAGLE, natural acceptance",
        },
        "reference": {
            "hardware": "NVIDIA H200",
            "authority": "reference accuracies provided in the evaluation guide",
            "independently_reproduced": False,
        },
        "totals": {
            "final_unique_questions": final_questions,
            "final_responses": final_responses,
            "observed_unique_questions": total_observed_questions,
            "validated_responses": total_validated_responses,
            "correct_responses": total_correct,
            "question_coverage": total_observed_questions / final_questions,
            "response_coverage": total_validated_responses / final_responses,
            "aggregate_accuracy_reported": False,
            "aggregate_accuracy_reason": "datasets have different sizes, repeat counts, and task semantics",
        },
        "datasets": dataset_summaries,
    }
    write_json(args.repo_dir / "data" / "results-summary.json", snapshot)
    write_json(args.repo_dir / "data" / "evidence" / "private-source-manifest.json", all_source_artifacts)

    tsv = [
        "dataset\ttotal_questions\tvalidated_questions\tfinal_repeats\tvalidated_responses\tcorrect\tmi300x_accuracy\th200_reference_accuracy\tquestion_coverage\tresponse_coverage\tphase"
    ]
    for item in dataset_summaries:
        tsv.append(
            "\t".join(
                [
                    item["display_name"],
                    str(item["total_questions"]),
                    str(item["validated_unique_questions"]),
                    str(item["final_repeats"]),
                    str(item["validated_responses"]),
                    str(item["correct"]),
                    f'{item["mi300x_accuracy"]:.12f}',
                    f'{item["h200_reference_accuracy"]:.12f}',
                    f'{item["question_coverage"]:.12f}',
                    f'{item["response_coverage"]:.12f}',
                    item["phase"],
                ]
            )
        )
    with (args.repo_dir / "data" / "results-summary.tsv").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write("\n".join(tsv) + "\n")
    print(
        "PUBLIC_SNAPSHOT=PASS "
        f"datasets={len(dataset_summaries)} questions={total_observed_questions} "
        f"responses={total_validated_responses} correct={total_correct}"
    )


if __name__ == "__main__":
    main()
