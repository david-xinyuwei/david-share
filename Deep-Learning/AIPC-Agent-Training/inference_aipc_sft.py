#!/usr/bin/env python3
"""
AIPC SFT Model Inference Test
Test the fine-tuned model on AI PC questions
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def load_model(model_path: str):
    """Load the fine-tuned model"""
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto"
    )
    return model, tokenizer

def generate_response(model, tokenizer, question: str, max_new_tokens: int = 512):
    """Generate response for a question"""
    messages = [
        {"role": "user", "content": question}
    ]
    
    # Apply chat template
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )
    
    response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    return response

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="checkpoints/aipc_sft_v1", help="Model path")
    parser.add_argument("--base_model", default="microsoft/Phi-3-mini-4k-instruct", help="Base model for comparison")
    parser.add_argument("--compare", action="store_true", help="Compare with base model")
    args = parser.parse_args()
    
    # Test questions covering different AI PC topics
    test_questions = [
        "什么是 AI PC？它和普通笔记本电脑有什么区别？",
        "Intel Core Ultra 处理器的 NPU 有什么作用？",
        "在 AI PC 上运行本地大语言模型需要什么配置？",
        "Snapdragon X Elite 和 Intel Core Ultra 哪个更适合 AI 应用？",
        "NPU、GPU、CPU 在 AI 推理任务中各自的优势是什么？",
    ]
    
    # Load fine-tuned model
    print("=" * 60)
    print("🚀 AIPC SFT Model Inference Test")
    print("=" * 60)
    
    model, tokenizer = load_model(args.model)
    
    print(f"\n📊 Testing {len(test_questions)} questions...\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*60}")
        print(f"Question {i}: {question}")
        print("-" * 60)
        
        response = generate_response(model, tokenizer, question)
        print(f"[SFT Model Response]:\n{response}")
        
        if args.compare:
            # Load and test base model
            base_model, base_tokenizer = load_model(args.base_model)
            base_response = generate_response(base_model, base_tokenizer, question)
            print(f"\n[Base Model Response]:\n{base_response}")
            del base_model  # Free memory
            torch.cuda.empty_cache()
    
    print("\n" + "=" * 60)
    print("✅ Inference test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
