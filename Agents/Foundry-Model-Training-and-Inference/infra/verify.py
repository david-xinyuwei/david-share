"""Check a deployment through its public endpoint.

  python infra/verify.py --resource-group <name>          about 1 minute: deployment states and a few short calls
  python infra/verify.py --resource-group <name> --full   about 10 minutes: adds the 50 held-out GSM8K rows through the
                                                          base model and through the adapter, and a streaming speed test

Every request carries a Microsoft Entra token for https://ai.azure.com; `model` is a deployment name.
Report: ~/.foundry-lora/<resource group>/verify-report.json   Exit code: 0 = every check passed, 1 = a check failed.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import time
import urllib.request

import foundry as f

QUESTION = [{"role": "user", "content": "Tom has 3 apples and buys 5 more. How many apples does he have? Answer with a number."}]
# The speed test uses the prompt the README's numbers were measured with (Chinese: "about 300 characters on how a company
# picks the GPU type and the number of instances when it serves an open-source model on Managed Compute").
SPEED_PROMPT = [{"role": "user", "content": "请用中文写一段约 300 字的说明：企业在 Azure 上用 Managed Compute 部署开源模型时，"
                                            "怎样根据业务量选择 GPU 型号和实例数。"}]
NUMBER = r"-?\d+(?:\.\d+)?"
ROW_MAX_TOKENS = 800


def parse_args():
    p = argparse.ArgumentParser(description="Check the target deployment and its adapters through the account endpoint.")
    p.add_argument("--resource-group", required=True)
    p.add_argument("--subscription")
    p.add_argument("--target", default=f.DEFAULT_TARGET)
    p.add_argument("--adapter", help="adapter deployment to compare with the base model in --full (default: the one trained on the sample data)")
    p.add_argument("--full", action="store_true", help="add the held-out comparison (100 calls) and the streaming speed test (6 calls)")
    return p.parse_args()


def final_number(text: str) -> tuple[float | None, bool]:
    """(the number after '####' if present, else the last number in the text; whether '####' was present).
    The sample data ends every reference answer with '#### <number>!!!'."""
    t = (text or "").replace(",", "")
    marked = re.search(r"####\s*(" + NUMBER + ")", t)
    if marked:
        return float(marked.group(1)), True
    numbers = re.findall(NUMBER, t)
    return (float(numbers[-1]) if numbers else None), False


def score_row(reference: str, output: str) -> dict:
    gold, _ = final_number(reference)
    predicted, marked = final_number(output)
    return {"gold": gold, "predicted": predicted, "marker": marked,
            "correct": gold is not None and predicted is not None and abs(predicted - gold) < 1e-6}


def ask_row(sol, model: str, index: int, row: dict) -> dict:
    """One held-out row: the row's system and user turns, temperature 0, no reasoning, the same token limit for every model."""
    code = reply = seconds = None
    for attempt in range(1, 4):
        code, reply, seconds = f.chat(sol, model, row["messages"][:-1], max_tokens=ROW_MAX_TOKENS)
        if code == 200:
            break
        time.sleep(10 * attempt)
    reference = row["messages"][-1]["content"]
    if code != 200:
        return {"row": index, "model": model, "http": code, "error": f.brief(reply)}
    output = f.answer_text(reply)
    return {"row": index, "model": model, "http": 200, "seconds": seconds, "output": output,
            "completionTokens": reply["usage"]["completion_tokens"],
            "cut": reply["choices"][0].get("finish_reason") == "length", **score_row(reference, output)}


def held_out(sol, model: str, rows: list[dict]) -> tuple[dict, list[dict]]:
    with cf.ThreadPoolExecutor(4) as pool:
        records = list(pool.map(lambda item: ask_row(sol, model, *item), enumerate(rows)))
    ok = [r for r in records if r["http"] == 200]
    summary = {"rows": len(rows), "answered": len(ok),
               "correctByLastNumber": sum(r["correct"] for r in ok),
               "meanCompletionTokens": round(sum(r["completionTokens"] for r in ok) / max(1, len(ok)), 1),
               "cutAtTokenLimit": sum(r["cut"] for r in ok), "withMarker": sum(r["marker"] for r in ok)}
    return summary, records


def stream_once(sol, model: str) -> dict:
    """One streamed completion of up to 600 tokens (reasoning left on): time to first token and tokens per second."""
    body = {"model": model, "messages": SPEED_PROMPT, "temperature": 0, "max_tokens": 600, "stream": True,
            "stream_options": {"include_usage": True}}
    req = urllib.request.Request(sol.chat_url, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": "Bearer " + f.token(f.AI_AUDIENCE), "Content-Type": "application/json"})
    started, first, usage = time.time(), None, None
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            event = json.loads(line[5:])
            for choice in event.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content"):
                    first = first or time.time()
            usage = event.get("usage") or usage
    ended = time.time()
    tokens = (usage or {}).get("completion_tokens")
    return {"firstTokenSeconds": round(first - started, 2) if first else None, "totalSeconds": round(ended - started, 2),
            "completionTokens": tokens,
            "tokensPerSecond": round((tokens - 1) / (ended - first), 1) if tokens and first and ended > first else None}


def main() -> int:
    args = parse_args()
    sub = f.use_subscription(args.subscription)["id"]
    folder = f.state_dir(args.resource_group)
    sol = f.require_solution(sub, args.resource_group, args.target)
    report = f.Receipt(folder / "verify-report.json", kind="checks", resourceGroup=args.resource_group,
                       endpoint=sol.chat_url, full=args.full)
    metrics: dict = {}

    code, _, target = f.http("GET", sol.target_url())
    props = (target or {}).get("properties", {}) if isinstance(target, dict) else {}
    target_ok = report.add("Target deployment is Succeeded", "PASS" if f.state_of(target) == "Succeeded" else "FAIL",
                           f"{sol.target}: {f.state_of(target) or f'HTTP {code}'}, model {str(props.get('model')).split('/models/')[-1]}, "
                           f"{props.get('totalAccelerators')} x {props.get('acceleratorType')}")

    code, _, listing = f.http("GET", sol.adapter_url())
    attached = [a for a in (listing.get("value", []) if isinstance(listing, dict) else [])
                if a["properties"].get("targetDeploymentName") == sol.target]
    names = [a["name"] for a in attached if f.state_of(a) == "Succeeded"]
    report.add("Adapter deployments are Succeeded", "PASS" if attached and len(names) == len(attached) else "FAIL",
               ", ".join(f"{a['name']}: {f.state_of(a)}" for a in attached) or "no adapter deployment on this target")
    if not target_ok:
        print(f"\nRESULT: {report.close()}   report: {report.path}")
        return 1

    code, reply, seconds = f.chat(sol, sol.target, QUESTION)
    base_served = reply.get("model") if code == 200 else None
    report.add("The base model answers under the target's name", "PASS" if code == 200 and "8" in f.answer_text(reply) else "FAIL",
               f"HTTP {code}, {seconds} s, answer {f.answer_text(reply).strip()[:40]!r}, served model {base_served}"
               if code == 200 else f"HTTP {code} {f.brief(reply)}")

    for name in names:
        code, reply, seconds = f.chat(sol, name, QUESTION, max_tokens=200)
        served = reply.get("model") if code == 200 else None
        ok = code == 200 and "8" in f.answer_text(reply) and served != base_served
        report.add(f"Adapter {name} answers under its own name", "PASS" if ok else "FAIL",
                   f"HTTP {code}, {seconds} s, served model {served} (base: {base_served})" if code == 200 else f"HTTP {code} {f.brief(reply)}")

    code, reply, _ = f.chat(sol, f"no-such-deployment-{int(time.time())}", QUESTION)
    report.add("An unknown deployment name is rejected", "PASS" if code == 404 else "FAIL", f"HTTP {code} {f.brief(reply, 120)}")

    if args.full and names:
        rows = [json.loads(line) for line in f.dataset_bytes("validation", _cache(folder)).decode("utf-8").splitlines() if line.strip()]
        adapter = args.adapter or _sample_adapter(sol, names)
        rows_file = folder / f"verify-rows-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        outputs = {}
        for label, model in (("base", sol.target), ("adapter", adapter)):
            t0 = time.time()
            summary, records = held_out(sol, model, rows)
            metrics[label] = {"deployment": model, **summary}
            outputs[label] = {r["row"]: r.get("output") for r in records}
            with rows_file.open("a", encoding="utf-8") as out:
                out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
            report.add(f"Held-out rows through {model}", "PASS" if summary["answered"] == len(rows) else "FAIL",
                       f"{summary['answered']}/{len(rows)} answered; correct by last number {summary['correctByLastNumber']}; "
                       f"mean {summary['meanCompletionTokens']} completion tokens; {summary['cutAtTokenLimit']} cut at "
                       f"{ROW_MAX_TOKENS} tokens; {summary['withMarker']} with '####'", time.time() - t0)
        same = sum(1 for i in outputs["base"] if outputs["base"][i] is not None and outputs["base"][i] == outputs["adapter"].get(i))
        metrics["identicalOutputs"] = same
        report.add("The adapter changes the answers", "PASS" if same < len(rows) else "FAIL",
                   f"{same} of {len(rows)} outputs identical to the base model's; rows saved to {rows_file.name}")
        for label, model in (("base", sol.target), ("adapter", adapter)):
            try:
                runs = [stream_once(sol, model) for _ in range(3)]
            except (OSError, ValueError) as e:
                report.add(f"Streaming speed of {model}", "FAIL", f"{type(e).__name__}: {e}")
                continue
            metrics[label]["streaming"] = runs
            report.add(f"Streaming speed of {model}", "PASS" if all(r["tokensPerSecond"] for r in runs) else "FAIL",
                       "tokens per second " + " / ".join(str(r["tokensPerSecond"]) for r in runs)
                       + "; first token after " + " / ".join(str(r["firstTokenSeconds"]) for r in runs) + " s")
    status = report.close(metrics=metrics)
    print(f"\nRESULT: {status}   report: {report.path}")
    return 0 if status == "PASS" else 1


def _cache(folder):
    cache = folder / "data"
    cache.mkdir(exist_ok=True)
    return cache


def _sample_adapter(sol, names: list[str]) -> str:
    """The adapter deployment whose training job used the uploaded sample file; the first adapter when none matches."""
    try:
        code, _, listing = f.http("GET", sol.openai + "/files?purpose=fine-tune&limit=1000", audience=f.AI_AUDIENCE)
        sample = {x["id"] for x in listing.get("data", []) if x.get("filename") == f.DATASET["files"]["train"]["upload_as"]}
        for a in f.deployable_adapters(f.list_jobs(sol), f.project_models(sol), sol.target):
            if a["name"] in names and a["trainingFile"] in sample:
                return a["name"]
    except (f.Stop, AttributeError, KeyError, TypeError):
        pass
    return names[0]


if __name__ == "__main__":
    f.main_guard(main)
