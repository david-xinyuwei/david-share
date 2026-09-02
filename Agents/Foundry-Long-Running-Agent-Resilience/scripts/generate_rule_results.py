#!/usr/bin/env python3
"""Evaluate SOP-68 RUN rules from repository evidence and write deterministic results."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any, Callable
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RULE_IDS = tuple(f"RUN-{index:03d}" for index in range(1, 16))
LEGAL_STATUSES = {"PASS", "FAIL", "NOT_VERIFIED", "N/A"}
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)*(?![A-Za-z0-9])")


def read_json(root: Path, relative: str) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative}: JSON root must be an object")
    return value


def read_jsonl(root: Path, relative: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (root / relative).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalized_sha256(path: Path) -> str:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt"}:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def normalized_size(path: Path) -> int:
    content = path.read_bytes()
    if path.suffix.lower() in {".json", ".jsonl", ".md", ".py", ".txt"}:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return len(content)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def check(
    check_id: str,
    passed: bool,
    actual: object,
    expected: object,
) -> dict[str, Any]:
    return {
        "actual": str(actual),
        "expected": str(expected),
        "id": check_id,
        "passed": bool(passed),
    }


def result(
    rule_id: str,
    evidence: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "applicable": True,
        "checks": checks,
        "evidence": evidence,
        "id": rule_id,
        "status": "PASS" if checks and all(item["passed"] for item in checks) else "FAIL",
    }


def find_event(
    events: list[dict[str, Any]],
    event_name: str,
    **expected: Any,
) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in events
            if event.get("event") == event_name
            and all(event.get(key) == value for key, value in expected.items())
        ),
        None,
    )


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(),
        3,
    )


def extract_command_value(command: str, option: str) -> str | None:
    match = re.search(rf"{re.escape(option)}(?:=|\s+)(?:\"([^\"]+)\"|(\S+))", command)
    return (match.group(1) or match.group(2)) if match else None


def source_sections(root: Path) -> tuple[str, ...]:
    source = (
        root
        / "hosted-agent"
        / "src"
        / "lra-evidence-agent"
        / "translation_workload.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SOURCE_SECTIONS"
                for target in node.targets
            )
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
                return value
    raise ValueError("SOURCE_SECTIONS tuple was not found")


def checkpoint_contract_sha256(translations: list[str]) -> str:
    names = [f"translation_section_{index:02d}" for index in range(1, len(translations) + 1)]
    payload = {
        "names": names,
        "result_sha256": sorted(sha256_text(value) for value in translations),
    }
    return sha256_text(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def generated_artifact_matches(
    root: Path,
    artifact: dict[str, Any],
) -> tuple[bool, str]:
    generator = root / artifact["generator"]
    source = root / artifact["input"]
    expected = root / artifact["output"]
    arguments = artifact.get("arguments", [])
    with tempfile.TemporaryDirectory(prefix="lra-rule-artifact-") as temporary:
        actual = Path(temporary) / expected.name
        completed = subprocess.run(
            [
                sys.executable,
                str(generator),
                "--input",
                str(source),
                "--output",
                str(actual),
                *arguments,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        matches = (
            completed.returncode == 0
            and actual.is_file()
            and actual.read_bytes() == expected.read_bytes()
        )
        detail = (
            "byte-identical"
            if matches
            else f"exit={completed.returncode}; stderr={completed.stderr.strip()[:160]}"
        )
        return matches, detail


def fenced_text_blocks(text: str) -> list[str]:
    return re.findall(r"^```text\s*\n(.*?)^```\s*$", text, flags=re.MULTILINE | re.DOTALL)


def heading_levels(text: str) -> list[int]:
    return [len(value) for value in re.findall(r"^(#{1,6})\s+", text, flags=re.MULTILINE)]


def table_shapes(text: str) -> list[tuple[int, int]]:
    shapes: list[tuple[int, int]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        if not line.strip().startswith("|"):
            continue
        separator = lines[index + 1].strip()
        if not separator.startswith("|") or not re.fullmatch(r"[|:\-\s]+", separator):
            continue
        rows = 2
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].strip().startswith("|"):
            rows += 1
            cursor += 1
        shapes.append((line.count("|") - 1, rows))
    return shapes


def fenced_languages(text: str) -> list[str]:
    return re.findall(r"^```([A-Za-z0-9_+-]*)\s*$", text, flags=re.MULTILINE)


def markdown_images(text: str) -> list[str]:
    return re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)


def png_dimensions(path: Path) -> tuple[int, int]:
    content = path.read_bytes()
    if content[:8] != b"\x89PNG\r\n\x1a\n" or content[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", content[16:24])


def evidence_manifest_matches(root: Path) -> bool:
    manifest_path = root / "evidence" / "manifest.json"
    manifest = read_json(root, "evidence/manifest.json")
    entries = {
        item.get("path"): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in (root / "evidence").rglob("*")
        if path.is_file() and path != manifest_path
    }
    return set(entries) == actual_paths and all(
        entries[relative].get("sha256") == normalized_sha256(root / relative)
        and entries[relative].get("bytes") == normalized_size(root / relative)
        for relative in actual_paths
    )


def baseline_rule_document() -> dict[str, Any]:
    return {
        "rules": [
            {
                "applicable": True,
                "checks": [
                    {
                        "actual": "true",
                        "expected": "true",
                        "id": "baseline",
                        "passed": True,
                    }
                ],
                "evidence": ["README.md"],
                "id": rule_id,
                "status": "PASS",
            }
            for rule_id in REQUIRED_RULE_IDS
        ],
        "scenario_type": "measured-runtime-recovery-demo",
        "schema_version": 1,
    }


def rule_mutation_outcomes(
    root: Path,
    run_contract: dict[str, Any],
) -> dict[str, bool]:
    baseline = baseline_rule_document()

    def rejected(mutator: Callable[[dict[str, Any]], None]) -> bool:
        document = json.loads(json.dumps(baseline))
        mutator(document)
        return bool(validate_document(root, document))

    outcomes = {
        "missing_rule": rejected(lambda document: document["rules"].pop()),
        "duplicate_rule": rejected(
            lambda document: document["rules"].__setitem__(
                -1,
                json.loads(json.dumps(document["rules"][0])),
            )
        ),
        "false_applicability": rejected(
            lambda document: document["rules"][0].update(applicable=False)
        ),
        "forged_pass": rejected(
            lambda document: document["rules"][0]["checks"][0].update(passed=False)
        ),
        "escaping_path": rejected(
            lambda document: document["rules"][0]["evidence"].__setitem__(
                0,
                "../README.md",
            )
        ),
        "absolute_path": rejected(
            lambda document: document["rules"][0]["evidence"].__setitem__(
                0,
                str((root / "README.md").resolve()),
            )
        ),
    }

    with tempfile.TemporaryDirectory(prefix="lra-rule-mutations-") as temporary:
        target = Path(temporary) / "repo"
        shutil.copytree(
            root,
            target,
            ignore=shutil.ignore_patterns(
                ".git",
                ".repo-evidence",
                ".demo-state",
                "__pycache__",
                "bin",
                "obj",
            ),
        )
        trace_artifact = next(
            artifact
            for artifact in run_contract["generated_artifacts"]
            if artifact["output"].endswith("-trace.txt")
        )
        trace_path = target / trace_artifact["output"]
        trace_path.write_text(
            trace_path.read_text(encoding="utf-8") + "tampered\n",
            encoding="utf-8",
        )
        matches, _ = generated_artifact_matches(target, trace_artifact)
        outcomes["stale_generated_artifact"] = not matches

        observation_path = target / "evidence" / "observation-validation.json"
        observation_path.write_text(
            observation_path.read_text(encoding="utf-8") + " ",
            encoding="utf-8",
        )
        outcomes["manifest_drift"] = not evidence_manifest_matches(target)
    return outcomes


def evaluate_rules(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    en = (root / "README.md").read_text(encoding="utf-8")
    cn = (root / "README-CN.md").read_text(encoding="utf-8")
    local = read_json(root, "evidence/owned-hosted-agent-translation-local.json")
    live = read_json(root, "evidence/owned-hosted-agent-live-translation.json")
    safe = read_json(root, "evidence/owned-hosted-agent-live.json")
    status = read_json(root, "evidence/owned-hosted-agent-status.json")
    run_contract = read_json(root, "evidence/run-contract.json")
    run_manifest = read_json(
        root,
        "evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json",
    )
    scenario_matrix = read_json(root, "evidence/scenario-matrix.json")
    ui = read_json(root, "evidence/ui-evidence.json")
    observation = read_json(root, "evidence/observation-validation.json")
    local_events = read_jsonl(
        root,
        "evidence/owned-hosted-agent-translation-local-events.jsonl",
    )
    live_events = read_jsonl(
        root,
        "evidence/owned-hosted-agent-live-translation-events.jsonl",
    )
    commands = {
        item["id"]: item
        for item in run_manifest.get("commands", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    primary_command = commands["python-real-translation-hard-process-loss"]["command"]
    payload = extract_command_value(primary_command, "--payload") or ""
    workload = extract_command_value(primary_command, "--workload") or ""
    work_id = extract_command_value(primary_command, "--work-id") or ""
    crash_stage = extract_command_value(primary_command, "--crash-after-stage") or ""
    delay = extract_command_value(primary_command, "--stage-delay-ms") or ""
    svg_text = (root / "images/lra-recovery-timeline.svg").read_text(encoding="utf-8")
    excalidraw_text = (
        root / "images/lra-recovery-timeline.excalidraw"
    ).read_text(encoding="utf-8")

    rules: list[dict[str, Any]] = []
    rules.append(
        result(
            "RUN-001",
            [
                "README.md",
                "evidence/owned-hosted-agent-translation-local.json",
                "images/lra-recovery-timeline.svg",
            ],
            [
                check("workload", workload == local["acceptance"]["workload"], workload, local["acceptance"]["workload"]),
                check("work-id", work_id == local["work_id"], work_id, local["work_id"]),
                check(
                    "payload-hash",
                    sha256_text(payload) == local["acceptance"]["payload_sha256"],
                    sha256_text(payload),
                    local["acceptance"]["payload_sha256"],
                ),
                check("crash-stage", crash_stage == "3", crash_stage, "3"),
                check("stage-delay", delay == "1000", delay, "1000"),
                check(
                    "diagram-request-values",
                    all(
                        token in svg_text
                        for token in (payload, workload, work_id, "crash_after_stage=3", "stage_delay_ms=1000")
                    ),
                    "all request tokens present" if payload in svg_text else "request token missing",
                    "all request tokens present",
                ),
                check(
                    "readme-diagram",
                    "images/lra-recovery-timeline.png" in en
                    and "images/lra-recovery-timeline.png" in cn,
                    "embedded" if "images/lra-recovery-timeline.png" in en else "missing",
                    "embedded in both READMEs",
                ),
            ],
        )
    )

    sections = source_sections(root)
    rules.append(
        result(
            "RUN-002",
            [
                "hosted-agent/src/lra-evidence-agent/translation_workload.py",
                "hosted-agent/src/lra-evidence-agent/main.py",
                "evidence/owned-hosted-agent-live-translation-output.md",
            ],
            [
                check("source-section-count", len(sections) == 12, len(sections), 12),
                check(
                    "live-output-count",
                    len(live["acceptance"]["translated_texts"]) == len(sections),
                    len(live["acceptance"]["translated_texts"]),
                    len(sections),
                ),
                check(
                    "real-translator-call",
                    "_translate_sync" in (root / "hosted-agent/src/lra-evidence-agent/main.py").read_text(encoding="utf-8")
                    and "cognitiveservices.azure.com/.default"
                    in (root / "hosted-agent/src/lra-evidence-agent/main.py").read_text(encoding="utf-8"),
                    "present",
                    "managed-identity Translator call",
                ),
            ],
        )
    )

    code_checks: list[dict[str, Any]] = []
    for requirement in run_contract["code_requirements"]:
        source = (root / requirement["path"]).read_text(encoding="utf-8")
        missing = [token for token in requirement["contains"] if token not in source]
        code_checks.append(
            check(
                f"source:{requirement['path']}",
                not missing,
                ",".join(missing) if missing else "all required tokens",
                "all required tokens",
            )
        )
    rules.append(
        result(
            "RUN-003",
            [
                "README.md",
                "hosted-agent/src/lra-evidence-agent/main.py",
                "hosted-agent/src/lra-evidence-agent/requirements.txt",
                "dotnet-agent/Program.cs",
                "dotnet-agent/LraEvidenceAgent.csproj",
            ],
            code_checks
            + [
                check(
                    "readme-code-links",
                    all(
                        token in en
                        for token in (
                            "ResponsesServerOptions(resilient_background=True)",
                            "context.persisted_response",
                            "yield stream.checkpoint()",
                            "Environment.Exit(86)",
                        )
                    ),
                    "present",
                    "all wiring tokens linked",
                )
            ],
        )
    )

    timeline = local["timeline"]
    checkpoint = find_event(timeline, "checkpoint_committed", checkpoint="translation_section_04")
    fault = find_event(timeline, "fault_injected")
    process_exit = find_event(timeline, "process_exited", process_role="A")
    event_positions = {
        name: timeline.index(event) if event in timeline else -1
        for name, event in (
            ("checkpoint", checkpoint),
            ("fault", fault),
            ("exit", process_exit),
        )
    }
    rules.append(
        result(
            "RUN-004",
            [
                "evidence/owned-hosted-agent-translation-local.json",
                "evidence/owned-hosted-agent-translation-local-events.jsonl",
            ],
            [
                check(
                    "transition-order",
                    0 <= event_positions["checkpoint"] <= event_positions["fault"] < event_positions["exit"],
                    event_positions,
                    "checkpoint <= fault < process exit",
                ),
                check("exit-code", process_exit is not None and process_exit.get("exit_code") == 86, process_exit, "exit_code=86"),
                check("fault-requested", local.get("fault_injection_requested") is True, local.get("fault_injection_requested"), True),
            ],
        )
    )

    local_process_hashes = {
        event.get("process_instance_sha256")
        for event in local_events
        if event.get("process_instance_sha256")
    }
    local_response_hashes = {
        event.get("response_id_sha256")
        for event in local_events
        if event.get("response_id_sha256")
    }
    live_recovered = find_event(live_events, "handler_entered", entry_mode="recovered")
    rules.append(
        result(
            "RUN-005",
            [
                "evidence/owned-hosted-agent-translation-local.json",
                "evidence/owned-hosted-agent-live-translation.json",
                "evidence/owned-hosted-agent-live-translation-events.jsonl",
            ],
            [
                check("same-response-local", local["durable_state"]["same_response_reused"] is True, local["durable_state"]["same_response_reused"], True),
                check("local-process-count", len(local_process_hashes) == 2, len(local_process_hashes), 2),
                check("local-response-count", local_response_hashes == {local["response_id_sha256"]}, local_response_hashes, {local["response_id_sha256"]}),
                check("entry-modes", local["acceptance"]["entry_modes"] == ["fresh", "recovered"], local["acceptance"]["entry_modes"], ["fresh", "recovered"]),
                check("live-process-count", live["acceptance"]["process_instance_count"] == 2, live["acceptance"]["process_instance_count"], 2),
                check(
                    "live-response-correlation",
                    live_recovered is not None
                    and live_recovered.get("response_id_sha256") == live["response_id_sha256"],
                    live_recovered.get("response_id_sha256") if live_recovered else None,
                    live["response_id_sha256"],
                ),
            ],
        )
    )

    first_live_checkpoint = next(
        (
            event
            for event in live_events
            if event.get("event") == "checkpoint_committed"
        ),
        None,
    )
    rules.append(
        result(
            "RUN-006",
            [
                "evidence/owned-hosted-agent-translation-local.json",
                "evidence/owned-hosted-agent-translation-local-trace.txt",
                "evidence/owned-hosted-agent-live-translation-trace.txt",
            ],
            [
                check("local-last-checkpoint", local["durable_state"]["last_checkpoint_before_loss"] == "translation_section_04", local["durable_state"]["last_checkpoint_before_loss"], "translation_section_04"),
                check("local-first-recovered", local["durable_state"]["first_checkpoint_after_recovery"] == "translation_section_05", local["durable_state"]["first_checkpoint_after_recovery"], "translation_section_05"),
                check("all-checkpoints-once", local["acceptance"]["all_expected_checkpoints_completed_once"] is True, local["acceptance"]["all_expected_checkpoints_completed_once"], True),
                check(
                    "live-resume-point",
                    live_recovered is not None
                    and live_recovered.get("resume_from_checkpoint") == "translation_section_05",
                    live_recovered.get("resume_from_checkpoint") if live_recovered else None,
                    "translation_section_05",
                ),
                check(
                    "live-first-recovered-checkpoint",
                    first_live_checkpoint is not None
                    and first_live_checkpoint.get("checkpoint") == "translation_section_05",
                    first_live_checkpoint.get("checkpoint") if first_live_checkpoint else None,
                    "translation_section_05",
                ),
            ],
        )
    )

    translations = live["acceptance"]["translated_texts"]
    translation_artifact = next(
        artifact
        for artifact in run_contract["generated_artifacts"]
        if artifact["output"] == "evidence/owned-hosted-agent-live-translation-output.md"
    )
    translation_matches, translation_detail = generated_artifact_matches(
        root,
        translation_artifact,
    )
    rules.append(
        result(
            "RUN-007",
            [
                "evidence/owned-hosted-agent-live-translation.json",
                "evidence/owned-hosted-agent-live-translation-output.md",
                "scripts/render_translation_result.py",
            ],
            [
                check("terminal-status", live["acceptance"]["status"] == "completed", live["acceptance"]["status"], "completed"),
                check("translation-count", len(translations) == 12, len(translations), 12),
                check("translations-nonempty", all(isinstance(value, str) and value.strip() for value in translations), "all nonempty", "all nonempty"),
                check(
                    "checkpoint-contract-hash",
                    checkpoint_contract_sha256(translations)
                    == live["acceptance"]["checkpoint_contract_sha256"],
                    checkpoint_contract_sha256(translations),
                    live["acceptance"]["checkpoint_contract_sha256"],
                ),
                check("generated-output", translation_matches, translation_detail, "byte-identical"),
            ],
        )
    )

    trace_artifacts = [
        artifact
        for artifact in run_contract["generated_artifacts"]
        if artifact["output"].endswith("-trace.txt")
    ]
    trace_checks: list[dict[str, Any]] = []
    for artifact in trace_artifacts:
        matches, detail = generated_artifact_matches(root, artifact)
        trace_checks.append(
            check(f"generated:{artifact['output']}", matches, detail, "byte-identical")
        )
    en_blocks = fenced_text_blocks(en)
    cn_blocks = fenced_text_blocks(cn)
    expected_traces = [
        (root / relative).read_text(encoding="utf-8")
        for relative in run_contract["readme_traces"]
    ]
    trace_checks.extend(
        [
            check(
                "english-readme-traces",
                [block.strip() + "\n" for block in en_blocks] == expected_traces,
                len(en_blocks),
                len(expected_traces),
            ),
            check(
                "chinese-readme-traces",
                [block.strip() + "\n" for block in cn_blocks] == expected_traces,
                len(cn_blocks),
                len(expected_traces),
            ),
        ]
    )
    rules.append(
        result(
            "RUN-008",
            [
                "evidence/run-contract.json",
                "evidence/owned-hosted-agent-translation-local-trace.txt",
                "evidence/owned-hosted-agent-live-translation-trace.txt",
                "scripts/render_recovery_trace.py",
            ],
            trace_checks,
        )
    )

    excalidraw = json.loads(excalidraw_text)
    excalidraw_visible_text = "\n".join(
        str(element.get("text", ""))
        for element in excalidraw.get("elements", [])
        if isinstance(element, dict) and element.get("type") == "text"
    )
    local_terminal = find_event(timeline, "terminal_observed")
    diagram_tokens = (
        payload,
        "18:25:31.601",
        "os._exit(86)",
        "18:25:45.176",
        "18:25:46.591",
        "completed 18:26:11.276",
        "49.555 s",
    )
    key_hashes = {
        item["path"]: item["sha256"]
        for item in run_manifest["key_code"]
        if isinstance(item, dict)
    }
    diagram_paths = (
        "images/lra-recovery-timeline.png",
        "images/lra-recovery-timeline.svg",
        "images/lra-recovery-timeline.excalidraw",
    )
    rules.append(
        result(
            "RUN-009",
            list(diagram_paths) + ["evidence/run-contract.json"],
            [
                check("png-dimensions", png_dimensions(root / diagram_paths[0]) == (1800, 1120), png_dimensions(root / diagram_paths[0]), (1800, 1120)),
                check("svg-valid", ET.parse(root / diagram_paths[1]) is not None, "valid XML", "valid XML"),
                check("svg-critical-tokens", all(token in svg_text for token in diagram_tokens), "all present", "all present"),
                check("excalidraw-critical-tokens", all(token in excalidraw_visible_text for token in diagram_tokens), "all present", "all present"),
                check(
                    "excalidraw-text-dimensions",
                    all(
                        element.get("width", 0) > 0 and element.get("height", 0) > 0
                        for element in excalidraw.get("elements", [])
                        if isinstance(element, dict) and element.get("type") == "text"
                    ),
                    "all positive",
                    "all positive",
                ),
                check(
                    "diagram-key-hashes",
                    all(
                        key_hashes.get(path) == normalized_sha256(root / path)
                        for path in diagram_paths
                    ),
                    "all match",
                    "all match",
                ),
                check(
                    "terminal-evidence-present",
                    local_terminal is not None and local_terminal.get("status") == "completed",
                    local_terminal.get("status") if local_terminal else None,
                    "completed",
                ),
            ],
        )
    )

    live_polls = live["poll_events"]
    timeout_index = next(
        index
        for index, event in enumerate(live_polls)
        if event.get("kind") == "connection_error"
    )
    poll_before = next(
        event for event in reversed(live_polls[:timeout_index]) if event.get("kind") == "poll"
    )
    poll_after = next(
        event for event in live_polls[timeout_index + 1 :] if event.get("kind") == "poll"
    )
    live_completed = find_event(live_events, "handler_completed")
    live_trace = (
        root / "evidence/owned-hosted-agent-live-translation-trace.txt"
    ).read_text(encoding="utf-8")
    exact_recovery = seconds_between(
        local["milestones"]["process_down_at_utc"],
        local["milestones"]["recovered_entry_at_utc"],
    )
    observation_gap = seconds_between(poll_before["at"], poll_after["at"])
    recovered_to_completed = seconds_between(
        live_recovered["at_utc"],
        live_completed["at_utc"],
    )
    rules.append(
        result(
            "RUN-010",
            [
                "evidence/owned-hosted-agent-translation-local.json",
                "evidence/owned-hosted-agent-live-translation-trace.txt",
                "README.md",
            ],
            [
                check("exact-local-recovery", exact_recovery == local["milestones"]["down_to_recovered_seconds"], exact_recovery, local["milestones"]["down_to_recovered_seconds"]),
                check("hosted-observation-gap", observation_gap == 49.555, observation_gap, 49.555),
                check("hosted-recovered-to-complete", recovered_to_completed == 16.511, recovered_to_completed, 16.511),
                check("exact-down-unavailable", "exact_process_a_down_at=NOT_AVAILABLE" in live_trace, "present", "present"),
                check("gap-not-called-exact-hang", "not_exact_hang" in live_trace and "not an exact hang" in en.lower(), "bounded", "bounded"),
            ],
        )
    )

    ui_checks: list[dict[str, Any]] = []
    for index, asset in enumerate(ui["assets"]):
        published = root / asset["published_path"]
        ui_checks.extend(
            [
                check(f"ui-hash-{index}", normalized_sha256(published) == asset["published_sha256"], normalized_sha256(published), asset["published_sha256"]),
                check(f"ui-version-{index}", f"version {status['version']} is selected" in [claim.lower() for claim in asset["proves"]], asset["proves"], f"version {status['version']} is selected"),
                check(f"ui-nonclaim-{index}", "process-loss recovery behavior" in asset["does_not_prove"], asset["does_not_prove"], "process-loss recovery behavior"),
                check(f"ui-behavior-evidence-{index}", (root / asset["behavior_evidence"]).is_file(), asset["behavior_evidence"], "existing file"),
            ]
        )
    ui_checks.append(
        check(
            "readme-dual-proof-boundary",
            "do not prove process recovery" in en.lower()
            and "不能证明恢复" in cn,
            "present",
            "present in both READMEs",
        )
    )
    rules.append(
        result(
            "RUN-011",
            [
                "evidence/ui-evidence.json",
                "evidence/owned-hosted-agent-status.json",
                "evidence/owned-hosted-agent-live-translation.json",
            ],
            ui_checks,
        )
    )

    scenarios = scenario_matrix["scenarios"]
    scenario_fields_valid = all(
        isinstance(item, dict)
        and item.get("status") in {"PASS", "NOT_VERIFIED"}
        and all(
            isinstance(item.get(field), str) and item.get(field)
            for field in ("id", "trigger", "expected", "actual", "runtime_protocol")
        )
        and isinstance(item.get("evidence"), list)
        and bool(item["evidence"])
        for item in scenarios
    )
    scenario_evidence_valid = all(
        (root / evidence_path).is_file()
        for item in scenarios
        for evidence_path in item.get("evidence", [])
    )
    graceful = next(item for item in scenarios if item["id"] == "graceful-shutdown-handoff")
    rules.append(
        result(
            "RUN-012",
            [
                "evidence/scenario-matrix.json",
                "evidence/owned-hosted-agent-graceful-attempt.json",
            ],
            [
                check("scenario-fields", scenario_fields_valid, scenario_fields_valid, True),
                check("scenario-evidence", scenario_evidence_valid, scenario_evidence_valid, True),
                check("graceful-boundary", graceful["status"] == "NOT_VERIFIED", graceful["status"], "NOT_VERIFIED"),
            ],
        )
    )

    rules.append(
        result(
            "RUN-013",
            [
                "evidence/owned-hosted-agent-status.json",
                "evidence/owned-hosted-agent-live.json",
                "evidence/ui-evidence.json",
            ],
            [
                check("safe-version", safe["deployment"]["version"] == status["version"] == "9", f"{safe['deployment']['version']}/{status['version']}", "9/9"),
                check("safe-content-hash", safe["deployment"]["content_sha256"] == status["content_sha256"], safe["deployment"]["content_sha256"], status["content_sha256"]),
                check("fault-disabled", status["fault_injection_enabled"] is False, status["fault_injection_enabled"], False),
                check("safe-active", status["status"] == "active", status["status"], "active"),
                check("safe-completed", safe["passed"] is True and safe["acceptance"]["status"] == "completed", safe["acceptance"]["status"], "completed"),
                check("safe-one-process", safe["acceptance"]["process_instance_count"] == 1 and safe["acceptance"]["recovery_proven"] is False, safe["acceptance"]["process_instance_count"], 1),
                check("safe-output-count", len(safe["acceptance"]["translated_texts"]) == 12, len(safe["acceptance"]["translated_texts"]), 12),
            ],
        )
    )

    en_numbers = Counter(NUMBER_PATTERN.findall(en))
    cn_numbers = Counter(NUMBER_PATTERN.findall(cn))
    rules.append(
        result(
            "RUN-014",
            ["README.md", "README-CN.md", "scripts/validate_repo.py"],
            [
                check("heading-shape", heading_levels(en) == heading_levels(cn), heading_levels(en), heading_levels(cn)),
                check("table-shape", table_shapes(en) == table_shapes(cn), table_shapes(en), table_shapes(cn)),
                check("code-block-shape", fenced_languages(en) == fenced_languages(cn), fenced_languages(en), fenced_languages(cn)),
                check("image-order", markdown_images(en) == markdown_images(cn), markdown_images(en), markdown_images(cn)),
                check("numeric-drift", en_numbers == cn_numbers, sum((en_numbers - cn_numbers).values()) + sum((cn_numbers - en_numbers).values()), 0),
                check("risk-boundaries", "not an SLA" in en and "不是 SLA" in cn and "NOT VERIFIED" in en and "NOT VERIFIED" in cn, "present", "present"),
            ],
        )
    )

    mutation_outcomes = rule_mutation_outcomes(root, run_contract)
    rules.append(
        result(
            "RUN-015",
            [
                "evidence/observation-validation.json",
                "tests/test_owned_hosted_agent.py",
                "tests/test_rule_results.py",
                "scripts/validate_repo.py",
            ],
            [
                check("observation-negative-evidence", observation.get("passed") is True and all(case.get("matched") for case in observation.get("observation_cases", [])), observation.get("passed"), True),
                *[
                    check(
                        f"mutation:{name}",
                        passed,
                        passed,
                        True,
                    )
                    for name, passed in sorted(mutation_outcomes.items())
                ],
            ],
        )
    )

    return {
        "rules": rules,
        "scenario_type": "measured-runtime-recovery-demo",
        "schema_version": 1,
    }


def secure_evidence_path(root: Path, relative: object) -> tuple[bool, str]:
    if not isinstance(relative, str) or not relative:
        return False, "path must be a non-empty string"
    candidate = Path(relative)
    if candidate.is_absolute():
        return False, "absolute path is forbidden"
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return False, "path escapes repository root"
    if not resolved.is_file():
        return False, "file does not exist"
    return True, "ok"


def validate_document(
    root: Path,
    document: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    rules = document.get("rules")
    if (
        document.get("schema_version") != 1
        or document.get("scenario_type") != "measured-runtime-recovery-demo"
        or not isinstance(rules, list)
    ):
        return ["rule document identity or rule list is invalid"]
    ids = [rule.get("id") for rule in rules if isinstance(rule, dict)]
    if (
        len(ids) != len(rules)
        or len(ids) != len(set(ids))
        or set(ids) != set(REQUIRED_RULE_IDS)
    ):
        errors.append("rule results are missing, duplicated, unknown, or incomplete")
    for rule in rules:
        if not isinstance(rule, dict):
            errors.append("rule result must be an object")
            continue
        rule_id = rule.get("id")
        applicable = rule.get("applicable")
        status = rule.get("status")
        checks = rule.get("checks")
        evidence = rule.get("evidence")
        if applicable is not True:
            errors.append(f"{rule_id}: measured recovery rule must be applicable")
        if status not in LEGAL_STATUSES:
            errors.append(f"{rule_id}: illegal status")
        if not isinstance(checks, list) or not checks:
            errors.append(f"{rule_id}: checks are missing")
            checks = []
        check_ids = [
            item.get("id")
            for item in checks
            if isinstance(item, dict)
        ]
        if len(check_ids) != len(checks) or len(check_ids) != len(set(check_ids)):
            errors.append(f"{rule_id}: checks are invalid or duplicated")
        check_passes: list[bool] = []
        for item in checks:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or not isinstance(item.get("passed"), bool)
                or not isinstance(item.get("actual"), str)
                or not isinstance(item.get("expected"), str)
            ):
                errors.append(f"{rule_id}: check shape is invalid")
                continue
            check_passes.append(item["passed"])
        expected_status = "PASS" if check_passes and all(check_passes) else "FAIL"
        if status != expected_status:
            errors.append(
                f"{rule_id}: status {status!r} does not match computed {expected_status!r}"
            )
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{rule_id}: evidence is missing")
            evidence = []
        for relative in evidence:
            valid, detail = secure_evidence_path(root, relative)
            if not valid:
                errors.append(f"{rule_id}: invalid evidence path {relative!r}: {detail}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "evidence" / "run-contract.json",
        help="Run contract used only to resolve the repository root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "rule-results.json",
    )
    args = parser.parse_args()
    root = args.input.resolve().parents[1]
    results = evaluate_rules(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    errors = validate_document(root, results)
    for rule in results["rules"]:
        print(f"RULE {rule['id']} {rule['status']} {len(rule['evidence'])}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if any(rule["status"] != "PASS" for rule in results["rules"]):
        return 1
    print(f"wrote computed rule results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
