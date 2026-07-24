from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_agent_is_prompt_kind_with_managed_harness_source() -> None:
    agent = yaml.safe_load((ROOT / "agent.yaml").read_text(encoding="utf-8"))
    instructions = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )

    assert agent["kind"] == "prompt"
    assert "Foundry prompt agent with a managed GHCP harness" in instructions
