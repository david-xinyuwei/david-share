"""
GDPVAL LLM-as-Judge Evaluation
使用 Azure GPT-5.2-chat 作为 Judge 评估 Grok 模型输出质量
"""

import json
import time
import os
from datetime import datetime
from openai import AzureOpenAI
import httpx

# ========== Azure GPT-5.2-chat (Judge) 配置 ==========
JUDGE_ENDPOINT = "https://your-aoai-endpoint.openai.azure.com/"
JUDGE_API_KEY = "YOUR_AZURE_OPENAI_KEY"
JUDGE_MODEL = "gpt-5.2-chat"
JUDGE_API_VERSION = "2025-04-01-preview"

# 创建 Judge 客户端 (使用 Responses API)
judge_client = AzureOpenAI(
    azure_endpoint=JUDGE_ENDPOINT,
    api_key=JUDGE_API_KEY,
    api_version=JUDGE_API_VERSION,
    http_client=httpx.Client(timeout=httpx.Timeout(300.0, connect=60.0))
)

# LLM-as-Judge 评分 prompt
JUDGE_SYSTEM_PROMPT = """You are an expert evaluator assessing AI model responses to professional work tasks.

For each task, you will receive:
1. The original task prompt (professional work request)
2. The AI model's response

Evaluate the response on the following criteria (each 1-10 scale):

1. **Completeness (1-10)**: Does the response address all aspects of the task? Are all required deliverables included?
2. **Accuracy (1-10)**: Is the information correct? Are calculations accurate? Are technical details right?
3. **Professionalism (1-10)**: Is the tone and format appropriate for the professional context?
4. **Clarity (1-10)**: Is the response well-organized, clear, and easy to understand?
5. **Actionability (1-10)**: Can the requester use this response directly? Is it practical and implementable?

Output your evaluation in the following JSON format:
{
    "completeness": <score>,
    "accuracy": <score>,
    "professionalism": <score>,
    "clarity": <score>,
    "actionability": <score>,
    "overall": <average of above>,
    "strengths": "<brief description of what was done well>",
    "weaknesses": "<brief description of areas for improvement>",
    "summary": "<one sentence overall assessment>"
}

Be fair, objective, and consistent in your evaluations. Consider the complexity and scope of each task."""


def evaluate_response(task_prompt: str, model_response: str, task_id: str = "") -> dict:
    """使用 GPT-5.2-chat 评估模型响应"""
    
    # 构建完整的评估 prompt（Responses API 使用单一 input 字符串）
    full_prompt = f"""{JUDGE_SYSTEM_PROMPT}

---

## Task Prompt:
{task_prompt[:3000]}{"..." if len(task_prompt) > 3000 else ""}

## Model Response:
{model_response[:8000]}{"..." if len(model_response) > 8000 else ""}

Please evaluate this response according to the criteria above. Output only the JSON evaluation."""

    try:
        # GPT-5 使用 Responses API (input 是字符串，不是 messages 列表)
        response = judge_client.responses.create(
            model=JUDGE_MODEL,
            input=full_prompt,
            reasoning={"effort": "medium"}
        )
        
        # 提取响应文本
        result_text = response.output_text if hasattr(response, 'output_text') else str(response.output)
        
        # 尝试解析 JSON
        # 查找 JSON 块
        import re
        json_match = re.search(r'\{[^{}]*"completeness"[^{}]*\}', result_text, re.DOTALL)
        if json_match:
            eval_result = json.loads(json_match.group())
        else:
            # 尝试直接解析
            eval_result = json.loads(result_text)
        
        eval_result["task_id"] = task_id
        eval_result["raw_judge_response"] = result_text[:500]
        return eval_result
        
    except json.JSONDecodeError as e:
        return {
            "task_id": task_id,
            "error": f"JSON parse error: {str(e)}",
            "raw_judge_response": result_text[:500] if 'result_text' in locals() else "N/A"
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "error": str(e)
        }


def load_grok_results(results_file: str) -> list:
    """加载 Grok 测试结果"""
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_tasks(tasks_file: str = "gdpval.json") -> dict:
    """加载任务数据，返回 task_id -> task 映射"""
    with open(tasks_file, 'r', encoding='utf-8') as f:
        tasks = json.load(f)
    return {t['task_id']: t for t in tasks}


def run_evaluation(results_file: str, max_evals: int = None):
    """运行评估"""
    
    print(f"\n{'='*60}")
    print("GDPVAL LLM-as-Judge Evaluation")
    print(f"Judge Model: {JUDGE_MODEL}")
    print(f"{'='*60}")
    
    # 加载数据
    grok_results = load_grok_results(results_file)
    tasks = load_tasks("gdpval.json")
    
    # 只评估成功的结果
    success_results = [r for r in grok_results if r['status'] == 'success' and r.get('response')]
    
    if max_evals:
        success_results = success_results[:max_evals]
    
    print(f"待评估结果数: {len(success_results)}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)
    
    all_evaluations = []
    
    for i, result in enumerate(success_results):
        task_id = result['task_id']
        model = result['model']
        task = tasks.get(task_id, {})
        
        print(f"\n[{i+1}/{len(success_results)}] 评估 {model} - {result['occupation'][:30]}...")
        
        eval_result = evaluate_response(
            task_prompt=task.get('prompt', ''),
            model_response=result['response'],
            task_id=task_id
        )
        
        eval_result['model'] = model
        eval_result['occupation'] = result['occupation']
        eval_result['sector'] = result['sector']
        eval_result['latency_seconds'] = result['latency_seconds']
        
        all_evaluations.append(eval_result)
        
        # 打印分数
        if 'overall' in eval_result:
            print(f"  ✓ Overall: {eval_result['overall']:.1f}/10")
            print(f"    Completeness: {eval_result.get('completeness', 'N/A')}, "
                  f"Accuracy: {eval_result.get('accuracy', 'N/A')}, "
                  f"Clarity: {eval_result.get('clarity', 'N/A')}")
        else:
            print(f"  ✗ Error: {eval_result.get('error', 'Unknown')[:50]}")
        
        # 避免速率限制
        time.sleep(2)
    
    # 保存评估结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"gdpval_evaluations_{timestamp}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_evaluations, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n{'='*60}")
    print(f"评估完成！结果已保存到: {output_file}")
    print(f"{'='*60}")
    
    # 打印汇总统计
    print_summary(all_evaluations)
    
    return all_evaluations


def print_summary(evaluations: list):
    """打印评估汇总"""
    
    print("\n【按模型汇总】")
    
    models = set(e['model'] for e in evaluations if 'model' in e)
    
    for model in sorted(models):
        model_evals = [e for e in evaluations if e.get('model') == model and 'overall' in e]
        if model_evals:
            avg_overall = sum(e['overall'] for e in model_evals) / len(model_evals)
            avg_completeness = sum(e.get('completeness', 0) for e in model_evals) / len(model_evals)
            avg_accuracy = sum(e.get('accuracy', 0) for e in model_evals) / len(model_evals)
            avg_clarity = sum(e.get('clarity', 0) for e in model_evals) / len(model_evals)
            
            print(f"\n  {model}:")
            print(f"    Overall:      {avg_overall:.2f}/10")
            print(f"    Completeness: {avg_completeness:.2f}/10")
            print(f"    Accuracy:     {avg_accuracy:.2f}/10")
            print(f"    Clarity:      {avg_clarity:.2f}/10")
            print(f"    Samples:      {len(model_evals)}")


def quick_eval(results_file: str = None, num_evals: int = 4):
    """快速评估 - 只评估几个结果"""
    
    # 找到最新的结果文件
    if not results_file:
        import glob
        files = glob.glob("gdpval_results_*.json")
        if files:
            results_file = max(files)
            print(f"使用最新结果文件: {results_file}")
        else:
            print("错误: 找不到 gdpval_results_*.json 文件")
            return
    
    return run_evaluation(results_file, max_evals=num_evals)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        # 完整评估
        results_file = sys.argv[2] if len(sys.argv) > 2 else None
        if not results_file:
            import glob
            files = glob.glob("gdpval_results_*.json")
            results_file = max(files) if files else None
        if results_file:
            run_evaluation(results_file)
        else:
            print("错误: 找不到结果文件")
    else:
        # 快速评估（默认4个）
        quick_eval()
