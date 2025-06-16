import re
from transformers import AutoTokenizer
from trl import GRPOConfig, GRPOTrainer
from peft import LoraConfig

from config import init, close, is_bfloat16_supported, get_gsm8k_questions, Config


def extract_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    """Extract the content within tags from a string using regex"""

    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    match = re.search(
        pattern, text, re.DOTALL
    )  # DOTALL allows matching across multiple lines

    if match:
        answer = match.group(1)
        answer = re.sub(r"[%$]", "", answer).strip()  # Remove '%' and '$'
        return answer

    return ""


def extract_last_xml_answer(text, start_tag="<answer>", end_tag="</answer>"):
    """Extract the content within the last occurrence of tags from a string using regex"""

    pattern = re.escape(start_tag) + r"(.*?)" + re.escape(end_tag)
    matches = re.findall(pattern, text, re.DOTALL)  # Find all matches

    if matches:
        answer = matches[-1]  # Get the last match
        answer = re.sub(r"[%$]", "", answer).strip()  # Remove '%' and '$'
        return answer

    return ""


def format_reward_func(completions, **kwargs):
    """Reward function that checks if the completion has the correct format."""
    pattern = r"^<reasoning>[\s\S]*?<\/reasoning>\s*<answer>[\s\S]*?<\/answer>$"
    responses = [completion[0]["content"] for completion in completions]
    rewards = [1.0 if re.match(pattern, response) else 0.0 for response in responses]
    return rewards


def correctness_reward_func(completions, answer, **kwargs):
    """Reward function that checks if the answer is correct."""
    responses = [completion[0]["content"] for completion in completions]
    extracted_responses = [extract_last_xml_answer(response) for response in responses]
    rewards = [
        2.0 if extracted == correct else 0.0
        for extracted, correct in zip(extracted_responses, answer)
    ]
    return rewards


if __name__ == "__main__":

    init()
    params = Config()

    gsm8k_train = get_gsm8k_questions(split="train")

    peft_config = LoraConfig(
        lora_alpha=64,
        lora_dropout=0,
        r=64,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    training_args = GRPOConfig(
        use_vllm=True,  # use vLLM for fast inference!
        vllm_device="cuda:0",
        vllm_gpu_memory_utilization=0.35,
        vllm_max_model_len=params.max_prompt_length + params.max_completion_length,
        learning_rate=1e-5,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        warmup_ratio=0.1,
        beta=0.005,  # divergence coefficient
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        bf16=is_bfloat16_supported(),
        fp16=not is_bfloat16_supported(),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        gradient_accumulation_steps=4,
        per_device_train_batch_size=4,
        num_generations=4,
        temperature=0.5,
        max_prompt_length=params.max_prompt_length,
        max_completion_length=params.max_completion_length,
        num_train_epochs=2,
        # max_steps=1024,
        logging_steps=100,
        save_steps=500,
        max_grad_norm=0.1,
        report_to="tensorboard",
        logging_dir="logs/runs",
        output_dir="outputs",
    )

    tokenizer = AutoTokenizer.from_pretrained(params.MODEL_NAME)

    trainer = GRPOTrainer(
        model=params.MODEL_NAME,
        processing_class=tokenizer,
        reward_funcs=[correctness_reward_func, format_reward_func],
        args=training_args,
        train_dataset=gsm8k_train,
        peft_config=peft_config,
    )

    trainer.train()

    merged_model = trainer.model.merge_and_unload()
    tokenizer.save_pretrained(params.OUTPUT_MODEL)
    merged_model.save_pretrained(params.OUTPUT_MODEL)

    close()
