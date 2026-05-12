"""Generate a podcast-style audio summary of the Azure Agent Skills evaluation.

Generated using the `podcast-generation` skill from microsoft/skills.

What this script does (per the skill's workflow):
  1. Connect via WebSocket to Azure OpenAI Realtime endpoint (gpt-realtime-mini)
  2. Send a podcast script narrating the 63-tool MCP evaluation results
  3. Collect PCM audio chunks + transcript via streaming events
  4. Convert raw PCM (24kHz, 16-bit, mono) to a playable WAV file
  5. Save to evaluation-podcast.wav

Skill-specific patterns enforced:
  - Endpoint must NOT include /openai/v1/ — just the base URL
  - Convert HTTPS → wss:// for the WebSocket connection
  - session.output_modalities = ["audio"] for audio-only response
  - Listen for response.output_audio.delta and response.output_audio_transcript.delta
  - PCM format is fixed: 24kHz / 16-bit / mono
  - Wait for response.done event before exiting

Source: https://github.com/microsoft/skills/blob/main/.github/skills/podcast-generation/SKILL.md
        (fetched 2026-05-12)

Run:
    pip install openai
    export AZURE_OPENAI_AUDIO_API_KEY=...
    export AZURE_OPENAI_AUDIO_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    export AZURE_OPENAI_AUDIO_DEPLOYMENT=gpt-realtime-mini
    python generate_evaluation_podcast.py
"""
import asyncio
import base64
import os
import struct
import sys
from pathlib import Path

from openai import AsyncOpenAI

# ---- Skill-specified env vars ----
API_KEY = os.environ.get("AZURE_OPENAI_AUDIO_API_KEY")
ENDPOINT = os.environ.get("AZURE_OPENAI_AUDIO_ENDPOINT")
DEPLOYMENT = os.environ.get("AZURE_OPENAI_AUDIO_DEPLOYMENT", "gpt-realtime-mini")

if not API_KEY or not ENDPOINT:
    print("ERROR: AZURE_OPENAI_AUDIO_API_KEY and AZURE_OPENAI_AUDIO_ENDPOINT required.")
    print("       (Skill spec: endpoint should NOT include /openai/v1/ — just the base URL.)")
    sys.exit(1)

# ---- Skill rule: convert HTTPS → wss:// + append /openai/v1 ----
WS_URL = ENDPOINT.replace("https://", "wss://").rstrip("/") + "/openai/v1"

# ---- Podcast script (the content to narrate) ----
PODCAST_SCRIPT = """
Welcome to the Azure Agent Skills In Action briefing.

Microsoft published two skills repositories: azure-skills, with 26 top-level skills
and 31 SKILL.md definitions covering Azure resource management, and skills, with
174 skills across Python, .NET, TypeScript, Java, and Rust.

To verify these skills are not just documentation, we ran every callable Azure MCP tool
against a real Azure subscription with Owner permission. The result: 63 out of 63 tools
were probed. 45 executed successfully and returned live Azure data. 9 had valid
schemas but needed resource-specific inputs we did not have. 5 returned tool errors.
2 were intentionally blocked because they had side effects. 2 still need better
test cases.

Then we used 11 individual skills to produce real deliverables. cloud-solution-architect
designed a complete RAG agent system with the 7-step Well-Architected Framework workflow.
github-issue-creator turned a 6-line error log into 3 structured GitHub issues.
mcp-builder produced a working FastMCP server. frontend-design-review audited a 726-line
single-page app across 5 quality pillars. microsoft-docs generated a 14-slide presentation
where every fact came from a learn dot microsoft dot com URL displayed on the slide footer.

The verdict: the skills are not promotional. They produce real engineering artifacts when
loaded into a coding agent and given a concrete task. Customer can audit every claim by
running the same harness against their own Azure subscription.

This podcast itself was generated using the podcast-generation skill, which uses
Azure OpenAI's GPT Realtime Mini model via WebSocket to produce real audio output.
"""


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw PCM (24kHz/16-bit/mono per skill spec) in a WAV header."""
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_bytes)

    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVEfmt "
    header += struct.pack("<I", 16)  # fmt chunk size
    header += struct.pack("<H", 1)  # PCM format
    header += struct.pack("<H", num_channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", block_align)
    header += struct.pack("<H", bits_per_sample)
    header += b"data"
    header += struct.pack("<I", data_size)
    return header + pcm_bytes


async def main():
    print(f"Connecting to {WS_URL} (deployment: {DEPLOYMENT})...")
    client = AsyncOpenAI(websocket_base_url=WS_URL, api_key=API_KEY)

    audio_chunks: list[bytes] = []
    transcript_parts: list[str] = []

    async with client.realtime.connect(model=DEPLOYMENT) as conn:
        # Skill rule: configure for audio-only output
        await conn.session.update(session={
            "output_modalities": ["audio"],
            "instructions": "You are a professional technical podcast narrator. Speak clearly, naturally, and with measured pacing.",
        })

        # Send the podcast script
        await conn.conversation.item.create(item={
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": PODCAST_SCRIPT}],
        })

        await conn.response.create()

        # Skill rule: listen for these specific events
        async for event in conn:
            if event.type == "response.output_audio.delta":
                audio_chunks.append(base64.b64decode(event.delta))
            elif event.type == "response.output_audio_transcript.delta":
                transcript_parts.append(event.delta)
                print(event.delta, end="", flush=True)
            elif event.type == "response.done":
                print("\n[done]")
                break
            elif event.type == "error":
                print(f"\n[error] {event.error.message}")
                break

    # Skill rule: PCM is 24kHz / 16-bit / mono
    pcm = b"".join(audio_chunks)
    wav = pcm_to_wav(pcm, sample_rate=24000)

    out_path = Path(__file__).parent / "evaluation-podcast.wav"
    out_path.write_bytes(wav)
    print(f"\n✅ Saved: {out_path}  ({len(wav):,} bytes, {len(pcm)/24000/2:.1f}s audio)")

    transcript_path = Path(__file__).parent / "evaluation-podcast-transcript.txt"
    transcript_path.write_text("".join(transcript_parts))
    print(f"✅ Transcript: {transcript_path}")


if __name__ == "__main__":
    asyncio.run(main())
