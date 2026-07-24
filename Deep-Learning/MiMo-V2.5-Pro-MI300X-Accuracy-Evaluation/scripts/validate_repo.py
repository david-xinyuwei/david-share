#!/usr/bin/env python3
"""Fail-closed validator for the public MI300X accuracy snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "aime": (16, 16, 16, 1.0, 0.903),
    "cmmlu": (128, 384, 345, 345 / 384, 0.901),
    "minerva_math": (1536, 4608, 4498, 4498 / 4608, 0.936),
    "mmlu_pro": (512, 1024, 915, 915 / 1024, 0.851),
    "mmlu_redux": (512, 1536, 1478, 1478 / 1536, 0.9497),
    "supergpqa": (512, 512, 360, 360 / 512, 0.624),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    repo = args.repo.resolve()
    summary = json.loads((repo / "data/results-summary.json").read_text(encoding="utf-8"))

    assert summary["totals"]["final_unique_questions"] == 60_533
    assert summary["totals"]["final_responses"] == 134_239
    assert summary["totals"]["observed_unique_questions"] == 3_216
    assert summary["totals"]["validated_responses"] == 8_080
    assert summary["totals"]["correct_responses"] == 7_612
    assert summary["totals"]["aggregate_accuracy_reported"] is False
    assert len(summary["datasets"]) == 6

    for item in summary["datasets"]:
        dataset = item["dataset"]
        assert dataset in EXPECTED
        questions, responses, correct, accuracy, h200 = EXPECTED[dataset]
        path = repo / item["audit_file"]
        audit = rows(path)
        assert sha256(path) == item["audit_sha256"]
        assert len(audit) == responses
        assert len({row["question_id"] for row in audit}) == questions
        assert all(row["metric"] in (0, 1) for row in audit)
        assert sum(row["metric"] for row in audit) == correct
        keys = [
            (row["question_id"], row["repeat_id"], row["repeat_slot"], row["source_index"])
            for row in audit
        ]
        assert len(keys) == len(set(keys))
        assert item["validated_unique_questions"] == questions
        assert item["validated_responses"] == responses
        assert item["correct"] == correct
        assert abs(item["mi300x_accuracy"] - accuracy) < 1e-12
        assert abs(item["h200_reference_accuracy"] - h200) < 1e-12
        assert item["validated_responses"] <= item["expected_final_responses"]

    readmes = [
        (repo / "README.md").read_text(encoding="utf-8"),
        (repo / "README-CN.md").read_text(encoding="utf-8"),
    ]
    required_fragments = [
        "8,080",
        "134,239",
        "100.0000%",
        "89.8438%",
        "97.6128%",
        "89.3555%",
        "96.2240%",
        "70.3125%",
    ]
    for text in readmes:
        for fragment in required_fragments:
            assert fragment in text, fragment
        assert not re.search(r"(?:20\.\d+\.\d+\.\d+|172\.16\.\d+\.\d+|root@|33901)", text)

    patch_hashes = (repo / "patches/evaluator-hashes.tsv").read_text(encoding="utf-8").splitlines()
    assert len([line for line in patch_hashes if line.strip()]) == 6
    assert len(list((repo / "patches").glob("eval_*.patch"))) == 6

    for path in repo.rglob("*"):
        if path.is_file() and path.name not in {"SHA256SUMS.txt"}:
            assert path.stat().st_size > 0, path

    print(
        "REPO_VALIDATION=PASS datasets=6 questions=3216 "
        "responses=8080 correct=7612 full_contract=134239"
    )


if __name__ == "__main__":
    main()
