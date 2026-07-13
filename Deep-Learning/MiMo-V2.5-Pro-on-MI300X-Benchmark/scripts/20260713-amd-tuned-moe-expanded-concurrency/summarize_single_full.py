#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPECTED_CONTEXT_LENGTH = 262151
MIN_MAX_REQ_INPUT_LEN = 262145
CORE_DECODE_CONCURRENCIES = (16, 32, 64, 128)
DECODE_CONCURRENCIES = (8, 16, 32, 64, 96, 128, 192, 256)
PREFILL_INPUTS = (8192, 65536, 262144)
PREFILL_CONCURRENCIES = (1, 2, 4, 8)
DP2_CONCURRENCIES = (1, 2, 4, 8, 16)

PATTERNS = {
    "successful_requests": r"Successful requests:\s+([0-9]+)",
    "input_tok_s": r"Input token throughput \(tok/s\):\s+([0-9.]+)",
    "output_tok_s": r"Output token throughput \(tok/s\):\s+([0-9.]+)",
    "mean_ttft_ms": r"Mean TTFT \(ms\):\s+([0-9.]+)",
    "median_ttft_ms": r"Median TTFT \(ms\):\s+([0-9.]+)",
    "p99_ttft_ms": r"P99 TTFT \(ms\):\s+([0-9.]+)",
    "mean_tpot_ms": r"Mean TPOT \(ms\):\s+([0-9.]+)",
    "median_tpot_ms": r"Median TPOT \(ms\):\s+([0-9.]+)",
    "p99_tpot_ms": r"P99 TPOT \(ms\):\s+([0-9.]+)",
}

CLIENT_FATAL_RE = re.compile(
    r"Traceback|ClientPayloadError|No available .*worker|TimedOut|Exception:|"
    r"Failed requests:\s+[1-9]",
    re.IGNORECASE,
)
SERVICE_FATAL_RE = re.compile(
    r"Traceback \(most recent call last\)|OutOfMemoryError|ClientPayloadError|"
    r"No available .*worker|Engine is dead|Segmentation fault|"
    r"Memory access fault|HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION|"
    r"Fatal Python error|"
    r"longer than the model['’]s context length|exceeds the maximum allowed length|"
    r"Health check failed|_watchdog_thread",
    re.IGNORECASE,
)


def extract(text: str, key: str) -> float | int | None:
    match = re.search(PATTERNS[key], text)
    if not match:
        return None
    return int(match.group(1)) if key == "successful_requests" else float(match.group(1))


def expected_points() -> list[tuple[str, int, int, int]]:
    points = [("decode", 8192, 1024, concurrency) for concurrency in DECODE_CONCURRENCIES]
    points.extend(
        ("prefill", input_tokens, 1, concurrency)
        for input_tokens in PREFILL_INPUTS
        for concurrency in PREFILL_CONCURRENCIES
    )
    points.extend(
        ("dp2", input_tokens, 1, concurrency)
        for input_tokens in PREFILL_INPUTS
        for concurrency in DP2_CONCURRENCIES
    )
    return points


def parse_distribution(path: Path) -> tuple[list[dict], bool]:
    if not path.exists():
        return [], False
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        worker, before, after, delta = line.split("\t")
        rows.append(
            {
                "worker": worker,
                "before": int(before),
                "after": int(after),
                "delta": int(delta),
            }
        )
    return (
        rows,
        len(rows) == 2
        and all(row["delta"] > 0 for row in rows)
        and sum(row["delta"] for row in rows) == 33,
    )


def parse_point(
    root: Path,
    point: tuple[str, int, int, int],
    rejected_points: dict[tuple[str, int, int, int], str],
) -> dict:
    phase, input_tokens, output_tokens, concurrency = point
    log_path = root / "rep-1" / phase / (
        f"benchmark_{input_tokens}_out{output_tokens}_con{concurrency}.log"
    )
    rc_path = log_path.with_suffix(".rc")
    context_path = log_path.with_suffix(".context_length")
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    rc = int(rc_path.read_text().strip()) if rc_path.exists() else None
    context_length = int(context_path.read_text().strip()) if context_path.exists() else None
    expected_success = 256 if phase == "decode" else 16 if phase == "prefill" else 32
    throughput_key = "output_tok_s" if phase == "decode" else "input_tok_s"
    distribution, distribution_valid = parse_distribution(
        log_path.with_suffix(".distribution.tsv")
    )

    reasons = []
    if not log_path.exists():
        reasons.append("missing client log")
    if rc != 0:
        reasons.append(f"rc={rc}")
    if extract(text, "successful_requests") != expected_success:
        reasons.append("unexpected successful-request count")
    if extract(text, throughput_key) is None:
        reasons.append(f"missing {throughput_key}")
    if CLIENT_FATAL_RE.search(text):
        reasons.append("client fatal marker")
    if context_length != EXPECTED_CONTEXT_LENGTH:
        reasons.append(f"context_length={context_length}")
    if phase == "dp2" and not distribution_valid:
        reasons.append("invalid two-worker distribution")
    if point in rejected_points:
        reasons.append(rejected_points[point])

    row = {
        "phase": phase,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "concurrency": concurrency,
        "expected_successful_requests": expected_success,
        "rc": rc,
        "context_length": context_length,
        "accepted": not reasons,
        "rejection_reasons": reasons,
        "log": str(log_path.relative_to(root)),
        "distribution": distribution,
        "distribution_valid": distribution_valid if phase == "dp2" else None,
    }
    for key in PATTERNS:
        row[key] = extract(text, key)
    return row


def check_service(
    log_path: Path,
    server_info_path: Path | None,
    name: str,
    requires_tuned_config: bool = True,
) -> dict:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if server_info_path is None:
        server_info = {}
        server_info_exists = False
    else:
        try:
            server_info = json.loads(server_info_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            server_info = {}
        server_info_exists = server_info_path.exists()
    context_length = server_info.get("context_length")
    max_req_input_len = server_info.get("max_req_input_len")
    tuned_config_loaded = "mimo_v2_5_pro_b16_tuned_fmoe.csv" in text
    return {
        "service": name,
        "_log_path": str(log_path.resolve()),
        "log_exists": log_path.exists(),
        "server_info_required": server_info_path is not None,
        "server_info_exists": server_info_exists,
        "context_length": context_length,
        "max_req_input_len": max_req_input_len,
        "capacity_valid": server_info_path is None
        or (
            context_length == EXPECTED_CONTEXT_LENGTH
            and isinstance(max_req_input_len, int)
            and max_req_input_len >= MIN_MAX_REQ_INPUT_LEN
        ),
        "fatal_count": len(SERVICE_FATAL_RE.findall(text)),
        "tuned_config_required": requires_tuned_config,
        "tuned_config_loaded": tuned_config_loaded,
        "tuned_config_valid": not requires_tuned_config or tuned_config_loaded,
    }


def service_checks(node0_root: Path, node1_root: Path) -> list[dict]:
    checks = [
        check_service(
            node0_root / "rep-1/onep/service/prefill_outer.log",
            node0_root / "rep-1/onep/service/prefill_server_info.json",
            "onep_prefill",
        ),
        check_service(
            node1_root / "rep-1/onep/service/decode_outer.log",
            node1_root / "rep-1/onep/service/decode_server_info.json",
            "onep_decode",
        ),
        check_service(
            node0_root / "rep-1/onep/service/router_outer.log",
            None,
            "onep_router",
            requires_tuned_config=False,
        ),
        check_service(
            node0_root / "rep-1/dp2/service/node0_outer.log",
            node0_root / "rep-1/dp2/service/node0_server_info.json",
            "dp2_node0",
        ),
        check_service(
            node1_root / "rep-1/dp2/service/node1_outer.log",
            node1_root / "rep-1/dp2/service/node1_server_info.json",
            "dp2_node1",
        ),
        check_service(
            node0_root / "rep-1/dp2/service/router_outer.log",
            None,
            "dp2_router",
            requires_tuned_config=False,
        ),
    ]
    return checks


def compare_core_decode(points: list[dict], prior_results: Path) -> list[dict]:
    prior = json.loads(prior_results.read_text(encoding="utf-8"))
    prior_by_concurrency = {int(row["concurrency"]): row for row in prior["decode"]}
    current_by_concurrency = {
        int(row["concurrency"]): row
        for row in points
        if row["phase"] == "decode"
    }
    comparisons = []
    for concurrency in CORE_DECODE_CONCURRENCIES:
        old = prior_by_concurrency[concurrency]
        new = current_by_concurrency[concurrency]
        comparisons.append(
            {
                "concurrency": concurrency,
                "prior_output_tok_s": old["output_tok_s"],
                "current_output_tok_s": new["output_tok_s"],
                "output_delta_pct": (new["output_tok_s"] / old["output_tok_s"] - 1) * 100,
                "prior_mean_tpot_ms": old["mean_tpot_ms"],
                "current_mean_tpot_ms": new["mean_tpot_ms"],
                "mean_tpot_delta_pct": (new["mean_tpot_ms"] / old["mean_tpot_ms"] - 1) * 100,
                "fresh_service_runs": 2,
            }
        )
    return comparisons


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def parse_point_key(value: str) -> tuple[str, int, int, int]:
    try:
        phase, input_tokens, output_tokens, concurrency = value.split(":")
        point = (phase, int(input_tokens), int(output_tokens), int(concurrency))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use phase:input:output:concurrency"
        ) from error
    if point not in expected_points():
        raise argparse.ArgumentTypeError(f"Point is outside the 35-point matrix: {point}")
    return point


def parse_rejected_point(value: str) -> tuple[tuple[str, int, int, int], str]:
    try:
        point_text, reason = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use phase:input:output:concurrency=reason"
        ) from error
    point = parse_point_key(point_text)
    if not reason.strip():
        raise argparse.ArgumentTypeError("Rejection reason cannot be empty")
    return point, reason.strip()


def parse_rejection_evidence(
    value: str,
) -> tuple[tuple[str, int, int, int], Path]:
    try:
        point_text, path_text = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use phase:input:output:concurrency=/path/to/fatal.log"
        ) from error
    point = parse_point_key(point_text)
    if not path_text.strip():
        raise argparse.ArgumentTypeError("Rejection evidence path cannot be empty")
    return point, Path(path_text.strip()).resolve()


def parse_observed_failure(value: str) -> tuple[str, Path]:
    try:
        failure_id, path_text = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use failure-id=/path/to/fatal.log") from error
    failure_id = failure_id.strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", failure_id):
        raise argparse.ArgumentTypeError(
            "Failure ID must contain only lowercase letters, digits, underscores, or hyphens"
        )
    if not path_text.strip():
        raise argparse.ArgumentTypeError("Observed failure evidence path cannot be empty")
    return failure_id, Path(path_text.strip()).resolve()


def portable_evidence_path(path: Path, node0_root: Path, node1_root: Path) -> str:
    resolved_path = path.resolve()
    for label, root in (("remote-node0", node0_root), ("remote-node1", node1_root)):
        try:
            relative_path = resolved_path.relative_to(root.resolve())
        except ValueError:
            continue
        return f"{label}/{relative_path.as_posix()}"
    return resolved_path.name


def render(payload: dict) -> str:
    points = payload["points"]
    sections = [
        "# AMD Tuned Fused-MoE Single Full Reproduction",
        "",
        "One complete expanded matrix was requested and executed. This report does not claim full-matrix N=3 or CV.",
        "",
        "## Decode 8K/1K",
        "",
    ]
    decode_rows = []
    for row in (item for item in points if item["phase"] == "decode"):
        decode_rows.append(
            [
                str(row["concurrency"]),
                str(row["successful_requests"]),
                f"{row['output_tok_s']:.2f}",
                f"{row['mean_tpot_ms']:.2f}",
                f"{row['mean_ttft_ms']:.2f}",
                "ACCEPTED" if row["accepted"] else "REJECTED",
            ]
        )
    sections.extend(
        [
            markdown_table(
                ["Concurrency", "Success", "Output tok/s", "Mean TPOT ms", "Mean TTFT ms", "Status"],
                decode_rows,
            ),
            "",
            "## Core Decode Fresh-Service Repeatability",
            "",
        ]
    )
    repeat_rows = [
        [
            str(row["concurrency"]),
            f"{row['prior_output_tok_s']:.2f}",
            f"{row['current_output_tok_s']:.2f}",
            f"{row['output_delta_pct']:+.2f}%",
            f"{row['mean_tpot_delta_pct']:+.2f}%",
        ]
        for row in payload["core_decode_repeatability"]
    ]
    sections.extend(
        [
            markdown_table(
                ["Concurrency", "Fresh run 1 tok/s", "Fresh run 2 tok/s", "Throughput delta", "Mean TPOT delta"],
                repeat_rows,
            ),
            "",
        ]
    )
    for phase, title in (("prefill", "1P1D Prefill"), ("dp2", "DP=2 Prefill")):
        rows = []
        for row in (item for item in points if item["phase"] == phase):
            deltas = ""
            if phase == "dp2":
                deltas = "/".join(str(item["delta"]) for item in row["distribution"])
            rows.append(
                [
                    str(row["input_tokens"]),
                    str(row["concurrency"]),
                    str(row["successful_requests"]),
                    f"{row['input_tok_s']:.2f}",
                    deltas,
                    "ACCEPTED" if row["accepted"] else "REJECTED",
                ]
            )
        sections.extend(
            [
                f"## {title}",
                "",
                markdown_table(
                    ["Input", "Concurrency", "Success", "Input tok/s", "Worker request deltas", "Status"],
                    rows,
                ),
                "",
            ]
        )
    sections.extend(
        [
            "## Acceptance Summary",
            "",
            f"- Matrix points: {payload['matrix_points']}",
            f"- Accepted points: {payload['accepted_points']}",
            f"- Rejected points: {payload['rejected_points']}",
            "- DP=2 is prefill-only capacity and is not 2P1D end-to-end throughput.",
            "",
        ]
    )
    if payload["observed_failed_attempts"]:
        sections.extend(["## Observed Failed Attempts", ""])
        for failure in payload["observed_failed_attempts"]:
            sections.append(
                f"- `{failure['id']}`: {len(failure['evidence'])} archived service logs "
                "contain hard-fail markers. A successful fresh-service retry does not erase "
                "this robustness incident."
            )
        sections.append("")
    for row in (item for item in points if not item["accepted"]):
        sections.append(
            "- Rejected boundary "
            f"{row['phase']}:{row['input_tokens']}:{row['output_tokens']}:{row['concurrency']}: "
            + "; ".join(row["rejection_reasons"])
        )
    sections.append("")
    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("node0_root", type=Path)
    parser.add_argument("--node1-root", type=Path, required=True)
    parser.add_argument("--prior-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--reject-point",
        action="append",
        type=parse_rejected_point,
        default=[],
        metavar="PHASE:INPUT:OUTPUT:CONCURRENCY=REASON",
    )
    parser.add_argument(
        "--rejection-evidence",
        action="append",
        type=parse_rejection_evidence,
        default=[],
        metavar="PHASE:INPUT:OUTPUT:CONCURRENCY=PATH",
        help="Unique external fatal log bound to one manually rejected point",
    )
    parser.add_argument(
        "--observed-failure",
        action="append",
        type=parse_observed_failure,
        default=[],
        metavar="FAILURE-ID=PATH",
        help="Archived fatal log for an observed failed attempt; repeat the ID for multiple nodes",
    )
    args = parser.parse_args()

    rejected_points = dict(args.reject_point)
    if len(rejected_points) != len(args.reject_point):
        raise SystemExit("Duplicate --reject-point entries")
    rejection_evidence: dict[tuple[str, int, int, int], list[Path]] = {}
    for point, path in args.rejection_evidence:
        rejection_evidence.setdefault(point, []).append(path)
    if set(rejection_evidence) != set(rejected_points):
        raise SystemExit(
            "--reject-point and --rejection-evidence must name the same points"
        )
    rejection_evidence_paths = [
        path for paths in rejection_evidence.values() for path in paths
    ]
    if not all(path.is_file() for path in rejection_evidence_paths):
        raise SystemExit("Each rejected point requires an existing evidence log")
    evidence_identities = [
        (path.stat().st_dev, path.stat().st_ino)
        for path in rejection_evidence_paths
    ]
    if len(set(evidence_identities)) != len(evidence_identities):
        raise SystemExit(
            "Each rejected point requires a unique physical evidence log"
        )
    observed_failure_paths = [path for _, path in args.observed_failure]
    if not all(path.is_file() for path in observed_failure_paths):
        raise SystemExit("Each observed failure requires an existing evidence log")
    observed_identities = [
        (path.stat().st_dev, path.stat().st_ino) for path in observed_failure_paths
    ]
    if len(set(observed_identities)) != len(observed_identities):
        raise SystemExit("Observed failure evidence must use unique physical logs")
    observed_failures_valid = all(
        SERVICE_FATAL_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        for path in observed_failure_paths
    )
    grouped_observed_failures: dict[str, list[Path]] = {}
    for failure_id, path in args.observed_failure:
        grouped_observed_failures.setdefault(failure_id, []).append(path)
    points = [
        parse_point(args.node0_root, point, rejected_points)
        for point in expected_points()
    ]
    checks = service_checks(args.node0_root, args.node1_root)
    service_base_valid = all(
        check["log_exists"]
        and check["capacity_valid"]
        and check["tuned_config_valid"]
        for check in checks
    )
    current_services_valid = service_base_valid and all(
        check["fatal_count"] == 0 for check in checks
    )
    rejection_evidence_identities = {
        (path.stat().st_dev, path.stat().st_ino) for path in rejection_evidence_paths
    }
    unaccounted_service_failures = []
    for check in checks:
        if check["fatal_count"] == 0:
            continue
        log_path = Path(check["_log_path"])
        if (log_path.stat().st_dev, log_path.stat().st_ino) not in rejection_evidence_identities:
            unaccounted_service_failures.append(check["service"])
    service_evidence_accounted = service_base_valid and not unaccounted_service_failures
    for check in checks:
        del check["_log_path"]
    boundary_valid = all(
        SERVICE_FATAL_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        for path in rejection_evidence_paths
    )
    core_repeatability = compare_core_decode(points, args.prior_results)
    accepted_points = sum(row["accepted"] for row in points)
    payload = {
        "run_id": args.run_id,
        "scope": "one complete expanded matrix",
        "expanded_matrix_repetitions": 1,
        "matrix_points": len(points),
        "accepted_points": accepted_points,
        "rejected_points": len(points) - accepted_points,
        "overall_status": (
            "accepted_with_rejected_boundaries" if rejected_points else "accepted"
        ),
        "points": points,
        "core_decode_repeatability": core_repeatability,
        "service_checks": checks,
        "current_services_valid": current_services_valid,
        "service_evidence_accounted": service_evidence_accounted,
        "unaccounted_service_failures": unaccounted_service_failures,
        "external_rejection_evidence_valid": boundary_valid,
        "rejection_evidence": {
            ":".join(map(str, point)): [
                portable_evidence_path(path, args.node0_root, args.node1_root)
                for path in paths
            ]
            for point, paths in rejection_evidence.items()
        },
        "rejection_evidence_sha256": {
            ":".join(map(str, point)): [
                hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
            ]
            for point, paths in rejection_evidence.items()
        },
        "observed_failed_attempts_count": len(grouped_observed_failures),
        "observed_failures_valid": observed_failures_valid,
        "observed_failed_attempts": [
            {
                "id": failure_id,
                "evidence": [
                    {
                        "path": portable_evidence_path(
                            path, args.node0_root, args.node1_root
                        ),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in paths
                ],
            }
            for failure_id, paths in sorted(grouped_observed_failures.items())
        ],
    }

    if len(points) != 35:
        raise SystemExit(f"Expected 35 points, found {len(points)}")
    if not service_evidence_accounted:
        raise SystemExit(
            "Current service evidence has missing capacity/tuning proof or unbound fatal markers"
        )
    if rejected_points and not boundary_valid:
        raise SystemExit("External rejection evidence is missing or has no fatal marker")
    if observed_failure_paths and not observed_failures_valid:
        raise SystemExit("Observed failure evidence has no hard-fail marker")
    expected_accepted = len(points) - len(rejected_points)
    if accepted_points != expected_accepted:
        raise SystemExit(
            f"Expected {expected_accepted} accepted points, got {accepted_points}"
        )

    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "results.json"
    markdown_path = args.output / "RESULTS.md"
    json_tmp = args.output / ".results.json.tmp"
    markdown_tmp = args.output / ".RESULTS.md.tmp"
    json_tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_tmp.write_text(render(payload), encoding="utf-8")
    json_tmp.replace(json_path)
    markdown_tmp.replace(markdown_path)


if __name__ == "__main__":
    main()