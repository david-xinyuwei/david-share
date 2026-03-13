#!/usr/bin/env python3
"""Translate README-CN.md to English using Azure OpenAI."""
import os, sys, re, time

from openai import AzureOpenAI

ENDPOINT = "https://admin-0620-resource.cognitiveservices.azure.com/"
API_KEY = "02dbc25d9eb44cc19b60d699ce7dd995"
MODEL = "gpt-5"
API_VERSION = "2025-01-01-preview"

client = AzureOpenAI(api_key=API_KEY, api_version=API_VERSION, azure_endpoint=ENDPOINT)

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def translate_chunk(text, idx, total):
    if not text.strip() or not has_chinese(text):
        return text
    print(f"  [{idx}/{total}] {len(text.splitlines())} lines...", end='', flush=True)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": """You are a professional AI/ML technical translator. Translate Chinese markdown to English.
Rules:
- Keep ALL markdown formatting (#, **, -, ```, etc.) exactly as-is
- Keep ALL code blocks COMPLETELY unchanged (do not translate code, variable names, code comments)
- Keep ALL image refs ![...](...) and URLs exactly as-is
- Keep table structure, translate Chinese cell content to English
- Professional technical English
- Keep tech terms: DPO, PPO, GRPO, LoRA, QLoRA, SFT, RLHF, RLAIF, GaLore, FSDP, DeepSpeed, etc.
- Output ONLY the translated text, no extra commentary
- Lines already in English: keep as-is unchanged
- Mixed lines: translate Chinese parts, keep English parts
- Translate '原文来自' to 'Originally from'"""},
                    {"role": "user", "content": text}
                ],
                max_completion_tokens=16000,
            )
            print(f" OK")
            return resp.choices[0].message.content
        except Exception as e:
            print(f" err:{e}", end='', flush=True)
            time.sleep(3*(attempt+1))
    print(" FAILED")
    return text

def split_chunks(content, max_lines=200):
    lines = content.split('\n')
    chunks, current = [], []
    in_code = False
    for line in lines:
        if line.strip().startswith('```'):
            in_code = not in_code
        if not in_code and line.startswith('# Part ') and current:
            chunks.append('\n'.join(current))
            current = [line]
        elif not in_code and len(current) >= max_lines and line.strip() == '':
            current.append(line)
            chunks.append('\n'.join(current))
            current = []
        else:
            current.append(line)
    if current:
        chunks.append('\n'.join(current))
    return chunks

def process(input_path, output_path):
    print(f"\n{'='*60}")
    print(f"IN:  {input_path}")
    print(f"OUT: {output_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"Lines: {content.count(chr(10))}")
    chunks = split_chunks(content)
    print(f"Chunks: {len(chunks)}")
    translated = []
    for i, chunk in enumerate(chunks):
        if has_chinese(chunk):
            translated.append(translate_chunk(chunk, i+1, len(chunks)))
        else:
            print(f"  [{i+1}/{len(chunks)}] EN only, skip")
            translated.append(chunk)
    output = '\n'.join(translated)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)
    rem = sum(1 for l in output.split('\n') if has_chinese(l) and not l.strip().startswith('![') and 'mmbiz' not in l and 'qpic.cn' not in l)
    print(f"Done: {output.count(chr(10))} lines, {rem} CN lines remaining")

import platform
if platform.system() == "Windows":
    BASE = r"G:\github\david-share\Deep-Learning"
else:
    BASE = "/mnt/g/github/david-share/Deep-Learning"
process(os.path.join(BASE, "LLM-Fine-Tuning-and-Alignment", "README-CN.md"),
        os.path.join(BASE, "LLM-Fine-Tuning-and-Alignment", "README.md"))
process(os.path.join(BASE, "LLM-RL-Training-and-Reasoning", "README-CN.md"),
        os.path.join(BASE, "LLM-RL-Training-and-Reasoning", "README.md"))
print("\nALL DONE!")
