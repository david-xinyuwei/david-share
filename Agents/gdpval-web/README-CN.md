# GDPVAL Grok 基准测试工具

> 基于真实经济价值任务的 AI 模型评测平台，使用 GPT-5.2 作为评委

## 🎯 概述

GDPVAL (GDP-Valuable Tasks) 基准测试工具在 **9 个行业领域** 的真实业务任务上评估 AI 模型。使用 **GPT-5.2-chat 作为公正评委**，从 5 个维度对回答进行评分（1-10分），并支持人工复核和修正。

**关键结果**: 初步测试中，grok-4-fast-non-reasoning 获得 **8.2/10** 平均分，与 gpt-5.2-chat-baseline (**8.4/10**) 相当。

---

## 🧠 技术架构

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Next.js 14)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  行业    │  │  模型    │  │  进度    │  │   可视化图表     │ │
│  │  选择器  │  │  选择器  │  │  面板    │  │ 雷达/柱状/热力图 │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│                         │ WebSocket                              │
└─────────────────────────┼───────────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────────┐
│                    后端 (FastAPI)                                │
│  ┌──────────────────────┴────────────────────────────────────┐  │
│  │                   WebSocket 处理器                         │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │  │
│  │  │ 阶段 1:     │  │ 阶段 2:     │  │ 阶段 3 & 4:       │  │  │
│  │  │ 模型测试    │→ │ AI 评估     │→ │ 人工复核 +        │  │  │
│  │  │ (流式输出)  │  │ (GPT-5.2)   │  │ 最终结果          │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│         │                      │                                 │
│    ┌────┴────┐           ┌─────┴─────┐                          │
│    │Grok API │           │Azure OpenAI│                          │
│    │(GitHub) │           │ (GPT-5.2)  │                          │
│    └─────────┘           └───────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 四阶段评测流程

| 阶段 | 名称 | 描述 |
|------|------|------|
| 1 | **模型测试** | 调用选定模型回答任务，实时流式输出 |
| 2 | **AI 评估** | GPT-5.2-chat 从 5 个维度评分（1-10分） |
| 3 | **人工复核** | 可选：人工审核并修正 AI 评分 |
| 4 | **完成** | 生成包含人工修正的最终结果 |

### 评估维度

| 维度 | 权重 | 描述 |
|------|------|------|
| 完整性 (Completeness) | 20% | 回答是否涵盖任务的所有方面？ |
| 准确性 (Accuracy) | 20% | 信息是否事实正确？ |
| 专业性 (Professionalism) | 20% | 是否使用恰当的行业术语？ |
| 清晰度 (Clarity) | 20% | 回答结构是否清晰易懂？ |
| 可操作性 (Actionability) | 20% | 是否提供具体可实施的建议？ |

### GPT-5.2 基线对比

为确保评测公平，我们支持将 **GPT-5.2-chat 作为选手**（不使用评委提示词）：

| 角色 | 系统提示词 | API |
|------|-----------|-----|
| **GPT-5.2 作为评委** | 完整评估提示词（含评分标准） | Azure OpenAI responses API |
| **GPT-5.2 作为选手** | 无（与 Grok 模型相同） | Azure OpenAI responses API |

这样可以将 Grok 模型与作为评委的同一模型进行比较，检测潜在的自我偏好偏差。

---

## 🖥️ 环境配置

| 组件 | 规格 |
|------|------|
| **前端** | Next.js 14.2.18 + TypeScript + Tailwind CSS + Recharts |
| **后端** | FastAPI + WebSocket + uvicorn |
| **Grok API** | Azure AI Foundry (models.inference.ai.azure.com) |
| **评委 API** | Azure OpenAI (gpt-5.2-chat，使用 responses API) |
| **Node.js** | >= 18.x |
| **Python** | >= 3.10 |

---

## 🚀 快速开始

### 前置要求

```bash
# Node.js 18+
node --version  # v18.x 或更高

# Python 3.10+
python --version  # 3.10 或更高
```

### 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR-USERNAME/gdpval-benchmark.git
cd gdpval-benchmark

# 后端安装
cd backend
pip install -r requirements.txt

# 前端安装
cd ../frontend
npm install
npm run build
```

### 配置

创建环境变量或在 UI 中配置：

| 参数 | 描述 | 示例 |
|------|------|------|
| `GROK_ENDPOINT` | Azure AI Foundry 端点 | `https://models.inference.ai.azure.com` |
| `GROK_API_KEY` | Grok API 的 GitHub Token | `YOUR-API-KEY` |
| `JUDGE_ENDPOINT` | Azure OpenAI 端点 | `https://YOUR-RESOURCE.openai.azure.com` |
| `JUDGE_API_KEY` | Azure OpenAI API Key | `YOUR-API-KEY` |
| `JUDGE_MODEL` | 评委模型部署名称 | `gpt-5.2-chat` |

### 运行

**方式 1: 分别启动**

```bash
# 终端 1 - 后端 (端口 8000)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# 终端 2 - 前端 (端口 3000)
cd frontend
npm start
```

**方式 2: 一键启动**

```bash
chmod +x start.sh
./start.sh
```

### 访问

- **Web 界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs

---

## 📊 测试结果

### 示例基准测试: 制造业 + 金融行业

**配置**:
- 模型: grok-3-mini, grok-4-fast-non-reasoning, gpt-5.2-chat-baseline
- 每行业任务数: 2
- 总评估数: 12

| 模型 | 制造业 | 金融 | **平均** |
|------|--------|------|----------|
| grok-3-mini | 8.0 | 6.4 | **7.2** |
| grok-4-fast-non-reasoning | 8.2 | 8.2 | **8.2** |
| gpt-5.2-chat-baseline | 8.0 | 8.8 | **8.4** |

### 延迟对比

| 模型 | 平均延迟 | 备注 |
|------|----------|------|
| grok-3-mini | 1.2s | 最快 |
| grok-4-fast-non-reasoning | 0.9s | 非常快 |
| gpt-5.2-chat-baseline | 18.5s | 包含推理过程 |

---

## 🔍 功能特性

### 实时流式输出
- 基于 WebSocket 的模型响应流式传输
- 评估过程中实时进度更新

### 可视化
- **能力雷达图**: 所有模型的 5 维度对比
- **模型排名**: 整体得分水平柱状图
- **行业×模型热力图**: 带平均分的颜色编码性能矩阵

### 导出选项
- **JSON**: 包含响应和评分理由的完整结果
- **Excel**: 用于进一步分析的表格数据
- **HTML 报告**: 可独立分享的报告

### 人工复核
- 在结果表格中编辑 AI 评分
- 修正后自动重新计算图表
- 追踪人工修正数量

---

## ⚠️ 踩坑记录

### 问题 1: GPT-5.2 API 返回错误

**症状**: `[ERROR] Unknown model: gpt-5.2-chat-baseline`

**原因**: 代码使用了显示名称而不是实际模型名称

**解决**: 使用 `self.config.judge_model`（配置值如 `gpt-5.2-chat`）而不是硬编码字符串

### 问题 2: Grok 响应显示变量引用错误

**症状**: 所有 Grok 模型响应都是错误消息 `[ERROR] local variable referenced before assignment`

**原因**: 添加 GPT-5.2 baseline 分支后，流式代码中的变量作用域问题

**解决**: 确保 `await self.send()` 在 `if chunk.choices` 块内

### 问题 3: 重新构建后前端显示空白

**症状**: 页面加载但什么都不显示

**原因**: 多个 Next.js 进程在不同端口运行，或 `.next` 缓存过期

**解决**: 
```bash
pkill -9 -f node
rm -rf .next
npm run build
npm start
```

---

## 📁 项目结构

```
gdpval-web/
├── backend/
│   ├── main.py              # FastAPI + WebSocket 服务器
│   ├── requirements.txt     # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx     # 主页面组件
│   │   │   ├── layout.tsx   # 应用布局
│   │   │   └── globals.css  # 全局样式
│   │   └── components/
│   │       ├── RadarChart.tsx
│   │       ├── BarChart.tsx
│   │       ├── HeatMap.tsx
│   │       ├── ProgressPanel.tsx
│   │       ├── ResultsTable.tsx
│   │       └── StreamLog.tsx
│   ├── package.json
│   ├── next.config.js       # API 代理配置
│   ├── tailwind.config.js
│   └── tsconfig.json
├── README.md                # 英文文档
├── README-CN.md             # 中文文档
└── start.sh
```

---

## 💡 建议

| 使用场景 | 建议 |
|----------|------|
| 快速对比 | 使用 grok-3-mini（最快）vs gpt-5.2-chat-baseline |
| 生产评测 | 使用 grok-4 或 grok-4-fast-reasoning 获得最佳质量 |
| 偏差检测 | 当 GPT-5.2 作为评委时，始终包含 gpt-5.2-chat-baseline |
| 大规模测试 | 限制 tasks_per_sector 为 5-10 以避免速率限制 |

---

## 📚 参考资料

- [Azure AI Foundry - Grok 模型](https://ai.azure.com/)
- [Azure OpenAI - GPT-5.2](https://learn.microsoft.com/azure/ai-services/openai/)
- [Next.js 文档](https://nextjs.org/docs)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.3.0 | 2025-12-21 | 添加 GPT-5.2 基线对比、四阶段流程、人工复核 |
| 0.2.0 | 2025-12-20 | 添加热力图、雷达图、Excel 导出 |
| 0.1.0 | 2025-12-19 | 初始版本（Gradio UI） |

---

*作者: 魏新宇 (Xinyu Wei, Microsoft AI and Apps GBB Architect) | 验证日期: 2025-12-21*
