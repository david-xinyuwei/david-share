import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_evidence_is_dated_and_redacted() -> None:
    evidence = json.loads((ROOT / "evidence-managed-agent.json").read_text(encoding="utf-8"))

    assert evidence["agent"] == {
        "name": "true-meeting-managed-agent",
        "version": "6",
        "status": "active",
        "kind": "prompt",
        "harness": "ghcp",
        "model": "Kimi-K2.7-Code",
        "tool_count": 1,
        "protocols": ["responses"],
        "authentication": ["Entra"],
    }
    assert evidence["validation"]["validated_at_utc"]
    assert evidence["validation"]["resource_identifiers"] == "redacted; public alias used"
    assert "validation snapshot" in evidence["validation"]["scope"]
    assert "revalidate after source or environment changes" in evidence["validation"][
        "scope"
    ]
