import logging
logging.getLogger('agent_framework').setLevel(logging.ERROR)

# Copyright (c) Microsoft. All rights reserved.
"""
Real Multi-Stage Human-in-the-Loop Workflow

Scenario: Technical Documentation Writing Process
涉及: 多个专业 Agent + 多个人工审批点

工作流程:
1. 用户输入文档主题
2. Researcher Agent 收集相关资料
3. 【人工审批点 1】审查研究资料，决定是否继续
4. 大纲设计 Agent 设计文档结构
5. 【人工审批点 2】审批大纲，提供修改意见
6. 撰写 Agent 根据大纲撰写正文
7. 【人工审批点 3】审批内容质量
8. 编辑 Agent 润色和格式化
9. 输出最终文档
"""

import asyncio
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from enum import Enum

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


class Stage(Enum):
    """工作流Stage"""
    RESEARCH = "research"
    OUTLINE = "outline"
    WRITING = "writing"
    EDITING = "editing"


@dataclass
class StageResult:
    """Stage结果"""
    stage: Stage
    content: str
    agent_id: str


@dataclass
class HumanReviewRequest:
    """人工审批请求"""
    stage: Stage
    stage_name: str
    content: str
    question: str


@dataclass
class HumanReviewResponse:
    """人工审批响应"""
    approved: bool
    feedback: str


class WorkflowCoordinator(Executor):
    """
    工作流协调器
    负责路由不同Stage的结果到相应的处理器
    """
    
    def __init__(self, id: str = "coordinator"):
        super().__init__(id=id)
        self._topic = ""
        self._research_result = ""
        self._outline_result = ""
        self._writing_result = ""
    
    @handler
    async def start_workflow(
        self,
        topic: str,
        ctx: WorkflowContext
    ) -> None:
        """启动工作流 - 发送给Researcher"""
        self._topic = topic
        
        print(f"\n{'='*70}")
        print(f"🚀 Workflow Started")
        print(f"{'='*70}")
        print(f"📋 Document Topic: {topic}")
        print(f"{'='*70}\n")
        print("📍 Stage 1: Research Data Collection")
        print("-" * 70)
        
        # 发送给Researcher
        request = AgentExecutorRequest(
            messages=[ChatMessage(
                role=Role.USER,
                text=f"请收集关于以下主题的相关资料和关键信息：{topic}\n\n要求：提供详细的背景信息、核心概念、最佳实践等。"
            )],
            should_respond=True
        )
        await ctx.send_message(request, target_id="researcher")
    
    @handler
    async def handle_stage_result(
        self,
        result: StageResult,
        ctx: WorkflowContext
    ) -> None:
        """处理Stage结果"""
        # 保存结果
        if result.stage == Stage.RESEARCH:
            self._research_result = result.content
        elif result.stage == Stage.OUTLINE:
            self._outline_result = result.content
        elif result.stage == Stage.WRITING:
            self._writing_result = result.content
        
        # 发送人工审批请求
        stage_names = {
            Stage.RESEARCH: "研究资料",
            Stage.OUTLINE: "文档大纲",
            Stage.WRITING: "正文内容",
            Stage.EDITING: "编辑润色"
        }
        
        questions = {
            Stage.RESEARCH: "Is the research sufficient? Does it need supplementation?",
            Stage.OUTLINE: "文档结构是否合理？是否需要调整？",
            Stage.WRITING: "内容质量是否满意？是否需要修改？",
            Stage.EDITING: "最终版本是否可以发布？"
        }
        
        review_request = HumanReviewRequest(
            stage=result.stage,
            stage_name=stage_names[result.stage],
            content=result.content,
            question=questions[result.stage]
        )
        
        await ctx.send_message(review_request, target_id="human_reviewer")
    
    @handler
    async def handle_approval(
        self,
        approval_result: tuple[Stage, bool, str],
        ctx: WorkflowContext
    ) -> None:
        """处理审批结果"""
        stage, approved, feedback = approval_result
        
        if not approved:
            # ✅ 验证点4: 拒绝后有真实的action
            print(f"\n{'='*70}")
            print(f"✅ Checkpoint 4: Real Action After Rejection - Agent Will Re-execute")
            print(f"{'='*70}")
            
            agent_map = {
                Stage.RESEARCH: "researcher",
                Stage.OUTLINE: "outline_designer",
                Stage.WRITING: "writer"
            }
            
            agent_id = agent_map.get(stage)
            if agent_id:
                print(f"❌ {stage.value} stage not approved, sending back for revision...")
                print(f"💬 Feedback: {feedback}")
                print(f"🔄 Scheduling {agent_id} for re-execution...")
                print(f"{'='*70}\n")
                
                request = AgentExecutorRequest(
                    messages=[ChatMessage(
                        role=Role.USER,
                        text=f"上一次的输出未通过审批。\n\nFeedback: {feedback}\n\n请根据反馈重新完成任务。"
                    )],
                    should_respond=True
                )
                await ctx.send_message(request, target_id=agent_id)
            return
        
        # 批准 - 进入下一Stage
        print(f"\n✅ {stage.value} Stage已批准")
        if feedback:
            print(f"💬 Feedback: {feedback}")
        print()
        
        if stage == Stage.RESEARCH:
            # ✅ 验证点2: Coordinator 调度不同的 agent
            print("✅ 验证点2: Coordinator调度 → 大纲设计Agent")
            print("📍 Stage 2: Document Outline Design")
            print("-" * 70)
            
            prompt = f"基于以下研究资料，设计一份详细的文档大纲：\n\n{self._research_result}\n\n要求：包含清晰的章节结构和每个部分的要点。"
            
            # ✅ 验证点3: 如果有反馈，添加到提示中
            if feedback:
                print(f"✅ 验证点3: 补充意见已添加到prompt: '{feedback}'")
                prompt += f"\n\n⚠️ 特别注意用户的要求: {feedback}"
            
            request = AgentExecutorRequest(
                messages=[ChatMessage(
                    role=Role.USER,
                    text=prompt
                )],
                should_respond=True
            )
            await ctx.send_message(request, target_id="outline_designer")
        
        elif stage == Stage.OUTLINE:
            # ✅ 验证点2: Coordinator 调度不同的 agent
            print("✅ 验证点2: Coordinator调度 → 撰写Agent")
            print("📍 Stage 3: 正文撰写")
            print("-" * 70)
            
            prompt = f"根据以下大纲撰写详细的文档内容：\n\n{self._outline_result}\n\n参考资料：\n{self._research_result}\n\n要求：内容详实、逻辑清晰、语言专业。"
            
            # ✅ 验证点3: 如果有反馈，添加到提示中
            if feedback:
                print(f"✅ 验证点3: 补充意见已添加到prompt: '{feedback}'")
                prompt += f"\n\n⚠️ 特别注意用户的要求: {feedback}"
            
            request = AgentExecutorRequest(
                messages=[ChatMessage(
                    role=Role.USER,
                    text=prompt
                )],
                should_respond=True
            )
            await ctx.send_message(request, target_id="writer")
        
        elif stage == Stage.WRITING:
            # ✅ 验证点2: Coordinator 调度不同的 agent
            print("✅ 验证点2: Coordinator调度 → 编辑Agent")
            print("📍 Stage 4: 编辑润色")
            print("-" * 70)
            
            prompt = f"请对以下文档进行润色和格式化：\n\n{self._writing_result}\n\n要求：确保语言流畅、格式规范、无错别字。"
            
            # ✅ 验证点3: 如果有反馈，添加到提示中
            if feedback:
                print(f"✅ 验证点3: 补充意见已添加到prompt: '{feedback}'")
                prompt += f"\n\n⚠️ 特别注意用户的要求: {feedback}"
            
            request = AgentExecutorRequest(
                messages=[ChatMessage(
                    role=Role.USER,
                    text=prompt
                )],
                should_respond=True
            )
            await ctx.send_message(request, target_id="editor")
        
        elif stage == Stage.EDITING:
            # 编辑完成 -> 输出最终文档
            print("📍 工作流完成!")
            print("="*70)
            await ctx.yield_output(self._writing_result)  # 输出最终版本


class StageExecutor(Executor):
    """
    Stage执行器 - 包装 AgentExecutor
    """
    
    def __init__(self, agent_executor: AgentExecutor, stage: Stage, id: str):
        super().__init__(id=id)
        self._agent_executor = agent_executor
        self._stage = stage
    
    @handler
    async def handle_request(
        self,
        request: AgentExecutorRequest,
        ctx: WorkflowContext
    ) -> None:
        """转发请求给 Agent"""
        await ctx.send_message(request, target_id=self._agent_executor.id)
    
    @handler
    async def handle_response(
        self,
        response: AgentExecutorResponse,
        ctx: WorkflowContext
    ) -> None:
        """处理 Agent 响应"""
        content = response.agent_run_response.text or "无输出"
        
        # 包装成 StageResult 发送给协调器
        result = StageResult(
            stage=self._stage,
            content=content,
            agent_id=self.id
        )
        
        await ctx.send_message(result, target_id="coordinator")


class HumanReviewerExecutor(Executor):
    """人工审核执行器"""
    
    def __init__(self, id: str = "human_reviewer"):
        super().__init__(id=id)
    
    @handler
    async def review(
        self,
        request: HumanReviewRequest,
        ctx: WorkflowContext
    ) -> None:
        """请求人工审核"""
        print(f"\n{'='*70}")
        print(f"🔍 {request.stage_name}完成 - 需要人工审批")
        print(f"{'='*70}")
        print(f"📄 Content Preview:")
        print(request.content[:500] + ("..." if len(request.content) > 500 else ""))
        print(f"{'='*70}\n")
        
        await ctx.request_info(
            request_data=request,
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
        # 发送审批结果给协调器
        approval_result = (
            original_request.stage,
            response.approved,
            response.feedback
        )
        await ctx.send_message(approval_result, target_id="coordinator")


async def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # 配置
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-chat")
    
    if not endpoint or not api_key:
        print("❌ Error: 请设置环境变量")
        return
    
    print("="*70)
    print("📝 Technical Documentation Workflow (Multi-Stage HITL)")
    print("="*70)
    print()
    print("💡 Workflow contains 4 stages:")
    print("   1️⃣  Research → Human Approval")
    print("   2️⃣  Outline → Human Approval")
    print("   3️⃣  Writing → Human Approval")
    print("   4️⃣  Editing → Output")
    print()
    print("="*70)
    print()
    
    # 创建 chat client
    chat_client = AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2025-01-01-preview",
        max_tokens=1500,
    )
    
    # ✅ 验证点1: 创建4个不同的 Agents，每个有独立的instructions
    print("="*70)
    print("✅ Checkpoint 1: Create Different Agents")
    print("="*70)
    
    print("🤖 Agent 1: Researcher")
    print("   Instructions: Professional researcher responsible for collecting and organizing materials")
    researcher_agent = chat_client.create_agent(
        instructions="你是Professional researcher responsible for collecting and organizing materials。提供详细、准确的信息。"
    )
    
    print("🤖 Agent 2: Document Architect")
    print("   Instructions: Responsible for designing clear document structure and outline")
    outline_agent = chat_client.create_agent(
        instructions="你是Document Architect，Responsible for designing clear document structure and outline。确保逻辑清晰、层次分明。"
    )
    
    print("🤖 Agent 3: Technical Writer")
    print("   Instructions: Responsible for writing detailed document content")
    writer_agent = chat_client.create_agent(
        instructions="你是专业的Technical Writer，Responsible for writing detailed document content。语言专业、内容充实。"
    )
    
    print("🤖 Agent 4: Professional Editor")
    print("   Instructions: Responsible for polishing and formatting documents")
    editor_agent = chat_client.create_agent(
        instructions="你是Professional Editor，Responsible for polishing and formatting documents。确保语言流畅、格式规范。"
    )
    
    print("="*70)
    print()
    
    # 创建 Executors
    researcher_exec = AgentExecutor(agent=researcher_agent, id="researcher_agent")
    outline_exec = AgentExecutor(agent=outline_agent, id="outline_agent")
    writer_exec = AgentExecutor(agent=writer_agent, id="writer_agent")
    editor_exec = AgentExecutor(agent=editor_agent, id="editor_agent")
    
    researcher = StageExecutor(researcher_exec, Stage.RESEARCH, "researcher")
    outline_designer = StageExecutor(outline_exec, Stage.OUTLINE, "outline_designer")
    writer = StageExecutor(writer_exec, Stage.WRITING, "writer")
    editor = StageExecutor(editor_exec, Stage.EDITING, "editor")
    
    coordinator = WorkflowCoordinator()
    human_reviewer = HumanReviewerExecutor()
    
    # 构建复杂的工作流
    workflow = (
        WorkflowBuilder()
        .set_start_executor(coordinator)
        # Coordinator -> Stage Executors
        .add_edge(coordinator, researcher)
        .add_edge(coordinator, outline_designer)
        .add_edge(coordinator, writer)
        .add_edge(coordinator, editor)
        # Stage Executors -> Agents
        .add_edge(researcher, researcher_exec)
        .add_edge(outline_designer, outline_exec)
        .add_edge(writer, writer_exec)
        .add_edge(editor, editor_exec)
        # Agents -> Stage Executors
        .add_edge(researcher_exec, researcher)
        .add_edge(outline_exec, outline_designer)
        .add_edge(writer_exec, writer)
        .add_edge(editor_exec, editor)
        # Stage Executors -> Coordinator
        .add_edge(researcher, coordinator)
        .add_edge(outline_designer, coordinator)
        .add_edge(writer, coordinator)
        .add_edge(editor, coordinator)
        # Coordinator -> Human Reviewer
        .add_edge(coordinator, human_reviewer)
        # Human Reviewer -> Coordinator
        .add_edge(human_reviewer, coordinator)
        .build()
    )
    
    # 获取用户输入
    print("🙋 Please enter the technical document topic:")
    print("(Example: Docker Containerization Getting Started Guide)")
    print()
    topic = input(">>> ").strip()  # noqa: ASYNC250
    
    if not topic:
        print("❌ 未输入主题，退出。")
        return
    
    print()
    
    # 运行工作流
    pending_responses: dict[str, HumanReviewResponse] | None = None
    workflow_output: str | None = None
    
    while workflow_output is None:
        if pending_responses:
            stream = workflow.send_responses_streaming(pending_responses)
        else:
            stream = workflow.run_stream(topic)
        
        events = [event async for event in stream]
        pending_responses = None
        
        human_requests: list[tuple[str, HumanReviewRequest]] = []
        
        for event in events:
            if isinstance(event, RequestInfoEvent):
                if isinstance(event.data, HumanReviewRequest):
                    human_requests.append((event.request_id, event.data))
            elif isinstance(event, WorkflowOutputEvent):
                workflow_output = str(event.data)
        
        # 处理人工审批
        if human_requests:
            responses: dict[str, HumanReviewResponse] = {}
            
            for req_id, request in human_requests:
                print("="*70)
                print(f"🙋 人工审批: {request.stage_name}")
                print("="*70)
                print(f"❓ {request.question}")
                print("="*70)
                print()
                
                approved_input = input("Approve? (y/n): ").strip().lower()  # noqa: ASYNC250
                approved = approved_input == "y"
                
                feedback = ""
                if not approved:
                    feedback = input("Please provide feedback: ").strip()  # noqa: ASYNC250
                else:
                    feedback_input = input("Any additional comments? (Press Enter to skip): ").strip()  # noqa: ASYNC250
                    if feedback_input:
                        feedback = feedback_input
                
                print()
                
                responses[req_id] = HumanReviewResponse(
                    approved=approved,
                    feedback=feedback
                )
            
            pending_responses = responses
    
    # 最终输出
    print()
    print("="*70)
    print("🎉 文档撰写完成!")
    print("="*70)
    print()
    print(workflow_output)
    print()


if __name__ == "__main__":
    print()
    asyncio.run(main())

