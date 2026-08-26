"""Validate the committed sanitized runtime evidence and scenario boundaries."""

from __future__ import annotations

import json
import struct
from pathlib import Path

if __package__:
    from .evidence_provenance import canonical_sha256_file, sha256_file, source_snapshot
else:
    from evidence_provenance import canonical_sha256_file, sha256_file, source_snapshot

ROOT = Path(__file__).resolve().parents[1]
MONOREPO_ROOT = ROOT.parents[1]


def main() -> int:
    evidence = json.loads((ROOT / "evidence/live-validation.json").read_text(encoding="utf-8"))
    publication = json.loads(
        (ROOT / "evidence/publication-validation.json").read_text(encoding="utf-8")
    )
    screenshots = json.loads(
        (ROOT / "evidence/scenario-screenshots.json").read_text(encoding="utf-8")
    )
    scenario = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))

    assert evidence["evidence_type"] == "sanitized-runtime-summary"
    assert evidence["voice_live"]["session_updated"] is True
    assert evidence["voice_live"]["registered_tool_count"] == 24
    assert evidence["voice_live"]["server_accepted_tool_count"] == 24
    assert evidence["voice_live"]["model"] == "gpt-realtime"
    assert evidence["voice_live"]["model_version"] == "2025-08-28"
    assert evidence["voice_live"]["model_version_source"] == "Azure Resource Manager deployment metadata"
    assert evidence["voice_live"]["input_transcription"] == "gpt-4o-transcribe"
    assert len(evidence["external_smoke"]) == 6
    assert all(item["result"] == "PASS" and item["source"] for item in evidence["external_smoke"])
    assert evidence["publication"]["raw_logs_public"] is False
    assert len(evidence["does_not_prove"]) >= 4

    assert publication["evidence_type"] == "publication-package-validation"
    assert publication["source_tree"] == source_snapshot(ROOT)
    workflow = MONOREPO_ROOT / publication["workflow"]["path"]
    assert workflow.is_file()
    assert publication["workflow"]["sha256"] == canonical_sha256_file(workflow)
    assert publication["package"]["artifact_published"] is False
    assert publication["package"]["bytes"] > 0
    assert len(publication["package"]["sha256"]) == 64
    assert publication["packaged_self_check"]["result"] == "PASS"
    assert publication["packaged_self_check"]["passed"] >= 17
    assert publication["packaged_self_check"]["failed"] == 0
    assert publication["packaged_self_check"]["side_effects"] == []

    package_path = ROOT / publication["package"]["path"]
    self_check_path = ROOT / publication["packaged_self_check"]["path"]
    if package_path.exists():
        assert publication["package"]["bytes"] == package_path.stat().st_size
        assert publication["package"]["sha256"] == sha256_file(package_path)
    if self_check_path.exists():
        assert publication["packaged_self_check"]["sha256"] == sha256_file(self_check_path)

    assert screenshots["evidence_type"] == "sanitized-scenario-screenshots"
    assert screenshots["source"]["publicly_available"] is False
    assert screenshots["source"]["review_copy_speed"] == 1.5
    expected_screenshot_ids = {
        "medication-recognition",
        "email-receipt",
        "volume-control",
        "wallpaper-change",
    }
    assert {item["id"] for item in screenshots["scenarios"]} == expected_screenshot_ids
    for item in screenshots["scenarios"]:
        image_path = ROOT / item["image"]
        assert image_path.is_file(), image_path
        data = image_path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (item["width"], item["height"])
        offset = 8
        chunk_types: list[str] = []
        while offset < len(data):
            chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
            chunk_types.append(data[offset + 4 : offset + 8].decode("ascii"))
            offset += 12 + chunk_length
        assert not {"tEXt", "iTXt", "zTXt", "eXIf"} & set(chunk_types)
        assert image_path.stat().st_size == item["bytes"]
        assert sha256_file(image_path) == item["sha256"]
        assert item["tools"]
        assert item["observed_result"]
        assert item["redaction"]["removed"]
    assert not any(screenshots["privacy_assertions"].values())
    assert not list(ROOT.rglob("*.mp4"))

    ids = {item["id"] for item in scenario["scenarios"]}
    assert {"voice-live-conversation", "windows-device-control", "mail-delivery"} <= ids
    assert all(item["evidence"] for item in scenario["scenarios"])

    print(
        "PASS: evidence records the sanitized deployment version, 24 accepted tools, six live smoke checks, "
        "source/workflow/package hashes, four privacy-safe scenario screenshots, and explicit publication boundaries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
