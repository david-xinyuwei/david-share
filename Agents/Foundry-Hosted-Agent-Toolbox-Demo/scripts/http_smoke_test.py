import argparse
import json
from pathlib import Path

import httpx


REQUEST_DIR = Path(__file__).resolve().parents[1] / "examples" / "requests"


def load_request(name: str) -> dict[str, str]:
    with (REQUEST_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def post_response(client: httpx.Client, base_url: str, body: dict[str, str]) -> dict[str, object]:
    response = client.post(f"{base_url.rstrip('/')}/responses", json=body)
    response.raise_for_status()
    return response.json()


def extract_text(payload: dict[str, object]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text" and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks) or json.dumps(payload, indent=2)[:2000]


def main() -> None:
    parser = argparse.ArgumentParser(description="HTTP smoke test for the local Responses server.")
    parser.add_argument("--base-url", default="http://localhost:8088")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--skip-web", action="store_true", help="Only test the Toolbox code_interpreter path.")
    args = parser.parse_args()

    with httpx.Client(timeout=args.timeout) as client:
        code_payload = post_response(client, args.base_url, load_request("code_interpreter.json"))
        print("CODE_HTTP_RESULT_START")
        print(extract_text(code_payload))
        print("CODE_HTTP_RESULT_END")

        if not args.skip_web:
            web_payload = post_response(client, args.base_url, load_request("direct_web_search.json"))
            print("WEB_HTTP_RESULT_START")
            print(extract_text(web_payload))
            print("WEB_HTTP_RESULT_END")


if __name__ == "__main__":
    main()