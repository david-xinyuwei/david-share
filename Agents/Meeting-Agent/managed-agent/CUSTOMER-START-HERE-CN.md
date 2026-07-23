# Managed Meeting Agent 客户快速入口

本交付包包含独立的Managed Agent实现。早期`Agents/Meeting-Agent` Repo保持不变。

## 支持路径

`会议事件 -> 本机Windows UI -> Foundry Managed Agent -> 思维导图和可编辑PPTX -> 未发送的New Outlook草稿`

## 前置条件

- Windows 11和New Outlook
- Python 3.12
- Node.js 22或更高版本
- Azure CLI已在独立`AZURE_CONFIG_DIR`中登录
- 当前身份有权访问已部署的`managed-meeting-agent`

## 启动

在Windows原生PowerShell中运行：

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
az account show

.\scripts\start-ui.ps1 `
  -ManagedAgentEndpoint "https://<account>.services.ai.azure.com/api/projects/<project>/openai/v1/responses" `
  -ManagedAgentName "managed-meeting-agent" `
  -ManagedAgentVersion "1" `
  -AzureConfigDir $env:AZURE_CONFIG_DIR
```

打开`http://127.0.0.1:4173`，选择 **Meeting JSON**，上传`examples/meeting-record-stargate.json`，然后点击 **Generate meeting package**。

## 验收

只有以下条件全部满足才算通过：

1. 页面Header显示 **Foundry Managed Agent** 和 **entra auth**。
2. 六个真实处理阶段全部完成。
3. 页面显示思维导图，并能下载有效的JSON、Mermaid、PNG、PPTX和EML产物。
4. PowerPoint能够打开并编辑，共六页。
5. New Outlook打开可编辑草稿，包含`X-Unsent: 1`、正文内嵌思维图，以及PNG/PPTX附件。
6. 用户必须手动点击 **Send**。

客户主路径不使用AOAI API Key，也不具备自动发送能力。架构、证据、测试和边界见[README-CN.md](README-CN.md)。
