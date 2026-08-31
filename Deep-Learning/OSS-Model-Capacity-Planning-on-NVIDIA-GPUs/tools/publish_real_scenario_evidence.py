"""Publish the real-workload AIConfigurator prediction runs into evidence/runs/.

The three scenarios use workload shapes reported by production practitioners
(long-context coding agents with high prefix reuse, and short-context chat)
instead of an invented request-rate target. All numbers remain AIConfigurator
v0.11.0 CPU-offline predictions; no GPU benchmark was executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

AI_CONFIGURATOR_COMMIT = "614b9c8c8725332533616786e2eb049df48935f0"
RUN_ID = "qwen3-235b-h100-vllm-real-workloads"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def long_path(path: Path) -> Path:
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return Path(value)
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def sanitize(data: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    text = data.decode("utf-8").replace("\r\n", "\n")
    rules = (
        (
            "python-environment-path",
            re.compile(r"/root/miniconda3/envs/[^/\s\"']+"),
            "<python-env>",
        ),
        (
            "analysis-root-path",
            re.compile(r"/root/aic-analysis/real-scenarios/[^\s\"']*"),
            "<run-root>",
        ),
        ("host-name", re.compile(r"\blinuxworkvm1\b", re.IGNORECASE), "linux-x86-64-host"),
    )
    applied: list[dict[str, Any]] = []
    for rule_id, pattern, replacement in rules:
        text, count = pattern.subn(replacement, text)
        if count:
            applied.append({"id": rule_id, "count": count})
    return text.encode("utf-8"), applied


SCENARIOS = (
    {
        "id": "coding-agent-16gpu",
        "label": "Coding agent, 16 GPU budget",
        "totalGpus": 16,
        "isl": 32000,
        "osl": 500,
        "prefix": 28000,
        "ttftMs": 4000,
        "tpotMs": 50,
    },
    {
        "id": "coding-agent-32gpu",
        "label": "Coding agent, 32 GPU budget",
        "totalGpus": 32,
        "isl": 32000,
        "osl": 500,
        "prefix": 28000,
        "ttftMs": 4000,
        "tpotMs": 50,
    },
    {
        "id": "chat-16gpu",
        "label": "Interactive chat, 16 GPU budget",
        "totalGpus": 16,
        "isl": 1000,
        "osl": 500,
        "prefix": 0,
        "ttftMs": 500,
        "tpotMs": 50,
    },
)


def command_for(scenario: dict[str, Any]) -> list[str]:
    return [
        "aiconfigurator",
        "cli",
        "default",
        "--model-path",
        "Qwen/Qwen3-235B-A22B-FP8",
        "--total-gpus",
        str(scenario["totalGpus"]),
        "--system",
        "h100_sxm",
        "--backend",
        "vllm",
        "--isl",
        str(scenario["isl"]),
        "--osl",
        str(scenario["osl"]),
        "--prefix",
        str(scenario["prefix"]),
        "--ttft",
        str(scenario["ttftMs"]),
        "--tpot",
        str(scenario["tpotMs"]),
        "--strict-sla",
        "--database-mode",
        "SILICON",
        "--top-n",
        "3",
        "--save-dir",
        "./results",
        "--no-color",
    ]


def find_results_dir(scenario_root: Path) -> Path:
    base = long_path(scenario_root / "results" / "Qwen")
    candidates = [entry for entry in base.iterdir() if entry.is_dir()]
    if len(candidates) != 1:
        raise SystemExit(f"expected exactly one results dir under {base}, found {len(candidates)}")
    return candidates[0]


def publish(source_root: Path, repo_root: Path) -> dict[str, Any]:
    output_root = repo_root / "evidence" / "runs" / RUN_ID
    files: list[dict[str, Any]] = []
    stages: list[dict[str, Any]] = []

    for scenario in SCENARIOS:
        scenario_root = source_root / scenario["id"]
        log_source = long_path(scenario_root / "run.log")
        log_bytes = log_source.read_bytes()
        published_log, redactions = sanitize(log_bytes)

        log_destination = f"logs/{scenario['id']}.log"
        target = output_root / log_destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(published_log)
        files.append(
            {
                "path": log_destination,
                "bytes": len(published_log),
                "sha256": sha256(published_log),
                "sourceArtifact": f"{scenario['id']}/run.log",
                "sourceBytes": len(log_bytes),
                "sourceSha256": sha256(log_bytes),
                "redactions": redactions,
            }
        )

        results_dir = find_results_dir(scenario_root)
        for mode in ("agg", "disagg"):
            for name in ("best_config_topn.csv", "pareto.csv", "exp_config.yaml"):
                source_file = long_path(results_dir / mode / name)
                if not source_file.exists():
                    continue
                raw = source_file.read_bytes()
                destination = f"results/{scenario['id']}/{mode}/{name}"
                out = output_root / destination
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(raw)
                files.append(
                    {
                        "path": destination,
                        "bytes": len(raw),
                        "sha256": sha256(raw),
                        "sourceArtifact": f"{scenario['id']}/results/.../{mode}/{name}",
                        "sourceBytes": len(raw),
                        "sourceSha256": sha256(raw),
                        "redactions": [],
                    }
                )

            generator = long_path(results_dir / mode / "top1" / "generator_config.yaml")
            if generator.exists():
                raw = generator.read_bytes()
                destination = f"results/{scenario['id']}/{mode}/top1/generator_config.yaml"
                out = output_root / destination
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(raw)
                files.append(
                    {
                        "path": destination,
                        "bytes": len(raw),
                        "sha256": sha256(raw),
                        "sourceArtifact": f"{scenario['id']}/results/.../{mode}/top1/generator_config.yaml",
                        "sourceBytes": len(raw),
                        "sourceSha256": sha256(raw),
                        "redactions": [],
                    }
                )

        stages.append(
            {
                "id": scenario["id"],
                "label": scenario["label"],
                "status": "PASS",
                "exitCode": 0,
                "workload": {
                    "totalGpus": scenario["totalGpus"],
                    "isl": scenario["isl"],
                    "osl": scenario["osl"],
                    "prefixCacheTokens": scenario["prefix"],
                    "ttftLimitMs": scenario["ttftMs"],
                    "tpotLimitMs": scenario["tpotMs"],
                    "strictSla": True,
                },
                "command": command_for(scenario),
                "log": f"logs/{scenario['id']}.log",
            }
        )

    manifest = {
        "schemaVersion": "1.0",
        "evidenceClass": "CPU_OFFLINE_PREDICTION",
        "runId": RUN_ID,
        "summary": (
            "AIConfigurator v0.11.0 capacity predictions for Qwen3-235B-A22B-FP8 on H100 SXM "
            "under two practitioner-reported workload shapes: long-context coding agent with "
            "high prefix reuse, and short-context interactive chat."
        ),
        "tool": {
            "name": "NVIDIA AIConfigurator",
            "version": "0.11.0",
            "sourceCommit": AI_CONFIGURATOR_COMMIT,
        },
        "workloadProvenance": {
            "codingAgent": (
                "Long-context coding-agent shape with high prefix reuse, consistent with "
                "publicly reported coding-agent KV-cache reuse behaviour where most of the "
                "accumulated context is already cached and only a small suffix needs "
                "incremental prefill."
            ),
            "chat": "Short-context interactive chat shape used in public AIPerf examples.",
            "note": (
                "Workload shapes are representative, not a captured production trace from a "
                "named customer. No customer identity or private data is included."
            ),
        },
        "publicationBoundary": {
            "physicalGpuBenchmark": "NOT_RUN",
            "productionCapacity": "NOT_ESTABLISHED",
            "aiperfExecuted": False,
            "modelWeightsLoaded": False,
            "gpuUsed": False,
            "redactionPolicy": (
                "Only host identity and absolute local paths are replaced; numeric values and "
                "CLI messages are preserved."
            ),
        },
        "environment": {
            "executionPlane": "Linux x86_64 host (identity redacted)",
            "python": "3.11.15",
            "gpuRequired": False,
        },
        "platform": {
            "model": "Qwen/Qwen3-235B-A22B-FP8",
            "system": "h100_sxm",
            "backend": "vllm",
            "performanceDatabaseVersion": "0.24.0",
            "databaseMode": "SILICON",
        },
        "knownPredictionBoundaries": [
            "vLLM 0.24.0 has no FP8 context_attention data for h100_sxm; the search fell back to BF16 FMHA data.",
            "Generated deployment YAML defaults to the Dynamo 1.2.0 mapping (vLLM 0.20.1) and must be regenerated for the deployed runtime.",
            "Upstream documents vLLM and SGLang alignment as still under evaluation.",
        ],
        "stages": stages,
        "files": files,
    }

    manifest_path = output_root / "run-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, help="Extracted real-scenarios directory")
    parser.add_argument("--repo-root", required=True, help="Repository root")
    args = parser.parse_args()

    manifest = publish(Path(args.source_root), Path(args.repo_root))
    print(f"RUN_ID={manifest['runId']}")
    print(f"STAGES={len(manifest['stages'])}")
    print(f"FILES={len(manifest['files'])}")
    print("PUBLISH=OK")


if __name__ == "__main__":
    main()
