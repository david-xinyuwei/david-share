"""Validate bilingual README structure and local asset links."""

import re
from pathlib import Path
from xml.etree import ElementTree

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README-CN.md")
EXPECTED_IMAGES = [
    "images/meeting-agent-architecture.svg",
    "evidence/sample-runs/product-planning/mind-map.png",
    "evidence/sample-runs/operations-review/mind-map.png",
    "images/outlook-draft-handoff-sanitized.png",
]


def local_images(text: str) -> list[str]:
    return [
        target
        for target in re.findall(r"!\[[^]]*]\(([^)]+)\)", text)
        if not target.startswith(("http://", "https://"))
    ]


def local_links(text: str) -> list[str]:
    return [
        target.split("#", 1)[0]
        for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", text)
        if target
        and not target.startswith(("#", "http://", "https://", "mailto:"))
    ]


def main() -> int:
    texts = [path.read_text(encoding="utf-8") for path in README_PATHS]
    headings = [re.findall(r"^#{1,6} ", text, flags=re.MULTILINE) for text in texts]
    images = [local_images(text) for text in texts]

    assert len(headings[0]) == len(headings[1])
    assert images[0] == images[1]
    assert images[0] == EXPECTED_IMAGES
    for image in images[0]:
        assert (ROOT / image).is_file(), image

    architecture = ElementTree.parse(ROOT / EXPECTED_IMAGES[0]).getroot()
    assert architecture.attrib["width"] == "2400"
    assert architecture.attrib["height"] == "2100"
    assert architecture.attrib["viewBox"] == "0 0 2400 2100"
    namespace = "{http://www.w3.org/2000/svg}"
    architecture_labels = {
        "".join(node.itertext()).strip()
        for node in architecture.findall(f"{namespace}text")
    }
    assert len(architecture.findall(f"{namespace}rect")) >= 10
    assert len(architecture.findall(f"{namespace}path")) >= 10
    assert {"Meeting Agent", "New Outlook Draft", "Human Review", "Manual Send"} <= (
        architecture_labels
    )

    screenshot = Image.open(ROOT / EXPECTED_IMAGES[-1]).convert("RGB")
    assert screenshot.size == (1721, 940)
    assert all(variance > 100 for variance in ImageStat.Stat(screenshot).var)
    for text in texts:
        for link in local_links(text):
            assert (ROOT / link).exists(), link
        assert "Xinyu Wei" in text or "魏新宇" in text
        assert "automatic_send" in text
        assert "offline-contract" in text
    print(
        f"PASS: bilingual READMEs share {len(headings[0])} headings "
        f"and {len(images[0])} local images."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())