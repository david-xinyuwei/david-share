from datasets import load_dataset
import pandas as pd
import os

def main():
    print("📥 Loading GSM8K dataset (test split)...")
    try:
        # 尝试加载 GSM8K
        dataset = load_dataset("gsm8k", "main", split="test")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    # 抽取前 100 道
    print("✂️ Selecting first 100 samples...")
    subset = dataset.select(range(100))
    
    data = []
    for item in subset:
        # GSM8K 的 answer 字段通常包含推理过程，最后以 #### 数字 结尾
        # 我们提取最后的数字作为 ground_truth
        full_answer = item["answer"]
        ground_truth = full_answer.split("####")[-1].strip()
        
        data.append({
            "question": item["question"],
            "ground_truth": ground_truth,
            "full_solution": full_answer
        })
    
    df = pd.DataFrame(data)
    output_file = "gsm8k_100_test.parquet"
    df.to_parquet(output_file)
    print(f"✅ Saved 100 GSM8K samples to {output_file}")
    print(f"   Sample 1 Question: {data[0]['question']}")
    print(f"   Sample 1 GT: {data[0]['ground_truth']}")

if __name__ == "__main__":
    main()
