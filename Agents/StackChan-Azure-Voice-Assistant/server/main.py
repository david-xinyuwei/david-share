"""Azure XiaoZhi Server — FastAPI entry point.

Implements the XiaoZhi WebSocket protocol so a StackChan device
(or any xiaozhi-esp32 compatible device) can connect and use
Azure Speech + Azure OpenAI as its cloud backend.

Usage:
    python main.py                      # dev
    uvicorn main:app --host 0.0.0.0     # production
"""
import logging
import asyncio
import base64
import io
import wave
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware

import config
from xiaozhi_handler import XiaoZhiSession
from azure_speech import recognize_speech, synthesize_speech
from azure_llm import chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Azure XiaoZhi Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_HERE = Path(__file__).resolve().parent

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ASYNC_TIMEOUT = 30  # seconds


@app.get("/api/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "version": "0.1.0",
        "speech_region": config.AZURE_SPEECH_REGION,
    })


@app.get("/", response_class=HTMLResponse)
async def web_ui():
    """Serve the demo recording UI."""
    html_path = _HERE / "static" / "index.html"
    try:
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HTMLResponse("<h1>Web demo not available</h1>", status_code=404)


@app.post("/api/voice")
async def voice_turn(audio: UploadFile = File(...)):
    """Browser-friendly endpoint: upload WAV → STT → LLM → TTS → return.

    Returns JSON with text fields + base64-encoded PCM audio.
    """
    wav_bytes = await audio.read()

    # ── upload guards ──
    if len(wav_bytes) > MAX_UPLOAD_BYTES:
        return JSONResponse({"error": "file too large"}, status_code=413)

    duration_sec = 0.0
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            duration_sec = wf.getnframes() / float(wf.getframerate() or 16000)
    except Exception:
        pass
    if 0 < duration_sec < 0.45:
        return JSONResponse({"stt": "", "reply": "", "emotion": "neutral", "audio": "", "reason": "audio_too_short"})

    # ── STT (with timeout) ──
    try:
        stt_text = await asyncio.wait_for(asyncio.to_thread(recognize_speech, wav_bytes), timeout=ASYNC_TIMEOUT)
    except asyncio.TimeoutError:
        return JSONResponse({"stt": "", "reply": "", "emotion": "neutral", "audio": "", "reason": "stt_timeout"})
    if not stt_text:
        return JSONResponse({"stt": "", "reply": "", "emotion": "neutral", "audio": "", "reason": "stt_empty"})

    # ── LLM (per-request history, no global shared state) ──
    history: list[dict] = []  # demo: no cross-request memory
    try:
        reply, emotion = await asyncio.wait_for(asyncio.to_thread(chat, stt_text, history), timeout=ASYNC_TIMEOUT)
    except asyncio.TimeoutError:
        return JSONResponse({"stt": stt_text, "reply": "", "emotion": "neutral", "audio": "", "reason": "llm_timeout"})

    # ── TTS (with timeout) ──
    try:
        tts_pcm = await asyncio.wait_for(asyncio.to_thread(synthesize_speech, reply), timeout=ASYNC_TIMEOUT)
    except asyncio.TimeoutError:
        tts_pcm = b""
    audio_b64 = base64.b64encode(tts_pcm).decode() if tts_pcm else ""

    return JSONResponse({
        "stt": stt_text,
        "reply": reply,
        "emotion": emotion,
        "audio": audio_b64,
        "audio_sample_rate": 24000,
        "reason": "ok",
    })


@app.websocket("/xiaozhi/v1/")
async def xiaozhi_ws(ws: WebSocket):
    """XiaoZhi WebSocket endpoint.

    Device connects here with headers:
      Authorization: Bearer <token>
      Protocol-Version: 1
      Device-Id: <MAC>
      Client-Id: <UUID>
    """
    await ws.accept()

    device_id = ws.headers.get("device-id", "unknown")
    proto_ver = ws.headers.get("protocol-version", "1")
    logger.info("Device connected: %s  proto=%s", device_id, proto_ver)

    session = XiaoZhiSession(ws, device_id=device_id)
    try:
        await session.run()
    except WebSocketDisconnect:
        logger.info("Device disconnected: %s", device_id)
    except Exception as exc:
        logger.error("Unexpected error for %s: %s", device_id, exc)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info",
    )
