"""Reconcile saved responses with official graders, without regrading answers."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from statistics import median


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def identity(record):
    return record["task_id"], record["repetition"]


def load_group(root, route, group):
    directory = root / "results" / route / group
    summary = read_json(directory / "group-summary.json")
    records = []
    for path in directory.glob("repeat-*/*.json"):
        if path.name.endswith(".receipt.json"):
            continue
        record = read_json(path)
        if record["status"] != "COMPLETE":
            raise ValueError(f"Incomplete response: {path}")
        record["repetition"] = int(path.parent.name.split("-")[-1])
        record["record_path"] = path.relative_to(root).as_posix()
        record["record_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(record)
    records.sort(key=lambda record: (record["repetition"], record["dataset"], int(record["task_id"].split("/")[1].split("-")[0]), record["task_id"]))
    if len(records) != summary["expected"] or len(records) != summary["requests"]:
        raise ValueError(f"Response denominator mismatch: {route}/{group}")
    if len({identity(record) for record in records}) != len(records):
        raise ValueError(f"Duplicate task/repetition: {route}/{group}")
    if len({record["protocol_hash"] for record in records}) != 1:
        raise ValueError(f"Mixed protocols: {route}/{group}")
    return records, summary


def attach_grades(root, route, group, records):
    directory = root / "results" / route / (group + "-scores")
    code = [record for record in records if record["dataset"] == "humaneval_plus"]
    if code:
        original = read_jsonl(directory / "samples.jsonl")
        sanitized = read_jsonl(directory / "samples-sanitized.jsonl")
        result = read_json(directory / "evalplus-results.json")
        if len(code) != len(original) or len(code) != len(sanitized):
            raise ValueError("Code sample count changed across scoring stages")
        expected_counts = Counter(record["task_id"] for record in code)
        if expected_counts != Counter({task: len(grades) for task, grades in result["eval"].items()}):
            raise ValueError("Code evaluator omitted or duplicated samples")
        occurrence = defaultdict(int)
        for record, source, extracted in zip(code, original, sanitized):
            task = record["task_id"]
            if source["task_id"] != task or extracted["task_id"] != task or source["solution"] != record["content"]:
                raise ValueError(f"Code response/input mismatch: {task}")
            grade = result["eval"][task][occurrence[task]]
            occurrence[task] += 1
            if grade["task_id"] != task or grade["solution"] != extracted["solution"]:
                raise ValueError(f"Code grader/sample mismatch: {task}")
            record["base_correct"] = grade["base_status"] == "pass"
            record["correct"] = record["base_correct"] and grade["plus_status"] == "pass"
            record["grader_status"] = {name: grade[name] for name in ("base_status", "plus_status")}
    maths = [record for record in records if record["dataset"] == "math_500"]
    if maths:
        inputs = read_csv(directory / "math-input.csv")
        outputs = read_csv(directory / "math-scores.csv")
        if len(maths) != len(inputs) or len(maths) != len(outputs):
            raise ValueError("Math row count changed across scoring stages")
        for record, source, grade in zip(maths, inputs, outputs):
            if source["task_id"] != record["task_id"] or source["answer"] != (record["content"] or "NO_FINAL_ANSWER"):
                raise ValueError(f"Math response/input mismatch: {record['task_id']}")
            if grade["original_answer"] != source["answer"] or grade["gold_answer"] != source["gold"]:
                raise ValueError(f"Math grader row/input mismatch: {record['task_id']}")
            value = grade["is_correct"].lower()
            if value not in ("true", "false"):
                raise ValueError(f"Unrecognized math grade: {value}")
            record["correct"] = value == "true"
            record["grader_status"] = {"error": grade.get("error", ""), "extracted_answer": grade.get("extracted_answer", "")}
    return records


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    location = (len(ordered) - 1) * fraction
    lower = int(location)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (location - lower)


def summarize(records):
    result = {}
    for dataset in sorted({record["dataset"] for record in records}):
        selected = [record for record in records if record["dataset"] == dataset]
        correct = sum(record["correct"] for record in selected)
        durations = [record["total_s"] for record in selected]
        speeds = [record["output_tps_e2e"] for record in selected]
        first_tokens = [record["ttft_any_s"] for record in selected if record["ttft_any_s"] is not None]
        result[dataset] = {
            "responses": len(selected),
            "tasks": len({record["task_id"] for record in selected}),
            "correct": correct,
            "accuracy": correct / len(selected),
            "finish_counts": dict(Counter(record["finish_reason"] for record in selected)),
            "empty_content": sum(not record["content"].strip() for record in selected),
            "nonempty_reasoning": sum(bool(record["reasoning"].strip()) for record in selected),
            "median_output_tokens": median(record["usage"]["completion_tokens"] for record in selected),
            "median_total_s": median(durations),
            "p95_total_s": percentile(durations, 0.95),
            "median_output_tps_e2e": median(speeds),
            "tokens_per_summed_request_second": sum(record["usage"]["completion_tokens"] for record in selected) / sum(durations),
            "median_ttft_any_s": median(first_tokens) if first_tokens else None,
            "p95_ttft_any_s": percentile(first_tokens, 0.95),
        }
        if dataset == "humaneval_plus":
            result[dataset]["base_correct"] = sum(record["base_correct"] for record in selected)
        if dataset == "math_500":
            result[dataset]["scorer_errors"] = sum(bool(record["grader_status"]["error"]) for record in selected)
    return result


def paired_comparison(reference, candidate):
    reference_by_id = {identity(record): record for record in reference}
    candidate_by_id = {identity(record): record for record in candidate}
    if reference_by_id.keys() != candidate_by_id.keys():
        raise ValueError("Paired comparison has different task/repetition sets")
    rows = []
    for key, original in reference_by_id.items():
        alternative = candidate_by_id[key]
        if original["request"] != alternative["request"] or original["protocol_hash"] != alternative["protocol_hash"]:
            raise ValueError(f"Paired requests/protocols differ: {key}")
        rows.append({
            "task_id": original["task_id"], "dataset": original["dataset"], "repetition": original["repetition"],
            "reference_correct": original["correct"], "candidate_correct": alternative["correct"],
            "same_content": original["content"] == alternative["content"],
            "reference_finish": original["finish_reason"], "candidate_finish": alternative["finish_reason"],
            "reference_tokens": original["usage"]["completion_tokens"], "candidate_tokens": alternative["usage"]["completion_tokens"],
            "latency_ratio_reference_over_candidate": original["total_s"] / alternative["total_s"],
            "tps_ratio_candidate_over_reference": alternative["output_tps_e2e"] / original["output_tps_e2e"],
            "reference_record": original["record_path"], "candidate_record": alternative["record_path"],
            "reference_sha256": original["record_sha256"], "candidate_sha256": alternative["record_sha256"],
        })
    summary = {}
    for dataset in sorted({row["dataset"] for row in rows}):
        selected = [row for row in rows if row["dataset"] == dataset]
        quadrants = Counter((row["reference_correct"], row["candidate_correct"]) for row in selected)
        summary[dataset] = {
            "pairs": len(selected), "both_correct": quadrants[True, True],
            "reference_only_correct": quadrants[True, False], "candidate_only_correct": quadrants[False, True],
            "both_wrong": quadrants[False, False], "same_content": sum(row["same_content"] for row in selected),
            "accuracy_delta_percentage_points": 100 * (quadrants[False, True] - quadrants[True, False]) / len(selected),
            "median_paired_latency_ratio": median(row["latency_ratio_reference_over_candidate"] for row in selected),
            "median_paired_tps_ratio": median(row["tps_ratio_candidate_over_reference"] for row in selected),
        }
    return summary, rows


def metric_counters(path):
    counters = Counter()
    pattern = re.compile(r"^(vllm:spec_decode_num_(?:drafts|draft_tokens|accepted_tokens)_total)(?:\{[^\n]*\})?\s+([0-9.eE+-]+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.fullmatch(line)
        if match:
            counters[match.group(1)] += float(match.group(2))
    return counters


def acceptance_metrics(root, route):
    directory = root / "results" / route
    before = metric_counters(directory / "metrics-full-before.txt")
    after = metric_counters(directory / "metrics-full-after.txt")
    delta = {name: value - before[name] for name, value in after.items()}
    if any(value < 0 for value in delta.values()):
        raise ValueError("Speculative counter decreased within the route process")
    drafted = delta.get("vllm:spec_decode_num_draft_tokens_total", 0)
    accepted = delta.get("vllm:spec_decode_num_accepted_tokens_total", 0)
    iterations = delta.get("vllm:spec_decode_num_drafts_total", 0)
    if not drafted or not iterations:
        raise ValueError(f"No observed speculative-decoding counters for {route}")
    return {"scope": "All requests in this route process, including supplemental groups", "draft_tokens": drafted, "accepted_tokens": accepted, "draft_iterations": iterations, "acceptance_fraction": accepted / drafted, "mean_acceptance_length": 1 + accepted / iterations}


def repeated_consistency(records):
    by_task = defaultdict(list)
    for record in records:
        by_task[record["task_id"]].append(record)
    changed_text = [task for task, runs in by_task.items() if len({record["content"] for record in runs}) > 1]
    changed_correctness = [task for task, runs in by_task.items() if len({record["correct"] for record in runs}) > 1]
    return {"tasks": len(by_task), "repetitions_per_task": sorted({len(runs) for runs in by_task.values()}), "changed_content_tasks": changed_text, "changed_correctness_tasks": changed_correctness}


def prefix_tasks(tasks, count):
    return [task for dataset in ("humaneval_plus", "math_500") for task in [item for item in tasks if item["dataset"] == dataset][:count]]


def validate_group_requests(records, selected, repeats, protocol, protocol_hash, group):
    expected = {(task["task_id"], repetition) for task in selected for repetition in range(repeats)}
    if {identity(record) for record in records} != expected:
        raise ValueError(f"Frozen task/repetition set changed: {group}")
    tasks = {task["task_id"]: task for task in selected}
    primary = protocol["primary_quality"]
    sampling = protocol["supplemental_matrix"]["sampling"]
    for record in records:
        task = tasks[record["task_id"]]
        request = record["request"]
        expected_seed = sampling["seeds"][record["repetition"]] if group == "sampling" else primary["seed"]
        expected_temperature = sampling["temperature"] if group == "sampling" else primary["temperature"]
        expected_top_p = sampling["top_p"] if group == "sampling" else primary["top_p"]
        valid = record["protocol_hash"] == protocol_hash and request["model"] == protocol["target"]["model_id"]
        valid = valid and request["messages"] == task["messages"] and request["max_tokens"] == task["max_tokens"]
        valid = valid and request["seed"] == expected_seed and request["temperature"] == expected_temperature and request["top_p"] == expected_top_p
        valid = valid and request["top_k"] == primary["top_k"] and request["chat_template_kwargs"]["enable_thinking"] is False
        valid = valid and request["stream"] == (group == "streaming")
        if not valid:
            raise ValueError(f"Observed request differs from frozen protocol: {group}/{identity(record)}")


def load_protocol(root):
    protocol_path = root / "src/experiment.json"
    protocol = read_json(protocol_path)
    protocol_hash = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    projection_path = root / "metadata/protocol-public-projection.json"
    if projection_path.is_file():
        projection = read_json(projection_path)
        if projection["public_sha256"] != protocol_hash or projection["removed_json_pointers"] != ["/resource"]:
            raise ValueError("Public protocol projection does not match its provenance")
        if "resource" in protocol or not re.fullmatch(r"[0-9a-f]{64}", projection["source_sha256"]):
            raise ValueError("Invalid public protocol projection")
        protocol_hash = projection["source_sha256"]
    return protocol, protocol_hash


def analyze_matrix(root, output_directory):
    protocol, protocol_hash = load_protocol(root)
    inputs = read_json(root / "metadata/inputs.json")
    manifest = root / "data/tasks.jsonl"
    if inputs["manifest_sha256"] != hashlib.sha256(manifest.read_bytes()).hexdigest():
        raise ValueError("Frozen task manifest changed")
    campaign = read_json(root / "state/campaign.json")
    if campaign["phase"] != "COMPLETE" or campaign["exit_code"] != 0:
        raise ValueError("Full campaign has not completed successfully")
    tasks = read_jsonl(manifest)
    if Counter(task["dataset"] for task in tasks) != {"humaneval_plus": 164, "math_500": 500}:
        raise ValueError("Frozen primary dataset counts differ")
    long_tasks = read_json(root / "data/long-context-tasks.json")
    repeated = prefix_tasks(tasks, 8)
    matched = prefix_tasks(tasks, 32)
    groups = [("primary", tasks, 1), ("repeatability", repeated, 3), ("streaming", repeated, 3)]
    groups += [(f"concurrency-{level}", matched, 1) for level in (1, 4, 8)]
    groups += [("sampling", repeated, 3), ("long-context", long_tasks, 1)]
    result = {"scope": "complete_frozen_matrix", "protocol_sha256": protocol_hash, "task_manifest_sha256": inputs["manifest_sha256"], "coverage": [], "routes": {}, "comparisons": {}, "claim_boundary": "Finite task regression on one deployment. No universal equivalence, distribution-equivalence or noninferiority claim."}
    all_records = {}
    for route in ("baseline", "mtp5", "dflash15", "dflash5"):
        result["routes"][route] = {}
        for group, selected, repeats in ([("matched-window", matched, 1)] if route == "dflash5" else groups):
            records, execution = load_group(root, route, group)
            validate_group_requests(records, selected, repeats, protocol, protocol_hash, group)
            if group == "long-context":
                expected = {task["task_id"]: task for task in selected}
                saved = {row["task_id"]: row for row in read_json(root / "results" / route / group / "correctness.json")}
                for record in records:
                    task = expected[record["task_id"]]
                    record["correct"] = record["content"].strip() == task["expected"]
                    if saved[record["task_id"]]["correct"] != record["correct"]:
                        raise ValueError("Synthetic retrieval grade differs from raw response")
            else:
                attach_grades(root, route, group, records)
            all_records[route, group] = records
            result["coverage"].append({"route": route, "group": group, "expected": len(selected) * repeats, "observed": len(records)})
            entry = {"quality_and_latency": summarize(records), "execution": execution}
            if group == "repeatability":
                entry["same_seed_consistency"] = repeated_consistency(records)
            if group == "long-context":
                entry["cases"] = [{"task_id": record["task_id"], "nominal_input_tokens": expected[record["task_id"]]["nominal_input_tokens"], "tokenizer_input_tokens": expected[record["task_id"]]["actual_input_tokens"], "server_prompt_tokens": record["usage"]["prompt_tokens"], "correct": record["correct"]} for record in records]
            result["routes"][route][group] = entry
        if route != "baseline":
            result["routes"][route]["acceptance"] = acceptance_metrics(root, route)

    def save_pair(name, reference, candidate):
        comparison, rows = paired_comparison(reference, candidate)
        result["comparisons"][name] = comparison
        with (output_directory / (name + ".csv")).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    output_directory.mkdir(parents=True, exist_ok=True)
    matched_ids = {task["task_id"] for task in matched}
    for route in ("mtp5", "dflash15"):
        save_pair("baseline-vs-" + route, all_records["baseline", "primary"], all_records[route, "primary"])
        save_pair("sampling-baseline-vs-" + route, all_records["baseline", "sampling"], all_records[route, "sampling"])
    save_pair("mtp5-vs-dflash15", all_records["mtp5", "primary"], all_records["dflash15", "primary"])
    for route in ("baseline", "mtp5", "dflash15"):
        selected = [record for record in all_records[route, "primary"] if record["task_id"] in matched_ids]
        save_pair(route + "-vs-dflash5-matched", selected, all_records["dflash5", "matched-window"])
        for level in (4, 8):
            save_pair(f"{route}-concurrency-1-vs-{level}", all_records[route, "concurrency-1"], all_records[route, f"concurrency-{level}"])
    result["observed_matrix_responses"] = sum(row["observed"] for row in result["coverage"])
    if result["observed_matrix_responses"] != 3100:
        raise ValueError("Total frozen matrix coverage is incomplete")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", default="primary")
    parser.add_argument("--routes", nargs="+", default=["baseline", "mtp5", "dflash15"])
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    if args.matrix:
        result = analyze_matrix(args.root, args.output.parent)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"scope": result["scope"], "responses": result["observed_matrix_responses"], "output": str(args.output)}, ensure_ascii=False))
        return
    result = {"scope": args.group, "routes": {}, "comparisons": {}, "claim_boundary": "Observed finite task results, not a proof of universal equivalence or a noninferiority test."}
    all_records = {}
    for route in args.routes:
        records, execution = load_group(args.root, route, args.group)
        all_records[route] = attach_grades(args.root, route, args.group, records)
        if args.group == "primary" and Counter(record["dataset"] for record in records) != {"humaneval_plus": 164, "math_500": 500}:
            raise ValueError(f"Primary scope incomplete: {route}")
        result["routes"][route] = {"quality_and_latency": summarize(records), "execution": execution}
    for route in args.routes:
        if route != "baseline" and "baseline" in all_records:
            comparison, rows = paired_comparison(all_records["baseline"], all_records[route])
            result["comparisons"][route] = comparison
            path = args.output.parent / (route + "-paired.csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"scope": args.group, "routes": args.routes, "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()