"""Repository checks: page layout in both languages, links and images, every measured number against data/results.json,
the two figures against their HTML sources, and no private hosts, paths or keys.

Run from the repository root (no Azure, no browser, no CAD kernel needed):
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [("README.md", "README_CN.md"), ("docs/RESULTS.md", "docs/RESULTS_CN.md"), ("docs/TESTING.md", "docs/TESTING_CN.md")]
SECTIONS = {"README.md": ["Purpose", "Results", "Steps"], "README_CN.md": ["目的", "实现效果", "操作步骤"]}
RESULT_HEADINGS = {"README.md": "Results", "README_CN.md": "实现效果"}
FENCE = re.compile(r"^\s*(```|~~~)")
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img[^>]*\ssrc=\"([^\"]+)\"|<a[^>]*\shref=\"([^\"]+)\"")
NUMBER = re.compile(r"(?<![\w.#/-])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\w])")
SKIP_SPANS = re.compile(r"`[^`]*`|\]\([^)]*\)|<[^>]+>|https?://\S+|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b|"
                        r"\b\d+(?:\.\d+){2,}\b|\br\d+\b|\d+(?:\s?[×x]\s?\d+)+")
PRIVATE = [
    # The README videos are GitHub attachments whose public URL ends in a GUID; any other GUID still fails.
    (re.compile(r"(?<!github\.com/user-attachments/assets/)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I),
     "GUID (subscription, tenant or client id)"),
    (re.compile(r"[A-Za-z]:\\Users\\", re.I), "local Windows user path"),
    (re.compile(r"\b[\w.-]+@(microsoft|outlook|hotmail|gmail)\.com\b", re.I), "e-mail address"),
    (re.compile(r"\b[a-z0-9-]+\.[a-z]+\.cloudapp\.azure\.com\b", re.I), "public VM host name"),
    # Placeholder resource names used by studio/tests (acme, host-res, ...) are allowed by name; any other host fails.
    (re.compile(r"https://(?!<|example\.invalid|(?:acme|acme-res|host-res|host-resource|test-resource|stale|a|mai)\.)"
                r"[a-z0-9-]+\.(openai\.azure\.com|services\.ai\.azure\.com|cognitiveservices\.azure\.com)", re.I),
     "real Azure resource endpoint"),
    (re.compile(r"(api[_-]?key|password|secret)\s*[=:]\s*['\"]?[A-Za-z0-9+/]{24,}", re.I), "key-like value"),
]
TEXT_SUFFIXES = {".md", ".py", ".js", ".mjs", ".cjs", ".html", ".css", ".json", ".txt", ".log", ".sh", ".ps1", ".conf", ".service",
                 ".yml", ".example", ".gitignore", ".gitattributes"}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def outside_fences(text: str) -> list[tuple[int, str]]:
    lines, inside = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            lines.append((i, line))
    return lines


def table_shapes(text: str) -> list[tuple[int, int]]:
    shapes, rows, cols = [], 0, 0
    for _, line in outside_fences(text) + [(0, "")]:
        if line.lstrip().startswith("|"):
            if re.match(r"^\s*\|\s*:?-{3,}", line):
                continue
            cols = cols or line.strip().strip("|").count("|") + 1
            rows += 1
        elif rows:
            shapes.append((cols, rows - 1))
            rows, cols = 0, 0
    return shapes


def headings(text: str, level: int) -> list[str]:
    return [line[level + 1:].strip() for _, line in outside_fences(text) if line.startswith("#" * level + " ")]


def slug(heading: str) -> str:
    s = re.sub(r"<[^>]+>|`", "", heading).strip().lower()
    s = re.sub(r"[^\w\- \u4e00-\u9fff]", "", s)
    return s.replace(" ", "-")


def section(text: str, title: str) -> list[tuple[int, str]]:
    out, on = [], False
    for i, line in outside_fences(text):
        if line.startswith("## "):
            on = line[3:].strip() == title
            continue
        if on:
            out.append((i, line))
    return out


def numeric_leaves(obj, acc: set[float]) -> set[float]:
    if isinstance(obj, dict):
        for v in obj.values():
            numeric_leaves(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            numeric_leaves(v, acc)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        acc.add(float(obj))
    return acc


def displayed_forms(values: set[float]) -> set[str]:
    forms = set()
    for v in values:
        for x in (v, v / 1e6, v / 1024 / 1024):            # bytes may be shown in MB or MiB
            for d in (0, 1, 2, 3):                          # masses are stored and shown with 3 decimals
                forms.add(f"{x:.{d}f}")
    return forms


class RepositoryTest(unittest.TestCase):
    def test_readme_sections_in_agreed_order(self):
        for page, want in SECTIONS.items():
            self.assertEqual(headings(read(page), 2), want, page)

    def test_opening_has_badges_author_and_language_switch(self):
        for page, other, author in (("README.md", "README_CN.md", "Author: Xinyu Wei"), ("README_CN.md", "README.md", "作者：Xinyu Wei")):
            head = "\n".join(read(page).splitlines()[:12])
            self.assertGreaterEqual(head.count("img.shields.io/badge"), 3, page)
            self.assertIn(author, head, page)
            self.assertIn(f"]({other})", head, page)

    def test_both_languages_have_the_same_tables_and_images(self):
        for en, zh in PAIRS:
            self.assertEqual(table_shapes(read(en)), table_shapes(read(zh)), f"{en} vs {zh}")
            imgs = lambda t: [m.group(1) or m.group(2) for m in LINK.finditer(t) if (m.group(0).startswith("!") or m.group(2))]
            self.assertEqual(len(imgs(read(en))), len(imgs(read(zh))), f"image count {en} vs {zh}")

    def test_relative_links_and_anchors_resolve(self):
        pages = [p for pair in PAIRS for p in pair] + ["NOTICE.md"]
        for page in pages:
            base = (ROOT / page).parent
            for i, line in outside_fences(read(page)):
                for m in LINK.finditer(line):
                    target = m.group(1) or m.group(2) or m.group(3)
                    if re.match(r"^(https?:|mailto:)", target):
                        continue
                    path, _, anchor = target.partition("#")
                    file = (base / path).resolve() if path else ROOT / page
                    self.assertTrue(file.exists(), f"{page}:{i} -> {target}")
                    if anchor and file.suffix == ".md":
                        slugs = {slug(h) for level in (2, 3, 4) for h in headings(file.read_text(encoding="utf-8"), level)}
                        self.assertIn(anchor, slugs, f"{page}:{i} -> {target}")

    def test_every_image_is_ledgered_with_its_hash(self):
        ledger = json.loads(read("images/SOURCES.json"))
        entries = {e["file"]: e for e in ledger["images"] + ledger["icons"]}
        on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / "images").rglob("*") if p.suffix in (".png", ".jpg", ".svg")}
        self.assertEqual(on_disk, set(entries), "images/ and images/SOURCES.json list different files")
        for rel, entry in entries.items():
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), entry["sha256"], rel)
        for page in [p for pair in PAIRS for p in pair]:
            base = (ROOT / page).parent
            for m in LINK.finditer(read(page)):
                target = m.group(1) or m.group(2)
                if target and re.search(r"\.(png|jpg|svg)$", target) and not target.startswith("http"):
                    self.assertIn((base / target).resolve().relative_to(ROOT).as_posix(), entries, f"{page}: {target}")

    def test_figures_match_their_sources(self):
        spec = importlib.util.spec_from_file_location("build_diagram", ROOT / "tools" / "build_diagram.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ledger = json.loads(read("images/SOURCES.json"))
        self.assertEqual(module.check_icons(ledger), [])
        figures = {e["file"]: e for e in ledger["images"] if e["kind"] == "original explanatory diagram"}
        self.assertEqual(set(figures), {f"images/{n}-{lang}.png" for n in module.FIGURES for lang in ("en", "zh")})
        for rel, f in figures.items():
            html_sha = hashlib.sha256((ROOT / f["source"]).read_bytes()).hexdigest()
            self.assertEqual(f["source_sha256"], html_sha, f"{rel}: re-render with python tools/build_diagram.py")

    def test_data_matches_its_inputs(self):
        spec = importlib.util.spec_from_file_location("build_results", ROOT / "tools" / "build_results.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.build(), json.loads(read("data/results.json")), "run python tools/build_results.py")

    def test_numbers_in_results_come_from_data(self):
        """Whitelist direction: every number of 10 or more (or with decimals) quoted as a result must be a value in data/.
        Block quotes are verbatim inputs (prompts), and code spans name settings in the code; neither is a result."""
        data = json.loads(read("data/results.json"))
        ledger = json.loads(read("images/SOURCES.json"))
        machine = {float(x) for v in data["machine"].values() if isinstance(v, str) for x in re.findall(r"\d+(?:\.\d+)?", v)}
        allowed = displayed_forms(numeric_leaves(data, set()) | numeric_leaves(ledger["images"], set()) | machine)
        quoted = [(page, i, line) for page, title in RESULT_HEADINGS.items() for i, line in section(read(page), title)]
        quoted += [(page, i, line) for page in ("docs/RESULTS.md", "docs/RESULTS_CN.md") for i, line in outside_fences(read(page))]
        missing = []
        for page, i, line in quoted:
            if line.lstrip().startswith(">"):
                continue
            for m in NUMBER.finditer(SKIP_SPANS.sub(" ", line)):
                whole, frac = m.group(1).replace(",", ""), m.group(2)
                text = f"{whole}.{frac}" if frac else whole
                if not frac and int(whole) < 10:
                    continue
                if text not in allowed:
                    missing.append(f"{page}:{i}: {text}")
        self.assertEqual(missing, [], "numbers without a value in data/results.json or images/SOURCES.json")

    def test_no_private_hosts_paths_or_keys(self):
        findings = []
        for p in sorted(ROOT.rglob("*")):
            rel = p.relative_to(ROOT).as_posix()
            if not p.is_file() or p.suffix not in TEXT_SUFFIXES or any(part in (".venv", "venv", "vendor", "cad_cache", "cad_cache_en",
                                                                                   "render_cache", "cad_out", "__pycache__") for part in p.parts):
                continue
            if rel in ("studio/static/icons/lucide.min.js", "tests/test_repo.py"):
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for pattern, what in PRIVATE:
                    if pattern.search(line):
                        findings.append(f"{rel}:{i}: {what}")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
