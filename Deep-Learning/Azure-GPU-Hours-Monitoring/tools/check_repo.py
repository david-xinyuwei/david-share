#!/usr/bin/env python3
"""Public-content and structure audit for this repository.

    python tools/check_repo.py

Fails (exit 1) on: a broken relative link, image or in-page anchor; a `##` heading out of reader order;
a table wider than four columns (they overflow a 390 px phone column); an undocumented top-level path;
English and Chinese generated blocks that carry different numbers; or content that must not be
published (customer or private names, hosts, accounts, GUIDs, addresses, calendar dates, collapsed
blocks, and the retired UI and alert scope).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = {"en": ROOT / "README.md", "cn": ROOT / "README_CN.md"}
READER_ORDER = {
    "en": ["Start Here", "What This Repository Delivers", "Architecture and Metrics", "Configure on Azure",
           "Query from Your Platform", "Validation on One H100 VM", "Tests and Offline Checks",
           "Limits, Assets and Sources"],
    "cn": ["从这里开始", "本仓库做了什么、提供什么", "架构与指标口径", "在 Azure 上配置", "从客户平台查询",
           "单台 H100 VM 上的实测验证", "测试与离线校验", "边界、目录与资料"],
}
MAX_TABLE_COLUMNS = 4
TOP_LEVEL_EXEMPT = {".gitattributes", ".gitignore", "README.md", "__pycache__"}
FORBIDDEN = [
    (re.compile(r"(?i)sungrow|geek\s*plus|极智嘉|阳光电源"), "customer name"),
    (re.compile(r"(?i)rg-geekplus|law-gpuhours-demo|gpuhours-demo|sungrow-122b|rg-gpu-hours-replay-"), "internal resource name"),
    (re.compile(r"(?i)\bazureuser\b|\btrainer-[ab]\b"), "account name on the measured VM"),
    (re.compile(r"\b(?:Kurt|Super)\b|超伦|王轶|百超"), "personal name from private correspondence"),
    (re.compile(r"(?i)\b[A-Z]:\\Users\\|/home/[\w.-]+/|/Users/[\w.-]+/|\\\\[\w.-]+\\"), "user or network path"),
    (re.compile(r"\b[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.-]+\b"), "e-mail address"),
    (re.compile(r"\b(?!0\.0\.0\.0\b)(?!127\.0\.0\.1\b)(?!169\.254\.169\.254\b)(?:\d{1,3}\.){3}\d{1,3}\b"),
     "IPv4 address (only the Azure instance metadata address is allowed)"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "GUID (subscription, tenant or workspace)"),
    (re.compile(r"<details", re.I), "collapsed block"),
    (re.compile(r"(?<!api-version=)\b20\d\d-\d\d-\d\d\b|\b20\d\d(?:0[1-9]|1[0-2])(?:[0-2]\d|3[01])\b"
                r"|\b(?:January|February|March|April|June|July|August|September|October|November|December)\b"
                r"|\d{1,2}\s*月\s*\d{1,2}\s*日"), "calendar date"),
    (re.compile(r"README-CN\.md"), "retired file name (the Chinese README is README_CN.md)"),
    (re.compile(r"(?i)\bworkbook\b|webui|deploy-webui|alert-gpu-idle|dashboard-(?:webui|charts)"), "retired UI or alert scope"),
]
SCAN_SUFFIXES = {".md", ".py", ".json", ".jsonl", ".txt", ".sh", ".yml", ".kql", ""}
SCAN_SKIP_FILES = {"check_repo.py", "test_public_content.py"}  # files that hold guard probes
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)|!\[[^\]]*\]\(([^)\s]+)\)|<img\s+[^>]*src=\"([^\"]+)\"")
GENERATED = re.compile(r"<!-- BEGIN GENERATED: (?P<name>[a-z0-9-]+) -->\n(?P<body>.*?)<!-- END GENERATED: (?P=name) -->", re.S)
LINK_TARGET = re.compile(r"\]\([^)]*\)")
NUMBER = re.compile(r"(?<![A-Za-z_\d])[+\-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
IMG_WIDTH = re.compile(r"<img\s+[^>]*width=\"(\d+)\"")


def slug(heading: str) -> str:
    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def headings(text: str) -> list[tuple[int, str]]:
    out, fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        m = re.match(r"^(#{1,6}) (.+)$", line)
        if m and not fence:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def check_links(lang: str, text: str, errors: list[str]) -> None:
    anchors = {slug(h) for _, h in headings(text)}
    for m in LINK.finditer(text):
        target = next(g for g in m.groups() if g)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path, _, anchor = target.partition("#")
        if not path:
            if anchor not in anchors:
                errors.append(f"{lang}: BROKEN_ANCHOR #{anchor}")
            continue
        resolved = (ROOT / path).resolve()
        outside = ROOT.resolve() not in resolved.parents and resolved != ROOT.resolve()
        if outside and os.environ.get("CHECK_MONOREPO_LINKS") != "1":
            continue  # the monorepo may be a sparse checkout; CI sets CHECK_MONOREPO_LINKS=1
        if not resolved.exists():
            errors.append(f"{lang}: BROKEN_LOCAL_LINK {target}")
    for w in IMG_WIDTH.findall(text):
        if int(w) > 900:
            errors.append(f"{lang}: IMAGE_TOO_WIDE {w}")


def check_order(lang: str, text: str, errors: list[str]) -> None:
    got = [h for level, h in headings(text) if level == 2]
    if got != READER_ORDER[lang]:
        errors.append(f"{lang}: HEADING_ORDER {got}")


def _rows(body: str) -> list[list[str]]:
    """Numbers per table row or list item; code blocks compare as whole text."""
    visible = [LINK_TARGET.sub("]", l) for l in body.splitlines()]
    lines = [l for l in visible if l.startswith("|")]
    if lines:
        return [NUMBER.findall(l) for l in lines[2:]]
    items = [l for l in visible if l.startswith("- ")]
    if items:
        return [NUMBER.findall(l) for l in items]
    return [[body.split("```", 1)[1] if "```" in body else ""]]


def check_bilingual(errors: list[str]) -> None:
    blocks = {lang: {m.group("name"): m.group("body") for m in GENERATED.finditer(p.read_text(encoding="utf-8"))}
              for lang, p in READMES.items()}
    if set(blocks["en"]) != set(blocks["cn"]):
        errors.append(f"BILINGUAL_BLOCK_SET {sorted(set(blocks['en']) ^ set(blocks['cn']))}")
    for name in sorted(set(blocks["en"]) & set(blocks["cn"])):
        en, cn = _rows(blocks["en"][name]), _rows(blocks["cn"][name])
        if len(en) != len(cn):
            errors.append(f"BILINGUAL_ROWS {name}: {len(en)} vs {len(cn)} rows")
            continue
        for i, (a, b) in enumerate(zip(en, cn)):
            if a != b:
                errors.append(f"BILINGUAL_NUMBERS {name} row {i + 1}: en {a} cn {b}")


def check_table_shape(lang: str, text: str, errors: list[str]) -> None:
    rows, fence = [], False
    for line in text.splitlines() + [""]:
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("|"):
            rows.append(line)
            continue
        if rows:
            widths = {len(re.split(r"(?<!\\)\|", r)) - 2 for r in rows}
            if len(widths) != 1:
                errors.append(f"{lang}: TABLE_SHAPE {rows[0][:60]!r}")
            elif next(iter(widths)) > MAX_TABLE_COLUMNS:
                errors.append(f"{lang}: TABLE_TOO_WIDE {next(iter(widths))} columns: {rows[0][:60]!r}")
            rows = []


def check_top_level(errors: list[str]) -> None:
    text = READMES["en"].read_text(encoding="utf-8") + READMES["cn"].read_text(encoding="utf-8")
    for entry in ROOT.iterdir():
        if entry.name in TOP_LEVEL_EXEMPT:
            continue
        ref = entry.name + ("/" if entry.is_dir() else "")
        if f"({ref})" not in text and f"({entry.name})" not in text:
            errors.append(f"UNDOCUMENTED_TOP_LEVEL {ref}")


def check_forbidden(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES or path.name in SCAN_SKIP_FILES:
            continue
        rel = path.relative_to(ROOT)
        if "__pycache__" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern, why in FORBIDDEN:
            m = pattern.search(text)
            if m:
                errors.append(f"FORBIDDEN {rel.as_posix()}: {why}: {m.group(0)!r}")


def run() -> list[str]:
    errors: list[str] = []
    for lang, path in READMES.items():
        text = path.read_text(encoding="utf-8")
        check_links(lang, text, errors)
        check_order(lang, text, errors)
        check_table_shape(lang, text, errors)
    check_bilingual(errors)
    check_top_level(errors)
    check_forbidden(errors)
    return errors


def main() -> int:
    errors = run()
    if errors:
        print("\n".join(errors))
        return 1
    print("PASS links, reader order, table width, top-level paths, bilingual numbers and public-content guards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
