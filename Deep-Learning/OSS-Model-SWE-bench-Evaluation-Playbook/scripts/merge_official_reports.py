#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from swebench_outcomes import OUTCOME_KEYS, load_outcomes, require_expected_count, sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    merged = {}
    hashes = {}
    for path in args.report:
        shard = load_outcomes(path)
        overlap = set(merged) & set(shard)
        if overlap:
            raise ValueError(f"Official report shards overlap: {sorted(overlap)[:5]}")
        merged.update(shard)
        hashes[str(path)] = sha256(path)

    require_expected_count(merged, args.expected_count, Path("merged reports"))

    payload = {
        key: sorted(instance_id for instance_id, value in merged.items() if value == outcome)
        for key, outcome in OUTCOME_KEYS.items()
    }
    payload["source_report_sha256"] = hashes
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"MERGED_OFFICIAL_REPORT=PASS cases={len(merged)} shards={len(args.report)}")


if __name__ == "__main__":
    main()
