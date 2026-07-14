"""Validate the public, sanitized evidence record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageStat


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence_path = root / "evidence" / "outlook-draft-probe.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["result"] == "pass"
    assert evidence["eml"]["x_unsent"] == "1"
    assert evidence["eml"]["recipient_count"] == 0
    assert evidence["eml"]["attachment_count"] == 2
    assert evidence["automatic_send"] is False
    assert evidence["new_outlook_window"]["count_delta"] == 1
    screenshot = evidence["documentation_screenshot"]
    screenshot_path = root / screenshot["path"]
    image = Image.open(screenshot_path)
    assert screenshot["sanitized_derivative"] is True
    assert image.size == (screenshot["width"], screenshot["height"])
    assert screenshot_path.stat().st_size == screenshot["bytes"]
    assert hashlib.sha256(screenshot_path.read_bytes()).hexdigest() == screenshot["sha256"]
    assert all(variance > 100 for variance in ImageStat.Stat(image.convert("RGB")).var)
    print("PASS: sanitized New Outlook evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())