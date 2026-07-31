#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

from swebench_outcomes import is_pass, load_outcomes, require_expected_count, sha256


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        required = {
            "instance_id",
            "direction",
            "reference_outcome",
            "candidate_outcome",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Dispute manifest is missing required columns: {sorted(required)}")
        return list(reader)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Replace every frozen dispute exactly once. Missing, extra, or overlapping "
            "targeted results fail closed."
        )
    )
    parser.add_argument("--reference-report", type=Path, required=True)
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--dispute-manifest", type=Path, required=True)
    parser.add_argument(
        "--retest-report",
        type=Path,
        action="append",
        default=[],
        help="Repeat for disjoint retest shards; omit when the frozen set is empty.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    reference = load_outcomes(args.reference_report)
    baseline = load_outcomes(args.baseline_report)
    require_expected_count(reference, args.expected_count, args.reference_report)
    require_expected_count(baseline, args.expected_count, args.baseline_report)
    if set(reference) != set(baseline):
        raise ValueError("Reference and baseline report ID sets differ")

    expected_disputes = {
        instance_id
        for instance_id in reference
        if is_pass(reference[instance_id]) != is_pass(baseline[instance_id])
    }
    manifest_rows = read_manifest(args.dispute_manifest)
    manifest_ids = {row["instance_id"] for row in manifest_rows}
    if len(manifest_rows) != len(manifest_ids):
        raise ValueError("Dispute manifest contains duplicate instance IDs")
    if manifest_ids != expected_disputes:
        raise ValueError(
            "Dispute manifest is not the frozen full binary difference: "
            f"expected={len(expected_disputes)} actual={len(manifest_ids)}"
        )
    for row in manifest_rows:
        instance_id = row["instance_id"]
        expected_direction = (
            "REFERENCE_PASS_CANDIDATE_NOT"
            if is_pass(reference[instance_id])
            else "CANDIDATE_PASS_REFERENCE_NOT"
        )
        expected_row = {
            "direction": expected_direction,
            "reference_outcome": reference[instance_id],
            "candidate_outcome": baseline[instance_id],
        }
        actual_row = {key: row[key] for key in expected_row}
        if actual_row != expected_row:
            raise ValueError(
                f"Dispute manifest metadata differs from current reports for {instance_id}"
            )

    retest = {}
    retest_hashes = {}
    for path in args.retest_report:
        shard = load_outcomes(path)
        overlap = set(retest) & set(shard)
        if overlap:
            raise ValueError(f"Retest shards overlap: {sorted(overlap)[:5]}")
        retest.update(shard)
        retest_hashes[str(path)] = sha256(path)
    if set(retest) != manifest_ids:
        missing = sorted(manifest_ids - set(retest))
        extra = sorted(set(retest) - manifest_ids)
        raise ValueError(
            "Retest results must cover every frozen dispute exactly once: "
            f"missing={missing[:5]} extra={extra[:5]}"
        )

    final_outcomes = dict(baseline)
    final_outcomes.update(retest)
    resolved_ids = sorted(
        instance_id for instance_id, outcome in final_outcomes.items() if outcome == "R"
    )
    counts = {
        outcome: sum(value == outcome for value in final_outcomes.values())
        for outcome in ("R", "U", "E", "X")
    }
    total = len(final_outcomes)
    accuracy_pct = round(len(resolved_ids) / total * 100, 2)

    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for instance_id in sorted(final_outcomes):
        rows.append(
            {
                "instance_id": instance_id,
                "baseline_outcome": baseline[instance_id],
                "final_outcome": final_outcomes[instance_id],
                "source": "targeted_retest" if instance_id in retest else "uncontested_baseline",
            }
        )
    outcomes_path = args.output_dir / "final-outcomes.tsv"
    with outcomes_path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["instance_id", "baseline_outcome", "final_outcome", "source"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "contract": {
            "expected_cases": args.expected_count,
            "frozen_disputes": len(manifest_ids),
            "targeted_results": len(retest),
            "dynamic_narrowing": False,
            "one_targeted_outcome_per_dispute": True,
        },
        "result": {
            "resolved": len(resolved_ids),
            "unresolved": counts["U"],
            "empty": counts["E"],
            "errors": counts["X"],
            "total": total,
            "accuracy_pct": accuracy_pct,
        },
        "evidence": {
            "reference_report_sha256": sha256(args.reference_report),
            "baseline_report_sha256": sha256(args.baseline_report),
            "dispute_manifest_sha256": sha256(args.dispute_manifest),
            "retest_report_sha256": retest_hashes,
            "final_outcomes_sha256": sha256(outcomes_path),
        },
    }
    (args.output_dir / "final-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(
        "FROZEN_DISPUTE_FINAL=PASS "
        f"resolved={len(resolved_ids)}/{total} accuracy={accuracy_pct:.2f}%"
    )


if __name__ == "__main__":
    main()
