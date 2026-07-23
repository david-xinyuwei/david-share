import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_runtime_snapshot_is_historical_and_redacted() -> None:
    data = json.loads((ROOT / "evidence-managed-agent.json").read_text(encoding="utf-8"))
    assert data["validation"]["validated_at_utc"]
    assert data["validation"]["resource_identifiers"] == "redacted; public alias used"
