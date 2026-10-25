import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def require(value, message):
    if not value:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def quantile(values, probability):
    values = sorted(values)
    return values[math.ceil(probability * len(values)) - 1] if values else None


def validate_records(records, matrix):
    require(len(records) == matrix["attemptLimit"] == 50, "Expected fifty records")
    cases = {case["id"]: case for case in matrix["cases"]}
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
            require(request["system"] == matrix["baseRequest"]["system"], "Changed source material")
            require(request["thinking"] == trace["thinking"] == {"type": case["thinking"]}, "Thinking mode changed")
            require(request["output_config"] == trace["output_config"] == {"effort": "medium"}, "Effort changed")
            require(request["stream"] is True and trace["stream"] is True and request["max_tokens"] == trace["max_tokens"] == 4096, "Generation settings changed")
            markers = {item["path"]: item["value"] for item in trace["cache_markers"]}
            expected_markers = {"system[0].cache_control": {"type": "ephemeral"}}
            if case["cache"] == "conversation":
                expected_markers["cache_control"] = {"type": "ephemeral"}
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
    require(len(seen) == 50, "Unknown records outside matrix")
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.check:
        result = {key: value for key, value in result.items() if key != "groups"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()