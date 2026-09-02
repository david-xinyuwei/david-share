#!/usr/bin/env python3
"""Drive the steering recovery scenario against the Foundry-hosted steering Agent.

Order under test (the change of mind lands *after* recovery, see the README boundary
on the reverse order):

1. ``POST`` response A: translate into language A with a guarded hard exit after
   ``--crash-after-stage``. The SSE stream ends without a terminal event because the
   process is gone.
2. Reattach to A with ``stream=true`` until replacement compute re-enters it as
   ``recovered`` and commits ``--steer-after-sections`` more checkpoints. Reconnects
   replay the persisted prefix, so items are de-duplicated by ``output_index``; before
   the recovery scan has re-entered the task the gateway answers 400, which is
   treated as "not yet" and the durable status is polled instead.
3. ``POST`` response B on the same conversation (``previous_response_id`` = A) asking
   for language B. A winds down with the sections it has; B is a new target
   language, so it starts at section 1 and must finish all sections on the
   replacement process.

Only SHA-256 digests of response IDs and process instance IDs are written to disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

TERMINAL_EVENTS = {
    "response.completed",
    "response.failed",
    "response.incomplete",
    "response.cancelled",
}
STAGE_COUNT = 30


class RequestError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def seconds_between(start: str, end: str) -> float:
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 3
    )


def with_query(url: str, **extra: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update(extra)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), "")
    )


def item_url(endpoint: str, response_id: str, **extra: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    path = f"{parsed.path.rstrip('/')}/{urllib.parse.quote(response_id, safe='')}"
    base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))
    return with_query(base, **extra) if extra else base


def azure_cli_token() -> str:
    az = shutil.which("az.exe") or shutil.which("az.cmd") or shutil.which("az")
    if not az:
        raise RuntimeError("Azure CLI executable was not found on PATH")
    command = [az, "account", "get-access-token", "--resource", "https://ai.azure.com",
               "--query", "accessToken", "-o", "tsv"]
    if Path(az).suffix.lower() in {".cmd", ".bat"}:
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    token = subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()
    if not token:
        raise RuntimeError("Azure CLI returned an empty access token")
    return token


def open_request(
    method: str,
    url: str,
    body: dict[str, Any] | None,
    token: str | None,
    timeout_seconds: float,
    accept: str,
):
    headers = {"Accept": accept}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        return urllib.request.urlopen(request, timeout=timeout_seconds)
    except urllib.error.HTTPError as error:
        raise RequestError(error.code, error.read().decode("utf-8", errors="replace")) from error


def request_json(method: str, url: str, body: dict[str, Any] | None, token: str | None,
                 timeout_seconds: float = 30) -> dict[str, Any]:
    with open_request(method, url, body, token, timeout_seconds, "application/json") as response:
        return json.loads(response.read().decode("utf-8"))


def iter_sse(response) -> Iterator[dict[str, Any]]:
    """Yield decoded ``data:`` payloads; a closed socket simply ends the iterator."""
    data_lines: list[str] = []
    while True:
        raw = response.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if data_lines:
                try:
                    yield json.loads("".join(data_lines))
                except json.JSONDecodeError:
                    pass
                data_lines = []
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())


def json_record(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    for part in item.get("content") or []:
        if not isinstance(part, dict) or part.get("type") != "output_text":
            continue
        try:
            candidate = json.loads(part.get("text") or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(candidate, dict) and candidate.get("kind") in {
            "lre_steering_entry",
            "lra_stage",
        }:
            return candidate
    return None


class Lane:
    """One stored response as the client observes it."""

    def __init__(self, role: str) -> None:
        self.role = role
        self.response_id = ""
        self.entries: list[dict[str, Any]] = []
        self.stages: list[dict[str, Any]] = []
        self.seen: set[int] = set()
        self.terminal: dict[str, Any] | None = None

    @property
    def response_sha256(self) -> str:
        return sha256_text(self.response_id) if self.response_id else ""

    def stage_indexes(self, entry_mode: str | None = None) -> list[int]:
        return [
            int(stage["stage_index"])
            for stage in self.stages
            if entry_mode is None or stage.get("entry_mode") == entry_mode
        ]


def steering_checks(
    *,
    fresh: list[int],
    recovered: list[int],
    crash_after_stage: int,
    fresh_process: str,
    recovered_process: str,
    original_status: str,
    steered_entry: dict[str, Any],
    replacement_indexes: list[int],
    replacement_targets: list[str],
    replacement_target: str,
    replacement_terminal: str | None,
    texts: list[str],
) -> dict[str, bool]:
    """The acceptance rules; every rule must hold for the run to pass."""
    steered_process = str(steered_entry.get("process_sha256") or "")
    resume_index = recovered[0] if recovered else -1
    return {
        "fresh_sections_are_a_prefix": bool(fresh) and fresh == list(range(len(fresh))),
        "process_exited_after_crash_stage": bool(fresh) and fresh[-1] == crash_after_stage,
        "recovered_on_a_different_process": bool(recovered_process) and recovered_process != fresh_process,
        "resume_after_last_checkpoint": bool(fresh) and bool(recovered) and resume_index == fresh[-1] + 1,
        "recovered_sections_are_contiguous": bool(recovered)
        and recovered == list(range(resume_index, resume_index + len(recovered))),
        "original_response_completed": original_status == "completed",
        "steered_entry_on_replacement_process": steered_entry.get("entry_mode") == "steered"
        and bool(steered_process)
        and steered_process == recovered_process,
        "replacement_starts_at_section_1": bool(replacement_indexes) and replacement_indexes[0] == 0,
        "replacement_completed_all_sections": replacement_indexes == list(range(STAGE_COUNT)),
        "replacement_target_everywhere": bool(replacement_targets)
        and all(target == replacement_target for target in replacement_targets),
        "replacement_response_completed": replacement_terminal == "response.completed",
        "every_section_has_text": bool(texts) and all(text.strip() for text in texts),
    }


class Run:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.token = azure_cli_token() if args.auth == "azure-cli" else None
        self.timeline: list[dict[str, Any]] = []
        self.started_at = utc_now()

    def event(self, name: str, **fields: Any) -> None:
        row = {"at_utc": utc_now(), "event": name, "work_id": self.args.work_id,
               "source": "client_stream", **fields}
        self.timeline.append(row)
        detail = " ".join(f"{key}={value}" for key, value in fields.items()
                          if key not in {"response_id_sha256", "process_instance_sha256"})
        print(f"[{row['at_utc']}] {name} {detail}".rstrip(), flush=True)

    def request_body(self, target: str, inject: bool, previous: str | None = None) -> dict[str, Any]:
        body = {
            "model": self.args.agent_name,
            "input": json.dumps(
                {
                    "target": target,
                    "inject_process_loss": inject,
                    "crash_after_stage": self.args.crash_after_stage,
                    "stage_delay_ms": self.args.stage_delay_ms,
                },
                sort_keys=True,
            ),
            "store": True,
            "background": True,
            "stream": True,
        }
        if previous:
            body["previous_response_id"] = previous
        return body

    def consume(self, response, lane: Lane, stop_when=None) -> str | None:
        """Feed SSE events into the lane; return the terminal type, "stopped", or None."""
        for message in iter_sse(response):
            kind = message.get("type")
            if kind == "response.created":
                if not lane.response_id:
                    lane.response_id = str((message.get("response") or {}).get("id") or "")
                    self.event("response_created", response_role=lane.role,
                               response_id_sha256=lane.response_sha256)
            elif kind == "response.output_item.done":
                index = message.get("output_index")
                record = json_record(message.get("item"))
                if record is None or not isinstance(index, int) or index in lane.seen:
                    continue
                lane.seen.add(index)
                if record["kind"] == "lre_steering_entry":
                    lane.entries.append(record)
                    self.event("handler_entered", response_role=lane.role,
                               entry_mode=record.get("entry_mode"), target=record.get("target"),
                               resume_from_checkpoint=f"translation_section_{int(record.get('resume_from', 0)) + 1:02d}",
                               process_instance_sha256=record.get("process_sha256"),
                               response_id_sha256=lane.response_sha256)
                else:
                    lane.stages.append(record)
                    self.event("checkpoint_committed", response_role=lane.role,
                               checkpoint=record.get("stage_name"), entry_mode=record.get("entry_mode"),
                               target=record.get("target"),
                               process_instance_sha256=sha256_text(str(record.get("process_instance_id") or "")),
                               response_id_sha256=lane.response_sha256)
                    if stop_when is not None and stop_when(lane):
                        return "stopped"
            elif kind in TERMINAL_EVENTS:
                lane.terminal = message.get("response") or {}
                self.event("terminal_observed", response_role=lane.role,
                           status=lane.terminal.get("status"), response_id_sha256=lane.response_sha256)
                return kind
        return None

    def run(self) -> dict[str, Any]:
        args = self.args
        lane_a = Lane("A")
        lane_b = Lane("B")
        self.event("request_started", response_role="A", target=args.original_target,
                   crash_after_stage=args.crash_after_stage, fault_injection_requested=True)
        with open_request("POST", args.endpoint, self.request_body(args.original_target, True),
                          self.token, args.stream_timeout_seconds, "text/event-stream") as response:
            terminal = self.consume(response, lane_a)
        fresh = lane_a.stage_indexes("fresh")
        if terminal is not None or not lane_a.response_id or not fresh:
            raise RuntimeError(f"response A did not lose its process as requested: terminal={terminal} fresh={len(fresh)}")
        fresh_process = str(lane_a.entries[0].get("process_sha256") or "")
        self.event("stream_ended_without_terminal", response_role="A",
                   committed_sections=len(fresh), process_instance_sha256=fresh_process,
                   response_id_sha256=lane_a.response_sha256,
                   detail="the gateway closed the SSE stream cleanly; the process is gone")

        # Reattach until the replacement process re-enters A and commits enough sections.
        deadline = time.monotonic() + args.deadline_seconds
        recovered_process = ""
        rejected_logged = False
        target_count = len(fresh) + args.steer_after_sections
        stream_url = item_url(args.endpoint, lane_a.response_id, stream="true")
        status_url = item_url(args.endpoint, lane_a.response_id)
        while time.monotonic() < deadline and lane_a.terminal is None:
            try:
                with open_request("GET", stream_url, None, self.token, args.reconnect_timeout_seconds,
                                  "text/event-stream") as response:
                    self.event("reconnect_attached", response_role="A", response_id_sha256=lane_a.response_sha256)
                    terminal = self.consume(response, lane_a,
                                            stop_when=lambda lane: len(lane.stages) >= target_count)
                recovered = [entry for entry in lane_a.entries if entry.get("entry_mode") == "recovered"]
                if recovered:
                    recovered_process = str(recovered[-1].get("process_sha256") or "")
                if terminal == "stopped" or (recovered_process and len(lane_a.stages) >= target_count):
                    break
            except RequestError as error:
                # Replacement compute answers HTTP before its recovery scan has re-entered the
                # durable task; until then no live stream exists and the gateway answers 400.
                if not rejected_logged:
                    self.event("reconnect_rejected", response_role="A", http_status=error.status,
                               response_id_sha256=lane_a.response_sha256,
                               detail="no live stream yet; polling the durable status instead")
                    rejected_logged = True
            except (TimeoutError, OSError) as error:
                self.event("reconnect_timeout", response_role="A", detail=type(error).__name__,
                           response_id_sha256=lane_a.response_sha256)
            snapshot = request_json("GET", status_url, None, self.token)
            status = str(snapshot.get("status") or "")
            if status not in {"queued", "in_progress"}:
                raise RuntimeError(f"response A ended as {status or 'unknown'} before recovery was observed")
            time.sleep(args.poll_interval_seconds)

        recovered_stages = lane_a.stage_indexes("recovered")
        if not recovered_process or not recovered_stages:
            raise RuntimeError("replacement compute never re-entered response A")
        if lane_a.terminal is not None:
            raise RuntimeError("response A completed before the change of mind could be posted")
        resume_index = recovered_stages[0]
        self.event("recovery_observed", response_role="A",
                   resume_from_checkpoint=f"translation_section_{resume_index + 1:02d}",
                   last_checkpoint_before_loss=f"translation_section_{fresh[-1] + 1:02d}",
                   process_instance_sha256=recovered_process, response_id_sha256=lane_a.response_sha256)

        # Change of mind: post B on the same conversation while A is still translating.
        self.event("steer_posted", response_role="B", from_target=args.original_target,
                   to_target=args.replacement_target, previous_response_sha256=lane_a.response_sha256,
                   original_sections_so_far=len(lane_a.stages))
        with open_request("POST", args.endpoint,
                          self.request_body(args.replacement_target, False, lane_a.response_id),
                          self.token, args.deadline_seconds, "text/event-stream") as response:
            terminal_b = self.consume(response, lane_b)
        final_a = request_json("GET", status_url, None, self.token)
        if lane_a.terminal is None:
            lane_a.terminal = final_a
            self.event("terminal_observed", response_role="A", status=final_a.get("status"),
                       response_id_sha256=lane_a.response_sha256)

        steered = lane_b.entries[0] if lane_b.entries else {}
        steered_process = str(steered.get("process_sha256") or "")
        b_indexes = lane_b.stage_indexes()
        checks = steering_checks(
            fresh=fresh,
            recovered=recovered_stages,
            crash_after_stage=args.crash_after_stage,
            fresh_process=fresh_process,
            recovered_process=recovered_process,
            original_status=str(final_a.get("status")),
            steered_entry=steered,
            replacement_indexes=b_indexes,
            replacement_targets=[str(s.get("target")) for s in lane_b.stages],
            replacement_target=args.replacement_target,
            replacement_terminal=terminal_b,
            texts=[str(s.get("translated_text") or "") for s in lane_a.stages + lane_b.stages],
        )
        passed = all(checks.values())
        finished = utc_now()
        report = {
            "schema_version": 1,
            "evidence_type": "owned-hosted-agent-steering",
            "endpoint_class": "foundry-hosted-agent",
            "work_id": args.work_id,
            "deployment": {"agent_name": args.agent_name, "version": args.agent_version},
            "request": {
                "original_target": args.original_target,
                "replacement_target": args.replacement_target,
                "crash_after_stage": args.crash_after_stage,
                "steer_after_sections": args.steer_after_sections,
                "stage_delay_ms": args.stage_delay_ms,
                "fault_injection_requested": True,
            },
            "responses": {
                "A": {
                    "response_id_sha256": lane_a.response_sha256,
                    "status": final_a.get("status"),
                    "entry_modes": [entry.get("entry_mode") for entry in lane_a.entries],
                    "fresh_sections": len(fresh),
                    "recovered_sections": len(recovered_stages),
                    "last_checkpoint_before_loss": f"translation_section_{fresh[-1] + 1:02d}",
                    "first_checkpoint_after_recovery": f"translation_section_{resume_index + 1:02d}",
                    "process_instance_sha256": [fresh_process, recovered_process],
                },
                "B": {
                    "response_id_sha256": lane_b.response_sha256,
                    "status": (lane_b.terminal or {}).get("status"),
                    "entry_modes": [entry.get("entry_mode") for entry in lane_b.entries],
                    "sections": len(lane_b.stages),
                    "process_instance_sha256": [steered_process],
                },
            },
            "acceptance": {**checks, "process_instance_count": len({fresh_process, recovered_process}),
                           "sections_translated_twice_across_languages": len(set(lane_a.stage_indexes()) & set(b_indexes))},
            "samples": {
                "original_last": {"section": lane_a.stages[-1]["stage_name"], "text": lane_a.stages[-1]["translated_text"]},
                "replacement_first": {"section": lane_b.stages[0]["stage_name"], "text": lane_b.stages[0]["translated_text"]} if lane_b.stages else None,
                "replacement_same_section": next(({"section": s["stage_name"], "text": s["translated_text"]}
                                                  for s in lane_b.stages if s["stage_index"] == lane_a.stages[-1]["stage_index"]), None),
            },
            "started_at_utc": self.started_at,
            "generated_at_utc": finished,
            "elapsed_seconds": seconds_between(self.started_at, finished),
            "timeline": self.timeline,
            "passed": passed,
        }
        return report


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", required=True,
                        help="Hosted Agent Responses endpoint, including its API-version query string")
    parser.add_argument("--auth", choices=("none", "azure-cli"), default="azure-cli")
    parser.add_argument("--agent-name", default="lre-steering-agent")
    parser.add_argument("--agent-version", default="unknown")
    parser.add_argument("--work-id", default="owned-agent-live-steering")
    parser.add_argument("--original-target", default="zh-Hans")
    parser.add_argument("--replacement-target", default="zh-Hant")
    parser.add_argument("--crash-after-stage", type=int, default=9)
    parser.add_argument("--steer-after-sections", type=int, default=4)
    parser.add_argument("--stage-delay-ms", type=int, default=300)
    parser.add_argument("--deadline-seconds", type=float, default=300)
    parser.add_argument("--stream-timeout-seconds", type=float, default=180)
    parser.add_argument("--reconnect-timeout-seconds", type=float, default=15)
    parser.add_argument("--poll-interval-seconds", type=float, default=3)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--log-report", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run = Run(args)
    try:
        report = run.run()
    except (RuntimeError, RequestError, OSError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        if args.log_report:
            write_jsonl(args.log_report, run.timeline)
        return 2
    if args.report:
        write_json(args.report, report)
    if args.log_report:
        write_jsonl(args.log_report, report["timeline"])
    failed = [name for name, ok in report["acceptance"].items() if ok is False]
    print(f"RESULT {'PASS' if report['passed'] else 'FAIL'} elapsed={report['elapsed_seconds']}s failed_checks={failed}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
