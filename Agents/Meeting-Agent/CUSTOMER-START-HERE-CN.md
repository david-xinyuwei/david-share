# Meeting Agent 客户快速入口

本交付包包含本机Windows Meeting Agent的源码、锁定依赖、合成会议样例、可编辑PowerPoint模板、测试和客户Runbook。

## 支持的端到端路径

使用Windows原生PowerShell。完整路径是：

`Meeting JSON -> 本机浏览器UI -> Azure OpenAI GPT-5.4 -> 六卡片思维图/PPTX -> 未发送的New Outlook草稿`

### 前置条件

- Windows 11和New Outlook
- Python 3.12
- Node.js 22或更高版本
- 已有Azure OpenAI endpoint、deployment名称和API Key
- Azure OpenAI资源必须已启用Local Auth

### 启动

在Azure Portal中打开目标Azure OpenAI或Azure AI Services资源，进入 **Resource Management > Keys and Endpoint**，复制Endpoint和 **KEY 1** 或 **KEY 2**。在 **Model deployments** 中确认deployment名称。

```powershell
Set-Location .\Meeting-Agent
.\scripts\start-ui-key.ps1 `
	-Endpoint "https://<your-resource>.openai.azure.com/" `
	-Deployment "gpt-5.4"
```

命令启动后，PowerShell会显示`Azure OpenAI API key:`。在提示后粘贴 **KEY 1** 或 **KEY 2**并按Enter；隐藏输入不会显示任何字符。不要把Key追加到命令中，启动器特意不提供`-ApiKey`参数。Key不会写入文件，也不会发送到浏览器。

打开`http://127.0.0.1:4173`，选择 **Meeting JSON**，上传`examples/meeting-record-stargate.json`，然后点击 **Generate meeting package**。

只有页面显示Azure OpenAI、`gpt-5.4 · reasoning medium · key auth`、六个完成阶段、六卡片思维图、可编辑六页PowerPoint，并生成正文内嵌同一卡片图的未发送New Outlook草稿时才算验收通过。邮件始终需要人工点击 **Send**。

如果启动器返回`403 AuthenticationTypeDisabled`，请让Azure资源管理员设置`disableLocalAuth=false`。Key模式使用现有资源，不负责部署Azure基础设施。

完整Runbook、架构、验证证据、故障排查和Linux/macOS仅Backend路径见[README-CN.md](README-CN.md)。