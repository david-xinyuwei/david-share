# Azure Voice Live — Component Reference

[![Azure](https://img.shields.io/badge/Azure-Voice%20Live-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
[![API](https://img.shields.io/badge/API-2026--01--01--preview-b11f4b)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
[![Evidence](https://img.shields.io/badge/claims-source--graded-16a34a)](#evidence-grading)
[![Offline](https://img.shields.io/badge/offline-single--file%20HTML-f59e0b)](./azure-voice-live-components.html)

Every component you can plug into **Azure Voice Live**, mapped across the three layers of a voice agent — **listen (STT) → think (LLM/SLM) → speak (TTS)**. Each row pairs a readable display name with the **exact API enum value** you must write in JSON.

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

[中文版](./README-CN.md) &nbsp;|&nbsp; [Offline HTML](./azure-voice-live-components.html) (dark mode + print styles)

> [!IMPORTANT]
> The **Display name** column is a readability convention of this document, **not schema**. When writing JSON, always use the **API literal** column.

---

## The distinction most people miss

`voice.type` carries **two fundamentally different semantics**:

| Kind | Values | Separate TTS stage? |
|------|--------|:---:|
| **Native voice** — the end-to-end model emits audio itself | `openai`, `azure-realtime-native` | **No** |
| **External synthesis** — text is sent to the Azure Speech engine | `azure-standard`, `azure-custom`, `azure-personal`, `avatar-voice-sync` | **Yes** |

For `gpt-realtime` and `azure-realtime` the model is **speech-to-speech end-to-end** — audio in, audio out, with no TTS stage at all. There, `voice.type` only picks a voice; it does not insert a synthesis step.

This single fact explains two behaviours that otherwise look arbitrary:

- **`instructions` steers output audio only for OpenAI voices.** Official wording: *"The instructions could guide the output audio if OpenAI voices are used but may not apply to Azure voices."* With a native voice, speech **is** part of the inference.
- **Switching to an Azure custom voice adds latency** — it breaks the end-to-end path and inserts a real synthesis stage.

---

## 1. Full component table

### ① STT — listen &nbsp;·&nbsp; `input_audio_transcription.model`

| Display name | **API literal** | Constraints |
|---|---|---|
| **Azure-Speech-STT** | `azure-speech` | **On by default.** The **only** model supporting Phrase List + Custom Speech (max 10 locales) |
| MAI-Transcribe-STT | `mai-transcribe` | Microsoft preview; pairs with all non-multimodal models |
| OpenAI-Whisper-STT | `whisper-1` | **Only with `gpt-realtime*`**; no Phrase List |
| OpenAI-GPT4o-STT | `gpt-4o-transcribe` | Same; supports `prompt` for terminology hints |
| OpenAI-GPT4o-mini-STT | `gpt-4o-mini-transcribe` | Same; lower cost |
| OpenAI-GPT4o-Diarize-STT | `gpt-4o-transcribe-diarize` | Same; adds speaker diarization |

### ② LLM / SLM — think &nbsp;·&nbsp; WebSocket `?model=`

| Display name | **API literal** | Listen | Speak | Note |
|---|---|:---:|:---:|---|
| GPT-Realtime `LLM` | `gpt-realtime` / `-1.5` / `-mini` | ✅ | ✅ | *"**option to** use Azure TTS"* — native voice, replaceable |
| Azure-Realtime `LLM` | `azure-realtime` | ✅ | ✅ | Requires API `2026-01-01-preview`+ |
| **Phi4-MM-Realtime `SLM`** | `phi4-mm-realtime` | ✅ | **❌** | No *"option to"* wording → **external TTS required** ⚠️ |
| **Text-only `LLM`/`SLM`** | `phi4-mini` `SLM` · `gpt-4o` `-mini` · `gpt-4.1` `-mini` `-nano` · `gpt-5.4` `gpt-5.3-chat` `gpt-5.2` `gpt-5.2-chat` `gpt-5.1` `gpt-5.1-chat` `gpt-5` `-mini` `-nano` | ❌ | ❌ | No ears, no mouth → **both ① and ③ required** |

### ③ TTS — speak &nbsp;·&nbsp; `voice.type`

| Display name | **API literal** | Kind | Constraints |
|---|---|---|---|
| **Azure-Speech-TTS-standard** | `azure-standard` | External synthesis | Neural / HD / **MAI-Voice-2-Flash**; params `name` `rate` `temperature` `custom_lexicon_url` |
| **Azure-Speech-TTS-custom** | `azure-custom` | External synthesis | Brand voice (Professional CNV); **requires `endpoint_id`** (GUID) |
| **Azure-Speech-TTS-personal** | `azure-personal` | External synthesis | Short-sample cloning; **requires `model`** (`DragonLatestNeural` / `DragonHDOmniLatestNeural` / `MAI-Voice-1`) |
| **Azure-Speech-TTS-avatar-sync** | `avatar-voice-sync` | External synthesis | For custom avatar; takes `model` only, **no `name`** |
| Azure-Realtime native voice | `azure-realtime-native` | **Native voice** | **Not a TTS engine.** `azure-realtime` only; 30 voices, default `ava`, Chinese `xiaoxiao` / `yunxi` |
| OpenAI native voice | `openai` | **Native voice** | **Not a TTS engine.** Object `RealtimeOpenAIVoice`; 10 voices `alloy` `ash` `ballad` `coral` `echo` `sage` `shimmer` `verse` `marin` `cedar`; **exclusive `instructions`** for natural-language tone control |

---

## 2. Azure Speech has 5 entry points

`azure-speech` as a literal exists **only** in STT config. On the output side, Azure Speech appears as four `azure-*` values — because each requires different mandatory parameters (tagged-union design; one name could not carry them).

| Component | Azure Speech? | Note |
|---|:---:|---|
| Azure-Speech-**STT** `azure-speech` | ✅ | Speech to text |
| Azure-Speech-**TTS-standard** `azure-standard` | ✅ | Prebuilt voices |
| Azure-Speech-**TTS-custom** `azure-custom` | ✅ | Professionally trained brand voice |
| Azure-Speech-**TTS-personal** `azure-personal` | ✅ | Personal voice cloning |
| Azure-Speech-**TTS-avatar-sync** `avatar-voice-sync` | ✅ | Avatar-synced speech |
| Azure-Realtime native voice `azure-realtime-native` | ⚠️ | Different product line; a voice option of the end-to-end model |
| MAI-Transcribe-STT `mai-transcribe` | ⚠️ | Microsoft MAI line |
| OpenAI-* `openai` `whisper-1` … | ❌ | OpenAI line |

## 3. Layer ② has only 4 classes

| Class | Example | Listen | Speak | What you must add |
|---|---|:---:|:---:|---|
| Multimodal LLM (voice replaceable) | GPT-Realtime | ✅ | ✅ | Nothing |
| Multimodal LLM (Azure line) | Azure-Realtime | ✅ | ✅ | Nothing |
| **Multimodal SLM (ears, no mouth)** | Phi4-MM-Realtime | ✅ | **❌** | **③ TTS only** |
| **Text-only LLM / SLM** | Phi4-Mini · GPT-4o / 4.1 / 5 | ❌ | ❌ | **Both ① and ③** |

**LLM vs SLM** — `phi4-mm-realtime` and `phi4-mini` are Microsoft **Phi small language models**, positioned for in-car / edge, billed at the **lite** tier. Everything else in layer ② is an Azure OpenAI LLM.

## 4. STT × model compatibility

| STT | Text-only LLM/SLM | GPT-Realtime | Azure-Realtime | Phi4-MM |
|---|:---:|:---:|:---:|:---:|
| **Azure-Speech-STT** | ✅ **default** | ❌ | ❌ | ❌ |
| MAI-Transcribe-STT | ✅ | ❌ | ❌ | ❌ |
| OpenAI-Whisper-STT | ❌ | ✅ side-channel | ❌ | ❌ |
| OpenAI-GPT4o-STT ×3 | ❌ | ✅ side-channel | ❌ | ❌ |

**Side-channel** = the Realtime model already hears; the transcription model only produces an extra text record. Multimodal models (including `phi4-mm-realtime`) do not take an external STT.

## 5. Five reference pipelines

| Pipeline | ① STT | ② LLM / SLM | ③ TTS | Use when |
|---|---|---|---|---|
| **A · Cascade** | Azure-Speech-STT | Text-only **LLM** | TTS-standard / TTS-custom | **Phrase List / Custom Speech / fine-tune needed** |
| **B · GPT native** | built-in | GPT-Realtime **LLM** — **end-to-end S2S, no TTS stage**; `voice.type="openai"` just picks a voice | — | **Lowest latency** |
| **C · Hybrid** | built-in | GPT-Realtime **LLM** | **Azure-Speech-TTS-custom** — *real synthesis stage inserted* | **Brand voice required**; cost = end-to-end path broken → added latency |
| **D · Phi low-cost** | built-in | **Phi4-MM-Realtime `SLM`** | **Azure-Speech-TTS-\* required** | Official in-car Scenario 4; lite tier |
| **E · Azure full-stack** | built-in | Azure-Realtime **LLM** — **end-to-end S2S, no TTS stage**; `voice.type="azure-realtime-native"` | — | Built-in Chinese voices (`xiaoxiao` / `yunxi`) |

## 6. Config examples

**A · Cascade** — text-only LLM, both ① and ③ required:

```jsonc
// wss://<resource>/voice-live/realtime?api-version=2026-04-10&model=gpt-4.1
{
  "input_audio_transcription": {
    "model": "azure-speech",                  // Azure-Speech-STT
    "phrase_list": ["Contoso", "Fabrikam"],
    "custom_speech": { "zh-CN": "<model-id>" }
  },
  "voice": {
    "type": "azure-custom",                   // Azure-Speech-TTS-custom
    "name": "zh-CN-BrandNeural",
    "endpoint_id": "<your-endpoint-guid>"
  },
  "turn_detection": { "type": "azure_semantic_vad_multilingual" }
}
```

**D · Phi low-cost** — SLM already hears, only ③ needed:

```jsonc
// ...?model=phi4-mm-realtime
{
  "voice": { "type": "azure-standard", "name": "zh-CN-XiaoxiaoNeural" }
}
```

**Why the four TTS types cannot share one name** — each has a different required shape:

```jsonc
{ "type": "azure-standard", "name": "en-US-AvaNeural" }

{ "type": "azure-custom", "name": "en-US-CustomNeural",
  "endpoint_id": "your-endpoint-id" }            // <- extra

{ "type": "azure-personal", "name": "your-voice",
  "model": "DragonLatestNeural" }                // <- extra

{ "type": "avatar-voice-sync",
  "model": "DragonHDOmniLatestNeural" }          // <- no name
```

## 7. Billing tiers

| Tier | Models | Type |
|---|---|---|
| **pro** | `gpt-realtime`, `gpt-4o`, `gpt-4.1`, `gpt-5`, `gpt-5-chat` | LLM |
| **basic** | `gpt-realtime-mini`, `gpt-4o-mini`, `gpt-4.1-mini`, `gpt-5-mini` | LLM |
| **lite** | `gpt-5-nano` | LLM |
| **lite** | `phi4-mm-realtime`, `phi4-mini` | **SLM** |
| ❓ unlisted | `azure-realtime`, `gpt-realtime-1.5`, `gpt-5.1`–`gpt-5.4` | — |

Token conversion: Azure OpenAI ≈ **10 / 20**; Phi SLM ≈ **12.5 / 20** (input / output, tokens per second).

## Evidence grading

| Grade | Meaning |
|-------|---------|
| ✅✅ | Cross-verified across two independent official pages |
| ✅ | Single official source |
| ⚠️ | Inference, or single source not yet cross-checked |
| ❓ | Unknown / not published |

| Grade | Content |
|---|---|
| ✅✅ | STT × model compatibility; Phrase List unsupported for `whisper-1` / `gpt-4o-transcribe` / `-mini-transcribe` / `-transcribe-diarize`; Custom Speech only on `azure-speech`; `azure-standard` and `azure-custom` parameter shapes; MAI-Voice-2-Flash and its 4 Chinese voices (`zh-CN-Bo` / `Lan` / `Mei` / `Wei`) |
| ✅ | Layer ② model roster; Phi as SLM; `azure-realtime` 30 voices and default `ava`; `azure-personal`; `avatar-voice-sync`; full `RealtimeOpenAIVoice` definition incl. the `instructions` field; the official four-way split *"OpenAI voices, Azure custom voices, Azure standard voices, and Azure personal voices"* |
| ⚠️ | **`phi4-mm-realtime` cannot speak natively** — inferred from the missing *"option to use"* wording plus the billing scenario metering its native audio and Azure Speech Custom output **separately**. Not stated by Microsoft in one explicit sentence. |
| ⚠️ | Billing tiers and token rates — single official page, not cross-verified |
| ❓ | Billing tier for `azure-realtime`, `gpt-realtime-1.5`, `gpt-5.1`–`gpt-5.4`; whether pricing-page `gpt-5-chat` maps 1:1 to roster `gpt-5.1-chat` / `5.2-chat` / `5.3-chat` — **confirm before quoting a price** |

## Scope and limitations

- Built against **Voice Live API `2026-01-01-preview`**. Preview surfaces change — re-verify before committing to a design.
- No latency benchmarks here. Latency depends on region, voice, text length and network path — measure in your own environment.
- Billing figures are **not** a quotation basis without confirmation.

## Sources

- [Voice Live API Reference — `2026-01-01-preview`](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [How to use the Voice Live API](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to)
- [Customize voice and avatar in Voice Live](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to-customize)
