#!/usr/bin/env python3
"""Validate bilingual README structure, claims, links, and images."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "README-CN.md")
EXPECTED_IMAGES = [
    "images/evidence-pipeline.png",
    "images/resilience-architecture.png",
    "images/scenario-coverage.png",
]
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
    errors: list[str] = []
    texts = [path.read_text(encoding="utf-8") for path in READMES]
    lines = [text.splitlines() for text in texts]
    heading_levels = [re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in texts]
    fence_languages = [re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in texts]
    images = [local_targets(text, images=True) for text in texts]

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(abs(len(lines[0]) - len(lines[1])) <= 30, "README line-count drift exceeds 30")
    require(heading_levels[0] == heading_levels[1], "README heading-level sequence differs")
    require(fence_languages[0] == fence_languages[1], "README code-fence languages differ")
    require(table_shapes(lines[0]) == table_shapes(lines[1]), "README table shapes differ")
    require(len(images[0]) == len(images[1]) == 3, "README image counts must both equal 3")
    require(images[0] == EXPECTED_IMAGES, "English README image order is unexpected")
    require(
        images[1] == [path.replace(".png", "-cn.png") for path in EXPECTED_IMAGES],
        "Chinese README must use the localized image set",
    )
    for readme, text in zip(READMES, texts, strict=True):
        for target in local_targets(text, images=False) + local_targets(text, images=True):
            require((ROOT / target).exists(), f"{readme.name}: missing local link target: {target}")
        require(SCENARIOS <= {scenario for scenario in SCENARIOS if scenario in text}, f"{readme.name}: missing scenario ID")
        require("Xinyu Wei" in text or "魏新宇" in text, f"{readme.name}: missing author")

    number_pattern = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:/\d+)?")
    require(
        Counter(number_pattern.findall(texts[0])) == Counter(number_pattern.findall(texts[1])),
        "README numeric claims differ",
    )
    require("not a production certification" in texts[0], "English production boundary missing")
    require("不是生产认证" in texts[1], "Chinese production boundary missing")
    require("does not include private-preview source code" in texts[0], "English export boundary missing")
    require("不包含 private-preview 源码" in texts[1], "Chinese export boundary missing")
    require("author-attested" in texts[0], "English provenance boundary missing")
    require("作者证明" in texts[1], "Chinese provenance boundary missing")
    require("main documented scenarios" in texts[0], "English scope boundary missing")
    require("主场景" in texts[1], "Chinese scope boundary missing")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        f"PASS: bilingual READMEs share {len(heading_levels[0])} headings, "
        f"{len(fence_languages[0]) // 2} code blocks, {len(images[0])} localized images, "
        "matching numeric claims, and 8 scenario IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
