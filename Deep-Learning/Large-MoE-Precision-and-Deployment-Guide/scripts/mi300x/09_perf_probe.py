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
import json, sys, time, threading, urllib.request, argparse, statistics, subprocess, os

ap = argparse.ArgumentParser()
ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--base", default="http://127.0.0.1:8000")
ap.add_argument("--conc", default="1,8")
ap.add_argument("--rounds", type=int, default=3)
ap.add_argument("--max-tokens", type=int, default=256)
ap.add_argument("--prompt", default="Explain in about 150 words why mixture-of-experts models keep the router in higher precision than the experts.")
ap.add_argument("--prompt-file")
ap.add_argument("--timeout", type=float, default=900)
a = ap.parse_args()
if a.prompt_file:
    with open(a.prompt_file, encoding="utf-8") as prompt_file:
        a.prompt = prompt_file.read()

def one_stream(idx, results):
    body = json.dumps({"model": a.model, "messages": [{"role": "user", "content": a.prompt}],
                       "max_tokens": a.max_tokens, "temperature": 0, "stream": True,
                       "stream_options": {"include_usage": True}}).encode()
    req = urllib.request.Request(a.base + "/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    started_unix_s = time.time()
    t_send = time.perf_counter(); t_first = None; t_last = None; usage = None; chunks = 0; finish = None
    first_content = None; first_reasoning = None; content = []; reasoning = []; error = None; completed = False
    request_id = None
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"): continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    completed = True
                    break
                event = json.loads(payload)
                now = time.perf_counter()
                request_id = event.get("id", request_id)
                if event.get("usage"): usage = event["usage"]
                if event.get("error"):
                    error = {"type": "ServerStreamError", "detail": event["error"]}
                    break
                for choice in event.get("choices", []):
                    delta = choice.get("delta", {})
                    text = delta.get("content")
                    thought = delta.get("reasoning_content") or delta.get("reasoning")
                    if text:
                        content.append(text)
                        if first_content is None: first_content = now
                    if thought:
                        reasoning.append(thought)
                        if first_reasoning is None: first_reasoning = now
                    if text or thought:
                        chunks += 1; t_last = now
                        if t_first is None: t_first = now
                    if choice.get("finish_reason"): finish = choice["finish_reason"]
    except Exception as exception:
        error = {"type": type(exception).__name__, "http_status": getattr(exception, "code", None)}
    t_end = time.perf_counter()
    if error is None and (not completed or not usage or not finish or t_first is None):
        error = {"type": "IncompleteStream", "done_received": completed, "usage_received": bool(usage)}
    ct = (usage or {}).get("completion_tokens")
    dec = None
    if ct and t_first and t_last and t_last > t_first and ct > 1:
        dec = (ct - 1) / (t_last - t_first)
    results[idx] = {"ttft_s": (t_first - t_send) if t_first else None, "decode_tok_s": dec,
                    "completion_tokens": ct, "prompt_tokens": (usage or {}).get("prompt_tokens"),
                    "text_chunks": chunks, "finish_reason": finish, "wall_s": t_end - t_send,
                    "first_content_s": first_content - t_send if first_content is not None else None,
                    "first_reasoning_s": first_reasoning - t_send if first_reasoning is not None else None,
                    "content": "".join(content), "reasoning": "".join(reasoning), "usage": usage,
                    "request_id": request_id, "error": error, "status": "FAILED" if error else "OK",
                    "answer_complete": error is None and finish == "stop" and bool(content),
                    "started_unix_s": started_unix_s, "finished_unix_s": time.time(),
                    "t_send": t_send, "t_end": t_end}

def p95(values):
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[94]

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

def persist_report(record):
    temporary = a.out + ".tmp"
    with open(temporary, "w", encoding="utf-8") as output:
        json.dump(record, output, indent=1)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, a.out)

report = {"model": a.model, "base": a.base, "prompt": a.prompt, "max_tokens": a.max_tokens, "rounds": a.rounds,
          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpu_mem_before": gpu_mem(), "levels": []}
report["metric_definitions"] = {
    "ttft_s": "Request send to first streamed reasoning or content text; not necessarily final-answer text.",
    "first_content_s": "Request send to first streamed final-answer content text.",
    "decode_tok_s": "(completion_tokens - 1) / time between first and last text-bearing chunks; token-rate estimate, not per-token event latency.",
    "wall_s": "Request send to stream completion or failure, including terminal usage and protocol handling.",
    "wall_s_statistics": "Median and P95 use protocol-complete requests; failures retain raw wall time and remain in request counts.",
    "p95_estimator": "Inclusive linear interpolation; small or repeated-prompt samples do not establish production tail latency.",
    "agg_tok_s": "Tokens from protocol-complete requests divided by the whole round span, including failed-request time."
}
report["request_parameters"] = {"temperature": 0, "stream": True, "stream_options": {"include_usage": True}, "timeout_s": a.timeout}
report["status"] = "IN_PROGRESS"
report["checkpoint_granularity"] = "completed_round"
persist_report(report)
# warm-up: one request so JIT/graph capture does not land in the measured rounds
w = {}; one_stream(0, w); report["warmup"] = {k: v for k, v in w[0].items() if not k.startswith("t_")}
persist_report(report)
for conc in [int(x) for x in a.conc.split(",")]:
    rounds = []
    report["partial_level"] = {"concurrency": conc, "rounds": rounds}
    for r in range(a.rounds):
        persist_report(report)
        res = {}; th = [threading.Thread(target=one_stream, args=(i, res)) for i in range(conc)]
        round_started_unix_s = time.time()
        t0 = time.perf_counter()
        for t in th: t.start()
        for t in th: t.join()
        rs = [res[i] for i in range(conc)]
        tot_tokens = sum((x["completion_tokens"] or 0) for x in rs if x["status"] == "OK")
        span = max(x["t_end"] for x in rs) - min(x["t_send"] for x in rs)
        rounds.append({"requests": [{k: v for k, v in x.items() if not k.startswith("t_")} for x in rs],
                       "agg_tok_s": tot_tokens / span if span > 0 else None, "span_s": span, "total_completion_tokens": tot_tokens,
                       "started_unix_s": round_started_unix_s, "finished_unix_s": time.time(),
                       "n_success": sum(x["status"] == "OK" for x in rs), "n_failed": sum(x["status"] != "OK" for x in rs)})
    ttfts = [x["ttft_s"] for rd in rounds for x in rd["requests"] if x["status"] == "OK" and x["ttft_s"] is not None]
    decs = [x["decode_tok_s"] for rd in rounds for x in rd["requests"] if x["status"] == "OK" and x["decode_tok_s"] is not None]
    walls = [request["wall_s"] for batch in rounds for request in batch["requests"] if request["status"] == "OK"]
    aggs = [rd["agg_tok_s"] for rd in rounds if rd["agg_tok_s"] is not None]
    report["levels"].append({"concurrency": conc, "rounds": rounds,
                             "ttft_s_median": statistics.median(ttfts) if ttfts else None,
                             "ttft_s_max": max(ttfts) if ttfts else None,
                             "ttft_s_p95": p95(ttfts),
                             "e2e_s_median": statistics.median(walls) if walls else None,
                             "e2e_s_p95": p95(walls),
                             "decode_tok_s_per_request_median": statistics.median(decs) if decs else None,
                             "agg_tok_s_median": statistics.median(aggs) if aggs else None,
                             "n_requests": sum(len(rd["requests"]) for rd in rounds),
                             "n_success": sum(rd["n_success"] for rd in rounds),
                             "n_failed": sum(rd["n_failed"] for rd in rounds),
                             "n_complete_answers": sum(x["answer_complete"] for rd in rounds for x in rd["requests"])})
    report.pop("partial_level", None)
    persist_report(report)
    print(f"conc={conc} ttft_med={report['levels'][-1]['ttft_s_median']} dec_med={report['levels'][-1]['decode_tok_s_per_request_median']} agg_med={report['levels'][-1]['agg_tok_s_median']}", flush=True)
report["gpu_mem_after"] = gpu_mem()
report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
report["status"] = "FAILED" if report["warmup"]["status"] != "OK" or any(level["n_failed"] for level in report["levels"]) else "PASS"
persist_report(report)
print("PERF_DONE", a.out)
if report["status"] != "PASS":
    raise SystemExit(1)
