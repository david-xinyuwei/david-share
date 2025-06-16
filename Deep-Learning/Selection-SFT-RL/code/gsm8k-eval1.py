"""
Evaluation script for Gemma-2-2B-IT models fine-tuned on GSM8K.
Supports optional --model_dir to evaluate multiple checkpoints.
"""

import argparse  # NEW ↓↓
import re
import json
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from config import init, close, get_gsm8k_questions, Config


# ───────────────────────────  Helper Functions  ────────────────────────────
def sampler(
    model,
    input_string,
    temperature=0.0,
    top_p=1.0,
    max_prompt_length=None,
    max_completion_length=256,
):
    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        truncate_prompt_tokens=max_prompt_length,
        max_tokens=max_completion_length,
    )
    output = model.generate([input_string], sampling_params, use_tqdm=False)
    return output[0].outputs[0].text


def extract_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    tag_pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    match = re.search(tag_pattern, text, re.DOTALL)
    if match:
        answer = re.sub(r"[%$]", "", match.group(1)).strip()
        return answer
    return ""


def extract_last_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    tag_pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    matches = re.findall(tag_pattern, text, re.DOTALL)
    if matches:
        answer = re.sub(r"[%$]", "", matches[-1]).strip()
        return answer
    return ""


def find_number(search_string):
    numbers = re.compile(r"-?[\d,]*\.?\d+", re.S).findall(search_string)
    return numbers[-1] if numbers else ""


def remove_symbols(x: str) -> str:
    return x.replace(",", "").replace("%", "").replace("$", "").strip()


def get_num_tokens(text, tokenizer_instance):
    return len(tokenizer_instance(text, return_tensors="pt")["input_ids"][0])


# ───────────────────────────  Main  ────────────────────────────
if __name__ == "__main__":
    init()
    params = Config()

    # NEW ↓↓  Argument parser for custom model directory
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model_dir",
        type=str,
        default=None,
        help="Path to merged model directory. "
             "If omitted, defaults to Config.OUTPUT_MODEL",
    )
    args = parser.parse_args()
    model_path = args.model_dir or params.OUTPUT_MODEL
    # NEW ↑↑

    # Load model
    print(f"Evaluating model: {model_path}")
    llm = LLM(model=model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    # Load evaluation dataset
    gsm8k_test = get_gsm8k_questions("test")

    ground_truth, answers, input_tokens, output_tokens, records = {}, {}, [], [], {}
    idx = correct_format = plausibly_correct = correct = 0

    for task_id, item in tqdm(enumerate(gsm8k_test), total=len(gsm8k_test)):
        prompt = item["prompt"][0]["content"]
        ground_truth[task_id] = item["answer"]
        input_tokens.append(get_num_tokens(prompt, tokenizer))

        response = sampler(
            llm,
            input_string=prompt,
            temperature=0,
            max_prompt_length=params.max_prompt_length,
            max_completion_length=params.max_completion_length,
        )
        output_tokens.append(get_num_tokens(response, tokenizer))

        answers[task_id] = remove_symbols(find_number(response))

        pattern = r"^<reasoning>[\s\S]*?<\/reasoning>\s*<answer>[\s\S]*?<\/answer>$"
        if re.match(pattern, response.strip()):
            correct_format += 1

        extracted_xml_answer = extract_last_xml_answer(response)
        if answers[task_id] == ground_truth[task_id] or extracted_xml_answer == ground_truth[task_id]:
            plausibly_correct += 1
        if extracted_xml_answer == ground_truth[task_id]:
            correct += 1

        records[task_id] = {
            "prompt": prompt,
            "answer": ground_truth[task_id],
            "response": response,
            "last_numeric_response": answers[task_id],
            "xml_response": extracted_xml_answer,
            "xml_match": bool(re.match(pattern, response.strip())),
        }
        idx += 1

    # Save records
    with open("records.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4)

    # Report metrics
    print("-" * 40)
    print(f"Input:  max tokens: {max(input_tokens)}")
    print(f"        avg tokens: {sum(input_tokens) / (idx + 1):.1f}")
    print(f"Output: max tokens: {max(output_tokens)}")
    print(f"        avg tokens: {sum(output_tokens) / (idx + 1):.1f}")
    print(f"Correct format:       {correct_format} / {idx+1} "
          f"({correct_format / (idx + 1) * 100:.1f}%)")
    print(f"Plausibly correct:    {plausibly_correct} / {idx+1} "
          f"({plausibly_correct / (idx + 1) * 100:.1f}%)")
    print(f"Correct:              {correct} / {idx+1} "
          f"({correct / (idx + 1) * 100:.1f}%)")
    print("=" * 40)

    close(llm)
