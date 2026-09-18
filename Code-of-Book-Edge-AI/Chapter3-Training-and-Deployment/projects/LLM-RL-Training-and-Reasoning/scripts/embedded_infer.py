#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Inference script for embedded C++ code generation model
"""

import torch
import argparse
import re
from transformers import AutoTokenizer, AutoModelForCausalLM

# Constants
CODE_START = "<code>"
CODE_END = "</code>"
THINK_START = "<think>"
THINK_END = "</think>"

SYSTEM_PROMPT = f"""You are an expert embedded C/C++ programmer specializing in STM32, FreeRTOS, and hardware drivers.
When given a coding task:
1. First think about the solution between {THINK_START} and {THINK_END}
2. Then provide the complete code between {CODE_START} and {CODE_END}

Your code should:
- Follow embedded best practices (no dynamic allocation, handle hardware registers properly)
- Include necessary headers
- Be compilable with arm-none-eabi-gcc"""


def chat_template(messages):
    """Apply chat template"""
    out = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        out.append(f"<|{role}|>{content}<|end|>")
    out.append(f"<|assistant|>{THINK_START}")
    return "".join(out)


def extract_code(text):
    """Extract code from generated text"""
    match = re.search(r'<code>\s*(.*?)\s*</code>', text, re.DOTALL)
    if match:
        return match.group(1)
    
    match = re.search(r'```(?:c|cpp|c\+\+)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    return text


def main():
    parser = argparse.ArgumentParser(description="Embedded Code Generator Inference")
    parser.add_argument("--model_dir", default="outputs_embedded/embedded_coder_final",
                        help="Path to the trained model")
    parser.add_argument("--task", required=True, help="Coding task description")
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()
    
    print(f"Loading model from: {args.model_dir}")
    
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    
    # Build prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Write embedded C code to: {args.task}"}
    ]
    
    prompt = chat_template(messages)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    print(f"\nGenerating code for: {args.task}")
    print("-" * 60)
    
    # Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=args.max_tokens,
            temperature=args.temperature if args.temperature > 0 else None,
            do_sample=args.temperature > 0,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = response.split("<|assistant|>")[-1]
    
    print("\n=== Generated Response ===")
    print(response)
    
    print("\n=== Extracted Code ===")
    code = extract_code(response)
    print(code)
    
    # Optional: syntax check with STM32 stub headers
    try:
        import subprocess
        import tempfile
        import os
        
        # Import stub headers from training script
        try:
            from embedded_grpo_train import STM32_STUB_HEADERS
        except ImportError:
            STM32_STUB_HEADERS = ""
        
        # Create stub header file
        stub_path = None
        if STM32_STUB_HEADERS:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False) as stub_f:
                stub_f.write(STM32_STUB_HEADERS)
                stub_path = stub_f.name
        
        # Create code file with stub include
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            if stub_path:
                # Always prepend stub header (even if code doesn't have #include)
                f.write(f'#include "{stub_path}"\n\n')
                # Also replace any existing STM32 headers
                modified_code = code.replace('#include "stm32f4xx_hal.h"', '// (using stub header)')
                modified_code = modified_code.replace('#include <stm32f4xx_hal.h>', '// (using stub header)')
                modified_code = modified_code.replace('#include "FreeRTOS.h"', '// (using stub header)')
                modified_code = modified_code.replace('#include "task.h"', '// (using stub header)')
                f.write(modified_code)
            else:
                f.write(code)
            code_path = f.name
        
        result = subprocess.run(
            ['clang', '-fsyntax-only', '-x', 'c', '-Wno-implicit-function-declaration', code_path],
            capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0:
            print("\n✅ Syntax check: PASSED")
        else:
            print(f"\n❌ Syntax check: FAILED\n{result.stderr}")
        
        # Cleanup
        os.unlink(code_path)
        if stub_path and os.path.exists(stub_path):
            os.unlink(stub_path)
    except Exception as e:
        print(f"\n⚠️ Could not run syntax check: {e}")


if __name__ == "__main__":
    main()
