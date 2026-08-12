"""Dataset and preflight tests built from synthetic test-only fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from job_contract import ContractError, REQUIRED_SAMPLE_FILES  # noqa: E402
from preflight import build_preflight_report, validate_jsonl  # noqa: E402


def valid_record() -> dict:
    return {
        "data_source": "synthetic_test_grader",
        "prompt": [
            {"role": "system", "content": "Use the tool when needed."},
            {"role": "user", "content": "Resolve test order TEST-001."},
        ],
        "reward_model": {"ground_truth": "Action: synthetic pass."},
        "extra_info": {"fixture": True},
    }


def write_sample(root: Path) -> None:
    for relative in REQUIRED_SAMPLE_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".jsonl":
            path.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
        elif path.suffix == ".yaml":
            path.write_text("tools: []\n", encoding="utf-8")
        else:
            path.write_text("# synthetic test fixture\n", encoding="utf-8")


def write_inputs(root: Path) -> tuple[Path, Path]:
    config = {
        "projectEndpoint": "https://account.services.ai.azure.com/api/projects/project",
        "computeId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/account/computes/cluster"
        ),
        "computeClusterSku": "STANDARD_NC96ADS_A100_V4",
        "uamiId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.ManagedIdentity/userAssignedIdentities/uami"
        ),
        "storageConnectionName": "storage",
        "environmentImage": "registry.example/verl:verified",
        "nodeCount": 1,
        "gpusPerNode": 4,
    }
    overrides = {
        "NCCL_P2P_DISABLE": "1",
        "NCCL_SHM_DISABLE": "1",
        "NCCL_DEBUG": "INFO",
        "ROLLOUT_GPU_MEMORY_UTILIZATION": "0.6",
        "TRAINER_LOGGER": '["console"]',
        "VERL_EXTRA_OVERRIDES": (
            "actor_rollout_ref.rollout.checkpoint_engine."
            "update_weights_bucket_megabytes=4096 "
            "actor_rollout_ref.actor.entropy_from_logits_with_chunking=True"
        ),
    }
    config_path = root / "config.json"
    overrides_path = root / "overrides.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    return config_path, overrides_path


def test_jsonl_report_has_count_hash_and_source(tmp_path):
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
    report = validate_jsonl(path)
    assert report["records"] == 1
    assert len(report["sha256"]) == 64
    assert report["dataSources"] == ["synthetic_test_grader"]
    assert report["maxMessagesPerPrompt"] == 2


def test_rejects_blank_jsonl_record(tmp_path):
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps(valid_record()) + "\n\n", encoding="utf-8")
    with pytest.raises(ContractError, match="blank JSONL record"):
        validate_jsonl(path)


def test_rejects_record_without_user_message(tmp_path):
    record = valid_record()
    record["prompt"] = [{"role": "system", "content": "System only."}]
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(ContractError, match="no user message"):
        validate_jsonl(path)


def test_preflight_is_offline_and_freezes_inputs(tmp_path):
    sample = tmp_path / "sample"
    write_sample(sample)
    config_path, overrides_path = write_inputs(tmp_path)
    report = build_preflight_report(
        config_path, overrides_path, sample, allow_placeholders=False
    )
    assert report["status"] == "PREFLIGHT_PASS"
    assert report["sideEffects"] == []
    assert report["datasets"]["train"]["records"] == 1
    assert len(report["sample"]["inventory"]) == len(REQUIRED_SAMPLE_FILES)
    assert report["contract"]["distribution"]["type"] == "Ray"
    assert report["contract"]["resources"]["instance_count"] == 1
