"""Validate the public, sanitized evidence record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageStat


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence = json.loads(
        (root / "evidence" / "outlook-draft-probe.json").read_text(encoding="utf-8")
    )
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

    foundry = json.loads(
        (root / "evidence" / "foundry-live-validation.json").read_text(encoding="utf-8")
    )
    assert foundry["result"] == "pass"
    assert foundry["runtime"]["agent_status"] == "active"
    assert foundry["runtime"]["protocol"] == "Invocations 2.0.0"
    assert foundry["differential"] == {
        "source_hashes_distinct": True,
        "analysis_outputs_distinct": True,
    }
    assert len(foundry["runs"]) == 2
    assert len({run["source_sha256"] for run in foundry["runs"]}) == 2
    assert len({run["title"] for run in foundry["runs"]}) == 2
    for run in foundry["runs"]:
        assert len(run["source_sha256"]) == 64
        for artifact in run["artifacts"].values():
            assert artifact["bytes"] > 0
            assert len(artifact["sha256"]) == 64
    browser = foundry["browser"]
    assert browser["mode"] == "Microsoft Foundry"
    assert browser["console_errors"] == 0
    assert browser["failed_requests"] == 0
    assert browser["eml_attachment_count"] == 2
    assert browser["desktop_viewport"]["horizontal_overflow"] is False
    assert browser["mobile_viewport"]["horizontal_overflow"] is False
    live_screenshot = browser["screenshot"]
    live_screenshot_path = root / live_screenshot["path"]
    live_image = Image.open(live_screenshot_path)
    assert live_image.size == (live_screenshot["width"], live_screenshot["height"])
    assert live_screenshot_path.stat().st_size == live_screenshot["bytes"]
    assert (
        hashlib.sha256(live_screenshot_path.read_bytes()).hexdigest()
        == live_screenshot["sha256"]
    )
    assert foundry["automatic_send"] is False
    assert foundry["redaction"]["sanitized"] is True
    print("PASS: sanitized Outlook and live Foundry evidence are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())