# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.4.2 Multi LoRA Adapter的代码实现

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from huggingface_hub import snapshot_download
# 加载基础模型（启用 LoRA 支持）
llm = LLM(model="meta-llama/Meta-Llama-3-8B", enable_lora=True, max_lora_rank=16)
# 创建聊天任务的 LoRARequest
oasst_lora_path = snapshot_download(repo_id="kaitchup/Meta-Llama-3-8B-oasst-Adapter")
oasstLR = LoRARequest("oasst", 1, oasst_lora_path)
# 创建函数调用任务的 LoRARequest
xlam_lora_path = snapshot_download(repo_id="kaitchup/Meta-Llama-3-8B-xLAM-Adapter")
xlamLR = LoRARequest("xlam", 2, xlam_lora_path)

# （1）使用聊天适配器（oasst）
prompts_oasst = ["### Human: 请检查数字8和1233是否是2的幂次。### Assistant:"]
sampling_params_oasst = SamplingParams(temperature=0.7, top_p=0.9, max_tokens=500)
outputs = llm.generate(prompts_oasst, sampling_params_oasst, lora_request=oasstLR)
print(outputs[0].outputs[0].text)

# （2）使用函数调用适配器（xlam）
prompts_xlam = ["<user>计算75除以1555的结果是多少？</user>\n\n<tools>"]
sampling_params_xlam = SamplingParams(temperature=0.0, max_tokens=500)
outputs = llm.generate(prompts_xlam, sampling_params_xlam, lora_request=xlamLR)
print(outputs[0].outputs[0].text)
