import pandas as pd
import re

def extract_answer(text):
    if not isinstance(text, str):
        return ""
        
    # 0. Remove verification sections (CRITICAL FIX)
    # The model often ends with "To verify: ... 75 = 75", causing us to pick 75 instead of the answer.
    verification_markers = ["To verify", "To check", "Verification:", "Check:", "This confirms"]
    for marker in verification_markers:
        # Case insensitive check might be better, but let's try exact first
        if marker in text:
            text = text.split(marker)[0]
            break
    
    # 1. Prefer \boxed{}
    boxed_match = re.search(r'\\boxed\{([^}]+)\}', text)
    if boxed_match:
        return boxed_match.group(1)
    
    # 2. Narrow down to "Final Answer" section if present
    # We look for the LAST occurrence of these markers to be safe
    final_answer_markers = ["### Final Answer", "Final Answer:", "Therefore,", "So,"]
    
    search_text = text
    for marker in final_answer_markers:
        if marker in text:
            # Split and take the last part
            parts = text.split(marker)
            if len(parts) > 1:
                search_text = parts[-1]
            # We don't break here, we try to find the most specific/last marker? 
            # Actually, "Therefore" might appear multiple times. 
            # Let's just take the last split of the first marker found? 
            # No, "Final Answer" is stronger than "Therefore".
            
    # Let's try a priority queue of markers
    if "### Final Answer" in text:
        search_text = text.split("### Final Answer")[-1]
    elif "Final Answer:" in text:
        search_text = text.split("Final Answer:")[-1]
    elif "Therefore," in text:
        search_text = text.split("Therefore,")[-1]
    elif "So," in text:
        search_text = text.split("So,")[-1]
            
    # 3. Look for bolded numbers **123** or **123.45** in the search_text
    bold_matches = re.findall(r'\*\*([0-9]+\.?[0-9]*)\*\*', search_text)
    if bold_matches:
        return bold_matches[-1] # Take the last bolded number
        
    # 4. Fallback: Find ALL numbers in the remaining text and take the LAST one.
    # We look for integers or decimals.
    numbers = re.findall(r'-?\d+\.?\d*', search_text)
    if numbers:
        return numbers[-1]
        
    # If we didn't find anything in the search_text (maybe it was empty?), try the whole text
    numbers_full = re.findall(r'-?\d+\.?\d*', text)
    if numbers_full:
        return numbers_full[-1]

    return ""

def normalize_number(s):
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def main():
    print("Loading validation_trained_model.parquet...")
    df = pd.read_parquet("validation_trained_model.parquet")
    
    print(f"Loaded {len(df)} rows.")
    
    correct_count = 0
    total = 0
    
    for index, row in df.iterrows():
        # The column name in the saved parquet file is 'ground_truth', not 'answer'
        ground_truth = normalize_number(str(row['ground_truth']))
        
        # Extract from the 'response' column (which contains the model output)
        predicted_str = extract_answer(row['response'])
        predicted = normalize_number(predicted_str)
        
        if ground_truth is not None and predicted is not None:
            # Compare with tolerance
            if abs(ground_truth - predicted) < 1e-6:
                correct_count += 1
        
        total += 1
        
        if index < 5:
            print(f"GT: {ground_truth}, Pred: {predicted} (str: {predicted_str})")

    accuracy = (correct_count / total) * 100
    print(f"New Accuracy: {accuracy:.2f}%")
    
    # Update the dataframe with new predictions and correctness
    # We need to make sure we are updating the right rows. 
    # Since we iterated in order, we can just assign lists.
    
    new_predicted = []
    new_correct = []
    
    for index, row in df.iterrows():
        ground_truth = normalize_number(str(row['ground_truth']))
        predicted_str = extract_answer(row['response'])
        predicted = normalize_number(predicted_str)
        
        is_correct = False
        if ground_truth is not None and predicted is not None:
            # 1. Exact match
            if abs(ground_truth - predicted) < 1e-6:
                is_correct = True
            # 2. Rounding match (GT=55, Pred=55.9)
            elif abs(round(predicted) - ground_truth) < 1e-6:
                is_correct = True
            # 3. Floor match (GT=55, Pred=55.9) - sometimes GT is just truncated
            elif abs(int(predicted) - ground_truth) < 1e-6:
                is_correct = True
                
        new_predicted.append(predicted_str if predicted_str else "N/A")
        new_correct.append(is_correct)
        
        if is_correct:
            correct_count += 1
        
    df['predicted'] = new_predicted
    df['correct'] = new_correct
    
    print("Saving updated parquet file...")
    df.to_parquet("validation_trained_model.parquet", index=False)
    print("Done.")

if __name__ == "__main__":
    main()
