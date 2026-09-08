import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def digest(content):
    return hashlib.sha256(content).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_file(root, relative):
    resolved = (root / relative).resolve()
    require(resolved.is_relative_to(root), "Artifact path escapes the run directory")
    return resolved


def statistics_for(values):
    if not values:
        return {"count": 0}
    return {"count": len(values), "mean": statistics.mean(values),
            "median": statistics.median(values), "minimum": min(values), "maximum": max(values)}


def summarize(root):
    result_bytes = (root / "5way_v2_results.json").read_bytes()
    result = json.loads(result_bytes)
    reference = json.loads((root / "source" / "reference-facts.json").read_text("utf-8"))
    method = reference["method"]
    config = result["config"]
    prompt_path = root / "source" / "prompts.csv"
    with prompt_path.open(encoding="utf-8-sig", newline="") as prompt_file:
        prompts = [row["prompt"].strip() for row in csv.DictReader(prompt_file)]
    require(digest(prompt_path.read_bytes()) == config["prompts_sha256"], "Prompt snapshot changed")
    require(digest((root / "source" / "benchmark_5way_v2.py").read_bytes()) == result["script_sha256"],
            "Executed runner snapshot changed")
    require(len(prompts) == method["prompt_count"] and config["rounds"] == method["rounds"],
            "Prompt count or rounds differ from the frozen protocol")
    groups = {group["id"]: group for group in config["group_configurations"]}
    require(len(groups) == 2 and set(config["groups"]) == set(groups), "Expected two grounding groups")
    for group in groups.values():
        require(group["provider"] == "mai" and group["model"] == method["model"]
                and group["model_version"] == method["model_version"], "Wrong provider or model")
        require(type(group["web_grounding"]) is bool and group["auto_aspect_ratio"] is False,
                "Grounding or aspect-ratio configuration mismatch")
    by_setting = {group["web_grounding"]: group["id"] for group in groups.values()}
    require(set(by_setting) == {False, True}, "Both explicit grounding settings are required")
    require(config["resolution"] == "1024x1024" and config["concurrency"] == 1,
            "Resolution or concurrency changed")
    expected = []
    for round_number in range(1, method["rounds"] + 1):
        order = [by_setting[value] for value in method["round_order"][str(round_number)]]
        require(config["round_order"][str(round_number)] == order, "Group order changed")
        expected.extend((round_number, prompt_index, group_id)
                        for prompt_index in range(1, len(prompts) + 1) for group_id in order)
    require(len(expected) == method["formal_samples"] == config["formal_sample_count"],
            "Planned denominator mismatch")
    rows = result["raw_data"]
    actual = [(row["round"], row["prompt_idx"], row["group"]) for row in rows]
    require(actual == expected[:len(actual)], "Recorded samples are duplicated, reordered or unexpected")
    attempt_lines = (root / "attempts.jsonl").read_bytes().splitlines(keepends=True)
    attempts = [json.loads(line) for line in attempt_lines if line.endswith(b"\n")]
    formal_attempts = [attempt for attempt in attempts if attempt["phase"] == "formal"]
    samples = []
    for row in rows:
        group = groups[row["group"]]
        prompt = prompts[row["prompt_idx"] - 1]
        sample_attempts = [attempt for attempt in formal_attempts
                           if (attempt["round"], attempt["prompt_idx"], attempt["group"])
                           == (row["round"], row["prompt_idx"], row["group"])]
        require(len(sample_attempts) == row["attempt_count"], "Attempt count mismatch")
        require([attempt["attempt"] for attempt in sample_attempts] == list(range(1, len(sample_attempts) + 1)),
                "Attempt sequence mismatch")
        require(row["prompt_sha256"] == digest(prompt.encode("utf-8")), "Row prompt mismatch")
        expected_request = {"model": method["model"], "prompt": prompt, "width": method["width"],
                            "height": method["height"], "auto_aspect_ratio": False,
                            "web_grounding": group["web_grounding"]}
        for attempt in sample_attempts:
            require(attempt["request"] == expected_request, "Actual request differs from the frozen treatment")
            require(math.isfinite(attempt["request_seconds"]) and attempt["request_seconds"] >= 0,
                    "Invalid request duration")
        require(math.isfinite(row["logical_request_seconds"]) and row["logical_request_seconds"] >= 0,
                "Invalid logical duration")
        metadata = {}
        if row["ok"]:
            successes = [attempt for attempt in sample_attempts if attempt["ok"]]
            require(len(successes) == 1 and successes[0] is sample_attempts[-1], "Invalid retry success sequence")
            successful = successes[0]
            require(successful["http_status"] == 200 and row["time"] == successful["request_seconds"],
                    "Successful response timing mismatch")
            expected_image = f'{row["group"]}/r{row["round"]}/{row["prompt_idx"]:02d}_test.png'
            require(row["image"] == expected_image, "Image belongs to another treatment or prompt")
            image_bytes = local_file(root, row["image"]).read_bytes()
            require(digest(image_bytes) == row["image_sha256"] == successful["image_sha256"], "Image hash mismatch")
            require(image_bytes[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", image_bytes[16:24]) == (1024, 1024),
                    "Invalid PNG dimensions")
            require(len(image_bytes) == row["size_bytes"] == successful["image_bytes"], "Image size mismatch")
            metadata = json.loads(local_file(root, successful["response_metadata"]).read_text("utf-8"))
            require(metadata.get("usage") == row["token_info"].get("usage"), "Usage differs from response")
        else:
            require(not any(attempt["ok"] for attempt in sample_attempts) and not row["image"],
                    "Failed sample contains a success or image")
        samples.append({**row, "web_grounding": group["web_grounding"],
                        "response_metadata_keys": sorted(metadata),
                        "input_text_tokens": (metadata.get("usage") or {}).get("num_input_text_tokens")})
    grouped = {}
    for enabled, group_id in by_setting.items():
        selected = [sample for sample in samples if sample["group"] == group_id]
        successes = [sample for sample in selected if sample["ok"]]
        grouped[group_id] = {
            "web_grounding": enabled, "planned_samples": len(prompts) * method["rounds"],
            "recorded_samples": len(selected), "successful_samples": len(successes),
            "failed_samples": len(selected) - len(successes),
            "first_attempt_successful_samples": sum(sample["first_attempt_ok"] for sample in selected),
            "completed_sample_http_attempts": sum(sample["attempt_count"] for sample in selected),
            "unsuccessful_http_status_counts": dict(Counter(str(attempt.get("http_status", "exception"))
                for attempt in formal_attempts if attempt["group"] == group_id and not attempt["ok"])),
            "response_metadata_keys": sorted({key for sample in selected for key in sample["response_metadata_keys"]}),
            "successful_request_seconds": statistics_for([sample["time"] for sample in successes]),
            "logical_request_seconds": statistics_for([sample["logical_request_seconds"] for sample in selected]),
            "input_text_tokens": statistics_for([sample["input_text_tokens"] for sample in successes
                                                  if sample["input_text_tokens"] is not None])}
    complete = result["state"] in ("COMPLETED", "COMPLETED_WITH_FAILURES") and actual == expected
    if complete:
        require(len(result["warmup"]) == method["warmups_excluded"] and all(item["ok"] for item in result["warmup"]),
                "Warmup accounting mismatch")
    return {"validation_status": "PASS", "complete": complete, "state": result["state"],
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "result_sha256": digest(result_bytes), "runner_sha256": result["script_sha256"],
            "prompts_sha256": config["prompts_sha256"], "planned_samples": len(expected),
            "recorded_samples": len(rows), "successful_samples": sum(row["ok"] for row in rows),
            "warmups_excluded": len(result["warmup"]), "groups": grouped, "samples": samples,
            "unsuccessful_attempts": [attempt for attempt in formal_attempts if not attempt["ok"]],
            "boundary": "Data integrity checks are not proof of factual image quality or of a web search being executed."}


def write_artifacts(root, summary):
    destination = root / "web-grounding-summary.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    lines = ["# MAI-Image-2.6 Web Grounding: Original Images", "",
             f'State: {summary["state"]}. Recorded: {summary["recorded_samples"]}/{summary["planned_samples"]}.',
             "", f'{summary["warmups_excluded"]} warmups are excluded. These are all returned original images, not selected best samples.',
             "Times below are successful HTTP request duration / complete logical call duration in seconds.", ""]
    for prompt_index in sorted({sample["prompt_idx"] for sample in summary["samples"]}):
        for round_number in (1, 2):
            selected = [sample for sample in summary["samples"]
                        if sample["prompt_idx"] == prompt_index and sample["round"] == round_number]
            if not selected:
                continue
            cells = []
            for setting in (False, True):
                sample = next((sample for sample in selected if sample["web_grounding"] is setting), None)
                if sample is None:
                    cells.append("PENDING")
                elif sample["ok"]:
                    cells.append(f'![Original image]({sample["image"]})<br>{sample["time"]:.2f} / '
                                 f'{sample["logical_request_seconds"]:.2f} s; {sample["attempt_count"]} attempt(s)')
                else:
                    cells.append(f'NO IMAGE RETURNED; {sample["attempt_count"]} attempt(s)')
            lines.extend([f"## Prompt {prompt_index}, Round {round_number}", "",
                          "| Web Grounding Off | Web Grounding On |", "| --- | --- |",
                          "| " + " | ".join(cells) + " |", ""])
    (root / "image-comparison.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline integrity and latency summary for the grounding supplement.")
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate without writing derived artifacts.")
    arguments = parser.parse_args()
    root = arguments.run_directory.resolve()
    summary = summarize(root)
    require(not arguments.require_complete or summary["complete"], "The experiment has not reached a complete terminal state")
    review_path = root / "visual-review.json"
    if review_path.exists():
        review_bytes = review_path.read_bytes()
        review = json.loads(review_bytes)
        if review["status"] == "COMPLETE":
            require(summary["complete"] and review["result_sha256"] == summary["result_sha256"],
                    "Visual review refers to a different or incomplete result")
            expected_images = {sample["image"]: sample for sample in summary["samples"] if sample["ok"]}
            observed_images = [observation["image"] for observation in review["observations"]]
            require(len(observed_images) == len(set(observed_images)) and set(observed_images) == set(expected_images),
                    "Visual review does not cover every returned image exactly once")
            for observation in review["observations"]:
                sample = expected_images[observation["image"]]
                require(all(observation[field] == sample[field] for field in ("round", "prompt_idx", "web_grounding")),
                        "Visual observation is assigned to the wrong sample")
            summary["visual_review_inventory_verified"] = True
            summary["visual_review_sha256"] = digest(review_bytes)
    if not arguments.check:
        write_artifacts(root, summary)
    print(json.dumps({key: value for key, value in summary.items() if key not in ("samples", "unsuccessful_attempts")}, indent=2))


if __name__ == "__main__":
    main()