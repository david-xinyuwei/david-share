# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.6.3 训练飞轮实现方案 —— GRPO 阶段
# 完整可运行版本见 projects/AIPC-Agent-Training/train_grpo_aipc.py

def reward_function(completions, **kwargs):
    """
    AI PC Expert 奖励函数 (V1.1 GRPO Training)
    设计原则：正向引导 > 负向惩罚
    - 关键词覆盖：引导模型使用 AI PC 专业术语
    - 长度约束：避免过长或过短的回答
    - 结构化：鼓励分点列举，便于用户理解
    - 无幻觉：避免输出与边缘设备无关的服务器术语
    """
    # 正向关键词（AI PC 领域术语）
    keywords = ['NPU', 'Intel Core Ultra', 'Snapdragon X', 'AI PC',
                'AIPC', 'Copilot', 'DirectML', 'ONNX', 'OpenVINO']
    # 幻觉词（服务器/数据中心术语，边缘场景不应出现）
    hallucination_words = ['服务器', 'GPU集群', '云端训练',
                          'A100', 'H100', '数据中心']
    rewards = []
    for completion in completions:
        score = 0.0
        # 1. 关键词覆盖 (+0.3)
        keyword_count = sum(1 for kw in keywords
                        if kw.lower() in completion.lower())
        score += min(0.3, keyword_count * 0.05)
        # 2. 长度适中 (+0.2)
        length = len(completion)
        if 100 <= length <= 500:
            score += 0.2
        elif 50 <= length < 100 or 500 < length <= 800:
            score += 0.1
        # 3. 结构化输出 (+0.2)
        if any(m in completion for m in ['1.', '2.', '•', '-', '首先', '其次']):
            score += 0.2
        # 4. 无幻觉 (+0.3)
        if not any(hw in completion for hw in hallucination_words):
            score += 0.3
        rewards.append(score)
    return rewards
