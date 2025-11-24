import torch
import flash_attn
import vllm
import verl
import agentlightning

print(f"PyTorch: {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
print(f"FlashAttn: {flash_attn.__version__}")
print(f"vLLM: {vllm.__version__}")
print(f"VERL: {verl.__version__}")
print(f"AgentLightning: {agentlightning.__version__}")
