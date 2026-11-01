"""Long-input variants of the test records, for measuring on-device cost (latency, memory) at a chosen input length.

The message, device fields, questions and labels of each test record stay exactly as they are; the state gains one
extra field, `device_log`, filled with synthetic but realistic laptop diagnostic lines until the whole request is
about --target-tokens long. The padding is deterministic (seeded by the record's case id) and contains no policy
field and no mention of queues, so it should not change the answer; whether it does is reported by the run, not assumed.

This measures criteria 3 and 4 (latency, memory) at a long input. It does NOT measure accuracy at that length: the
labels are those of the short record, and the appended log is noise. Token counts are approximated with a
characters-per-token ratio and confirmed from the server's usage.input_tokens after the run.

  python make_long_state.py --data data/contoso/final --workload support --target-tokens 7800 --limit 40 --out data/contoso/final/long8k_test_support.jsonl
"""
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_vendor_data import read_jsonl, write_jsonl  # noqa: E402

# Qwen tokenizer: roughly 3.6 characters per token on this kind of ASCII log text (checked against usage.input_tokens of
# the first run; adjust --chars-per-token if the server reports a different ratio).
LEVELS = ("INFO", "INFO", "INFO", "WARN", "DEBUG")
COMPONENTS = ("power.mgr", "thermal.svc", "wifi.drv", "bt.stack", "disp.ctl", "audio.hda", "storage.nvme", "bios.acpi", "usb.hub", "sensor.hub")
EVENTS = ("heartbeat ok", "state poll", "cadence tick", "sampler cycle", "metric flush", "queue drain", "watchdog kick", "cache sync", "link check", "timer wake")


def log_lines(rng, n):
    t = rng.randint(1_700_000_000, 1_760_000_000)
    out = []
    for _ in range(n):
        t += rng.randint(1, 9)
        out.append(f"{t} {rng.choice(LEVELS):5} {rng.choice(COMPONENTS):12} {rng.choice(EVENTS)} id={rng.randint(1000, 9999)} "
                   f"v={rng.random():.3f} d={rng.randint(0, 999)}ms")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data", required=True)
    ap.add_argument("--workload", default="support")
    ap.add_argument("--target-tokens", type=int, default=7800)
    ap.add_argument("--chars-per-token", type=float, default=3.6)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    records = read_jsonl(Path(a.data) / f"test_{a.workload}.jsonl")[: a.limit]
    out = []
    for r in records:
        base_chars = len(json.dumps(r["state"], ensure_ascii=False)) + len(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "label"} for k, v in r["questions"].items()}, ensure_ascii=False))
        need = max(0, int(a.target_tokens * a.chars_per_token) - base_chars)
        rng = random.Random(int(hashlib.sha256(r["_meta"]["case"].encode()).hexdigest()[:8], 16))
        lines = []
        while sum(len(l) + 1 for l in lines) < need:
            lines += log_lines(rng, 50)
        state = dict(r["state"])
        state["device_log"] = "\n".join(lines)
        meta = dict(r["_meta"])
        meta.update({"case": meta["case"] + "-long", "aug": f"long-{a.target_tokens}", "approx_tokens": a.target_tokens})
        out.append({"state": state, "questions": r["questions"], "_meta": meta})
    write_jsonl(Path(a.out), out)
    chars = [len(json.dumps(x["state"], ensure_ascii=False)) for x in out]
    print(json.dumps({"records": len(out), "state_chars_min": min(chars), "state_chars_max": max(chars),
                      "approx_tokens_target": a.target_tokens, "sha256": hashlib.sha256(Path(a.out).read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
