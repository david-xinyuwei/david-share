# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第5章 §5.2.4 启动命令

# DeepSpeed 方式（书中：deepspeed deepspeed.py）
deepspeed deepspeed_dpo.py

# FSDP 方式（书中：accelerate launch --config_file config_fsdp.yaml fsdp+QLoRA.py）
accelerate launch --config_file config_fsdp.yaml fsdp_qlora_dpo.py
