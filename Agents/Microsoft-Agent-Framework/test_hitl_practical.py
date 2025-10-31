# Copyright (c) Microsoft. All rights reserved.
"""
实用的 Human-in-the-Loop 示例

场景：AI 助手帮助用户完成任务，用户可以：
1. 手工输入任务/问题
2. 审查 AI 的输出
3. 提供反馈让 AI 改进
4. 迭代直到满意

改进：
- 增加 max_tokens 让输出更详细
- 支持手工输入问题
- 更实际的应用场景
"""

import asyncio
import os
from dataclasses import dataclass

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    ChatMessage,
    Executor,
    RequestInfoEvent,
    WorkflowBuilder,
    WorkflowContext,
    WorkflowOutputEvent,
    WorkflowRunState,
    WorkflowStatusEvent,
    handler,
    response_handler,
    Role,
)
from agent_framework.azure import AzureOpenAIChatClient


@dataclass
class HumanReviewRequest:
    """人工审核请求"""
    task: str
    agent_output: str
    iteration: int  # 第几轮迭代


@dataclass
class HumanReviewResponse:
    """人工审核响应"""
    action: str  # "approve" (批准), "revise" (修改), "exit" (退出)
    feedback: str  # 反馈内容


class AIAssistantExecutor(Executor):
    """
    AI 助手 Executor - 包装 AgentExecutor 并处理迭代
    """
    
    def __init__(self, agent_executor: AgentExecutor, id: str = "ai_assistant"):
        super().__init__(id=id)
        self._agent_executor = agent_executor
        self._conversation_history: list[ChatMessage] = []
    
    @handler
    async def handle_user_request(
        self,
        request: AgentExecutorRequest,
        ctx: WorkflowContext
    ) -> None:
        """处理用户请求 - 转发给 Agent"""
        # 保存对话历史
        self._conversation_history.extend(request.messages)
        
        # 转发给 Agent Executor
        await ctx.send_message(request, target_id=self._agent_executor.id)
    
    @handler
    async def handle_agent_response(
        self,
        response: AgentExecutorResponse,
        ctx: WorkflowContext
    ) -> None:
        """处理 Agent 响应 - 发送给人工审核"""
        # 保存 Agent 的回复
        agent_messages = response.agent_run_response.messages
        self._conversation_history.extend(agent_messages)
        
        # 获取 Agent 输出文本
        agent_output = response.agent_run_response.text or "无输出"
        
        # 获取当前任务（从历史消息中提取）
        user_messages = [m for m in self._conversation_history if m.role == Role.USER]
        current_task = user_messages[-1].text if user_messages else "未知任务"
        
        # 计算迭代次数
        state = await ctx.get_executor_state() or {}
        iteration = state.get("iteration", 0) + 1
        await ctx.set_executor_state({"iteration": iteration})
        
        print(f"\n{'='*70}")
        print(f"🤖 AI 助手已完成 (第 {iteration} 轮)")
        print(f"{'='*70}")
        print(f"任务: {current_task[:100]}...")
        print(f"{'='*70}")
        print("📝 AI 输出:")
        print(agent_output)
        print(f"{'='*70}\n")
        
        # 发送审核请求
        review_request = HumanReviewRequest(
            task=current_task,
            agent_output=agent_output,
            iteration=iteration
        )
        
        await ctx.send_message(review_request, target_id="human_reviewer")


class HumanReviewerExecutor(Executor):
    """人工审核员 Executor"""
    
    def __init__(self, id: str = "human_reviewer"):
        super().__init__(id=id)
    
    @handler
    async def review(
        self,
        request: HumanReviewRequest,
        ctx: WorkflowContext
    ) -> None:
        """请求人工审核"""
        await ctx.request_info(
            request_data=request,
            request_type=HumanReviewRequest,
            response_type=HumanReviewResponse
        )
    
    @response_handler
    async def handle_response(
        self,
        original_request: HumanReviewRequest,
        response: HumanReviewResponse,
        ctx: WorkflowContext
    ) -> None:
        """处理人工审核结果"""
        print(f"\n{'='*70}")
        print(f"✅ 收到审核结果: {response.action.upper()}")
        if response.feedback:
            print(f"💬 反馈: {response.feedback}")
        print(f"{'='*70}\n")
        
        if response.action == "approve":
            # 批准 - 输出最终结果
            await ctx.yield_output(f"✅ 任务完成!\n\n{original_request.agent_output}")
        
        elif response.action == "revise":
            # 需要修改 - 将反馈发回 AI 助手
            if not response.feedback:
                print("⚠️  警告: 请求修改但未提供反馈，将使用默认反馈")
                response.feedback = "请改进你的回答，使其更详细、更准确。"
            
            print(f"📤 将反馈发送回 AI 助手...")
            
            revision_request = AgentExecutorRequest(
                messages=[ChatMessage(
                    role=Role.USER,
                    text=f"📝 用户反馈: {response.feedback}\n\n请根据这个反馈改进你的回答。"
                )],
                should_respond=True
            )
            
            await ctx.send_message(revision_request, target_id="ai_assistant")
        
        elif response.action == "exit":
            # 退出
            await ctx.yield_output(f"🛑 用户终止任务。\n\n最后一次输出:\n{original_request.agent_output}")


async def main():
    # 配置
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-chat")
    
    if not endpoint or not api_key:
        print("❌ Error: 请设置环境变量 AZURE_OPENAI_ENDPOINT 和 AZURE_OPENAI_API_KEY")
        return
    
    print("="*70)
    print("🤖 AI 助手 + Human-in-the-Loop 实用示例")
    print("="*70)
    print()
    print("💡 使用说明:")
    print("   1. 输入你的问题/任务")
    print("   2. AI 助手会给出回答")
    print("   3. 你可以选择:")
    print("      - approve (批准) - 满意并结束")
    print("      - revise (修改) - 提供反馈让 AI 改进")
    print("      - exit (退出) - 终止任务")
    print()
    print("="*70)
    print()
    
    # 创建 chat client (增加 max_tokens)
    chat_client = AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2025-01-01-preview",
        max_tokens=2000,  # 📌 增加 max_tokens
    )
    
    # 创建 agent (更详细的指令)
    agent = chat_client.create_agent(
        instructions="""你是一个专业的 AI 助手。

重要要求:
1. 回答要详细、完整、有深度
2. 提供具体的例子和解释
3. 结构清晰，使用标题和列表
4. 如果收到用户反馈，认真理解并针对性改进
5. 不要过于简短，确保信息充分

你的目标是提供高质量、有价值的回答。"""
    )
    
    agent_executor = AgentExecutor(agent=agent, id="agent")
    ai_assistant = AIAssistantExecutor(agent_executor=agent_executor, id="ai_assistant")
    human_reviewer = HumanReviewerExecutor(id="human_reviewer")
    
    # 构建 workflow (循环)
    workflow = (
        WorkflowBuilder()
        .set_start_executor(ai_assistant)
        .add_edge(ai_assistant, agent_executor)  # AI Assistant -> Agent
        .add_edge(agent_executor, ai_assistant)  # Agent -> AI Assistant
        .add_edge(ai_assistant, human_reviewer)  # AI Assistant -> Human Reviewer
        .add_edge(human_reviewer, ai_assistant)  # Human feedback -> AI Assistant
        .build()
    )
    
    # 📌 手工输入任务
    print("🙋 请输入你的问题或任务:")
    print("(例如: 解释什么是 Kubernetes 以及它的核心概念)")
    print()
    user_input = input(">>> ").strip()  # noqa: ASYNC250
    
    if not user_input:
        print("❌ 未输入任务，退出。")
        return
    
    print()
    print(f"✅ 任务已接收: {user_input}")
    print()
    print("⏳ AI 助手正在处理...")
    print("-" * 70)
    
    # Human-in-the-Loop 循环
    pending_responses: dict[str, HumanReviewResponse] | None = None
    workflow_output: str | None = None
    
    while workflow_output is None:
        # 运行或恢复 workflow
        if pending_responses:
            stream = workflow.send_responses_streaming(pending_responses)
        else:
            # 第一次运行 - 发送用户任务
            initial_request = AgentExecutorRequest(
                messages=[ChatMessage(role=Role.USER, text=user_input)],
                should_respond=True
            )
            stream = workflow.run_stream(initial_request)
        
        # 收集事件
        events = [event async for event in stream]
        pending_responses = None
        
        # 处理事件
        human_requests: list[tuple[str, HumanReviewRequest]] = []
        
        for event in events:
            if isinstance(event, RequestInfoEvent):
                if isinstance(event.data, HumanReviewRequest):
                    human_requests.append((event.request_id, event.data))
            
            elif isinstance(event, WorkflowOutputEvent):
                workflow_output = str(event.data)
            
            elif isinstance(event, WorkflowStatusEvent):
                if event.state == WorkflowRunState.IDLE_WITH_PENDING_REQUESTS:
                    print()
        
        # 收集人工审核
        if human_requests:
            responses: dict[str, HumanReviewResponse] = {}
            
            for req_id, request in human_requests:
                print("="*70)
                print("🙋 请审核 AI 的输出")
                print("="*70)
                print("选项:")
                print("  [a] approve  - 批准并结束")
                print("  [r] revise   - 提供反馈让 AI 改进")
                print("  [e] exit     - 退出")
                print("="*70)
                print()
                
                action_input = input("请选择 (a/r/e): ").strip().lower()  # noqa: ASYNC250
                
                if action_input == "a":
                    action = "approve"
                    feedback = ""
                elif action_input == "r":
                    action = "revise"
                    feedback = input("请输入反馈 (如何改进): ").strip()  # noqa: ASYNC250
                elif action_input == "e":
                    action = "exit"
                    feedback = ""
                else:
                    print("⚠️  无效选项，默认为 exit")
                    action = "exit"
                    feedback = ""
                
                print()
                
                responses[req_id] = HumanReviewResponse(
                    action=action,
                    feedback=feedback
                )
            
            pending_responses = responses
    
    # 显示最终结果
    print()
    print("="*70)
    print("🎉 任务完成!")
    print("="*70)
    print()
    print(workflow_output)
    print()


if __name__ == "__main__":
    print()
    asyncio.run(main())
