"""
This module contains all the configurations files and functions for GRPO training
"""

import os
import gc
import warnings
import contextlib
import torch
from huggingface_hub import login
from datasets import load_dataset, Dataset
from vllm.distributed.parallel_state import (
    destroy_model_parallel,
    destroy_distributed_environment,
)

R1_STYLE_SYSTEM_PROMPT = """A conversation between User and Assistant. The user asks a question, and the Assistant solves it.
The assistant first thinks about the reasoning process in the mind and then provides the user
with the answer."""

TASK_SPECIFIC_INSTRUCTIONS = """The reasoning process and answer are enclosed within tags.The answer must be a single integer."""

EXAMPLE = """<reasoning>
</reasoning>
<answer>
</answer>"""

XML_COT_FORMAT = """\
<reasoning>
{reasoning}
</reasoning>
<answer>
{answer}
</answer>
"""

SYSTEM_PROMPT = (
    R1_STYLE_SYSTEM_PROMPT + "\n\n" + TASK_SPECIFIC_INSTRUCTIONS + "\n" + EXAMPLE + "\n"
)


class Config:
    """Configuration parameters"""

    MODEL_NAME = "Google/gemma-2-2b-it"
    OUTPUT_MODEL = "gemma-2-2b-it-grpo"

    max_prompt_length = 256
    max_completion_length = 256


def init():
    """Initialization script"""
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

    token = os.environ.get("HF_TOKEN")
    login(token=token)

    torch.cuda.empty_cache()
    gc.collect()
    warnings.filterwarnings("ignore")


def close(llm=None):
    """Close vllm"""
    destroy_model_parallel()
    destroy_distributed_environment()
    if llm:
        del llm.llm_engine.model_executor
        del llm
    with contextlib.suppress(AssertionError):
        torch.distributed.destroy_process_group()
    gc.collect()
    torch.cuda.empty_cache()


def is_bfloat16_supported():
    """Checks if the current device supports bfloat16."""
    return torch.cuda.is_available() and torch.cuda.get_device_capability(0)[0] >= 8


def info_device():
    """Get device for PyTorch"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    return device


def extract_hash_answer(text: str) -> str | None:
    """Extract numeric answer from GSM8K example"""
    if "####" not in text:
        return None
    return text.split("####")[1].strip()


def get_gsm8k_questions(split="train"):
    """Upload GSM8k dataset"""
    data = load_dataset("openai/gsm8k", "main", cache_dir="/tmp")[split]
    data = data.map(
        lambda x: {
            "prompt": [
                {"role": "user", "content": SYSTEM_PROMPT + "\n" + x["question"]},
            ],
            "answer": extract_hash_answer(x["answer"]),
        }
    )
    return data


def get_limo(split="train"):
    """Upload GAIR/LIMO dataset"""
    data = load_dataset("GAIR/LIMO", cache_dir="/tmp")[split]
    data = data.map(
        lambda x: {
            "prompt": "\n".join(
                [
                    x["question"],
                    R1_STYLE_SYSTEM_PROMPT,
                    "<reasoning>",
                    x["solution"],
                    "</reasoning>",
                    "<answer>",
                    x["answer"],
                    "<answer>",
                ]
            )
        }
    )
    return data


def get_splitted_limo(tokenizer, split="train", max_length=4096, overlap_chars=1024):
    """Load GAIR/LIMO dataset and split long texts into overlapping chunks of max_length tokens."""

    data = load_dataset("GAIR/LIMO", cache_dir="/tmp")[split]

    examples = []
    for example in data:

        # Format text as a single string
        text = "\n".join(
            [
                example["question"],
                "<reasoning>",
                example["solution"],
                "</reasoning>",
                "<answer>",
                example["answer"],
                "</answer>",
            ]
        )

        # Tokenize without truncation
        input_ids = tokenizer.encode(text, truncation=False, add_special_tokens=False)

        for i in range(0, len(input_ids), max_length - overlap_chars):
            chunk = input_ids[i : i + max_length]
            examples.append(tokenizer.decode(chunk))

    dataset = Dataset.from_dict({"prompt": examples})
    return dataset


if __name__ == "__main__":
    pass
