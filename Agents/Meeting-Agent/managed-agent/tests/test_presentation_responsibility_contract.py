from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_guides_slide_content_not_deck_plan_or_visual_layout() -> None:
    skill = (ROOT / "skills" / "meeting-package" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "## Slide narrative" in skill
    assert "six-slide customer-ready deck" in skill
    for item in (
        "A concise cover and executive summary.",
        "A visual overview of the main topics.",
        "Decisions paired with supporting context.",
        "An action register with owner and due date.",
        "A mind-map overview.",
        "Open questions and next-step discussion.",
    ):
        assert item in skill
    for visual_detail in ("Segoe UI", "RGBColor", "slide_layouts", "shape coordinates"):
        assert visual_detail not in skill


def test_renderer_owns_deterministic_powerpoint_format() -> None:
    renderer = (ROOT / "src" / "meeting_agent" / "artifacts.py").read_text(
        encoding="utf-8"
    )
    template = ROOT / "src" / "meeting_agent" / "templates" / "meeting-agent-template.zip"

    assert template.is_file()
    assert 'templates/meeting-agent-template.zip' in renderer
    assert 'paragraph.font.name = "Segoe UI"' in renderer
    for size in ("size=32", "size=18", "size=16", "size=22"):
        assert size in renderer
    for color in ("FFFFFF", "00B04F", "0078D4", "FFAA00"):
        assert color in renderer
    for placeholder in ("MA_TITLE", "MA_SUMMARY", "MA_DECISIONS", "MA_ACTIONS"):
        assert placeholder in renderer


def test_docs_describe_current_and_target_presentation_boundaries() -> None:
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
    assert "model-guidance decoupling" in english_flat
    assert "模型指导松耦合" in chinese_flat
    assert "presentation-story" in english
    assert "presentation-story" in chinese
    assert "not claimed as implemented by v6" in english_flat
    assert "不把这个目标写成 v6 已实现能力" in chinese_flat
