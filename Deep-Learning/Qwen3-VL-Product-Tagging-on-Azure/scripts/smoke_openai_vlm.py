import argparse
import base64
import json
import mimetypes
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator


def image_to_data_url(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Response did not contain a JSON object")
        return json.loads(text[start : end + 1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Image-observed smoke test for an OpenAI-compatible VLM endpoint.")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--image", type=Path, default=Path("data/sample_images/synthetic_jacket.png"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/product_tag.schema.json"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    image_url = image_to_data_url(args.image)

    prompt = (
        "Inspect the product image and return only valid JSON matching this schema: "
        "category, colors, materials, patterns, style_tags, attributes, confidence."
    )
    body = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 256,
    }

    headers = {"Authorization": f"Bearer {args.api_key}"}
    url = args.base_url.rstrip("/") + "/chat/completions"
    with httpx.Client(timeout=args.timeout) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

    parsed = extract_json(content)
    errors = sorted(validator.iter_errors(parsed), key=lambda error: list(error.path))
    if errors:
        for error in errors:
            print(f"SCHEMA_ERROR {list(error.path)}: {error.message}")
        raise SystemExit(2)

    joined = json.dumps(parsed, ensure_ascii=False).lower()
    observed_terms = ["jacket", "navy", "collar", "sleeve", "formal", "solid"]
    if not any(term in joined for term in observed_terms):
        print("IMAGE_OBSERVED_WARNING: parsed JSON did not mention expected visible product terms")
        raise SystemExit(3)

    print("SMOKE_PASS")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
