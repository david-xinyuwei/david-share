from datasets import load_dataset
import pandas as pd
import re

def extract_boxed_answer(text):
    """
    Extract the content within \boxed{...}.
    Handles nested braces by counting.
    """
    idx = text.rfind("\\boxed{")
    if idx == -1:
        return text.strip()
    
    idx += 7 # Length of "\boxed{"
    brace_count = 1
    end_idx = idx
    
    while brace_count > 0 and end_idx < len(text):
        if text[end_idx] == "{":
            brace_count += 1
        elif text[end_idx] == "}":
            brace_count -= 1
        end_idx += 1
        
    if brace_count == 0:
        return text[idx:end_idx-1]
    
    return text.strip()

def main():
    print("📥 Loading MATH dataset (test split)...")
    dataset = None
    
    # Try different MATH dataset versions
    sources = [
        "hendrycks/competition_math",
        "lighteval/MATH",
        "HuggingFaceH4/MATH-500"
    ]
    
    for source in sources:
        print(f"Trying to load {source}...")
        try:
            dataset = load_dataset(source, split="test", trust_remote_code=True)
            print(f"✅ Successfully loaded {source}")
            break
        except Exception as e:
            print(f"❌ Failed to load {source}: {e}")
            try:
                # Try without trust_remote_code
                dataset = load_dataset(source, split="test")
                print(f"✅ Successfully loaded {source} (without trust_remote_code)")
                break
            except Exception as e2:
                print(f"❌ Failed to load {source} (without trust_remote_code): {e2}")
    
    if dataset is None:
        print("❌ Could not load any MATH dataset.")
        return

    # Select 100 samples
    print("✂️ Selecting first 100 samples...")
    subset = dataset.select(range(100))
    
    data = []
    for item in subset:
        # Handle different column names
        question = item.get("problem") or item.get("question")
        solution = item.get("solution") or item.get("answer")
        
        ground_truth = extract_boxed_answer(solution)
        
        data.append({
            "question": question,
            "ground_truth": ground_truth,
            "full_solution": solution,
            "level": item.get("level", "Unknown"),
            "type": item.get("type", "Unknown")
        })
    
    df = pd.DataFrame(data)
    output_file = "math_100_test.parquet"
    df.to_parquet(output_file)
    print(f"✅ Saved 100 MATH samples to {output_file}")
    print(f"   Sample 1 Question: {data[0]['question'][:50]}...")
    print(f"   Sample 1 GT: {data[0]['ground_truth']}")

if __name__ == "__main__":
    main()
