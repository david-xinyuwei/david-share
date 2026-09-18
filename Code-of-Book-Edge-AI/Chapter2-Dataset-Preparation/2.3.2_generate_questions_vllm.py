# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第2章 §2.3.2 批量生成问题
# 依赖 2.3.1_persona_to_prompt.py 生成的 questions 列表

from vllm import LLM, SamplingParams
# 加载 Qwen2.5模型，设置模型最大上下文长度
llm = LLM(model="Qwen/Qwen2.5-7B-Instruct", max_model_len=1500)
# 设置随机采样参数(更高温度如temperature=0.7，top_p=0.95能增强生成多样性)
sampling_params = SamplingParams(temperature=0.7, top_p=0.95, max_tokens=1024)
question_prompts = []
# 每个persona执行5次推理，生成5个不同问题
for _ in range(5):
    outputs = llm.chat(messages=questions,
                        sampling_params=sampling_params,
                        use_tqdm=True)
    for output in outputs:
        # 提取原始persona文本
        c_persona = output.prompt.split('\n\n')[1].split("<|im_end|>")[0].strip()
        # 组合成后续用于答案生成的prompt
        generated_text = f"You are this persona: {c_persona}\n\nAnswer the following question:\n{output.outputs[0].text}"
        question_prompts.append({
            "role": "user",
            "content": generated_text
        })
print(f"总计生成问题数量：{len(question_prompts)}")
