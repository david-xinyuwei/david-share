# Managed Meeting Agent 客户快速入口

本交付包提供Meeting Agent产品的Foundry Managed实现路径。Classic实现继续保留在同一产品主页中。

## 支持路径

`会议事件 -> 本机Windows UI -> Foundry Managed Agent -> 思维导图和可编辑PPTX -> 未发送的New Outlook草稿`

## 前置条件

- Windows 11和New Outlook
- Python 3.12
- Node.js 22或更高版本
- Azure CLI已在独立`AZURE_CONFIG_DIR`中登录
- 当前身份有权访问已部署的`true-meeting-managed-agent` v6

## 启动

在Windows原生PowerShell中运行：

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
az account show

.\scripts\start-ui.ps1 `
  -ManagedAgentEndpoint "https://<account>.services.ai.azure.com/api/projects/<project>/openai/v1/responses" `
  -ManagedAgentName "true-meeting-managed-agent" `
  -ManagedAgentVersion "6" `
  -ManagedAgentModel "Kimi-K2.7-Code" `
  -RequireDeckPlan $true `
  -AzureConfigDir $env:AZURE_CONFIG_DIR
```

应使用部署/Reconcile输出的Active Name与Version；`6`是已验证Kimi版本，不代表每次重新部署都继续使用相同编号。不要从历史GPT-5.4证据复制Agent Name或Version。
当前Reconcile后的版本必须保持`-RequireDeckPlan $true`；即使省略该参数，启动器也默认启用严格模式。只有明确重放历史`managed-meeting-agent` GPT-5.4 v6兼容路径时才可设为false。

打开`http://127.0.0.1:4173`，选择 **Meeting JSON**，上传`examples/meeting-record-stargate.json`，然后点击 **Generate meeting package**。

## 验收

只有以下条件全部满足才算通过：

1. 页面Header显示 **Foundry Managed Agent**、`Kimi-K2.7-Code`和 **entra auth**。
2. 六个真实处理阶段全部完成。
3. 页面显示思维导图，并能下载有效的JSON、Mermaid、PNG、PPTX和EML产物。
4. PowerPoint能够打开并编辑，共六页。
5. New Outlook打开可编辑草稿，包含`X-Unsent: 1`、正文内嵌思维图，以及PNG/PPTX附件。
6. 用户必须手动点击 **Send**。

客户主路径不使用AOAI API Key，也不具备自动发送能力。架构、证据、测试和边界见[Managed实现说明](docs/MANAGED-IMPLEMENTATION-CN.md)，统一入口见[产品首页](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Meeting-Agent)。
