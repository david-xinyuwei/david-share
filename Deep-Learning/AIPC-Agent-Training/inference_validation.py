"""
inference_validation.py - 验证训练后模型效果

使用 vLLM 加载训练后的模型，对比训练前后的回答质量。

使用方法：
    python inference_validation.py --model ./aipc_agent_output/final_model
"""

import os
import argparse
from typing import List, Dict

# 测试问题集
TEST_QUESTIONS = [
    # 基础功能
    "AIPC 的 NPU 和 GPU 有什么区别？",
    "如何检查我的电脑是否支持 AIPC 功能？",
    "AIPC 上可以运行哪些 AI 应用？",
    
    # 使用指南
    "如何启用 AIPC 的本地大模型功能？",
    "怎么让 Copilot 使用本地 NPU 而不是云端？",
    "AIPC 的 AI 功能需要联网吗？",
    
    # 故障排除
    "AIPC 运行 AI 应用时风扇声音很大，怎么解决？",
    "为什么 NPU 显示不可用？",
    "AI 应用运行很慢，如何优化？",
    
    # 进阶问题
    "AIPC 上如何部署自己的 AI 模型？",
    "NPU 支持哪些 AI 框架？",
    "如何监控 NPU 的使用率？"
]


def validate_with_vllm(model_path: str, questions: List[str]) -> List[Dict]:
    """使用 vLLM 进行推理验证"""
    
    try:
        from vllm import LLM, SamplingParams
    except ImportError:
        print("请安装 vLLM: pip install vllm")
        return []
    
    print(f"加载模型: {model_path}")
    llm = LLM(model=model_path, trust_remote_code=True)
    
    sampling_params = SamplingParams(
        temperature=0.7,
        max_tokens=512,
        top_p=0.9
    )
    
    results = []
    
    print(f"\n开始推理 {len(questions)} 个问题...")
    outputs = llm.generate(questions, sampling_params)
    
    for question, output in zip(questions, outputs):
        answer = output.outputs[0].text.strip()
        results.append({
            "question": question,
            "answer": answer
        })
    
    return results


def validate_with_transformers(model_path: str, questions: List[str]) -> List[Dict]:
    """使用 transformers 进行推理验证（备选方案）"""
    
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        print("请安装 transformers: pip install transformers")
        return []
    
    print(f"加载模型: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    
    results = []
    
    for i, question in enumerate(questions):
        print(f"[{i+1}/{len(questions)}] {question[:30]}...")
        
        messages = [{"role": "user", "content": question}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9,
                do_sample=True
            )
        
        answer = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        
        results.append({
            "question": question,
            "answer": answer.strip()
        })
    
    return results


def compare_models(base_model: str, trained_model: str, questions: List[str]):
    """对比基座模型和训练后模型"""
    
    print("=" * 60)
    print("模型效果对比")
    print("=" * 60)
    
    print("\n>>> 加载基座模型...")
    base_results = validate_with_vllm(base_model, questions)
    
    print("\n>>> 加载训练后模型...")
    trained_results = validate_with_vllm(trained_model, questions)
    
    # 输出对比结果
    print("\n" + "=" * 60)
    print("对比结果")
    print("=" * 60)
    
    for i, (base, trained) in enumerate(zip(base_results, trained_results)):
        print(f"\n{'='*60}")
        print(f"问题 {i+1}: {base['question']}")
        print(f"{'='*60}")
        print(f"\n【基座模型】:")
        print(base['answer'][:500])
        print(f"\n【训练后模型】:")
        print(trained['answer'][:500])


def main(args):
    """主流程"""
    
    questions = TEST_QUESTIONS[:args.num_questions]
    
    if args.compare:
        # 对比模式
        compare_models(args.base_model, args.model, questions)
    else:
        # 单模型验证
        print(f"验证模型: {args.model}")
        
        if args.use_transformers:
            results = validate_with_transformers(args.model, questions)
        else:
            results = validate_with_vllm(args.model, questions)
        
        # 输出结果
        print("\n" + "=" * 60)
        print("验证结果")
        print("=" * 60)
        
        for i, result in enumerate(results):
            print(f"\n【问题 {i+1}】: {result['question']}")
            print(f"【回答】: {result['answer']}")
            print("-" * 40)
        
        # 保存结果
        if args.output:
            import json
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存至: {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="验证 AIPC 智能体训练效果")
    
    parser.add_argument("--model", required=True, help="训练后的模型路径")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-3B-Instruct", help="基座模型")
    parser.add_argument("--output", help="结果输出文件路径")
    parser.add_argument("--num-questions", type=int, default=5, help="测试问题数量")
    parser.add_argument("--compare", action="store_true", help="对比基座模型和训练后模型")
    parser.add_argument("--use-transformers", action="store_true", help="使用 transformers 而非 vLLM")
    
    args = parser.parse_args()
    main(args)
