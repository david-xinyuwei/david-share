"""XiaoZhi WebSocket protocol handler.

Implements the device ↔ server session lifecycle:
  hello handshake → listen (collect Opus) → STT → LLM → TTS → send Opus

Reference: https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md
"""
import asyncio
import json
import logging
import uuid
from enum import Enum

from fastapi import WebSocket

import config
from azure_llm import chat
from azure_speech import recognize_speech, synthesize_speech
from opus_codec import OpusDecoder, OpusEncoder

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class XiaoZhiSession:
    """One WebSocket session with a StackChan device."""

    def __init__(self, ws: WebSocket, device_id: str = "unknown"):
        self.ws = ws
        self.device_id = device_id
        self.session_id = str(uuid.uuid4())
        self.state = State.IDLE

        # audio codec
        self.decoder = OpusDecoder(config.OPUS_SAMPLE_RATE, config.OPUS_CHANNELS)
        self.encoder = OpusEncoder(config.TTS_SAMPLE_RATE, config.OPUS_CHANNELS)

        # accumulated PCM from device mic
        self._pcm_buf = bytearray()

        # multi-turn chat history (kept short)
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # public entry
    # ------------------------------------------------------------------
    async def run(self):
        """Main receive loop — called from the FastAPI endpoint."""
        try:
            while True:
                msg = await self.ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if "bytes" in msg and msg["bytes"]:
                    await self._on_binary(msg["bytes"])
                elif "text" in msg and msg["text"]:
                    await self._on_text(msg["text"])
        except Exception as exc:
            logger.error("[%s] session error: %s", self.session_id[:8], exc)
        finally:
            logger.info("[%s] session closed", self.session_id[:8])

    # ------------------------------------------------------------------
    # binary (Opus audio frames)
    # ------------------------------------------------------------------
    async def _on_binary(self, data: bytes):
        if self.state is not State.LISTENING:
            return
        pcm = self.decoder.decode(data)
        if pcm:
            self._pcm_buf.extend(pcm)

    # ------------------------------------------------------------------
    # JSON messages
    # ------------------------------------------------------------------
    async def _on_text(self, raw: str):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("bad JSON: %s", raw[:120])
            return

        t = msg.get("type", "")
        logger.info("[%s] ← %s  state=%s", self.session_id[:8], t, msg.get("state", ""))

        if t == "hello":
            await self._handle_hello(msg)
        elif t == "listen":
            await self._handle_listen(msg)
        elif t == "abort":
            self._reset()

    # ------------------------------------------------------------------
    # hello handshake
    # ------------------------------------------------------------------
    async def _handle_hello(self, msg: dict):
        reply = {
            "type": "hello",
            "transport": "websocket",
            "session_id": self.session_id,
            "audio_params": {
                "format": "opus",
                "sample_rate": config.TTS_SAMPLE_RATE,
                "channels": config.OPUS_CHANNELS,
                "frame_duration": config.OPUS_FRAME_DURATION_MS,
            },
        }
        await self._send_json(reply)
        logger.info("[%s] handshake OK  device=%s", self.session_id[:8], self.device_id)

    # ------------------------------------------------------------------
    # listen start / stop
    # ------------------------------------------------------------------
    async def _handle_listen(self, msg: dict):
        st = msg.get("state")

        if st in ("start", "detect"):
            self.state = State.LISTENING
            self._pcm_buf = bytearray()
            # Fresh decoder for each turn — Opus decoder is stateful
            self.decoder = OpusDecoder(config.OPUS_SAMPLE_RATE, config.OPUS_CHANNELS)
            logger.info("[%s] ▶ listening  mode=%s", self.session_id[:8], msg.get("mode"))

        elif st == "stop":
            self.state = State.THINKING
            pcm_bytes = bytes(self._pcm_buf)
            self._pcm_buf = bytearray()
            logger.info(
                "[%s] ■ stop listening  pcm=%d bytes",
                self.session_id[:8], len(pcm_bytes),
            )
            await self._process_turn(pcm_bytes)

    # ------------------------------------------------------------------
    # core pipeline: STT → LLM → TTS
    # ------------------------------------------------------------------
    async def _process_turn(self, pcm: bytes):
        if len(pcm) < 1920:  # <60 ms, too short
            self._reset()
            return

        # ---- STT ----
        text = await asyncio.to_thread(recognize_speech, pcm)
        if not text:
            self._reset()
            return

        await self._send_json({
            "session_id": self.session_id,
            "type": "stt",
            "text": text,
        })

        # ---- LLM ----
        reply, emotion = await asyncio.to_thread(chat, text, self._history)

        # maintain history
        self._history.append({"role": "user", "content": text})
        self._history.append({"role": "assistant", "content": reply})
        if len(self._history) > 20:
            self._history = self._history[-20:]

        # send emotion so device updates expression
        await self._send_json({
            "session_id": self.session_id,
            "type": "llm",
            "emotion": emotion,
            "text": "",
        })

        # ---- TTS ----
        self.state = State.SPEAKING

        await self._send_json({
            "session_id": self.session_id,
            "type": "tts",
            "state": "start",
        })
        await self._send_json({
            "session_id": self.session_id,
            "type": "tts",
            "state": "sentence_start",
            "text": reply,
        })

        tts_pcm = await asyncio.to_thread(synthesize_speech, reply)
        if tts_pcm:
            opus_frames = self.encoder.encode_all(tts_pcm)
            for frame in opus_frames:
                await self.ws.send_bytes(frame)
                # pace slightly faster than real-time to keep buffer fed
                await asyncio.sleep(config.OPUS_FRAME_DURATION_MS / 1000.0 * 0.8)

        await self._send_json({
            "session_id": self.session_id,
            "type": "tts",
            "state": "stop",
        })

        self._reset()
        logger.info("[%s] ✓ turn complete", self.session_id[:8])

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    async def _send_json(self, obj: dict):
        await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    def _reset(self):
        self.state = State.IDLE
        self._pcm_buf = bytearray()
