"""
AIPC Domain Reward Functions
=============================

Shared reward functions for AIPC domain training.
Used by train_grpo_agl.py and train_feedback_agl.py.

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import re
from typing import Dict, List, Tuple


# =============================================================================
# AIPC Domain Keywords
# =============================================================================

AIPC_KEYWORDS = {
    "hardware": [
        "NPU", "CPU", "GPU", "Intel", "AMD", "Qualcomm", "Snapdragon",
        "Core Ultra", "Ryzen AI", "XDNA", "AI Boost", "内存", "显存",
        "功耗", "散热", "处理器", "加速器", "算力", "TOPS",
        "Meteor Lake", "Lunar Lake", "Arrow Lake",
    ],
    "software": [
        "Windows", "DirectML", "ONNX", "Runtime", "Copilot", "API",
        "量化", "INT4", "INT8", "FP16", "BF16", "Olive", "模型优化",
        "推理", "部署", "SDK", "驱动", "Windows ML", "WinML",
        "OpenVINO", "TensorRT", "vLLM", "llama.cpp",
    ],
    "applications": [
        "字幕", "翻译", "Stable Diffusion", "Whisper", "语音识别",
        "图像生成", "代码补全", "RAG", "向量数据库", "本地部署",
        "实时", "离线", "隐私", "Phi-3", "Phi-4", "LLM",
        "大语言模型", "多模态", "Vision", "VLM",
    ],
    "optimization": [
        "延迟", "吞吐量", "批处理", "流式", "预热", "缓存",
        "内存优化", "显存优化", "KV Cache", "Flash Attention",
        "量化", "剪枝", "蒸馏", "融合", "编译",
    ],
}

# Structure patterns
STRUCTURE_PATTERNS = {
    "markdown_header": r"^#+\s+.+$",
    "code_block": r"```[\w]*\n[\s\S]*?\n```",
    "inline_code": r"`[^`]+`",
    "bullet_list": r"^[\*\-]\s+.+$",
    "numbered_list": r"^\d+\.\s+.+$",
    "table": r"\|.+\|",
}

# Hallucination indicators - things that don't exist
HALLUCINATION_INDICATORS = [
    r"Intel Core Ultra \d{5}",  # Fake model numbers (5 digits)
    r"AMD Ryzen AI \d{5}",
    r"NPU 性能达到 \d{4,} TOPS",  # Unrealistic TOPS claims (>1000)
    r"Windows 1[3-9]|Windows 2\d",  # Future Windows versions
    r"发布于 202[7-9]|203\d",  # Future dates (2027+)
    r"Phi-[5-9]|Phi-\d{2}",  # Future Phi models
    r"GPT-[6-9]|GPT-\d{2}",  # Future GPT models
]


# =============================================================================
# Reward Component Functions
# =============================================================================


def compute_keyword_coverage(response: str) -> Tuple[float, Dict]:
    """
    Compute keyword coverage score.
    
    Args:
        response: Model response text
        
    Returns:
        Tuple of (score, details dict)
    """
    response_lower = response.lower()
    category_matches = {}
    total_keywords = 0
    matched_keywords = 0
    
    for category, keywords in AIPC_KEYWORDS.items():
        matches = []
        for keyword in keywords:
            total_keywords += 1
            if keyword.lower() in response_lower:
                matched_keywords += 1
                matches.append(keyword)
        category_matches[category] = matches
    
    # Score: expect at least 10% coverage for full score
    expected_coverage = total_keywords * 0.1
    coverage_ratio = min(1.0, matched_keywords / expected_coverage)
    score = coverage_ratio * 0.4
    
    details = {
        "matched_keywords": matched_keywords,
        "total_keywords": total_keywords,
        "coverage_ratio": matched_keywords / total_keywords,
        "category_matches": category_matches,
    }
    
    return score, details


def compute_structure_score(response: str) -> Tuple[float, Dict]:
    """
    Compute structure quality score based on Markdown formatting.
    
    Args:
        response: Model response text
        
    Returns:
        Tuple of (score, details dict)
    """
    score = 0.0
    found_patterns = []
    
    # Check for headers (0.08 points)
    if re.search(STRUCTURE_PATTERNS["markdown_header"], response, re.MULTILINE):
        score += 0.08
        found_patterns.append("markdown_header")
    
    # Check for code blocks (0.08 points)
    if re.search(STRUCTURE_PATTERNS["code_block"], response):
        score += 0.08
        found_patterns.append("code_block")
    
    # Check for inline code (0.04 points)
    if re.search(STRUCTURE_PATTERNS["inline_code"], response):
        score += 0.04
        found_patterns.append("inline_code")
    
    # Check for lists (0.06 points)
    if re.search(STRUCTURE_PATTERNS["bullet_list"], response, re.MULTILINE) or \
       re.search(STRUCTURE_PATTERNS["numbered_list"], response, re.MULTILINE):
        score += 0.06
        found_patterns.append("list")
    
    # Check for tables (0.04 points)
    if re.search(STRUCTURE_PATTERNS["table"], response):
        score += 0.04
        found_patterns.append("table")
    
    details = {
        "found_patterns": found_patterns,
        "pattern_count": len(found_patterns),
    }
    
    return score, details


def compute_hallucination_penalty(response: str) -> Tuple[float, Dict]:
    """
    Compute hallucination penalty.
    
    Args:
        response: Model response text
        
    Returns:
        Tuple of (penalty, details dict)
    """
    penalty = 0.0
    found_hallucinations = []
    
    for pattern in HALLUCINATION_INDICATORS:
        matches = re.findall(pattern, response)
        if matches:
            penalty += 0.1 * len(matches)
            found_hallucinations.extend(matches)
    
    penalty = min(0.3, penalty)
    
    details = {
        "found_hallucinations": found_hallucinations,
        "hallucination_count": len(found_hallucinations),
    }
    
    return penalty, details


def compute_length_bonus(response: str) -> Tuple[float, Dict]:
    """
    Compute length-based bonus/penalty.
    
    Optimal length: 300-1500 characters
    
    Args:
        response: Model response text
        
    Returns:
        Tuple of (bonus, details dict)
    """
    length = len(response)
    
    if length < 100:
        bonus = -0.1  # Too short
    elif length < 300:
        bonus = 0.0
    elif length <= 1500:
        bonus = 0.1  # Optimal range
    elif length <= 3000:
        bonus = 0.05
    else:
        bonus = 0.0  # Too long, no bonus
    
    details = {
        "length": length,
        "optimal_range": "300-1500",
    }
    
    return bonus, details


# =============================================================================
# Main Reward Function
# =============================================================================


def compute_aipc_reward(response: str, detailed: bool = False) -> float | Tuple[float, Dict]:
    """
    Compute comprehensive AIPC domain reward.
    
    Components:
        - Keyword coverage: 0-0.4
        - Structure score: 0-0.3
        - No hallucination bonus: 0-0.3
        - Length bonus: -0.1 to +0.1
    
    Args:
        response: Model response text
        detailed: Whether to return detailed breakdown
        
    Returns:
        If detailed=False: Total reward between 0 and 1
        If detailed=True: Tuple of (reward, details dict)
    """
    keyword_score, keyword_details = compute_keyword_coverage(response)
    structure_score, structure_details = compute_structure_score(response)
    hallucination_penalty, hallucination_details = compute_hallucination_penalty(response)
    length_bonus, length_details = compute_length_bonus(response)
    
    # Compute final reward
    no_hallucination_bonus = 0.3 - hallucination_penalty
    total_reward = keyword_score + structure_score + no_hallucination_bonus + length_bonus
    
    # Clamp to [0, 1]
    total_reward = max(0.0, min(1.0, total_reward))
    
    if detailed:
        details = {
            "total_reward": total_reward,
            "components": {
                "keyword_coverage": {
                    "score": keyword_score,
                    "max": 0.4,
                    **keyword_details,
                },
                "structure": {
                    "score": structure_score,
                    "max": 0.3,
                    **structure_details,
                },
                "no_hallucination": {
                    "score": no_hallucination_bonus,
                    "max": 0.3,
                    "penalty": hallucination_penalty,
                    **hallucination_details,
                },
                "length": {
                    "bonus": length_bonus,
                    **length_details,
                },
            },
        }
        return total_reward, details
    
    return total_reward


# =============================================================================
# Test Function
# =============================================================================


def test_reward_function():
    """Test reward function with sample responses."""
    
    # Good response
    good_response = """
# Intel Core Ultra 处理器的 NPU 架构

## 概述

Intel Core Ultra 系列处理器集成了专用的 NPU (Neural Processing Unit)，用于加速 AI 推理任务。

### 关键特性

- **算力**: 达到 34 TOPS (INT8)
- **功耗**: 仅 5W TDP
- **支持框架**: OpenVINO, DirectML, ONNX Runtime

### 代码示例

```python
import openvino as ov
core = ov.Core()
model = core.read_model("model.xml")
compiled = core.compile_model(model, "NPU")
```

这种架构使得 AIPC 能够在本地运行 Phi-3 等大语言模型。
"""
    
    # Bad response (short, no structure)
    bad_response = "NPU 是神经处理单元。"
    
    # Hallucinating response
    hallucinating_response = """
Intel Core Ultra 99999 处理器发布于 2030 年，
NPU 性能达到 10000 TOPS，支持 GPT-10 模型。
"""
    
    print("=" * 60)
    print("Testing AIPC Reward Function")
    print("=" * 60)
    
    for name, response in [
        ("Good", good_response),
        ("Bad", bad_response),
        ("Hallucinating", hallucinating_response),
    ]:
        reward, details = compute_aipc_reward(response, detailed=True)
        print(f"\n{name} Response:")
        print(f"  Total Reward: {reward:.4f}")
        print(f"  Keyword Coverage: {details['components']['keyword_coverage']['score']:.4f}")
        print(f"  Structure Score: {details['components']['structure']['score']:.4f}")
        print(f"  No Hallucination: {details['components']['no_hallucination']['score']:.4f}")
        print(f"  Length Bonus: {details['components']['length']['bonus']:.4f}")


if __name__ == "__main__":
    test_reward_function()


# =============================================================================
# GPT-5.2 LLM-as-Judge Reward Function (Recommended)
# =============================================================================

def create_gpt52_reward_function(
    azure_endpoint: str,
    api_key: str,
    api_version: str = "2025-04-01-preview",
    model_name: str = "gpt-5.2"
):
    """
    Create a GPT-5.2 based reward function for GRPO training.
    
    This approach uses GPT-5.2 as a judge to evaluate response quality,
    which provides more accurate rewards than keyword-based methods.
    
    Args:
        azure_endpoint: Azure OpenAI endpoint
        api_key: API key
        api_version: API version
        model_name: Model deployment name
        
    Returns:
        Reward function compatible with TRL GRPOTrainer
        
    Example:
        >>> reward_fn = create_gpt52_reward_function(
        ...     azure_endpoint="https://<your-resource><your-resource>.openai.azure.com",
        ...     api_key="YOUR_KEY"
        ... )
        >>> trainer = GRPOTrainer(..., reward_funcs=reward_fn)
    """
    from openai import AzureOpenAI
    import re
    
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version
    )
    
    def gpt52_reward(prompts, completions, **kwargs):
        """
        Evaluate responses using GPT-5.2.
        
        Args:
            prompts: List of input prompts
            completions: List of model completions
            
        Returns:
            List of reward scores normalized to [-1, 1]
        """
        rewards = []
        for prompt, completion in zip(prompts, completions):
            try:
                eval_prompt = f"""评估这个AI PC技术回答的质量(1-10分)，只返回数字:
问题: {prompt}
回答: {completion[:500]}"""
                
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": eval_prompt}],
                    temperature=0,
                    max_completion_tokens=10
                )
                content = resp.choices[0].message.content
                match = re.search(r"(\d+)", content)
                if match:
                    score = float(match.group(1))
                    # Normalize to [-1, 1]: score 5 = 0, score 10 = 1, score 0 = -1
                    normalized = (score - 5) / 5
                    rewards.append(normalized)
                else:
                    rewards.append(0.0)
            except Exception as e:
                print(f"GPT-5.2 reward error: {e}")
                rewards.append(0.0)
        return rewards
    
    return gpt52_reward


def create_gpt52_detailed_reward_function(
    azure_endpoint: str,
    api_key: str,
    api_version: str = "2025-04-01-preview",
    model_name: str = "gpt-5.2"
):
    """
    Create a detailed GPT-5.2 reward function with 5-dimension evaluation.
    
    Dimensions:
    1. 准确性 (Accuracy): Technical correctness
    2. 完整性 (Completeness): Comprehensive coverage
    3. 专业性 (Professionalism): Proper terminology
    4. 实用性 (Practicality): Actionable advice
    5. 代码质量 (Code Quality): If applicable
    
    Returns:
        Reward function with detailed scoring
    """
    from openai import AzureOpenAI
    import json
    import re
    
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version
    )
    
    def detailed_reward(prompts, completions, **kwargs):
        rewards = []
        for prompt, completion in zip(prompts, completions):
            try:
                eval_prompt = f"""请评估以下AI PC技术问答的质量。

问题: {prompt}

回答: {completion[:800]}

请从以下5个维度评分(每个维度1-4分):
1. 准确性: 技术信息是否正确
2. 完整性: 是否全面回答了问题
3. 专业性: 是否使用了正确的技术术语
4. 实用性: 对用户是否有实际帮助
5. 代码质量(如适用): 代码是否可运行、有注释

请用JSON格式返回: {{"准确性": X, "完整性": X, "专业性": X, "实用性": X, "代码质量": X, "总分": XX}}"""
                
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": eval_prompt}],
                    temperature=0,
                    max_completion_tokens=200
                )
                content = resp.choices[0].message.content
                
                # Extract JSON
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    total = result.get("总分", 10)
                    # Normalize: 20分满分 -> [-1, 1]
                    normalized = (total - 10) / 10
                    rewards.append(normalized)
                else:
                    rewards.append(0.0)
            except Exception as e:
                print(f"Detailed reward error: {e}")
                rewards.append(0.0)
        return rewards
    
    return detailed_reward
