import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_evidence_is_dated_and_redacted() -> None:
    evidence = json.loads((ROOT / "evidence-managed-agent.json").read_text(encoding="utf-8"))

    assert evidence["agent"]["name"] == "managed-meeting-agent"
    assert evidence["validation"]["validated_at_utc"]
    assert evidence["validation"]["resource_identifiers"] == "redacted; public alias used"
    assert "validation snapshot" in evidence["validation"]["scope"]
    assert "revalidate after source or environment changes" in evidence["validation"][
        "scope"
    ]
