// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 3. 语音合成模块：VITS ONNX

// 简单示例：构建字符到ID映射
var tokens = File.ReadAllLines("tokens.txt"); // 假设模型提供tokens列表
Dictionary<char,int> char2id = tokens.Select((tok, idx) => new { tok, idx })
                                  .Where(x => x.tok.Length == 1)
                                  .ToDictionary(x => x.tok[0], x => x.idx);
int[] textIds = inputText.Select(ch => char2id.ContainsKey(ch) ? char2id[ch] : char2id['<unk>']).ToArray();

using var ttsSession = new InferenceSession("vits.onnx");
var inputTensor = new DenseTensor<int>(textIds, new int[] { 1, textIds.Length });
var inputs = new List<NamedOnnxValue> {
    NamedOnnxValue.CreateFromTensor("text", inputTensor)
};
using var results = ttsSession.Run(inputs);
float[] audioFloats = results.First().AsEnumerable<float>().ToArray();
int sampleRate = 22050; // 该模型输出22050Hz采样率
