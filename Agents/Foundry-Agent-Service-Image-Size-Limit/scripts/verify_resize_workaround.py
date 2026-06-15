#!/usr/bin/env python3
"""Verify resize workaround: same image WITHOUT resize = FAIL, WITH resize = OK"""
import json, base64, os, sys
sys.path.insert(0, 'scripts')
from workaround_resize_python import resize_and_encode
from io import BytesIO
from PIL import Image
from urllib.request import Request, urlopen
from urllib.error import HTTPError

key = os.environ['FOUNDRY_KEY']
base = os.environ.get('AGENT_SVC_BASE', 'https://YOUR_RESOURCE.services.ai.azure.com/api/projects/YOUR_PROJECT')
url = f'{base}/openai/v1/responses'

# Generate 500KB test image (simulating phone camera)
w, h = 1600, 1200
img = Image.new('RGB', (w, h))
px = img.load()
for y in range(h):
    for x in range(w):
        px[x, y] = ((x*7+y*3) % 256, (x*3+y*7+128) % 256, (x*5+y*5+64) % 256)
buf = BytesIO()
img.save(buf, format='JPEG', quality=90)
raw = buf.getvalue()
print(f"Original image: {len(raw)/1024:.0f}KB")

# Test 1: WITHOUT resize (expect FAIL)
b64_raw = base64.b64encode(raw).decode()
payload = {
    'model': 'gpt-4o-mini',
    'input': [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': 'Describe this image'},
        {'type': 'input_image', 'image_url': f'data:image/jpeg;base64,{b64_raw}', 'detail': 'auto'}
    ]}],
    'max_output_tokens': 50
}
body = json.dumps(payload).encode()
print(f"\nTest 1 - WITHOUT resize: body={len(body)/1024:.0f}KB")
req = Request(url, data=body, headers={'Content-Type': 'application/json', 'api-key': key}, method='POST')
try:
    with urlopen(req, timeout=60) as r:
        print("  Result: OK (unexpected!)")
except HTTPError as e:
    e.read()
    print(f"  Result: FAIL {e.code} (expected)")

# Test 2: WITH resize (expect OK)
result = resize_and_encode(raw)
print(f"\nTest 2 - WITH resize: {result['originalKB']}KB -> {result['resizedKB']}KB")
payload2 = {
    'model': 'gpt-4o-mini',
    'input': [{'role': 'user', 'content': [
        {'type': 'input_text', 'text': 'Describe this image'},
        {'type': 'input_image', 'image_url': f"data:image/jpeg;base64,{result['base64']}", 'detail': 'auto'}
    ]}],
    'max_output_tokens': 50
}
body2 = json.dumps(payload2).encode()
print(f"  body={len(body2)/1024:.0f}KB")
req2 = Request(url, data=body2, headers={'Content-Type': 'application/json', 'api-key': key}, method='POST')
try:
    with urlopen(req2, timeout=60) as r:
        resp = json.loads(r.read().decode())
        txt = ''
        for o in resp.get('output', []):
            for c in o.get('content', []):
                if c.get('type') == 'output_text':
                    txt = c['text'][:80]
        print(f"  Result: OK - Model response: {txt}")
except HTTPError as e:
    err = e.read().decode(errors='replace')[:200]
    print(f"  Result: FAIL {e.code}: {err}")

print("\nDone.")
