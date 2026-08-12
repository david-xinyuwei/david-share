"""Pure Foundry Custom Code Training job-contract construction and validation.

This module deliberately imports no Azure SDK. It owns the part of the official
`rft-with-verl` notebook that can be validated offline: configuration shape, SKU mapping,
mount contract, output naming, Ray topology, and the measured environment overrides.
`scripts/submit_job.py` is the thin SDK adapter.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

UPSTREAM_REPOSITORY = "https://github.com/microsoft-foundry/custom-code-training"
UPSTREAM_COMMIT = "018d095f508280efce9e79c4b19fc941d7361b30"
UPSTREAM_SAMPLE = "code-samples/sdk/training/rft-with-verl"
DEFAULT_MODEL_URI = (
    "azureml://registries/azure-huggingface/models/qwen--qwen3-14b/versions/2"
)

SKU_TO_INSTANCE_TYPE = {
    "STANDARD_ND96AMS_A100_V4": "Singularity.ND96am_A100_v4-n1",
    "STANDARD_ND96AMSR_A100_V4": "Singularity.ND96amrs_A100_v4-n1",
    "STANDARD_ND96ISR_H200_V5": "Singularity.ND96r_H200_v5",
    "STANDARD_ND96ISRF_H200_V5": "Singularity.ND96r_H200_v5",
    "STANDARD_ND96IS_H200_V5": "Singularity.ND96_H200_v5",
    "STANDARD_ND96ISRF_H100_V5": "Singularity.ND96r_H100_v5",
    "STANDARD_ND96ISR_H100_V5": "Singularity.ND96r_H100_v5",
    "STANDARD_ND96IS_H100_V5": "Singularity.ND96_H100_v5",
    "STANDARD_ND96IS_NOIB_H100_V5": "Singularity.ND96_H100_v5",
    "STANDARD_ND96IS_FLEX_H100_V5": "Singularity.ND96_H100_v5",
    "STANDARD_ND96AMS_A100_FLEX_V4": "Singularity.ND96am_A100_v4-n1",
    "STANDARD_NC96ADS_A100_V4": "Singularity.NC96ad_A100_v4-n1",
    "STANDARD_ND96ASR_V4": "Singularity.ND96rs_v4-n1",
}

SKU_TO_GPUS_PER_NODE = {
    sku: (4 if sku == "STANDARD_NC96ADS_A100_V4" else 8)
    for sku in SKU_TO_INSTANCE_TYPE
}

REQUIRED_CONFIG_KEYS = {
    "projectEndpoint",
    "computeId",
    "computeClusterSku",
    "uamiId",
    "storageConnectionName",
    "environmentImage",
    "nodeCount",
    "gpusPerNode",
}
OPTIONAL_CONFIG_KEYS = {
    "$schema",
    "modelDatasetUri",
    "codeDatasetName",
    "dataDatasetName",
    "jobPrefix",
    "description",
}
REQUIRED_SAMPLE_FILES = (
    "code/verl_rft_startup.sh",
    "code/reasoning_train_rft.py",
    "code/jsonl_dataset.py",
    "code/retail_tool.py",
    "code/retail_tools.py",
    "code/retail_db.json",
    "code/retail_grader_rft_tools_v3.py",
    "code/retail_toolcall_reward.py",
    "code/config/tool_config/tool_config_template.yaml",
    "data/train.jsonl",
    "data/validation.jsonl",
)
PLACEHOLDER_RE = re.compile(r"<[^>]+>")
ARM_COMPUTE_RE = re.compile(
    r"^/subscriptions/[^/]+/resourcegroups/[^/]+/providers/"
    r"microsoft\.cognitiveservices/accounts/[^/]+/computes/[^/]+$",
    re.IGNORECASE,
)
ARM_UAMI_RE = re.compile(
    r"^/subscriptions/[^/]+/resourcegroups/[^/]+/providers/"
    r"microsoft\.managedidentity/userassignedidentities/[^/]+$",
    re.IGNORECASE,
)


class ContractError(ValueError):
    """Raised when a job configuration cannot produce the verified contract."""


@dataclass(frozen=True)
class Contract:
    """SDK-independent representation of the Foundry CommandJob."""

    command: str
    inputs: dict[str, dict[str, str]]
    outputs: dict[str, dict[str, str]]
    environment: dict[str, str]
    resources: dict[str, Any]
    distribution: dict[str, Any]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "environment": self.environment,
            "resources": self.resources,
            "distribution": self.distribution,
            "metadata": self.metadata,
        }


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON object from {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"expected a JSON object in {path}")
    return value


def _require_no_placeholders(value: Any, path: str = "config") -> None:
    if isinstance(value, str) and PLACEHOLDER_RE.search(value):
        raise ContractError(f"placeholder remains at {path}: {value!r}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _require_no_placeholders(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _require_no_placeholders(child, f"{path}[{index}]")


def validate_config(config: Mapping[str, Any], *, allow_placeholders: bool = False) -> None:
    missing = sorted(REQUIRED_CONFIG_KEYS - config.keys())
    if missing:
        raise ContractError(f"missing config keys: {', '.join(missing)}")

    unknown = sorted(config.keys() - REQUIRED_CONFIG_KEYS - OPTIONAL_CONFIG_KEYS)
    if unknown:
        raise ContractError(f"unknown config keys: {', '.join(unknown)}")

    if not allow_placeholders:
        _require_no_placeholders(config)

    endpoint = str(config["projectEndpoint"])
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or "/api/projects/" not in parsed.path:
        raise ContractError("projectEndpoint must be an HTTPS Foundry project endpoint")

    compute_id = str(config["computeId"])
    if not allow_placeholders and not ARM_COMPUTE_RE.fullmatch(compute_id):
        raise ContractError("computeId is not a Foundry Compute ARM ID")

    uami_id = str(config["uamiId"])
    if not allow_placeholders and not ARM_UAMI_RE.fullmatch(uami_id):
        raise ContractError("uamiId is not a user-assigned managed identity ARM ID")

    sku = str(config["computeClusterSku"]).upper()
    if sku not in SKU_TO_INSTANCE_TYPE:
        raise ContractError(f"unsupported computeClusterSku: {sku}")

    for key in ("nodeCount", "gpusPerNode"):
        value = config[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ContractError(f"{key} must be a positive integer")

    expected_gpus = SKU_TO_GPUS_PER_NODE[sku]
    if config["gpusPerNode"] != expected_gpus:
        raise ContractError(
            f"gpusPerNode must equal {expected_gpus} for {sku}, got {config['gpusPerNode']}"
        )

    image = str(config["environmentImage"])
    if not allow_placeholders:
        if ":" not in image.rsplit("/", 1)[-1] and "@sha256:" not in image:
            raise ContractError("environmentImage must be pinned by tag or digest")
        if image.endswith(":latest"):
            raise ContractError("environmentImage must not use the mutable :latest tag")

    model_uri = str(config.get("modelDatasetUri", DEFAULT_MODEL_URI))
    if not model_uri.startswith(("azureml://", "azureai://")):
        raise ContractError("modelDatasetUri must use azureml:// or azureai://")

    for key in ("storageConnectionName", "codeDatasetName", "dataDatasetName", "jobPrefix"):
        if key in config and not str(config[key]).strip():
            raise ContractError(f"{key} must not be empty")


def validate_sample_layout(sample_dir: Path) -> None:
    missing = [relative for relative in REQUIRED_SAMPLE_FILES if not (sample_dir / relative).is_file()]
    if missing:
        raise ContractError("official sample payload is incomplete: " + ", ".join(missing))


def validate_overrides(overrides: Mapping[str, Any]) -> dict[str, str]:
    required = {
        "NCCL_P2P_DISABLE": "1",
        "NCCL_SHM_DISABLE": "1",
        "NCCL_DEBUG": "INFO",
        "ROLLOUT_GPU_MEMORY_UTILIZATION": "0.6",
        "TRAINER_LOGGER": '["console"]',
    }
    normalised = {str(key): str(value) for key, value in overrides.items()}
    for key, expected in required.items():
        if normalised.get(key) != expected:
            raise ContractError(f"verified override {key} must equal {expected!r}")

    extra = normalised.get("VERL_EXTRA_OVERRIDES", "")
    expected_tokens = {
        "actor_rollout_ref.rollout.checkpoint_engine.update_weights_bucket_megabytes=4096",
        "actor_rollout_ref.actor.entropy_from_logits_with_chunking=True",
    }
    actual_tokens = set(extra.split())
    if any(token.startswith("+") for token in actual_tokens):
        raise ContractError("verified Hydra overrides target existing keys and must not start with '+'")
    if not expected_tokens.issubset(actual_tokens):
        missing = sorted(expected_tokens - actual_tokens)
        raise ContractError("VERL_EXTRA_OVERRIDES is missing: " + ", ".join(missing))
    return normalised


def build_contract(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any],
    *,
    code_uri: str,
    data_uri: str,
    suffix: str,
    allow_placeholders: bool = False,
) -> Contract:
    validate_config(config, allow_placeholders=allow_placeholders)
    environment = validate_overrides(overrides)

    model_output = f"model_output_{suffix}"
    intermediate_output = f"intermediate_folder_{suffix}"
    command = (
        'bash "${{inputs.code_dataset}}/verl_rft_startup.sh"'
        ' --model-path "${{inputs.model}}"'
        ' --dataset-path "${{inputs.train_data}}"'
        ' --code-path "${{inputs.code_dataset}}"'
        f' --output-model-path "${{{{outputs.{model_output}}}}}"'
        f' --output-intermediate-folder "${{{{outputs.{intermediate_output}}}}}"'
    )

    environment.update(
        {
            "HYDRA_FULL_ERROR": "1",
            "VERL_LOGGING_LEVEL": "INFO",
            "VLLM_USE_DEEP_GEMM": "0",
            "VLLM_MOE_USE_DEEP_GEMM": "0",
            "VLLM_DEEP_GEMM_WARMUP": "skip",
            "VLLM_RAY_EXTRA_ENV_VARS_TO_COPY": (
                "VLLM_USE_DEEP_GEMM,VLLM_MOE_USE_DEEP_GEMM,VLLM_DEEP_GEMM_WARMUP"
            ),
            "N_GPUS_PER_NODE": str(config["gpusPerNode"]),
            "N_NODES": str(config["nodeCount"]),
            "HF_MODEL_ID": "Qwen/Qwen3-14B",
        }
    )

    sku = str(config["computeClusterSku"]).upper()
    model_uri = str(config.get("modelDatasetUri", DEFAULT_MODEL_URI))
    return Contract(
        command=command,
        inputs={
            "train_data": {"type": "uri_folder", "path": data_uri, "mode": "ReadOnlyMount"},
            "model": {"type": "uri_folder", "path": model_uri, "mode": "ReadOnlyMount"},
            "code_dataset": {"type": "uri_folder", "path": code_uri, "mode": "ReadOnlyMount"},
        },
        outputs={
            model_output: {
                "type": "custom_model",
                "mode": "ReadWriteMount",
                "asset_name": model_output,
            },
            intermediate_output: {
                "type": "uri_folder",
                "mode": "ReadWriteMount",
                "asset_name": intermediate_output,
            },
        },
        environment=environment,
        resources={
            "instance_count": int(config["nodeCount"]),
            "instance_type": SKU_TO_INSTANCE_TYPE[sku],
            "properties": {
                "AISuperComputer": {
                    "interactive": False,
                    "slaTier": "Premium",
                    "imageVersion": "",
                    "scalePolicy": {
                        "autoScaleIntervalInSec": 120,
                        "maxInstanceTypeCount": int(config["nodeCount"]),
                        "minInstanceTypeCount": int(config["nodeCount"]),
                    },
                }
            },
        },
        distribution={
            "type": "Ray",
            "port": 6379,
            "include_dashboard": "False",
            "head_node_additional_args": "",
            "worker_node_additional_args": "",
        },
        metadata={
            "upstreamRepository": UPSTREAM_REPOSITORY,
            "upstreamCommit": UPSTREAM_COMMIT,
            "upstreamSample": UPSTREAM_SAMPLE,
            "computeClusterSku": sku,
            "environmentImage": str(config["environmentImage"]),
            "computeId": str(config["computeId"]),
            "uamiId": str(config["uamiId"]),
            "jobPrefix": str(config.get("jobPrefix", "verl-retail-grpo")),
            "description": str(config.get("description", "verl RFT (GRPO) submission")),
        },
    )
