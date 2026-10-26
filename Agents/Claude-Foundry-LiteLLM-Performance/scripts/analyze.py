import argparse
import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MODEL_NAMES = {
    "opus55-standard": "claude-opus-5-5",
    "sonnet55-standard": "claude-sonnet-5-5",
    "haiku55-standard": "claude-haiku-5-5",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def quantile(values, probability):
    values = sorted(values)
    return values[math.ceil(probability * len(values)) - 1] if values else None


def validate_records(records, matrix, selected_cases=None):
    all_cases = {case["id"]: case for case in matrix["cases"]}
    require(len(all_cases) == len(matrix["cases"]) == 10 and len(matrix["questions"]) == 5, "Unexpected matrix dimensions")
    require(matrix["attemptLimit"] == 50, "Unexpected attempt limit")
    selected_cases = list(all_cases) if selected_cases is None else selected_cases
    require(selected_cases and len(set(selected_cases)) == len(selected_cases) and set(selected_cases) <= set(all_cases), "Invalid selected cases")
    cases = {case_id: all_cases[case_id] for case_id in selected_cases}
    expected_count = len(cases) * len(matrix["questions"])
    require(len(records) == expected_count, "Expected fifty records" if expected_count == 50 else "Incomplete selected cases")
    seen = set()
    groups = {}
    for case_id, case in cases.items():
        selected = sorted([record for record in records if record["measurement"]["caseId"] == case_id], key=lambda record: record["measurement"]["turn"])
        require([record["measurement"]["turn"] for record in selected] == [1, 2, 3, 4, 5], "Missing or duplicate turn")
        previous = None
        for record in selected:
            row = record["measurement"]
            request = record["request"]
            response = record["response"]
            usage = response["usage"]
            trace = record["providerRequest"]
            require(row["callId"] not in seen and trace["call_id"] == row["callId"], "Duplicate or mismatched call")
            seen.add(row["callId"])
            require(record["httpStatus"] == 200 and record["messageStopReceived"] and response["stop_reason"] == "end_turn", "Incomplete response")
            require(request["model"] == response["model"] == case["model"], "Wrong model")
            require(trace["model"] == MODEL_NAMES[case["model"]], "Provider model changed")
            require(not response.get("error") and any(block["type"] == "text" and block.get("text", "").strip() for block in response["content"]), "Empty or failed answer")
            require(request["system"] == matrix["baseRequest"]["system"], "Changed source material")
            require(request["thinking"] == trace["thinking"] == {"type": case["thinking"]}, "Thinking mode changed")
            require(request["output_config"] == trace["output_config"] == {"effort": "medium"}, "Effort changed")
            require(request["stream"] is True and trace["stream"] is True and request["max_tokens"] == trace["max_tokens"] == 4096, "Generation settings changed")
            markers = {item["path"]: item["value"] for item in trace["cache_markers"]}
            expected_markers = {"system[0].cache_control": {"type": "ephemeral"}}
            if case["cache"] == "conversation":
                expected_markers["cache_control"] = {"type": "ephemeral"}
                require(request.get("cache_control") == {"type": "ephemeral"}, "Missing conversation cache")
            else:
                require("cache_control" not in request, "Unexpected conversation cache")
            require(markers == expected_markers, "Cache markers changed")
            expected_history = [] if previous is None else previous["request"]["messages"] + [{"role": "assistant", "content": previous["response"]["content"]}]
            expected_history += [{"role": "user", "content": matrix["questions"][row["turn"] - 1]}]
            require(request["messages"] == expected_history, "History or questions changed")
            previous = record
            total_input = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
            require(total_input == row["totalInputTokens"], "Input denominator changed")
            for source, target in (("input_tokens", "uncachedInputTokens"), ("cache_creation_input_tokens", "cacheWriteTokens"), ("cache_read_input_tokens", "cacheReadTokens"), ("output_tokens", "outputTokens")):
                require(usage[source] == row[target], "Token field changed")
            thinking = usage["output_tokens_details"]["thinking_tokens"]
            require(thinking == row["thinkingTokens"] and usage["output_tokens"] - thinking == row["visibleOutputTokens"], "Thinking accounting changed")
            if case["thinking"] != "adaptive":
                require(thinking == 0 and all(block["type"] == "text" for block in response["content"]), "Thinking-off ineffective")
            require(0 <= row["headersSeconds"] <= row["firstBodyByteSeconds"] <= row["firstSseSeconds"] <= row["ttftSeconds"] <= record["messageStopSeconds"] <= row["e2eSeconds"], "Timing order changed")
            require(math.isclose(row["postFirstSseWaitSeconds"], row["ttftSeconds"] - row["firstSseSeconds"], abs_tol=1e-10), "Timing interval changed")
            for field, count in (("outputTokensPerSecond", row["outputTokens"]), ("visibleTokensPerSecond", row["visibleOutputTokens"])):
                require(math.isclose(row[field], count / row["e2eSeconds"], abs_tol=1e-10), "Throughput changed")
            rates = record["prices"]
            cost = (usage["input_tokens"] * rates["input"] + usage["cache_creation_input_tokens"] * rates["write"] + usage["cache_read_input_tokens"] * rates["read"] + usage["output_tokens"] * rates["output"]) / 1000000
            require(math.isclose(cost, row["estimatedCostUsd"], abs_tol=1e-12), "Cost changed")
            require(row["sha256"] == record["rawSha256"], "Raw provenance mismatch")
            timings = record["eventTimings"]
            require(all(left["elapsedSeconds"] <= right["elapsedSeconds"] for left, right in zip(timings, timings[1:])), "Nonmonotonic event timing")
        rows = [record["measurement"] for record in selected]
        total_input = sum(row["totalInputTokens"] for row in rows)
        group = {"config": case, "samples": len(rows), "cacheReadSharePercent": 100 * sum(row["cacheReadTokens"] for row in rows) / total_input,
                 "costUsd": sum(row["estimatedCostUsd"] for row in rows), "thinkingRequests": sum(row["thinkingTokens"] > 0 for row in rows),
                 "thinkingTokens": sum(row["thinkingTokens"] for row in rows), "outputTokens": sum(row["outputTokens"] for row in rows),
                 "rows": rows}
        for field in ("ttftSeconds", "e2eSeconds", "headersSeconds", "firstBodyByteSeconds", "firstSseSeconds", "firstThinkingSeconds", "firstSignatureSeconds", "postFirstSseWaitSeconds", "outputTokensPerSecond", "visibleTokensPerSecond"):
            values = [row[field] for row in rows if row[field] is not None]
            group[field] = {"p50": quantile(values, 0.50), "p95": quantile(values, 0.95), "samples": len(values)}
        groups[case_id] = group
    require(len(seen) == expected_count, "Unknown records outside matrix")
    return groups


def validate(root=ROOT):
    provenance = read_json(root / "evidence/provenance.json")
    for name, expected in provenance["files"].items():
        require(hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, "Hash mismatch: " + name)
    records = read_json(root / "evidence/requests.json")
    matrix = read_json(root / "data/matrix.json")
    groups = validate_records(records, matrix)
    saved = read_json(root / "evidence/summary.json")
    for case_id, group in groups.items():
        expected = saved["groups"][case_id]["allTurns"]
        require(math.isclose(group["cacheReadSharePercent"], expected["cacheReadSharePercent"], abs_tol=1e-10), "Saved cache summary changed")
        require(math.isclose(group["ttftSeconds"]["p50"], expected["ttftSeconds"]["p50"], abs_tol=1e-10), "Saved TTFT changed")
        require(math.isclose(group["costUsd"], expected["estimatedCostUsd"], abs_tol=1e-12), "Saved cost summary changed")
    total = sum(group["costUsd"] for group in groups.values())
    require(math.isclose(total, saved["costUsd"], abs_tol=1e-12), "Total cost changed")
    return {"status": "PASS", "requests": 50, "configurations": 10, "costUsd": total, "groups": groups}


def load_provider_traces(paths):
    traces = {}
    for path in paths:
        text = Path(path).read_text(encoding="utf-8-sig")
        try:
            decoded = json.loads(text)
            entries = decoded if isinstance(decoded, list) else [decoded]
        except json.JSONDecodeError:
            entries = text.splitlines()
        for entry in entries:
            if isinstance(entry, str):
                try:
                    entry = json.loads(entry)
                except json.JSONDecodeError:
                    if "CLAUDE_PROVIDER_TRACE " not in entry:
                        continue
                    entry = json.loads(entry.split("CLAUDE_PROVIDER_TRACE ", 1)[1])
            if isinstance(entry, dict) and "Log" in entry:
                message = entry["Log"]
                if "CLAUDE_PROVIDER_TRACE " not in message:
                    continue
                entry = json.loads(message.split("CLAUDE_PROVIDER_TRACE ", 1)[1])
            if not isinstance(entry, dict) or entry.get("stage") != "pre_api_call":
                continue
            require(entry.get("capture") == "PROVIDER_REQUEST_FIELDS", "Provider request unavailable")
            call_id = entry.get("call_id")
            require(isinstance(call_id, str) and bool(call_id), "Provider call ID missing")
            require(call_id not in traces or traces[call_id] == entry, "Conflicting provider traces")
            traces[call_id] = entry
    require(traces, "No provider traces found")
    return traces


def validate_stream(record):
    events = [json.loads(line[5:].strip()) for line in record["sseWireLines"]
              if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]")]
    require(events == record["sseEvents"], "SSE events differ from wire capture")
    timings = record["eventTimings"]
    require(len(events) == len(timings), "Missing event timestamps")
    require(all(timing["event"] == index and timing["type"] == event["type"]
                for index, (timing, event) in enumerate(zip(timings, events))), "Event timestamp mismatch")
    elapsed = [timing["elapsedSeconds"] for timing in timings]
    require(elapsed and all(isinstance(value, (int, float)) and math.isfinite(value) for value in elapsed), "Invalid event timing")
    require(record["firstBodyByteSeconds"] <= elapsed[0] and elapsed[-1] <= record["elapsedSeconds"]
            and all(left <= right for left, right in zip(elapsed, elapsed[1:])), "Event timing outside response")
    require(record["firstBodyByteSeconds"] <= record["firstSseEventSeconds"] <= elapsed[0], "First SSE timing mismatch")
    blocks = {}
    open_blocks = set()
    parsed = {}
    first_events = {}
    starts = stops = 0
    for index, event in enumerate(events):
        kind = event["type"]
        require(kind != "error", "Stream error event")
        if kind == "ping":
            continue
        require(stops == 0 and (kind == "message_start" or starts == 1), "Event outside message")
        if kind == "message_start":
            starts += 1
            require(starts == 1 and event["message"]["content"] == [], "Mutated or duplicate message start")
            parsed = copy.deepcopy(event["message"])
        elif kind == "content_block_start":
            require(event["index"] not in blocks, "Duplicate content block")
            blocks[event["index"]] = copy.deepcopy(event["content_block"])
            require(event["content_block"]["type"] in ("text", "thinking", "redacted_thinking"), "Unsupported content block")
            open_blocks.add(event["index"])
            if event["content_block"]["type"] == "thinking":
                first_events.setdefault("firstThinkingEventSeconds", index)
        elif kind == "content_block_delta":
            field = {"text_delta": "text", "thinking_delta": "thinking", "signature_delta": "signature"}.get(event["delta"]["type"])
            require(field is not None and event["index"] in open_blocks and field in blocks[event["index"]], "Unsupported or orphan content delta")
            blocks[event["index"]][field] += event["delta"][field]
            if field == "text" and event["delta"][field]:
                first_events.setdefault("firstVisibleTextSeconds", index)
            elif field == "signature":
                first_events.setdefault("firstSignatureSeconds", index)
        elif kind == "content_block_stop":
            require(event["index"] in open_blocks, "Orphan content stop")
            open_blocks.remove(event["index"])
        elif kind == "message_delta":
            require(not open_blocks, "Message delta before content stop")
            parsed.update(event.get("delta", {}))
            parsed["usage"].update(event.get("usage", {}))
        elif kind == "message_stop":
            require(not open_blocks, "Unclosed content block")
            stops += 1
            first_events["messageStopSeconds"] = index
        else:
            raise ValueError("Unsupported stream event: " + kind)
    require(starts == stops == 1, "Incomplete stream")
    require("firstVisibleTextSeconds" in first_events, "No visible text event")
    for field in ("firstVisibleTextSeconds", "firstThinkingEventSeconds", "firstSignatureSeconds", "messageStopSeconds"):
        if field not in first_events:
            require(record.get(field) is None, "Timing without matching event: " + field)
            continue
        index = first_events[field]
        upper = elapsed[index + 1] if index + 1 < len(elapsed) else record["elapsedSeconds"]
        require(record.get(field) is not None and elapsed[index] <= record[field] <= upper, "Event timing mismatch: " + field)
    require(parsed["usage"] == record["response"]["usage"], "Cumulative usage mismatch")
    require(sorted(blocks) == list(range(len(blocks))), "Content block index gap")
    parsed["content"] = [blocks[index] for index in sorted(blocks)]
    require(parsed == record["response"], "Accumulated response mismatch")


def project_raw_record(path, trace):
    record = read_json(path)
    require(record["status"] == "CAPTURED" and record["httpStatus"] == 200, "Request failed")
    validate_stream(record)
    usage = record["response"]["usage"]
    total_input = sum(usage[field] for field in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    thinking = usage["output_tokens_details"]["thinking_tokens"]
    output = usage["output_tokens"]
    elapsed = record["elapsedSeconds"]
    require(elapsed > 0 and 0 <= thinking <= output and total_input > 0, "Invalid token or timing values")
    require(total_input < 100000 and usage["cache_creation"]["ephemeral_1h_input_tokens"] == 0, "Unverified pricing tier")
    require(usage["speed"] == "standard", "Unexpected serving speed")
    prices = record["pricingUsdPerMillionTokens"]
    require(all(isinstance(prices[field], (int, float)) and math.isfinite(prices[field]) and prices[field] >= 0
                for field in ("input", "write", "read", "output")), "Invalid recorded prices")
    cost = (usage["input_tokens"] * prices["input"] + usage["cache_creation_input_tokens"] * prices["write"]
            + usage["cache_read_input_tokens"] * prices["read"] + output * prices["output"]) / 1000000
    require(math.isclose(cost, record["estimatedModelCostUsd"], abs_tol=1e-12), "Recorded cost mismatch")
    call_id = record["headers"]["x-litellm-call-id"][0]
    row = {
        "caseId": record["matrixCaseId"], "turn": int(record["label"].rsplit("-", 1)[1]), "callId": call_id,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "file": path.name,
        "totalInputTokens": total_input, "uncachedInputTokens": usage["input_tokens"],
        "cacheWriteTokens": usage["cache_creation_input_tokens"], "cacheReadTokens": usage["cache_read_input_tokens"],
        "thinkingTokens": thinking, "outputTokens": output, "visibleOutputTokens": output - thinking,
        "headersSeconds": record["responseHeadersSeconds"], "firstBodyByteSeconds": record["firstBodyByteSeconds"],
        "firstSseSeconds": record["firstSseEventSeconds"], "ttftSeconds": record["firstVisibleTextSeconds"],
        "e2eSeconds": elapsed, "firstThinkingSeconds": record.get("firstThinkingEventSeconds"),
        "firstSignatureSeconds": record.get("firstSignatureSeconds"),
        "postFirstSseWaitSeconds": record["firstVisibleTextSeconds"] - record["firstSseEventSeconds"],
        "outputTokensPerSecond": output / elapsed, "visibleTokensPerSecond": (output - thinking) / elapsed,
        "estimatedCostUsd": cost,
    }
    return {"measurement": row, "request": record["request"], "response": record["response"],
            "providerRequest": trace, "httpStatus": record["httpStatus"], "messageStopReceived": record["messageStopReceived"],
            "messageStopSeconds": record["messageStopSeconds"], "eventTimings": record["eventTimings"],
            "prices": prices, "rawSha256": row["sha256"]}


def analyze_run(run_directory, trace_paths):
    run = Path(run_directory).resolve()
    metadata = read_json(run / "run.json")
    matrix_path = run / "matrix.json"
    matrix = read_json(matrix_path)
    require(hashlib.sha256(matrix_path.read_bytes()).hexdigest() == metadata["matrixSha256"], "Run matrix hash changed")
    runner = run / "source/scripts/invoke_case.ps1"
    require(hashlib.sha256(runner.read_bytes()).hexdigest() == metadata["runnerSha256"], "Frozen runner hash changed")
    selected = metadata["selectedCases"]
    require(metadata["status"] == "EXECUTED_PENDING_PROVIDER_TRACE_AUDIT" and not metadata["failedCases"], "Run did not complete")
    require(metadata["completedCases"] == selected, "Incomplete run state")
    traces = load_provider_traces(trace_paths)
    records = []
    used = set()
    for path in sorted(run.glob("ACA_HTTP_*.json")):
        record = read_json(path)
        require(record["sourceHashes"]["matrix"] == metadata["matrixSha256"], "Request matrix hash changed")
        call_id = record["headers"]["x-litellm-call-id"][0]
        require(call_id in traces, "Missing provider trace for a recorded call")
        used.add(call_id)
        records.append(project_raw_record(path, traces[call_id]))
    groups = validate_records(records, matrix, selected)
    cost = sum(group["costUsd"] for group in groups.values())
    require(cost + matrix["priorWorkBudgetReserveUsd"] <= matrix["budgetUsd"], "Recorded budget exceeded")
    return {"status": "PASS", "kind": "raw-run-audit", "run": run.name,
            "captured": datetime.now(timezone.utc).isoformat(), "requests": len(records),
            "configurations": len(groups), "providerCalls": len(used), "unrelatedTraceCalls": len(set(traces) - used),
            "matrixSha256": metadata["matrixSha256"], "runnerSha256": metadata["runnerSha256"],
            "metadataSha256": hashlib.sha256((run / "run.json").read_bytes()).hexdigest(),
            "analyzerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "traceInputs": [{"file": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                    for path in trace_paths],
            "questions": matrix["questions"],
            "costUsd": cost, "costBasis": "Rates recorded by this run; not a current price lookup or invoice",
            "groups": groups}


def write_run_outputs(run_directory, result):
    run = Path(run_directory)
    (run / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Run Audit", "", f'Run: {result["run"]}', f'Status: {result["status"]}',
             f'Audited at: {result["captured"]} (UTC)',
             f'Requests: {result["requests"]}; configurations: {result["configurations"]}',
             f'Provider calls matched: {result["providerCalls"]}; unrelated trace calls: {result["unrelatedTraceCalls"]}', "",
             "## Input and Contract", "",
             "This run compares client-visible waiting across its selected thinking and cache configurations.",
             "Same source and prompt order; medium effort, streaming, max_tokens=4096, no tools and no retries.",
             "Histories grow from each configuration's own responses, so cache is not an isolated causal variable.",
             "[Full source and matrix](matrix.json) | [Raw-file hashes and metrics](analysis.json)", ""]
    for index, question in enumerate(result["questions"], 1):
        lines.extend([f"{index}. {question}", ""])
    lines.extend(["## Observations", "", f'Estimated model cost: USD {result["costUsd"]:.8f}', "", result["costBasis"], "",
             "One dependent five-turn conversation per configuration. No production-tail, quality-equivalence or causal claim.",
             "Cache-read share = total read / (uncached + written + read) input tokens across all five turns.",
             "Initial writes are not hits; new prompts and history still need processing.",
             "First text spans client send to the first nonempty text_delta. E2E ends at complete stream consumption.",
             "Output tokens/s includes thinking and uses full client E2E; visible output subtracts thinking tokens.", ""])
    for case_id, group in result["groups"].items():
        config = group["config"]
        lines.extend([f'### {MODEL_NAMES[config["model"]]} / {config["thinking"]} / {config["cache"]}',
                      "", f"Case: `{case_id}`", "", "| Metric | Value |", "|---|---:|",
                      f'| Cache-read share | {group["cacheReadSharePercent"]:.2f}% |',
                      f'| First text P50 | {group["ttftSeconds"]["p50"]:.3f} s |',
                      f'| E2E P50 | {group["e2eSeconds"]["p50"]:.3f} s |',
                      f'| Output P50 | {group["outputTokensPerSecond"]["p50"]:.2f} tokens/s |',
                      f'| Visible output P50 | {group["visibleTokensPerSecond"]["p50"]:.2f} tokens/s |', ""])
    (run / "analysis.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run-directory", type=Path)
    parser.add_argument("--trace-file", type=Path, action="append", default=[])
    args = parser.parse_args()
    if bool(args.run_directory) != bool(args.trace_file):
        parser.error("--run-directory and at least one --trace-file must be supplied together")
    result = analyze_run(args.run_directory, args.trace_file) if args.run_directory else validate()
    if args.run_directory and not args.check:
        write_run_outputs(args.run_directory, result)
    if args.check or args.run_directory:
        result = {key: value for key, value in result.items() if key != "groups"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()