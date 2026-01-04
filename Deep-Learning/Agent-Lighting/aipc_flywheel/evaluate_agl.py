#!/usr/bin/env python3
"""
AIPC Model Evaluation Script
============================

Evaluate trained AIPC model using LLM Judge (GPT-4o/5.2).

Features:
    - Batch inference on test dataset
    - LLM-based quality assessment
    - Multi-dimensional scoring (Accuracy, Completeness, Relevance)
    - Detailed failure analysis
    - Export failed cases for feedback training

Usage:
    python evaluate_agl.py --model checkpoints/aipc_grpo_v1 --output results/eval_v1.json

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from openai import AzureOpenAI
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# LLM Judge Prompts
# =============================================================================

JUDGE_SYSTEM_PROMPT = """你是一个专业的 AI 评估专家，负责评估 AIPC (AI PC) 领域技术回答的质量。

评估维度：
1. **准确性 (Accuracy)**: 技术信息是否正确，有无事实错误或虚构内容
2. **完整性 (Completeness)**: 是否充分回答了问题，覆盖了关键点
3. **相关性 (Relevance)**: 回答是否紧扣问题，有无跑题

评分标准 (1-10分):
- 9-10: 优秀 - 专业级回答，可直接用于技术文档
- 7-8: 良好 - 基本正确，有小瑕疵但不影响理解
- 5-6: 及格 - 部分正确，有明显遗漏或小错误
- 3-4: 较差 - 错误较多或严重不完整
- 1-2: 很差 - 大量错误或完全跑题

请以 JSON 格式返回评估结果：
{
    "accuracy": <1-10>,
    "completeness": <1-10>,
    "relevance": <1-10>,
    "overall": <1-10>,
    "passed": <true/false>,
    "issues": ["问题1", "问题2", ...],
    "suggestions": "改进建议"
}

注意：overall >= 7 视为通过 (passed=true)"""

JUDGE_USER_TEMPLATE = """请评估以下 AIPC 技术问答的质量：

## 问题
{question}

## 模型回答
{response}

请按照评估标准给出评分和分析。"""


# =============================================================================
# Model Inference
# =============================================================================


def load_model(model_path: str, device: str = "auto"):
    """Load model and tokenizer for inference."""
    logger.info(f"Loading model from {model_path}")
    
    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="left",
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map=device,
        attn_implementation="flash_attention_2",
    )
    
    model.eval()
    
    return model, tokenizer


def generate_response(
    model,
    tokenizer,
    question: str,
    max_new_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    """Generate response from model."""
    messages = [{"role": "user", "content": question}]
    
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            pad_token_id=tokenizer.pad_token_id,
        )
    
    response = tokenizer.decode(
        outputs[0][inputs.input_ids.shape[1]:],
        skip_special_tokens=True,
    )
    
    return response.strip()


# =============================================================================
# LLM Judge
# =============================================================================


# Azure OpenAI GPT-5.2 Configuration
AZURE_OPENAI_ENDPOINT = "https://YOUR-RESOURCE.openai.azure.com/"
AZURE_OPENAI_API_KEY = "YOUR-API-KEY"
AZURE_OPENAI_API_VERSION = "2025-04-01-preview"


def create_judge_client() -> AzureOpenAI:
    """Create Azure OpenAI client for GPT-5.2 Responses API."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", AZURE_OPENAI_ENDPOINT)
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", AZURE_OPENAI_API_KEY)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", AZURE_OPENAI_API_VERSION)
    
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def judge_response(
    client: AzureOpenAI,
    question: str,
    response: str,
    judge_model: str = "gpt-5.2",
) -> Dict:
    """Judge a single response using GPT-5.2 Responses API."""
    user_prompt = JUDGE_USER_TEMPLATE.format(
        question=question,
        response=response,
    )
    
    try:
        # GPT-5.2 uses Responses API
        completion = client.responses.create(
            model=judge_model,
            input=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            reasoning={"effort": "low", "summary": "auto"},
            text={"format": {"type": "json_object"}},
        )
        
        # Extract JSON from response output
        result_text = None
        for item in completion.output:
            if hasattr(item, 'content') and item.content:
                for content_item in item.content:
                    if hasattr(content_item, 'text'):
                        result_text = content_item.text
                        break
        
        if not result_text:
            raise ValueError("No text in response")
        
        result = json.loads(result_text)
        
        # Ensure required fields
        result.setdefault("accuracy", 5)
        result.setdefault("completeness", 5)
        result.setdefault("relevance", 5)
        result.setdefault("overall", 5)
        result.setdefault("passed", result["overall"] >= 7)
        result.setdefault("issues", [])
        result.setdefault("suggestions", "")
        
        return result
        
    except Exception as e:
        logger.error(f"Judge error: {e}")
        return {
            "accuracy": 0,
            "completeness": 0,
            "relevance": 0,
            "overall": 0,
            "passed": False,
            "issues": [f"Judge error: {str(e)}"],
            "suggestions": "",
            "error": True,
        }


# =============================================================================
# Evaluation Pipeline
# =============================================================================


def load_test_data(test_path: str) -> List[Dict]:
    """Load test data from JSONL file."""
    test_data = []
    
    with open(test_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                test_data.append(sample)
    
    logger.info(f"Loaded {len(test_data)} test samples from {test_path}")
    return test_data


def run_evaluation(
    model,
    tokenizer,
    judge_client: AzureOpenAI,
    test_data: List[Dict],
    output_dir: str,
    judge_model: str = "gpt-5.2",
    max_new_tokens: int = 1024,
) -> Dict:
    """Run full evaluation pipeline."""
    results = []
    failed_cases = []
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Running evaluation on {len(test_data)} samples")
    
    for sample in tqdm(test_data, desc="Evaluating"):
        question = sample.get("question", sample.get("conversations", [{}])[0].get("value", ""))
        topic = sample.get("topic", "unknown")
        
        # Generate response
        response = generate_response(model, tokenizer, question, max_new_tokens)
        
        # Judge response
        judgment = judge_response(judge_client, question, response, judge_model)
        
        result = {
            "question": question,
            "topic": topic,
            "response": response,
            "judgment": judgment,
        }
        results.append(result)
        
        if not judgment["passed"]:
            failed_cases.append(result)
    
    # Compute statistics
    total = len(results)
    passed = sum(1 for r in results if r["judgment"]["passed"])
    pass_rate = passed / total if total > 0 else 0
    
    avg_accuracy = sum(r["judgment"]["accuracy"] for r in results) / total if total > 0 else 0
    avg_completeness = sum(r["judgment"]["completeness"] for r in results) / total if total > 0 else 0
    avg_relevance = sum(r["judgment"]["relevance"] for r in results) / total if total > 0 else 0
    avg_overall = sum(r["judgment"]["overall"] for r in results) / total if total > 0 else 0
    
    stats = {
        "total_samples": total,
        "passed_samples": passed,
        "failed_samples": total - passed,
        "pass_rate": pass_rate,
        "average_scores": {
            "accuracy": avg_accuracy,
            "completeness": avg_completeness,
            "relevance": avg_relevance,
            "overall": avg_overall,
        },
        "evaluation_time": datetime.now().isoformat(),
        "judge_model": judge_model,
    }
    
    # Save results
    eval_result = {
        "stats": stats,
        "results": results,
    }
    
    eval_path = output_dir / "eval_result.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_result, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved evaluation results to {eval_path}")
    
    # Save failed cases for feedback training
    if failed_cases:
        failed_path = output_dir / "failed_cases.jsonl"
        with open(failed_path, "w", encoding="utf-8") as f:
            for case in failed_cases:
                f.write(json.dumps(case, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(failed_cases)} failed cases to {failed_path}")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Evaluation Summary")
    logger.info("=" * 60)
    logger.info(f"Total samples: {total}")
    logger.info(f"Passed: {passed} ({pass_rate*100:.1f}%)")
    logger.info(f"Failed: {total - passed}")
    logger.info("-" * 60)
    logger.info("Average Scores:")
    logger.info(f"  Accuracy: {avg_accuracy:.2f}/10")
    logger.info(f"  Completeness: {avg_completeness:.2f}/10")
    logger.info(f"  Relevance: {avg_relevance:.2f}/10")
    logger.info(f"  Overall: {avg_overall:.2f}/10")
    logger.info("=" * 60)
    
    return stats


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AIPC Model Evaluation with LLM Judge",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to model checkpoint to evaluate",
    )
    parser.add_argument(
        "--test_data",
        type=str,
        default="data/aipc_test.jsonl",
        help="Path to test data (JSONL)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results",
        help="Output directory for evaluation results",
    )
    parser.add_argument(
        "--judge_model",
        type=str,
        default="gpt-5.2",
        help="LLM model to use as judge (gpt-5.2, gpt-5.1)",
    )
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=1024,
        help="Maximum tokens to generate",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device to run model on",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("AIPC Model Evaluation")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Test data: {args.test_data}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Judge model: {args.judge_model}")
    logger.info("=" * 60)
    
    # Load model
    model, tokenizer = load_model(args.model, args.device)
    
    # Load test data
    test_data = load_test_data(args.test_data)
    
    # Create judge client
    judge_client = create_judge_client()
    
    # Run evaluation
    stats = run_evaluation(
        model=model,
        tokenizer=tokenizer,
        judge_client=judge_client,
        test_data=test_data,
        output_dir=args.output,
        judge_model=args.judge_model,
        max_new_tokens=args.max_new_tokens,
    )
    
    # Exit with appropriate code
    if stats["pass_rate"] < 0.7:
        logger.warning("Pass rate below 70%, consider running feedback training")
        sys.exit(1)
    
    logger.info("✅ Evaluation completed successfully!")


if __name__ == "__main__":
    main()
