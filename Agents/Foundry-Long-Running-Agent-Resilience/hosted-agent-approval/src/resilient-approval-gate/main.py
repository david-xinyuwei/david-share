# Copyright (c) Microsoft. All rights reserved.

"""Resilient translate → human review → continue agent (invocations protocol).

Ported from the Microsoft ``resilient-approval-gate`` Hosted Agent sample and
re-shaped around the same 30-section translation job the Portal's other
resilience demos use. The human gate is a *review of a real sample*:

1. **start** — translate the first ``sample_size`` sections with Azure Translator,
   checkpointing every section in the durable chain state, then *suspend* with
   status ``awaiting_review`` so a reviewer can read the sample.
2. **approve_review** — the reviewer accepts the sample; the agent translates the
   remaining sections (again checkpointing each one) and resolves.
   ``reject_review`` stops the job instead.

The ``@multi_turn_task`` chain keeps the target language, every committed
section, and the review state in the task store, so the wait for the reviewer —
and the translation itself — survive a container restart, an OOM kill, or a
redeploy. A recovered process resumes at the first uncommitted section and the
reviewer's decision lands on whichever instance is alive.

Every POST returns ``202`` with an ``invocation_id``; ``GET /invocations/{id}``
returns the invocation's terminal output plus live ``progress`` (sections
committed so far) read from the same durable state.

Required environment variables:
    LRA_TRANSLATOR_ENDPOINT, LRA_TRANSLATOR_REGION, LRA_TRANSLATOR_RESOURCE_ID
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from azure.ai.agentserver.core.tasks import (
    TaskConflictError,
    TaskContext,
    multi_turn_task,
)
from azure.ai.agentserver.core.tasks._manager import get_task_manager
from azure.ai.agentserver.invocations import InvocationAgentServerHost
from azure.identity import DefaultAzureCredential

from translation_workload import SECTION_IDS, SOURCE_SECTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("resilient-approval-gate")

if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    logger.warning(
        "APPLICATIONINSIGHTS_CONNECTION_STRING not set — traces will not be sent to "
        "Application Insights. It is auto-injected in hosted Foundry containers."
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
if not os.environ.get("LRA_TRANSLATOR_ENDPOINT"):
    raise RuntimeError("LRA_TRANSLATOR_ENDPOINT is required")
FAULT_INJECTION_ENABLED = (
    os.environ.get("LRE_ENABLE_FAULT_INJECTION", "false").lower() == "true"
)
DEFAULT_STAGE_DELAY_MS = int(os.environ.get("LRE_STAGE_DELAY_MS", "300"))
DEFAULT_TARGET = "zh-Hans"
DEFAULT_SAMPLE_SIZE = 10
TARGET_LANGUAGES = {
    "zh-Hans": "Simplified Chinese",
    "zh-Hant": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}
PROCESS_INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
PROCESS_SHA256 = hashlib.sha256(PROCESS_INSTANCE_ID.encode("utf-8")).hexdigest()
TRANSLATOR_CREDENTIAL = DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _translate_sync(text: str, target: str) -> str:
    endpoint = os.environ["LRA_TRANSLATOR_ENDPOINT"].rstrip("/")
    region = os.environ.get("LRA_TRANSLATOR_REGION", "global")
    resource_id = os.environ.get("LRA_TRANSLATOR_RESOURCE_ID", "").strip()
    query = urllib.parse.urlencode({"api-version": "3.0", "from": "en", "to": target})
    # A resource without a custom subdomain is reached through the shared global
    # endpoint and identified by the resource-ID header.
    path = "/translate" if resource_id else "/translator/text/v3.0/translate"
    token = TRANSLATOR_CREDENTIAL.get_token("https://cognitiveservices.azure.com/.default")
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": region,
    }
    if resource_id:
        headers["Ocp-Apim-ResourceId"] = resource_id
    request = urllib.request.Request(
        f"{endpoint}{path}?{query}",
        data=json.dumps([{"Text": text}]).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Translator returned HTTP {error.code}: {body}") from error
    try:
        translated = payload[0]["translations"][0]["text"]
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError(f"Translator returned an unexpected payload: {payload!r}") from error
    if not isinstance(translated, str) or not translated.strip():
        raise RuntimeError("Translator returned empty text")
    return translated


# ---------------------------------------------------------------------------
# OpenAPI 3.0 spec — served at GET /invocations/docs/openapi.json
# ---------------------------------------------------------------------------
OPENAPI_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {
        "title": "Resilient Translation Review-Gate Agent",
        "version": "2.0.0",
        "description": (
            "Translates a 30-section document with Azure Translator, suspends after a "
            "sample batch for human review, and finishes the remaining sections once the "
            "review is approved. Every section is a durable checkpoint."
        ),
    },
    "paths": {
        "/invocations": {
            "post": {
                "summary": "Start the job or respond to the pending review",
                "parameters": [
                    {
                        "name": "agent_session_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": [
                                            "start",
                                            "approve_review",
                                            "reject_review",
                                            "inject_process_loss",
                                            "probe_instance",
                                        ],
                                    },
                                    "target": {"type": "string", "enum": sorted(TARGET_LANGUAGES)},
                                    "sample_size": {"type": "integer", "minimum": 1, "maximum": 29},
                                    "stage_delay_ms": {"type": "integer", "minimum": 0, "maximum": 10000},
                                    "approver": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["action"],
                            }
                        }
                    },
                },
                "responses": {
                    "202": {"description": "Accepted; poll the invocation for status."},
                    "409": {"description": "The chain is busy translating; retry shortly."},
                },
            }
        },
        "/invocations/{invocation_id}": {
            "get": {
                "summary": "Poll the status, output and live progress of an invocation",
                "parameters": [
                    {
                        "name": "invocation_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "agent_session_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {
                    "200": {"description": "Current status, output and progress."},
                    "404": {"description": "Invocation not found."},
                },
            }
        },
        "/invocations/{invocation_id}/cancel": {
            "post": {
                "summary": "Cancel the job (deletes the resilient chain)",
                "parameters": [
                    {
                        "name": "invocation_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "agent_session_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "Cancellation result."}},
            }
        },
    },
}


# ---------------------------------------------------------------------------
# Resilient chain — one @multi_turn_task per job (task_id == job session).
# ---------------------------------------------------------------------------
@multi_turn_task(name="translation_review_workflow")
async def review_workflow(ctx: TaskContext[dict]) -> dict[str, Any]:
    """One resilient chain per job. Each POST runs this from the top.

    The default metadata namespace holds the per-invocation result the HTTP
    ``GET`` handler polls. The ``"job"`` namespace holds cross-turn state — the
    target language, every committed section, and the review phase — that must
    survive both the human wait and any crash.
    """

    data = ctx.input
    invocation_id: str = data.get("invocation_id", ctx.input_id)
    action = str(data.get("action", "start")).lower()
    job = ctx.metadata("job")

    ctx.metadata["invocation_id"] = invocation_id
    ctx.metadata["status"] = "running"
    await ctx.metadata.flush()

    if ctx.entry_mode == "recovered":
        logger.warning(
            "LRE_REVIEW_RECOVERED task=%s phase=%s completed=%s process=%s",
            ctx.task_id,
            job.get("phase"),
            job.get("completed_sections"),
            PROCESS_SHA256,
        )

    try:
        if action == "start":
            return await _do_start(ctx, job, data)
        if action == "approve_review":
            return await _continue_after_review(ctx, job, data, approved=True)
        if action == "reject_review":
            return await _continue_after_review(ctx, job, data, approved=False)
        return await _complete(ctx, job, {"status": "error", "message": f"Unknown action: {action}"})
    except Exception as error:
        # Without this the poller keeps reading ``running`` after the handler died
        # (for example on a Translator 401). Record the failure, then let the
        # runtime handle the exception exactly as before.
        ctx.metadata["status"] = "failed"
        ctx.metadata["error"] = f"{type(error).__name__}: {error}"
        await ctx.metadata.flush()
        logger.exception(
            "LRE_REVIEW_TURN_FAILED task=%s action=%s process=%s", ctx.task_id, action, PROCESS_SHA256
        )
        raise


async def _do_start(ctx: TaskContext[dict], job: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Turn 1: translate the sample batch, then suspend for human review."""

    phase = job.get("phase")
    if phase in ("awaiting_review", "executing", "resolved"):
        # Idempotent replay: report the current state instead of restarting.
        return await _complete(ctx, job, {"status": phase, "note": "Job already started."})

    target = str(data.get("target") or DEFAULT_TARGET)
    if target not in TARGET_LANGUAGES:
        return await _complete(
            ctx,
            job,
            {"status": "error", "message": f"target must be one of {', '.join(sorted(TARGET_LANGUAGES))}"},
        )
    sample_size = data.get("sample_size", DEFAULT_SAMPLE_SIZE)
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size not in range(1, len(SOURCE_SECTIONS)):
        return await _complete(ctx, job, {"status": "error", "message": f"sample_size must be 1-{len(SOURCE_SECTIONS) - 1}"})
    stage_delay_ms = data.get("stage_delay_ms", DEFAULT_STAGE_DELAY_MS)
    if isinstance(stage_delay_ms, bool) or not isinstance(stage_delay_ms, int) or stage_delay_ms not in range(0, 10_001):
        return await _complete(ctx, job, {"status": "error", "message": "stage_delay_ms must be 0-10000"})

    if phase is None:
        job["target"] = target
        job["sample_size"] = sample_size
        job["stage_delay_ms"] = stage_delay_ms
        job["results"] = []
        job["completed_sections"] = 0
        job["phase"] = "sampling"
        job["started_at"] = _now_iso()
        await job.flush()

    await _translate_range(ctx, job, until=int(job["sample_size"]))

    job["phase"] = "awaiting_review"
    job["review_ready_at"] = _now_iso()
    await job.flush()
    return await _complete(
        ctx,
        job,
        {
            "status": "awaiting_review",
            "note": "Review the sample translation. POST action=approve_review (or reject_review).",
        },
    )


async def _continue_after_review(
    ctx: TaskContext[dict], job: Any, data: dict[str, Any], *, approved: bool
) -> dict[str, Any]:
    """Later turns: apply the reviewer's decision and finish (or stop) the job."""

    phase = job.get("phase")
    if phase == "resolved":
        return await _complete(ctx, job, {"status": "resolved", "outcome": job.get("outcome"), "note": "Job already resolved."})
    if phase not in ("awaiting_review", "executing"):
        return await _complete(ctx, job, {"status": "error", "message": "No sample awaiting review."})

    if not approved:
        job["phase"] = "resolved"
        job["outcome"] = "stopped"
        job["reviewer"] = data.get("approver", "unknown")
        job["review_reason"] = data.get("reason", "")
        await job.flush()
        return await _complete(ctx, job, {"status": "resolved", "outcome": "stopped", "note": "Sample rejected; translation halted."})

    if phase == "awaiting_review":
        job["reviewer"] = data.get("approver", "unknown")
        job["approved_at"] = _now_iso()
        job["phase"] = "executing"
        await job.flush()

    await _translate_range(ctx, job, until=len(SOURCE_SECTIONS))

    job["phase"] = "resolved"
    job["outcome"] = "completed"
    job["resolved_at"] = _now_iso()
    await job.flush()
    return await _complete(
        ctx,
        job,
        {
            "status": "resolved",
            "outcome": "completed",
            "summary": f"Translated {len(SOURCE_SECTIONS)}/{len(SOURCE_SECTIONS)} sections into {job['target']}.",
        },
    )


async def _translate_range(ctx: TaskContext[dict], job: Any, *, until: int) -> None:
    """Translate sections up to ``until`` with one durable checkpoint per section.

    Resumes at ``completed_sections`` so a recovered process never repeats a
    committed section and never skips one.
    """

    target = str(job["target"])
    delay = int(job.get("stage_delay_ms", DEFAULT_STAGE_DELAY_MS)) / 1000
    results: list[dict[str, Any]] = list(job.get("results", []))
    completed = int(job.get("completed_sections", 0) or 0)
    entry_mode = ctx.entry_mode
    for index in range(completed, until):
        translated = await asyncio.to_thread(_translate_sync, SOURCE_SECTIONS[index], target)
        await asyncio.sleep(delay)
        results.append(
            {
                "stage_index": index,
                "stage_name": SECTION_IDS[index],
                "source_text": SOURCE_SECTIONS[index],
                "translated_text": translated,
                "stage_result_sha256": hashlib.sha256(translated.encode("utf-8")).hexdigest(),
                "entry_mode": entry_mode,
                "process_sha256": PROCESS_SHA256,
                "batch": "sample" if index < int(job["sample_size"]) else "remaining",
                "at": _now_iso(),
            }
        )
        job["results"] = results
        job["completed_sections"] = index + 1
        # Watermark: a crash after this flush resumes at index+1, never re-running index.
        await job.flush()
        logger.info(
            "LRE_REVIEW_SECTION_COMMITTED task=%s section=%d target=%s process=%s",
            ctx.task_id,
            index,
            target,
            PROCESS_SHA256,
        )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _progress(job_state: dict[str, Any] | None) -> dict[str, Any]:
    job_state = job_state or {}
    results = job_state.get("results") or []
    return {
        "phase": job_state.get("phase"),
        "target": job_state.get("target"),
        "target_name": TARGET_LANGUAGES.get(str(job_state.get("target")), None),
        "sample_size": job_state.get("sample_size"),
        "total_sections": len(SOURCE_SECTIONS),
        "completed_sections": job_state.get("completed_sections", 0),
        "reviewer": job_state.get("reviewer"),
        "results": results,
    }


async def _complete(ctx: TaskContext[dict], job: Any, result: dict[str, Any]) -> dict[str, Any]:
    """Publish the per-invocation result to the default namespace, then return."""

    result = {
        **result,
        **{k: v for k, v in _progress(dict(job)).items() if k != "results"},
        "entry_mode": ctx.entry_mode,
        "process_sha256": PROCESS_SHA256,
        "task_id_sha256": hashlib.sha256(ctx.task_id.encode("utf-8")).hexdigest(),
    }
    ctx.metadata["status"] = "completed"
    ctx.metadata["output"] = result
    await ctx.metadata.flush()
    return result


# ---------------------------------------------------------------------------
# Server + HTTP handlers
# ---------------------------------------------------------------------------
app = InvocationAgentServerHost(openapi_spec=OPENAPI_SPEC)

# In-memory convenience index so GET works with just an invocation_id while the
# process is alive. The authoritative, crash-surviving state is the task store;
# this map is only a lookup shortcut (GET also accepts ?agent_session_id=).
_inv_to_task: dict[str, str] = {}


def _task_id(session_id: str) -> str:
    return f"job-{session_id}"


def _resolve_task_id(request: Request, invocation_id: str) -> str | None:
    if invocation_id in _inv_to_task:
        return _inv_to_task[invocation_id]
    session_id = request.query_params.get("agent_session_id") or getattr(
        request.state, "session_id", ""
    )
    return _task_id(session_id) if session_id else None


async def _read_task_payload(task_id: str) -> dict[str, Any] | None:
    info = await get_task_manager().provider.get(task_id)
    if info is None:
        return None
    return dict(info.payload or {})


@app.invoke_handler
async def handle_invoke(request: Request) -> Response:
    """Start or resume the resilient chain for this job; return 202 immediately."""

    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError
    except Exception:  # pylint: disable=broad-except
        return JSONResponse({"error": "Body must be a JSON object with an 'action'."}, status_code=400)

    session_id: str = request.state.session_id
    invocation_id: str = request.state.invocation_id
    task_id = _task_id(session_id)
    action = str(data.get("action", "")).lower()

    if action == "probe_instance":
        return JSONResponse(
            {
                "session_id": session_id,
                "invocation_id": invocation_id,
                "status": "completed",
                "process_sha256": PROCESS_SHA256,
            }
        )

    if action == "inject_process_loss":
        if not FAULT_INJECTION_ENABLED:
            return JSONResponse(
                {"error": "Fault injection is disabled for this deployment."},
                status_code=403,
            )
        payload = await _read_task_payload(task_id)
        job_state = (payload or {}).get("metadata:job") or {}
        if job_state.get("phase") != "awaiting_review":
            return JSONResponse(
                {"error": "Process loss is allowed only while a sample awaits review."},
                status_code=409,
            )
        logger.critical(
            "LRE_REVIEW_PROCESS_LOSS task=%s process=%s completed=%s",
            task_id,
            PROCESS_SHA256,
            job_state.get("completed_sections"),
        )
        await asyncio.sleep(0.25)
        os._exit(86)

    data["invocation_id"] = invocation_id

    try:
        await review_workflow.start(task_id=task_id, input=data)
    except TaskConflictError:
        return JSONResponse(
            {"error": "Job is translating; wait for the next gate before posting again."},
            status_code=409,
        )

    _inv_to_task[invocation_id] = task_id
    return JSONResponse(
        {"session_id": session_id, "invocation_id": invocation_id, "status": "running"},
        status_code=202,
    )


@app.get_invocation_handler
async def poll_invocation(request: Request) -> Response:
    """Poll an invocation's status/output plus live section progress."""

    invocation_id: str = request.state.invocation_id
    task_id = _resolve_task_id(request, invocation_id)
    if not task_id:
        return JSONResponse(
            {"error": "Provide ?agent_session_id=<id> to locate the job."},
            status_code=404,
        )

    payload = await _read_task_payload(task_id)
    if payload is None:
        return JSONResponse({"error": "Job not found."}, status_code=404)
    meta = payload.get("metadata") or {}
    if meta.get("invocation_id") != invocation_id:
        return JSONResponse(
            {"error": "This invocation is not the most recent for the job.", "current": meta.get("status")},
            status_code=404,
        )

    return JSONResponse(
        {
            "invocation_id": invocation_id,
            "status": meta.get("status"),
            "output": meta.get("output"),
            "error": meta.get("error"),
            "progress": _progress(payload.get("metadata:job")),
            "process_sha256": PROCESS_SHA256,
        }
    )


@app.cancel_invocation_handler
async def cancel_invocation(request: Request) -> Response:
    """Cancel the whole job — deletes the resilient chain (idempotent)."""

    invocation_id: str = request.state.invocation_id
    task_id = _resolve_task_id(request, invocation_id)
    if not task_id:
        return JSONResponse({"error": "Provide ?agent_session_id=<id> to locate the job."}, status_code=404)

    await review_workflow.delete(task_id)
    return JSONResponse({"invocation_id": invocation_id, "status": "cancelled"})


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
