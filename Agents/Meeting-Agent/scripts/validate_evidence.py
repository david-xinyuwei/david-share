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

    aoai = json.loads(
        (root / "evidence" / "aoai-live-validation.json").read_text(encoding="utf-8")
    )
    assert aoai["result"] == "pass"
    assert aoai["runtime"] == {
        "product": "Azure OpenAI Responses API",
        "model": "gpt-5.4",
        "model_version": "2026-03-05",
        "model_sku": "GlobalStandard",
        "reasoning_effort": "medium",
        "store": False,
        "http_status": 200,
        "python_runtime": "python_3_12",
    }
    assert len(aoai["source"]["content_sha256"]) == 64
    assert aoai["artifacts"]["presentation"]["slides"] == 6
    assert aoai["artifacts"]["mind_map_mermaid"]["bytes"] > 0
    assert aoai["artifacts"]["eml"]["x_unsent"] == "1"
    assert aoai["artifacts"]["eml"]["attachment_count"] == 2
    for artifact in aoai["artifacts"].values():
        assert artifact["bytes"] > 0
        assert len(artifact["sha256"]) == 64
    browser = aoai["browser"]
    assert browser["runtime_label"] == "Azure OpenAI Responses API"
    assert browser["model_label"] == "gpt-5.4 · reasoning medium"
    assert browser["console_errors"] == 0
    assert browser["failed_requests"] == 0
    assert browser["desktop_viewport"]["horizontal_overflow"] is False
    assert browser["mobile_viewport"] == {
        "width": 390,
        "height": 844,
        "horizontal_overflow": False,
        "mermaid_visible": True,
        "artifact_action_count": 4,
    }
    assert browser["mermaid"]["width"] >= 300
    assert browser["mermaid"]["height"] >= 150
    assert browser["mermaid"]["groups"] > 20
    assert browser["outlook_enabled"] is True
    live_screenshot = browser["screenshot"]
    live_screenshot_path = root / live_screenshot["path"]
    live_image = Image.open(live_screenshot_path)
    assert live_image.size == (live_screenshot["width"], live_screenshot["height"])
    assert live_screenshot_path.stat().st_size == live_screenshot["bytes"]
    assert (
        hashlib.sha256(live_screenshot_path.read_bytes()).hexdigest()
        == live_screenshot["sha256"]
    )
    assert aoai["automatic_send"] is False
    assert aoai["redaction"]["sanitized"] is True
    print("PASS: sanitized Outlook and live AOAI evidence are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())