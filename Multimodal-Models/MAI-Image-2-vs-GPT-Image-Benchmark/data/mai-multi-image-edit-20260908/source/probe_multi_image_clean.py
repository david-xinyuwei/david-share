"""Measure MAI-Image-2.6 single-image versus multi-image edits without a self-contradicting prompt.

An earlier probe reused one plural prompt ("combine the reference images") for a
single-image call, which asks for something the input cannot satisfy. That output
therefore cannot represent single-image edit quality. This run separates the two
questions that were previously conflated:

Group A, capability: each input count receives a prompt it can actually satisfy,
so the returned image represents that usage honestly. Because the prompts differ,
Group A cannot attribute a difference to the extra image.

Group B, attribution: the prompt is held constant while only the images change,
and both single-image arms are run so the comparison is symmetric. Each image's
unique elements should appear only when that image is present. The fixed prompt
is under-determined for a single input, so Group B measures attribution only and
is not evidence of single-image edit quality.
"""

import base64
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

WORKSPACE = Path(__file__).resolve().parent
OUTPUT = WORKSPACE / "runs" / "multi-image-clean-20260908"
ARCHIVE = Path("C:/david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark"
               "/data/lenovo-web-grounding-20260908")
EDITS_PATH = "/mai/v1/images/edits"
TIMEOUT_SECONDS = 300
INTER_CALL_WAIT = 35.0
DEPLOYMENT = "MAI-Image-2.6"

IMAGE_ONE = ARCHIVE / "mai-image-2.6-web-off" / "r1" / "01_test.png"
IMAGE_TWO = ARCHIVE / "mai-image-2.6-web-off" / "r1" / "02_test.png"

SINGLE_PROMPT = ("Show the laptop from the reference image alone on a plain white studio "
                 "background as a clean product photograph.")
MULTI_PROMPT = ("Show the laptops from both reference images together on one plain white "
                "studio background as a clean product photograph.")
FIXED_PROMPT = ("Place every laptop that appears in the reference images on one plain white "
                "studio background as a clean product photograph.")

sys.path.insert(0, str(WORKSPACE))
from probe_multi_image_edit import read_credentials  # noqa: E402


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def post(endpoint, key, prompt, images, label):
    files = []
    handles = []
    try:
        for path in images:
            handle = open(path, "rb")
            handles.append(handle)
            files.append(("image", (path.name, handle, "image/png")))
        started = time.monotonic()
        response = requests.post(
            endpoint.rstrip("/") + EDITS_PATH,
            headers={"api-key": key},
            data={"model": DEPLOYMENT, "prompt": prompt},
            files=files,
            timeout=TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - started
    finally:
        for handle in handles:
            handle.close()

    record = {
        "label": label,
        "prompt": prompt,
        "input_images": [path.name for path in images],
        "input_paths": [str(path.relative_to(ARCHIVE)) for path in images],
        "input_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in images],
        "image_count": len(images),
        "status_code": response.status_code,
        "request_seconds": round(elapsed, 3),
        "requested_at_utc": utc_now(),
    }
    try:
        payload = response.json()
    except ValueError:
        record["raw_text_head"] = response.text[:800]
        record["outcome"] = "NON_JSON"
        return record, None

    data = payload.get("data") or []
    b64 = data[0].get("b64_json") if data and isinstance(data[0], dict) else None
    if b64:
        image_bytes = base64.b64decode(b64)
        record["output_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        record["output_bytes"] = len(image_bytes)
        record["outcome"] = "RETURNED_IMAGE"
        return record, image_bytes
    record["error_payload"] = payload.get("error") or payload
    record["outcome"] = "REJECTED" if response.status_code >= 400 else "NO_IMAGE"
    return record, None


def run(endpoint, key, plan, results, save):
    for index, (group, label, prompt, images) in enumerate(plan, start=1):
        print(f"[{index}/{len(plan)}] {group} :: {label} ({len(images)} image)", flush=True)
        attempts = 0
        while True:
            attempts += 1
            try:
                record, image_bytes = post(endpoint, key, prompt, images, label)
            except requests.RequestException as error:
                record, image_bytes = {"label": label, "outcome": "TRANSPORT_ERROR",
                                       "error": f"{type(error).__name__}: {error}",
                                       "requested_at_utc": utc_now()}, None
            if record.get("status_code") == 429 and attempts < 4:
                print(f"    429 rate limit; waiting {INTER_CALL_WAIT}s then retrying", flush=True)
                time.sleep(INTER_CALL_WAIT)
                continue
            break

        record["group"] = group
        record["attempts_used"] = attempts
        if image_bytes:
            target = OUTPUT / f"{index:02d}_{label}.png"
            target.write_bytes(image_bytes)
            record["output_path"] = target.name
        results["attempts"].append(record)
        save()
        print(f"    -> status={record.get('status_code')} {record.get('outcome')} "
              f"sha={str(record.get('output_sha256'))[:12]} "
              f"{record.get('request_seconds')}s", flush=True)
        if index < len(plan):
            time.sleep(INTER_CALL_WAIT)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for path in (IMAGE_ONE, IMAGE_TWO):
        if not path.is_file():
            raise SystemExit(f"Input image missing: {path}")
    endpoint, key = read_credentials()

    results = {
        "purpose": ("Separate single-image and multi-image edit capability from the "
                    "attribution comparison"),
        "model_deployment": DEPLOYMENT,
        "endpoint_host": endpoint.split("//")[-1].split("/")[0],
        "started_at_utc": utc_now(),
        "environment": {"platform": platform.platform(),
                        "python": platform.python_version(),
                        "requests": requests.__version__},
        "groups": {
            "A_capability": ("Each input count gets a prompt it can satisfy, so each output "
                             "represents that usage. Prompts differ, so this group cannot "
                             "attribute a difference to the extra image."),
            "B_attribution": ("The prompt is fixed and only the images change, with both "
                              "single-image arms present. The fixed prompt is under-determined "
                              "for one input, so this group measures attribution only and is "
                              "not evidence of single-image edit quality."),
        },
        "prompts": {"single": SINGLE_PROMPT, "multi": MULTI_PROMPT, "fixed": FIXED_PROMPT},
        "attempts": [],
    }

    def save():
        (OUTPUT / "clean-results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    save()
    plan = [
        ("A_capability", "single_image_matched_prompt", SINGLE_PROMPT, [IMAGE_ONE]),
        ("A_capability", "two_images_matched_prompt", MULTI_PROMPT, [IMAGE_ONE, IMAGE_TWO]),
        ("B_attribution", "fixed_prompt_image_two_only", FIXED_PROMPT, [IMAGE_TWO]),
    ]
    run(endpoint, key, plan, results, save)

    results["ended_at_utc"] = utc_now()
    save()
    print("\nSaved:", OUTPUT / "clean-results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
