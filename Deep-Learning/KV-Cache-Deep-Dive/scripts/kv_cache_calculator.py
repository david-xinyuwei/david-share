#!/usr/bin/env python3
"""
KV Cache Size Calculator — Supports GQA, MLA, and Hybrid architectures.

Fetches model config from HuggingFace and computes KV cache memory
for a given context length, batch size, and data type.

Author: 魏新宇 (Xinyu Wei)
"""

import argparse
import json
import sys
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)

HF_CONFIG_URL = "https://huggingface.co/{model_id}/raw/main/config.json"


def fetch_config(model_id: str) -> Dict[str, Any]:
    """Fetch config.json from HuggingFace Hub."""
    url = HF_CONFIG_URL.format(model_id=model_id)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def detect_architecture(cfg: Dict[str, Any]) -> str:
    """Auto-detect model architecture type for KV cache calculation."""
    text_cfg = cfg.get("text_config", cfg)

    if "kv_lora_rank" in text_cfg:
        return "mla"
    if "hybrid_override_pattern" in cfg:
        return "hybrid_mamba"
    if "layer_types" in text_cfg or "full_attention_interval" in text_cfg:
        return "hybrid_attention"
    return "gqa"


def count_attention_layers_hybrid_attn(cfg: Dict[str, Any]) -> int:
    """Count full-attention layers in hybrid linear+attention models (e.g. Qwen3.5)."""
    text_cfg = cfg.get("text_config", cfg)
    layer_types = text_cfg.get("layer_types", [])
    if layer_types:
        return sum(1 for x in layer_types if x == "full_attention")
    num_layers = int(text_cfg["num_hidden_layers"])
    interval = int(text_cfg.get("full_attention_interval", 1))
    return num_layers // interval


def count_attention_layers_hybrid_mamba(cfg: Dict[str, Any]) -> int:
    """Count attention layers in hybrid Mamba+Attention models (e.g. Nemotron)."""
    pattern = cfg.get("hybrid_override_pattern", "")
    if pattern:
        return pattern.count("*")
    raise ValueError("No hybrid_override_pattern found.")


def compute_kv_cache(
    cfg: Dict[str, Any],
    context_length: int = 32768,
    batch_size: int = 1,
    dtype_bytes: int = 2,
) -> Dict[str, Any]:
    """Compute KV cache size for any supported architecture."""
    arch = detect_architecture(cfg)
    text_cfg = cfg.get("text_config", cfg)
    result = {"architecture": arch}

    if arch == "mla":
        layers = int(text_cfg["num_hidden_layers"])
        kv_lora_rank = int(text_cfg["kv_lora_rank"])
        qk_rope_head_dim = int(text_cfg["qk_rope_head_dim"])
        latent_width = kv_lora_rank + qk_rope_head_dim
        per_token = layers * latent_width * dtype_bytes
        result.update({
            "layers": layers,
            "kv_lora_rank": kv_lora_rank,
            "qk_rope_head_dim": qk_rope_head_dim,
            "latent_width": latent_width,
            "formula": "L × (kv_lora_rank + qk_rope_head_dim) × bytes",
        })

    elif arch == "hybrid_mamba":
        attn_layers = count_attention_layers_hybrid_mamba(cfg)
        total_layers = int(text_cfg["num_hidden_layers"])
        num_kv_heads = int(text_cfg["num_key_value_heads"])
        head_dim = int(text_cfg["head_dim"])
        per_token = attn_layers * 2 * num_kv_heads * head_dim * dtype_bytes
        result.update({
            "total_layers": total_layers,
            "attention_layers": attn_layers,
            "num_kv_heads": num_kv_heads,
            "head_dim": head_dim,
            "formula": "L_attn × 2 × H_kv × D × bytes",
            "note": "Only attention layers have KV cache; Mamba layers use recurrent state.",
        })

    elif arch == "hybrid_attention":
        attn_layers = count_attention_layers_hybrid_attn(cfg)
        total_layers = int(text_cfg["num_hidden_layers"])
        num_kv_heads = int(text_cfg["num_key_value_heads"])
        head_dim = int(text_cfg["head_dim"])
        per_token = attn_layers * 2 * num_kv_heads * head_dim * dtype_bytes
        result.update({
            "total_layers": total_layers,
            "attention_layers": attn_layers,
            "num_kv_heads": num_kv_heads,
            "head_dim": head_dim,
            "formula": "L_attn × 2 × H_kv × D × bytes",
            "note": "Only full-attention layers have KV cache; linear-attention layers do not.",
        })

    else:  # standard GQA
        layers = int(text_cfg["num_hidden_layers"])
        num_kv_heads = int(text_cfg["num_key_value_heads"])
        head_dim = int(text_cfg["head_dim"])
        per_token = layers * 2 * num_kv_heads * head_dim * dtype_bytes
        result.update({
            "layers": layers,
            "num_kv_heads": num_kv_heads,
            "head_dim": head_dim,
            "formula": "L × 2 × H_kv × D × bytes",
        })

    total_bytes = per_token * context_length * batch_size
    result.update({
        "per_token_bytes": per_token,
        "per_token_kib": per_token / 1024,
        "context_length": context_length,
        "batch_size": batch_size,
        "dtype_bytes": dtype_bytes,
        "total_bytes": total_bytes,
        "total_gib": total_bytes / (1024**3),
        "total_gb": total_bytes / 1e9,
    })
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Calculate KV cache size for any HuggingFace model."
    )
    parser.add_argument("model_id", help="HuggingFace model ID (e.g. Qwen/Qwen3-8B)")
    parser.add_argument("--context-length", type=int, default=32768, help="Context length in tokens")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size (concurrent sequences)")
    parser.add_argument("--dtype-bytes", type=int, default=2, choices=[1, 2, 4],
                        help="Bytes per element: 2=BF16/FP16, 1=FP8/INT8, 4=FP32")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print(f"Fetching config for {args.model_id}...")
    cfg = fetch_config(args.model_id)
    result = compute_kv_cache(cfg, args.context_length, args.batch_size, args.dtype_bytes)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Model: {args.model_id}")
        print(f"Architecture: {result['architecture']}")
        print(f"{'='*60}")
        for k, v in result.items():
            if k in ("architecture",):
                continue
            print(f"  {k:>25}: {v}")
        print(f"\n  >>> KV Cache = {result['total_gib']:.4f} GiB "
              f"({result['total_gb']:.4f} GB) "
              f"for {args.context_length} tokens, batch={args.batch_size}")


if __name__ == "__main__":
    main()
