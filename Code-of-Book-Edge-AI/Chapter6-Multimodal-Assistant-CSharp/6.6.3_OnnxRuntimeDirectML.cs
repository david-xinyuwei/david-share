// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 5. ONNX Runtime 统一推理框架

var options = new SessionOptions();
// 使用GPU加速(DirectML)
options.AppendExecutionProvider_DML();
var session = new InferenceSession("model.onnx", options);
