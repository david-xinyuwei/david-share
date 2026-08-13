"""Offline tests for the Foundry job contract. No Azure SDK or credential required."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from job_contract import (  # noqa: E402
    ContractError,
    REQUIRED_SAMPLE_FILES,
    build_contract,
    validate_config,
    validate_overrides,
    validate_sample_layout,
)


@pytest.fixture
def config() -> dict:
    return {
        "projectEndpoint": "https://account.services.ai.azure.com/api/projects/project",
        "computeId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/account/computes/cluster"
        ),
        "computeClusterSku": "STANDARD_NC96ADS_A100_V4",
        "uamiId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.ManagedIdentity/userAssignedIdentities/training-uami"
        ),
        "storageConnectionName": "workspace-storage",
        "modelDatasetUri": (
            "azureml://registries/azure-huggingface/models/qwen--qwen3-14b/versions/2"
        ),
        "environmentImage": "registry.example/verl-rft:cu128-verified",
        "nodeCount": 1,
        "gpusPerNode": 4,
        "codeDatasetName": "verl-retail-code",
        "dataDatasetName": "verl-retail-data",
        "jobPrefix": "verl-retail-grpo",
    }


@pytest.fixture
def overrides() -> dict:
    return {
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


def test_builds_measured_nc96_contract(config, overrides):
    contract = build_contract(
        config,
        overrides,
        code_uri="azureai://code/version/1",
        data_uri="azureai://data/version/1",
        suffix="abc123",
    )

    assert contract.resources["instance_type"] == "Singularity.NC96ad_A100_v4-n1"
    assert contract.resources["instance_count"] == 1
    assert contract.distribution == {
        "type": "Ray",
        "port": 6379,
        "include_dashboard": "False",
        "head_node_additional_args": "",
        "worker_node_additional_args": "",
    }
    assert contract.inputs["model"]["mode"] == "ReadOnlyMount"
    assert contract.outputs["model_output_abc123"]["type"] == "custom_model"
    assert contract.outputs["model_output_abc123"]["asset_name"] == "model_output_abc123"
    assert "${{inputs.code_dataset}}/verl_rft_startup.sh" in contract.command
    assert "${{outputs.model_output_abc123}}" in contract.command


def test_contract_contains_every_measured_override(config, overrides):
    contract = build_contract(
        config, overrides, code_uri="code", data_uri="data", suffix="run"
    )
    assert contract.environment["NCCL_P2P_DISABLE"] == "1"
    assert contract.environment["NCCL_SHM_DISABLE"] == "1"
    assert contract.environment["ROLLOUT_GPU_MEMORY_UTILIZATION"] == "0.6"
    assert "checkpoint_engine.update_weights_bucket_megabytes=4096" in (
        contract.environment["VERL_EXTRA_OVERRIDES"]
    )
    assert "entropy_from_logits_with_chunking=True" in (
        contract.environment["VERL_EXTRA_OVERRIDES"]
    )


def test_rejects_unreplaced_placeholder(config):
    config["projectEndpoint"] = "https://<account>.services.ai.azure.com/api/projects/project"
    with pytest.raises(ContractError, match="placeholder remains"):
        validate_config(config)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://account.services.ai.azure.com/api/projects/project",
        "https://evil.example/api/projects/project",
        "https://account.services.ai.azure.com@evil.example/api/projects/project",
        "https://account.services.ai.azure.com:443/api/projects/project",
        "https://ACCOUNT.services.ai.azure.com/api/projects/project",
        "https://account.services.ai.azure.com/api/projects/project/extra",
        "https://account.services.ai.azure.com/api/projects/project?target=other",
        "https://account.services.ai.azure.com/api/projects/project#fragment",
        "https://account.services.ai.azure.com/api/projects/project%2Fextra",
        "https://account.services.ai.azure.com/api/projects/project%3Ftarget",
        "https://account.services.ai.azure.com/api/projects/project%23fragment",
    ],
)
def test_rejects_non_foundry_project_endpoint(config, endpoint):
    config["projectEndpoint"] = endpoint
    with pytest.raises(ContractError, match="HTTPS Foundry project endpoint"):
        validate_config(config)


def test_schema_and_runtime_accept_exact_foundry_project_endpoint(config):
    endpoint = "https://account-01.services.ai.azure.com/api/projects/project_name"
    config["projectEndpoint"] = endpoint
    validate_config(config)
    schema_path = Path(__file__).resolve().parents[1] / "configs/foundry-job.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    endpoint_schema = schema["properties"]["projectEndpoint"]
    assert sum(bool(re.search(rule["pattern"], endpoint)) for rule in endpoint_schema["oneOf"]) == 1


def test_schema_and_example_mode_accept_exact_endpoint_placeholders(config):
    endpoint = "https://<account>.services.ai.azure.com/api/projects/<project>"
    config["projectEndpoint"] = endpoint
    validate_config(config, allow_placeholders=True)
    schema_path = Path(__file__).resolve().parents[1] / "configs/foundry-job.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    endpoint_schema = schema["properties"]["projectEndpoint"]
    assert sum(bool(re.search(rule["pattern"], endpoint)) for rule in endpoint_schema["oneOf"]) == 1


def test_example_mode_allows_placeholders_but_still_checks_shape(config):
    config["computeId"] = "/subscriptions/<sub>/resourcegroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/computes/<compute>"
    validate_config(config, allow_placeholders=True)
    config["nodeCount"] = 0
    with pytest.raises(ContractError, match="positive integer"):
        validate_config(config, allow_placeholders=True)


def test_rejects_unknown_config_key(config):
    config["gpuCount"] = 4
    with pytest.raises(ContractError, match="unknown config keys: gpuCount"):
        validate_config(config)


def test_rejects_mutable_latest_image(config):
    config["environmentImage"] = "registry.example/verl-rft:latest"
    with pytest.raises(ContractError, match="must not use"):
        validate_config(config)


@pytest.mark.parametrize(
    "image",
    [
        "registry.example/verl-rft@sha256:not-a-digest",
        "registry.example/verl-rft@sha256:ABCDEF",
        "registry.example/verl-rft@sha256:" + "a" * 63,
        "registry.example/verl-rft@other:tag",
    ],
)
def test_rejects_malformed_image_digest(config, image):
    config["environmentImage"] = image
    with pytest.raises(ContractError, match="64 lowercase hex"):
        validate_config(config)


def schema_accepts_image(image: str) -> bool:
    schema_path = Path(__file__).resolve().parents[1] / "configs/foundry-job.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    image_schema = schema["properties"]["environmentImage"]
    matches = sum(bool(re.search(rule["pattern"], image)) for rule in image_schema["oneOf"])
    rejected = bool(re.search(image_schema["not"]["pattern"], image))
    return matches == 1 and not rejected


@pytest.mark.parametrize(
    "image",
    [
        "registry.example/verl-rft:verified",
        "registry.example:5000/team/verl-rft:verified",
        "registry.example/verl-rft@sha256:" + "a" * 64,
        "registry.example/verl-rft:verified@sha256:" + "b" * 64,
    ],
)
def test_schema_accepts_pinned_image_reference(image):
    assert schema_accepts_image(image)


@pytest.mark.parametrize(
    "image",
    [
        "registry.example/verl-rft:latest",
        "registry.example/verl-rft@sha256:not-a-digest",
        "registry.example/verl-rft@sha256:" + "a" * 63,
        "registry.example/verl-rft@other:tag",
        "registry.example/verl-rft",
    ],
)
def test_schema_rejects_unpinned_or_malformed_image_reference(image):
    assert not schema_accepts_image(image)


def test_rejects_unsupported_sku(config):
    config["computeClusterSku"] = "STANDARD_NC24ADS_A100_V4"
    with pytest.raises(ContractError, match="unsupported computeClusterSku"):
        validate_config(config)


@pytest.mark.parametrize("sku", ["STANDARD_D64_V3", "STANDARD_NC24S_V3"])
def test_rejects_non_grpo_compute_families(config, sku):
    config["computeClusterSku"] = sku
    with pytest.raises(ContractError, match="unsupported computeClusterSku"):
        validate_config(config)


def test_rejects_gpu_count_that_does_not_match_sku(config):
    config["gpusPerNode"] = 8
    with pytest.raises(ContractError, match="must equal 4"):
        validate_config(config)


def test_rejects_wrong_resource_id_shapes(config):
    config["computeId"] = "/subscriptions/sub/resourcegroups/rg/providers/Microsoft.Compute/virtualMachines/vm"
    with pytest.raises(ContractError, match="Compute ARM ID"):
        validate_config(config)


def test_rejects_missing_nccl_shm_override(overrides):
    del overrides["NCCL_SHM_DISABLE"]
    with pytest.raises(ContractError, match="NCCL_SHM_DISABLE"):
        validate_overrides(overrides)


def test_rejects_hydra_plus_prefix(overrides):
    overrides["VERL_EXTRA_OVERRIDES"] = (
        "+actor_rollout_ref.rollout.checkpoint_engine."
        "update_weights_bucket_megabytes=4096 "
        "actor_rollout_ref.actor.entropy_from_logits_with_chunking=True"
    )
    with pytest.raises(ContractError, match="must not start"):
        validate_overrides(overrides)


def test_rejects_incomplete_upstream_sample(tmp_path):
    (tmp_path / "code").mkdir()
    (tmp_path / "code/verl_rft_startup.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    with pytest.raises(ContractError, match="payload is incomplete"):
        validate_sample_layout(tmp_path)


@pytest.mark.parametrize("missing", REQUIRED_SAMPLE_FILES)
def test_rejects_each_missing_runtime_file(tmp_path, missing):
    for relative in REQUIRED_SAMPLE_FILES:
        if relative == missing:
            continue
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test fixture\n", encoding="utf-8")

    with pytest.raises(ContractError, match=re.escape(missing)):
        validate_sample_layout(tmp_path)
