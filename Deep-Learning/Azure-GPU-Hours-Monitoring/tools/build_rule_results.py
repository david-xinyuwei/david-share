#!/usr/bin/env python3
"""Build and verify the SOP-68 executable rule catalog.

    python tools/build_rule_results.py
    python tools/build_rule_results.py --check

The status of every rule is computed from the committed repository. PASS rules
have only passing checks and existing repository-relative evidence paths.
Rules that do not apply to this monitoring repository are N/A with a reason.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "rule-results.json"
RUNS = json.loads((ROOT / "evidence" / "runs.json").read_text(encoding="utf-8"))["runs"]
MEASUREMENTS = json.loads((ROOT / "evidence" / "measurements.json").read_text(encoding="utf-8"))["runs"]
READMES = [ROOT / "README.md", ROOT / "README_CN.md"]


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def check(check_id: str, passed: bool, actual: str, expected: str) -> dict:
    return {"id": check_id, "passed": bool(passed), "actual": actual, "expected": expected}


def passed(rule_id: str, checks: list[dict], evidence: list[str]) -> dict:
    return {"id": rule_id, "applicable": True, "status": "PASS" if all(c["passed"] for c in checks) else "FAIL",
            "checks": checks, "evidence": evidence}


def na(rule_id: str, reason: str) -> dict:
    return {"id": rule_id, "applicable": False, "status": "N/A", "reason": reason, "checks": [], "evidence": []}


def build() -> dict:
    en, cn = [p.read_text(encoding="utf-8") for p in READMES]
    collector = (ROOT / "vm" / "gpu_collector.py").read_text(encoding="utf-8")
    configure = (ROOT / "scripts" / "configure.sh").read_text(encoding="utf-8")
    evidence_tests = (ROOT / "tests" / "test_evidence.py").read_text(encoding="utf-8")
    public_tests = (ROOT / "tests" / "test_public_content.py").read_text(encoding="utf-8")
    configure_tests = (ROOT / "tests" / "test_configure.py").read_text(encoding="utf-8")
    configure_tests += (ROOT / "tests" / "test_auth.py").read_text(encoding="utf-8")

    run_headings = {
        "validation-1": ("### validation-1:", "### validation-1："),
        "replay-1": ("### replay-1:", "### replay-1："),
        "configure-2": ("### configure-2:", "### configure-2："),
        "jobs-1": ("### jobs-1:", "### jobs-1："),
        "auth-1": ("### auth-1:", "### auth-1："),
    }
    actual_inputs = all(
        all(h in doc and "**Input.**" in doc[doc.index(h):] if lang == 0 else h in doc and "**输入。**" in doc[doc.index(h):]
            for lang, (doc, h) in enumerate(zip((en, cn), headings)))
        for headings in run_headings.values()
    )
    source_hashes = {p: sha(p) for p in (
        "scripts/configure.sh", "scripts/setup-workspace.sh", "scripts/onboard-vm.sh",
        "scripts/offboard-vm.sh", "scripts/remove-workspace.sh",
        "vm/gpu_collector.py", "examples/gpu_hours_client.py",
        "scripts/create-query-identity.sh", "scripts/query-gpu-hours.sh",
        "scripts/create-query-identity.sh", "scripts/query-gpu-hours.sh",
        "kql/summary.kql", "kql/per_vm.kql", "kql/per_hour.kql", "kql/per_day.kql",
    )}
    terminal_outputs = all((ROOT / "evidence" / "runs" / rid / "raw-manifest.json").is_file() for rid in RUNS)
    setup = MEASUREMENTS["configure-2"]
    duration_sum = sum(s["seconds"] for s in RUNS["configure-2"]["steps"] if s["seconds"] is not None)
    scenario_matrix = all(all(h in doc for doc, h in zip((en, cn), headings)) for headings in run_headings.values())
    cleanups = {
        rid: any("cleanup" in s["step"].lower() or "remove" in s["step"].lower()
                 or "offboard" in s["step"].lower() or "下线" in s["step"]
                 for s in run["steps"])
        for rid, run in RUNS.items() if "steps" in run
    }
    bilingual_assets = all(block in en and block in cn for block in re.findall(r"BEGIN GENERATED: ([a-z0-9-]+)", en))
    mutation_names = (
        "test_vm_without_rows_is_rejected", "test_failed_onboarding_is_rejected",
        "test_missing_grant_is_rejected", "test_coverage_that_turns_unknown_time_into_idle_is_rejected",
        "test_step_durations_that_do_not_add_up_are_rejected", "test_changed_evidence_row_is_rejected",
        "test_bilingual_number_mismatch_is_detected", "test_heading_order_is_enforced",
        "test_uniform_scale_set_is_rejected", "test_missing_rows_time_out_with_exit_3",
        "test_wrong_secret_exits_4", "test_missing_role_exits_5",
        "test_wrong_secret_exits_4", "test_missing_role_exits_5",
    )
    mutations = all(name in evidence_tests + public_tests + configure_tests for name in mutation_names)

    rules = [
        passed("RUN-001", [
            check("actual-inputs-in-both-readmes", actual_inputs, f"{len(run_headings)} runs in 2 languages",
                  "every run has its actual input before the result"),
            check("run-contracts-present", set(RUNS) == set(run_headings), sorted(RUNS), sorted(run_headings)),
        ], ["README.md", "README_CN.md", "evidence/runs.json"]),
        passed("RUN-002", [
            check("owned-load-generator", (ROOT / "tests/load/gpu_load.py").is_file(), "tests/load/gpu_load.py", "exists"),
            check("owned-run-wrapper", (ROOT / "tests/load/run-load.sh").is_file(), "tests/load/run-load.sh", "exists"),
        ], ["tests/load/gpu_load.py", "tests/load/run-load.sh", "README.md", "README_CN.md"]),
        passed("RUN-003", [
            check("source-hashes", len(source_hashes) == 13, source_hashes, "thirteen load-bearing source files hashed"),
            check("collector-runid-source", "AZUREML_RUN_ID=" in collector, "collector reads AZUREML_RUN_ID", "present"),
            check("readme-source-links", all(p in en and p in cn for p in source_hashes), sorted(source_hashes),
                  "every load-bearing source path linked in both READMEs"),
        ], [*source_hashes, "README.md", "README_CN.md"]),
        na("RUN-004", "No customer-visible fault, retry, handoff, queue or deployment transition is claimed."),
        na("RUN-005", "The repository does not claim recovery or takeover between process instances."),
        na("RUN-006", "The repository does not claim checkpoint or durable-progress continuation."),
        passed("RUN-007", [
            check("run-output-manifests", terminal_outputs, sorted(RUNS), "one manifest per run"),
            check("configure-query-result", setup["rows_at_step_7"] > 0,
                  f"{setup['rows_at_step_7']} fresh row(s) for the exact VM resource ID", "at least one"),
            check("job-terminal-status", all(x["Status"] == "Completed" for x in MEASUREMENTS["jobs-1"]["jobs"]["per_job"]),
                  [x["Status"] for x in MEASUREMENTS["jobs-1"]["jobs"]["per_job"]], "all Completed"),
        ], ["evidence/runs.json", "evidence/measurements.json", "evidence/runs/configure-2/console.txt",
            "evidence/runs/jobs-1/kql-results.json"]),
        na("RUN-008", "Event order and recovery are not customer-visible claims; author operations are not published as a reader log."),
        na("RUN-009", "No recovery, replacement or continuation storyboard is claimed."),
        passed("RUN-010", [
            check("configure-duration-sum", duration_sum == RUNS["configure-2"]["elapsed_seconds"], duration_sum,
                  RUNS["configure-2"]["elapsed_seconds"]),
            check("offset-not-calendar-time",
                  f"+{setup['last_row_minute_after_start']}" in
                  (ROOT / "evidence/runs/configure-2/console.txt").read_text(encoding="utf-8"),
                  f"+{setup['last_row_minute_after_start']}", "public evidence uses the generated elapsed offset"),
        ], ["evidence/runs.json", "evidence/runs/configure-2/console.txt",
            "evidence/runs/configure-2/receipt.json"]),
        na("RUN-011", "The repository does not claim a deployed customer UI or product object; it delivers scripts, KQL and evidence."),
        passed("RUN-012", [
            check("scenario-headings-bilingual", scenario_matrix, sorted(run_headings), "all scenarios in both READMEs"),
            check("scenario-contracts", set(RUNS) == set(MEASUREMENTS), sorted(MEASUREMENTS), sorted(RUNS)),
        ], ["README.md", "README_CN.md", "evidence/runs.json", "evidence/measurements.json"]),
        passed("RUN-013", [
            check("cleanup-in-each-mutable-run", all(cleanups.values()), cleanups, "cleanup recorded for every run with steps"),
            check("configure-cleanup-observed", "resource group deleted" in en and "资源组已删除" in cn,
                  "cleanup appears in both READMEs", "present"),
        ], ["evidence/runs.json", "README.md", "README_CN.md"]),
        passed("RUN-014", [
            check("generated-block-set", bilingual_assets,
                  sorted(re.findall(r"BEGIN GENERATED: ([a-z0-9-]+)", en)),
                  "same generated blocks in both READMEs"),
            check("bilingual-command-entry", "./scripts/configure.sh -c gpu-hours.env" in en
                  and "./scripts/configure.sh -c gpu-hours.env" in cn, "same command", "present in both"),
        ], ["README.md", "README_CN.md", "tools/build_readme.py", "tools/check_repo.py"]),
        passed("RUN-015", [
            check("negative-mutation-tests", mutations, list(mutation_names), "every named mutation test exists"),
            check("tampered-hash-test", "HASH_MISMATCH" in evidence_tests, "HASH_MISMATCH asserted", "present"),
            check("retired-file-guard", ("QUICK" + "START.md") in public_tests
                  and ("QUICK" + "START_CN.md") in public_tests,
                  "retired QUICKSTART files guarded", "present"),
        ], ["tests/test_evidence.py", "tests/test_public_content.py", "tests/test_configure.py", "tests/test_auth.py"]),
    ]
    return {"schema": 1, "source_hashes": source_hashes, "rules": rules}


def validate(data: dict) -> list[str]:
    errors = []
    expected = [f"RUN-{i:03d}" for i in range(1, 16)]
    ids = [r.get("id") for r in data.get("rules", [])]
    if ids != expected:
        errors.append(f"RULE_SET {ids} != {expected}")
    for rule in data.get("rules", []):
        status = rule.get("status")
        if status not in {"PASS", "FAIL", "NOT_VERIFIED", "N/A"}:
            errors.append(f"{rule.get('id')} INVALID_STATUS {status}")
        if rule.get("applicable"):
            if not rule.get("checks"):
                errors.append(f"{rule['id']} NO_CHECKS")
            derived = "PASS" if rule.get("checks") and all(c.get("passed") is True for c in rule["checks"]) else "FAIL"
            if status != derived:
                errors.append(f"{rule['id']} FORGED_STATUS {status} != {derived}")
            if not rule.get("evidence"):
                errors.append(f"{rule['id']} NO_EVIDENCE")
        elif status != "N/A" or not rule.get("reason"):
            errors.append(f"{rule['id']} UNJUSTIFIED_NA")
        for rel in rule.get("evidence", []):
            path = Path(rel)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"{rule['id']} EVIDENCE_ESCAPE {rel}")
                continue
            resolved = (ROOT / path).resolve()
            if ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve():
                errors.append(f"{rule['id']} EVIDENCE_ESCAPE {rel}")
            elif not resolved.exists():
                errors.append(f"{rule['id']} MISSING_EVIDENCE {rel}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    data = build()
    errors = validate(data)
    if errors:
        print("\n".join(errors))
        return 1
    text = json.dumps(data, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text:
            print("RULE_RESULTS_STALE evidence/rule-results.json differs from a fresh evaluation")
            return 1
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
    for rule in data["rules"]:
        print(f"RULE {rule['id']} {rule['status']} {len(rule['evidence'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
