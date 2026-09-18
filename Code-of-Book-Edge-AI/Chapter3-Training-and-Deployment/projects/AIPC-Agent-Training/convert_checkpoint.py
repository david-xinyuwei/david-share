import os
import torch
import glob
import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer
from safetensors.torch import load_file

# Configuration
BASE_MODEL_PATH = "meta-llama/Llama-3.2-3B-Instruct"

def convert_checkpoint(checkpoint_path, output_path):
    print(f"🚀 Starting checkpoint conversion...")
    print(f"   Base Model: {BASE_MODEL_PATH}")
    print(f"   Checkpoint: {checkpoint_path}")
    print(f"   Output:     {output_path}")

    # 1. Load Tokenizer
    print("\n📚 Loading tokenizer...")
    try:
        # Try loading from huggingface subdir first as that's where verl saves it
        tokenizer = AutoTokenizer.from_pretrained(os.path.join(checkpoint_path, "huggingface"), trust_remote_code=True)
    except:
        try:
            tokenizer = AutoTokenizer.from_pretrained(checkpoint_path, trust_remote_code=True)
        except:
            print("   Warning: Could not load tokenizer from checkpoint, using base model...")
            tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
    
    # 2. Load Model State Dict
    print("\n📦 Loading checkpoint weights...")
    state_dict = {}

    # Try loading safetensors first
    safetensor_files = glob.glob(os.path.join(checkpoint_path, "*.safetensors"))
    if safetensor_files:
        print(f"   Found {len(safetensor_files)} safetensors files.")
        for f in safetensor_files:
            print(f"   Loading {os.path.basename(f)}...")
            state_dict.update(load_file(f))
    else:
        # Try loading bin files
        bin_files = glob.glob(os.path.join(checkpoint_path, "*.bin"))
        if bin_files:
            print(f"   Found {len(bin_files)} bin files.")
            for f in bin_files:
                print(f"   Loading {os.path.basename(f)}...")
                state_dict.update(torch.load(f, map_location="cpu"))
        else:
            # Try loading pt files (Verl/FSDP output)
            pt_files = glob.glob(os.path.join(checkpoint_path, "*.pt"))
            if pt_files:
                print(f"   Found {len(pt_files)} pt files.")
                for f in pt_files:
                    if "optim" in f or "extra_state" in f: 
                        continue
                    print(f"   Loading {os.path.basename(f)}...")
                    state_dict.update(torch.load(f, map_location="cpu"))
            else:
                raise FileNotFoundError("No .safetensors, .bin, or .pt files found in checkpoint directory!")

    # 3. Filter Keys
    print("\n🧹 Filtering internal keys...")
    new_state_dict = {}
    removed_keys = []
    for k, v in state_dict.items():
        # Filter out training framework internal keys like '_snapshot'
        if "_snapshot" in k or "optimizer" in k:
            removed_keys.append(k)
        else:
            new_state_dict[k] = v

    print(f"   Removed {len(removed_keys)} internal keys (e.g., _snapshot).")

    # 4. Load Base Model Structure
    print("\n🏗️  Loading base model structure...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_PATH,
            trust_remote_code=True,
            device_map="cpu",
            torch_dtype=torch.float16,
            local_files_only=True
        )
        print("   Loaded from local cache.")
    except Exception as e:
        print(f"   Could not load from local cache ({e}), trying online...")
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
    print(f"\n💾 Saving converted model to {output_path}...")
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)

    print("\n✅ Conversion Complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Ray/Verl checkpoint to Hugging Face format")
    parser.add_argument("--checkpoint_path", type=str, required=True, help="Path to the input checkpoint directory")
    parser.add_argument("--output_path", type=str, required=True, help="Path to save the converted model")
    
    args = parser.parse_args()
    
    convert_checkpoint(args.checkpoint_path, args.output_path)
