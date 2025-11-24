
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Configuration
BASE_MODEL_NAME = os.environ.get("BASE_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
# 指向包含 .pt 文件的目录
CHECKPOINT_DIR = os.environ.get(
    "CHECKPOINT_DIR",
    os.path.join(os.getcwd(), "checkpoints/AgentLightningTutorial/math_agent_large/global_step_10/actor")
)
OUTPUT_DIR = os.environ.get(
    "OUTPUT_DIR",
    os.path.join(os.getcwd(), "checkpoints/AgentLightningTutorial/math_agent_large/global_step_10_hf")
)

def convert():
    print(f"Loading base model: {BASE_MODEL_NAME}")
    # 使用 CPU 加载以避免显存问题
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME,
        torch_dtype=torch.float16,
        trust_remote_code=True,
        device_map="cpu"
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME, trust_remote_code=True)

    pt_file = os.path.join(CHECKPOINT_DIR, "model_world_size_1_rank_0.pt")
    print(f"Loading checkpoint: {pt_file}")
    
    if not os.path.exists(pt_file):
        print(f"Error: File not found: {pt_file}")
        return

    state_dict = torch.load(pt_file, map_location="cpu")
    
    print("Applying state dict...")
    # strict=False 允许一些不匹配（例如缓冲区或版本差异）
    missing, unexpected = model.load_state_dict(state_dict, strict=False)
    
    print(f"Missing keys: {len(missing)}")
    if len(missing) > 0:
        print(f"Example missing: {missing[:5]}")
        
    print(f"Unexpected keys: {len(unexpected)}")
    if len(unexpected) > 0:
        print(f"Example unexpected: {unexpected[:5]}")
    
    print(f"Saving to {OUTPUT_DIR}")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("Done!")

if __name__ == "__main__":
    convert()
