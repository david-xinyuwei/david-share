# 远场英文会议转写：六条 Azure 语音路径，四段 AMI 片段

2026-10-02 · 每个模型跑一次 · 4 段片段，282 s，归一化后 930 个参考词 · 语料：AMI Meeting Corpus, test set, SDM (Array1-01)（CC BY 4.0）

把片段放在这里，是为了让读者听到模型听到的原声，并把人工参考文本和每份机器转写对照着读。这是一份带评分表的试听集，不是
benchmark：每个模型只跑了一次，WER 相差不到约一个点的差距请视为未分出胜负。

## 片段

从四场测试集会议的单个远场麦克风录音（Array1-01）中切出 45–75 s
的窗口，取参考词最多、且说话人重叠低于 15% 的那一段。每段的字节范围、AMI
镜像 URL 和参考分段见 [`manifest.json`](manifest.json)。

| 片段 | 会议 | 窗口 | 时长 | 说话人 | 参考词（原始） | 重叠 | 人工转写 |
|---|---|---|---:|---:|---:|---:|---|
| [`EN2002a_0106p13-0179p93`](clips/EN2002a_0106p13-0179p93.wav) | EN2002a | 106.13–179.93 s | 73.8 s | 4 | 261 | 7% | [reference](clips/EN2002a_0106p13-0179p93.ref.txt) |
| [`ES2004a_0850p73-0912p60`](clips/ES2004a_0850p73-0912p60.wav) | ES2004a | 850.73–912.60 s | 61.9 s | 4 | 223 | 10% | [reference](clips/ES2004a_0850p73-0912p60.ref.txt) |
| [`IS1009a_0685p59-0758p09`](clips/IS1009a_0685p59-0758p09.wav) | IS1009a | 685.59–758.09 s | 72.5 s | 4 | 215 | 8% | [reference](clips/IS1009a_0685p59-0758p09.ref.txt) |
| [`TS3003a_1246p83-1320p78`](clips/TS3003a_1246p83-1320p78.wav) | TS3003a | 1246.83–1320.78 s | 74.0 s | 4 | 225 | 10% | [reference](clips/TS3003a_1246p83-1320p78.ref.txt) |

## 模型

| 公开名称 | 文件中的标识 | 调用方式 |
|---|---|---|
| MAI-Transcribe-2-Streaming | `mai-stream` | Azure AI Foundry realtime transcription session, deployment `mai-transcribe-2-streaming`, 16 kHz PCM sent at real-time pace |
| gpt-live-transcribe | `gpt-live` | Azure OpenAI realtime transcription session, 24 kHz PCM (clips resampled from 16 kHz), sent at real-time pace |
| Azure AI Speech real-time | `speech-rt` | Speech SDK 1.52.0 continuous recognition, `standard` model, en-US, 16 kHz, sent at real-time pace |
| MAI-Transcribe-2 | `mai-batch` | Azure AI Speech Fast Transcription with `enhancedMode.model = MAI-Transcribe-2`, whole file in one request |
| gpt-transcribe | `gpt-batch` | Azure OpenAI `/audio/transcriptions`, deployment `gpt-transcribe`, whole file in one request |
| Azure AI Speech Fast Transcription | `fast-en` | Fast Transcription REST API, en-US, whole file in one request |

流式路径按实时速度、每 100 ms 一块接收音频；整文件路径一次请求收到整个 WAV。六条路径在 2026-10-02 从同一客户端运行。

## 评分

词错误率 =（替换 + 删除 + 插入）/ 参考词数，先经 Whisper 英文文本归一化（`whisper_normalizer.english.EnglishTextNormalizer`），与 Open ASR
Leaderboard 相同。时延取四段片段的中位数。表格由 [`scores.json`](scores.json) 生成；每段、每个模型的转写文本在
[`transcripts/`](transcripts/)。

| Model | WER (all clips) | Errors / ref words | Sub / Del / Ins | EN2002a_0106p13-0179p93 | ES2004a_0850p73-0912p60 | IS1009a_0685p59-0758p09 | TS3003a_1246p83-1320p78 |
|---|---|---|---|---|---|---|---|
| Azure AI Speech Fast Transcription (`fast-en`) | 22.4% | 208 / 930 | 41 / 163 / 4 | 21.1% | 24.2% | 19.1% | 25.0% |
| gpt-transcribe (`gpt-batch`) | 20.5% | 191 / 930 | 40 / 142 / 9 | 21.5% | 18.6% | 16.7% | 25.0% |
| gpt-live-transcribe (`gpt-live`) | 21.3% | 198 / 930 | 49 / 144 / 5 | 20.8% | 19.5% | 18.1% | 26.8% |
| MAI-Transcribe-2 (`mai-batch`) | 15.8% | 147 / 930 | 36 / 96 / 15 | 15.0% | 14.3% | 13.0% | 21.0% |
| MAI-Transcribe-2-Streaming (`mai-stream`) | 17.7% | 165 / 930 | 48 / 103 / 14 | 15.8% | 19.9% | 14.4% | 21.0% |
| Azure AI Speech real-time (`speech-rt`) | 24.8% | 231 / 930 | 56 / 170 / 5 | 23.8% | 24.2% | 17.2% | 33.9% |

| Model | First text, any (s, median) | First finalized text (s, median) | Final text after audio end (s, median) | Whole-file request (s, median) |
|---|---|---|---|---|
| Azure AI Speech Fast Transcription (`fast-en`) | - | - | - | 7.777 |
| gpt-transcribe (`gpt-batch`) | - | - | - | 7.707 |
| gpt-live-transcribe (`gpt-live`) | 2.795 | 2.795 | 1.255 | - |
| MAI-Transcribe-2 (`mai-batch`) | - | - | - | 6.707 |
| MAI-Transcribe-2-Streaming (`mai-stream`) | 0.789 | 2.943 | 0.442 | - |
| Azure AI Speech real-time (`speech-rt`) | 3.744 | 11.125 | 0.583 | - |

时延列的读法："first text" 是音频开始流式发送后第一段（临时或最终）文本到达的时刻；"final text after audio end" 是最后一块音频发出后，
最后一段文本还要多久到达。Azure AI Speech 实时识别从片段开头就报告了语音，但本次运行中它的首批事件晚了数秒（原因未查明），
因此其首字时间不可比；准确率可比。

## 署名

音频与参考转写来自 AMI Meeting Corpus（爱丁堡大学及合作方），许可 CC BY 4.0：https://groups.inf.ed.ac.uk/ami/corpus/ 。
参考分段取自 `edinburghcstr/ami` 数据集修订 `46f28f2503e2ec48f8867a84eef356c70476beab`，各 WAV 的切分边界、字节范围与
SHA-256 记录在 `manifest.json`。片段除切分外未作修改。

## 文件

| 文件 | SHA-256 |
|---|---|
| `clips/EN2002a_0106p13-0179p93.ref.txt` | `80e2e5805460f8c2…` |
| `clips/EN2002a_0106p13-0179p93.wav` | `4acc11d3df009ef5…` |
| `clips/ES2004a_0850p73-0912p60.ref.txt` | `dca0b3303589c55c…` |
| `clips/ES2004a_0850p73-0912p60.wav` | `105a84bf34c90083…` |
| `clips/IS1009a_0685p59-0758p09.ref.txt` | `6e1ee22f7f75ae87…` |
| `clips/IS1009a_0685p59-0758p09.wav` | `f54e50d5dd143870…` |
| `clips/TS3003a_1246p83-1320p78.ref.txt` | `7a1efec02db4a167…` |
| `clips/TS3003a_1246p83-1320p78.wav` | `adc358f65c970eb2…` |
| `manifest.json` | `f7be2885f3701f4b…` |
| `scores.json` | `a321c98485335243…` |
| `scores.md` | `ccfb5225a5cbad6f…` |
| `transcripts/EN2002a_0106p13-0179p93.fast-en.txt` | `2a3d81df699a9c06…` |
| `transcripts/EN2002a_0106p13-0179p93.gpt-batch.txt` | `a77aaf84347f21e2…` |
| `transcripts/EN2002a_0106p13-0179p93.gpt-live.txt` | `2712384aa833b3bb…` |
| `transcripts/EN2002a_0106p13-0179p93.mai-batch.txt` | `6ccb623a498fe478…` |
| `transcripts/EN2002a_0106p13-0179p93.mai-stream.txt` | `f0fd0e3343d55fe6…` |
| `transcripts/EN2002a_0106p13-0179p93.speech-rt.txt` | `7619df6e8d657d84…` |
| `transcripts/ES2004a_0850p73-0912p60.fast-en.txt` | `7d3fdfd597822598…` |
| `transcripts/ES2004a_0850p73-0912p60.gpt-batch.txt` | `1eddad0d74007416…` |
| `transcripts/ES2004a_0850p73-0912p60.gpt-live.txt` | `7ee02a0faba98cbb…` |
| `transcripts/ES2004a_0850p73-0912p60.mai-batch.txt` | `4144f0ce549702f9…` |
| `transcripts/ES2004a_0850p73-0912p60.mai-stream.txt` | `63dc4cc607c4d85e…` |
| `transcripts/ES2004a_0850p73-0912p60.speech-rt.txt` | `d50929f36ee44f3e…` |
| `transcripts/IS1009a_0685p59-0758p09.fast-en.txt` | `c9b1a8d5823b06ef…` |
| `transcripts/IS1009a_0685p59-0758p09.gpt-batch.txt` | `0ae01775d9c89a9a…` |
| `transcripts/IS1009a_0685p59-0758p09.gpt-live.txt` | `957bd327146d807f…` |
| `transcripts/IS1009a_0685p59-0758p09.mai-batch.txt` | `219059bb07e1c2d1…` |
| `transcripts/IS1009a_0685p59-0758p09.mai-stream.txt` | `334fa1c1e00cd020…` |
| `transcripts/IS1009a_0685p59-0758p09.speech-rt.txt` | `800f73aa09e4b0f4…` |
| `transcripts/TS3003a_1246p83-1320p78.fast-en.txt` | `f1757fe3777d869b…` |
| `transcripts/TS3003a_1246p83-1320p78.gpt-batch.txt` | `dfe5f175544322c9…` |
| `transcripts/TS3003a_1246p83-1320p78.gpt-live.txt` | `0653fe7be663caf9…` |
| `transcripts/TS3003a_1246p83-1320p78.mai-batch.txt` | `c68d037a2ed97039…` |
| `transcripts/TS3003a_1246p83-1320p78.mai-stream.txt` | `ba25a5a3eb218490…` |
| `transcripts/TS3003a_1246p83-1320p78.speech-rt.txt` | `ae24817f85ec29f3…` |
