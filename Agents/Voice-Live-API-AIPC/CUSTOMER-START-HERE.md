# Customer Start Here - Voice Live API for AIPC

[English](CUSTOMER-START-HERE.md) | [中文](CUSTOMER-START-HERE-CN.md)

Use this page for the shortest verified Windows path. Read [README.md](README.md) for architecture, evidence, optional providers, and security boundaries.

## What you need

- Windows 10/11, Python 3.11-3.13, microphone, and speaker
- A Microsoft Foundry resource in a Voice Live supported region
- The resource endpoint and either an API key or an Entra identity with `Cognitive Services User` and `Foundry User`

## Install

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
Set-Location .\david-share\Agents\Voice-Live-API-AIPC
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## Configure

Edit `.env` with your own resource values. For the shortest local demo path:

```ini
AZURE_VOICELIVE_ENDPOINT=https://<your-resource>.services.ai.azure.com/
AZURE_VOICELIVE_MODEL=gpt-realtime
AZURE_VOICELIVE_VOICE=zh-CN-XiaoxiaoMultilingualNeural
AZURE_VOICELIVE_API_KEY=<your-api-key>
```

`.env` is ignored by Git. Never paste the key into a command, issue, log, or screenshot.

## Verify without opening the microphone

```powershell
.\.venv\Scripts\python.exe -m scripts.preflight --mode voicelive --dry-run
.\.venv\Scripts\python.exe -m scripts.preflight --mode voicelive
```

Accept the setup only when the offline gate serializes 24 tools and the live gate receives `session.updated` with all 24 tools accepted.

## Run

```powershell
.\run.cmd
```

Select **Start conversation**. First test a harmless request such as time or weather before enabling camera, Windows power, wallpaper, or mail side effects.

Camera open/capture, timezone, power, wallpaper, image generation, and mail are code-protected actions. The first call cannot execute; review the summarized action and confirm it in a separate user turn. Changed, replayed, expired, or cancelled confirmations are rejected.

## Optional mail delivery

Mail is not a fixture: after the separate confirmation it sends through Microsoft Graph by default. Configure a public-client app, delegated `Mail.Send`, `GRAPH_CLIENT_ID`, and `MAIL_ALLOWED_RECIPIENTS`, then run:

```powershell
.\.venv\Scripts\python.exe -m scripts.graph_login
```

See [README.md](README.md#microsoft-graph-mail) and [SECURITY.md](SECURITY.md) before enabling delivery.
