"""Audit the exact public allowlist for private identifiers and secrets."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_customer_package.py"
TEXT_SUFFIXES = {
    "",
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
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
PRIVATE_PROJECT_TERMS = (
    "Yun" + "shang",
    "Len" + "ovo",
    "Qi" + "ra",
    "AI-" + "Super-Agent",
)
PATTERNS = {
    "private project term": re.compile(
        "|".join(re.escape(term) for term in PRIVATE_PROJECT_TERMS),
        re.I,
    ),
    "Azure resource ID": re.compile(r"/subscriptions/[0-9a-f-]{36}/", re.I),
    "Windows user path": re.compile(r"[A-Za-z]:\\Users\\", re.I),
    "WSL absolute path": re.compile(r"/mnt/[a-z]/", re.I),
    "Microsoft account": re.compile(r"\b[A-Z0-9._%+-]+@microsoft\.com\b", re.I),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\bgh[opsu]_[A-Za-z0-9]{30,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def _builder():
    specification = importlib.util.spec_from_file_location("public_builder", BUILDER_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _texts(path: Path) -> list[str]:
    if path.suffix.casefold() in TEXT_SUFFIXES:
        return [path.read_text(encoding="utf-8")]
    if path.suffix.casefold() == ".pptx":
        try:
            with ZipFile(path) as archive:
                return [
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in archive.namelist()
                    if name.endswith((".xml", ".rels"))
                ]
        except BadZipFile as error:
            raise RuntimeError(f"Invalid PPTX in public allowlist: {path}") from error
    return []


def main() -> int:
    builder = _builder()
    findings: list[str] = []
    files = builder.package_files()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if path.name == "password.txt" or relative.startswith(("logs/", "runtime/", ".azure/")):
            findings.append(f"forbidden path: {relative}")
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        for text in _texts(path):
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{label}: {relative}")
    if findings:
        raise SystemExit("Public package audit failed:\n- " + "\n- ".join(sorted(set(findings))))
    print(f"PASS: {len(files)} allowlisted public files contain no private identifiers or secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
