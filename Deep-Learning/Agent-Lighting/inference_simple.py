import asyncio
from openai import AsyncOpenAI
import sys
import os

# Config
CHECKPOINT_PATH = os.environ.get(
    "CHECKPOINT_PATH",
    os.path.join(os.getcwd(), "checkpoints/AgentLightningTutorial/math_agent/global_step_1")
)
VLLM_URL = "http://localhost:8001/v1"

# Init client
client = AsyncOpenAI(base_url=VLLM_URL, api_key="EMPTY")

async def inference_math_question(question: str) -> str:
    try:
        response = await client.chat.completions.create(
            model=CHECKPOINT_PATH,
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
    print("🧮 Math Inference Test")
    print("="*60 + "\n")
    
    for i, question in enumerate(test_questions, 1):
        answer = await inference_math_question(question)
        print(f"{i}. Question: {question}")
        print(f"   Answer: {answer}\n")

if __name__ == "__main__":
    asyncio.run(main())
