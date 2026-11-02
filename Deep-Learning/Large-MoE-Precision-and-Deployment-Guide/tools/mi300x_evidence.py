#!/usr/bin/env python3
"""Project a private MI300X evidence directory into the public data/mi300x-run/ set and summarize it.

    python3 tools/mi300x_evidence.py project <private_evidence_dir> <tag>   # writes data/mi300x-run/<tag>/
    python3 tools/mi300x_evidence.py summarize                            # rewrites data/mi300x-run/summary.json
    python3 tools/mi300x_evidence.py table                                # prints the summary as Markdown

`project` copies the small raw artifacts (00_meta.txt, 01_models.json, *_request.json, *_response.json,
04_rocm_smi_vram.json, 05_server_keylines.log, 08_perf.json) and replaces host names, private IPs and the login user
with role labels. Full container logs and Ray worker logs stay private because of size; their SHA-256 values are kept
in SHA256SUMS.private.txt so the public summary can be matched against them.

`summarize` reads every data/mi300x-run/<tag>/ directory and extracts, from the raw files only, the numbers that the
README and VALIDATION pages quote: kernels/backends selected, weights per GPU, KV cache budget, smoke request wall
clock, token usage and finish reasons, and — when scripts/mi300x/09_perf_probe.py was run — the TTFT / decode
throughput medians per concurrency level. tests/mi300x.test.mjs asserts the documents against this file, so a quoted
number cannot drift from the evidence without a failing test.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "mi300x-run"
SMALL = ("00_meta.txt", "01_models.json", "04_rocm_smi_vram.json", "05_server_keylines.log", "08_perf.json")
# Private identifiers observed in the 2026-11-02 run -> public role labels. Extend when a new environment is used.
REDACT = [
    (re.compile(r"mi3007ca7000000"), "node0"),
    (re.compile(r"mi3007ca7000001"), "node1"),
    (re.compile(r"\b10\.0\.0\.5\b"), "<node0-private-ip>"),
    (re.compile(r"\b10\.0\.0\.4\b"), "<node1-private-ip>"),
    (re.compile(r"/home/azureuser"), "$MOE_ROOT/.."),
    (re.compile(r"\bazureuser\b"), "<login-user>"),
    (re.compile(r"\x1b\[[0-9;]*m"), ""),
]
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def redact(text: str) -> str:
    for pattern, replacement in REDACT:
        text = pattern.sub(replacement, text)
    return text


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def project(src: Path, tag: str) -> Path:
    dst = PUBLIC / tag
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(src.iterdir()):
        if not path.is_file():
            continue
        if path.name in SMALL or re.match(r"\d\d_smoke\d?_(request|response)\.json$", path.name):
            if path.stat().st_size == 0:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            (dst / path.name).write_text(redact(text), encoding="utf-8", newline="\n")
            copied.append(path.name)
    private = []
    for path in sorted(src.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt" and path.name not in copied:
            private.append(f"{sha256(path)}  {path.relative_to(src).as_posix()}")
    (dst / "SHA256SUMS.private.txt").write_text("\n".join(private) + "\n", encoding="utf-8", newline="\n")
    (dst / "PROJECTION.json").write_text(json.dumps({
        "source_tag": tag,
        "public_files": copied,
        "private_files_hashed": len(private),
        "redaction": "host names -> node0/node1, private IPs -> <nodeN-private-ip>, login user -> <login-user>, ANSI colour removed",
        "note": "Full container logs and Ray worker logs are kept in the author's private evidence directory; "
                "their SHA-256 values are listed in SHA256SUMS.private.txt.",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return dst


def _first(pattern: str, text: str, group: int = 1, cast=str):
    m = re.search(pattern, text, flags=re.M)
    return cast(m.group(group)) if m else None


def _all(pattern: str, text: str, cast=str):
    return [cast(x) for x in re.findall(pattern, text, flags=re.M)]


def summarize_tag(tag_dir: Path) -> dict:
    meta = (tag_dir / "00_meta.txt").read_text(encoding="utf-8")
    key = ANSI.sub("", (tag_dir / "05_server_keylines.log").read_text(encoding="utf-8", errors="replace"))
    out: dict = {"tag": tag_dir.name}
    out["evidence_start_utc"] = _first(r"^EVIDENCE_START=(\S+)", meta)
    out["image"] = _first(r"image=(\S+)", meta)
    out["image_id"] = _first(r"imageid=(sha256:[0-9a-f]+)", meta)
    out["rocm_host"] = _first(r"rocm_host=(\S+)", meta)
    out["kernel"] = _first(r"kernel=(\S+)", meta)
    # `args=` may span several lines (the two-node launcher is a bash -lc script); it ends at the models_http line.
    m = re.search(r"args=(.*?)\nmodels_http=", meta.replace("\r", ""), flags=re.S)
    args = " ".join((m.group(1) if m else "").split())
    out["served_model_name"] = _first(r"--served-model-name (\S+)", args)
    out["revision"] = _first(r"--revision (\S+)", args)
    out["tensor_parallel_size"] = _first(r"--tensor-parallel-size (\d+)", args, cast=int)
    out["pipeline_parallel_size"] = _first(r"--pipeline-parallel-size (\d+)", args, cast=int)
    out["data_parallel_size"] = _first(r"--data-parallel-size (\d+)", args, cast=int)
    out["expert_parallel"] = "--enable-expert-parallel" in args
    out["max_model_len"] = _first(r"--max-model-len (\d+)", args, cast=int)
    out["mamba_ssm_cache_dtype"] = _first(r"--mamba-ssm-cache-dtype (\S+)", args)
    # kernels / backends
    out["moe_backend"] = sorted(set(_all(r"Using (\S+ MoE backend|\S+Experts MoE backend)", key)))
    out["moe_backend_selection"] = sorted(set(_all(r"Using (ROCm AITER|TRITON) Unquantized MoE backend", key)))
    out["attention_backend_override"] = sorted(set(_all(r"Overriding with (\S+) out of potential backends", key)))
    out["mamba_ssu_backend"] = sorted(set(_all(r"Using (\S+) Mamba SSU backend", key)))
    out["allreduce_backends"] = sorted({f"{group}:{backends}" for backends, group in
                                        re.findall(r"Using (\[[^\]]+\]) all-reduce backends \(in dispatch order\) for group '(\w+):0'", key)})
    out["aiter_fused_moe_shapes"] = len(set(_all(r"\[aiter\] \[fused_moe\] using (\S+ default for \([^)]*\))", key)))
    # memory
    out["model_loading_gib_per_gpu"] = sorted({float(a) for a, _ in re.findall(r"Model loading took ([0-9.]+) GiB memory and ([0-9.]+) seconds", key)})
    out["model_loading_seconds"] = sorted({round(float(b), 1) for _, b in re.findall(r"Model loading took ([0-9.]+) GiB memory and ([0-9.]+) seconds", key)})
    out["available_kv_cache_gib"] = sorted({float(x) for x in _all(r"Available KV cache memory: ([0-9.]+) GiB", key)})
    out["gpu_kv_cache_tokens"] = sorted({int(x.replace(",", "")) for x in _all(r"GPU KV cache size: ([0-9,]+) tokens", key)})
    out["max_concurrency_at_max_len"] = sorted({float(x) for x in _all(r"Maximum concurrency for [0-9,]+ tokens per request: ([0-9.]+)x", key)})
    out["consumed_memory_gib"] = sorted({float(x) for x in _all(r"Actual usage is ([0-9.]+) GiB for consumed memory", key)})
    out["init_engine_seconds"] = _first(r"init engine .* took ([0-9.]+) s", key, cast=float)
    # smoke requests
    smokes = []
    for req in sorted(tag_dir.glob("*_request.json")):
        name = req.name[: -len("_request.json")]
        resp = tag_dir / f"{name}_response.json"
        request = json.loads(req.read_text(encoding="utf-8"))
        # 00_meta.txt keys: smoke_wall_secs / smoke2_wall_secs / smoke3_wall_secs (06_evidence.sh drops the numeric prefix)
        key_name = re.sub(r"^\d\d_", "", name)
        wall = _first(rf"^(?:{name}|{key_name})_wall_secs=([0-9.]+)", meta, cast=float)
        entry = {"name": name, "prompt": request["messages"][0]["content"], "max_tokens": request["max_tokens"],
                 "temperature": request["temperature"], "wall_secs": round(wall, 2) if wall is not None else None}
        if resp.exists() and resp.stat().st_size > 0:
            r = json.loads(resp.read_text(encoding="utf-8"))
            choice = r["choices"][0]
            usage = r.get("usage", {})
            entry.update({
                "finish_reason": choice.get("finish_reason"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                "content_chars": len(choice["message"].get("content") or ""),
                "content": (choice["message"].get("content") or "")[:400],
            })
        else:
            entry.update({"finish_reason": None, "note": "no response: request timed out (see wall_secs)"})
        smokes.append(entry)
    out["smoke"] = smokes
    # serving probe (09_perf_probe.py): medians per concurrency level, straight from the probe's own JSON
    perf_path = tag_dir / "08_perf.json"
    if perf_path.exists() and perf_path.stat().st_size > 0:
        p = json.loads(perf_path.read_text(encoding="utf-8"))
        levels = []
        for lv in p["levels"]:
            reqs = [r for rd in lv["rounds"] for r in rd["requests"]]
            levels.append({
                "concurrency": lv["concurrency"],
                "n_requests": lv["n_requests"],
                "ttft_s_median": round(lv["ttft_s_median"], 3) if lv["ttft_s_median"] is not None else None,
                "ttft_s_max": round(lv["ttft_s_max"], 3) if lv["ttft_s_max"] is not None else None,
                "decode_tok_s_per_request_median": round(lv["decode_tok_s_per_request_median"], 1)
                if lv["decode_tok_s_per_request_median"] is not None else None,
                "agg_tok_s_median": round(lv["agg_tok_s_median"], 1) if lv["agg_tok_s_median"] is not None else None,
                "completion_tokens_per_request": sorted({r["completion_tokens"] for r in reqs if r.get("completion_tokens")}),
                "finish_reasons": sorted({r["finish_reason"] for r in reqs if r.get("finish_reason")}),
            })
        out["perf"] = {
            "prompt": p["prompt"], "max_tokens": p["max_tokens"], "rounds": p["rounds"],
            "started_utc": p.get("started_utc"), "finished_utc": p.get("finished_utc"),
            "warmup": {k: p["warmup"].get(k) for k in ("ttft_s", "decode_tok_s", "completion_tokens", "finish_reason")},
            "gpu_used_gib_before": (p.get("gpu_mem_before") or {}).get("used_gib_per_gpu"),
            "gpu_used_gib_after": (p.get("gpu_mem_after") or {}).get("used_gib_per_gpu"),
            "levels": levels,
        }
    return out


def summarize() -> dict:
    tags = sorted(p for p in PUBLIC.iterdir() if p.is_dir())
    summary = {"schema_version": 1,
               "scope": "Numbers extracted from the raw files in data/mi300x-run/<tag>/ only; nothing typed by hand.",
               "runs": [summarize_tag(t) for t in tags]}
    (PUBLIC / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return summary


def table(summary: dict) -> str:
    lines = ["| Run | Layout | MoE backend | Weights/GPU GiB | KV free GiB | KV tokens | Smoke (finish, wall s) | Probe: conc → TTFT s / tok/s per req / agg tok/s |",
             "|---|---|---|---|---|---|---|---|"]
    for r in summary["runs"]:
        layout = f"TP{r['tensor_parallel_size']}" + (f"×PP{r['pipeline_parallel_size']}" if r.get("pipeline_parallel_size") else "") + \
                 (f"×DP{r['data_parallel_size']}" if r.get("data_parallel_size") else "") + ("+EP" if r["expert_parallel"] else "")
        smoke = "; ".join(f"{s['name']}={s.get('finish_reason')}@{s['wall_secs']}" for s in r["smoke"])
        perf = "; ".join(f"{lv['concurrency']} → {lv['ttft_s_median']} / {lv['decode_tok_s_per_request_median']} / {lv['agg_tok_s_median']}"
                         for lv in (r.get("perf") or {}).get("levels", [])) or "not run"
        lines.append(f"| {r['tag']} | {layout} | {', '.join(r['moe_backend'])} | {'/'.join(map(str, r['model_loading_gib_per_gpu']))} | "
                     f"{'/'.join(map(str, r['available_kv_cache_gib']))} | {'/'.join(f'{t:,}' for t in r['gpu_kv_cache_tokens'])} | {smoke} | {perf} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "project":
        if len(argv) != 4:
            print(__doc__); return 2
        dst = project(Path(argv[2]), argv[3]); print(f"projected -> {dst}"); return 0
    if len(argv) >= 2 and argv[1] == "summarize":
        s = summarize(); print(f"summary.json: {len(s['runs'])} runs"); return 0
    if len(argv) >= 2 and argv[1] == "table":
        print(table(json.loads((PUBLIC / "summary.json").read_text(encoding="utf-8")))); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
