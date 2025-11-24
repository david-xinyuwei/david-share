import pandas as pd
try:
    df = pd.read_parquet('gsm8k_trained_responses.parquet')
    print("--- First Response ---")
    print(df.iloc[0]['response'])
    print("--- End First Response ---")
    print(f"Total rows: {len(df)}")
    
    # Check if responses are empty
    empty_count = df[df['response'] == ""].shape[0]
    print(f"Empty responses: {empty_count}")
    
    # Check ground truth format
    print("--- First Ground Truth ---")
    print(df.iloc[0]['ground_truth'])
except Exception as e:
    print(e)
