# 第6章 AIPC边缘端多模态智能助手构建

[English](README.md) | 中文

> **作者**: 魏新宇 (Xinyu Wei)

## 书中代码清单

| 章节 | 文件 | 说明 |
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

## 环境

C# / WPF（.NET）+ NuGet 包 `NAudio`、`Microsoft.ML.OnnxRuntime`、`Microsoft.ML.OnnxRuntimeGenAI`、`Microsoft.ML.OnnxRuntime.DirectML`；各 `.cs` 文件为书中讲解顺序对应的代码片段，需放入同一 WPF 工程中组合使用。

## 与印刷版的差异说明

- `6.6.3_PhiLlmGeneration.cs`：书中模型目录名 `"Phi-4-mini-int4-cpu "` 末尾多一个空格，已去掉。

## 许可证

MIT
