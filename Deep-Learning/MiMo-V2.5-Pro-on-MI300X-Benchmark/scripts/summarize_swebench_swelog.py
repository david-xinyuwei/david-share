#!/usr/bin/env python3
"""Summarize a mini-swe-agent ``swelog`` tarball into per-case TSV and aggregate JSON.

Two modes:

* ``--tarball PATH --label NAME --output-dir data/swebench`` streams a delivered
  ``swelog/<run>/<instance>/{<instance>.traj.json, reward_extra_info.json}`` archive,
  writes ``<label>.cases.tsv`` and merges the aggregate into ``summary.json``.
* ``--check data/swebench`` recomputes every aggregate from the committed TSVs and
  fails closed when the committed ``summary.json`` disagrees.

The scoring rule is the customer's ``exp_stats.py`` rule: a case counts as Pass when its
``exit_status`` is ``Submitted - Pass``; ``Average steps`` is the mean of
``info.model_stats.api_calls``. The tarball itself is not redistributed; its SHA-256 is
recorded so a holder of the delivered package can verify the same bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import statistics
import sys
import tarfile
from collections import Counter
from pathlib import Path

TSV_FIELDS = ("instance_id", "exit_status", "api_calls", "resolved", "patch_exists")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_cases(tarball: Path) -> tuple[str, dict[str, dict], dict[str, str]]:
    cases: dict[str, dict] = {}
    results_index: dict[str, str] = {}
    root = None
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            if len(parts) < 3 or parts[0] != "swelog":
                continue
            root = parts[1]
            if len(parts) == 3 and parts[2] == "results-0.json":
                payload = json.load(archive.extractfile(member))
                results_index = {key: value["exit_status"] for key, value in payload.items()}
                continue
            if len(parts) != 4:
                continue
            instance_id, filename = parts[2], parts[3]
            case = cases.setdefault(instance_id, {"instance_id": instance_id})
            if filename == f"{instance_id}.traj.json":
                traj = json.load(archive.extractfile(member))
                info = traj["info"]
                case["exit_status"] = info["exit_status"]
                case["api_calls"] = int(info["model_stats"]["api_calls"])
            elif filename == "reward_extra_info.json":
                reward = json.load(archive.extractfile(member))
                # Cases that never produced a patch carry no ``resolved`` key.
                case["resolved"] = bool(reward.get("resolved", False))
                case["patch_exists"] = bool(reward.get("patch_exists", False))
    if root is None:
        raise SystemExit(f"no swelog root found in {tarball}")
    return root, cases, results_index


def aggregate(rows: list[dict]) -> dict:
    status_counter = Counter(row["exit_status"] for row in rows)
    passed = status_counter.get("Submitted - Pass", 0)
    total = len(rows)
    resolved = sum(1 for row in rows if str(row["resolved"]).lower() == "true")
    steps = [int(row["api_calls"]) for row in rows]
    return {
        "cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_ratio_pct": round(passed / total * 100, 2),
        "resolved_flag_count": resolved,
        "exit_status_breakdown": dict(sorted(status_counter.items())),
        "limits_exceeded": sum(count for status, count in status_counter.items() if status.startswith("LimitsExceeded")),
        "average_steps": round(statistics.mean(steps), 2),
        "min_steps": min(steps),
        "max_steps": max(steps),
    }


def write_tsv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=TSV_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: item["instance_id"]):
            writer.writerow({field: row[field] for field in TSV_FIELDS})


def load_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def summarize(args: argparse.Namespace) -> None:
    tarball = Path(args.tarball)
    root, cases, results_index = read_cases(tarball)
    rows = []
    for instance_id, case in cases.items():
        missing = [field for field in TSV_FIELDS if field not in case]
        if missing:
            raise SystemExit(f"{instance_id}: missing {missing}")
        if results_index and results_index.get(instance_id) != case["exit_status"]:
            raise SystemExit(f"{instance_id}: results-0.json disagrees with traj exit_status")
        if (case["exit_status"] == "Submitted - Pass") != case["resolved"]:
            raise SystemExit(f"{instance_id}: exit_status and reward.resolved disagree")
        rows.append(case)
    if results_index and set(results_index) != set(cases):
        raise SystemExit("results-0.json case set differs from trajectory case set")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tsv_path = output_dir / f"{args.label}.cases.tsv"
    write_tsv(tsv_path, rows)
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {"runs": {}}
    entry = summary["runs"].setdefault(args.label, {})
    entry.update(
        {
            "swelog_root": root,
            "delivered_package": tarball.name,
            "delivered_package_sha256": sha256_file(tarball),
            "cases_tsv": tsv_path.name,
            "cases_tsv_sha256": sha256_file(tsv_path),
            **aggregate(rows),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{args.label}: {entry['passed']}/{entry['cases']} = {entry['pass_ratio_pct']}% avg_steps={entry['average_steps']}")


def check(args: argparse.Namespace) -> None:
    directory = Path(args.check)
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    failures = []
    for label, entry in summary["runs"].items():
        tsv_path = directory / entry["cases_tsv"]
        if sha256_file(tsv_path) != entry["cases_tsv_sha256"]:
            failures.append(f"{label}: cases TSV hash mismatch")
            continue
        recomputed = aggregate(load_tsv(tsv_path))
        for key, value in recomputed.items():
            if entry.get(key) != value:
                failures.append(f"{label}: {key} committed={entry.get(key)!r} recomputed={value!r}")
        print(f"RUN {label} {entry['passed']}/{entry['cases']} {entry['pass_ratio_pct']}% steps={entry['average_steps']}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        raise SystemExit(1)
    print("SWEBENCH_SUMMARY=PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tarball", help="delivered swelog tar.gz to summarize")
    parser.add_argument("--label", help="run label used for the TSV name and summary key")
    parser.add_argument("--output-dir", default="data/swebench")
    parser.add_argument("--check", metavar="DIR", help="recompute aggregates from committed TSVs and compare")
    args = parser.parse_args()
    if args.check:
        check(args)
    elif args.tarball and args.label:
        summarize(args)
    else:
        parser.error("use --tarball/--label to summarize or --check DIR to verify")


if __name__ == "__main__":
    main()
