#!/usr/bin/env python3
"""Precise binary search for Agent Service body size threshold."""
import json, base64, os, sys
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from PIL import Image

key = os.environ['FOUNDRY_KEY']
base = os.environ.get('AGENT_SVC_BASE', 'https://YOUR_RESOURCE.services.ai.azure.com/api/projects/YOUR_PROJECT')
url = f'{base}/openai/v1/responses'

# Generate source image for b64 data (needs to be large enough)
w, h, q = 800, 600, 90
img = Image.new('RGB', (w, h))
px = img.load()
for y in range(h):
    for x in range(w):
        px[x, y] = ((x*7+y*3) % 256, (x*3+y*7+128) % 256, (x*5+y*5+64) % 256)
buf = BytesIO()
img.save(buf, format='JPEG', quality=q)
full_b64 = base64.b64encode(buf.getvalue()).decode()
print(f"Source image b64 length: {len(full_b64)} chars")

# Measure JSON overhead
tmpl = json.dumps({
    'model': 'gpt-4o-mini',
    'input': [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': 'Describe'},
        {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,PLACEHOLDER', 'detail': 'low'}
    ]}],
    'max_output_tokens': 50
}).encode()
overhead = len(tmpl) - len('PLACEHOLDER')
print(f"JSON overhead: {overhead} bytes\n")

def test_body_size(target_body):
    b64_len = target_body - overhead
    if b64_len <= 0 or b64_len > len(full_b64):
        return None
    b64_sub = full_b64[:b64_len - (b64_len % 4)]  # align to 4

    payload = {
        'model': 'gpt-4o-mini',
        'input': [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': 'Describe'},
            {'type': 'input_image', 'image_url': f'data:image/jpeg;base64,{b64_sub}', 'detail': 'low'}
        ]}],
        'max_output_tokens': 50
    }
    body = json.dumps(payload).encode()
    actual = len(body)

    req = Request(url, data=body, headers={
        'Content-Type': 'application/json',
        'api-key': key
    }, method='POST')
    try:
        with urlopen(req, timeout=60) as r:
            return (actual, True)
    except HTTPError as e:
        e.read()
        return (actual, False)
    except Exception:
        return (actual, None)

# Phase 1: coarse scan
print("Phase 1: Coarse scan (1KB steps from 50KB to 70KB)")
print(f"{'Target':>8} {'Actual':>8} Status")
print("-" * 30)

last_ok = 0
first_fail = 999999

for kb in range(50, 71):
    target = kb * 1024
    result = test_body_size(target)
    if result is None:
        continue
    actual, ok = result
    status = "OK" if ok else "FAIL"
    print(f"{target:>7}B {actual:>7}B {status}")
    if ok:
        last_ok = max(last_ok, actual)
    elif not ok:
        first_fail = min(first_fail, actual)

print(f"\nCoarse: last OK={last_ok}B, first FAIL={first_fail}B")
print(f"        last OK={last_ok/1024:.1f}KB, first FAIL={first_fail/1024:.1f}KB")

# Phase 2: fine binary search between last_ok and first_fail
if last_ok > 0 and first_fail < 999999:
    print(f"\nPhase 2: Fine binary search between {last_ok}B and {first_fail}B")
    lo, hi = last_ok, first_fail
    for _ in range(15):
        if hi - lo <= 100:
            break
        mid = (lo + hi) // 2
        result = test_body_size(mid)
        if result is None:
            break
        actual, ok = result
        if ok:
            lo = actual
            print(f"  {actual:>7}B ({actual/1024:.1f}KB) OK")
        else:
            hi = actual
            print(f"  {actual:>7}B ({actual/1024:.1f}KB) FAIL")

    print(f"\nFINAL THRESHOLD: between {lo}B and {hi}B")
    print(f"                 between {lo/1024:.1f}KB and {hi/1024:.1f}KB")
    print(f"                 64KB = {64*1024}B = 65536B")
    print(f"                 lo < 65536 < hi? {lo < 65536 < hi}")
