import os
import torch
import glob
from transformers import AutoModelForCausalLM, AutoTokenizer
from safetensors.torch import load_file

# Configuration
BASE_MODEL_PATH = os.environ.get("BASE_MODEL_PATH", "Qwen/Qwen2.5-3B-Instruct")
CHECKPOINT_PATH = os.environ.get("CHECKPOINT_PATH", "checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "checkpoints/AgentLightningTutorial/math_agent_3b_h100_v4_deepthink/global_step_100/actor/huggingface")

def convert_checkpoint():
    print(f"🚀 Starting checkpoint conversion...")
    print(f"   Base Model: {BASE_MODEL_PATH}")
    print(f"   Checkpoint: {CHECKPOINT_PATH}")
    print(f"   Output:     {OUTPUT_PATH}")

    # 1. Load Tokenizer
    print("\n📚 Loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT_PATH, trust_remote_code=True)
    except:
        print("   Warning: Could not load tokenizer from checkpoint, using base model...")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)

    # 2. Load Model State Dict
    print("\n📦 Loading checkpoint weights...")
    state_dict = {}
    
    # Try loading safetensors first
    safetensor_files = glob.glob(os.path.join(CHECKPOINT_PATH, "*.safetensors"))
    if safetensor_files:
        print(f"   Found {len(safetensor_files)} safetensors files.")
        for f in safetensor_files:
            print(f"   Loading {os.path.basename(f)}...")
            state_dict.update(load_file(f))
    else:
        # Try loading bin files
        bin_files = glob.glob(os.path.join(CHECKPOINT_PATH, "*.bin"))
        if bin_files:
            print(f"   Found {len(bin_files)} bin files.")
            for f in bin_files:
                print(f"   Loading {os.path.basename(f)}...")
                state_dict.update(torch.load(f, map_location="cpu"))
        else:
            raise FileNotFoundError("No .safetensors or .bin files found in checkpoint directory!")

    # 3. Filter Keys
    print("\n🧹 Filtering internal keys...")
    new_state_dict = {}
    removed_keys = []
    for k, v in state_dict.items():
        # Filter out AgentLightning/Verl specific keys like '_snapshot'
        if "_snapshot" in k or "optimizer" in k:
            removed_keys.append(k)
        else:
            new_state_dict[k] = v
    
    print(f"   Removed {len(removed_keys)} internal keys (e.g., _snapshot).")

    # 4. Load Base Model Structure
    print("\n🏗️  Loading base model structure...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        trust_remote_code=True,
        device_map="cpu",
        torch_dtype=torch.float16
    )

    # 5. Apply Weights
    print("\n🔧 Applying filtered weights to model...")
    missing, unexpected = model.load_state_dict(new_state_dict, strict=False)
    
    if missing:
        print(f"   ⚠️ Missing keys: {len(missing)} (This is expected if only LoRA/partial weights, but check carefully)")
        # print(missing[:5])
    if unexpected:
        print(f"   ⚠️ Unexpected keys: {len(unexpected)}")
        # print(unexpected[:5])

    # 6. Save Converted Model
    print(f"\n💾 Saving converted model to {OUTPUT_PATH}...")
    model.save_pretrained(OUTPUT_PATH)
    tokenizer.save_pretrained(OUTPUT_PATH)
    
    print("\n✅ Conversion Complete!")

if __name__ == "__main__":
    convert_checkpoint()
