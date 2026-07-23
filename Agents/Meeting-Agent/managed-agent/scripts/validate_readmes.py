"""Validate Managed Meeting Agent bilingual documentation and local links."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README-CN.md")


def _local_links(text: str) -> list[str]:
    return [
        target.split("#", 1)[0]
        for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", text)
        if target and not target.startswith(("#", "http://", "https://", "mailto:"))
    ]


def main() -> int:
    english, chinese = (path.read_text(encoding="utf-8") for path in README_PATHS)
    required_pairs = (
        ("Foundry Prompt Agent", "Foundry Prompt Agent"),
        ("managed-meeting-agent", "managed-meeting-agent"),
        ("harness=ghcp", "harness=ghcp"),
        ("Entra", "Entra"),
        ("six-slide", "六页"),
        ("X-Unsent: 1", "X-Unsent: 1"),
        ("manual Send", "手动点击 **Send**"),
        ("not production certification", "不是生产认证"),
        ("does not depend", "不依赖"),
        ("667357dac6ee2dc30102d572c458c77861112bea", "667357dac6ee2dc30102d572c458c77861112bea"),
    )
    for english_text, chinese_text in required_pairs:
        assert english_text.casefold() in english.casefold(), english_text
        assert chinese_text in chinese, chinese_text
    assert "start-ui-key.ps1" not in english + chinese
    assert "AZURE_OPENAI_API_KEY" not in english + chinese
    assert english.count("| `product-planning` |") == 1
    assert chinese.count("| `product-planning` |") == 1
    assert english.count("| `operations-review` |") == 1
    assert chinese.count("| `operations-review` |") == 1
    for text in (english, chinese):
        for link in _local_links(text):
            assert (ROOT / link).exists(), link

    architecture = ElementTree.parse(ROOT / "images" / "meeting-agent-architecture.svg").getroot()
    assert architecture.attrib["viewBox"] == "0 0 2400 2100"
    xml_text = ElementTree.tostring(architecture, encoding="unicode")
    assert "Managed Agent Analysis" in xml_text
    assert "no API-key fallback" in xml_text
    assert "AOAI Responses Analysis" not in xml_text
    print("PASS: bilingual Managed Agent documentation and architecture are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
