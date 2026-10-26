"""Send one streamed Messages request with the parameters used in the tests.

Prints the answer on stdout and one JSON line on stderr with the status, the
first-text and end times in seconds, usage and the list-price cost. Exit 0
only when the request completed (HTTP 200, message_stop, end_turn, text).
"""
import argparse
import json
import sys

from claude_api import TokenProvider, cost_usd, new_client, stream_message
from pricing import PRICES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--model", default="claude-sonnet-5-5", choices=sorted(PRICES))
    parser.add_argument("--thinking", default="adaptive", choices=["adaptive", "between_tools", "disabled"])
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-tokens", type=int, default=128000)
    args = parser.parse_args()
    body = {"model": args.model, "max_tokens": args.max_tokens, "stream": True,
            "thinking": {"type": args.thinking}, "output_config": {"effort": args.effort},
            "messages": [{"role": "user", "content": args.prompt}]}
    client = new_client()
    try:
        record = stream_message(client, TokenProvider(), body, deadline_s=900)
    finally:
        client.close()
    print(record["text"])
    usage = record.get("usage") or {}
    timing = record.get("timing") or {}
    summary = {"status": record["status"], "http_status": record["http_status"],
               "first_text_s": timing.get("first_text"), "end_s": timing.get("end"),
               "usage": usage, "cost_usd": cost_usd(args.model, usage) if usage else None}
    if record.get("error_body") or record.get("error"):
        summary["error"] = record.get("error_body") or record.get("error")
    print(json.dumps(summary), file=sys.stderr)
    sys.exit(0 if record["status"] == "completed" else 1)


if __name__ == "__main__":
    main()
