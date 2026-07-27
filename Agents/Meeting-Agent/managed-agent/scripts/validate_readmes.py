"""Validate Managed Meeting Agent bilingual documentation and local links."""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PAIRS = (
    (
        ROOT.parent / "README.md",
        ROOT.parent / "README-CN.md",
    ),
    (
        ROOT / "docs" / "MANAGED-IMPLEMENTATION.md",
        ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md",
    ),
    (
        ROOT / "docs" / "IMPLEMENTATION-COMPARISON.md",
        ROOT / "docs" / "IMPLEMENTATION-COMPARISON-CN.md",
    ),
)


def _local_links(text: str) -> list[str]:
    return [
        target.split("#", 1)[0]
        for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", text)
        if target and not target.startswith(("#", "http://", "https://", "mailto:"))
    ]


def _squash_whitespace(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    managed_paths = DOCUMENT_PAIRS[1]
    english, chinese = (path.read_text(encoding="utf-8") for path in managed_paths)
    english_flat = _squash_whitespace(english)
    chinese_flat = _squash_whitespace(chinese)
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
        ("not a requirement to host this repository in GitHub", "不表示本 Repo 必须托管在 GitHub"),
        ("667357dac6ee2dc30102d572c458c77861112bea", "667357dac6ee2dc30102d572c458c77861112bea"),
    )
    for english_text, chinese_text in required_pairs:
        assert english_text.casefold() in english_flat.casefold(), english_text
        assert chinese_text in chinese_flat, chinese_text
    assert "start-ui-key.ps1" not in english + chinese
    assert "AZURE_OPENAI_API_KEY" not in english + chinese
    assert english.count("| `product-planning` |") == 1
    assert chinese.count("| `product-planning` |") == 1
    assert english.count("| `operations-review` |") == 1
    assert chinese.count("| `operations-review` |") == 1
    for paths in DOCUMENT_PAIRS:
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for link in _local_links(text):
                assert (path.parent / link).resolve().exists(), f"{path}: {link}"

    architecture = ElementTree.parse(ROOT / "images" / "meeting-agent-architecture.svg").getroot()
    assert architecture.attrib["viewBox"] == "0 0 2400 2100"
    xml_text = ElementTree.tostring(architecture, encoding="unicode")
    assert "Managed Agent Analysis" in xml_text
    assert "no API-key fallback" in xml_text
    assert "AOAI Responses Analysis" not in xml_text
    print("PASS: required bilingual documentation markers and local links are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
