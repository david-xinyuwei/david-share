#!/usr/bin/env python3
import argparse
import copy
import hashlib
import json
from pathlib import Path


def remove_path(payload: dict, dotted_path: str) -> None:
    parts = dotted_path.split(".")
    current = payload
    for part in parts[:-1]:
        value = current.get(part)
        if not isinstance(value, dict):
            return
        current = value
    current.pop(parts[-1], None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--ignore",
        action="append",
        default=["environment.image", "agent.output_path"],
        help="Dotted config path to ignore; repeat as needed.",
    )
    args = parser.parse_args()

    predictions = json.loads((args.run_dir / "preds.json").read_text())
    normalized = {}
    for instance_id in sorted(predictions):
        trajectory = json.loads(
            (args.run_dir / instance_id / f"{instance_id}.traj.json").read_text()
        )
        config = copy.deepcopy(trajectory["info"]["config"])
        for dotted_path in args.ignore:
            remove_path(config, dotted_path)
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
        normalized[instance_id] = hashlib.sha256(canonical.encode()).hexdigest()

    unique = sorted(set(normalized.values()))
    print(
        json.dumps(
            {
                "instances": len(normalized),
                "normalized_config_count": len(unique),
                "normalized_config_sha256": unique,
                "ignored_paths": args.ignore,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if len(unique) != 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
