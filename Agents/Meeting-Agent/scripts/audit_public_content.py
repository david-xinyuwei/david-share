"""Fail CI when public text contains likely secrets or private project details."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".azure",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "artifacts",
    "build",
    "dist",
    "node_modules",
    "playwright-report",
    "runtime",
    "test-results",
}
SKIP_FILES = {"password.txt", Path(__file__).name}
LEGACY_TERMS = ("Yun" + "shang", "云" + "上", "xinyuwei" + "-david")
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".eml",
    ".example",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".svg",
    ".toml",
    ".txt",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "Windows absolute path": re.compile(r"\b[A-Za-z]:\\"),
    "WSL absolute path": re.compile(r"/mnt/[a-z]/", re.I),
    "private Linux path": re.compile(r"/(?:root|home)/[A-Za-z0-9._-]+/"),
    "Azure resource ID": re.compile(r"/subscriptions/[0-9a-f-]{36}/", re.I),
    "IPv4 address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "private project term": re.compile(
        r"Lenovo|Qira|Jessie|智迪|AI-Super-Agent|Backend-of-david-share|"
        + "|".join(re.escape(term) for term in LEGACY_TERMS)
        + r"|总司令|军规|柯南|大魏",
        re.I,
    ),
}


def public_text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
        and path.name not in SKIP_FILES
        and path.is_file()
        and path.suffix.casefold() in TEXT_SUFFIXES
    ]


def main() -> int:
    findings: list[str] = []
    paths = public_text_files()
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"invalid UTF-8: {path.relative_to(ROOT)}")
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(0).casefold()
                if label == "email address" and value.endswith(
                    ("@example.com", "@example.net", "@example.org")
                ):
                    continue
                if label == "IPv4 address" and value in {"0.0.0.0", "127.0.0.1"}:
                    continue
                if label == "private Linux path" and value.startswith("/home/session/"):
                    continue
                findings.append(f"{label}: {path.relative_to(ROOT)}")
                break
    assert "password.txt" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    if findings:
        raise SystemExit("Public-content audit failed:\n- " + "\n- ".join(findings))
    print(f"PASS: {len(paths)} public text files passed sanitization checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())