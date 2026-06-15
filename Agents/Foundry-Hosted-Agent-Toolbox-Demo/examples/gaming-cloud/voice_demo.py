"""Gaming Voice Demo — speech-to-text → agent → answer.

Simulates a gaming voice assistant: the player speaks a question, Foundry Whisper
transcribes it, the hosted agent processes it and returns an answer.

For this demo we generate a synthetic WAV file (no mic needed) so the demo is
reproducible. In production the WAV would come from the device's microphone.

Prerequisites:
    1. python main.py                   (keep running)
    2. Whisper deployment "whisper" in the same Foundry account
    3. pip install httpx (already in requirements.txt)

Run:
    python examples/gaming-cloud/voice_demo.py
"""
import argparse
import json
import os
import struct
import tempfile

import httpx
from azure.identity import AzureCliCredential


def generate_silent_wav(path: str, duration_s: float = 2.0, sample_rate: int = 16000) -> None:
    """Write a minimal valid WAV file with silence. We only need a valid file
    so Whisper returns an empty or near-empty transcript — the point of the demo
    is the pipeline, not the audio content. For a real demo, replace this with
    a recorded WAV."""
    num_samples = int(sample_rate * duration_s)
    data_size = num_samples * 2  # 16-bit mono
    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


def transcribe_with_whisper(audio_path: str, account_base: str, deployment: str, token: str) -> str:
    """Call the Foundry Whisper deployment to transcribe audio."""
    url = f"{account_base}/openai/deployments/{deployment}/audio/transcriptions?api-version=2024-06-01"
    with open(audio_path, "rb") as f:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"response_format": "text"},
            timeout=60.0,
        )
    resp.raise_for_status()
    return resp.text.strip()


def ask_agent(client: httpx.Client, base_url: str, prompt: str) -> str:
    resp = client.post(f"{base_url.rstrip('/')}/responses", json={"input": prompt})
    resp.raise_for_status()
    payload = resp.json()
    chunks = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for c in item.get("content", []):
            if isinstance(c, dict) and c.get("type") == "output_text" and c.get("text"):
                chunks.append(c["text"])
    return "\n".join(chunks) or json.dumps(payload, indent=2)[:1500]


# A pre-written "player question" we'll use instead of silence for a meaningful demo.
# In production this would be the actual whisper transcript from mic audio.
SIMULATED_PLAYER_QUESTION = (
    "My FPS keeps dropping to single digits in Dragon Valley but runs fine "
    "everywhere else. I have 16 GB RAM and an RTX 3060. What should I do?"
)


def main():
    parser = argparse.ArgumentParser(description="Gaming Voice Demo: speech → Whisper → agent → answer")
    parser.add_argument("--base-url", default="http://localhost:8088")
    parser.add_argument("--whisper-deployment", default="whisper")
    parser.add_argument("--audio-file", default="", help="Path to a real WAV file. If empty, uses a simulated transcript.")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not project_endpoint:
        raise SystemExit(
            "Set FOUNDRY_PROJECT_ENDPOINT, for example "
            "https://<account>.services.ai.azure.com/api/projects/<project>."
        )
    # Account base = project endpoint without /api/projects/<project>
    if "/api/projects/" in project_endpoint:
        account_base = project_endpoint.split("/api/projects/")[0]
    else:
        account_base = project_endpoint.rstrip("/")

    credential = AzureCliCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token

    print("=" * 60)
    print("🎮🎤  GAMING VOICE DEMO: Speech → Whisper → Agent → Answer")
    print("=" * 60)

    # Step 1: Transcribe audio (or simulate)
    if args.audio_file:
        print(f"\n[Step 1] Transcribing {args.audio_file} with Whisper...")
        transcript = transcribe_with_whisper(
            args.audio_file, account_base, args.whisper_deployment, token
        )
        print(f"  Whisper transcript: \"{transcript}\"")
    else:
        # Generate a silent WAV to prove Whisper endpoint works, then use simulated text
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        generate_silent_wav(tmp_path)
        print(f"\n[Step 1] Testing Whisper endpoint with silent WAV...")
        try:
            silent_transcript = transcribe_with_whisper(
                tmp_path, account_base, args.whisper_deployment, token
            )
            print(f"  Whisper returned: \"{silent_transcript}\" (silent audio → empty/short transcript, expected)")
            print(f"  ✅ Whisper endpoint is live and responding.")
        except Exception as e:
            print(f"  ⚠️ Whisper call failed: {e}")
        finally:
            os.unlink(tmp_path)

        transcript = SIMULATED_PLAYER_QUESTION
        print(f"\n  Using simulated player voice transcript:")
        print(f"  \"{transcript}\"")

    # Step 2: Send to agent
    print(f"\n[Step 2] Sending transcript to hosted agent at {args.base_url}...")
    agent_prompt = (
        f"A player asked via voice chat (transcribed by Whisper):\n\n"
        f"\"{transcript}\"\n\n"
        f"Use code_interpreter to analyze any data if provided, and give the player "
        f"a helpful 3-sentence response about their gaming performance issue."
    )

    with httpx.Client(timeout=args.timeout) as client:
        answer = ask_agent(client, args.base_url, agent_prompt)

    print(f"\n🎮  AGENT RESPONSE TO PLAYER:\n")
    for line in answer.split("\n"):
        print(f"  {line}")
    print(f"\n{'='*60}")
    print("Pipeline: 🎤 Voice → Whisper STT → Hosted Agent → Toolbox → Answer")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
