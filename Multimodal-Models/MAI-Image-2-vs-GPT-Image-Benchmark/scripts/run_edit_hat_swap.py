"""Run or verify the two-round headwear-swap image-edit comparison.

Live calls read deployment origins and keys only from environment variables.
`--dry-run` validates the input and request plan without credentials or writes.
`--check` validates a completed two-round output directory without model calls.
"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


GROUPS = (
    "mai-image-2.6",
    "gpt-image-2-low",
    "gpt-image-2-medium",
    "gpt-image-2-high",
)
DEFAULT_PROMPT = (
    "Replace only the headwear worn by the man in the foreground with a black "
    "academic graduation cap with a tassel. Keep his face, beard, expression and "
    "pose exactly as they are. Keep his embroidered robe, the courtyard and every "
    "other person unchanged."
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def png_dimensions(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        raise ValueError("response is not a PNG")
    return struct.unpack(">II", data[16:24])


def validate_input(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"input image not found: {path}")
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError("this reproducible scenario expects a JPEG input")
    return hashlib.sha256(data).hexdigest(), len(data)


def make_specs(round_number, prompt=DEFAULT_PROMPT, gpt_size="auto",
               mai_model="MAI-Image-2.6", gpt_deployment="gpt-image-2"):
    specs = [{
        "label": "mai-image-2.6",
        "provider": "mai",
        "data": {"model": mai_model, "prompt": prompt},
    }]
    for quality in ("low", "medium", "high"):
        specs.append({
            "label": f"gpt-image-2-{quality}",
            "provider": "gpt",
            "data": {"model": gpt_deployment, "prompt": prompt, "n": "1",
                     "size": gpt_size, "quality": quality},
        })
    if round_number == 2:
        specs.reverse()
    return specs


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def credentials_from_environment():
    names = ("MAI_ENDPOINT", "AZURE_API_KEY", "GPT_ENDPOINT",
             "AZURE_OPENAI_API_KEY", "GPT_DEPLOYMENT")
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value or "<" in value]
    if missing:
        raise ValueError("set these environment variables before a live run: " + ", ".join(missing))
    for name in ("MAI_ENDPOINT", "GPT_ENDPOINT"):
        if not values[name].startswith("https://"):
            raise ValueError(f"{name} must be an https resource origin")
    return values


def request_target(spec, credentials):
    if spec["provider"] == "mai":
        return (credentials["MAI_ENDPOINT"].rstrip("/") + "/mai/v1/images/edits",
                {"api-key": credentials["AZURE_API_KEY"]})
    version = os.environ.get("GPT_API_VERSION", "2025-04-01-preview")
    path = (f"/openai/deployments/{credentials['GPT_DEPLOYMENT']}/images/edits"
            f"?api-version={version}")
    return (credentials["GPT_ENDPOINT"].rstrip("/") + path,
            {"api-key": credentials["AZURE_OPENAI_API_KEY"]})


def post_edit(url, headers, fields, input_path, timeout, max_attempts, retry_wait):
    last_record = None
    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        with Path(input_path).open("rb") as image_file:
            response = requests.post(
                url,
                headers=headers,
                data=fields,
                files={"image": (Path(input_path).name, image_file, "image/jpeg")},
                timeout=timeout,
            )
        elapsed = time.monotonic() - started
        record = {
            "status_code": response.status_code,
            "request_seconds": round(elapsed, 3),
            "requested_at_utc": utc_now(),
            "sent_fields": sorted(fields),
            "auth_mode": "api-key",
            "attempts_used": attempt,
        }
        last_record = record
        if response.status_code == 429 and attempt < max_attempts:
            wait = float(response.headers.get("retry-after", retry_wait))
            time.sleep(max(wait, retry_wait))
            continue
        try:
            payload = response.json()
        except ValueError:
            record.update({"outcome": "NON_JSON", "raw_text_head": response.text[:400]})
            return record, None
        items = payload.get("data") or []
        encoded = items[0].get("b64_json") if items and isinstance(items[0], dict) else None
        if response.status_code == 200 and encoded:
            image = base64.b64decode(encoded, validate=True)
            width, height = png_dimensions(image)
            record.update({"outcome": "RETURNED_IMAGE", "output_sha256": hashlib.sha256(image).hexdigest(),
                           "output_bytes": len(image), "width": width, "height": height})
            return record, image
        error = payload.get("error") or payload
        message = error.get("message") if isinstance(error, dict) else str(error)
        record.update({"outcome": "REJECTED" if response.status_code >= 400 else "NO_IMAGE",
                       "error_message": str(message)[:400]})
        return record, None
    return last_record, None


def run_round(args):
    source_sha, source_bytes = validate_input(args.input)
    output_root = args.output.resolve()
    round_dir = output_root if args.round == 1 else output_root / "r2"
    if (round_dir / "edit-results.json").exists():
        raise ValueError(f"output already exists; choose a new --output: {round_dir}")
    if args.round == 1:
        output_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.input, output_root / "input.jpg")
    elif not (output_root / "input.jpg").is_file():
        raise ValueError("run round 1 first so the frozen input exists in the output directory")
    elif file_sha256(output_root / "input.jpg") != source_sha:
        raise ValueError("round 2 input differs from the frozen round 1 input")
    round_dir.mkdir(parents=True, exist_ok=True)

    credentials = credentials_from_environment()
    specs = make_specs(args.round, args.prompt, args.gpt_size,
                       os.environ.get("MAI_MODEL", "MAI-Image-2.6"), credentials["GPT_DEPLOYMENT"])
    results = {
        "purpose": "Replace headwear in one supplied photo and compare edit behaviour",
        "round": args.round,
        "gpt_size_parameter": args.gpt_size,
        "prompt": args.prompt,
        "source_image": "input.jpg",
        "source_sha256": source_sha,
        "source_bytes": source_bytes,
        "started_at_utc": utc_now(),
        "boundary": ("A returned image proves the call succeeded, not that the requested edit is correct; "
                     "visual preservation requires a separate review."),
        "attempts": [],
    }
    results_path = round_dir / "edit-results.json"
    write_json(results_path, results)
    for index, spec in enumerate(specs, start=1):
        url, headers = request_target(spec, credentials)
        record, image = post_edit(url, headers, spec["data"], args.input, args.timeout,
                                  args.max_attempts, args.retry_wait)
        record["label"] = spec["label"]
        if image is not None:
            filename = f"{index:02d}_{spec['label']}.png"
            (round_dir / filename).write_bytes(image)
            record["output_path"] = filename
        results["attempts"].append(record)
        write_json(results_path, results)
        print(f"[{index}/4] {spec['label']}: {record.get('status_code')} {record['outcome']} ",
              f"{record.get('request_seconds')}s", flush=True)
        if index < len(specs):
            time.sleep(args.inter_call_wait)
    results["ended_at_utc"] = utc_now()
    write_json(results_path, results)
    returned = sum(item.get("outcome") == "RETURNED_IMAGE" for item in results["attempts"])
    print(json.dumps({"status": "PASS" if returned == 4 else "FAIL",
                      "round": args.round, "outputs": returned, "directory": str(round_dir)}))
    return 0 if returned == 4 else 1


def check_output(output_root):
    output_root = Path(output_root).resolve()
    input_path = output_root / "input.jpg"
    source_sha, _ = validate_input(input_path)
    outputs = 0
    size_parameter = None
    for round_number, relative in ((1, ""), (2, "r2")):
        base = output_root / relative
        results = json.loads((base / "edit-results.json").read_text("utf-8"))
        expected = [spec["label"] for spec in make_specs(round_number)]
        actual = [attempt["label"] for attempt in results.get("attempts", [])]
        if actual != expected:
            raise ValueError(f"round {round_number} order/configurations differ: {actual}")
        if results.get("round") != round_number or results.get("source_sha256") != source_sha:
            raise ValueError(f"round {round_number} metadata does not match its input")
        this_size = results.get("gpt_size_parameter")
        if size_parameter is None:
            size_parameter = this_size
        elif this_size != size_parameter:
            raise ValueError("GPT size parameter differs between rounds")
        for attempt in results["attempts"]:
            if attempt.get("status_code") != 200 or attempt.get("outcome") != "RETURNED_IMAGE":
                raise ValueError(f"{attempt['label']} did not return an image")
            image_path = base / attempt["output_path"]
            data = image_path.read_bytes()
            png_dimensions(data)
            if hashlib.sha256(data).hexdigest() != attempt["output_sha256"]:
                raise ValueError(f"{attempt['label']} output hash mismatch")
            outputs += 1
    return {"status": "PASS", "rounds": 2, "outputs": outputs,
            "gpt_size_parameter": size_parameter}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="JPEG input image; required for live or dry runs")
    parser.add_argument("--output", type=Path, default=Path("runs/edit-hat-swap-reproduction"))
    parser.add_argument("--round", type=int, choices=(1, 2), default=1)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--gpt-size", default="auto")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-wait", type=float, default=35)
    parser.add_argument("--inter-call-wait", type=float, default=35)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.check:
        print(json.dumps(check_output(args.output)))
        return 0
    if args.input is None:
        raise SystemExit("--input is required unless --check is used")
    source_sha, source_bytes = validate_input(args.input)
    specs = make_specs(args.round, args.prompt, args.gpt_size)
    if args.dry_run:
        print(json.dumps({"status": "PASS", "mode": "DRY_RUN", "round": args.round,
                          "input_sha256": source_sha, "input_bytes": source_bytes,
                          "gpt_size_parameter": args.gpt_size,
                          "order": [spec["label"] for spec in specs],
                          "output": str(args.output)}, indent=2))
        return 0
    return run_round(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, requests.RequestException) as error:
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)