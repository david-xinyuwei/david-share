# Azure Voice Live — Component Reference

[![Azure](https://img.shields.io/badge/Azure-Voice%20Live-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
[![API](https://img.shields.io/badge/API-2026--01--01--preview-b11f4b)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
[![Format](https://img.shields.io/badge/format-single--file%20HTML-16a34a)](./azure-voice-live-components.html)
[![Language](https://img.shields.io/badge/lang-中文-orange)](./azure-voice-live-components.html)

A single-file, self-contained reference table for every component you can plug into **Azure Voice Live** — mapped across the three layers of a voice agent: **listen (STT) → think (LLM/SLM) → speak (TTS)**. Each row pairs a human-readable display name with the **exact API enum value** you must write in JSON, so you never guess a config value again.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

[**▶ View the reference table online**](https://htmlpreview.github.io/?https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/Azure-Voice-Live/azure-voice-live-components.html) &nbsp;|&nbsp; [Download HTML](./azure-voice-live-components.html) &nbsp;|&nbsp; The reference content is written in Chinese.

---

## Why this exists

Voice Live's configuration surface is easy to get wrong in three specific ways, and all three cause real integration bugs:

1. **The same brand name maps to different config fields.** `azure-speech` is a valid literal *only* in `input_audio_transcription.model`. On the output side, Azure Speech appears as **four different** `voice.type` values — because each one requires different mandatory parameters.
2. **`voice.type` is not always a TTS engine.** For `gpt-realtime` and `azure-realtime`, the model is **speech-to-speech end-to-end** — audio in, audio out, with *no separate TTS stage*. There, `voice.type` only selects a voice; it does not insert a synthesis step.
3. **Capability is not symmetric.** `phi4-mm-realtime` can listen and think, but the official model table does not grant it the "option to use Azure TTS" wording that `gpt-realtime` gets — so an external TTS must be attached.

This reference makes all three explicit in one table.

## What's inside

| # | Section | Content |
|---|---------|---------|
| 1 | **Full component table** | All three layers expanded — display name ↔ **API literal** ↔ config location ↔ listen/think/speak ↔ constraints |
| 2 | **Azure Speech entry points** | 1 STT + 4 TTS, and which values do *not* belong to Azure Speech |
| 3 | **Layer ② has only 4 classes** | Plus the LLM vs SLM split |
| 4 | **STT × model compatibility matrix** | Which transcription model pairs with which model family |
| 5 | **Five reference pipelines** | Cascade / GPT-native / Hybrid / Phi low-cost / Azure full-stack |
| 6 | **Config examples** | Real JSON, including why the four TTS types cannot share one name |
| 7 | **Billing tiers** | pro / basic / lite mapping |
| 8 | **Evidence grading** | Every claim tagged by source strength |

## The key distinction most people miss

`voice.type` carries **two fundamentally different semantics**:

| Kind | Values | Separate TTS stage? |
|------|--------|:---:|
| **Native voice** — the end-to-end model emits audio itself | `openai`, `azure-realtime-native` | **No** |
| **External synthesis** — text is sent to the Azure Speech engine | `azure-standard`, `azure-custom`, `azure-personal`, `avatar-voice-sync` | **Yes** |

This single distinction explains two behaviours that otherwise look arbitrary:

- The `instructions` field steers output audio **only** for OpenAI voices — official wording: *"The instructions could guide the output audio if OpenAI voices are used but may not apply to Azure voices."* Because with a native voice, speech **is** part of the inference.
- Switching a `gpt-realtime` session to an Azure custom voice **adds latency** — because it breaks the end-to-end path and inserts a real synthesis stage.

## Evidence grading

Every claim in the table carries a grade. Nothing is stated more strongly than its source allows.

| Grade | Meaning |
|-------|---------|
| ✅✅ | Cross-verified across two independent official pages |
| ✅ | Single official source |
| ⚠️ | Inference, or single source not yet cross-checked |
| ❓ | Unknown / not published |

Notable entries:

- ⚠️ **`phi4-mm-realtime` cannot speak natively** — inferred from the absence of the *"option to use"* wording plus the billing scenario that meters its native audio and the Azure Speech Custom output **separately**. Microsoft has not stated this in one explicit sentence.
- ❓ **Billing tier unpublished** for `azure-realtime`, `gpt-realtime-1.5`, and `gpt-5.1`–`gpt-5.4`.
- ⚠️ **Naming mismatch** — the pricing page uses the generic `gpt-5-chat`, while the model roster uses point-versioned `gpt-5.1-chat` / `gpt-5.2-chat` / `gpt-5.3-chat`. Confirm the mapping before quoting a price.

## Scope and limitations

- Built against **Voice Live API `2026-01-01-preview`**. Preview surfaces change; re-verify against current docs before committing to a design.
- The left column of the table is a **readability convention**, not a schema. Always write the middle column (the API literal) in JSON.
- Billing tiers and token rates come from a single official page and are **not cross-verified**. Do not use them as a quotation basis without confirmation.
- No latency benchmarks are included here. Latency depends on region, voice, text length, and network path — measure it in your own environment.

## Sources

- [Voice Live API Reference — `2026-01-01-preview`](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [How to use the Voice Live API](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to)
- [Customize voice and avatar in Voice Live](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to-customize)

## Usage

The HTML is fully self-contained — no build step, no external assets, no network calls.

```bash
# open locally
start Multimodal-Models/Azure-Voice-Live/azure-voice-live-components.html   # Windows
open  Multimodal-Models/Azure-Voice-Live/azure-voice-live-components.html   # macOS
```

It follows the OS light/dark preference, has a manual theme toggle, and includes print styles — `Ctrl+P` produces a clean PDF with buttons hidden and table rows kept off page breaks.
