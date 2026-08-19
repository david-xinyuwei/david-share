"""Fail when public files contain likely secrets or private-environment values."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".venv", "__pycache__", "live-evidence", "runtime", "upstream"}
TEXT_SUFFIXES = {"", ".json", ".md", ".ps1", ".py", ".svg", ".txt", ".yml"}
SELF = Path(__file__).name

PATTERNS = {
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._-]{30,}\b", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
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


def public_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file() or path.name == SELF:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.casefold() in TEXT_SUFFIXES:
            yield path


def findings(root: Path = ROOT, extra_files: tuple[Path, ...] = ()) -> list[str]:
    errors: list[str] = []
    paths = list(public_files(root))
    for extra in extra_files:
        resolved = extra.resolve()
        if not resolved.is_file():
            errors.append(f"{extra}: extra audit file is missing")
        elif resolved not in paths:
            paths.append(resolved)
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
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