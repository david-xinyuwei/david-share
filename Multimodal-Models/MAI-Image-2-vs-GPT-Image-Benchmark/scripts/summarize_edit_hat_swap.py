"""Validate and summarize the headwear-replacement edit test offline.

One photograph was sent to the edit endpoint of every measured configuration
with a prompt that asks for exactly one change and lists what must stay the same.
That makes the result checkable item by item without an aesthetic score: did the
headwear change, and did the face, robe, bystanders, title and framing survive.

This module ties the published PNGs to the request records by SHA-256, confirms
the review covers every returned image, and exposes per-configuration latency,
output dimensions and the preservation checklist for the report. No model calls.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_paired_run import GROUPS

REVIEW_CHECKS = (
    "headwear_replaced_with_graduation_cap",
    "face_and_beard_preserved",
    "robe_embroidery_preserved",
    "bystanders_and_background_unchanged",
    "title_and_seal_preserved",
    "input_aspect_ratio_preserved",
)


def png_dimensions(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")
    width, height, _, colour = struct.unpack(">IIBB", data[16:26])
    return width, height, colour


def jpeg_dimensions(path):
    """Read width/height from JPEG SOF markers without a decoder dependency."""
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"Not a JPEG: {path}")
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[offset + 5:offset + 9])
            return width, height
        length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
        offset += 2 + length
    raise ValueError("JPEG SOF marker not found")


def _round_outputs(archive, results, review, relative_dir, source_sha, source_w, source_h):
    """Tie one round's PNGs to its request records and review, in GROUPS order.

    `relative_dir` is "" for round 1 (flat archive root, the original layout) and
    "r2" for the repeat, so every published path stays relative to the archive.
    """
    if results["source_sha256"] != source_sha:
        raise ValueError(f"{relative_dir or 'round 1'}: request record used a different input image")
    if not review["input_sha256"] or not source_sha.startswith(review["input_sha256"]):
        raise ValueError(f"{relative_dir or 'round 1'}: review does not refer to the published input")
    by_label = {attempt["label"]: attempt for attempt in results["attempts"]}
    if set(by_label) != set(GROUPS):
        raise ValueError(f"Expected one attempt per configuration, found {sorted(by_label)}")
    if set(review["per_output"]) != set(GROUPS):
        raise ValueError("Review must cover every configuration")

    outputs = []
    for group in GROUPS:
        attempt = by_label[group]
        if attempt.get("outcome") != "RETURNED_IMAGE":
            raise ValueError(f"{group} returned no image")
        relative = f"{relative_dir}/{attempt['output_path']}" if relative_dir else attempt["output_path"]
        path = archive / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != attempt["output_sha256"]:
            raise ValueError(f"{group}: published PNG does not match the recorded hash")
        width, height, colour = png_dimensions(path)
        checks = review["per_output"][group]
        if any(check not in checks for check in REVIEW_CHECKS):
            raise ValueError(f"{group}: review is missing a checklist item")
        preserved = sum(1 for check in REVIEW_CHECKS[1:] if checks[check])
        outputs.append({
            "group": group,
            "request_seconds": attempt["request_seconds"],
            "status_code": attempt["status_code"],
            "attempts_used": attempt.get("attempts_used", 1),
            "output": relative,
            "output_sha256": digest,
            "output_kib": path.stat().st_size / 1024,
            "width": width, "height": height, "colour_type": colour,
            "keeps_input_aspect": abs(width / height - source_w / source_h) < 0.02,
            "checks": {check: bool(checks[check]) for check in REVIEW_CHECKS},
            "preserved_count": preserved,
            "preserved_total": len(REVIEW_CHECKS) - 1,
            "observation": checks["observation"],
        })
    return outputs


def summarize(archive):
    archive = Path(archive)
    source = archive / "input.jpg"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    source_w, source_h = jpeg_dimensions(source)

    # Round 1 lives at the archive root; each repeat lives in r<N>/ with the same
    # three files, so a second round is added by dropping in a directory, not by
    # rewriting the first round's evidence.
    round_dirs = [("", 1)] + sorted(
        ((p.name, int(p.name[1:])) for p in archive.glob("r[0-9]*") if p.is_dir()),
        key=lambda item: item[1])
    rounds = []
    prompt = None
    gpt_size = None
    supersedes = None
    summary_observation = None
    for relative_dir, number in round_dirs:
        base = archive / relative_dir if relative_dir else archive
        results = json.loads((base / "edit-results.json").read_text("utf-8"))
        review = json.loads((base / "edit-review.json").read_text("utf-8"))
        if prompt is None:
            prompt = results["prompt"]
        elif results["prompt"] != prompt:
            raise ValueError(f"{relative_dir}: prompt differs from round 1")
        if results.get("round", 1) != number:
            raise ValueError(f"{relative_dir}: record says round {results.get('round', 1)}")
        # The size parameter sent to GPT is part of the protocol; it must be recorded
        # and identical across rounds, otherwise rounds are not comparable.
        this_size = results.get("gpt_size_parameter")
        if this_size is None:
            raise ValueError(f"{relative_dir or 'round 1'}: record does not state the GPT size parameter")
        if gpt_size is None:
            gpt_size = this_size
        elif this_size != gpt_size:
            raise ValueError(f"{relative_dir}: GPT size parameter {this_size!r} differs from round 1 {gpt_size!r}")
        if number == 1:
            supersedes = review.get("supersedes")
            summary_observation = review.get("summary_observation")
        rounds.append({
            "round": number,
            "order_sent": [attempt["label"] for attempt in results["attempts"]],
            "measured_at_utc": [results["started_at_utc"], results.get("ended_at_utc")],
            "outputs": _round_outputs(archive, results, review, relative_dir,
                                      source_sha, source_w, source_h),
            "review_method": review["method"],
            "boundary": review["boundary"],
        })

    first = rounds[0]
    return {
        "archive": archive.as_posix(),
        "prompt": prompt,
        "gpt_size_parameter": gpt_size,
        "supersedes": supersedes,
        "summary_observation": summary_observation,
        "source": {"file": source.name, "sha256": source_sha, "bytes": source.stat().st_size,
                   "width": source_w, "height": source_h},
        "rounds": rounds,
        # Round-1 fields kept at the top level so existing readers keep working.
        "measured_at_utc": first["measured_at_utc"],
        "outputs": first["outputs"],
        "review_method": first["review_method"],
        "boundary": first["boundary"],
        "complete": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    summary = summarize(arguments.archive)
    if arguments.check:
        print(json.dumps({"status": "PASS", "rounds": len(summary["rounds"]),
                          "outputs": sum(len(r["outputs"]) for r in summary["rounds"])}))
        return 0
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
