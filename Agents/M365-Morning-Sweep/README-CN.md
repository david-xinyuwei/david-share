# M365 Morning Sweep Agent

> 一个 AI 驱动的执行助手——通过 **Microsoft Graph API** 读取你的 M365 邮件、日历和 Teams 聊天，使用 **Azure OpenAI** 进行结构化分析，生成"晨扫"简报：邮件优先级排序、带详细上下文的待办事项、联系人画像、关系网络映射、跨数据源智能洞察，以及可直接在 Dashboard 上编辑并发送的 AI 草拟回复。

---

## 在 Azure 上运行

| 组件 | 说明 |
|---|---|
| **Azure OpenAI** | 任意 Chat Completion 部署（GPT-4o、GPT-4.1 等）+ `text-embedding-3-large` 用于向量检索 |
| **Microsoft Graph API** | Mail.Read, Mail.Send, Calendars.Read, Chat.Read, User.Read, People.Read |
| **Azure AI Search** | （可选）邮件/聊天历史的向量+关键词索引 |
| **Azure Cosmos DB** | （可选）联系人画像持久化和分析历史记录 |
| **Foundry IQ** | （可选）Agentic Retrieval——跨邮件和聊天的智能检索 |

---

## 架构

```
┌──────────────────────────────────────────────────────────────────┐
│                     Microsoft Graph API (M365)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │   邮件    │  │   日历   │  │  Teams   │  │  联系人/People  │ │
│  │ (N 小时)  │  │  (48h)   │  │   聊天   │  │   (Top 10)     │ │
│  └─────┬─────┘  └─────┬────┘  └─────┬────┘  └──────┬──────────┘ │
└────────┼───────────────┼─────────────┼──────────────┼────────────┘
         └───────────────┴──────┬──────┴──────────────┘
                                │
                    ┌───────────▼────────────┐
                    │     Azure OpenAI       │
                    │    结构化分析引擎       │
                    │   (JSON 输出模式)      │
                    └───────────┬────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
┌────────▼────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
│   JSON 输出     │  │  Live Server      │  │  静态 Dashboard   │
│   (CLI 模式)    │  │  (SSE + 轮询)     │  │  (HTML 嵌入)      │
└─────────────────┘  └─────────┬─────────┘  └───────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼──────┐ ┌──────▼──────┐ ┌───────▼───────┐
     │  /api/data    │ │ /api/send   │ │ /api/optimize │
     │  JSON API     │ │ 发送邮件    │ │ 人设优化草稿  │
     └───────────────┘ └─────────────┘ └───────────────┘

可选数据层（支持跨 Session 记忆）：
  ┌───────────────┐   ┌───────────────┐   ┌────────────────┐
  │  AI Search    │   │  Cosmos DB    │   │  Foundry IQ    │
  │ emails 索引   │   │ profiles      │   │ Knowledge Base │
  │ chats 索引    │   │ analyses      │   │ Agentic RAG    │
  │ 向量+关键词   │   │ 历史记录      │   │ 跨源检索       │
  └───────────────┘   └───────────────┘   └────────────────┘
```

---

## 功能

### 核心 Agent（`morning_sweep.py`）

**数据采集** — 一次 Sweep 从 4 个 Graph API 端点拉取：
- **邮件**：过去 N 小时（可配置），按主题+发件人去重，带正文摘要
- **日历**：未来 48 小时的事件，含参会人、地点、议程
- **Teams 聊天**：最近 10 个聊天，每个取最新 20 条消息，含群聊
- **联系人**：通过 Microsoft Graph People API 获取最相关的 10 个联系人

**Azure OpenAI 分析** — 将采集到的数据发送给 Chat Completion 模型，以结构化 JSON 输出。System Prompt 要求模型生成：

| 输出字段 | 内容说明 |
|---|---|
| `priority_emails` | **所有**邮件按紧急度（high/medium/low）排序，附建议操作和理由，包含发件人邮箱 |
| `today_schedule` | 日历事件，附准备笔记、关键参会人和上下文 |
| `action_items` | 提取的待办，P0/P1/P2 优先级。每个事项包含 `detail` 对象：background（2-3 句上下文）、prep_needed（具体准备项）、related_people（人名+角色）、related_history、suggested_approach |
| `cross_check_insights` | 跨数据源关联——同一话题同时出现在邮件和聊天中时，标注来源引用 |
| `contact_profiles` | 每人的沟通风格（formal/direct/casual）、关系类型、情感倾向、互动频率、交往建议 |
| `relationship_network` | 核心圈识别 + 需关注的关系预警 |
| `draft_replies` | 为**每封**邮件生成的 AI 回复草稿，根据联系人沟通风格量身定制 |

**认证方式** — 两种模式：
- **委派认证**（交互式）：MSAL Device Code Flow，带持久化 Token 缓存
- **Service Principal**（无人值守）：Client Credentials，适合服务器部署

**跨 Session 记忆** — 基于文件的历史（保留最近 50 次分析的 JSON）。历史分析会回传到 Prompt 中，让模型能说出"这个问题 3 天前就提出了"或"这是一个反复出现的待办"这样的洞察。

### 实时 Dashboard 服务（`live_server.py`）

纯 Python HTTP 服务器（无 Flask/Django 依赖），提供实时 Dashboard：

- **智能轮询**：每 15 秒轮询 Graph API，但只有数据实际变化时才触发 Azure OpenAI 分析（基于邮件主题 + 聊天预览的 MD5 哈希对比），避免不必要的 API 开销
- **SSE 推送**：浏览器每 5-10 秒轮询 `/api/data`，无需刷新页面即可即时更新
- **Basic Auth**：除 `/api/health` 和 `/api/schema` 外，所有端点均需认证
- **线程安全**：分析在后台线程运行，服务器始终保持响应

**REST API 端点**：

| 端点 | 方法 | 认证 | 说明 |
|---|---|---|---|
| `/` | GET | 需要 | Dashboard HTML 页面 |
| `/api/data` | GET | 需要 | 当前分析结果（JSON） |
| `/api/health` | GET | 不需要 | 服务状态、指标、数据时效 |
| `/api/schema` | GET | 不需要 | API 文档，含完整 JSON Schema |
| `/api/send-mail` | POST | 需要 | 通过 Graph API 发送邮件（支持附件） |
| `/api/optimize-draft` | POST | 需要 | 根据特定人设/沟通风格重写草稿 |
| `/api/refresh` | POST | 需要 | 强制重新分析，可自定义时间范围 |
| `/api/insights` | GET | 需要 | CosmosDB 历史趋势 |

### 富 Dashboard（`dashboard.html`）

单文件 HTML Dashboard，无需构建工具或外部依赖：

- **Hero Header**：问候语 + 统计栏（邮件数、待办数、聊天数、画像数）+ 时间范围选择器（24h 到 30 天）+ 手动同步按钮
- **邮件优先级**：按紧急度颜色编码（红/橙/绿边框），可折叠展示建议操作和来源引用
- **To-Do 列表**：交互式复选框（勾选后划线），可折叠详情面板展示背景、准备事项、相关人员和建议方案
- **Teams 聊天**：按聊天主题分组的近期消息，显示发送者、内容摘要和时间戳
- **联系人画像**：头像首字母圆圈、角色/关系标签、沟通风格徽章、情感指示点（绿/橙/红）、交往建议
- **关系网络**：核心圈（绿色标签）和需关注（红色标签）可视化
- **跨源洞察**：渐变卡片展示邮件、聊天、日历之间的关联发现
- **Foundry IQ 面板**：Agentic Retrieval 结果——展示查询、AI 生成的回答、引用数量和来源类型
- **AI 草拟回复**：可折叠的回复卡片，包含：
  - 可编辑的草稿文本（contentEditable）
  - 人设优化按钮——点击联系人名字，根据其沟通风格重写草稿，提供修改前后对比
  - 拖拽或选择文件附件（base64 编码，单文件最大 3MB）
  - 一键发送，带确认弹窗
- **历史洞察**：CosmosDB 支撑的历史面板，展示分析时间线和联系人画像演变
- **Footer**：Token 用量、时间戳、技术栈标签

### 数据层（`data_layer.py`）

可选但推荐在生产环境使用。每个组件独立容错（部分功能失败不影响其他）：

**AI Search 集成**：
- 两个索引：`emails`（含 `body_vector` 用于语义搜索）和 `chats`（含 `content_vector`）
- 数据灌入：Graph API 数据 → `text-embedding-3-large` 向量化 → AI Search 上传
- 检索：关键词搜索、语义/向量搜索、按发件人查询历史
- 用于丰富 GPT 上下文，提供历史模式识别

**Foundry IQ（Agentic Retrieval）**：
- 从 `emails` 和 `chats` AI Search 索引创建 Knowledge Sources
- 创建跨两个来源的 Knowledge Base
- 查询从当前邮件主题和聊天话题自动生成
- 返回带引用的 AI 跨源回答
- 示例："What do I know about: Q2 AI Strategy" → 同时搜索邮件和聊天索引 → 返回综合回答

**CosmosDB 集成**：
- `profiles` 容器：联系人画像（沟通风格、情感、话题），每次分析后更新
- `analyses` 容器：历史分析摘要，用于趋势检测
- 通过 Service Principal 进行 AAD 认证（代码中无 Key）

### 基础设施搭建（`setup_infra.py`）

一条命令搭建所有 Azure 资源：
```bash
python setup_infra.py --all
```
创建：
- AI Search 索引（`emails`、`chats`），HNSW 向量搜索配置，3072 维
- CosmosDB 数据库 `morning_sweep`，含 `profiles` 和 `analyses` 容器
- Foundry IQ Knowledge Sources 和 Knowledge Base
- 从 Graph API 初始数据灌入

---

## 快速开始

### 1. 前置条件

- Python 3.10+
- 一个部署了 Chat Completion 模型的 Azure OpenAI 资源
- 一个配置了 Graph API 权限的 Entra ID 应用注册（参见 [Entra ID 配置](#entra-id-应用注册)）

### 2. 安装

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 Azure OpenAI endpoint、key、tenant ID 和 client ID
```

### 4. 首次运行（交互式登录）

```bash
# 加载环境变量
export $(grep -v '^#' .env | xargs)

# 通过 Device Code Flow 交互式登录
python morning_sweep.py --login --hours 24

# 输出：结构化 JSON 简报打印到控制台
# Token 缓存在 ~/.morning_sweep_token_cache.json，后续运行自动使用
```

### 5. 后续运行

```bash
# 使用缓存 Token，回溯 48 小时，保存到文件
python morning_sweep.py --hours 48 -o briefing.json

# 仅拉取数据（不调用 Azure OpenAI）
python morning_sweep.py --no-ai

# 启用完整数据层（AI Search + CosmosDB + Foundry IQ）
python morning_sweep.py --data-layer --hours 168
```

### 6. 实时 Dashboard

```bash
export $(grep -v '^#' .env | xargs)
python live_server.py
# 浏览器打开 http://localhost:8088
# 默认凭据：admin / changeme（可通过 DASHBOARD_USER/DASHBOARD_PASSWORD 配置）
```

### 7. 基础设施搭建（可选）

```bash
# 需要 SEARCH_ENDPOINT, SEARCH_KEY, COSMOS_ENDPOINT, COSMOS_KEY
python setup_infra.py --setup    # 创建索引和容器
python setup_infra.py --ingest   # 从 Graph API 灌入数据
python setup_infra.py --all      # 全部执行
```

---

## Service Principal 模式（无人值守）

用于自动化/服务器部署，无需交互式登录：

```bash
export USE_SP_AUTH=true
export SP_TENANT=your-tenant-id
export SP_CLIENT_ID=your-sp-client-id
export SP_CLIENT_SECRET=your-sp-client-secret
export SP_TARGET_USER=user@yourtenant.onmicrosoft.com

# CLI 模式
python morning_sweep.py --hours 24 -o output.json

# 或 Live Server 模式
python live_server.py
```

SP 模式下，Graph API 调用会自动将 `/me` 替换为 `/users/{target_user}`。

---

## 文件结构

```
M365-Morning-Sweep/
├── morning_sweep.py                       # 核心 Agent：Graph API → Azure OpenAI → JSON
│                                          #   认证（MSAL 委派 + SP）、数据采集、
│                                          #   GPT 分析、历史持久化（611 行）
├── live_server.py                         # 实时 Dashboard 服务：SSE + 智能轮询 +
│                                          #   REST API + 内嵌 fallback HTML（693 行）
├── dashboard.html                         # 富 Dashboard：hero header、可折叠卡片、
│                                          #   人设优化、拖拽附件、CosmosDB 洞察面板（598 行）
├── data_layer.py                          # AI Search + CosmosDB + Foundry IQ 集成：
│                                          #   灌入、检索、画像、历史（365 行）
├── setup_infra.py                         # 一键 Azure 资源搭建（252 行）
├── auto_refresh_server.py                 # 简单自动刷新服务（仅轮询，94 行）
├── morning_sweep_dashboard_template.html  # 静态/离线模式的 Dashboard 模板
├── refresh_dashboard.sh                   # 一键：拉取数据 + 重建静态 Dashboard
├── requirements.txt                       # Python 依赖
├── .env.example                           # 环境变量模板
├── .gitignore                             # 排除 .env、JSON 数据、Token 缓存
├── README.md                              # English version
└── README-CN.md                           # 本文件
```

---

## Entra ID 应用注册

### 委派权限（交互式登录）

| 权限 | 用途 |
|---|---|
| `Mail.Read` | 读取用户邮件 |
| `Mail.Send` | 从 Dashboard 发送邮件 |
| `Calendars.Read` | 读取日历事件 |
| `Chat.Read` | 读取 Teams 聊天消息 |
| `User.Read` | 获取用户信息（姓名、职位、部门） |
| `People.Read` | 获取相关联系人用于关系映射 |

### 应用权限（Service Principal）

| 权限 | 用途 |
|---|---|
| `Mail.Read` | 读取目标用户邮件 |
| `Calendars.Read` | 读取目标用户日历 |
| `Chat.Read.All` | 读取 Teams 聊天（需管理员同意） |
| `User.Read.All` | 获取用户信息 |

> **注意**：应用权限需要在 Azure Portal 中进行管理员同意。

---

## 配置参考

| 变量 | 是否必须 | 默认值 | 说明 |
|---|---|---|---|
| `TENANT_ID` | 是 | — | Azure AD 租户 ID |
| `CLIENT_ID` | 是 | — | 应用注册的 Client ID |
| `AOAI_ENDPOINT` | 是 | — | Azure OpenAI 端点 URL |
| `AOAI_KEY` | 是 | — | Azure OpenAI API Key |
| `AOAI_DEPLOYMENT` | 否 | `gpt-4o` | Chat Completion 部署名称 |
| `AOAI_API_VERSION` | 否 | `2025-04-01-preview` | Azure OpenAI API 版本 |
| `USE_SP_AUTH` | 否 | `false` | 启用 Service Principal 模式 |
| `SP_TENANT` | SP 模式 | — | SP 租户 ID |
| `SP_CLIENT_ID` | SP 模式 | — | SP Client ID |
| `SP_CLIENT_SECRET` | SP 模式 | — | SP Client Secret |
| `SP_TARGET_USER` | SP 模式 | — | 目标用户 UPN（如 `user@tenant.onmicrosoft.com`） |
| `USE_DATA_LAYER` | 否 | `false` | 启用 AI Search + CosmosDB + Foundry IQ |
| `SEARCH_ENDPOINT` | 数据层 | — | Azure AI Search 端点 |
| `SEARCH_KEY` | 数据层 | — | Azure AI Search Admin Key |
| `COSMOS_ENDPOINT` | 数据层 | — | Cosmos DB 端点 |
| `COSMOS_KEY` | 数据层 | — | Cosmos DB Key（仅 setup_infra.py 使用；运行时用 AAD） |
| `FOUNDRY_IQ_KB` | 数据层 | `morning-sweep-kb` | Knowledge Base 名称 |
| `PORT` | 否 | `8088` | Dashboard 服务端口 |
| `DASHBOARD_USER` | 否 | `admin` | Basic Auth 用户名 |
| `DASHBOARD_PASSWORD` | 否 | `changeme` | Basic Auth 密码 |
| `POLL_INTERVAL` | 否 | `15` | Graph API 轮询间隔（秒） |
| `EMAIL_HOURS` | 否 | `168` | 默认邮件回溯窗口（小时） |

---

## 已知问题 / 故障排除

| 问题 | 解决方案 |
|-------|----------|
| 登录时 `AADSTS65001` | 在 Azure Portal 中为应用注册的权限授予管理员同意 |
| Graph API 访问 `/me/chats` 返回 403 | `Chat.Read` 在大多数租户中需要管理员同意 |
| CosmosDB `(Forbidden) Request originated from IP...` | 将 VM/客户端 IP 添加到 CosmosDB 防火墙白名单，**同时**确保 `publicNetworkAccess` 为 `Enabled`（两者缺一不可） |
| 日历结果为空 | Graph API 使用 UTC 时区；`calendarView` 需要明确的 `startDateTime`/`endDateTime` |
| Token 缓存过期 | 使用 `--login` 通过 Device Code Flow 重新认证 |
| Azure OpenAI 返回非 JSON | 模型偶尔结构化输出失败；Agent 保存原始响应并在下次轮询时重试 |
| Dashboard 显示 "Loading..." | 检查 `/api/health`——如果 status 为 `warming_up`，说明首次 Graph API 轮询尚未完成 |
| Dashboard 发送邮件失败 | 确认 `Mail.Send` 权限已授予并获得管理员同意 |

---

*Author: Xinyu Wei (魏新宇)*
