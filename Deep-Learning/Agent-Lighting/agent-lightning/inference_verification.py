import asyncio
from openai import AsyncOpenAI
import sys

import os

# 配置
# 指向转换后的模型路径
MODEL_PATH = os.environ.get(
    "MODEL_PATH",
    os.path.join(os.getcwd(), "checkpoints/AgentLightningTutorial/math_agent_0.5b_3epochs_verified/global_step_360/actor/huggingface_converted")
)
VLLM_URL = os.environ.get("VLLM_URL", "http://127.0.0.1:8000/v1")  # 使用默认端口 8000
API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")

# 初始化客户端
client = AsyncOpenAI(base_url=VLLM_URL, api_key=API_KEY)

async def inference_math_question(question: str) -> str:
    """使用训练好的模型回答数学问题"""
    try:
        response = await client.chat.completions.create(
            model=MODEL_PATH,
            messages=[
                {"role": "system", "content": "You are a math assistant. Output ONLY the final number."},
                {"role": "user", "content": question}
            ],
            temperature=0.1,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

async def main():
    test_questions = [
        "Calculate 25 * 4 + 10",
        "What is 15% of 200?",
        "Solve 3x = 12",
        "100 divided by 5 plus 8",
        "Square root of 144",
        "Calculate 50 * 2 - 10",
        "What is 20% of 500?"
    ]

    print("\n" + "="*60)
    print("🧮 数学问题推理验证 (Checkpoint 360)")
    print("="*60 + "\n")

    for i, question in enumerate(test_questions, 1):
        answer = await inference_math_question(question)
        print(f"{i}. 问题: {question}")
        print(f"   回答: {answer}\n")

if __name__ == "__main__":
    asyncio.run(main())
