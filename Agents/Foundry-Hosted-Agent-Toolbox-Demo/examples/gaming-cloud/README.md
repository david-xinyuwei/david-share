# Gaming Cloud Demo

Three gaming scenarios that demonstrate how a Hosted Agent + Toolbox serves a cloud gaming platform.

## Scenarios

| # | Scenario | Tools used | What it shows |
|:-:|---|---|---|
| 1 | **Player Support** — diagnose frame drops from telemetry | `code_interpreter` (stats) + `file_search` (game knowledge) | Cloud agent replaces human support — analyzes data + retrieves docs |
| 2 | **Game Art Generation** — create concept art from text | `direct_image_generate` | Cloud agent generates UGC / loading screens on demand |
| 3 | **Post-match Intel** — search + analyze esports data | `direct_web_search` + `code_interpreter` | Cloud agent combines live web data with computed analysis |

## Prerequisites

1. Hosted agent running: `python main.py` (from repo root)
2. Toolbox includes `code_interpreter` + `file_search`
3. `.env` has `ENABLE_DIRECT_WEB_SEARCH=true` and (for scenario 2) `ENABLE_DIRECT_IMAGE_GENERATE=true`

## Run

All three scenarios:

```bash
python examples/gaming-cloud/gaming_demo.py
```

One specific scenario:

```bash
python examples/gaming-cloud/gaming_demo.py --scenario 1   # Player Support only
python examples/gaming-cloud/gaming_demo.py --scenario 2   # Game Art only
python examples/gaming-cloud/gaming_demo.py --scenario 3   # Post-match Intel only
```

## What customers see

This demo answers the question gaming teams ask: **"What can a cloud-side agent do for my game when local GPU is already busy rendering?"**

The answer: **computation, knowledge retrieval, web grounding, and image generation — all happen in the cloud, zero local GPU load.**

The device only sends a text prompt (or voice-to-text result) and receives a text answer (or an image URL). All heavy lifting — model inference, Python execution, document search, Bing grounding, image generation — runs in the Foundry cloud behind a single `/responses` endpoint.
