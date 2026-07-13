#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FATAL_RE = re.compile(
    r"Traceback \(most recent call last\)|OutOfMemoryError|ClientPayloadError|"
    r"No available .*worker|Engine is dead|Segmentation fault|"
    r"Memory access fault|HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION|"
    r"Fatal Python error|"
    r"longer than the model['’]s context length|exceeds the maximum allowed length|"
    r"Health check failed|_watchdog_thread",
    re.IGNORECASE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("onep", "dp2"), required=True)
    args = parser.parse_args()

    expected_names = {
        "onep": {"prefill_outer.log", "decode_outer.log", "router_outer.log"},
        "dp2": {"node0_outer.log", "node1_outer.log", "router_outer.log"},
    }[args.profile]
    supplied_names = [path.name for path in args.logs]
    profile_valid = len(supplied_names) == len(expected_names) and set(supplied_names) == expected_names
    rows = []
    for path in args.logs:
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        row = {
            "path": str(path),
            "exists": path.exists(),
            "fatal_count": len(FATAL_RE.findall(text)),
            "tuned_config_loaded": "mimo_v2_5_pro_b16_tuned_fmoe.csv" in text,
        }
        rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    evidence = {"profile": args.profile, "profile_valid": profile_valid, "logs": rows}
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    if not profile_valid:
        raise SystemExit(f"Expected exactly these logs: {sorted(expected_names)}")
    if any(not row["exists"] for row in rows):
        raise SystemExit("One or more required service logs are missing")
    if any(row["fatal_count"] for row in rows):
        raise SystemExit("One or more service logs contain fatal markers")
    if any(
        row["path"].endswith("_outer.log")
        and not row["path"].endswith("router_outer.log")
        and not row["tuned_config_loaded"]
        for row in rows
    ):
        raise SystemExit("One or more service logs are missing the tuned config marker")


if __name__ == "__main__":
    main()