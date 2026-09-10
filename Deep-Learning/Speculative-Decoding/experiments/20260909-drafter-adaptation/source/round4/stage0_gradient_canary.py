"""Stage 0 canary: prove a DFlash draft-model training step is implementable.

Mirrors the shape contract of dflash_generate: the drafter sees the target's context
features for the prefix plus one masked block, and predicts that block in parallel.
Builds a tiny target and drafter from the released DFlash 2 config shape, then checks
that a weighted cross-entropy step produces gradients only on the drafter.
"""

import argparse
import json
import math
from pathlib import Path

import torch
from torch import nn
from transformers import Qwen3Config, Qwen3ForCausalLM

from dflash.model import (
    DFlash2DraftModel,
    _draft_value,
    _output_head,
    _raw_input_embeddings,
    extract_context_feature,
)

TINY = {"hidden_size": 128, "intermediate_size": 256, "num_hidden_layers": 5,
        "num_attention_heads": 4, "num_key_value_heads": 2, "head_dim": 32, "vocab_size": 512}
TARGET_LAYERS = 8
BLOCK = 8
GAMMA = 7.0
SEQUENCE = 64
ANCHOR = 32


def build_configs(released):
    target = Qwen3Config(
        hidden_size=TINY["hidden_size"], intermediate_size=TINY["intermediate_size"],
        num_hidden_layers=TARGET_LAYERS, num_attention_heads=TINY["num_attention_heads"],
        num_key_value_heads=TINY["num_key_value_heads"], head_dim=TINY["head_dim"],
        vocab_size=TINY["vocab_size"], max_position_embeddings=512, tie_word_embeddings=False,
    )
    layer_ids = [round(1 + index * (TARGET_LAYERS - 4) / 4) for index in range(5)]
    dropped = {"architectures", "dflash_config", "dtype", "layer_types",
               "transformers_version", "rope_parameters", "_name_or_path"}
    draft_kwargs = {key: value for key, value in released.items() if key not in dropped}
    draft_kwargs.update(TINY)
    draft_kwargs.update(num_target_layers=TARGET_LAYERS, max_position_embeddings=512,
                        tie_word_embeddings=False)
    draft = Qwen3Config(**draft_kwargs)
    draft.dflash_config = dict(released["dflash_config"], block_size=BLOCK,
                               mask_token_id=TINY["vocab_size"] - 1, target_layer_ids=layer_ids)
    return target, draft, layer_ids


def initialize_conv_kernels(drafter):
    """`GroupedDynamicCausalConv.base_kernel` is `torch.empty`, so a config-built model
    starts from uninitialized memory. Released checkpoints overwrite it; training from
    scratch must seed it. Identity taps keep the conv neutral at step 0."""
    seeded = []
    for name, parameter in drafter.named_parameters():
        if name.endswith("base_kernel"):
            with torch.no_grad():
                parameter.zero_()
                parameter[:, 0, :] = 1.0
            seeded.append(name)
    return seeded


def training_step(target, drafter, input_ids, layer_ids, anchor):
    """One masked block predicted in parallel from the target's prefix features."""
    with torch.no_grad():
        states = target(input_ids[:, :anchor], output_hidden_states=True).hidden_states
    context = extract_context_feature(list(states), layer_ids)

    mask_id = drafter.config.dflash_config["mask_token_id"]
    block_ids = torch.full((1, BLOCK), mask_id, dtype=torch.long)
    block_ids[0, 0] = input_ids[0, anchor]
    scale = float(_draft_value(drafter.config, "input_embedding_scale", 1.0))
    noise = _raw_input_embeddings(target, block_ids, scale).detach()

    hidden = drafter(
        position_ids=torch.arange(anchor + BLOCK).unsqueeze(0),
        attention_mask=None,
        noise_embedding=noise,
        target_hidden=context,
        use_cache=False,
    )[:, 1 - BLOCK:, :]

    logits = drafter.compute_logits(hidden, _output_head(target))
    labels = input_ids[0, anchor + 1: anchor + BLOCK]
    weights = torch.tensor([math.exp(-index / GAMMA) for index in range(BLOCK - 1)])
    per_token = nn.functional.cross_entropy(logits[0].float(), labels, reduction="none")
    return (per_token * weights).sum() / weights.sum()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Released DFlash 2 config.json")
    parser.add_argument("--steps", type=int, default=30)
    args = parser.parse_args()

    torch.manual_seed(0)
    released = json.loads(args.config.read_text(encoding="utf-8"))
    target_config, draft_config, layer_ids = build_configs(released)

    target = Qwen3ForCausalLM(target_config).eval()
    target.requires_grad_(False)
    drafter = DFlash2DraftModel(draft_config).train()
    seeded = initialize_conv_kernels(drafter)

    print(json.dumps({
        "target_layer_ids": layer_ids,
        "context_dim": len(layer_ids) * TINY["hidden_size"],
        "drafter_fc_in": drafter.fc.in_features, "drafter_fc_out": drafter.fc.out_features,
        "drafter_params": sum(p.numel() for p in drafter.parameters()),
        "conv_kernels_seeded": seeded,
    }))

    input_ids = torch.randint(0, TINY["vocab_size"] - 1, (1, SEQUENCE))
    optimizer = torch.optim.AdamW(drafter.parameters(), lr=6e-4)
    history = []
    groups = {}
    for step in range(args.steps):
        loss = training_step(target, drafter, input_ids, layer_ids, ANCHOR)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        if step == 0:
            for name, parameter in drafter.named_parameters():
                key = name.split(".")[0]
                trained = parameter.grad is not None and bool(parameter.grad.abs().sum() > 0)
                groups[key] = groups.get(key, False) or trained
            print(json.dumps({"drafter_grad_by_group": groups,
                              "target_params_with_grad": sum(
                                  1 for p in target.parameters() if p.grad is not None)}))
        torch.nn.utils.clip_grad_norm_(drafter.parameters(), 1.0)
        optimizer.step()
        history.append(round(loss.item(), 4))

    checks = {
        "loss_finite": all(math.isfinite(value) for value in history),
        "loss_decreased": history[-1] < history[0],
        "target_frozen": all(p.grad is None for p in target.parameters()),
        "backbone_trained": groups.get("layers", False) and groups.get("fc", False),
    }
    print(json.dumps({"loss_first": history[0], "loss_last": history[-1],
                      "loss_every_5": history[::5], "checks": checks}))
    print("STAGE0=" + ("PASS" if all(checks.values()) else "FAIL"))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
