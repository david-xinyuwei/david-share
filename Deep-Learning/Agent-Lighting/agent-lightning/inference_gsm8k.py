import pandas as pd
from openai import OpenAI
import sys
from tqdm import tqdm
import re

# Configuration
MODEL_URL = "http://localhost:8000/v1"
API_KEY = "EMPTY"

def get_response(client, question):
    messages = [
        {"role": "system", "content": "You are a helpful math assistant. Please solve the problem step by step and put your final answer within \\boxed{}."},
        {"role": "user", "content": question}
    ]
    
    try:
        response = client.chat.completions.create(
            model=client.models.list().data[0].id,  # Use the served model ID
            messages=messages,
            temperature=0.0,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    if len(sys.argv) < 3:
        print("Usage: python inference_gsm8k.py <input_parquet> <output_parquet> [port]")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    port = sys.argv[3] if len(sys.argv) > 3 else "8000"
    
    base_url = f"http://localhost:{port}/v1"
    
    print(f"🚀 Starting Inference on {input_file}")
    print(f"🔌 Connecting to vLLM at {base_url}")
    
    client = OpenAI(api_key=API_KEY, base_url=base_url)
    
    df = pd.read_parquet(input_file)
    responses = []
    
    print(f"📊 Processing {len(df)} samples...")
    
    for index, row in tqdm(df.iterrows(), total=len(df)):
        question = row['question']
        resp = get_response(client, question)
        responses.append(resp)
        
    df['response'] = responses
    df.to_parquet(output_file)
    print(f"💾 Saved responses to {output_file}")

if __name__ == "__main__":
    main()
