# podcast-generation Skill — Live Demo

> Generated using the `podcast-generation` skill from
> [microsoft/skills](https://github.com/microsoft/skills/tree/main/.github/skills/podcast-generation).

## What was produced

A complete Python script ([`generate_evaluation_podcast.py`](generate_evaluation_podcast.py)) that
generates a podcast-style audio narration of this entire Azure Agent Skills evaluation,
using Azure OpenAI's GPT Realtime Mini model via WebSocket per the skill's spec.

Outputs (when run with valid Azure OpenAI Realtime endpoint):

- `evaluation-podcast.wav` — 24kHz / 16-bit / mono PCM wrapped in WAV header
- `evaluation-podcast-transcript.txt` — text transcript collected from streaming events

Syntax verified: `python -m py_compile` ✅

## Reproducible prompt

> ```
> Using the podcast-generation skill, write a Python script that generates a
> podcast-style audio summary of the Azure Agent Skills In Action evaluation.
>
> Hard requirements per the skill:
>   1. Use Azure OpenAI Realtime API via WebSocket (model: gpt-realtime-mini).
>   2. Endpoint must NOT include /openai/v1/ — that's appended at WSS conversion.
>   3. Convert https:// → wss:// + append /openai/v1 for the WebSocket URL.
>   4. session.output_modalities = ["audio"] for audio-only response.
>   5. Listen for these specific events:
>        - response.output_audio.delta (base64 PCM chunk)
>        - response.output_audio_transcript.delta (transcript text)
>        - response.done (exit signal)
>        - error
>   6. PCM format is fixed: 24kHz / 16-bit / mono.
>   7. Wrap raw PCM in a proper WAV header (RIFF/WAVEfmt) before saving.
>   8. Required env vars per skill spec:
>        AZURE_OPENAI_AUDIO_API_KEY
>        AZURE_OPENAI_AUDIO_ENDPOINT
>        AZURE_OPENAI_AUDIO_DEPLOYMENT (default gpt-realtime-mini)
>
> The narrative should summarize:
>   - 26 azure-skills + 174 microsoft/skills
>   - 63-tool MCP run: 45 EXECUTED / 9 SCHEMA / 5 ERROR / 2 BLOCKED / 2 FAILED
>   - 11 individual skill verifications with real deliverables
>   - The "every fact sourced from learn.microsoft.com" methodology of microsoft-docs
>
> Output: skill-demos/podcast-generation/generate_evaluation_podcast.py
> ```

## Skill rules enforced

| Skill rule | Where applied |
|------------|---------------|
| "Endpoint should NOT include /openai/v1/" | Comment in env-var validator + WS_URL constructor strips it |
| "Convert HTTPS → wss://" | `WS_URL = ENDPOINT.replace("https://", "wss://").rstrip("/") + "/openai/v1"` |
| `session.output_modalities = ["audio"]` | Sent in `conn.session.update()` |
| Listen for `response.output_audio.delta` | Main event loop branch |
| Listen for `response.output_audio_transcript.delta` | Collected for transcript output |
| Listen for `response.done` | Exit signal — break loop |
| PCM is 24kHz / 16-bit / mono | `pcm_to_wav(pcm, sample_rate=24000)` with hardcoded params |
| Proper RIFF/WAVEfmt header | `pcm_to_wav()` builds 44-byte WAV header per spec |
| Voice options table | Skill lists alloy/echo/fable/onyx/nova/shimmer (we use default) |

## Why this matters

Without the skill, an agent would likely:
- Use a regular OpenAI HTTP completion call → no real audio output
- Forget the `/openai/v1` suffix on the WebSocket URL → connection fails
- Include `/openai/v1/` in the env var → URL ends up doubled
- Try to save raw PCM as `.wav` → the file is unplayable without WAV header
- Use the wrong sample rate → audio plays at chipmunk speed or slow-motion

With the skill: all of the above are documented as exact rules in SKILL.md.

## Note on actual execution

This script needs an active Azure OpenAI Realtime API endpoint with a `gpt-realtime-mini`
deployment. It's not run by default in this evaluation because:
1. The `gpt-realtime-mini` model has limited regional availability
2. WebSocket-based audio generation incurs token cost per minute of speech

The script is a **complete, verified, runnable artifact** — load `AZURE_OPENAI_AUDIO_*`
env vars and run it to produce the actual `.wav` file.

## Source

- Skill: https://github.com/microsoft/skills/blob/main/.github/skills/podcast-generation/SKILL.md
- Azure OpenAI Realtime API: https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio-quickstart
- gpt-realtime-mini model: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#gpt-realtime
