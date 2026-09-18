// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 1. 语音识别模块：NAudio 采集麦克风

var waveIn = new WaveInEvent();
waveIn.DeviceNumber = 0; // 默认麦克风
waveIn.WaveFormat = new WaveFormat(16000, 16, 1);
waveIn.BufferMilliseconds = 50; // 缓冲大小，降低延迟
waveIn.DataAvailable += (s, e) =>
{
    // 将缓冲数据写入内存流
    audioStream.Write(e.Buffer, 0, e.BytesRecorded);
};
