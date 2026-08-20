# Voice Live Agent

基于 **Azure AI Foundry Voice Live API** 的中文桌面语音代理。跑在 Windows 本机，用语音完成实时问答、查数据、看摄像头识物、控制系统设置、整理简报、发邮件、换桌面壁纸——**所有工具都在用户自己的电脑上执行**。

同一套代码内置三种语音接入方式，可在界面上现场切换，用于向客户演示 Voice Live 的架构取舍。

---

## 一、三种运行模式

微软官方把 Voice Live 的部署方式分为三种 pattern。本项目把它们做成了下拉框里可现场切换的选项，**外加一个非 Voice Live 的对照组**。

| 界面选项 | 服务 | 大脑 | 语音链路 |
|---|---|---|---|
| `voicelive` | Azure Voice Live | 模型直连 | 端到端 / 混合 / 级联（由配置决定） |
| `voicelive-agent` | Azure Voice Live | Foundry Agent 托管 | 级联（STT → Agent → TTS） |
| `realtime` | Azure OpenAI Realtime | 模型部署直连 | 端到端（**非 Voice Live**） |

### 1.1 pattern 与配置的对应关系（实测）

Voice Live 落在哪种 pattern，由 **模型** 和 **音色** 两个配置决定，**不需要改代码**：

| Pattern | `AZURE_VOICELIVE_MODEL` | `AZURE_VOICELIVE_VOICE` | 实测 |
|---|---|---|---|
| **(a) Integrated S2S**<br>一个模型包办 STT·LLM·TTS，延迟最低 | `gpt-realtime` | `alloy`（模型原生音色） | ✅ PASS |
| **(b) Hybrid**<br>Realtime 做 STT+LLM，Azure 做 TTS，可用品牌音色 | `gpt-realtime` | `zh-CN-XiaoxiaoMultilingualNeural` | ✅ PASS |
| **(c) Cascaded**<br>Azure STT → 文本模型 → Azure TTS，可换任意强模型 | `gpt-4.1` | `zh-CN-XiaoxiaoMultilingualNeural` | ✅ PASS |

三档均实测通过（`status=COMPLETED` 且成功触发 `function_call`）。

> **中文场景注意**：`alloy` 等模型原生音色的中文表现不佳，商用中文场景建议走 (b) 或 (c) 的 Azure 神经音色。

代码里的判断只有一行——音色名带 `-` 视为 Azure 音色，否则直接交给模型：

```python
voice=AzureStandardVoice(name=voice) if "-" in voice else voice
```

### 1.2 Foundry Agent 模式解决什么问题

`voicelive-agent` **不是第四种 pattern**，它落在 (c) Cascaded 那一行。它改变的不是语音链路，而是**人设与工具定义存放的位置**：

```python
# 模型直连：instructions 和工具由客户端每次 session.update 下发
connect(endpoint=..., credential=..., model="gpt-realtime")

# Agent 托管：instructions 和工具写在云端 Agent 定义里
connect(endpoint=..., credential=..., agent_name="...", project_name="...")
```

**价值只在多端场景**：手机 App、车机、PC 连同一个 Agent，改人设不用逐端发版。**单客户端场景下它是净成本**，实测限制如下（均为服务端返回原文）：

| 限制 | 服务端返回 |
|---|---|
| 不能用 API Key | `Key authentication is not supported in Foundry Agent mode.` |
| 不能运行时下发工具 | `Configuring tools at runtime in Foundry Agent mode is not supported.`<br>`Please configure tools in the agent definition.` |
| 不能挂多模态实时模型 | 配 `gpt-realtime` 时返回 `status=FAILED` 且 output 为空 |
| 转写模型受限 | `Only 'azure-speech', 'azure-mrs', 'mai-transcribe-1', 'mai-transcribe-1.5', and 'mai-transcribe' are supported in cascaded pipelines` |

最后一条是服务端自己把 Agent 模式称为 **cascaded pipeline**，也是"Agent 模式必然级联"最直接的证据。

> **工具仍在本机执行。** Agent 只存放工具的 *定义*；模型决定调用哪个工具后，参数回传到客户端，由本机代码真正执行。云端 Agent 一行设备操作代码都没有。

### 1.3 与 Azure OpenAI Realtime 的差异

`realtime` 模式走的是 `/openai/v1/realtime`，**不是 Voice Live**，因此拿不到 Voice Live 的语音增强层：

| | Voice Live | Azure OpenAI Realtime |
|---|---|---|
| 语义 VAD（中文） | ✅ `azure_semantic_vad_multilingual`，可去填充词 | ❌ 仅 `semantic_vad` |
| 降噪 | ✅ `azure_deep_noise_suppression` | ❌ |
| 服务端回声消除 | ✅ 含 Live-Reference AEC | ❌ 需自己在客户端实现 |
| 音色 | 600+ Azure 神经音色 / HD / 自定义 | 仅模型原生音色 |
| Avatar | ✅ | ❌ |
| 模型部署 | 服务端托管，无需自行部署 | 需自行部署 |

保留这个模式是为了让客户直观看到"不用 Voice Live 会少掉什么"。

---

## 二、能力清单

19 个工具全部注册在本机，由模型按语音意图触发。

### 桌面与设备控制

| 语音指令 | 后台真实发生 | 可查证 |
|---|---|---|
| 「现在音量多少」 | Core Audio `IAudioEndpointVolume.GetMasterVolumeLevelScalar` | ✅ 与系统音量条一致 |
| 「音量调到 30」「声音大一点」 | `SetMasterVolumeLevelScalar` | ✅ 系统音量条实时变化 |
| 「静音」「取消静音」 | `SetMute` | ✅ 托盘图标同步变化 |
| 「打开计算器 / 记事本 / 资源管理器 / 任务管理器 / 画图」 | `subprocess.Popen` 启动进程 | ✅ 窗口弹出 |
| 「打开设置」 | `os.startfile("ms-settings:")` | ✅ 设置应用打开 |
| 「显示桌面」 | Win32 `keybd_event` 模拟 Win+D | ✅ 所有窗口最小化 |
| 「把时区改成西雅图」 | PowerShell `Set-TimeZone` | ✅ 系统时钟立即变化 |
| 「换成桌面背景」 | Win32 `SystemParametersInfoW` | ✅ 桌面立即变化 |

### 感知与信息

| 语音指令 | 后台真实发生 | 可查证 |
|---|---|---|
| 「打开摄像头」 | OpenCV 常开实时流，界面同步预览 | ✅ 画面实时刷新 |
| 「这是什么」（举起物品） | 抓当前帧 → 多模态模型识别 | ✅ 返回物品描述 |
| 「哪里有卖」 | 识别结果 → 网页搜索 | ✅ 返回购买链接 |
| 「北京天气怎么样」 | `GET api.open-meteo.com` 实时气象 | ✅ 带观测时间的真实温湿度 |
| 「微软股价多少」 | `GET query1.finance.yahoo.com` 实时报价 | ✅ 与 Yahoo Finance 一致 |
| 「有什么新闻」 | 拉取真实 RSS（Google News / BBC） | ✅ 可点击原文链接 |
| 「搜一下 XXX」 | WebIQ `client.web.search` | 需有效 key |
| 「纽约现在几点」 | 本机 IANA tzdata 计算 | ✅ 含 UTC offset |

### 内容生成与投递

| 语音指令 | 后台真实发生 | 可查证 |
|---|---|---|
| 「整理一份新闻简报」 | 真实 RSS + Azure OpenAI 整理 | ✅ 每条标注来源媒体 |
| 「发到我邮箱」 | 真实 SMTP 投递（收件人白名单） | ✅ 收件箱可收到 |
| 「网上找一张壁纸」 | 图片搜索 + https 下载校验 | 需有效 key |
| 「生成一张壁纸」 | Azure OpenAI 图像生成，落盘本地 | 需图像模型部署 |

**没有任何一个工具返回模拟数据。** 外部依赖不可用时工具显式返回失败原因，模型如实告知用户，不做静默兜底。

### 图像识别不经过 Voice Live

摄像头识物是 **function call 内部单独调用 Chat Completions API**，与语音链路完全解耦：

```
用户：「这是什么」
  → Voice Live 识别意图，触发 function call
  → 本机抓取当前帧 → 单独调用多模态模型 → 返回文字描述
  → Voice Live 将描述合成语音播报
```

Voice Live 全程只处理语音，**不接触图像**。因此不需要为了图像能力切换模型或引入 Agent。

---

## 三、架构

```
┌──────────────────────────────────────────────────────────┐
│  Windows 本机                                             │
│                                                           │
│  麦克风 ──PCM16/24kHz──┐                                  │
│  扬声器 ◀──audio delta─┤  语音后端（三选一）                │
│  摄像头 ──实时流──┐     └──── function call ────┐          │
│                  │                              │          │
│                  ▼                              ▼          │
│           帧缓存（常开）            本地工具注册表（19 个）   │
│                  │                              │          │
│                  └──► 多模态模型识别 ◀───────────┘          │
│                                                            │
│  音量控制 / 应用启动 / 时区 / 壁纸  ← 均由本机代码执行        │
└──────────────────────────────────────────────────────────┘
                            │
                            ▼
              Azure Voice Live / Azure OpenAI Realtime
```

- 三个后端共享同一套音频管线与工具编排代码（[src/agent_core.py](src/agent_core.py)）
- 同步工具经 `asyncio.to_thread` 执行，不阻塞音频事件循环
- 一轮内多个 function call 用 `asyncio.gather` 并发执行
- `VoiceLiveFoundryAgent` 继承 `VoiceLiveAgent`，只覆写连接参数

详细调用链见 [docs/architecture.png](docs/architecture.png) 与 [docs/sequence.png](docs/sequence.png)。

---

## 四、工程要点

### 4.1 回声与打断

远程桌面、外放扬声器场景下，麦克风会拾取到助手自己的声音，导致"自己打断自己"。本项目采用两层防护：

**服务端 Live-Reference AEC**（Voice Live 官方方案，API 版本 `2026-07-15+`）

默认情况下服务端用它自己发出的音频作为回声参考，并**假设客户端收到即播放**。远程桌面下播放延迟常超过 2 秒，该假设失效。Live-Reference AEC 改由客户端上报**实际播放的音频**：

```python
AudioEchoCancellation(type="server_echo_cancellation",
                      reference_source="client", channels=2)
```

音频以双声道交错上行：channel 0 为麦克风，channel 1 为播放参考。启用后客户端不再静音上行，抢话完全交由服务端判定。

可通过 `AUDIO_LIVE_REFERENCE_AEC=false` 回退到客户端门限方案。

**客户端 barge-in 状态机**（回退方案）

单帧电平判断会被音频尖峰误触发。实现采用连续帧确认 + 迟滞释放 + 预缓冲补发：

| 参数 | 值 | 作用 |
|---|---|---|
| 连续确认帧数 | 3 | 避免单帧尖峰误判为抢话 |
| 释放帧数 | 6 | 说话中途停顿不会被判定为结束 |
| 迟滞系数 | 0.65 | 防止在门限附近反复进出 |
| 预缓冲帧数 | 4 | 确认期被静音的字头补发，避免吞字 |

### 4.2 摄像头

- 常开实时流，后台线程持续抓帧；识别工具直接取当前帧，用户举起物品即可提问，无需重新打开设备
- 后端按实测可用性排序（DirectShow 优先，Media Foundation 次之），并记住上次成功的组合
- 打开失败自动重试一次——设备刚被释放时会短暂不可用

### 4.3 音量控制

使用 Core Audio 的 `IAudioEndpointVolume` 而非模拟音量键：能读到精确百分比，不受焦点窗口影响。工具在线程池执行，**每次调用自行初始化 COM 套间**（`CoInitialize` / `CoUninitialize`），并兼容新旧两版 pycaw 的接口差异。

相对调节（"声音大一点"）由模型先查询当前值再换算目标百分比，提示词中已约定该流程。

### 4.4 转写模型

Agent 模式使用 `mai-transcribe`。Agent 走文本推理，**转写质量直接决定意图判断**，中文识别错误会导致完全错误的工具调用。

---

## 五、环境要求

- Windows 10/11（音量、壁纸、时区、应用启动依赖 Win32 / PowerShell / Core Audio）
- Python 3.10+
- 麦克风与扬声器（演示建议佩戴耳机，物理断开回声通路）
- Azure AI Foundry 资源（Voice Live 无需单独部署模型）
- 账号需要 `Cognitive Services User` 与 `Foundry User` 角色

---

## 六、安装

```powershell
git clone <this-repo>
cd voice-live-agent
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

编辑 `.env` 填入 Foundry endpoint。推荐 Entra 认证（`AZURE_VOICELIVE_API_KEY` 留空），并为本项目单独隔离 Azure CLI 配置目录：

```powershell
$env:AZURE_CONFIG_DIR = "$HOME\.azure-voice-live-agent"
az login
az account set --subscription <your-subscription-id>
az account show -o table
```

> **Foundry Agent 模式必须使用 Entra**，服务端拒绝 API Key。若只用 `voicelive` / `realtime` 模式，可使用 Key。

### 使用 Foundry Agent 模式（可选）

需先在 Foundry 项目下创建 Agent，把 instructions 和工具定义写入 Agent，然后配置：

```ini
AZURE_VOICELIVE_AGENT_NAME=<agent-name>
AZURE_VOICELIVE_PROJECT_NAME=<project-name>
AZURE_VOICELIVE_AGENT_VERSION=<version>
```

创建 Agent 的 REST 端点（`api-version=2025-11-15-preview`）：

```
POST {project_endpoint}/agents                     # 新建
POST {project_endpoint}/agents/{name}/versions     # 已存在时追加版本
```

`definition.model` **必须是文本模型**（如 `gpt-4.1`、`gpt-5` 系列）。配置多模态实时模型会导致响应为空且不报错。

**本机新增工具后必须同步创建 Agent 新版本**，否则云端仍是旧的工具清单。

---

## 七、验证

四层验证，逐层加深，任何一层失败都不要往下走：

```powershell
# 1. 不联网：会话配置与工具 schema 能否正确序列化
.venv\Scripts\python.exe -m scripts.preflight --mode voicelive --dry-run
.venv\Scripts\python.exe -m scripts.preflight --mode realtime  --dry-run

# 2. 真实调用外部数据源（天气/股票/新闻/时区/搜索），不需要 Azure 凭据
.venv\Scripts\python.exe -m scripts.smoke_tools

# 3. 真实连接语音后端：验证认证、模型、音色、工具 schema 被服务端接受，不开麦
.venv\Scripts\python.exe -m scripts.preflight --mode voicelive
.venv\Scripts\python.exe -m scripts.preflight --mode realtime

# 4. 加验简报、生图与换壁纸（会真的改桌面）
.venv\Scripts\python.exe -m scripts.smoke_tools --all
```

### 已验证项

| 环节 | 状态 | 证据 |
|---|---|---|
| 工具注册与 schema 序列化 | ✅ | 三个后端均输出 19 个工具 |
| Voice Live 端到端语音 | ✅ | 真实中英文对话，STT/TTS 双向通 |
| Voice Live 三种 pattern | ✅ | (a)(b)(c) 均 `COMPLETED` 且触发 `function_call` |
| Foundry Agent 模式 | ✅ | `COMPLETED`，22 个音频块，触发 `function_call` |
| Agent 工具同步 | ✅ | v3 含 19 工具，「把音量调到 30」触发 `set_system_volume` |
| Azure OpenAI Realtime | ✅ | `wss://…/openai/v1/realtime` GA 格式 |
| 系统音量控制 | ✅ | 100%→30%→55%→静音→恢复，10 项断言全通过 |
| 应用启动 / 显示桌面 | ✅ | 进程实际启动，非法应用名正确报错 |
| 天气 / 股票 / 新闻 / 时区 | ✅ | 返回真实实时数据 |
| 邮件投递 | ✅ | HTTP 202 + 收件箱实际收到 |
| 摄像头实时流 | ✅ | 连续帧亮度变化，界面同步刷新 |
| Win32 换壁纸 | ✅ | 注册表 `WallPaper` 与 `WallpaperStyle` 已写入并生效 |
| 系统时区修改 | ✅ | 系统时钟实际变化，无需提权 |
| barge-in 状态机 | ✅ | 8 项状态机单元测试全通过 |
| Live-Reference AEC | ✅ | 交错格式 7 项单测通过；服务端 `session.updated` 无错误 |
| SSRF / 路径穿越 / 收件人白名单 | ✅ | http、localhost、127.0.0.1、169.254.169.254 均被拒 |

---

## 八、运行

```powershell
.venv\Scripts\python.exe app.py
```

界面右上角下拉框切换三种模式。日志写入 `logs\<时间戳>_voiceagent.log`。

打包为独立 exe：

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean LenovoVoiceAgent.spec
```

产物在 `dist\`，需与 `.env` 放在同一目录。

---

## 九、演示话术

1. 「把音量调到 30」→「现在音量多少」→「静音」→「取消静音」
2. 「打开计算器」→「显示桌面」
3. 「北京今天天气怎么样，需要带伞吗」
4. 「把系统时区改成西雅图」→ 再问「现在几点」
5. 「打开摄像头」→ 举起物品 →「这是什么」→「哪里有卖」
6. 「帮我整理一份人工智能的新闻简报」→「发到我邮箱」
7. 「网上找一张雪山日出的壁纸，换成我的桌面」

第 5、6、7 条会连续触发多个工具调用，是展示编排能力的重点场景。
演示架构取舍时，可在同一句话下切换三种模式，直观对比延迟与音色差异。

---

## 十、配置说明

| 变量 | 用途 | 缺失时的行为 |
|---|---|---|
| `AZURE_VOICELIVE_ENDPOINT` | Voice Live 接入点 | `voicelive` 模式启动即报错 |
| `AZURE_VOICELIVE_MODEL` | 默认 `gpt-realtime`；改文本模型即切 Cascaded | 使用默认值 |
| `AZURE_VOICELIVE_VOICE` | 默认中文神经音色；改 `alloy` 即切 Integrated S2S | 使用默认值 |
| `AZURE_VOICELIVE_API_KEY` | 留空则用 Entra 令牌 | 使用 Entra |
| `AZURE_VOICELIVE_AGENT_NAME` | Foundry Agent 名 | `voicelive-agent` 模式启动即报错 |
| `AZURE_VOICELIVE_PROJECT_NAME` | Foundry 项目名 | 同上 |
| `AZURE_VOICELIVE_AGENT_VERSION` | Agent 版本号 | 使用服务端默认 |
| `AUDIO_LIVE_REFERENCE_AEC` | 默认 `true`；`false` 回退客户端门限 | 启用 |
| `AUDIO_HALF_DUPLEX` | 客户端回声保护；启用 AEC 时自动关闭 | 启用 |
| `AZURE_OPENAI_ENDPOINT` | Realtime 后端 + 简报 + 生图 + 图像识别 | 相关功能报错 |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | 简报整理与图像识别 | 相关工具返回失败 |
| `AZURE_OPENAI_IMAGE_DEPLOYMENT` | 壁纸生图 | 生图工具返回失败 |
| `SMTP_*` | 邮件投递 | 发邮件工具返回失败 |
| `MAIL_ALLOWED_RECIPIENTS` | 收件人白名单 | **为空则拒绝一切发送** |
| `NEWS_FEEDS` | RSS 源列表 | 用内置的 Google News + BBC |
| `WALLPAPER_DIR` | 壁纸落盘目录 | 默认 `artifacts\wallpapers` |

---

## 十一、安全边界

- 邮件收件人必须命中 `MAIL_ALLOWED_RECIPIENTS` 白名单，防止语音指令被诱导发往任意地址
- 收件人与主题拒绝含换行符，阻断邮件头注入
- 换壁纸只接受 `WALLPAPER_DIR` 目录内的文件，路径解析后校验，阻断路径穿越
- 图片下载强制 https，拒绝内网地址与云元数据端点（`localhost`、`127.0.0.1`、`169.254.169.254`）
- 应用启动限定在固定白名单内，不接受任意可执行文件路径
- 音量参数在服务端夹紧到 0–100，越界值不会抛错也不会溢出
- 所有凭据从 `.env` 读取，`.env` 与令牌缓存均不入库

---

## 十二、已知限制

- 摄像头识物依赖多模态模型部署；实时语音模型不适合稳定的画面理解，视觉分析须单独指向支持图像输入的部署
- Foundry Agent 模式不支持 API Key、不支持运行时下发工具、不能挂多模态实时模型
- `alloy` 等模型原生音色中文表现不佳，中文商用场景建议使用 Azure 神经音色
- 远程桌面下摄像头依赖客户端勾选「视频捕获设备」重定向
- 音量控制依赖 `pycaw` + `comtypes`，仅 Windows 可用
- 图像生成需要 Foundry 资源中存在图像模型部署

---

## 许可

MIT
