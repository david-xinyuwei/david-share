# 客户从这里开始 - 面向 AIPC 的 Voice Live API 语音代理

[English](CUSTOMER-START-HERE.md) | [中文](CUSTOMER-START-HERE-CN.md)

这份文档只保留 Windows 最短验证路径。架构、证据、可选提供方与安全边界见 [README-CN.md](README-CN.md)。

## 需要准备什么

- Windows 10/11、Python 3.11-3.13、麦克风和扬声器
- 位于 Voice Live 支持区域的 Microsoft Foundry 资源
- 资源 endpoint，以及 API Key；或拥有 `Cognitive Services User` 和 `Foundry User` 的 Entra 身份

## 安装

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
Set-Location .\david-share\Agents\Voice-Live-API-AIPC
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

## 配置

在 `.env` 中填写自己的资源信息。本机 Demo 最短配置如下：

```ini
AZURE_VOICELIVE_ENDPOINT=https://<your-resource>.services.ai.azure.com/
AZURE_VOICELIVE_MODEL=gpt-realtime
AZURE_VOICELIVE_VOICE=zh-CN-XiaoxiaoMultilingualNeural
AZURE_VOICELIVE_API_KEY=<your-api-key>
```

Git 会忽略 `.env`。不要把 Key 粘贴到命令、Issue、日志或截图中。

## 不打开麦克风的验证

```powershell
.\.venv\Scripts\python.exe -m scripts.preflight --mode voicelive --dry-run
.\.venv\Scripts\python.exe -m scripts.preflight --mode voicelive
```

只有离线 gate 能序列化 24 个工具，并且真实连接收到 `session.updated`、服务端接受全部 24 个工具，才算配置通过。

## 运行

```powershell
.\run.cmd
```

点击**开始对话**。先用时间或天气这类无害请求验证，再启用摄像头、Windows 电源、壁纸或邮件副作用。

要选择英文，请说：**“Please speak English for this demo and keep using English until I explicitly request another language.”** 该选择会持续生效，直到你明确要求另一种语言；仅引用其他语言不会触发切换。尚未指定语言时默认中文。

打开/抓拍摄像头、时区、电源、壁纸、生图和邮件都是代码层受保护操作。第一次调用不会执行；请先核对系统概括的操作，再在下一轮明确确认。参数变化、token 重放、过期或取消都会被拒绝。

## 可选邮件发送

邮件不是 fixture：完成独立确认后，默认会通过 Microsoft Graph 实际发送。配置 Public Client 应用、delegated `Mail.Send`、`GRAPH_CLIENT_ID` 与 `MAIL_ALLOWED_RECIPIENTS` 后运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.graph_login
```

启用前请阅读 [README-CN.md](README-CN.md#microsoft-graph-邮件) 与 [SECURITY.md](SECURITY.md)。
