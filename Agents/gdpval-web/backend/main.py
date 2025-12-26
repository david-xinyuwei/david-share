"""
GDPVAL Grok Benchmark Tool - FastAPI Backend
WebSocket 实时推送 + REST API
"""

import json
import time
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI, AzureOpenAI

# ============================================================
# 数据模型
# ============================================================

class BenchmarkConfig(BaseModel):
    sectors: list[str]
    models: list[str]
    tasks_per_sector: int = 2
    grok_endpoint: str = "https://models.inference.ai.azure.com"
    grok_api_key: str = ""
    judge_endpoint: str = "https://your-aoai-endpoint.openai.azure.com"
    judge_api_key: str = ""
    judge_model: str = "gpt-4.1"
    judge_api_version: str = "2024-12-01-preview"

class TaskResult(BaseModel):
    model: str
    sector: str
    occupation: str
    completeness: float
    accuracy: float
    professionalism: float
    clarity: float
    actionability: float
    overall: float
    latency: float
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    response: str = ""
    judge_summary: str = ""
    judge_strengths: str = ""
    judge_weaknesses: str = ""
    human_score: Optional[float] = None
    notes: str = ""

# ============================================================
# 加载 GDPVAL 数据
# ============================================================

DATA_PATH = Path(__file__).parent.parent.parent / "gdpval_enhanced.json"
DATA_PATH_FALLBACK = Path(__file__).parent.parent.parent / "gdpval.json"

def load_gdpval_data():
    """加载 GDPVAL 增强数据集（含附件内容）"""
    if DATA_PATH.exists():
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 回退到原始数据
    if DATA_PATH_FALLBACK.exists():
        with open(DATA_PATH_FALLBACK, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

GDPVAL_DATA = load_gdpval_data()

# 计算每个行业的任务数
def get_sector_stats():
    from collections import Counter
    sector_counts = Counter(t['sector'] for t in GDPVAL_DATA)
    return dict(sector_counts)

# ============================================================
# Grok 模型列表
# ============================================================

GROK_MODELS = [
    "grok-3",
    "grok-3-mini", 
    "grok-4",
    "grok-4-fast-reasoning",
    "grok-4-fast-non-reasoning",
    "grok-code-fast-1",
    "gpt-5.1-chat-baseline"
]

# ============================================================
# Judge Prompt
# ============================================================

JUDGE_PROMPT = """You are an expert evaluator assessing AI responses to professional workplace tasks.

Task given to AI:
{task}

AI's Response:
{response}

Evaluate the response on these 5 dimensions (1-10 scale). For each dimension, provide the score AND a brief reason:

1. Completeness - Does it address all aspects of the task?
2. Accuracy - Is the information correct and reliable?
3. Professionalism - Is the tone and format appropriate?
4. Clarity - Is it well-organized and easy to understand?
5. Actionability - Can the user directly apply this advice?

Return JSON only:
{
  "completeness": {"score": <1-10>, "reason": "<why this score>"},
  "accuracy": {"score": <1-10>, "reason": "<why this score>"},
  "professionalism": {"score": <1-10>, "reason": "<why this score>"},
  "clarity": {"score": <1-10>, "reason": "<why this score>"},
  "actionability": {"score": <1-10>, "reason": "<why this score>"},
  "overall": <average of 5 scores>,
  "summary": "<one sentence overall assessment>",
  "strengths": "<key strengths>",
  "weaknesses": "<areas for improvement>"
}"""

# ============================================================
# FastAPI App
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"✅ GDPVAL Backend started. Loaded {len(GDPVAL_DATA)} tasks.")
    yield
    print("👋 GDPVAL Backend shutting down.")

app = FastAPI(
    title="GDPVAL Grok Benchmark API",
    version="0.2.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# REST API 端点
# ============================================================

@app.get("/api/info")
async def get_info():
    """获取数据集信息"""
    return {
        "total_tasks": len(GDPVAL_DATA),
        "sectors": get_sector_stats(),
        "models": GROK_MODELS
    }

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# ============================================================
# WebSocket 实时评测
# ============================================================

class BenchmarkRunner:
    """评测执行器"""
    
    def __init__(self, websocket: WebSocket, config: BenchmarkConfig):
        self.ws = websocket
        self.config = config
        self.grok_client = None
        self.judge_client = None
        
    async def send(self, msg_type: str, data: dict):
        """发送 WebSocket 消息"""
        await self.ws.send_json({"type": msg_type, **data})
    
    def create_clients(self):
        """创建 API 客户端"""
        # Grok client (Azure AI Foundry - OpenAI 兼容格式)
        self.grok_client = OpenAI(
            base_url=self.config.grok_endpoint,
            api_key=self.config.grok_api_key,
        )
        
        # Judge client (Azure OpenAI)
        self.judge_client = AzureOpenAI(
            azure_endpoint=self.config.judge_endpoint,
            api_key=self.config.judge_api_key,
            api_version=self.config.judge_api_version
        )
    
    async def run_grok_task(self, model: str, prompt: str) -> tuple[str, float, int, int, int]:
        """调用 Grok 模型，流式输出，返回 (response, latency, input_tokens, output_tokens, cached_tokens)"""
        start_time = time.time()
        full_response = ""
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        
        try:
            # GPT-5.1 baseline: use judge_client with gpt-5.1-chat (not judge model)
            if model == "gpt-5.1-chat-baseline":
                response = self.judge_client.responses.create(
                    model="gpt-5.1-chat",  # Use gpt-5.1-chat as baseline contestant
                    input=prompt,
                    reasoning={"effort": "medium"}
                )
                for item in response.output:
                    if item.type == "message":
                        for block in item.content:
                            if block.type == "output_text":
                                full_response = block.text
                                await self.send("stream", {"content": full_response})
                # 从 GPT-5.1 response 获取实际 usage
                if hasattr(response, 'usage') and response.usage:
                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens
                    if hasattr(response.usage, 'input_tokens_details') and response.usage.input_tokens_details:
                        cached_tokens = getattr(response.usage.input_tokens_details, 'cached_tokens', 0)
                    print(f"[TOKEN] GPT-5.2 usage: input={input_tokens}, output={output_tokens}, cached={cached_tokens}")
                else:
                    # 估算 token 数
                    input_tokens = len(prompt) // 4
                    output_tokens = len(full_response) // 4
                    print(f"[TOKEN] GPT-5.2 estimated: input={input_tokens}, output={output_tokens}")
            else:
                # Grok models: use grok_client with streaming
                # grok-3-mini 是 reasoning 模型，需要更大的 max_tokens（reasoning + content）
                max_tokens = 16384 if "mini" in model else 4096
                stream = self.grok_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    stream_options={"include_usage": True},  # 请求返回 usage
                    max_tokens=max_tokens,
                    temperature=0.7  # 平衡创造性和一致性
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content

                        # 实时推送流式内容
                        await self.send("stream", {"content": content})
                    
                    # 从最后一个 chunk 获取 usage
                    if hasattr(chunk, 'usage') and chunk.usage:
                        input_tokens = getattr(chunk.usage, 'prompt_tokens', 0)
                        output_tokens = getattr(chunk.usage, 'completion_tokens', 0)
                    
                    await asyncio.sleep(0)  # 让出控制权
                
                # 如果没有获取到 usage，使用估算
                if input_tokens == 0:
                    input_tokens = len(prompt) // 4
                    print(f"[TOKEN] Estimated input_tokens from prompt length: {input_tokens}")
                if output_tokens == 0:
                    output_tokens = len(full_response) // 4
                    print(f"[TOKEN] Estimated output_tokens from response length: {output_tokens}")
                else:
                    print(f"[TOKEN] Got actual usage: input={input_tokens}, output={output_tokens}")
                    
        except Exception as e:
            full_response = f"[ERROR] {str(e)}"
            await self.send("error", {"message": str(e)})
        
        latency = time.time() - start_time
        return full_response, latency, input_tokens, output_tokens, cached_tokens
    
    def judge_response(self, task_prompt: str, response: str) -> dict:
        """GPT-5.2 评估 - 使用 responses API"""
        eval_prompt = f"""{JUDGE_PROMPT}

## Task:
{task_prompt[:2000]}{"..." if len(task_prompt) > 2000 else ""}

## Response:
{response[:6000]}{"..." if len(response) > 6000 else ""}"""

        try:
            # GPT-5.2 使用 responses API
            result = self.judge_client.responses.create(
                model=self.config.judge_model,
                input=eval_prompt,
                reasoning={"effort": "medium"}
            )
            
            content = result.output_text if hasattr(result, 'output_text') else str(result.output)
            print(f"[DEBUG] Judge raw response: {content[:500]}")
            
            # 使用正则提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*"completeness"[\s\S]*"overall"[\s\S]*\}', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group()
                print(f"[DEBUG] Extracted JSON: {json_str[:300]}")
                
                data = json.loads(json_str)
                
                # 解析新格式（支持嵌套和扁平两种格式）
                parsed = {}
                for key in ['completeness', 'accuracy', 'professionalism', 'clarity', 'actionability']:
                    if isinstance(data.get(key), dict):
                        parsed[key] = data[key].get('score', 0)
                        parsed[f'{key}_reason'] = data[key].get('reason', '')
                    else:
                        parsed[key] = data.get(key, 0)
                        parsed[f'{key}_reason'] = ''
                
                parsed['overall'] = data.get('overall', 0)
                parsed['summary'] = data.get('summary', '')
                parsed['strengths'] = data.get('strengths', '')
                parsed['weaknesses'] = data.get('weaknesses', '')
                
                return parsed
            else:
                print(f"[ERROR] No JSON found in response")
                return {"error": f"无法解析评分JSON: {content[:100]}"}
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON decode error: {e}")
            return {"error": f"JSON解析失败: {str(e)}"}
        except Exception as e:
            print(f"[ERROR] Judge error: {e}")
            return {"error": str(e)}
    
    async def run(self):
        """执行完整评测流程"""
        try:
            self.create_clients()
        except Exception as e:
            await self.send("error", {"message": f"API 客户端创建失败: {e}"})
            return
        
        # 筛选任务
        tasks = [t for t in GDPVAL_DATA if t['sector'] in self.config.sectors]
        selected_tasks = []
        for sector in self.config.sectors:
            sector_tasks = [t for t in tasks if t['sector'] == sector][:self.config.tasks_per_sector]
            selected_tasks.extend(sector_tasks)
        
        total_runs = len(selected_tasks) * len(self.config.models)
        
        await self.send("start", {
            "total": total_runs,
            "models": self.config.models,
            "sectors": self.config.sectors
        })
        
        # ============================================================
        # 阶段 1: 模型测试
        # ============================================================
        test_results = []
        current = 0
        
        for model in self.config.models:
            for task in selected_tasks:
                current += 1
                
                await self.send("phase1_progress", {
                    "current": current,
                    "total": total_runs,
                    "model": model,
                    "sector": task['sector'],
                    "occupation": task['occupation']
                })
                
                # 清空流式缓冲
                await self.send("stream_start", {
                    "model": model,
                    "task": task['occupation']
                })
                
                # 使用 enhanced_prompt（包含附件内容），回退到原始 prompt
                prompt_to_use = task.get('enhanced_prompt', task['prompt'])
                response, latency, input_tokens, output_tokens, cached_tokens = await self.run_grok_task(model, prompt_to_use)
                
                test_results.append({
                    'model': model,
                    'task': task,
                    'response': response,
                    'latency': latency,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'cached_tokens': cached_tokens
                })
                
                await self.send("phase1_complete", {
                    "current": current,
                    "latency": round(latency, 1),
                    "response_preview": response[:200]
                })
        
        # ============================================================
        # 阶段 2: AI 评估
        # ============================================================
        results = []
        
        await self.send("phase2_start", {"total": len(test_results)})
        
        for i, tr in enumerate(test_results):
            await self.send("phase2_progress", {
                "current": i + 1,
                "total": len(test_results),
                "model": tr['model'],
                "occupation": tr['task']['occupation']
            })
            
            # Judge 也使用 enhanced_prompt 进行评估（完整上下文）
            prompt_for_judge = tr['task'].get('enhanced_prompt', tr['task']['prompt'])
            eval_result = self.judge_response(prompt_for_judge, tr['response'])
            
            if 'error' not in eval_result:
                result = TaskResult(
                    model=tr['model'],
                    sector=tr['task']['sector'],
                    occupation=tr['task']['occupation'],
                    completeness=eval_result.get('completeness', 0),
                    accuracy=eval_result.get('accuracy', 0),
                    professionalism=eval_result.get('professionalism', 0),
                    clarity=eval_result.get('clarity', 0),
                    actionability=eval_result.get('actionability', 0),
                    overall=eval_result.get('overall', 0),
                    latency=round(tr['latency'], 1),
                    input_tokens=tr.get('input_tokens', 0),
                    output_tokens=tr.get('output_tokens', 0),
                    cached_tokens=tr.get('cached_tokens', 0),
                    response=tr['response'][:500],
                    judge_summary=eval_result.get('summary', ''),
                    judge_strengths=eval_result.get('strengths', ''),
                    judge_weaknesses=eval_result.get('weaknesses', '')
                )
                
                # 发送评分详情
                await self.send("phase2_result", {
                    "index": i,
                    "result": result.model_dump(),
                    "reasons": {
                        "completeness": eval_result.get('completeness_reason', ''),
                        "accuracy": eval_result.get('accuracy_reason', ''),
                        "professionalism": eval_result.get('professionalism_reason', ''),
                        "clarity": eval_result.get('clarity_reason', ''),
                        "actionability": eval_result.get('actionability_reason', '')
                    }
                })
            else:
                result = TaskResult(
                    model=tr['model'],
                    sector=tr['task']['sector'],
                    occupation=tr['task']['occupation'],
                    completeness=0, accuracy=0, professionalism=0,
                    clarity=0, actionability=0, overall=0,
                    latency=round(tr['latency'], 1),
                    input_tokens=tr.get('input_tokens', 0),
                    output_tokens=tr.get('output_tokens', 0),
                    cached_tokens=tr.get('cached_tokens', 0),
                    response=tr['response'][:500],
                    notes=f"❌ {eval_result.get('error', 'Unknown')[:50]}"
                )
                
                await self.send("phase2_error", {
                    "index": i,
                    "error": eval_result.get('error', 'Unknown')
                })
            
            results.append(result)
        
        # ============================================================
        # 阶段 3: 完成，进入人工复核
        # ============================================================
        await self.send("complete", {
            "total": len(results),
            "results": [r.model_dump() for r in results],
            "timestamp": datetime.now().isoformat()
        })


@app.websocket("/ws/benchmark")
async def websocket_benchmark(websocket: WebSocket):
    """WebSocket 评测端点"""
    await websocket.accept()
    
    try:
        # 等待配置
        data = await websocket.receive_json()
        config = BenchmarkConfig(**data)
        
        # 执行评测
        runner = BenchmarkRunner(websocket, config)
        await runner.run()
        
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
