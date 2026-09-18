// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 3. 语音合成模块：无文件播放

var waveOut = new WaveOutEvent();
var waveFormat = WaveFormat.CreateIeeeFloatWaveFormat(sampleRate, 1);
var waveProvider = new BufferedWaveProvider(waveFormat);
byte[] audioBytes = new byte[audioFloats.Length * sizeof(float)];
Buffer.BlockCopy(audioFloats, 0, audioBytes, 0, audioBytes.Length);
waveProvider.AddSamples(audioBytes, 0, audioBytes.Length);
waveOut.Init(waveProvider);
waveOut.Play();
