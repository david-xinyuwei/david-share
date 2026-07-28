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
        "version": "9",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-5.4",
        "tool_count": 1,
        "protocols": ["responses"],
        "authentication": ["Entra"],
    }
    assert agent["validation"]["assertions_passed"] is True
    assert agent["validation"]["identities_and_tenant_urls_redacted"] is True
    assert agent["validation"]["source_hash_manifest"] == (
        "evidence/managed-live-gpt54/presentation-skill-v9-validation.json"
    )

    presentation_v9 = json.loads(
        (
            ROOT
            / "evidence"
            / "managed-live-gpt54"
            / "presentation-skill-v9-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert presentation_v9["agent"] == {
        "name": "managed-meeting-agent",
        "version": "9",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-5.4",
        "authentication": "Entra",
    }
    assert presentation_v9["presentation_skill"]["version"] == "3"
    assert presentation_v9["presentation_skill"]["package_files"] == [
        "SKILL.md",
        "references/deck-contract.yaml",
        "assets/presentation-style.yaml",
    ]
    assert presentation_v9["toolbox"]["version"] == "5"
    assert presentation_v9["strict_response"]["deck_plan_authored_by_agent"] is True
    assert presentation_v9["live_browser_json_e2e"]["status"] == "passed"
    assert presentation_v9["live_browser_json_e2e"]["pptx_slides"] == 6
    assert presentation_v9["live_browser_json_e2e"]["eml_x_unsent"] == "1"
    assert presentation_v9["resource_identifiers"] == "redacted"

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
    historical_skill = (
        ROOT / "evidence" / "managed-live" / "meeting-package-v2-SKILL.md"
    )
    historical_text = historical_skill.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert hashlib.sha256(historical_text.encode()).hexdigest() == skill[
        "canonical_lf_sha256"
    ]
    current_skills = {
        "meeting-package": ("SKILL.md",),
        "presentation-story": (
            "SKILL.md",
            "references/deck-contract.yaml",
            "assets/presentation-style.yaml",
        ),
    }
    for skill_name, filenames in current_skills.items():
        for filename in filenames:
            source = ROOT / "skills" / skill_name / filename
            packaged = (
                ROOT / "src" / "meeting_agent" / "skills" / skill_name / filename
            )
            assert source.read_bytes() == packaged.read_bytes()

    scenarios = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))
    assert scenarios["scenarios"]["windows-managed-runtime"]["fallback"] is False
    assert scenarios["scenarios"]["browser-contract-e2e"]["type"] == "test-fixture"
    assert scenarios["scenarios"]["browser-live-e2e"]["requires_explicit_mode"] is True

    parity = json.loads(
        (ROOT / "evidence" / "managed-live" / "parity-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert parity["schema_version"] == 2
    assert parity["baseline_commit"] == "667357dac6ee2dc30102d572c458c77861112bea"
    assert len(parity["entries"]) == 6
    for entry in parity["entries"]:
        managed_relative = entry["managed_path"].removeprefix(
            "Agents/Meeting-Agent/managed-agent/"
        )
        managed_path = ROOT / managed_relative
        assert hashlib.sha256(managed_path.read_bytes()).hexdigest() == entry["sha256"]
    intentional = parity["intentional_differences"]
    assert len(intentional) == 2
    assert {
        entry["managed_path"].removeprefix(
            "Agents/Meeting-Agent/managed-agent/"
        )
        for entry in intentional
    } == {
        "src/meeting_agent/models.py",
        "src/meeting_agent/hosted_pipeline.py",
    }
    for entry in intentional:
        managed_relative = entry["managed_path"].removeprefix(
            "Agents/Meeting-Agent/managed-agent/"
        )
        managed_path = ROOT / managed_relative
        assert hashlib.sha256(managed_path.read_bytes()).hexdigest() == (
            entry["managed_sha256"]
        )
        assert entry["baseline_sha256"] != entry["managed_sha256"]
        assert entry["reason"]

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

    historical_gpt54_runtime = json.loads(
        (
            ROOT / "evidence" / "managed-live-gpt54" / "runtime-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert historical_gpt54_runtime["agent"] == {
        "name": "managed-meeting-agent",
        "version": "6",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-5.4",
        "protocol": "responses",
        "authentication": "Entra",
    }
    assert historical_gpt54_runtime["model_deployment"]["version"] == "2026-03-05"
    assert historical_gpt54_runtime["model_deployment"]["sku"] == "GlobalStandard"
    assert historical_gpt54_runtime["toolbox"]["connection_auth_type"] == (
        "AgenticIdentityToken"
    )
    assert historical_gpt54_runtime["rbac"]["principal"] == "agent-specific identity"
    assert historical_gpt54_runtime["reconcile"]["idempotent"] is True
    assert historical_gpt54_runtime["resource_identifiers"] == "redacted"

    historical_gpt54_runs = json.loads(
        (
            ROOT
            / "evidence"
            / "managed-live-gpt54"
            / "dual-input-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert historical_gpt54_runs["agent"]["version"] == "6"
    assert historical_gpt54_runs["agent"]["model"] == "gpt-5.4"
    assert historical_gpt54_runs["stream_model_deltas_present"] is True
    assert historical_gpt54_runs["cross_input_analysis_differs"] is True
    assert historical_gpt54_runs["cross_input_pptx_differs"] is True
    assert historical_gpt54_runs["automatic_send"] is False
    assert len(
        {run["analysis_sha256"] for run in historical_gpt54_runs["runs"].values()}
    ) == 2
    for run in historical_gpt54_runs["runs"].values():
        assert run["png"]["size"] == [1280, 720]
        assert run["png"]["nonblank"] is True
        assert run["pptx"]["slides"] == 6
        assert run["pptx"]["title_present"] is True
        assert run["pptx"]["current_mind_map_embedded"] is True
        assert run["eml"]["x_unsent"] == "1"
        assert run["eml"]["recipient_count"] == 0
        assert run["eml"]["attachment_count"] == 2

    historical_gpt54_ui = json.loads(
        (ROOT / "evidence" / "managed-live-gpt54" / "ui-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert historical_gpt54_ui["runtime"]["version"] == "6"
    assert historical_gpt54_ui["runtime"]["model"] == "gpt-5.4"
    assert historical_gpt54_ui["windows_runtime"]["node_architecture"] == "arm64"
    assert historical_gpt54_ui["windows_runtime"]["edge_pe_machine"] == "0xAA64"
    assert historical_gpt54_ui["playwright"]["projects"] == ["desktop", "mobile"]
    assert historical_gpt54_ui["playwright"]["passed"] == 2
    assert historical_gpt54_ui["playwright"]["failed"] == 0

    current_v9 = json.loads(
        (
            ROOT
            / "evidence"
            / "managed-live-gpt54"
            / "presentation-skill-v9-validation.json"
        ).read_text(encoding="utf-8")
    )
    assert current_v9["agent"] == {
        "name": "managed-meeting-agent",
        "version": "9",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "gpt-5.4",
        "authentication": "Entra",
    }
    assert current_v9["presentation_skill"]["package_files"] == [
        "SKILL.md",
        "references/deck-contract.yaml",
        "assets/presentation-style.yaml",
    ]
    assert current_v9["toolbox"]["version"] == "5"
    assert current_v9["toolbox"]["skills"] == {
        "meeting-package": "3",
        "presentation-story": "3",
    }
    assert current_v9["strict_response"]["deck_plan_authored_by_agent"] is True
    assert current_v9["live_browser_json_e2e"]["status"] == "passed"
    assert current_v9["live_browser_json_e2e"]["pptx_slides"] == 6
    assert current_v9["live_browser_json_e2e"]["eml_x_unsent"] == "1"
    print(
        "PASS: historical v2/v6 and current v9 Managed Agent evidence is valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
