#!/usr/bin/env python3
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


ALLOWED_STATUSES = {"Submitted", "LimitsExceeded", "RepeatedFormatError", "TimeExceeded"}


def read_manifest(path: Path) -> set[str]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    ids = [row["instance_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Manifest contains duplicate instance IDs")
    return set(ids)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    predictions_path = args.run_dir / "preds.json"
    predictions = json.loads(predictions_path.read_text())
    if not isinstance(predictions, dict):
        raise ValueError("preds.json must be an object keyed by instance_id")
    ids = set(predictions)
    if args.manifest and ids != read_manifest(args.manifest):
        raise ValueError("Prediction IDs differ from the frozen manifest")
    if args.expected_count is not None and len(ids) != args.expected_count:
        raise ValueError(f"Prediction count {len(ids)} != {args.expected_count}")

    statuses = Counter()
    config_hashes = set()
    empty = []
    for instance_id in sorted(ids):
        prediction = predictions[instance_id]
        if not isinstance(prediction, dict):
            raise ValueError(f"Prediction for {instance_id} must be an object")
        if prediction.get("instance_id") != instance_id:
            raise ValueError(f"Prediction key and embedded instance_id differ for {instance_id}")
        if not isinstance(prediction.get("model_name_or_path"), str) or not prediction[
            "model_name_or_path"
        ]:
            raise ValueError(f"Missing model_name_or_path for {instance_id}")
        if not isinstance(prediction.get("model_patch"), str):
            raise ValueError(f"model_patch must be a string for {instance_id}")
        path = args.run_dir / instance_id / f"{instance_id}.traj.json"
        trajectory = json.loads(path.read_text())
        info = trajectory.get("info", {})
        status = str(info.get("exit_status", ""))
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Invalid exit status for {instance_id}: {status!r}")
        statuses[status] += 1
        config = info.get("config")
        if not isinstance(config, dict):
            raise ValueError(f"Missing effective config for {instance_id}")
        config_hashes.add(json.dumps(config, sort_keys=True, separators=(",", ":")))
        if not prediction["model_patch"].strip():
            empty.append(instance_id)

    summary = {
        "state": "PASS",
        "predictions": len(ids),
        "nonempty_patches": len(ids) - len(empty),
        "empty_patches": len(empty),
        "empty_patch_ids": empty,
        "exit_statuses": dict(statuses),
        "raw_effective_config_count": len(config_hashes),
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
