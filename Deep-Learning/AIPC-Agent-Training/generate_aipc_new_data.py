#!/usr/bin/env python3
"""
Fresh Corpus Injector for AI PC Domain (DevOps Flywheel)
--------------------------------------------------------
Generates NEW, UNSEEN questions and answers for the AI PC domain.
Focuses on:
1. Advanced Scenarios (Local RAG, Stable Diffusion, Coding)
2. Comparison/Analysis (NPU vs GPU, X Elite vs M3)
3. Edge Cases (Battery life, Privacy, Offline capability)

Usage:
    python generate_aipc_new_data.py --num 500 --output new_aipc_data.jsonl
"""

import os
import json
import asyncio
import random
import argparse
import logging
from typing import List, Dict

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Azure OpenAI Configuration
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://YOUR-ENDPOINT.openai.azure.com/")
AZURE_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")

TOPICS = [
    "Local LLM Inference on NPU (Llama 3, Phi-3)",
    "Stable Diffusion generation speed on Core Ultra vs Snapdragon",
    "Battery life impact of NPU offloading",
    "Privacy benefits of local AI processing",
    "Windows Studio Effects implementation",
    "Copilot+ PC hardware requirements",
    "Qualcomm Hexagon NPU architecture",
    "Intel AI Boost NPU architecture",
    "AMD Ryzen AI capabilities",
    "Hybrid AI (Cloud + Edge) workflows"
]

SYSTEM_PROMPT = """
You are an expert AI PC Technical Evangelist.
Generate diverse, high-quality Q&A pairs about AI PCs.
The questions should be technical, specific, and cover new scenarios.
Do NOT generate simple "What is AI PC" questions (we have enough of those).
Focus on: Performance, Architecture, Specific Apps, Troubleshooting, Comparisons.

Format: JSON object with "prompt" and "completion" fields.
"""

async def generate_batch(client, batch_size: int, topic: str) -> List[Dict]:
    prompt = f"""
    Generate {batch_size} distinct Q&A pairs about: {topic}.
    
    Requirements:
    1. Questions must be in Chinese.
    2. Answers must be detailed, accurate, and professional.
    3. Avoid mentioning "Alibaba" or "Aliyun" completely.
    4. Ensure "Intel Core Ultra" is associated with Client/Laptop, NOT Server.
    5. Ensure "Snapdragon X Elite" is associated with PC Processor, NOT just Modem.
    
    Output format: A JSON list of objects, each having "prompt" and "completion".
    Example:
    [
        {{"prompt": "如何在 Core Ultra 上运行本地 Llama 3？", "completion": "..."}},
        ...
    ]
    """
    
    try:
        response = await client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        # Handle cases where the model might wrap the list in a key
        if isinstance(data, dict):
            for key in data:
                if isinstance(data[key], list):
                    return data[key]
            return [] # Fallback
        return data
    except Exception as e:
        logger.error(f"Generation failed for topic {topic}: {e}")
        return []

async def main(num_questions: int, output_file: str, local_test: bool = False):
    if local_test:
        logger.info("Running in Local Test Mode (Mock Data)")
        mock_data = [
            {"prompt": "NPU 对续航有什么帮助？", "completion": "NPU 专为低功耗 AI 任务设计..."},
            {"prompt": "如何在 NPU 上跑量化模型？", "completion": "使用 OpenVINO 或 ONNX Runtime..."}
        ]
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in mock_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        logger.info(f"Saved mock data to {output_file}")
        return

    if not AZURE_KEY:
        logger.error("AZURE_OPENAI_API_KEY not set. Cannot generate data.")
        return

    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_KEY,
        api_version=AZURE_API_VERSION
    )

    logger.info(f"Generating {num_questions} new questions...")
    all_data = []
    
    # Calculate batches
    batch_size = 5
    num_batches = (num_questions + batch_size - 1) // batch_size
    
    tasks = []
    for i in range(num_batches):
        topic = random.choice(TOPICS)
        tasks.append(generate_batch(client, batch_size, topic))
    
    results = await asyncio.gather(*tasks)
    
    for batch in results:
        all_data.extend(batch)
        
    # Trim to exact number
    all_data = all_data[:num_questions]
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in all_data:
            # Convert to SFT/DPO format if needed, here we keep simple prompt/completion
            # For DPO mixing, we might need to format it as chosen/rejected (self-play style)
            # Or just keep it as SFT data for the "Anchor" part if we mix SFT loss.
            # But for DPO trainer, we need pairs.
            # Strategy: Use these as "Chosen", and generate a "Rejected" (e.g. by a weaker model or just empty?)
            # Actually, for "New Injection", it's best used as SFT data (Supervised Fine-Tuning) mixed in.
            # But if we are doing DPO, we need pairs.
            # Hack: Use the same response for Chosen, and a slightly degraded version for Rejected?
            # Or better: Just use this for SFT stage?
            # Wait, we are doing "DPO Hotfix".
            # If we want to inject new knowledge during DPO, we need (Prompt, Good, Bad).
            # We can generate a "Bad" response using a simple prompt to GPT-3.5 or just noise?
            # Let's stick to generating just the good data first. We can construct pairs later.
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    logger.info(f"Successfully generated {len(all_data)} items to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num", type=int, default=500)
    parser.add_argument("--output", type=str, default="new_aipc_data.jsonl")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    asyncio.run(main(args.num, args.output, args.test))
