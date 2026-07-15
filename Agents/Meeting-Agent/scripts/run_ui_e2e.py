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
UI_URL = "http://127.0.0.1:4173"


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    processes: list[tuple[subprocess.Popen[bytes], object]] = []
    try:
        agent_log = (RUNTIME_DIR / "agent.log").open("wb")
        agent_environment = {
            **os.environ,
            "PORT": "18088",
            "OTEL_SDK_DISABLED": "true",
            "MEETING_AGENT_ANALYZER": "offline-contract",
            "MEETING_AGENT_ENABLE_OFFLINE_CONTRACT": "1",
            "MEETING_AGENT_SESSION_HOME": str(RUNTIME_DIR / "session"),
        }
        agent = subprocess.Popen(
            [sys.executable, "main.py"],
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
            "MEETING_AGENT_LOCAL_AGENT_URL": AGENT_URL,
            "MEETING_AGENT_LOCAL_SESSION_HOME": str(RUNTIME_DIR / "session"),
            "MEETING_AGENT_NAME": "meeting-agent",
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

        completed = subprocess.run(
            [_playwright_command(), "test", "--reporter=json"],
            cwd=UI_DIR,
            env={**os.environ, "MEETING_AGENT_UI_URL": UI_URL},
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
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
        if len(results) != 4 or any(result["status"] != "passed" for result in results):
            print(completed.stdout, file=sys.stderr)
            _print_logs()
            return 1
        (RUNTIME_DIR / "playwright.json").write_text(completed.stdout, encoding="utf-8")
        print("PLAYWRIGHT_E2E_PASS tests=4 projects=desktop,mobile")
        return 0
    finally:
        for process, stream in reversed(processes):
            _stop(process)
            stream.close()


def _wait_for(url: str, process: subprocess.Popen[bytes], label: str) -> None:
    deadline = time.monotonic() + 30
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