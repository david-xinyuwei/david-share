"""Fail when public files contain likely secrets or private-environment values."""

from __future__ import annotations

import argparse
import os
import re
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "__pycache__", "live-evidence", "runtime", "upstream"}
TEXT_SUFFIXES = {
    "",
    ".json",
    ".lock",
    ".md",
    ".ps1",
    ".py",
    ".svg",
    ".txt",
    ".yml",
    ".yaml",
}

PATTERNS = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._-]{30,}\b", re.IGNORECASE),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Azure storage key": re.compile(r"\bAccountKey=[A-Za-z0-9+/]{40,}={0,2}", re.IGNORECASE),
    "Azure SAS": re.compile(r"(?:^|[?&])sig=[A-Za-z0-9%+/]{20,}", re.IGNORECASE),
    "Azure UUID": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "Azure resource ID": re.compile(r"/subscriptions/[0-9a-f-]{36}/", re.IGNORECASE),
    "Windows user path": re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    "WSL absolute path": re.compile(r"/mnt/[a-z]/", re.IGNORECASE),
    "work email": re.compile(r"\b[A-Z0-9._%+-]+@microsoft\.com\b", re.IGNORECASE),
    "tenant domain": re.compile(r"\.onmicrosoft\.com\b", re.IGNORECASE),
    "cloud VM": re.compile(r"\.cloudapp\.azure\.com\b", re.IGNORECASE),
}
PRIVATE_TERMS = (
    "AI-" + "Super-Agent",
    "Len" + "ovo",
    "总" + "司令",
    "作" + "战",
)


def is_reparse(path: Path) -> bool:
    metadata = path.lstat()
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(
        attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def public_files(root: Path) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    errors: list[str] = []
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        retained: list[str] = []
        for directory in directories:
            path = current_path / directory
            if directory in SKIP_PARTS:
                continue
            if is_reparse(path):
                errors.append(f"{path.relative_to(root)}: symlink or reparse point")
                continue
            retained.append(directory)
        directories[:] = retained
        for filename in files:
            path = current_path / filename
            if is_reparse(path):
                errors.append(f"{path.relative_to(root)}: symlink or reparse point")
                continue
            if path.suffix.casefold() not in TEXT_SUFFIXES:
                errors.append(f"{path.relative_to(root)}: unsupported public file format")
                continue
            paths.append(path)
    return paths, errors


def findings(root: Path = ROOT, extra_files: tuple[Path, ...] = ()) -> list[str]:
    paths, errors = public_files(root)
    for extra in extra_files:
        resolved = extra.resolve()
        if not resolved.is_file():
            errors.append(f"{extra}: extra audit file is missing")
        elif resolved not in paths:
            paths.append(resolved)
    for path in paths:
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{relative}: text file is not valid UTF-8")
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                if name == "work email" and match.group(0).casefold().endswith("@example.invalid"):
                    continue
                errors.append(f"{relative}: {name}")
        for term in PRIVATE_TERMS:
            if term.casefold() in text.casefold():
                errors.append(f"{relative}: private project term")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra", action="append", type=Path, default=[])
    args = parser.parse_args()
    errors = findings(extra_files=tuple(args.extra))
    if errors:
        print("PUBLIC_BOUNDARY=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PUBLIC_BOUNDARY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())