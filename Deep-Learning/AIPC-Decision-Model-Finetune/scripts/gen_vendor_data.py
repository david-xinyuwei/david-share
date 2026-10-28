#!/usr/bin/env python3
"""Simulated private decision data for Contoso PC: code samples cases and computes labels, an LLM writes the text.

  python gen_vendor_data.py sample --workload support --n 1400 --seed 11 --out data/support/g1.cases.jsonl
  python gen_vendor_data.py render --cases data/support/g1.cases.jsonl --out data/support/g1.texts.jsonl --dry-run
  python gen_vendor_data.py render --cases ... --out ... --model <deployment>      # needs GEN_BASE_URL, GEN_API_KEY
  python gen_vendor_data.py build --workload support --cases ... --texts ... --out data/support/g1 --splits 70,10,10,10
  python gen_vendor_data.py build ... --out data/support/ood --splits 0,0,0,100                          # all test

GEN_BASE_URL is an OpenAI-compatible base (Azure OpenAI: https://<resource>.openai.azure.com/openai/v1).
GEN_AUTH selects the key header: api-key (default), bearer, apim. The key is read from GEN_API_KEY and never printed.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vendor_policy import WORKLOADS, record_of, rng_for  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")

SYSTEM = {
    "support": "You write realistic messages that customers send to Contoso PC support. Contoso PC is a laptop maker. "
               "Reply with a single JSON object and nothing else.",
    "assistant": "You write realistic requests that people type or say to Contoso Assistant, the AI assistant built "
                 "into their Contoso laptop. Reply with a single JSON object and nothing else.",
}
RULES = {
    "support": [
        "zh means Simplified Chinese as a mainland Chinese customer would type it; en means English.",
        "Channel style: app_chat = short chat lines; email = greeting, body and sign-off; phone_transcript = what the "
        "customer said on the phone, verbatim, with spoken fillers; forum_dm = informal private message.",
        "Convey every listed fact concretely, in the customer's own words, as symptoms and needs, not as categories.",
        "Never mention error codes, warranty or plan names, when or where the laptop was bought, how old it is, "
        "battery cycle counts, the country, or any Contoso team, queue or department. The support system attaches "
        "the device record separately.",
        "You may name the product as 'Contoso <product line>' when natural.",
        "Add no symptoms, safety worries, deadlines, time pressure or requests beyond the listed facts; the tone may "
        "still show impatience or politeness.",
    ],
    "assistant": [
        "zh means Simplified Chinese as a mainland Chinese user would type or say it; en means English.",
        "Write what the user says to the assistant: casual, direct, often without a greeting.",
        "Convey the request concretely. Never name internal tool ids, and never mention the network, mobile data, "
        "whether the PC is a company device, the battery level or the charger.",
        "Add no second request beyond the listed facts.",
    ],
}


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    p = Path(path)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def cmd_sample(a):
    w = WORKLOADS[a.workload]
    cases = []
    for i in range(a.n):
        c = w["sample"](rng_for(a.seed, i), shift=a.shift)
        c["id"] = f"{a.workload}-{a.tag}-{a.seed}-{i:05d}"
        cases.append(c)
    write_jsonl(a.out, cases)
    print(f"{len(cases)} cases -> {a.out}")


def case_brief(c):
    w = WORKLOADS[c["workload"]]
    brief = {"id": c["id"], "language": c["lang"], "tone": c["tone"], "length": c["length"], "facts": w["facts"](c)}
    if c["workload"] == "support":
        brief.update(channel=c["channel"], product_line=c["device"]["product_line"])
    return brief


def build_prompt(workload, batch):
    lines = ["Write one message for each case.", "Rules:", *[f"- {r}" for r in RULES[workload]],
             "- Every message must differ from the others in wording, details and structure.",
             "Cases:", json.dumps([case_brief(c) for c in batch], ensure_ascii=False),
             'Return {"messages": [{"id": "<case id>", "text": "<message>"}]} with exactly one message per case.']
    return "\n".join(lines)


TOKEN_LOCK = threading.Lock()


def refresh_token():
    """Entra token for resources with key auth disabled: GEN_TOKEN_CMD prints a fresh bearer token."""
    cmd = os.environ.get("GEN_TOKEN_CMD")
    if not cmd:
        return False
    with TOKEN_LOCK:
        token = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True).stdout.strip()
        os.environ["GEN_API_KEY"] = token
    return bool(token)


def chat(prompt, workload, model, timeout=300, retries=6, json_mode=True):
    base, auth = os.environ["GEN_BASE_URL"].rstrip("/"), os.environ.get("GEN_AUTH", "api-key")
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM[workload]},
                                         {"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if os.environ.get("GEN_REASONING_EFFORT"):  # reasoning models: writing short messages needs little thinking
        body["reasoning_effort"] = os.environ["GEN_REASONING_EFFORT"]
    data_bytes = json.dumps(body).encode()
    for attempt in range(retries):
        key = os.environ["GEN_API_KEY"]
        header = {"api-key": ("api-key", key), "bearer": ("authorization", f"Bearer {key}"),
                  "apim": ("Ocp-Apim-Subscription-Key", key)}[auth]
        req = urllib.request.Request(f"{base}/chat/completions", data=data_bytes, method="POST",
                                     headers={"content-type": "application/json", header[0]: header[1]})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, list):  # some gateways return content blocks
                    content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                return content, data.get("usage") or {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            # Some gateways reject structured output; plain-text JSON still parses.
            if e.code == 400 and json_mode and ("response_format" in detail or "structured output" in detail.lower()):
                return chat(prompt, workload, model, timeout, retries, json_mode=False)
            if e.code == 401 and attempt < retries - 1 and refresh_token():
                continue
            if e.code in (401, 403, 404) or (e.code < 500 and e.code not in (408, 409, 429)):
                raise SystemExit(f"HTTP {e.code} from the generator endpoint: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                raise SystemExit(f"generator endpoint unreachable: {e}")
        time.sleep(min(2 ** attempt * 2, 60))
    raise SystemExit("generator endpoint kept failing")


def check_text(c, text):
    if not isinstance(text, str) or not text.strip():
        return "empty"
    if len(text) > 1500:
        return "too long"
    cjk = len(CJK.findall(text))
    if c["lang"] == "zh" and cjk < 6:
        return "not Chinese"
    if c["lang"] == "en" and cjk:
        return "not English"
    low = text.lower()
    for word in WORKLOADS[c["workload"]]["forbidden"]:
        if word.lower() in low:
            return f"leaks {word}"
    return None


def cmd_render(a):
    cases = read_jsonl(a.cases)
    done = {r["id"] for r in read_jsonl(a.out)}
    todo = [c for c in cases if c["id"] not in done]
    workload = cases[0]["workload"]
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    if a.dry_run:
        print(build_prompt(workload, (batches or [cases[:a.batch]])[0]))
        return
    refresh_token()
    for var in ("GEN_BASE_URL", "GEN_API_KEY"):
        if not os.environ.get(var):
            raise SystemExit(f"set {var} (or GEN_TOKEN_CMD)")
    usage, rejected, t0 = Counter(), Counter(), time.time()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"{len(done)} done, {len(todo)} to render in {len(batches)} calls with {a.model}", flush=True)
    with out.open("a", encoding="utf-8", newline="\n") as f, ThreadPoolExecutor(a.concurrency) as pool:
        futures = {pool.submit(chat, build_prompt(workload, b), workload, a.model): b for b in batches}
        for n, fut in enumerate(as_completed(futures), 1):
            batch = {c["id"]: c for c in futures[fut]}
            content, use = fut.result()
            for k in ("prompt_tokens", "completion_tokens"):
                usage[k] += int(use.get(k) or 0)
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                msgs = json.loads(text[text.find("{"):text.rfind("}") + 1]).get("messages", [])
            except (json.JSONDecodeError, AttributeError):
                msgs, rejected["bad json"] = [], rejected["bad json"] + 1
            for m in msgs if isinstance(msgs, list) else []:
                c = batch.pop(m.get("id"), None) if isinstance(m, dict) else None
                if c is None:
                    rejected["unknown id"] += 1
                    continue
                why = check_text(c, m.get("text"))
                if why:
                    rejected[why] += 1
                    continue
                f.write(json.dumps({"id": c["id"], "text": m["text"].strip(), "generator": a.model},
                                   ensure_ascii=False) + "\n")
            rejected["missing"] += len(batch)
            f.flush()
            if n % 10 == 0 or n == len(batches):
                print(f"  {n}/{len(batches)} calls, {time.time() - t0:.0f}s, tokens {dict(usage)}", flush=True)
    usage_path = out.with_suffix(".usage.json")
    prev = json.loads(usage_path.read_text(encoding="utf-8")) if usage_path.exists() else {}
    for k, v in usage.items():
        prev[k] = prev.get(k, 0) + v
    usage_path.write_text(json.dumps({**prev, "model": a.model}, indent=1), encoding="utf-8")
    print(f"rendered {len(read_jsonl(a.out))}/{len(cases)}; rejected {dict(rejected)}; re-run to fill gaps")


def flip_pair(c, rng):
    """A copy of the case with one visible field changed so that at least one label changes (same message text)."""
    w = WORKLOADS[c["workload"]]
    base = w["labels"](c)
    if c["workload"] == "support":
        d = c["device"]
        options = [("region", "SG" if d["region"] != "SG" else "JP"),
                   ("warranty_plan", rng.choice([p for p in ("Standard 1Y", "Premium Care 3Y", "Accidental Damage 2Y")
                                                 if p != d["warranty_plan"]])),
                   ("days_since_purchase", rng.choice((200, 500, 900, 1200))),
                   ("battery_cycles", 650 if d["battery_cycles"] < 500 else 250),
                   ("product_line", "AuraBook 14" if d["product_line"] == "Titan G7" else "Titan G7")]
        key = "device"
    else:
        x = c["context"]
        options = [("network", rng.choice([n for n in ("wifi", "metered", "offline") if n != x["network"]])),
                   ("enterprise_managed", not x["enterprise_managed"]),
                   ("battery_pct", 12 if x["battery_pct"] >= 20 else 60)]
        key = "context"
    rng.shuffle(options)
    for field, value in options:
        twin = json.loads(json.dumps(c))
        twin[key][field] = value
        if field == "battery_pct":
            twin[key]["power_source"] = "battery"
        if w["labels"](twin) != base:
            twin["id"] = c["id"] + "-pair"
            twin["pair_of"], twin["pair_field"] = c["id"], field
            return twin
    return None


def split_of(group, cuts):
    h = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 100
    names, acc = ("train", "calib", "dev", "test"), 0
    for name, share in zip(names, cuts):
        acc += share
        if h < acc:
            return name
    return "test"


def cmd_build(a):
    cases = {c["id"]: c for c in read_jsonl(a.cases)}
    texts = {}
    for path in a.texts:
        for r in read_jsonl(path):
            texts.setdefault(r["id"], r)
    cuts = [int(x) for x in a.splits.split(",")]
    out = {s: [] for s in ("train", "calib", "dev", "test")}
    prompt_only = []
    report = {"labels": {}, "pairs": 0, "missing_text": 0}
    for cid, c in cases.items():
        t = texts.get(cid)
        if t is None:
            report["missing_text"] += 1
            continue
        split = split_of(cid, cuts)
        variants = [c]
        twin = flip_pair(c, rng_for(a.seed, int(hashlib.sha256(cid.encode()).hexdigest()[:6], 16)))
        if twin and int(hashlib.sha256((cid + "p").encode()).hexdigest()[:4], 16) % 100 < a.pair_share:
            variants.append(twin)
            report["pairs"] += 1
        for v in variants:
            meta = {"source": f"contoso-{c['workload']}", "group": cid, "case": v["id"], "lang": c["lang"],
                    "generator": t["generator"], "pair_field": v.get("pair_field")}
            rec = {**record_of(v, t["text"]), "_meta": meta}
            out[split].append(rec)
            if split in ("dev", "test"):
                prompt_only.append({**record_of(v, t["text"], with_policy=True), "_meta": {**meta, "split": split}})
            for qid, q in rec["questions"].items():
                report["labels"].setdefault(split, {}).setdefault(qid, Counter())[str(q["label"])] += 1
    root = Path(a.out)
    for split, rows in out.items():
        if rows:
            write_jsonl(root / f"{split}.jsonl", rows)
    if prompt_only:
        write_jsonl(root / "prompt_policy.jsonl", prompt_only)
    report["counts"] = {s: len(r) for s, r in out.items()}
    report["labels"] = {s: {q: dict(c) for q, c in d.items()} for s, d in report["labels"].items()}
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("counts", "pairs", "missing_text")}))


def cmd_assemble(a):
    """Flat files for remote_pipeline.sh from <root>/<workload>/{g1,ood}, plus a manifest with counts and hashes."""
    root, out = Path(a.root), Path(a.out)
    files = {"train.jsonl": [], "calib.jsonl": []}
    for w in ("support", "assistant"):
        g1, ood = root / w / "g1", root / w / "ood"
        files["train.jsonl"] += read_jsonl(g1 / "train.jsonl")
        files["calib.jsonl"] += read_jsonl(g1 / "calib.jsonl")
        files[f"dev_{w}.jsonl"] = read_jsonl(g1 / "dev.jsonl")
        files[f"test_{w}.jsonl"] = read_jsonl(g1 / "test.jsonl")
        files[f"policy_test_{w}.jsonl"] = [r for r in read_jsonl(g1 / "prompt_policy.jsonl") if r["_meta"]["split"] == "test"]
        if (ood / "test.jsonl").exists():  # the out-of-distribution set may arrive after training has started
            files[f"ood_{w}.jsonl"] = read_jsonl(ood / "test.jsonl")
            files[f"policy_ood_{w}.jsonl"] = read_jsonl(ood / "prompt_policy.jsonl")
    manifest = {}
    for name, rows in files.items():
        if not rows:
            raise SystemExit(f"{name} is empty; build every workload first")
        write_jsonl(out / name, rows)
        manifest[name] = {"records": len(rows), "questions": sum(len(r["questions"]) for r in rows),
                          "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({k: v["records"] for k, v in manifest.items()}))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--workload", choices=sorted(WORKLOADS), required=True)
    s.add_argument("--n", type=int, required=True)
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--tag", default="g1")
    s.add_argument("--shift", action="store_true", help="out-of-distribution field mix and two-issue messages")
    s.add_argument("--out", required=True)
    r = sub.add_parser("render")
    r.add_argument("--cases", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--model", default=os.environ.get("GEN_MODEL", ""))
    r.add_argument("--batch", type=int, default=8)
    r.add_argument("--concurrency", type=int, default=6)
    r.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--workload", choices=sorted(WORKLOADS), required=True)
    b.add_argument("--cases", required=True)
    b.add_argument("--texts", nargs="+", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--splits", default="70,10,10,10", help="train,calib,dev,test percentages by message group")
    b.add_argument("--pair-share", type=int, default=35, help="percent of messages that also get a field-flipped twin")
    b.add_argument("--seed", type=int, default=7)
    m = sub.add_parser("assemble")
    m.add_argument("--root", required=True, help="directory holding <workload>/g1 and <workload>/ood builds")
    m.add_argument("--out", required=True)
    a = ap.parse_args()
    {"sample": cmd_sample, "render": cmd_render, "build": cmd_build, "assemble": cmd_assemble}[a.cmd](a)


if __name__ == "__main__":
    main()
