"""Edit one real photo with MAI-Image-2.6 and GPT-Image-2, then measure what changed.

The task is deliberately checkable: replace the headwear in a supplied photograph
with a graduation cap. Four things can be verified per output without any
aesthetic judgement — whether the headwear was replaced, whether the face is
preserved, whether the robe embroidery survives, and whether bystanders were
altered.

It also settles a mechanism question directly. If the edit endpoint repaints only
the requested region, the untouched pixels stay close to the source. If it
regenerates the whole frame, they do not. The pixel comparison is computed
offline afterwards from the saved PNGs, not asserted here.

GPT's quality tiers are a text-to-image parameter. Whether the edits endpoint
accepts `quality` is probed rather than assumed: an unsupported tier is recorded
as REJECTED with the service's own message instead of being silently dropped.
"""

import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

AZ = Path(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd")
AZ_PROFILE = Path(r"C:\Users\xinyuwei\.azure-a15b-mngenvmcap066105-me-mngenvmcap066105-xinyuwei-1")

WORKSPACE = Path(__file__).resolve().parent
SOURCE_IMAGE = WORKSPACE / "4.jpg"


def _round_from_argv():
    """`--round N` selects the repeat; round 1 keeps the original flat layout."""
    arguments = sys.argv[1:]
    if "--round" in arguments:
        return int(arguments[arguments.index("--round") + 1])
    return 1


ROUND = _round_from_argv()
OUTPUT = WORKSPACE / "runs" / "edit-hat-swap-20260908"
if ROUND > 1:
    OUTPUT = OUTPUT / f"r{ROUND}"
TIMEOUT_SECONDS = 300
INTER_CALL_WAIT = 35.0
MAI_DEPLOYMENT = "MAI-Image-2.6"
GPT_DEPLOYMENT = os.environ.get("GPT_DEPLOYMENT", "gpt-image-2")
GPT_API_VERSION = os.environ.get("GPT_API_VERSION", "2025-04-01-preview")

PROMPT = ("Replace only the headwear worn by the man in the foreground with a black "
          "academic graduation cap with a tassel. Keep his face, beard, expression and "
          "pose exactly as they are. Keep his embroidered robe, the courtyard and every "
          "other person unchanged.")

sys.path.insert(0, str(WORKSPACE))
from probe_multi_image_edit import read_credentials as read_mai_credentials  # noqa: E402


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_discovered_gpt(preferred_location="eastus2"):
    """Use the gpt-image-2 deployment found by find_gpt_a15b.py, key read via Azure.

    The 88-sample benchmark ran GPT in eastus2, so the same-region deployment is
    preferred to keep the edit test comparable. The key is fetched from ARM at call
    time rather than trusted from a file written earlier, and is never printed.
    """
    discovery = WORKSPACE / "gpt-deployment-discovery.json"
    if not discovery.is_file():
        return None, None, None
    usable = json.loads(discovery.read_text("utf-8")).get("usable") or []
    if not usable:
        return None, None, None
    chosen = next((u for u in usable if u.get("location") == preferred_location), usable[0])
    env = dict(os.environ)
    env["AZURE_CONFIG_DIR"] = str(AZ_PROFILE)
    done = subprocess.run([str(AZ), "cognitiveservices", "account", "keys", "list", "--name",
                           chosen["account"], "--resource-group", chosen["resource_group"],
                           "-o", "json"], capture_output=True, text=True, env=env, timeout=90)
    if done.returncode != 0:
        return None, None, None
    key = json.loads(done.stdout or "{}").get("key1")
    origin = chosen["endpoint"].rstrip("/")
    print(f"using discovered deployment {chosen['deployment']} on {chosen['account']} "
          f"({chosen['location']}, v{chosen['version']})", flush=True)
    return origin, key, chosen["deployment"]


def read_gpt_credentials():
    """Read the GPT origin, deployment and key from the workspace password file.

    The entry stores the deployment name, then a full request URL, then the bare
    key. The origin is taken from the URL rather than assuming an `openai.azure.com`
    host, because this resource is a `cognitiveservices.azure.com` AI Services
    account. Placeholder lines are skipped so a pasted quickstart cannot be read
    as a credential.
    """
    lines = (WORKSPACE / "password").read_text("utf-8", errors="ignore").splitlines()
    origin = key = deployment = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if "<" in stripped or ">" in stripped:
            continue
        if origin is None and ("cognitiveservices.azure.com" in stripped
                               or "openai.azure.com" in stripped):
            for token in stripped.replace(",", " ").replace('"', " ").split():
                if "azure.com" in token and token.startswith("http"):
                    origin = "https://" + token.split("//", 1)[1].split("/", 1)[0]
                    if "/deployments/" in token:
                        deployment = token.split("/deployments/")[1].split("/")[0]
                    break
            for previous in reversed(lines[max(0, index - 3):index]):
                text = previous.strip()
                if text and "://" not in text and " " not in text and "gpt" in text.lower():
                    deployment = deployment or text
                    break
            for candidate in lines[index + 1:index + 4]:
                text = candidate.strip().strip('"').strip("'")
                if len(text) >= 32 and " " not in text and "://" not in text:
                    key = text
                    break
            break
    return origin, key, deployment


def entra_bearer_token():
    """Fetch a Cognitive Services token from the isolated CLI profile; never printed."""
    env = dict(os.environ)
    env["AZURE_CONFIG_DIR"] = str(AZ_PROFILE)
    try:
        done = subprocess.run([str(AZ), "account", "get-access-token", "--resource",
                               "https://cognitiveservices.azure.com", "--query", "accessToken",
                               "-o", "tsv"], capture_output=True, text=True, env=env, timeout=90)
    except (subprocess.TimeoutExpired, OSError):
        return None
    token = (done.stdout or "").strip()
    return token if done.returncode == 0 and token else None


def post_edit(url, headers, data, image_path, label):
    with open(image_path, "rb") as handle:
        files = [("image", (image_path.name, handle, "image/jpeg"))]
        started = time.monotonic()
        response = requests.post(url, headers=headers, data=data, files=files,
                                 timeout=TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started

    record = {"label": label, "status_code": response.status_code,
              "request_seconds": round(elapsed, 3), "requested_at_utc": utc_now(),
              "sent_fields": sorted(data.keys()),
              "auth_mode": "bearer" if "Authorization" in headers else "api-key"}
    try:
        payload = response.json()
    except ValueError:
        record["raw_text_head"] = response.text[:600]
        record["outcome"] = "NON_JSON"
        return record, None

    data_list = payload.get("data") or []
    b64 = data_list[0].get("b64_json") if data_list and isinstance(data_list[0], dict) else None
    if b64:
        image_bytes = base64.b64decode(b64)
        record["output_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        record["output_bytes"] = len(image_bytes)
        record["outcome"] = "RETURNED_IMAGE"
        return record, image_bytes
    error = payload.get("error") or payload
    record["error_message"] = (error.get("message") if isinstance(error, dict)
                               else str(error))[:400]
    record["outcome"] = "REJECTED" if response.status_code >= 400 else "NO_IMAGE"
    return record, None


def main():
    gpt_only = "--gpt-only" in sys.argv[1:] or bool(os.environ.get("SKIP_MAI"))
    if not SOURCE_IMAGE.is_file():
        raise SystemExit(f"Source image missing: {SOURCE_IMAGE}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    mai_endpoint, mai_key = read_mai_credentials()
    # Prefer the deployment that ARM confirms exists; the password-file entry points
    # at an account with no gpt-image-2 deployment and local auth disabled.
    gpt_endpoint, gpt_key, gpt_deployment = read_discovered_gpt()
    if not (gpt_endpoint and gpt_key):
        gpt_endpoint, gpt_key, gpt_deployment = read_gpt_credentials()
    gpt_deployment = gpt_deployment or GPT_DEPLOYMENT

    # In --gpt-only mode keep the MAI record already on disk and replace only the
    # GPT attempts, so the earlier MAI output and its timing are not re-spent.
    existing_path = OUTPUT / "edit-results.json"
    kept_attempts = []
    if gpt_only and existing_path.is_file():
        previous = json.loads(existing_path.read_text("utf-8"))
        kept_attempts = [a for a in previous.get("attempts", [])
                         if not a.get("label", "").startswith("gpt-")]
        print(f"keeping {len(kept_attempts)} existing non-GPT attempt(s)", flush=True)

    results = {
        "purpose": "Replace headwear in one supplied photo and compare edit behaviour",
        "round": ROUND,
        "prompt": PROMPT,
        "source_image": SOURCE_IMAGE.name,
        "source_sha256": hashlib.sha256(SOURCE_IMAGE.read_bytes()).hexdigest(),
        "source_bytes": SOURCE_IMAGE.stat().st_size,
        "started_at_utc": utc_now(),
        "environment": {"platform": platform.platform(), "python": platform.python_version(),
                        "requests": requests.__version__},
        "gpt_endpoint_present": bool(gpt_endpoint and gpt_key),
        "boundary": ("Quality tiers are a text-to-image parameter; whether the edits "
                     "endpoint honours them is recorded from the service response rather "
                     "than assumed. A returned image proves the call succeeded, not that "
                     "the requested edit is correct; that is judged from the pixels."),
        "attempts": kept_attempts,
    }

    # MAI already returned an image in the first pass; only the GPT tiers are missing.
    plan = [] if gpt_only else [
        ("mai-image-2.6", mai_endpoint, "/mai/v1/images/edits",
         {"api-key": mai_key}, {"model": MAI_DEPLOYMENT, "prompt": PROMPT})]
    if gpt_endpoint and gpt_key:
        gpt_path = f"/openai/deployments/{gpt_deployment}/images/edits?api-version={GPT_API_VERSION}"
        print(f"GPT endpoint host: {gpt_endpoint.split('//')[-1]}  deployment: {gpt_deployment}",
              flush=True)
        for tier in ("low", "medium", "high"):
            plan.append((f"gpt-image-2-{tier}", gpt_endpoint, gpt_path, {"api-key": gpt_key},
                         {"model": gpt_deployment, "prompt": PROMPT, "n": "1",
                          "size": "1024x1024", "quality": tier}))
    else:
        print("GPT endpoint/key not found in the password file; MAI only.", flush=True)
    if ROUND % 2 == 0:
        # Same protocol as the eleven text-to-image scenarios: even rounds reverse
        # the configuration order so position in the sequence is not confounded.
        plan.reverse()
    print(f"round {ROUND}: order {[label for label, *_ in plan]} -> {OUTPUT}", flush=True)

    def save():
        (OUTPUT / "edit-results.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    save()
    offset = len(kept_attempts)
    bearer = None
    for index, (label, endpoint, path, headers, data) in enumerate(plan, start=1):
        print(f"[{index}/{len(plan)}] {label}", flush=True)
        attempts = 0
        active_headers = dict(headers)
        while True:
            attempts += 1
            try:
                record, image_bytes = post_edit(endpoint.rstrip("/") + path, active_headers,
                                                data, SOURCE_IMAGE, label)
            except requests.RequestException as error:
                record, image_bytes = {"label": label, "outcome": "TRANSPORT_ERROR",
                                       "error": f"{type(error).__name__}: {error}",
                                       "requested_at_utc": utc_now()}, None
            if record.get("status_code") == 429 and attempts < 4:
                print(f"    429 rate limit; waiting {INTER_CALL_WAIT}s", flush=True)
                time.sleep(INTER_CALL_WAIT)
                continue
            # A 401 with api-key on an account that disables local auth is an
            # authentication-mode mismatch, not a bad key; retry once with Entra.
            if (record.get("status_code") == 401 and "api-key" in active_headers
                    and label.startswith("gpt-") and attempts < 3):
                bearer = bearer or entra_bearer_token()
                if bearer:
                    print("    401 with api-key; retrying once with Entra bearer token", flush=True)
                    active_headers = {"Authorization": f"Bearer {bearer}"}
                    continue
            break
        record["attempts_used"] = attempts
        if image_bytes:
            target = OUTPUT / f"{offset + index:02d}_{label}.png"
            target.write_bytes(image_bytes)
            record["output_path"] = target.name
        results["attempts"].append(record)
        save()
        print(f"    -> {record.get('status_code')} {record.get('outcome')} "
              f"{record.get('request_seconds')}s "
              f"{record.get('error_message', '')[:120]}", flush=True)
        if index < len(plan):
            time.sleep(INTER_CALL_WAIT)

    results["ended_at_utc"] = utc_now()
    save()
    print("\nSaved:", OUTPUT / "edit-results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
