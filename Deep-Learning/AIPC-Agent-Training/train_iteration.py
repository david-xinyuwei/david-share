#!/usr/bin/env python3
"""
完整迭代训练脚本
================
一次迭代包含两个阶段：
1. DPO 训练：学习边界（从用户反馈中学什么是错的）
2. GRPO 训练：优化质量（实时采样 + 实时打分）

用法:
    python train_iteration.py \
        --base-model output/v1_model \
        --dpo-data data/dpo_v2.jsonl \
        --grpo-prompts data/grpo_prompts_v2.jsonl \
        --output output/v2_model
"""

import os
import json
import argparse
import subprocess
import sys
from datetime import datetime


def run_command(cmd: list, description: str) -> bool:
    """运行命令并返回是否成功"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print("=" * 60)
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"❌ {description} 失败")
        return False
    
    print(f"✅ {description} 完成")
    return True


def main():
    parser = argparse.ArgumentParser(description="完整迭代训练 (DPO + GRPO)")
    parser.add_argument("--base-model", required=True, help="基座模型路径")
    parser.add_argument("--dpo-data", required=True, help="DPO 数据文件")
    parser.add_argument("--grpo-prompts", required=True, help="GRPO prompts 文件")
    parser.add_argument("--output", required=True, help="最终输出模型路径")
    parser.add_argument("--dpo-epochs", type=int, default=3, help="DPO 训练轮数")
    parser.add_argument("--grpo-epochs", type=int, default=1, help="GRPO 训练轮数")
    parser.add_argument("--skip-dpo", action="store_true", help="跳过 DPO 阶段")
    parser.add_argument("--skip-grpo", action="store_true", help="跳过 GRPO 阶段")
    args = parser.parse_args()
    
    # 检查环境变量
    if not os.getenv("AZURE_OPENAI_ENDPOINT") or not os.getenv("AZURE_OPENAI_KEY"):
        print("❌ 请设置 AZURE_OPENAI_ENDPOINT 和 AZURE_OPENAI_KEY 环境变量")
        return
    
    print("=" * 60)
    print("完整迭代训练 (DPO + GRPO)")
    print("=" * 60)
    print(f"基座模型: {args.base_model}")
    print(f"DPO 数据: {args.dpo_data}")
    print(f"GRPO Prompts: {args.grpo_prompts}")
    print(f"输出模型: {args.output}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 中间模型路径
    dpo_output = f"{args.output}_dpo_temp"
    
    # ============ Stage 1: DPO 训练 ============
    if not args.skip_dpo:
        # 检查 DPO 数据
        if not os.path.exists(args.dpo_data):
            print(f"❌ DPO 数据文件不存在: {args.dpo_data}")
            return
        
        with open(args.dpo_data, "r") as f:
            dpo_count = sum(1 for _ in f)
        print(f"\nDPO 数据量: {dpo_count} 条")
        
        if dpo_count == 0:
            print("⚠️ DPO 数据为空，跳过 DPO 阶段")
            dpo_output = args.base_model
        else:
            dpo_cmd = [
                sys.executable, "train_dpo.py",
                "--base-model", args.base_model,
                "--data", args.dpo_data,
                "--output", dpo_output,
                "--epochs", str(args.dpo_epochs)
            ]
            
            if not run_command(dpo_cmd, "Stage 1: DPO 训练"):
                return
    else:
        print("\n⏭️ 跳过 DPO 阶段")
        dpo_output = args.base_model
    
    # ============ Stage 2: GRPO 训练 ============
    if not args.skip_grpo:
        # 检查 GRPO prompts
        if not os.path.exists(args.grpo_prompts):
            print(f"❌ GRPO prompts 文件不存在: {args.grpo_prompts}")
            return
        
        with open(args.grpo_prompts, "r") as f:
            grpo_count = sum(1 for _ in f)
        print(f"\nGRPO prompts 数量: {grpo_count} 条")
        
        grpo_cmd = [
            sys.executable, "train_grpo.py",
            "--base-model", dpo_output,
            "--prompts", args.grpo_prompts,
            "--output", args.output,
            "--epochs", str(args.grpo_epochs)
        ]
        
        if not run_command(grpo_cmd, "Stage 2: GRPO 训练 (实时采样)"):
            return
    else:
        print("\n⏭️ 跳过 GRPO 阶段")
        # 如果跳过 GRPO，直接复制 DPO 输出
        if dpo_output != args.output:
            import shutil
            if os.path.exists(args.output):
                shutil.rmtree(args.output)
            shutil.copytree(dpo_output, args.output)
    
    # ============ 清理临时文件 ============
    if not args.skip_dpo and not args.skip_grpo and dpo_output != args.base_model:
        import shutil
        if os.path.exists(dpo_output):
            print(f"\n清理临时目录: {dpo_output}")
            shutil.rmtree(dpo_output)
    
    # ============ 完成 ============
    print("\n" + "=" * 60)
    print("✅ 迭代训练完成！")
    print("=" * 60)
    print(f"最终模型: {args.output}")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 下一步提示
    print("\n📋 下一步:")
    print("1. 部署模型到 vLLM 服务")
    print("2. 收集用户反馈")
    print("3. 运行 generate_feedback_data.py 生成下一轮训练数据")
    print("4. 运行 prepare_grpo_prompts.py 准备 GRPO prompts")
    print("5. 继续下一轮迭代")


if __name__ == "__main__":
    main()
