import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
from datetime import datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, percentage):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_statistics(values):
    if not values:
        return None
    return {
        "samples": len(values),
        "mean_seconds": statistics.mean(values),
        "p50_seconds": statistics.median(values),
        "p95_seconds": percentile(values, 95),
        "sample_stddev_seconds": statistics.stdev(values) if len(values) > 1 else None,
        "minimum_seconds": min(values),
        "maximum_seconds": max(values),
    }


def summarize(run_directory, prompts_path, historical_path=None):
    result_path = run_directory / "5way_v2_results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["state"] not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
        raise ValueError("The run has not reached a terminal state; no final summary was generated.")
    if result["config"]["groups"] != ["mai-image-2.6"]:
        raise ValueError("This summary is scoped to MAI-Image-2.6 only.")
    with prompts_path.open(encoding="utf-8-sig", newline="") as prompt_file:
        reader = csv.reader(prompt_file)
        next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]
    if digest(prompts_path) != result["config"]["prompts_sha256"]:
        raise ValueError("The prompt source hash differs from the measured run.")
    rows = result["raw_data"]
    groups = result["config"]["groups"]
    rounds = result["config"]["rounds"]
    expected = {(round_number, prompt_index, group) for round_number in range(1, rounds + 1)
                for prompt_index in range(1, len(prompts) + 1) for group in groups}
    actual = [(row["round"], row["prompt_idx"], row["group"]) for row in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Recorded samples do not match the complete, unique planned matrix.")
    attempts = [json.loads(line) for line in (run_directory / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if line]
    formal_attempts = [attempt for attempt in attempts if attempt["phase"] == "formal"]
    successful = [row for row in rows if row["ok"]]
    image_inventory = []
    for row in rows:
        prompt = prompts[row["prompt_idx"] - 1]
        if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != row["prompt_sha256"]:
            raise ValueError("A measured prompt differs from the original CSV.")
        matching_attempts = [attempt for attempt in formal_attempts if
                             (attempt["round"], attempt["prompt_idx"], attempt["group"]) ==
                             (row["round"], row["prompt_idx"], row["group"])]
        if len(matching_attempts) != row["attempt_count"]:
            raise ValueError("Per-sample attempt counts do not reconcile.")
        if row["ok"]:
            image_path = run_directory / row["image"]
            content = image_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != row["image_sha256"]:
                raise ValueError("An image hash differs from its measurement record.")
            if content[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", content[16:24]) != (1024, 1024):
                raise ValueError("An image does not have the expected PNG header and dimensions.")
            image_inventory.append({"path": row["image"], "bytes": len(content), "sha256": row["image_sha256"]})
    formal_start = min(datetime.fromisoformat(row["started_at_utc"]) for row in rows)
    formal_end = max(datetime.fromisoformat(row["ended_at_utc"]) for row in rows)
    formal_wall_seconds = (formal_end - formal_start).total_seconds()
    per_prompt = []
    for prompt_index, prompt in enumerate(prompts, 1):
        prompt_rows = [row for row in rows if row["prompt_idx"] == prompt_index]
        per_prompt.append({"prompt_index": prompt_index, "prompt": prompt,
                           "successful_samples": sum(row["ok"] for row in prompt_rows),
                           "planned_samples": len(groups) * rounds,
                           "rounds": [{"round": row["round"], "group": row["group"],
                                       "ok": row["ok"], "request_seconds": row["time"],
                                       "logical_request_seconds": row["logical_request_seconds"],
                                       "attempts": row["attempt_count"], "image": row["image"]}
                                      for row in prompt_rows],
                           "latency": latency_statistics([row["time"] for row in prompt_rows if row["ok"]])})
    summary = {
        "run_id": run_directory.name,
        "result_sha256": digest(result_path),
        "attempts_sha256": digest(run_directory / "attempts.jsonl"),
        "prompts_sha256": digest(prompts_path),
        "model": groups,
        "model_version": result["config"]["model_version"],
        "test_started_at_utc": result["started_at_utc"],
        "test_ended_at_utc": result["ended_at_utc"],
        "total_run_seconds_including_warmup_and_waits": (datetime.fromisoformat(result["ended_at_utc"]) - datetime.fromisoformat(result["started_at_utc"])).total_seconds(),
        "formal_sample_count": len(expected),
        "successful_samples": len(successful),
        "failed_samples": len(rows) - len(successful),
        "first_attempt_successful_samples": sum(row["first_attempt_ok"] is True for row in rows),
        "formal_http_attempts": len(formal_attempts),
        "warmup_http_attempts": len(attempts) - len(formal_attempts),
        "http_429_attempts": sum(attempt.get("http_status") == 429 for attempt in formal_attempts),
        "successful_request_latency": latency_statistics([row["time"] for row in successful]),
        "logical_request_latency_all_samples": latency_statistics([row["logical_request_seconds"] for row in rows]),
        "formal_window_seconds_including_inter_call_waits": formal_wall_seconds,
        "observed_serial_images_per_minute_including_waits": len(successful) * 60 / formal_wall_seconds,
        "per_round": [{"round": round_number, "latency": latency_statistics([row["time"] for row in successful if row["round"] == round_number])}
                      for round_number in range(1, rounds + 1)],
        "per_prompt": per_prompt,
        "images": image_inventory,
        "percentile_method": "Linear interpolation at (n-1)*p; small-sample descriptive P95, not a production guarantee.",
        "quality_method": "Unblinded visual inspection and full image disclosure; no automated quality score or human-preference win rate is inferred.",
        "capacity_boundary": "Serial observed completion rate, not maximum service throughput.",
    }
    if historical_path:
        historical = json.loads(historical_path.read_text(encoding="utf-8"))
        summary["historical_reference"] = {
            "sha256": digest(historical_path), "timestamp": historical["timestamp"],
            "comparison_scope": "Different dates and client locations. Historical context, not a contemporaneous controlled comparison.",
            "groups": [{"group": group, "successful_samples": sum(row["group"] == group and row["ok"] for row in historical["raw_data"]),
                        "latency": latency_statistics([row["time"] for row in historical["raw_data"] if row["group"] == group and row["ok"]])}
                       for group in historical["config"]["groups"]],
        }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and summarize an existing MAI benchmark; never calls a model.")
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).resolve().parents[1] / "prompts.csv")
    parser.add_argument("--historical-results", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    output = arguments.output or arguments.run_directory / "summary.json"
    summary = summarize(arguments.run_directory, arguments.prompts, arguments.historical_results)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "PASS", "samples": summary["formal_sample_count"],
                      "successes": summary["successful_samples"], "output": str(output),
                      "latency": summary["successful_request_latency"]}))