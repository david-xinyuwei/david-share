#!/usr/bin/env python3
"""Validate bilingual README structure, claims, links, and images."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "README-CN.md")
EXPECTED_IMAGES = ["images/evidence-pipeline.png", "images/scenario-coverage.png"]
SCENARIOS = {
    "research-invocations-python",
    "research-responses-python",
    "graph-hitl-invocations-python",
    "graph-hitl-responses-python",
    "durable-workflow-python",
    "steering-python",
    "research-invocations-dotnet",
    "research-responses-dotnet",
}


def local_targets(text: str, images: bool) -> list[str]:
    prefix = r"!" if images else r"(?<!!)"
    targets = re.findall(prefix + r"\[[^]]*]\(([^)]+)\)", text)
    return [
        target.split("#", 1)[0]
        for target in targets
        if target and not target.startswith(("#", "http://", "https://", "mailto:"))
    ]


def table_shapes(lines: list[str]) -> list[int]:
    return [line.count("|") for line in lines if re.fullmatch(r"\|[-:| ]+\|", line)]


def main() -> int:
    texts = [path.read_text(encoding="utf-8") for path in READMES]
    lines = [text.splitlines() for text in texts]
    heading_levels = [re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in texts]
    fence_languages = [re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in texts]
    images = [local_targets(text, images=True) for text in texts]

    assert abs(len(lines[0]) - len(lines[1])) <= 20
    assert heading_levels[0] == heading_levels[1]
    assert fence_languages[0] == fence_languages[1]
    assert table_shapes(lines[0]) == table_shapes(lines[1])
    assert images[0] == images[1] == EXPECTED_IMAGES
    for text in texts:
        for target in local_targets(text, images=False) + local_targets(text, images=True):
            assert (ROOT / target).exists(), target
        assert SCENARIOS <= {scenario for scenario in SCENARIOS if scenario in text}
        assert "Xinyu Wei" in text or "魏新宇" in text
    assert "not a production certification" in texts[0]
    assert "不是生产认证" in texts[1]
    assert "does not include private-preview source code" in texts[0]
    assert "不包含 private-preview 源码" in texts[1]
    assert "main documented scenarios" in texts[0]
    assert "主场景" in texts[1]
    print(
        f"PASS: bilingual READMEs share {len(heading_levels[0])} headings, "
        f"{len(fence_languages[0]) // 2} code blocks, {len(images[0])} images, and 8 scenario IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
