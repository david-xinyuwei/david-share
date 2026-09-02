#!/usr/bin/env python3
"""Drive the human-approval recovery scenario against the approval-gate Agent.

The job is the shared 30-section translation. The Agent translates a sample batch,
suspends the resilient multi-turn task for human review, and must survive the loss
of its process while it waits. The client then plays the reviewer: it approves on
whichever instance is alive and checks that the remaining sections finish on it,
that the task identity is unchanged, and that the reviewed sample was not re-run.

Two ways to run it:

* ``--local`` starts the Agent from ``src/resilient-approval-gate`` on a free port,
  observes the real ``os._exit(86)``, and starts a second host process against the
  same state root. This gives exact process-down and process-up timestamps.
* ``--endpoint <invocations endpoint>`` runs against the Foundry-hosted Agent, where
  the platform replaces the instance; the client probes until a different process
  identity answers.

Only SHA-256 digests of task and process identifiers are written to disk.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent
AGENT_SOURCE = ROOT / "src" / "resilient-approval-gate"
STAGE_COUNT = 30
INJECTED_EXIT_CODE = 86
NOT_READY_STATUSES = {404, 424, 500, 502, 503, 504}


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


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


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


def invocations_url(endpoint: str, session_id: str, invocation_id: str | None = None) -> str:
    parsed = urllib.parse.urlsplit(endpoint)
    path = parsed.path.rstrip("/")
    if invocation_id:
        path = f"{path}/{urllib.parse.quote(invocation_id, safe='')}"
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    # The Invocations protocol pins a job to a session through this query parameter.
    query["agent_session_id"] = session_id
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, urllib.parse.urlencode(query), "")
    )


def request_json(method: str, url: str, body: dict[str, Any] | None, token: str | None,
                 timeout_seconds: float = 30) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return response.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        raise RequestError(error.code, error.read().decode("utf-8", errors="replace")) from error


def approval_checks(
    *,
    process_a: str,
    process_b: str,
    task_sha: str,
    output: dict[str, Any],
    results: list[dict[str, Any]],
    sample_hashes: list[str],
) -> dict[str, bool]:
    """The acceptance rules; every rule must hold for the run to pass."""
    sample = results[: len(sample_hashes)]
    remaining = results[len(sample_hashes):]
    return {
        "review_gate_reached": bool(sample_hashes) and bool(task_sha),
        "process_replaced": bool(process_b) and process_b != process_a,
        "task_identity_unchanged": bool(task_sha) and output.get("task_id_sha256") == task_sha,
        "resolved_as_completed": output.get("status") == "resolved" and output.get("outcome") == "completed",
        "all_sections_present_once": [item.get("stage_index") for item in results] == list(range(STAGE_COUNT)),
        "sample_result_hashes_unchanged": [item.get("stage_result_sha256") for item in sample] == sample_hashes,
        "sample_translated_on_process_a": bool(sample) and {item.get("process_sha256") for item in sample} == {process_a},
        "remaining_translated_on_process_b": bool(remaining) and {item.get("process_sha256") for item in remaining} == {process_b},
        "every_section_has_text": bool(results) and all((item.get("translated_text") or "").strip() for item in results),
    }


class LocalHost:
    """The Agent process under test when running locally."""

    def __init__(self, state_root: Path, log_path: Path, port: int) -> None:
        self.state_root = state_root
        self.log_path = log_path
        self.port = port
        self.process: subprocess.Popen[bytes] | None = None
        self.log = None

    def start(self) -> None:
        self.log = self.log_path.open("ab")
        env = {
            **os.environ,
            "AGENTSERVER_STATE_ROOT": str(self.state_root),
            "LRE_ENABLE_FAULT_INJECTION": "true",
            "PORT": str(self.port),
        }
        # A local run must call Translator as the signed-in developer. On an Azure
        # VM, DefaultAzureCredential would otherwise pick the VM's managed identity
        # first, which normally has no role on the Translator resource.
        env.setdefault("AZURE_TOKEN_CREDENTIALS", "dev")
        self.process = subprocess.Popen(
            [sys.executable, "main.py"], cwd=AGENT_SOURCE, env=env,
            stdout=self.log, stderr=subprocess.STDOUT,
        )

    def wait_exit(self, timeout: float) -> int:
        assert self.process is not None
        code = self.process.wait(timeout)
        if self.log is not None:
            self.log.close()
        return code

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log is not None and not self.log.closed:
            self.log.close()


class Run:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.token = azure_cli_token() if (not args.local and args.auth == "azure-cli") else None
        self.timeline: list[dict[str, Any]] = []
        self.started_at = utc_now()
        self.session_id = args.session_id or f"approval-{secrets.token_hex(6)}"
        self.emitted: set[int] = set()
        self.endpoint = args.endpoint

    def event(self, name: str, **fields: Any) -> None:
        row = {"at_utc": utc_now(), "event": name, "work_id": self.args.work_id,
               "source": "client_poll", **fields}
        self.timeline.append(row)
        detail = " ".join(f"{key}={value}" for key, value in fields.items()
                          if key not in {"task_id_sha256", "process_instance_sha256"})
        print(f"[{row['at_utc']}] {name} {detail}".rstrip(), flush=True)

    def post(self, payload: dict[str, Any], timeout: float = 30) -> tuple[int, dict[str, Any]]:
        return request_json("POST", invocations_url(self.endpoint, self.session_id), payload,
                            self.token, timeout)

    def post_when_ready(self, payload: dict[str, Any], deadline_seconds: float) -> tuple[int, dict[str, Any]]:
        deadline = time.monotonic() + deadline_seconds
        last: str = ""
        while time.monotonic() < deadline:
            try:
                return self.post(payload, timeout=15)
            except RequestError as error:
                if error.status not in NOT_READY_STATUSES:
                    raise
                last = f"HTTP {error.status}"
            except (OSError, TimeoutError) as error:
                last = type(error).__name__
            time.sleep(self.args.poll_interval_seconds)
        raise RuntimeError(f"agent did not accept {payload.get('action')} in time: {last}")

    def surface_sections(self, results: list[dict[str, Any]]) -> None:
        for item in results:
            index = item.get("stage_index")
            if not isinstance(index, int) or index in self.emitted:
                continue
            self.emitted.add(index)
            self.event("checkpoint_committed", checkpoint=item.get("stage_name"), batch=item.get("batch"),
                       entry_mode=item.get("entry_mode"),
                       process_instance_sha256=item.get("process_sha256"))

    def turn(self, payload: dict[str, Any], deadline_seconds: float) -> dict[str, Any]:
        """Submit one invocation and poll it to completion, surfacing sections as they land."""
        status, accepted = self.post_when_ready(payload, deadline_seconds)
        invocation_id = str(accepted.get("invocation_id") or "")
        if status != 202 or not invocation_id:
            raise RuntimeError(f"{payload.get('action')} did not return 202 with an invocation id (HTTP {status})")
        self.event("invocation_accepted", action=payload.get("action"),
                   invocation_id_sha256=sha256_text(invocation_id))
        url = invocations_url(self.endpoint, self.session_id, invocation_id)
        deadline = time.monotonic() + deadline_seconds
        last_status = ""
        while time.monotonic() < deadline:
            try:
                _, state = request_json("GET", url, None, self.token, 30)
            except RequestError as error:
                if error.status in NOT_READY_STATUSES:
                    time.sleep(self.args.poll_interval_seconds)
                    continue
                raise
            self.surface_sections((state.get("progress") or {}).get("results") or [])
            last_status = str(state.get("status") or "")
            if last_status == "completed" and isinstance(state.get("output"), dict):
                return state
            if last_status == "failed":
                raise RuntimeError(f"{payload.get('action')} failed inside the Agent: {state.get('error')}")
            time.sleep(self.args.poll_interval_seconds)
        raise RuntimeError(
            f"invocation for {payload.get('action')} did not complete in time (last status: {last_status or 'none'})"
        )

    def run(self) -> dict[str, Any]:
        args = self.args
        host: LocalHost | None = None
        temporary: tempfile.TemporaryDirectory[str] | None = None
        try:
            if args.local:
                temporary = tempfile.TemporaryDirectory(prefix="lra-approval-")
                root = Path(temporary.name)
                (root / "state").mkdir()
                host_log = Path(args.host_log) if args.host_log else root / "agent.log"
                host = LocalHost(root / "state", host_log, free_port())
                self.endpoint = f"http://127.0.0.1:{host.port}/invocations"
                host.start()
                self.event("process_started", process_role="A", endpoint_class="local-agentserver")
            return self.execute(host)
        finally:
            if host is not None:
                host.stop()
            if temporary is not None:
                temporary.cleanup()

    def execute(self, host: LocalHost | None) -> dict[str, Any]:
        args = self.args
        self.event("request_started", action="start", target=args.target, sample_size=args.sample_size,
                   session_id_sha256=sha256_text(self.session_id))
        started = self.turn({"action": "start", "target": args.target, "sample_size": args.sample_size,
                             "stage_delay_ms": args.stage_delay_ms}, args.deadline_seconds)
        output = started.get("output") or {}
        sample = (started.get("progress") or {}).get("results") or []
        process_a = str(output.get("process_sha256") or "")
        task_sha = str(output.get("task_id_sha256") or "")
        if output.get("status") != "awaiting_review" or len(sample) != args.sample_size or not process_a or not task_sha:
            raise RuntimeError(f"the sample did not reach the review gate: {output}")
        sample_hashes = [str(item.get("stage_result_sha256") or "") for item in sample]
        self.event("review_gate_reached", sample_sections=len(sample), task_id_sha256=task_sha,
                   process_instance_sha256=process_a)

        # Lose the process while the review is pending.
        self.event("fault_injected", mode="hard_process_exit", exit_code=INJECTED_EXIT_CODE,
                   process_instance_sha256=process_a)
        try:
            self.post({"action": "inject_process_loss"}, timeout=30)
        except (RequestError, OSError, TimeoutError):
            pass
        if host is not None:
            exit_code = host.wait_exit(30)
            self.event("process_exited", process_role="A", exit_code=exit_code, process_instance_sha256=process_a)
            if exit_code != INJECTED_EXIT_CODE:
                raise RuntimeError(f"process A exited with {exit_code}, expected {INJECTED_EXIT_CODE}")
            host.start()
            self.event("process_started", process_role="B", endpoint_class="local-agentserver")
        else:
            self.event("process_lost", detail="instance loss requested; the platform must replace it",
                       process_instance_sha256=process_a)

        deadline = time.monotonic() + args.deadline_seconds
        process_b = ""
        while time.monotonic() < deadline and not process_b:
            try:
                status, probe = self.post({"action": "probe_instance"}, timeout=15)
                candidate = str(probe.get("process_sha256") or "") if status == 200 else ""
                if candidate and candidate != process_a:
                    process_b = candidate
                    break
            except RequestError as error:
                if error.status not in NOT_READY_STATUSES:
                    raise
            except (OSError, TimeoutError):
                pass
            time.sleep(args.poll_interval_seconds)
        if not process_b:
            raise RuntimeError("no replacement instance answered with a new process identity")
        self.event("replacement_instance_observed", process_role="B", process_instance_sha256=process_b)

        # The reviewer's decision lands on the replacement instance.
        self.event("approval_submitted", decision="approve_review", approver=args.approver,
                   task_id_sha256=task_sha, process_instance_sha256=process_b)
        final = self.turn({"action": "approve_review", "approver": args.approver}, args.deadline_seconds)
        output = final.get("output") or {}
        results = (final.get("progress") or {}).get("results") or []
        self.event("terminal_observed", status=output.get("status"), outcome=output.get("outcome"),
                   sections=len(results), task_id_sha256=str(output.get("task_id_sha256") or ""),
                   process_instance_sha256=str(output.get("process_sha256") or ""))

        checks = approval_checks(
            process_a=process_a,
            process_b=process_b,
            task_sha=task_sha,
            output=output,
            results=results,
            sample_hashes=sample_hashes,
        )
        passed = all(checks.values())
        finished = utc_now()
        return {
            "schema_version": 1,
            "evidence_type": "owned-hosted-agent-approval",
            "endpoint_class": "local-agentserver" if host is not None else "foundry-hosted-agent",
            "work_id": args.work_id,
            "deployment": {"agent_name": args.agent_name, "version": args.agent_version},
            "request": {"target": args.target, "sample_size": args.sample_size,
                        "stage_delay_ms": args.stage_delay_ms, "fault_injection_requested": True},
            "task_id_sha256": task_sha,
            "session_id_sha256": sha256_text(self.session_id),
            "acceptance": {
                **checks,
                "process_instance_sha256": [process_a, process_b],
                "process_instance_count": len({process_a, process_b}),
                "sample_sections": len(sample_hashes),
                "remaining_sections": len(results) - len(sample_hashes),
                "total_sections": len(results),
                "status": output.get("status"),
                "outcome": output.get("outcome"),
            },
            "samples": {
                "last_sample_section": {"section": sample[-1]["stage_name"], "text": sample[-1]["translated_text"]},
                "first_remaining_section": {"section": results[len(sample_hashes)]["stage_name"],
                                            "text": results[len(sample_hashes)]["translated_text"]}
                if len(results) > len(sample_hashes) else None,
            },
            "started_at_utc": self.started_at,
            "generated_at_utc": finished,
            "elapsed_seconds": seconds_between(self.started_at, finished),
            "timeline": self.timeline,
            "passed": passed,
        }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true", help="start the Agent from src/ and replace its process locally")
    mode.add_argument("--endpoint", help="Hosted Agent Invocations endpoint, including its API-version query string")
    parser.add_argument("--auth", choices=("none", "azure-cli"), default="azure-cli")
    parser.add_argument("--agent-name", default="lre-approval-gate")
    parser.add_argument("--agent-version", default="unknown")
    parser.add_argument("--work-id", default="owned-agent-approval-recovery")
    parser.add_argument("--session-id", help="job session; generated when omitted")
    parser.add_argument("--target", default="zh-Hans")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--stage-delay-ms", type=int, default=300)
    parser.add_argument("--approver", default="repository reviewer")
    parser.add_argument("--deadline-seconds", type=float, default=300)
    parser.add_argument("--poll-interval-seconds", type=float, default=1)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--log-report", type=Path)
    parser.add_argument("--host-log", type=Path,
                        help="--local only: keep the Agent process output here instead of the temporary directory")
    args = parser.parse_args(argv)
    if args.local:
        for name in ("LRA_TRANSLATOR_ENDPOINT", "LRA_TRANSLATOR_RESOURCE_ID"):
            if not os.environ.get(name):
                parser.error(f"--local needs {name} in the environment so the Agent can call Translator")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run = Run(args)
    try:
        report = run.run()
    except (RuntimeError, RequestError, OSError, subprocess.TimeoutExpired) as error:
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
