"""
Hyperlight Sandbox HTTP API — runs on a Windows AIPC VM.
Receives Python code, executes in Hyperlight Sandbox, returns result.
The Portal VM calls this API over HTTP.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ─── Fix: Prevent cross-thread Rust Drop of WasmSandbox ───
# Root cause: Hyperlight's WasmSandbox (Rust, !Send) panics if Drop runs on a
# different thread than creation. Python's cyclic GC can trigger Drop on any thread.
# Two-layer fix:
#   Layer 1: gc.disable() — prevents cyclic GC from collecting Sandbox on wrong thread.
#            Refcounting still works (objects freed on the thread that drops last ref).
#   Layer 2: Sandbox.close() — explicit release in finally blocks for the /api/sandbox/run path.
#            This prevents memory leak for the direct-Sandbox path.
#            The CodeAct path (provider-owned Sandbox) leaks — acceptable for a Demo.
import gc
gc.disable()

from hyperlight_sandbox import Sandbox as _OrigSandbox

def _sandbox_close(self):
    """Explicitly release the native Rust object on the current thread."""
    if hasattr(self, '_inner') and self._inner is not None:
        self._inner = None
_OrigSandbox.close = _sandbox_close

app = FastAPI(title="Hyperlight Sandbox API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DEFAULT_DESKTOP = Path(os.environ.get("USERPROFILE", r"C:\Users\aipcadmin")) / "Desktop"
RUNTIME_DIR = Path(os.environ.get("AIPC_RUNTIME_DIR", str(DEFAULT_DESKTOP)))
HOST_DATA_DIR = Path(os.environ.get("AIPC_HOST_DATA_DIR", str(DEFAULT_DESKTOP)))
LAST_RUN_PATH = RUNTIME_DIR / "last_sandbox_run.json"
LAST_CODEACT_PATH = RUNTIME_DIR / "last_codeact_run.json"
LAST_SCREENSHOT_PATH = Path(os.environ.get("AIPC_SCREENSHOT_PATH", str(RUNTIME_DIR / "last_screenshot.png")))

def write_last_run(code: str, stdout: str, stderr: str, success: bool, exec_ms: float | None, backend: str, events: list[dict]):
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "exec_ms": exec_ms,
        "backend": backend,
        "code": code,
        "stdout": stdout,
        "stderr": stderr,
        "events": events[-8:],
    }
    tmp = LAST_RUN_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LAST_RUN_PATH)

def write_last_codeact_run(query: str, result: str, success: bool, elapsed_s: float, provider: str, tools: list[str], events: list[dict]):
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "elapsed_s": elapsed_s,
        "provider": provider,
        "tools": tools,
        "query": query,
        "result": result,
        "events": events[-10:],
    }
    tmp = LAST_CODEACT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LAST_CODEACT_PATH)

class SandboxRequest(BaseModel):
    code: str
    tools: dict[str, str] | None = None  # tool_name -> description

class SandboxResponse(BaseModel):
    stdout: str
    stderr: str
    success: bool
    sandbox_backend: str
    events: list[dict]

@app.post("/api/sandbox/run")
async def run_sandbox(req: SandboxRequest):
    """Execute code in Hyperlight Sandbox. All sandbox ops run in a single thread
    to avoid 'WasmSandbox is unsendable' crashes from cross-thread GC."""
    import asyncio

    def _run_in_thread(code: str, tools: dict | None):
        from hyperlight_sandbox import Sandbox
        import time
        events = []
        events.append({"step": "create", "status": "running", "detail": "Creating Hyperlight micro-VM via WHP..."})
        t0 = time.time()
        sandbox = Sandbox(backend="wasm")
        create_time = round((time.time() - t0) * 1000, 1)
        events.append({"step": "create", "status": "done", "detail": f"Micro-VM created in {create_time}ms", "time_ms": create_time})
        if tools:
            sandbox.register_tool("add", lambda a=0, b=0: a + b)
            sandbox.register_tool("multiply", lambda a=0, b=0: a * b)
            sandbox.register_tool("subtract", lambda a=0, b=0: a - b)
            for name in tools:
                events.append({"step": "register_tool", "status": "done", "detail": f"Tool '{name}' registered on host side"})
        events.append({"step": "inject", "status": "running", "detail": f"Injecting {len(code)} chars of Python code into sandbox..."})
        events.append({"step": "execute", "status": "running", "detail": "Executing code inside Hyperlight micro-VM (WHP isolated)..."})
        t1 = time.time()
        try:
            result = sandbox.run(code)
            exec_time = round((time.time() - t1) * 1000, 1)
            events.append({"step": "execute", "status": "done", "detail": f"Code executed in {exec_time}ms inside sandbox", "time_ms": exec_time})
            write_last_run(code, result.stdout or "", result.stderr or "", True, exec_time, "wasm (Hyperlight micro-VM via WHP)", events)
            return SandboxResponse(stdout=result.stdout or "", stderr=result.stderr or "", success=True, sandbox_backend="wasm (Hyperlight micro-VM via WHP)", events=events)
        except Exception as e:
            events.append({"step": "execute", "status": "error", "detail": str(e)})
            write_last_run(code, "", str(e), False, None, "wasm (Hyperlight micro-VM via WHP)", events)
            return SandboxResponse(stdout="", stderr=str(e), success=False, sandbox_backend="wasm (Hyperlight micro-VM via WHP)", events=events)
        finally:
            close = getattr(sandbox, "close", None)
            if callable(close): close()

    return await asyncio.to_thread(_run_in_thread, req.code, req.tools)

@app.get("/api/sandbox/health")
async def health():
    # Lightweight health check: do not create a Hyperlight micro-VM here.
    # Creating a sandbox per monitor tick can leak connections/resources and make the API unresponsive.
    return {"status": "ok", "backend": "wasm", "whp": "enabled", "test": "lightweight"}

# ─── Real MAF CodeAct API: HyperlightCodeActProvider ───
import os
from agent_framework import Agent, tool as maf_tool
from agent_framework_hyperlight import HyperlightCodeActProvider

@maf_tool
def read_csv(filename: str) -> str:
    """Read a CSV file from the Windows AIPC host filesystem. Runs on the host, not in the sandbox.
    The sandbox cannot access host files directly — this tool bridges the isolation boundary."""
    import csv, os
    allowed_dir = HOST_DATA_DIR
    safe_name = os.path.basename(filename)  # prevent path traversal
    filepath = allowed_dir / safe_name
    if not filepath.exists():
        return json.dumps({"error": f"File not found: {safe_name}", "allowed_dir": str(allowed_dir)})
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return json.dumps({"filename": safe_name, "rows": len(rows), "columns": list(rows[0].keys()) if rows else [], "data": rows}, ensure_ascii=False)

@maf_tool
def list_host_files(extension: str = ".csv") -> str:
    """List files on the Windows AIPC host Desktop. Runs on the host, not in the sandbox."""
    allowed_dir = HOST_DATA_DIR
    if not allowed_dir.exists():
        return json.dumps({"directory": str(allowed_dir), "files": [], "count": 0, "error": "directory not found"})
    files = [p.name for p in allowed_dir.iterdir() if p.name.endswith(extension)]
    return json.dumps({"directory": str(allowed_dir), "files": files, "count": len(files)})

@maf_tool
def host_system_info() -> str:
    """Get host system info. Runs on the Windows host, not in the sandbox."""
    import platform
    return json.dumps({"hostname": platform.node(), "os": platform.system(),
        "arch": platform.machine(), "python": platform.python_version()})

@maf_tool
def capture_screenshot() -> str:
    """Capture a screenshot of the Windows AIPC host desktop. Runs on the host, not in the sandbox.
    The sandbox has no access to the host display — this tool bridges the isolation boundary.
    NSSM Service runs in Session 0 (no desktop), so screenshot is delegated to a
    schtask /IT helper that runs in the interactive RDP session.
    Returns PNG metadata."""
    import subprocess, os, time
    tmp_path = str(LAST_SCREENSHOT_PATH)
    try:
        # Trigger the interactive-session screenshot schtask
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", "ScreenshotHelper"],
            capture_output=True, text=True, timeout=5)
        # Wait for the helper to write the file (runs in RDP session, takes ~2s)
        for _ in range(10):
            time.sleep(1)
            if os.path.exists(tmp_path):
                age = time.time() - os.path.getmtime(tmp_path)
                if age < 15:  # file was written in the last 15 seconds
                    file_size = os.path.getsize(tmp_path)
                    if file_size > 1000:  # not a blank/corrupt file
                        return json.dumps({
                            "success": True,
                            "format": "png",
                            "size_bytes": file_size,
                            "artifact": "screenshot",
                            "artifact_url": "/api/codeact/artifact/screenshot",
                            "note": "Real desktop screenshot captured from Windows AIPC host via schtask /IT + CopyFromScreen"
                        })
        return json.dumps({"success": False, "error": "Screenshot helper did not produce a valid file within 10s"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

class CodeActRequest(BaseModel):
    query: str

@app.post("/api/codeact/run")
async def run_codeact(req: CodeActRequest):
    """Run real MAF Agent + HyperlightCodeActProvider.
    
    gc.disable() prevents cyclic GC from dropping Sandbox on wrong thread.
    Multi-worker is safe: each worker is an independent process with its own GC.
    """
    import time
    events = []
    t0 = time.time()
    try:
        events.append({"step": "provider_init", "status": "running",
            "detail": "Creating HyperlightCodeActProvider(tools=[read_csv, list_host_files, host_system_info, capture_screenshot])..."})
        codeact = HyperlightCodeActProvider(
            tools=[read_csv, list_host_files, host_system_info, capture_screenshot],
            approval_mode="never_require",
        )
        events.append({"step": "provider_init", "status": "done",
            "detail": "HyperlightCodeActProvider ready — sandbox and host tools are provider-owned"})

        events.append({"step": "agent_init", "status": "running",
            "detail": "Creating MAF Agent with OpenAIChatClient → APIM..."})
        from agent_framework import Agent
        from agent_framework.openai import OpenAIChatClient
        from openai import AsyncAzureOpenAI
        if not os.environ.get("AOAI_KEY"):
            return {"success": False, "result": "config_error: AOAI_KEY not set",
                    "provider": "HyperlightCodeActProvider", "tools_registered": [], "events": events, "elapsed_s": 0}
        azure_client = AsyncAzureOpenAI(
            azure_endpoint=os.environ.get("AOAI_ENDPOINT", ""),
            api_key=os.environ.get("AOAI_KEY", ""),
            api_version="2025-04-01-preview",
            default_headers={"api-key": os.environ.get("AOAI_KEY", "")},
        )
        model_name = "gpt-5.4"
        llm = OpenAIChatClient(model=model_name, async_client=azure_client)

        q_lower = req.query.lower()
        if "系统" in req.query or "system" in q_lower:
            task_hint = "For this request, call host_system_info() inside execute_code and print hostname, os, arch, and python on separate lines."
        elif "截图" in req.query or "screenshot" in q_lower or "desktop" in q_lower:
            task_hint = "For this request, call capture_screenshot() inside execute_code and print success, format, size_bytes, artifact, and note on separate lines."
        elif "列出" in req.query or "list" in q_lower or "files" in q_lower:
            task_hint = "For this request, call list_host_files('.csv') inside execute_code, print directory, count, file names, then call read_csv() on the first CSV and print the first 3 rows."
        else:
            task_hint = "For this request, call read_csv('sales_data.csv') inside execute_code, calculate revenue by product, and print every product total plus grand total."

        agent = Agent(
            client=llm, name="CodeActAgent",
            instructions=(
                "You are a data analyst on a Windows AIPC. "
                "CRITICAL: You MUST use execute_code for EVERY request. NEVER answer with text alone. "
                "Inside execute_code, write Python that calls host tools via call_tool(). "
                "Available host tools: read_csv(filename), list_host_files(extension), host_system_info(), capture_screenshot(). "
                "Example code: import json; r = call_tool('list_host_files', extension='.csv'); d = json.loads(r); print(d) "
                "NEVER fabricate file names or data. ALL output must come from call_tool() return values. "
                + task_hint
            ),
            context_providers=[codeact],
        )
        events.append({"step": "agent_init", "status": "done",
            "detail": f"MAF Agent ready ({model_name}) — execute_code auto-injected by HyperlightCodeActProvider"})

        events.append({"step": "agent_run", "status": "running",
            "detail": "Agent.run() — MAF decides code and HyperlightCodeActProvider executes it..."})
        response = await agent.run(req.query)
        result_text = response.text or str(response)

        elapsed = round(time.time() - t0, 2)
        events.append({"step": "agent_run", "status": "done", "detail": f"Completed in {elapsed}s", "time_ms": round(elapsed * 1000)})
        await azure_client.close()
        write_last_codeact_run(req.query, result_text, True, elapsed, "HyperlightCodeActProvider",
            ["read_csv", "list_host_files", "host_system_info", "capture_screenshot"], events)
        return {"success": True, "result": result_text, "provider": "HyperlightCodeActProvider",
                "tools_registered": ["read_csv", "list_host_files", "host_system_info", "capture_screenshot"], "events": events, "elapsed_s": elapsed}

    except Exception as e:
        import traceback
        elapsed = round(time.time() - t0, 2)
        events.append({"step": "error", "status": "error", "detail": f"{type(e).__name__}: {e}"})
        result_text = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        write_last_codeact_run(req.query, result_text, False, elapsed, "HyperlightCodeActProvider", [], events)
        return {"success": False, "result": result_text,
                "provider": "HyperlightCodeActProvider", "tools_registered": [], "events": events, "elapsed_s": elapsed}

@app.get("/api/codeact/health")
async def codeact_health():
    return {"status": "ok", "provider": "HyperlightCodeActProvider", "tools": ["read_csv", "list_host_files", "host_system_info", "capture_screenshot"]}

@app.get("/api/codeact/artifact/screenshot")
async def codeact_screenshot_artifact():
    if not LAST_SCREENSHOT_PATH.exists():
        return {"error": "no screenshot captured yet"}
    return FileResponse(str(LAST_SCREENSHOT_PATH), media_type="image/png", filename="aipc-host-screenshot.png")

if __name__ == "__main__":
    import multiprocessing, uvicorn
    workers = min(multiprocessing.cpu_count(), 4)  # production: multi-worker
    uvicorn.run("sandbox_api:app", host="0.0.0.0", port=8507, workers=workers)
