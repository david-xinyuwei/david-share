"""Smoke-test client — simulates a StackChan device via WebSocket.

Usage:
    python test_client.py [--url ws://localhost:8080/xiaozhi/v1/]

Sends a hello, then a short sine-wave audio burst encoded as Opus,
then listen-stop, and prints server responses.  Requires opuslib.
"""
import argparse
import asyncio
import json
import math
import struct
import sys

import websockets
import opuslib


SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 60
FRAME_SIZE = SAMPLE_RATE * FRAME_MS // 1000  # 960 samples


def generate_sine_pcm(freq: float = 440.0, duration_s: float = 2.0) -> bytes:
    """Return 16-bit LE mono PCM of a sine wave (silence-like test tone)."""
    n_samples = int(SAMPLE_RATE * duration_s)
    buf = bytearray()
    for i in range(n_samples):
        val = int(3000 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        buf.extend(struct.pack("<h", val))
    return bytes(buf)


def pcm_to_opus_frames(pcm: bytes) -> list[bytes]:
    enc = opuslib.Encoder(SAMPLE_RATE, CHANNELS, opuslib.APPLICATION_AUDIO)
    bpf = FRAME_SIZE * CHANNELS * 2
    frames = []
    for off in range(0, len(pcm), bpf):
        chunk = pcm[off : off + bpf]
        if len(chunk) < bpf:
            chunk += b"\x00" * (bpf - len(chunk))
        frames.append(enc.encode(chunk, FRAME_SIZE))
    return frames


async def main(url: str):
    token = "test-token"
    headers = {
        "Authorization": f"Bearer {token}",
        "Protocol-Version": "1",
        "Device-Id": "AA:BB:CC:DD:EE:FF",
        "Client-Id": "test-client-001",
    }

    async with websockets.connect(url, additional_headers=headers) as ws:
        # --- hello ---
        hello = {
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "audio_params": {
                "format": "opus",
                "sample_rate": SAMPLE_RATE,
                "channels": CHANNELS,
                "frame_duration": FRAME_MS,
            },
        }
        await ws.send(json.dumps(hello))
        reply = await ws.recv()
        print("← hello reply:", reply)

        # --- listen start ---
        await ws.send(json.dumps({
            "type": "listen",
            "state": "start",
            "mode": "manual",
        }))

        # --- send test audio ---
        print("Sending 2 s test tone...")
        pcm = generate_sine_pcm(440.0, 2.0)
        frames = pcm_to_opus_frames(pcm)
        for f in frames:
            await ws.send(f)
            await asyncio.sleep(FRAME_MS / 1000.0)

        # --- listen stop ---
        await ws.send(json.dumps({
            "type": "listen",
            "state": "stop",
        }))
        print("listen-stop sent, waiting for server responses...")

        # --- collect responses ---
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                if isinstance(msg, bytes):
                    print(f"← audio frame ({len(msg)} bytes)")
                else:
                    data = json.loads(msg)
                    print(f"← {data.get('type', '?')}: {msg[:200]}")
                    if data.get("type") == "tts" and data.get("state") == "stop":
                        break
        except asyncio.TimeoutError:
            print("Timeout waiting for server.")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        default="ws://localhost:8080/xiaozhi/v1/",
        help="WebSocket URL of the Azure XiaoZhi Server",
    )
    args = parser.parse_args()
    asyncio.run(main(args.url))
