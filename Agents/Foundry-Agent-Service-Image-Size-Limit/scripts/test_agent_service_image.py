#!/usr/bin/env python3
"""
Agent Service (services.ai) vs AOAI Direct (openai.azure.com) — Large Image Test
Reproduce the issue: base64 images fail on Agent Service project endpoint.

Author: Xinyu Wei
Date: 2026-04-16
"""
import base64, json, os, sys, time
from io import BytesIO
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# --- Endpoints (override via env vars) ---
AGENT_SVC_BASE = os.environ.get("AGENT_SVC_BASE", "https://YOUR_RESOURCE.services.ai.azure.com/api/projects/YOUR_PROJECT")
AOAI_BASE = os.environ.get("AOAI_BASE", "https://<your-resource>.openai.azure.com")
MODEL = os.environ.get("MODEL", "gpt-4o-mini")
PROMPT = "What do you see in this image? Reply in one sentence."

def get_keys():
    foundry_key = os.environ.get("FOUNDRY_KEY", "").strip()
    aoai_key = os.environ.get("AOAI_KEY", "").strip()
    if not foundry_key or not aoai_key:
        print("ERROR: Set FOUNDRY_KEY and AOAI_KEY env vars")
        sys.exit(1)
    return foundry_key, aoai_key

def generate_test_image(target_kb):
    """Generate a JPEG test image of approximately target_kb size."""
    try:
        from PIL import Image
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        from PIL import Image

    if target_kb <= 100:
        w, h, q = 640, 480, 85
    elif target_kb <= 500:
        w, h, q = 1920, 1080, 90
    elif target_kb <= 1000:
        w, h, q = 2560, 1440, 92
    else:
        w, h, q = 4096, 2160, 95

    img = Image.new('RGB', (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x*7+y*3)%256, (x*3+y*7+128)%256, (x*5+y*5+64)%256)

    buf = BytesIO()
    img.save(buf, format='JPEG', quality=q)
    actual = len(buf.getvalue()) / 1024

    for _ in range(10):
        if abs(actual - target_kb) / max(target_kb, 1) < 0.3:
            break
        if actual < target_kb:
            q = min(q + 3, 100)
            w, h = int(w * 1.2), int(h * 1.2)
            img = img.resize((w, h))
        else:
            q = max(q - 5, 10)
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=q)
        actual = len(buf.getvalue()) / 1024

    return buf.getvalue(), actual

def call_responses_api(endpoint_url, api_key, image_bytes, detail="auto"):
    """Call the Responses API and return result dict."""
    b64_str = base64.b64encode(image_bytes).decode('utf-8')
    b64_kb = len(b64_str) / 1024

    payload = {
        "model": MODEL,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{b64_str}",
                    "detail": detail
                }
            ]
        }],
        "max_output_tokens": 50
    }

    body = json.dumps(payload).encode('utf-8')
    body_mb = len(body) / (1024 * 1024)

    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    req = Request(endpoint_url, data=body, headers=headers, method='POST')

    t0 = time.time()
    try:
        with urlopen(req, timeout=120) as resp:
            elapsed = time.time() - t0
            result = json.loads(resp.read().decode('utf-8'))
            out_text = ""
            for out in result.get("output", []):
                for c in out.get("content", []):
                    if c.get("type") == "output_text":
                        out_text = c.get("text", "")[:80]
            return {
                "status": "SUCCESS",
                "http": resp.status,
                "body_mb": round(body_mb, 2),
                "b64_kb": round(b64_kb, 1),
                "elapsed_s": round(elapsed, 1),
                "output": out_text,
                "tokens": result.get("usage", {})
            }
    except HTTPError as e:
        elapsed = time.time() - t0
        err = e.read().decode('utf-8', errors='replace')[:300]
        return {
            "status": "FAIL",
            "http": e.code,
            "body_mb": round(body_mb, 2),
            "b64_kb": round(b64_kb, 1),
            "elapsed_s": round(elapsed, 1),
            "error": err
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "status": "ERROR",
            "body_mb": round(body_mb, 2),
            "b64_kb": round(b64_kb, 1),
            "elapsed_s": round(elapsed, 1),
            "error": str(e)[:300]
        }

def main():
    foundry_key, aoai_key = get_keys()

    agent_svc_url = f"{AGENT_SVC_BASE}/openai/v1/responses"
    aoai_url = f"{AOAI_BASE}/openai/v1/responses"

    print("=" * 90)
    print("Agent Service (services.ai) vs AOAI Direct (openai.azure.com) — Image Size Test")
    print(f"  Agent SVC: {agent_svc_url}")
    print(f"  AOAI:      {aoai_url}")
    print(f"  Model:     {MODEL}")
    print("=" * 90)

    test_sizes = [50, 200, 500, 800, 1200]
    results = []

    # Generate images
    print("\n[1] Generating test images...")
    images = {}
    for kb in test_sizes:
        data, actual = generate_test_image(kb)
        images[kb] = data
        b64 = len(base64.b64encode(data)) / 1024
        print(f"    {kb:>5}KB target -> {actual:>7.1f}KB actual -> {b64:>7.1f}KB base64")

    # Test matrix
    print(f"\n[2] Testing...\n")
    header = f"{'Size':>6} | {'Detail':>6} | {'Endpoint':>12} | {'BodyMB':>7} | {'Status':>8} | {'HTTP':>4} | {'Time':>5} | Result"
    print(header)
    print("-" * 100)

    for kb in test_sizes:
        for detail in ["auto", "low"]:
            for ep_name, url, key in [
                ("AgentSvc", agent_svc_url, foundry_key),
                ("AOAI", aoai_url, aoai_key)
            ]:
                r = call_responses_api(url, key, images[kb], detail)
                r["size_kb"] = kb
                r["detail"] = detail
                r["endpoint"] = ep_name
                results.append(r)

                info = r.get("output", r.get("error", ""))[:50]
                print(f"{kb:>5}KB | {detail:>6} | {ep_name:>12} | {r['body_mb']:>6.2f} | {r['status']:>8} | {r.get('http','?'):>4} | {r['elapsed_s']:>4.1f}s | {info}")

        print()  # blank line between sizes

    # Summary
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)
    agent_pass = sum(1 for r in results if r["endpoint"] == "AgentSvc" and r["status"] == "SUCCESS")
    agent_total = sum(1 for r in results if r["endpoint"] == "AgentSvc")
    aoai_pass = sum(1 for r in results if r["endpoint"] == "AOAI" and r["status"] == "SUCCESS")
    aoai_total = sum(1 for r in results if r["endpoint"] == "AOAI")
    print(f"  Agent Service: {agent_pass}/{agent_total} passed")
    print(f"  AOAI Direct:   {aoai_pass}/{aoai_total} passed")

    # Find threshold
    agent_fails = [r for r in results if r["endpoint"] == "AgentSvc" and r["status"] != "SUCCESS"]
    if agent_fails:
        min_fail = min(r["size_kb"] for r in agent_fails)
        print(f"\n  [FAIL] Agent Service FAILS starting at {min_fail}KB image size")
        print(f"     Fail details: {agent_fails[0].get('error', 'N/A')[:200]}")
    else:
        print(f"\n  [PASS] Agent Service passed ALL sizes (up to {max(test_sizes)}KB)")

    # Save results
    outfile = os.path.join(os.path.dirname(__file__), "..", "20260416-progress", "agent-service-test-results.json")
    with open(outfile, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {outfile}")

if __name__ == "__main__":
    main()
