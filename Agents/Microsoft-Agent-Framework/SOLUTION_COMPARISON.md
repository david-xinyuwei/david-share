# MagenticBuilder HITL 解决方案对比

## 客户问题
> "官方示例 `magentic_human_plan_update.py` 似乎只能用来做 PlanReview，不能在执行过程中让用户补充信息"

## 问题分析

### 官方示例的局限性 ❌

**magentic_human_plan_update.py** 的 HITL 实现：

```python
workflow = (
    MagenticBuilder()
    .participants(researcher=researcher_agent, coder=coder_agent)
    .with_standard_manager(...)
    .with_plan_review()  # ← 只支持 Plan Review
    .build()
)
```

**关键限制**：
1. ✅ **只在执行前** - 仅在 Magentic 开始执行前请求人工审批计划
2. ❌ **不在执行中** - 无法在 agent 执行过程中暂停并收集用户输入
3. ❌ **单次审批** - 只有一个审批点（approve/revise/exit）
4. ❌ **无法分阶段** - 不能在多个阶段之间插入人工审批
5. ❌ **反馈不传递** - revise 只是让 orchestrator 重新规划，不能针对具体 agent 输出提供反馈

**代码特征**：
```python
if isinstance(event, RequestInfoEvent) and event.request_type is MagenticPlanReviewRequest:
    # 只处理 PlanReviewRequest 类型
    pending_request = event
    review_req = cast(MagenticPlanReviewRequest, event.data)
    
    # 用户只能选择 approve/revise/exit
    reply = MagenticPlanReviewReply(decision=MagenticPlanReviewDecision.APPROVE)
```

---

## 我们的解决方案 ✅

### 方案特点

我们实现了 **真正的多阶段执行过程中的 HITL**：

```python
# test_multi_stage_hitl.py - 关键创新点

# 1️⃣ 自定义 RequestInfoEvent 类型 - 不限于 PlanReview
@dataclass
class HumanReviewRequest:
    stage: Stage
    stage_name: str
    content: str  # agent 实际输出的内容
    question: str

@dataclass
class HumanReviewResponse:
    approved: bool
    feedback: str  # 可以是任何用户反馈

# 2️⃣ 在每个 Agent 执行后插入审批点
await ctx.request_info(
    request_data=review_request,
    request_type=HumanReviewRequest,  # 自定义类型
    response_type=HumanReviewResponse
)

# 3️⃣ 反馈真正影响下一个 Agent
if feedback:
    prompt += f"\n\n⚠️ 特别注意用户的要求: {feedback}"
```

### 核心能力对比

| 特性 | 官方示例 | 我们的方案 |
|------|---------|-----------|
| **审批时机** | ❌ 执行前（Plan Review） | ✅ 执行中（每个 Agent 后） |
| **审批点数量** | ❌ 单次 | ✅ 多次（4个阶段 = 4个审批点） |
| **自定义审批类型** | ❌ 固定 PlanReviewRequest | ✅ 任意自定义类型 |
| **查看 Agent 输出** | ❌ 只能看 Plan 文本 | ✅ 看到每个 Agent 的实际输出 |
| **反馈传递** | ❌ revise 只重新规划 | ✅ 反馈直接传给下一个 Agent |
| **拒绝后行为** | ❌ 整个 workflow 重新规划 | ✅ 单个 Agent 根据反馈重做 |
| **适用场景** | 计划确认 | 内容审批、质量把关、迭代改进 |

---

## 技术实现细节

### 1. 官方示例的实现方式

```python
# 官方示例：只在 Magentic 内部的计划阶段暂停
workflow = MagenticBuilder().with_plan_review().build()

# 事件流：
# 1. workflow.run_stream(task)
# 2. Magentic orchestrator 生成 plan
# 3. → RequestInfoEvent[MagenticPlanReviewRequest] ← 唯一的暂停点
# 4. 用户 approve/revise
# 5. Agents 开始执行（无法再暂停）
# 6. FinalResultEvent
```

**问题**：一旦用户 approve 了 plan，就无法再干预！

---

### 2. 我们的实现方式

```python
# 我们的方案：在 workflow 的任何位置插入 HITL

class WorkflowCoordinator(Executor):
    @handler
    async def handle_stage_result(self, result: StageResult, ctx: WorkflowContext):
        # Agent 完成任务
        self._research_result = result.content
        
        # 💡 立即请求人工审批
        review_request = HumanReviewRequest(
            stage=result.stage,
            content=result.content,  # Agent 的实际输出
            question="研究资料是否充分？"
        )
        await ctx.request_info(
            request_data=review_request,
            request_type=HumanReviewRequest,
            response_type=HumanReviewResponse
        )

# 事件流：
# 1. workflow.run_stream(task)
# 2. Researcher Agent 执行
# 3. → RequestInfoEvent[HumanReviewRequest] ← 第1个暂停点
# 4. 用户审批 + 提供反馈
# 5. Outline Agent 执行（收到反馈）
# 6. → RequestInfoEvent[HumanReviewRequest] ← 第2个暂停点
# 7. 用户审批 + 提供反馈
# 8. Writer Agent 执行（收到反馈）
# 9. → RequestInfoEvent[HumanReviewRequest] ← 第3个暂停点
# ... 可以无限扩展
```

---

## 实际效果演示

### 官方示例的交互流程

```
用户输入任务 → Magentic 生成计划
                      ↓
              【Plan Review 审批点】
                      ↓
         用户只能 approve/revise/exit
                      ↓
              Agents 自动执行
              （无法再干预）
                      ↓
                 最终结果
```

### 我们的交互流程

```
用户输入任务 → Researcher Agent 收集资料
                         ↓
              【审批点1：研究资料】
              - 查看：Agent 实际输出的研究内容
              - 操作：批准 / 拒绝重做 / 提供补充意见
              - 反馈："哲学和伦理学重点说"
                         ↓
            Outline Agent 设计大纲
            （收到反馈："哲学和伦理学重点说"）
                         ↓
              【审批点2：文档大纲】
              - 查看：Agent 生成的大纲
              - 操作：批准 / 拒绝重做 / 提供补充意见
              - 反馈："重点谈稳定高薪到资本增值"
                         ↓
              Writer Agent 撰写内容
            （收到反馈："重点谈稳定高薪到资本增值"）
                         ↓
              【审批点3：正文内容】
              - 查看：完整文档内容
              - 操作：批准 / 拒绝重做 / 提供补充意见
                         ↓
              Editor Agent 润色
                         ↓
              【审批点4：最终版本】
                         ↓
                    发布
```

---

## 代码对比

### 官方示例代码

```python
# magentic_human_plan_update.py

# 1. 固定的 Plan Review 类型
if isinstance(event, RequestInfoEvent) and event.request_type is MagenticPlanReviewRequest:
    review_req = cast(MagenticPlanReviewRequest, event.data)
    print(f"Plan: {review_req.plan_text}")  # 只能看到计划文本
    
    # 2. 固定的响应类型
    reply = MagenticPlanReviewReply(
        decision=MagenticPlanReviewDecision.APPROVE  # 只有 APPROVE/REVISE
    )

# 3. 无法访问 Agent 的实际输出
# 4. 无法针对特定 Agent 提供反馈
```

### 我们的代码

```python
# test_multi_stage_hitl.py

# 1. 自定义审批类型 - 灵活！
@dataclass
class HumanReviewRequest:
    stage: Stage              # 当前阶段
    content: str              # Agent 实际输出 ← 关键！
    question: str             # 审批问题
    agent_name: str           # 哪个 Agent 产出的

# 2. 自定义响应 - 可携带任意信息！
@dataclass
class HumanReviewResponse:
    approved: bool
    feedback: str  # 任意文本反馈

# 3. 在任意位置插入审批
async def handle_stage_result(self, result: StageResult, ctx: WorkflowContext):
    # 拿到 Agent 的实际输出
    content = result.content
    
    # 请求人工审批
    await ctx.request_info(
        request_data=HumanReviewRequest(
            stage=result.stage,
            content=content,  # ← Agent 的真实输出！
            question="是否批准？"
        ),
        request_type=HumanReviewRequest,
        response_type=HumanReviewResponse
    )

# 4. 反馈真正传递给下一个 Agent
if feedback:
    prompt = f"上一阶段的反馈: {feedback}\n\n请根据反馈执行任务"
    await ctx.send_message(request, target_id="next_agent")
```

---

## 适用场景对比

### 官方示例适用场景 ✅
- ✅ 任务分解审批
- ✅ 计划合理性检查
- ✅ 资源分配确认
- ✅ 执行策略审批

### 官方示例不适用场景 ❌
- ❌ 内容质量审批（无法看到内容）
- ❌ 分阶段把关（只有一次审批）
- ❌ 迭代改进（feedback 不传递）
- ❌ 合规审查（需要多个审批点）

### 我们的方案适用场景 ✅✅✅
- ✅ **文档撰写流程**：研究 → 大纲 → 撰写 → 编辑（每步审批）
- ✅ **代码开发流程**：需求 → 设计 → 编码 → 测试（每步审批）
- ✅ **数据处理流程**：采集 → 清洗 → 分析 → 报告（每步审批）
- ✅ **内容创作流程**：选题 → 素材 → 初稿 → 终稿（每步审批）
- ✅ **产品设计流程**：调研 → 原型 → UI → Review（每步审批）
- ✅ **任何需要多阶段质量把关的流程**

---

## 核心差异总结

| 维度 | 官方示例 | 我们的方案 |
|------|---------|-----------|
| **HITL 位置** | Magentic 执行前 | Workflow 执行中 |
| **能看到什么** | 文本计划 | Agent 实际输出 |
| **审批次数** | 1 次 | N 次（可扩展） |
| **反馈作用** | 重新生成计划 | 直接影响下一个 Agent |
| **拒绝行为** | 整体重来 | 单个 Agent 重做 |
| **扩展性** | 受限于 Magentic | 完全自定义 |

---

## 结论

**客户问题的根源**：
- 官方示例的 `with_plan_review()` 是 **Magentic 特有的功能**
- 它只能在 **Magentic orchestrator 生成计划时** 暂停
- **无法在 Agent 执行过程中** 进行人工干预

**我们的解决方案**：
- 使用 Agent Framework 的 **通用 HITL 机制**：`ctx.request_info()`
- 可以在 **任何 Executor 的任何位置** 插入审批点
- **完全自定义** 审批数据类型和响应格式
- **真正实现** 执行过程中的人工参与和反馈循环

**关键创新**：
1. ✅ 不依赖 Magentic 的 Plan Review
2. ✅ 在每个 Agent 执行后插入审批点
3. ✅ 查看和审批 Agent 的实际输出
4. ✅ 反馈直接传递给下一个 Agent
5. ✅ 拒绝后单个 Agent 根据反馈重做

---

## 示例代码

完整实现见：`test_multi_stage_hitl.py`

关键代码片段：

```python
# 1. 在 Agent 完成后插入审批
@handler
async def handle_stage_result(self, result: StageResult, ctx: WorkflowContext):
    self._research_result = result.content
    
    # 💡 关键：在这里暂停，等待人工审批
    await ctx.request_info(
        request_data=HumanReviewRequest(...),
        request_type=HumanReviewRequest,
        response_type=HumanReviewResponse
    )

# 2. 处理审批结果
@handler
async def handle_approval(self, approval: tuple[Stage, bool, str], ctx: WorkflowContext):
    stage, approved, feedback = approval
    
    if not approved:
        # 💡 拒绝：Agent 重做
        await ctx.send_message(redo_request, target_id="agent")
    else:
        # 💡 批准：传递反馈给下一个 Agent
        prompt = f"任务描述...\n\n⚠️ 用户反馈: {feedback}"
        await ctx.send_message(request, target_id="next_agent")
```

---

## 对客户的回答

> **问**：官方示例只能做 PlanReview，不能在执行过程中让用户补充信息，能否解决？

> **答**：✅ **完全可以解决！**
> 
> 我们的方案不使用 Magentic 的 `with_plan_review()`，而是利用 Agent Framework 的通用 HITL 机制 `ctx.request_info()`，在每个 Agent 执行后插入审批点。
> 
> **关键优势**：
> 1. ✅ 真正的执行中暂停（不是执行前）
> 2. ✅ 可以看到每个 Agent 的实际输出
> 3. ✅ 可以在多个阶段插入审批点
> 4. ✅ 用户反馈直接影响下一个 Agent
> 5. ✅ 拒绝后单个 Agent 重做（不是整体重来）
> 
> **已验证的4个特性**：
> 1. ✅ 每个流程使用不同的 Agent
> 2. ✅ Coordinator 调度不同的 Agent
> 3. ✅ 补充意见真正传递并生效
> 4. ✅ 拒绝后有真实的重做 action
> 
> 详见：`test_multi_stage_hitl.py`
