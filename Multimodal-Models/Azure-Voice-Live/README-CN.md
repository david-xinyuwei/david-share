# Azure Voice Live 全组件参考表

[![Azure](https://img.shields.io/badge/Azure-Voice%20Live-0078D4?logo=microsoftazure&logoColor=white)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
[![API](https://img.shields.io/badge/API-2026--01--01--preview-b11f4b)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
[![证据](https://img.shields.io/badge/结论-逐条标注来源强度-16a34a)](#证据等级)
[![离线](https://img.shields.io/badge/离线版-单文件%20HTML-f59e0b)](./azure-voice-live-components.html)

把 **Azure Voice Live** 能接的每一个组件，按语音 Agent 的三层拆开 —— **听（STT）→ 想（LLM/SLM）→ 说（TTS）**。每一行左边是可读的展示名，右边是**写 JSON 时必须填的官方 API 值**。

> Author: 魏新宇 (Xinyu Wei) — Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

[English](./README.md) &nbsp;|&nbsp; [离线 HTML 版](./azure-voice-live-components.html)（深浅色切换 + 打印样式）

> [!IMPORTANT]
> **展示名**那一列是本文的可读命名约定，**不是 schema**。写 JSON 时一律使用 **API 实际值**那一列。

---

## 最容易看错的一点

`voice.type` 承载着**两种本质不同的语义**：

| 性质 | 值 | 有独立 TTS 环节吗 |
|---|---|:---:|
| **原生发声** —— 端到端模型自己出音频 | `openai`、`azure-realtime-native` | **没有** |
| **外接合成** —— 文本送进 Azure Speech 引擎 | `azure-standard`、`azure-custom`、`azure-personal`、`avatar-voice-sync` | **有** |

`gpt-realtime` 和 `azure-realtime` 是 **speech-to-speech 端到端**模型：音频进、音频出，**根本没有独立 TTS 环节**。这时 `voice.type` 只是"选哪个声线"，不会插入合成步骤。

这一条能解释另外两个看起来很随意的行为：

- **`instructions` 只对 OpenAI voice 生效**。官方原文：*"The instructions could guide the output audio if OpenAI voices are used but may not apply to Azure voices."* 因为原生发声时，**语音本身就是推理的一部分**。
- **换成 Azure 自定义音色会增加延迟** —— 端到端链路被打断，插入了真实的合成环节。

---

## 一、全组件总表

### ① STT — 听 &nbsp;·&nbsp; 配置位置 `input_audio_transcription.model`

| 展示名 | **API 实际值** | 关键约束 |
|---|---|---|
| **Azure-Speech-STT** | `azure-speech` | **默认自动激活**。**唯一**支持 Phrase List + Custom Speech（最多 10 个 locale） |
| MAI-Transcribe-STT | `mai-transcribe` | 微软 preview；可配全部非多模态模型 |
| OpenAI-Whisper-STT | `whisper-1` | **仅配 `gpt-realtime*`**；不支持 Phrase List |
| OpenAI-GPT4o-STT | `gpt-4o-transcribe` | 同上；可用 `prompt` 引导术语 |
| OpenAI-GPT4o-mini-STT | `gpt-4o-mini-transcribe` | 同上；成本更低 |
| OpenAI-GPT4o-Diarize-STT | `gpt-4o-transcribe-diarize` | 同上；带说话人分离 |

### ② LLM / SLM — 想 &nbsp;·&nbsp; 配置位置 WebSocket `?model=`

| 展示名 | **API 实际值** | 听 | 说 | 说明 |
|---|---|:---:|:---:|---|
| GPT-Realtime `LLM` | `gpt-realtime` / `-1.5` / `-mini` | ✅ | ✅ | 官方写 *"**option to** use Azure TTS"* —— 自带语音，可换 |
| Azure-Realtime `LLM` | `azure-realtime` | ✅ | ✅ | 需 API `2026-01-01-preview` 及以上 |
| **Phi4-MM-Realtime `SLM`** | `phi4-mm-realtime` | ✅ | **❌** | 官方无 *"option to"* 字样 → **必须外接 TTS** ⚠️ |
| **纯文本 `LLM`/`SLM`** | `phi4-mini` `SLM` · `gpt-4o` `-mini` · `gpt-4.1` `-mini` `-nano` · `gpt-5.4` `gpt-5.3-chat` `gpt-5.2` `gpt-5.2-chat` `gpt-5.1` `gpt-5.1-chat` `gpt-5` `-mini` `-nano` | ❌ | ❌ | 没耳朵没嘴 → **① 和 ③ 都必须配** |

### ③ TTS — 说 &nbsp;·&nbsp; 配置位置 `voice.type`

| 展示名 | **API 实际值** | 性质 | 关键约束 |
|---|---|---|---|
| **Azure-Speech-TTS-standard** | `azure-standard` | 外接合成 | Neural / HD / **MAI-Voice-2-Flash**；参数 `name` `rate` `temperature` `custom_lexicon_url` |
| **Azure-Speech-TTS-custom** | `azure-custom` | 外接合成 | 品牌专属音色（Professional CNV）；**必须给 `endpoint_id`**（GUID） |
| **Azure-Speech-TTS-personal** | `azure-personal` | 外接合成 | 短样本克隆；**必须给 `model`**（`DragonLatestNeural` / `DragonHDOmniLatestNeural` / `MAI-Voice-1`） |
| **Azure-Speech-TTS-avatar-sync** | `avatar-voice-sync` | 外接合成 | 配 custom avatar；只要 `model`，**不要 `name`** |
| Azure-Realtime 原生声线 | `azure-realtime-native` | **原生发声** | **不是 TTS 引擎**。仅 `azure-realtime` 可用；30 个音色，默认 `ava`，中文 `xiaoxiao` / `yunxi` |
| OpenAI 原生声线 | `openai` | **原生发声** | **不是 TTS 引擎**。官方对象 `RealtimeOpenAIVoice`；10 个音色 `alloy` `ash` `ballad` `coral` `echo` `sage` `shimmer` `verse` `marin` `cedar`；**独有 `instructions`**，可用自然语言控制语气 |

---

## 二、Azure Speech 一共 5 个入口

`azure-speech` 这个字面值**只存在于 STT 配置里**。输出侧的 Azure Speech 用四个 `azure-*` 值表示 —— 因为每种必填参数不同（tagged union 设计，一个名字承载不了）。

| 组件 | 属于 Azure Speech | 说明 |
|---|:---:|---|
| Azure-Speech-**STT** `azure-speech` | ✅ | 语音转文字 |
| Azure-Speech-**TTS-standard** `azure-standard` | ✅ | 预制音色 |
| Azure-Speech-**TTS-custom** `azure-custom` | ✅ | 专业自训品牌音色 |
| Azure-Speech-**TTS-personal** `azure-personal` | ✅ | 个人语音克隆 |
| Azure-Speech-**TTS-avatar-sync** `avatar-voice-sync` | ✅ | 数字人同步语音 |
| Azure-Realtime 原生声线 `azure-realtime-native` | ⚠️ | 另一条产品线；端到端模型的声线选项 |
| MAI-Transcribe-STT `mai-transcribe` | ⚠️ | 微软 MAI 线 |
| OpenAI-* `openai` `whisper-1` … | ❌ | OpenAI 产品线 |

## 三、② 层其实只有 4 类

| 类别 | 代表 | 听 | 说 | 你还需要补什么 |
|---|---|:---:|:---:|---|
| 多模态 LLM（嘴可换） | GPT-Realtime | ✅ | ✅ | 什么都不用补 |
| 多模态 LLM（Azure 线） | Azure-Realtime | ✅ | ✅ | 什么都不用补 |
| **多模态 SLM（有耳无嘴）** | Phi4-MM-Realtime | ✅ | **❌** | **只补 ③ TTS** |
| **纯文本 LLM / SLM** | Phi4-Mini · GPT-4o / 4.1 / 5 全系 | ❌ | ❌ | **① 和 ③ 都要补** |

**LLM vs SLM** —— `phi4-mm-realtime` 和 `phi4-mini` 是微软 **Phi 小模型**，车载 / 边缘定位，计费走 **lite 最低档**。② 层其余都是 Azure OpenAI 大模型。

## 四、STT × 模型 配对矩阵

| STT | 纯文本 LLM/SLM | GPT-Realtime | Azure-Realtime | Phi4-MM |
|---|:---:|:---:|:---:|:---:|
| **Azure-Speech-STT** | ✅ **默认** | ❌ | ❌ | ❌ |
| MAI-Transcribe-STT | ✅ | ❌ | ❌ | ❌ |
| OpenAI-Whisper-STT | ❌ | ✅ 旁路 | ❌ | ❌ |
| OpenAI-GPT4o-STT 三兄弟 | ❌ | ✅ 旁路 | ❌ | ❌ |

**旁路** = Realtime 模型自带耳朵，这里配转录模型只是额外产出一份文字记录，不改变语音理解路径。多模态模型（含 `phi4-mm-realtime`）不接外部 STT。

## 五、五种典型链路

| 链路 | ① STT | ② LLM / SLM | ③ TTS | 适用场景 |
|---|---|---|---|---|
| **A · Cascade** | Azure-Speech-STT | 纯文本 **LLM** | TTS-standard / TTS-custom | **要 Phrase List / Custom Speech / fine-tune** |
| **B · GPT 原生** | 自带 | GPT-Realtime **LLM** —— **端到端 S2S，无独立 TTS 环节**；`voice.type="openai"` 只是选声线 | — | **最低延迟** |
| **C · Hybrid** | 自带 | GPT-Realtime **LLM** | **Azure-Speech-TTS-custom** —— *真的插入独立 TTS 环节* | **要品牌专属音色**；代价 = 端到端被打断 → 延迟增加 |
| **D · Phi 低成本** | 自带 | **Phi4-MM-Realtime `SLM`** | **必须外接 Azure-Speech-TTS-\*** | 官方车载 Scenario 4，lite 档最省 |
| **E · Azure 全栈** | 自带 | Azure-Realtime **LLM** —— **端到端 S2S，无独立 TTS 环节**；`voice.type="azure-realtime-native"` | — | 中文音色内置（`xiaoxiao` / `yunxi`） |

## 六、配置示例

**A · Cascade** —— 纯文本 LLM，① 和 ③ 都要配：

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

**D · Phi 低成本** —— SLM 自带耳朵，只补 ③：

```jsonc
// ...?model=phi4-mm-realtime
{
  "voice": { "type": "azure-standard", "name": "zh-CN-XiaoxiaoNeural" }
}
```

**为什么四种 TTS 不能合并成一个名字** —— 每种必填字段都不同：

```jsonc
{ "type": "azure-standard", "name": "en-US-AvaNeural" }

{ "type": "azure-custom", "name": "en-US-CustomNeural",
  "endpoint_id": "your-endpoint-id" }            // <- 多了这个

{ "type": "azure-personal", "name": "your-voice",
  "model": "DragonLatestNeural" }                // <- 多了这个

{ "type": "avatar-voice-sync",
  "model": "DragonHDOmniLatestNeural" }          // <- 没有 name
```

## 七、计费档位

| 档位 | 模型 | 类型 |
|---|---|---|
| **pro** | `gpt-realtime`、`gpt-4o`、`gpt-4.1`、`gpt-5`、`gpt-5-chat` | LLM |
| **basic** | `gpt-realtime-mini`、`gpt-4o-mini`、`gpt-4.1-mini`、`gpt-5-mini` | LLM |
| **lite** | `gpt-5-nano` | LLM |
| **lite** | `phi4-mm-realtime`、`phi4-mini` | **SLM** |
| ❓ 未列出 | `azure-realtime`、`gpt-realtime-1.5`、`gpt-5.1`–`gpt-5.4` | — |

Token 换算速率：Azure OpenAI 约 **10 / 20**；Phi SLM 约 **12.5 / 20**（输入 / 输出，tokens 每秒）。

## 证据等级

| 等级 | 含义 |
|---|---|
| ✅✅ | 两个独立官方页面交叉验证 |
| ✅ | 单一官方来源 |
| ⚠️ | 推断，或单源未交叉 |
| ❓ | 未知 / 官方未公布 |

| 等级 | 内容 |
|---|---|
| ✅✅ | STT × 模型兼容矩阵；Phrase List 不支持 `whisper-1` / `gpt-4o-transcribe` / `-mini-transcribe` / `-transcribe-diarize`；Custom Speech 仅支持 `azure-speech`；`azure-standard` 与 `azure-custom` 的参数结构；MAI-Voice-2-Flash 及其 4 个中文音色（`zh-CN-Bo` / `Lan` / `Mei` / `Wei`） |
| ✅ | ② 层模型清单；Phi 的 SLM 定位；`azure-realtime` 的 30 个音色与默认 `ava`；`azure-personal`；`avatar-voice-sync`；`RealtimeOpenAIVoice` 完整定义（含 `instructions` 字段）；官方四分法 *"OpenAI voices, Azure custom voices, Azure standard voices, and Azure personal voices"* |
| ⚠️ | **`phi4-mm-realtime` 不能原生出声** —— 依据是官方缺少 *"option to use"* 字样，加上计费 Scenario 4 把它的原生音频与 Azure Speech Custom 输出**分开计费**。微软没有用一句话明确说过这件事。 |
| ⚠️ | 计费档位与 token 换算速率 —— 单一官方页面，未交叉验证 |
| ❓ | `azure-realtime`、`gpt-realtime-1.5`、`gpt-5.1`–`gpt-5.4` 的计费档位；计费页的通用名 `gpt-5-chat` 与模型清单的 `gpt-5.1-chat` / `5.2-chat` / `5.3-chat` 是否一一对应 —— **正式报价前必须确认** |

## 适用范围与限制

- 基于 **Voice Live API `2026-01-01-preview`**。Preview 接口会变，落设计前请重新核对当前官方文档。
- 本表**不含延迟基准数据**。延迟取决于 region、音色、文本长度和网络路径，请在自己的环境实测。
- 计费信息未经交叉验证，**不能直接作为报价依据**。

## 官方来源

- [Voice Live API Reference — `2026-01-01-preview`](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-01-01-preview)
- [Voice Live 概述](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [如何使用 Voice Live API](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to)
- [在 Voice Live 中自定义语音与 Avatar](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to-customize)
