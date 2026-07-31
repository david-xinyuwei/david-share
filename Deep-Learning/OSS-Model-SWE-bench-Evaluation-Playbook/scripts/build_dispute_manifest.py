#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

from swebench_outcomes import is_pass, load_outcomes, require_expected_count, sha256


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze the bidirectional Pass/Not-Pass disputes between two full reports."
    )
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reference = load_outcomes(args.reference_report)
    candidate = load_outcomes(args.candidate_report)
    require_expected_count(reference, args.expected_count, args.reference_report)
    require_expected_count(candidate, args.expected_count, args.candidate_report)
    if set(reference) != set(candidate):
        missing_reference = sorted(set(candidate) - set(reference))
        missing_candidate = sorted(set(reference) - set(candidate))
        raise ValueError(
            "Report ID sets differ: "
            f"missing_reference={missing_reference[:5]} "
            f"missing_candidate={missing_candidate[:5]}"
        )

    rows = []
    for instance_id in sorted(reference):
        reference_outcome = reference[instance_id]
        candidate_outcome = candidate[instance_id]
        if is_pass(reference_outcome) == is_pass(candidate_outcome):
            continue
        rows.append(
            {
                "instance_id": instance_id,
                "direction": (
                    "REFERENCE_PASS_CANDIDATE_NOT"
                    if is_pass(reference_outcome)
                    else "CANDIDATE_PASS_REFERENCE_NOT"
                ),
                "reference_outcome": reference_outcome,
                "candidate_outcome": candidate_outcome,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "instance_id",
                "direction",
                "reference_outcome",
                "candidate_outcome",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "contract": "bidirectional binary disputes frozen before any targeted retest",
        "expected_cases": args.expected_count,
        "total_cases": len(reference),
        "frozen_disputes": len(rows),
        "reference_pass_candidate_not": sum(
            row["direction"] == "REFERENCE_PASS_CANDIDATE_NOT" for row in rows
        ),
        "candidate_pass_reference_not": sum(
            row["direction"] == "CANDIDATE_PASS_REFERENCE_NOT" for row in rows
        ),
        "reference_report_sha256": sha256(args.reference_report),
        "candidate_report_sha256": sha256(args.candidate_report),
        "manifest_sha256": sha256(args.output),
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        "DISPUTE_MANIFEST=PASS "
        f"total={len(reference)} disputes={len(rows)} "
        f"directions={summary['reference_pass_candidate_not']}/"
        f"{summary['candidate_pass_reference_not']}"
    )


if __name__ == "__main__":
    main()
