"""Find the documented and actual multi-image contract of the MAI image edits API.

Two independent questions are answered separately:

1. Does the service itself describe a multi-image contract? Probed by sending
   deliberately malformed requests and reading the service's own validation
   text, which is the API's authoritative statement about accepted fields.
2. How many images does it actually accept? Probed by increasing the number of
   `image` form fields until the service rejects the request.

A 200 response only proves the request was accepted. Whether an extra image
influenced the output requires comparing returned pixels, so this probe records
output hashes and never claims influence by itself.
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
OUTPUT = WORKSPACE / "runs" / "multi-image-limit-probe-20260908"
ARCHIVE = Path("C:/david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark"
               "/data/lenovo-web-grounding-20260908")
EDITS_PATH = "/mai/v1/images/edits"
TIMEOUT_SECONDS = 300
INTER_CALL_WAIT = 35.0
DEPLOYMENT = "MAI-Image-2.6"
PROMPT = ("Place every device shown in the reference images together on one plain "
          "studio background as a single clean product photograph.")

sys.path.insert(0, str(WORKSPACE))
from probe_multi_image_edit import read_credentials  # noqa: E402


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def source_images():
    """Distinct source images; reused deliberately when more slots are needed."""
    candidates = [
        ARCHIVE / "mai-image-2.6-web-off" / "r1" / "01_test.png",
        ARCHIVE / "mai-image-2.6-web-off" / "r1" / "02_test.png",
        ARCHIVE / "mai-image-2.6-web-off" / "r1" / "03_test.png",
        ARCHIVE / "mai-image-2.6-web-off" / "r2" / "01_test.png",
        ARCHIVE / "mai-image-2.6-web-off" / "r2" / "02_test.png",
        ARCHIVE / "mai-image-2.6-web-off" / "r2" / "03_test.png",
        ARCHIVE / "mai-image-2.6-web-on" / "r1" / "01_test.png",
        ARCHIVE / "mai-image-2.6-web-on" / "r1" / "02_test.png",
        ARCHIVE / "mai-image-2.6-web-on" / "r1" / "03_test.png",
    ]
    available = [path for path in candidates if path.is_file()]
    if len(available) < 2:
        raise SystemExit("Need at least two source images for this probe")
    return available


def post(endpoint, key, files_spec, label):
    files = []
    handles = []
    try:
        for field, path in files_spec:
            handle = open(path, "rb")
            handles.append(handle)
            files.append((field, (path.name, handle, "image/png")))
        started = time.monotonic()
        response = requests.post(
            endpoint.rstrip("/") + EDITS_PATH,
            headers={"api-key": key},
            data={"model": DEPLOYMENT, "prompt": PROMPT},
            files=files,
            timeout=TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - started
    finally:
        for handle in handles:
            handle.close()

    record = {
        "label": label,
        "fields_sent": [field for field, _ in files_spec],
        "image_count": len(files_spec),
        "status_code": response.status_code,
        "request_seconds": round(elapsed, 3),
        "requested_at_utc": utc_now(),
    }
    try:
        payload = response.json()
    except ValueError:
        record["raw_text_head"] = response.text[:1000]
        return record, None

    data = payload.get("data") or []
    b64 = data[0].get("b64_json") if data and isinstance(data[0], dict) else None
    if b64:
        image_bytes = base64.b64decode(b64)
        record["output_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        record["output_bytes"] = len(image_bytes)
        record["outcome"] = "ACCEPTED_RETURNED_IMAGE"
        return record, image_bytes
    record["error_payload"] = payload.get("error") or payload
    record["outcome"] = "REJECTED" if response.status_code >= 400 else "NO_IMAGE"
    return record, None


def service_contract_probes(endpoint, key, images):
    """Read the service's own validation messages about accepted image fields."""
    probes = [
        ("no_image_at_all", []),
        ("wrong_field_name_only", [("reference", images[0])]),
        ("numbered_fields", [("image1", images[0]), ("image2", images[1])]),
        ("prefixed_fields", [("image_a", images[0]), ("image_b", images[1])]),
    ]
    results = []
    for index, (label, spec) in enumerate(probes, start=1):
        print(f"[contract {index}/{len(probes)}] {label}", flush=True)
        try:
            record, image_bytes = post(endpoint, key, spec, label)
        except requests.RequestException as error:
            record, image_bytes = {"label": label, "outcome": "TRANSPORT_ERROR",
                                   "error": f"{type(error).__name__}: {error}"}, None
        if image_bytes:
            target = OUTPUT / f"contract_{index:02d}_{label}.png"
            target.write_bytes(image_bytes)
            record["output_path"] = target.name
        results.append(record)
        print(f"    -> status={record.get('status_code')} {record.get('outcome')} "
              f"{str(record.get('error_payload'))[:160]}", flush=True)
        time.sleep(INTER_CALL_WAIT if image_bytes else 6.0)
    return results


def count_limit_probes(endpoint, key, images, counts):
    """Increase the number of `image` fields until the service refuses."""
    results = []
    for index, count in enumerate(counts, start=1):
        spec = [("image", images[i % len(images)]) for i in range(count)]
        print(f"[count {index}/{len(counts)}] {count} image fields", flush=True)
        try:
            record, image_bytes = post(endpoint, key, spec, f"{count}_images")
        except requests.RequestException as error:
            record, image_bytes = {"label": f"{count}_images", "image_count": count,
                                   "outcome": "TRANSPORT_ERROR",
                                   "error": f"{type(error).__name__}: {error}"}, None
        if image_bytes:
            target = OUTPUT / f"count_{count:02d}_images.png"
            target.write_bytes(image_bytes)
            record["output_path"] = target.name
        results.append(record)
        print(f"    -> status={record.get('status_code')} {record.get('outcome')} "
              f"sha={str(record.get('output_sha256'))[:12]} "
              f"{record.get('request_seconds')}s", flush=True)
        if index < len(counts):
            time.sleep(INTER_CALL_WAIT if image_bytes else 6.0)
    return results


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    endpoint, key = read_credentials()
    images = source_images()

    results = {
        "purpose": "Establish the service-stated and actual multi-image contract",
        "model_deployment": DEPLOYMENT,
        "endpoint_host": endpoint.split("//")[-1].split("/")[0],
        "prompt": PROMPT,
        "distinct_source_images": [str(path.relative_to(ARCHIVE)) for path in images],
        "started_at_utc": utc_now(),
        "environment": {"platform": platform.platform(),
                        "python": platform.python_version(),
                        "requests": requests.__version__},
        "boundary": ("Validation text is the service's own statement about accepted fields. "
                     "A 200 proves acceptance only; pixel comparison is required to show a "
                     "given image influenced the output."),
    }

    def save():
        (OUTPUT / "limit-probe-results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    results["service_contract"] = []
    save()
    results["service_contract"] = service_contract_probes(endpoint, key, images)
    save()

    results["count_limit"] = count_limit_probes(endpoint, key, images, [3, 5, 9])
    results["ended_at_utc"] = utc_now()
    save()
    print("\nSaved:", OUTPUT / "limit-probe-results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
