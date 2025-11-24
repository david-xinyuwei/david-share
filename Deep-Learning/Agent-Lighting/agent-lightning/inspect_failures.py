import pandas as pd

df = pd.read_parquet('validation_trained_model.parquet')
failures = df[~df['correct']]

print(f"Total Failures: {len(failures)}")
print("="*50)

for idx, row in failures.head(10).iterrows():
    print(f"Question: {row['question']}")
    print(f"Ground Truth: {row['ground_truth']}")
    print(f"Predicted (Parsed): {row['predicted']}")
    print(f"Full Response:\n{row['response']}")
    print("-" * 50)
