import pandas as pd

def analyze_improvements():
    # Load the judged results
    try:
        base_df = pd.read_parquet("math_base_judged.parquet")
        trained_df = pd.read_parquet("math_trained_judged.parquet")
    except FileNotFoundError:
        print("Error: Could not find result files. Make sure math_base_judged.parquet and math_trained_judged.parquet exist.")
        return

    # Rename columns for merging
    print("Base columns:", base_df.columns)
    print("Trained columns:", trained_df.columns)

    base_df = base_df.rename(columns={
        "response": "base_response", 
        "llm_correct": "base_correct",
        "llm_reason": "base_reason"
    })
    trained_df = trained_df.rename(columns={
        "response": "trained_response", 
        "llm_correct": "trained_correct",
        "llm_reason": "trained_reason"
    })

    # Merge on question only (safer)
    merged_df = pd.merge(base_df, trained_df, on="question", how="inner")

    # 1. Find cases where Trained won (Base: Wrong, Trained: Correct)
    wins = merged_df[(merged_df["base_correct"] == False) & (merged_df["trained_correct"] == True)]
    
    # 2. Find cases where Trained lost (Base: Correct, Trained: Wrong)
    losses = merged_df[(merged_df["base_correct"] == True) & (merged_df["trained_correct"] == False)]

    print(f"Total samples compared: {len(merged_df)}")
    print(f"Trained Model Wins (Fixed Base's mistake): {len(wins)}")
    print(f"Trained Model Losses (Broke Base's success): {len(losses)}")
    print(f"Net Improvement: {len(wins) - len(losses)}")
    
    # 3. Analyze Reasoning Length (Proxy for 'thinking' effort)
    merged_df["base_len"] = merged_df["base_response"].str.len()
    merged_df["trained_len"] = merged_df["trained_response"].str.len()
    
    avg_base_len = merged_df["base_len"].mean()
    avg_trained_len = merged_df["trained_len"].mean()
    
    print(f"\nAverage Response Length (Characters):")
    print(f"Base Model: {avg_base_len:.0f}")
    print(f"Trained Model: {avg_trained_len:.0f}")
    print(f"Change: {((avg_trained_len - avg_base_len) / avg_base_len) * 100:.1f}%")

    # 4. Show a specific example of a "Win"
    if not wins.empty:
        print("\n" + "="*50)
        print("🏆 CASE STUDY: A Problem the Trained Model Fixed")
        print("="*50)
        sample = wins.iloc[0]
        print(f"❓ Question: {sample['question']}")
        print(f"✅ Ground Truth: {sample['ground_truth_x']}") # ground_truth might be duplicated as _x and _y
        print("-" * 30)
        print(f"❌ Base Model Response (Wrong):\n{sample['base_response']}") 
        print("-" * 30)
        print(f"✅ Trained Model Response (Correct):\n{sample['trained_response']}")
        print("="*50)

if __name__ == "__main__":
    analyze_improvements()
