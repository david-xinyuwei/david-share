#!/usr/bin/env python3
"""
GRPO Prompts 准备脚本
=====================
合并旧错题 + 新注入问题，保持总量恒定

策略：
- 旧错题优先（模型还没学会的）
- 新问题补足（保持数量恒定，持续进化）
- 可选：按错误严重程度排序

用法:
    python prepare_grpo_prompts.py \
        --old-errors data/v2_errors.jsonl \
        --new-questions data/new_questions.jsonl \
        --output data/grpo_prompts_v3.jsonl \
        --target-count 100
"""

import os
import json
import argparse
import random
from datetime import datetime


def load_jsonl(filepath: str) -> list:
    """加载 JSONL 文件"""
    if not os.path.exists(filepath):
        return []
    
    items = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line.strip()))
    return items


def save_jsonl(items: list, filepath: str):
    """保存 JSONL 文件"""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="准备 GRPO prompts")
    parser.add_argument("--old-errors", help="旧错题文件 (上一版本的错误)")
    parser.add_argument("--old-grpo", help="上一轮的 GRPO prompts（可选，用于筛选仍是错误的）")
    parser.add_argument("--new-questions", help="新问题文件")
    parser.add_argument("--output", required=True, help="输出文件")
    parser.add_argument("--target-count", type=int, default=100, help="目标问题数量")
    parser.add_argument("--error-priority", type=float, default=0.7,
                        help="错题优先比例 (0-1)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("GRPO Prompts 准备")
    print("=" * 60)
    
    # 加载旧错题
    old_errors = []
    if args.old_errors and os.path.exists(args.old_errors):
        old_errors = load_jsonl(args.old_errors)
        print(f"加载旧错题: {len(old_errors)} 条")
    
    # 如果有上一轮 GRPO prompts，筛选出仍是错误的
    if args.old_grpo and os.path.exists(args.old_grpo):
        old_grpo = load_jsonl(args.old_grpo)
        still_errors = [p for p in old_grpo if p.get("is_error", False)]
        print(f"上轮仍错误: {len(still_errors)} 条")
        # 合并，去重
        error_prompts = set()
        for item in old_errors + still_errors:
            prompt = item.get("prompt", item.get("question", ""))
            if prompt:
                error_prompts.add(prompt)
        old_errors = [{"prompt": p, "source": "error"} for p in error_prompts]
        print(f"合并后错题: {len(old_errors)} 条")
    
    # 加载新问题
    new_questions = []
    if args.new_questions and os.path.exists(args.new_questions):
        new_questions = load_jsonl(args.new_questions)
        print(f"加载新问题: {len(new_questions)} 条")
    
    # 计算分配
    error_count = min(len(old_errors), int(args.target_count * args.error_priority))
    new_count = args.target_count - error_count
    
    # 如果新问题不够，用更多错题
    if new_count > len(new_questions):
        new_count = len(new_questions)
        error_count = min(len(old_errors), args.target_count - new_count)
    
    print()
    print(f"目标数量: {args.target_count}")
    print(f"错题分配: {error_count}")
    print(f"新题分配: {new_count}")
    
    # 选择错题（按严重程度排序，分数低的优先）
    if old_errors:
        # 按 last_score 或 score_rejected 排序
        old_errors_sorted = sorted(
            old_errors,
            key=lambda x: x.get("last_score", x.get("score_rejected", 5))
        )
        selected_errors = old_errors_sorted[:error_count]
    else:
        selected_errors = []
    
    # 选择新问题（随机采样）
    if new_questions and new_count > 0:
        if len(new_questions) > new_count:
            selected_new = random.sample(new_questions, new_count)
        else:
            selected_new = new_questions
    else:
        selected_new = []
    
    # 合并并构造输出
    output_prompts = []
    
    for item in selected_errors:
        prompt = item.get("prompt", item.get("question", ""))
        output_prompts.append({
            "prompt": prompt,
            "source": "error",
            "priority": "high"
        })
    
    for item in selected_new:
        prompt = item.get("prompt", item.get("question", ""))
        output_prompts.append({
            "prompt": prompt,
            "source": "new",
            "priority": "normal"
        })
    
    # 打乱顺序
    random.shuffle(output_prompts)
    
    # 保存
    save_jsonl(output_prompts, args.output)
    
    # 统计
    print()
    print("=" * 60)
    print("输出统计")
    print("=" * 60)
    print(f"总计: {len(output_prompts)} 条")
    print(f"  - 错题: {len(selected_errors)}")
    print(f"  - 新题: {len(selected_new)}")
    print(f"输出: {args.output}")
    
    # 如果数量不足，给出警告
    if len(output_prompts) < args.target_count:
        print()
        print(f"⚠️ 警告: 实际数量 ({len(output_prompts)}) 少于目标 ({args.target_count})")
        print("   考虑添加更多新问题或降低目标数量")


if __name__ == "__main__":
    main()
