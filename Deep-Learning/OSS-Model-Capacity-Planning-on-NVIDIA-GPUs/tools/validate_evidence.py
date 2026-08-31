from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evidence" / "runs"
EXPECTED_RUNS = {
    "qwen3-32b-h200-trtllm-50rps",
    "qwen3-235b-h100-vllm-50rps",
}
FORBIDDEN_PUBLIC_PATTERNS = {
    "private-linux-root": re.compile(r"/root/"),
    "private-windows-profile": re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    "private-execution-plane": re.compile(r"(?m)^EXECUTION_PLANE=(?!LINUX_X86_64$).+$"),
    "private-workspace-root": re.compile(r"/remote-workspaces/", re.IGNORECASE),
}
REQUIRED_LOG_LINKS = {
    "evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/01-support.log",
    "evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/02-recommend-plotext6-failure.log",
    "evidence/runs/qwen3-32b-h200-trtllm-50rps/logs/03-recommend-success.log",
    "evidence/runs/qwen3-235b-h100-vllm-50rps/logs/01-two-gpu-infeasible.log",
    "evidence/runs/qwen3-235b-h100-vllm-50rps/logs/02-four-gpu-worker.log",
    "evidence/runs/qwen3-235b-h100-vllm-50rps/logs/03-capacity-50rps.log",
    "evidence/runs/qwen3-235b-h100-vllm-50rps/logs/04-cpu-memory-profile.log",
}
RETIRED_CHINESE_PHRASES = {
    "OSS 模型",
    "open-weight 模型",
    "平台合同",
    "模型合同",
    "Workload 合同",
    "主要 sizing engine",
    "开源结合",
    "拟议结合层",
    "独立 adapter",
    "benchmark calibration service",
    "CLI thin runner",
    "workload point",
    "cache profile",
    "Support matrix 按版本",
    "Known Issues",
    "Search、generator 与 runtime",
    "CPU-offline predictions",
    "容量规划 runner",
    "Workload buckets",
    "backend matrix",
    "policy candidates",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(manifest["schemaVersion"] == "1.0", f"Unsupported manifest schema: {path}")
    require(manifest["evidenceClass"] == "CPU_OFFLINE_PREDICTION", f"Wrong evidence class: {path}")
    require(manifest["tool"]["version"] == "0.11.0", f"Wrong tool version: {path}")
    require(manifest["publicationBoundary"]["physicalGpuBenchmark"] == "NOT_RUN", f"GPU boundary missing: {path}")
    return manifest


def validate_manifest_files(run_root: Path, manifest: dict[str, Any]) -> None:
    paths: set[str] = set()
    for entry in manifest["files"]:
        relative = entry["path"]
        require(relative not in paths, f"Duplicate manifest path: {relative}")
        paths.add(relative)
        target = (run_root / relative).resolve()
        require(target.is_relative_to(run_root.resolve()), f"Evidence path escapes run root: {relative}")
        require(target.is_file(), f"Missing evidence file: {relative}")
        require(target.stat().st_size == entry["bytes"], f"Byte-count mismatch: {relative}")
        require(sha256(target) == entry["sha256"], f"SHA-256 mismatch: {relative}")
        require(len(entry["sourceSha256"]) == 64, f"Source SHA-256 missing: {relative}")


def validate_log_exit(run_root: Path, relative: str, expected: int) -> None:
    text = (run_root / relative).read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^EXIT_CODE=(\d+)$", text)
    require(matches == [str(expected)], f"Unexpected EXIT_CODE markers in {relative}: {matches}")


def validate_qwen32(run_root: Path, manifest: dict[str, Any]) -> None:
    require([stage["status"] for stage in manifest["stages"]] == ["PASS", "FAIL", "PASS", "PASS"], "Qwen3-32B stage sequence drift")
    require(manifest["stages"][1]["classification"] == "ENVIRONMENT", "Initial failure classification drift")
    validate_log_exit(run_root, "logs/01-support.log", 0)
    validate_log_exit(run_root, "logs/02-recommend-plotext6-failure.log", 1)
    validate_log_exit(run_root, "logs/03-recommend-success.log", 0)
    failure = (run_root / "logs/02-recommend-plotext6-failure.log").read_text(encoding="utf-8")
    require("AttributeError: module 'plotext' has no attribute 'plot_size'" in failure, "Expected plotext failure missing")
    success = (run_root / "logs/03-recommend-success.log").read_text(encoding="utf-8")
    require("agg GPUs needed: 32 (replicas: 32)" in success, "32-GPU result missing from log")
    require("disagg GPUs needed: 34 (replicas: 17)" in success, "34-GPU result missing from log")
    agg = first_row(run_root / "results" / "agg" / "best_config_topn.csv")
    disagg = first_row(run_root / "results" / "disagg" / "best_config_topn.csv")
    require(int(agg["replicas_needed"]) * int(agg["num_total_gpus"]) == 32, "Qwen3-32B Aggregated arithmetic failed")
    require(int(disagg["replicas_needed"]) * int(disagg["num_total_gpus"]) == 34, "Qwen3-32B Disaggregated arithmetic failed")
    for row in (agg, disagg):
        require(float(row["request_rate"]) * int(row["replicas_needed"]) >= 50, "Qwen3-32B request-rate target failed")
        require(float(row["ttft"]) <= 2000, "Qwen3-32B TTFT target failed")
        require(float(row["tpot"]) <= 30, "Qwen3-32B TPOT target failed")


def validate_qwen235(run_root: Path, manifest: dict[str, Any]) -> None:
    require([stage["status"] for stage in manifest["stages"]] == ["FAIL", "PASS", "PASS", "PASS"], "Qwen3-235B stage sequence drift")
    require(manifest["stages"][0]["expectedForBoundaryStudy"] is True, "Two-GPU boundary flag missing")
    validate_log_exit(run_root, "logs/01-two-gpu-infeasible.log", 1)
    validate_log_exit(run_root, "logs/02-four-gpu-worker.log", 0)
    validate_log_exit(run_root, "logs/03-capacity-50rps.log", 0)
    validate_log_exit(run_root, "logs/04-cpu-memory-profile.log", 0)
    two_gpu = (run_root / "logs/01-two-gpu-infeasible.log").read_text(encoding="utf-8")
    require("model does not fit in GPU memory" in two_gpu, "Two-GPU infeasibility evidence missing")
    worker = first_row(run_root / "results" / "worker-4g" / "agg" / "best_config_topn.csv")
    require(int(worker["num_total_gpus"]) == 4, "Four-GPU worker size drift")
    require(worker["parallel"] == "tp4pp1dp1etp4ep1", "Four-GPU worker topology drift")
    agg = first_row(run_root / "results" / "agg" / "best_config_topn.csv")
    disagg = first_row(run_root / "results" / "disagg" / "best_config_topn.csv")
    require(int(agg["replicas_needed"]) * int(agg["num_total_gpus"]) == 428, "Qwen3-235B Aggregated arithmetic failed")
    require(int(disagg["replicas_needed"]) * int(disagg["num_total_gpus"]) == 920, "Qwen3-235B Disaggregated arithmetic failed")
    capacity_log = (run_root / "logs/03-capacity-50rps.log").read_text(encoding="utf-8")
    require("agg GPUs needed: 428 (replicas: 107)" in capacity_log, "428-GPU log result missing")
    require("disagg GPUs needed: 920 (replicas: 115)" in capacity_log, "920-GPU log result missing")
    require("Perf-DB version: 0.24.0" in capacity_log, "vLLM search version warning missing")
    require("Defaulting to backend version from dynamo 1.2.0: (vllm)0.20.1" in capacity_log, "vLLM generated-config version warning missing")
    profile = (run_root / "logs/04-cpu-memory-profile.log").read_text(encoding="utf-8")
    require("Maximum resident set size (kbytes): 496100" in profile, "CPU memory evidence missing")


def validate_public_boundary() -> None:
    suffixes = {".json", ".log", ".csv", ".yaml", ".yml", ".md", ".txt"}
    for path in RUNS.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        for rule_id, pattern in FORBIDDEN_PUBLIC_PATTERNS.items():
            require(not pattern.search(text), f"{rule_id} found in {path.relative_to(ROOT)}")


def command_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:bash|powershell)\n(.*?)\n```", text.replace("\r\n", "\n"), re.DOTALL)


def validate_readme_links(path: Path, text: str) -> None:
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#")):
            continue
        resolved = (path.parent / target).resolve()
        require(resolved.is_relative_to(ROOT.parents[1].resolve()), f"README link escapes repository: {target}")
        require(resolved.exists(), f"Broken README link in {path.name}: {target}")


def validate_readmes() -> None:
    english_path = ROOT / "README.md"
    chinese_path = ROOT / "README-CN.md"
    english = english_path.read_text(encoding="utf-8")
    chinese = chinese_path.read_text(encoding="utf-8")
    require("## 5. Reproduce the complete CPU-offline run" in english, "Detailed English walkthrough missing")
    require("## 5. 完整复现一次 CPU 离线预测" in chinese, "Detailed Chinese walkthrough missing")
    for token in (
        "requirements-repro.txt",
        "aiconfigurator cli support",
        "aiconfigurator cli recommend",
        "AttributeError: module 'plotext' has no attribute 'plot_size'",
        "agg GPUs needed: 32 (replicas: 32)",
        "disagg GPUs needed: 34 (replicas: 17)",
        "README_VALIDATION=PASS LOG_LINKS=7 COMMAND_BLOCKS=9",
        "EVIDENCE_VALIDATION=PASS RUNS=2 PUBLIC_BOUNDARY=PASS",
    ):
        require(token in english, f"English walkthrough token missing: {token}")
        require(token in chinese, f"Chinese walkthrough token missing: {token}")
    for link in REQUIRED_LOG_LINKS:
        require(link in english, f"English full-log link missing: {link}")
        require(link in chinese, f"Chinese full-log link missing: {link}")
    require(command_blocks(english) == command_blocks(chinese), "Bilingual Bash/PowerShell command blocks drifted")
    for phrase in RETIRED_CHINESE_PHRASES:
        require(phrase not in chinese, f"Retired Chinese phrase found: {phrase}")
    validate_readme_links(english_path, english)
    validate_readme_links(chinese_path, chinese)
    print(f"README_VALIDATION=PASS LOG_LINKS={len(REQUIRED_LOG_LINKS)} COMMAND_BLOCKS={len(command_blocks(english))}")


def main() -> None:
    manifests = sorted(RUNS.glob("*/run-manifest.json"))
    require({path.parent.name for path in manifests} == EXPECTED_RUNS, "Run-manifest set mismatch")
    for path in manifests:
        manifest = load_manifest(path)
        run_root = path.parent
        require(manifest["runId"] == run_root.name, f"Run ID/path mismatch: {path}")
        validate_manifest_files(run_root, manifest)
        if manifest["runId"] == "qwen3-32b-h200-trtllm-50rps":
            validate_qwen32(run_root, manifest)
        else:
            validate_qwen235(run_root, manifest)
        print(f"RUN {manifest['runId']} PASS files={len(manifest['files'])}")
    validate_public_boundary()
    validate_readmes()
    print("EVIDENCE_VALIDATION=PASS RUNS=2 PUBLIC_BOUNDARY=PASS")


if __name__ == "__main__":
    main()