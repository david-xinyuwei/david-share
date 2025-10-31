# Multi-Stage Human-in-the-Loop (HITL) Workflow Solution

## 📋 概述

本项目提供了一个完整的**多阶段人工参与工作流**解决方案，解决了 Microsoft Agent Framework 官方示例 `magentic_human_plan_update.py` 的局限性。

### 客户问题
> "官方示例只能用来做 PlanReview，不能在执行过程中让用户补充信息"

### 我们的解决方案
✅ **在 Agent 执行过程中**插入多个人工审批点  
✅ 查看每个 Agent 的**实际输出内容**  
✅ 用户反馈**直接传递**给下一个 Agent  
✅ 拒绝后单个 Agent **根据反馈重做**  

---

## 🎯 核心特性

### 1️⃣ 多阶段审批
- 支持在工作流的**任意位置**插入审批点
- 示例中实现了4个阶段的人工审批
- 可扩展到任意多个审批点

### 2️⃣ 真实输出审查
- 不是审批"计划"，而是审批 Agent 的**实际输出**
- 可以看到每个 Agent 生成的完整内容
- 基于真实结果做决策

### 3️⃣ 反馈传递机制
- 用户在审批时提供的补充意见
- 会自动添加到下一个 Agent 的 prompt 中
- 确保用户需求贯穿整个流程

### 4️⃣ 灵活的拒绝处理
- 拒绝后只需重做当前阶段
- 不用从头开始整个流程
- Agent 根据用户反馈进行针对性改进

---

## 📂 文件说明

### 主要文件

| 文件 | 说明 |
|------|------|
| **test_multi_stage_hitl.py** | 完整的4阶段HITL工作流示例（文档撰写场景） |
| **SOLUTION_COMPARISON.md** | 详细的方案对比文档（官方示例 vs 我们的方案） |
| **test_hitl_practical.py** | 简化的2阶段HITL示例（快速理解概念） |
| **test_magentic.py** | MagenticBuilder基础用法（对比参考） |
| **README.md** | 本文档 |

### 推荐阅读顺序
1. 📖 **README.md** - 快速了解方案
2. 📄 **SOLUTION_COMPARISON.md** - 深入理解技术方案
3. 💻 **test_multi_stage_hitl.py** - 运行完整示例

---

## 🚀 快速开始

### 前置要求
- Python 3.8+
- Microsoft Agent Framework (`agent-framework-core`)
- Azure OpenAI 或 OpenAI API 访问权限

### 配置环境变量

```bash
# Linux/Mac
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key-here"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"

# Windows PowerShell
$env:AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-api-key-here"
$env:AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4"
```

### 运行示例

```bash
python test_multi_stage_hitl.py
```

### 交互流程

```
1️⃣ 输入文档主题
   例如: "如何学好AI" 或 "Docker容器化技术入门"

2️⃣ 阶段1: 研究资料收集
   → Agent 完成资料收集
   → 【审批点】查看研究内容
   → 操作: y批准 / n拒绝 / 提供补充意见

3️⃣ 阶段2: 文档大纲设计
   → Agent 设计文档结构（收到上一阶段的反馈）
   → 【审批点】查看大纲
   → 操作: y批准 / n拒绝 / 提供补充意见

4️⃣ 阶段3: 正文撰写
   → Agent 撰写完整内容
   → 【审批点】查看正文
   → 操作: y批准 / n拒绝 / 提供补充意见

5️⃣ 阶段4: 编辑润色
   → Agent 润色格式化
   → 【审批点】最终审批
   → 完成！输出最终文档
```

---

## 🆚 对比官方示例

### 详细对比表格

| 特性 | 官方示例 | 我们的方案 |
|------|---------|-----------|
| **HITL 时机** | ❌ 执行前 | ✅ 执行中 |
| **审批内容** | ❌ 文本计划 | ✅ Agent 实际输出 |
| **审批次数** | ❌ 1次 | ✅ N次（示例4次） |
| **反馈作用** | ❌ 重新生成计划 | ✅ 影响下一个 Agent |
| **拒绝行为** | ❌ 整体重来 | ✅ 单个 Agent 重做 |
| **扩展性** | ❌ 受限于 Magentic | ✅ 完全自定义 |

详细对比见：[SOLUTION_COMPARISON.md](./SOLUTION_COMPARISON.md)

---

## 💡 核心技术实现

### 关键代码片段

#### 1. 自定义审批类型

```python
@dataclass
class HumanReviewRequest:
    stage: Stage
    stage_name: str
    content: str      # Agent 的实际输出
    question: str

@dataclass
class HumanReviewResponse:
    approved: bool
    feedback: str     # 用户反馈
```

#### 2. 在 Agent 执行后插入审批点

```python
@handler
async def handle_stage_result(self, result: StageResult, ctx: WorkflowContext):
    # 💡 关键：请求人工审批
    await ctx.request_info(
        request_data=HumanReviewRequest(
            content=result.content  # Agent 的实际输出
        ),
        request_type=HumanReviewRequest,
        response_type=HumanReviewResponse
    )
```

#### 3. 反馈传递给下一个 Agent

```python
@handler
async def handle_approval(self, approval, ctx: WorkflowContext):
    stage, approved, feedback = approval
    
    if approved:
        prompt = f"基于以下资料设计大纲：\n\n{self._research_result}"
        
        # 💡 关键：添加用户反馈
        if feedback:
            prompt += f"\n\n⚠️ 用户要求: {feedback}"
        
        await ctx.send_message(request, target_id="next_agent")
```

---

## 📊 实际运行效果

### 示例：反馈生效

```
用户输入: "如何学好AI"

阶段1 - 研究资料:
输出: 通用的AI学习资料...
反馈: "哲学和伦理学重点说" ✅

阶段2 - 文档大纲:
输出: 增加了"哲学与伦理视角"章节 ← 反馈生效！
反馈: "重点谈从稳定高薪到资本增值" ✅

阶段3 - 正文撰写:
输出: 标题变为《从稳定高薪到资本增值》← 反馈生效！
```

---

## 🎯 适用场景

### ✅ 非常适合

- **文档撰写流程**：研究 → 大纲 → 撰写 → 编辑
- **代码开发流程**：需求 → 设计 → 编码 → 测试
- **内容创作流程**：选题 → 素材 → 初稿 → 终稿
- **数据处理流程**：采集 → 清洗 → 分析 → 报告
- **产品设计流程**：调研 → 原型 → UI → Review
- **任何需要多阶段质量把关的流程**

---

## 🐛 常见问题

### Q1: 环境变量未设置
**错误**: `❌ Error: 请设置环境变量`

**解决**: 确保设置了 `AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_API_KEY`、`AZURE_OPENAI_DEPLOYMENT_NAME`

### Q2: 导入错误
**错误**: `ModuleNotFoundError: No module named 'agent_framework'`

**解决**: `pip install agent-framework-core`

---

## 📚 相关资源

- [Agent Framework GitHub](https://github.com/microsoft/agent-framework)
- [Agent Framework 文档](https://microsoft.github.io/agent-framework/)
- [官方 HITL 示例](https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/workflows/human_in_the_loop)

---

## 👤 作者

**David Xinyuwei**
- GitHub: [@david-xinyuwei](https://github.com/david-xinyuwei)

---

**最后更新**: 2025年10月31日
