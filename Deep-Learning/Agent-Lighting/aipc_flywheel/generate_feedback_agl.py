#!/usr/bin/env python3
"""
AIPC Feedback Data Generator
============================

Generate correction data from failed evaluation cases.
Uses teacher model (GPT-4o/5.2) to create improved responses.

Features:
    - Load failed cases from evaluation
    - Generate high-quality corrections via teacher model
    - Create positive/negative pairs for preference learning
    - Export in format suitable for feedback training

Usage:
    python generate_feedback_agl.py --failed results/failed_cases.jsonl --output data/feedback_v1.jsonl

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from openai import AzureOpenAI
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Prompts
# =============================================================================

CORRECTION_SYSTEM_PROMPT = """你是 AIPC (AI PC) 领域的技术专家。给定一个技术问题和一个质量较差的回答，你需要生成一个高质量的改进版回答。

改进要求：
1. **准确性**: 修正所有技术错误和虚构内容
2. **完整性**: 覆盖问题的所有关键点
3. **相关性**: 紧扣问题主题，不跑题
4. **结构性**: 使用清晰的 Markdown 格式（标题、列表、代码块）
5. **专业性**: 使用准确的技术术语，中英文混用时技术词保留英文

原回答的问题：
{issues}

请生成改进后的回答，直接给出内容，不要任何前言或解释。"""

CORRECTION_USER_TEMPLATE = """## 问题
{question}

## 原回答（质量较差）
{original_response}

## 改进建议
{suggestions}

请生成改进后的高质量回答："""


# =============================================================================
# Feedback Generation
# =============================================================================


# Azure OpenAI GPT-5.2 Configuration
AZURE_OPENAI_ENDPOINT = "https://YOUR-RESOURCE.openai.azure.com/"
AZURE_OPENAI_API_KEY = "YOUR-API-KEY"
AZURE_OPENAI_API_VERSION = "2025-04-01-preview"


def create_client() -> AzureOpenAI:
    """Create Azure OpenAI client for GPT-5.2 Responses API."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", AZURE_OPENAI_ENDPOINT)
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", AZURE_OPENAI_API_KEY)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", AZURE_OPENAI_API_VERSION)
    
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def load_failed_cases(failed_path: str) -> List[Dict]:
    """Load failed cases from evaluation."""
    cases = []
    
    with open(failed_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    
    logger.info(f"Loaded {len(cases)} failed cases from {failed_path}")
    return cases


def generate_correction(
    client: AzureOpenAI,
    question: str,
    original_response: str,
    issues: List[str],
    suggestions: str,
    model: str = "gpt-5.2",
) -> Optional[str]:
    """Generate corrected response using GPT-5.2 Responses API."""
    
    issues_text = "\n".join(f"- {issue}" for issue in issues) if issues else "无具体问题列表"
    
    system_prompt = CORRECTION_SYSTEM_PROMPT.format(issues=issues_text)
    user_prompt = CORRECTION_USER_TEMPLATE.format(
        question=question,
        original_response=original_response,
        suggestions=suggestions or "请提供更准确、完整、结构清晰的回答",
    )
    
    try:
        # GPT-5.2 uses Responses API
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            reasoning={"effort": "medium", "summary": "auto"},
        )
        
        # Extract text from response output
        for item in response.output:
            if hasattr(item, 'content') and item.content:
                for content_item in item.content:
                    if hasattr(content_item, 'text'):
                        return content_item.text.strip()
        return None
    except Exception as e:
        logger.error(f"Failed to generate correction: {e}")
        return None


def generate_feedback_data(
    client: AzureOpenAI,
    failed_cases: List[Dict],
    model: str = "gpt-5.2",
) -> List[Dict]:
    """Generate feedback training data from failed cases."""
    feedback_data = []
    
    for case in tqdm(failed_cases, desc="Generating corrections"):
        question = case["question"]
        original_response = case["response"]
        judgment = case["judgment"]
        
        issues = judgment.get("issues", [])
        suggestions = judgment.get("suggestions", "")
        
        # Generate improved response
        corrected_response = generate_correction(
            client=client,
            question=question,
            original_response=original_response,
            issues=issues,
            suggestions=suggestions,
            model=model,
        )
        
        if corrected_response:
            # Create feedback sample
            feedback_sample = {
                "question": question,
                "positive_response": corrected_response,  # Good response (from teacher)
                "negative_response": original_response,   # Bad response (from model)
                "issues": issues,
                "original_scores": {
                    "accuracy": judgment.get("accuracy", 0),
                    "completeness": judgment.get("completeness", 0),
                    "relevance": judgment.get("relevance", 0),
                    "overall": judgment.get("overall", 0),
                },
            }
            feedback_data.append(feedback_sample)
        else:
            logger.warning(f"Failed to generate correction for: {question[:50]}...")
    
    logger.info(f"Generated {len(feedback_data)} feedback samples")
    return feedback_data


def save_feedback_data(
    feedback_data: List[Dict],
    output_path: str,
    format: str = "preference",
) -> None:
    """Save feedback data in specified format."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in feedback_data:
            if format == "preference":
                # Format for GRPO preference learning
                output_sample = {
                    "prompt": sample["question"],
                    "chosen": sample["positive_response"],
                    "rejected": sample["negative_response"],
                    "metadata": {
                        "issues": sample["issues"],
                        "original_scores": sample["original_scores"],
                    },
                }
            elif format == "sharegpt":
                # Format for continued SFT
                output_sample = {
                    "conversations": [
                        {"from": "human", "value": sample["question"]},
                        {"from": "gpt", "value": sample["positive_response"]},
                    ],
                }
            else:
                output_sample = sample
            
            f.write(json.dumps(output_sample, ensure_ascii=False) + "\n")
    
    logger.info(f"Saved {len(feedback_data)} samples to {output_path}")


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate feedback training data from failed cases",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--failed",
        type=str,
        required=True,
        help="Path to failed cases file (JSONL from evaluation)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/feedback_v1.jsonl",
        help="Output path for feedback data",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.2",
        help="Teacher model for generating corrections (gpt-5.2, gpt-5.1)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["preference", "sharegpt", "raw"],
        default="preference",
        help="Output format (preference for GRPO, sharegpt for SFT)",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("AIPC Feedback Data Generator")
    logger.info("=" * 60)
    logger.info(f"Failed cases: {args.failed}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Teacher model: {args.model}")
    logger.info(f"Format: {args.format}")
    logger.info("=" * 60)
    
    # Load failed cases
    failed_cases = load_failed_cases(args.failed)
    
    if not failed_cases:
        logger.info("No failed cases to process. Exiting.")
        return
    
    # Create client
    client = create_client()
    
    # Generate feedback data
    feedback_data = generate_feedback_data(
        client=client,
        failed_cases=failed_cases,
        model=args.model,
    )
    
    # Save feedback data
    save_feedback_data(
        feedback_data=feedback_data,
        output_path=args.output,
        format=args.format,
    )
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
