"""Validate and summarize the MAI image-edit input-count evidence offline.

Answers three separable questions from saved records only, with no model calls:

  * capability - what a single-image edit and a two-image edit actually return,
    each measured with a prompt that its input count can satisfy;
  * attribution - whether the second image influenced the result, measured with
    one prompt held constant while only the images change;
  * accepted contract - which multipart field names and image counts the service
    itself accepts, taken from its own validation messages.

The distinction matters because an earlier run reused a plural prompt for a
single input. That output cannot represent single-image quality, so this module
refuses to label any attribution-group arm as a capability result, and requires
the capability arms to carry their own matched prompts.

It also checks whether returned PNGs carry an alpha channel, because a white
background produced by the model is not a transparent cutout.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

CAPABILITY_LABELS = ("single_image_matched_prompt", "two_images_matched_prompt")
ATTRIBUTION_LABELS = ("single_image", "two_image_fields", "fixed_prompt_image_two_only")
REJECTED_FIELD_SHAPES = ("image_array_suffix", "image_plural_field",
                         "numbered_fields", "prefixed_fields", "wrong_field_name_only")
SERVICE_LIMIT_TEXT = "Only 1 to 5 image files are supported for edit requests."
FIELD_PREFIX_TEXT = "File must be attached in a form field with a name starting with 'image'."


def load(path):
    return json.loads(Path(path).read_text("utf-8"))


def png_facts(path):
    """Read dimensions and colour type; colour type 2 and 0 carry no alpha channel."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")
    width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
    return {"width": width, "height": height, "bit_depth": depth, "colour_type": colour,
            "has_alpha_channel": colour in (4, 6), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def index_by(records, *keys):
    table = {}
    for record in records:
        for key in keys:
            value = record.get(key)
            if value:
                table[value] = record
    return table


def summarize(archive):
    archive = Path(archive)
    clean = load(archive / "clean-results.json")
    shapes = load(archive / "field-shape-results.json")
    limit = load(archive / "limit-probe-results.json")

    clean_by = index_by(clean["attempts"], "label")
    shape_by = index_by(shapes["attempts"], "shape", "label")

    capability = []
    for label in CAPABILITY_LABELS:
        record = clean_by.get(label)
        if record is None:
            raise ValueError(f"Capability arm missing: {label}")
        if record.get("outcome") != "RETURNED_IMAGE":
            raise ValueError(f"Capability arm returned no image: {label}")
        prompt = record["prompt"]
        count = record["image_count"]
        singular = "the reference image" in prompt or "reference image alone" in prompt
        plural = "both reference images" in prompt
        if count == 1 and not singular:
            raise ValueError(f"Single-image capability arm needs a singular prompt: {label}")
        if count == 2 and not plural:
            raise ValueError(f"Two-image capability arm needs a plural prompt: {label}")
        image = archive / record["output_path"]
        capability.append({"label": label, "image_count": count, "prompt": prompt,
                           "request_seconds": record["request_seconds"],
                           "status_code": record["status_code"],
                           "output": record["output_path"], "png": png_facts(image)})

    attribution = []
    prompts = set()
    for label in ATTRIBUTION_LABELS:
        record = clean_by.get(label) or shape_by.get(label)
        if record is None:
            raise ValueError(f"Attribution arm missing: {label}")
        if record.get("outcome") not in ("RETURNED_IMAGE", "ACCEPTED_RETURNED_IMAGE"):
            raise ValueError(f"Attribution arm returned no image: {label}")
        prompt = record.get("prompt") or clean["prompts"]["fixed"]
        prompts.add(prompt)
        stored = record["output_path"]
        candidate = archive / stored
        if not candidate.is_file():
            candidate = archive / f"attribution_{stored}"
        if not candidate.is_file():
            raise ValueError(f"Attribution image missing for {label}: {stored}")
        attribution.append({"label": label, "image_count": record.get("image_count",
                                                                      len(record.get("input_images") or [])),
                            "inputs": record.get("input_images"),
                            "request_seconds": record["request_seconds"],
                            "output": candidate.name, "png": png_facts(candidate)})
    if len(attribution) != 3:
        raise ValueError("Attribution needs both single-image arms and the two-image arm")

    contract = {"service_limit_message": None, "field_prefix_message": None,
                "rejected_shapes": [], "quota_limited_counts": [], "rejected_counts": []}
    limit_records = (limit.get("service_contract") or []) + (limit.get("count_limit") or [])
    for record in limit_records:
        payload = record.get("error_payload") or {}
        message = payload.get("message") if isinstance(payload, dict) else ""
        # The service prefixes its validation text with "Invalid request. Error => ".
        if SERVICE_LIMIT_TEXT in message:
            contract["service_limit_message"] = SERVICE_LIMIT_TEXT
            if record.get("image_count"):
                contract["rejected_counts"].append(record["image_count"])
        if FIELD_PREFIX_TEXT in message:
            contract["field_prefix_message"] = FIELD_PREFIX_TEXT
        if record.get("status_code") == 429 and record.get("image_count"):
            contract["quota_limited_counts"].append(record["image_count"])
    limit_by_label = {record.get("label"): record for record in limit_records}
    for label in REJECTED_FIELD_SHAPES:
        record = limit_by_label.get(label) or shape_by.get(label)
        if record and record.get("status_code") == 400:
            contract["rejected_shapes"].append(label)
    if contract["service_limit_message"] is None:
        raise ValueError("Service-stated image-count limit not found in evidence")
    if contract["field_prefix_message"] is None:
        raise ValueError("Service-stated field-name rule not found in evidence")

    alpha = [entry for entry in capability + attribution if entry["png"]["has_alpha_channel"]]
    return {
        "archive": archive.as_posix(),
        "model_deployment": clean["model_deployment"],
        "measured_at_utc": [clean["started_at_utc"], clean.get("ended_at_utc")],
        "capability": capability,
        "attribution": attribution,
        "attribution_prompt_held_constant": len(prompts) == 1,
        "attribution_prompts": sorted(prompts),
        "contract": contract,
        "any_output_has_alpha_channel": bool(alpha),
        "transparent_cutout_supported": bool(alpha),
        "complete": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero unless the evidence satisfies every requirement")
    args = parser.parse_args()
    summary = summarize(args.archive)
    if args.check:
        problems = []
        if len(summary["capability"]) != 2:
            problems.append("capability arms")
        if len(summary["attribution"]) != 3:
            problems.append("attribution arms")
        if summary["transparent_cutout_supported"]:
            problems.append("unexpected alpha channel")
        print(json.dumps({"status": "PASS" if not problems else "FAIL",
                          "problems": problems}, ensure_ascii=False))
        return 1 if problems else 0
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
