#!/usr/bin/env python3
"""
Agent Lightning + GPT-5 Math Data Generator
Enhanced Version: Leveraging Agent Lightning's Tracing and Parallel Capabilities
"""
import asyncio
import json
import random
import re
import os
from pathlib import Path
from typing import TypedDict
from opentelemetry import trace

import pandas as pd
import agentlightning as agl


# Azure OpenAI Configuration
# Please set these environment variables before running
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "your-key-here")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

# Math Problem Types
MATH_TYPES = [
    "basic arithmetic (addition, subtraction, multiplication, division)",
    "percentage calculations",
    "simple algebraic equations",
    "geometry (area, perimeter, volume)",
    "probability and statistics",
    "number sequences and patterns",
    "word problems with money",
    "time and distance calculations",
    "fractions and decimals",
    "square roots and powers"
]


class GenerationTask(TypedDict):
    """Structure for data generation task"""
    batch_id: int
    batch_size: int
    math_types: list[str]
    # To store generated data
    generated_data: list[dict]


# ============= Agent Lightning Version: Using @agl.rollout =============
@agl.rollout
async def gpt5_data_generator(task: GenerationTask, llm: agl.LLM) -> float:
    """
    Generate a batch of math problems using Agent Lightning's Agent
    
    Returns:
        float: Success rate (returned as reward to the framework)
    """
    # Use the LLM endpoint injected by Agent Lightning
    # Tracer will automatically track all calls from this AsyncOpenAI client
    from openai import AsyncAzureOpenAI
    
    client = AsyncAzureOpenAI(
        azure_endpoint=llm.endpoint or AZURE_OPENAI_ENDPOINT,
        api_key=llm.api_key or AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    
    batch_id = task['batch_id']
    batch_size = task['batch_size']
    types_str = ", ".join(task['math_types'])
    
    # Initialize result list
    if 'generated_data' not in task:
        task['generated_data'] = []
    
    # Get Tracer
    tracer = trace.get_tracer("gpt5_data_generator")

    # Build prompt
    prompt = f"""Generate {batch_size} diverse math problems focusing on: {types_str}.

Requirements:
1. Each problem should be clear and solvable
2. Difficulty range: elementary to middle school level
3. Answer must be a single numeric value (integer or decimal)
4. Include a mix of direct calculation and word problems

Return ONLY a JSON array with this exact format:
[
  {{"question": "Calculate 15 + 27", "answer": "42"}},
  {{"question": "What is 20% of 150?", "answer": "30"}},
  ...
]

Generate exactly {batch_size} problems now."""
    
    try:
        # Call GPT-5
        # Manually create Span to demonstrate Agent Lightning's tracing capability
        with tracer.start_as_current_span("gpt-5.1-chat-completion") as span:
            span.set_attribute("llm.model", "gpt-5.1-preview")
            span.set_attribute("batch.id", batch_id)
            
            response = await client.chat.completions.create(
                model=llm.model or AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a math teacher creating practice problems."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
            )
            
            # Record Token usage
            if response.usage:
                span.set_attribute("llm.usage.total_tokens", response.usage.total_tokens)
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content
        
        # Parse JSON
        batch_data = json.loads(json_str)
        
        # Validate and clean data
        valid_batch = []
        for item in batch_data:
            if "question" in item and "answer" in item:
                answer = str(item["answer"]).strip()
                numbers = re.findall(r'-?\d+\.?\d*', answer)
                if numbers:
                    item["answer"] = numbers[0]
                    item["batch_id"] = batch_id  # Add batch ID
                    valid_batch.append(item)
        
        # Save data to task object (pass by reference)
        task['generated_data'].extend(valid_batch)
        
        # ✅ Record data quality
        success_rate = len(valid_batch) / batch_size
        agl.emit_reward(success_rate)  # Use reward to record success rate
        
        print(f"✅ Batch {batch_id}: Generated {len(valid_batch)}/{batch_size} valid samples (Success Rate: {success_rate:.1%})")
        
        return success_rate
        
    except Exception as e:
        print(f"⚠️ Batch {batch_id} failed: {e}")
        agl.emit_reward(0.0)  # Reward is 0 for failed batch
        return 0.0


def create_generation_tasks(num_questions: int, batch_size: int) -> list[GenerationTask]:
    """Create data generation tasks"""
    num_batches = (num_questions + batch_size - 1) // batch_size
    tasks = []
    
    for batch_id in range(num_batches):
        # Randomly select math types
        selected_types = random.sample(MATH_TYPES, k=min(3, len(MATH_TYPES)))
        
        task = GenerationTask(
            batch_id=batch_id + 1,
            batch_size=batch_size,
            math_types=selected_types,
            generated_data=[]  # Initialize as empty list
        )
        tasks.append(task)
    
    return tasks


def generate_fallback_data(num: int) -> list[dict]:
    """Programmatically generate math problems as fallback"""
    fallback = []
    for _ in range(num):
        q_type = random.choice(['add', 'mul', 'percent', 'equation', 'sqrt'])
        
        if q_type == 'add':
            a, b = random.randint(10, 500), random.randint(10, 500)
            fallback.append({
                "question": f"Calculate {a} + {b}",
                "answer": str(a + b)
            })
        elif q_type == 'mul':
            a, b = random.randint(5, 50), random.randint(5, 50)
            fallback.append({
                "question": f"Calculate {a} * {b}",
                "answer": str(a * b)
            })
        elif q_type == 'percent':
            p = random.choice([5, 10, 15, 20, 25, 30, 50])
            n = random.randint(100, 1000)
            fallback.append({
                "question": f"What is {p}% of {n}?",
                "answer": str(int(n * p / 100))
            })
        elif q_type == 'equation':
            x = random.randint(2, 20)
            coef = random.randint(2, 10)
            fallback.append({
                "question": f"Solve {coef}x = {coef * x}",
                "answer": str(x)
            })
        elif q_type == 'sqrt':
            n = random.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144, 169, 196, 225])
            fallback.append({
                "question": f"Square root of {n}",
                "answer": str(int(n ** 0.5))
            })
    
    return fallback


def clean_and_validate_data(data: list[dict]) -> list[dict]:
    """Data quality check and cleaning"""
    print("\n🔍 Checking data quality...\n")
    
    # 1. Deduplication
    unique_data = []
    seen_questions = set()
    for item in data:
        q = item['question'].lower().strip()
        if q not in seen_questions:
            seen_questions.add(q)
            unique_data.append(item)
    
    print(f"Deduplication: {len(unique_data)} items ({len(data) - len(unique_data)} duplicates removed)")
    
    # 2. Validate answer format
    valid_data = []
    for item in unique_data:
        try:
            float(item['answer'])
            valid_data.append(item)
        except:
            print(f"⚠️ Removing invalid answer: Q={item['question'][:50]}... A={item['answer']}")
    
    print(f"Validation: {len(valid_data)} valid items")
    
    # 3. Fallback data (if insufficient)
    if len(valid_data) < 4500:
        print(f"\n⚠️ Data insufficient (<4500), generating fallback data...")
        needed = 4500 - len(valid_data)
        fallback_data = generate_fallback_data(needed)
        valid_data.extend(fallback_data)
        print(f"✅ Added {needed} fallback items")
    
    return valid_data


def save_data(data: list[dict], output_dir: str = "data"):
    """Save data to Parquet files"""
    # Shuffle data
    random.shuffle(data)
    
    # Split train/test (90% / 10%)
    split_idx = int(len(data) * 0.9)
    train_data = data[:split_idx]
    test_data = data[split_idx:]
    
    print(f"\n📊 Dataset Statistics:")
    print(f"  Train set: {len(train_data)} items")
    print(f"  Test set: {len(test_data)} items")
    print(f"  Total: {len(data)} items\n")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Convert to DataFrame and save
    train_df = pd.DataFrame(train_data)
    test_df = pd.DataFrame(test_data)
    
    train_path = output_path / "train_gpt5_large.parquet"
    test_path = output_path / "test_gpt5_large.parquet"
    
    train_df.to_parquet(train_path, index=False)
    test_df.to_parquet(test_path, index=False)
    
    print(f"✅ Data saved:")
    print(f"  Train data: {train_path}")
    print(f"  Test data: {test_path}\n")
    
    print("📝 Data Example:")
    print(train_df.head(3).to_string(index=False))
    
    return train_path, test_path


async def run_data_generation():
    """Execute data generation asynchronously"""
    # 1. Create generation tasks
    num_questions = 5000
    batch_size = 20
    tasks = create_generation_tasks(num_questions, batch_size)
    
    print(f"📋 Created {len(tasks)} generation tasks")
    print(f"📦 Generating {batch_size} items per batch\n")
    
    # 2. Configure LLM resource
    llm_resource = agl.LLM(
        endpoint=AZURE_OPENAI_ENDPOINT,
        model=AZURE_OPENAI_DEPLOYMENT,
        api_key=AZURE_OPENAI_API_KEY,
    )
    
    print("🔄 Starting data generation...\n")
    
    # Initialize Runner and Store to enable tracing
    store = agl.InMemoryLightningStore()
    tracer = agl.OtelTracer()
    runner = agl.LitAgentRunner(tracer=tracer)
    
    all_generated_data = []
    
    # Use run_context to initialize Tracer
    with runner.run_context(agent=gpt5_data_generator, store=store):
        for task in tasks:
            try:
                # Use runner.step to execute Agent
                # This correctly handles @agl.rollout context
                # Return value is success_rate (float), data is stored in task['generated_data']
                await runner.step(
                    input=task,
                    resources={"llm": llm_resource}
                )
                
                # Get generated data from task object
                if 'generated_data' in task and task['generated_data']:
                    batch_data = task['generated_data']
                    all_generated_data.extend(batch_data)
                    # Clear to free memory (optional)
                    task['generated_data'] = []
                
                # Print trace details to show GPT-4o presence
                traces = tracer.get_last_trace()
                print(f"🔍 Spans captured in this Rollout ({len(traces)}):")
                for span in traces:
                    print(f"   👉 Span: {span.name}")
                    if span.attributes:
                        print(f"      Attributes: {span.attributes}")

                # Rate limiting to avoid API limits
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"⚠️ Batch failed: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print(f"\n✅ Data generation complete! Generated {len(all_generated_data)} items")
    return all_generated_data


def main():
    """Main function: Generate data using Agent Lightning framework"""
    print("="*70)
    print("🚀 Agent Lightning + GPT-5.1 Math Data Generator")
    print("="*70 + "\n")
    
    print("✨ Agent Lightning Advantages:")
    print("  1. Auto-trace all GPT-5.1 calls")
    print("  2. Record prompt/response/tokens (if Store configured)")
    print("  3. Use @agl.rollout decorator for tracing")
    print("  4. Consistent code structure with training scripts\n")
    
    # Configure logging to file (save Agent Lightning framework logs)
    agl.logging.setup(files="agent_execution.log", level="INFO")
    
    # Execute asynchronous data generation
    all_generated_data = asyncio.run(run_data_generation())
    
    # 4. Clean data
    clean_data = clean_and_validate_data(all_generated_data)
    
    # 5. Save data
    train_path, test_path = save_data(clean_data)
    
    print("\n" + "="*70)
    print("✅ Data generation finished!")
    print("="*70)
    print(f"\n📂 Train data: {train_path}")
    print(f"📂 Test data: {test_path}")
    print("\n🚀 Next step:")
    print("   python train_math_agent_vllm.py")


if __name__ == "__main__":
    main()
