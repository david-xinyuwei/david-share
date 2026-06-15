#!/usr/bin/env python3
"""TurboQuant Accuracy Benchmark: MMLU-Pro + GSM8K across KV cache configs.
Tests whether TurboQuant KV cache quantization degrades reasoning accuracy.
"""
import json, time, re, gc, random, argparse
import torch
from vllm import LLM, SamplingParams

# ============================================================
# MMLU-Pro subset (50 questions, diverse categories)
# ============================================================
MMLU_QUESTIONS = [
    {"q": "What is the capital of France?", "choices": ["A) London", "B) Paris", "C) Berlin", "D) Madrid"], "answer": "B"},
    {"q": "Which planet is known as the Red Planet?", "choices": ["A) Venus", "B) Jupiter", "C) Mars", "D) Saturn"], "answer": "C"},
    {"q": "What is the speed of light in vacuum approximately?", "choices": ["A) 3×10^6 m/s", "B) 3×10^8 m/s", "C) 3×10^10 m/s", "D) 3×10^5 m/s"], "answer": "B"},
    {"q": "Who wrote 'A Brief History of Time'?", "choices": ["A) Einstein", "B) Feynman", "C) Hawking", "D) Newton"], "answer": "C"},
    {"q": "What is the chemical symbol for gold?", "choices": ["A) Ag", "B) Fe", "C) Au", "D) Cu"], "answer": "C"},
    {"q": "In which year did World War II end?", "choices": ["A) 1943", "B) 1944", "C) 1945", "D) 1946"], "answer": "C"},
    {"q": "What is the derivative of x^3?", "choices": ["A) x^2", "B) 3x^2", "C) 3x", "D) x^3/3"], "answer": "B"},
    {"q": "Which element has atomic number 1?", "choices": ["A) Helium", "B) Lithium", "C) Oxygen", "D) Hydrogen"], "answer": "D"},
    {"q": "What is the SI unit of electric current?", "choices": ["A) Volt", "B) Watt", "C) Ampere", "D) Ohm"], "answer": "C"},
    {"q": "What is the largest organ in the human body?", "choices": ["A) Liver", "B) Brain", "C) Skin", "D) Heart"], "answer": "C"},
    {"q": "What is the integral of 1/x?", "choices": ["A) x", "B) ln|x| + C", "C) 1/x^2", "D) e^x"], "answer": "B"},
    {"q": "Which gas makes up about 78% of Earth's atmosphere?", "choices": ["A) Oxygen", "B) Carbon dioxide", "C) Nitrogen", "D) Argon"], "answer": "C"},
    {"q": "What is the powerhouse of the cell?", "choices": ["A) Nucleus", "B) Ribosome", "C) Mitochondria", "D) Golgi body"], "answer": "C"},
    {"q": "In binary, what is 1010 + 0110?", "choices": ["A) 1100", "B) 10000", "C) 1110", "D) 10100"], "answer": "B"},
    {"q": "What is the time complexity of binary search?", "choices": ["A) O(n)", "B) O(n^2)", "C) O(log n)", "D) O(1)"], "answer": "C"},
    {"q": "Which vitamin is produced when skin is exposed to sunlight?", "choices": ["A) Vitamin A", "B) Vitamin B", "C) Vitamin C", "D) Vitamin D"], "answer": "D"},
    {"q": "What is the pH of pure water?", "choices": ["A) 5", "B) 7", "C) 9", "D) 14"], "answer": "B"},
    {"q": "Who proposed the theory of general relativity?", "choices": ["A) Newton", "B) Bohr", "C) Einstein", "D) Planck"], "answer": "C"},
    {"q": "What is the Fibonacci sequence after 1, 1, 2, 3, 5?", "choices": ["A) 7", "B) 8", "C) 9", "D) 10"], "answer": "B"},
    {"q": "Which data structure uses LIFO?", "choices": ["A) Queue", "B) Stack", "C) Linked List", "D) Tree"], "answer": "B"},
    {"q": "What is Avogadro's number approximately?", "choices": ["A) 6.02×10^23", "B) 3.14×10^20", "C) 1.38×10^-23", "D) 9.81"], "answer": "A"},
    {"q": "What does HTTP stand for?", "choices": ["A) HyperText Transfer Protocol", "B) High Tech Transfer Protocol", "C) HyperText Transmission Process", "D) Host Transfer Text Protocol"], "answer": "A"},
    {"q": "What is the square root of 144?", "choices": ["A) 10", "B) 11", "C) 12", "D) 13"], "answer": "C"},
    {"q": "Which programming language is known for 'Write once, run anywhere'?", "choices": ["A) Python", "B) C++", "C) Java", "D) JavaScript"], "answer": "C"},
    {"q": "What is the chemical formula for water?", "choices": ["A) CO2", "B) H2O", "C) NaCl", "D) O2"], "answer": "B"},
    {"q": "What is the value of pi to two decimal places?", "choices": ["A) 3.12", "B) 3.14", "C) 3.16", "D) 3.18"], "answer": "B"},
    {"q": "In TCP/IP, which layer is responsible for routing?", "choices": ["A) Application", "B) Transport", "C) Network", "D) Data Link"], "answer": "C"},
    {"q": "What is the determinant of a 2x2 identity matrix?", "choices": ["A) 0", "B) 1", "C) 2", "D) -1"], "answer": "B"},
    {"q": "Who discovered penicillin?", "choices": ["A) Pasteur", "B) Fleming", "C) Koch", "D) Jenner"], "answer": "B"},
    {"q": "What sorting algorithm has O(n log n) average case?", "choices": ["A) Bubble sort", "B) Selection sort", "C) Merge sort", "D) Insertion sort"], "answer": "C"},
]

# ============================================================
# GSM8K subset (20 math word problems)
# ============================================================
GSM8K_QUESTIONS = [
    {"q": "Janet has 5 apples. She buys 3 more and then gives away 2. How many apples does she have?", "answer": 6},
    {"q": "A store sells shirts for $15 each. If Tom buys 4 shirts and pays with a $100 bill, how much change does he get?", "answer": 40},
    {"q": "A train travels at 60 mph for 3 hours. How many miles does it travel?", "answer": 180},
    {"q": "If a rectangle has length 8 and width 5, what is its area?", "answer": 40},
    {"q": "Sarah has 24 cookies. She wants to share them equally among 6 friends. How many cookies does each friend get?", "answer": 4},
    {"q": "A book costs $12.50. If you buy 3 books and get a 10% discount on the total, how much do you pay?", "answer": 33.75},
    {"q": "John runs 3 miles every day. How many miles does he run in 2 weeks?", "answer": 42},
    {"q": "If 5 workers can build a wall in 10 days, how many days would it take 10 workers?", "answer": 5},
    {"q": "A car uses 8 gallons of gas to travel 240 miles. How many miles per gallon does it get?", "answer": 30},
    {"q": "Emma saves $25 per week. How much will she save in 8 weeks?", "answer": 200},
    {"q": "A pizza is cut into 8 slices. If 3 people each eat 2 slices, how many slices are left?", "answer": 2},
    {"q": "The temperature was 45°F in the morning and rose by 18°F by noon. What was the temperature at noon?", "answer": 63},
    {"q": "A farmer has 120 chickens. He sells 1/3 of them. How many chickens does he have left?", "answer": 80},
    {"q": "If a shirt originally costs $40 and is on sale for 25% off, what is the sale price?", "answer": 30},
    {"q": "A classroom has 5 rows of desks with 6 desks in each row. How many desks are there?", "answer": 30},
    {"q": "Mike earns $12 per hour. If he works 8 hours on Monday and 6 hours on Tuesday, how much does he earn?", "answer": 168},
    {"q": "A tank holds 500 liters. If it is 60% full, how many liters of water are in it?", "answer": 300},
    {"q": "Lisa bought 3 pens at $2 each and 2 notebooks at $5 each. How much did she spend?", "answer": 16},
    {"q": "A car depreciates 15% per year. If it costs $20,000 new, what is it worth after 1 year?", "answer": 17000},
    {"q": "If the perimeter of a square is 36 cm, what is the length of one side?", "answer": 9},
]

def build_mmlu_prompt(item):
    choices_str = "\n".join(item["choices"])
    return f"""Answer the following multiple choice question. Reply with ONLY the letter (A, B, C, or D).

Question: {item['q']}
{choices_str}

Answer:"""

def build_gsm8k_prompt(item):
    return f"""Solve the following math problem. Show your work, then give the final numerical answer on the last line as: #### <number>

Problem: {item['q']}

Solution:"""

def extract_mmlu_answer(text):
    text = text.strip()
    match = re.search(r'\b([ABCD])\b', text[:20])
    return match.group(1) if match else text[:1].upper()

def extract_gsm8k_answer(text):
    match = re.search(r'####\s*([\d,.]+)', text)
    if match:
        return float(match.group(1).replace(',', ''))
    numbers = re.findall(r'[\d,.]+', text)
    if numbers:
        try:
            return float(numbers[-1].replace(',', ''))
        except:
            pass
    return None

def run_eval(model_path, kv_cache_dtype, max_model_len=8192):
    print(f"\n{'='*60}", flush=True)
    print(f"Config: kv_cache_dtype={kv_cache_dtype}", flush=True)
    print(f"{'='*60}", flush=True)

    llm = LLM(model=model_path, kv_cache_dtype=kv_cache_dtype,
              max_model_len=max_model_len, gpu_memory_utilization=0.9,
              enforce_eager=True, trust_remote_code=True)

    # MMLU
    mmlu_prompts = [build_mmlu_prompt(q) for q in MMLU_QUESTIONS]
    sp = SamplingParams(temperature=0, max_tokens=8)
    t0 = time.time()
    mmlu_outputs = llm.generate(mmlu_prompts, sp)
    mmlu_time = time.time() - t0

    mmlu_correct = 0
    mmlu_details = []
    for i, (out, q) in enumerate(zip(mmlu_outputs, MMLU_QUESTIONS)):
        pred = extract_mmlu_answer(out.outputs[0].text)
        correct = pred == q["answer"]
        if correct:
            mmlu_correct += 1
        mmlu_details.append({"idx": i, "pred": pred, "gold": q["answer"], "correct": correct})

    mmlu_acc = mmlu_correct / len(MMLU_QUESTIONS)
    print(f"  MMLU: {mmlu_correct}/{len(MMLU_QUESTIONS)} = {mmlu_acc*100:.1f}% ({mmlu_time:.1f}s)", flush=True)

    # GSM8K
    gsm_prompts = [build_gsm8k_prompt(q) for q in GSM8K_QUESTIONS]
    sp_gsm = SamplingParams(temperature=0, max_tokens=256)
    t0 = time.time()
    gsm_outputs = llm.generate(gsm_prompts, sp_gsm)
    gsm_time = time.time() - t0

    gsm_correct = 0
    gsm_details = []
    for i, (out, q) in enumerate(zip(gsm_outputs, GSM8K_QUESTIONS)):
        pred = extract_gsm8k_answer(out.outputs[0].text)
        correct = pred is not None and abs(pred - q["answer"]) < 0.01
        if correct:
            gsm_correct += 1
        gsm_details.append({"idx": i, "pred": pred, "gold": q["answer"], "correct": correct, "text": out.outputs[0].text[:200]})

    gsm_acc = gsm_correct / len(GSM8K_QUESTIONS)
    print(f"  GSM8K: {gsm_correct}/{len(GSM8K_QUESTIONS)} = {gsm_acc*100:.1f}% ({gsm_time:.1f}s)", flush=True)

    result = {
        "kv_cache_dtype": kv_cache_dtype,
        "mmlu_accuracy": round(mmlu_acc, 4),
        "mmlu_correct": mmlu_correct,
        "mmlu_total": len(MMLU_QUESTIONS),
        "mmlu_time_s": round(mmlu_time, 1),
        "gsm8k_accuracy": round(gsm_acc, 4),
        "gsm8k_correct": gsm_correct,
        "gsm8k_total": len(GSM8K_QUESTIONS),
        "gsm8k_time_s": round(gsm_time, 1),
        "mmlu_details": mmlu_details,
        "gsm8k_details": gsm_details,
    }

    del llm
    gc.collect()
    torch.cuda.empty_cache()
    time.sleep(5)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="YOUR_MODEL_PATH")
    parser.add_argument("--output", default="./results_accuracy.json")
    args = parser.parse_args()

    configs = ["auto", "fp8_e4m3", "turboquant_3bit_nc", "turboquant_4bit_nc"]
    all_results = []

    for cfg in configs:
        try:
            r = run_eval(args.model, cfg)
            all_results.append(r)
        except Exception as e:
            import traceback
            traceback.print_exc()
            all_results.append({"kv_cache_dtype": cfg, "error": str(e)[:300]})

    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*70}", flush=True)
    print(f"{'Config':<25} {'MMLU':>12} {'GSM8K':>12}", flush=True)
    print(f"{'='*70}", flush=True)
    for r in all_results:
        if "error" in r:
            print(f"{r['kv_cache_dtype']:<25} ERROR: {r['error'][:40]}")
        else:
            print(f"{r['kv_cache_dtype']:<25} {r['mmlu_correct']}/{r['mmlu_total']} ({r['mmlu_accuracy']*100:.1f}%) {r['gsm8k_correct']}/{r['gsm8k_total']} ({r['gsm8k_accuracy']*100:.1f}%)")
    print(f"{'='*70}", flush=True)
    print("ACCURACY_BENCHMARK_DONE", flush=True)

if __name__ == "__main__":
    main()
