from pathlib import Path

from meeting_agent.analyzers import _managed_analysis_prompt
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_mind_map_story_is_a_separate_behavior_asset() -> None:
    meeting = (ROOT / "skills" / "meeting-package" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    mind_map = (ROOT / "skills" / "mind-map-story" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    packaged = (
        ROOT / "src" / "meeting_agent" / "skills" / "mind-map-story" / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert mind_map == packaged
    assert "# Mind Map Story Skill" in mind_map
    assert "Create the `mind_map` semantic tree" in mind_map
    assert "Create 3-6 distinct first-level branches" in mind_map
    assert "do not choose rendering coordinates" in mind_map
    assert "## Mind map" not in meeting
    assert "Create 3-6 meaningful first-level branches" not in meeting


def test_managed_prompt_routes_mind_map_to_its_skill() -> None:
    prompt = _managed_analysis_prompt(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl"),
        require_deck_plan=True,
    )

    assert "meeting-package Skill" in prompt
    assert "mind-map-story Skill" in prompt
    assert "presentation-story Skill" in prompt
    assert "mind_map tree" in prompt
