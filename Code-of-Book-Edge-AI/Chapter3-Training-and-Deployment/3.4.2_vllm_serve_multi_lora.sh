# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.4.2 线上服务时的核心代码示例

vllm serve meta-llama/Meta-Llama-3-8B \
    --enable-lora \
    --lora-modules oasst={oasst_lora_path} xlam={xlam_lora_path}
