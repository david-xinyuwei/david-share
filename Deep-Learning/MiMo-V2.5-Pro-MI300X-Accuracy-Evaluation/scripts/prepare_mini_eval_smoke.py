#!/usr/bin/env python3
"""Add opt-in smoke controls while preserving customer full-eval defaults."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    if old not in text:
        raise RuntimeError(f"expected anchor not found in {path}: {old!r}")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor is not unique in {path}: {old!r}")
    return text.replace(old, new, 1)


def patch_aime(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "AIME_REPEATS = int(os.getenv" in text:
        print("AIME_PATCH=SKIP")
        return
    shutil.copy2(path, path.with_suffix(".py.customer-original"))
    text = replace_once(
        text,
        "MAX_CONCURRENT_REQUESTS = int(os.getenv(\"MAX_CONCURRENT_REQUESTS\", 50))\n",
        "MAX_CONCURRENT_REQUESTS = int(os.getenv(\"MAX_CONCURRENT_REQUESTS\", 50))\n"
        "MAX_SAMPLES = int(os.getenv(\"MAX_SAMPLES\", 0))\n"
        "AIME_REPEATS = int(os.getenv(\"REPEATS\", 32))\n",
        path,
    )
    text = replace_once(text, "    repeats = 32\n", "    repeats = AIME_REPEATS\n", path)
    text = replace_once(
        text,
        '    query_idxs, messages, gts = load_data("data/aime_24_25.jsonl")\n',
        '    query_idxs, messages, gts = load_data("data/aime_24_25.jsonl")\n'
        "    if MAX_SAMPLES > 0:\n"
        "        query_idxs = query_idxs[:MAX_SAMPLES]\n"
        "        messages = messages[:MAX_SAMPLES]\n"
        "        gts = gts[:MAX_SAMPLES]\n",
        path,
    )
    path.write_text(text, encoding="utf-8")
    print("AIME_PATCH=PASS")


def patch_supergpqa(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "MAX_SAMPLES = int(os.getenv" in text:
        print("SUPERGPQA_PATCH=SKIP")
        return
    shutil.copy2(path, path.with_suffix(".py.customer-original"))
    text = replace_once(
        text,
        "MAX_CONCURRENT_REQUESTS = int(os.getenv(\"MAX_CONCURRENT_REQUESTS\", 50))\n",
        "MAX_CONCURRENT_REQUESTS = int(os.getenv(\"MAX_CONCURRENT_REQUESTS\", 50))\n"
        "MAX_SAMPLES = int(os.getenv(\"MAX_SAMPLES\", 0))\n",
        path,
    )
    text = replace_once(
        text,
        '    query_idxs, messages, gts = load_data("data/SuperGPQA")\n',
        '    query_idxs, messages, gts = load_data("data/SuperGPQA")\n'
        "    if MAX_SAMPLES > 0:\n"
        "        query_idxs = query_idxs[:MAX_SAMPLES]\n"
        "        messages = messages[:MAX_SAMPLES]\n"
        "        gts = gts[:MAX_SAMPLES]\n",
        path,
    )
    path.write_text(text, encoding="utf-8")
    print("SUPERGPQA_PATCH=PASS")


def patch_sample_offset(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SAMPLE_OFFSET = int(os.getenv" in text:
        print(f"SAMPLE_OFFSET_PATCH=SKIP path={path.name}")
        return
    text = replace_once(
        text,
        'MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 0))\n',
        'MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 0))\n'
        'SAMPLE_OFFSET = int(os.getenv("SAMPLE_OFFSET", 0))\n',
        path,
    )
    old_slice = (
        "    if MAX_SAMPLES > 0:\n"
        "        query_idxs = query_idxs[:MAX_SAMPLES]\n"
        "        messages = messages[:MAX_SAMPLES]\n"
        "        gts = gts[:MAX_SAMPLES]\n"
    )
    new_slice = (
        "    if MAX_SAMPLES > 0:\n"
        "        stop = SAMPLE_OFFSET + MAX_SAMPLES\n"
        "        query_idxs = query_idxs[SAMPLE_OFFSET:stop]\n"
        "        messages = messages[SAMPLE_OFFSET:stop]\n"
        "        gts = gts[SAMPLE_OFFSET:stop]\n"
    )
    text = replace_once(text, old_slice, new_slice, path)
    path.write_text(text, encoding="utf-8")
    print(f"SAMPLE_OFFSET_PATCH=PASS path={path.name}")


def patch_fail_closed(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if (
        "raise RuntimeError(" in text
        and "Request {request_idx} failed after {max_retries} attempts: {e}" in text
    ):
        print(f"FAIL_CLOSED_PATCH=SKIP path={path.name}")
        return
    old = (
        "                else:\n"
        "                    print(f\"Failed to get response for request {request_idx}: {e}\")\n"
        "                    return request_idx, \"\"\n"
    )
    new = (
        "                else:\n"
        "                    raise RuntimeError(\n"
        "                        f\"Request {request_idx} failed after {max_retries} attempts: {e}\"\n"
        "                    ) from e\n"
    )
    text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")
    print(f"FAIL_CLOSED_PATCH=PASS path={path.name}")


def patch_live_progress(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "LIVE_PROGRESS_PATH = os.getenv" in text:
        print(f"LIVE_PROGRESS_PATCH=SKIP path={path.name}")
        return

    text = replace_once(
        text,
        'STREAM_MODE = os.getenv("STREAM_MODE", "true").lower() == "true"\n'
        if path.name == "eval_aime.py"
        else 'MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 50))\n',
        (
            'STREAM_MODE = os.getenv("STREAM_MODE", "true").lower() == "true"\n'
            'LIVE_PROGRESS_PATH = os.getenv("LIVE_PROGRESS_PATH")\n'
        )
        if path.name == "eval_aime.py"
        else (
            'MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 50))\n'
            'LIVE_PROGRESS_PATH = os.getenv("LIVE_PROGRESS_PATH")\n'
        ),
        path,
    )

    if path.name == "eval_aime.py":
        anchor = (
            "        if convert_int(extracted_pred) == convert_int(results[query_idx]['ground_truth']):\n"
            "            results[query_idx]['metrics'].append(1)\n"
            "        else:\n"
            "            results[query_idx]['metrics'].append(0)\n"
        )
        replacement = anchor + (
            "\n"
            "        if LIVE_PROGRESS_PATH:\n"
            "            live_record = {\n"
            "                'request_idx': request_idx,\n"
            "                'query_idx': query_idx,\n"
            "                'repeat_idx': int(repeat_idx),\n"
            "                'ground_truth': results[query_idx]['ground_truth'],\n"
            "                'prediction': extracted_pred,\n"
            "                'metric': results[query_idx]['metrics'][-1],\n"
            "                'response_empty': not bool(response),\n"
            "                'response_chars': len(response),\n"
            "            }\n"
            "            with open(LIVE_PROGRESS_PATH, 'a') as live_fw:\n"
            "                live_fw.write(json.dumps(live_record, ensure_ascii=False) + '\\n')\n"
            "                live_fw.flush()\n"
        )
    else:
        anchor = (
            "        if pred == results[query_idx][\"ground_truth\"]:\n"
            "            results[query_idx][\"metrics\"].append(1)\n"
            "        else:\n"
            "            results[query_idx][\"metrics\"].append(0)\n"
        )
        replacement = anchor + (
            "\n"
            "        if LIVE_PROGRESS_PATH:\n"
            "            live_record = {\n"
            "                'request_idx': request_idx,\n"
            "                'query_idx': query_idx,\n"
            "                'repeat_idx': int(repeat_idx),\n"
            "                'ground_truth': results[query_idx]['ground_truth'],\n"
            "                'prediction': pred,\n"
            "                'metric': results[query_idx]['metrics'][-1],\n"
            "                'response_empty': not bool(response),\n"
            "                'response_chars': len(response),\n"
            "            }\n"
            "            with open(LIVE_PROGRESS_PATH, 'a') as live_fw:\n"
            "                live_fw.write(json.dumps(live_record, ensure_ascii=False) + '\\n')\n"
            "                live_fw.flush()\n"
        )

    text = replace_once(text, anchor, replacement, path)
    path.write_text(text, encoding="utf-8")
    print(f"LIVE_PROGRESS_PATCH=PASS path={path.name}")


def patch_sharding(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SHARD_INDEX = int(os.getenv" in text:
        print(f"SHARDING_PATCH=SKIP path={path.name}")
        return

    text = replace_once(
        text,
        'SAMPLE_OFFSET = int(os.getenv("SAMPLE_OFFSET", 0))\n',
        'SAMPLE_OFFSET = int(os.getenv("SAMPLE_OFFSET", 0))\n'
        'SHARD_INDEX = int(os.getenv("SHARD_INDEX", 0))\n'
        'SHARD_COUNT = int(os.getenv("SHARD_COUNT", 1))\n',
        path,
    )
    if path.name == "eval_aime.py":
        text = replace_once(
            text,
            "    tasks = []\n"
            "    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)\n"
            "    for repeat_idx in range(repeats):\n"
            "        for query_idx, message in zip(query_idxs, messages):\n",
            "    if SHARD_COUNT < 1 or not 0 <= SHARD_INDEX < SHARD_COUNT:\n"
            "        raise ValueError(\"Invalid SHARD_INDEX/SHARD_COUNT\")\n"
            "\n"
            "    tasks = []\n"
            "    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)\n"
            "    for repeat_idx in range(repeats):\n"
            "        if repeat_idx % SHARD_COUNT != SHARD_INDEX:\n"
            "            continue\n"
            "        for query_idx, message in zip(query_idxs, messages):\n",
            path,
        )
    else:
        text = replace_once(
            text,
            "    results = {}\n",
            "    if SHARD_COUNT < 1 or not 0 <= SHARD_INDEX < SHARD_COUNT:\n"
            "        raise ValueError(\"Invalid SHARD_INDEX/SHARD_COUNT\")\n"
            "    selected = [\n"
            "        (query_idx, message, gt)\n"
            "        for query_idx, message, gt in zip(query_idxs, messages, gts)\n"
            "        if query_idx % SHARD_COUNT == SHARD_INDEX\n"
            "    ]\n"
            "    query_idxs = [item[0] for item in selected]\n"
            "    messages = [item[1] for item in selected]\n"
            "    gts = [item[2] for item in selected]\n"
            "\n"
            "    results = {}\n",
            path,
        )

    text = text.replace(
        "                'response_chars': len(response),\n",
        "                'response_chars': len(response),\n"
        "                'shard_index': SHARD_INDEX,\n"
        "                'shard_count': SHARD_COUNT,\n",
        1,
    )
    path.write_text(text, encoding="utf-8")
    print(f"SHARDING_PATCH=PASS path={path.name}")


def patch_aime_repeat_provenance(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if '"repeat_indices": []' in text:
        print("AIME_REPEAT_PROVENANCE_PATCH=SKIP")
        return
    text = replace_once(
        text,
        '            "ground_truth": gt,\n'
        '            "model_responses": [],\n',
        '            "ground_truth": gt,\n'
        '            "repeat_indices": [],\n'
        '            "model_responses": [],\n',
        path,
    )
    text = replace_once(
        text,
        "        query_idx = int(\"_\".join(request_idx.split(\"_\")[1:]))\n"
        "        results[query_idx]['model_responses'].append(response)\n",
        "        query_idx = int(\"_\".join(request_idx.split(\"_\")[1:]))\n"
        "        results[query_idx]['repeat_indices'].append(int(repeat_idx))\n"
        "        results[query_idx]['model_responses'].append(response)\n",
        path,
    )
    path.write_text(text, encoding="utf-8")
    print("AIME_REPEAT_PROVENANCE_PATCH=PASS")


def patch_aime_executed_repeat_count(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "executed_repeat_indices = [" in text:
        print("AIME_EXECUTED_REPEAT_COUNT_PATCH=SKIP")
        return
    text = replace_once(
        text,
        "    tasks = []\n"
        "    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)\n"
        "    for repeat_idx in range(repeats):\n"
        "        if repeat_idx % SHARD_COUNT != SHARD_INDEX:\n"
        "            continue\n"
        "        for query_idx, message in zip(query_idxs, messages):\n",
        "    executed_repeat_indices = [\n"
        "        repeat_idx\n"
        "        for repeat_idx in range(repeats)\n"
        "        if repeat_idx % SHARD_COUNT == SHARD_INDEX\n"
        "    ]\n"
        "    if not executed_repeat_indices:\n"
        "        raise ValueError(\"AIME shard selects no repeat indices\")\n"
        "\n"
        "    tasks = []\n"
        "    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)\n"
        "    for repeat_idx in executed_repeat_indices:\n"
        "        for query_idx, message in zip(query_idxs, messages):\n",
        path,
    )
    text = replace_once(
        text,
        '    print(f"AIME Accuracy over {repeats} runs: {sum(final_metric) / len(final_metric) * 100:.4f}")\n',
        '    print(f"AIME Accuracy over {len(executed_repeat_indices)} runs: {sum(final_metric) / len(final_metric) * 100:.4f}")\n',
        path,
    )
    text = replace_once(
        text,
        '        "repeats": repeats,\n',
        '        "repeats": len(executed_repeat_indices),\n',
        path,
    )
    path.write_text(text, encoding="utf-8")
    print("AIME_EXECUTED_REPEAT_COUNT_PATCH=PASS")


def patch_generic_eval_controls(
    path: Path, default_repeats: int, load_anchor: str
) -> None:
    text = path.read_text(encoding="utf-8")
    if "EVAL_REPEATS = int(os.getenv" in text:
        print(f"GENERIC_CONTROLS_PATCH=SKIP path={path.name}")
        return
    backup = path.with_suffix(".py.customer-original")
    if not backup.exists():
        shutil.copy2(path, backup)
    text = replace_once(
        text,
        'MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 50))\n',
        'MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 50))\n'
        'MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 0))\n'
        'SAMPLE_OFFSET = int(os.getenv("SAMPLE_OFFSET", 0))\n'
        f'EVAL_REPEATS = int(os.getenv("REPEATS", {default_repeats}))\n',
        path,
    )
    text = replace_once(
        text,
        f"    repeats = {default_repeats}\n",
        "    repeats = EVAL_REPEATS\n",
        path,
    )
    text = replace_once(
        text,
        load_anchor,
        load_anchor
        + "    if MAX_SAMPLES > 0:\n"
        + "        stop = SAMPLE_OFFSET + MAX_SAMPLES\n"
        + "        query_idxs = query_idxs[SAMPLE_OFFSET:stop]\n"
        + "        messages = messages[SAMPLE_OFFSET:stop]\n"
        + "        gts = gts[SAMPLE_OFFSET:stop]\n",
        path,
    )
    path.write_text(text, encoding="utf-8")
    print(f"GENERIC_CONTROLS_PATCH=PASS path={path.name}")


def patch_mmlu_pro_fail_closed(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "MMLU-Pro request {request_idx} failed after {max_retries} attempts"
    if marker in text:
        print("MMLU_PRO_FAIL_CLOSED_PATCH=SKIP")
        return
    old = (
        "                else:\n"
        "                    print(f\"[llm_inference] failed on {request_idx}: {e}\")\n"
        "                    return request_idx, \"\"\n"
    )
    new = (
        "                else:\n"
        "                    raise RuntimeError(\n"
        "                        f\"MMLU-Pro request {request_idx} failed after {max_retries} attempts: {e}\"\n"
        "                    ) from e\n"
    )
    text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")
    print("MMLU_PRO_FAIL_CLOSED_PATCH=PASS")


def patch_repeat_offset(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "REPEAT_OFFSET = int(os.getenv" in text:
        print(f"REPEAT_OFFSET_PATCH=SKIP path={path.name}")
        return
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("EVAL_REPEATS = int(os.getenv"):
            lines.insert(
                index + 1,
                'REPEAT_OFFSET = int(os.getenv("REPEAT_OFFSET", 0))\n',
            )
            text = "".join(lines)
            break
    else:
        text = replace_once(
            text,
            'MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 0))\n',
            'MAX_SAMPLES = int(os.getenv("MAX_SAMPLES", 0))\n'
            'REPEAT_OFFSET = int(os.getenv("REPEAT_OFFSET", 0))\n',
            path,
        )
    text = replace_once(
        text,
        "    for repeat_idx in range(repeats):\n",
        "    for repeat_idx in range(REPEAT_OFFSET, REPEAT_OFFSET + repeats):\n",
        path,
    )
    path.write_text(text, encoding="utf-8")
    print(f"REPEAT_OFFSET_PATCH=PASS path={path.name}")


def patch_response_metadata(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    response_name = "resp" if path.name in {"eval_cmmlu.py", "eval_mmlu_pro.py"} else "response"
    if '"response_metadata": []' in text:
        repeat_marker = '"repeat_idx": int(str(request_idx).split("_", 1)[0])'
        if repeat_marker not in text:
            anchor = f'                    "response_id": getattr({response_name}, "id", None),\n'
            replacement = (
                anchor
                + '                    "request_idx": str(request_idx),\n'
                + '                    "repeat_idx": int(str(request_idx).split("_", 1)[0]),\n'
            )
            text = replace_once(text, anchor, replacement, path)
            path.write_text(text, encoding="utf-8")
            print(f"RESPONSE_REPEAT_PROVENANCE_PATCH=PASS path={path.name}")
            return
        print(f"RESPONSE_METADATA_PATCH=SKIP path={path.name}")
        return

    return_anchor = "                return request_idx, content\n"
    metadata_block = (
        "                usage = getattr(RESPONSE_OBJECT, \"usage\", None)\n"
        "                metadata = {\n"
        "                    \"response_id\": getattr(RESPONSE_OBJECT, \"id\", None),\n"
        "                    \"request_idx\": str(request_idx),\n"
        "                    \"repeat_idx\": int(str(request_idx).split(\"_\", 1)[0]),\n"
        "                    \"finish_reason\": getattr(choice0, \"finish_reason\", None),\n"
        "                    \"content_is_none\": getattr(msg0, \"content\", None) is None,\n"
        "                    \"content_chars\": len(getattr(msg0, \"content\", None) or \"\"),\n"
        "                    \"reasoning_chars\": len(getattr(msg0, \"reasoning_content\", None) or \"\"),\n"
        "                    \"tool_calls_present\": bool(getattr(msg0, \"tool_calls\", None)),\n"
        "                    \"prompt_tokens\": getattr(usage, \"prompt_tokens\", None),\n"
        "                    \"completion_tokens\": getattr(usage, \"completion_tokens\", None),\n"
        "                    \"total_tokens\": getattr(usage, \"total_tokens\", None),\n"
        "                }\n"
        "                return request_idx, content, metadata\n"
    ).replace("RESPONSE_OBJECT", response_name)
    text = replace_once(text, return_anchor, metadata_block, path)
    text = replace_once(
        text,
        '            "metrics": [],\n',
        '            "metrics": [],\n'
        '            "response_metadata": [],\n',
        path,
    )
    text = replace_once(
        text,
        "        request_idx, response = await future\n",
        "        request_idx, response, response_metadata = await future\n",
        path,
    )
    append_anchor = (
        '        results[qid]["model_responses"].append(response)\n'
        if path.name == "eval_cmmlu.py"
        else '        results[query_idx]["model_responses"].append(response)\n'
    )
    append_replacement = append_anchor + (
        '        results[qid]["response_metadata"].append(response_metadata)\n'
        if path.name == "eval_cmmlu.py"
        else '        results[query_idx]["response_metadata"].append(response_metadata)\n'
    )
    text = replace_once(text, append_anchor, append_replacement, path)

    if path.name == "eval_supergpqa.py":
        text = replace_once(
            text,
            "                'response_chars': len(response),\n",
            "                'response_chars': len(response),\n"
            "                'response_metadata': response_metadata,\n",
            path,
        )
    path.write_text(text, encoding="utf-8")
    print(f"RESPONSE_METADATA_PATCH=PASS path={path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    args = parser.parse_args()
    aime_path = args.source_dir / "eval_aime.py"
    supergpqa_path = args.source_dir / "eval_supergpqa.py"
    patch_aime(aime_path)
    patch_supergpqa(supergpqa_path)
    patch_sample_offset(aime_path)
    patch_sample_offset(supergpqa_path)
    patch_fail_closed(aime_path)
    patch_fail_closed(supergpqa_path)
    patch_live_progress(aime_path)
    patch_live_progress(supergpqa_path)
    patch_sharding(aime_path)
    patch_sharding(supergpqa_path)
    patch_aime_repeat_provenance(aime_path)
    patch_aime_executed_repeat_count(aime_path)

    generic_specs = [
        (
            args.source_dir / "eval_cmmlu.py",
            3,
            "    query_idxs, messages, gts = load_cmmlu_data(CMMLU_DATASET_NAME)\n",
        ),
        (
            args.source_dir / "eval_minerva_math.py",
            3,
            '    query_idxs, messages, gts = load_data("data/hendrycks_math")\n',
        ),
        (
            args.source_dir / "eval_mmlu_pro.py",
            2,
            "    query_idxs, messages, gts = load_mmlu_pro_data(MMLU_PRO_DATASET)\n",
        ),
        (
            args.source_dir / "eval_mmlu_redux.py",
            6,
            '    query_idxs, messages, gts = load_data("data/mmlu-redux-2.1")\n',
        ),
    ]
    for path, default_repeats, load_anchor in generic_specs:
        patch_generic_eval_controls(path, default_repeats, load_anchor)
    for path, _, _ in generic_specs:
        patch_repeat_offset(path)
    patch_repeat_offset(supergpqa_path)
    for path, _, _ in generic_specs:
        if path.name == "eval_mmlu_pro.py":
            patch_mmlu_pro_fail_closed(path)
        else:
            patch_fail_closed(path)
    for path, _, _ in generic_specs:
        patch_response_metadata(path)
    patch_response_metadata(supergpqa_path)


if __name__ == "__main__":
    main()
