#!/usr/bin/env python3
"""
Translate mixed CN/EN README to pure English using Azure OpenAI.
Run this on a VM with internet access (e.g., personalvm).
"""
import os, sys, re, time, json

AOAI_KEY = sys.argv[1] if len(sys.argv) > 1 else ""
AOAI_ENDPOINT = sys.argv[2] if len(sys.argv) > 2 else ""
AOAI_DEPLOYMENT = sys.argv[3] if len(sys.argv) > 3 else "gpt-4o"
INPUT_FILE = sys.argv[4] if len(sys.argv) > 4 else ""
OUTPUT_FILE = sys.argv[5] if len(sys.argv) > 5 else ""

if not all([AOAI_KEY, AOAI_ENDPOINT, INPUT_FILE, OUTPUT_FILE]):
    print("Usage: python3 translate_remote.py <key> <endpoint> <deployment> <input.md> <output.md>")
    sys.exit(1)

from openai import AzureOpenAI
client = AzureOpenAI(api_key=AOAI_KEY, api_version="2025-04-01-preview", azure_endpoint=AOAI_ENDPOINT)

def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def translate_chunk(text, idx, total):
    if not text.strip() or not has_chinese(text):
        return text
    print(f"  [{idx}/{total}] Translating {len(text.splitlines())} lines...", end='', flush=True)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=AOAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": """You are a professional AI/ML technical translator. Translate Chinese markdown to English.
Rules:
- Keep ALL markdown formatting exactly as-is
- Keep ALL code blocks COMPLETELY unchanged
- Keep ALL image references ![...](...) as-is
- Keep ALL URLs as-is
- Keep table structure, translate cell content
- Professional technical English
- Keep tech terms: DPO, PPO, GRPO, LoRA, QLoRA, SFT, RLHF, etc.
- Output ONLY translated text
- Lines already in English: keep as-is
- Translate '原文来自' to 'Originally from'"""},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=16000,
            )
            result = resp.choices[0].message.content
            print(f" OK")
            return result
        except Exception as e:
            print(f" retry({e})", end='', flush=True)
            time.sleep(3*(attempt+1))
    print(f" FAILED")
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

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    content = f.read()
print(f"Input: {INPUT_FILE} ({content.count(chr(10))} lines)")

chunks = split_chunks(content)
print(f"Chunks: {len(chunks)}")

translated = []
for i, chunk in enumerate(chunks):
    if has_chinese(chunk):
        translated.append(translate_chunk(chunk, i+1, len(chunks)))
    else:
        print(f"  [{i+1}/{len(chunks)}] English only, keeping")
        translated.append(chunk)

output = '\n'.join(translated)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(output)

remaining = sum(1 for l in output.split('\n') if has_chinese(l) and not l.strip().startswith('![') and 'mmbiz' not in l)
print(f"\nOutput: {OUTPUT_FILE} ({output.count(chr(10))} lines, {remaining} CN lines remaining)")
