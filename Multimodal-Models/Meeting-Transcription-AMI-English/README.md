# English meeting transcription on far-field audio: six Azure speech paths, four AMI clips

2026-10-02 · one run per model · 4 clips, 282 s, 930 reference words after normalisation · corpus: AMI Meeting Corpus, test set, SDM (Array1-01) (CC BY 4.0)

The clips are here so you can listen to exactly what the models heard and read the human reference next to each
machine transcript. This is a listening set with a score sheet, not a benchmark: every model ran once, so treat
gaps under about one WER point as unresolved.

## Clips

Windows of 45–75 s were cut from the
single-distant-microphone recording (Array1-01) of four test-set meetings, choosing the window with the most reference
words whose speaker overlap stayed under 15%. Byte ranges, the
AMI mirror URL and the reference segments for each clip are in [`manifest.json`](manifest.json).

| Clip | Meeting | Window | Length | Speakers | Ref. words (raw) | Overlap | Human transcript |
|---|---|---|---:|---:|---:|---:|---|
| [`EN2002a_0106p13-0179p93`](clips/EN2002a_0106p13-0179p93.wav) | EN2002a | 106.13–179.93 s | 73.8 s | 4 | 261 | 7% | [reference](clips/EN2002a_0106p13-0179p93.ref.txt) |
| [`ES2004a_0850p73-0912p60`](clips/ES2004a_0850p73-0912p60.wav) | ES2004a | 850.73–912.60 s | 61.9 s | 4 | 223 | 10% | [reference](clips/ES2004a_0850p73-0912p60.ref.txt) |
| [`IS1009a_0685p59-0758p09`](clips/IS1009a_0685p59-0758p09.wav) | IS1009a | 685.59–758.09 s | 72.5 s | 4 | 215 | 8% | [reference](clips/IS1009a_0685p59-0758p09.ref.txt) |
| [`TS3003a_1246p83-1320p78`](clips/TS3003a_1246p83-1320p78.wav) | TS3003a | 1246.83–1320.78 s | 74.0 s | 4 | 225 | 10% | [reference](clips/TS3003a_1246p83-1320p78.ref.txt) |

## Models

| Public name | Arm in the files | How it was called |
|---|---|---|
| MAI-Transcribe-2-Streaming | `mai-stream` | Azure AI Foundry realtime transcription session, deployment `mai-transcribe-2-streaming`, 16 kHz PCM sent at real-time pace |
| gpt-live-transcribe | `gpt-live` | Azure OpenAI realtime transcription session, 24 kHz PCM (clips resampled from 16 kHz), sent at real-time pace |
| Azure AI Speech real-time | `speech-rt` | Speech SDK 1.52.0 continuous recognition, `standard` model, en-US, 16 kHz, sent at real-time pace |
| MAI-Transcribe-2 | `mai-batch` | Azure AI Speech Fast Transcription with `enhancedMode.model = MAI-Transcribe-2`, whole file in one request |
| gpt-transcribe | `gpt-batch` | Azure OpenAI `/audio/transcriptions`, deployment `gpt-transcribe`, whole file in one request |
| Azure AI Speech Fast Transcription | `fast-en` | Fast Transcription REST API, en-US, whole file in one request |

Streaming paths received the audio at real-time pace in 100 ms chunks; whole-file paths received the WAV in one
request. All six ran from the same client on 2026-10-02.

## Scores

Word error rate = (substitutions + deletions + insertions) / reference words after the Whisper English text
normaliser (`whisper_normalizer.english.EnglishTextNormalizer`), the same normaliser the Open ASR Leaderboard uses. Timing is the median over
the four clips. Generated from [`scores.json`](scores.json); the per-clip and per-model hypotheses are in
[`transcripts/`](transcripts/).

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

Reading the timing columns: "first text" is when the first partial or final text arrived after the audio started
streaming; "final text after audio end" is how long the last text took to arrive after the last audio chunk was sent.
Azure AI Speech real-time reported speech from the start of the clip but its first events arrived several seconds
late in this run (cause not identified), so its first-text time is not comparable; its accuracy is.

## Attribution

Audio and reference transcripts are from the AMI Meeting Corpus (University of Edinburgh and partners), licensed
CC BY 4.0: https://groups.inf.ed.ac.uk/ami/corpus/ . Reference segments were taken from the `edinburghcstr/ami`
dataset revision `46f28f2503e2ec48f8867a84eef356c70476beab` and the clip boundaries, byte ranges and SHA-256 of
each WAV are recorded in `manifest.json`. The clips are redistributed unchanged apart from cutting.

## Files

| File | SHA-256 |
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
