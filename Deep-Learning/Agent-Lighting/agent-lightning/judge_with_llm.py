import pandas as pd
import sys
from tqdm import tqdm
import os
import json

# Configuration
JUDGE_MODEL = "gpt-4o"  # Or gpt-5-preview if available
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
API_VERSION = "2024-08-01-preview"


def judge_answer(client, question, ground_truth, model_response):
    prompt = f"""
    You are a math judge. Compare the model's response to the ground truth.
    
    Question: {question}
    Ground Truth: {ground_truth}
    Model Response: {model_response}
    
    Does the model's response match the ground truth? 
    Focus on the final numeric value or expression.
    Ignore minor formatting differences.
    
    Return a JSON object:
    {{
        "correct": true/false,
        "reason": "explanation"
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        return f'{{"correct": false, "reason": "Error: {str(e)}"}}'

def main():
    if len(sys.argv) < 3:
        print("Usage: python judge_with_llm.py <input_parquet> <output_parquet>")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not API_KEY or not ENDPOINT:
        print("❌ Error: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set.")
        return

    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=API_KEY,
        api_version=API_VERSION,
        azure_endpoint=ENDPOINT
    )
    
    df = pd.read_parquet(input_file)
    results = []
    
    print(f"⚖️ Judging {len(df)} samples...")
    
    for index, row in tqdm(df.iterrows(), total=len(df)):
        # Handle different column names for ground truth
        ground_truth = row.get('answer') or row.get('ground_truth') or row.get('solution')
        if ground_truth is None:
            print(f"⚠️ Warning: No ground truth found for row {index}")
            ground_truth = "N/A"
            
        res_json = judge_answer(client, row['question'], ground_truth, row['response'])
        results.append(res_json)
        
    df['judge_result'] = results
    
    # Parse JSON to columns
    corrects = []
    reasons = []
    for r in results:
        try:
            j = json.loads(r)
            corrects.append(j.get("correct", False))
            reasons.append(j.get("reason", ""))
        except Exception:
            corrects.append(False)
            reasons.append("Parse Error")
            
    df['llm_correct'] = corrects
    df['llm_reason'] = reasons
    
    df.to_parquet(output_file)
    print(f"💾 Saved judgment results to {output_file}")

if __name__ == "__main__":
    main()
