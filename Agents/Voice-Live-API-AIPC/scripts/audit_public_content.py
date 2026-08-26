"""Fail closed when public text contains secrets or private project identifiers."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "artifacts",
    "build",
    "dist",
    "logs",
    "node_modules",
}
SKIP_FILES = {Path(__file__).name}
TEXT_SUFFIXES = {
    "",
    ".cmd",
    ".example",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".svg",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
PATTERNS = {
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Azure resource ID": re.compile(r"/subscriptions/[0-9a-f-]{36}/", re.I),
    "specific Azure endpoint": re.compile(
        r"https://(?!<)[a-z0-9-]+\.(?:cognitiveservices|services\.ai|openai)\.azure\.com",
        re.I,
    ),
    "private project term": re.compile(
        r"Voice Agent Lenovo|AI-Super-Agent|Backend-of-david-share|"
        r"总司令|大魏|军规|ed3df1b6|a15bb3f6|davidsajare",
        re.I,
    ),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "Windows user path": re.compile(r"\b[A-Za-z]:\\Users\\(?!<you>)[^\\\s]+\\", re.I),
}
FORBIDDEN_NAMES = {".env", ".msal_token_cache.json", "password", "password.txt"}


def public_text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.name not in SKIP_FILES
        and path.name not in FORBIDDEN_NAMES
        and not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
        and path.suffix.casefold() in TEXT_SUFFIXES
    ]


def main() -> int:
    forbidden = [path.name for path in ROOT.rglob("*") if path.name in FORBIDDEN_NAMES]
    if forbidden:
        raise SystemExit("Forbidden local files: " + ", ".join(sorted(set(forbidden))))

    findings: list[str] = []
    paths = public_text_files()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            matches = list(pattern.finditer(text))
            if label == "email address":
                matches = [
                    match
                    for match in matches
                    if not match.group(0).casefold().endswith(
                        ("@example.com", "@example.net", "@example.org")
                    )
                ]
            if matches:
                findings.append(f"{label}: {path.relative_to(ROOT)}")

    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for required in (".env", ".msal_token_cache.json", "password", "password.txt"):
        if required not in ignored:
            findings.append(f"missing .gitignore rule: {required}")

    if findings:
        raise SystemExit("Public-content audit failed:\n- " + "\n- ".join(findings))
    print(f"PASS: {len(paths)} public text files contain no secret or private identifiers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
