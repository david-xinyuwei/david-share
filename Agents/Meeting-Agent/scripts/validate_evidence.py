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
        "authentication": "key",
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
    assert aoai["artifacts"]["eml"]["inline_mind_map"] is True
    for artifact in aoai["artifacts"].values():
        assert artifact["bytes"] > 0
        assert len(artifact["sha256"]) == 64
    browser = aoai["browser"]
    assert browser["runtime_label"] == "Azure OpenAI Responses API"
    assert browser["model_label"] == "gpt-5.4 · reasoning medium · key auth"
    assert browser["console_errors"] == 0
    assert browser["failed_requests"] == 0
    assert browser["desktop_viewport"]["horizontal_overflow"] is False
    assert browser["mobile_viewport"] == {
        "width": 390,
        "height": 844,
        "horizontal_overflow": False,
        "mind_map_visible": True,
        "artifact_action_count": 4,
    }
    assert browser["mind_map"]["layout"] == "six-card"
    assert browser["mind_map"]["width"] >= 300
    assert browser["mind_map"]["height"] >= 100
    assert browser["mind_map"]["natural_width"] == 1280
    assert browser["mind_map"]["natural_height"] == 720
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

    video = json.loads(
        (root / "evidence" / "meeting-agent-demo-video.json").read_text(
            encoding="utf-8"
        )
    )
    video_path = root / video["asset"]
    assert video_path.is_file()
    assert video_path.stat().st_size == video["output"]["bytes"]
    assert (
        hashlib.sha256(video_path.read_bytes()).hexdigest()
        == video["output"]["sha256"]
    )
    assert video["output"]["codec"] == "h264"
    assert video["output"]["width"] == video["source"]["width"] == 2392
    assert video["output"]["height"] == video["source"]["height"] == 1500
    assert video["output"]["frames"] == video["source"]["frames"] == 3860
    assert 1.595 <= video["output"]["speed"] <= 1.605
    assert video["output"]["ssim"] >= 0.995
    assert video["output"]["psnr_db"] >= 40
    assert video["browser_playback"] == {
        "protocol": "http",
        "ready_state": 4,
        "duration_seconds": 80.4375,
        "width": 2392,
        "height": 1500,
        "media_error": None,
        "playback_started": True,
    }
    assert video["distribution"] == {
        "user_attachment_url": (
            "https://github.com/user-attachments/assets/"
            "023f22f0-31f2-4039-85f0-e22712770ff2"
        ),
        "github_native_player_verified": True,
        "duration_seconds": 80.4375,
        "width": 2392,
        "height": 1500,
        "ready_state": 4,
        "media_error": None,
    }
    assert all(video["assertions"].values())

    differential = json.loads(
        (root / "evidence" / "aoai-runtime-differential.json").read_text(
            encoding="utf-8"
        )
    )
    assert differential["result"] == "pass"
    assert differential["runtime"] == {
        "product": "Azure OpenAI Responses API",
        "authentication": "key",
        "model": "gpt-5.4",
        "reasoning_effort": "medium",
        "store": False,
    }
    assert len(differential["runs"]) == 2
    first_run, second_run = differential["runs"]
    assert first_run["source_sha256"] != second_run["source_sha256"]
    assert first_run["title"] != second_run["title"]
    assert first_run["http_status"] == second_run["http_status"] == 200
    for name in ("analysis", "mind_map_png", "presentation", "eml"):
        first_hash = first_run["artifacts"][name]["sha256"]
        second_hash = second_run["artifacts"][name]["sha256"]
        assert len(first_hash) == len(second_hash) == 64
        assert first_hash != second_hash
        assert differential["assertions"]["artifact_hashes_differ"][name] is True
    assert differential["assertions"]["source_hashes_differ"] is True
    assert differential["assertions"]["titles_differ"] is True
    assert differential["assertions"]["live_model_response_id_present"] is True
    assert differential["assertions"]["differential_model_response_id_present"] is True
    assert differential["assertions"]["real_delta_precedes_analysis"] is True
    assert differential["redaction"]["sanitized"] is True
    print("PASS: sanitized Outlook and live AOAI evidence are internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())