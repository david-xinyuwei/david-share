import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
from datetime import datetime
from pathlib import Path

from summarize_mai_run import digest, latency_statistics


GROUPS = ("mai-image-2.6", "gpt-image-2-low", "gpt-image-2-medium", "gpt-image-2-high")


def token_count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def validate_source_snapshot(directory, result):
    published_hash = digest(directory / "source" / "benchmark_5way_v2.py")
    if published_hash == result["script_sha256"]:
        return
    provenance_path = directory / "provenance.json"
    if not provenance_path.exists():
        raise ValueError("Executed-source snapshot hash does not match")
    projection = json.loads(provenance_path.read_text("utf-8")).get("publication_redaction", {})
    if (projection.get("kind") != "financial-metadata-removal"
            or projection.get("original_script_sha256") != result["script_sha256"]
            or projection.get("published_script_sha256") != published_hash
            or projection.get("published_result_sha256") != digest(directory / "5way_v2_results.json")):
        raise ValueError("Public source projection does not match its recorded provenance")


def validate_image(directory, relative_path, expected_hash):
    path = (directory / relative_path).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("Image path escapes the run directory")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise ValueError("Image bytes differ from the recorded hash")
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", content[16:24]) != (1024, 1024):
        raise ValueError("Image is not a 1024x1024 PNG")
    return {"path": relative_path, "bytes": len(content), "sha256": expected_hash}


def validate_attempts(directory, matching, group, prompt, expected_count, expected_success):
    if not matching or len(matching) != expected_count or len(matching) > 3:
        raise ValueError("Attempt count does not reconcile")
    if [attempt["attempt"] for attempt in matching] != list(range(1, len(matching) + 1)):
        raise ValueError("Attempt sequence is incomplete or duplicated")
    if sum(attempt["ok"] for attempt in matching) != int(expected_success):
        raise ValueError("Logical result and attempt outcomes disagree")
    if any(attempt["ok"] for attempt in matching[:-1]) or matching[-1]["ok"] is not expected_success:
        raise ValueError("The retry sequence must end immediately after success")
    expected_request = ({"model": "MAI-Image-2.6", "prompt": prompt, "width": 1024, "height": 1024}
                        if group == GROUPS[0] else
                        {"prompt": prompt, "n": 1, "size": "1024x1024", "quality": group.removeprefix("gpt-image-2-")})
    for attempt in matching:
        if attempt["request"] != expected_request:
            raise ValueError("Recorded request differs from the frozen model/quality/resolution contract")
        if not token_count(attempt["request_seconds"]):
            raise ValueError("Attempt duration is invalid")
        if attempt["ok"]:
            if attempt["http_status"] != 200 or (attempt["width"], attempt["height"]) != (1024, 1024):
                raise ValueError("Successful attempt has inconsistent HTTP/image metadata")
            metadata_path = (directory / attempt["response_metadata"]).resolve()
            if not metadata_path.is_relative_to(directory.resolve()):
                raise ValueError("Response metadata path escapes the run directory")
            metadata = json.loads(metadata_path.read_text("utf-8"))
            if len(metadata.get("data", [])) != 1 or "b64_json" in metadata["data"][0]:
                raise ValueError("Archived response metadata has unexpected image content")
    return next((attempt for attempt in matching if attempt["ok"]), None)


def summarize(run_directory, prompts_path):
    result_path = run_directory / "5way_v2_results.json"
    result = json.loads(result_path.read_text("utf-8"))
    if result["state"] not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
        raise ValueError("The paired run has not reached a terminal state")
    config = result["config"]
    if tuple(config["groups"]) != GROUPS or config["rounds"] != 2 or config["resolution"] != "1024x1024":
        raise ValueError("This summary requires the four frozen model/quality configurations")
    if config["concurrency"] != 1 or config["inter_call_wait"] != 5:
        raise ValueError("The measurement schedule differs from the original serial procedure")
    if digest(prompts_path) != config["prompts_sha256"]:
        raise ValueError("Prompt source differs from the measured source")
    validate_source_snapshot(run_directory, result)
    if digest(run_directory / "source" / "prompts.csv") != config["prompts_sha256"]:
        raise ValueError("Prompt snapshot hash does not match")
    with prompts_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]
    if len(prompts) != 11:
        raise ValueError("The original eleven scenarios are required")
    expected_order = [(round_number, prompt_index, group)
                      for round_number in (1, 2)
                      for prompt_index in range(1, len(prompts) + 1)
                      for group in (GROUPS if round_number == 1 else tuple(reversed(GROUPS)))]
    rows = result["raw_data"]
    actual_order = [(row["round"], row["prompt_idx"], row["group"]) for row in rows]
    if actual_order != expected_order or len(rows) != config["formal_sample_count"]:
        raise ValueError("Formal samples do not match the complete ordered 88-sample matrix")
    expected_quality = {group: None if group == GROUPS[0] else group.removeprefix("gpt-image-2-") for group in GROUPS}
    configurations = config["group_configurations"]
    if len(configurations) != len(GROUPS) or [item["id"] for item in configurations] != list(GROUPS):
        raise ValueError("Configuration identities are missing or duplicated")
    for item in configurations:
        is_mai = item["id"] == GROUPS[0]
        if (item["quality"] != expected_quality[item["id"]]
                or item["provider"] != ("mai" if is_mai else "gpt")
                or item["model"] != ("MAI-Image-2.6" if is_mai else "gpt-image-2")
                or item["deployment_sku"] != "GlobalStandard"):
            raise ValueError("Configuration provider/model/quality/SKU differs from the measured matrix")
    attempts_path = run_directory / "attempts.jsonl"
    attempts = [json.loads(line) for line in attempts_path.read_text("utf-8").splitlines() if line]
    formal_attempts = [attempt for attempt in attempts if attempt["phase"] == "formal"]
    warmup_attempts = [attempt for attempt in attempts if attempt["phase"] == "warmup"]
    if len(formal_attempts) + len(warmup_attempts) != len(attempts):
        raise ValueError("Unexpected attempt phase")
    if any((attempt["round"], attempt["prompt_idx"], attempt["group"]) not in expected_order for attempt in formal_attempts):
        raise ValueError("An attempt is outside the frozen formal matrix")
    images = []
    for row in rows:
        prompt = prompts[row["prompt_idx"] - 1]
        if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != row["prompt_sha256"]:
            raise ValueError("Prompt content changed")
        if row["quality"] != expected_quality[row["group"]]:
            raise ValueError("Sample quality label differs from its configuration")
        matching = [attempt for attempt in formal_attempts if
                    (attempt["round"], attempt["prompt_idx"], attempt["group"]) ==
                    (row["round"], row["prompt_idx"], row["group"])]
        succeeded = validate_attempts(run_directory, matching, row["group"], prompt, row["attempt_count"], row["ok"])
        if row["first_attempt_ok"] is not matching[0]["ok"]:
            raise ValueError("First-attempt outcome does not reconcile")
        if not token_count(row["time"]) or not token_count(row["logical_request_seconds"]):
            raise ValueError("Sample duration is not a finite nonnegative value")
        sample_wall_seconds = (datetime.fromisoformat(row["ended_at_utc"]) - datetime.fromisoformat(row["started_at_utc"])).total_seconds()
        if row["logical_request_seconds"] > sample_wall_seconds + 0.1:
            raise ValueError("Logical duration exceeds the recorded sample interval")
        if row["logical_request_seconds"] < sum(attempt["request_seconds"] for attempt in matching) - 0.01:
            raise ValueError("Logical request duration is shorter than its HTTP attempts")
        if succeeded:
            if (row["image_sha256"] != succeeded["image_sha256"] or row["time"] != succeeded["request_seconds"]
                    or row["size_bytes"] != succeeded["image_bytes"]):
                raise ValueError("Successful sample disagrees with its producing attempt")
            metadata = json.loads((run_directory / succeeded["response_metadata"]).read_text("utf-8"))
            if row["token_info"].get("usage") != metadata.get("usage"):
                raise ValueError("Sample usage differs from the archived response")
            images.append(validate_image(run_directory, row["image"], row["image_sha256"]))
        elif (row["token_info"] != {} or row["image"] is not None or row["image_sha256"] is not None
              or row["size_bytes"] != 0 or row["time"] != 0):
            raise ValueError("A failed sample cannot contain inferred output or usage")
    warmups = result["warmup"]
    if [row["group"] for row in warmups] != list(GROUPS) or not all(row["ok"] for row in warmups):
        raise ValueError("Exactly one successful warmup per configuration is required")
    for row in warmups:
        matching = [attempt for attempt in warmup_attempts if attempt["group"] == row["group"]]
        succeeded = validate_attempts(run_directory, matching, row["group"], "blue circle", row["attempt_count"], True)
        metadata = json.loads((run_directory / succeeded["response_metadata"]).read_text("utf-8"))
        if row["token_info"].get("usage") != metadata.get("usage") or row["time"] != succeeded["request_seconds"]:
            raise ValueError("Warmup usage or duration differs from its original response")
        images.append(validate_image(run_directory, "warmup-" + row["group"] + ".png", succeeded["image_sha256"]))
    if sum(row["attempt_count"] for row in warmups) != len(warmup_attempts):
        raise ValueError("Warmup attempt count does not reconcile")
    metrics = []
    for group in GROUPS:
        group_rows = [row for row in rows if row["group"] == group]
        successful = [row for row in group_rows if row["ok"]]
        group_attempts = [attempt for attempt in formal_attempts if attempt["group"] == group]
        configuration = next(item for item in config["group_configurations"] if item["id"] == group)
        metrics.append({"group": group, "configuration": configuration, "planned_samples": len(group_rows),
                        "successful_samples": len(successful), "failed_samples": len(group_rows) - len(successful),
                        "first_attempt_successful_samples": sum(row["first_attempt_ok"] for row in group_rows),
                        "formal_http_attempts": len(group_attempts),
                        "unsuccessful_http_attempts": sum(not attempt["ok"] for attempt in group_attempts),
                        "unsuccessful_attempt_seconds": sum(attempt["request_seconds"] for attempt in group_attempts if not attempt["ok"]),
                        "http_429_attempts": sum(attempt.get("http_status") == 429 for attempt in group_attempts),
                        "successful_request_latency": latency_statistics([row["time"] for row in successful]),
                        "logical_request_latency_all_samples": latency_statistics([row["logical_request_seconds"] for row in group_rows]),
                        "mean_image_kib": statistics.mean(row["size_bytes"] / 1024 for row in successful) if successful else None,
                        "returned_output_tokens": sorted(set(row["token_info"].get("usage", {}).get(
                            "num_output_tokens" if group == GROUPS[0] else "output_tokens") for row in successful
                            if row["token_info"].get("usage", {}).get("num_output_tokens" if group == GROUPS[0] else "output_tokens") is not None)),
                        "per_round": [{"round": round_number, "latency": latency_statistics(
                            [row["time"] for row in successful if row["round"] == round_number])} for round_number in (1, 2)]})
    formal_start = min(datetime.fromisoformat(row["started_at_utc"]) for row in rows)
    formal_end = max(datetime.fromisoformat(row["ended_at_utc"]) for row in rows)
    formal_seconds = (formal_end - formal_start).total_seconds()
    unsuccessful_attempts = [
        {key: attempt.get(key) for key in ("sample_id", "group", "round", "prompt_idx", "attempt",
                                           "started_at_utc", "finished_at_utc", "request_seconds",
                                           "http_status", "exception_type", "error")}
        for attempt in formal_attempts if not attempt["ok"]]
    per_prompt = [{"prompt_index": prompt_index, "prompt": prompt,
                   "configurations": [{"group": group, "rounds": [
                       {"round": row["round"], "ok": row["ok"], "request_seconds": row["time"],
                        "logical_request_seconds": row["logical_request_seconds"], "attempts": row["attempt_count"],
                        "image": row["image"], "image_kib": row["size_bytes"] / 1024}
                       for row in rows if row["prompt_idx"] == prompt_index and row["group"] == group],
                       "latency": latency_statistics([row["time"] for row in rows
                           if row["prompt_idx"] == prompt_index and row["group"] == group and row["ok"]])}
                       for group in GROUPS]} for prompt_index, prompt in enumerate(prompts, 1)]
    return {"run_id": run_directory.name, "validation_status": "PASS", "state": result["state"],
            "result_sha256": digest(result_path), "attempts_sha256": digest(attempts_path),
            "prompts_sha256": digest(prompts_path), "script_sha256": result["script_sha256"],
            "test_started_at_utc": result["started_at_utc"], "test_ended_at_utc": result["ended_at_utc"],
            "environment": result["environment"], "config": config,
            "formal_started_at_utc": formal_start.isoformat(), "formal_ended_at_utc": formal_end.isoformat(),
            "formal_window_seconds_including_waits": formal_seconds,
            "wall_seconds_including_warmup_and_stage_pause": (datetime.fromisoformat(result["ended_at_utc"]) - datetime.fromisoformat(result["started_at_utc"])).total_seconds(),
            "formal_samples": len(rows), "warmup_samples": len(warmups),
            "successful_samples": sum(row["ok"] for row in rows),
            "failed_samples": sum(not row["ok"] for row in rows),
            "formal_http_attempts": len(formal_attempts), "warmup_http_attempts": len(warmup_attempts),
            "unsuccessful_attempts": unsuccessful_attempts,
            "mixed_workload_observed_images_per_minute": sum(row["ok"] for row in rows) * 60 / formal_seconds,
            "groups": metrics, "per_prompt": per_prompt, "images": images,
            "limitations": ["Single 1024x1024 resolution, eleven prompts, two rounds, one serial run; P95 is descriptive.",
                            "Same client and interleaved schedule, but deployment regions and per-request timeouts differ.",
                            "GPT quality labels are not matched to a MAI quality tier; MAI sends no quality field.",
                            "Observed mixed-workload rate includes waits/retries and is not per-model or maximum service throughput.",
                            "Full images and unblinded observations are not a human preference study or automated quality score.",
                            "Earlier April and September measurements are separate cohorts, not pooled samples."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a frozen four-configuration image run without calling any model.")
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--prompts", type=Path, default=Path(__file__).resolve().parents[1] / "prompts.csv")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    summary = summarize(arguments.run_directory, arguments.prompts)
    output = arguments.output or arguments.run_directory / "summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(json.dumps({"validation": "PASS", "formal_samples": summary["formal_samples"],
                      "successes": summary["successful_samples"], "groups": summary["groups"]}))