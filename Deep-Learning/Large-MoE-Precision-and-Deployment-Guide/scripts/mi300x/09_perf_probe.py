#!/usr/bin/env python3
"""09_perf_probe.py <served_model_name> <out_json> [--base http://127.0.0.1:8000] [--conc 1,8] [--rounds 3]

Small serving probe for one running vLLM server: streams chat completions and records, per request,
time-to-first-token (TTFT) and decode throughput, then aggregates per concurrency level.
Stdlib only (runs on the node's host Python). Not a benchmark: 3 rounds x {1,8} concurrent streams of one
fixed prompt with max_tokens 256 at temperature 0. It answers "roughly how fast is this deployment" and
nothing else; distributions, long prompts and large batches are out of scope.

Definitions written into the JSON (so the README can quote them without ambiguity):
  ttft_s           wall time from request send to the first streamed chunk whose delta carries text
                   (reasoning or content). For reasoning models the first visible token is reasoning text.
  decode_tok_s     (completion_tokens - 1) / (time of last chunk - time of first text chunk), per request
  agg_tok_s        sum(completion_tokens) / (last finish - first send) over all streams of one round
  completion_tokens  from the final `usage` object the server emits (stream_options.include_usage=true)
"""
import json, sys, time, threading, urllib.request, argparse, statistics, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--base", default="http://127.0.0.1:8000")
ap.add_argument("--conc", default="1,8")
ap.add_argument("--rounds", type=int, default=3)
ap.add_argument("--max-tokens", type=int, default=256)
ap.add_argument("--prompt", default="Explain in about 150 words why mixture-of-experts models keep the router in higher precision than the experts.")
a = ap.parse_args()

def one_stream(idx, results):
    body = json.dumps({"model": a.model, "messages": [{"role": "user", "content": a.prompt}],
                       "max_tokens": a.max_tokens, "temperature": 0, "stream": True,
                       "stream_options": {"include_usage": True}}).encode()
    req = urllib.request.Request(a.base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    t_send = time.perf_counter(); t_first = None; t_last = None; usage = None; chunks = 0; finish = None
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"): continue
            payload = line[5:].strip()
            if payload == "[DONE]": break
            d = json.loads(payload)
            now = time.perf_counter()
            if d.get("usage"): usage = d["usage"]
            for ch in d.get("choices", []):
                delta = ch.get("delta", {})
                if delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning"):
                    chunks += 1; t_last = now
                    if t_first is None: t_first = now
                if ch.get("finish_reason"): finish = ch["finish_reason"]
    ct = (usage or {}).get("completion_tokens")
    dec = None
    if ct and t_first and t_last and t_last > t_first and ct > 1:
        dec = (ct - 1) / (t_last - t_first)
    results[idx] = {"ttft_s": (t_first - t_send) if t_first else None, "decode_tok_s": dec,
                    "completion_tokens": ct, "prompt_tokens": (usage or {}).get("prompt_tokens"),
                    "text_chunks": chunks, "finish_reason": finish, "wall_s": (t_last or time.perf_counter()) - t_send,
                    "t_send": t_send, "t_end": t_last or time.perf_counter()}

def gpu_mem():
    try:
        out = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--json"], capture_output=True, text=True, timeout=30).stdout
        d = json.loads(out)
        used = []; total = []
        for k, v in sorted(d.items()):
            u = v.get("VRAM Total Used Memory (B)"); t = v.get("VRAM Total Memory (B)")
            if u and t: used.append(int(u)); total.append(int(t))
        return {"gpus": len(used), "used_gib_per_gpu": [round(x / 2**30, 1) for x in used], "total_gib_per_gpu": [round(x / 2**30, 1) for x in total]}
    except Exception as e:
        return {"error": str(e)[:200]}

report = {"model": a.model, "base": a.base, "prompt": a.prompt, "max_tokens": a.max_tokens, "rounds": a.rounds,
          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpu_mem_before": gpu_mem(), "levels": []}
# warm-up: one request so JIT/graph capture does not land in the measured rounds
w = {}; one_stream(0, w); report["warmup"] = {k: v for k, v in w[0].items() if not k.startswith("t_")}
for conc in [int(x) for x in a.conc.split(",")]:
    rounds = []
    for r in range(a.rounds):
        res = {}; th = [threading.Thread(target=one_stream, args=(i, res)) for i in range(conc)]
        t0 = time.perf_counter()
        for t in th: t.start()
        for t in th: t.join()
        rs = [res[i] for i in range(conc)]
        tot_tokens = sum((x["completion_tokens"] or 0) for x in rs)
        span = max(x["t_end"] for x in rs) - min(x["t_send"] for x in rs)
        rounds.append({"requests": [{k: v for k, v in x.items() if not k.startswith("t_")} for x in rs],
                       "agg_tok_s": tot_tokens / span if span > 0 else None, "span_s": span, "total_completion_tokens": tot_tokens})
    ttfts = [x["ttft_s"] for rd in rounds for x in rd["requests"] if x["ttft_s"] is not None]
    decs = [x["decode_tok_s"] for rd in rounds for x in rd["requests"] if x["decode_tok_s"] is not None]
    aggs = [rd["agg_tok_s"] for rd in rounds if rd["agg_tok_s"]]
    report["levels"].append({"concurrency": conc, "rounds": rounds,
                             "ttft_s_median": statistics.median(ttfts) if ttfts else None,
                             "ttft_s_max": max(ttfts) if ttfts else None,
                             "decode_tok_s_per_request_median": statistics.median(decs) if decs else None,
                             "agg_tok_s_median": statistics.median(aggs) if aggs else None,
                             "n_requests": len(ttfts)})
    print(f"conc={conc} ttft_med={report['levels'][-1]['ttft_s_median']} dec_med={report['levels'][-1]['decode_tok_s_per_request_median']} agg_med={report['levels'][-1]['agg_tok_s_median']}", flush=True)
report["gpu_mem_after"] = gpu_mem()
report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
with open(a.out, "w") as f: json.dump(report, f, indent=1)
print("PERF_DONE", a.out)
