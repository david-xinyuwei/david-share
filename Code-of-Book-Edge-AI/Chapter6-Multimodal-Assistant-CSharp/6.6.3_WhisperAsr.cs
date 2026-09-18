// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 1. 语音识别模块：Whisper ONNX 推理

// 加载Whisper-small onnx模型
using var session = new InferenceSession("whisper-small.onnx", sessionOptions);
// 如果模型含自定义算子（如音频解码），需注册扩展库
sessionOptions = new SessionOptions();
sessionOptions.RegisterCustomOpsLibrary("onnxruntime_extensions.dll");
// 构造输入张量（假设模型要求audio_stream为uint8数组）
var audioData = audioStream.ToArray(); // 从MemoryStream获取音频字节
var tensor = new DenseTensor<byte>(audioData, new int[] { 1, audioData.Length });
var inputs = new List<NamedOnnxValue> {
    NamedOnnxValue.CreateFromTensor("audio_stream", tensor),
    // 其他推理参数，如长度限制等，按模型需要提供
};
using var results = session.Run(inputs);
// 假设模型输出直接为文本
string transcription = results.First().AsEnumerable<string>().First();
