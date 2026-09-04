#!/usr/bin/env python3
"""Back-translate the Chinese README with Azure AI Translator and record evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "README-CN.md"
DEFAULT_ENGLISH = ROOT / "README.md"
DEFAULT_OUTPUT = ROOT / "evidence" / "translator-back-translation.json"
TRANSLATOR_HOST = "api.cognitive.microsofttranslator.com"
CJK_RE = re.compile(r"[\u3400-\u9fff]")
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:\d{4}-\d{2}-\d{2}|\d+(?:\.\d+)?)(?![A-Za-z0-9_])"
)
STAGE_WORDS = {
    "one": "1",
    "first": "1",
    "two": "2",
    "second": "2",
    "three": "3",
    "third": "3",
    "four": "4",
    "fourth": "4",
    "five": "5",
    "fifth": "5",
}
CHINESE_STAGE_NUMBERS = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
}
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_markdown_line(line: str) -> str:
    if TABLE_SEPARATOR_RE.fullmatch(line):
        return ""
    value = html.unescape(line.strip())
    value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("`", "").replace("**", "").replace("__", "")
    value = re.sub(r"^#{1,6}\s*", "", value)
    value = re.sub(r"^(?:[-*+]\s+|>\s*|\d+\.\s+)", "", value)
    if value.startswith("|") and value.endswith("|"):
        value = " — ".join(cell.strip() for cell in value.strip("|").split("|"))
    return " ".join(value.split())


def extract_translation_units(markdown: str) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    buffer: list[str] = []
    buffer_start = 0
    buffer_end = 0
    in_fence = False

    def flush() -> None:
        nonlocal buffer, buffer_start, buffer_end
        text = " ".join(buffer).strip()
        if text and CJK_RE.search(text):
            units.append(
                {
                    "lineStart": buffer_start,
                    "lineEnd": buffer_end,
                    "text": text,
                }
            )
        buffer = []
        buffer_start = 0
        buffer_end = 0

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        normalized = normalize_markdown_line(line)
        if not normalized or not CJK_RE.search(normalized):
            flush()
            continue
        stripped = line.lstrip()
        standalone = stripped.startswith(("#", "|", "- ", "* ", "+ ", "> "))
        if standalone:
            flush()
            units.append(
                {
                    "lineStart": line_number,
                    "lineEnd": line_number,
                    "text": normalized,
                }
            )
            continue
        if not buffer:
            buffer_start = line_number
        buffer.append(normalized)
        buffer_end = line_number
    flush()
    return units


def batch_units(
    units: list[dict[str, object]],
    max_items: int = 90,
    max_characters: int = 40_000,
) -> list[list[dict[str, object]]]:
    batches: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    character_count = 0
    for unit in units:
        text_length = len(str(unit["text"]))
        if text_length > max_characters:
            raise ValueError("A translation unit exceeds the Translator request budget")
        if current and (
            len(current) >= max_items
            or character_count + text_length > max_characters
        ):
            batches.append(current)
            current = []
            character_count = 0
        current.append(unit)
        character_count += text_length
    if current:
        batches.append(current)
    return batches


def numeric_tokens(text: str) -> set[str]:
    tokens = set(NUMBER_RE.findall(text))
    for match in re.finditer(
        r"\b(one|first|two|second|three|third|four|fourth|five|fifth)[- ](?:stage|phase)s?\b",
        text,
        flags=re.IGNORECASE,
    ):
        tokens.add(STAGE_WORDS[match.group(1).lower()])
    for match in re.finditer(r"(?:第\s*)?([一二三四五])\s*阶段", text):
        tokens.add(CHINESE_STAGE_NUMBERS[match.group(1)])
    return tokens


def numeric_drift(source: str, target: str) -> dict[str, object]:
    source_tokens = numeric_tokens(source)
    target_tokens = numeric_tokens(target)
    missing = source_tokens - target_tokens
    added = target_tokens - source_tokens
    return {
        "count": len(missing) + len(added),
        "missing": {token: 1 for token in sorted(missing)},
        "added": {token: 1 for token in sorted(added)},
    }


def translate_batch(
    units: list[dict[str, object]],
    endpoint: str,
    key: str,
    region: str | None,
    opener=urllib.request.urlopen,
) -> tuple[list[str], dict[str, object]]:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "https" or parsed.hostname != TRANSLATOR_HOST:
        raise ValueError("--endpoint must be the global Azure AI Translator endpoint")
    url = (
        f"https://{TRANSLATOR_HOST}/translate"
        "?api-version=3.0&from=zh-Hans&to=en"
    )
    body = json.dumps(
        [{"Text": unit["text"]} for unit in units],
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json; charset=UTF-8",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    if region and region.lower() != "global":
        headers["Ocp-Apim-Subscription-Region"] = region
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with opener(request, timeout=90) as response:
            response_body = response.read()
            response_headers = response.headers
            status = response.status
    except urllib.error.HTTPError as error:
        detail = error.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure AI Translator returned HTTP {error.code}: {detail}") from error
    payload = json.loads(response_body)
    if status != 200 or len(payload) != len(units):
        raise RuntimeError("Azure AI Translator returned an incomplete response")
    translations = [
        str(item["translations"][0]["text"])
        for item in payload
    ]
    request_id = response_headers.get("X-RequestId", "")
    return translations, {
        "httpStatus": status,
        "requestIdSha256": sha256_text(request_id) if request_id else None,
        "meteredUsage": int(response_headers.get("X-Metered-Usage", "0") or 0),
    }


def build_document(args: argparse.Namespace) -> dict[str, object]:
    key = os.getenv(args.key_environment_variable)
    if not key:
        raise RuntimeError(f"{args.key_environment_variable} is required")
    source_text = args.source.read_text(encoding="utf-8")
    english_text = args.english.read_text(encoding="utf-8")
    units = extract_translation_units(source_text)
    if not units:
        raise RuntimeError("No Chinese prose units were extracted")

    translations: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []
    for batch_index, batch in enumerate(batch_units(units), start=1):
        translated, call = translate_batch(
            batch,
            args.endpoint,
            key,
            args.resource_location,
        )
        calls.append(
            {
                "batch": batch_index,
                "unitCount": len(batch),
                **call,
            }
        )
        translations.extend(
            {
                "lineStart": unit["lineStart"],
                "lineEnd": unit["lineEnd"],
                "sourceSha256": sha256_text(str(unit["text"])),
                "backTranslation": translated_text,
            }
            for unit, translated_text in zip(batch, translated, strict=True)
        )

    source_prose = "\n".join(str(unit["text"]) for unit in units)
    back_translation = "\n".join(
        str(item["backTranslation"]) for item in translations
    )
    resource_id = os.getenv(args.resource_id_environment_variable, "")
    drift = {
        "englishToChinese": numeric_drift(english_text, source_text),
        "chineseToBackTranslation": numeric_drift(
            source_prose,
            back_translation,
        ),
    }
    return {
        "schemaVersion": 1,
        "service": "Azure AI Translator",
        "apiVersion": "3.0",
        "sourceLanguage": "zh-Hans",
        "targetLanguage": "en",
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "resource": {
            "kind": args.resource_kind,
            "sku": args.resource_sku,
            "location": args.resource_location,
            "endpointHost": TRANSLATOR_HOST,
            "resourceIdSha256": sha256_text(resource_id) if resource_id else None,
        },
        "inputs": {
            "chinesePath": args.source.relative_to(ROOT).as_posix(),
            "chineseSha256": sha256_file(args.source),
            "englishPath": args.english.relative_to(ROOT).as_posix(),
            "englishSha256": sha256_file(args.english),
            "translationUnitCount": len(units),
            "sourceCharacterCount": len(source_prose),
        },
        "calls": calls,
        "translations": translations,
        "numericDrift": drift,
        "outputSha256": sha256_text(back_translation),
        "status": (
            "PASS" if all(value["count"] == 0 for value in drift.values()) else "FAIL"
        ),
    }


def validate_document(
    document: dict[str, object],
    source: pathlib.Path = DEFAULT_SOURCE,
    english: pathlib.Path = DEFAULT_ENGLISH,
) -> list[str]:
    errors: list[str] = []
    if document.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    if document.get("service") != "Azure AI Translator":
        errors.append("service must be Azure AI Translator")
    if document.get("apiVersion") != "3.0":
        errors.append("apiVersion must be 3.0")
    if document.get("sourceLanguage") != "zh-Hans" or document.get("targetLanguage") != "en":
        errors.append("translation direction must be zh-Hans to en")
    resource = document.get("resource")
    if not isinstance(resource, dict) or not (
        resource.get("kind") == "TextTranslation"
        and resource.get("sku") in {"F0", "S1"}
        and resource.get("endpointHost") == TRANSLATOR_HOST
        and isinstance(resource.get("resourceIdSha256"), str)
        and len(resource["resourceIdSha256"]) == 64
    ):
        errors.append("Translator resource identity is incomplete")
    inputs = document.get("inputs")
    if not isinstance(inputs, dict) or not (
        inputs.get("chineseSha256") == sha256_file(source)
        and inputs.get("englishSha256") == sha256_file(english)
        and isinstance(inputs.get("translationUnitCount"), int)
        and inputs["translationUnitCount"] > 0
    ):
        errors.append("Translator input hashes or unit count are stale")
    calls = document.get("calls")
    if not isinstance(calls, list) or not calls or not all(
        isinstance(call, dict)
        and call.get("httpStatus") == 200
        and isinstance(call.get("requestIdSha256"), str)
        and len(call["requestIdSha256"]) == 64
        and isinstance(call.get("meteredUsage"), int)
        and call["meteredUsage"] > 0
        for call in calls
    ):
        errors.append("Translator call evidence is incomplete")
    translations = document.get("translations")
    if not isinstance(translations, list) or not isinstance(inputs, dict) or (
        len(translations) != inputs.get("translationUnitCount")
    ):
        errors.append("Translator output count does not match the input")
    drift = document.get("numericDrift")
    if not isinstance(drift, dict) or any(
        not isinstance(value, dict) or value.get("count") != 0
        for value in drift.values()
    ):
        errors.append("Translator numeric drift is nonzero")
    if document.get("status") != "PASS":
        errors.append("Translator evidence status is not PASS")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--english", type=pathlib.Path, default=DEFAULT_ENGLISH)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--endpoint",
        default=f"https://{TRANSLATOR_HOST}",
    )
    parser.add_argument("--resource-kind", default="TextTranslation")
    parser.add_argument("--resource-sku", default="F0")
    parser.add_argument("--resource-location", default="global")
    parser.add_argument(
        "--key-environment-variable",
        default="AZURE_TRANSLATOR_KEY",
    )
    parser.add_argument(
        "--resource-id-environment-variable",
        default="AZURE_TRANSLATOR_RESOURCE_ID",
    )
    parser.add_argument("--check", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        document = json.loads(args.output.read_text(encoding="utf-8"))
        errors = validate_document(document, args.source, args.english)
        if errors:
            for error in errors:
                print(f"ERROR {error}")
            return 1
        print("AZURE_TRANSLATOR_BACK_TRANSLATION=PASS")
        return 0
    try:
        document = build_document(args)
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        return 2
    args.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    drift = document["numericDrift"]
    print(
        json.dumps(
            {
                "status": document["status"],
                "service": document["service"],
                "calls": len(document["calls"]),
                "translationUnits": document["inputs"]["translationUnitCount"],
                "meteredUsage": sum(call["meteredUsage"] for call in document["calls"]),
                "englishToChineseNumericDrift": drift["englishToChinese"]["count"],
                "chineseToBackTranslationNumericDrift": drift["chineseToBackTranslation"]["count"],
                "output": args.output.relative_to(ROOT).as_posix(),
            },
            indent=2,
        )
    )
    return 0 if all(value["count"] == 0 for value in drift.values()) else 1


if __name__ == "__main__":
    sys.exit(main())