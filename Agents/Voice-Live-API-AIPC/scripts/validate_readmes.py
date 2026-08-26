"""Validate bilingual README shape, local links, images, and critical claims."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README-CN.md")
CUSTOMER_PATHS = (ROOT / "CUSTOMER-START-HERE.md", ROOT / "CUSTOMER-START-HERE-CN.md")
WORKFLOW_PATH = ROOT.parents[1] / ".github" / "workflows" / "voice-live-aipc-ci.yml"
EXPECTED_IMAGES = (
    "images/voice-live-aipc-ui.png",
    "images/voice-live-aipc-architecture.svg",
)


def local_links(text: str) -> list[str]:
    links = []
    for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", text):
        target = target.split("#", 1)[0]
        if target and not target.startswith(("http://", "https://", "mailto:", "#")):
            links.append(target)
    return links


def local_images(text: str) -> list[str]:
    return [
        target
        for target in re.findall(r"!\[[^]]*]\(([^)]+)\)", text)
        if not target.startswith(("http://", "https://"))
    ]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def main() -> int:
    texts = [path.read_text(encoding="utf-8") for path in README_PATHS]
    headings = [re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in texts]
    fences = [re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in texts]
    table_shapes = [
        [line.count("|") for line in text.splitlines() if re.fullmatch(r"\|[-:| ]+\|", line)]
        for text in texts
    ]
    images = [local_images(text) for text in texts]

    assert headings[0] == headings[1]
    assert fences[0] == fences[1]
    assert table_shapes[0] == table_shapes[1]
    assert tuple(images[0]) == EXPECTED_IMAGES
    assert images[0] == images[1]

    for text in texts:
        for link in local_links(text):
            assert (ROOT / link).exists(), link
        assert "Voice Live" in text
        assert "AIPC" in text
        assert "APIC" not in text
        assert text.count("24") >= 5
        assert "gpt-realtime" in text
        assert "gpt-4o-transcribe" in text
        assert "Microsoft Graph" in text
        assert "test-fixture" in text
        assert "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live" in text

    assert "No mock fallback" in texts[0]
    assert "No production certification" in texts[0]
    assert "不做 mock fallback" in texts[1]
    assert "不是生产认证" in texts[1]

    customer_texts = [path.read_text(encoding="utf-8") for path in CUSTOMER_PATHS]
    customer_headings = [
        re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in customer_texts
    ]
    customer_fences = [
        re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in customer_texts
    ]
    assert customer_headings[0] == customer_headings[1]
    assert customer_fences[0] == customer_fences[1]
    for text in customer_texts:
        for link in local_links(text):
            assert (ROOT / link).exists(), link
        assert "Voice Live" in text
        assert "AIPC" in text
        assert "gpt-realtime" in text
        assert "24" in text

    assert WORKFLOW_PATH.is_file(), WORKFLOW_PATH
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '"Agents/Voice-Live-API-AIPC/**"' in workflow
    assert "SELF_CHECK=PASS" in workflow
    assert "pre_delivery_check.py" in workflow

    svg_root = ElementTree.parse(ROOT / EXPECTED_IMAGES[1]).getroot()
    assert svg_root.attrib["width"] == "1600"
    assert svg_root.attrib["height"] == "900"
    labels = " ".join("".join(node.itertext()) for node in svg_root.iter())
    for label in ("Windows AIPC", "Azure Voice Live WebSocket", "24 registered local tools"):
        assert label in labels

    ui_path = ROOT / EXPECTED_IMAGES[0]
    assert png_size(ui_path) == (1136, 739)
    assert ui_path.stat().st_size > 40_000

    print(
        f"PASS: bilingual READMEs share {len(headings[0])} headings, "
        f"{len(fences[0]) // 2} code blocks, {len(table_shapes[0])} tables, "
        f"and {len(images[0])} validated images; customer pages and monorepo CI are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
