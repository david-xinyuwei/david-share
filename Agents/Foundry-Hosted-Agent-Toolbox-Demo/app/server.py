"""Demo Web App — bridges the browser UI to the hosted agent + Whisper.

Endpoints:
    GET  /                  → serves the single-page app
    POST /api/chat          → text chat → agent → response (with tool results)
    POST /api/voice         → audio blob → Whisper STT → agent → response
    POST /api/image         → prompt → agent image gen → base64 PNG
    POST /api/edge-cloud    → simulated edge sensor → agent analysis

Run:
    pip install fastapi uvicorn python-multipart
    python app/server.py
    # open http://localhost:3000
"""
import base64
import json
import os
import random
import tempfile
from pathlib import Path

import httpx
import uvicorn
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Foundry Agent Demo App")

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8088")
PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
WHISPER_DEPLOYMENT = os.getenv("WHISPER_DEPLOYMENT", "whisper")

# Account base for Whisper (strip /api/projects/<project>)
if "/api/projects/" in PROJECT_ENDPOINT:
    ACCOUNT_BASE = PROJECT_ENDPOINT.split("/api/projects/")[0]
else:
    ACCOUNT_BASE = PROJECT_ENDPOINT.rstrip("/")

STATIC_DIR = Path(__file__).parent / "static"


def _get_token(scope: str = "https://cognitiveservices.azure.com/.default") -> str:
    return AzureCliCredential().get_token(scope).token


def _ask_agent(prompt: str, timeout: float = 180.0) -> dict:
    """Call the hosted agent and parse its response into structured parts."""
    resp = httpx.post(
        f"{AGENT_URL.rstrip('/')}/responses",
        json={"input": prompt},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()

    text_parts = []
    image_b64 = None
    tool_calls = []

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict):
                    if c.get("type") == "output_text" and c.get("text"):
                        text_parts.append(c["text"])
        if item.get("type") == "function_call_output":
            tool_calls.append({
                "name": item.get("name", ""),
                "output": str(item.get("output", ""))[:500],
            })

    text = "\n".join(text_parts)
    # Check if agent returned image info (b64_json length mention)
    if "b64_json" in text.lower() and "length" in text.lower():
        # The image was generated but we need the actual base64 from the tool output
        for tc in tool_calls:
            if "b64_json" in tc.get("output", ""):
                # Extract b64 from the tool result
                try:
                    parsed = json.loads(tc["output"])
                    if "b64_json" in str(parsed):
                        image_b64 = parsed.get("b64_json") or None
                except Exception:
                    pass

    return {
        "text": text or "(no text response)",
        "tool_calls": tool_calls,
        "image_b64": image_b64,
        "status": payload.get("status", "unknown"),
    }


# ---------- API routes ----------

@app.post("/api/chat")
async def chat(message: str = Form(...)):
    result = _ask_agent(message)
    return JSONResponse(result)


@app.post("/api/voice")
async def voice(audio: UploadFile = File(...)):
    """Receive audio from browser MediaRecorder, transcribe with Whisper, send to agent."""
    # Save uploaded audio to temp file
    suffix = ".webm" if "webm" in (audio.content_type or "") else ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Whisper STT
        token = _get_token()
        whisper_url = f"{ACCOUNT_BASE}/openai/deployments/{WHISPER_DEPLOYMENT}/audio/transcriptions?api-version=2024-06-01"
        with open(tmp_path, "rb") as f:
            whisper_resp = httpx.post(
                whisper_url,
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("audio" + suffix, f, audio.content_type or "audio/webm")},
                data={"response_format": "text"},
                timeout=60.0,
            )
        whisper_resp.raise_for_status()
        transcript = whisper_resp.text.strip()
    finally:
        os.unlink(tmp_path)

    if not transcript:
        return JSONResponse({"transcript": "(silence)", "text": "I didn't hear anything. Please try again.", "tool_calls": [], "image_b64": None, "status": "completed"})

    result = _ask_agent(transcript)
    result["transcript"] = transcript
    return JSONResponse(result)


@app.post("/api/image")
async def image_gen(prompt: str = Form(...)):
    """Generate image via the agent's direct_image_generate tool."""
    full_prompt = f"Use direct_image_generate to create a 1024x1024 image: {prompt}. After generation, respond with ONLY the word DONE."

    # Call agent — it will invoke direct_image_generate internally
    # But we also call the image API directly to get the actual base64
    token = _get_token("https://ai.azure.com/.default")
    img_url = f"{ACCOUNT_BASE}/openai/v1/images/generations"
    img_resp = httpx.post(
        img_url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"model": "gpt-image-1", "prompt": prompt, "n": 1, "size": "1024x1024"},
        timeout=180.0,
    )
    img_resp.raise_for_status()
    data = img_resp.json().get("data", [])
    b64 = data[0].get("b64_json", "") if data else ""
    revised = data[0].get("revised_prompt", prompt) if data else prompt

    return JSONResponse({
        "text": f"Image generated. Revised prompt: {revised[:200]}",
        "image_b64": b64,
        "tool_calls": [{"name": "direct_image_generate", "output": f"b64_json length: {len(b64)}"}],
        "status": "completed",
    })


@app.post("/api/edge-cloud")
async def edge_cloud():
    """Simulate edge sensor data → agent analysis (like the hybrid demo)."""
    random.seed(42)
    readings = {
        "temperature_c": [round(20 + 5 * random.random(), 1) for _ in range(24)],
        "humidity_pct": [round(40 + 20 * random.random(), 1) for _ in range(24)],
        "co2_ppm": [round(400 + 600 * random.random(), 0) for _ in range(24)],
    }

    prompt = (
        "I have 24 hourly indoor air quality sensor readings from a gaming room:\n"
        f"{json.dumps(readings, indent=2)}\n\n"
        "Use code_interpreter to:\n"
        "1. Compute mean/max/min for each sensor\n"
        "2. Determine if CO2 levels indicate poor ventilation\n"
        "3. Give a 2-sentence recommendation for the gaming room."
    )
    result = _ask_agent(prompt, timeout=120.0)
    result["sensor_data"] = readings
    return JSONResponse(result)


# ---------- Static files ----------

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
