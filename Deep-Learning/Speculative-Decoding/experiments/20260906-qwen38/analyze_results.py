"""Reconcile returned Qwen3.8 evidence and export secret-free result tables."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile


DATASETS = ("humaneval_plus", "math_500")
ROUTES = ("baseline", "mtp7", "dflash2_7")
GROUP_FIELDS = (
    "group_id", "stage", "route", "concurrency", "base_seed", "repetition",
    "thinking", "dataset", "planned", "ordered_task_ids", "status", "completed",
    "throughput_status", "elapsed_wall_s", "clock_start_ns", "clock_end_ns",
    "completion_tokens", "prompt_tokens", "output_tokens_per_second",
    "input_tokens_per_second", "requests_per_second", "client", "datasets",
)
ENGINE_FIELDS = (
    "status", "generation_tokens", "prompt_tokens", "finished_requests",
    "generation_tokens_per_second", "prompt_tokens_per_second", "speculation",
)


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_groups(archive, verification):
    require(verification.get("archive_verified") is True, "ARCHIVE_NOT_VERIFIED")
    require(archive.stat().st_size == verification["bytes"], "ARCHIVE_SIZE_CHANGED")
    require(digest_file(archive) == verification["sha256"], "ARCHIVE_HASH_CHANGED")
    groups = []
    with tarfile.open(archive, "r|gz") as bundle:
        for member in bundle:
            if not member.name.endswith("/group-summary.json"):
                continue
            source = bundle.extractfile(member)
            require(source is not None, "GROUP_UNREADABLE")
            with source:
                raw = source.read()
            original = json.loads(raw)
            group = {key: original[key] for key in GROUP_FIELDS if key in original}
            if original.get("scores") is not None:
                group["scores"] = {key: original["scores"][key] for key in ("by_task", "datasets")}
            if original.get("engine") is not None:
                group["engine"] = {key: original["engine"][key] for key in ENGINE_FIELDS if key in original["engine"]}
            group["source"] = {"member": member.name, "sha256": hashlib.sha256(raw).hexdigest()}
            groups.append(group)
    return sorted(groups, key=lambda group: group["group_id"])


def verify_groups(groups, completed):
    require(len({group["group_id"] for group in groups}) == len(groups), "DUPLICATE_GROUP")
    require(sum(group["completed"] for group in groups) == completed, "COMPLETED_COUNT_MISMATCH")
    for group in groups:
        require(group["status"] == "COMPLETE", "GROUP_NOT_COMPLETE")
        require(group["planned"] == group["completed"] == len(group["ordered_task_ids"]), "GROUP_DENOMINATOR_MISMATCH")
        require(len(set(group["ordered_task_ids"])) == group["completed"], "DUPLICATE_TASK")
        require(group["throughput_status"] == "VALID", "RESUMED_OR_INVALID_THROUGHPUT")
        wall = group["elapsed_wall_s"]
        require(wall > 0 and math.isfinite(wall), "INVALID_WALL_TIME")
        require(math.isclose(group["completion_tokens"] / wall, group["output_tokens_per_second"], rel_tol=1e-10), "CLIENT_THROUGHPUT_MISMATCH")
        engine = group.get("engine", {})
        require(isinstance(engine, dict) and engine.get("status") == "RECONCILED", "ENGINE_NOT_RECONCILED")
        require(engine.get("generation_tokens") == group["completion_tokens"], "ENGINE_TOKEN_MISMATCH")
        require(engine.get("prompt_tokens") == group["prompt_tokens"], "ENGINE_PROMPT_TOKEN_MISMATCH")
        require(engine.get("finished_requests") == group["completed"], "ENGINE_REQUEST_COUNT_MISMATCH")
        require(isinstance(engine.get("generation_tokens_per_second"), (int, float)), "ENGINE_THROUGHPUT_MISSING")
        require(math.isclose(engine["generation_tokens"] / wall, engine["generation_tokens_per_second"], rel_tol=1e-10), "ENGINE_THROUGHPUT_MISMATCH")
        scores = group.get("scores")
        if group["stage"] == "G":
            require(scores is None, "DIAGNOSTIC_MUST_NOT_BECOME_QUALITY_SCORE")
            continue
        require(scores is not None, "OFFICIAL_SCORES_MISSING")
        require(set(scores["by_task"]) == set(group["ordered_task_ids"]), "SCORE_TASK_SET_MISMATCH")
        for dataset in DATASETS:
            prefix = "HumanEval/" if dataset == "humaneval_plus" else "MATH-500/"
            grades = [grade for task_id, grade in scores["by_task"].items() if task_id.startswith(prefix)]
            counts = scores["datasets"][dataset]
            require(len(grades) == counts["denominator"], "DATASET_DENOMINATOR_MISMATCH")
            require(all(type(grade["correct"]) is bool for grade in grades), "NONBOOLEAN_VERDICT")
            require(sum(grade["correct"] for grade in grades) == counts["raw_correct"], "RAW_SCORE_MISMATCH")
            require(sum(grade["correct"] and grade["finish_reason"] == "stop" for grade in grades) == counts["normal_correct"], "NORMAL_SCORE_MISMATCH")
            require(dict(Counter(grade["finish_reason"] for grade in grades)) == counts["finish_counts"], "FINISH_REASON_MISMATCH")
            for field in ("denominator", "raw_correct", "normal_correct", "finish_counts"):
                require(group["datasets"][dataset][field] == counts[field], "GROUP_SCORE_SUMMARY_MISMATCH")


def spread(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values), "values": values}


def summarize(groups, coverage):
    verify_groups(groups, coverage["completed_responses"])
    matched = [group for group in groups if group["stage"] == "S"]
    seeds = coverage["matched_seeds"]
    cells = defaultdict(list)
    lookup = {}
    for group in matched:
        require(set(group["ordered_task_ids"]) == set(matched[0]["ordered_task_ids"]), "MATCHED_TASK_SET_CHANGED")
        key = (group["route"], group["concurrency"])
        cells[key].append(group)
        lookup[(group["route"], group["concurrency"], group["base_seed"])] = group
    require(len(cells) == len(ROUTES) * len(coverage["matched_concurrency"]), "MATCHED_CELLS_MISSING")
    rows = []
    comparisons = []
    for concurrency in coverage["matched_concurrency"]:
        for route in ROUTES:
            selected = sorted(cells[(route, concurrency)], key=lambda group: group["base_seed"])
            require([group["base_seed"] for group in selected] == seeds, "MATCHED_SEEDS_MISSING")
            require(all(group["planned"] == 64 for group in selected), "MATCHED_SUBSET_NOT_64")
            row = {"route": route, "concurrency": concurrency, "seeds": seeds,
                   "throughput_tok_s": spread([group["output_tokens_per_second"] for group in selected]),
                   "group_wall_s": spread([group["elapsed_wall_s"] for group in selected]),
                   "datasets": {}, "source_groups": [group["group_id"] for group in selected]}
            for dataset in DATASETS:
                counts = [group["scores"]["datasets"][dataset] for group in selected]
                require(all(count["denominator"] == 32 for count in counts), "MATCHED_DATASET_NOT_32")
                row["datasets"][dataset] = {
                    "denominator_per_repeat": 32,
                    "raw_correct": [count["raw_correct"] for count in counts],
                    "normal_correct": [count["normal_correct"] for count in counts],
                    "length_stopped": [count["finish_counts"].get("length", 0) for count in counts],
                    "mean_accuracy": sum(count["raw_correct"] for count in counts) / (32 * len(counts)),
                }
            speculation = [group.get("engine", {}).get("speculation", {}).get("acceptance_rate") for group in selected]
            row["acceptance_rate"] = spread(speculation) if all(value is not None for value in speculation) else None
            rows.append(row)
        for reference in ("baseline", "mtp7"):
            paired = []
            for seed in seeds:
                candidate = lookup[("dflash2_7", concurrency, seed)]
                baseline = lookup[(reference, concurrency, seed)]
                require(candidate["ordered_task_ids"] == baseline["ordered_task_ids"], "PAIRED_INPUT_ORDER_MISMATCH")
                comparison = {"seed": seed, "throughput_ratio": candidate["output_tokens_per_second"] / baseline["output_tokens_per_second"], "datasets": {}}
                for dataset in DATASETS:
                    difference = candidate["scores"]["datasets"][dataset]["raw_correct"] - baseline["scores"]["datasets"][dataset]["raw_correct"]
                    comparison["datasets"][dataset] = {"correct_difference": difference, "accuracy_difference_pp": difference / 32 * 100}
                paired.append(comparison)
            comparisons.append({"candidate": "dflash2_7", "reference": reference, "concurrency": concurrency,
                                "paired": paired, "throughput_ratio": spread([pair["throughput_ratio"] for pair in paired])})
    return {"coverage": coverage, "stage_group_counts": dict(Counter(group["stage"] for group in groups)),
            "stage_response_counts": {stage: sum(group["completed"] for group in groups if group["stage"] == stage) for stage in ("C", "G", "S", "F")},
            "matched_summary": rows, "paired_comparisons": comparisons,
            "method": "Offline reconciliation of archived official-grader verdicts and saved token counters; no new generation or grading; repeats are not independent new tasks."}


def dump_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def draw_throughput(summary, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    figure, axes = pyplot.subplots(1, 3, figsize=(15, 7.6), dpi=100)
    colors = ("#637078", "#C68118", "#16836F")
    labels = ("Baseline", "MTP7", "DFlash 2-7")
    for axis, concurrency in zip(axes, summary["coverage"]["matched_concurrency"]):
        rows = [row for row in summary["matched_summary"] if row["concurrency"] == concurrency]
        medians = [row["throughput_tok_s"]["median"] for row in rows]
        errors = [[median - row["throughput_tok_s"]["min"] for median, row in zip(medians, rows)],
                  [row["throughput_tok_s"]["max"] - median for median, row in zip(medians, rows)]]
        bars = axis.bar(labels, medians, color=colors, width=0.62, yerr=errors, capsize=6)
        axis.set_title(f"Concurrency {concurrency}", fontsize=16, pad=18)
        axis.set_ylim(0, max(row["throughput_tok_s"]["max"] for row in rows) * 1.23)
        axis.set_ylabel("Group output tokens / second", fontsize=11)
        axis.tick_params(axis="both", labelsize=11)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#DCE3E1", linewidth=0.8)
        axis.bar_label(bars, fmt="%.2f", padding=10, fontsize=12)
    figure.suptitle("Qwen3.8-27B: matched serving throughput", fontsize=23, y=0.95)
    figure.text(0.5, 0.88, "Same 64 tasks | 3 seeds per route | H100 NVL | vLLM 0.28.0 | Thinking included",
                ha="center", fontsize=13, color="#4B555A")
    figure.text(0.5, 0.075, "Bars: three-seed median. Error bars: observed minimum and maximum, not confidence intervals.",
                ha="center", fontsize=11, color="#4B555A")
    figure.text(0.5, 0.035, "Author measurement: qwen38-quality-20260906 | Source: data/groups.json | S stage only; F was not run.",
                ha="center", fontsize=11, color="#4B555A")
    figure.subplots_adjust(left=0.065, right=0.975, bottom=0.18, top=0.77, wspace=0.34)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, facecolor="white")
    pyplot.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--archive", type=Path)
    inputs.add_argument("--groups", type=Path)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path, help="Optional PNG, requires matplotlib")
    args = parser.parse_args()
    if args.archive:
        require(args.verification is not None, "VERIFICATION_RECEIPT_REQUIRED")
        verification = json.loads(args.verification.read_text(encoding="utf-8"))
        groups = read_groups(args.archive, verification)
        campaign = verification["campaign"]
        contract = json.loads((args.verification.parent.parent / "experiment.json").read_text(encoding="utf-8-sig"))
        coverage = {"run_id": verification["run_id"], "archive_sha256": verification["sha256"],
                    "planned_responses": campaign["total"], "completed_responses": campaign["completed"],
                    "planned_groups": campaign["groups_total"], "completed_groups": campaign["groups_completed"],
                    "campaign_phase": campaign["phase"], "reason": campaign["error"],
                    "remaining_groups": campaign["remaining_groups"],
                    "matched_seeds": contract["serving_checks"]["matched_base_seeds"],
                    "matched_concurrency": contract["serving_checks"]["matched_concurrency"],
                    "target": contract["target"], "draft": contract["draft"], "sampling": contract["sampling"],
                    "vllm_version": contract["serving"]["vllm_version"],
                    "vllm_commit": contract["serving"]["vllm_commit"],
                    "projection": "Only result, grade and timing fields; infrastructure locators and credentials are excluded."}
    else:
        saved = json.loads(args.groups.read_text(encoding="utf-8"))
        groups, coverage = saved["groups"], saved["coverage"]
    result = summarize(groups, coverage)
    require(len(groups) == coverage["completed_groups"], "GROUP_COVERAGE_MISMATCH")
    require(len(groups) + len(coverage["remaining_groups"]) == coverage["planned_groups"], "PLANNED_GROUPS_MISMATCH")
    args.output.mkdir(parents=True, exist_ok=True)
    dump_json(args.output / "groups.json", {"coverage": coverage, "groups": groups})
    dump_json(args.output / "summary.json", result)
    if args.figure:
        draw_throughput(result, args.figure)
    print(json.dumps({"status": "OFFLINE_RECONCILIATION_PASS", "groups": len(groups),
                      "responses": coverage["completed_responses"], "planned_responses": coverage["planned_responses"],
                      "summary_sha256": digest_file(args.output / "summary.json"),
                      "matched_summary": result["matched_summary"], "paired_comparisons": result["paired_comparisons"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()