"""
Phi-4-multimodal-instruct Passport OCR Test
Test environment: NVIDIA GPU with 16GB+ VRAM
"""

from transformers import AutoModelForCausalLM, AutoProcessor
from PIL import Image
import torch
import time

def test_passport_ocr_phi4(image_path: str, num_runs: int = 3):
    print("=" * 70)
    print("🧪 Phi-4-multimodal-instruct Passport OCR Test")
    print("=" * 70)
    
    # Load model
    print("\n📥 Loading Phi-4-multimodal-instruct...")
    torch.cuda.reset_peak_memory_stats()
    
    model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Phi-4-multimodal-instruct",
        torch_dtype=torch.float16,
        device_map="cuda",
        trust_remote_code=True,
        _attn_implementation="eager"
    )
    processor = AutoProcessor.from_pretrained(
        "microsoft/Phi-4-multimodal-instruct",
        trust_remote_code=True
    )
    
    mem_after_load = torch.cuda.max_memory_allocated() / 1024**3
    print(f"✅ Model loaded, VRAM: {mem_after_load:.2f} GB")
    
    # Load image
    image = Image.open(image_path)
    
    # Prepare prompt (Phi-4 format)
    prompt = """<|user|>
<|image_1|>
Please extract all text fields from this passport image and return as JSON:

{
  "Passport No.": "",
  "Surname": "",
  "Given Names": "",
  "Nationality": "",
  "Date of birth": "",
  "Sex": "",
  "Place of birth": "",
  "Date of issue": "",
  "Date of expiration": ""
}

Read the actual printed text in the Visual Inspection Zone (VIZ), not from the MRZ code at the bottom.
<|end|>
<|assistant|>
"""
    
    inputs = processor(prompt, images=[image], return_tensors="pt").to("cuda")
    
    # Run inference
    results = []
    for run in range(num_runs):
        start_time = time.time()
        
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False
            )
        
        output_text = processor.decode(output[0], skip_special_tokens=True)
        # Extract assistant response
        if "<|assistant|>" in output_text:
            output_text = output_text.split("<|assistant|>")[-1].strip()
        
        inference_time = time.time() - start_time
        results.append((output_text, inference_time))
        print(f"\n🔄 Run {run+1}/{num_runs} ({inference_time:.2f}s)")
    
    # Results
    print("\n" + "=" * 70)
    print("📋 Output:")
    print("=" * 70)
    print(results[0][0])
    
    # Statistics
    mem_peak = torch.cuda.max_memory_allocated() / 1024**3
    avg_time = sum(r[1] for r in results) / len(results)
    consistent = all(r[0] == results[0][0] for r in results)
    
    print("\n" + "=" * 70)
    print("📊 Statistics:")
    print("=" * 70)
    print(f"⏱️  Average inference time: {avg_time:.2f}s")
    print(f"💾 Peak VRAM: {mem_peak:.2f} GB")
    print(f"🔁 Consistency ({num_runs} runs): {'✅ Consistent' if consistent else '❌ Inconsistent'}")
    print("=" * 70)
    
    return results

if __name__ == "__main__":
    import sys
    image_path = sys.argv[1] if len(sys.argv) > 1 else "images/usa-passport.jpg"
    test_passport_ocr_phi4(image_path)
