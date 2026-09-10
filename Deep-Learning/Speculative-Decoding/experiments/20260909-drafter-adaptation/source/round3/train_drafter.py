"""Train or re-adapt a DFlash draft model against a frozen target.

The shape contract mirrors dflash_generate and was verified by stage0_gradient_canary.py:
the drafter receives the target's context features for a prefix plus one masked block,
and predicts that block in parallel.

Known gap: this trains the DFlash backbone with the paper's position-weighted
cross-entropy. It does NOT train the DFlash 2 candidate selector, which receives no
gradient from this objective and has no public training implementation.

    python train_drafter.py --smoke
    python train_drafter.py --target <dir> --drafter <dir> --data <jsonl> --output <dir>
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from torch import nn
from transformers import AutoModelForCausalLM, AutoTokenizer, Qwen3Config, Qwen3ForCausalLM

from dflash.model import (
    DFlash2DraftModel,
    _draft_value,
    _output_head,
    _raw_input_embeddings,
    extract_context_feature,
)

SMOKE = {"hidden_size": 128, "intermediate_size": 256, "num_hidden_layers": 5,
         "num_attention_heads": 4, "num_key_value_heads": 2, "head_dim": 32,
         "vocab_size": 512, "target_layers": 8, "block": 8}


def seed_conv_kernels(drafter):
    """`base_kernel` is allocated with torch.empty; a config-built drafter starts from
    uninitialized memory. Identity taps keep the two-tap convolution neutral at step 0."""
    seeded = []
    for name, parameter in drafter.named_parameters():
        if name.endswith("base_kernel"):
            with torch.no_grad():
                parameter.zero_()
                parameter[:, 0, :] = 1.0
            seeded.append(name)
    return seeded


def build_smoke_models(config_path):
    released = json.loads(Path(config_path).read_text(encoding="utf-8"))
    tiny = {key: SMOKE[key] for key in
            ("hidden_size", "intermediate_size", "num_hidden_layers", "num_attention_heads",
             "num_key_value_heads", "head_dim", "vocab_size")}
    target_config = Qwen3Config(
        **{**tiny, "num_hidden_layers": SMOKE["target_layers"]},
        max_position_embeddings=512, tie_word_embeddings=False)
    layer_ids = [round(1 + index * (SMOKE["target_layers"] - 4) / 4) for index in range(5)]
    dropped = {"architectures", "dflash_config", "dtype", "layer_types",
               "transformers_version", "rope_parameters", "_name_or_path"}
    draft_kwargs = {key: value for key, value in released.items() if key not in dropped}
    draft_kwargs.update(tiny)
    draft_kwargs.update(num_target_layers=SMOKE["target_layers"], max_position_embeddings=512,
                        tie_word_embeddings=False)
    draft_config = Qwen3Config(**draft_kwargs)
    draft_config.dflash_config = dict(released["dflash_config"], block_size=SMOKE["block"],
                                      mask_token_id=tiny["vocab_size"] - 1,
                                      target_layer_ids=layer_ids)
    target = Qwen3ForCausalLM(target_config).eval()
    drafter = DFlash2DraftModel(draft_config)
    return target, drafter, layer_ids


def load_models(target_path, drafter_path, device, dtype, adapter_path=None,
                drafter_dtype=None):
    target = AutoModelForCausalLM.from_pretrained(
        target_path, dtype=dtype, device_map=device)
    if adapter_path is not None:
        # The drafter must be adapted to the hidden states of the model that will
        # actually serve. Training against the base weights while the deployed
        # target carries the adapter would measure nothing.
        from peft import PeftModel
        target = PeftModel.from_pretrained(target, str(adapter_path)).merge_and_unload()
    target = target.eval()
    drafter = DFlash2DraftModel.from_pretrained(
        drafter_path, dtype=drafter_dtype or dtype).to(device)
    layer_ids = list(drafter.config.dflash_config["target_layer_ids"])
    return target, drafter, layer_ids


def target_context(target, input_ids, layer_ids):
    """One full-sequence forward; causal masking makes every prefix slice of the
    result identical to a separate prefix-only forward, so all anchors share it."""
    with torch.no_grad():
        states = target(input_ids, output_hidden_states=True).hidden_states
        return extract_context_feature(list(states), layer_ids)


def anchor_loss(target, drafter, input_ids, context_full, anchor, block, gamma, autocast,
                train_selector=False):
    mask_id = drafter.config.dflash_config["mask_token_id"]
    block_ids = torch.full((1, block), mask_id, dtype=torch.long, device=input_ids.device)
    block_ids[0, 0] = input_ids[0, anchor]
    scale = float(_draft_value(drafter.config, "input_embedding_scale", 1.0))
    with torch.no_grad():
        noise = _raw_input_embeddings(target, block_ids, scale)

    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=autocast):
        hidden = drafter(
            position_ids=torch.arange(anchor + block, device=input_ids.device).unsqueeze(0),
            attention_mask=None,
            noise_embedding=noise.to(drafter.dtype),
            target_hidden=context_full[:, :anchor, :].to(drafter.dtype),
            use_cache=False,
        )[:, 1 - block:, :]
        logits = drafter.compute_logits(hidden, _output_head(target))

    labels = input_ids[0, anchor + 1: anchor + block]
    weights = torch.tensor([math.exp(-index / gamma) for index in range(block - 1)],
                           device=logits.device)
    per_token = nn.functional.cross_entropy(logits[0].float(), labels, reduction="none")
    backbone = (per_token * weights).sum() / weights.sum()
    if not train_selector:
        return backbone, None
    selector = selector_loss(drafter, hidden.detach(), logits.detach(), input_ids, anchor, block,
                             weights, autocast)
    return backbone, selector


def selector_loss(drafter, hidden, logits, input_ids, anchor, block, weights, autocast):
    """Teacher-forced version of CandidateSelector.select(): same top-k candidates, same
    bilinear rescoring, but the predecessor is the true previous token instead of the
    chosen one. Positions whose true token is outside the top-k get no gradient because
    the selector cannot recover them at inference either. hidden/logits arrive detached
    so only the selector's own parameters move."""
    sel = drafter.candidate_selector
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=autocast):
        unary, candidates = torch.topk(logits, sel.top_k, dim=-1, sorted=False)   # [1, B-1, k]
        projected = sel.hidden_projection(hidden)                                 # [1, B-1, r]
        predecessors = input_ids[0, anchor: anchor + block - 1]                    # true token before each slot
        truth = input_ids[0, anchor + 1: anchor + block]
        pred_emb = sel.predecessor_codebook(predecessors)                          # [B-1, r]
        succ_emb = sel.successor_codebook(candidates[0])                           # [B-1, k, r]
        pairwise = torch.einsum("pr,pkr->pk", pred_emb * projected[0], succ_emb)
        scores = unary[0].float() + pairwise.float()                              # [B-1, k]
    hit = candidates[0] == truth[:, None]                                          # [B-1, k]
    present = hit.any(dim=-1)
    if not bool(present.any()):
        return scores.sum() * 0.0
    label = hit.float().argmax(dim=-1)
    per_slot = nn.functional.cross_entropy(scores[present], label[present], reduction="none")
    return (per_slot * weights[present]).sum() / weights[present].sum()


def sample_anchors(length, block, count, rng, start=1):
    """Random anchor positions inside [start, length - block). `start` is the first
    completion token so the drafter is never trained to predict the prompt."""
    usable = [position for position in range(max(1, start), length - block)]
    rng.shuffle(usable)
    return sorted(usable[:count])


def train(target, drafter, sequences, layer_ids, args, device):
    # AdamW defaults to weight_decay=0.01, which pulls an already-converged released
    # drafter toward zero on every step. Re-adaptation also needs warmup: hitting
    # converged weights with the full learning rate on step 1 diverges.
    optimizer = torch.optim.AdamW(drafter.parameters(), lr=args.lr,
                                  weight_decay=args.weight_decay)
    total_steps = max(1, args.epochs * len(sequences))
    warmup_steps = max(1, int(args.warmup_fraction * total_steps))

    def lr_at(step):
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return max(0.05, 0.5 * (1.0 + math.cos(math.pi * progress)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_at)
    rng = random.Random(args.seed)
    autocast = device == "cuda" and drafter.dtype == torch.float32
    drafter.train()
    history, selector_history = [], []
    started = time.time()
    for epoch in range(args.epochs):
        for input_ids, completion_start in sequences:
            input_ids = input_ids.to(device)
            anchors = sample_anchors(input_ids.shape[1], args.block, args.anchors_per_sequence,
                                     rng, completion_start)
            if not anchors:
                continue
            context_full = target_context(target, input_ids, layer_ids)
            optimizer.zero_grad(set_to_none=True)
            total, total_sel = 0.0, 0.0
            for anchor in anchors:
                backbone, selector = anchor_loss(target, drafter, input_ids, context_full, anchor,
                                                 args.block, args.gamma, autocast, args.train_selector)
                loss = backbone / len(anchors)
                if selector is not None:
                    loss = loss + args.selector_weight * selector / len(anchors)
                    total_sel += float(selector.detach()) / len(anchors)
                loss.backward()
                total += float(backbone.detach()) / len(anchors)
            torch.nn.utils.clip_grad_norm_(drafter.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            history.append(round(total, 4))
            if args.train_selector:
                selector_history.append(round(total_sel, 4))
            if len(history) % 50 == 0:
                print(json.dumps({"step": len(history), "loss_50": round(sum(history[-50:]) / 50, 4),
                                  "selector_loss_50": round(sum(selector_history[-50:]) / 50, 4)
                                  if selector_history else None,
                                  "lr": scheduler.get_last_lr()[0],
                                  "sec_per_step": round((time.time() - started) / len(history), 2),
                                  "gpu_gib": round(torch.cuda.max_memory_allocated() / 2**30, 1)
                                  if device == "cuda" else None}), flush=True)
        window = max(1, len(sequences) // 10)
        print(json.dumps({"epoch": epoch, "steps": len(history),
                          "loss_first_window": round(sum(history[:window]) / window, 4),
                          "loss_last_window": round(sum(history[-window:]) / window, 4),
                          "selector_first_window": round(sum(selector_history[:window]) / window, 4)
                          if selector_history else None,
                          "selector_last_window": round(sum(selector_history[-window:]) / window, 4)
                          if selector_history else None,
                          "lr": scheduler.get_last_lr()[0]}), flush=True)
    drafter.selector_history = selector_history
    return history


def load_sequences(path, tokenizer, max_length, limit):
    """Each JSONL record needs a `text` field holding a chat-formatted prompt plus the
    target's own response. The completion start is the token after the last
    `<|im_start|>`; anchors before it would train the drafter on the user's prompt."""
    im_start = tokenizer.convert_tokens_to_ids("<|im_start|>")
    sequences = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        text = json.loads(line)["text"]
        ids = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).input_ids
        hits = (ids[0] == im_start).nonzero(as_tuple=True)[0]
        completion_start = int(hits[-1]) + 1 if hits.numel() else 1
        if ids.shape[1] - completion_start > 2 * SMOKE["block"]:
            sequences.append((ids, completion_start))
        if len(sequences) >= limit:
            break
    return sequences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Tiny CPU run, no downloads")
    parser.add_argument("--config", type=Path, default=Path("dflash2-config.json"))
    parser.add_argument("--target", type=Path)
    parser.add_argument("--adapter", type=Path, default=None,
                        help="LoRA adapter merged into the target before training")
    parser.add_argument("--drafter", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=6e-4)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--warmup-fraction", type=float, default=0.05)
    parser.add_argument("--gamma", type=float, default=7.0)
    parser.add_argument("--block", type=int, default=8)
    parser.add_argument("--anchors-per-sequence", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--drafter-dtype", choices=["bfloat16", "float32"], default="bfloat16",
                        help="float32 keeps fp32 master weights and runs the forward under "
                             "bf16 autocast; bf16 params quantize small AdamW updates away")
    parser.add_argument("--train-selector", action="store_true",
                        help="also train the DFlash 2 candidate selector with a teacher-forced "
                             "top-k cross-entropy that mirrors CandidateSelector.select()")
    parser.add_argument("--selector-weight", type=float, default=1.0)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    if args.smoke:
        device, dtype = "cpu", torch.float32
        target, drafter, layer_ids = build_smoke_models(args.config)
        seeded = seed_conv_kernels(drafter)
        args.block, args.epochs, args.anchors_per_sequence = SMOKE["block"], 2, 3
        sequences = [(torch.randint(0, SMOKE["vocab_size"] - 1, (1, 64)), 1) for _ in range(4)]
        print(json.dumps({"mode": "smoke", "conv_kernels_seeded": len(seeded),
                          "target_layer_ids": layer_ids, "sequences": len(sequences)}))
    else:
        for required in ("target", "drafter", "data", "output"):
            if getattr(args, required) is None:
                parser.error(f"--{required} is required unless --smoke is set")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device == "cuda" else torch.float32
        drafter_dtype = getattr(torch, args.drafter_dtype) if device == "cuda" else torch.float32
        target, drafter, layer_ids = load_models(args.target, args.drafter, device, dtype,
                                                 args.adapter, drafter_dtype)
        tokenizer = AutoTokenizer.from_pretrained(args.target)
        sequences = load_sequences(args.data, tokenizer, args.max_length, args.limit)
        completion_tokens = sum(ids.shape[1] - start for ids, start in sequences)
        print(json.dumps({"mode": "train", "device": device, "sequences": len(sequences),
                          "completion_tokens": completion_tokens,
                          "drafter_dtype": str(drafter.dtype),
                          "adapter": str(args.adapter) if args.adapter else None,
                          "target_layer_ids": layer_ids}))

    target.requires_grad_(False)
    train_started = time.time()
    history = train(target, drafter, sequences, layer_ids, args, device)

    # Single-sequence endpoints are noise; compare averaged windows instead.
    window = max(1, len(history) // 10)
    first_window = sum(history[:window]) / window
    last_window = sum(history[-window:]) / window
    checks = {"loss_finite": all(math.isfinite(value) for value in history),
              "loss_decreased": last_window < first_window}
    if args.output:
        # Ship the checkpoint in the released bf16 format regardless of training dtype.
        drafter = drafter.to(torch.bfloat16) if device == "cuda" else drafter
        args.output.mkdir(parents=True, exist_ok=True)
        drafter.save_pretrained(args.output)
        reloaded = DFlash2DraftModel.from_pretrained(args.output)
        checks["checkpoint_reloads"] = all(
            torch.equal(saved.cpu(), original.detach().cpu())
            for saved, original in zip(reloaded.state_dict().values(), drafter.state_dict().values()))
        (args.output / "training-history.json").write_text(
            json.dumps({"history": history,
                        "selector_history": getattr(drafter, "selector_history", []),
                        "args": {k: str(v) for k, v in vars(args).items()}},
                       indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"loss_first_window": round(first_window, 4),
                      "loss_last_window": round(last_window, 4), "steps": len(history),
                      "sec_per_step": round((time.time() - train_started) / max(1, len(history)), 2),
                      "peak_gpu_gib": round(torch.cuda.max_memory_allocated() / 2**30, 1)
                      if device == "cuda" else None, "checks": checks}))
    print("TRAIN=" + ("PASS" if all(checks.values()) else "FAIL"))
    raise SystemExit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
