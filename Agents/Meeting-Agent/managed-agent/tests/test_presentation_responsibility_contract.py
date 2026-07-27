from pathlib import Path

from meeting_agent.models import DeckPlan
from meeting_agent.presentation import (
    SLIDE_ORDER,
    load_deck_contract,
    load_presentation_style,
    resolve_deck_plan,
)
from tests.support import sample_analysis

ROOT = Path(__file__).resolve().parents[1]


def test_skill_guides_slide_content_not_deck_plan_or_visual_layout() -> None:
    skill = (ROOT / "skills" / "presentation-story" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "# Presentation Story Skill" in skill
    assert "## DeckPlan contract" in skill
    assert "Return exactly six typed sections" in skill
    for section in (
        "`cover`:",
        "`overview`:",
        "`topics`:",
        "`decisions_actions`:",
        "`mind_map`:",
        "`next_steps`:",
    ):
        assert section in skill
    for visual_detail in ("Segoe UI", "RGBColor", "slide_layouts"):
        assert visual_detail not in skill


def test_deck_plan_and_style_are_external_versioned_contracts() -> None:
    contract = load_deck_contract()
    style = load_presentation_style()

    assert contract.slide_order == SLIDE_ORDER
    assert contract.limits.topics == 6
    assert contract.limits.actions == 5
    assert style.font_family == "Segoe UI"
    assert style.font_sizes.cover_title == 32
    assert style.colors.action_accent == "FFAA00"
    assert style.mind_map.frame_margin_inches == 0.14


def test_legacy_v6_analysis_gets_a_strict_six_slide_plan() -> None:
    analysis = sample_analysis("product-planning")

    deck_plan = resolve_deck_plan(analysis)

    assert isinstance(deck_plan, DeckPlan)
    assert deck_plan.cover.title == analysis.title
    assert deck_plan.overview.summary == analysis.summary
    assert deck_plan.topics.items == analysis.topics
    assert deck_plan.decisions_actions.actions == analysis.action_items
    assert deck_plan.next_steps.questions == analysis.open_questions


def test_renderer_has_no_presentation_content_or_style_literals() -> None:
    renderer = (ROOT / "src" / "meeting_agent" / "artifacts.py").read_text(
        encoding="utf-8"
    )
    template = ROOT / "src" / "meeting_agent" / "templates" / "meeting-agent-template.zip"

    assert template.is_file()
    assert 'templates/meeting-agent-template.zip' in renderer
    assert "load_presentation_style" in renderer
    assert "load_deck_contract" in renderer
    assert "resolve_deck_plan" in renderer
    for literal in (
        '"Segoe UI"',
        '"FFFFFF"',
        '"00B04F"',
        '"0078D4"',
        '"FFAA00"',
        "No decision recorded",
        "No open question recorded",
        "Confirm the action owners",
    ):
        assert literal not in renderer
    for placeholder in ("MA_TITLE", "MA_SUMMARY", "MA_DECISIONS", "MA_ACTIONS"):
        assert placeholder in renderer


def test_docs_describe_implemented_source_and_live_boundaries() -> None:
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md").read_text(
        encoding="utf-8"
    )
    english_flat = " ".join(english.split())
    chinese_flat = " ".join(chinese.split())

    assert "versioned behavior assets inside the Managed Prompt Agent architecture" in english_flat
    assert "Managed Prompt Agent 架构中的版本化行为资产" in chinese_flat
    assert "source implementation now completes the presentation-domain separation" in english_flat
    assert "当前源码已经完成 Presentation Domain 松耦合" in chinese_flat
    assert "presentation-story" in english
    assert "presentation-story" in chinese
    assert "does **not** prove that `presentation-story` is deployed" in english_flat
    assert "**不证明** `presentation-story` 已部署" in chinese_flat
