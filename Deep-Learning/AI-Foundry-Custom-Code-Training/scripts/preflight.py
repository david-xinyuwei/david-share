"""Fail-closed offline preflight for the official rft-with-verl sample.

No Azure call is made. The preflight checks the public job configuration, verifies the
upstream sample payload and JSONL contracts, freezes hashes, then renders the exact job
contract that `submit_job.py` will hand to the pinned Foundry SDK.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from job_contract import (
    ContractError,
    REQUIRED_SAMPLE_FILES,
    build_contract,
    load_json_object,
    validate_config,
    validate_overrides,
    validate_sample_layout,
)

REQUIRED_RECORD_KEYS = {"data_source", "prompt", "reward_model", "extra_info"}
ALLOWED_ROLES = {"system", "user", "assistant", "tool"}
DEFAULT_INPUT_MANIFEST = Path(__file__).resolve().parents[1] / "evidence/input-manifest.jsonl"
UPLOAD_ROOTS = ("code", "data")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError as error:
        raise ContractError(f"cannot inspect upload tree entry {path}: {error}") from error
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def upload_tree_inventory(sample_dir: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for root_name in UPLOAD_ROOTS:
        root = sample_dir / root_name
        if is_link_like(root):
            raise ContractError(f"upload tree root must not be a link or reparse point: {root}")
        if not root.is_dir():
            raise ContractError(f"upload tree is missing directory: {root}")
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if is_link_like(path):
                raise ContractError(f"upload tree must not contain links or reparse points: {path}")
            if path.is_file():
                inventory.append(
                    {
                        "path": path.relative_to(sample_dir).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
            elif not path.is_dir():
                raise ContractError(f"upload tree contains an unsupported entry: {path}")
    if not inventory:
        raise ContractError("upload tree contains no files")
    return inventory


def create_upload_snapshot(sample_dir: Path, destination: Path) -> Path:
    if destination.exists():
        raise ContractError(f"upload snapshot destination already exists: {destination}")
    source_inventory = upload_tree_inventory(sample_dir)
    try:
        destination.mkdir(parents=True)
        for root_name in UPLOAD_ROOTS:
            shutil.copytree(
                sample_dir / root_name,
                destination / root_name,
                symlinks=True,
            )
    except OSError as error:
        raise ContractError(f"cannot create upload snapshot: {error}") from error
    require_upload_tree_unchanged(destination, source_inventory)
    return destination


def require_upload_tree_unchanged(
    sample_dir: Path, expected_inventory: list[dict[str, Any]]
) -> None:
    actual_inventory = upload_tree_inventory(sample_dir)
    if actual_inventory != expected_inventory:
        expected_by_path = {row["path"]: row for row in expected_inventory}
        actual_by_path = {row["path"]: row for row in actual_inventory}
        changed = sorted(
            path
            for path in set(expected_by_path) | set(actual_by_path)
            if expected_by_path.get(path) != actual_by_path.get(path)
        )
        raise ContractError("staged upload payload changed: " + ", ".join(changed))


def validate_jsonl(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"dataset file is missing: {path}")

    count = 0
    data_sources: set[str] = set()
    max_messages = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ContractError(f"{path.name}:{line_number}: blank JSONL record")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ContractError(f"{path.name}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(record, dict):
                raise ContractError(f"{path.name}:{line_number}: record must be an object")

            missing = REQUIRED_RECORD_KEYS - record.keys()
            if missing:
                raise ContractError(
                    f"{path.name}:{line_number}: missing keys {', '.join(sorted(missing))}"
                )

            source = record["data_source"]
            if not isinstance(source, str) or not source:
                raise ContractError(f"{path.name}:{line_number}: data_source must be a string")
            data_sources.add(source)

            prompt = record["prompt"]
            if not isinstance(prompt, list) or not prompt:
                raise ContractError(f"{path.name}:{line_number}: prompt must be a non-empty list")
            max_messages = max(max_messages, len(prompt))
            for message_index, message in enumerate(prompt):
                if not isinstance(message, dict):
                    raise ContractError(
                        f"{path.name}:{line_number}: prompt[{message_index}] must be an object"
                    )
                role = message.get("role")
                content = message.get("content")
                if role not in ALLOWED_ROLES or not isinstance(content, str) or not content:
                    raise ContractError(
                        f"{path.name}:{line_number}: prompt[{message_index}] has invalid role/content"
                    )
            if not any(message.get("role") == "user" for message in prompt):
                raise ContractError(f"{path.name}:{line_number}: prompt has no user message")

            reward = record["reward_model"]
            if not isinstance(reward, dict) or not isinstance(reward.get("ground_truth"), str):
                raise ContractError(
                    f"{path.name}:{line_number}: reward_model.ground_truth must be a string"
                )
            if not isinstance(record["extra_info"], dict):
                raise ContractError(f"{path.name}:{line_number}: extra_info must be an object")
            count += 1

    if count == 0:
        raise ContractError(f"dataset file is empty: {path}")
    return {
        "path": str(path),
        "records": count,
        "sha256": sha256(path),
        "dataSources": sorted(data_sources),
        "maxMessagesPerPrompt": max_messages,
    }


def validate_input_manifest(
    inventory: list[dict[str, Any]],
    manifest_path: Path,
    upload_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ContractError(f"expected input manifest is missing: {manifest_path}")
    try:
        expected = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except json.JSONDecodeError as error:
        raise ContractError(f"invalid input manifest {manifest_path}: {error}") from error

    expected_identity = [
        {"path": row.get("path"), "bytes": row.get("bytes"), "sha256": row.get("sha256")}
        for row in expected
    ]
    if inventory != expected_identity:
        actual_by_path = {row["path"]: row for row in inventory}
        expected_by_path = {row["path"]: row for row in expected_identity}
        changed = sorted(
            path
            for path in set(actual_by_path) | set(expected_by_path)
            if actual_by_path.get(path) != expected_by_path.get(path)
        )
        raise ContractError("input drift from measured lineage: " + ", ".join(changed))
    upload_by_path = {row["path"]: row for row in upload_inventory}
    expected_by_path = {row["path"]: row for row in expected_identity}
    if upload_by_path != expected_by_path:
        changed = sorted(
            path
            for path in set(upload_by_path) | set(expected_by_path)
            if upload_by_path.get(path) != expected_by_path.get(path)
        )
        raise ContractError("complete upload tree drift from measured lineage: " + ", ".join(changed))
    return {"path": str(manifest_path), "sha256": sha256(manifest_path), "files": len(expected)}


def build_preflight_report(
    config_path: Path,
    overrides_path: Path,
    sample_dir: Path,
    *,
    allow_placeholders: bool,
    expected_input_manifest: Path | None = None,
) -> dict[str, Any]:
    config = load_json_object(config_path)
    overrides = load_json_object(overrides_path)
    validate_config(config, allow_placeholders=allow_placeholders)
    validate_overrides(overrides)
    validate_sample_layout(sample_dir)

    inventory = []
    for relative in REQUIRED_SAMPLE_FILES:
        path = sample_dir / relative
        inventory.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    upload_inventory = upload_tree_inventory(sample_dir)
    manifest = (
        validate_input_manifest(inventory, expected_input_manifest, upload_inventory)
        if expected_input_manifest is not None
        else None
    )

    train = validate_jsonl(sample_dir / "data/train.jsonl")
    validation = validate_jsonl(sample_dir / "data/validation.jsonl")
    contract = build_contract(
        config,
        overrides,
        code_uri="pending://code-dataset-upload",
        data_uri="pending://data-dataset-upload",
        suffix="plan",
        allow_placeholders=allow_placeholders,
    )
    return {
        "status": "EXAMPLE_CONFIG_ONLY" if allow_placeholders else "PREFLIGHT_PASS",
        "sideEffects": [],
        "config": {
            "path": str(config_path),
            "sha256": sha256(config_path),
            "placeholdersAllowed": allow_placeholders,
        },
        "overrides": {"path": str(overrides_path), "sha256": sha256(overrides_path)},
        "sample": {
            "root": str(sample_dir),
            "inventory": inventory,
            "uploadInventory": upload_inventory,
            "expectedInputManifest": manifest,
        },
        "datasets": {"train": train, "validation": validation},
        "contract": contract.as_dict(),
    }


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--overrides", required=True, type=Path)
    parser.add_argument(
        "--sample-dir", required=True, type=Path, help="Upstream rft-with-verl directory"
    )
    parser.add_argument("--write-plan", type=Path)
    parser.add_argument(
        "--expected-input-manifest",
        type=Path,
        default=DEFAULT_INPUT_MANIFEST,
        help="Measured input identity; any byte drift fails before Azure access",
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Validate the shipped example shape; never use for validate/submit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_preflight_report(
            args.config.resolve(),
            args.overrides.resolve(),
            args.sample_dir.resolve(),
            allow_placeholders=args.allow_placeholders,
            expected_input_manifest=args.expected_input_manifest.resolve(),
        )
    except ContractError as error:
        print(f"PREFLIGHT_FAIL: {error}")
        return 1

    if args.write_plan:
        write_json_atomic(args.write_plan, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
