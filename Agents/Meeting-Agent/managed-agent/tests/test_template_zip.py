import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_template_zip_is_valid_ooxml() -> None:
    template = ROOT / "src" / "meeting_agent" / "templates" / "meeting-agent-template.zip"
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "*.zip binary" in attributes
    assert zipfile.is_zipfile(template)
    with zipfile.ZipFile(template) as archive:
        assert "ppt/presentation.xml" in archive.namelist()
