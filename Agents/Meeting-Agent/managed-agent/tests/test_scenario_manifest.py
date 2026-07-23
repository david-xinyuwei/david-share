import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_manifest_separates_fixture_and_live_paths() -> None:
    scenarios = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))[
        "scenarios"
    ]

    assert scenarios["browser-contract-e2e"]["type"] == "test-fixture"
    assert scenarios["browser-contract-e2e"]["attestation"] == "test-fixture"
    assert scenarios["browser-live-e2e"]["type"] == "dynamic-runtime"
    assert scenarios["browser-live-e2e"]["requires_explicit_mode"] is True
    assert scenarios["windows-managed-runtime"]["fallback"] is False
