#!/usr/bin/env python3
"""Create 4 domain-specific dummy LoRA adapters for EXAONE Multi-LoRA testing.

Author: Xinyu Wei
Usage: python3 create_lora_adapters.py --base-model /data/EXAONE-3.5-2.4B-Instruct --output-dir /data
"""
import torch
import os
import json
import argparse
import gc
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer


def create_adapters(base_model_path: str, output_dir: str):
    print("Loading base model on CPU for adapter creation...")
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)

    adapters = [
        {
            "name": "exaone-lora-customer-support",
            "rank": 8,
            "target_modules": ["q_proj", "v_proj"],
            "desc": "Customer service chatbot adapter (lightweight, rank=8)",
        },
        {
            "name": "exaone-lora-code-assistant",
            "rank": 16,
            "target_modules": ["q_proj", "k_proj", "v_proj", "out_proj"],
            "desc": "Code generation assistant (medium, rank=16)",
        },
        {
            "name": "exaone-lora-legal-korean",
            "rank": 32,
            "target_modules": ["q_proj", "v_proj", "c_fc_0"],
            "desc": "Korean legal document processing (large, rank=32)",
        },
        {
            "name": "exaone-lora-medical",
            "rank": 64,
            "target_modules": ["q_proj", "k_proj", "v_proj", "out_proj", "c_fc_0", "c_fc_1"],
            "desc": "Medical NLP specialized adapter (max rank=64)",
        },
    ]

    for i, adapter_cfg in enumerate(adapters):
        save_path = os.path.join(output_dir, adapter_cfg["name"])
        if os.path.exists(save_path):
            print(f"  SKIP {adapter_cfg['name']} already exists")
            continue

        print(f"\nCreating [{i+1}/4] {adapter_cfg['name']} (rank={adapter_cfg['rank']})...")

        model = AutoModelForCausalLM.from_pretrained(
            base_model_path,
            trust_remote_code=True,
            dtype=torch.bfloat16,
            device_map="cpu",
        )

        # Patch get_input_embeddings if not implemented (transformers 5.x issue)
        try:
            model.get_input_embeddings()
        except NotImplementedError:
            model.get_input_embeddings = lambda: model.transformer.wte

        lora_config = LoraConfig(
            r=adapter_cfg["rank"],
            lora_alpha=adapter_cfg["rank"] * 2,
            target_modules=adapter_cfg["target_modules"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )

        peft_model = get_peft_model(model, lora_config)
        trainable = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in peft_model.parameters())
        print(f"  Trainable: {trainable/1e6:.2f}M / {total/1e9:.2f}B ({100*trainable/total:.3f}%)")

        # Simulate training by adding small random perturbations to LoRA weights
        with torch.no_grad():
            for name, param in peft_model.named_parameters():
                if param.requires_grad:
                    param.add_(torch.randn_like(param) * 0.01)

        peft_model.save_pretrained(save_path)
        tokenizer.save_pretrained(save_path)

        files = os.listdir(save_path)
        total_size = sum(os.path.getsize(os.path.join(save_path, f)) for f in files)
        print(f"  OK Saved to {save_path} ({len(files)} files, {total_size/1e6:.1f}MB)")

        del peft_model, model
        gc.collect()

    print("\nAll 4 LoRA adapters summary:")
    for a in adapters:
        p = os.path.join(output_dir, a["name"])
        exists = os.path.exists(p)
        status = "OK" if exists else "FAIL"
        print(f"  [{status}] {a['name']} (rank={a['rank']}, targets={a['target_modules']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create dummy LoRA adapters for EXAONE Multi-LoRA testing")
    parser.add_argument("--base-model", default="/data/EXAONE-3.5-2.4B-Instruct", help="Base model path")
    parser.add_argument("--output-dir", default="/data", help="Output directory for adapters")
    args = parser.parse_args()
    create_adapters(args.base_model, args.output_dir)
