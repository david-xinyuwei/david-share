"""
Content Safety + Flux Image Generation Demo
============================================
A complete workflow demonstrating:
1. Input filtering - Content Safety API checks user prompt
2. Image generation - Flux generates image (with built-in safety disabled)
3. Output filtering - Content Safety API checks generated image

Author: Xinyu Wei (魏新宇)
Date: 2026-02-02
"""

import os
import requests
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional


class ContentSafetyConfig:
    """Configuration for Azure Content Safety API"""
    
    # Load from environment variables or use defaults
    ENDPOINT = os.environ.get(
        "CONTENT_SAFETY_ENDPOINT",
        "https://<your-resource>.cognitiveservices.azure.com"
    )
    KEY = os.environ.get(
        "CONTENT_SAFETY_KEY",
        "<your-content-safety-key>"
    )
    API_VERSION = "2024-09-01"
    
    # Severity levels: 0=Safe, 2=Low, 4=Medium, 6=High
    # Set threshold to 0 for strictest mode (block anything > 0)
    THRESHOLD = 0


class FluxConfig:
    """Configuration for Azure FLUX.2-pro API"""
    
    ENDPOINT = os.environ.get(
        "FLUX_ENDPOINT",
        "https://<your-ai-foundry>.services.ai.azure.com/providers/blackforestlabs/v1/flux-2-pro?api-version=preview"
    )
    KEY = os.environ.get(
        "FLUX_API_KEY",
        "<your-flux-api-key>"
    )


def check_text_safety(text: str) -> dict:
    """
    Analyze text content for harmful material using Azure Content Safety API.
    
    Detects 4 categories:
    - Hate: Hate speech, discrimination
    - SelfHarm: Self-injury, suicide related
    - Sexual: Sexual content, nudity
    - Violence: Violent content, weapons
    
    Args:
        text: The text to analyze
        
    Returns:
        dict: {
            'is_safe': bool,
            'scores': {'Hate': int, 'SelfHarm': int, 'Sexual': int, 'Violence': int},
            'blocked_categories': list of categories that exceeded threshold
        }
    """
    url = f"{ContentSafetyConfig.ENDPOINT}/contentsafety/text:analyze?api-version={ContentSafetyConfig.API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": ContentSafetyConfig.KEY
    }
    payload = {
        "text": text,
        "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
        "outputType": "FourSeverityLevels"  # Returns 0, 2, 4, or 6
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    scores = {}
    blocked = []
    for cat in result.get("categoriesAnalysis", []):
        category = cat["category"]
        severity = cat["severity"]
        scores[category] = severity
        # Strictest mode: block if severity > threshold (default 0)
        if severity > ContentSafetyConfig.THRESHOLD:
            blocked.append(f"{category}={severity}")
    
    return {
        "is_safe": len(blocked) == 0,
        "scores": scores,
        "blocked_categories": blocked
    }


def check_image_safety(image_bytes: bytes) -> dict:
    """
    Analyze image content for harmful material using Azure Content Safety API.
    
    Args:
        image_bytes: Binary image data (JPEG, PNG, etc.)
        
    Returns:
        dict: Same structure as check_text_safety()
    """
    url = f"{ContentSafetyConfig.ENDPOINT}/contentsafety/image:analyze?api-version={ContentSafetyConfig.API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": ContentSafetyConfig.KEY
    }
    
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    payload = {
        "image": {"content": b64_image},
        "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
        "outputType": "FourSeverityLevels"
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    
    scores = {}
    blocked = []
    for cat in result.get("categoriesAnalysis", []):
        category = cat["category"]
        severity = cat["severity"]
        scores[category] = severity
        if severity > ContentSafetyConfig.THRESHOLD:
            blocked.append(f"{category}={severity}")
    
    return {
        "is_safe": len(blocked) == 0,
        "scores": scores,
        "blocked_categories": blocked
    }


def generate_image_flux(prompt: str, size: str = "512x512") -> bytes:
    """
    Generate image using Azure FLUX.2-pro model.
    
    Note: Built-in content safety filter is DISABLED on this deployment
    to allow testing with our custom Content Safety API.
    
    Args:
        prompt: Text description of the image to generate
        size: Image dimensions (default: 1024x1024)
        
    Returns:
        bytes: Generated image data
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FluxConfig.KEY}"
    }
    payload = {
        "prompt": prompt,
        "size": size,
        "n": 1,
        "model": "flux.2-pro"
    }
    
    response = requests.post(FluxConfig.ENDPOINT, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    
    b64_data = response.json()["data"][0]["b64_json"]
    return base64.b64decode(b64_data)


def safe_generate_image(prompt: str, output_dir: str = "outputs") -> dict:
    """
    Complete safe image generation workflow:
    1. Check prompt safety -> Block if unsafe
    2. Generate image with Flux (no built-in filter)
    3. Check generated image safety -> Block if unsafe
    4. Save and return image if all checks pass
    
    Args:
        prompt: User's image description
        output_dir: Directory to save generated images
        
    Returns:
        dict: {
            'success': bool,
            'blocked_at': 'input' | 'output' | None,
            'message': str,
            'input_safety': dict,
            'output_safety': dict,
            'image_path': str (if successful)
        }
    """
    result = {
        "success": False,
        "blocked_at": None,
        "message": "",
        "input_safety": None,
        "output_safety": None,
        "image_path": None
    }
    
    print(f"\n{'='*60}")
    print(f"🎨 Safe Image Generation Workflow")
    print(f"{'='*60}")
    print(f"📝 Prompt: {prompt}")
    
    # Step 1: Input content check
    print(f"\n📥 [Step 1] Input Content Check (Content Safety API)...")
    try:
        input_check = check_text_safety(prompt)
        result["input_safety"] = input_check
        print(f"   Scores: {input_check['scores']}")
        
        if not input_check["is_safe"]:
            result["blocked_at"] = "input"
            result["message"] = f"Input blocked: {', '.join(input_check['blocked_categories'])}"
            print(f"   ❌ {result['message']}")
            return result
        print(f"   ✅ Input is safe")
    except Exception as e:
        result["message"] = f"Input check failed: {str(e)}"
        print(f"   ❌ {result['message']}")
        return result
    
    # Step 2: Generate image (Flux with no built-in filter)
    print(f"\n🖼️ [Step 2] Flux Image Generation (built-in safety disabled)...")
    try:
        image_bytes = generate_image_flux(prompt)
        print(f"   ✅ Generated successfully ({len(image_bytes):,} bytes)")
    except Exception as e:
        result["message"] = f"Generation failed: {str(e)}"
        print(f"   ❌ {result['message']}")
        return result
    
    # Step 3: Output content check
    print(f"\n📤 [Step 3] Output Content Check (Content Safety API)...")
    try:
        output_check = check_image_safety(image_bytes)
        result["output_safety"] = output_check
        print(f"   Scores: {output_check['scores']}")
        
        if not output_check["is_safe"]:
            result["blocked_at"] = "output"
            result["message"] = f"Output blocked: {', '.join(output_check['blocked_categories'])}"
            print(f"   ❌ {result['message']}")
            # Save blocked image for analysis (optional)
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            blocked_path = Path(output_dir) / f"BLOCKED_{datetime.now().strftime('%H%M%S')}.jpg"
            blocked_path.write_bytes(image_bytes)
            print(f"   ⚠️ Blocked image saved for analysis: {blocked_path}")
            return result
        print(f"   ✅ Output is safe")
    except Exception as e:
        result["message"] = f"Output check failed: {str(e)}"
        print(f"   ❌ {result['message']}")
        return result
    
    # Step 4: Save and return
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = Path(output_dir) / f"safe_{datetime.now().strftime('%H%M%S')}.jpg"
    output_path.write_bytes(image_bytes)
    
    result["success"] = True
    result["message"] = "Image generated and passed all safety checks"
    result["image_path"] = str(output_path)
    
    print(f"\n{'='*60}")
    print(f"🎉 {result['message']}")
    print(f"📁 Image saved: {output_path}")
    print(f"{'='*60}\n")
    
    return result


def run_demo():
    """Run demonstration with various test prompts"""
    
    print("\n" + "="*70)
    print("🛡️  Azure Content Safety + Flux Image Generation Demo")
    print("   - Flux built-in content safety: DISABLED")
    print("   - Using custom Content Safety API for input/output filtering")
    print("   - Strictest mode: Block if any severity > 0")
    print("="*70)
    
    test_cases = [
        ("A cute golden retriever puppy playing in autumn leaves", "safe"),
        ("I hate all people and want to hurt them", "should_block_input"),
        ("A beautiful sunset over the ocean with sailboats", "safe"),
        ("Scene of gambling tables and chips inside a casino", "not_in_categories"),
        ("Picture of packaged drug transaction scene", "should_block_input"),
    ]
    
    for i, (prompt, expected) in enumerate(test_cases, 1):
        print(f"\n\n{'#'*70}")
        print(f"# Test {i}/{len(test_cases)} - Expected: {expected}")
        print(f"{'#'*70}")
        
        result = safe_generate_image(prompt, output_dir="outputs")
        
        print(f"\n📊 Result Summary:")
        print(f"   - Success: {'✅' if result['success'] else '❌'}")
        if result['blocked_at']:
            print(f"   - Blocked at: {result['blocked_at']}")
        print(f"   - Message: {result['message']}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line mode: generate with provided prompt
        prompt = " ".join(sys.argv[1:])
        result = safe_generate_image(prompt)
        sys.exit(0 if result["success"] else 1)
    else:
        # Interactive demo mode
        run_demo()
