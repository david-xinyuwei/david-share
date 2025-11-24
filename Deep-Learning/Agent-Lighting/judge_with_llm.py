import os
import pandas as pd
import json
import time
from openai import AzureOpenAI

# ================= 配置区域 =================
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "your-api-key")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
AZURE_OPENAI_API_VERSION = "2025-01-01-preview"

import sys
if len(sys.argv) > 1:
    INPUT_FILE = sys.argv[1]
    OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "validation_llm_judged.parquet"
else:
    INPUT_FILE = "validation_trained_model.parquet"
    OUTPUT_FILE = "validation_llm_judged.parquet"

# ===========================================

def get_judge_verdict(client, question, ground_truth, student_response):
    prompt = f"""
    You are an expert Math Teacher and Grader.
    
    Task: Evaluate the Student's response against the Ground Truth.
    
    [Question]
    {question}
    
    [Ground Truth]
    {ground_truth}
    
    [Student Response]
    {student_response}
    
    [Grading Criteria]
    1. CORRECTNESS: Does the student's final answer match the ground truth value?
    2. FORMATTING: Ignore differences in formatting (e.g., "x = 5" vs "5", "5.0" vs "5").
    3. PRECISION: Accept high-precision decimals if they round to the ground truth (e.g., 55.9 vs 55).
    4. VERIFICATION: Ignore any "To verify" or "Check" sections at the end. Look for the main conclusion.
    
    Output strictly valid JSON:
    {{
        "is_correct": true/false,
        "explanation": "Brief reason for the verdict"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a strict but fair math judge. Output JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=1.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        # 如果出错，返回 None
        return {"is_correct": False, "explanation": f"API Error: {str(e)}"}

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 文件未找到: {INPUT_FILE}")
        return

    print(f"📂 加载数据: {INPUT_FILE}...")
    df = pd.read_parquet(INPUT_FILE)
    
    # 初始化 Azure OpenAI 客户端
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    
    print(f"🚀 开始使用 {AZURE_OPENAI_DEPLOYMENT} 进行 AI 裁判评估...")
    
    llm_correct = []
    llm_reasons = []
    
    total = len(df)
    
    print(f"📊 待评测样本数: {len(df)}")

    for index, row in df.iterrows():
        print(f"[{index+1}/{total}] 正在评测题目: {row['question'][:50]}...")
        
        verdict = get_judge_verdict(
            client, 
            row['question'], 
            row['ground_truth'], 
            row['response']
        )
        
        is_correct = verdict.get("is_correct", False)
        reason = verdict.get("explanation", "No explanation")
        
        llm_correct.append(is_correct)
        llm_reasons.append(reason)
        
        status = "✅" if is_correct else "❌"
        print(f"   -> 裁判结果: {status} | 原因: {reason}")
        
        # 简单的速率限制保护
        # time.sleep(0.1)

    df['llm_correct'] = llm_correct
    df['llm_reason'] = llm_reasons
    
    accuracy = df['llm_correct'].mean() * 100
    print("="*50)
    print(f"🏆 LLM 裁判最终准确率: {accuracy:.2f}%")
    print("="*50)
    
    df.to_parquet(OUTPUT_FILE, index=False)
    print(f"💾 评测结果已保存至 {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
