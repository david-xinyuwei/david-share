// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 2. 语言模型推理模块：GenAI 逐 token 生成

using Microsoft.ML.OnnxRuntimeGenAI;
var model = new Model("Phi-4-mini-int4-cpu");     // 加载Phi-4-mini-int4-cpu模型
var tokenizer = new Tokenizer(model);       // 内置分词器（根据模型字典）
string systemPrompt = "你是一个智能助手，请用简洁风格回答用户问题。";
string userQuestion = recognizedText;        // 上一步ASR识别的文本
string prompt = $"<|system|>{systemPrompt}<|end|><|user|>{userQuestion}<|end|><|assistant|>";
long[] inputIds = tokenizer.Encode(prompt);  // 对完整提示进行分词编码
// 设置生成参数
var gParams = new GeneratorParams(model);
gParams.SetInputSequences(inputIds);
gParams.SetSearchOption("max_length",1024);  // 允许生成的最大词元长度
// 创建生成器并逐步生成输出
var generator = new Generator(model, gParams);
StringBuilder answerBuilder = new StringBuilder();
while (!generator.IsDone())
{
    generator.ComputeLogits();
    generator.GenerateNextToken();
    var outputTokens = generator.GetSequence(0);
    // 解码新增的最后一个词元并附加到结果
    var newToken = outputTokens[^1];
    answerBuilder.Append(tokenizer.Decode(new long[] { newToken }));
}
string assistantAnswer = answerBuilder.ToString();
