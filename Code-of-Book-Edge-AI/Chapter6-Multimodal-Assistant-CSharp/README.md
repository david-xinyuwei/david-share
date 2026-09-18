# Chapter 6: Building a Multimodal AI Assistant on the AI PC

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇)

## Code listings from the book

| Section | File | Description |
|---|---|---|
| 6.6.3 | [`6.6.3_AudioCapture.cs`](6.6.3_AudioCapture.cs) | NAudio 采集 16kHz/16bit 单声道音频 |
| 6.6.3 | [`6.6.3_WhisperAsr.cs`](6.6.3_WhisperAsr.cs) | ONNX Runtime 运行 Whisper-small 得到转录文本 |
| 6.6.3 | [`6.6.3_build_phi4_mini_onnx.sh`](6.6.3_build_phi4_mini_onnx.sh) | 用 onnxruntime-genai 把 Phi-4-mini 导出为 CPU INT4 ONNX |
| 6.6.3 | [`6.6.3_PhiLlmGeneration.cs`](6.6.3_PhiLlmGeneration.cs) | Microsoft.ML.OnnxRuntimeGenAI 加载 Phi-4-mini 并逐 token 生成回答 |
| 6.6.3 | [`6.6.3_VitsTts.cs`](6.6.3_VitsTts.cs) | 字符→ID 映射与 VITS ONNX 推理得到语音波形 |
| 6.6.3 | [`6.6.3_WavFileWriter.cs`](6.6.3_WavFileWriter.cs) | 把浮点 PCM 写成 16-bit WAV |
| 6.6.3 | [`6.6.3_BufferedPlayback.cs`](6.6.3_BufferedPlayback.cs) | NAudio BufferedWaveProvider 直接播放 |
| 6.6.3 | [`6.6.3_AsyncPipeline.cs`](6.6.3_AsyncPipeline.cs) | ASR → LLM → TTS 的 async/await 串联，不阻塞 UI 线程 |
| 6.6.3 | [`6.6.3_OnnxRuntimeDirectML.cs`](6.6.3_OnnxRuntimeDirectML.cs) | 启用 DirectML 执行提供程序 |

## Environment

C# / WPF (.NET) with the NuGet packages `NAudio`, `Microsoft.ML.OnnxRuntime`, `Microsoft.ML.OnnxRuntimeGenAI` and `Microsoft.ML.OnnxRuntime.DirectML`; the `.cs` files are the snippets in the order the book explains them and are meant to be combined in one WPF project.

## Differences from the printed text

- `6.6.3_PhiLlmGeneration.cs`: the printed model folder name `"Phi-4-mini-int4-cpu "` has a trailing space; removed.

## License

MIT
