#!/usr/bin/env python3
"""LoRA supervised fine-tuning of the target model on the narrow domain split.

This step exists to create a *mismatched* target: the drafter was trained against
the original model's hidden states, and fine-tuning moves those hidden states.
The adapter is saved separately instead of a merged 52 GB checkpoint, because the
ephemeral disk on the benchmark VM cannot hold a second full copy of the weights.

Loss is computed on assistant tokens only. The prompt part of every sequence is
masked with -100 so the model is not trained to reproduce patient questions.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

from peft import LoraConfig, get_peft_model

IGNORE_INDEX = -100


class DomainDataset(Dataset):
    """Chat-formatted records with the prompt region masked out of the loss."""

    def __init__(self, path: Path, tokenizer, max_length: int, limit: int | None):
        self.samples = []
        self.dropped_long = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                prompt_text = tokenizer.apply_chat_template(
                    [{"role": "user", "content": record["prompt"]}],
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                prompt_ids = tokenizer(prompt_text, add_special_tokens=False).input_ids
                answer_ids = tokenizer(
                    record["response"], add_special_tokens=False
                ).input_ids + [tokenizer.eos_token_id]

                input_ids = prompt_ids + answer_ids
                labels = [IGNORE_INDEX] * len(prompt_ids) + list(answer_ids)
                # Truncating and keeping EOS would teach the model that an answer may end
                # mid-sentence anywhere; drop long samples instead so EOS only follows a
                # complete answer.
                if len(input_ids) > max_length:
                    self.dropped_long += 1
                    continue
                if all(value == IGNORE_INDEX for value in labels):
                    continue
                self.samples.append((input_ids, labels))
                if limit is not None and len(self.samples) >= limit:
                    break

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index):
        return self.samples[index]


def collate(batch, pad_token_id: int):
    width = max(len(item[0]) for item in batch)
    input_ids, labels, attention = [], [], []
    for ids, lab in batch:
        pad = width - len(ids)
        input_ids.append(ids + [pad_token_id] * pad)
        labels.append(lab + [IGNORE_INDEX] * pad)
        attention.append([1] * len(ids) + [0] * pad)
    return (
        torch.tensor(input_ids, dtype=torch.long),
        torch.tensor(labels, dtype=torch.long),
        torch.tensor(attention, dtype=torch.long),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--lora-rank", type=int, default=32)
    parser.add_argument("--lora-alpha", type=int, default=64)
    parser.add_argument("--target-modules", choices=["all", "attention"], default="all",
                        help="attention = q/k/v/o only; all also adapts the MLP projections")
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--log-every", type=int, default=10)
    args = parser.parse_args()

    torch.manual_seed(args.seed)

    tokenizer = AutoTokenizer.from_pretrained(args.target)
    model = AutoModelForCausalLM.from_pretrained(
        args.target, dtype=torch.bfloat16, device_map="cuda"
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    modules = ["q_proj", "k_proj", "v_proj", "o_proj"]
    if args.target_modules == "all":
        modules += ["gate_proj", "up_proj", "down_proj"]
    lora = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=modules,
    )
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(
        json.dumps(
            {
                "trainable_params": trainable,
                "total_params": total,
                "trainable_pct": round(100 * trainable / total, 4),
            }
        ),
        flush=True,
    )

    dataset = DomainDataset(Path(args.data), tokenizer, args.max_length, args.limit)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate(batch, pad_id),
    )

    steps_per_epoch = math.ceil(len(loader) / args.grad_accum)
    total_steps = steps_per_epoch * args.epochs
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0
    )
    scheduler = get_cosine_schedule_with_warmup(optimizer, int(0.03 * total_steps) + 1, total_steps)

    print(
        json.dumps(
            {"sequences": len(dataset), "dropped_long": dataset.dropped_long,
             "optimizer_steps": total_steps, "grad_accum": args.grad_accum,
             "target_modules": modules}
        ),
        flush=True,
    )

    history = []
    started = time.time()
    model.train()
    step = 0
    for epoch in range(args.epochs):
        running, counted = 0.0, 0
        for batch_index, (input_ids, labels, attention) in enumerate(loader):
            input_ids = input_ids.to("cuda")
            labels = labels.to("cuda")
            attention = attention.to("cuda")

            out = model(input_ids=input_ids, attention_mask=attention, labels=labels)
            loss = out.loss / args.grad_accum
            loss.backward()
            running += out.loss.item()
            counted += 1

            if (batch_index + 1) % args.grad_accum == 0 or batch_index + 1 == len(loader):
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0
                )
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                step += 1
                if step % args.log_every == 0 or step == total_steps:
                    mean_loss = running / max(counted, 1)
                    history.append({"step": step, "loss": mean_loss})
                    print(
                        f"step {step}/{total_steps} loss {mean_loss:.4f} "
                        f"lr {scheduler.get_last_lr()[0]:.2e} "
                        f"gpu {torch.cuda.max_memory_allocated() / 2**30:.1f}G "
                        f"elapsed {time.time() - started:.0f}s",
                        flush=True,
                    )
                    running, counted = 0.0, 0

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    (output_dir / "training_summary.json").write_text(
        json.dumps(
            {
                "target": args.target,
                "data": args.data,
                "sequences": len(dataset),
                "epochs": args.epochs,
                "optimizer_steps": total_steps,
                "lr": args.lr,
                "lora_rank": args.lora_rank,
                "lora_alpha": args.lora_alpha,
                "target_modules": modules,
                "dropped_long": dataset.dropped_long,
                "max_length": args.max_length,
                "seed": args.seed,
                "loss_history": history,
                "first_logged_loss": history[0]["loss"] if history else None,
                "last_logged_loss": history[-1]["loss"] if history else None,
                "wall_clock_seconds": round(time.time() - started, 1),
                "peak_gpu_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    saved = sorted(p.name for p in output_dir.iterdir())
    print(json.dumps({"saved_files": saved}, ensure_ascii=False), flush=True)
    print("FINETUNE_TARGET=PASS", flush=True)


if __name__ == "__main__":
    main()
