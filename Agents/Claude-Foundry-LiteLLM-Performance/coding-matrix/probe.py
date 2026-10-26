"""Ask each deployment which parameter values it accepts (Qira-style 400 probing).

Writes one JSONL line per probe request and a summary of accepted
thinking-mode x effort combinations that defines the benchmark matrix.
"""
import argparse
import json
import re
import threading
from pathlib import Path

from claude_api import TokenProvider, new_client, sha256_json, stream_message

MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
CANDIDATE_EFFORTS = ["low", "medium", "high", "xhigh", "max"]
PROMPT = "Reply with exactly one word: OK"


def make_body(model, thinking="adaptive", effort=None, max_tokens=1024, **extra):
    body = {"model": model, "max_tokens": max_tokens, "stream": True,
            "messages": [{"role": "user", "content": PROMPT}]}
    if thinking == "enabled":
        body["thinking"] = {"type": "enabled", "budget_tokens": 1024}
    elif thinking is not None:
        body["thinking"] = {"type": thinking}
    if effort is not None:
        body["output_config"] = {"effort": effort}
    body.update(extra)
    return body


def error_message(record):
    body = record.get("error_body") or {}
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return error.get("message")
    return json.dumps(body)[:600] if body else None


def thinking_tokens(record):
    usage = record.get("usage") or {}
    return (usage.get("output_tokens_details") or {}).get("thinking_tokens")


def run_model(model, out_path, lock, summary):
    client, tokens = new_client(), TokenProvider()
    results = []

    def probe(name, body):
        record = stream_message(client, tokens, body, deadline_s=300)
        row = {"model": model, "probe": name, "request": body, "request_sha256": sha256_json(body),
               "status": record["status"], "http_status": record["http_status"],
               "error_message": error_message(record), "stop_reason": record.get("stop_reason"),
               "usage": record.get("usage"), "thinking_tokens": thinking_tokens(record),
               "timing": record.get("timing"), "headers": record.get("headers"),
               "text_head": (record.get("text") or "")[:80], "sent_utc": record["sent_utc"]}
        with lock:
            with out_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        results.append(row)
        return row

    invalid = probe("effort_invalid", make_body(model, effort="probe-invalid-value"))
    listed = re.findall(r"'([a-z]+)'", invalid.get("error_message") or "")
    efforts = list(dict.fromkeys(CANDIDATE_EFFORTS + [value for value in listed if value not in ("adaptive",)]))
    accepted = {}
    for mode in ("adaptive", "disabled", "between_tools"):
        accepted[mode] = []
        for effort in efforts:
            row = probe(f"{mode}_{effort}", make_body(model, thinking=mode, effort=effort))
            if row["http_status"] == 200:
                accepted[mode].append(effort)
        probe(f"{mode}_default_effort", make_body(model, thinking=mode))
    probe("thinking_omitted", make_body(model, thinking=None))
    probe("thinking_enabled_budget", make_body(model, thinking="enabled", max_tokens=2048))
    off_mode = next((mode for mode in ("disabled", "between_tools") if accepted[mode]), None)
    for mode in [m for m in ("adaptive", off_mode) if m]:
        probe(f"{mode}_temperature_0.5", make_body(model, thinking=mode, effort="medium", temperature=0.5))
        probe(f"{mode}_top_p_0.9", make_body(model, thinking=mode, effort="medium", top_p=0.9))
        probe(f"{mode}_top_k_40", make_body(model, thinking=mode, effort="medium", top_k=40))
    probe("max_tokens_1000000", make_body(model, effort="low", max_tokens=1_000_000))
    probe("max_tokens_32000", make_body(model, effort="low", max_tokens=32000))
    long_system = "Reference notes for this probe. " * 400
    probe("cache_ttl_1h_system", make_body(
        model, effort="low",
        system=[{"type": "text", "text": long_system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]))
    probe("cache_top_level_auto", make_body(model, effort="low", cache_control={"type": "ephemeral"}))
    for index in range(4):
        probe(f"tpm_burst_{index + 1}", make_body(model, effort="low", max_tokens=32000))
    with lock:
        summary[model] = {"listed_in_400": listed, "accepted": accepted,
                          "requests": len(results),
                          "http_200": sum(1 for row in results if row["http_status"] == 200)}
    client.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "probe_results.jsonl"
    lock, summary = threading.Lock(), {}
    threads = [threading.Thread(target=run_model, args=(model, out_path, lock, summary)) for model in MODELS]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    (out_dir / "probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
