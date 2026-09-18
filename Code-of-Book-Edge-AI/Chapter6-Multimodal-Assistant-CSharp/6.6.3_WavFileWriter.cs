// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 3. 语音合成模块：写 WAV 文件

using(var waveFile = new WaveFileWriter("assistant_output.wav", new WaveFormat(sampleRate, 16, 1)))
{
    // 将float转换为16-bit PCM写入
    foreach(float sample in audioFloats)
    {
        short intSample = (short)Math.Max(Math.Min(sample * 32767, 32767), -32768);
        waveFile.WriteByte((byte)(intSample & 0xFF));
        waveFile.WriteByte((byte)((intSample >> 8) & 0xFF));
    }
}
