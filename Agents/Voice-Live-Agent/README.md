# Voice Live Agent

English | [中文](README-CN.md)

A Chinese-language desktop voice agent built on the **Azure AI Foundry Voice Live API**. It runs on a Windows machine and handles real-time Q&A, live data lookup, camera-based object recognition, system control, news briefings, email delivery, and wallpaper changes — **every tool executes on the user's own PC**.

One codebase ships three voice connection modes, switchable at runtime from the UI, so customers can see the Voice Live architecture trade-offs side by side.

## What's Real vs What's Demo

| | Detail |
|---|---|
| ✅ **Real** | All voice paths hit live Azure Voice Live / Azure OpenAI Realtime services. No local simulation. |
| ✅ **Real** | All 19 tools genuinely execute: volume via Core Audio API, wallpaper via Win32, timezone via PowerShell, weather/stocks/news via live public APIs, email actually delivered. |
| ✅ **Real** | Foundry Agent mode connects to a real hosted Agent; tool definitions live in the cloud and are verifiable in the Foundry portal. |
| ⚠️ **Bring your own** | WebIQ search needs a valid key; image generation needs an image model deployed in your Foundry resource. |
| ⚠️ **Platform bound** | Volume, wallpaper, timezone, and app launching depend on Windows APIs. Windows only. |
| ❌ **Never** | No tool returns simulated data. When a dependency is unavailable the tool returns an explicit failure and the model tells the user the truth — **no silent fallback**. |

---

## 1. Three Runtime Modes

Microsoft documents three Voice Live deployment patterns. This project exposes them as runtime-switchable options, **plus one non-Voice-Live control group**.

| UI option | Service | Brain | Voice path |
|---|---|---|---|
| `voicelive` | Azure Voice Live | Model direct | S2S / Hybrid / Cascaded, driven by config |
| `voicelive-agent` | Azure Voice Live | Foundry Agent hosted | Cascaded (STT → Agent → TTS) |
| `realtime` | Azure OpenAI Realtime | Model deployment | End-to-end (**not Voice Live**) |

### 1.1 Pattern selection is configuration, not code (measured)

Which pattern Voice Live lands in is decided by two settings — **model** and **voice**. No code change required:

| Pattern | `AZURE_VOICELIVE_MODEL` | `AZURE_VOICELIVE_VOICE` | Measured |
|---|---|---|---|
| **(a) Integrated S2S**<br>One model does STT·LLM·TTS, lowest latency | `gpt-realtime` | `alloy` (model-native voice) | ✅ PASS |
| **(b) Hybrid**<br>Realtime handles STT+LLM, Azure does TTS, brand voice available | `gpt-realtime` | `zh-CN-XiaoxiaoMultilingualNeural` | ✅ PASS |
| **(c) Cascaded**<br>Azure STT → text model → Azure TTS, any strong model | `gpt-4.1` | `zh-CN-XiaoxiaoMultilingualNeural` | ✅ PASS |

All three verified end to end (`status=COMPLETED` with a successful `function_call`).

> **Chinese-language note**: model-native voices such as `alloy` perform poorly in Mandarin. Production Chinese scenarios should use (b) or (c) with an Azure neural voice.

The entire branch is one line — a voice name containing `-` is treated as an Azure voice, otherwise it is passed straight to the model:

```python
voice=AzureStandardVoice(name=voice) if "-" in voice else voice
```

### 1.2 What Foundry Agent mode actually changes

`voicelive-agent` is **not a fourth pattern**. It sits on the (c) Cascaded row. What it changes is not the voice path but **where the persona and tool definitions live**:

```python
# Model direct: instructions and tools pushed by the client on every session.update
connect(endpoint=..., credential=..., model="gpt-realtime")

# Agent hosted: instructions and tools stored in the cloud Agent definition
connect(endpoint=..., credential=..., agent_name="...", project_name="...")
```

**The value is multi-client only**: a phone app, a car head unit, and a PC all connect to the same Agent, so changing the persona does not require shipping each client. **For a single client it is a net cost.** Measured constraints, all quoted verbatim from the service:

| Constraint | Server response |
|---|---|
| API keys rejected | `Key authentication is not supported in Foundry Agent mode.` |
| Runtime tool config rejected | `Configuring tools at runtime in Foundry Agent mode is not supported.`<br>`Please configure tools in the agent definition.` |
| Multimodal realtime models unusable | Configuring `gpt-realtime` yields `status=FAILED` with empty output |
| Transcription models restricted | `Only 'azure-speech', 'azure-mrs', 'mai-transcribe-1', 'mai-transcribe-1.5', and 'mai-transcribe' are supported in cascaded pipelines` |

That last message is the service itself calling Agent mode a **cascaded pipeline** — the most direct evidence that Agent mode is necessarily cascaded.

> **Tools still execute locally.** The Agent stores only the tool *definitions*. Once the model picks a tool, the arguments come back to the client and local code does the actual work. The cloud Agent contains zero device-control code.

### 1.3 How this differs from Azure OpenAI Realtime

The `realtime` mode talks to `/openai/v1/realtime`, which is **not Voice Live**, so it gets none of the Voice Live speech enhancement layer:

| | Voice Live | Azure OpenAI Realtime |
|---|---|---|
| Semantic VAD (Chinese) | ✅ `azure_semantic_vad_multilingual`, filler-word removal | ❌ `semantic_vad` only |
| Noise suppression | ✅ `azure_deep_noise_suppression` | ❌ |
| Server-side echo cancellation | ✅ including Live-Reference AEC | ❌ must be built client-side |
| Voices | 600+ Azure neural / HD / custom | model-native only |
| Avatar | ✅ | ❌ |
| Model deployment | service-managed, none required | must deploy yourself |

This mode is kept so customers can see concretely what they lose by not using Voice Live.

---

## 2. Capabilities

19 tools, all registered locally, triggered by the model from voice intent.

### Desktop and device control

| Voice command | What actually happens | Verifiable |
|---|---|---|
| "What's the volume?" | Core Audio `IAudioEndpointVolume.GetMasterVolumeLevelScalar` | ✅ matches the system volume slider |
| "Set volume to 30" / "louder" | `SetMasterVolumeLevelScalar` | ✅ system slider moves live |
| "Mute" / "unmute" | `SetMute` | ✅ tray icon changes |
| "Open calculator / notepad / explorer / task manager / paint" | `subprocess.Popen` | ✅ window appears |
| "Open settings" | `os.startfile("ms-settings:")` | ✅ Settings app opens |
| "Show desktop" | Win32 `keybd_event` simulating Win+D | ✅ windows minimize |
| "Change the timezone to Seattle" | PowerShell `Set-TimeZone` | ✅ system clock changes immediately |
| "Set it as my wallpaper" | Win32 `SystemParametersInfoW` | ✅ desktop changes immediately |

### Perception and information

| Voice command | What actually happens | Verifiable |
|---|---|---|
| "Open the camera" | OpenCV always-on stream, mirrored in the UI | ✅ live frame updates |
| "What is this?" (holding an object) | Grab current frame → multimodal model | ✅ returns an object description |
| "Where can I buy it?" | Recognition result → web search | ✅ returns purchase links |
| "What's the weather in Beijing?" | `GET api.open-meteo.com` | ✅ real readings with observation time |
| "What's Microsoft's stock price?" | `GET query1.finance.yahoo.com` | ✅ matches Yahoo Finance |
| "Any news?" | Live RSS (Google News / BBC) | ✅ clickable source links |
| "Search for X" | WebIQ `client.web.search` | needs a valid key |
| "What time is it in New York?" | Local IANA tzdata | ✅ includes UTC offset |

### Content generation and delivery

| Voice command | What actually happens | Verifiable |
|---|---|---|
| "Put together a news briefing" | Live RSS + Azure OpenAI | ✅ every item cites its source |
| "Email it to me" | Real SMTP delivery (recipient allowlist) | ✅ arrives in the inbox |
| "Find a wallpaper online" | Image search + https download validation | needs a valid key |
| "Generate a wallpaper" | Azure OpenAI image generation, saved locally | needs an image deployment |

### Image recognition does not go through Voice Live

Camera recognition is a **Chat Completions call made inside a function call**, fully decoupled from the voice path:

```
User: "What is this?"
  → Voice Live recognizes intent, emits a function call
  → local code grabs the current frame → calls a multimodal model → gets text back
  → Voice Live speaks that description
```

Voice Live only ever handles audio and **never sees an image**. No model switch or Agent is needed to add vision.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Windows host                                             │
│                                                           │
│  Microphone ──PCM16/24kHz──┐                              │
│  Speaker    ◀──audio delta─┤  voice backend (one of three)│
│  Camera     ──live stream──┐└──── function call ────┐     │
│                            │                        │     │
│                            ▼                        ▼     │
│                   frame buffer (always on)   tool registry│
│                            │                   (19 tools) │
│                            └─► multimodal ◀────────┘      │
│                                                            │
│  volume / app launch / timezone / wallpaper ← all local     │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
              Azure Voice Live / Azure OpenAI Realtime
```

- All three backends share one audio pipeline and one tool orchestration layer ([src/agent_core.py](src/agent_core.py))
- Synchronous tools run via `asyncio.to_thread` so the audio event loop is never blocked
- Multiple function calls in one turn execute concurrently via `asyncio.gather`
- `VoiceLiveFoundryAgent` extends `VoiceLiveAgent`, overriding only the connection parameters

See [docs/architecture.png](docs/architecture.png) and [docs/sequence.png](docs/sequence.png) for the full call chain.

---

## 4. Engineering Notes

### 4.1 Echo and barge-in

Over remote desktop or with open speakers, the microphone picks up the assistant's own voice and it interrupts itself. Two layers of defense:

**Server-side Live-Reference AEC** (official Voice Live feature, API version `2026-07-15+`)

By default the service uses its own outbound audio as the echo reference and **assumes the client plays it the moment it arrives**. Over remote desktop, playback often lags by more than two seconds and that assumption breaks. Live-Reference AEC makes the client report **what it actually played**:

```python
AudioEchoCancellation(type="server_echo_cancellation",
                      reference_source="client", channels=2)
```

Audio is uploaded as interleaved stereo: channel 0 is the microphone, channel 1 is the playback reference. With this enabled the client stops muting its uplink and lets the service decide what is a real interruption.

Set `AUDIO_LIVE_REFERENCE_AEC=false` to fall back to the client-side gate.

**Client-side barge-in state machine** (fallback)

Single-frame level checks fire on any audio spike. The implementation uses consecutive-frame confirmation, hysteresis release, and prebuffer replay:

| Parameter | Value | Purpose |
|---|---|---|
| Confirmation frames | 3 | A single spike is not an interruption |
| Release frames | 6 | A pause mid-sentence is not the end of a turn |
| Hysteresis ratio | 0.65 | Prevents oscillation around the threshold |
| Prebuffer frames | 4 | Replays frames muted during confirmation so the leading syllable survives |

### 4.2 Camera

- Always-on stream with a background capture thread; the recognition tool reads the current frame, so the user can just hold something up and ask
- Backends ordered by measured availability (DirectShow first, Media Foundation second), and the last working combination is remembered
- One automatic retry on open failure — a just-released device is briefly unavailable

### 4.3 Volume control

Uses Core Audio's `IAudioEndpointVolume` rather than simulating volume keys: it reads an exact percentage and is unaffected by window focus. The tool runs in a thread pool, so **it initializes its own COM apartment** (`CoInitialize` / `CoUninitialize`) on every call and handles the interface differences between pycaw versions.

Relative adjustments ("a bit louder") are handled by the model querying the current value first, a flow the system prompt makes explicit.

### 4.4 Transcription model

Agent mode uses `mai-transcribe`. Agent mode reasons over text, so **transcription quality directly determines intent**; a Chinese mis-transcription produces an entirely wrong tool call.

---

## 5. Requirements

- Windows 10/11 (volume, wallpaper, timezone, and app launching depend on Win32 / PowerShell / Core Audio)
- Python 3.10+
- Microphone and speaker (headphones recommended for demos — they physically break the echo loop)
- An Azure AI Foundry resource (Voice Live needs no model deployment)
- The account needs the `Cognitive Services User` and `Foundry User` roles

---

## 6. Setup

```powershell
git clone <this-repo>
cd voice-live-agent
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and fill in your Foundry endpoint. Entra authentication is recommended (leave `AZURE_VOICELIVE_API_KEY` empty). Isolate the Azure CLI config directory for this project:

```powershell
$env:AZURE_CONFIG_DIR = "$HOME\.azure-voice-live-agent"
az login
az account set --subscription <your-subscription-id>
az account show -o table
```

> **Foundry Agent mode requires Entra.** The service rejects API keys. The `voicelive` and `realtime` modes accept keys.

### Optional: Foundry Agent mode

Create an Agent in your Foundry project with the instructions and tool definitions, then configure:

```ini
AZURE_VOICELIVE_AGENT_NAME=<agent-name>
AZURE_VOICELIVE_PROJECT_NAME=<project-name>
AZURE_VOICELIVE_AGENT_VERSION=<version>
```

REST endpoints for Agent creation (`api-version=2025-11-15-preview`):

```
POST {project_endpoint}/agents                     # create
POST {project_endpoint}/agents/{name}/versions     # add a version to an existing agent
```

`definition.model` **must be a text model** (for example `gpt-4.1` or a `gpt-5` variant). Configuring a multimodal realtime model produces an empty response with no error.

**After adding tools locally you must publish a new Agent version**, otherwise the cloud still holds the old tool list.

---

## 7. Validation

Four layers, increasing in depth. Do not proceed past a failing layer:

```powershell
# 1. Offline: can the session config and tool schemas serialize correctly
.venv\Scripts\python.exe -m scripts.preflight --mode voicelive --dry-run
.venv\Scripts\python.exe -m scripts.preflight --mode realtime  --dry-run

# 2. Live external data sources (weather/stocks/news/timezone/search), no Azure credentials needed
.venv\Scripts\python.exe -m scripts.smoke_tools

# 3. Real backend connection: auth, model, voice, and tool schema accepted by the service, mic stays off
.venv\Scripts\python.exe -m scripts.preflight --mode voicelive
.venv\Scripts\python.exe -m scripts.preflight --mode realtime

# 4. Adds briefing, image generation, and wallpaper (this really changes your desktop)
.venv\Scripts\python.exe -m scripts.smoke_tools --all
```

### Verified

| Item | Status | Evidence |
|---|---|---|
| Tool registration and schema serialization | ✅ | All three backends emit 19 tools |
| Voice Live end-to-end speech | ✅ | Real Chinese/English conversation, STT and TTS both working |
| Voice Live three patterns | ✅ | (a)(b)(c) all `COMPLETED` with a `function_call` |
| Foundry Agent mode | ✅ | `COMPLETED`, 22 audio chunks, `function_call` triggered |
| Agent tool sync | ✅ | v3 carries 19 tools; "set volume to 30" triggers `set_system_volume` |
| Azure OpenAI Realtime | ✅ | `wss://…/openai/v1/realtime` GA format |
| System volume control | ✅ | 100%→30%→55%→mute→restored, 10 assertions passed |
| App launch / show desktop | ✅ | Processes actually start; invalid app names raise correctly |
| Weather / stocks / news / timezone | ✅ | Live data returned |
| Email delivery | ✅ | HTTP 202 plus actual inbox receipt |
| Camera live stream | ✅ | Frame brightness changes across frames, UI mirrors it |
| Win32 wallpaper | ✅ | Registry `WallPaper` and `WallpaperStyle` written and applied |
| System timezone change | ✅ | System clock actually changes, no elevation needed |
| barge-in state machine | ✅ | 8 state-machine unit assertions passed |
| Live-Reference AEC | ✅ | 7 interleaving assertions passed; service returns `session.updated` with no error |
| SSRF / path traversal / recipient allowlist | ✅ | http, localhost, 127.0.0.1, 169.254.169.254 all rejected |

---

## 8. Running

```powershell
.venv\Scripts\python.exe app.py
```

The dropdown in the top-right switches modes. Logs are written to `logs\<timestamp>_voiceagent.log`.

Build a standalone exe:

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean VoiceLiveAgent.spec
```

Output lands in `dist\` and needs `.env` alongside it.

---

## 9. Demo Script

1. "Set the volume to 30" → "What's the volume now?" → "Mute" → "Unmute"
2. "Open the calculator" → "Show the desktop"
3. "What's the weather in Beijing, do I need an umbrella?"
4. "Change the system timezone to Seattle" → then "What time is it now?"
5. "Open the camera" → hold up an object → "What is this?" → "Where can I buy it?"
6. "Put together a news briefing on AI" → "Email it to me"
7. "Find a snowy sunrise wallpaper online and set it as my desktop"

Items 5, 6, and 7 chain multiple tool calls and are the strongest orchestration moments.
To discuss architecture trade-offs, switch modes on the same sentence and let the audience hear the latency and voice differences.

---

## 10. Configuration

| Variable | Purpose | Behavior if missing |
|---|---|---|
| `AZURE_VOICELIVE_ENDPOINT` | Voice Live endpoint | `voicelive` mode fails at startup |
| `AZURE_VOICELIVE_MODEL` | Defaults to `gpt-realtime`; a text model switches to Cascaded | uses default |
| `AZURE_VOICELIVE_VOICE` | Defaults to a Chinese neural voice; `alloy` switches to Integrated S2S | uses default |
| `AZURE_VOICELIVE_API_KEY` | Empty means Entra token | uses Entra |
| `AZURE_VOICELIVE_AGENT_NAME` | Foundry Agent name | `voicelive-agent` fails at startup |
| `AZURE_VOICELIVE_PROJECT_NAME` | Foundry project name | same as above |
| `AZURE_VOICELIVE_AGENT_VERSION` | Agent version | service default |
| `AUDIO_LIVE_REFERENCE_AEC` | Defaults to `true`; `false` falls back to the client gate | enabled |
| `AUDIO_HALF_DUPLEX` | Client echo guard; auto-disabled when Live-Reference AEC is on | enabled |
| `AZURE_OPENAI_ENDPOINT` | Realtime backend + briefing + image generation + vision | related features fail |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Briefing and image recognition | those tools return failure |
| `AZURE_OPENAI_IMAGE_DEPLOYMENT` | Wallpaper generation | that tool returns failure |
| `SMTP_*` | Email delivery | email tool returns failure |
| `MAIL_ALLOWED_RECIPIENTS` | Recipient allowlist | **empty rejects all sending** |
| `NEWS_FEEDS` | RSS source list | falls back to Google News + BBC |
| `WALLPAPER_DIR` | Wallpaper output directory | defaults to `artifacts\wallpapers` |

---

## 11. Security Boundaries

- Email recipients must match `MAIL_ALLOWED_RECIPIENTS`, so a voice command cannot be coaxed into mailing an arbitrary address
- Recipients and subjects reject newline characters, blocking header injection
- Wallpaper changes accept only files inside `WALLPAPER_DIR`, validated after path resolution, blocking traversal
- Image downloads require https and reject internal addresses and cloud metadata endpoints (`localhost`, `127.0.0.1`, `169.254.169.254`)
- App launching is restricted to a fixed allowlist; arbitrary executable paths are not accepted
- Volume values are clamped to 0–100 server-side; out-of-range input neither throws nor overflows
- All credentials come from `.env`; neither `.env` nor the token cache is committed

---

## 12. Known Limitations

- Camera recognition needs a multimodal deployment; realtime speech models are unreliable for scene understanding, so vision must point at an image-capable deployment
- Foundry Agent mode rejects API keys, rejects runtime tool configuration, and cannot host multimodal realtime models
- Model-native voices such as `alloy` are weak in Mandarin; use Azure neural voices for Chinese production scenarios
- Over remote desktop the camera requires the client to enable video capture redirection
- Volume control depends on `pycaw` + `comtypes` and is Windows-only
- Image generation requires an image model deployment in the Foundry resource

---

## License

MIT
