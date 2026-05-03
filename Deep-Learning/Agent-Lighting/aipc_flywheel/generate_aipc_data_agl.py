#!/usr/bin/env python3
"""
AIPC Domain Training Data Generator
====================================

Generate high-quality AIPC (AI PC) domain training data using teacher model (GPT-4o/5.2).

Features:
    - Domain-specific question generation
    - Multi-turn conversation support
    - Automatic quality filtering
    - ShareGPT format output

Usage:
    python generate_aipc_data_agl.py --output data/aipc_train.jsonl --num_samples 1000

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import random
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
# AIPC Domain Topics
# =============================================================================

AIPC_TOPICS = {
    "hardware": [
        "Intel Core Ultra 系列处理器的 NPU 架构",
        "AMD Ryzen AI 的 XDNA 技术",
        "Qualcomm Snapdragon X Elite 的性能特点",
        "AIPC 的 NPU vs GPU vs CPU 计算分工",
        "Intel AI Boost 引擎的工作原理",
        "AIPC 的散热设计挑战",
        "低功耗 AI 加速器的优势",
        "AIPC 内存带宽对 AI 性能的影响",
    ],
    "software": [
        "Windows Copilot Runtime 架构",
        "DirectML 和 ONNX Runtime 的关系",
        "Windows AI Studio 的使用方法",
        "AIPC 上的模型量化技术 (INT4/INT8)",
        "Windows ML API 的调用方式",
        "Olive 模型优化工具链",
        "AIPC 本地大模型部署方案",
        "Phi-3 系列模型在 AIPC 上的优化",
    ],
    "applications": [
        "AIPC 实时字幕和翻译功能",
        "Windows Studio Effects 的 AI 增强",
        "本地 Copilot 私有化部署",
        "AIPC 图像生成 (Stable Diffusion) 加速",
        "代码补全模型本地运行",
        "语音识别模型 (Whisper) 本地部署",
        "AIPC 视频会议 AI 背景虚化",
        "本地 RAG 应用实现",
    ],
    "optimization": [
        "AIPC 模型推理延迟优化",
        "内存占用优化技术",
        "批处理推理 vs 流式推理",
        "模型预热和缓存策略",
        "多模型并行调度",
        "功耗和性能平衡策略",
        "AIPC 应用的 UX 优化",
        "模型加载时间优化",
    ],
}

QUESTION_TEMPLATES = [
    "请详细介绍{topic}",
    "如何在 AIPC 上实现{topic}？请提供具体步骤",
    "{topic}的技术原理是什么？",
    "对比分析{topic}与传统方案的优劣",
    "在{topic}方面，有哪些最佳实践？",
    "请解释{topic}，并给出代码示例",
    "{topic}在实际应用中会遇到哪些挑战？",
    "如何优化{topic}的性能？",
]


# =============================================================================
# Data Generation Functions
# =============================================================================


# Azure OpenAI GPT-5.2 Configuration
AZURE_OPENAI_ENDPOINT = "https://<your-resource>.openai.azure.com/"
AZURE_OPENAI_API_KEY = "YOUR-API-KEY"
AZURE_OPENAI_API_VERSION = "2025-04-01-preview"


def create_azure_client() -> AzureOpenAI:
    """Create Azure OpenAI client for GPT-5.2 Responses API."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", AZURE_OPENAI_ENDPOINT)
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", AZURE_OPENAI_API_KEY)
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", AZURE_OPENAI_API_VERSION)
    
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
    )


def generate_question(topic: str) -> str:
    """Generate a question from a topic using template."""
    template = random.choice(QUESTION_TEMPLATES)
    return template.format(topic=topic)


def generate_response(
    client: AzureOpenAI,
    question: str,
    model: str = "gpt-5.2",
    temperature: float = 0.7,
) -> Optional[str]:
    """Generate response from teacher model using GPT-5.2 Responses API."""
    system_prompt = """你是 AIPC (AI PC) 领域的技术专家。请根据用户问题提供详细、准确、专业的回答。

回答要求：
1. 技术内容准确，不要编造不存在的产品或功能
2. 适当使用 Markdown 格式（标题、列表、代码块）
3. 如果涉及代码，使用 Python 或相关语言的正确语法
4. 回答长度适中，信息密度高
5. 使用中文回答，技术术语保留英文"""

    try:
        # GPT-5.2 uses Responses API instead of Chat Completions
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            reasoning={"effort": "medium", "summary": "auto"},
        )
        # Extract text from response output
        for item in response.output:
            if hasattr(item, 'content') and item.content:
                for content_item in item.content:
                    if hasattr(content_item, 'text'):
                        return content_item.text
        return None
    except Exception as e:
        logger.error(f"Failed to generate response: {e}")
        return None


def quality_filter(response: str, min_length: int = 200) -> bool:
    """Filter low-quality responses."""
    if not response:
        return False
    if len(response) < min_length:
        return False
    # Check for common error indicators
    error_indicators = ["抱歉", "无法回答", "不确定", "请提供更多"]
    if any(indicator in response[:100] for indicator in error_indicators):
        return False
    return True


def to_sharegpt_format(question: str, response: str) -> Dict:
    """Convert Q&A pair to ShareGPT format."""
    return {
        "conversations": [
            {"from": "human", "value": question},
            {"from": "gpt", "value": response},
        ]
    }


def generate_dataset(
    client: AzureOpenAI,
    num_samples: int,
    model: str = "gpt-5.2",
    output_path: Optional[str] = None,
) -> List[Dict]:
    """Generate complete training dataset."""
    dataset = []
    all_topics = []
    
    # Flatten all topics
    for category, topics in AIPC_TOPICS.items():
        all_topics.extend(topics)
    
    # Generate samples with progress bar
    pbar = tqdm(total=num_samples, desc="Generating samples")
    attempts = 0
    max_attempts = num_samples * 3  # Allow 3x attempts for failures
    
    while len(dataset) < num_samples and attempts < max_attempts:
        attempts += 1
        
        # Select random topic
        topic = random.choice(all_topics)
        question = generate_question(topic)
        
        # Generate response
        response = generate_response(client, question, model)
        
        # Quality filter
        if quality_filter(response):
            sample = to_sharegpt_format(question, response)
            dataset.append(sample)
            pbar.update(1)
            
            # Save incrementally
            if output_path and len(dataset) % 10 == 0:
                save_dataset(dataset, output_path)
        else:
            logger.debug(f"Filtered out low-quality response for: {question[:50]}...")
    
    pbar.close()
    
    if len(dataset) < num_samples:
        logger.warning(
            f"Only generated {len(dataset)}/{num_samples} samples after {attempts} attempts"
        )
    
    return dataset


def save_dataset(dataset: List[Dict], output_path: str) -> None:
    """Save dataset to JSONL file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in dataset:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    
    logger.info(f"Saved {len(dataset)} samples to {output_path}")


# =============================================================================
# Test Data Generation
# =============================================================================


def generate_test_data(
    client: AzureOpenAI,
    num_samples: int = 100,
    model: str = "gpt-5.2",
) -> List[Dict]:
    """Generate test dataset (questions only, no reference answers)."""
    test_data = []
    all_topics = []
    
    for category, topics in AIPC_TOPICS.items():
        all_topics.extend(topics)
    
    # Shuffle and take subset
    random.shuffle(all_topics)
    selected_topics = all_topics[:num_samples]
    
    for topic in tqdm(selected_topics, desc="Generating test questions"):
        question = generate_question(topic)
        test_data.append({
            "question": question,
            "topic": topic,
        })
    
    return test_data


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate AIPC domain training data using teacher model",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="data/aipc_train.jsonl",
        help="Output path for training data (JSONL format)",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=1000,
        help="Number of training samples to generate",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.2",
        help="Teacher model to use (gpt-5.2, gpt-5.1, gpt-4o)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature for generation",
    )
    parser.add_argument(
        "--generate_test",
        action="store_true",
        help="Also generate test dataset",
    )
    parser.add_argument(
        "--test_output",
        type=str,
        default="data/aipc_test.jsonl",
        help="Output path for test data",
    )
    parser.add_argument(
        "--test_samples",
        type=int,
        default=100,
        help="Number of test samples to generate",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    # Set random seed
    random.seed(args.seed)
    
    logger.info("=" * 60)
    logger.info("AIPC Domain Training Data Generator")
    logger.info("=" * 60)
    logger.info(f"Output: {args.output}")
    logger.info(f"Num samples: {args.num_samples}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Temperature: {args.temperature}")
    logger.info("=" * 60)
    
    # Create client
    client = create_azure_client()
    
    # Generate training data
    dataset = generate_dataset(
        client=client,
        num_samples=args.num_samples,
        model=args.model,
        output_path=args.output,
    )
    
    # Save final dataset
    save_dataset(dataset, args.output)
    logger.info(f"✅ Generated {len(dataset)} training samples")
    
    # Generate test data if requested
    if args.generate_test:
        test_data = generate_test_data(
            client=client,
            num_samples=args.test_samples,
            model=args.model,
        )
        
        test_output = Path(args.test_output)
        test_output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(test_output, "w", encoding="utf-8") as f:
            for sample in test_data:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        
        logger.info(f"✅ Generated {len(test_data)} test samples to {test_output}")
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
