"""Run the real local Hosted Agent and browser UI for Playwright E2E."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"
RUNTIME_DIR = ROOT / "runtime" / "ui-e2e"
AGENT_URL = "http://127.0.0.1:18088"
UI_URL = "http://127.0.0.1:4174"


def main() -> int:
    mode = os.environ.get("MEETING_AGENT_E2E_MODE", "fixture")
    if mode not in {"fixture", "live"}:
        raise RuntimeError("MEETING_AGENT_E2E_MODE must be fixture or live")
    live = mode == "live"
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_DIR / "playwright.json").unlink(missing_ok=True)
    processes: list[tuple[subprocess.Popen[bytes], object]] = []
    try:
        agent_log = (RUNTIME_DIR / "agent.log").open("wb")
        agent_environment = {
            **os.environ,
            "PORT": "18088",
            "OTEL_EXPERIMENTAL_RESOURCE_DETECTORS": "service_instance,otel",
            "OTEL_SDK_DISABLED": "true",
            "MEETING_AGENT_SESSION_HOME": str(RUNTIME_DIR / "session"),
            "PYTHONPATH": str(ROOT / "src"),
            "MEETING_AGENT_E2E_MODE": mode,
        }
        if not live:
            for name in (
                "MANAGED_AGENT_ENDPOINT",
                "MANAGED_AGENT_NAME",
                "MANAGED_AGENT_VERSION",
                "MANAGED_AGENT_CREDENTIAL",
                "AZURE_CLIENT_ID",
                "AZURE_CLIENT_SECRET",
                "AZURE_TENANT_ID",
            ):
                agent_environment.pop(name, None)
        agent = subprocess.Popen(
            [sys.executable, "-m", "tests.e2e_server"],
            cwd=ROOT,
            env=agent_environment,
            stdin=subprocess.DEVNULL,
            stdout=agent_log,
            stderr=subprocess.STDOUT,
            **_process_group_options(),
        )
        processes.append((agent, agent_log))
        _wait_for(f"{AGENT_URL}/readiness", agent, "Hosted Agent")

        ui_log = (RUNTIME_DIR / "ui.log").open("wb")
        ui_environment = {
            **os.environ,
            "PORT": "4174",
            "MEETING_AGENT_LOCAL_AGENT_URL": AGENT_URL,
            "MEETING_AGENT_LOCAL_SESSION_HOME": str(RUNTIME_DIR / "session"),
            "MEETING_AGENT_NAME": os.environ.get(
                "MANAGED_AGENT_NAME", "true-meeting-managed-agent"
            ),
            "MEETING_AGENT_RUNTIME_MODE": "managed",
            "MEETING_AGENT_RUNTIME_ATTESTATION": (
                "live-managed" if live else "test-fixture"
            ),
            "MANAGED_AGENT_VERSION": os.environ.get(
                "MANAGED_AGENT_VERSION", "test-fixture"
            ),
            "MANAGED_AGENT_MODEL": os.environ.get(
                "MANAGED_AGENT_MODEL", "test-fixture"
            ),
        }
        ui = subprocess.Popen(
            [_npm_command(), "start"],
            cwd=UI_DIR,
            env=ui_environment,
            stdin=subprocess.DEVNULL,
            stdout=ui_log,
            stderr=subprocess.STDOUT,
            **_process_group_options(),
        )
        processes.append((ui, ui_log))
        _wait_for(f"{UI_URL}/api/health", ui, "UI BFF")

        playwright_arguments = [
            _playwright_command(),
            "test",
            "--reporter=json",
            "--workers=1",
        ]
        if live:
            playwright_arguments.extend(("live-managed.spec.ts", "--project=desktop"))
        try:
            completed = subprocess.run(
                playwright_arguments,
                cwd=UI_DIR,
                env={
                    **os.environ,
                    "MEETING_AGENT_UI_URL": UI_URL,
                    "MEETING_AGENT_E2E_MODE": mode,
                },
                check=False,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            _print_logs()
            raise
        if completed.returncode:
            print(completed.stdout, file=sys.stderr)
            print(completed.stderr, file=sys.stderr)
            _print_logs()
            return completed.returncode
        report = json.loads(completed.stdout)
        results = [
            result
            for suite in report["suites"]
            for spec in suite["specs"]
            for test in spec["tests"]
            for result in test["results"]
        ]
        expected_results = 1 if live else 4
        if len(results) != expected_results or any(
            result["status"] != "passed" for result in results
        ):
            print(completed.stdout, file=sys.stderr)
            _print_logs()
            return 1
        (RUNTIME_DIR / "playwright.json").write_text(completed.stdout, encoding="utf-8")
        if live:
            print("PLAYWRIGHT_LIVE_MANAGED_PASS tests=1 project=desktop")
        else:
            print("PLAYWRIGHT_E2E_PASS tests=4 projects=desktop,mobile")
        return 0
    finally:
        for process, stream in reversed(processes):
            _stop(process)
            stream.close()


def _wait_for(url: str, process: subprocess.Popen[bytes], label: str) -> None:
    deadline = time.monotonic() + 90
    last_error = "not ready"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            _print_logs()
            raise RuntimeError(f"{label} exited before readiness (code {process.returncode})")
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, URLError) as error:
            last_error = str(error)
        time.sleep(0.2)
    _print_logs()
    raise RuntimeError(f"{label} readiness timed out: {last_error}")


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=10,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _print_logs() -> None:
    for name in ("agent.log", "ui.log"):
        path = RUNTIME_DIR / name
        if path.is_file():
            print(f"--- {name} ---", file=sys.stderr)
            print(path.read_text(encoding="utf-8", errors="replace")[-8_000:], file=sys.stderr)


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _playwright_command() -> str:
    executable = "playwright.cmd" if os.name == "nt" else "playwright"
    return str(UI_DIR / "node_modules" / ".bin" / executable)


def _process_group_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


if __name__ == "__main__":
    raise SystemExit(main())