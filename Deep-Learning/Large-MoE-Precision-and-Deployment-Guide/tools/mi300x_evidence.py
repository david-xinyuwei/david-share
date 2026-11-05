#!/usr/bin/env python3
"""Project a private MI300X evidence directory into the public data/mi300x-run/ set and summarize it.

    python3 tools/mi300x_evidence.py project <private_evidence_dir> <tag>   # writes data/mi300x-run/<tag>/
    python3 tools/mi300x_evidence.py project-rccl <private_rccl_dir>        # writes data/mi300x-run/rccl_probe/
    python3 tools/mi300x_evidence.py summarize                            # rewrites data/mi300x-run/summary.json
    python3 tools/mi300x_evidence.py table                                # prints the summary as Markdown
    python3 tools/mi300x_evidence.py project-fiveway <private_run_dir>      # writes data/mi300x-fiveway/<run_id>/
    python3 tools/mi300x_evidence.py init-fiveway <new_run_dir> <summary>   # prepare a fresh run without old scores
    python3 tools/mi300x_evidence.py render-fiveway <summary>              # update only the marked README tables

`project` copies the small raw artifacts (00_meta.txt, 01_models.json, *_request.json, *_response.json,
04_rocm_smi_vram.json, 05_server_keylines.log, 08_perf.json) and replaces host names, private IPs and the login user
with role labels. Full container logs and Ray worker logs stay private because of size; their SHA-256 values are kept
in SHA256SUMS.private.txt so the public summary can be matched against them.

`project-rccl` projects the node-0 logs of scripts/mi300x/07_rccl_probe.sh (one file per variant, `ref` = default GPU
Direct RDMA, `nogdr` = NCCL_NET_GDR_LEVEL=0): the probe's own PROBE_START / RCCL_PROBE_OK / PROBE_EXIT lines, the
RCCL/HIP/ROCm version header, and the first occurrence of each distinct NCCL WARN / watchdog-timeout message, with host
names replaced by role labels. The full logs are hashed into SHA256SUMS.private.txt like the other private files.

`summarize` reads every data/mi300x-run/<tag>/ directory and extracts, from the raw files only, the numbers that the
README and VALIDATION pages quote: kernels/backends selected, weights per GPU, KV cache budget, smoke request wall
clock, token usage and finish reasons, and — when scripts/mi300x/09_perf_probe.py was run — the TTFT / decode
throughput medians per concurrency level; the RCCL probe result per variant is added under `rccl_probe` when the
projection exists. tests/mi300x.test.mjs asserts the documents against this file, so a quoted number cannot drift
from the evidence without a failing test.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "mi300x-run"
RCCL_TAG = "rccl_probe"
SMALL = ("00_meta.txt", "01_models.json", "04_rocm_smi_vram.json", "05_server_keylines.log", "08_perf.json")
MEASURED_STATUSES = ("PASS", "COMPLETE_WITH_ERRORS")
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


# Lines of a 07_rccl_probe.sh log that the public projection keeps verbatim (after redaction).
RCCL_KEEP = re.compile(r"^(PROBE_START=|PROBE_EXIT=|RCCL_PROBE_OK=|RCCL version|HIP version|ROCm version|Librccl path)")
# Lines kept once per distinct message: RCCL warnings and the PyTorch collective watchdog. The per-rank prefix
# ("[2026-11-01 18:00:03] host:pid:tid [4] /path/file.cc:1605 " or "[rank5]:[E1101 17:58:22.507895301 File.cpp:730] ")
# is stripped so that the same message from sixteen ranks collapses to one line.
RCCL_ONCE = re.compile(r"NCCL WARN|Watchdog caught collective operation timeout|Received a dump signal")
RCCL_PREFIX = re.compile(r"^(\[[^\]]*\] \S+ \[\d+\] \S+ |\[rank\d+\]:\[E[0-9.: ]+\S+\] (\[[^\]]*\] )?)")
# Per-rank variation inside an otherwise identical message: elapsed millis, the signalling rank, trailing queue state.
RCCL_NORMALIZE = [
    (re.compile(r" for device \d+$"), " for device <n>"),
    (re.compile(r"ran for \d+ millis"), "ran for <n> millis"),
    (re.compile(r"from\s+rank \d+"), "from rank <n>"),
    (re.compile(r"\. Last enqueued.*$"), "."),
]


def project_rccl(src: Path) -> Path:
    """Project the 07_rccl_probe.sh node-0 logs (one per variant) into data/mi300x-run/rccl_probe/."""
    dst = PUBLIC / RCCL_TAG
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for path in sorted(src.glob("*_rccl_probe_*_node*.log")):
        text = ANSI.sub("", path.read_text(encoding="utf-8", errors="replace"))
        kept, seen = [], set()
        for line in text.splitlines():
            if RCCL_KEEP.match(line):
                kept.append(line)
            elif RCCL_ONCE.search(line):
                message = RCCL_PREFIX.sub("", line).strip()
                for pattern, replacement in RCCL_NORMALIZE:
                    message = pattern.sub(replacement, message)
                if message not in seen:
                    seen.add(message)
                    kept.append(message)
        name = re.sub(r"^\d\d_", "07_", path.name)          # the private copy was numbered 10_, the script is 07_
        (dst / name).write_text(redact("\n".join(kept)) + "\n", encoding="utf-8", newline="\n")
        copied.append(name)
    private = [f"{sha256(p)}  {p.relative_to(src).as_posix()}" for p in sorted(src.rglob("*")) if p.is_file()]
    (dst / "SHA256SUMS.private.txt").write_text("\n".join(private) + "\n", encoding="utf-8", newline="\n")
    (dst / "PROJECTION.json").write_text(json.dumps({
        "source": "scripts/mi300x/07_rccl_probe.sh node-0 logs, one per variant (ref = default GPU Direct RDMA, nogdr = NCCL_NET_GDR_LEVEL=0)",
        "public_files": copied,
        "private_files_hashed": len(private),
        "kept": "PROBE_START / RCCL_PROBE_OK / PROBE_EXIT lines, RCCL/HIP/ROCm version header, first occurrence of each distinct NCCL WARN and watchdog message",
        "redaction": "host names -> node0/node1, ANSI colour removed; the full logs are hashed in SHA256SUMS.private.txt",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return dst


def summarize_rccl(tag_dir: Path) -> list[dict]:
    """One entry per projected variant log, read from the probe's own result line only."""
    out = []
    for path in sorted(tag_dir.glob("07_rccl_probe_*_node0.log")):
        text = path.read_text(encoding="utf-8")
        entry = {
            "file": path.name,
            "variant": _first(r"^PROBE_START=\S+ node_rank=\d+ variant=(\S+)", text),
            "probe_start_utc": _first(r"^PROBE_START=(\S+)", text),
            "probe_end_utc": _first(r"PROBE_END=(\S+)", text),
            "probe_exit": _first(r"^PROBE_EXIT=(\d+)", text, cast=int),
            "rccl_version": _first(r"^RCCL version\s*:\s*(\S+)", text),
            "rocm_version": _first(r"^ROCm version\s*:\s*(\S+)", text),
            "ok": _first(r"^RCCL_PROBE_OK=(\w+)", text) == "True",
            "world": _first(r"^RCCL_PROBE_OK=\S+ world=(\d+)", text, cast=int),
            "bytes": _first(r" bytes=(\d+)", text, cast=int),
            "first_allreduce_s": _first(r" first_allreduce_s=([0-9.]+)", text, cast=float),
            "avg_allreduce_ms": _first(r" avg_allreduce_ms=([0-9.]+)", text, cast=float),
            "busbw_GBps": _first(r" busbw_GBps=([0-9.]+)", text, cast=float),
            "peermem_fallback": "Peermem not available" in text,
            "watchdog_timeout": "Watchdog caught collective operation timeout" in text,
        }
        out.append(entry)
    return out


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
    tags = sorted(p for p in PUBLIC.iterdir() if p.is_dir() and p.name != RCCL_TAG)
    summary = {"schema_version": 1,
               "scope": "Numbers extracted from the raw files in data/mi300x-run/<tag>/ only; nothing typed by hand.",
               "runs": [summarize_tag(t) for t in tags]}
    if (PUBLIC / RCCL_TAG).is_dir():
        summary["rccl_probe"] = summarize_rccl(PUBLIC / RCCL_TAG)
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


def percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[94]


def normalize_resource_sample(record: dict, previous: dict | None = None) -> dict:
    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    gpu_fields = {"use_percent": "GPU use (%)", "memory_activity_percent": "GPU Memory Read/Write Activity (%)",
                  "vram_used_bytes": "VRAM Total Used Memory (B)",
                  "power_watts": "Current Socket Graphics Package Power (W)"}
    memory = record["host"]["memory_bytes"]
    result = {"unix_s": record["unix_s"], "sample_seconds": record["sample_seconds"],
              "gpus": {card: {name: number(native.get(field)) for name, field in gpu_fields.items()}
                       for card, native in record["gpu_native"].items() if card.startswith("card")},
              "host_cpu_percent": record.get("host_cpu_percent") if previous is not None else None,
              "host_memory_used_bytes": memory["MemTotal"] - memory["MemAvailable"],
              "network_bytes_per_s": {}, "infiniband_bytes_per_s": {}}
    interval = record["unix_s"] - previous["unix_s"] if previous is not None else None
    for counter_group, output_group in (("network_bytes", "network_bytes_per_s"),
                                       ("infiniband_bytes", "infiniband_bytes_per_s")):
        for device, counters in record["host"][counter_group].items():
            rates = {}
            for counter, value in counters.items():
                prior = previous["host"][counter_group].get(device, {}).get(counter) if previous else None
                rates[counter] = ((value - prior) / interval
                                  if prior is not None and interval is not None and interval > 0 and value >= prior else None)
            result[output_group][device] = rates
    return result


def resource_window_summary(path: Path, workloads: list[dict]) -> tuple[list[dict], dict]:
    windows = [{"workload": workload["file"], "concurrency": level["concurrency"], **window}
               for workload in workloads for level in workload["levels"] for window in level["round_windows"]
               if window["started_unix_s"] is not None and window["finished_unix_s"] is not None]
    selected = []
    previous = None
    measurement_end = max((window["finished_unix_s"] for window in windows), default=None)
    source_integrity = {"status": "COMPLETE", "valid_records": 0, "truncated_tail": None}
    with path.open("rb") as source:
        for line_number, raw in enumerate(source, 1):
            try:
                record = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                if (raw.endswith(b"\n") or source.read(1) or previous is None
                        or measurement_end is None or previous["unix_s"] < measurement_end):
                    raise ValueError(f"{path.name}: invalid resource record at line {line_number}") from error
                source_integrity["status"] = "PARTIAL_TRAILING_RECORD_OUTSIDE_WINDOWS"
                source_integrity["truncated_tail"] = {
                    "line": line_number, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                    "last_valid_unix_s": previous["unix_s"], "measurement_end_unix_s": measurement_end,
                }
                break
            source_integrity["valid_records"] += 1
            window = next((candidate for candidate in windows
                           if candidate["started_unix_s"] <= record["unix_s"] < candidate["finished_unix_s"]), None)
            if window is not None:
                prior = previous if previous and previous["unix_s"] >= window["started_unix_s"] else None
                sample = normalize_resource_sample(record, prior)
                sample.update({key: window[key] for key in ("workload", "concurrency", "round")})
                selected.append(sample)
            previous = record
    def stats(values):
        present = [value for value in values if value is not None]
        return {"samples": len(present), "missing": len(values) - len(present),
                "mean": statistics.mean(present) if present else None,
                "max": max(present) if present else None, "p95": percentile95(present)}
    summaries = {}
    for workload in workloads:
        summaries[workload["file"]] = {}
        for level in workload["levels"]:
            samples = [sample for sample in selected
                       if sample["workload"] == workload["file"] and sample["concurrency"] == level["concurrency"]]
            summary = {"status": "OBSERVED" if samples else "MISSING", "sample_count": len(samples),
                       "source_integrity": source_integrity,
                       "samples_per_round": {str(window["round"]): sum(sample["round"] == window["round"] for sample in samples)
                                             for window in level["round_windows"]},
                       "host_cpu_percent": stats([sample["host_cpu_percent"] for sample in samples]),
                       "host_memory_used_bytes": stats([sample["host_memory_used_bytes"] for sample in samples])}
            for group in ("gpus", "network_bytes_per_s", "infiniband_bytes_per_s"):
                devices = sorted({device for sample in samples for device in sample[group]})
                summary[group] = {}
                for device in devices:
                    fields = sorted({field for sample in samples for field in sample[group].get(device, {})})
                    summary[group][device] = {field: stats([sample[group].get(device, {}).get(field) for sample in samples])
                                              for field in fields}
            summaries[workload["file"]][str(level["concurrency"])] = summary
    return selected, summaries


def vllm_arguments(command: list[str]) -> list[str]:
    if command and command[0] in ("-c", "-lc"):
        if len(command) == 2:
            arguments = shlex.split(command[1])
        elif command[2] == "qwen-fiveway":
            arguments = command[3:]
        else:
            raise ValueError("Unrecognized shell wrapper in recorded launch")
    else:
        arguments = command
    if "serve" not in arguments:
        raise ValueError("Recorded launch does not contain vLLM serve arguments")
    return arguments


def summarize_fiveway_perf(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    levels = []
    for level in report["levels"]:
        requests = [request for batch in level["rounds"] for request in batch["requests"]]
        expected = report["rounds"] * level["concurrency"]
        if len(requests) != expected:
            raise ValueError(f"{path.name}: expected {expected} requests, got {len(requests)}")
        successful = [request for request in requests if request["status"] == "OK"]
        round_rates = []
        for batch in level["rounds"]:
            tokens = sum(request["completion_tokens"] for request in batch["requests"] if request["status"] == "OK")
            if batch["span_s"] <= 0:
                raise ValueError(f"{path.name}: non-positive round duration")
            round_rates.append(tokens / batch["span_s"])
        def median(field: str):
            values = [request[field] for request in successful if request.get(field) is not None]
            return statistics.median(values) if values else None
        levels.append({
            "concurrency": level["concurrency"],
            "n_requests": len(requests),
            "n_success": len(successful),
            "n_failed": len(requests) - len(successful),
            "n_complete_answers": sum(request["answer_complete"] for request in successful),
            "n_truncated": sum(request["finish_reason"] == "length" for request in successful),
            "prompt_tokens": sorted({request["prompt_tokens"] for request in successful}),
            "completion_tokens": sorted({request["completion_tokens"] for request in successful}),
            "ttft_s_median": median("ttft_s"),
            "ttft_s_p95": percentile95([request["ttft_s"] for request in successful if request.get("ttft_s") is not None]),
            "first_content_s_median": median("first_content_s"),
            "decode_tok_s_median": median("decode_tok_s"),
            "wall_s_median": median("wall_s"),
            "e2e_s_median": median("wall_s"),
            "e2e_s_p95": percentile95([request["wall_s"] for request in successful if request.get("wall_s") is not None]),
            "aggregate_tok_s_median": statistics.median(round_rates),
            "aggregate_tok_s_rounds": round_rates,
            "round_spans_s": [batch["span_s"] for batch in level["rounds"]],
            "round_windows": [{"round": index, "started_unix_s": batch.get("started_unix_s"),
                               "finished_unix_s": batch.get("finished_unix_s")}
                              for index, batch in enumerate(level["rounds"], 1)],
        })
    return {"file": path.name, "prompt": report["prompt"], "max_tokens": report["max_tokens"],
            "rounds": report["rounds"], "status": report["status"],
            "n_requests": sum(level["n_requests"] for level in levels),
            "n_success": sum(level["n_success"] for level in levels),
            "n_failed": sum(level["n_failed"] for level in levels),
            "n_complete_answers": sum(level["n_complete_answers"] for level in levels),
            "n_truncated": sum(level["n_truncated"] for level in levels),
            "started_utc": report["started_utc"], "finished_utc": report["finished_utc"],
            "warmup": {key: report["warmup"].get(key) for key in ("status", "error", "ttft_s", "wall_s",
                   "prompt_tokens", "completion_tokens", "finish_reason", "answer_complete")},
            "metric_definitions": report["metric_definitions"], "levels": levels}


TRANSPORT_DEFINITION = ("Per node: sum over the listed interfaces of the mean one-second byte rate inside the measured rounds, "
                        "in MB/s (10^6 bytes per second). InfiniBand = the mlx5_ib* port data counters (RDMA verbs traffic; "
                        "the sampler multiplies the 4-byte counters by 4); IPoIB = the ib* network interfaces; "
                        "eth0 = the Azure Ethernet interface used for sockets.")
TRANSPORT_FIELDS = ("infiniband_rx_mb_s", "infiniband_tx_mb_s", "ipoib_rx_mb_s", "eth0_rx_mb_s")


def transport_rates(resource: dict) -> dict:
    def total(group: str, predicate, counter: str):
        means = [fields[counter]["mean"] for device, fields in resource.get(group, {}).items()
                 if predicate(device) and counter in fields]
        return None if not means or any(mean is None for mean in means) else sum(means) / 1e6
    infiniband = lambda device: device.startswith("mlx5_ib")
    ipoib = lambda device: re.fullmatch(r"ib\d+", device) is not None
    return {"infiniband_rx_mb_s": total("infiniband_bytes_per_s", infiniband, "port_rcv_data_bytes"),
            "infiniband_tx_mb_s": total("infiniband_bytes_per_s", infiniband, "port_xmit_data_bytes"),
            "ipoib_rx_mb_s": total("network_bytes_per_s", ipoib, "rx_bytes"),
            "eth0_rx_mb_s": total("network_bytes_per_s", lambda device: device == "eth0", "rx_bytes")}


TIME_BUDGET_DEFINITION = (
    "One input and one concurrency level, named in publication.time_budget. Measured: time per output token = 1000 / "
    "median per-request decode speed; InfiniBand receive per node = the mean one-second receive rate inside the "
    "measured rounds x their total duration, divided by the output tokens of those rounds (the prompt's share is "
    "included) or by the processed tokens (prompt plus output); transfer time = those bytes at the nominal per-node "
    "InfiniBand rate, and at one port's rate. Estimated, not measured: the cross-node collectives per token and the "
    "lower bound of their extra cost over the reference layout's intra-node collectives (sources and assumption in "
    "publication.time_budget).")


def time_budget(summary: dict, spec: dict) -> dict:
    """Per-token time and cross-node bytes of the layouts named in the publication spec, plus the estimate they allow.

    Every measured value is derived from level statistics already in the summary, so the tests can recompute them."""
    nominal_bytes_s = summary["transport_nominal_infiniband_mb_s_per_node"] * 1e6
    port_bytes_s = summary["conditions"]["network"]["infiniband_port_rate_gbit_s"] * 1e9 / 8
    by_id = {strategy["id"]: strategy for strategy in summary["strategies"]}

    def received(level: dict) -> tuple[float, dict]:
        output = sum(rate * span for rate, span in zip(level["aggregate_tok_s_rounds"], level["round_spans_s"]))
        seconds = sum(level["round_spans_s"])
        return output, {node: rates["infiniband_rx_mb_s"] * 1e6 * seconds for node, rates in level["transport"].items()}

    layouts = {}
    for layout in spec["layouts"]:
        workload = next(item for item in by_id[layout]["workloads"] if item["file"] == spec["workload"])
        level = next(item for item in workload["levels"] if item["concurrency"] == spec["concurrency"])
        if len(level["prompt_tokens"]) != 1:
            raise ValueError(f"{layout}: the time budget needs a single prompt length")
        output, nodes = received(level)
        processed = output + level["n_success"] * level["prompt_tokens"][0]
        busier = max(nodes, key=nodes.get)
        per_output = nodes[busier] / output
        layouts[layout] = {
            "decode_tok_s_median": level["decode_tok_s_median"],
            "ms_per_output_token": 1000 / level["decode_tok_s_median"],
            "output_tokens": round(output),
            "processed_tokens": round(processed),
            "busier_node": busier,
            "infiniband_rx_bytes_per_output_token": {node: value / output for node, value in nodes.items()},
            "infiniband_rx_bytes_per_processed_token": {node: value / processed for node, value in nodes.items()},
            "busier_node_infiniband_rx_bytes_per_output_token": per_output,
            "transfer_us_per_output_token_at_nominal": per_output / nominal_bytes_s * 1e6,
            "transfer_us_per_output_token_at_one_port": per_output / port_bytes_s * 1e6,
        }
    reference = spec["reference_layout"]
    for layout, entry in layouts.items():
        entry["extra_ms_per_output_token_vs_reference"] = entry["ms_per_output_token"] - layouts[reference]["ms_per_output_token"]
        entry["transfer_share_of_extra_ratio"] = (
            None if layout == reference else
            entry["transfer_us_per_output_token_at_nominal"] / (entry["extra_ms_per_output_token_vs_reference"] * 1000))
        entry["one_port_transfer_share_of_extra_ratio"] = (
            None if layout == reference else
            entry["transfer_us_per_output_token_at_one_port"] / (entry["extra_ms_per_output_token_vs_reference"] * 1000))
    bound = layouts[spec["lower_bound_layout"]]
    if bound["extra_ms_per_output_token_vs_reference"] <= 0:
        raise ValueError("The lower-bound layout is not slower than the reference layout; no bound follows")
    in_layers = spec["language_layers"] * spec["cross_node_collectives_per_layer"]
    collectives = in_layers + spec["collectives_per_step_outside_layers"]
    per_collective = bound["busier_node_infiniband_rx_bytes_per_output_token"] / collectives
    estimate = {"status": "ESTIMATE_NOT_MEASURED", "layout": spec["lower_bound_layout"],
                "cross_node_all_reduces_in_layers_per_token": in_layers,
                "cross_node_collectives_per_token": collectives,
                "extra_us_per_cross_node_collective_lower_bound": bound["extra_ms_per_output_token_vs_reference"] * 1000 / collectives,
                "infiniband_rx_bytes_per_collective_mean": per_collective,
                "transfer_us_per_collective_at_nominal": per_collective / nominal_bytes_s * 1e6}
    expected = spec["pipeline_handoff_hidden_size"] * spec["pipeline_handoff_bytes_per_value"]
    measured = layouts[spec["pipeline_layout"]]["infiniband_rx_bytes_per_processed_token"][spec["pipeline_receiving_node"]]
    pipeline = {"layout": spec["pipeline_layout"], "node": spec["pipeline_receiving_node"],
                "expected_bytes_per_processed_token": expected, "measured_bytes_per_processed_token": measured,
                "measured_to_expected_ratio": measured / expected}
    points = {}
    for layout in spec["layouts"]:
        values = []
        for workload in by_id[layout]["workloads"]:
            for level in workload["levels"]:
                output, nodes = received(level)
                values.append(max(nodes.values()) / output)
        points[layout] = {"points": len(values),
                          "busier_node_infiniband_rx_bytes_per_output_token_min": min(values),
                          "busier_node_infiniband_rx_bytes_per_output_token_max": max(values)}
    return {"definition": TIME_BUDGET_DEFINITION, "workload": spec["workload"], "concurrency": spec["concurrency"],
            "reference_layout": reference,
            "nominal_infiniband_mb_s_per_node": summary["transport_nominal_infiniband_mb_s_per_node"],
            "one_port_infiniband_gb_s": port_bytes_s / 1e9,
            "layouts": layouts, "estimate": estimate, "pipeline_handoff": pipeline, "all_points": points}


def fiveway_comparisons(summary: dict, specs: list[dict]) -> list[dict]:
    """Compare measured layouts point by point (input x concurrency) against a baseline layout.

    Every value is read from the level statistics already in the summary; relative changes are stored so that
    documents quote them instead of computing percentages by hand."""
    measured = [strategy for strategy in summary["strategies"] if strategy["status"] in MEASURED_STATUSES]
    results = []
    for spec in specs:
        metric, baseline, higher = spec["metric"], spec["baseline"], spec["better"] == "higher"
        points = []
        files = [workload["file"] for workload in measured[0]["workloads"]]
        for filename in files:
            levels = {strategy["id"]: {level["concurrency"]: level for level in
                                       next(item for item in strategy["workloads"] if item["file"] == filename)["levels"]}
                      for strategy in measured}
            for concurrency in summary["conditions"]["planned_concurrency"]:
                values = {strategy_id: levels[strategy_id][concurrency][metric] for strategy_id in levels}
                if any(value is None for value in values.values()):
                    continue
                best = (max if higher else min)(values, key=values.get)
                points.append({"workload": filename, "concurrency": concurrency, "values": values, "best": best,
                               "changes": [{"strategy": strategy_id, "relative_change_ratio": value / values[baseline] - 1,
                                            "abs_relative_change_ratio": abs(value / values[baseline] - 1)}
                                           for strategy_id, value in values.items() if strategy_id != baseline]})
        versus = {}
        for strategy_id in (strategy["id"] for strategy in measured if strategy["id"] != baseline):
            changes = [change["relative_change_ratio"] for point in points for change in point["changes"]
                       if change["strategy"] == strategy_id]
            magnitudes = [abs(change) for change in changes]
            versus[strategy_id] = {"better_count": sum((change > 0) == higher and change != 0 for change in changes),
                                   "worse_count": sum((change < 0) == higher and change != 0 for change in changes),
                                   "relative_change_ratio_min": min(changes), "relative_change_ratio_max": max(changes),
                                   "abs_relative_change_ratio_min": min(magnitudes),
                                   "abs_relative_change_ratio_max": max(magnitudes)}
        results.append({"metric": metric, "baseline": baseline, "better": spec["better"], "points": points,
                        "summary": {"points": len(points),
                                    "best_counts": {strategy["id"]: sum(point["best"] == strategy["id"] for point in points)
                                                    for strategy in measured},
                                    "versus_baseline": versus}})
    return results


def project_fiveway(src: Path) -> Path:
    src = src.resolve()
    metadata = json.loads((src / "run.json").read_text(encoding="utf-8"))
    run_id = metadata["run_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid run identifier")
    expected_ids = ["tp", "pp", "tep", "dp", "pd"]
    if [strategy["id"] for strategy in metadata["strategies"]] != expected_ids:
        raise ValueError("The five requested strategies must all be present in order")
    dst = ROOT / "data" / "mi300x-fiveway" / run_id
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    private_hashes = []
    def copy_text(path: Path, relative: Path) -> None:
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redact(path.read_text(encoding="utf-8", errors="strict")), encoding="utf-8", newline="\n")
        copied.append(relative.as_posix())
        private_hashes.append(f"{sha256(path)}  {path.relative_to(src).as_posix()}")
    for name in ("guide_prompt.txt", "smoke_request.json"):
        copy_text(src / name, Path(name))
    if metadata.get("publication") and (src / "SOURCE_SHA256SUMS").exists():
        copy_text(src / "SOURCE_SHA256SUMS", Path("SOURCE_SHA256SUMS"))
        source_scripts = []
        for line in (src / "SOURCE_SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(maxsplit=1)
            if not name.startswith("source/"):
                continue
            data = (src / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f"Source script hash mismatch: {name}")
            # Git stores text with LF line endings; keep the raw digest as provenance and add the LF digest for comparison.
            source_scripts.append({"file": name, "recorded_sha256": digest,
                                   "lf_sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
                                   "crlf_line_endings": b"\r\n" in data})
    if (src / "runtime-contract.log").exists():
        copy_text(src / "runtime-contract.log", Path("runtime-contract.log"))
    summary = {"schema_version": 1, "run_id": run_id, "status": metadata.get("status"), "source": metadata["source"],
               "scope": {key: value for key, value in metadata["requested_scope"].items()
                         if key in ("model", "revision", "precision", "nodes", "gpus_per_node", "gpu", "attribution")},
               "conditions": metadata["common_conditions"],
               "billing_reference": metadata["billing"], "strategies": []}
    for key in ("parent_run_id", "finished_utc", "publication"):
        if key in metadata:
            summary[key] = metadata[key]
    if metadata.get("publication") and (src / "SOURCE_SHA256SUMS").exists():
        summary["source_scripts"] = source_scripts
    if "recovery_phase" in metadata:
        summary["recovery_phase"] = {key: value for key, value in metadata["recovery_phase"].items()
                                     if key in ("stage", "execution_order", "comparison_boundary", "collector_boundary")}
    if "interruption" in metadata:
        summary["interruption"] = metadata["interruption"]
    for strategy in metadata["strategies"]:
        entry = {key: strategy[key] for key in ("id", "website_name", "website_label", "candidate_layout", "hypothesis", "discriminating_check", "status")}
        for key in ("observed_result", "source_discrepancy", "scope_boundary", "phase", "source_sha256",
                "checkpoint_files", "checkpoint_bytes", "observed_physical_bytes_per_gpu",
                "gpus_per_pool_if_split_evenly", "budget_fraction", "website_description_verbatim",
                "required_nodes", "required_gpus", "available_nodes", "figure"):
            if key in strategy:
                entry[key] = strategy[key]
        run_dir = src / strategy["id"]
        status_path = run_dir / "status.json"
        if status_path.exists():
            actual_status = json.loads(status_path.read_text(encoding="utf-8"))
            entry.update({"status": actual_status["status"], "phase": actual_status["phase"], "finished_utc": actual_status["observed_utc"]})
        if entry["status"] in MEASURED_STATUSES:
            for line in (run_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                expected_hash, remote_path = line.split(maxsplit=1)
                relative = Path(remote_path).relative_to(Path(metadata["evidence"]["remote_root"]))
                original = (src / relative).resolve()
                if not original.is_relative_to(src) or sha256(original) != expected_hash:
                    raise ValueError(f"Original evidence hash mismatch: {relative}")
            launch = (run_dir / "launch.txt").read_text(encoding="utf-8").strip().split(" ", 2)
            command = json.loads(launch[2])
            arguments = vllm_arguments(command)
            def flag(name: str, default=None):
                return arguments[arguments.index(name) + 1] if name in arguments else default
            entry["runtime"] = {"image_id": launch[1], "tensor_parallel_size": int(flag("--tensor-parallel-size", "1")),
                                "pipeline_parallel_size": int(flag("--pipeline-parallel-size", "1")),
                                "data_parallel_size": int(flag("--data-parallel-size", "1")),
                                "data_parallel_size_local": int(flag("--data-parallel-size-local", "1")),
                                "expert_parallel": "--enable-expert-parallel" in arguments,
                                "executor": flag("--distributed-executor-backend"), "revision": flag("--revision"),
                                "gpu_memory_utilization": float(flag("--gpu-memory-utilization")),
                                "model": arguments[arguments.index("serve") + 1],
                                "dtype": flag("--dtype"), "attention_backend": flag("--attention-backend"),
                                "moe_backend": flag("--moe-backend"),
                                "kv_transfer_config": json.loads(flag("--kv-transfer-config", "null"))}
            if metadata.get("publication"):
                entry["runtime"]["arguments"] = arguments
            smoke = json.loads((run_dir / "smoke-response.json").read_text(encoding="utf-8"))
            timing = (run_dir / "smoke-timing.txt").read_text(encoding="utf-8").split()
            entry["smoke"] = {"http_status": int(timing[0]), "wall_s": float(timing[1]),
                              "finish_reason": smoke["choices"][0]["finish_reason"],
                              "content": smoke["choices"][0]["message"].get("content"), "usage": smoke["usage"]}
            entry["workloads"] = [summarize_fiveway_perf(run_dir / name) for name in ("perf-short.json", "perf-guide.json")]
            expected_status = ("COMPLETE_WITH_ERRORS" if any(workload["status"] != "PASS" for workload in entry["workloads"])
                               else "PASS")
            if entry["status"] != expected_status:
                raise ValueError(f"{strategy['id']}: completion status contradicts raw request results")
            entry["counts"] = {"formal_requests": sum(workload["n_requests"] for workload in entry["workloads"]),
                               "protocol_complete_requests": sum(workload["n_success"] for workload in entry["workloads"]),
                               "failed_requests": sum(workload["n_failed"] for workload in entry["workloads"]),
                               "complete_answers": sum(workload["n_complete_answers"] for workload in entry["workloads"]),
                               "truncated_answers": sum(workload["n_truncated"] for workload in entry["workloads"])}
            entry["resource_files"] = {}
            for node in ("node0", "node1"):
                resource_path = src / f"resources-{node}.jsonl"
                if not resource_path.exists():
                    continue
                expected_hash = resource_path.with_suffix(".sha256").read_text(encoding="utf-8").split()[0]
                if sha256(resource_path) != expected_hash:
                    raise ValueError(f"Resource evidence hash mismatch: {resource_path.name}")
                samples, resource_summaries = resource_window_summary(resource_path, entry["workloads"])
                relative = Path(strategy["id"]) / resource_path.name
                target = dst / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("w", encoding="utf-8", newline="\n") as output:
                    for sample in samples:
                        output.write(json.dumps(sample) + "\n")
                copied.append(relative.as_posix())
                private_hashes.append(f"{expected_hash}  {resource_path.name}")
                entry["resource_files"][node] = relative.as_posix()
                for workload in entry["workloads"]:
                    for level in workload["levels"]:
                        level.setdefault("resources", {})[node] = resource_summaries[workload["file"]][str(level["concurrency"])]
            for workload in entry["workloads"]:
                for level in workload["levels"]:
                    if level.get("resources"):
                        level["transport"] = {node: transport_rates(resource) for node, resource in level["resources"].items()}
                    if metadata.get("publication"):
                        throughput = level["aggregate_tok_s_median"]
                        level["steady_state_usd_per_million_output_tokens"] = (
                            metadata["billing"]["reference_two_vm_hour"] * 1_000_000 / (throughput * 3600)
                            if throughput else None)
            entry["missing_resource_nodes"] = [f"node{index}" for index in range(metadata["requested_scope"]["nodes"])
                                               if f"node{index}" not in entry["resource_files"]]
            log = (run_dir / "server.log").read_text(encoding="utf-8", errors="replace")
            keep = re.compile(r"Using .*backend|Model loading took|Available KV cache memory|GPU KV cache size|world size .*assigned|Custom.*allreduce is disabled|Application startup complete|KV Transfer metrics:|Sync batch data transfer timeout|hipIpcOpenMemHandle failed|EngineCore encountered a fatal error|TimeoutError|RuntimeError:")
            keylines = "\n".join(line for line in log.splitlines() if keep.search(line)) + "\n"
            key_path = dst / strategy["id"] / "server-keylines.log"
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(redact(keylines), encoding="utf-8", newline="\n")
            copied.append(key_path.relative_to(dst).as_posix())
            private_hashes.append(f"{sha256(run_dir / 'server.log')}  {strategy['id']}/server.log")
            worker_path = run_dir / "worker.log"
            if worker_path.exists():
                worker_log = worker_path.read_text(encoding="utf-8", errors="replace")
                worker_relative = Path(strategy["id"]) / "worker-keylines.log"
                (dst / worker_relative).write_text(redact("\n".join(line for line in worker_log.splitlines() if keep.search(line))) + "\n", encoding="utf-8", newline="\n")
                copied.append(worker_relative.as_posix())
                private_hashes.append(f"{sha256(worker_path)}  {strategy['id']}/worker.log")
            entry["memory"] = {"weight_gib_per_gpu": sorted(set(_all(r"Model loading took ([0-9.]+) GiB", log, float))),
                               "kv_available_gib_per_gpu": sorted(set(_all(r"Available KV cache memory: ([0-9.]+) GiB", log, float))),
                               "kv_cache_tokens": sorted(set(_all(r"GPU KV cache size: ([0-9,]+) tokens", log,
                                                                  lambda value: int(value.replace(",", "")))))}
            for name in ("status.json", "launch.txt", "smoke-response.json", "smoke-timing.txt", "perf-short.json", "perf-guide.json", "gpu-before.json", "gpu-after.json"):
                copy_text(run_dir / name, Path(strategy["id"]) / name)
            for name in ("metrics-before.txt", "metrics-smoke.txt", "metrics-after.txt", "prefill-metrics-before.txt",
                         "prefill-metrics-smoke.txt", "prefill-metrics-after.txt", "proxy-launch.txt", "worker-launch.txt"):
                if (run_dir / name).exists():
                    copy_text(run_dir / name, Path(strategy["id"]) / name)
            entry["native_metrics_status"] = {}
            for path in sorted(run_dir.glob("*-status.json")):
                entry["native_metrics_status"][path.name] = json.loads(path.read_text(encoding="utf-8"))
                copy_text(path, Path(strategy["id"]) / path.name)
            for path in sorted(run_dir.glob("*-error.txt")):
                copy_text(path, Path(strategy["id"]) / path.name)
        summary["strategies"].append(entry)
    workloads = [workload for strategy in summary["strategies"] for workload in strategy.get("workloads", [])]
    summary["counts"] = {"planned_layouts": len(summary["strategies"]),
                         "completed_layouts": sum(strategy["status"] in MEASURED_STATUSES for strategy in summary["strategies"]),
                         "formal_requests": sum(workload["n_requests"] for workload in workloads),
                         "protocol_complete_requests": sum(workload["n_success"] for workload in workloads),
                         "failed_requests": sum(workload["n_failed"] for workload in workloads),
                         "complete_answers": sum(workload["n_complete_answers"] for workload in workloads),
                         "truncated_answers": sum(workload["n_truncated"] for workload in workloads)}
    if any(level.get("transport") for workload in workloads for level in workload["levels"]):
        summary["transport_definition"] = TRANSPORT_DEFINITION
        summary["transport_peaks"] = {}
        network = summary["conditions"].get("network", {})
        nominal = (network["infiniband_ports_per_node"] * network["infiniband_port_rate_gbit_s"] * 1e9 / 8 / 1e6
                   if "infiniband_port_rate_gbit_s" in network else None)
        if nominal:
            summary["transport_nominal_infiniband_mb_s_per_node"] = nominal
        for strategy in summary["strategies"]:
            levels = [level for workload in strategy.get("workloads", []) for level in workload["levels"] if level.get("transport")]
            if levels:
                peaks = {f"{field}_max": max((rates[field] for level in levels for rates in level["transport"].values()
                                              if rates.get(field) is not None), default=None)
                         for field in TRANSPORT_FIELDS}
                if peaks["infiniband_rx_mb_s_max"] is not None:
                    peaks["infiniband_rx_gb_s_max"] = peaks["infiniband_rx_mb_s_max"] / 1000
                if nominal and peaks["infiniband_rx_mb_s_max"] is not None:
                    peaks["infiniband_rx_share_of_nominal_max"] = peaks["infiniband_rx_mb_s_max"] / nominal
                summary["transport_peaks"][strategy["id"]] = peaks
    if summary.get("publication", {}).get("comparisons"):
        summary["comparisons"] = fiveway_comparisons(summary, summary["publication"]["comparisons"])
    if summary.get("publication", {}).get("time_budget"):
        summary["time_budget"] = time_budget(summary, summary["publication"]["time_budget"])
    (dst / "summary.json").write_text(redact(json.dumps(summary, ensure_ascii=False, indent=2)) + "\n", encoding="utf-8", newline="\n")
    (dst / "SHA256SUMS.private.txt").write_text("\n".join(private_hashes) + "\n", encoding="utf-8", newline="\n")
    (dst / "PROJECTION.json").write_text(json.dumps({"run_id": run_id, "public_files": copied,
        "redaction": "Reuses the MI300X role-label redactor. Raw private files are unchanged.",
        "boundary": "Completed sweeps, including failed requests, have original hashes verified. Incomplete strategies remain visible; no performance is invented."}, indent=2) + "\n", encoding="utf-8", newline="\n")
    return dst


def fiveway_tables(summary: dict, language: str) -> str:
    chinese = language == "zh"
    names = {"tp": "TP16", "pp": "TP8 x PP2", "tep": "TP16 + EP", "dp": "DP + EP", "pd": "Prefill/Decode"}
    if summary.get("publication"):
        names = {**names, "pp": "TP8 × PP2"}
    def display(value, digits=1, scale=1):
        return "-" if value is None else f"{value * scale:,.{digits}f}"
    boundary = "延迟分位数只统计传输完整的请求；总吞吐的时间分母保留失败等待。没有成功请求的延迟和没有输出的单位成本记为 `-`。" if chinese else "Latency quantiles include complete streams only; aggregate throughput retains failed-request waiting time. Unavailable latency and unit cost are shown as `-`."
    lines = [boundary, ""]
    for workload_index, filename in enumerate(("perf-short.json", "perf-guide.json")):
        title = (("短工程问题" if workload_index == 0 else "网站部署分析问题") if chinese
                 else ("Short engineering prompt" if workload_index == 0 else "Deployment-guide analysis prompt"))
        measured = [next(workload for workload in strategy["workloads"] if workload["file"] == filename)
                    for strategy in summary["strategies"] if strategy["status"] in MEASURED_STATUSES]
        lengths = sorted({count for workload in measured for level in workload["levels"] for count in level["prompt_tokens"]})
        limits = sorted({workload["max_tokens"] for workload in measured})
        if len(limits) != 1:
            raise ValueError("Workload output limits differ across strategies")
        lines.append(f"**{title}**")
        lines.append("")
        token_counts = ", ".join(map(str, lengths))
        if lengths:
            lines.append((f"服务端记录输入 {token_counts} token（包含聊天模板）；输出上限 {limits[0]} token。" if chinese
                          else f"Server-recorded input: {token_counts} tokens, including the chat template; output limit: {limits[0]} tokens."))
        else:
            lines.append((f"没有成功请求返回输入 token 计数；请求的输出上限为 {limits[0]} token。" if chinese
                          else f"No successful request returned an input-token count; requested output limit: {limits[0]} tokens."))
        lines.append("")
        lines.append("| 布局 | 并发数（concurrency） | 首文本延迟中位数（ms） | 首文本延迟 P95（ms） | E2E 中位数（s） | E2E P95（s） | 单请求解码估计（token/s） | 总吞吐（token/s） | 传输完整/发出请求 | 完整答案/传输完整 | 稳态计算费（美元/百万输出 token） |" if chinese else
                 "| Layout | Concurrent requests | Median first-text latency (ms) | P95 first-text latency (ms) | Median E2E (s) | P95 E2E (s) | Per-request decode estimate (token/s) | Aggregate throughput (token/s) | Complete streams/requests sent | Complete answers/complete streams | Steady-state compute (USD/million output tokens) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for strategy in summary["strategies"]:
            if strategy["status"] not in MEASURED_STATUSES:
                status_names = {"BLOCKED_PLATFORM_INTERRUPTION": ("中断，数据未齐", "Interrupted; incomplete data"),
                                "IN_PROGRESS": ("进行中", "In progress"), "NOT_RUN": ("未测", "Not run"),
                                "EXCLUDED": ("网站置灰，未测", "Greyed out on the website; not run"),
                                "BLOCKED_RESOURCE_SCOPE": ("网站配置需 4 节点，未测", "Website configuration needs 4 nodes; not run")}
                status = status_names.get(strategy["status"], ("未完成", "Incomplete"))[0 if chinese else 1]
                lines.append(f"| {names[strategy['id']]} | {status} | - | - | - | - | - | - | - | - | - |")
                continue
            workload = next(item for item in strategy["workloads"] if item["file"] == filename)
            for level in workload["levels"]:
                throughput = level["aggregate_tok_s_median"]
                cost = (summary["billing_reference"]["reference_two_vm_hour"] * 1_000_000 / (throughput * 3600)
                    if throughput is not None and throughput > 0 else None)
                cost = level.get("steady_state_usd_per_million_output_tokens", cost)
                lines.append(f"| {names[strategy['id']]} | {level['concurrency']} | {display(level['ttft_s_median'], 0, 1000)} | "
                         f"{display(level.get('ttft_s_p95'), 0, 1000)} | {display(level.get('e2e_s_median', level.get('wall_s_median')), 2)} | "
                         f"{display(level.get('e2e_s_p95'), 2)} | {display(level['decode_tok_s_median'])} | {display(throughput)} | "
                         f"{level['n_success']}/{level['n_requests']} | {level['n_complete_answers']}/{level['n_success']} | {display(cost, 2)} |")
        lines.append("")
    if summary.get("publication") and summary.get("transport_peaks"):
        lines.extend(transport_tables(summary, chinese, names))
    return "\n".join(lines).rstrip()


def transport_number(value) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    return f"{value:,.0f}" if value >= 10 else f"{value:.1f}"


def transport_tables(summary: dict, chinese: bool, names: dict) -> list[str]:
    """Inter-node traffic tables for runs that publish a two-node resource projection."""
    measured = [strategy for strategy in summary["strategies"] if strategy["status"] in MEASURED_STATUSES]
    concurrency = summary["conditions"]["planned_concurrency"]
    titles = {"perf-short.json": ("短工程问题", "Short prompt"), "perf-guide.json": ("网站部署分析问题", "Guide prompt")}
    if chinese:
        intro = ("每格两个数，依次是节点 0 和节点 1：该节点 8 个 InfiniBand 端口（`mlx5_ib*`，RDMA verbs 流量）的接收速率之和，"
                 "取 3 轮正式请求时间窗内每秒采样的均值，单位 MB/s（10^6 字节/秒）；10 MB/s 以上取整，以下保留一位小数。"
                 "第二张表列出每个布局在任一节点上这些均值中的最高值，并补充 IPoIB（`ib*` 网络接口）和 `eth0` 两类接口。")
        first = "布局 · 输入（每格：节点 0 / 节点 1 的 InfiniBand 接收，MB/s）"
        column = "并发请求数：{count}"
        peak_header = ("| 布局 | InfiniBand 接收，各档均值中最高（MB/s） | IPoIB 接收，各档均值中最高（MB/s） | "
                       "eth0 接收，各档均值中最高（MB/s） |")
    else:
        intro = ("Each cell holds two numbers, node 0 then node 1: the receive rate summed over that node's eight InfiniBand "
                 "ports (`mlx5_ib*`, RDMA verbs traffic), averaged over the one-second samples inside the three measured "
                 "rounds, in MB/s (10^6 bytes per second), rounded to whole numbers, or to one decimal below 10 MB/s. "
                 "The second table lists, per layout, the highest of these averages on either node, also for the IPoIB "
                 "(`ib*` network interfaces) and `eth0` interfaces.")
        first = "Layout · input (cells: node 0 / node 1 InfiniBand receive, MB/s)"
        column = "Concurrent requests: {count}"
        peak_header = ("| Layout | InfiniBand receive, highest level average (MB/s) | IPoIB receive, highest level average (MB/s) | "
                       "eth0 receive, highest level average (MB/s) |")
    lines = ["**测量轮次内的跨节点流量**" if chinese else "**Inter-node traffic inside the measured rounds**", "", intro, ""]
    lines.append(f"| {first} | " + " | ".join(column.format(count=count) for count in concurrency) + " |")
    lines.append("|---|" + "---:|" * len(concurrency))
    for strategy in measured:
        for workload in strategy["workloads"]:
            cells = []
            for level in workload["levels"]:
                rates = [level.get("transport", {}).get(node, {}).get("infiniband_rx_mb_s") for node in ("node0", "node1")]
                cells.append(" / ".join(transport_number(rate) for rate in rates))
            label = titles[workload["file"]][0 if chinese else 1]
            lines.append(f"| {names[strategy['id']]} · {label} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(peak_header)
    lines.append("|---|---:|---:|---:|")
    for strategy in measured:
        peaks = summary["transport_peaks"][strategy["id"]]
        cells = [transport_number(peaks[f"{field}_max"]) for field in ("infiniband_rx_mb_s", "ipoib_rx_mb_s", "eth0_rx_mb_s")]
        lines.append(f"| {names[strategy['id']]} | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def time_budget_table(summary: dict, chinese: bool) -> str:
    """The per-token time budget as one Markdown table; every value is read from summary["time_budget"]."""
    budget, spec = summary["time_budget"], summary["publication"]["time_budget"]
    names = {"tp": "TP16", "pp": "TP8 × PP2", "tep": "TP16 + EP"}
    inputs = {"perf-short.json": ("短问题", "short prompt"), "perf-guide.json": ("部署分析问题", "deployment-analysis prompt")}
    workload = inputs[budget["workload"]][0 if chinese else 1]
    reference = budget["reference_layout"]
    nominal = budget["nominal_infiniband_mb_s_per_node"] / 1000
    collectives = budget["estimate"]["cross_node_collectives_per_token"]
    layers, per_layer = spec["language_layers"], spec["cross_node_collectives_per_layer"]
    outside = spec["collectives_per_step_outside_layers"]

    def size(value: float) -> str:
        return f"{value / 1e6:.1f} MB" if value >= 1e6 else f"{value / 1e3:.0f} KB"

    def micro(value: float) -> str:
        return f"{value:.0f}" if value >= 10 else f"{value:.2f}"

    if chinese:
        header = (f"| 布局（{workload}，并发 {budget['concurrency']}） | 每个输出 token 的时间（ms，实测） | "
                  f"比 {names[reference]} 每个 token 多用的时间（ms） | 较忙节点每个输出 token 的 InfiniBand 接收量（实测，含输入部分的分摊） | "
                  f"这些数据以每节点 {nominal:.0f} GB/s 传输所需时间（µs） | 每个 token 的集合通信与跨节点交接（按 vLLM 源码估算） |")
    else:
        header = (f"| Layout ({workload}, concurrency {budget['concurrency']}) | Time per output token (ms, measured) | "
                  f"Extra time per token vs {names[reference]} (ms) | InfiniBand receive per output token, busier node (measured, prompt share included) | "
                  f"Time to move it at {nominal:.0f} GB/s per node (µs) | Collectives and cross-node hand-offs per token (estimated from the vLLM source) |")
    lines = [header, "|---|---:|---:|---:|---:|---|"]
    for layout in [reference] + [item for item in spec["layouts"] if item != reference]:
        entry = budget["layouts"][layout]
        if layout == reference:
            extra = "0（基准）" if chinese else "0 (reference)"
            sync = (f"{collectives} 次集合通信都在节点内；流水级之间交接 1 次" if chinese
                    else f"{collectives} collectives, all inside a node; 1 hand-off between the pipeline stages")
        else:
            extra = f"{entry['extra_ms_per_output_token_vs_reference']:.1f}"
            sync = (f"约 {collectives} 次集合通信都跨节点（{layers} 层 × {per_layer} 次 all-reduce，再加 {outside} 次）" if chinese
                    else f"≈{collectives} collectives, all across nodes ({layers} layers × {per_layer} all-reduces, plus {outside})")
            if layout != budget["estimate"]["layout"]:
                sync += ("；页面说明 Triton 专家内核在专家并行下更慢" if chinese
                         else "; the page notes that the Triton expert kernels are slower with expert parallelism")
        lines.append(f"| {names[layout]} | {entry['ms_per_output_token']:.1f} | {extra} | "
                     f"{size(entry['busier_node_infiniband_rx_bytes_per_output_token'])} | "
                     f"{micro(entry['transfer_us_per_output_token_at_nominal'])} | {sync} |")
    lines.extend(["", (
        "每个 token 的时间与差值都先用未舍入的原值计算，再分别四舍五入；直接相减表中的显示值，末位数字可能与差值列不同。"
        if chinese else
        "Per-token times and differences are calculated from unrounded values, then rounded separately; subtracting the displayed times can differ from the difference column by one last-place digit."
    )])
    return "\n".join(lines)


def render_fiveway_tables(path: Path) -> None:
    summary = json.loads(path.read_text(encoding="utf-8"))
    marker = "QWEN FIVEWAY RESULTS" if summary["scope"]["model"].startswith("Qwen/") else "FIVEWAY RESULTS"
    if summary.get("parent_run_id"):
        marker = "QWEN RECOVERY FIVEWAY RESULTS"
    marker = summary.get("publication", {}).get("marker", marker)
    for filename, language in (("README.md", "en"), ("README_CN.md", "zh")):
        target = ROOT / filename
        text = target.read_text(encoding="utf-8")
        pattern = rf"<!-- BEGIN {marker} -->.*?<!-- END {marker} -->"
        if len(re.findall(pattern, text, flags=re.S)) != 1:
            raise ValueError(f"{filename}: expected exactly one fiveway result region")
        replacement = f"<!-- BEGIN {marker} -->\n" + fiveway_tables(summary, language) + f"\n<!-- END {marker} -->"
        text = re.sub(pattern, lambda match: replacement, text, flags=re.S)
        if summary.get("time_budget"):
            budget_marker = re.sub(r" RESULTS$", "", marker) + " TIME BUDGET"
            budget_pattern = rf"<!-- BEGIN {budget_marker} -->.*?<!-- END {budget_marker} -->"
            if len(re.findall(budget_pattern, text, flags=re.S)) != 1:
                raise ValueError(f"{filename}: expected exactly one time-budget region")
            budget_region = (f"<!-- BEGIN {budget_marker} -->\n" + time_budget_table(summary, language == "zh")
                             + f"\n<!-- END {budget_marker} -->")
            text = re.sub(budget_pattern, lambda match: budget_region, text, flags=re.S)
        target.write_text(text, encoding="utf-8", newline="\n")


def init_fiveway(destination: Path, template_path: Path) -> None:
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError("Choose a new run directory; existing runs are never overwritten")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", destination.name):
        raise ValueError("Run directory name must use letters, digits, underscores or hyphens")
    template = json.loads(template_path.read_text(encoding="utf-8"))
    keys = ("id", "website_name", "website_label", "candidate_layout", "hypothesis", "discriminating_check")
    descriptive = ("website_description_verbatim", "scope_boundary", "required_nodes", "required_gpus", "available_nodes", "figure")
    strategies = [{**{key: item[key] for key in keys}, **{key: item[key] for key in descriptive if key in item}, "status": "NOT_RUN"}
                  for item in template["strategies"]]
    metadata = {"run_id": destination.name, "status": "NOT_RUN", "requested_scope": template["scope"],
                "source": template["source"], "common_conditions": template["conditions"], "strategies": strategies,
                "billing": template["billing_reference"], "evidence": {"remote_root": destination.as_posix()},
                "boundary": "Template conditions and prices are historical; verify hardware, compatibility and current billing before execution. No old scores were copied."}
    if "publication" in template:
        # A fresh run never writes into the published regions or figures of the run it was initialized from.
        metadata["publication"] = {**template["publication"], "marker": f"FIVEWAY RESULTS {destination.name}",
                                   "figure_basename": f"mi300x-{destination.name}"}
    (destination / "source").mkdir(parents=True)
    scripts = ["00_env.sh", "09_perf_probe.py", "10_measure_layout.sh", "Dockerfile.muse-ray"]
    if template["scope"]["model"].startswith("Qwen/"):
        scripts.extend(("11_serve_qwen_fiveway.sh", "12_resource_monitor.py", "13_mooncake_transfer_probe.py",
                        "mooncake_connector_proxy.py"))
    else:
        scripts.extend(("08_serve_muse_2node.sh", "12_resource_monitor.py", "14_run_remaining_layouts.sh"))
    for name in scripts:
        shutil.copy2(ROOT / "scripts" / "mi300x" / name, destination / "source" / name)
    for name in ("guide_prompt.txt", "smoke_request.json"):
        shutil.copy2(template_path.parent / name, destination / name)
    (destination / "run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "init-fiveway":
        init_fiveway(Path(argv[2]), Path(argv[3])); print("fresh fiveway run initialized; no inference executed"); return 0
    if len(argv) == 3 and argv[1] == "render-fiveway":
        render_fiveway_tables(Path(argv[2])); print("fiveway tables rendered from summary"); return 0
    if len(argv) == 3 and argv[1] == "project-fiveway":
        print(f"projected -> {project_fiveway(Path(argv[2]))}"); return 0
    if len(argv) >= 2 and argv[1] == "project":
        if len(argv) != 4:
            print(__doc__); return 2
        dst = project(Path(argv[2]), argv[3]); print(f"projected -> {dst}"); return 0
    if len(argv) >= 2 and argv[1] == "project-rccl":
        if len(argv) != 3:
            print(__doc__); return 2
        dst = project_rccl(Path(argv[2])); print(f"projected -> {dst}"); return 0
    if len(argv) >= 2 and argv[1] == "summarize":
        s = summarize(); print(f"summary.json: {len(s['runs'])} runs"); return 0
    if len(argv) >= 2 and argv[1] == "table":
        print(table(json.loads((PUBLIC / "summary.json").read_text(encoding="utf-8")))); return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
