# Copyright (c) Microsoft. All rights reserved.

"""Browser demo for the repository-owned Long-Running Agent Resilience Agents.

One small FastAPI service drives the three Agents in this repository through four
interruptions and streams every durable checkpoint to the page as it lands:

* ``/api/run``              - the checkpoint Agent (``hosted-agent/``): safe baseline,
                              hard process loss, or caller disconnect and reattach
* ``/api/steering``         - the steering Agent (``hosted-agent-steering/``): process
                              loss, recovery, then a change of target language
* ``/api/approval``         - the approval Agent (``hosted-agent-approval/``): sample,
                              instance loss while the review is pending, replacement
* ``/api/approval/decide``  - the human decision, landing on whichever instance is alive
* ``/api/validator-check``  - proves the checkpoint acceptance rejects damaged runs

The page is a demonstration surface. The acceptance rules are the same fail-closed
rules the command-line runners apply; the JSON reports and logs under ``evidence/``
remain the evidence, not the screen.

Configuration (environment):
    FOUNDRY_PROJECT_ENDPOINT    Foundry project endpoint (required)
    FOUNDRY_API_VERSION         API version query value (default ``v1``)
    LRA_FAULT_AGENT_NAME        checkpoint Agent name (default ``lra-evidence-agent``)
    LRA_STEERING_AGENT_NAME     steering Agent name (default ``lre-steering-agent``)
    LRA_APPROVAL_AGENT_NAME     approval Agent name (default ``lre-approval-gate``)
    PORTAL_USERNAME / PORTAL_PASSWORD / PORTAL_SESSION_SECRET
                                set all three to require a sign-in; leave unset for a
                                local, loopback-only demo
    PORTAL_COOKIE_SECURE        ``true`` when served over HTTPS

Authentication to Foundry uses the Azure CLI login of the operator, or a service
principal when AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET are set.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from azure.identity import AzureCliCredential, ClientSecretCredential
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AI_SCOPE = "https://ai.azure.com/.default"
logger = logging.getLogger("uvicorn.error")


class Settings:
    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
    api_version = os.getenv("FOUNDRY_API_VERSION", "v1")
    fault_agent_name = os.getenv("LRA_FAULT_AGENT_NAME", "lra-evidence-agent")
    steering_agent_name = os.getenv("LRA_STEERING_AGENT_NAME", "lre-steering-agent")
    approval_agent_name = os.getenv("LRA_APPROVAL_AGENT_NAME", "lre-approval-gate")
    portal_username = os.getenv("PORTAL_USERNAME", "")
    portal_password = os.getenv("PORTAL_PASSWORD", "")
    portal_session_secret = os.getenv("PORTAL_SESSION_SECRET", "")
    cookie_secure = os.getenv("PORTAL_COOKIE_SECURE", "false").lower() == "true"
    sp_client_id = os.getenv("AZURE_CLIENT_ID", "")
    sp_tenant_id = os.getenv("AZURE_TENANT_ID", "")

    @classmethod
    def auth_required(cls) -> bool:
        return bool(cls.portal_username and cls.portal_password and cls.portal_session_secret)


settings = Settings()


def _build_credential() -> tuple[Any, str]:
    client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
    if settings.sp_client_id and settings.sp_tenant_id and client_secret:
        return ClientSecretCredential(settings.sp_tenant_id, settings.sp_client_id, client_secret), "service_principal"
    return AzureCliCredential(), "azure_cli_user"


class TokenCache:
    def __init__(self) -> None:
        self._credential, self.mode = _build_credential()
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, scope: str, *, force: bool = False) -> str:
        async with self._lock:
            cached = self._cache.get(scope)
            if not force and cached and cached[1] - time.time() > 300:
                return cached[0]
            token = await asyncio.to_thread(self._credential.get_token, scope)
            self._cache[scope] = (token.token, float(token.expires_on))
            return token.token

    def invalidate(self, scope: str) -> None:
        self._cache.pop(scope, None)


token_cache = TokenCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=20.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    yield
    await app.state.http.aclose()


app = FastAPI(
    title="LRA resilience demo",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/assets", StaticFiles(directory=BASE_DIR.parent / "images"), name="assets")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith(("/api/", "/auth/")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------------------------------------------------------------------------
# Optional sign-in (only when PORTAL_USERNAME / PORTAL_PASSWORD / PORTAL_SESSION_SECRET are set)
# ---------------------------------------------------------------------------
def _session_token(username: str, expires: int) -> str:
    encoded = base64.urlsafe_b64encode(f"{username}|{expires}".encode()).decode().rstrip("=")
    signature = hmac.new(settings.portal_session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _verify_session(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    encoded, signature = token.rsplit(".", 1)
    expected = hmac.new(settings.portal_session_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        username, expires = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return username == settings.portal_username and int(expires) > int(time.time())
    except (ValueError, UnicodeDecodeError):
        return False


def require_auth(portal_session: str | None = Cookie(default=None)) -> str:
    if not settings.auth_required():
        return "local"
    if not _verify_session(portal_session):
        raise HTTPException(status_code=401, detail="Authentication required")
    return settings.portal_username


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


@app.get("/api/auth/status")
async def auth_status(portal_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    required = settings.auth_required()
    return {
        "auth_required": required,
        "authenticated": (not required) or _verify_session(portal_session),
        "credential_mode": token_cache.mode,
    }


@app.post("/auth/login")
async def login(body: LoginRequest, response: Response) -> dict[str, bool]:
    if not settings.auth_required():
        return {"authenticated": True}
    ok = hmac.compare_digest(body.username, settings.portal_username) and hmac.compare_digest(
        body.password, settings.portal_password
    )
    if not ok:
        await asyncio.sleep(0.5)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    expires = int(time.time()) + 8 * 3600
    response.set_cookie(
        "portal_session",
        _session_token(body.username, expires),
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=8 * 3600,
        path="/",
    )
    return {"authenticated": True}


@app.post("/auth/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("portal_session", path="/")
    return {"authenticated": False}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
TARGET = Literal["zh-Hans", "zh-Hant", "ja", "ko", "fr", "de", "es"]
TARGET_NAMES = {
    "zh-Hans": "Simplified Chinese",
    "zh-Hant": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}


class ResilienceRequest(BaseModel):
    inject: bool = True
    # crash kills the Agent process; detach only drops the caller's connection.
    mode: Literal["crash", "detach"] = "crash"
    crash_after_stage: int = Field(default=3, ge=0, le=28)
    stage_delay_ms: int = Field(default=300, ge=100, le=2000)
    detach_after_sections: int = Field(default=3, ge=1, le=25)
    detach_seconds: float = Field(default=8.0, ge=1.0, le=60.0)


class SteeringDemoRequest(BaseModel):
    original_target: TARGET = "zh-Hans"
    replacement_target: TARGET = "zh-Hant"
    # Sections the recovered turn must commit before the page changes direction.
    steer_after_sections: int = Field(default=4, ge=2, le=10)
    crash_after_stage: int = Field(default=9, ge=2, le=20)
    stage_delay_ms: int = Field(default=300, ge=100, le=2000)


class ApprovalDemoRequest(BaseModel):
    target: TARGET = "zh-Hans"
    sample_size: int = Field(default=10, ge=3, le=20)
    stage_delay_ms: int = Field(default=300, ge=100, le=2000)
    # When false the run stops at the review gate and waits for /api/approval/decide.
    auto_approve: bool = False
    approver: str = Field(default="demo operator", min_length=1, max_length=120)


class ApprovalDecisionRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    decision: Literal["approve", "reject"] = "approve"
    approver: str = Field(default="demo operator", min_length=1, max_length=120)
    # Evidence from the first phase so the verdict can prove same task + new instance.
    task_id_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    process_a_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sample_hashes: list[str] = Field(default_factory=list, max_length=30)


# ---------------------------------------------------------------------------
# Foundry plumbing
# ---------------------------------------------------------------------------
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
LRA_TERMINAL_EVENTS = frozenset(
    {"response.completed", "response.failed", "response.incomplete", "response.cancelled"}
)
LRA_STREAM_TIMEOUT = httpx.Timeout(180.0, connect=20.0)
# A reconnect against compute that is still starting parks for about a minute before the
# platform answers, so probe with a short read timeout and retry instead of waiting it out.
LRA_RECONNECT_TIMEOUT = httpx.Timeout(10.0, connect=10.0)
LRA_RECONNECT_INTERVAL_SECONDS = 1.0
LRA_DEADLINE_SECONDS = 300.0
# After a process loss the replacement answers HTTP before its startup recovery scan has
# re-entered the durable task; poll the durable status at this pace until the stream exists.
LRE_REENTRY_POLL_SECONDS = 3.0
NOT_READY_STATUSES = {404, 424, 500, 502, 503, 504}


class _LraSessionPending(RuntimeError):
    """Replacement compute has not accepted the reconnect yet."""


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _sha(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _agent_url(agent: str, *parts: str, **query: str) -> str:
    if not settings.project_endpoint:
        raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT is not configured")
    path = "/".join(part.strip("/") for part in parts if part)
    url = f"{settings.project_endpoint}/agents/{agent}"
    if path:
        url = f"{url}/{path}"
    params = {"api-version": settings.api_version, **query}
    return f"{url}?{urlencode(params)}"


def _responses_url(agent: str, *parts: str, **query: str) -> str:
    return _agent_url(agent, "endpoint/protocols/openai/responses", *parts, **query)


def _approval_url(agent: str, session_id: str, invocation_id: str | None = None) -> str:
    parts = ("endpoint/protocols/invocations",) + ((invocation_id,) if invocation_id else ())
    return _agent_url(agent, *parts, agent_session_id=session_id)


async def _request(
    request: Request, method: str, url: str, *, json_body: dict[str, Any] | None = None
) -> httpx.Response:
    client: httpx.AsyncClient = request.app.state.http
    for attempt in range(2):
        token = await token_cache.get(AI_SCOPE, force=attempt == 1)
        response = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            json=json_body,
        )
        if response.status_code != 401 or attempt == 1:
            return response
        token_cache.invalidate(AI_SCOPE)
    raise RuntimeError("unreachable")


def _raise_foundry(response: httpx.Response, operation: str) -> None:
    if response.status_code < 400:
        return
    try:
        detail = response.json()
    except ValueError:
        detail = response.text[:500]
    raise HTTPException(
        status_code=502,
        detail={"operation": operation, "upstream_status": response.status_code, "error": detail},
    )


async def _get_agent(request: Request, agent_name: str) -> dict[str, Any]:
    response = await _request(request, "GET", _agent_url(agent_name))
    _raise_foundry(response, f"get-agent:{agent_name}")
    return response.json()


def _runtime_contract(agent: dict[str, Any], label: str) -> dict[str, Any]:
    latest = (agent.get("versions") or {}).get("latest") or agent
    definition = latest.get("definition") or {}
    code = definition.get("code_configuration") or {}
    return {
        "label": label,
        "name": agent.get("name") or agent.get("id"),
        "version": str(latest.get("version") or agent.get("version") or ""),
        "status": latest.get("status") or agent.get("status"),
        "kind": definition.get("kind"),
        "runtime": code.get("runtime"),
        "content_hash": code.get("content_hash"),
        "protocols": definition.get("protocol_versions") or [],
    }


async def _response_json(request: Request, url: str) -> dict[str, Any]:
    response = await _request(request, "GET", url)
    _raise_foundry(response, "get-resilient-response")
    payload = response.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="response payload is not an object")
    return payload


async def _lra_stream_events(
    request: Request,
    method: str,
    url: str,
    body: dict[str, Any] | None,
    timeout: httpx.Timeout = LRA_STREAM_TIMEOUT,
) -> AsyncIterator[dict[str, Any]]:
    client: httpx.AsyncClient = request.app.state.http
    token = await token_cache.get(AI_SCOPE)
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
    async with client.stream(method, url, json=body, headers=headers, timeout=timeout) as response:
        if "text/event-stream" not in response.headers.get("content-type", ""):
            payload = (await response.aread()).decode("utf-8", errors="replace")
            if "session_not_ready" in payload:
                raise _LraSessionPending(payload[:200])
            raise HTTPException(
                status_code=502,
                detail={
                    "operation": "resilience-stream",
                    "upstream_status": response.status_code,
                    "error": payload[:400],
                },
            )
        buffer = ""
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                for line in block.splitlines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        yield json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue


def _record_from_item(item: Any, kind: str) -> dict[str, Any] | None:
    """One JSON record the Agent serialised into an output item, if it is of ``kind``."""
    if not isinstance(item, dict):
        return None
    for part in item.get("content") or []:
        if not isinstance(part, dict) or part.get("type") != "output_text":
            continue
        try:
            candidate = json.loads(part.get("text") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(candidate, dict) and candidate.get("kind") == kind:
            return candidate
    return None


def _lra_record_from_item(item: Any) -> dict[str, Any] | None:
    return _record_from_item(item, "lra_stage")


def _steering_entry_from_item(item: Any) -> dict[str, Any] | None:
    return _record_from_item(item, "lre_steering_entry")


# ---------------------------------------------------------------------------
# Scenario 1-3: the checkpoint Agent (baseline, hard process loss, caller disconnect)
# ---------------------------------------------------------------------------
def _lra_processes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group checkpoints by the process that committed them, in first-seen order."""
    groups: dict[str, dict[str, Any]] = {}
    for record in records:
        process_id = record.get("process_instance_id")
        if not isinstance(process_id, str) or not process_id:
            continue
        bucket = groups.get(process_id)
        if bucket is None:
            bucket = {"process_sha256": _sha(process_id), "entry_mode": record.get("entry_mode"), "stages": []}
            groups[process_id] = bucket
        bucket["stages"].append(
            {
                "index": record.get("stage_index"),
                "name": record.get("stage_name"),
                "source": record.get("source_text") or None,
                "text": record.get("translated_text") or None,
            }
        )
    return list(groups.values())


def _lra_acceptance(
    processes: list[dict[str, Any]],
    stage_count: int,
    status: str | None,
    mode: str,
    inject: bool,
) -> dict[str, Any]:
    """Fail closed unless the checkpoints form one complete, ordered, non-duplicated run."""
    indexes = [stage["index"] for item in processes for stage in item["stages"]]
    entry_modes = sorted({item["entry_mode"] for item in processes if item["entry_mode"]})
    contiguous = indexes == list(range(len(indexes)))
    complete = bool(stage_count) and len(indexes) == stage_count
    pairs_present = all(
        (stage.get("source") or "").strip() and (stage.get("text") or "").strip()
        for item in processes
        for stage in item["stages"]
    )
    handoff_expected = mode == "crash" and inject
    active_processes = [item for item in processes if item.get("stages")]
    handed_off = len(active_processes) > 1 and any(
        item.get("entry_mode") == "recovered" and item.get("stages")
        for item in active_processes
    )
    sound = contiguous and complete and pairs_present and status == "completed"
    verdict = "PASS" if (sound and (handed_off or not handoff_expected)) else "FAIL"
    return {
        "checkpoints_ordered_once": contiguous,
        "checkpoints_complete": complete,
        "source_translation_pairs_present": pairs_present,
        "terminal_completed": status == "completed",
        "process_count": len(active_processes),
        "entry_modes": entry_modes,
        "handed_off_to_new_process": handed_off,
        "verdict": verdict,
        "passed": verdict == "PASS",
    }


async def _resilience_stream(
    request: Request,
    *,
    mode: str,
    inject: bool,
    crash_after_stage: int,
    stage_delay_ms: int,
    detach_after_sections: int,
    detach_seconds: float,
) -> AsyncIterator[str]:
    agent = settings.fault_agent_name
    inject_fault = mode == "crash" and inject
    work_id = f"demo-{secrets.token_hex(6)}"
    work_input = {
        "work_id": work_id,
        "payload": "browser resilience demo",
        "crash_after_stage": crash_after_stage if inject_fault else None,
        "stage_delay_ms": stage_delay_ms,
        "workload": "translator_batch",
    }
    started = time.monotonic()
    state: dict[str, Any] = {
        "response_id": None,
        "response_sha": None,
        "terminal": None,
        "seen": {},
        "order": [],
        "recovered": False,
    }

    async def pump(method: str, url: str, body: dict[str, Any] | None, timeout: httpx.Timeout = LRA_STREAM_TIMEOUT):
        """Forward one stream connection, skipping checkpoints a previous connection replayed."""
        async for event in _lra_stream_events(request, method, url, body, timeout):
            event_type = event.get("type")
            if event_type == "response.created" and state["response_id"] is None:
                response_id = (event.get("response") or {}).get("id")
                if not isinstance(response_id, str) or not response_id:
                    continue
                state["response_id"] = response_id
                state["response_sha"] = _sha(response_id)
                yield _sse(
                    {
                        "kind": "created",
                        "agent": agent,
                        "mode": mode,
                        "work_id": work_id,
                        "inject": inject_fault,
                        "crash_after_stage": crash_after_stage if inject_fault else None,
                        "response_id_sha256": state["response_sha"],
                    }
                )
            elif event_type == "response.output_item.done":
                index = event.get("output_index")
                record = _lra_record_from_item(event.get("item"))
                if record is None or not isinstance(index, int) or index in state["seen"]:
                    continue
                state["seen"][index] = record
                process_sha = _sha(record.get("process_instance_id"))
                if process_sha not in state["order"]:
                    state["order"].append(process_sha)
                entry_mode = record.get("entry_mode")
                if entry_mode == "recovered" and not state["recovered"]:
                    state["recovered"] = True
                    yield _sse(
                        {"kind": "recovered", "resume_from": record.get("stage_name"), "process_count": len(state["order"])}
                    )
                yield _sse(
                    {
                        "kind": "checkpoint",
                        "index": index,
                        "name": record.get("stage_name"),
                        "entry_mode": entry_mode,
                        "process_sha256": process_sha,
                        "process_ordinal": state["order"].index(process_sha),
                        "source": record.get("source_text"),
                        "text": record.get("translated_text"),
                        "stage_count": record.get("stage_count"),
                    }
                )
            elif event_type in LRA_TERMINAL_EVENTS:
                state["terminal"] = event.get("response") or {}

    try:
        async for frame in pump(
            "POST",
            _responses_url(agent),
            {
                "model": agent,
                "input": json.dumps(work_input, sort_keys=True),
                "store": True,
                "background": True,
                "stream": True,
            },
        ):
            yield frame
            # detach mode ends the connection on purpose; the Agent keeps translating.
            if mode == "detach" and len(state["seen"]) >= detach_after_sections:
                break

        if state["response_id"] is None:
            yield _sse({"kind": "error", "message": "agent did not return a response id"})
            return

        sections_at_detach = len(state["seen"])
        if mode == "detach" and state["terminal"] is None:
            yield _sse({"kind": "detached", "sections_before_detach": sections_at_detach, "seconds": detach_seconds})
            await asyncio.sleep(detach_seconds)

        resume_url = _responses_url(agent, state["response_id"], stream="true")
        deadline = time.monotonic() + LRA_DEADLINE_SECONDS
        announced_gap = False
        reattached = False
        while state["terminal"] is None and time.monotonic() < deadline:
            if not announced_gap:
                announced_gap = True
                if mode != "detach":
                    yield _sse({"kind": "fault_window", "detail": "the stream ended before a terminal event"})
            try:
                async for frame in pump("GET", resume_url, None, LRA_RECONNECT_TIMEOUT):
                    if not reattached:
                        reattached = True
                        if mode == "detach":
                            yield _sse({"kind": "reattached", "sections_before_detach": sections_at_detach})
                    yield frame
            except _LraSessionPending:
                yield _sse({"kind": "waiting", "detail": "replacement compute is still starting"})
                await asyncio.sleep(LRA_RECONNECT_INTERVAL_SECONDS)
            except httpx.HTTPError as exc:
                yield _sse({"kind": "waiting", "detail": type(exc).__name__})
                await asyncio.sleep(LRA_RECONNECT_INTERVAL_SECONDS)
            except HTTPException:
                # The replacement answers HTTP before its recovery scan re-entered the task,
                # so no live stream exists yet; read the durable status instead of failing.
                snapshot = await _response_json(request, _responses_url(agent, state["response_id"]))
                status = str(snapshot.get("status") or "")
                if status in {"queued", "in_progress"}:
                    yield _sse({"kind": "waiting", "detail": "replacement process is up; the task is waiting to be re-entered"})
                    await asyncio.sleep(LRE_REENTRY_POLL_SECONDS)
                    continue
                state["terminal"] = snapshot

        if state["terminal"] is None:
            yield _sse(
                {"kind": "error", "message": f"response did not reach a terminal state within {LRA_DEADLINE_SECONDS:.0f}s"}
            )
            return

        indexes = sorted(state["seen"])
        records = [state["seen"][index] for index in indexes]
        processes = _lra_processes(records)
        entry_modes = sorted({item["entry_mode"] for item in processes if item["entry_mode"]})
        status = (state["terminal"] or {}).get("status")
        stage_count = records[-1].get("stage_count") if records else 0
        acceptance = _lra_acceptance(processes, stage_count, status, mode, inject)
        yield _sse(
            {
                "kind": "done",
                "result": {
                    "status": status,
                    "agent": agent,
                    "mode": mode,
                    "work_id": work_id,
                    "response_id_sha256": state["response_sha"],
                    "processes": processes,
                    "process_count": len(processes),
                    "entry_modes": entry_modes,
                    "stage_count": stage_count,
                    "sections_before_detach": sections_at_detach if mode == "detach" else None,
                    "acceptance": acceptance,
                    "checkpoints_ordered_once": acceptance["checkpoints_ordered_once"],
                    "recovery_proven": acceptance["handed_off_to_new_process"] and status == "completed",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                },
            }
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail, ensure_ascii=False)
        yield _sse({"kind": "error", "message": detail[:400]})
    except httpx.HTTPError as exc:
        yield _sse({"kind": "error", "message": f"{type(exc).__name__}: {exc}"[:400]})


# ---------------------------------------------------------------------------
# Scenario 4: the steering Agent (process loss, recovery, then a change of target)
# ---------------------------------------------------------------------------
def _steering_checkpoint_event(lane: str, record: dict[str, Any], output_index: int) -> dict[str, Any]:
    return {
        "kind": "checkpoint",
        "lane": lane,
        "output_index": output_index,
        "index": record.get("stage_index"),
        "name": record.get("stage_name"),
        "entry_mode": record.get("entry_mode"),
        "target": record.get("target"),
        "process_sha256": _sha(record.get("process_instance_id")),
        "source": record.get("source_text"),
        "text": record.get("translated_text"),
        "stage_count": record.get("stage_count"),
    }


async def _steering_stream(request: Request, body: SteeringDemoRequest) -> AsyncIterator[str]:
    """Crash the translation mid-way, let replacement compute resume it from the last
    checkpoint, then steer the same conversation to a new target language."""
    agent = settings.steering_agent_name
    started = time.monotonic()
    first_id = ""
    first_process = ""
    recovered_process = ""
    second_id = ""
    steered_process = ""
    first_terminal: dict[str, Any] | None = None
    second_terminal: dict[str, Any] | None = None
    # Reconnects replay the persisted prefix of a response, so items are deduplicated
    # by output_index exactly like the checkpoint demo does.
    a_seen: dict[int, dict[str, Any]] = {}
    b_seen: dict[int, dict[str, Any]] = {}

    def request_payload(target: str, *, inject: bool) -> dict[str, Any]:
        return {
            "model": agent,
            "input": json.dumps(
                {
                    "target": target,
                    "inject_process_loss": inject,
                    "crash_after_stage": body.crash_after_stage,
                    "stage_delay_ms": body.stage_delay_ms,
                },
                sort_keys=True,
            ),
            "store": True,
            "background": True,
            "stream": True,
        }

    def fresh_records() -> list[dict[str, Any]]:
        return [a_seen[i] for i in sorted(a_seen) if a_seen[i].get("entry_mode") == "fresh"]

    def recovered_records() -> list[dict[str, Any]]:
        return [a_seen[i] for i in sorted(a_seen) if a_seen[i].get("entry_mode") == "recovered"]

    def stage_count() -> int:
        counts = {int(r.get("stage_count") or 0) for r in list(a_seen.values()) + list(b_seen.values())}
        counts.discard(0)
        return max(counts) if len(counts) == 1 else 0

    try:
        contract = _runtime_contract(await _get_agent(request, agent), "steering")
        yield _sse(
            {
                "kind": "scenario_started",
                "scenario": "steering",
                "agent": agent,
                "version": contract.get("version"),
                "original_target": body.original_target,
                "replacement_target": body.replacement_target,
            }
        )

        # Objective A: translate into the original target with fault injection; the
        # fresh process exits right after committing checkpoint crash_after_stage.
        async for event in _lra_stream_events(
            request, "POST", _responses_url(agent), request_payload(body.original_target, inject=True)
        ):
            event_type = event.get("type")
            if event_type == "response.created":
                first_id = str((event.get("response") or {}).get("id") or "")
                if first_id:
                    yield _sse(
                        {
                            "kind": "objective_started",
                            "lane": "original",
                            "target": body.original_target,
                            "target_name": TARGET_NAMES[body.original_target],
                            "response_id_sha256": _sha(first_id),
                        }
                    )
            elif event_type == "response.output_item.done":
                index = event.get("output_index")
                entry = _steering_entry_from_item(event.get("item"))
                if entry and entry.get("entry_mode") == "fresh":
                    first_process = str(entry.get("process_sha256") or "")
                    yield _sse({**entry, "kind": "entry", "lane": "original"})
                    continue
                record = _lra_record_from_item(event.get("item"))
                if record is not None and isinstance(index, int) and index not in a_seen:
                    a_seen[index] = record
                    yield _sse(_steering_checkpoint_event("original", record, index))
            elif event_type in LRA_TERMINAL_EVENTS:
                raise RuntimeError("objective A completed before the injected process loss")

        committed_before_loss = fresh_records()
        if not first_id or not first_process or not committed_before_loss:
            raise RuntimeError("objective A did not expose response, process and checkpoint evidence")
        yield _sse(
            {
                "kind": "process_lost",
                "lane": "original",
                "process_sha256": first_process,
                "committed_sections": len(committed_before_loss),
                "detail": f"the agent process exited after committing section {committed_before_loss[-1]['stage_index'] + 1}",
            }
        )

        # Reattach to A until replacement compute re-enters it as a recovered turn and
        # commits steer_after_sections more checkpoints.
        deadline = time.monotonic() + LRA_DEADLINE_SECONDS
        while (
            not (recovered_process and len(recovered_records()) >= body.steer_after_sections)
            and first_terminal is None
            and time.monotonic() < deadline
        ):
            try:
                async for event in _lra_stream_events(
                    request, "GET", _responses_url(agent, first_id, stream="true"), None, LRA_RECONNECT_TIMEOUT
                ):
                    event_type = event.get("type")
                    if event_type == "response.output_item.done":
                        index = event.get("output_index")
                        entry = _steering_entry_from_item(event.get("item"))
                        if entry and entry.get("entry_mode") == "recovered":
                            process = str(entry.get("process_sha256") or "")
                            if process and not recovered_process:
                                recovered_process = process
                                yield _sse(
                                    {**entry, "kind": "recovered", "lane": "original", "committed_sections": len(committed_before_loss)}
                                )
                            continue
                        record = _lra_record_from_item(event.get("item"))
                        if record is None or not isinstance(index, int) or index in a_seen:
                            continue
                        a_seen[index] = record
                        yield _sse(_steering_checkpoint_event("original", record, index))
                        if record.get("entry_mode") == "recovered" and len(recovered_records()) >= body.steer_after_sections:
                            break
                    elif event_type in LRA_TERMINAL_EVENTS:
                        first_terminal = event.get("response") or {}
                        break
            except (_LraSessionPending, httpx.HTTPError):
                yield _sse({"kind": "waiting", "detail": "replacement compute is starting"})
                await asyncio.sleep(LRA_RECONNECT_INTERVAL_SECONDS)
            except HTTPException:
                # The replacement process answers HTTP before its startup recovery scan has
                # re-entered the durable task, so no live stream exists yet and the SDK
                # answers 400. Read the durable status instead of failing.
                snapshot = await _response_json(request, _responses_url(agent, first_id))
                status = str(snapshot.get("status") or "")
                if status in {"queued", "in_progress"}:
                    yield _sse(
                        {
                            "kind": "waiting",
                            "detail": f"replacement process is up; objective A is durable ({status}) and waiting to be re-entered",
                        }
                    )
                    await asyncio.sleep(LRE_REENTRY_POLL_SECONDS)
                    continue
                raise RuntimeError(f"objective A ended as {status or 'unknown'} before recovery")

        resumed = recovered_records()
        if not recovered_process or not resumed:
            raise RuntimeError("replacement compute never re-entered objective A")
        if first_terminal is not None:
            raise RuntimeError("objective A completed on replacement compute before steering was issued")
        resume_at = int(resumed[0]["stage_index"])
        last_before = int(committed_before_loss[-1]["stage_index"])
        if resume_at != last_before + 1:
            raise RuntimeError(
                f"recovery resumed at section {resume_at + 1} after {last_before + 1}; the checkpoint continuity is broken"
            )

        # Steer: post B on the same conversation while the recovered A is still translating.
        yield _sse(
            {
                "kind": "steer_issued",
                "from_target": body.original_target,
                "to_target": body.replacement_target,
                "from": TARGET_NAMES[body.original_target],
                "to": TARGET_NAMES[body.replacement_target],
                "original_sections": len(a_seen),
            }
        )
        second_payload = request_payload(body.replacement_target, inject=False)
        second_payload["previous_response_id"] = first_id
        async for event in _lra_stream_events(
            request, "POST", _responses_url(agent), second_payload, httpx.Timeout(LRA_DEADLINE_SECONDS, connect=20.0)
        ):
            event_type = event.get("type")
            if event_type == "response.created":
                second_id = str((event.get("response") or {}).get("id") or "")
                if second_id:
                    yield _sse(
                        {
                            "kind": "objective_started",
                            "lane": "replacement",
                            "target": body.replacement_target,
                            "target_name": TARGET_NAMES[body.replacement_target],
                            "response_id_sha256": _sha(second_id),
                        }
                    )
            elif event_type == "response.output_item.done":
                index = event.get("output_index")
                entry = _steering_entry_from_item(event.get("item"))
                if entry and entry.get("entry_mode") == "steered":
                    steered_process = str(entry.get("process_sha256") or "")
                    yield _sse({**entry, "kind": "entry", "lane": "replacement"})
                    continue
                record = _lra_record_from_item(event.get("item"))
                if record is not None and isinstance(index, int) and index not in b_seen:
                    b_seen[index] = record
                    yield _sse(_steering_checkpoint_event("replacement", record, index))
            elif event_type in LRA_TERMINAL_EVENTS:
                second_terminal = event.get("response") or {}

        if not second_id or not steered_process:
            raise RuntimeError("objective B did not enter as a steered turn")
        if second_terminal is None:
            raise RuntimeError("objective B did not reach a terminal state")
        first = await _response_json(request, _responses_url(agent, first_id))
        total = stage_count()
        b_records = [b_seen[i] for i in sorted(b_seen)]
        b_indexes = [record.get("stage_index") for record in b_records]
        passed = all(
            (
                total > 0,
                first.get("status") == "completed",
                second_terminal.get("status") == "completed",
                recovered_process != first_process,
                steered_process == recovered_process,
                b_indexes == list(range(total)),
                all(record.get("target") == body.replacement_target for record in b_records),
                all((record.get("translated_text") or "").strip() for record in b_records),
            )
        )
        if not passed:
            raise RuntimeError("steering acceptance failed: fresh/recovered/steered evidence is incomplete")
        a_records = [a_seen[i] for i in sorted(a_seen)]
        yield _sse(
            {
                "kind": "done",
                "result": {
                    "verdict": "PASS",
                    "agent": agent,
                    "agent_version": contract.get("version"),
                    "original_target": body.original_target,
                    "replacement_target": body.replacement_target,
                    "original_status": first.get("status"),
                    "replacement_status": second_terminal.get("status"),
                    "original_process_sha256": first_process,
                    "recovered_process_sha256": recovered_process,
                    "steered_process_sha256": steered_process,
                    "process_replaced": recovered_process != first_process,
                    "steered_on_replacement": steered_process == recovered_process,
                    "sections_before_loss": len(committed_before_loss),
                    "resume_at": resume_at + 1,
                    "stage_count": total,
                    "original_sections": len(a_records),
                    "replacement_sections": len(b_records),
                    "checkpoint_continuity": f"{committed_before_loss[-1]['stage_name']} -> {resumed[0]['stage_name']}",
                    "sample": {
                        "original": [{"index": r["stage_index"], "text": r["translated_text"]} for r in a_records[:2]],
                        "replacement": [{"index": r["stage_index"], "text": r["translated_text"]} for r in b_records[:2]],
                    },
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                },
            }
        )
    except (HTTPException, RuntimeError, httpx.HTTPError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        yield _sse({"kind": "error", "message": detail[:500]})


# ---------------------------------------------------------------------------
# Scenario 5: the approval Agent (review gate that survives instance loss)
# ---------------------------------------------------------------------------
async def _approval_post(request: Request, agent: str, session_id: str, payload: dict[str, Any]) -> httpx.Response:
    return await _request(request, "POST", _approval_url(agent, session_id), json_body=payload)


async def _approval_turn(
    request: Request, agent: str, session_id: str, payload: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Submit one invocation and yield poll snapshots until the turn completes.

    Every snapshot carries the Agent's live ``progress`` so the caller can surface
    sections as they are committed; the final snapshot has ``status == completed``.
    """
    response = await _approval_post(request, agent, session_id, payload)
    _raise_foundry(response, f"approval-{payload.get('action')}")
    created = response.json()
    invocation_id = str(created.get("invocation_id") or "")
    if response.status_code != 202 or not invocation_id:
        raise RuntimeError("approval turn did not return 202 with an invocation id")
    deadline = time.monotonic() + LRA_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        current = await _request(request, "GET", _approval_url(agent, session_id, invocation_id))
        if current.status_code in NOT_READY_STATUSES:
            await asyncio.sleep(1)
            continue
        _raise_foundry(current, f"approval-poll-{invocation_id}")
        state = current.json()
        state["invocation_id"] = invocation_id
        yield state
        if state.get("status") == "failed":
            raise RuntimeError(f"the Agent reported a failed turn: {state.get('error')}")
        if state.get("status") == "completed" and isinstance(state.get("output"), dict):
            return
        await asyncio.sleep(1)
    raise RuntimeError(f"approval invocation {invocation_id} did not complete")


def _approval_section_event(result: dict[str, Any], total: int) -> dict[str, Any]:
    return {
        "kind": "section",
        "index": result.get("stage_index"),
        "name": result.get("stage_name"),
        "batch": result.get("batch"),
        "entry_mode": result.get("entry_mode"),
        "process_sha256": result.get("process_sha256"),
        "source": result.get("source_text"),
        "text": result.get("translated_text"),
        "stage_result_sha256": result.get("stage_result_sha256"),
        "total_sections": total,
    }


def _approval_total(state: dict[str, Any]) -> int:
    return int(((state.get("progress") or {}).get("total_sections")) or 0)


async def _approval_decide_events(
    request: Request,
    agent: str,
    session_id: str,
    *,
    decision: str,
    approver: str,
    task_sha: str,
    process_a: str,
    sample_hashes: list[str],
    already_emitted: set[int],
) -> AsyncIterator[dict[str, Any]]:
    """Second phase: land the reviewer's decision on whichever instance is alive and
    stream the remaining sections until the job resolves."""
    action = "approve_review" if decision == "approve" else "reject_review"
    yield {"kind": "approval_submitted", "decision": action, "actor": approver}
    final: dict[str, Any] | None = None
    async for state in _approval_turn(request, agent, session_id, {"action": action, "approver": approver}):
        total = _approval_total(state)
        for result in (state.get("progress") or {}).get("results") or []:
            index = result.get("stage_index")
            if isinstance(index, int) and index not in already_emitted:
                already_emitted.add(index)
                yield _approval_section_event(result, total)
        if state.get("status") == "completed":
            final = state
    if final is None:
        raise RuntimeError("the review decision did not reach a terminal state")
    output = final.get("output") or {}
    results = (final.get("progress") or {}).get("results") or []
    total = _approval_total(final)
    process_b = str(output.get("process_sha256") or "")
    if decision == "reject":
        passed = output.get("status") == "resolved" and output.get("outcome") == "stopped"
        yield {
            "kind": "done",
            "result": {
                "verdict": "PASS" if passed else "FAIL",
                "status": "rejected",
                "agent": agent,
                "task_id_sha256": output.get("task_id_sha256"),
                "process_b_sha256": process_b,
                "completed_sections": len(results),
            },
        }
        return
    indexes = [item.get("stage_index") for item in results]
    sample_now = [item.get("stage_result_sha256") for item in results[: len(sample_hashes)]]
    passed = all(
        (
            total > 0,
            output.get("status") == "resolved",
            output.get("outcome") == "completed",
            output.get("task_id_sha256") == task_sha,
            process_b and process_b != process_a,
            indexes == list(range(total)),
            all((item.get("translated_text") or "").strip() for item in results),
            # The reviewed sample must survive the instance loss untouched.
            not sample_hashes or sample_now == sample_hashes,
            all(item.get("process_sha256") == process_a for item in results[: len(sample_hashes)]),
            all(item.get("process_sha256") == process_b for item in results[len(sample_hashes):]),
        )
    )
    if not passed:
        raise RuntimeError("approval acceptance failed after replacement compute")
    yield {
        "kind": "done",
        "result": {
            "verdict": "PASS",
            "status": "completed",
            "agent": agent,
            "target": output.get("target"),
            "target_name": output.get("target_name"),
            "task_id_sha256": task_sha,
            "process_a_sha256": process_a,
            "process_b_sha256": process_b,
            "process_replaced": True,
            "sample_sections": len(sample_hashes),
            "remaining_sections": len(results) - len(sample_hashes),
            "total_sections": len(results),
            "sample_preserved": True,
            "reviewer": approver,
        },
    }


async def _approval_stream(request: Request, body: ApprovalDemoRequest) -> AsyncIterator[str]:
    """First phase: translate the sample, lose the instance while the sample awaits
    review, prove a replacement instance is serving, then either stop for the human
    (default) or approve on their behalf when auto_approve is set."""
    agent = settings.approval_agent_name
    session_id = f"approval-{secrets.token_hex(8)}"
    started = time.monotonic()
    emitted: set[int] = set()
    try:
        contract = _runtime_contract(await _get_agent(request, agent), "approval gate")
        yield _sse(
            {
                "kind": "scenario_started",
                "scenario": "approval",
                "agent": agent,
                "version": contract.get("version"),
                "session_id": session_id,
                "target": body.target,
                "target_name": TARGET_NAMES[body.target],
                "sample_size": body.sample_size,
            }
        )
        yield _sse({"kind": "translating_sample", "sample_size": body.sample_size})
        sampled: dict[str, Any] | None = None
        async for state in _approval_turn(
            request,
            agent,
            session_id,
            {"action": "start", "target": body.target, "sample_size": body.sample_size, "stage_delay_ms": body.stage_delay_ms},
        ):
            total = _approval_total(state)
            for result in (state.get("progress") or {}).get("results") or []:
                index = result.get("stage_index")
                if isinstance(index, int) and index not in emitted:
                    emitted.add(index)
                    yield _sse(_approval_section_event(result, total))
            if state.get("status") == "completed":
                sampled = state
        output = (sampled or {}).get("output") or {}
        sample = ((sampled or {}).get("progress") or {}).get("results") or []
        process_a = str(output.get("process_sha256") or "")
        task_sha = str(output.get("task_id_sha256") or "")
        if output.get("status") != "awaiting_review" or len(sample) != body.sample_size or not process_a or not task_sha:
            raise RuntimeError("the agent did not persist a reviewable sample translation")
        sample_hashes = [str(item.get("stage_result_sha256") or "") for item in sample]
        yield _sse(
            {
                "kind": "review_ready",
                "sample_size": len(sample),
                "total_sections": _approval_total(sampled or {}),
                "process_sha256": process_a,
                "task_id_sha256": task_sha,
                "detail": "the sample is durable and waiting for a reviewer",
            }
        )

        yield _sse({"kind": "fault_armed", "detail": "process loss while the review is pending"})
        try:
            fault = await asyncio.wait_for(
                _approval_post(request, agent, session_id, {"action": "inject_process_loss"}), timeout=30
            )
        except (TimeoutError, httpx.HTTPError):
            fault = None
        if fault is not None and fault.status_code not in {424, 500, 502, 503, 504}:
            raise RuntimeError(f"fault injection returned HTTP {fault.status_code} instead of losing the process")
        yield _sse(
            {
                "kind": "process_lost",
                "process_sha256": process_a,
                "detail": "the sample and the pending review remain in the durable task store",
            }
        )

        process_b = ""
        deadline = time.monotonic() + LRA_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            try:
                probe = await _approval_post(request, agent, session_id, {"action": "probe_instance"})
                if probe.status_code == 200:
                    candidate = str(probe.json().get("process_sha256") or "")
                    if candidate and candidate != process_a:
                        process_b = candidate
                        break
                elif probe.status_code not in NOT_READY_STATUSES:
                    _raise_foundry(probe, "approval-instance-probe")
            except httpx.HTTPError:
                pass
            yield _sse({"kind": "waiting", "detail": "replacement compute is starting"})
            await asyncio.sleep(LRA_RECONNECT_INTERVAL_SECONDS)
        if not process_b:
            raise RuntimeError("replacement compute did not expose a new process identity")
        yield _sse(
            {
                "kind": "recovered",
                "process_sha256": process_b,
                "detail": "a new instance is serving; the sample is still awaiting review",
            }
        )

        handoff = {
            "session_id": session_id,
            "task_id_sha256": task_sha,
            "process_a_sha256": process_a,
            "process_b_sha256": process_b,
            "sample_hashes": sample_hashes,
            "sample_size": len(sample),
        }
        if not body.auto_approve:
            yield _sse({"kind": "awaiting_human", **handoff})
            yield _sse(
                {
                    "kind": "done",
                    "result": {
                        "verdict": "AWAITING_APPROVAL",
                        "status": "awaiting_approval",
                        "agent": agent,
                        "agent_version": contract.get("version"),
                        "target": body.target,
                        "target_name": TARGET_NAMES[body.target],
                        **handoff,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                    },
                }
            )
            return

        async for event in _approval_decide_events(
            request,
            agent,
            session_id,
            decision="approve",
            approver=body.approver,
            task_sha=task_sha,
            process_a=process_a,
            sample_hashes=sample_hashes,
            already_emitted=emitted,
        ):
            if event.get("kind") == "done":
                event["result"] = {
                    **event["result"],
                    "agent_version": contract.get("version"),
                    "session_id": session_id,
                    "auto_approved": True,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            yield _sse(event)
    except (HTTPException, RuntimeError, httpx.HTTPError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        yield _sse({"kind": "error", "message": detail[:500]})


async def _approval_decision_stream(request: Request, body: ApprovalDecisionRequest) -> AsyncIterator[str]:
    agent = settings.approval_agent_name
    started = time.monotonic()
    try:
        contract = _runtime_contract(await _get_agent(request, agent), "approval gate")
        async for event in _approval_decide_events(
            request,
            agent,
            body.session_id,
            decision=body.decision,
            approver=body.approver,
            task_sha=body.task_id_sha256,
            process_a=body.process_a_sha256,
            sample_hashes=body.sample_hashes,
            already_emitted=set(range(len(body.sample_hashes))),
        ):
            if event.get("kind") == "done":
                event["result"] = {
                    **event["result"],
                    "agent_version": contract.get("version"),
                    "session_id": body.session_id,
                    "auto_approved": False,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            yield _sse(event)
    except (HTTPException, RuntimeError, httpx.HTTPError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False)
        yield _sse({"kind": "error", "message": detail[:500]})


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "lra-resilience-demo"}


@app.get("/api/agents")
async def agents(request: Request, _: str = Depends(require_auth)) -> dict[str, Any]:
    if not settings.project_endpoint:
        return {
            "configured": False,
            "agents": [],
            "detail": "Set FOUNDRY_PROJECT_ENDPOINT to read the deployed Agents.",
        }
    names = (
        (settings.fault_agent_name, "checkpoint recovery"),
        (settings.steering_agent_name, "steering"),
        (settings.approval_agent_name, "approval gate"),
    )
    definitions = await asyncio.gather(*(_get_agent(request, name) for name, _ in names))
    return {
        "configured": True,
        "agents": [
            _runtime_contract(definition, label) for definition, (_, label) in zip(definitions, names, strict=True)
        ]
    }


@app.post("/api/validator-check")
async def validator_check(_: str = Depends(require_auth)) -> dict[str, Any]:
    """A PASS is only worth something if damaged evidence is actually rejected."""

    def stage(index: int, *, text: str = "译文") -> dict[str, Any]:
        return {"index": index, "name": f"translation_section_{index + 1:02d}", "source": "English source", "text": text}

    def run(first: list[int], second: list[int], **overrides: Any) -> list[dict[str, Any]]:
        stages_a = [stage(index) for index in first]
        stages_b = [stage(index) for index in second]
        if overrides.get("blank_last") and stages_b:
            stages_b[-1] = stage(stages_b[-1]["index"], text="")
        lanes = [{"process_sha256": "a" * 64, "entry_mode": "fresh", "stages": stages_a}]
        if stages_b or not overrides.get("single_process"):
            lanes.append({"process_sha256": "b" * 64, "entry_mode": "recovered", "stages": stages_b})
        return lanes

    cases = [
        ("healthy-process-loss", "A complete, ordered, handed-off run must pass", False, run([0, 1, 2, 3], [4, 5, 6, 7]), "completed", "crash", True),
        ("healthy-safe-run", "A complete no-fault run in one process must pass", False, run(list(range(8)), [], single_process=True), "completed", "crash", False),
        ("healthy-observer-restart", "A complete observer-restart run in one process must pass", False, run(list(range(8)), [], single_process=True), "completed", "detach", False),
        ("missing-checkpoint", "A gap in the checkpoint sequence must be rejected", True, run([0, 1, 2, 3], [4, 6, 7]), "completed", "crash", True),
        ("duplicate-checkpoint", "A repeated checkpoint must be rejected", True, run([0, 1, 2, 3], [3, 4, 5, 6]), "completed", "crash", True),
        ("empty-translation", "A checkpoint without its translated text must be rejected", True, run([0, 1, 2, 3], [4, 5, 6, 7], blank_last=True), "completed", "crash", True),
        ("no-handoff", "A crash run that never reached a second process must be rejected", True, run(list(range(8)), [], single_process=True), "completed", "crash", True),
        ("non-terminal-status", "A run that never reached completed must be rejected", True, run([0, 1, 2, 3], [4, 5, 6, 7]), "in_progress", "crash", True),
    ]
    results = []
    for case_id, purpose, expect_rejected, processes, status, mode, inject in cases:
        acceptance = _lra_acceptance(processes, 8, status, mode, inject)
        rejected = not acceptance["passed"]
        results.append(
            {
                "id": case_id,
                "purpose": purpose,
                "expect_rejected": expect_rejected,
                "rejected": rejected,
                "behaved": rejected == expect_rejected,
                "verdict": acceptance["verdict"],
            }
        )
    return {"cases": results, "all_behaved": all(item["behaved"] for item in results)}


@app.post("/api/run")
async def run(body: ResilienceRequest, request: Request, username: str = Depends(require_auth)) -> StreamingResponse:
    logger.info("run actor=%s mode=%s inject=%s crash_after_stage=%s", username, body.mode, body.inject, body.crash_after_stage)
    return StreamingResponse(
        _resilience_stream(
            request,
            mode=body.mode,
            inject=body.inject,
            crash_after_stage=body.crash_after_stage,
            stage_delay_ms=body.stage_delay_ms,
            detach_after_sections=body.detach_after_sections,
            detach_seconds=body.detach_seconds,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/steering")
async def steering(body: SteeringDemoRequest, request: Request, username: str = Depends(require_auth)) -> StreamingResponse:
    logger.info("steering actor=%s targets=%s->%s", username, body.original_target, body.replacement_target)
    return StreamingResponse(_steering_stream(request, body), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/api/approval")
async def approval(body: ApprovalDemoRequest, request: Request, username: str = Depends(require_auth)) -> StreamingResponse:
    logger.info("approval actor=%s target=%s sample=%s auto=%s", username, body.target, body.sample_size, body.auto_approve)
    return StreamingResponse(_approval_stream(request, body), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/api/approval/decide")
async def approval_decide(
    body: ApprovalDecisionRequest, request: Request, username: str = Depends(require_auth)
) -> StreamingResponse:
    logger.info("approval_decide actor=%s decision=%s", username, body.decision)
    return StreamingResponse(_approval_decision_stream(request, body), media_type="text/event-stream", headers=SSE_HEADERS)
