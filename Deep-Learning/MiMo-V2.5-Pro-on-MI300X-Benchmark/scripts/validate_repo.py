#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "README-CN.md")


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
    for path in READMES:
        text = path.read_text(encoding="utf-8")
        assert text.count("```") % 2 == 0, f"Unclosed code fence: {path}"
        headings = re.findall(r"^#{1,6} ", text, re.MULTILINE)
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
            "not a strict apples-to-apples" if path.name == "README.md" else "不是严格 apples-to-apples",
            "--password-stdin",
            "validate_server_info.py",
            "validate_service_logs.py",
            "validate_exact_256k.py",
            "write_distribution.py",
        ):
            assert required in text, f"Missing README requirement in {path.name}: {required}"
    assert shapes[0] == shapes[1], f"Bilingual README structure mismatch: {shapes}"


def check_result_tables() -> None:
    final_rows = load_tsv(ROOT / "data/final-results.tsv")
    scalability_rows = load_tsv(ROOT / "data/scalability-results.tsv")
    repeatability_rows = load_tsv(ROOT / "data/decode-repeatability.tsv")
    decode_audit = load_json(ROOT / "data/validation/decode-service-log-audit-8k.json")
    assert len(final_rows) == 9
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
            label = {8192: "8K", 65536: "64K", 262144: "Nominal 256K"}[
                int(row["input_tokens"])
            ]
            line = f"| {label} | {concurrency} | {throughput:,.2f} | {ttft:,.2f} |"
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
    assert evidence["runtime"]["runtime_image"] == image["immutable_pull_ref"]
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
    assert h200["revalidated_at"] == "2026-07-17"
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
    assert "all 64K output points are reported with no hardware ratio" in english
    assert "全部 64K output 点" in chinese and "不计算硬件比率" in chinese
    assert "A strict NVIDIA comparison requires" in english
    assert "要做严格 NVIDIA 对比" in chinese
    assert "actual D-node batch" in english
    assert "实际 D batch" in chinese
    assert "four 8-GPU nodes, 32 GPUs total" in english
    assert "4 台 8-GPU 节点，共 32 张 GPU" in chinese

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
    assert runtime["runtime_image"] == image["immutable_pull_ref"]
    assert runtime["runtime_image_id"] == image["image_id"]
    assert int(runtime["runtime_image_layers"]) == image["layer_count"] == 37
    assert runtime["sglang_source_head"] == image["sglang_commit"]
    assert runtime["aiter_source_head"] == image["aiter_commit"]
    assert runtime["tuned_csv_sha256"] == image["tuned_csv_sha256"]
    assert image["clean_docker_pull_verified"] is True
    assert image["runtime_manifest_verified"] is True
    assert image["tag_write_enabled"] is False
    assert image["tag_delete_enabled"] is False

    exact = load_json(ROOT / "data/validation/exact-token-256k.json")
    headline_256k = next(
        row
        for row in final_rows
        if row["topology"] == "1P1D"
        and row["surface"] == "prefill"
        and row["input_tokens"] == "262144"
    )
    assert exact["status"] == "VALIDATED"
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the MiMo-V2.5-Pro MI300X public benchmark repository."
    )
    parser.parse_args()
    checks = (
        ("readmes", check_readmes),
        ("result_tables", check_result_tables),
        ("long_context_decode", check_long_context_decode),
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