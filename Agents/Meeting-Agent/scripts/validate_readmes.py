"""Validate bilingual README structure and local asset links."""

import json
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
RUN_NAMES = ("product-planning", "operations-review")
CRITICAL_CLAIMS = (
    ("No live Azure response is committed", "公开仓库不提交真实 Azure response"),
    ("not an AI-quality substitute", "不是 AI 质量替代品"),
    ("does not transmit mail", "不发送邮件"),
    ("store=False", "store=False"),
)


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


def evidence_rows(text: str) -> dict[str, tuple[int, str, str]]:
    pattern = re.compile(
        r"^\| `(product-planning|operations-review)` \| (\d+) \| "
        r"`([0-9a-f]{64})` \| `([0-9a-f]{64})` \|",
        flags=re.MULTILINE,
    )
    return {
        run_name: (int(event_count), source_hash, analysis_hash)
        for run_name, event_count, source_hash, analysis_hash in pattern.findall(text)
    }


def main() -> int:
    texts = [path.read_text(encoding="utf-8") for path in README_PATHS]
    lines = [text.splitlines() for text in texts]
    headings = [re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in texts]
    fence_languages = [
        re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in texts
    ]
    table_shapes = [
        [line.count("|") for line in readme_lines if re.fullmatch(r"\|[-:| ]+\|", line)]
        for readme_lines in lines
    ]
    images = [local_images(text) for text in texts]
    readme_evidence = [evidence_rows(text) for text in texts]

    assert len(lines[0]) == len(lines[1])
    assert headings[0] == headings[1]
    assert fence_languages[0] == fence_languages[1]
    assert table_shapes[0] == table_shapes[1]
    assert images[0] == images[1]
    assert images[0] == EXPECTED_IMAGES
    assert readme_evidence[0] == readme_evidence[1]
    assert set(readme_evidence[0]) == set(RUN_NAMES)
    for image in images[0]:
        assert (ROOT / image).is_file(), image
    for run_name in RUN_NAMES:
        evidence_path = ROOT / "evidence" / "sample-runs" / run_name / "evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        expected = (
            evidence["source"]["event_count"],
            evidence["source"]["content_sha256"],
            evidence["artifacts"]["analysis"]["sha256"],
        )
        assert readme_evidence[0][run_name] == expected

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
    for english_claim, chinese_claim in CRITICAL_CLAIMS:
        assert english_claim.casefold() in texts[0].casefold()
        assert chinese_claim in texts[1]
    print(
        f"PASS: bilingual READMEs share {len(headings[0])} headings, "
        f"{len(fence_languages[0]) // 2} code blocks, and evidence for "
        f"{len(readme_evidence[0])} sample runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())