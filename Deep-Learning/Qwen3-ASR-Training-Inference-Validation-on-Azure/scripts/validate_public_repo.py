"""Public repo validation checks for the Qwen3-ASR Azure guide.

The checks are deterministic and offline. They focus on common public-repo delivery
risks: missing required files, broken local links, unparsable JSON evidence,
missing bilingual major sections, and obvious secret/private-environment leakage.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "README-CN.md",
    "ATTRIBUTION.md",
    "VALIDATION_CHECKLIST.md",
    "EXTERNAL-SOURCES.md",
    "requirements.txt",
    "configs/vllm.qwen3-asr.example.sh",
    "results/README.md",
]

SECRET_PATTERNS = [
    ("Hugging Face token", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    ("OpenAI-style key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("Azure subscription id", re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")),
    ("SSH command", re.compile("ssh" + "pa" + "ss" + r"|ssh\s+-p\s+\d+\s+" + "root" + "@", re.IGNORECASE)),
    ("Private Windows path", re.compile(r"[A-Z]:\\(AI-Super-Agent|Users|github|Backend-of-david-share)", re.IGNORECASE)),
]

TEXT_SUFFIXES = {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt"}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def check_required_files(errors: list[str]) -> None:
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            fail(f"missing required file: {rel}", errors)


def check_json_files(errors: list[str]) -> None:
    for path in (ROOT / "results").rglob("*.json"):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validator should report any parse failure.
            fail(f"invalid JSON: {path.relative_to(ROOT)} ({exc})", errors)


def check_local_links(errors: list[str]) -> None:
    for rel in ["README.md", "README-CN.md"]:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)|!\[[^\]]*\]\(([^)]+)\)", text)
        for normal, image in links:
            target = normal or image
            if not target or re.match(r"https?://", target) or target.startswith("#"):
                continue
            target_path = (path.parent / target.split("#", 1)[0]).resolve()
            try:
                target_path.relative_to(ROOT.resolve())
            except ValueError:
                fail(f"link escapes repo: {rel} -> {target}", errors)
                continue
            if not target_path.exists():
                fail(f"broken local link: {rel} -> {target}", errors)


def check_bilingual_sections(errors: list[str]) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README-CN.md").read_text(encoding="utf-8")
    en_major = re.findall(r"^## ", readme, flags=re.MULTILINE)
    cn_major = re.findall(r"^## ", readme_cn, flags=re.MULTILINE)
    if len(en_major) != len(cn_major):
        fail(f"major section count mismatch: README.md={len(en_major)} README-CN.md={len(cn_major)}", errors)
    required_phrases = ["Mission Coverage Snapshot", "Current Limitations", "References"]
    for phrase in required_phrases:
        if phrase not in readme:
            fail(f"README.md missing phrase: {phrase}", errors)
    required_cn_phrases = ["作战目标覆盖表", "当前限制", "References"]
    for phrase in required_cn_phrases:
        if phrase not in readme_cn:
            fail(f"README-CN.md missing phrase: {phrase}", errors)


def check_secret_patterns(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "validate_public_repo.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"possible secret/private data ({name}): {path.relative_to(ROOT)}", errors)


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_json_files(errors)
    check_local_links(errors)
    check_bilingual_sections(errors)
    check_secret_patterns(errors)

    if errors:
        print("VALIDATION FAILED")
        for item in errors:
            print(f"- {item}")
        return 1

    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
