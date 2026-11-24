"""Shared helpers for up.py, verify.py and down.py.

Only the Python standard library and the Azure CLI are needed. Every call is authenticated with a Microsoft Entra
token from `az account get-access-token`; no key is read or stored (the Foundry account is created with key
authentication disabled). State and receipts are written to ~/.foundry-lora/<resource group>/, outside the repository.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ARM = "https://management.azure.com"
ARM_AUDIENCE = ARM + "/"
AI_AUDIENCE = "https://ai.azure.com"
API_ACCOUNT = "2025-06-01"
API_MANAGED_COMPUTE = "2026-11-01"
API_ADAPTER = "2026-09-15-preview"
SOLUTION_TAG = "foundry-managed-training-lora"

# What this repository deploys. The base model version of the target deployment is not fixed here:
# up.py reads it from the registered LoRA adapter, because an adapter only fits the exact version it was trained on.
TRAINING_MODEL = "qwen3.8-27b"
BASE_MODEL_FAMILY = "azureml://registries/azure-huggingface/models/qwen--qwen3.8-27b/versions/"
LORA_TEMPLATE = ("azureml://registries/azure-huggingface/deploymenttemplates/"
                 "qwen--qwen3-8-27b--lora-256k-nvidia-2xh100/labels/latest")
ACCELERATOR = "H100_80GB"
GPUS_PER_INSTANCE = 2
MAX_ADAPTERS_PER_TARGET = 8
DEFAULT_TARGET = "qwen38-lora"
PRICE_METERS = {"gpu": "Mngd H100_80GB Gl", "training": "Qwen38 27b SFT Gl 1M Tokens",
                "programmed": "Qwen38 27b Train Gl 1M Tokens"}

# Regions where Global Managed Training lists Qwen3.8-27B (Learn, "Training in Microsoft Foundry", read 2026-11-23).
TRAINING_REGIONS = ("australiaeast", "eastus", "eastus2", "koreacentral", "northcentralus", "swedencentral",
                    "switzerlandnorth", "uaenorth", "uksouth", "westus3")

# The sample data, pinned to one commit of the public repository so that every run trains on the same bytes.
DATASET = {
    "repo": "microsoft-foundry/fine-tuning",
    "commit": "9ddb5e71f2eee8127b99fa8fba433d0f6593de5a",
    "folder": "Sample_Datasets/Supervised_Fine_Tuning/Text-GSM8K",
    "files": {
        "train": {"source": "chat_train.jsonl", "upload_as": "gsm8k-train.jsonl", "rows": 449,
                  "sha256": "9b6e0d6ffe6cf804e94335f2434706548235c912b5e38e2c67648d2e7c0c3612"},
        "validation": {"source": "chat_validation.jsonl", "upload_as": "gsm8k-validation.jsonl", "rows": 50,
                       "sha256": "698d6db7a70ab03ededea14236bb55c38295cf61ab477767d2bc7720c7a16b1d"},
    },
}

_tokens: dict[str, tuple[str, float]] = {}
_az: str | None = None
_subscription: str | None = None
_log_file: Path | None = None


class Stop(Exception):
    """A condition the reader has to act on; the message says what to do."""


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    line = f"{now()} {message}"
    print(line, flush=True)
    if _log_file is not None:
        with _log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# ---------------------------------------------------------------- Azure CLI and tokens

def az(args: list[str], check: bool = True) -> str:
    """Run the Azure CLI and return its stdout. The subscription chosen with use_subscription() is added."""
    global _az
    if _az is None:
        _az = shutil.which("az") or shutil.which("az.cmd")
        if _az is None:
            raise Stop("Azure CLI not found. Install it (https://learn.microsoft.com/cli/azure/install-azure-cli) and run `az login`.")
    cmd = [_az, *args]
    scoped = args[0] in ("group", "deployment", "provider", "resource") or args[:2] == ['account', 'get-access-token']
    if _subscription and scoped and "--subscription" not in args:
        cmd += ["--subscription", _subscription]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise Stop(f"`az {' '.join(args[:4])} ...` failed (exit {r.returncode}): {r.stderr.strip()[-600:]}")
    return r.stdout


def use_subscription(name_or_id: str | None) -> dict:
    """Check the sign-in and return the account record of the subscription the scripts will use."""
    global _subscription
    args = ['account', 'show', '-o', 'json'] + (["--subscription", name_or_id] if name_or_id else [])
    try:
        account = json.loads(az(args))
    except (Stop, ValueError) as e:
        raise Stop(f"Not signed in to Azure, or the subscription is not visible. Run `az login` first. ({e})") from None
    _subscription = account["id"]
    return account


def token(audience: str = ARM_AUDIENCE) -> str:
    cached = _tokens.get(audience)
    if cached and cached[1] - time.time() > 300:
        return cached[0]
    d = json.loads(az(['account', 'get-access-token', '--resource', audience, '-o', 'json']))
    _tokens[audience] = (d["accessToken"], float(d.get("expires_on") or time.time() + 1800))
    return d["accessToken"]


def http(method: str, url: str, body=None, audience: str = ARM_AUDIENCE, headers: dict | None = None,
         timeout: int = 120, data: bytes | None = None) -> tuple[int, dict, object]:
    """One HTTPS call. Returns (status, headers, parsed JSON or text). A relative url is an ARM path.
    A network error is returned as status 0 so that polling loops can continue."""
    if not url.startswith("http"):
        url = ARM + url
    payload = data if data is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    for attempt in (1, 2):
        h = {"Authorization": "Bearer " + token(audience)}
        if data is None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(url, data=payload, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), _parse(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 1:  # the cached token expired: fetch a new one and repeat the call once
                _tokens.pop(audience, None)
                continue
            return e.code, dict(e.headers), _parse(e.read())
        except OSError as e:  # URLError, timeout, connection reset
            return 0, {}, f"{type(e).__name__}: {e}"
    return 0, {}, "unreachable"


def list_all(url: str, audience: str = ARM_AUDIENCE) -> tuple[int, list]:
    """(status, items) of an Azure Resource Manager list, read to its last page. A first page can be empty while the
    items come on the page its nextLink names."""
    items, code = [], 0
    for _ in range(50):
        code, _, body = http("GET", url, audience=audience)
        if code != 200 or not isinstance(body, dict):
            return code, items
        items += body.get("value", [])
        url = body.get("nextLink")
        if not url:
            break
    return code, items


def _parse(raw: bytes):
    text = raw.decode("utf-8", "replace")
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def state_of(body) -> str | None:
    return (body.get("properties") or {}).get("provisioningState") if isinstance(body, dict) else None


def brief(body, limit: int = 300) -> str:
    return (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))[:limit]


# ---------------------------------------------------------------- state, receipts

def state_dir(resource_group: str) -> Path:
    global _log_file
    d = Path.home() / ".foundry-lora" / resource_group
    d.mkdir(parents=True, exist_ok=True)
    _log_file = d / "run.log"
    return d


def load_state(resource_group: str) -> dict:
    p = state_dir(resource_group) / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(resource_group: str, state: dict) -> None:
    (state_dir(resource_group) / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


class Receipt:
    """Step-by-step record of one script run: {"status": PASS|FAIL, "steps"|"checks": [{name, status, seconds, detail}]}."""

    def __init__(self, path: Path, kind: str = "steps", **facts):
        self.path, self.kind, self.items = path, kind, []
        self.doc = {"status": "RUNNING", "started": now(), **facts, kind: self.items}
        self._write()

    def add(self, name: str, status: str, detail: str = "", seconds: float | None = None, **extra) -> bool:
        item = {"name": name, "status": status, "detail": detail, **extra}
        if seconds is not None:
            item["seconds"] = round(seconds, 1)
        self.items.append(item)
        log(f"[{status}] {name}" + (f": {detail}" if detail else ""))
        self._write()
        return status == "PASS"

    def close(self, **facts) -> str:
        bad = [i["name"] for i in self.items if i["status"] not in ("PASS", "INFO")]
        self.doc.update(facts)
        self.doc["status"] = "PASS" if self.items and not bad else "FAIL"
        self.doc["finished"] = now()
        self._write()
        return self.doc["status"]

    def _write(self) -> None:
        self.path.write_text(json.dumps(self.doc, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- resources

class Solution:
    """Names and endpoints of one deployment of this repository, read back from Azure."""

    def __init__(self, subscription: str, resource_group: str, account: str, project: str, location: str,
                 project_endpoint: str, target: str = DEFAULT_TARGET):
        self.subscription, self.resource_group = subscription, resource_group
        self.account, self.project, self.location, self.target = account, project, location, target
        self.project_endpoint = project_endpoint.rstrip("/")
        self.endpoint = self.project_endpoint.split("/api/projects/")[0]
        self.account_id = (f"/subscriptions/{subscription}/resourceGroups/{resource_group}"
                           f"/providers/Microsoft.CognitiveServices/accounts/{account}")

    @property
    def openai(self) -> str:
        return self.project_endpoint + "/openai/v1"

    @property
    def chat_url(self) -> str:
        return self.endpoint + "/openai/v1/chat/completions"

    def target_url(self, name: str | None = None, collection: bool = False) -> str:
        tail = "" if collection else "/" + (name or self.target)
        return f"{self.account_id}/managedComputeDeployments{tail}?api-version={API_MANAGED_COMPUTE}"

    def adapter_url(self, name: str | None = None) -> str:
        return f"{self.account_id}/adapterDeployments{'/' + name if name else ''}?api-version={API_ADAPTER}"


def find_solution(subscription: str, resource_group: str, target: str = DEFAULT_TARGET) -> Solution | None:
    """The Foundry account and project that up.py created in this resource group (found by tag), or None."""
    base = f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts"
    code, accounts = list_all(f"{base}?api-version={API_ACCOUNT}")
    if code != 200:
        return None
    for acct in accounts:
        if (acct.get("tags") or {}).get("solution") != SOLUTION_TAG:
            continue
        code, projects = list_all(f"{acct['id']}/projects?api-version={API_ACCOUNT}")
        for proj in projects if code == 200 else []:
            endpoint = ((proj.get("properties") or {}).get("endpoints") or {}).get("AI Foundry API")
            if endpoint:
                return Solution(subscription, resource_group, acct["name"], proj["name"].split("/")[-1],
                                acct.get("location", ""), endpoint, target)
    return None


def require_solution(subscription: str, resource_group: str, target: str) -> Solution:
    s = find_solution(subscription, resource_group, target)
    if s is None:
        raise Stop(f"No Foundry account created by this repository in resource group '{resource_group}'. "
                   f"Run `python infra/up.py --resource-group {resource_group}` first.")
    return s


def quota(subscription: str, location: str, accelerator: str = ACCELERATOR) -> tuple[int, int] | None:
    """(used, limit) GPUs of the Global managed compute quota, or None when it cannot be read."""
    code, rows = list_all(f"/subscriptions/{subscription}/providers/Microsoft.CognitiveServices/locations/{location}"
                          f"/managedComputeUsages?api-version={API_MANAGED_COMPUTE}")
    if code != 200:
        return None
    for row in rows:
        if (row.get("name") or {}).get("value") == f"ManagedCompute.Global.{accelerator}":
            return int(row.get("currentValue") or 0), int(row.get("limit") or 0)
    return None


def list_price(meter: str) -> float | None:
    """Public list price in USD from the Azure Retail Prices API (no sign-in). None when it cannot be read."""
    flt = urllib.parse.quote(f"meterName eq '{meter}' and currencyCode eq 'USD'")
    try:
        with urllib.request.urlopen(f"https://prices.azure.com/api/retail/prices?$filter={flt}", timeout=30) as r:
            items = json.loads(r.read()).get("Items", [])
    except (OSError, ValueError):
        return None
    prices = {i.get("retailPrice") for i in items if i.get("type") == "Consumption"}
    return prices.pop() if len(prices) == 1 else None


# ---------------------------------------------------------------- Managed Training: files, jobs, registered adapters

def dataset_bytes(part: str, cache: Path) -> bytes:
    """The pinned sample file, downloaded once and checked against its SHA-256."""
    meta = DATASET["files"][part]
    path = cache / meta["upload_as"]
    if not path.is_file():
        url = (f"https://raw.githubusercontent.com/{DATASET['repo']}/{DATASET['commit']}/"
               f"{DATASET['folder']}/{meta['source']}")
        with urllib.request.urlopen(url, timeout=120) as r:
            path.write_bytes(r.read().replace(b"\r\n", b"\n"))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != meta["sha256"]:
        path.unlink()
        raise Stop(f"{meta['source']} does not match its pinned SHA-256. Delete {cache} and run again.")
    return data


def upload_file(sol: Solution, name: str, data: bytes) -> str:
    """Upload one JSONL file for fine-tuning (reused when a processed file with the same name and size exists)."""
    code, _, listing = http("GET", sol.openai + "/files?purpose=fine-tune&limit=1000", audience=AI_AUDIENCE)
    for f in (listing or {}).get("data", []) if code == 200 else []:
        if f.get("filename") == name and f.get("bytes") == len(data) and f.get("status") == "processed":
            return f["id"]
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nfine-tune\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/jsonl\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    code, _, f = http("POST", sol.openai + "/files", audience=AI_AUDIENCE, data=body, timeout=300,
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    if code not in (200, 201) or not isinstance(f, dict):
        raise Stop(f"Upload of {name} failed: HTTP {code} {brief(f)}")
    for _ in range(120):
        code, _, info = http("GET", f"{sol.openai}/files/{f['id']}", audience=AI_AUDIENCE)
        if isinstance(info, dict) and info.get("status") in ("processed", "error"):
            break
        time.sleep(5)
    if not isinstance(info, dict) or info.get("status") != "processed":
        raise Stop(f"File {name} was not accepted: {brief(info)}")
    return f["id"]


def list_jobs(sol: Solution) -> list[dict]:
    code, _, body = http("GET", sol.openai + "/fine_tuning/jobs?limit=100", audience=AI_AUDIENCE)
    if code != 200 or not isinstance(body, dict):
        raise Stop(f"Cannot list fine-tuning jobs: HTTP {code} {brief(body)}")
    return body.get("data", [])


def project_models(sol: Solution) -> list[dict]:
    code, _, body = http("GET", sol.project_endpoint + "/models?api-version=v1", audience=AI_AUDIENCE,
                         headers={"Foundry-Features": "Models=V1Preview"})
    if code != 200 or not isinstance(body, dict):
        raise Stop(f"Cannot list the project's models: HTTP {code} {brief(body)}")
    return body.get("value", [])


def source_model_id(job: dict) -> str | None:
    """The registered LoRA adapter a finished job points to; None while the job has not registered one."""
    for option in (job.get("metadata") or {}).get("deployment_options") or []:
        if option.get("format") == "ManagedCompute":
            return option.get("source_model_id")
    return None


def adapter_name(target: str, job: dict) -> str:
    """Adapter deployment name: 1-64 letters, digits, '.', '_' or '-', starting with a letter or digit, unique in the account."""
    label = job.get("display_name") or job.get("suffix") or job["id"][-8:]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-._") or job["id"][-8:]
    return f"{target}-{label}"[:64].rstrip("-._")


def deployable_adapters(jobs: list[dict], models: list[dict], target: str) -> list[dict]:
    """Succeeded jobs whose LoRA adapter is registered in the project: newest job per name, at most eight.
    Each item: {name, job, sourceModelId, baseModel, trainingFile}."""
    registered = {m.get("id"): m for m in models if m.get("weightType") == "LoRA"}
    chosen: dict[str, dict] = {}
    for job in sorted(jobs, key=lambda j: j.get("created_at") or 0, reverse=True):
        src = source_model_id(job)
        model = registered.get(src)
        if job.get("status") != "succeeded" or not model:
            continue
        base = (model.get("derivedModelInformation") or {}).get("baseModel") or ""
        if not base.startswith(BASE_MODEL_FAMILY):
            continue
        name = adapter_name(target, job)
        chosen.setdefault(name, {"name": name, "job": job["id"], "sourceModelId": src, "baseModel": base,
                                 "trainingFile": job.get("training_file")})
    return list(chosen.values())[:MAX_ADAPTERS_PER_TARGET]


# ---------------------------------------------------------------- Programmed Training: saved checkpoints

def named_adapters(specs: list[str], models: list[dict], target: str) -> list[dict]:
    """Adapters named on the command line as NAME or NAME=LABEL: LoRA models of the project, such as the checkpoint a
    Programmed Training session saved. LABEL ends the adapter deployment's name; a named model keeps that name even when
    a training job also points to it, as a session's entry in the job list does."""
    registered = {m.get("name"): m for m in models if m.get("weightType") == "LoRA"}
    found = []
    for spec in specs:
        name, _, label = spec.partition("=")
        model = registered.get(name)
        if model is None:
            raise Stop(f"--adapter-model {name}: the project has no LoRA model with this name. "
                       f"Its LoRA models: {', '.join(sorted(registered)) or 'none'}")
        base = (model.get("derivedModelInformation") or {}).get("baseModel") or ""
        if not base.startswith(BASE_MODEL_FAMILY):
            raise Stop(f"--adapter-model {name} was trained on {base or 'an unknown base model'}, not on {TRAINING_MODEL}")
        found.append({"name": adapter_name(target, {"display_name": label or name.removeprefix("model_"), "id": name}),
                      "job": None, "sourceModelId": model["id"], "baseModel": base, "trainingFile": None})
    return found


def adapters_to_deploy(jobs: list[dict], models: list[dict], target: str, specs: list[str] | tuple = ()) -> list[dict]:
    """The adapters named with --adapter-model first, then the adapters that training jobs registered; at most eight.
    A model that is named on the command line keeps that name only."""
    named = named_adapters(list(specs), models, target)
    named_ids = {a["sourceModelId"] for a in named}
    adapters = named + [a for a in deployable_adapters(jobs, models, target) if a["sourceModelId"] not in named_ids]
    names = [a["name"] for a in adapters]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise Stop(f"Two adapters would get the deployment name {twice[0]}. "
                   "Give one of them another LABEL: --adapter-model NAME=LABEL")
    return adapters[:MAX_ADAPTERS_PER_TARGET]


def session_adapter(models: list[dict], session_id: str) -> dict | None:
    """The LoRA model that the final checkpoint of a Programmed Training session became: the project model that carries
    the session in its tags and whose name ends in "-final" (session_<id> was listed as model_<id>-final in our test).
    None until the project lists it."""
    return next((m for m in models if m.get("weightType") == "LoRA" and (m.get("tags") or {}).get("session") == session_id
                 and str(m.get("name") or "").endswith("-final")), None)


def session_summary(metric_rows: list[dict]) -> dict:
    """What one session did, from the rows of the metrics.jsonl that the cookbook's training loop writes: a row per
    optimizer step (train_mean_nll, num_tokens) and a test/nll value wherever a validation pass ran."""
    steps = [r for r in metric_rows if "train_mean_nll" in r]
    return {"steps": len(steps), "trainingTokens": sum(int(r.get("num_tokens") or 0) for r in steps),
            "trainingLoss": [r["train_mean_nll"] for r in steps],
            "validationLoss": [r["test/nll"] for r in metric_rows if "test/nll" in r]}


# ---------------------------------------------------------------- inference

def chat(sol: Solution, model: str, messages: list[dict], max_tokens: int = 60, timeout: int = 180, **extra):
    """One chat completion through the account's OpenAI-compatible route. `model` is a deployment name:
    the target deployment answers as the base model, an adapter deployment answers with its LoRA adapter."""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0,
            "reasoning_effort": "none", **extra}
    started = time.time()
    code, headers, reply = http("POST", sol.chat_url, body, audience=AI_AUDIENCE, timeout=timeout)
    return code, reply, round(time.time() - started, 2)


def answer_text(reply) -> str:
    try:
        return reply["choices"][0]["message"].get("content") or ""
    except (TypeError, KeyError, IndexError):
        return ""


def main_guard(run) -> None:
    """Run a script's main(); print a Stop as one line and exit 1."""
    try:
        sys.exit(run())
    except Stop as e:
        print(f"\nSTOPPED: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted. Nothing was deleted; run the same command again to continue.", file=sys.stderr)
        sys.exit(130)
