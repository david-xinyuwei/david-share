import pandas as pd

# Define file paths
BASE_FILE = "validation_base_llm_judged.parquet"
TRAINED_FILE = "validation_llm_judged.parquet"

def analyze_regression():
    print(f"Loading {BASE_FILE}...")
    try:
        df_base = pd.read_parquet(BASE_FILE)
    except FileNotFoundError:
        print(f"Error: {BASE_FILE} not found.")
        return

    print(f"Loading {TRAINED_FILE}...")
    try:
        df_trained = pd.read_parquet(TRAINED_FILE)
    except FileNotFoundError:
        print(f"Error: {TRAINED_FILE} not found.")
        return

    # Ensure indices align or merge on question
    # Assuming the order is preserved and identical, but merging on question is safer if unique
    # Let's assume index alignment for now as they come from the same source dataset generation process
    
    if len(df_base) != len(df_trained):
        print(f"Warning: Dataset sizes differ! Base: {len(df_base)}, Trained: {len(df_trained)}")
    
    # Rename columns for merge
    df_base = df_base.rename(columns={
        "response": "response_base", 
        "llm_correct": "correct_base",
        "llm_reason": "reason_base"
    })
    
    df_trained = df_trained.rename(columns={
        "response": "response_trained", 
        "llm_correct": "correct_trained",
        "llm_reason": "reason_trained"
    })
    
    # Merge
    # We use the question and ground_truth as keys to be safe
    df_merged = pd.merge(
        df_base[['question', 'ground_truth', 'response_base', 'correct_base', 'reason_base']],
        df_trained[['question', 'ground_truth', 'response_trained', 'correct_trained', 'reason_trained']],
        on=['question', 'ground_truth'],
        how='inner'
    )
    
    print(f"Matched {len(df_merged)} records.")
    
    # Identify Regressions: Base Correct AND Trained Incorrect
    regressions = df_merged[
        (df_merged['correct_base'] == True) & 
        (df_merged['correct_trained'] == False)
    ]
    
    # Identify Improvements: Base Incorrect AND Trained Correct
    improvements = df_merged[
        (df_merged['correct_base'] == False) & 
        (df_merged['correct_trained'] == True)
    ]
    
    print("\n" + "="*50)
    print("📊 ANALYSIS SUMMARY")
    print("="*50)
    print(f"Base Accuracy:    {df_merged['correct_base'].mean()*100:.2f}%")
    print(f"Trained Accuracy: {df_merged['correct_trained'].mean()*100:.2f}%")
    print(f"📉 Regressions (Good -> Bad): {len(regressions)}")
    print(f"📈 Improvements (Bad -> Good): {len(improvements)}")
    print("="*50)
    
    if len(regressions) > 0:
        print("\n🔍 EXAMPLES OF REGRESSION (What went wrong?):")
        for i, row in regressions.head(10).iterrows():
            print("-" * 80)
            print(f"Q: {row['question']}")
            print(f"Ground Truth: {row['ground_truth']}")
            print(f"✅ Base Response: {row['response_base']}")
            print(f"   Reason: {row['reason_base']}")
            print(f"❌ Trained Response: {row['response_trained']}")
            print(f"   Reason: {row['reason_trained']}")

    if len(improvements) > 0:
        print("\n🔍 EXAMPLES OF IMPROVEMENTS (What got better?):")
        for i, row in improvements.head(5).iterrows():
            print("-" * 80)
            print(f"Q: {row['question']}")
            print(f"Ground Truth: {row['ground_truth']}")
            print(f"❌ Base Response: {row['response_base']}")
            print(f"✅ Trained Response: {row['response_trained']}")

if __name__ == "__main__":
    analyze_regression()
