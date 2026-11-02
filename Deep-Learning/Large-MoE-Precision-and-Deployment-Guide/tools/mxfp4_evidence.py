#!/usr/bin/env python3
"""Project the 2026-11-02 MXFP4 / NVFP4 low-precision runs into data/mi300x-mxfp4/ and summarize them.

    python3 tools/mxfp4_evidence.py project <private_evidence_root>   # writes data/mi300x-mxfp4/<run>/
    python3 tools/mxfp4_evidence.py summarize                          # rewrites data/mi300x-mxfp4/summary.json

<private_evidence_root> is the author's evidence directory holding three run folders:
  mxfp4-full-<stamp>/{inkling,nemotron}/   full-model MXFP4 deployments (launch.json, first_response.json,
                                            08_perf.json, acceptance_state.json, server_final.log)
  muse-mxfp4-<stamp>/{.,muse_path}/         the two Muse MXFP4 launch attempts that failed before loading weights
  fp4_compat_<stamp>/                        the NVFP4 single-expert kernel probe (gpu_probe.json)

`project` copies the small raw files, replaces private IPs / hosts / the login user with role labels (same
rules as tools/mi300x_evidence.py), keeps only the decisive lines of each server log, and records the SHA-256
of every private file it did not copy. `summarize` derives data/mi300x-mxfp4/summary.json from the projected
files only; tests/mxfp4.test.mjs checks that the READMEs quote exactly those values.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mi300x_evidence import redact, sha256  # noqa: E402  (same redaction rules for the same cluster)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "mi300x-mxfp4"
KEEP_LOG = re.compile(
    r"Mxfp4 MoE backend|OCP_MX|Quantization ?Emulation|Online quantization|Model loading took|Available KV cache memory|"
    r"GPU KV cache size|Maximum concurrency|Application startup complete|NotImplementedError|quantization=|"
    r"Using \S+ (Unquantized )?MoE backend|Using \S+Experts|non-default args", re.I)
SMALL = ("launch.json", "first_request.json", "first_response.json", "08_perf.json", "acceptance_state.json",
         "models.json", "gpu_before.json", "gpu_after.json", "gpu_probe.json")


def _copy_small(src: Path, dst: Path, copied: list[str]) -> None:
    for path in sorted(src.iterdir()):
        if path.is_file() and path.name in SMALL and path.stat().st_size > 0:
            (dst / path.name).write_text(redact(path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")
            copied.append(path.name)


def _keylines(src_log: Path, dst: Path, copied: list[str]) -> None:
    if not src_log.exists():
        return
    lines = [redact(line) for line in src_log.read_text(encoding="utf-8", errors="replace").splitlines() if KEEP_LOG.search(line)]
    (dst / "server_keylines.log").write_text("\n".join(lines[:400]) + "\n", encoding="utf-8", newline="\n")
    copied.append("server_keylines.log")


def _private_hashes(src: Path, dst: Path, copied: list[str], note: str) -> None:
    private = [f"{sha256(p)}  {p.relative_to(src).as_posix()}" for p in sorted(src.rglob("*"))
               if p.is_file() and p.name != "SHA256SUMS.txt" and p.name not in copied]
    (dst / "SHA256SUMS.private.txt").write_text("\n".join(private) + "\n", encoding="utf-8", newline="\n")
    (dst / "PROJECTION.json").write_text(json.dumps({
        "source": src.name, "public_files": copied, "private_files_hashed": len(private),
        "redaction": "host names -> node0/node1, private IPs -> <nodeN-private-ip>, login user -> <login-user>, ANSI colour removed; "
                     "postcheck.json (public VM addresses) is not published",
        "note": note}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def project(root: Path) -> None:
    full = next(root.glob("mxfp4-full-*"))
    for model in ("inkling", "nemotron"):
        src, dst = full / model, PUBLIC / f"{model}_mxfp4_8xMI300X"
        dst.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        _copy_small(src, dst, copied)
        _keylines(src / "server_final.log", dst, copied)
        _private_hashes(src, dst, copied, "Full server logs and the acceptance log stay private; their SHA-256 values are listed.")
    muse = next(root.glob("muse-mxfp4-*"))
    for attempt, src in (("attempt1_generic_online_flags", muse), ("attempt2_muse_online_quant_env", muse / "muse_path")):
        dst = PUBLIC / f"muse_mxfp4_8xMI300X_{attempt}"
        dst.mkdir(parents=True, exist_ok=True)
        copied = []
        _copy_small(src, dst, copied)
        _keylines(src / "server_final.log", dst, copied)
        _private_hashes(src, dst, copied, "Both attempts exited before loading weights; the full startup logs stay private.")
    probe = next(root.glob("fp4_compat_*"))
    dst = PUBLIC / "nvfp4_single_expert_probe_1xMI300X"
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    _copy_small(probe, dst, copied)
    _private_hashes(probe, dst, copied, "Per-expert weight samples and postcheck.json (public VM addresses) stay private.")
    print(f"projected -> {PUBLIC}")


def _round(v, nd):
    return None if v is None else round(v, nd)


def summarize_full(tag_dir: Path) -> dict:
    launch = json.loads((tag_dir / "launch.json").read_text(encoding="utf-8"))
    args = " ".join(launch["args"])
    key = (tag_dir / "server_keylines.log").read_text(encoding="utf-8", errors="replace")
    first = json.loads((tag_dir / "first_response.json").read_text(encoding="utf-8"))
    perf = json.loads((tag_dir / "08_perf.json").read_text(encoding="utf-8"))
    state = json.loads((tag_dir / "acceptance_state.json").read_text(encoding="utf-8"))
    out = {
        "tag": tag_dir.name, "status": state["status"],
        "image_id": launch["image"],
        "model_arg": launch["args"][1], "revision": re.search(r"--revision (\S+)", args).group(1),
        "served_model_name": re.search(r"--served-model-name (\S+)", args).group(1),
        "tensor_parallel_size": int(re.search(r"--tensor-parallel-size (\d+)", args).group(1)),
        "expert_parallel": "--enable-expert-parallel" in args,
        "enforce_eager": "--enforce-eager" in args,
        "max_model_len": int(re.search(r"--max-model-len (\d+)", args).group(1)),
        "online_quantization_flags": re.search(r"(--quantization online --quantization-config \S+ --moe-backend emulation)", args).group(1)
        if "--quantization online" in args else None,
        "mxfp4_backend_selected": sorted(set(re.findall(r"Using '(\S+)' Mxfp4 MoE backend", key))),
        "expert_classes": sorted(set(re.findall(r"Using (\S+Experts)\b", key))),
        "model_loading_gib_per_gpu": sorted({float(x) for x in re.findall(r"Model loading took ([0-9.]+) GiB", key)}),
        "model_loading_seconds": sorted({round(float(x), 1) for x in re.findall(r"Model loading took [0-9.]+ GiB memory and ([0-9.]+) seconds", key)}),
        "available_kv_cache_gib": sorted({float(x) for x in re.findall(r"Available KV cache memory: ([0-9.]+) GiB", key)}),
        "gpu_kv_cache_tokens": sorted({int(x.replace(",", "")) for x in re.findall(r"GPU KV cache size: ([0-9,]+) tokens", key)}),
        "first_answer": {
            "prompt_tokens": first["usage"]["prompt_tokens"], "completion_tokens": first["usage"]["completion_tokens"],
            "reasoning_tokens": (first["usage"].get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "finish_reason": first["finish_reason"], "ttft_s": _round(first["ttft_s"], 2),
            "first_final_content_s": _round(first["first_final_content_s"], 2), "wall_s": _round(first["wall_s"], 2),
            "content": first["content"][:400],
        },
        "perf": {"prompt": perf["prompt"], "max_tokens": perf["max_tokens"], "rounds": perf["rounds"],
                 "gpu_used_gib_before": (perf.get("gpu_mem_before") or {}).get("used_gib_per_gpu"),
                 "levels": [{"concurrency": lv["concurrency"], "n_requests": lv["n_requests"],
                             "ttft_s_median": _round(lv["ttft_s_median"], 3), "ttft_s_max": _round(lv["ttft_s_max"], 3),
                             "decode_tok_s_per_request_median": _round(lv["decode_tok_s_per_request_median"], 1),
                             "agg_tok_s_median": _round(lv["agg_tok_s_median"], 1),
                             "finish_reasons": sorted({r["finish_reason"] for rd in lv["rounds"] for r in rd["requests"] if r.get("finish_reason")})}
                            for lv in perf["levels"]]},
    }
    return out


def summarize_muse(tag_dir: Path) -> dict:
    launch = json.loads((tag_dir / "launch.json").read_text(encoding="utf-8"))
    key = (tag_dir / "server_keylines.log").read_text(encoding="utf-8", errors="replace")
    state = json.loads((tag_dir / "acceptance_state.json").read_text(encoding="utf-8"))
    errors = sorted({m.strip() for m in re.findall(r"NotImplementedError: (.*)$", key, flags=re.M)})
    return {"tag": tag_dir.name, "status": state["status"], "image_id": launch["image"], "model_arg": launch["args"][1],
            "revision": re.search(r"--revision (\S+)", " ".join(launch["args"])).group(1),
            "quantization_flags": [a for a in launch["args"] if a.startswith("--quantization") or a.startswith("--moe-backend")]
            + [launch["args"][i + 1] for i, a in enumerate(launch["args"]) if a in ("--quantization", "--quantization-config", "--moe-backend")],
            "mxfp4_backend_selected": sorted(set(re.findall(r"Using '(\S+)' Mxfp4 MoE backend", key))),
            "weights_loaded": bool(re.search(r"Model loading took", key)),
            "error": errors[0] if errors else None}


def summarize_probe(tag_dir: Path) -> dict:
    p = json.loads((tag_dir / "gpu_probe.json").read_text(encoding="utf-8"))
    return {"tag": tag_dir.name, "scope": p["scope"], "full_model_inference": p["full_model_inference"],
            "versions": p["versions"], "relative_l2_limit": p["relative_l2_limit"],
            "results": [{"model": r["model"], "revision": r["revision"], "status": r["status"], "backend": r["backend"],
                         "expert_class": r["expert_class"], "relative_l2_error": r["relative_l2_error"]} for r in p["results"]]}


def summarize() -> dict:
    s = {"schema_version": 1, "run_date": "2026-11-02",
         "scope": "Numbers extracted from the projected raw files in data/mi300x-mxfp4/<run>/ only; nothing typed by hand.",
         "full_model_mxfp4": [summarize_full(PUBLIC / t) for t in ("inkling_mxfp4_8xMI300X", "nemotron_mxfp4_8xMI300X")],
         "muse_mxfp4_attempts": [summarize_muse(p) for p in sorted(PUBLIC.glob("muse_mxfp4_8xMI300X_*"))],
         "nvfp4_single_expert_probe": summarize_probe(PUBLIC / "nvfp4_single_expert_probe_1xMI300X")}
    (PUBLIC / "summary.json").write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return s


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "project":
        project(Path(argv[2])); return 0
    if len(argv) == 2 and argv[1] == "summarize":
        s = summarize(); print(f"summary.json: {len(s['full_model_mxfp4'])} full runs, {len(s['muse_mxfp4_attempts'])} Muse attempts"); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
