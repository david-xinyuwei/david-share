import pandas as pd
import re

def normalize(s):
    try:
        return float(s)
    except:
        return None

def analyze():
    try:
        df = pd.read_parquet("validation_trained_model.parquet")
    except Exception as e:
        print(f"Error reading parquet: {e}")
        return

    precision_errors = 0
    parsing_failures = 0
    true_errors = 0
    
    print("Analyzing failures...")
    print("-" * 50)
    
    for idx, row in df.iterrows():
        if row['correct']:
            continue
            
        gt = normalize(str(row['ground_truth']))
        resp = row['response']
        pred = normalize(str(row['predicted']))
        
        if gt is None:
            continue

        # Extract ALL numbers from the response to see if the answer is hidden somewhere
        # We filter out very long numbers to avoid parsing timestamps or IDs
        all_nums = []
        for x in re.findall(r'-?\d+\.?\d*', resp):
            try:
                if len(x) < 15:
                    all_nums.append(float(x))
            except:
                pass
        
        # Check 1: Did the model output the EXACT number somewhere?
        found_gt_in_response = False
        for num in all_nums:
            if abs(num - gt) < 0.001:
                found_gt_in_response = True
                break
        
        # Check 2: Did the model output a number that rounds to the GT? (e.g. 55.9 -> 55)
        found_rounding_match = False
        rounding_val = None
        for num in all_nums:
            # Check if rounding the model's number equals the GT
            if abs(round(num) - gt) < 0.001:
                found_rounding_match = True
                rounding_val = num
                break
            # Check if flooring/ceiling matches (sometimes GT is truncated)
            if abs(int(num) - gt) < 0.001:
                found_rounding_match = True
                rounding_val = num
                break

        if found_gt_in_response:
            # The correct number is in the text, but our parser picked something else (or nothing)
            parsing_failures += 1
            if parsing_failures <= 3:
                print(f"[Parsing Error] GT: {gt} | Pred: {pred}")
                print(f"Response Snippet: {resp[-200:]}") # Print last 200 chars
                print("-" * 20)
        elif found_rounding_match:
            # The model is likely correct but more precise, or GT is simplified
            precision_errors += 1
            if precision_errors <= 5:
                print(f"[Precision/Rounding] GT: {gt} | Model has: {rounding_val} (Pred: {pred})")
        else:
            true_errors += 1
            if true_errors <= 5:
                print(f"[True Error] GT: {gt} | Pred: {pred} | Response: {resp[:100]}...")

    print("-" * 50)
    print(f"Total Failures: {len(df[~df['correct']])}")
    print(f"1. Parsing Errors (Correct number exists in text but missed): {parsing_failures}")
    print(f"2. Precision/Rounding Mismatches (Model: 55.9, GT: 55): {precision_errors}")
    print(f"3. Likely True Errors (Model is wrong): {true_errors}")
    
    potential_acc = (len(df[df['correct']]) + parsing_failures + precision_errors) / len(df) * 100
    print(f"\nPotential Accuracy if fixed: {potential_acc:.1f}%")

if __name__ == "__main__":
    analyze()
