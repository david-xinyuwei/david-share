"""
Qwen2-VL-7B-Instruct Passport OCR Test
Test environment: NVIDIA A100 80GB GPU
"""

from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info
from PIL import Image
import torch
import time
import json

def test_passport_ocr(image_path: str, num_runs: int = 3):
    print("=" * 70)
    print("🧪 Qwen2-VL-7B-Instruct Passport OCR Test")
    print("=" * 70)
    
    # Load model
    print("\n📥 Loading Qwen2-VL-7B-Instruct...")
    torch.cuda.reset_peak_memory_stats()
    
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2-VL-7B-Instruct",
        torch_dtype=torch.float16,
        device_map="cuda"
    )
    processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-7B-Instruct")
    
    mem_after_load = torch.cuda.max_memory_allocated() / 1024**3
    print(f"✅ Model loaded, VRAM: {mem_after_load:.2f} GB")
    
    # Prepare prompt
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": """Please extract all text fields from this passport image and return as JSON:

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

Read the actual printed text in the Visual Inspection Zone (VIZ), not from the MRZ code at the bottom."""}
            ]
        }
    ]
    
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt"
    ).to("cuda")
    
    # Run inference
    results = []
    for run in range(num_runs):
        start_time = time.time()
        
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False
            )
        
        generated_ids_trimmed = [
            out_ids[len(in_ids):] 
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = processor.batch_decode(
            generated_ids_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]
        
        inference_time = time.time() - start_time
        results.append((output_text, inference_time))
        print(f"\n🔄 Run {run+1}/{num_runs} ({inference_time:.2f}s)")
    
    # Results
    print("\n" + "=" * 70)
    print("�� Output:")
    print("=" * 70)
    print(results[0][0])
    
    # Statistics
    mem_peak = torch.cuda.max_memory_allocated() / 1024**3
    avg_time = sum(r[1] for r in results) / len(results)
    consistent = all(r[0] == results[0][0] for r in results)
    
    print("\n" + "=" * 70)
    print("�� Statistics:")
    print("=" * 70)
    print(f"⏱️  Average inference time: {avg_time:.2f}s")
    print(f"💾 Peak VRAM: {mem_peak:.2f} GB")
    print(f"🔁 Consistency ({num_runs} runs): {'✅ Consistent' if consistent else '❌ Inconsistent'}")
    print("=" * 70)
    
    return results

if __name__ == "__main__":
    import sys
    image_path = sys.argv[1] if len(sys.argv) > 1 else "images/usa-passport.jpg"
    test_passport_ocr(image_path)
