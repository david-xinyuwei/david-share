"""
Test MAI-Image-2 API via Azure OpenAI Image Generation endpoint
Author: Xinyu Wei (魏新宇)

MAI-Image-2 uses the standard Azure OpenAI images/generations API:
POST https://{resource}.openai.azure.com/openai/deployments/{deployment}/images/generations?api-version=2024-10-21
"""
import os
import sys
import json
import base64
import time
import requests
from pathlib import Path
from urllib.parse import urlencode

# Configuration
API_KEY = os.environ.get("MAI_API_KEY", "<your-api-key>")
RESOURCE_NAME = "<your-resource-name>"
DEPLOYMENT_NAME = "mai-image-2"
API_VERSION = "2025-04-01-preview"

# MAI-Image-2 uses cognitiveservices endpoint with preview API version
# (openai.azure.com + GA api-version returns "unknown_model")
BASE_URL = f"https://{RESOURCE_NAME}.cognitiveservices.azure.com"
API_PATH = f"/openai/deployments/{DEPLOYMENT_NAME}/images/generations"

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_image(prompt, size="1024x1024", quality="hd", style="natural",
                   response_format="b64_json", filename="test.png"):
    """Call MAI-Image-2 via Azure OpenAI images/generations API."""
    url = f"{BASE_URL}{API_PATH}?api-version={API_VERSION}"
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
        "style": style,
        "response_format": response_format,
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }

    print(f"\n{'='*60}")
    print(f"Prompt: {prompt[:100]}{'...' if len(prompt)>100 else ''}")
    print(f"Size: {size} | Quality: {quality} | Style: {style}")

    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        elapsed = time.time() - start

        print(f"Status: {response.status_code} ({elapsed:.1f}s)")

        if response.status_code == 200:
            result = response.json()
            data_list = result.get("data", [])
            if data_list and "b64_json" in data_list[0]:
                img_bytes = base64.b64decode(data_list[0]["b64_json"])
                out_path = OUTPUT_DIR / filename
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                revised = data_list[0].get("revised_prompt", "")
                print(f"SUCCESS! Saved: {out_path} ({len(img_bytes)/1024:.0f} KB)")
                if revised:
                    print(f"Revised prompt: {revised[:120]}...")
                return True, elapsed
            elif data_list and "url" in data_list[0]:
                img_url = data_list[0]["url"]
                print(f"Image URL returned (downloading...)")
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200:
                    out_path = OUTPUT_DIR / filename
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    print(f"SUCCESS! Saved: {out_path} ({len(img_resp.content)/1024:.0f} KB)")
                    return True, elapsed
            else:
                print(f"Response: {json.dumps(result, indent=2)[:500]}")
        elif response.status_code == 429:
            retry_after = response.headers.get("retry-after", "unknown")
            print(f"Rate limited! Retry-After: {retry_after}s")
            try:
                err = response.json()
                print(f"Detail: {json.dumps(err, indent=2)[:300]}")
            except Exception:
                pass
            return "rate_limited", elapsed
        else:
            try:
                err = response.json()
                print(f"Error: {json.dumps(err, indent=2)[:500]}")
            except Exception:
                print(f"Response: {response.text[:500]}")

    except requests.exceptions.Timeout:
        print("Request timed out (180s)")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    return False, 0


def wait_for_rate_limit(seconds=65):
    """Wait for rate limit to reset (1 RPM = 60s window)."""
    print(f"\n--- Waiting {seconds}s for rate limit reset ---")
    for i in range(seconds, 0, -10):
        print(f"  {i}s remaining...")
        time.sleep(min(10, i))
    print("  Ready!")


def main():
    print("=" * 60)
    print("MAI-Image-2 Super Detective Test")
    print(f"Endpoint: {BASE_URL}")
    print(f"Deployment: {DEPLOYMENT_NAME}")
    print(f"API Version: {API_VERSION}")
    print(f"Rate Limit: 1 RPM (expect waits between calls)")
    print("=" * 60)

    results = []

    # Test 1: Simple test - confirm API works
    print("\n[Test 1] Basic connectivity - simple prompt")
    success, elapsed = generate_image(
        "A bright red apple on a clean white background, studio lighting, product photography",
        size="1024x1024", quality="standard", style="natural",
        filename="01_basic_apple.png"
    )
    results.append(("Basic Connectivity", success, elapsed))

    if success == "rate_limited":
        wait_for_rate_limit(65)
        success, elapsed = generate_image(
            "A bright red apple on a clean white background, studio lighting",
            size="1024x1024", quality="standard", style="natural",
            filename="01_basic_apple.png"
        )
        results[-1] = ("Basic Connectivity", success, elapsed)

    if not success or success == "rate_limited":
        print("\n\n[FATAL] Cannot connect to MAI-Image-2 API. Aborting.")
        print("Debug info:")
        print(f"  URL: {BASE_URL}{API_PATH}?api-version={API_VERSION}")
        print(f"  Key: {API_KEY[:8]}...{API_KEY[-4:]}")
        sys.exit(1)

    # Test 2: Text rendering (MAI-Image-2's key differentiator)
    wait_for_rate_limit(65)
    print("\n[Test 2] Text Rendering - MAI-Image-2's flagship feature")
    success, elapsed = generate_image(
        "A wooden sign with the text 'Welcome to Azure AI' carved into it, rustic style, forest background",
        size="1024x1024", quality="hd", style="natural",
        filename="02_text_rendering.png"
    )
    results.append(("Text Rendering", success, elapsed))

    # Test 3: Photorealism
    wait_for_rate_limit(65)
    print("\n[Test 3] Photorealism")
    success, elapsed = generate_image(
        "A professional portrait photo of a confident woman engineer in a modern tech office, warm lighting, bokeh background, Canon EOS R5",
        size="1024x1024", quality="hd", style="natural",
        filename="03_photorealism.png"
    )
    results.append(("Photorealism", success, elapsed))

    # Test 4: Complex scene
    wait_for_rate_limit(65)
    print("\n[Test 4] Complex Scene")
    success, elapsed = generate_image(
        "A bustling Tokyo street at night, neon signs in Japanese kanji, rain-slicked roads reflecting colorful lights, people with transparent umbrellas, steam rising from a ramen stall",
        size="1792x1024", quality="hd", style="vivid",
        filename="04_complex_scene.png"
    )
    results.append(("Complex Scene (Wide)", success, elapsed))

    # Test 5: Product design
    wait_for_rate_limit(65)
    print("\n[Test 5] Product Design")
    success, elapsed = generate_image(
        "A sleek modern smartphone floating above a marble surface, holographic UI elements around it, soft studio lighting, minimalist product photography",
        size="1024x1792", quality="hd", style="vivid",
        filename="05_product_design.png"
    )
    results.append(("Product Design (Portrait)", success, elapsed))

    # Summary
    print("\n\n" + "=" * 60)
    print("TEST SUMMARY - MAI-Image-2")
    print("=" * 60)
    for name, success, elapsed in results:
        if success is True:
            status = f"PASS ({elapsed:.1f}s)"
        elif success == "rate_limited":
            status = "RATE_LIMITED"
        else:
            status = "FAIL"
        print(f"  [{status}] {name}")

    passed = sum(1 for _, s, _ in results if s is True)
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed")
    print(f"Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
