#!/usr/bin/env python3
"""Generate the public evidence integrity manifest."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
MANIFEST = EVIDENCE / "manifest.json"

PROVENANCE = {
    "evidence/README.md": "Maintained evidence index and reproduction commands.",
    "evidence/observation-validation.json": "python scripts/validate_observations.py self-test",
    "evidence/owned-approval-live-events.jsonl": "Client-polled events from hosted-agent-approval/run_approval_recovery.py against lre-approval-gate version 4.",
    "evidence/owned-approval-live-trace.txt": "scripts/render_approval_trace.py from owned-approval-live.json.",
    "evidence/owned-approval-live.json": "Version 4 Foundry review-gate instance-loss run through hosted-agent-approval/run_approval_recovery.py.",
    "evidence/owned-approval-local-events.jsonl": "Client-polled events from hosted-agent-approval/run_approval_recovery.py --local.",
    "evidence/owned-approval-local-trace.txt": "scripts/render_approval_trace.py from owned-approval-local.json.",
    "evidence/owned-approval-local.json": "Local AgentServer review-gate process-loss run through hosted-agent-approval/run_approval_recovery.py --local.",
    "evidence/owned-hosted-agent-dotnet-events.jsonl": "Sanitized .NET AgentServer console lifecycle events.",
    "evidence/owned-hosted-agent-dotnet.json": "Generic recovery runner against the repository-owned .NET Agent.",
    "evidence/owned-hosted-agent-graceful-attempt.json": "Bounded Windows graceful-shutdown attempts and non-claim.",
    "evidence/owned-hosted-agent-live-recovery-events.jsonl": "Sanitized Version 5 recovery-container console events.",
    "evidence/owned-hosted-agent-live-recovery.json": "Version 5 Foundry fault run through hosted-agent/client.py.",
    "evidence/owned-hosted-agent-live-translation-events.jsonl": "Sanitized Version 7 Translator recovery-container console events.",
    "evidence/owned-hosted-agent-live-translation-output.md": "scripts/render_translation_result.py from the Version 7 report.",
    "evidence/owned-hosted-agent-live-translation-trace.txt": "scripts/render_recovery_trace.py from the Version 7 report and recovery-container events.",
    "evidence/owned-hosted-agent-live-translation.json": "Version 7 real Translator S1 Foundry recovery run.",
    "evidence/owned-hosted-agent-live.json": "Version 9 safe Translator S1 Foundry run through hosted-agent/client.py.",
    "evidence/owned-hosted-agent-local-events.jsonl": "Sanitized Python AgentServer console lifecycle events.",
    "evidence/owned-hosted-agent-local.json": "Python hard-loss run through hosted-agent/run_local_recovery.py.",
    "evidence/owned-hosted-agent-local-trace.txt": "scripts/render_recovery_trace.py from owned-hosted-agent-local.json.",
    "evidence/owned-hosted-agent-observer-events.jsonl": "Sanitized observer-restart Agent console events.",
    "evidence/owned-hosted-agent-observer.json": "hosted-agent/run_observer_restart.py",
    "evidence/owned-hosted-agent-status.json": "Sanitized azd ai agent show for safe Version 9.",
    "evidence/owned-hosted-agent-translation-local-events.jsonl": "Sanitized real Translator local recovery lifecycle events.",
    "evidence/owned-hosted-agent-translation-local-trace.txt": "scripts/render_recovery_trace.py from the local Translator report.",
    "evidence/owned-hosted-agent-translation-local.json": "Real Translator S1 hard-loss run through hosted-agent/run_local_recovery.py.",
    "evidence/owned-steering-live-events.jsonl": "Client-observed stream events from hosted-agent-steering/run_steering_recovery.py against lre-steering-agent version 9.",
    "evidence/owned-steering-live-trace.txt": "scripts/render_steering_trace.py from owned-steering-live.json.",
    "evidence/owned-steering-live.json": "Version 9 Foundry crash, recover, then steer run through hosted-agent-steering/run_steering_recovery.py.",
    "evidence/public-sdk-contract.json": "python scripts/verify_public_resilience_api.py --format json",
    "evidence/recovery-contract-demo.json": "python scripts/recovery_contract_demo.py demo",
    "evidence/recovery-contract-events.jsonl": "Structured events from recovery_contract_demo.py.",
    "evidence/resilience-sdk-usage.json": "python examples/resilience_sdk_usage.py --check --format json",
    "evidence/run-contract.json": "Maintained scenario-agnostic complete-run contract.",
    "evidence/rule-results.json": "Executable SOP-68 RUN-001 through RUN-015 rule outcomes and evidence paths.",
    "evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json": "Commands, exits, logs, status, UI, and key-code hashes for this validation cycle.",
    "evidence/scenario-manifest.json": "Maintained authenticity classification and non-claims.",
    "evidence/scenario-matrix.json": "Maintained PASS and NOT_VERIFIED mode matrix.",
    "evidence/steering-order-boundary.json": "Bounded steer-then-crash attempts and non-claim.",
    "evidence/ui-evidence.json": "Visible signed-in Portal captures sanitized into images/product-ui.",
}

NORMALIZED_SUFFIXES = {".json", ".jsonl", ".md", ".py", ".txt"}


def normalized_bytes(path: Path) -> bytes:
    content = path.read_bytes()
    if path.suffix.lower() in NORMALIZED_SUFFIXES:
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return content


def main() -> int:
    paths = sorted(
        path
        for path in EVIDENCE.rglob("*")
        if path.is_file() and path != MANIFEST
    )
    relative_paths = [path.relative_to(ROOT).as_posix() for path in paths]
    unknown = sorted(set(relative_paths) - set(PROVENANCE))
    stale = sorted(set(PROVENANCE) - set(relative_paths))
    if unknown or stale:
        raise SystemExit(
            f"provenance map drift: unknown={unknown}, stale={stale}"
        )
    entries = []
    for path, relative in zip(paths, relative_paths, strict=True):
        content = normalized_bytes(path)
        entries.append(
            {
                "bytes": len(content),
                "path": relative,
                "provenance": PROVENANCE[relative],
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    payload = {
        "algorithm": "sha256",
        "files": entries,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "normalization": "utf-8-lf",
        "schema_version": 1,
    }
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"wrote {len(entries)} evidence hashes to {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
