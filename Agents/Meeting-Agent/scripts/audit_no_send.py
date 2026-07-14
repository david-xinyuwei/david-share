"""Fail CI if a source file adds an automatic mail transmission path."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = (ROOT / "src", ROOT / "scripts")
FORBIDDEN = {
    "Graph sendMail": re.compile(r"\bsendMail\b", re.IGNORECASE),
    "message send endpoint": re.compile(r"[/'\"]send(?:\b|[/'\"])", re.IGNORECASE),
    "SMTP client": re.compile(r"\bsmtplib\b|\bSMTP\s*\(", re.IGNORECASE),
    "Outlook object-model Send": re.compile(r"MailItem\s*\.\s*Send", re.IGNORECASE),
    "UI Send activation": re.compile(
        r"(?:GetInvokePattern|\.Click\s*\().{0,160}(?:Send|发送)",
        re.IGNORECASE | re.DOTALL,
    ),
}


def main() -> int:
    findings: list[str] = []
    for source_dir in SOURCE_DIRS:
        for path in source_dir.rglob("*.py"):
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            for label, pattern in FORBIDDEN.items():
                if pattern.search(text):
                    findings.append(f"{label}: {path.relative_to(ROOT)}")
    if findings:
        print("Automatic-send audit failed:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1
    print("PASS: no automatic mail transmission path found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())