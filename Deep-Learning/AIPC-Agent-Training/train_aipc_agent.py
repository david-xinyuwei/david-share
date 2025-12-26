"""
train_aipc_agent.py - AIPC 技术支持智能体 GRPO 训练脚本

核心机制：
1. 训练数据由 GPT-5.2 从私有文档生成
2. 奖励信号由 GPT-5.2 模拟人类点赞/踩

使用方法：
    python train_aipc_agent.py --data aipc_training_data.json --output ./output

环境变量：
    AZURE_OPENAI_API_KEY - Azure OpenAI API 密钥
    AZURE_OPENAI_ENDPOINT - Azure OpenAI 端点
    AZURE_OPENAI_DEPLOYMENT - 部署名称 (默认: gpt-5.2)

硬件要求：
    - GPU: A100 80GB (推荐) 或 A10 24GB (最低)
    - 内存: 64GB+
"""

import os
import json
import argparse
import re
from typing import List, Dict, Any
import torch
from datasets import Dataset
from openai import AzureOpenAI

# Agent Lightning imports
try:
    from agentlightning import GRPOTrainer, GRPOConfig
    from agentlightning.reward import BaseReward
except ImportError:
    print("请安装 agent-lightning: pip install agent-lightning==0.3.0")
    exit(1)


# ============================================================================
# GPT-5.2 模拟人类点赞的 Prompt - 这是训练成功的关键！
# ============================================================================
HUMAN_FEEDBACK_SIMULATOR = """你是一个普通的 AIPC 用户，需要判断客服 AI 的回答是否值得点赞。

你要模拟真实用户的反应：
- 如果回答真的有帮助，解决了问题，你会点赞 👍
- 如果回答没什么用，或者看不懂，你会踩 👎
- 不要当老好人！要有区分度！

评估标准（模拟真实用户心理）：

👍 会点赞 (0.85-1.0):
- 直接解决了我的问题
- 步骤清晰，我能照着做
- 专业但不难懂
- 覆盖了我可能遇到的情况

😐 不会操作 (0.5-0.7):
- 说了一些有用的，但不够具体
- 需要我自己再查其他资料
- 有点啰嗦或跑题
- 没有针对我的具体问题

👎 会踩 (0.0-0.4):
- 完全没有帮助
- 看不懂在说什么
- 答非所问
- 给了错误的信息

用户问题：{question}
AI 回答：{response}

请严格按照真实用户的反应评分，不要所有回答都给中间分！
输出格式（必须严格遵循）：
分数：X.XX
反馈：👍/😐/👎
理由：（一句话说明）"""


class GPT52HumanFeedbackSimulator(BaseReward):
    """
    使用 GPT-5.2 模拟人类点赞/踩行为的奖励函数
    
    核心思想：
    - 真实场景中，用户会对 AI 回答点赞或踩
    - 初期没有足够的真实反馈数据
    - 使用 GPT-5.2 模拟"一个普通用户会不会点赞"
    
    关键设计：
    1. Prompt 要让 GPT-5.2 "挑剔"，不要当老好人
    2. 分数要有区分度，不能都是 0.7-0.8
    3. 好回答和差回答的分数差距要大
    """
    
    def __init__(
        self,
        prompt_template: str = HUMAN_FEEDBACK_SIMULATOR,
        score_pattern: str = r"分数[：:]\s*(\d+\.?\d*)",
        default_score: float = 0.5,
        temperature: float = 0.1,  # 评分要稳定，用低温度
    ):
        super().__init__()
        self.prompt_template = prompt_template
        self.score_pattern = score_pattern
        self.default_score = default_score
        self.temperature = temperature
        
        # 初始化 Azure OpenAI 客户端 (GPT-5.2)
        self.client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
        )
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
        print(f"[奖励函数] 使用 {self.deployment} 模拟人类点赞反馈")
    
    def __call__(self, prompts: List[str], responses: List[str]) -> List[float]:
        """
        计算每个 response 的奖励分数（模拟用户是否会点赞）
        
        Args:
            prompts: 用户问题列表
            responses: 模型回答列表
            
        Returns:
            分数列表 (0.0-1.0)，代表"用户点赞的概率"
        """
        scores = []
        for prompt, response in zip(prompts, responses):
            score = self._simulate_human_feedback(prompt, response)
            scores.append(score)
        return scores
    
    def _simulate_human_feedback(self, question: str, response: str) -> float:
        """
        模拟一个真实用户看到这个回答后的反应
        
        返回：用户点赞的概率 (0.0-1.0)
        """
        judge_prompt = self.prompt_template.format(
            question=question,
            response=response
        )
        
        try:
            result = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": judge_prompt}],
                temperature=self.temperature,
                max_tokens=200
            )
            
            judge_response = result.choices[0].message.content
            
            # 提取分数
            match = re.search(self.score_pattern, judge_response)
            if match:
                score = float(match.group(1))
                # 确保分数在 0-1 范围内
                score = max(0.0, min(1.0, score))
                return score
            else:
                print(f"警告：无法从 GPT-5.2 回复中提取分数: {judge_response[:100]}")
                return self.default_score
                
        except Exception as e:
            print(f"GPT-5.2 API 调用失败: {e}")
            return self.default_score


def load_training_data(data_path: str) -> Dataset:
    """
    加载 GPT-5.2 生成的训练数据
    
    数据格式：
    [
        {"prompt": "用户问题1", "response": "参考回答1"},
        {"prompt": "用户问题2", "response": "参考回答2"},
        ...
    ]
    
    注意：response 字段仅用于参考，GRPO 会让模型自己生成回答
    """
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    prompts = [item["prompt"] for item in data]
    print(f"加载了 {len(prompts)} 个训练样本（由 GPT-5.2 生成）")
    
    # 显示前 3 个样本
    print("\n训练数据示例：")
    for i, p in enumerate(prompts[:3]):
        print(f"  {i+1}. {p[:50]}...")
    
    return Dataset.from_dict({"prompt": prompts})


def main(args):
    """主训练流程"""
    
    # ========== 1. 环境检查 ==========
    print("=" * 60)
    print("AIPC 技术支持智能体 GRPO 训练")
    print("核心机制：GPT-5.2 模拟人类点赞/踩作为奖励信号")
    print("=" * 60)
    
    # 检查必需的环境变量
    required_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
    missing_vars = [v for v in required_vars if v not in os.environ]
    if missing_vars:
        raise ValueError(f"缺少环境变量: {', '.join(missing_vars)}")
    
    # 检查 GPU
    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 GPU，GRPO 训练需要 GPU")
    
    gpu_name = torch.cuda.get_device_name(0)
    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {gpu_name} ({gpu_memory:.1f} GB)")
    
    # ========== 2. 加载数据 ==========
    print(f"\n加载训练数据: {args.data}")
    train_dataset = load_training_data(args.data)
    
    # ========== 3. 配置训练参数 ==========
    print(f"\n配置训练参数:")
    print(f"  - 基座模型: {args.model}")
    print(f"  - 学习率: {args.lr}")
    print(f"  - 训练轮数: {args.epochs}")
    print(f"  - Group Size: {args.group_size}")
    print(f"  - 输出目录: {args.output}")
    
    config = GRPOConfig(
        # 模型配置
        model_name=args.model,
        
        # 训练超参数
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        
        # GRPO 特有参数
        group_size=args.group_size,  # 每个 prompt 生成多少个回答
        
        # 生成参数
        max_new_tokens=512,
        temperature=0.8,  # 探索性要高一些
        
        # 输出配置
        output_dir=args.output,
        logging_steps=1,
        save_steps=10,
        
        # 精度配置
        bf16=True,
    )
    
    # ========== 4. 初始化 GPT-5.2 点赞模拟器 ==========
    print(f"\n初始化 GPT-5.2 人类反馈模拟器...")
    reward_fn = GPT52HumanFeedbackSimulator(
        prompt_template=HUMAN_FEEDBACK_SIMULATOR,
        score_pattern=r"分数[：:]\s*(\d+\.?\d*)",
        temperature=0.1
    )
    
    # 测试模拟器是否正常工作
    print("测试 GPT-5.2 点赞模拟器...")
    test_scores = reward_fn(
        ["AIPC 是什么？"],
        ["AIPC 是搭载了 AI 加速芯片（NPU）的个人电脑，可以在本地运行 AI 应用。"]
    )
    print(f"测试评分: {test_scores[0]:.2f} (模拟用户点赞概率)")
    
    # ========== 5. 开始训练 ==========
    print(f"\n" + "=" * 60)
    print("开始 GRPO 训练")
    print("奖励来源：GPT-5.2 模拟用户点赞/踩")
    print("=" * 60)
    
    trainer = GRPOTrainer(
        config=config,
        train_dataset=train_dataset,
        reward_function=reward_fn
    )
    
    trainer.train()
    
    # ========== 6. 保存模型 ==========
    print(f"\n训练完成！")
    print(f"模型保存至: {args.output}")
    
    # 保存训练配置
    config_path = os.path.join(args.output, "training_config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "model": args.model,
            "learning_rate": args.lr,
            "epochs": args.epochs,
            "group_size": args.group_size,
            "data": args.data,
            "reward_source": "GPT-5.2 模拟人类点赞/踩",
            "data_source": "GPT-5.2 从私有文档生成"
        }, f, indent=2, ensure_ascii=False)
    print(f"配置保存至: {config_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AIPC 技术支持智能体 GRPO 训练（GPT-5.2 模拟点赞反馈）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
核心机制：
    1. 训练数据：GPT-5.2 从私有 AIPC 文档生成 QA 对
    2. 奖励信号：GPT-5.2 模拟用户点赞/踩行为
    
示例：
    # 基本训练
    python train_aipc_agent.py --data data/aipc_qa.json --output ./output
    
    # 指定模型和学习率
    python train_aipc_agent.py --data data/aipc_qa.json --model Qwen/Qwen2.5-7B-Instruct --lr 5e-6
        """
    )
    
    parser.add_argument(
        "--data", 
        required=True, 
        help="GPT-5.2 生成的训练数据 JSON 文件路径"
    )
    parser.add_argument(
        "--model", 
        default="Qwen/Qwen2.5-3B-Instruct", 
        help="基座模型 (默认: Qwen2.5-3B-Instruct)"
    )
    parser.add_argument(
        "--output", 
        default="./aipc_agent_output", 
        help="输出目录 (默认: ./aipc_agent_output)"
    )
    parser.add_argument(
        "--lr", 
        type=float, 
        default=1e-5, 
        help="学习率 (默认: 1e-5)"
    )
    parser.add_argument(
        "--epochs", 
        type=int, 
        default=1, 
        help="训练轮数 (默认: 1)"
    )
    parser.add_argument(
        "--group-size", 
        type=int, 
        default=4, 
        help="GRPO group size (默认: 4)"
    )
    
    args = parser.parse_args()
    main(args)
