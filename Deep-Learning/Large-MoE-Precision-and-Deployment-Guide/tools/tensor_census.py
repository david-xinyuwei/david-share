#!/usr/bin/env python3
"""07_tensor_census.py <snapshot_dir> <out_json>
Per-tensor dtype census read directly from safetensors headers (no torch, no GPU).
Groups tensors by component so the repo's component tables can cite observed storage dtypes.
"""
import json, os, re, struct, sys, collections

snap, out = sys.argv[1], sys.argv[2]
DT_BYTES = {"BF16": 2, "F16": 2, "F32": 4, "F64": 8, "F8_E4M3": 1, "F8_E5M2": 1, "U8": 1, "I8": 1, "I32": 4, "I64": 8, "BOOL": 1, "F4": 0.5}

RULES = [  # (component label, regex on tensor name) — first match wins
    ("mtp",                  r"^mtp\.|\.mtp\.|nextn|draft"),
    ("embedding",            r"embed_tokens|embeddings\.weight|wte|tok_embeddings|embedding\.|llm\.embed\.weight"),
    ("lm_head",              r"lm_head|output\.weight$|final_logits|unembed"),
    ("vision_audio_encoder", r"model\.visual\.|model\.audio\.|vision|image|encoder\.|projector|perception"),
    ("norm_bias_scale",      r"norm|ln_|layernorm|rmsnorm|\.bias$|_scale$|input_scale|weight_scale"),
    ("router_gate",          r"\.gate\.(weight|bias)$|router|\.gate_proj_router|expert_bias|e_score"),
    ("shared_expert",        r"shared_expert|shared_mlp|shared_experts|shared_w13|shared_w2"),
    ("routed_expert",        r"experts\.|\.experts\b|w13_weight|w2_weight|gate_up_proj|down_proj.*expert"),
    ("latent_proj",          r"latent|fc_in_latent|fc_out_latent|moe_in|moe_out|up_proj_latent|down_proj_latent"),
    ("mamba_conv_state",     r"mixer\.(conv1d|A_log|D|dt_bias)|\.A_log|\.D$|dt_bias|conv1d"),
    ("mamba_proj",           r"mixer\.(in_proj|out_proj)"),
    ("short_conv",           r"sconv|short_conv|shortconv"),
    ("attention_proj",       r"attn|attention|q_proj|k_proj|v_proj|o_proj|qkv|out_proj|wqkv|wo\.weight"),
    ("dense_mlp",            r"mlp\.(gate_proj|up_proj|down_proj|fc1|fc2|w1|w2|w3|w13|w2_md|w13_md)"),
]

census = collections.defaultdict(lambda: collections.defaultdict(lambda: {"tensors": 0, "elements": 0, "bytes": 0}))
total = {"files": 0, "tensors": 0, "bytes": 0}
examples = collections.defaultdict(dict)
unmatched = collections.Counter()

for fn in sorted(os.listdir(snap)):
    if not fn.endswith(".safetensors"):
        continue
    p = os.path.join(snap, fn)
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n))
    total["files"] += 1
    for name, meta in hdr.items():
        if name == "__metadata__":
            continue
        dt = meta["dtype"]; shape = meta["shape"]
        el = 1
        for s in shape: el *= s
        b = meta["data_offsets"][1] - meta["data_offsets"][0]
        comp = "other"
        for label, rx in RULES:
            if re.search(rx, name):
                comp = label; break
        if comp == "other":
            unmatched[re.sub(r"\d+", "N", name)] += 1
        c = census[comp][dt]; c["tensors"] += 1; c["elements"] += el; c["bytes"] += b
        total["tensors"] += 1; total["bytes"] += b
        if dt not in examples[comp]:
            examples[comp][dt] = {"name": name, "shape": shape}

result = {
    "snapshot_dir": snap,
    "total": total,
    "by_component": {k: dict(v) for k, v in census.items()},
    "component_examples": examples,
    "unmatched_patterns_top": unmatched.most_common(25),
}
with open(out, "w") as f:
    json.dump(result, f, indent=1)
print(f"CENSUS_DONE files={total['files']} tensors={total['tensors']} bytes={total['bytes']} out={out}")
for comp, dts in sorted(census.items()):
    print(comp, {dt: f"{v['bytes']/1e9:.1f}GB/{v['tensors']}t" for dt, v in dts.items()})
