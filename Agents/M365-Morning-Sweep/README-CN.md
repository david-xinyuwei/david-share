# M365 Morning Sweep Agent

> 一个 AI 驱动的执行助手，通过 **Graph API** 读取你的 Microsoft 365 邮件、日历和 Teams 聊天，使用 **Azure OpenAI** 分析后生成结构化的"晨扫"简报——包含邮件优先级排序、待办事项、联系人画像、关系洞察和 AI 草拟的回复。

---

## 在 Azure 上运行

| 组件 | 说明 |
|---|---|
| **Azure OpenAI** | GPT-4o / GPT-4.1 或任意 Chat Completion 部署 |
| **Microsoft Graph API** | Mail.Read, Calendars.Read, Chat.Read, User.Read, People.Read |
| **Azure AI Search** | （可选）邮件/聊天历史的向量+关键词搜索 |
| **Azure Cosmos DB** | （可选）联系人画像和分析历史持久化 |
| **Foundry IQ** | （可选）跨邮件和聊天的 Agentic Retrieval |

---

## 架构

```
┌──────────────────────────────────────────────────────────┐
│                    Graph API (M365)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │   邮件   │  │   日历   │  │   聊天   │  │  联系人 │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
└───────┼──────────────┼──────────────┼─────────────┼──────┘
        │              │              │             │
        └──────────────┴──────┬───────┴─────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Azure OpenAI     │
                    │    (分析引擎)       │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────▼───┐  ┌───────▼──────┐  ┌─────▼──────┐
     │  JSON       │  │  Live Server │  │  Dashboard │
     │  输出       │  │  (SSE/轮询)  │  │  (HTML)    │
     └─────────────┘  └──────────────┘  └────────────┘

可选数据层：
  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │  AI Search  │   │  Cosmos DB  │   │ Foundry IQ  │
  │  (历史检索) │   │ (画像存储)  │   │ (Agentic)   │
  └─────────────┘   └─────────────┘   └─────────────┘
```

---

## 功能

### 核心功能（无需额外基础设施）
- **邮件优先级排序** — 按紧急度（高/中/低）排列所有邮件，附建议操作
- **今日日程** — 日历事件，附准备笔记和关键参会人
- **待办事项** — 提取的任务，P0/P1/P2 优先级，含详细上下文
- **联系人画像** — 沟通风格、关系类型、情感分析
- **关系网络** — 核心圈识别和需关注的关系预警
- **AI 草拟回复** — 根据每个联系人的沟通风格量身定制的邮件回复
- **交叉验证洞察** — 邮件、聊天、日历之间的关联发现
- **文件历史** — 基于本地 JSON 文件的跨 Session 记忆（保留最近 50 次分析）

### 增强数据层（可选，需要 AI Search + Cosmos DB）
- **向量检索** — 跨历史邮件和聊天的语义搜索
- **Foundry IQ** — 跨数据源的 Agentic Retrieval 智能检索
- **联系人持久化** — 画像存储在 Cosmos DB 中，随时间丰富
- **分析历史** — 历史分析可查询，用于趋势检测

### 实时 Dashboard
- **SSE 推送** — Server-Sent Events 实时更新浏览器（无需刷新页面）
- **智能轮询** — 仅当 Graph API 数据实际变化时才触发 Azure OpenAI（基于 hash）
- **Basic Auth** — 简单的用户名/密码保护
- **交互式 To-Do** — 直接在浏览器中勾选完成待办事项
- **可编辑草稿** — 发送前修改 AI 生成的回复

---

## 快速开始

### 1. 前置条件

- Python 3.10+
- 一个部署了 Chat Completion 模型的 Azure OpenAI 资源
- 一个配置了 Graph API 权限的 Entra ID 应用注册

### 2. 安装

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

### 4. 首次运行（交互式登录）

```bash
# 加载环境变量
export $(grep -v '^#' .env | xargs)

# 交互式登录（通过 Device Code Flow）
python morning_sweep.py --login

# 后续运行使用缓存的 Token
python morning_sweep.py --hours 48 -o output.json
```

### 5. 实时 Dashboard

```bash
export $(grep -v '^#' .env | xargs)
python live_server.py
# 浏览器打开 http://localhost:8088
```

---

## 使用方式

### CLI 参数

```bash
python morning_sweep.py --help

  --login           强制交互式登录
  --hours N         回溯 N 小时的邮件（默认 24）
  --output FILE     保存输出到 JSON 文件
  --no-ai           跳过 Azure OpenAI 分析，仅抓取原始数据
  --data-layer      启用 AI Search + CosmosDB 增强
```

### Service Principal 模式（无人值守）

用于自动化/服务器部署，无需交互式登录：

```bash
export USE_SP_AUTH=true
export SP_TENANT=your-tenant-id
export SP_CLIENT_ID=your-sp-client-id
export SP_CLIENT_SECRET=your-sp-client-secret
export SP_TARGET_USER=user@yourtenant.onmicrosoft.com

python morning_sweep.py --hours 24 -o output.json
```

### 基础设施搭建（可选）

```bash
# 创建 AI Search 索引 + CosmosDB 容器 + Foundry IQ Knowledge Base
python setup_infra.py --all
```

---

## 输出结构

Azure OpenAI 分析生成的结构化 JSON 包含以下部分：

| 字段 | 说明 |
|---------|-------------|
| `greeting` | 个性化的早间问候 |
| `priority_emails` | 所有邮件，含紧急度评级和建议操作 |
| `today_schedule` | 日历事件，含准备笔记 |
| `action_items` | 提取的任务，P0/P1/P2 优先级，含详细上下文 |
| `cross_check_insights` | 跨数据源关联（邮件 ↔ 聊天 ↔ 日历）|
| `contact_profiles` | 每个联系人的沟通风格和关系分析 |
| `relationship_network` | 核心圈和需关注的联系人 |
| `draft_replies` | AI 为每封邮件草拟的回复 |

---

## 文件结构

```
M365-Morning-Sweep/
├── morning_sweep.py               # 核心 Agent：Graph API → Azure OpenAI → JSON
├── live_server.py                  # 实时 Dashboard 服务（SSE + 智能轮询）
├── auto_refresh_server.py          # 简单自动刷新服务（仅轮询）
├── dashboard.html                  # 富 Dashboard，集成 Foundry IQ
├── morning_sweep_dashboard_template.html  # 静态模式的 Dashboard 模板
├── data_layer.py                   # AI Search + CosmosDB + Foundry IQ 集成
├── setup_infra.py                  # 一键基础设施搭建
├── refresh_dashboard.sh            # 一键数据刷新 + Dashboard 重建
├── requirements.txt                # Python 依赖
├── .env.example                    # 环境变量模板
└── .gitignore
```

---

## Entra ID 应用注册

### 委派权限（交互式登录）
- `Mail.Read`
- `Mail.Send`
- `Calendars.Read`
- `Chat.Read`
- `User.Read`
- `People.Read`

### 应用权限（Service Principal）
- `Mail.Read`
- `Calendars.Read`
- `Chat.Read.All`
- `User.Read.All`

---

## 已知问题 / 故障排除

| 问题 | 解决方案 |
|-------|----------|
| 登录时 `AADSTS65001` | 为应用注册的权限授予管理员同意 |
| Graph API 访问 `/me/chats` 返回 403 | `Chat.Read` 权限在大多数租户中需要管理员同意 |
| CosmosDB 防火墙错误 | 将 VM/客户端 IP 添加到 CosmosDB 防火墙白名单，确保 `publicNetworkAccess` 为 `Enabled` |
| 日历结果为空 | 检查时区 — Graph API 使用 UTC，`calendarView` 需要明确的起止时间 |
| Token 缓存过期 | 使用 `--login` 重新认证 |

---

*Author: Xinyu Wei (魏新宇)*
