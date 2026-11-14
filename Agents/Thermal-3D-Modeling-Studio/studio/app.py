"""Thermal 3D Modeling Studio — GPT-6 Astra on Microsoft Foundry.

FastAPI backend: session login, scenario catalogue, streaming generation (SSE),
pre-generated example cache. GPT-6 is called through the Azure OpenAI v1 endpoint with
an Entra ID token (VM user-assigned managed identity in production, Azure CLI locally).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib.util
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

import aiohttp
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential, ChainedTokenCredential, CredentialUnavailableError, ManagedIdentityCredential
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError, AsyncOpenAI, BadRequestError
from pydantic import BaseModel, Field, field_validator, model_validator

import cad_runner
from scenarios import DEFAULT_INDUSTRY, normalize_lang, public_industries, public_scenarios, system_prompt_for
from proposal import ProposalPayload, build_proposal_docx, proposal_filename

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("azure", "azure.core.pipeline.policies.http_logging_policy", "azure.identity", "httpx", "httpx2", "openai"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("thermal3d")

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
CACHE_DIR = BASE / "cache"
CACHE_DIR.mkdir(exist_ok=True)
CAD_DIR = BASE / "cad_out"  # 轨 B artefacts: cad_out/<job_id>/model.{py,step,stl,glb} + parts.json
CAD_DIR.mkdir(exist_ok=True)
# Pre-generated 轨 B results per scenario (cad_cache/<scenario_id>/{model.step,model.stl,model.glb,model.py,parts.json,meta.json}),
# built offline by pregen_cad.py from the hand-verified reference scripts in cad_examples/ and shipped with the app like cache/.
# Selecting a scenario card shows this solid immediately; “生成 STEP” still runs GPT-6 live.
CAD_CACHE_DIR = BASE / "cad_cache"
CAD_CACHE_EN_DIR = BASE / "cad_cache_en"   # English-UI builds of the same reference scripts (pregen_cad.py --lang en)
CAD_CACHE_PREFIX = "cache-"           # job ids of cached results: cache-<scenario_id>, so /api/cad/file serves both kinds
# Pre-generated 轨 C renders per scenario (render_cache/<scenario_id>/{render.png,snapshot.png,meta.json}), made by
# pregen_render.py through the live page (WebGL snapshot → /api/render) and shipped like cad_cache/.
RENDER_CACHE_DIR = BASE / "render_cache"
# Reference CadQuery script shown to GPT-6 as the worked example of the 轨 B contract (parts, materials, real fillets,
# counterbores, O-ring groove, slots, two-diameter ports). Verified on OCCT 2026-11-07: 4 parts, 200 faces, 12 s.
CAD_EXAMPLE_PATH = BASE / "cad_examples" / "coldplate.py"
CAD_EXAMPLE = CAD_EXAMPLE_PATH.read_text(encoding="utf-8") if CAD_EXAMPLE_PATH.exists() else ""

AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT", "").rstrip("/")  # no default: a fresh environment must point at its own resource
AOAI_DEPLOYMENT = os.getenv("AOAI_DEPLOYMENT", "gpt-6-astra")
AOAI_REASONING_EFFORT = os.getenv("AOAI_REASONING_EFFORT", "medium").strip()
# Values a request may name, cheapest first; AOAI_REASONING_EFFORT is the default when a request does not choose ("off"/"default"
# = send nothing). GPT-6 Astra does not support 'none' (OpenAI reasoning guide; on 2026-11-14 its Chat Completions endpoint answered
# "Supported values are: 'low', 'medium', 'high', and 'xhigh'."), so the UI offers those four and a request for 'none' is sent as
# 'low'. A deployment that refuses more narrows supported_efforts with its first such 400, and the UI follows.
REASONING_EFFORTS = ("none", "low", "medium", "high", "xhigh")
supported_efforts: tuple[str, ...] = ("low", "medium", "high", "xhigh")
AOAI_MAX_TOKENS = int(os.getenv("AOAI_MAX_TOKENS", "24000"))
# Photoreal render step (轨 C): an image-edit model turns the WebGL snapshot into a studio product shot. Empty → step hidden.
# Probed 2026-09-11 on gpt-image-2.5-sunburst: images.edit accepts size/quality/n/output_format, rejects input_fidelity.
AOAI_IMAGE_DEPLOYMENT = os.getenv("AOAI_IMAGE_DEPLOYMENT", "").strip()
# Per the Foundry image how-to (GPT-Image-2.5): custom WIDTHxHEIGHT, edges multiples of 16, ratio ≤ 3:1, ≤ 3840 px; quality low…max/auto.
RENDER_SIZES = ("1024x1024", "1536x1024", "1024x1536", "1792x1024", "2048x1152")  # last two ≈ 16:9 for slides
RENDER_QUALITIES = ("low", "medium", "high", "xhigh", "max")  # max: 2026-11-09, 2048x1152 in 57–70 s, 6,507 tokens
MAX_RENDER_INPUT_CHARS = 11_500_000  # ≈ 8 MB PNG as base64
# Concept Studio (轨 D): natural language → concept image (before any 3D). Two providers:
#   gpt-image  → the AOAI_IMAGE_DEPLOYMENT above (text→image and image→image edits)
#   mai        → MAI-Image-2.6 on a Foundry resource (`POST {MAI_ENDPOINT}/mai/v1/images/generations|edits`; `api-key` header
#                when MAI_API_KEY is set, otherwise the host Entra token — the resource may have local auth disabled) with
#                `web_grounding=true` = "search Bing first, then draw" (Web IQ). Empty MAI_ENDPOINT → provider hidden.
MAI_ENDPOINT = os.getenv("MAI_ENDPOINT", "").rstrip("/")
MAI_API_KEY = os.getenv("MAI_API_KEY", "").strip() or None
MAI_MODEL = os.getenv("MAI_MODEL", "MAI-Image-2.6").strip()
# Public HTTPS front (nginx + Let's Encrypt). When set, plain-HTTP requests that did not come through the TLS proxy are
# redirected there (308), so the old http://host:3005 links keep working but nothing sensitive travels in clear text.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
# SDK-level transparent retries on 408/429/5xx: explicit so a request_id maps to a known number of billed attempts.
AOAI_MAX_RETRIES = int(os.getenv("AOAI_MAX_RETRIES", "1"))
HISTORY_TURNS = int(os.getenv("HISTORY_TURNS", "3"))  # assistant turns kept for iteration
# Predicted outputs: when iterating on a previous model, send its raw output as the prediction so
# unchanged code is accepted instead of decoded token-by-token. Off by default — gpt-6-astra
# (2026-09-03) rejects the parameter ("unsupported_parameter"); enable once the deployment supports it.
AOAI_PREDICTED_OUTPUTS = os.getenv("AOAI_PREDICTED_OUTPUTS", "0").strip().lower() not in ("0", "false", "off", "")
# 轨 B (CadQuery → STEP): wall-clock budget for one OCCT run, retries with the traceback fed back to GPT-6,
# and how many finished jobs to keep on disk (oldest are pruned).
CAD_TIMEOUT_S = int(os.getenv("CAD_TIMEOUT_S", "150"))
CAD_MAX_ATTEMPTS = int(os.getenv("CAD_MAX_ATTEMPTS", "3"))
CAD_KEEP_JOBS = int(os.getenv("CAD_KEEP_JOBS", "40"))
CAD_AVAILABLE = importlib.util.find_spec("cadquery") is not None

PORTAL_USERNAME = os.getenv("PORTAL_USERNAME", "studio")
PORTAL_PASSWORD = os.getenv("PORTAL_PASSWORD")  # no default in source: unset → login disabled with a clear error
# Optional second account for the demo owner: signs in like everyone else, but is exempt from REQUIRE_BYOK and always
# runs on the host connection configured in .env — so the owner never types a key into a browser.
PORTAL_OWNER_USERNAME = os.getenv("PORTAL_OWNER_USERNAME", "").strip()
PORTAL_OWNER_PASSWORD = os.getenv("PORTAL_OWNER_PASSWORD")
# Host connection credential: Entra ID token (managed identity / az login) by default; AOAI_API_KEY for key-auth resources.
AOAI_API_KEY = os.getenv("AOAI_API_KEY", "").strip() or None
SESSION_SECRET = os.getenv("PORTAL_SESSION_SECRET") or secrets.token_hex(32)
SESSION_TTL = 12 * 3600
OWNER_SESSION_TTL = int(os.getenv("OWNER_SESSION_TTL_DAYS", "30")) * 86400
COOKIE = "s3d_session"
ROLE_OWNER, ROLE_VISITOR = "owner", "visitor"
# SSE heartbeat while the model / OCCT is silent: Azure public IPs drop idle TCP flows after 4 min by default.
HEARTBEAT_S = float(os.getenv("SSE_HEARTBEAT_S", "15"))
# Back-pressure: beyond these, a request gets an immediate, explained SSE error instead of piling onto the VM.
MAX_CONCURRENT_GENERATIONS = int(os.getenv("MAX_CONCURRENT_GENERATIONS", "4"))
MAX_CONCURRENT_CAD = int(os.getenv("MAX_CONCURRENT_CAD", "2"))
# Backend limits on request payloads (the browser enforces the same, but the server is the authority).
MAX_PROMPT_CHARS = 8000
MAX_IMAGE_DATA_URL_CHARS = 11_500_000  # ≈ 8 MB binary as base64
MAX_CAD_HTML_CHARS = 400_000

SENTINELS = ["SUMMARY", "HTML", "METRICS", "SUGGESTIONS"]


class AzCommandCredential:
    """Fallback for local development: shell out to `az account get-access-token`.

    azure-identity's AzureCliCredential cannot always locate az.cmd on Windows; this
    runs the CLI through the shell so PATHEXT resolution applies.
    """

    def get_token(self, *scopes: str, **_: Any) -> AccessToken:
        import shutil
        import subprocess

        if not shutil.which("az"):
            raise CredentialUnavailableError("az CLI not found on PATH")
        resource = scopes[0].removesuffix("/.default") if scopes else "https://cognitiveservices.azure.com"
        cmd = f'az account get-access-token --resource "{resource}" -o json'
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise CredentialUnavailableError(f"az account get-access-token failed: {proc.stderr.strip()[:300]}")
        data = json.loads(proc.stdout)
        expires_on = int(data.get("expires_on") or 0)
        if not expires_on:
            expires_on = int(time.time()) + 3000
        return AccessToken(data["accessToken"], expires_on)


class TokenProvider:
    """Entra ID bearer token for Azure OpenAI, cached until shortly before expiry."""

    SCOPE = "https://cognitiveservices.azure.com/.default"

    def __init__(self) -> None:
        creds: list[Any] = []
        client_id = os.getenv("AZURE_CLIENT_ID")
        if client_id:
            creds.append(ManagedIdentityCredential(client_id=client_id))
        creds.append(AzureCliCredential())
        creds.append(AzCommandCredential())
        self._cred = ChainedTokenCredential(*creds)
        self._token: str | None = None
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def get(self) -> str:
        async with self._lock:
            if self._token and time.time() < self._expires - 300:
                return self._token
            tok = await asyncio.to_thread(self._cred.get_token, self.SCOPE)
            self._token, self._expires = tok.token, float(tok.expires_on)
            return self._token


tokens = TokenProvider()
app = FastAPI(title="Thermal 3D Modeling Studio", docs_url=None, redoc_url=None)
stats = {"generated": 0, "generated_visitor_key": 0, "last_latency_s": None, "started": time.time()}
gen_slots = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
cad_slots = asyncio.Semaphore(MAX_CONCURRENT_CAD)
if not PORTAL_PASSWORD:
    log.error("PORTAL_PASSWORD is not set — sign-in is disabled until it is configured in .env")
if not AOAI_ENDPOINT:
    log.error("AOAI_ENDPOINT is not set — model calls will fail until it is configured in .env")


# ------------------------------------------------------------- model connection: server-managed by default, optional legacy BYOK
# HOST_CONNECTION_FOR_ALL keeps credentials entirely on the server.  A separate deployment may explicitly disable
# it to restore the legacy per-request visitor endpoint/key headers, which are validated and never persisted here.
AZURE_ENDPOINT_RE = re.compile(r"^https://[A-Za-z0-9-]+\.(openai\.azure\.com|cognitiveservices\.azure\.com|services\.ai\.azure\.com)$")
DEPLOYMENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
API_KEY_RE = re.compile(r"^[A-Za-z0-9._~+/=-]{16,256}$")
# REQUIRE_BYOK=1: live generation / STEP only with a visitor key (saved examples stay free) — protects the host quota.
REQUIRE_BYOK = os.getenv("REQUIRE_BYOK", "0").strip().lower() not in ("0", "false", "off", "")
# This deployment is a signed-in application, not a credential-entry form.  Keep Azure credentials on the
# server and route every authenticated account through the configured host connection by default.  Setting
# this to 0 restores the legacy BYOK behavior for deployments that explicitly need it.
HOST_CONNECTION_FOR_ALL = os.getenv("HOST_CONNECTION_FOR_ALL", "1").strip().lower() not in ("0", "false", "off", "")


@dataclass(frozen=True)
class ModelConnection:
    endpoint: str
    deployment: str
    key: str | None      # visitor's API key; None → host Entra ID token
    source: str          # "host" | "visitor"

    @property
    def host(self) -> str:
        return self.endpoint.split("//", 1)[-1]

    async def client(self) -> AsyncOpenAI:
        # Visitor → their key. Host → AOAI_API_KEY from .env if the resource uses key auth, else an Entra ID token.
        api_key = self.key or AOAI_API_KEY or await tokens.get()
        return AsyncOpenAI(base_url=f"{self.endpoint}/openai/v1", api_key=api_key, timeout=600, max_retries=AOAI_MAX_RETRIES)


def host_connection() -> ModelConnection:
    return ModelConnection(AOAI_ENDPOINT, AOAI_DEPLOYMENT, None, "host")


def connection_from_request(request: Request, lang: str | None = "zh") -> ModelConnection:
    """X-AOAI-Endpoint / X-AOAI-Key / X-AOAI-Deployment → visitor connection; none of them → host default.
    In host-managed mode browser credentials are deliberately ignored, so no key leaves or enters the UI.
    In legacy BYOK mode malformed values are rejected (400) instead of silently falling back to the host key."""
    if HOST_CONNECTION_FOR_ALL:
        return host_connection()
    en = normalize_lang(lang) == "en"
    endpoint = (request.headers.get("x-aoai-endpoint") or "").strip().rstrip("/")
    key = (request.headers.get("x-aoai-key") or "").strip()
    deployment = (request.headers.get("x-aoai-deployment") or "").strip()
    if not endpoint and not key and not deployment:
        if byok_required_for(session_role(request)):
            raise HTTPException(status_code=403, detail=(
                "Live generation on this demo requires your own Azure OpenAI key — open “Model connection” (🔑) in the header. Saved examples remain available."
                if en else "本演示的实时生成需要使用你自己的 Azure OpenAI key —— 请点击顶栏的「模型连接」（🔑）填写；预生成示例不受影响。"))
        return host_connection()
    if not AZURE_ENDPOINT_RE.match(endpoint):
        raise HTTPException(status_code=400, detail=(
            "Endpoint must look like https://<resource>.openai.azure.com (or .cognitiveservices.azure.com / .services.ai.azure.com)"
            if en else "Endpoint 必须形如 https://<资源名>.openai.azure.com（或 .cognitiveservices.azure.com / .services.ai.azure.com）"))
    if not API_KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="API key is missing or malformed" if en else "API key 缺失或格式不正确")
    if not DEPLOYMENT_RE.match(deployment or AOAI_DEPLOYMENT):
        raise HTTPException(status_code=400, detail="Deployment name is malformed" if en else "部署名格式不正确")
    return ModelConnection(endpoint, deployment or AOAI_DEPLOYMENT, key, "visitor")


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temp file + os.replace so a crash mid-write never leaves a truncated JSON behind."""
    tmp = path.with_name(f".{path.name}.{uuid4().hex[:8]}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


async def with_heartbeat(source: AsyncIterator[Any], interval: float | None = None) -> AsyncIterator[tuple[str, Any]]:
    """Re-yield `source` items as ("item", x); whenever the source is silent for `interval` seconds (default
    HEARTBEAT_S), yield ("heartbeat", None) so the SSE response keeps flowing bytes (idle TCP flows are cut by the cloud NAT)."""
    interval = HEARTBEAT_S if interval is None else interval
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for item in source:
                await queue.put(("item", item))
            await queue.put(("end", None))
        except Exception as e:  # noqa: BLE001 — hand the failure to the consumer
            await queue.put(("error", e))

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                kind, item = await asyncio.wait_for(queue.get(), interval)
            except asyncio.TimeoutError:
                yield ("heartbeat", None)
                continue
            if kind == "end":
                return
            if kind == "error":
                raise item
            yield ("item", item)
    finally:
        task.cancel()


async def _single(aw: Any) -> AsyncIterator[Any]:
    yield await aw


def effective_effort(requested: str | None) -> str | None:
    """Reasoning effort actually sent: the request's choice when given, else the server default, moved to the nearest value the
    deployment supports. None means the parameter is omitted (default/off), letting the deployment apply its own default."""
    value = (requested or AOAI_REASONING_EFFORT or "").strip().lower()
    return nearest_effort(value) if value in REASONING_EFFORTS else None


def nearest_effort(value: str) -> str:
    """value when the deployment supports it, else the next supported one up the cost order, else the highest supported one."""
    if value in supported_efforts:
        return value
    higher = [e for e in REASONING_EFFORTS[REASONING_EFFORTS.index(value) + 1:] if e in supported_efforts]
    return higher[0] if higher else supported_efforts[-1]


def retry_effort(kwargs: dict[str, Any], error: Exception) -> bool:
    """After a 400 that names reasoning_effort: learn the values the error lists as supported and switch to the nearest one, or
    drop the parameter (the deployment's own default) when it lists none we know. False when the error is about something else."""
    global supported_efforts
    message = str(error)
    if "reasoning_effort" not in kwargs or "reasoning_effort" not in message:
        return False
    sent = kwargs.pop("reasoning_effort")
    listed = re.search(r"Supported values are:([^.]*)", message)
    known = tuple(e for e in REASONING_EFFORTS if listed and f"'{e}'" in listed.group(1))
    if known:
        if known != supported_efforts:
            log.warning("the deployment supports reasoning_effort %s only (it refused %s)", ", ".join(known), sent)
        supported_efforts = known
        if nearest_effort(sent) != sent:
            kwargs["reasoning_effort"] = nearest_effort(sent)
    return True


# ----------------------------------------------------------------------------- auth
def _sign(payload: str) -> str:
    return hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def session_ttl_for(role: str) -> int:
    """Visitors: 12 h. Owner: 30 days — the presenter signs in once per browser and never types a key (host connection)."""
    return OWNER_SESSION_TTL if role == ROLE_OWNER else SESSION_TTL


def make_session(user: str, role: str = ROLE_VISITOR) -> str:
    payload = f"{user}|{role}|{int(time.time()) + session_ttl_for(role)}"
    return f"{payload}|{_sign(payload)}"


def read_session(cookie: str | None) -> tuple[str, str] | None:
    """(user, role) for a valid, unexpired cookie; None otherwise. Format: user|role|exp|sig."""
    if not cookie or cookie.count("|") != 3:
        return None
    user, role, exp, sig = cookie.split("|")
    if not hmac.compare_digest(sig, _sign(f"{user}|{role}|{exp}")):
        return None
    if not exp.isdigit() or int(exp) < time.time() or role not in (ROLE_OWNER, ROLE_VISITOR):
        return None
    return user, role


def require_user(request: Request) -> str:
    session = read_session(request.cookies.get(COOKIE))
    if not session:
        raise HTTPException(status_code=401, detail="not signed in")
    return session[0]


def session_role(request: Request) -> str:
    session = read_session(request.cookies.get(COOKIE))
    return session[1] if session else ROLE_VISITOR


def byok_required_for(role: str) -> bool:
    """Legacy REQUIRE_BYOK applies to visitors only when server-managed mode is explicitly disabled."""
    return not HOST_CONNECTION_FOR_ALL and REQUIRE_BYOK and role != ROLE_OWNER


VENDOR_DIR = (STATIC / "vendor").resolve()


def precompressed_vendor(request: Request) -> Path | None:
    """`<file>.js.gz` next to a vendor script (written by deploy/remote_install.sh) when the browser accepts gzip.
    three.module.js is 1.27 MB raw / ~330 KB gzipped: this cuts the cold first render by several seconds."""
    path = request.url.path
    if request.method != "GET" or not path.startswith("/static/vendor/") or not path.endswith(".js"):
        return None
    if "gzip" not in request.headers.get("accept-encoding", "").lower():
        return None
    target = (STATIC / path[len("/static/"):].lstrip("/")).resolve()
    if VENDOR_DIR not in target.parents:  # path traversal guard
        return None
    gz = target.with_name(target.name + ".gz")
    return gz if gz.is_file() else None


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]")


def https_redirect_for(request: Request) -> RedirectResponse | None:
    """308 to PUBLIC_BASE_URL for clear-text requests from outside (direct hits on the uvicorn port).
    Requests through the TLS proxy arrive with scheme https (--proxy-headers); loopback and /healthz stay untouched."""
    if not PUBLIC_BASE_URL or request.url.scheme != "http" or request.url.path == "/healthz":
        return None
    host = (request.headers.get("host") or "").split(":")[0].lower()
    if not host or host in LOCAL_HOSTS:
        return None
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(f"{PUBLIC_BASE_URL}{request.url.path}{query}", status_code=308)


@app.middleware("http")
async def static_cors(request: Request, call_next):
    redirect = https_redirect_for(request)
    if redirect is not None:
        return redirect
    gz = precompressed_vendor(request)
    if gz is not None:
        return FileResponse(gz, media_type="text/javascript; charset=utf-8",
                            headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding", "Access-Control-Allow-Origin": "*",
                                     "Cache-Control": "public, max-age=86400"})
    response = await call_next(request)
    # The viewer iframe is sandboxed (opaque origin); module scripts need CORS on vendor files.
    if request.url.path.startswith("/static/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        long_cache = "/static/vendor/" in request.url.path and response.status_code == 200
        response.headers["Cache-Control"] = "public, max-age=86400" if long_cache else "no-cache"
    return response


class LoginBody(BaseModel):
    username: str
    password: str


def _credentials_match(username: str, password: str, expected_user: str | None, expected_password: str | None) -> bool:
    if not expected_user or not expected_password:
        return False
    # Compare bytes: compare_digest() on str raises TypeError for non-ASCII input (a CJK username would 500).
    return hmac.compare_digest(username.encode("utf-8"), expected_user.encode("utf-8")) and \
        hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))


@app.post("/api/login")
async def login(body: LoginBody, response: Response, request: Request):
    if not PORTAL_PASSWORD and not PORTAL_OWNER_PASSWORD:
        raise HTTPException(status_code=503, detail="登录未配置：服务器缺少 PORTAL_PASSWORD / Sign-in not configured on the server")
    user = body.username.strip()
    if _credentials_match(user, body.password, PORTAL_OWNER_USERNAME, PORTAL_OWNER_PASSWORD):
        role = ROLE_OWNER
    elif _credentials_match(user, body.password, PORTAL_USERNAME, PORTAL_PASSWORD):
        role = ROLE_VISITOR
    else:
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    # Behind the TLS front (X-Forwarded-Proto: https via --proxy-headers) the session cookie is marked Secure.
    secure = request.url.scheme == "https"
    response.set_cookie(COOKIE, make_session(user, role), max_age=session_ttl_for(role), httponly=True, samesite="lax", secure=secure)
    return {"ok": True, "user": user, "role": role}


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
async def me(request: Request):
    session = read_session(request.cookies.get(COOKIE))
    if not session:
        raise HTTPException(status_code=401, detail="not signed in")
    user, role = session
    return {
        "user": user,
        "role": role,
        "deployment": AOAI_DEPLOYMENT,
        "endpoint": AOAI_ENDPOINT,
        "endpoint_host": AOAI_ENDPOINT.split("//", 1)[-1],
        "host_auth": "api_key" if AOAI_API_KEY else "entra_id",
        "host_connection_for_all": HOST_CONNECTION_FOR_ALL,
        "reasoning_effort": effective_effort(None),
        "reasoning_efforts": list(supported_efforts),
        "stats": stats,
        "cached": sorted(p.stem for p in CACHE_DIR.glob("*.json") if not p.stem.endswith(".en")),
        "cached_en": sorted(p.stem[:-3] for p in CACHE_DIR.glob("*.en.json")),
        "cad_cached": cad_cached_ids(),
        "render_cached": render_cached_ids(),
        "cad_available": CAD_AVAILABLE,
        "limits": {"max_concurrent_generations": MAX_CONCURRENT_GENERATIONS, "max_concurrent_cad": MAX_CONCURRENT_CAD,
                   "max_prompt_chars": MAX_PROMPT_CHARS, "heartbeat_s": HEARTBEAT_S},
        "byok_required": byok_required_for(role),   # effective for *this* user: the owner is exempt
        "image_deployment": AOAI_IMAGE_DEPLOYMENT or None,
        "render_sizes": list(RENDER_SIZES), "render_qualities": list(RENDER_QUALITIES),
        "concept_providers": [p for p, on in (("gpt-image", bool(AOAI_IMAGE_DEPLOYMENT)), ("mai", mai_enabled())) if on],
        "mai_model": MAI_MODEL if mai_enabled() else None,
        "mai_edits": mai_enabled(),   # MAI-Image-2.6 also refines (multipart edits) — verified 2026-09-11
    }


# ------------------------------------------------------------------------ scenarios
def cache_path(scenario_id: str, lang: str | None = "zh") -> Path:
    """cache/<id>.json holds the Chinese example, cache/<id>.en.json the English one."""
    sid = re.sub(r"[^a-z0-9_-]", "", scenario_id.lower())
    return CACHE_DIR / (f"{sid}.en.json" if normalize_lang(lang) == "en" else f"{sid}.json")


@app.get("/api/scenarios")
async def scenarios(request: Request):
    require_user(request)
    return {"scenarios": public_scenarios(), "industries": public_industries()}


@app.get("/api/industries")
async def industries():
    """Public (pre-login) industry groups: the sign-in page titles itself after ?industry=… before any session exists."""
    return {"industries": public_industries(), "default": DEFAULT_INDUSTRY}


@app.get("/api/cache/{scenario_id}")
async def cached_example(scenario_id: str, request: Request, lang: str = "zh"):
    require_user(request)
    lang = normalize_lang(lang)
    path = cache_path(scenario_id, lang)
    served_lang = lang
    if not path.exists():
        # No example saved in the requested language: serve the other one and say so (the UI shows a note).
        other = "zh" if lang == "en" else "en"
        if cache_path(scenario_id, other).exists():
            path, served_lang = cache_path(scenario_id, other), other
    if not path.exists():
        raise HTTPException(status_code=404, detail="no cached example")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data.get("html"), str):
        data["html"] = normalize_html(data["html"])
    # Cache provenance is assigned here, never trusted from the stored model output.
    data["source"] = "pre_generated"
    data["request_id"] = None
    data["lang"] = served_lang
    data["lang_fallback"] = served_lang != lang
    return JSONResponse(data)


# ------------------------------------------------------------------------ generation
IMAGE_DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=\s]+$")


class Message(BaseModel):
    role: str = Field(pattern=r"^(user|assistant|system)$")
    # Assistant turns carry the previous raw model output (tens of KB); user turns are capped at MAX_PROMPT_CHARS.
    content: str = Field(max_length=200_000)
    image: str | None = Field(default=None, max_length=MAX_IMAGE_DATA_URL_CHARS)  # data URL (PNG / JPEG / WebP only)

    @field_validator("image")
    @classmethod
    def _image_is_supported_data_url(cls, v: str | None) -> str | None:
        if v is not None and not IMAGE_DATA_URL_RE.match(v):
            raise ValueError("image must be a base64 data URL of type image/png, image/jpeg or image/webp")
        return v

    @model_validator(mode="after")
    def _user_prompt_length(self) -> "Message":
        if self.role == "user" and len(self.content) > MAX_PROMPT_CHARS:
            raise ValueError(f"prompt too long ({len(self.content)} > {MAX_PROMPT_CHARS} characters)")
        return self


class GenerateBody(BaseModel):
    scenario_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    messages: list[Message] = Field(min_length=1, max_length=40)
    save_as_cache: bool = False  # only honoured for the pregen script (loopback)
    lang: str = Field(default="zh", max_length=16)  # UI language: 'zh' (default) or 'en' → model writes all text in that language
    # UI choice of GPT-6 reasoning effort; None → server default (AOAI_REASONING_EFFORT). Anything else is a 422.
    reasoning_effort: str | None = Field(default=None, pattern=r"^(none|low|medium|high|xhigh)$")

    @model_validator(mode="after")
    def _last_turn_is_a_bounded_prompt(self) -> "GenerateBody":
        # The last message is always sent to the model as the user turn, whatever role the client declared.
        if len(self.messages[-1].content) > MAX_PROMPT_CHARS:
            raise ValueError(f"prompt too long ({len(self.messages[-1].content)} > {MAX_PROMPT_CHARS} characters)")
        return self


def _safe_json(text: str, default: Any) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return default


# `studio-kit` is the project's own look-and-feel helper (static/studio-kit.js): calibrated PBR presets, filleted
# boxes, a Blender-style light rig. Every generated scene gets the alias, whether or not the model wrote it.
CANONICAL_IMPORTMAP = ('<script type="importmap">{"imports":{"three":"/static/vendor/three/three.module.js",'
                       '"three/addons/":"/static/vendor/three/jsm/","studio-kit":"/static/studio-kit.js"}}</script>')
IMPORTMAP_RE = re.compile(r"<script[^>]*type=[\"']importmap[\"'][^>]*>.*?</script>", re.S | re.I)


def normalize_html(html: str) -> str:
    """Make the generated scene robust: canonical import map, no stray whitespace in vendor URLs."""
    if IMPORTMAP_RE.search(html):
        html = IMPORTMAP_RE.sub(CANONICAL_IMPORTMAP, html, count=1)
    elif "<head" in html:
        html = re.sub(r"<head([^>]*)>", lambda m: f"<head{m.group(1)}>" + CANONICAL_IMPORTMAP, html, count=1)
    html = re.sub(r"([\"'])\s+/static/vendor/", r"\1/static/vendor/", html)
    return html


def parse_output(raw: str) -> dict[str, Any]:
    sections: dict[str, str] = {}
    for i, name in enumerate(SENTINELS):
        nxt = SENTINELS[i + 1] if i + 1 < len(SENTINELS) else "END"
        m = re.search(rf"<<<{name}>>>\s*(.*?)\s*(?=<<<{nxt}>>>|<<<END>>>|\Z)", raw, re.S)
        sections[name.lower()] = m.group(1).strip() if m else ""
    html = sections["html"]
    html = re.sub(r"^```(?:html)?\s*", "", html)
    html = re.sub(r"\s*```$", "", html)
    if "<html" not in html.lower():
        m = re.search(r"(<!DOCTYPE html.*?</html>)", raw, re.S | re.I)
        html = m.group(1) if m else html
    if "<html" in html.lower():
        html = normalize_html(html)
    metrics = _safe_json(sections["metrics"], [])
    suggestions = _safe_json(sections["suggestions"], [])
    if not isinstance(metrics, list):
        metrics = []
    if not isinstance(suggestions, list):
        suggestions = []
    summary = sections["summary"] or (raw[:400] if "<html" not in html.lower() else "")
    return {
        "ok": "<html" in html.lower() and "</html>" in html.lower() and "<<<END>>>" in raw,
        "summary": summary,
        "html": html,
        "metrics": [m for m in metrics if isinstance(m, dict)][:10],
        "suggestions": [str(s) for s in suggestions][:3],
    }


def build_messages(body: GenerateBody) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system_prompt_for(body.scenario_id, body.lang)}]
    history = body.messages[:-1]
    # keep the last N assistant turns (with their preceding user turns) so the model can iterate
    assistant_idx = [i for i, m in enumerate(history) if m.role == "assistant"]
    keep_from = 0
    if len(assistant_idx) > HISTORY_TURNS:
        keep_from = max(0, assistant_idx[-HISTORY_TURNS] - 1)
    for m in history[keep_from:]:
        if m.role not in ("user", "assistant"):
            continue
        msgs.append({"role": m.role, "content": m.content})
    last = body.messages[-1]
    if last.image:
        fallback = "Model the part shown in this drawing/photo." if normalize_lang(body.lang) == "en" else "请根据这张图纸/照片建模。"
        msgs.append({"role": "user", "content": [
            {"type": "text", "text": last.content or fallback},
            {"type": "image_url", "image_url": {"url": last.image, "detail": "high"}},
        ]})
    else:
        msgs.append({"role": "user", "content": last.content})
    return msgs


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def previous_assistant_output(body: GenerateBody) -> str | None:
    """Raw output of the last assistant turn (the model being iterated on), if any."""
    for m in reversed(body.messages[:-1]):
        if m.role == "assistant" and m.content and "<<<HTML>>>" in m.content:
            return m.content
    return None


def early_html(raw: str) -> str | None:
    """Return the HTML block once the model has moved on to <<<METRICS>>> (so the scene can render early)."""
    if "<<<METRICS>>>" not in raw or "<<<HTML>>>" not in raw:
        return None
    block = raw.split("<<<HTML>>>", 1)[1].split("<<<METRICS>>>", 1)[0].strip()
    block = re.sub(r"^```(?:html)?\s*", "", block)
    block = re.sub(r"\s*```$", "", block)
    if "<html" not in block.lower() or "</html>" not in block.lower():
        return None
    return normalize_html(block)


async def run_generation(body: GenerateBody, conn: ModelConnection | None = None) -> AsyncIterator[str]:
    conn = conn or host_connection()
    t0 = time.time()
    request_id = uuid4().hex
    client = None
    stream = None
    slot = False
    effort = effective_effort(body.reasoning_effort)
    yield sse("start", {"model": conn.deployment, "t": t0, "request_id": request_id, "source": "live", "reasoning_effort": effort,
                        "key_source": conn.source, "endpoint_host": conn.host})
    try:
        if gen_slots.locked():
            raise RuntimeError(f"Server busy: {MAX_CONCURRENT_GENERATIONS} generations already running — please retry in a moment."
                               if normalize_lang(body.lang) == "en"
                               else f"服务器繁忙：已有 {MAX_CONCURRENT_GENERATIONS} 个生成任务在运行，请稍后重试。")
        await gen_slots.acquire()
        slot = True
        # Host connection: a cold Entra token fetch can take seconds — heartbeats cover it. Visitor key: immediate.
        async for kind, item in with_heartbeat(_single(conn.client())):
            if kind == "heartbeat":
                yield sse("heartbeat", {"t": round(time.time() - t0, 1)})
            else:
                client = item
        kwargs: dict[str, Any] = {
            "model": conn.deployment,
            "messages": build_messages(body),
            "stream": True,
            "max_completion_tokens": AOAI_MAX_TOKENS,
            "stream_options": {"include_usage": True},
        }
        if effort:
            kwargs["reasoning_effort"] = effort
        previous = previous_assistant_output(body) if AOAI_PREDICTED_OUTPUTS else None
        if previous:
            kwargs["prediction"] = {"type": "content", "content": previous}
        async def open_stream() -> Any:
            for _ in range(3):
                try:
                    return await client.chat.completions.create(**kwargs)
                except BadRequestError as e:
                    msg = str(e)
                    # Drop optional parameters the deployment does not accept and retry.
                    if "prediction" in kwargs and ("prediction" in msg or "predict" in msg.lower()):
                        kwargs.pop("prediction")
                        log.warning("request=%s predicted outputs rejected by deployment, retrying without", request_id)
                    elif not retry_effort(kwargs, e):
                        raise
            return None

        # Azure only sends the response headers together with the first chunk, so the whole time-to-first-token
        # (minutes at higher reasoning effort) is spent inside create(): heartbeats must cover that wait too.
        async for kind, item in with_heartbeat(_single(open_stream())):
            if kind == "heartbeat":
                yield sse("heartbeat", {"t": round(time.time() - t0, 1)})
            else:
                stream = item
        if stream is None:
            raise ValueError("无法创建模型请求。")
        chunks: list[str] = []
        usage = None
        first_token_at = None
        actual_model = None
        completion_id = None
        finish_reason = None
        html_sent = False
        tail = ""  # rolling window so a sentinel split across tokens is still detected
        async for kind, chunk in with_heartbeat(stream):
            if kind == "heartbeat":
                # Decoding pause longer than HEARTBEAT_S: keep the connection alive.
                yield sse("heartbeat", {"t": round(time.time() - t0, 1)})
                continue
            actual_model = chunk.model or actual_model
            completion_id = chunk.id or completion_id
            if getattr(chunk, "usage", None):
                usage = chunk.usage.model_dump()
            if chunk.choices and chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                piece = chunk.choices[0].delta.content
                if first_token_at is None:
                    first_token_at = time.time()
                chunks.append(piece)
                yield sse("delta", {"text": piece})
                # As soon as the HTML block is closed, let the browser start rendering while the
                # model is still writing metrics and suggestions (saves ~10–20 s of perceived wait).
                if not html_sent:
                    window = tail + piece
                    tail = window[-64:]
                    if "<<<METRICS>>>" in window:
                        html = early_html("".join(chunks))
                        if html:
                            html_sent = True
                            # The stream is open, so the effort is settled: a refused choice has already been replaced.
                            yield sse("html", {"html": html, "request_id": request_id, "source": "live",
                                               "reasoning_effort": kwargs.get("reasoning_effort"), "t": round(time.time() - t0, 1)})
        raw = "".join(chunks)
        en = normalize_lang(body.lang) == "en"
        if finish_reason != "stop":
            raise ValueError(f"The model did not finish normally (finish_reason={finish_reason}); no cached result was substituted." if en
                             else f"模型输出未正常完成（finish_reason={finish_reason}），未使用缓存替代。")
        parsed = parse_output(raw)
        if not parsed["ok"]:
            raise ValueError("The model did not return complete HTML with the END sentinel; please retry. No cached result was substituted." if en
                             else "模型未返回完整的 HTML 与结束标记，请重试；未使用缓存替代。")
        latency = round(time.time() - t0, 1)
        stats["generated"] += 1
        if conn.source == "visitor":
            stats["generated_visitor_key"] += 1
        stats["last_latency_s"] = latency
        stats["last_effort"] = kwargs.get("reasoning_effort")
        details = (usage or {}).get("completion_tokens_details") or {}
        result = {
            **parsed,
            "raw": raw,
            "usage": usage,
            "latency_s": latency,
            "ttft_s": round(first_token_at - t0, 1) if first_token_at else None,
            "model": conn.deployment,
            "actual_model": actual_model,
            "completion_id": completion_id,
            "request_id": request_id,
            "source": "live",
            "key_source": conn.source,          # "host" (Entra token of this deployment) or "visitor" (their own key)
            "endpoint_host": conn.host,
            "predicted": bool(kwargs.get("prediction")),
            "accepted_prediction_tokens": details.get("accepted_prediction_tokens"),
            "reasoning_effort": kwargs.get("reasoning_effort"),  # what was actually sent (None = deployment default)
            "reasoning_tokens": details.get("reasoning_tokens"),
            "scenario_id": body.scenario_id,
            "prompt": body.messages[-1].content,
            "lang": normalize_lang(body.lang),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        # Saved examples come from the host deployment only (pregen over loopback) — a visitor's model never writes the cache.
        if body.save_as_cache and body.scenario_id and parsed["ok"] and conn.source == "host":
            path = cache_path(body.scenario_id, body.lang)
            atomic_write_text(path, json.dumps(result, ensure_ascii=False))
            log.info("cached example saved to %s (%.1fs)", path.name, latency)
        log.info("request=%s generation done scenario=%s ok=%s latency=%.1fs ttft=%s tokens=%s effort=%s reasoning_tokens=%s key=%s host=%s predicted=%s accepted=%s",
                 request_id, body.scenario_id, parsed["ok"], latency, result["ttft_s"], (usage or {}).get("completion_tokens"),
                 result["reasoning_effort"], result["reasoning_tokens"], conn.source, conn.host, result["predicted"], result["accepted_prediction_tokens"])
        yield sse("done", result)
    except asyncio.CancelledError:
        # Client disconnected (cancel button / navigation) — release the upstream stream quietly.
        log.info("request=%s cancelled by client after %.1fs", request_id, time.time() - t0)
        raise
    except Exception as e:  # noqa: BLE001 — every failure must reach the browser as an SSE error event
        log.exception("request=%s generation failed (key=%s host=%s)", request_id, conn.source, conn.host)
        yield sse("error", {"message": f"{type(e).__name__}: {e}", "request_id": request_id, "source": "live", "key_source": conn.source})
    finally:
        if slot:
            gen_slots.release()
        if stream is not None:
            await stream.close()
        if client is not None:
            await client.close()


@app.post("/api/generate")
async def generate(body: GenerateBody, request: Request):
    require_user(request)
    conn = connection_from_request(request, body.lang)
    if body.save_as_cache and request.client and request.client.host not in ("127.0.0.1", "::1"):
        body.save_as_cache = False
    return StreamingResponse(run_generation(body, conn), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/connection/test")
async def connection_test(request: Request, lang: str = "zh"):
    """Cheapest possible round-trip with the effective connection before a long-running generation."""
    require_user(request)
    conn = connection_from_request(request, lang)
    t0 = time.time()
    client = await conn.client()
    try:
        kwargs: dict[str, Any] = {"model": conn.deployment, "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                                  "max_completion_tokens": 64, "reasoning_effort": supported_efforts[0]}
        try:
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), 60)
        except BadRequestError as e:
            if not retry_effort(kwargs, e):
                raise
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), 60)
        return {"ok": True, "deployment": conn.deployment, "endpoint_host": conn.host, "actual_model": resp.model,
                "latency_s": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001 — the visitor needs the upstream message (401 / 404 deployment / DNS); the key never appears in it
        log.info("connection test failed host=%s deployment=%s: %s", conn.host, conn.deployment, type(e).__name__)
        return {"ok": False, "deployment": conn.deployment, "endpoint_host": conn.host, "error": f"{type(e).__name__}: {str(e)[:300]}",
                "latency_s": round(time.time() - t0, 1)}
    finally:
        await client.close()


# ------------------------------------------------------------------- 轨 B: CadQuery → STEP
CAD_PROMPT = """你是「GPT-6 3D 建模工坊」的 CAD 实体建模引擎（轨 B）。不要在输出中提及任何具体公司或品牌名称。用户已经在轨 A 得到一个 three.js 可视化模型；现在要把同一个零件写成 CadQuery（OCCT B-rep）脚本，由服务器执行后导出 STEP 工程实体，供 SolidWorks / NX / Creo 直接打开，并用 B-rep 精确计算体积与质量。

【输出契约 —— 必须严格遵守】
只输出两个区块，哨兵行单独成行，区块之外不得有任何文字，不要 markdown 代码围栏：
<<<SUMMARY>>>
60–120 字中文：实体建模思路、与 three.js 可视化模型的一致性说明、做了哪些简化（例如翅片数量、螺纹、圆角）。纯文本。
<<<CAD>>>
一个完整的 Python 脚本（纯代码，不要围栏）。
<<<END>>>

【脚本规范】
1. 只允许 import cadquery as cq 以及标准库 math / itertools / functools。禁止 os、sys、subprocess、open()、exec/eval、cq.exporters 等任何文件或系统操作——导出由服务器完成。
2. 参数集中在脚本开头的 P = {...} 字典中（单位 mm，键名用英文，值只用数字/字符串），尽量沿用 three.js 版本 P 中的尺寸，保证两轨一致。
3. 必须定义变量 result：一个 cq.Workplane（栈上为实体）或 cq.Shape；多零件用 .union() 合并成一个实体，或用 cq.Compound.makeCompound([...]) 组成复合体。定义 DENSITY（g/cm³：铝 2.70、铜 8.96、黄铜 8.50、不锈钢 7.90、工程塑料 1.40）。
4. 可选：METRICS = [{"label","value","unit","note"}] 列出 3–5 项由脚本按 P 计算的补充工程量（流道总长、翅片数、换热面积等）；label / note 用中文，value 用 round() 保留 2–3 位小数，unit 可含 ²/³ 等字符；体积、质量、包络尺寸由服务器从 B-rep 计算，不要重复给出。
5. 性能：布尔运算（union / cut）总次数控制在 60 次以内，整个脚本必须在 60 s 内完成。重复件（翅片、针肋、扁管）数量 > 40 时不要逐个 union：用 cq.Compound.makeCompound(list_of_solids) 组成复合体，或按数量比例简化（在 SUMMARY 中说明）。避免对同一个大实体做几十次 cut：先把所有要减去的特征 union 成一个工具体，再 cut 一次。
6. 只用稳定 API：box / cylinder / circle / rect / slot2D / polyline / polygon / extrude / cut / union / translate / rotate / faces / edges / workplane / pushPoints / rarray / polarArray / hole / cboreHole / cskHole / fillet / chamfer / shell / revolve / sweep / cq.Solid.makeBox / makeCylinder / makeTorus / cq.Compound.makeCompound。
7. 代码必须自洽、无语法错误、不引用未定义变量；不要 print；不要 top-level 的 try/except 吞掉错误。
8. 若对话中给出了上一次执行的错误信息（Traceback），针对该错误修改脚本并保持其余结构不变。

【分件与材质 —— 供查看器大纲树与材质着色】
9. 必须定义 PARTS = {"中文部件名": 实体, ...}：把 result 中每个可独立命名的零部件（壳体、盖板、接头、阀芯、线圈座、安装支架、密封圈、紧固件…）单独列出，2–12 项；键用简短中文名（≤ 12 字），值是构成 result 的 cq.Workplane / cq.Shape（不要重新建一遍，复用中间变量）。PARTS 中各实体的并集应等于 result。单一实体零件也要拆：至少按"主体 / 接口 / 附件"分 2–3 项（例如冷板拆成 上盖板 / 流道基板 / 进出口接头）。
10. 定义 MATERIALS = {"中文部件名": "<preset>"}，为每个 PARTS 条目指定材质预设：aluminum（机加工/拉丝铝）、aluminumCast（压铸铝）、anodized（阳极氧化铝壳）、copper、brass、steel（不锈钢）、steelDark（发黑钢紧固件）、powderCoat（喷粉钢板）、polymer（深色工程塑料）、polymerLight（浅色塑料）、rubber（O 圈/密封）、copperWire（线圈）、pcb。混合材料零件用 DENSITIES = {"中文部件名": 密度} 覆盖单件密度。

【制造特征 —— 这是与"积木式模型"的本质区别，必须做到】
11. 外形圆角与倒角必须真实存在于 B-rep 中：机加工件外轮廓竖直边 .edges("|Z").fillet(r)（r 取 2–6 mm，且小于相邻边长的 1/3）；接口/凸台的端面 .faces("<X").chamfer(0.5–1.0)；钣金/压铸件至少对主体做一次 fillet。已做圆角的轮廓上再倒角时只选直边 .faces(">Z").edges("not %CIRCLE").chamfer(c)（倒角撞上圆角的相切边会让 OCCT 报 BRep_API: command not done）；fillet / chamfer 失败就用 try/except 换更小的尺寸或只对部分边做（见示例中的 soft_chamfer），不要放弃，也不要用 try/except 包住整个轮廓或布尔运算。
12. 必须包含真实产品上可见的次级特征，每个零件至少 3 类：① 安装孔——四角或安装耳上的通孔 .hole(d) 或沉孔 .cboreHole(d, cbore_d, cbore_depth)，孔径用标准值（M4 → 4.5，M5 → 5.5，M6 → 6.6，M8 → 9）；② 接口端的螺纹/卡口段——用 2–3 段不同直径的圆柱 + 端面倒角表示，内孔必须真的打穿（cut）而不是画一个圆；③ 腰形槽/减重槽——.slot2D(length, width).cutBlind(-depth)；④ 密封槽——O 圈槽 .rect/.circle 环形 cutBlind 1.5–2.5 mm 深；⑤ 铭牌凹区——浅 0.3 mm 的矩形 cutBlind；⑥ 翅片/针肋/扁管阵列——.rarray / .pushPoints 批量布置。
13. 壳体类零件（阀体、泵壳、集成模块、CDU 箱体）用 .shell(-t) 或内腔 cut 做出真实壁厚，不要实心块；内部流道/阀腔必须是真实空腔（cut 出来的），剖切时能看见。
14. 装配体各部件之间必须有真实配合面：接头插入壳体 2–5 mm（而不是悬浮接触），盖板与基板间留 0.1 mm 间隙或直接重合，紧固件头部坐在沉孔里。
15. 圆柱面段数由 OCCT 控制，不要自己用多边形近似圆；所有曲面特征用真实 revolve / cylinder / torus。""" + ("""

【参考示例 —— 一个已在服务器 OCCT 上执行通过的完整脚本（电池水冷板：4 个部件、200 个面、约 12 s）】
它展示了规则 9–15 的写法：PARTS / MATERIALS / DENSITIES / NAME、真实圆角与安全倒角、沉孔安装耳、O 圈槽、腰形减重槽、铭牌凹区、两段直径的接头与真实通孔、接头插入基板。按当前零件重新建模，不要照抄尺寸：
""" + CAD_EXAMPLE if CAD_EXAMPLE else "")

CAD_PROMPT_EN = """

【输出语言 —— English output required】
The user interface is in English: write the SUMMARY (50–100 English words) in English, and use English for the METRICS "label" / "note" / "unit" strings and for code comments. Keep the sentinels, the P dictionary, DENSITY, result and all numbers exactly as specified above.
Part names are shown to the user: the keys of PARTS / MATERIALS / DENSITIES and NAME must be short English names (at most 32 characters, e.g. "Channel base plate", "Inlet fitting"). The reference example above uses Chinese names only as an illustration; never copy them."""

CAD_METRIC_LABELS = {
    "zh": {"volume": ("STEP 实体体积", "OCCT B-rep 精确体积"), "mass": ("STEP 实体质量", "密度 {d} g/cm³"),
           "bbox": ("外形包络", "B-rep 包围盒"), "area": ("表面积", "全部外表面（含内腔）"), "topo": ("实体 / 面数", "STEP 拓扑规模")},
    "en": {"volume": ("STEP solid volume", "Exact OCCT B-rep volume"), "mass": ("STEP solid mass", "Density {d} g/cm³"),
           "bbox": ("Bounding box", "B-rep bounding box"), "area": ("Surface area", "All outer surfaces (incl. cavities)"),
           "topo": ("Solids / faces", "STEP topology size")},
}


class CadBody(BaseModel):
    scenario_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARS)      # user's modelling request (latest turn)
    summary: str = Field(default="", max_length=4000)                 # SUMMARY of the three.js result
    html: str = Field(default="", max_length=MAX_CAD_HTML_CHARS)      # three.js HTML (the P block is extracted for parameter parity)
    request_id: str | None = Field(default=None, max_length=64)       # provenance link to the 轨 A result (live request id or null for cache)
    lang: str = Field(default="zh", max_length=16)                    # UI language → SUMMARY / metric labels language
    reasoning_effort: str | None = Field(default=None, pattern=r"^(none|low|medium|high|xhigh)$")  # None → server default


def extract_param_block(html: str, limit: int = 3500) -> str:
    """The `const P = {...}` block of the generated scene, so the CAD script uses the same numbers."""
    m = re.search(r"const\s+P\s*=\s*\{", html)
    if not m:
        return ""
    i, depth = m.end(), 1
    while depth and i < len(html) and i - m.start() < limit:
        depth += (html[i] == "{") - (html[i] == "}")
        i += 1
    return html[m.start():i]


def parse_cad_output(raw: str) -> dict[str, Any]:
    m = re.search(r"<<<SUMMARY>>>\s*(.*?)\s*(?=<<<CAD>>>|\Z)", raw, re.S)
    summary = m.group(1).strip() if m else ""
    if "<<<CAD>>>" in raw or "```" in raw:
        code = cad_runner.extract_code(raw)
    else:
        # Contract ignored: take everything from the first import statement (drops leading prose).
        m2 = re.search(r"^(?:import|from)\s+\w", raw, re.M)
        code = (raw[m2.start():] if m2 else raw).split("<<<END>>>", 1)[0].strip() + "\n"
    return {"summary": summary, "code": code}


def cad_messages(body: CadBody, attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    en = normalize_lang(body.lang) == "en"
    scenario = next((s for s in public_scenarios() if s["id"] == body.scenario_id), None)
    title = (scenario.get("title_en") if en else scenario["title"]) if scenario else None
    ctx = [(f"Part / scenario: {title}" if title else "Part / scenario: custom") if en else (f"零件/场景：{title}" if title else "零件/场景：自定义"),
           ("User request: " if en else "用户需求：") + (body.prompt or "").strip()[:1500]]
    if body.summary:
        ctx.append(("three.js version summary: " if en else "three.js 版本摘要：") + body.summary.strip()[:800])
    p_block = extract_param_block(body.html or "")
    if p_block:
        ctx.append(("Parameter block of the three.js version (reuse its dimensions):\n" if en else "three.js 版本的参数块（请沿用其中的尺寸）：\n") + p_block)
    ctx.append("Output the CadQuery script per the contract." if en else "请按契约输出 CadQuery 脚本。")
    system = CAD_PROMPT + CAD_PROMPT_EN if en else CAD_PROMPT
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(ctx)}]
    repair = ("The server failed to run your script; the error is below. Fix it and re-output the complete answer under the same contract, without explanations:\n"
              if en else "服务器执行你的脚本失败，错误如下（请修正后按同样契约完整重新输出，不要解释）：\n")
    for a in attempts:
        msgs.append({"role": "assistant", "content": a["raw"]})
        msgs.append({"role": "user", "content": repair + a["error"][:2500]})
    return msgs


def prune_cad_jobs(keep: int) -> None:
    jobs = sorted((p for p in CAD_DIR.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    for old in jobs[:-keep] if keep > 0 else jobs:
        shutil.rmtree(old, ignore_errors=True)


async def cad_model_call(messages: list[dict[str, Any]], effort: str | None = None, conn: ModelConnection | None = None) -> tuple[str, dict[str, Any]]:
    conn = conn or host_connection()
    client = await conn.client()
    try:
        kwargs: dict[str, Any] = {"model": conn.deployment, "messages": messages, "max_completion_tokens": 12000}
        if effort:
            kwargs["reasoning_effort"] = effort
        try:
            resp = await client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            if not retry_effort(kwargs, e):
                raise
            resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        if choice.finish_reason != "stop":
            raise ValueError(f"模型输出未正常完成（finish_reason={choice.finish_reason}）")
        usage = resp.usage.model_dump() if resp.usage else {}
        return choice.message.content or "", {"usage": usage, "actual_model": resp.model, "completion_id": resp.id,
                                              "reasoning_effort": kwargs.get("reasoning_effort")}
    finally:
        await client.close()


async def run_cad(body: CadBody, conn: ModelConnection | None = None) -> AsyncIterator[str]:
    """SSE: `start` → (`attempt` → `heartbeat`* → `attempt`/`attempt_failed`)×N → `done` | `error`. One job dir per request."""
    conn = conn or host_connection()
    t0 = time.time()
    job_id = uuid4().hex[:12]
    job_dir = CAD_DIR / job_id
    effort = effective_effort(body.reasoning_effort)
    yield sse("start", {"job_id": job_id, "model": conn.deployment, "source": "live", "max_attempts": CAD_MAX_ATTEMPTS, "reasoning_effort": effort,
                        "key_source": conn.source, "endpoint_host": conn.host})
    attempts: list[dict[str, Any]] = []
    en = normalize_lang(body.lang) == "en"
    slot = False
    procs: list[subprocess.Popen] = []       # OCCT children of this job (killed if the client goes away)
    occt_done = threading.Event()            # set by the worker thread when run_script has returned
    occt_running = False
    try:
        if not CAD_AVAILABLE:
            raise RuntimeError("CadQuery is not installed on the server (pip install cadquery); STEP export unavailable."
                               if en else "服务器未安装 CadQuery（pip install cadquery），无法导出 STEP。")
        if cad_slots.locked():
            raise RuntimeError(f"Server busy: {MAX_CONCURRENT_CAD} STEP jobs already running — please retry in a moment." if en
                               else f"服务器繁忙：已有 {MAX_CONCURRENT_CAD} 个 STEP 任务在运行，请稍后重试。")
        await cad_slots.acquire()
        slot = True
        for n in range(1, CAD_MAX_ATTEMPTS + 1):
            yield sse("attempt", {"n": n, "phase": "model", "t": round(time.time() - t0, 1)})
            # The model call is one silent await of 1–12 min: heartbeats keep the SSE flow alive meanwhile.
            raw, meta = "", {}
            async for kind, item in with_heartbeat(_single(cad_model_call(cad_messages(body, attempts), effort, conn))):
                if kind == "heartbeat":
                    yield sse("heartbeat", {"n": n, "phase": "model", "t": round(time.time() - t0, 1)})
                else:
                    raw, meta = item
            parsed = parse_cad_output(raw)
            code = parsed["code"]
            problem = cad_runner.validate_code(code)
            if problem:
                attempts.append({"raw": raw, "error": (f"Static check failed: {problem}" if en else f"静态检查未通过：{problem}"), "n": n})
                log.warning("cad job=%s attempt=%d rejected: %s", job_id, n, problem)
                yield sse("attempt_failed", {"n": n, "error": problem, "t": round(time.time() - t0, 1)})
                continue
            yield sse("attempt", {"n": n, "phase": "occt", "t": round(time.time() - t0, 1), "code_lines": code.count("\n")})
            attempt_dir = job_dir / f"a{n}"
            result: dict[str, Any] = {}
            occt_done.clear()
            occt_running = True

            def run_occt(code=code, attempt_dir=attempt_dir) -> dict[str, Any]:
                try:
                    return cad_runner.run_script(code, attempt_dir, CAD_TIMEOUT_S, on_start=procs.append)
                finally:
                    occt_done.set()

            async for kind, item in with_heartbeat(_single(asyncio.to_thread(run_occt))):
                if kind == "heartbeat":
                    yield sse("heartbeat", {"n": n, "phase": "occt", "t": round(time.time() - t0, 1)})
                else:
                    result = item
            occt_running = False
            if result.get("ok"):
                for name in ("model.step", "model.stl", "model.py", "model.glb", "parts.json"):
                    shutil.copyfile(attempt_dir / name, job_dir / name)
                if en and any(p["name"].startswith("实体") for p in result.get("parts", [])):
                    # cad_runner names the solids itself when a script has no PARTS; those fallback names are Chinese.
                    for p in result["parts"]:
                        p["name"] = re.sub(r"^实体", "Solid", p["name"])
                    atomic_write_text(job_dir / "parts.json", json.dumps(result["parts"], ensure_ascii=False))
                atomic_write_text(job_dir / "meta.json", json.dumps({
                    "job_id": job_id, "scenario_id": body.scenario_id, "prompt": body.prompt[:2000], "attempts": n,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "linked_request_id": body.request_id,
                    **{k: v for k, v in result.items() if k not in ("params",)}}, ensure_ascii=False))
                prune_cad_jobs(CAD_KEEP_JOBS)
                stats["cad_jobs"] = stats.get("cad_jobs", 0) + 1
                latency = round(time.time() - t0, 1)
                bb = result["bbox_mm"]
                L = CAD_METRIC_LABELS[normalize_lang(body.lang)]
                metrics = [
                    {"label": L["volume"][0], "value": f"{result['volume_mm3'] / 1000:.2f}", "unit": "cm³", "note": L["volume"][1]},
                    {"label": L["mass"][0], "value": f"{result['mass_kg']:.3f}", "unit": "kg", "note": L["mass"][1].format(d=result["density_g_cm3"])},
                    {"label": L["bbox"][0], "value": f"{bb[0]:.1f} × {bb[1]:.1f} × {bb[2]:.1f}", "unit": "mm", "note": L["bbox"][1]},
                    {"label": L["area"][0], "value": f"{result['area_mm2'] / 1e6:.4f}", "unit": "m²", "note": L["area"][1]},
                    {"label": L["topo"][0], "value": f"{result['solids']} / {result['faces']}", "unit": "", "note": L["topo"][1]},
                ] + result.get("extra_metrics", [])
                log.info("cad job=%s done attempts=%d latency=%.1fs occt=%.1fs step=%dB effort=%s", job_id, n, latency,
                         result.get("elapsed_s", 0), result.get("step_bytes", 0), meta.get("reasoning_effort"))
                yield sse("done", {
                    "ok": True, "job_id": job_id, "attempts": n, "summary": parsed["summary"], "code": code,
                    "metrics": metrics, "raw": result, "latency_s": latency, "model": conn.deployment,
                    "actual_model": meta.get("actual_model"), "usage": meta.get("usage"), "source": "live",
                    "key_source": conn.source, "endpoint_host": conn.host,
                    "reasoning_effort": meta.get("reasoning_effort"),
                    "files": {"step": f"/api/cad/file/{job_id}/model.step", "stl": f"/api/cad/file/{job_id}/model.stl",
                              "py": f"/api/cad/file/{job_id}/model.py", "glb": f"/api/cad/file/{job_id}/model.glb"},
                    "parts": result.get("parts", []),
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                })
                return
            attempts.append({"raw": raw, "error": result.get("error", "unknown error"), "n": n})
            log.warning("cad job=%s attempt=%d failed after %.1fs: %s", job_id, n, result.get("elapsed_s", 0),
                        result.get("error", "")[-300:].replace("\n", " | "))
            yield sse("attempt_failed", {"n": n, "error": result.get("error", "")[-1200:], "t": round(time.time() - t0, 1)})
        raise ValueError((f"The CadQuery script failed {CAD_MAX_ATTEMPTS} times in a row; last error: " if en
                          else f"CadQuery 脚本连续 {CAD_MAX_ATTEMPTS} 次执行失败；最后错误：") + attempts[-1]["error"][-600:])
    except asyncio.CancelledError:
        log.info("cad job=%s cancelled by client after %.1fs", job_id, time.time() - t0)
        raise
    except Exception as e:  # noqa: BLE001 — surface every failure to the browser
        log.exception("cad job=%s failed", job_id)
        yield sse("error", {"message": f"{type(e).__name__}: {e}", "job_id": job_id, "attempts": len(attempts)})
    finally:
        if occt_running:
            # Client gone mid-OCCT: a thread cannot be cancelled, so kill the child and hand the slot back only
            # once the worker thread has actually returned (never while an orphaned OCCT process still runs).
            for p in procs:
                cad_runner.kill(p)
            if slot:
                slot = False

                async def release_when_finished() -> None:
                    await asyncio.to_thread(occt_done.wait, CAD_TIMEOUT_S + 30)
                    cad_slots.release()

                asyncio.get_running_loop().create_task(release_when_finished())
        if slot:
            cad_slots.release()


@app.post("/api/cad")
async def cad(body: CadBody, request: Request):
    require_user(request)
    conn = connection_from_request(request, body.lang)
    return StreamingResponse(run_cad(body, conn), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


CAD_CACHE_FILES = ("model.step", "model.stl", "model.glb", "model.py", "parts.json", "meta.json")


def cad_cache_dir(scenario_id: str, lang: str | None = "zh") -> Path | None:
    """cad_cache/<id>/ when every artefact of a pre-generated solid is present, else None (never a half-built directory).
    The English UI gets cad_cache_en/<id>/ (English part names, script and summary) when it is complete."""
    sid = re.sub(r"[^a-z0-9_-]", "", scenario_id.lower())
    roots = ([CAD_CACHE_EN_DIR] if normalize_lang(lang) == "en" else []) + [CAD_CACHE_DIR]
    for d in (root / sid for root in roots):
        if sid and all((d / n).is_file() for n in CAD_CACHE_FILES):
            return d
    return None


def cad_cached_ids() -> list[str]:
    if not CAD_CACHE_DIR.is_dir():
        return []
    return sorted(p.name for p in CAD_CACHE_DIR.iterdir() if p.is_dir() and cad_cache_dir(p.name) is not None)


@app.get("/api/cad/cache/{scenario_id}")
async def cached_cad(scenario_id: str, request: Request, lang: str = "zh"):
    """The pre-generated 轨 B result of a scenario, in the exact shape of the live SSE `done` event so the UI treats both alike.
    Provenance is fixed here (`source: pre_generated`, model from meta.json), never trusted from the stored file."""
    require_user(request)
    d = cad_cache_dir(scenario_id, lang)
    if d is None:
        raise HTTPException(status_code=404, detail="no cached CAD result")
    file_query = "?lang=en" if d.parent == CAD_CACHE_EN_DIR else ""
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    parts = json.loads((d / "parts.json").read_text(encoding="utf-8"))
    job_id = f"{CAD_CACHE_PREFIX}{d.name}"
    bb = meta["bbox_mm"]
    L = CAD_METRIC_LABELS[normalize_lang(lang)]
    metrics = [
        {"label": L["volume"][0], "value": f"{meta['volume_mm3'] / 1000:.2f}", "unit": "cm³", "note": L["volume"][1]},
        {"label": L["mass"][0], "value": f"{meta['mass_kg']:.3f}", "unit": "kg", "note": L["mass"][1].format(d=meta["density_g_cm3"])},
        {"label": L["bbox"][0], "value": f"{bb[0]:.1f} × {bb[1]:.1f} × {bb[2]:.1f}", "unit": "mm", "note": L["bbox"][1]},
        {"label": L["area"][0], "value": f"{meta['area_mm2'] / 1e6:.4f}", "unit": "m²", "note": L["area"][1]},
        {"label": L["topo"][0], "value": f"{meta['solids']} / {meta['faces']}", "unit": "", "note": L["topo"][1]},
    ] + meta.get("extra_metrics", [])
    return JSONResponse({
        "ok": True, "job_id": job_id, "attempts": 1, "summary": meta.get("summary", ""), "code": (d / "model.py").read_text(encoding="utf-8"),
        "metrics": metrics, "raw": {k: meta.get(k) for k in ("elapsed_s", "step_bytes", "stl_bytes", "glb_bytes", "solids", "faces")},
        "latency_s": meta.get("elapsed_s", 0), "model": meta.get("model", "reference-script"), "source": "pre_generated",
        "parts": parts, "created_at": meta.get("created_at"), "scenario_id": d.name,
        "files": {k: f"/api/cad/file/{job_id}/model.{k}{file_query}" for k in ("step", "stl", "py", "glb")},
    })


@app.get("/api/cad/file/{job_id}/{name}")
async def cad_file(job_id: str, name: str, request: Request, lang: str = "zh"):
    require_user(request)
    if name not in ("model.step", "model.stl", "model.py", "model.glb", "parts.json"):
        raise HTTPException(status_code=404, detail="not found")
    if job_id.startswith(CAD_CACHE_PREFIX):
        cached = cad_cache_dir(job_id[len(CAD_CACHE_PREFIX):], lang)
        if cached is None or cached.name != job_id[len(CAD_CACHE_PREFIX):]:
            raise HTTPException(status_code=404, detail="not found")
        path = cached / name
    elif re.fullmatch(r"[0-9a-f]{12}", job_id):
        path = CAD_DIR / job_id / name
    else:
        raise HTTPException(status_code=404, detail="not found")
    if not path.exists():
        raise HTTPException(status_code=404, detail="not found")
    media = {"model.step": "application/step", "model.stl": "model/stl", "model.py": "text/x-python; charset=utf-8",
             "model.glb": "model/gltf-binary", "parts.json": "application/json; charset=utf-8"}[name]
    return FileResponse(path, media_type=media, filename=f"thermal3d-{job_id}-{name}",
                        headers={"Cache-Control": "private, max-age=3600"})


# ------------------------------------------------------------- 轨 C: WebGL snapshot → gpt-image photoreal render
RENDER_STYLES = {
    # Style presets the UI offers; the user's free-text instruction is appended after the chosen preset.
    "studio": ("Studio product photograph on a seamless light-grey background, soft three-point lighting, gentle reflections on the floor, "
               "shallow depth of field, 50 mm lens look."),
    "exhibition": ("Trade-show display: the part on a dark matte plinth under focused spotlights with a subtle blue rim light, "
                   "dark background, premium industrial look."),
    "exploded": ("Technical exploded-view poster: keep the exploded arrangement, clean white background, crisp edges, "
                 "subtle drop shadows, catalogue style."),
    "section": ("Technical section illustration: cut faces rendered in a solid darker tint, coolant passages in translucent blue, "
                "clean white background, engineering-catalogue style."),
    "installed": ("The part installed in its real application context (vehicle underbody / data-centre rack as appropriate), "
                  "realistic surroundings slightly out of focus, natural lighting."),
}
RENDER_MATERIAL_HINT = {
    "zh": "材质按摘要中的材料还原（铝：拉丝/阳极氧化银灰；铜：抛光红铜；黄铜：金黄；不锈钢：磨砂银；工程塑料：黑色哑光）。",
    "en": "Materials follow the summary (aluminium: brushed / anodised silver-grey; copper: polished reddish; brass: golden; stainless: satin silver; engineering plastic: matte black).",
}


class RenderBody(BaseModel):
    scenario_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    summary: str = Field(default="", max_length=4000)                       # SUMMARY of the model on stage (materials, parts)
    image: str = Field(max_length=MAX_RENDER_INPUT_CHARS)                    # PNG data URL: the WebGL snapshot, or the previous render when refining
    base: str = Field(default="snapshot", pattern=r"^(snapshot|previous)$")  # what `image` is — recorded in the result for provenance
    style: str = Field(default="studio", pattern=r"^(studio|exhibition|exploded|section|installed)$")
    instruction: str = Field(default="", max_length=1500)                    # the user's own words for this turn ("white background, brushed finish")
    size: str = Field(default="1024x1024", pattern=r"^(1024x1024|1536x1024|1024x1536|1792x1024|2048x1152)$")
    quality: str = Field(default="medium", pattern=r"^(low|medium|high|xhigh|max)$")
    lang: str = Field(default="zh", max_length=16)

    @field_validator("image")
    @classmethod
    def _png_data_url(cls, v: str) -> str:
        if not v.startswith("data:image/png;base64,"):
            raise ValueError("image must be a PNG data URL")
        return v


def render_prompt(body: RenderBody) -> str:
    """One English instruction for the image model: keep the geometry of the input, change only presentation."""
    lang = normalize_lang(body.lang)
    parts = [
        "Turn the input image — a WebGL rendering of an industrial thermal-management part — into a photorealistic rendering.",
        "Keep the object's geometry, proportions, part arrangement and camera viewpoint exactly as in the input; do not add, remove or reshape parts.",
        RENDER_STYLES[body.style],
        RENDER_MATERIAL_HINT[lang],
        "Remove any grid, axis lines, numbered markers, labels or UI text from the picture; no text anywhere in the output.",
    ]
    if body.summary.strip():
        parts.append("What the part is (from the engineering summary): " + re.sub(r"\s+", " ", body.summary.strip())[:600])
    if body.instruction.strip():
        parts.append("Additional instruction from the user (highest priority): " + body.instruction.strip())
    return "\n".join(parts)[:3900]  # image models cap the prompt at 4000 characters


async def run_render(body: RenderBody, conn: ModelConnection | None = None) -> AsyncIterator[str]:
    """SSE: `start` → `heartbeat`* → `done` | `error`. The rendered PNG comes back inline (base64) — nothing is stored server-side."""
    conn = conn or host_connection()
    t0 = time.time()
    render_id = uuid4().hex[:12]
    en = normalize_lang(body.lang) == "en"
    yield sse("start", {"render_id": render_id, "model": AOAI_IMAGE_DEPLOYMENT, "source": "live", "key_source": conn.source, "endpoint_host": conn.host})
    client = None
    try:
        if not AOAI_IMAGE_DEPLOYMENT:
            raise RuntimeError("No image deployment configured on the server (AOAI_IMAGE_DEPLOYMENT)." if en else "服务器未配置图像模型部署（AOAI_IMAGE_DEPLOYMENT）。")
        png = base64.b64decode(body.image.split(",", 1)[1], validate=True)
        if len(png) < 100 or not png.startswith(b"\x89PNG"):
            raise ValueError("The snapshot is not a valid PNG." if en else "截图不是有效的 PNG。")
        prompt = render_prompt(body)
        client = await conn.client()
        kwargs: dict[str, Any] = {"model": AOAI_IMAGE_DEPLOYMENT, "image": ("snapshot.png", png, "image/png"), "prompt": prompt,
                                  "size": body.size, "quality": body.quality, "n": 1, "output_format": "png"}

        async def edit() -> Any:
            return await asyncio.wait_for(client.images.edit(**kwargs), 240)

        resp = None
        async for kind, item in with_heartbeat(_single(edit())):
            if kind == "heartbeat":
                yield sse("heartbeat", {"t": round(time.time() - t0, 1)})
            else:
                resp = item
        data = resp.data[0]
        if not data.b64_json:
            raise ValueError("The image model returned no image data." if en else "图像模型未返回图片数据。")
        usage = resp.usage.model_dump() if getattr(resp, "usage", None) else None
        latency = round(time.time() - t0, 1)
        stats["renders"] = stats.get("renders", 0) + 1
        log.info("render=%s done style=%s base=%s size=%s quality=%s latency=%.1fs key=%s host=%s usage=%s",
                 render_id, body.style, body.base, body.size, body.quality, latency, conn.source, conn.host,
                 (usage or {}).get("total_tokens"))
        yield sse("done", {"ok": True, "render_id": render_id, "image": "data:image/png;base64," + data.b64_json,
                           "prompt_used": prompt, "revised_prompt": getattr(data, "revised_prompt", None),
                           "style": body.style, "base": body.base, "instruction": body.instruction, "size": body.size, "quality": body.quality,
                           "model": AOAI_IMAGE_DEPLOYMENT, "usage": usage, "latency_s": latency, "source": "live",
                           "key_source": conn.source, "endpoint_host": conn.host,
                           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    except asyncio.CancelledError:
        log.info("render=%s cancelled by client after %.1fs", render_id, time.time() - t0)
        raise
    except Exception as e:  # noqa: BLE001 — surface every failure to the browser
        log.exception("render=%s failed (key=%s host=%s)", render_id, conn.source, conn.host)
        yield sse("error", {"message": f"{type(e).__name__}: {e}", "render_id": render_id, "source": "live"})
    finally:
        if client is not None:
            await client.close()


@app.post("/api/render")
async def render(body: RenderBody, request: Request):
    require_user(request)
    conn = connection_from_request(request, body.lang)
    return StreamingResponse(run_render(body, conn), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


RENDER_CACHE_FILES = ("render.png", "meta.json")
RENDER_CACHE_KEYS = ("render_id", "prompt_used", "revised_prompt", "style", "base", "instruction", "size", "quality", "model",
                     "usage", "latency_s", "created_at")


def render_cache_dir(scenario_id: str) -> Path | None:
    """render_cache/<id>/ when the render and its meta.json are both present, else None."""
    sid = re.sub(r"[^a-z0-9_-]", "", scenario_id.lower())
    d = RENDER_CACHE_DIR / sid
    return d if sid and all((d / n).is_file() for n in RENDER_CACHE_FILES) else None


def render_cached_ids() -> list[str]:
    if not RENDER_CACHE_DIR.is_dir():
        return []
    return sorted(p.name for p in RENDER_CACHE_DIR.iterdir() if p.is_dir() and render_cache_dir(p.name) is not None)


@app.get("/api/render/cache/{scenario_id}")
async def cached_render(scenario_id: str, request: Request):
    """The pre-generated 轨 C render of a scenario in the shape of the live `done` event; provenance fixed to pre_generated."""
    require_user(request)
    d = render_cache_dir(scenario_id)
    if d is None:
        raise HTTPException(status_code=404, detail="no cached render")
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    png = (d / "render.png").read_bytes()
    # 渲染图 vs CAD: STEP outline + edges in render pixels and the fit behind them (made offline by pregen_render_cad.py).
    overlay = None
    if (d / "cad_overlay.json").is_file() and (d / "cad_lines.png").is_file():
        overlay = json.loads((d / "cad_overlay.json").read_text(encoding="utf-8"))
        overlay["lines"] = "data:image/png;base64," + base64.b64encode((d / "cad_lines.png").read_bytes()).decode()
    # 工程渲染图: the STEP geometry rendered with the same camera, lines need no fit (made offline by pregen_engineering.py).
    engineering = None
    if all((d / n).is_file() for n in ("engineering.png", "engineering_lines.png", "engineering.json")):
        engineering = json.loads((d / "engineering.json").read_text(encoding="utf-8"))
        engineering["image"] = "data:image/png;base64," + base64.b64encode((d / "engineering.png").read_bytes()).decode()
        engineering["lines"] = "data:image/png;base64," + base64.b64encode((d / "engineering_lines.png").read_bytes()).decode()
    return JSONResponse({"ok": True, **{k: meta.get(k) for k in RENDER_CACHE_KEYS}, "source": "pre_generated", "scenario_id": d.name,
                         "image": "data:image/png;base64," + base64.b64encode(png).decode(), "cad_overlay": overlay,
                         "engineering": engineering})


# ------------------------------------------------------------- 轨 D: Concept Studio — natural language → concept image → 3D
CONCEPT_STYLE = ("Industrial-design concept rendering of a thermal-management component or system, clean studio lighting, "
                 "neutral light background, three-quarter view showing the overall form, realistic materials, no text, no labels, no people.")


class ConceptBody(BaseModel):
    prompt: str = Field(min_length=2, max_length=1500)                        # what to draw, in the user's words (zh or en)
    provider: str = Field(default="gpt-image", pattern=r"^(gpt-image|mai)$")
    web_grounding: bool = False                                                # MAI only: search Bing first, then draw (Web IQ)
    image: str | None = Field(default=None, max_length=MAX_RENDER_INPUT_CHARS)  # previous concept (PNG data URL) → edit instead of generate
    size: str = Field(default="1024x1024", pattern=r"^(1024x1024|1536x1024|1024x1536|1792x1024|2048x1152)$")
    quality: str = Field(default="medium", pattern=r"^(low|medium|high|xhigh|max)$")
    lang: str = Field(default="zh", max_length=16)

    @field_validator("image")
    @classmethod
    def _png_data_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("data:image/png;base64,"):
            raise ValueError("image must be a PNG data URL")
        return v


def concept_prompt(body: ConceptBody) -> str:
    if body.image:   # editing a previous concept: the user's words are the change request
        return ("Edit the input concept image as instructed; keep everything else (form, viewpoint, materials, lighting) unchanged. "
                f"Instruction: {body.prompt.strip()}. No text or labels in the output.")[:3900]
    return f"{CONCEPT_STYLE}\nSubject: {body.prompt.strip()}"[:3900]


def mai_enabled() -> bool:
    """MAI needs an endpoint; auth is MAI_API_KEY or, when absent, the host Entra token (same scope as Azure OpenAI)."""
    return bool(MAI_ENDPOINT)


MAI_MAX_PIXELS, MAI_MIN_EDGE = 1_048_576, 768   # documented MAI limits: each edge ≥ 768 px, width × height ≤ 1024²


def mai_dims(size: str) -> tuple[int, int]:
    """Map a UI size (gpt-image whitelist) onto MAI's pixel budget, keeping the aspect ratio and 16-px alignment."""
    w, h = (int(x) for x in size.split("x"))
    scale = min(1.0, (MAI_MAX_PIXELS / (w * h)) ** 0.5)
    w2, h2 = (max(MAI_MIN_EDGE, int(v * scale) // 16 * 16) for v in (w, h))
    while w2 * h2 > MAI_MAX_PIXELS:    # the ≥768 floor can push a wide ratio back over the cap: shrink the long edge
        if w2 >= h2:
            w2 -= 16
        else:
            h2 -= 16
    return w2, h2


async def mai_headers() -> dict[str, str]:
    return {"api-key": MAI_API_KEY} if MAI_API_KEY else {"Authorization": f"Bearer {await tokens.get()}"}


async def mai_generate(prompt: str, size: str, web_grounding: bool, image_png: bytes | None = None) -> tuple[str, dict[str, Any] | None, str | None]:
    """MAI-Image-2.6 text→image (`/mai/v1/images/generations`, JSON) or image edit (`/mai/v1/images/edits`, multipart).
    Shapes per the Foundry MAI image how-to; verified live 2026-09-11 (Bearer auth, web_grounding, edits, 1344×768)."""
    if not mai_enabled():
        raise RuntimeError("MAI_ENDPOINT not configured")
    headers = await mai_headers()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=240)) as hc:
        if image_png is not None:
            form = aiohttp.FormData()
            form.add_field("model", MAI_MODEL)
            form.add_field("prompt", prompt)
            form.add_field("web_grounding", "true" if web_grounding else "false")
            form.add_field("image", image_png, filename="concept.png", content_type="image/png")
            req = hc.post(f"{MAI_ENDPOINT}/mai/v1/images/edits", data=form, headers=headers)
        else:
            w, h = mai_dims(size)
            payload = {"model": MAI_MODEL, "prompt": prompt, "width": w, "height": h, "web_grounding": web_grounding}
            req = hc.post(f"{MAI_ENDPOINT}/mai/v1/images/generations", json=payload, headers=headers)
        async with req as r:
            text = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"MAI {r.status}: {text[:300]}")
            data = json.loads(text)
    item = (data.get("data") or [{}])[0]
    if not item.get("b64_json"):
        raise RuntimeError("MAI returned no image data")
    usage = data.get("usage")
    if isinstance(usage, dict):   # normalise MAI's field names onto the gpt-image shape the UI already understands
        usage = {**usage, "input_tokens": int(usage.get("num_input_text_tokens", 0) or 0) + int(usage.get("num_input_image_tokens", 0) or 0),
                 "output_tokens": int(usage.get("num_output_tokens", 0) or 0)}
        usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
    return item["b64_json"], usage, item.get("revised_prompt")


async def run_concept(body: ConceptBody, conn: ModelConnection | None = None) -> AsyncIterator[str]:
    """SSE: `start` → `heartbeat`* → `done` | `error`. Result = concept PNG (inline) ready to be attached to a GPT-6 3D request."""
    conn = conn or host_connection()
    t0 = time.time()
    concept_id = uuid4().hex[:12]
    en = normalize_lang(body.lang) == "en"
    model = MAI_MODEL if body.provider == "mai" else AOAI_IMAGE_DEPLOYMENT
    yield sse("start", {"concept_id": concept_id, "model": model, "provider": body.provider, "web_grounding": body.web_grounding and body.provider == "mai",
                        "source": "live", "key_source": conn.source if body.provider == "gpt-image" else "host", "endpoint_host": conn.host if body.provider == "gpt-image" else MAI_ENDPOINT.split("//", 1)[-1]})
    client = None
    try:
        prompt = concept_prompt(body)

        async def work() -> tuple[str, dict[str, Any] | None, str | None]:
            nonlocal client
            if body.provider == "mai":
                png = base64.b64decode(body.image.split(",", 1)[1], validate=True) if body.image else None
                return await mai_generate(prompt, body.size, body.web_grounding, png)
            if not AOAI_IMAGE_DEPLOYMENT:
                raise RuntimeError("No image deployment configured on the server (AOAI_IMAGE_DEPLOYMENT)." if en else "服务器未配置图像模型部署（AOAI_IMAGE_DEPLOYMENT）。")
            client = await conn.client()
            if body.image:
                png = base64.b64decode(body.image.split(",", 1)[1], validate=True)
                resp = await asyncio.wait_for(client.images.edit(model=AOAI_IMAGE_DEPLOYMENT, image=("concept.png", png, "image/png"), prompt=prompt,
                                                                 size=body.size, quality=body.quality, n=1, output_format="png"), 240)
            else:
                resp = await asyncio.wait_for(client.images.generate(model=AOAI_IMAGE_DEPLOYMENT, prompt=prompt, size=body.size, quality=body.quality,
                                                                     n=1, output_format="png"), 240)
            d = resp.data[0]
            return d.b64_json, (resp.usage.model_dump() if getattr(resp, "usage", None) else None), getattr(d, "revised_prompt", None)

        result = None
        async for kind, item in with_heartbeat(_single(work())):
            if kind == "heartbeat":
                yield sse("heartbeat", {"t": round(time.time() - t0, 1)})
            else:
                result = item
        b64, usage, revised = result
        latency = round(time.time() - t0, 1)
        stats["concepts"] = stats.get("concepts", 0) + 1
        log.info("concept=%s done provider=%s model=%s grounded=%s edit=%s size=%s latency=%.1fs", concept_id, body.provider, model,
                 body.web_grounding, bool(body.image), body.size, latency)
        yield sse("done", {"ok": True, "concept_id": concept_id, "image": "data:image/png;base64," + b64, "prompt_used": prompt,
                           "revised_prompt": revised, "provider": body.provider, "model": model, "web_grounding": body.web_grounding and body.provider == "mai",
                           "edit": bool(body.image), "instruction": body.prompt, "size": body.size, "quality": body.quality, "usage": usage,
                           "latency_s": latency, "source": "live", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("concept=%s failed provider=%s", concept_id, body.provider)
        yield sse("error", {"message": f"{type(e).__name__}: {e}", "concept_id": concept_id, "source": "live"})
    finally:
        if client is not None:
            await client.close()


@app.post("/api/concept")
async def concept(body: ConceptBody, request: Request):
    require_user(request)
    conn = connection_from_request(request, body.lang) if body.provider == "gpt-image" else host_connection()
    return StreamingResponse(run_concept(body, conn), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------------- 方案书 (.docx proposal)
class ProposalBody(ProposalPayload):
    narrative_by_model: bool = True        # let GPT-6 write the executive summary / rationale / risks / next steps
    reasoning_effort: str | None = Field(default=None, pattern=r"^(none|low|medium|high|xhigh)$")


NARRATIVE_PROMPT = {
    "zh": ("你是热管理与消费电子制造领域的资深方案工程师。根据下面的需求、模型摘要与工程量，用中文写四段方案书正文，"
           "只输出一个 JSON 对象，键为 executive_summary（方案要点，120–200 字）、design_rationale（设计说明：结构 / 材料 / 参数取舍，150–250 字）、"
           "risks（风险与待校核项，3–5 条，用「；」分隔或分行）、next_steps（下一步建议，3–5 条）。不要提及任何公司或品牌名称；"
           "数字只能引用下面给出的，不得编造；语气专业、面向研发与管理层。"),
    "en": ("You are a senior proposal engineer for thermal management and electronics manufacturing. From the requirement, model summary "
           "and metrics below, write four proposal sections in English and output ONE JSON object with keys executive_summary (80–140 words), "
           "design_rationale (structure / materials / parameter trade-offs, 100–180 words), risks (3–5 items to verify), next_steps (3–5 items). "
           "Never mention a company or brand; only quote numbers given below; professional register for engineers and management."),
}
NARRATIVE_KEYS = ("executive_summary", "design_rationale", "risks", "next_steps")


def narrative_context(body: ProposalPayload) -> str:
    metrics = "\n".join(f"- {m.label}: {m.value} {m.unit} {('(' + m.note + ')') if m.note else ''}".rstrip() for m in body.metrics)
    history = "\n".join(f"  {i + 1}. {h}" for i, h in enumerate(body.history))
    step = "\n".join(f"- {k}: {v}" for k, v in body.step.items())
    return (f"【需求 / Requirement】\n{body.requirement}\n" + (f"【迭代历史 / Earlier turns】\n{history}\n" if history else "")
            + f"【模型摘要 / Summary】\n{body.summary}\n【工程量 / Metrics】\n{metrics}\n"
            + (f"【STEP】\n{step}\n" if step else "") + (f"【建议 / Suggestions】\n" + "\n".join(f"- {s}" for s in body.suggestions) if body.suggestions else ""))


async def write_narrative(body: ProposalBody, conn: ModelConnection) -> tuple[dict[str, str], dict[str, Any] | None]:
    """One non-streaming GPT-6 call → the four narrative sections (lenient JSON parsing; missing keys are simply absent)."""
    lang = normalize_lang(body.lang)
    client = await conn.client()
    try:
        kwargs: dict[str, Any] = {"model": conn.deployment, "max_completion_tokens": 2500,
                                  "messages": [{"role": "system", "content": NARRATIVE_PROMPT[lang]}, {"role": "user", "content": narrative_context(body)}]}
        effort = effective_effort(body.reasoning_effort)
        if effort:
            kwargs["reasoning_effort"] = effort
        try:
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), 240)
        except BadRequestError as e:
            if not retry_effort(kwargs, e):
                raise
            resp = await asyncio.wait_for(client.chat.completions.create(**kwargs), 240)
    finally:
        await client.close()
    text = (resp.choices[0].message.content or "") if resp.choices else ""
    m = re.search(r"\{.*\}", text, re.S)
    data = _safe_json(m.group(0), {}) if m else {}
    narrative = {k: str(v).strip() for k, v in (data.items() if isinstance(data, dict) else []) if k in NARRATIVE_KEYS and str(v).strip()}
    usage = resp.usage.model_dump() if getattr(resp, "usage", None) else None
    return narrative, usage


@app.post("/api/proposal")
async def proposal(body: ProposalBody, request: Request):
    """Package the session into a .docx proposal. The narrative (optional) is written by GPT-6 on the caller's connection."""
    require_user(request)
    t0 = time.time()
    narrative_usage = None
    if body.narrative_by_model and not body.narrative:
        conn = connection_from_request(request, body.lang)
        try:
            body.narrative, narrative_usage = await write_narrative(body, conn)
        except Exception as e:  # noqa: BLE001 — the document is still produced from the raw data
            log.warning("proposal narrative failed: %s: %s", type(e).__name__, e)
            body.narrative = {}
    if not body.generated_at:
        body.generated_at = datetime.now().astimezone().isoformat(timespec="minutes")
    data = await asyncio.to_thread(build_proposal_docx, body)
    stats["proposals"] = stats.get("proposals", 0) + 1
    log.info("proposal built lang=%s bytes=%d narrative=%s latency=%.1fs", body.lang, len(data), bool(body.narrative), time.time() - t0)
    headers = {"Content-Disposition": f'attachment; filename="{proposal_filename(body)}"', "Cache-Control": "no-store",
               "X-Proposal-Narrative": "model" if body.narrative else "none"}
    if narrative_usage:
        headers["X-Proposal-Tokens"] = str(int(narrative_usage.get("total_tokens") or 0))
    return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers=headers)


# ------------------------------------------------------------------------- static
@app.get("/healthz")
async def healthz():
    return {"ok": True, "deployment": AOAI_DEPLOYMENT, "uptime_s": int(time.time() - stats["started"])}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
