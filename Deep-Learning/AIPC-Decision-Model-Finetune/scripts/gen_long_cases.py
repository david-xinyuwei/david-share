#!/usr/bin/env python3
"""Real long-input test set: support tickets whose *history* decides the answer.

Why this exists: the padded-log run in 验证结果/端侧引擎_x64长输入_* measured cost only; the padding carried no
information, so it could not say whether the model is accurate at long inputs. Here the length carries the label.

Each record = the short ticket (message + device record, same fields as the training data) plus a long
`case_history` field (prior tickets, chat transcripts, a diagnostic report, 2k-7k tokens) written by an LLM from a
fact list. Three policy clauses depend on facts that appear ONLY in the history; `scripts/vendor_policy.py` labels the
short part, and `long_labels()` below applies the history clauses on top. The LLM never decides a label.

History clauses (extensions of the written Contoso policy, stated to the model in every question's instructions):
  H1  A battery that was already replaced under the battery program is not replaced again: battery_program -> sales_ops.
  H2  A remote fan-profile reset that was already tried (and failed) in a prior ticket makes overheating a hardware fault
      on any model: remote_l1 -> onsite_repair / depot_repair / sales_ops by the usual warranty + region rule.
  H3  A diagnostic report that says "no backup" for a failing disk: urgency 3 (the short message may be silent about it);
      a report that confirms a backup: urgency falls back to 2 / 1.
Controls (no clause fires):
  N1  Same long history, but the decisive fact is absent or the opposite (battery not yet replaced; reset not tried; backup
      present) -> the short-record label stands. These stop the model from learning "long history => change the answer".

Commands (run on a machine that can reach the generator endpoint; GEN_BASE_URL / GEN_TOKEN_CMD as in gen_vendor_data.py):
  python scripts/gen_long_cases.py sample --n 160 --seed 23 --out data/contoso/long/long.cases.jsonl
  python scripts/gen_long_cases.py render-messages --cases data/contoso/long/long.cases.jsonl --out data/contoso/long/long.messages.jsonl --model gpt-5.4
  python scripts/gen_long_cases.py render --cases data/contoso/long/long.cases.jsonl --out data/contoso/long/long.texts.jsonl --model gpt-5.4
  python scripts/gen_long_cases.py build  --cases data/contoso/long/long.cases.jsonl --texts data/contoso/long/long.texts.jsonl --messages data/contoso/long/long.messages.jsonl --out data/contoso/final/long_test_support.jsonl
Then: scripts/run_engine_eval.ps1 ... -DataPrefix long_test_ -Workloads support (laptop or x86-64), compared with the labels.
Standard library only; the labels are computed, never generated.
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_vendor_data as gvd  # noqa: E402  (chat(), write_jsonl, read_jsonl, refresh_token)
import vendor_policy as vp  # noqa: E402

HISTORY_POLICY = (
    " Case history rules: a battery already replaced under the battery program is not replaced again (paid quote, "
    "sales_ops). Overheating after a remote fan-profile reset that was already tried in an earlier ticket is a hardware "
    "fault (onsite_repair / depot_repair / sales_ops by warranty and region). A failing disk is urgency 3 when the "
    "diagnostic report shows no backup, otherwise 2 if the customer must work today, else 1."
)

# scenario -> (clause, decisive fact present?) sampled per case
LONG_KINDS = {
    "battery_replaced": ("battery_drain", "H1", True),
    "battery_not_replaced": ("battery_drain", "H1", False),
    "reset_tried": ("thermal_shutdown", "H2", True),
    "reset_not_tried": ("thermal_shutdown", "H2", False),
    "no_backup_in_report": ("ssd_warning", "H3", True),
    "backup_in_report": ("ssd_warning", "H3", False),
}
LENGTH_TOKENS = (2000, 3500, 5000, 7000)


def long_labels(case):
    """Short-record policy, then the history clause that the case carries."""
    labels = vp.support_labels(case)
    dev, kind, decisive = case["device"], case["long_kind"], case["decisive"]
    if kind.startswith("battery") and decisive:              # H1: replaced before -> paid quote
        labels["queue"] = "sales_ops"
    elif kind.startswith("reset") and decisive:              # H2: hardware fault by warranty + region
        if not vp.in_warranty(dev):
            labels["queue"] = "sales_ops"
        elif dev["warranty_plan"] == "Premium Care 3Y" and dev["region"] in vp.ONSITE_REGIONS:
            labels["queue"], labels["onsite_eligible"] = "onsite_repair", True
        else:
            labels["queue"] = "depot_repair"
        labels["urgency"] = 2 if case["modifiers"]["deadline_today"] else 1
    elif kind.startswith("no_backup") or kind.startswith("backup"):  # H3: the report, not the message, decides
        labels["urgency"] = 3 if decisive else (2 if case["modifiers"]["deadline_today"] else 1)
    return labels


def sample_case(rng, i, seed):
    kind = list(LONG_KINDS)[i % len(LONG_KINDS)]
    scenario, clause, decisive = LONG_KINDS[kind]
    c = vp.sample_support(rng)
    c["scenario"] = scenario
    c["device"]["last_error_code"] = rng.choice(vp.SUPPORT_SCENARIOS[scenario][1])
    if scenario == "battery_drain":  # make the short-record rule say battery_program, so H1 is the only thing that flips it
        c["device"]["battery_cycles"] = rng.randint(120, 460)
        c["device"]["days_since_purchase"] = rng.randint(60, 700)
    if scenario == "thermal_shutdown":  # non-Titan so the short rule says remote_l1; vary warranty/region for H2 branches
        c["device"]["product_line"] = rng.choice([p for p in vp.PRODUCT_LINES if p != "Titan G7"])
    if scenario == "ssd_warning":  # the short message must NOT say whether there is a backup; the report does
        c["modifiers"]["has_backup"] = not decisive  # drives vendor_policy's own urgency; H3 overrides from the report anyway
    c.update(id=f"support-long-{seed}-{i:05d}", long_kind=kind, clause=clause, decisive=decisive,
             target_tokens=rng.choice(LENGTH_TOKENS))
    c["labels"] = long_labels(c)
    return c


def cmd_sample(a):
    cases = [sample_case(vp.rng_for(a.seed, i), i, a.seed) for i in range(a.n)]
    gvd.write_jsonl(a.out, cases)
    print(f"{len(cases)} cases -> {a.out}; kinds {dict(Counter(c['long_kind'] for c in cases))}; "
          f"label flips vs short policy: {sum(1 for c in cases if c['labels'] != vp.support_labels(c))}")


HISTORY_SYSTEM = ("You write realistic internal case-history documents for Contoso PC, a laptop maker: prior support "
                  "tickets, chat transcripts between the customer and support agents, and device diagnostic reports. "
                  "Reply with a single JSON object and nothing else.")


def history_facts(c):
    kind, dec, dev = c["long_kind"], c["decisive"], c["device"]
    f = [f"The customer owns a Contoso {dev['product_line']}; write the history as a mix of 3 to 6 prior tickets or chats "
         f"over the past year plus one device diagnostic report, each with a date, a ticket id and an agent name.",
         "Most of the history is about ordinary unrelated issues (Wi-Fi drops, a sticky key, a Windows update, an app "
         "sign-in problem, a question about an accessory). Resolve them in the history.",
         f"Write about {c['target_tokens']} tokens in total ({'Simplified Chinese' if c['lang'] == 'zh' else 'English'}); "
         "long, concrete, with timestamps and agent notes; realistic names and ticket ids; no markdown headings."]
    if kind.startswith("battery"):
        f.append("One earlier ticket, about 8 months ago, concerns battery runtime; include the device-agent error code BAT-047 in it."
                 + (" That ticket ENDED with the battery being REPLACED under the Contoso battery health program: state the replacement date, the new battery serial and that the program replacement was completed."
                    if dec else " That ticket ended with the agent only recalibrating the battery gauge remotely; make it clear that NO battery was replaced and NO program case was opened."))
    elif kind.startswith("reset"):
        f.append("One earlier ticket, about 3 months ago, concerns the laptop getting hot and shutting down."
                 + (" In that ticket the agent walked the customer through the REMOTE FAN-PROFILE RESET step by step and it was COMPLETED, and the ticket notes record that the overheating CONTINUED afterwards (the fix failed)."
                    if dec else " In that ticket the agent only sent a knowledge-base article; the remote fan-profile reset was NOT performed (the customer never got to it, the ticket was closed as 'customer did not respond')."))
    elif kind.startswith("no_backup") or kind.startswith("backup"):
        f.append("The diagnostic report (from the Contoso device agent, run this week) lists disk health with SMART attributes, "
                 "reallocated sectors and the SSD-501 warning, plus a 'Backup status' line."
                 + (" The Backup status line must say that NO backup exists: Contoso Cloud Backup is OFF and the last successful backup is 'never'."
                    if dec else " The Backup status line must say a backup EXISTS and completed successfully within the last 24 hours, with the backup size."))
    f.append("Do not mention the current ticket's resolution, any queue or department name, warranty plan, region or purchase date.")
    return f


def build_history_prompt(batch):
    briefs = [{"id": c["id"], "facts": history_facts(c)} for c in batch]
    return ("Write one case-history document for each case. Return "
            '{"documents": [{"id": "<case id>", "text": "<document>"}]} with exactly one document per case.\n'
            + json.dumps(briefs, ensure_ascii=False))


def cmd_render(a):
    cases = gvd.read_jsonl(a.cases)
    done = {r["id"]: r for r in gvd.read_jsonl(a.out)}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} cases, {len(done)} already rendered, {len(todo)} to do")
    if a.dry_run:
        print(build_history_prompt(todo[:1])[:1500])
        return
    if not os.environ.get("GEN_API_KEY"):
        gvd.refresh_token()
    gvd.SYSTEM["long"] = HISTORY_SYSTEM
    out_rows = list(done.values())
    usage = Counter()
    lock = threading.Lock()

    def one(c):  # one document per call: documents are long, batching them would cut the per-document length
        text, u = gvd.chat(build_history_prompt([c]), "long", a.model, timeout=600, json_mode=True)
        docs = json.loads(text)["documents"] if isinstance(text, str) else text["documents"]
        doc = next(d for d in docs if d["id"] == c["id"])["text"]
        return c["id"], doc, u

    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        futures = [pool.submit(one, c) for c in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            cid, doc, u = fut.result()
            with lock:
                out_rows.append({"id": cid, "text": doc, "model": a.model, "chars": len(doc)})
                usage.update({k: v for k, v in (u or {}).items() if isinstance(v, int)})
                gvd.write_jsonl(a.out, out_rows)  # checkpoint after every document
            if i % 10 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} rendered; chars so far {sum(r['chars'] for r in out_rows)}", flush=True)
    Path(a.out).with_suffix(".usage.json").write_text(json.dumps({**usage, "model": a.model}, indent=1), encoding="utf-8")
    print("usage:", dict(usage))


def message_brief(c):
    """Like gen_vendor_data.case_brief, but the decisive fact never enters the current message: the SSD cases get no
    backup sentence (the diagnostic report carries it), battery/thermal cases get only the symptom (+ deadline)."""
    facts = [vp.SUPPORT_SCENARIOS[c["scenario"]][0]]
    if c["modifiers"]["deadline_today"]:
        facts.append("they need the laptop working today for something specific and important (invent a concrete reason)")
    return {"id": c["id"], "language": c["lang"], "tone": c["tone"], "length": c["length"], "facts": facts,
            "channel": c["channel"], "product_line": c["device"]["product_line"]}


def cmd_render_messages(a):
    """Current-ticket messages in the training-data style (same system prompt and rules as gen_vendor_data), 8 per call."""
    cases = gvd.read_jsonl(a.cases)
    done = {r["id"]: r for r in gvd.read_jsonl(a.out)}
    todo = [c for c in cases if c["id"] not in done]
    print(f"{len(cases)} cases, {len(done)} already rendered, {len(todo)} to do")
    if a.dry_run:
        print(build_message_prompt(todo[:2])[:1200])
        return
    if not os.environ.get("GEN_API_KEY"):
        gvd.refresh_token()
    out_rows = list(done.values())
    usage = Counter()
    for i in range(0, len(todo), a.batch):
        batch = todo[i:i + a.batch]
        text, u = gvd.chat(build_message_prompt(batch), "support", a.model, timeout=300, json_mode=True)
        msgs = {m["id"]: m["text"] for m in json.loads(text)["messages"]}
        for c in batch:
            if c["id"] in msgs and msgs[c["id"]].strip():
                out_rows.append({"id": c["id"], "text": msgs[c["id"]], "model": a.model})
        usage.update({k: v for k, v in (u or {}).items() if isinstance(v, int)})
        gvd.write_jsonl(a.out, out_rows)
        print(f"  {min(i + a.batch, len(todo))}/{len(todo)} messages")
    Path(a.out).with_suffix(".usage.json").write_text(json.dumps({**usage, "model": a.model}, indent=1), encoding="utf-8")
    print("usage:", dict(usage))


def build_message_prompt(batch):
    lines = ["Write one message for each case.", "Rules:", *[f"- {r}" for r in gvd.RULES["support"]],
             "- Every message must differ from the others in wording, details and structure.",
             "- Do not mention backups, earlier tickets, earlier repairs or anything the customer did before; only the current symptom.",
             "Cases:", json.dumps([message_brief(c) for c in batch], ensure_ascii=False),
             'Return {"messages": [{"id": "<case id>", "text": "<message>"}]} with exactly one message per case.']
    return "\n".join(lines)


def cmd_build(a):
    cases = {c["id"]: c for c in gvd.read_jsonl(a.cases)}
    texts = {t["id"]: t["text"] for t in gvd.read_jsonl(a.texts)}
    rows = []
    msgs = {m["id"]: m["text"] for m in gvd.read_jsonl(a.messages)} if a.messages else {}
    missing_msgs = [cid for cid in cases if cid in texts and cid not in msgs]
    if a.messages and missing_msgs:
        raise SystemExit(f"{len(missing_msgs)} cases have a history but no rendered message (run render-messages first)")
    for cid, c in cases.items():
        if cid not in texts:
            continue
        message = msgs.get(cid) or (f"我的 Contoso {c['device']['product_line']} 又出问题了，详情见历史记录，请帮忙处理。" if c["lang"] == "zh"
                                     else f"My Contoso {c['device']['product_line']} is acting up again, see my case history, please help.")
        rec = vp.record_of(c, message)
        rec["state"]["case_history"] = texts[cid]
        for q in rec["questions"].values():
            q["instructions"] = f"{q['instructions']}{HISTORY_POLICY}"
        labels = c["labels"]
        for qid in rec["questions"]:
            rec["questions"][qid]["label"] = labels[qid]
        rec["_meta"] = {"source": "contoso-support-long", "group": cid, "case": cid, "lang": c["lang"], "generator": a.generator_tag,
                        "long_kind": c["long_kind"], "clause": c["clause"], "decisive": c["decisive"],
                        "short_policy_labels": vp.support_labels(c), "target_tokens": c["target_tokens"],
                        "history_chars": len(texts[cid])}
        rows.append(rec)
    gvd.write_jsonl(a.out, rows)
    flips = sum(1 for r in rows if r["_meta"]["short_policy_labels"] != {q: r["questions"][q]["label"] for q in r["questions"]})
    print(f"{len(rows)} records -> {a.out}; label differs from short policy in {flips}; "
          f"history chars median {sorted(r['_meta']['history_chars'] for r in rows)[len(rows)//2] if rows else 0}; "
          f"sha256 {hashlib.sha256(Path(a.out).read_bytes()).hexdigest()[:16]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample"); s.add_argument("--n", type=int, default=160); s.add_argument("--seed", type=int, default=23); s.add_argument("--out", required=True)
    r = sub.add_parser("render"); r.add_argument("--cases", required=True); r.add_argument("--out", required=True)
    r.add_argument("--model", default=os.environ.get("GEN_MODEL", "")); r.add_argument("--dry-run", action="store_true")
    r.add_argument("--concurrency", type=int, default=4, help="parallel documents in flight (each ~5k output tokens)")
    rm = sub.add_parser("render-messages"); rm.add_argument("--cases", required=True); rm.add_argument("--out", required=True)
    rm.add_argument("--model", default=os.environ.get("GEN_MODEL", "")); rm.add_argument("--batch", type=int, default=8); rm.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("build"); b.add_argument("--cases", required=True); b.add_argument("--texts", required=True); b.add_argument("--out", required=True)
    b.add_argument("--messages", default="", help="optional rendered short messages (gen_vendor_data render output); else a one-line pointer message")
    b.add_argument("--generator-tag", default="llm-C")
    a = ap.parse_args()
    {"sample": cmd_sample, "render": cmd_render, "render-messages": cmd_render_messages, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    main()
