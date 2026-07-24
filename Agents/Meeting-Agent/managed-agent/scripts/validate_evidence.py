"""Validate redacted Managed Agent, Skill, and artifact evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    agent = json.loads((ROOT / "evidence-managed-agent.json").read_text(encoding="utf-8"))
    definition = agent["agent"]
    assert definition == {
        "name": "managed-meeting-agent",
        "version": "2",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-oss-120b",
        "tool_count": 1,
        "protocols": ["responses"],
        "authentication": ["Entra"],
    }
    assert agent["validation"]["assertions_passed"] is True
    assert agent["validation"]["identities_and_tenant_urls_redacted"] is True

    skill = json.loads(
        (ROOT / "evidence" / "managed-live" / "toolbox-skill-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert skill["uri"] == "skill://meeting-package/SKILL.md"
    assert len(skill["raw_crlf_sha256"]) == 64
    assert len(skill["canonical_lf_sha256"]) == 64
    assert skill["cloud_matches_local_at_validation_time"] is True
    assert skill["canonical_text_matches_public_v2_source"] is True
    canonical_skill = ROOT / "skills" / "meeting-package" / "SKILL.md"
    packaged_skill = ROOT / "src" / "meeting_agent" / "skills" / "meeting-package" / "SKILL.md"
    assert canonical_skill.read_bytes() == packaged_skill.read_bytes()
    canonical_text = canonical_skill.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert hashlib.sha256(canonical_text.encode()).hexdigest() == skill[
        "canonical_lf_sha256"
    ]

    scenarios = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))
    assert scenarios["scenarios"]["windows-managed-runtime"]["fallback"] is False
    assert scenarios["scenarios"]["browser-contract-e2e"]["type"] == "test-fixture"
    assert scenarios["scenarios"]["browser-live-e2e"]["requires_explicit_mode"] is True

    parity = json.loads(
        (ROOT / "evidence" / "managed-live" / "parity-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert parity["baseline_commit"] == "667357dac6ee2dc30102d572c458c77861112bea"
    assert len(parity["entries"]) == 8
    for entry in parity["entries"]:
        managed_relative = entry["managed_path"].removeprefix(
            "Agents/Meeting-Agent/managed-agent/"
        )
        managed_path = ROOT / managed_relative
        assert hashlib.sha256(managed_path.read_bytes()).hexdigest() == entry["sha256"]

    artifacts = json.loads(
        (ROOT / "evidence" / "managed-live" / "artifact-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert artifacts["cross_input_analysis_differs"] is True
    runs = artifacts["runs"]
    assert set(runs) == {"live-product-planning", "live-operations-review"}
    assert len({run["analysis_sha256"] for run in runs.values()}) == 2
    for run in runs.values():
        assert run["png"]["format"] == "PNG"
        assert run["png"]["size"] == [1280, 720]
        assert run["png"]["bytes"] > 10_000
        assert run["pptx"]["slides"] == 6
        assert run["pptx"]["all_slides_have_text"] is True
        assert run["eml"] == {
            "x_unsent": "1",
            "recipient_count": 0,
            "attachments": ["mind-map.png", "meeting-summary.pptx"],
            "bytes": run["eml"]["bytes"],
        }
        assert run["eml"]["bytes"] > 50_000
    live_ui = json.loads(
        (ROOT / "evidence" / "managed-live" / "ui-live-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert live_ui["runtime"] == {
        "agent": "managed-meeting-agent",
        "version": "2",
        "authentication": "Entra",
        "fixture": False,
    }
    assert live_ui["playwright"]["result"] == "passed"
    assert live_ui["playwright"]["unexpected"] == 0
    assert live_ui["resource_identifiers"] == "redacted; public alias used"

    deployment = json.loads(
        (
            ROOT
            / "evidence"
            / "managed-live"
            / "public-v2-deployment-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert deployment["agent"] == {
        "name": "managed-meeting-agent",
        "version": "2",
        "authentication": "Entra",
    }
    assert deployment["source_commit_under_test"] == (
        "f34c1a8e3ccf1c2f46a6e5901399a79d6d27fcd8"
    )
    assert deployment["cross_input_analysis_differs"] is True
    assert deployment["automatic_send"] is False
    assert len({run["analysis_sha256"] for run in deployment["runs"].values()}) == 2
    for run in deployment["runs"].values():
        assert run["png"]["format"] == "PNG"
        assert run["png"]["size"] == [1280, 720]
        assert run["pptx"]["slides"] == 6
        assert run["pptx"]["all_slides_have_text"] is True
        assert run["eml"]["x_unsent"] == "1"
        assert run["eml"]["to_count"] == 0
        assert run["eml"]["attachments"] == [
            "mind-map.png",
            "meeting-summary.pptx",
        ]

    agent_reference = json.loads(
        (
            ROOT
            / "evidence"
            / "managed-live"
            / "public-v2-agent-reference-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert agent_reference["agent_reference_validated"] == {
        "name": "managed-meeting-agent",
        "version": "2",
    }
    assert agent_reference["stream_delta_count"] > 0
    assert agent_reference["stream_text_chars"] > 0
    assert agent_reference["response_id_present"] is True
    print("PASS: Managed Agent cloud, Skill, and cross-input artifact evidence is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
