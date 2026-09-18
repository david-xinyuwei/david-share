// 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 4. WPF 界面集成与异步处理

private async void OnRecordingStopped(object sender, StoppedEventArgs e)
{
    statusLabel.Content = "正在识别...";
    string userText = await Task.Run(() => RunWhisperASR(audioStream));
    userInputTextBox.Text = userText;
    statusLabel.Content = "正在思考...";
    string answerText = await Task.Run(() => RunLLM(userText));
    assistantTextBox.Text = answerText;
    statusLabel.Content = "正在合成语音...";
    float[] speech = await Task.Run(() => RunTTS(answerText));
    PlayAudio(speech);
    statusLabel.Content = "完成";
}
