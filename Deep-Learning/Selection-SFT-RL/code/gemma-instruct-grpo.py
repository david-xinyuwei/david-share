"""
Training instructions for instruct SFT on LIMO and RL GRPO on GSM8K
"""

import re
import gc
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from trl import GRPOConfig, GRPOTrainer, SFTConfig, SFTTrainer
from peft import LoraConfig

from config import (
    init,
    close,
    is_bfloat16_supported,
    get_gsm8k_questions,
    get_limo,
    Config,
)


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

    peft_config = LoraConfig(
        r=64,
        lora_alpha=64,
        lora_dropout=0,
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

    sft_training_args = SFTConfig(
        # Model parameters
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        max_seq_length=8192 // 2,
        # Optimization parameters
        optim="adamw_8bit",
        learning_rate=2e-4,
        weight_decay=0.01,
        max_grad_norm=0.3,
        lr_scheduler_type="linear",
        # Training schedule parameters
        num_train_epochs=1,
        # max_steps=6,
        warmup_ratio=0.05,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=2,
        # Dataset handling
        remove_unused_columns=False,
        label_names=[],
        dataset_num_proc=4,
        packing=False,
        # Checkpointing and logging
        save_steps=100,
        report_to="tensorboard",
        logging_dir="logs/sft_runs",
        output_dir="sft_output",
        overwrite_output_dir=True,
        # Reproducibility
        seed=0,
    )

    model = AutoModelForCausalLM.from_pretrained(
        params.MODEL_NAME,
        torch_dtype=torch.bfloat16,
        attn_implementation="eager",
        device_map="auto",
    )
    model.config.use_cache = False  # Disable caching

    tokenizer = AutoTokenizer.from_pretrained(params.MODEL_NAME)

    limo_train = get_limo(split="train")

    def formatting_func(example):
        """Formatting function for LIMO"""
        return example["prompt"]

    sft_trainer = SFTTrainer(
        model=model,
        args=sft_training_args,
        train_dataset=limo_train,
        peft_config=peft_config,
        formatting_func=formatting_func,
    )

    print(
        "\n",
        "*" * 16,
        "SFT Fine-Tuning on LIMO",
        "*" * 16,
    )
    sft_trainer.train()

    del sft_trainer
    del sft_training_args
    del limo_train
    for _ in range(10):
        torch.cuda.empty_cache()
        gc.collect()

    gsm8k_train = get_gsm8k_questions(split="train")

    training_args = GRPOConfig(
        # Model parameters
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        max_prompt_length=params.max_prompt_length,
        max_completion_length=params.max_completion_length,
        # Optimization parameters
        optim="adamw_8bit",
        learning_rate=1e-5,
        adam_beta1=0.9,
        adam_beta2=0.99,
        weight_decay=0.1,
        lr_scheduler_type="cosine",
        max_grad_norm=0.1,
        warmup_ratio=0.05,
        beta=0.005,  # divergence coefficient
        # Training schedule parameters
        num_train_epochs=2,
        max_steps=1024,  ### TESTING
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        # Generation parameters
        num_generations=4,
        temperature=0.5,
        # VLLM inference parameters
        use_vllm=True,  # use vLLM for fast inference!
        vllm_device="cuda:0",
        vllm_gpu_memory_utilization=0.35,
        vllm_max_model_len=params.max_prompt_length + params.max_completion_length,
        # Checkpointing and logging
        logging_steps=100,
        save_steps=500,
        report_to="tensorboard",
        logging_dir="logs/grpo_runs",
        output_dir="grpo_output",
        overwrite_output_dir=True,
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[correctness_reward_func, format_reward_func],
        args=training_args,
        train_dataset=gsm8k_train,
        peft_config=peft_config,
    )

    print(
        "\n",
        "*" * 16,
        "RL Fine-Tuning on GSM8K",
        "*" * 16,
    )
    trainer.train()

    merged_model = trainer.model.merge_and_unload()
    tokenizer.save_pretrained(params.OUTPUT_MODEL)
    merged_model.save_pretrained(params.OUTPUT_MODEL)

    close()
