import pandas as pd
import re
import sys

def extract_answer(content: str) -> str:
    if not isinstance(content, str):
        return "N/A"
        
    # 1. 优先查找 \boxed{...}
    boxed = re.findall(r'\\boxed\{([^}]+)\}', content)
    if boxed:
        return boxed[-1]
    
    # 2. 移除验证/检查部分
    content_clean = re.split(r'(To verify|Check:|Verification:|Verify:)', content, flags=re.IGNORECASE)[0]
    
    # 3. 查找 "Final Answer" 后的数字
    final_match = re.search(r'Final Answer:.*?(-?\d+\.?\d*)', content_clean, re.IGNORECASE | re.DOTALL)
    if final_match:
        return final_match.group(1)
        
    # 4. 回退到提取最后一个数字
    numbers = re.findall(r'-?\d+\.?\d*', content_clean)
    return numbers[-1] if numbers else "N/A"

def check_answer(predicted: str, ground_truth: str) -> bool:
    try:
        return abs(float(predicted) - float(ground_truth)) < 0.01
    except:
        return False

def reparse_file(filename: str):
    print(f"Reparsing {filename}...")
    df = pd.read_parquet(filename)
    
    # Apply new extraction logic
    df['predicted'] = df['response'].apply(extract_answer)
    
    # Re-check correctness
    df['correct'] = df.apply(lambda row: check_answer(row['predicted'], row['ground_truth']), axis=1)
    
    # Save back
    df.to_parquet(filename, index=False)
    
    acc = df['correct'].mean() * 100
    print(f"New Accuracy: {acc:.1f}%")

if __name__ == "__main__":
    reparse_file("validation_trained_model.parquet")
    # Also reparse base model just in case, though it's less likely to have verification steps
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        reparse_file("validation_base_model.parquet")
