# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.4.2 线上服务时的核心代码示例

from openai import OpenAI
client = OpenAI(api_key="EMPTY", base_url="http://localhost:8000/v1")
# 调用聊天适配器
response = client.completions.create(
    model="oasst",
    prompt="### Human: 请检查数字8和1233是否是2的幂次。### Assistant:",
    temperature=0.7,
    max_tokens=500
)
# 调用函数调用适配器
response = client.completions.create(
    model="xlam",
    prompt="<user>计算75除以1555的结果是多少？</user>\n\n<tools>",
    temperature=0.0,
    max_tokens=500
)
