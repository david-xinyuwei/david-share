from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


AI_CONFIGURATOR_COMMIT = "614b9c8c8725332533616786e2eb049df48935f0"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_path(root: Path, relative: str) -> Path:
    path = root / Path(relative)
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def sanitize_log(data: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    text = data.decode("utf-8").replace("\r\n", "\n")
    rules = (
        (
            "execution-plane",
            re.compile(r"(?m)^EXECUTION_PLANE=.+$"),
            "EXECUTION_PLANE=LINUX_X86_64",
        ),
        (
            "python-environment-path",
            re.compile(r"/root/miniconda3/envs/[^/\s\"']+"),
            "<python-env>",
        ),
        (
            "remote-workspace-path",
            re.compile(r"/root/remote-workspaces/[^\s\"']+?/(?=artifacts/)"),
            "<workspace>/",
        ),
        (
            "analysis-root-path",
            re.compile(r"/root/aic-analysis/qwen3-235b-fp8-h100-vllm/"),
            "<run-root>/",
        ),
        (
            "host-name",
            re.compile(r"\blinuxworkvm1\b", re.IGNORECASE),
            "linux-x86-64-host",
        ),
    )
    applied: list[dict[str, Any]] = []
    for rule_id, pattern, replacement in rules:
        text, count = pattern.subn(replacement, text)
        if count:
            applied.append({"id": rule_id, "count": count})
    return text.encode("utf-8"), applied


def file_entry(
    source_root: Path,
    output_root: Path,
    source: str,
    destination: str,
    *,
    redact: bool = False,
) -> dict[str, Any]:
    source_bytes = source_path(source_root, source).read_bytes()
    if redact:
        published_bytes, redactions = sanitize_log(source_bytes)
    else:
        published_bytes, redactions = source_bytes, []
    target = output_root / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(published_bytes)
    return {
        "path": destination.replace("\\", "/"),
        "bytes": len(published_bytes),
        "sha256": sha256(published_bytes),
        "sourceArtifact": source.replace("\\", "/"),
        "sourceBytes": len(source_bytes),
        "sourceSha256": sha256(source_bytes),
        "redactions": redactions,
    }


def qwen32_spec() -> dict[str, Any]:
    artifact = (
        "artifacts/canary-50rps-retry1/Qwen/"
        "Qwen3-32B-FP8_h200_sxm_trtllm_isl4000_osl1000_ttft2000_tpot30_47143"
    )
    recommend = [
        "aiconfigurator",
        "cli",
        "recommend",
        "--model-path",
        "Qwen/Qwen3-32B-FP8",
        "--system",
        "h200_sxm",
        "--backend",
        "trtllm",
        "--target-request-rate",
        "50",
        "--isl",
        "4000",
        "--osl",
        "1000",
        "--ttft",
        "2000",
        "--tpot",
        "30",
        "--database-mode",
        "SILICON",
        "--strict-sla",
        "--top-n",
        "5",
        "--save-dir",
        "<run-output>",
        "--no-color",
    ]
    return {
        "runId": "qwen3-32b-h200-trtllm-50rps",
        "summary": "Complete support, failed recommendation, repair, and successful recommendation lineage.",
        "environment": {
            "executionPlane": "Linux x86_64 host (identity redacted)",
            "os": "Ubuntu 24.04",
            "glibc": "2.39",
            "python": "3.11.15",
            "gpuRequired": False,
        },
        "workload": {
            "model": "Qwen/Qwen3-32B-FP8",
            "system": "h200_sxm",
            "backend": "trtllm",
            "databaseMode": "SILICON",
            "targetRequestRate": 50,
            "isl": 4000,
            "osl": 1000,
            "ttftLimitMs": 2000,
            "tpotLimitMs": 30,
        },
        "stages": [
            {
                "id": "support",
                "status": "PASS",
                "exitCode": 0,
                "startUtc": "2026-08-31T02:12:59Z",
                "endUtc": "2026-08-31T02:13:00Z",
                "command": [
                    "aiconfigurator",
                    "cli",
                    "support",
                    "--model-path",
                    "Qwen/Qwen3-32B-FP8",
                    "--system",
                    "h200_sxm",
                    "--backend",
                    "trtllm",
                    "--no-color",
                ],
                "log": "logs/01-support.log",
            },
            {
                "id": "recommend-initial",
                "status": "FAIL",
                "classification": "ENVIRONMENT",
                "exitCode": 1,
                "startUtc": "2026-08-31T02:13:24Z",
                "endUtc": "2026-08-31T02:13:38Z",
                "command": recommend,
                "failure": "plotext 6.0.0 removed plot_size, which AIConfigurator 0.11.0 calls while rendering the report.",
                "log": "logs/02-recommend-plotext6-failure.log",
            },
            {
                "id": "dependency-repair",
                "status": "PASS",
                "action": "Pin plotext==5.3.2; do not change the recommendation inputs.",
            },
            {
                "id": "recommend-retry",
                "status": "PASS",
                "exitCode": 0,
                "startUtc": "2026-08-31T02:15:08Z",
                "endUtc": "2026-08-31T02:15:23Z",
                "command": recommend,
                "log": "logs/03-recommend-success.log",
            },
        ],
        "files": [
            ("logs/01-support.log", "logs/01-support.log", True),
            ("logs/02-recommend-50rps.log", "logs/02-recommend-plotext6-failure.log", True),
            ("logs/03-recommend-50rps-retry1.log", "logs/03-recommend-success.log", True),
            (f"{artifact}/pareto_frontier.png", "results/pareto_frontier.png", False),
            (f"{artifact}/agg/best_config_topn.csv", "results/agg/best_config_topn.csv", False),
            (f"{artifact}/agg/exp_config.yaml", "results/agg/exp_config.yaml", False),
            (f"{artifact}/agg/pareto.csv", "results/agg/pareto.csv", False),
            (f"{artifact}/agg/top1/agg_config.yaml", "results/agg/top1/agg_config.yaml", False),
            (f"{artifact}/agg/top1/generator_config.yaml", "results/agg/top1/generator_config.yaml", False),
            (f"{artifact}/disagg/best_config_topn.csv", "results/disagg/best_config_topn.csv", False),
            (f"{artifact}/disagg/exp_config.yaml", "results/disagg/exp_config.yaml", False),
            (f"{artifact}/disagg/pareto.csv", "results/disagg/pareto.csv", False),
            (f"{artifact}/disagg/top1/prefill_config.yaml", "results/disagg/top1/prefill_config.yaml", False),
            (f"{artifact}/disagg/top1/decode_config.yaml", "results/disagg/top1/decode_config.yaml", False),
            (f"{artifact}/disagg/top1/generator_config.yaml", "results/disagg/top1/generator_config.yaml", False),
        ],
    }


def qwen235_spec() -> dict[str, Any]:
    worker = (
        "qwen3-235b-fp8-h100-vllm/4g/results/Qwen/"
        "Qwen3-235B-A22B-FP8_h100_sxm_vllm_isl4000_osl1000_ttft2000_tpot30_854075/agg"
    )
    capacity = (
        "qwen3-235b-fp8-h100-vllm/50rps/results/Qwen/"
        "Qwen3-235B-A22B-FP8_h100_sxm_vllm_isl4000_osl1000_ttft2000_tpot30_40859"
    )
    base = [
        "--model-path",
        "Qwen/Qwen3-235B-A22B-FP8",
        "--system",
        "h100_sxm",
        "--backend",
        "vllm",
        "--isl",
        "4000",
        "--osl",
        "1000",
        "--prefix",
        "0",
        "--ttft",
        "2000",
        "--tpot",
        "30",
        "--database-mode",
        "SILICON",
        "--strict-sla",
        "--top-n",
        "3",
        "--save-dir",
        "<run-output>",
        "--no-color",
    ]
    return {
        "runId": "qwen3-235b-h100-vllm-50rps",
        "summary": "Supplemental feasibility, minimum-worker, capacity, and CPU-footprint evidence.",
        "environment": {
            "executionPlane": "Linux x86_64 host (identity redacted)",
            "python": "3.11.15",
            "gpuRequired": False,
        },
        "workload": {
            "model": "Qwen/Qwen3-235B-A22B-FP8",
            "system": "h100_sxm",
            "backend": "vllm",
            "performanceDatabaseVersion": "0.24.0",
            "databaseMode": "SILICON",
            "targetRequestRate": 50,
            "isl": 4000,
            "osl": 1000,
            "ttftLimitMs": 2000,
            "tpotLimitMs": 30,
        },
        "stages": [
            {
                "id": "two-gpu-feasibility",
                "status": "FAIL",
                "expectedForBoundaryStudy": True,
                "exitCode": 1,
                "command": ["aiconfigurator", "cli", "default", "--total-gpus", "2", *base],
                "log": "logs/01-two-gpu-infeasible.log",
            },
            {
                "id": "four-gpu-worker",
                "status": "PASS",
                "exitCode": 0,
                "command": ["aiconfigurator", "cli", "default", "--total-gpus", "4", *base],
                "log": "logs/02-four-gpu-worker.log",
            },
            {
                "id": "capacity-50rps",
                "status": "PASS",
                "exitCode": 0,
                "command": [
                    "aiconfigurator",
                    "cli",
                    "recommend",
                    "--target-request-rate",
                    "50",
                    *base,
                ],
                "log": "logs/03-capacity-50rps.log",
            },
            {
                "id": "cpu-footprint",
                "status": "PASS",
                "exitCode": 0,
                "measurement": "GNU time -v around the four-GPU CPU-side search",
                "log": "logs/04-cpu-memory-profile.log",
            },
        ],
        "files": [
            ("qwen3-235b-fp8-h100-vllm/2g-run.log", "logs/01-two-gpu-infeasible.log", True),
            ("qwen3-235b-fp8-h100-vllm/4g/run.log", "logs/02-four-gpu-worker.log", True),
            ("qwen3-235b-fp8-h100-vllm/50rps/run.log", "logs/03-capacity-50rps.log", True),
            ("qwen3-235b-fp8-h100-vllm/cpu-memory-profile-4g-run.log", "logs/04-cpu-memory-profile.log", True),
            (f"{worker}/best_config_topn.csv", "results/worker-4g/agg/best_config_topn.csv", False),
            (f"{worker}/exp_config.yaml", "results/worker-4g/agg/exp_config.yaml", False),
            (f"{worker}/pareto.csv", "results/worker-4g/agg/pareto.csv", False),
            (f"{worker}/top1/generator_config.yaml", "results/worker-4g/agg/top1/generator_config.yaml", False),
            (f"{capacity}/agg/best_config_topn.csv", "results/agg/best_config_topn.csv", False),
            (f"{capacity}/agg/exp_config.yaml", "results/agg/exp_config.yaml", False),
            (f"{capacity}/agg/pareto.csv", "results/agg/pareto.csv", False),
            (f"{capacity}/agg/top1/generator_config.yaml", "results/agg/top1/generator_config.yaml", False),
            (f"{capacity}/disagg/best_config_topn.csv", "results/disagg/best_config_topn.csv", False),
            (f"{capacity}/disagg/exp_config.yaml", "results/disagg/exp_config.yaml", False),
            (f"{capacity}/disagg/pareto.csv", "results/disagg/pareto.csv", False),
            (f"{capacity}/disagg/top1/generator_config.yaml", "results/disagg/top1/generator_config.yaml", False),
        ],
    }


def publish(source_root: Path, output_root: Path, spec: dict[str, Any]) -> None:
    run_root = output_root / spec["runId"]
    entries = [
        file_entry(source_root, run_root, source, destination, redact=redact)
        for source, destination, redact in spec.pop("files")
    ]
    manifest = {
        "schemaVersion": "1.0",
        "evidenceClass": "CPU_OFFLINE_PREDICTION",
        "tool": {
            "name": "NVIDIA AIConfigurator",
            "version": "0.11.0",
            "sourceCommit": AI_CONFIGURATOR_COMMIT,
        },
        "publicationBoundary": {
            "physicalGpuBenchmark": "NOT_RUN",
            "productionCapacity": "NOT_ESTABLISHED",
            "redactionPolicy": "Only host identity and absolute local paths are replaced; numeric values and CLI messages are preserved.",
        },
        **spec,
        "files": entries,
    }
    manifest_path = run_root / "run-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"PUBLISHED {manifest['runId']} files={len(entries)} manifest={manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish curated, sanitized AIConfigurator run evidence.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evidence" / "runs",
    )
    args = parser.parse_args()
    for spec in (qwen32_spec(), qwen235_spec()):
        publish(args.source_root, args.output_root, spec)


if __name__ == "__main__":
    main()