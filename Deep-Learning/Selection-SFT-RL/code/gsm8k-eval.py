"""
Training instructions for RL GRPO on GSM8K
"""

import re
import json
from tqdm import tqdm
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from config import init, close, get_gsm8k_questions, Config


def sampler(
    model,
    input_string,
    temperature=0.0,
    top_p=1.0,
    max_prompt_length=None,
    max_completion_length=256,
):
    """LLM generration function"""
    sampling_params = SamplingParams(
        temperature=temperature,
        top_p=top_p,
        truncate_prompt_tokens=max_prompt_length,
        max_tokens=max_completion_length,
    )
    output = model.generate([input_string], sampling_params, use_tqdm=False)
    return output[0].outputs[0].text


def extract_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    """Extract the content within tags from a string using regex"""

    tag_pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    match = re.search(
        tag_pattern, text, re.DOTALL
    )  # DOTALL allows matching across multiple lines

    if match:
        answer = match.group(1)
        answer = re.sub(r"[%$]", "", answer).strip()  # Remove '%' and '$'
        return answer

    return ""


def extract_last_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    """Extract the content within the last occurrence of tags from a string using regex"""

    tag_pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    matches = re.findall(tag_pattern, text, re.DOTALL)  # Find all matches

    if matches:
        answer = matches[-1]  # Get the last match
        answer = re.sub(r"[%$]", "", answer).strip()  # Remove '%' and '$'
        return answer

    return ""


def find_number(search_string):
    """Finds the last number to appear in a string"""

    # Use regular expression to find all numbers in the search string
    numbers = re.compile(
        r"-?[\d,]*\.?\d+",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    ).findall(search_string)

    if numbers:
        return numbers[-1]  # Return the last number found
    else:
        return ""  # Return empty string if no number is found


def remove_symbols(x: str) -> str:
    """Remove commas, pct and USD symbols"""
    return x.replace(",", "").replace("%", "").replace("$", "").strip()


def get_num_tokens(text, tokenizer_instance):
    """Count the number of tokens in a string of text"""
    encoding = tokenizer_instance(text, return_tensors="pt")
    input_ids = encoding["input_ids"]
    return len(input_ids[0])


if __name__ == "__main__":

    init()
    params = Config()

    # Load the model to eval
    print(f"Evaluating model {params.OUTPUT_MODEL}")
    llm = LLM(model=params.OUTPUT_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(params.OUTPUT_MODEL)

    # Load the evaluation dataset
    gsm8k_test = get_gsm8k_questions("test")

    # Initialize dictionaries and lists to store results
    ground_truth = {}
    answers = {}
    input_tokens = []
    output_tokens = []
    records = {}

    # Initialize counters for evaluation metrics
    idx = 0
    correct_format = 0
    plausibly_correct = 0
    correct = 0

    # Iterate through the test dataset
    for task_id, item in tqdm(enumerate(gsm8k_test), total=len(gsm8k_test)):

        # Extract the prompt and ground truth answer
        prompt = item["prompt"][0]["content"]
        ground_truth[task_id] = item["answer"]

        # Tokenize and store input length
        input_tokens.append(get_num_tokens(prompt, tokenizer))

        # Generate model response
        response = sampler(
            llm,
            input_string=prompt,
            temperature=0,
            max_prompt_length=params.max_prompt_length,
            max_completion_length=params.max_completion_length,
        )

        # Tokenize and store output length
        output_tokens.append(get_num_tokens(response, tokenizer))

        # Process and store the model's numerical answer
        answers[task_id] = remove_symbols(find_number(response))

        # Check if response follows the required XML-like format
        pattern = r"^<reasoning>[\s\S]*?<\/reasoning>\s*<answer>[\s\S]*?<\/answer>$"
        if re.match(pattern, response.strip()):
            correct_format += 1

        # Check if extracted answer matches the ground truth in any acceptable form
        extracted_xml_answer = extract_last_xml_answer(response)
        if (
            answers[task_id] == ground_truth[task_id]
            or extracted_xml_answer == ground_truth[task_id]
        ):
            plausibly_correct += 1

        # Check if the extracted XML answer is exactly correct
        if extracted_xml_answer == ground_truth[task_id]:
            correct += 1

        # Store record
        records[task_id] = {
            "prompt": prompt,
            "answer": ground_truth[task_id],
            "response": response,
            "last_numeric_response": answers[task_id],
            "xml_response": extracted_xml_answer,
            "xml_match": bool(re.match(pattern, response.strip())),
        }

        idx += 1

# Save records to a JSON file
with open("records.json", "w", encoding="utf-8") as f:
    json.dump(records, f, indent=4)

# Report Benchmark results
print("-" * 40)

print(f"Input:  max tokens: {max(input_tokens)}")
print(f"        avg tokens: {sum(input_tokens) / (idx + 1):.1f}")

print(f"Output: max tokens: {max(output_tokens)}")
print(f"        avg tokens: {sum(output_tokens) / (idx + 1):.1f}")

print(
    f"Correct format:       {correct_format} out of {idx+1} "
    f"({correct_format / (idx + 1) * 100:.1f}%)"
)

print(
    f"Plausibly correct:    {plausibly_correct} out of {idx+1} "
    f"({plausibly_correct / (idx + 1) * 100:.1f}%)"
)

print(
    f"Correct:              {correct} out of {idx+1} "
    f"({correct / (idx + 1) * 100:.1f}%)"
)

print("=" * 40)

close(llm)
