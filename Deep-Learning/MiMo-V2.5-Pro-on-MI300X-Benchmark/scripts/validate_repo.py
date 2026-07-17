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
    assert len(final_rows) == 9
    assert len(scalability_rows) == 33
    assert len(repeatability_rows) == 4
    readme_texts = [path.read_text(encoding="utf-8") for path in READMES]

    for row in final_rows:
        mi300x = float(row["mi300x_tok_s"])
        concurrency = int(row["mi300x_concurrency"])
        if row["surface"] == "decode":
            h200_bs = int(row["xiaomi_h200_per_dp_bs"])
            h200_tok_s = float(row["xiaomi_h200_per_node_reference_tok_s"])
            h200_tpot = float(row["xiaomi_h200_per_dp_tpot_ms"])
            mi300x_tpot = float(row["mi300x_mean_tpot_ms"])
            assert concurrency == h200_bs
            assert round(mi300x / h200_tok_s * 100, 1) == float(
                row["mi300x_vs_h200_per_node_pct"]
            )
            assert round(mi300x_tpot / h200_tpot, 2) == float(
                row["mi300x_vs_h200_tpot_ratio"]
            )
            throughput_line = (
                f"| {concurrency} | {h200_bs} | **{mi300x:,.2f}** | "
                f"{h200_tok_s:,.0f} | {float(row['mi300x_vs_h200_per_node_pct']):.1f}% |"
            )
            tpot_line = (
                f"| {concurrency} | {h200_bs} | **{mi300x_tpot:.2f}** | "
                f"{h200_tpot:.2f} | {float(row['mi300x_vs_h200_tpot_ratio']):.2f}x |"
            )
            for text in readme_texts:
                assert throughput_line in text
                assert tpot_line in text.replace("×", "x")
        elif row["topology"] == "1P1D":
            h200 = float(row["xiaomi_h200_per_node_reference_tok_s"])
            assert round(mi300x / h200 * 100, 1) == float(row["mi300x_vs_h200_per_node_pct"])
            label = {8192: "8K", 65536: "64K", 262144: "256K"}[int(row["input_tokens"])]
            line = (
                f"| {label} | {concurrency} | **{mi300x:,.2f}** | "
                f"{h200:,.0f} | {float(row['mi300x_vs_h200_per_node_pct']):.1f}% |"
            )
            for text in readme_texts:
                assert line in text
        else:
            label = {8192: "8K", 65536: "64K"}[int(row["input_tokens"])]
            line = f"| {label} | {concurrency} | **{mi300x:,.2f}** |"
            for text in readme_texts:
                assert line in text

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
        label = "Requested 64K" if requested_input == 65536 else "Requested 255K (256K total)"
        line = (
            f"| {label} | 1K | {concurrency} | {prompts} | "
            f"{float(row['output_tok_s']):,.2f} | {float(row['input_tok_s']):,.2f} | {float(row['mean_tpot_ms']):,.2f} | "
            f"{float(row['mean_ttft_ms']):,.2f} |"
        )
        for text in readme_texts:
            assert line in text
    boundary = next(row for row in rows if row["requested_input_tokens"] == "261120")
    assert int(boundary["requested_input_tokens"]) != 262144
    assert int(boundary["requested_input_tokens"]) + int(boundary["output_tokens"]) == 262144

    evidence = load_json(ROOT / "data/validation/decode-long-context-evidence.json")
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
    mi300x_64k = {
        int(row["concurrency"]): row
        for row in rows
        if row["requested_input_tokens"] == "65536"
    }
    for concurrency in (16, 32, 64, 96):
        mi300x_tpot = float(mi300x_64k[concurrency]["mean_tpot_ms"])
        h200_tpot = float(h200_64k[concurrency]["mean_tpot_ms"])
        ratio = mi300x_tpot / h200_tpot
        line = (
            f"| {concurrency} | {mi300x_tpot:.2f} | {h200_tpot:.2f} | "
            f"{ratio:.2f}x |"
        )
        for text in readme_texts:
            assert line in text.replace("×", "x")
        h200_rate = float(h200_64k[concurrency]["output_tok_s"])
        assert math.isclose(
            h200_tpot,
            1000 / (h200_rate / concurrency),
            rel_tol=2e-6,
        )

    for text in readme_texts:
        assert "data/decode-long-context-results.tsv" in text
        assert "data/validation/decode-long-context-evidence.json" in text
        assert "benchmark_decode_long_context.sh" in text
        assert "18,983.91" in text and "27,400" in text and "69.3%" in text
        assert "TPOT / ITL" in text
        assert "TPUT" in text

    english, chinese = readme_texts
    assert "SGLang E2E output tok/s (Prefill-inclusive)" in english
    assert "SGLang E2E output tok/s（包含 Prefill）" in chinese
    assert "No matching customer E2E result" in english
    assert "No H200 ratio or parity claim" in english
    assert "客户无匹配 E2E 结果" in chinese
    assert "不计算 H200 比率" in chinese

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
                float(row["xiaomi_h200_per_node_reference_tok_s"]),
                prefill[int(row["input_tokens"])]["input_tok_s"],
                rel_tol=1e-9,
                abs_tol=1e-6,
            )
        else:
            point = decode[(int(row["input_tokens"]), int(row["xiaomi_h200_per_dp_bs"]))]
            assert math.isclose(
                float(row["xiaomi_h200_per_node_reference_tok_s"]),
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
    assert exact["input_tok_s"] == float(headline_256k["mi300x_tok_s"])
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