from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_source_and_package_copy_are_identical() -> None:
    canonical = ROOT / "skills" / "meeting-package" / "SKILL.md"
    packaged = ROOT / "src" / "meeting_agent" / "skills" / "meeting-package" / "SKILL.md"

    assert canonical.read_bytes() == packaged.read_bytes()
