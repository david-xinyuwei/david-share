#!/usr/bin/env python3
"""
Agent Lightning Enhanced LLM Judge
Uses AGL's tracing and rollout capabilities for answer evaluation
"""
import pandas as pd
import sys
from tqdm import tqdm
import os
import json
import asyncio
from typing import TypedDict
from opentelemetry import trace

import agentlightning as agl


# Configuration - Use environment variables
JUDGE_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")


class JudgeTask(TypedDict):
    """Structure for judgment task"""
    index: int
    question: str
    ground_truth: str
    model_response: str
    # Output fields
    correct: bool
    reason: str


# Global storage for results (workaround for TypedDict immutability)
_results_storage: dict[int, dict] = {}


@agl.rollout
async def judge_answer_agl(task: JudgeTask, llm: agl.LLM) -> float:
    """
    Judge a single answer using Agent Lightning's tracing
    
    Returns:
        float: 1.0 if correct, 0.0 if incorrect (as reward signal)
    """
    from openai import AsyncAzureOpenAI
    
    client = AsyncAzureOpenAI(
        azure_endpoint=llm.endpoint or ENDPOINT,
        api_key=llm.api_key or API_KEY,
        api_version=API_VERSION,
    )
    
    prompt = f"""You are a math judge. Compare the model's response to the ground truth.

Question: {task['question']}
Ground Truth: {task['ground_truth']}
Model Response: {task['model_response']}

Does the model's response match the ground truth? 
Focus on the final numeric value or expression.
Ignore minor formatting differences.

Return a JSON object:
{{
    "correct": true/false,
    "reason": "explanation"
}}"""

    # Get tracer for manual span creation
    tracer = trace.get_tracer("llm_judge")
    
    try:
        with tracer.start_as_current_span("judge-llm-call") as span:
            span.set_attribute("llm.model", JUDGE_MODEL)
            span.set_attribute("task.index", task['index'])
            span.set_attribute("question.length", len(task['question']))
            
            response = await client.chat.completions.create(
                model=llm.model or JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            # Record token usage
            if response.usage:
                span.set_attribute("llm.usage.total_tokens", response.usage.total_tokens)
            
            result_json = response.choices[0].message.content
            
            # Parse result
            try:
                parsed = json.loads(result_json)
                correct = parsed.get("correct", False)
                reason = parsed.get("reason", "")
                # Store results in global storage
                _results_storage[task['index']] = {
                    'correct': correct,
                    'reason': reason
                }
            except json.JSONDecodeError:
                _results_storage[task['index']] = {
                    'correct': False,
                    'reason': "JSON Parse Error"
                }
            
            # Emit reward based on correctness (for tracking purposes)
            reward = 1.0 if _results_storage[task['index']]['correct'] else 0.0
            agl.emit_reward(reward)
            
            span.set_attribute("judgment.correct", _results_storage[task['index']]['correct'])
            
            return reward
            
    except Exception as e:
        _results_storage[task['index']] = {
            'correct': False,
            'reason': f"Error: {str(e)}"
        }
        agl.emit_reward(0.0)
        return 0.0


async def run_judgments(tasks: list[JudgeTask], llm_resource: agl.LLM) -> list[JudgeTask]:
    """Run all judgment tasks with AGL tracing"""
    
    # Initialize AGL components
    store = agl.InMemoryLightningStore()
    tracer = agl.OtelTracer()
    runner = agl.LitAgentRunner(tracer=tracer)
    
    with runner.run_context(agent=judge_answer_agl, store=store):
        for task in tqdm(tasks, desc="⚖️ Judging with AGL"):
            try:
                await runner.step(
                    input=task,
                    resources={"llm": llm_resource}
                )
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"⚠️ Task {task['index']} failed: {e}")
                task['correct'] = False
                task['reason'] = f"Runner Error: {str(e)}"
    
    return tasks


def main():
    """Main function with AGL integration"""
    print("=" * 60)
    print("⚖️ Agent Lightning Enhanced LLM Judge")
    print("=" * 60 + "\n")
    
    if len(sys.argv) < 3:
        print("Usage: python judge_with_llm_agl.py <input_parquet> <output_parquet>")
        print("\nExample:")
        print("  python judge_with_llm_agl.py eval_results.parquet judged_results.parquet")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not API_KEY or not ENDPOINT:
        print("❌ Error: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set.")
        print("\nSet environment variables:")
        print("  export AZURE_OPENAI_API_KEY=your-key")
        print("  export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
        return

    # Setup AGL logging
    agl.logging.setup(files="judge_execution.log", level="INFO")
    
    print("✨ Agent Lightning Features:")
    print("  1. Auto-trace all LLM judge calls")
    print("  2. Record judgment decisions as rewards")
    print("  3. OpenTelemetry integration for observability")
    print()
    
    # Load data
    df = pd.read_parquet(input_file)
    print(f"📂 Loaded {len(df)} samples from {input_file}\n")
    
    # Create judgment tasks
    tasks: list[JudgeTask] = []
    for index, row in df.iterrows():
        ground_truth = row.get('answer') or row.get('ground_truth') or row.get('solution') or "N/A"
        
        task = JudgeTask(
            index=int(index),
            question=str(row['question']),
            ground_truth=str(ground_truth),
            model_response=str(row.get('response', '')),
            correct=False,
            reason=""
        )
        tasks.append(task)
    
    # Configure LLM resource
    llm_resource = agl.LLM(
        endpoint=ENDPOINT,
        model=JUDGE_MODEL,
        api_key=API_KEY,
    )
    
    # Run async judgments
    completed_tasks = asyncio.run(run_judgments(tasks, llm_resource))
    
    # Update DataFrame with results from global storage
    df['llm_correct'] = [_results_storage.get(t['index'], {}).get('correct', False) 
                         for t in completed_tasks]
    df['llm_reason'] = [_results_storage.get(t['index'], {}).get('reason', '') 
                        for t in completed_tasks]
    
    # Calculate accuracy
    correct_count = sum(1 for t in completed_tasks 
                        if _results_storage.get(t['index'], {}).get('correct', False))
    accuracy = correct_count / len(completed_tasks)
    
    # Save results
    df.to_parquet(output_file, index=False)
    
    print("\n" + "=" * 60)
    print("✅ Judgment Complete!")
    print("=" * 60)
    print(f"\n📊 Results:")
    print(f"   Total samples: {len(completed_tasks)}")
    print(f"   Correct: {correct_count}")
    print(f"   Incorrect: {len(completed_tasks) - correct_count}")
    print(f"   Accuracy: {accuracy:.1%}")
    print(f"\n💾 Saved to: {output_file}")
    print(f"📝 Logs saved to: judge_execution.log")


if __name__ == "__main__":
    main()
