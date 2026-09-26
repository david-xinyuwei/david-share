# US image-model test pack (for Andre)

Measures MAI-Image-2.6, GPT-Image-2 (low / high) and GPT-Image-2.5 flare + sunburst (auto / low / high) against East US / East US 2 deployments from one laptop, so the timings include the client-to-Azure path a user would actually see. Run it from a US laptop to get US-client numbers; the published run's client location is recorded in `runs/<name>/CLIENT-LOCATION.json`.

| | |
|---|---|
| Groups | 9 = MAI-Image-2.6 + gpt-image-2 × {low, high} + gpt-image-2.5-flare × {auto, low, high} + gpt-image-2.5-sunburst × {auto, low, high} |
| Prompts | 17 = 11 from the published benchmark repo + 6 from Anzhe's Sept 14–17 report |
| Rounds | 2, second round in reverse group order (cancels warm-up bias) |
| Images | 306 formal + 9 warm-up, all 1024×1024 PNG |
| Resources | GPT: `xinyuwei-2026-resource` (East US 2) · MAI: `xinyuwei-2026-eastus-img` (East US) |
| Auth | Entra ID bearer token from `az account get-access-token` — **no API keys**. Key auth is disabled on both resources by subscription policy (`disableLocalAuth=true`; a PATCH to `false` is reverted within seconds by the `CognitiveServices_LocalAuth_Modify` policy). |
| Pacing | 5 s between calls, 2 requests/min per deployment (matches provisioned capacity) |
| Runtime | roughly 4–5 h unattended; resumable |

## Prerequisites

1. Python 3.11+ and [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) on PATH.
2. `az login` as an identity that holds **Cognitive Services User** (for MAI) and **Cognitive Services OpenAI User** (for GPT), or Owner, on the two accounts above. Xinyu grants the role assignments; nothing else is shared.
3. Check the sign-in once: `az account get-access-token --resource https://cognitiveservices.azure.com --query expiresOn -o tsv` must print a timestamp.

The runner reads the expiry inside each token and fetches a new one when under 6 minutes remain (and immediately on any HTTP 401), so a 4–5 h run does not need re-login.

## Run it

The benchmark lives in one directory of a large repository; check out only that directory:

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Multimodal-Models/Image-Generation-US-Region-Benchmark
cd Multimodal-Models\Image-Generation-US-Region-Benchmark\testpack
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_us_matrix.py --dry-run   # validates prompts + endpoints, no network
.\.venv\Scripts\python.exe run_us_matrix.py --smoke     # 9 warm-up images, ~5 min, proves auth on every deployment
.\.venv\Scripts\python.exe run_us_matrix.py             # full matrix, resumes past the warm-ups
```

Linux/macOS: same commands with `.venv/bin/python`. No `.env` is needed; copy `.env.example` to `.env` only to override an endpoint or the client-location label.

Smoke-tested 2026-09-26 from Xinyu's laptop: 10/10 warm-ups returned images through the same code path.

If the laptop sleeps or the run is interrupted, run the last command again — `--resume` skips every sample already recorded.

## What to send back

Zip the whole `runs/us-matrix-<date>/` folder. It contains:

- `5way_v2_results.json` — one record per image: elapsed seconds, token usage, image SHA-256, HTTP request IDs
- `attempts.jsonl` — every HTTP attempt including retries and 429s
- `responses/` — API response metadata (base64 stripped)
- `<group>/r1/`, `<group>/r2/` — the images
- `RUN-INFO.txt` — runner and prompt hashes, client location, auth mode, exact command

Nothing in that folder contains a credential: the bearer token lives only in process memory. `.env` (if you created one) is git-ignored and stays on your machine.

## What the numbers mean

- `time` is wall-clock seconds from `requests.post` until the full response body arrived. It includes DNS, TLS, queueing, generation and download.
- Token counts are what each API returned (`usage.output_tokens` for GPT, `num_output_tokens` for MAI). GPT tiers are fixed per tier (196 / 439 or 1,756 / 7,024); MAI is a constant 1,024 per image.
- Cost is not computed by the runner; Xinyu applies list prices afterwards.
