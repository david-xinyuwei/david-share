#!/usr/bin/env python3
"""Fail-closed validator for the public MI300X accuracy snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "aime": (16, 16, 0, 16, 1.0, 0.903, 1.0, 0.95, 65_536, True),
    "cmmlu": (128, 384, 0, 345, 345 / 384, 0.901, 0.0, 1.0, 16_384, None),
    "minerva_math": (1536, 4608, 17, 4498, 4498 / 4608, 0.936, 0.0, 1.0, 16_384, None),
    "mmlu_pro": (512, 1024, 28, 915, 915 / 1024, 0.851, 0.0, 1.0, 16_384, None),
    "mmlu_redux": (512, 1536, 4, 1478, 1478 / 1536, 0.9497, 0.0, 1.0, 16_384, None),
    "supergpqa": (512, 512, 58, 360, 360 / 512, 0.624, 0.0, 1.0, 16_384, None),
}
FORBIDDEN_CONTENT_FIELDS = {
    "ground_truth_sha256", "prediction_sha256", "prompt_sha256", "response_sha256"
}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON: {path}: {exc}") from exc


def load_jsonl(path: Path) -> list[dict]:
    output = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                value = json.loads(line)
                require(isinstance(value, dict), f"non-object JSONL row: {path}:{line_number}")
                output.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSONL: {path}: {exc}") from exc
    return output


def logical_key(row: dict) -> tuple:
    if row.get("repeat_id") is not None:
        return row["question_id"], "repeat", row["repeat_id"]
    return row["question_id"], row["repeat_provenance"], row["repeat_slot"]


def validate_manifest(repo: Path) -> None:
    manifest = repo / "data/evidence/SHA256SUMS.txt"
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    listed = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"invalid SHA256SUMS line: {line!r}")
        expected_hash, relative_text = match.groups()
        relative = Path(relative_text)
        require(not relative.is_absolute(), f"absolute path in SHA256SUMS: {relative_text}")
        require(".." not in relative.parts and ":" not in relative_text, f"unsafe manifest path: {relative_text}")
        target = (repo / relative).resolve()
        require(target.is_relative_to(repo), f"manifest path escapes repo: {relative_text}")
        require(target.is_file(), f"manifest target missing: {relative_text}")
        require(relative_text not in listed, f"duplicate manifest path: {relative_text}")
        require(sha256(target) == expected_hash, f"SHA mismatch: {relative_text}")
        listed.add(relative_text)
    expected_files = {
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(repo).parts
        and "__pycache__" not in path.relative_to(repo).parts
        and path != manifest
    }
    require(listed == expected_files, f"manifest coverage mismatch: missing={sorted(expected_files-listed)} extra={sorted(listed-expected_files)}")


def validate_public_text(repo: Path) -> None:
    forbidden_patterns = {
        "Windows absolute path": re.compile(r"(?i)(?:^|[\s\"'])[a-z]:[\\/]"),
        "WSL absolute path": re.compile(r"/mnt/[a-z]/"),
        "private Linux home": re.compile(r"/(?:root|home)/"),
        "private IPv4": re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
        "shell identity": re.compile(r"\broot@"),
        "deleted evaluator diff": re.compile(r"eval_(?:aime|cmmlu|minerva_math|mmlu_pro|mmlu_redux|supergpqa)\.patch"),
    }
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.relative_to(repo).parts or "__pycache__" in path.relative_to(repo).parts:
            continue
        data = path.read_bytes()
        require(data, f"empty file: {path.relative_to(repo)}")
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in forbidden_patterns.items():
            require(pattern.search(text) is None, f"{label} found in {path.relative_to(repo)}")


def validate_readme(repo: Path) -> None:
    markdown_files = sorted(path for path in repo.rglob("*") if path.is_file() and path.suffix.lower() == ".md")
    require(markdown_files == [repo / "README.md"], f"expected exactly one Markdown file: {markdown_files}")
    readme = (repo / "README.md").read_text(encoding="utf-8")
    required = [
        "8,080条已验证评测记录", "7,973", "107", "134,239", "100.0000%",
        "89.8438%", "97.6128%", "89.3555%", "96.2240%", "70.3125%",
        "Temperature不同来源于各数据集Evaluator（评测器）的合同",
        "NOT VERIFIED / DIRECTIONAL", "旧公开commit曾含低熵答案哈希",
    ]
    for fragment in required:
        require(fragment in readme, f"README required fragment missing: {fragment}")
    require(readme.count("```") % 2 == 0, "unbalanced Markdown code fences")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme):
        if re.match(r"https?://", target) or target.startswith("#"):
            continue
        local_target = target.split("#", 1)[0]
        require((repo / local_target).exists(), f"broken README link: {target}")


def validate_repo(repo: Path) -> None:
    summary = load_json(repo / "data/results-summary.json")
    totals = summary.get("totals", {})
    expected_totals = {
        "final_unique_questions": 60_533, "final_responses": 134_239,
        "observed_unique_questions": 3_216, "validated_responses": 8_080,
        "correct_responses": 7_612, "nonempty_responses": 7_973,
        "length_limited_empty_responses": 107,
    }
    for key, expected in expected_totals.items():
        require(totals.get(key) == expected, f"summary total mismatch for {key}: {totals.get(key)} != {expected}")
    require(totals.get("aggregate_accuracy_reported") is False, "aggregate accuracy must not be reported")
    datasets = summary.get("datasets")
    require(isinstance(datasets, list) and len(datasets) == 6, "expected six dataset summaries")
    require({item.get("dataset") for item in datasets} == set(EXPECTED), "dataset summary keys changed")

    for item in datasets:
        dataset = item["dataset"]
        questions, responses, empty, correct, accuracy, h200, temperature, top_p, max_tokens, thinking = EXPECTED[dataset]
        audit_path = (repo / item["audit_file"]).resolve()
        require(audit_path.is_relative_to(repo) and audit_path.is_file(), f"unsafe/missing audit path for {dataset}")
        audit = load_jsonl(audit_path)
        require(sha256(audit_path) == item["audit_sha256"], f"audit SHA mismatch for {dataset}")
        require(len(audit) == responses, f"row count mismatch for {dataset}")
        require(len({row.get("question_id") for row in audit}) == questions, f"question count mismatch for {dataset}")
        require(all(type(row.get("metric")) is int and row["metric"] in (0, 1) for row in audit), f"non-binary metric for {dataset}")
        require(sum(row["metric"] for row in audit) == correct, f"correct count mismatch for {dataset}")
        keys = [logical_key(row) for row in audit]
        require(len(keys) == len(set(keys)), f"logical duplicate for {dataset}")
        for row in audit:
            require(FORBIDDEN_CONTENT_FIELDS.isdisjoint(row), f"content hash field leaked in {dataset}")
            if row.get("response_empty"):
                require(row["metric"] == 0, f"empty response scored correct in {dataset}")
                require(row.get("finish_reason") == "length", f"empty response without length finish in {dataset}")
                require(row.get("completion_tokens") == max_tokens, f"empty response token limit mismatch in {dataset}")
        require(sum(bool(row.get("response_empty")) for row in audit) == empty, f"empty response count mismatch for {dataset}")
        require(item.get("validated_unique_questions") == questions, f"summary question mismatch for {dataset}")
        require(item.get("validated_responses") == responses, f"summary response mismatch for {dataset}")
        require(item.get("nonempty_responses") == responses - empty, f"summary nonempty mismatch for {dataset}")
        require(item.get("length_limited_empty_responses") == empty, f"summary empty mismatch for {dataset}")
        require(item.get("correct") == correct, f"summary correct mismatch for {dataset}")
        require(abs(item.get("mi300x_accuracy") - accuracy) < 1e-12, f"accuracy mismatch for {dataset}")
        require(abs(item.get("h200_reference_accuracy") - h200) < 1e-12, f"H200 reference mismatch for {dataset}")
        expected_sampling = {"temperature": temperature, "top_p": top_p, "max_tokens": max_tokens, "enable_thinking": thinking}
        sampling = item.get("sampling_evidence", {})
        require(sampling.get("observed_config") == expected_sampling, f"sampling config mismatch for {dataset}")
        sources = sampling.get("source_summaries")
        require(isinstance(sources, list) and sources, f"sampling source evidence missing for {dataset}")
        require(all(re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")) for source in sources), f"sampling source SHA invalid for {dataset}")

    with (repo / "data/results-summary.tsv").open(encoding="utf-8", newline="") as handle:
        tsv_rows = list(csv.DictReader(handle, delimiter="\t"))
    require(len(tsv_rows) == 6, "TSV must contain six datasets")
    for row, item in zip(tsv_rows, datasets):
        require(row["dataset"] == item["display_name"], "TSV dataset order/name mismatch")
        require(int(row["validated_responses"]) == item["validated_responses"], "TSV response count mismatch")
        require(int(row["correct"]) == item["correct"], "TSV correct count mismatch")
        require(abs(float(row["mi300x_accuracy"]) - item["mi300x_accuracy"]) < 1e-11, "TSV accuracy mismatch")

    contract = load_json(repo / "data/xiaomi-final-contract.json")
    require(contract.get("totals") == {"unique_samples": 60_533, "expected_responses": 134_239}, "final contract totals changed")
    hashes = (repo / "patches/evaluator-hashes.tsv").read_text(encoding="utf-8").splitlines()
    require(len([line for line in hashes if line.strip()]) == 7, "evaluator hash table must have header plus six rows")
    require(not list((repo / "patches").glob("*.patch")), "third-party source diff must not be public")
    require({path.name for path in (repo / "scripts").glob("*.py")} == {"build_public_snapshot.py", "validate_repo.py"}, "unexpected public scripts")
    validate_manifest(repo)
    validate_public_text(repo)
    validate_readme(repo)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        validate_repo(repo)
    except ValidationError as exc:
        raise SystemExit(f"REPO_VALIDATION=FAIL {exc}") from exc
    print("REPO_VALIDATION=PASS datasets=6 questions=3216 responses=8080 nonempty=7973 empty_length=107 correct=7612 full_contract=134239")


if __name__ == "__main__":
    main()
