#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "README-CN.md")

BILINGUAL_HEADING_PAIRS = (
    ("# MiMo-V2.5-Pro on AMD MI300X — Benchmark Report", "# MiMo-V2.5-Pro 在 AMD MI300X 上的 Benchmark 报告"),
    ("## Executive Summary", "## 执行摘要"),
    ("### Relative Status at a Glance", "### 核心指标对比"),
    ("### What Happens as Input Length Grows", "### 输入长度增加时发生什么"),
    ("## Architecture", "## 架构"),
    ("## Why PD Disaggregation Has Independent Batch Sizes and Hyperparameters", "## 为什么 PD 分离后 Prefill 与 Decode 可以拥有独立 BS 和超参"),
    ("### Reading the Xiaomi Community Protocol: Dynamic Prefill Batching, Targeted Decode Occupancy", "### 如何解读小米社区版协议：Prefill 动态组批，Decode 按目标工况验收"),
    ("### One Request, Three Batch Concepts", "### 一个请求涉及的三类 Batch 概念"),
    ("### What PD Separates, and What Must Still Match", "### PD 可以分别调优什么，哪些契约必须保持一致"),
    ("### Capacity Connects ISL to the Actual Decode Batch", "### ISL 如何约束实际 Decode Batch"),
    ("### Measured 128K/192K Subset on the 7/13-Derived Runtime", "### 基于7/13环境的128K/192K实测子集"),
    ("#### Prefill Selected Points", "#### Prefill 选定测点"),
    ("#### Decode Fixed-BS4 Selected Points", "#### Decode 固定 BS4 选定测点"),
    ("### How to Extend the Length Study Without Mixing Variables", "### 后续如何只改变输入长度而不混入其他变量"),
    ("## Headline Results — Input and Output Views", "## 核心结果：输入与输出视图"),
    ("### Input Side — 1P1D Prefill", "### 输入侧：1P1D Prefill"),
    ("### Output Side — MI300X 1P1D Decode, 8K Input / 1K Output", "### 输出侧：MI300X 1P1D Decode，8K 输入 / 1K 输出"),
    ("#### Customer H200 8K Decode Reference", "#### 客户 H200 8K Decode 参考"),
    ("### Two-Node DP=2 Prefill — Peak Aggregate Throughput", "### 双节点 DP=2 Prefill：峰值聚合吞吐"),
    ("### Result Scope", "### 结果口径"),
    ("### H200 Reference Provenance", "### H200 参考数据来源"),
    ("## Microsoft Scalability Extension", "## 微软扩展性测试"),
    ("### Test Matrix", "### 测试矩阵"),
    ("### Decode Scalability — 8K Input / 1K Output", "### Decode 扩展性：8K 输入 / 1K 输出"),
    ("### Core Decode Fresh-Service Repeatability", "### Decode 核心测点的 Fresh-Service（全新服务）复测"),
    ("### Long-Context Results — Final Runtime Image", "### 长上下文结果：最终运行环境镜像"),
    ("#### Metric Contract", "#### 指标口径"),
    ("#### 1. Input Side — 64K Prefill", "#### 1. 输入侧：64K Prefill"),
    ("#### 2. Output Side — MI300X 64K Input / 1K Output", "#### 2. 输出侧：MI300X 64K 输入 / 1K 输出"),
    ("#### Customer H200 Output-Side Reference — Not Row-Aligned", "#### H200 输出侧参考：未与 MI300X 逐行对齐"),
    ("#### Why the PD-Serving Points Carry No Output-Side Ratio", "#### 为什么 PD serving 测点不计算输出侧比率"),
    ("#### Exact Fixed-Batch Decode — 64K Input / 1K Server-Accounted Output, BS16 (2026-07-18)", "#### Exact Fixed-Batch Decode（精确固定批次测试）— 64K 输入 / 服务端计数的 1K 输出，BS16（2026-07-18）"),
    ("#### 3. Customer Requirement Assessment", "#### 3. 客户问题评估"),
    ("#### Requested 255K Capability Point", "#### 请求 255K 的能力测点"),
    ("### 1P1D Prefill Scalability", "### 1P1D Prefill 扩展性"),
    ("### Two-Node DP=2 Prefill Scalability", "### 双节点 DP=2 Prefill 扩展性"),
    ("### 256K Methodology", "### 256K 测试口径"),
    ("### Machine-Readable Evidence", "### 机器可读证据"),
    ("## Hardware & Software Stack", "## 硬件与软件栈"),
    ("### Compute — Two-Node Azure MI300X Cluster", "### 计算：双节点 Azure MI300X 集群"),
    ("### Software Stack", "### 软件栈"),
    ("### Model", "### 模型"),
    ("## Running on Azure and Reproducing Final Results", "## 在 Azure 上运行并复现结果"),
    ("### Prerequisites", "### 前置条件"),
    ("### Pull and Start the Runtime — Both Nodes", "### 在两个节点拉取并启动 Runtime"),
    ("### 1P1D", "### 1P1D"),
    ("### DP=2 Two-Node Prefill", "### 双节点 Prefill（DP=2）"),
    ("### Cleanup", "### 清理"),
    ("## Required Runtime Settings", "## 必要的运行设置"),
    ("## References", "## 参考资料"),
)

CHINESE_TERM_INTRODUCTIONS = (
    "Prefill（预填充阶段）",
    "Decode（解码阶段）",
    "TTFT（首 Token 时延）",
    "TPOT（单 Token 生成时延）",
    "Batch Size（批大小）",
    "scheduler（调度器）",
    "fixed-acceptance performance benchmark（固定接受率性能测试）",
    "Retokenized（重新分词）",
    "expert routing（专家路由）",
    "manifest（哈希清单）",
    "pinned checkout（固定版本检出）",
    "per-point distribution evidence（逐点请求分布证据）",
    "RDMA memory registration（RDMA 内存注册）",
)

CHINESE_TRANSLATIONESE_FORBIDDEN = (
    "一眼看清相对参考状态",
    "客户端并发度",
    "工作簿局部方向性算术比值",
    "Column J",
    "deployment scope",
    "same-runtime",
    "selected points",
    "accepted runs",
    "accepted reproduction runs",
    "active Decode requests",
    "allocator granularity",
    "runtime reserve",
    "raw upper bound",
    "scheduler generation吞吐",
    "fresh DP=2 services",
    "distribution 证据",
    "host 权限",
    "Benchmark dataset 位于",
    "parent monorepo",
    "fresh-clone validator",
    "benchmark subtree",
    "effective value",
    "new sequences数量",
    "requests数量",
    "new sequences和",
    "input-token chunks组成",
    "requests组成",
    "不会因处理阶段改变，但会依次进入两个独立的 scheduler",
    "二者不存在一一映射",
    "只有在显式配置相应 limit",
    "只有显式配置了相应的 limit",
    "可以独立调优，并不意味着两侧契约可以不兼容",
    "提供已经测试的 SGLang/AITER 运行栈",
    "方向性对比中仅此项更低",
    "面对客户时，可以分四步说明",
    "重新标为 BS",
    "只代表历史版本",
    "不属于相互独立的重复实验",
)


def markdown_sections(text: str) -> list[tuple[str, str]]:
    masked = re.sub(
        r"```.*?```",
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
        flags=re.DOTALL,
    )
    matches = list(re.finditer(r"^#{1,6} .+$", masked, re.MULTILINE))
    return [
        (
            text[match.start() : match.end()],
            text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(text)],
        )
        for index, match in enumerate(matches)
    ]


def markdown_table_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def markdown_number_tokens(text: str) -> list[str]:
    return re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?(?:[A-Za-z]+|[%×])?", text)


def markdown_noncomment_code(text: str) -> list[tuple[str, list[str]]]:
    blocks = re.findall(r"```([^\n]*)\n(.*?)```", text, re.DOTALL)
    return [
        (
            language,
            [line.rstrip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")],
        )
        for language, body in blocks
    ]


def normalized_readme_links(text: str) -> list[str]:
    return [
        "<LANGUAGE_SWITCH>" if target in {"README.md", "README-CN.md"} else target
        for target in re.findall(r"\]\(([^)]+)\)", text)
    ]


def markdown_prose(text: str) -> str:
    without_fences = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    return re.sub(r"(?<!`)`[^`\n]+`(?!`)", " ", without_fences)


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert rows and all(None not in row for row in rows), f"Invalid TSV: {path}"
    return rows


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_hash_manifest(directory: Path) -> None:
    manifest = directory / "SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, name = line.split(maxsplit=1)
        path = directory / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"SHA mismatch: {path}"


def check_readmes() -> None:
    shapes = []
    readme_texts = []
    for path in READMES:
        text = path.read_text(encoding="utf-8")
        readme_texts.append(text)
        assert text.count("```") % 2 == 0, f"Unclosed code fence: {path}"
        headings = markdown_sections(text)
        tables = re.findall(r"^\|", text, re.MULTILINE)
        bash_blocks = re.findall(r"```bash\n(.*?)```", text, re.DOTALL)
        shapes.append((len(headings), len(tables), len(bash_blocks)))
        for index, block in enumerate(bash_blocks, 1):
            result = subprocess.run(
                ["bash", "-n"],
                input="set -Eeuo pipefail\n" + block,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, f"{path.name} bash block {index}: {result.stderr}"
        targets = re.findall(r"\]\(([^)#]+)(?:#[^)]+)?\)", text)
        targets += re.findall(r'<img\s+src="([^"]+)"', text)
        for target in targets:
            if "://" not in target:
                assert (ROOT / target).exists(), f"Missing local link in {path.name}: {target}"
        for required in (
            "data/validation/container-image.json",
            "data/validation/h200-reference.json",
            "data/validation/decode-service-log-audit-8k.json",
            "not a strict apples-to-apples" if path.name == "README.md" else "不构成严格同条件的硬件 benchmark",
            "Relative Status at a Glance" if path.name == "README.md" else "核心指标对比",
            "Only directionally lower metric: 6.6% lower" if path.name == "README.md" else "| 低 6.6% |",
            "fixed-acceptance performance benchmark" if path.name == "README.md" else "fixed acceptance（固定接受率）性能测试",
            "server-accounted 1K output" if path.name == "README.md" else "服务端计数的 1K 输出",
            "worksheet-local directional arithmetic ratio" if path.name == "README.md" else "该结果的相对值为 **70.0%**",
            "does not validate output quality" if path.name == "README.md" else "不验证输出质量",
            "retokenized generated-text tokens",
            "analyze_exact64_evidence.py",
            "does not independently establish the provenance or completeness" if path.name == "README.md" else "不能单独证明私有完整日志的来源与完整性",
            "no tested Prefill-throughput row exceeds" if path.name == "README.md" else "已实测的 Prefill 吞吐均未超过",
            "not a strict hardware ranking" if path.name == "README.md" else "不能作为严格的硬件排名",
            "client c16, observed batch 15 / 16" if path.name == "README.md" else "PD c16；实测 BS15–16",
            "must not be treated as a controlled 8K→64K TPOT curve" if path.name == "README.md" else "不能据此绘制受控的 8K→64K TPOT 曲线",
            "headline_exact.same_image_exact_no_ck",
            "headline_exact.points",
            "--password-stdin",
            "validate_server_info.py",
            "validate_service_logs.py",
            "validate_exact_256k.py",
            "write_distribution.py",
            "CodeQL passed" if path.name == "README.md" else "CodeQL 已通过",
            "without a matching `.gitmodules` URL" if path.name == "README.md" else "缺少对应的 `.gitmodules` URL",
        ):
            assert required in text, f"Missing README requirement in {path.name}: {required}"
    assert shapes[0] == shapes[1], f"Bilingual README structure mismatch: {shapes}"

    english_sections = markdown_sections(readme_texts[0])
    chinese_sections = markdown_sections(readme_texts[1])
    actual_heading_pairs = tuple(zip(
        (heading for heading, _ in english_sections),
        (heading for heading, _ in chinese_sections),
    ))
    assert actual_heading_pairs == BILINGUAL_HEADING_PAIRS, "Bilingual heading map or ordering changed"

    for index, ((english_heading, english_body), (chinese_heading, chinese_body)) in enumerate(
        zip(english_sections, chinese_sections),
        1,
    ):
        label = f"section {index}: {english_heading} / {chinese_heading}"
        english_links = normalized_readme_links(english_body)
        chinese_links = normalized_readme_links(chinese_body)
        assert english_links == chinese_links, f"Bilingual link mismatch in {label}"
        assert markdown_noncomment_code(english_body) == markdown_noncomment_code(chinese_body), (
            f"Bilingual executable-code mismatch in {label}"
        )

        english_tables = markdown_table_blocks(english_body)
        chinese_tables = markdown_table_blocks(chinese_body)
        assert len(english_tables) == len(chinese_tables), f"Bilingual table-count mismatch in {label}"
        for table_index, (english_table, chinese_table) in enumerate(zip(english_tables, chinese_tables), 1):
            english_rows = english_table.splitlines()
            chinese_rows = chinese_table.splitlines()
            english_shape = (len(english_rows), [row.count("|") for row in english_rows])
            chinese_shape = (len(chinese_rows), [row.count("|") for row in chinese_rows])
            assert english_shape == chinese_shape, f"Bilingual table-shape mismatch in {label}, table {table_index}"
            for row_index, (english_row, chinese_row) in enumerate(zip(english_rows, chinese_rows), 1):
                english_cells = english_row.strip("|").split("|")
                chinese_cells = chinese_row.strip("|").split("|")
                for cell_index, (english_cell, chinese_cell) in enumerate(zip(english_cells, chinese_cells), 1):
                    english_cell_numbers = markdown_number_tokens(english_cell)
                    chinese_cell_numbers = markdown_number_tokens(chinese_cell)
                    english_cell_counter = Counter(english_cell_numbers)
                    chinese_cell_counter = Counter(chinese_cell_numbers)
                    assert english_cell_counter == chinese_cell_counter, (
                        f"Bilingual table-number mismatch in {label}, table {table_index}, "
                        f"row {row_index}, cell {cell_index}: "
                        f"English-only={english_cell_counter - chinese_cell_counter}, "
                        f"Chinese-only={chinese_cell_counter - english_cell_counter}"
                    )

        english_inline_code = re.findall(r"(?<!`)`([^`\n]+)`(?!`)", english_body)
        chinese_inline_code = re.findall(r"(?<!`)`([^`\n]+)`(?!`)", chinese_body)
        assert Counter(english_inline_code) == Counter(chinese_inline_code), (
            f"Bilingual inline-code mismatch in {label}: {english_inline_code} != {chinese_inline_code}"
        )
        english_numbers = markdown_number_tokens(english_body)
        chinese_numbers = markdown_number_tokens(chinese_body)
        english_number_counter = Counter(english_numbers)
        chinese_number_counter = Counter(chinese_numbers)
        assert english_number_counter == chinese_number_counter, (
            f"Bilingual numeric-fact mismatch in {label}: "
            f"English-only={english_number_counter - chinese_number_counter}, "
            f"Chinese-only={chinese_number_counter - english_number_counter}"
        )

    chinese_prose = markdown_prose(readme_texts[1])
    for required in CHINESE_TERM_INTRODUCTIONS:
        assert required in chinese_prose, f"Missing Chinese first-use term explanation: {required}"
    for forbidden in CHINESE_TRANSLATIONESE_FORBIDDEN:
        assert forbidden not in chinese_prose, f"Translationese remains in README-CN.md: {forbidden}"


def check_batching_guide() -> None:
    english, chinese = [path.read_text(encoding="utf-8") for path in READMES]
    common_requirements = (
        "images/request_batching_lifecycle.png",
        "images/xiaomi_protocol_batch_planes.png",
        "images/kv_capacity_relationship.png",
        "requirements-diagrams.txt",
        "generate_batching_diagrams.py",
        "chunked-prefill-size",
        "max-prefill-tokens",
        "prefill-max-requests",
        "max-running-requests",
        "kv-cache-dtype=fp8_e4m3",
        "page-size=32",
        "context-length=262151",
        "1{,}442{,}464",
        "1{,}064{,}960",
        "73.8\\%",
        "255K input + 1K output",
        "256K input + 1K output",
        "#new-seq",
        "#new-token",
        "#running-req",
        "BS64",
        "BS96",
    )
    for text in (english, chinese):
        for required in common_requirements:
            assert required in text, f"Missing batching-guide requirement: {required}"

    english_requirements = (
        "Why PD Disaggregation Has Independent Batch Sizes and Hyperparameters",
        "single-node, non-PD",
        "It is not the 1P1D PD c16 record",
        "Single-node non-PD exact long ISL",
        "Prefill request batch",
        "Prefill token batch",
        "actual Decode batch",
        "they may differ",
        "Steady-state `4`, peak `5`",
        "Actual Decode batch `16`, queue `0`",
        "Non-PD capacity experiment",
        "Planning estimates; not measured",
        "is invalid under `context-length=262151`",
        "Reading the Xiaomi Community Protocol: Dynamic Prefill Batching, Targeted Decode Occupancy",
        "c32 is applied pressure, not Prefill BS",
        "There is no one-to-one mapping between the two sides",
        "A full Cartesian product of every Prefill and Decode point is unnecessary",
        "does not claim that the current MI300X path has reached per-DP BS96",
    )
    chinese_requirements = (
        "为什么 PD 分离后 Prefill 与 Decode 可以拥有独立 BS 和超参",
        "单节点非 PD",
        "该测量不属于 1P1D PD c16 测试",
        "单节点、非 PD；64K/1K",
        "Prefill request batch",
        "Prefill token batch",
        "actual Decode batch",
        "彼此独立，可以不同",
        "稳态 `4`、峰值 `5`",
        "实际 Decode batch `16`、queue `0`",
        "非 PD 容量实验",
        "规划估算；尚未实测",
        "超过 `context-length=262151` 的限制",
        "如何解读小米社区版协议：Prefill 动态组批，Decode 按目标工况验收",
        "c32 表示客户端施加的并发压力，不是 Prefill BS",
        "二者之间不存在固定的一一对应关系",
        "没有必要对所有 Prefill 与 Decode 测点做完整笛卡尔积",
        "不表示当前 MI300X 路径已经达到 per-DP BS96",
    )
    for required in english_requirements:
        assert required in english, f"Missing English batching-guide requirement: {required}"
    for required in chinese_requirements:
        assert required in chinese, f"Missing Chinese batching-guide requirement: {required}"

    requirements = (ROOT / "requirements-diagrams.txt").read_text(encoding="utf-8")
    assert requirements == "Pillow==12.2.0\n"

    expected_images = {
        "request_batching_lifecycle.png": (1856, 1136),
        "xiaomi_protocol_batch_planes.png": (1856, 1136),
        "kv_capacity_relationship.png": (1856, 1136),
    }
    for name, expected_size in expected_images.items():
        png = (ROOT / "images" / name).read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", png[16:24]) == expected_size
        assert len(png) > 50_000, f"Diagram unexpectedly small: {name}"

    prefill_launch = (ROOT / "scripts/amd-latest/launch_pd_prefill.sh").read_text(
        encoding="utf-8"
    )
    decode_launch = (ROOT / "scripts/amd-latest/launch_pd_decode.sh").read_text(
        encoding="utf-8"
    )
    single_launch = (ROOT / "scripts/amd-latest/launch_single_node_decode.sh").read_text(
        encoding="utf-8"
    )
    assert "--chunked-prefill-size 32768" in prefill_launch
    assert "--disable-cuda-graph" in prefill_launch
    assert "--chunked-prefill-size 16384" in decode_launch
    assert "--disable-cuda-graph" not in decode_launch
    assert "--mem-fraction-static 0.85" in prefill_launch
    assert "--mem-fraction-static 0.85" in decode_launch
    assert "--mem-fraction-static 0.95" in single_launch
    for contract in (
        "--context-length 262151",
        "--kv-cache-dtype fp8_e4m3",
        "--page-size 32",
        "--disaggregation-transfer-backend mooncake",
    ):
        assert contract in prefill_launch and contract in decode_launch


def check_controlled_isl() -> None:
    rows = load_tsv(ROOT / "data/controlled-isl-results.tsv")
    audit = load_json(ROOT / "data/validation/controlled-isl-evidence.json")
    image = load_json(ROOT / "data/validation/container-image.json")
    readme_texts = [path.read_text(encoding="utf-8") for path in READMES]
    expected = {
        ("prefill", 131072): {
            "headline": 15943.02,
            "mean_ttft_ms": 30170.48,
            "output_tokens": 1,
            "concurrency": 4,
            "num_prompts": 16,
        },
        ("prefill", 196608): {
            "headline": 13855.30,
            "mean_ttft_ms": 51894.88,
            "output_tokens": 1,
            "concurrency": 4,
            "num_prompts": 16,
        },
        ("decode", 131072): {
            "headline": 380.56,
            "client_output_tok_s": 94.59,
            "mean_ttft_ms": 20308.62,
            "mean_tpot_ms": 22.46,
            "output_tokens": 1024,
            "concurrency": 4,
            "num_prompts": 4,
            "usage": (0.36, 0.37),
        },
        ("decode", 196608): {
            "headline": 319.71,
            "client_output_tok_s": 58.90,
            "mean_ttft_ms": 35731.30,
            "mean_tpot_ms": 33.03,
            "output_tokens": 1024,
            "concurrency": 4,
            "num_prompts": 4,
            "usage": (0.55, 0.55),
        },
    }
    assert len(rows) == 4
    by_key = {(row["surface"], int(row["input_tokens"])): row for row in rows}
    assert set(by_key) == set(expected)
    assert audit["status"] == "VALIDATED"
    assert audit["measurement_date_beijing"] == "2026-07-19"
    assert audit["orchestrator_resume_started_at_utc"] == "2026-07-18T17:09:58Z"
    assert "started_at_utc" not in audit
    assert audit["measurement_repetitions_per_point"] == 1
    assert audit["runtime"]["runtime_image"] == image["runtime_identity"]
    assert audit["runtime"]["container_image_id"] == image["image_id"]
    assert audit["runtime"]["sglang_source_head"] == image["sglang_commit"]
    assert audit["runtime"]["aiter_source_head"] == image["aiter_commit"]
    assert audit["runtime"]["tuned_csv_sha256"] == image["tuned_csv_sha256"]
    assert audit["method"]["context_length"] == 262151
    assert audit["method"]["fixed_acceptance"] == {
        "length": 3.0,
        "scheduler_reported_rate": 0.67,
        "method": "match-expected",
        "validates_natural_acceptance": False,
        "validates_output_quality": False,
    }
    assert audit["scope"]["historical_202606_bs1_included"] is False
    assert "separate service launches" in audit["method"]["service_lifecycle"]
    assert "No same-service or fresh-service repeatability claim" in audit["method"]["service_lifecycle"]
    assert re.fullmatch(r"[0-9a-f]{64}", audit["private_source_manifest_sha256"])

    audit_points = {
        (point["surface"], point["input_tokens"]): point for point in audit["points"]
    }
    assert set(audit_points) == set(expected)
    for key, expected_point in expected.items():
        surface, input_tokens = key
        row = by_key[key]
        output_tokens = expected_point["output_tokens"]
        concurrency = expected_point["concurrency"]
        prompts = expected_point["num_prompts"]
        assert row["measurement_date"] == "2026-07-19"
        assert row["runtime_generation"] == "AMD_20260713_derived_final_image"
        assert row["output_tokens"] == str(output_tokens)
        assert row["client_concurrency"] == str(concurrency)
        assert row["num_prompts"] == str(prompts)
        assert row["successful_requests"] == str(prompts)
        assert int(row["total_input_tokens"]) == input_tokens * prompts
        assert int(row["total_generated_tokens"]) == output_tokens * prompts
        assert int(row["total_generated_tokens_retokenized"]) > 0
        assert row["measurement_repetitions"] == "1"
        assert row["status"] == "VALIDATED"
        assert row["runtime_image"] == image["runtime_identity"]
        assert "202606" not in row["source_run"] and "bs1" not in row["source_run"].lower()
        assert float(row["headline_value"]) == expected_point["headline"]
        assert audit_points[key]["headline_value"] == expected_point["headline"]
        assert float(row["mean_ttft_ms"]) == expected_point["mean_ttft_ms"]
        assert math.isclose(
            int(row["total_input_tokens"]) / float(row["benchmark_duration_s"]),
            float(row["input_tok_s"]),
            rel_tol=0.001,
        )
        if surface == "prefill":
            assert row["topology"] == "1P1D_PD"
            assert row["headline_metric"] == "input_tok_s"
            assert not row["actual_decode_batch"] and not row["scheduler_gen_tok_s"]
            assert int(row["total_generated_tokens_retokenized"]) == 16
        else:
            assert row["topology"] == "single_node_tp8_non_pd"
            assert row["headline_metric"] == "steady_bs4_scheduler_gen_tok_s"
            assert row["actual_decode_batch"] == "4"
            assert float(row["scheduler_gen_tok_s"]) == expected_point["headline"]
            assert row["raw_full_batch_samples"] == "8"
            assert row["transition_sample_excluded"] == "true"
            assert row["scheduler_samples"] == "7"
            assert (
                float(row["full_token_usage_min"]),
                float(row["full_token_usage_max"]),
            ) == expected_point["usage"]
            assert row["accept_len"] == "3.0" and row["accept_rate"] == "0.67"
            assert float(row["output_tok_s"]) == expected_point["client_output_tok_s"]
            assert float(row["mean_tpot_ms"]) == expected_point["mean_tpot_ms"]
            assert math.isclose(
                int(row["total_generated_tokens"]) / float(row["benchmark_duration_s"]),
                float(row["output_tok_s"]),
                rel_tol=0.001,
                abs_tol=0.005,
            )
            assert int(row["total_generated_tokens_retokenized"]) == 1028

    assert audit["deltas_128k_to_192k"] == {
        "prefill_input_tok_s_pct": -13.1,
        "decode_scheduler_gen_tok_s_pct": -16.0,
        "decode_mean_tpot_pct": 47.1,
        "decode_mean_ttft_pct": 75.9,
    }
    check_hash_manifest(ROOT / "data/evidence/controlled-isl-128k-192k")
    analyzer = subprocess.run(
        ["python3", str(ROOT / "scripts/analyze_controlled_isl_evidence.py")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert analyzer.returncode == 0, analyzer.stderr
    analyzer_result = json.loads(analyzer.stdout)
    assert analyzer_result["status"] == "PASS"
    assert analyzer_result["deltas_128k_to_192k"] == audit["deltas_128k_to_192k"]
    assert analyzer_result["acceptance_configuration"]["validates_natural_acceptance"] is False
    assert analyzer_result["acceptance_configuration"]["validates_output_quality"] is False

    english, chinese = readme_texts
    for path, text in zip(READMES, readme_texts):
        for required in (
            "data/controlled-isl-results.tsv",
            "data/validation/controlled-isl-evidence.json",
            "data/evidence/controlled-isl-128k-192k/",
            "analyze_controlled_isl_evidence.py",
            "15,943.02",
            "13,855.30",
            "380.56",
            "319.71",
        ):
            assert required in text, f"Missing controlled-ISL README value: {required}"
    for required in ("-13.1%", "-16.0%", "+47.1%", "+75.9%"):
        assert required in english, f"Missing controlled-ISL English delta: {required}"
    for required in ("下降 **13.1%**", "下降 **16.0%**", "增加 **47.1%**", "增加 **75.9%**"):
        assert required in chinese, f"Missing controlled-ISL Chinese delta: {required}"
    assert "Measured 128K/192K Subset on the 7/13-Derived Runtime" in english
    assert "基于7/13环境的128K/192K实测子集" in chinese
    assert "June BS1 boundary diagnostics are not included" in english
    assert "六月进行的 BS1 边界诊断未纳入这组结果" in chinese
    assert "separate service launches" in english
    assert "not a same-service or fresh-service repeatability claim" in english
    assert "两次独立启动的服务" in chinese
    assert "不代表同一服务内或服务重启后的重复性" in chinese
    assert "a 255K actual-BS4 point" in english
    assert "separately measured 255K PD-serving c1 capability point remains valid" in english
    assert "255K actual-BS4 测点" in chinese
    assert "单独实测的 255K PD-serving c1 能力点仍然有效" in chinese
    assert "64K same-method anchor and 255K remain open" not in english
    assert "64K同方法anchor、255K点" not in chinese
    assert "Future 128K/192K/255K combinations" not in english
    assert "未来128K/192K/255K组合" not in chinese

    prefill_benchmark = (ROOT / "scripts/amd-latest/benchmark_1p_prefill_long_isl_selected.sh").read_text(encoding="utf-8")
    decode_benchmark = (ROOT / "scripts/amd-latest/benchmark_decode_fixed_batch_bs4.sh").read_text(encoding="utf-8")
    for fragment in (
        "run_point 131072 1 4 16 1 1800",
        "run_point 196608 1 4 16 1 2400",
    ):
        assert fragment in prefill_benchmark
    for fragment in (
        "--random-output-len 1024",
        "--num-prompts 4",
        "--max-concurrency 4",
        "Total generated tokens:[[:space:]]+4096",
        "full_batch_samples=$(grep -c 'Decode batch, #running-req: 4'",
        "accept len: 3\\.00, accept rate: 0\\.67",
        "#queue-req: [1-9]",
    ):
        assert fragment in decode_benchmark


def check_result_tables() -> None:
    final_rows = load_tsv(ROOT / "data/final-results.tsv")
    scalability_rows = load_tsv(ROOT / "data/scalability-results.tsv")
    repeatability_rows = load_tsv(ROOT / "data/decode-repeatability.tsv")
    decode_audit = load_json(ROOT / "data/validation/decode-service-log-audit-8k.json")
    assert len(final_rows) == 9
    assert all(row["measurement_repetitions"] == "1" for row in final_rows)
    assert all(
        row["selection_policy"] == "selected_valid_record_for_reported_scope"
        for row in final_rows
    )
    assert len(scalability_rows) == 33
    assert len(repeatability_rows) == 4
    assert decode_audit["measurement_repetitions_per_headline_point"] == 1
    audit_by_concurrency = {point["client_concurrency"]: point for point in decode_audit["points"]}
    assert set(audit_by_concurrency) == {16, 32, 64, 128}
    expected_sources = {
        "tuned_moe_retest_20260713T014113Z": {
            "decode_outer_log_sha256": "7759dfb94c01c9a6e1df70e5d0b256485f12f3e1620f0f20d45cccd671981a47",
            "client_log_sha256": {
                "16": "69313313479cc4bca4221d69a52d0b90a6a094fb34c92eb9a04e2f85d7335664",
                "32": "c62aa0c52b697c24f3e09538746f04b36f53eb439f3549ad1e732536a2064903",
                "128": "dfcf0a8f96d962251f98efd51d00365eb4de13bc412c4523608e37c919f7d6d3",
            },
        },
        "amd_onnode_source_exact_20260714T104200Z": {
            "decode_outer_log_sha256": "3e85d094f11c2a06d43304657ea4f8686cb9134af881e182bc42279147455c3f",
            "client_log_sha256": {
                "64": "02f9585fe3a0d8bb74616fd33dfad9376718043932694c5913ee0085a9315d2c",
            },
        },
    }
    actual_sources = {
        source["run_id"]: {
            "decode_outer_log_sha256": source["decode_outer_log_sha256"],
            "client_log_sha256": source["client_log_sha256"],
        }
        for source in decode_audit["source_artifacts"]
    }
    assert actual_sources == expected_sources
    for point in decode_audit["points"]:
        source = actual_sources[point["source_run"]]
        assert str(point["client_concurrency"]) in source["client_log_sha256"]
    readme_texts = [path.read_text(encoding="utf-8") for path in READMES]

    prefill = {
        int(row["input_tokens"]): float(row["mi300x_throughput_tok_s"])
        for row in final_rows
        if row["topology"] == "1P1D" and row["surface"] == "prefill"
    }
    assert set(prefill) == {8192, 65536, 262144}
    same_matrix_prefill = {
        int(row["input_tokens"]): float(row["throughput_tok_s"])
        for row in scalability_rows
        if row["topology"] == "1P1D"
        and row["surface"] == "prefill"
        and int(row["concurrency"]) == 4
    }
    assert set(same_matrix_prefill) == {8192, 65536, 262144}
    assert round(
        (same_matrix_prefill[65536] / same_matrix_prefill[8192] - 1) * 100, 1
    ) == 3.3
    assert round(
        (same_matrix_prefill[262144] / same_matrix_prefill[65536] - 1) * 100, 1
    ) == -34.0
    for path, text in zip(READMES, readme_texts):
        assert "18,161.81 → 18,763.17" in text
        assert "18,763.17 → 12,389.64" in text
        assert "3.3%" in text and "34.0%" in text
        assert ("measurement N=1" if path.name == "README.md" else "测量次数 N=1") in text
        assert "20,305.98 → 18,983.91" not in text
        assert "18,983.91 → 12,864.96" not in text
    assert "Prefill remains flat through 64K in the controlled matrix" in readme_texts[0]
    assert "受控矩阵中，Prefill 吞吐到 64K 仍基本持平" in readme_texts[1]
    for rendered_phrase in (
        "**受控矩阵中，Prefill 吞吐到 64K 仍基本持平。** 这是",
        "**接近 256K 时，长输入带来的性能损失开始明显。** 该测点",
        "**已确认精确 262,144 个 Token 的 Prefill 能力**，但该记录",
        "**Decode 对长 context 比 Prefill 更敏感。** 这组输出 8K",
    ):
        assert rendered_phrase in readme_texts[1]
    assert "credible long-ISL performance measurement" in readme_texts[0]
    assert "长 ISL 性能测量结果可信" in readme_texts[1]

    for row in final_rows:
        mi300x = float(row["mi300x_throughput_tok_s"])
        concurrency = int(row["mi300x_client_concurrency"])
        if row["surface"] == "decode":
            h200_bs = int(row["xiaomi_h200_per_dp_bs"])
            h200_tok_s = float(row["xiaomi_h200_reference_tok_s"])
            h200_tpot = float(row["xiaomi_h200_per_dp_tpot_ms"])
            mi300x_tpot = float(row["mi300x_mean_tpot_ms"])
            mi300x_ttft_s = float(row["mi300x_mean_ttft_ms"]) / 1000
            audit = audit_by_concurrency[concurrency]
            assert concurrency == h200_bs
            assert row["mi300x_throughput_metric"] == "e2e_output"
            assert row["xiaomi_h200_throughput_metric"] == "decode_output"
            assert audit["source_run"] == row["headline_source"]
            assert int(row["mi300x_actual_decode_batch_mode"]) == audit["running_requests_mode"]
            assert int(row["mi300x_actual_decode_batch_max"]) == audit["running_requests_max"]
            assert float(row["mi300x_decode_node_mean_gen_tok_s"]) == audit["mean_gen_tok_s"]
            expected_status = (
                "directional_near_aligned_actual_batch"
                if concurrency in (16, 32)
                else "not_aligned_actual_decode_batch"
            )
            assert row["comparison_status"] == expected_status
            mi300x_line = (
                f"| {concurrency} | {audit['running_requests_mode']} / {audit['running_requests_max']} | "
                f"**{mi300x:,.2f}** | {audit['mean_gen_tok_s']:,.2f} | "
                f"{mi300x_ttft_s:,.2f} | {mi300x_tpot:.2f} |"
            )
            assert mi300x_line in readme_texts[0]
            assert mi300x_line in readme_texts[1]
            h200_line_en = f"| {h200_bs} | {h200_tok_s:,.0f} | {h200_tpot:.2f} | Not provided |"
            h200_line_cn = f"| {h200_bs} | {h200_tok_s:,.0f} | {h200_tpot:.2f} | 未提供 |"
            assert h200_line_en in readme_texts[0]
            assert h200_line_cn in readme_texts[1]
        elif row["topology"] == "1P1D":
            h200 = float(row["xiaomi_h200_reference_tok_s"])
            ratio = round(mi300x / h200 * 100, 1)
            assert row["mi300x_throughput_metric"] == "input"
            assert row["xiaomi_h200_throughput_metric"] == "input"
            assert row["comparison_status"] == "directional_missing_h200_input_concurrency"
            label = {8192: "8K", 65536: "64K", 262144: "256K"}[int(row["input_tokens"])]
            line = (
                f"| {label} | {concurrency} | **{mi300x:,.2f}** | "
                f"{h200:,.0f} | {ratio:.1f}% |"
            )
            for text in readme_texts:
                assert line in text
        else:
            assert row["mi300x_throughput_metric"] == "aggregate_input"
            assert row["comparison_status"] == "no_h200_dp2_reference"
            label = {8192: "8K", 65536: "64K"}[int(row["input_tokens"])]
            line = f"| {label} | {concurrency} | **{mi300x:,.2f}** |"
            for text in readme_texts:
                assert line in text

    c16 = next(
        row
        for row in final_rows
        if row["surface"] == "decode" and row["mi300x_client_concurrency"] == "16"
    )
    assert round(
        float(c16["mi300x_decode_node_mean_gen_tok_s"])
        / float(c16["xiaomi_h200_reference_tok_s"])
        * 100,
        1,
    ) == 95.6
    assert round(
        (float(c16["xiaomi_h200_per_dp_tpot_ms"]) - float(c16["mi300x_mean_tpot_ms"]))
        / float(c16["xiaomi_h200_per_dp_tpot_ms"])
        * 100,
        1,
    ) == 6.6
    assert "95.6%" in readme_texts[0] and "6.6% lower" in readme_texts[0]
    assert "95.6%" in readme_texts[1] and "低 6.6%" in readme_texts[1]
    assert "same local batch size" not in readme_texts[0]
    assert "相同 local batch" not in readme_texts[1]
    assert readme_texts[0].count("Observed Decode batch (steady-state / peak)") == 2
    assert readme_texts[1].count("实测 Decode batch（稳态 / 峰值）") == 2
    assert "mode / max" not in readme_texts[0]
    assert "Usually " not in readme_texts[0]
    assert "众数" not in readme_texts[1]
    assert "；最高 " not in readme_texts[1]

    for row in scalability_rows:
        throughput = float(row["throughput_tok_s"])
        ttft = float(row["mean_ttft_ms"])
        concurrency = int(row["concurrency"])
        if row["surface"] == "decode":
            line = (
                f"| {concurrency} | {throughput:,.2f} | "
                f"{float(row['mean_tpot_ms']):,.2f} | {ttft:,.2f} |"
            )
        else:
            input_tokens = int(row["input_tokens"])
            english_label = {8192: "8K", 65536: "64K", 262144: "Nominal 256K"}[input_tokens]
            chinese_label = {8192: "8K", 65536: "64K", 262144: "名义 256K"}[input_tokens]
            english_line = f"| {english_label} | {concurrency} | {throughput:,.2f} | {ttft:,.2f} |"
            chinese_line = f"| {chinese_label} | {concurrency} | {throughput:,.2f} | {ttft:,.2f} |"
            assert english_line in readme_texts[0]
            assert chinese_line in readme_texts[1]
            continue
        for text in readme_texts:
            assert line in text

    for row in repeatability_rows:
        line = (
            f"| {int(row['concurrency'])} | {float(row['fresh_run_1_output_tok_s']):,.2f} | "
            f"{float(row['fresh_run_2_output_tok_s']):,.2f} | "
            f"{float(row['throughput_delta_pct']):+.2f}% | "
            f"{float(row['fresh_run_1_mean_tpot_ms']):.2f} / "
            f"{float(row['fresh_run_2_mean_tpot_ms']):.2f} |"
        )
        for text in readme_texts:
            assert line in text


def check_long_context_decode() -> None:
    rows = load_tsv(ROOT / "data/decode-long-context-results.tsv")
    expected_fields = {
        "measurement_date",
        "topology",
        "surface",
        "requested_input_tokens",
        "output_tokens",
        "concurrency",
        "num_prompts",
        "successful_requests",
        "failed_requests",
        "total_input_tokens",
        "total_generated_tokens",
        "total_generated_tokens_retokenized",
        "benchmark_duration_s",
        "throughput_metric",
        "input_tok_s",
        "output_tok_s",
        "peak_output_tok_s",
        "peak_concurrent_requests",
        "mean_tpot_ms",
        "median_tpot_ms",
        "mean_ttft_ms",
        "context_length",
        "prompt_mode",
        "measurement_repetitions",
        "status",
        "runtime_image",
        "source_run",
    }
    assert set(rows[0]) == expected_fields
    expected = {
        (65536, 1024, 16): 32,
        (65536, 1024, 32): 64,
        (65536, 1024, 64): 128,
        (65536, 1024, 96): 192,
        (261120, 1024, 1): 1,
    }
    actual = {
        (
            int(row["requested_input_tokens"]),
            int(row["output_tokens"]),
            int(row["concurrency"]),
        ): int(row["num_prompts"])
        for row in rows
    }
    assert len(rows) == len(actual) == 5
    assert actual == expected
    assert not any("h200" in field.lower() for field in expected_fields)

    readme_texts = [path.read_text(encoding="utf-8") for path in READMES]
    for row in rows:
        requested_input = int(row["requested_input_tokens"])
        output_tokens = int(row["output_tokens"])
        concurrency = int(row["concurrency"])
        prompts = int(row["num_prompts"])
        assert row["measurement_date"] == "2026-07-17"
        assert row["topology"] == "1P1D" and row["surface"] == "decode"
        assert row["throughput_metric"] == "end_to_end_output"
        assert row["prompt_mode"] == "random_text"
        assert row["status"] == "VALIDATED"
        assert int(row["measurement_repetitions"]) == 1
        assert int(row["context_length"]) == 262151
        assert requested_input + output_tokens <= int(row["context_length"])
        assert int(row["successful_requests"]) == prompts
        assert int(row["failed_requests"]) == 0
        assert int(row["total_input_tokens"]) > 0
        assert int(row["total_generated_tokens"]) == output_tokens * prompts
        assert int(row["total_generated_tokens_retokenized"]) > 0
        assert math.isclose(
            int(row["total_generated_tokens"]) / float(row["benchmark_duration_s"]),
            float(row["output_tok_s"]),
            rel_tol=0.001,
        )
        assert math.isclose(
            int(row["total_input_tokens"]) / float(row["benchmark_duration_s"]),
            float(row["input_tok_s"]),
            rel_tol=0.001,
        )
        if requested_input == 65536:
            assert math.isclose(
                float(row["output_tok_s"]),
                float(row["input_tok_s"]) / 64,
                rel_tol=2e-5,
            )
        assert int(row["peak_concurrent_requests"]) > 0
        for field in ("benchmark_duration_s", "input_tok_s", "output_tok_s", "peak_output_tok_s", "mean_tpot_ms", "median_tpot_ms", "mean_ttft_ms"):
            value = float(row[field])
            assert math.isfinite(value) and value > 0
    boundary = next(row for row in rows if row["requested_input_tokens"] == "261120")
    assert int(boundary["requested_input_tokens"]) != 262144
    assert int(boundary["requested_input_tokens"]) + int(boundary["output_tokens"]) == 262144

    evidence = load_json(ROOT / "data/validation/decode-long-context-evidence.json")
    service_audit = load_json(ROOT / "data/validation/decode-service-log-audit.json")
    image = load_json(ROOT / "data/validation/container-image.json")
    h200 = load_json(ROOT / "data/validation/h200-reference.json")
    assert evidence["status"] == "VALIDATED"
    assert evidence["measurement_repetitions"] == 1
    assert evidence["points"] == rows
    assert evidence["runtime"]["runtime_image"] == image["runtime_identity"]
    assert evidence["runtime"]["container_image_id"] == image["image_id"]
    assert evidence["runtime"]["sglang_source_head"] == image["sglang_commit"]
    assert evidence["runtime"]["aiter_source_head"] == image["aiter_commit"]
    assert evidence["runtime"]["tuned_csv_sha256"] == image["tuned_csv_sha256"]
    assert evidence["method"]["context_length"] == 262151
    assert evidence["method"]["configured_transfer_backend"] == "Mooncake"
    assert evidence["method"]["configured_rdma_devices_per_worker"] == 8
    assert evidence["method"]["rdma_device_initialization_verified"] is True
    assert evidence["method"]["explicit_tcp_fallback_marker_found"] is False
    assert "full benchmark duration" in evidence["scope"]["throughput_definition"]
    assert len(evidence["point_artifacts"]) == 5
    assert len(evidence["service_artifacts"]) == 8
    for artifact in evidence["point_artifacts"]:
        assert re.fullmatch(r"[0-9a-f]{64}", artifact["client_log_sha256"])
        assert re.fullmatch(r"[0-9a-f]{64}", artifact["command_sha256"])
    for digest in evidence["service_artifacts"].values():
        assert re.fullmatch(r"[0-9a-f]{64}", digest)

    assert service_audit["source_run"] == evidence["run_id"]
    assert service_audit["measurement_repetitions"] == 1
    assert service_audit["source_artifact"]["sha256"] == evidence["service_artifacts"]["decode_outer_log_sha256"]
    expected_service_points = {
        16: (4, 5, 8, 267.97, 321.70),
        32: (4, 4, 24, 276.74, 321.91),
        64: (4, 5, 56, 282.81, 328.11),
        96: (4, 5, 88, 287.77, 338.68),
        1: (1, 1, 0, 80.64, 92.13),
    }
    assert len(service_audit["points"]) == 5
    for point in service_audit["points"]:
        expected_point = expected_service_points[point["client_concurrency"]]
        assert (
            point["running_requests_mode"],
            point["running_requests_max"],
            point["preallocated_requests_max"],
            point["mean_gen_tok_s"],
            point["max_gen_tok_s"],
        ) == expected_point

    h200_64k = {
        point["per_dp_bs"]: point
        for point in h200["decode"]["points"]
        if point["input_tokens"] == 65536
    }
    assert set(h200_64k) == {16, 32, 64, 96}
    assert h200["revalidated_at"] == "2026-07-18"
    assert h200["numeric_excerpt_sharing_authorization_evidence"] == (
        "not_recorded_in_repository; repository owner must confirm external sharing authority"
    )
    assert all(point["output_tokens"] is None for point in h200["decode"]["points"])
    assert h200["decode"]["tpot_origin"] == (
        "customer worksheet; derived as 1000 / "
        "(per-DP decode log output tok/s / per-DP BS)"
    )
    assert h200["matching_e2e_reference_available"] is False
    expected_h200_64k = {
        16: (11.994992, 1333.89),
        32: (14.314279, 2235.53),
        64: (16.327447, 3919.78),
        96: (19.625521, 4891.59),
    }
    for concurrency, (expected_tpot, expected_tok_s) in expected_h200_64k.items():
        assert h200_64k[concurrency]["mean_tpot_ms"] == expected_tpot
        assert h200_64k[concurrency]["output_tok_s"] == expected_tok_s
    mi300x_64k = {int(row["concurrency"]): row for row in rows if row["requested_input_tokens"] == "65536"}
    service_64k = {point["client_concurrency"]: point for point in service_audit["points"] if point["requested_input_tokens"] == 65536}
    for concurrency in (16, 32, 64, 96):
        row = mi300x_64k[concurrency]
        audit = service_64k[concurrency]
        line = (
            f"| {concurrency} | {audit['running_requests_mode']} / {audit['running_requests_max']} | "
            f"{float(row['output_tok_s']):,.2f} | {audit['mean_gen_tok_s']:,.2f} | "
            f"{float(row['mean_ttft_ms']) / 1000:,.2f} | {float(row['mean_tpot_ms']):,.2f} |"
        )
        for text in readme_texts:
            assert line in text
        h200_rate = float(h200_64k[concurrency]["output_tok_s"])
        assert math.isclose(
            float(h200_64k[concurrency]["mean_tpot_ms"]),
            1000 / (h200_rate / concurrency),
            rel_tol=2e-6,
        )
        h200_line_en = f"| {concurrency} | {h200_rate:,.2f} | {float(h200_64k[concurrency]['mean_tpot_ms']):.2f} | Not provided |"
        h200_line_cn = f"| {concurrency} | {h200_rate:,.2f} | {float(h200_64k[concurrency]['mean_tpot_ms']):.2f} | 未提供 |"
        assert h200_line_en in readme_texts[0]
        assert h200_line_cn in readme_texts[1]

    for text in readme_texts:
        assert "data/decode-long-context-results.tsv" in text
        assert "data/validation/decode-long-context-evidence.json" in text
        assert "data/validation/decode-service-log-audit.json" in text
        assert "benchmark_decode_long_context.sh" in text
        assert "18,983.91" in text and "27,400" in text and "69.3%" in text
        assert "E2E output tok/s" in text
        assert "Decode-node gen tok/s" in text or "Decode 节点 mean gen tok/s" in text
        assert "TPUT" in text

    english, chinese = readme_texts
    assert "Higher batch sizes (BS32–96) still require an EP/multi-node Decode deployment" in english
    assert "BS32–96 仍需 EP 或多节点 Decode 部署" in chinese
    assert "A strict NVIDIA comparison requires" in english
    assert "要做严格 NVIDIA 对比" in chinese
    assert "actual D-node batch" in english
    assert "实际 D-node batch" in chinese
    assert "four 8-GPU nodes, 32 GPUs total" in english
    assert "四台 8-GPU 节点，共 32 张 GPU" in chinese

    benchmark = (ROOT / "scripts/amd-latest/benchmark_decode_long_context.sh").read_text(
        encoding="utf-8"
    )
    for input_tokens, output_tokens, concurrency in expected:
        assert re.search(
            rf"^run_point {input_tokens} {output_tokens} {concurrency} ",
            benchmark,
            re.MULTILINE,
        )


def check_provenance() -> None:
    final_rows = load_tsv(ROOT / "data/final-results.tsv")
    h200 = load_json(ROOT / "data/validation/h200-reference.json")
    prefill = {point["input_tokens"]: point for point in h200["prefill"]["points"]}
    decode = {
        (point["input_tokens"], point["per_dp_bs"]): point
        for point in h200["decode"]["points"]
    }
    for row in final_rows:
        if row["topology"] != "1P1D":
            continue
        if row["surface"] == "prefill":
            assert math.isclose(
                float(row["xiaomi_h200_reference_tok_s"]),
                prefill[int(row["input_tokens"])]["input_tok_s"],
                rel_tol=1e-9,
                abs_tol=1e-6,
            )
        else:
            point = decode[(int(row["input_tokens"]), int(row["xiaomi_h200_per_dp_bs"]))]
            assert math.isclose(
                float(row["xiaomi_h200_reference_tok_s"]),
                point["output_tok_s"],
                rel_tol=1e-9,
                abs_tol=1e-6,
            )
            assert math.isclose(
                float(row["xiaomi_h200_per_dp_tpot_ms"]),
                point["mean_tpot_ms"],
                rel_tol=1e-9,
                abs_tol=1e-6,
            )

    image = load_json(ROOT / "data/validation/container-image.json")
    runtime = dict(
        line.split("=", 1)
        for line in (ROOT / "data/validation/runtime-version.txt").read_text().splitlines()
        if line
    )
    assert runtime["runtime_image"] == image["runtime_identity"]
    assert runtime["runtime_image_id"] == image["image_id"]
    assert int(runtime["runtime_image_layers"]) == image["layer_count"] == 37
    assert runtime["sglang_source_head"] == image["sglang_commit"]
    assert runtime["aiter_source_head"] == image["aiter_commit"]
    assert runtime["tuned_csv_sha256"] == image["tuned_csv_sha256"]
    assert image["clean_docker_pull_verified"] is True
    assert image["runtime_manifest_verified"] is True
    assert image["tag_write_enabled"] is False
    assert image["tag_delete_enabled"] is False
    assert image["runtime_alias"] == "AMD_20260713_derived_final_image"
    assert image["registry_visibility"].startswith("private;")
    assert "registry" not in image and "repository" not in image
    assert "immutable_pull_ref" not in image
    assert "azurecr.io" not in json.dumps(image)

    exact = load_json(ROOT / "data/validation/exact-token-256k.json")
    headline_256k = next(
        row
        for row in final_rows
        if row["topology"] == "1P1D"
        and row["surface"] == "prefill"
        and row["input_tokens"] == "262144"
    )
    assert exact["status"] == "VALIDATED"
    assert exact["measurement_repetitions"] == 1
    assert exact["tokenize_prompt"] is True
    assert exact["successful_requests"] == exact["retokenized_outputs"] == 16
    assert exact["total_input_tokens"] == 16 * 262144
    assert exact["input_tok_s"] == float(headline_256k["mi300x_throughput_tok_s"])
    for role in ("prefill", "decode"):
        info = load_json(ROOT / f"data/validation/{role}-server-info.json")
        assert info["context_length"] == 262151
        assert info["max_req_input_len"] >= 262145


def check_code_and_assets() -> None:
    bundle = ROOT / "scripts/amd-latest"
    for path in sorted(bundle.glob("*.sh")):
        subprocess.run(["bash", "-n", str(path)], check=True)
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    check_hash_manifest(bundle)
    check_hash_manifest(ROOT / "data/validation")

    png = (ROOT / "images/pd_architecture.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (1648, 948)


def check_public_boundary() -> None:
    patterns = {
        "credential": re.compile(
            r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|"
            r"Bearer\s+[A-Za-z0-9._-]{20,})"
        ),
        "azure_uuid": re.compile(
            r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
        ),
        "private_path": re.compile(
            r"(?i)(?:[A-Z]:\\|/mnt/[gc]/|AI-" r"Super-Agent|cloudapp\.azure|"
            r"\.onmicrosoft\.com|ssh" r"pass)"
        ),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    }
    findings = []
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in patterns.items():
            if pattern.search(text):
                findings.append((name, path.relative_to(ROOT).as_posix()))
    assert not findings, f"Public boundary findings: {findings}"
    assert not (ROOT / "password.txt").exists()


def check_fixed_batch_decode() -> None:
    rows = load_tsv(ROOT / "data/decode-fixed-batch-results.tsv")
    audit = load_json(ROOT / "data/validation/decode-fixed-batch-audit.json")
    image = load_json(ROOT / "data/validation/container-image.json")
    h200 = load_json(ROOT / "data/validation/h200-reference.json")
    readme_texts = [path.read_text(encoding="utf-8") for path in READMES]

    assert audit["run_id"] == "fixedbatch_decode_exact_and_diagnostic_20260718"
    assert audit["measurement_repetitions"] == 2
    assert audit["method"]["method_identity"] == "fixed_acceptance_performance_benchmark"
    assert "does not validate natural MTP acceptance or output quality" in audit["method"]["acceptance"]
    assert "tokenizer.encode(generated_text)" in audit["method"]["output_accounting"]
    assert audit["source_artifacts"]["public_sanitized_evidence"] == "data/evidence/exact64-fixed-acceptance"
    assert audit["source_artifacts"]["public_analyzer"] == "scripts/analyze_exact64_evidence.py"
    assert audit["runtime"]["runtime_image"] == image["runtime_identity"]
    assert audit["runtime"]["container_image_id"] == image["image_id"]
    assert audit["runtime"]["sglang_source_head"] == image["sglang_commit"]
    assert audit["runtime"]["aiter_source_head"] == image["aiter_commit"]
    assert audit["runtime"]["tuned_csv_sha256"] == image["tuned_csv_sha256"]
    assert audit["runtime"]["optimized_decode_env"] == {
        "SGLANG_AITER_UNIFIED_VERIFY": "1",
        "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE": "1",
    }
    assert "bpreshuffle" in audit["runtime"]["required_kernel_marker"].lower()
    assert "all four exact runs" in audit["method"]["transition_guard_rationale"]
    assert "can exclude at most one sample" in audit["method"]["transition_guard_rationale"]
    for key in (
        "launch_server_sh_sha256",
        "decode_outer_log_sha256_at_analysis",
        "decode_outer_log_sha256_in_remote_manifest",
        "exact_rep1_client_log_sha256",
        "exact_rep1_decode_window_sha256",
        "exact_rep1_service_log_sha256",
        "exact_rep2_client_log_sha256",
        "exact_rep2_decode_window_sha256",
        "exact_rep2_service_log_sha256",
        "exact_no_ck_rep1_client_log_sha256",
        "exact_no_ck_rep1_decode_window_sha256",
        "exact_no_ck_rep2_client_log_sha256",
        "exact_no_ck_rep2_decode_window_sha256",
    ):
        assert re.fullmatch(r"[0-9a-f]{64}", audit["source_artifacts"][key])

    assert len(rows) == 6
    exact_rows = [row for row in rows if row["result_role"] == "headline_exact_rep"]
    diagnostic_rows = [row for row in rows if row["result_role"] == "diagnostic_output8k"]
    assert len(exact_rows) == 2 and len(diagnostic_rows) == 4
    diagnostic_by_key = {
        (int(row["base_input_tokens"]), int(row["fixed_batch"])): row
        for row in diagnostic_rows
    }
    diagnostic_8k_bs16 = diagnostic_by_key[(8192, 16)]
    diagnostic_64k_bs16 = diagnostic_by_key[(65536, 16)]
    assert round(
        (
            float(diagnostic_64k_bs16["steady_gen_tok_s_mean"])
            / float(diagnostic_8k_bs16["steady_gen_tok_s_mean"])
            - 1
        )
        * 100,
        1,
    ) == -30.4
    assert round(
        (
            float(diagnostic_64k_bs16["implied_tpot_ms"])
            / float(diagnostic_8k_bs16["implied_tpot_ms"])
            - 1
        )
        * 100,
        1,
    ) == 43.6
    for row in diagnostic_rows:
        assert int(row["output_tokens"]) == 8192
        assert int(row["measurement_repetitions"]) == 1
        assert row["optimized_path"] == "not_verified"
        assert not any(
            row[field]
            for field in (
                "xiaomi_h200_per_dp_bs",
                "xiaomi_h200_reference_tok_s",
                "xiaomi_h200_per_dp_tpot_ms",
                "mi300x_vs_h200_pct",
            )
        )

    exact_points = {
        point["repetition"]: point for point in audit["headline_exact"]["points"]
    }
    assert set(exact_points) == {1, 2}
    for row in exact_rows:
        repetition = int(row["repetition"])
        point = exact_points[repetition]
        assert int(row["base_input_tokens"]) == 65536
        assert int(row["output_tokens"]) == 1024
        assert int(row["fixed_batch"]) == 16
        assert int(row["successful_requests"]) == point["successful_requests"] == 16
        assert int(row["total_input_tokens"]) == point["total_input_tokens"] == 1048576
        assert int(row["total_generated_tokens"]) == point["total_generated_tokens"] == 16384
        assert int(row["total_generated_tokens_retokenized"]) == point[
            "total_generated_tokens_retokenized"
        ] == 4112
        assert float(row["steady_gen_tok_s_mean"]) == point["steady_state"]["mean_gen_tok_s"]
        assert float(row["implied_tpot_ms"]) == point["steady_state"]["implied_tpot_ms_at_batch"]
        assert int(row["raw_full_batch_samples"]) == point["steady_state"]["raw_full_batch_samples"] == 8
        assert row["transition_sample_excluded"] == "true"
        assert point["steady_state"]["transition_sample_excluded"] is True
        assert int(row["steady_samples"]) == point["steady_state"]["samples_used"] == 7
        used_samples = point["steady_state"]["used_gen_tok_s"]
        assert len(used_samples) == 7
        assert point["steady_state"]["transition_first_sample_tok_s"] < (
            0.5 * statistics.median(used_samples)
        )
        assert point["steady_state"]["subsequent_sample_median_tok_s"] == round(
            statistics.median(used_samples), 2
        )
        assert point["steady_state"]["mean_gen_tok_s"] == round(
            statistics.mean(used_samples), 2
        )
        assert point["steady_state"]["median_gen_tok_s"] == round(
            statistics.median(used_samples), 2
        )
        assert point["steady_state"]["stdev_gen_tok_s"] == round(
            statistics.pstdev(used_samples), 2
        )
        assert point["steady_state"]["accept_len_values"] == [3.0]
        assert point["steady_state"]["accept_rate_values"] == [0.67]
        assert point["steady_state"]["queue_values"] == [0]
        assert int(row["measurement_repetitions"]) == 2
        assert row["source_run"] == "exact1k_ck_20260718"
        assert row["optimized_path"] == "aiter_ck_blockscale_bpreshuffle_verified"
        assert row["comparison_status"] == (
            "worksheet_local_directional_ratio_h200_output_length_unverified"
        )
        assert row["runtime_image"] == image["runtime_identity"]
        assert math.isclose(
            point["steady_state"]["implied_tpot_ms_at_batch"],
            1000.0 / (point["steady_state"]["mean_gen_tok_s"] / 16),
            abs_tol=0.01,
        )
        assert math.isclose(
            float(row["client_output_tok_s"]), point["client_output_tok_s"], abs_tol=0.01
        )

    aggregate = audit["headline_exact"]["aggregate"]
    run_means = [exact_points[index]["steady_state"]["mean_gen_tok_s"] for index in (1, 2)]
    assert run_means == [931.58, 935.92]
    assert aggregate["mean_of_fresh_runs_tok_s"] == round(sum(run_means) / 2, 2) == 933.75
    assert aggregate["repeatability_delta_pct_run2_vs_run1"] == round(
        (run_means[1] / run_means[0] - 1) * 100, 2
    ) == 0.47
    assert aggregate["implied_tpot_ms_at_batch"] == round(
        1000 / (aggregate["mean_of_fresh_runs_tok_s"] / 16), 2
    ) == 17.14

    baseline = audit["headline_exact"]["same_image_exact_no_ck"]
    assert baseline["optimized_path_marker_present"] is False
    for controlled_field in (
        "same host",
        "immutable image",
        "benchmark command",
        "two fresh-service repetitions",
        "adds only SGLANG_AITER_UNIFIED_VERIFY=1",
        "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1",
        "back-to-back",
    ):
        assert controlled_field in baseline["ab_control"]
    baseline_points = {point["repetition"]: point for point in baseline["points"]}
    assert set(baseline_points) == {1, 2}
    for point in baseline_points.values():
        used_samples = point["used_gen_tok_s"]
        assert len(used_samples) == 7
        assert point["transition_first_sample_tok_s"] < (
            0.5 * statistics.median(used_samples)
        )
        assert point["subsequent_sample_median_tok_s"] == round(
            statistics.median(used_samples), 2
        )
        assert point["mean_gen_tok_s"] == round(statistics.mean(used_samples), 2)
        assert point["implied_tpot_ms_at_batch"] == round(
            1000 / (point["mean_gen_tok_s"] / 16), 2
        )
    baseline_means = [baseline_points[index]["mean_gen_tok_s"] for index in (1, 2)]
    assert baseline_means == [740.29, 745.95]
    assert baseline["aggregate_mean_gen_tok_s"] == round(
        statistics.mean(baseline_means), 2
    ) == 743.12
    assert baseline["repeatability_delta_pct_run2_vs_run1"] == round(
        (baseline_means[1] / baseline_means[0] - 1) * 100, 2
    ) == 0.76
    assert baseline["implied_tpot_ms_at_batch"] == round(
        1000 / (baseline["aggregate_mean_gen_tok_s"] / 16), 2
    ) == 21.53
    assert aggregate["same_image_exact_no_ck_baseline_tok_s"] == baseline[
        "aggregate_mean_gen_tok_s"
    ]

    h200_bs16 = next(
        p for p in h200["decode"]["points"]
        if p["input_tokens"] == 65536 and p["per_dp_bs"] == 16
    )
    assert h200["decode"]["workbook_output_length_column_present"] is False
    assert "output_tokens is null" in h200["decode"][
        "point_output_tokens_modeling_note"
    ]
    assert h200_bs16["output_tokens"] is None
    assert "DP4 multiplier" in h200["decode"]["throughput_scope"]
    assert aggregate["h200_64k_bs16_worksheet_tok_s"] == h200_bs16["output_tok_s"]
    assert aggregate["h200_64k_bs16_worksheet_tpot_ms"] == h200_bs16["mean_tpot_ms"]
    assert aggregate["mi300x_vs_h200_worksheet_pct"] == round(
        aggregate["mean_of_fresh_runs_tok_s"] / h200_bs16["output_tok_s"] * 100, 1
    ) == 70.0
    assert round(
        (
            aggregate["implied_tpot_ms_at_batch"] / h200_bs16["mean_tpot_ms"]
            - 1
        )
        * 100,
        1,
    ) == 42.9
    assert aggregate["optimized_path_improvement_pct"] == round(
        (
            aggregate["mean_of_fresh_runs_tok_s"]
            / aggregate["same_image_exact_no_ck_baseline_tok_s"]
            - 1
        )
        * 100,
        1,
    ) == 25.7
    assert round(
        (
            aggregate["implied_tpot_ms_at_batch"]
            / baseline["implied_tpot_ms_at_batch"]
            - 1
        )
        * 100,
        1,
    ) == -20.4

    en_row = (
        "| 64K input / 1K server-accounted output | 16 | 931.58 / 935.92 | **933.75** | "
        "**0.47%** | **17.14 ms** | 1,333.89 tok/s, 11.99 ms | **70.0% worksheet-local** |"
    )
    cn_row = (
        "| 64K input / 1K server-accounted output | 16 | 931.58 / 935.92 | **933.75** | "
        "**0.47%** | **17.14 ms** | 1,333.89 tok/s，11.99 ms | **70.0% 对应行相对值** |"
    )
    assert en_row in readme_texts[0]
    assert cn_row in readme_texts[1]
    for path, text in zip(READMES, readme_texts):
        assert "data/decode-fixed-batch-results.tsv" in text
        assert "data/validation/decode-fixed-batch-audit.json" in text
        assert "launch_single_node_decode.sh" in text
        assert "benchmark_decode_fixed_batch.sh" in text
        assert "554,880" in text and "1,442,464" in text
        for value in ("933.75", "931.58", "935.92", "0.47%", "25.7%", "70.0%"):
            assert value in text
        assert "42.9%" in text
        for value in (
            "1,031.26 → 718.12",
            "15.52 → 22.28",
            "743.12 → 933.75",
            "21.53 → 17.14",
            "30.4%",
            "43.6%",
            "20.4%",
        ):
            assert value in text
        assert "53.8%" not in text
        assert text.count("718.12") == 1
        assert "diagnostic_output8k" in text
        assert "20260713-final" in text
        assert (
            "back-to-back" in text
            if path.name == "README.md"
            else "连续执行受控 A/B 测试" in text
        )
        assert "4,112" in text
        assert "fixed-acceptance" in text or "固定接受率" in text
        assert "data/evidence/exact64-fixed-acceptance/" in text
    assert "no output-length column" in readme_texts[0]
    assert "没有输出长度列" in readme_texts[1]
    assert "Decode diagnostic: 8K → 64K context" in readme_texts[0]
    assert "Decode 诊断：采用相同的固定 BS16、输出 8K 方法" in readme_texts[1]

    launch = (ROOT / "scripts/amd-latest/launch_single_node_decode.sh").read_text(
        encoding="utf-8"
    )
    benchmark = (ROOT / "scripts/amd-latest/benchmark_decode_fixed_batch.sh").read_text(
        encoding="utf-8"
    )
    bundle_readme = (ROOT / "scripts/amd-latest/README.md").read_text(encoding="utf-8")
    for flag in (
        "SGLANG_AITER_UNIFIED_VERIFY=1",
        "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1",
    ):
        assert flag in launch
    for value in (
        "--random-input-len 65536",
        "--random-output-len 1024",
        "--num-prompts 16",
        "--max-concurrency 16",
        "Total input tokens:[[:space:]]+1048576",
        "Total generated tokens:[[:space:]]+16384",
        "EXPECTED_RETOKENIZED_TOKENS",
        "Total generated tokens \\(retokenized\\)",
        "module_gemm_a8w8_blockscale_bpreshuffle",
    ):
        assert value in benchmark

    analyzer = subprocess.run(
        ["python3", str(ROOT / "scripts/analyze_exact64_evidence.py")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert analyzer.returncode == 0, analyzer.stderr
    analyzer_result = json.loads(analyzer.stdout)
    assert analyzer_result["status"] == "PASS"
    assert analyzer_result["method_identity"] == "fixed_acceptance_performance_benchmark"
    assert analyzer_result["evidence_scope"] == {
        "independently_recomputes_disclosed_sanitized_windows": True,
        "checks_consistency_with_published_audit": True,
        "proves_private_full_log_provenance_or_completeness": False,
    }
    assert analyzer_result["output_accounting"] == {
        "server_accounted_output_tokens_per_repetition": 16384,
        "retokenized_generated_text_tokens_per_repetition": 4112,
        "definition": "retokenized is tokenizer.encode(generated_text) length",
    }
    assert analyzer_result["aggregate"]["optimized_mean_tok_s"] == 933.75
    assert analyzer_result["aggregate"]["baseline_mean_tok_s"] == 743.12
    assert analyzer_result["aggregate"]["optimized_uplift_pct"] == 25.7
    for value in (
        "Exact 64K/1K Fixed-Batch Decode",
        "REP=1",
        "REP=2",
        "fixed-acceptance performance benchmark",
        "1,048,576 total input tokens",
        "16,384 server-accounted generated tokens",
        "4,112 retokenized generated-text tokens",
        "module_gemm_a8w8_blockscale_bpreshuffle",
        "50% of the median",
        "analyze_exact64_evidence.py",
    ):
        assert value in bundle_readme


def main() -> None:
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError(
            "Validation requires normal Python mode; -O/-OO removes assertion gates."
        )
    parser = argparse.ArgumentParser(
        description="Validate the MiMo-V2.5-Pro MI300X public benchmark repository."
    )
    parser.parse_args()
    checks = (
        ("readmes", check_readmes),
        ("batching_guide", check_batching_guide),
        ("controlled_isl", check_controlled_isl),
        ("result_tables", check_result_tables),
        ("long_context_decode", check_long_context_decode),
        ("fixed_batch_decode", check_fixed_batch_decode),
        ("provenance", check_provenance),
        ("code_and_assets", check_code_and_assets),
        ("public_boundary", check_public_boundary),
    )
    for name, check in checks:
        check()
        print(f"{name}=PASS")
    print("REPO_VALIDATION=PASS")


if __name__ == "__main__":
    main()