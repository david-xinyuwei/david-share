"""
Qwen2-VL-7B-Instruct-AWQ (4-bit) Passport OCR Test
Test environment: NVIDIA A100 80GB GPU with vLLM
"""

from vllm import LLM, SamplingParams
from PIL import Image
import torch
import time

def test_passport_ocr_awq(image_path: str, num_runs: int = 3):
    print("=" * 70)
    print("🧪 Qwen2-VL-7B-Instruct-AWQ (4-bit) Passport OCR Test")
    print("=" * 70)
    
    # Load model with vLLM
    print("\n📥 Loading Qwen2-VL-7B-Instruct-AWQ via vLLM...")
    
    llm = LLM(
        model="Qwen/Qwen2-VL-7B-Instruct-AWQ",
        trust_remote_code=True,
        max_model_len=4096,
        limit_mm_per_prompt={"image": 1},
    )
    
    print("✅ Model loaded")
    
    # Load image
    image = Image.open(image_path)
    
    # Prepare prompt (Qwen2-VL format)
    prompt = """<|im_start|>user
<|vision_start|><|image_pad|><|vision_end|>Please extract all text fields from this passport image and return as a structured format:

1. Surname / Nom / Apellido
2. Given Names / Prénom / Nombre  
3. Nationality / Nationalité / Nacionalidad
4. Date of birth / Date de naissance / Fecha de nacimiento
5. Sex / Sexe / Sexo
6. Place of birth / Lieu de naissance / Lugar de nacimiento
7. Date of issue / Date de délivrance / Fecha de expedición
8. Date of expiration / Date d'expiration / Fecha de caducidad
9. Issuing authority / Autorité de délivrance / Autoridad de expedición
10. Passport No. / N° de passeport / N° de pasaporte

Please read the actual printed text in the Visual Inspection Zone (VIZ) of the passport, not from the MRZ code at the bottom.<|im_end|>
<|im_start|>assistant
"""
    
    sampling_params = SamplingParams(temperature=0, max_tokens=512)
    
    # Run inference
    results = []
    for run in range(num_runs):
        start_time = time.time()
        
        outputs = llm.generate(
            [{
                "prompt": prompt,
                "multi_modal_data": {"image": image},
            }],
            sampling_params=sampling_params,
        )
        
        inference_time = time.time() - start_time
        output_text = outputs[0].outputs[0].text
        results.append((output_text, inference_time))
        print(f"\n🔄 Run {run+1}/{num_runs} ({inference_time:.2f}s)")
    
    # Results
    print("\n" + "=" * 70)
    print("📋 Qwen2-VL-7B-Instruct-AWQ Output:")
    print("=" * 70)
    print(results[0][0])
    
    # Statistics
    gpu_mem = torch.cuda.max_memory_allocated() / 1024**3
    avg_time = sum(r[1] for r in results) / len(results)
    consistent = all(r[0] == results[0][0] for r in results)
    
    print("\n" + "=" * 70)
    print("📊 Statistics:")
    print("=" * 70)
    print(f"⏱️  Average inference time: {avg_time:.2f}s")
    print(f"💾 Peak VRAM: {gpu_mem:.2f} GB (model ~6.5GB)")
    print(f"🔁 Consistency ({num_runs} runs): {'✅ Consistent' if consistent else '❌ Inconsistent'}")
    print("=" * 70)
    
    return results

if __name__ == "__main__":
    import sys
    image_path = sys.argv[1] if len(sys.argv) > 1 else "images/usa-passport.jpg"
    test_passport_ocr_awq(image_path)
