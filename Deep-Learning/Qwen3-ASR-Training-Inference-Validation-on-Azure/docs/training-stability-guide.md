# Training Stability & Speed Guide for Qwen3-ASR Fine-tuning

Generated: 2026-06-25
Purpose: Meeting preparation — common issues and solutions for large-scale ASR training

## Multi-GPU Training Template

### Official Qwen3-ASR SFT (single GPU verified)

```bash
# Single GPU (verified on H100 NVL 95GB)
python qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-0.6B \
  --train_file /path/to/train.jsonl \
  --eval_file /path/to/eval.jsonl \
  --output_dir /path/to/output \
  --epochs 3 \
  --batch_size 4 \
  --lr 2e-5 \
  --save_strategy epoch
```

### Multi-GPU with torchrun (recommended for customer)

```bash
# Multi-GPU with torchrun + DeepSpeed ZeRO-2
torchrun --nproc_per_node=8 --master_port=29500 \
  qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file /path/to/train.jsonl \
  --eval_file /path/to/eval.jsonl \
  --output_dir /path/to/output \
  --epochs 10 \
  --batch_size 8 \
  --grad_acc 4 \
  --lr 1e-5 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.05 \
  --num_workers 4 \
  --pin_memory True \
  --save_strategy steps \
  --save_steps 500 \
  --save_total_limit 3
```

### Accelerate Config (accelerate.yaml)

```yaml
compute_environment: LOCAL_MACHINE
distributed_type: MULTI_GPU
num_machines: 1
num_processes: 8
mixed_precision: bf16
deepspeed_config:
  deepspeed_config_file: deepspeed_zero2.json
  zero3_init_flag: false
```

### DeepSpeed ZeRO-2 Config

```json
{
  "bf16": {"enabled": true},
  "zero_optimization": {
    "stage": 2,
    "allgather_partitions": true,
    "allgather_bucket_size": 5e8,
    "overlap_comm": true,
    "reduce_scatter": true,
    "reduce_bucket_size": 5e8,
    "contiguous_gradients": true
  },
  "gradient_accumulation_steps": 4,
  "gradient_clipping": 1.0,
  "train_batch_size": "auto",
  "train_micro_batch_size_per_gpu": "auto"
}
```

## Common Training Issues Checklist

### 1. OOM (Out of Memory)

| Symptom | Cause | Fix |
|---|---|---|
| CUDA OOM during forward | Batch too large for model + audio length | Reduce `--batch_size`, enable gradient checkpointing |
| OOM during backward | Activation memory | Enable `gradient_checkpointing=True` in model config |
| OOM grows over time | Memory leak in dataloader | Set `--num_workers 4 --persistent_workers True` |

### 2. NCCL Timeout / Hang

| Symptom | Cause | Fix |
|---|---|---|
| Training hangs at step N | NCCL AllReduce timeout | Set `NCCL_TIMEOUT=1800`, check network between nodes |
| Timeout after checkpoint | Slow disk I/O during save | Use `--save_strategy epoch` or async save |
| Hang at start | Firewall blocking NCCL ports | Open ports 29500-29600, or use `NCCL_SOCKET_IFNAME=eth0` |

### 3. Loss Spike / NaN

| Symptom | Cause | Fix |
|---|---|---|
| Loss spike every N steps | Bad data sample (corrupted audio/empty transcript) | Filter training data: remove samples with duration < 0.5s or > 30s |
| NaN loss | Learning rate too high | Reduce `--lr`, add warmup (`--warmup_ratio 0.1`) |
| Loss doesn't decrease | Audio preprocessing mismatch | Verify sample rate = 16kHz, mono channel |

### 4. Training Speed Optimization

| Technique | Speedup | Notes |
|---|---|---|
| BF16 mixed precision | ~2x vs FP32 | Default in Qwen3-ASR SFT script |
| Gradient accumulation | Memory reduction | `--grad_acc 4` = effective batch 32 with bs=8 |
| DeepSpeed ZeRO-2 | Memory reduction | Best balance for < 10B models |
| `--num_workers 4` | Dataloader parallelism | Prevents GPU idle waiting for data |
| Pin memory | Faster H2D transfer | `--pin_memory True` |
| Prefetch factor | Pipeline data loading | `--prefetch_factor 2` |
| Gradient checkpointing | 50% less memory, 20% slower | Trade speed for larger batch/model |

### 5. Checkpoint & Resume

```bash
# Resume from last checkpoint
python qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file /path/to/train.jsonl \
  --output_dir /path/to/output \
  --resume True \
  --resume_from /path/to/output/checkpoint-1000
```

### 6. Quantized Training (QLoRA)

```bash
# QLoRA fine-tuning (if supported by official script)
pip install bitsandbytes peft

# Manual QLoRA approach if official script doesn't support it:
python -c "
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type='nf4',
    bnb_4bit_compute_dtype=torch.bfloat16
)
model = AutoModelForCausalLM.from_pretrained(
    'Qwen/Qwen3-ASR-0.6B',
    quantization_config=bnb_config,
    trust_remote_code=True
)
lora_config = LoraConfig(r=16, lora_alpha=32, target_modules=['q_proj','v_proj'])
model = get_peft_model(model, lora_config)
# Then use HF Trainer as usual
"
```

**Known limitation**: `Qwen3ASRConfig` may not be compatible with standard `AutoModelForCausalLM`. Use `qwen_asr` package's model loading instead.

## Azure-Specific Recommendations

| Customer Problem | Azure Solution |
|---|---|
| Data storage/transfer bottleneck | Azure Blob + AzCopy accelerated transfer + NVMe cache on VM |
| Training node instability | ND-series VMs with InfiniBand, auto-restart on failure |
| Multi-node NCCL | Azure VMSS with proximity placement group |
| Checkpoint storage | Azure Files Premium (NFS) mounted to all nodes |
| Capacity planning | Right-size GPU pool for training and production windows |
| Monitoring | Azure ML job monitoring or custom Prometheus + Grafana |

## Onsite Questions for Customer

1. How many GPUs/nodes are you training on currently?
2. What is your current training throughput (samples/sec or tokens/sec)?
3. What DeepSpeed stage are you using (ZeRO-1/2/3)?
4. Have you experienced NCCL timeouts or loss spikes? At what scale?
5. What is your audio data format and average duration?
6. Are you using gradient checkpointing?
7. What is your checkpoint save frequency and resume strategy?
