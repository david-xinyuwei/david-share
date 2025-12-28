# BiomedParse Fine-Tuning Guide

Fine-tuning Microsoft's BiomedParse medical image segmentation model for custom datasets.

**Author**: Xinyu Wei (Microsoft AI and Apps GBB)  
**Model**: [microsoft/BiomedParse](https://github.com/microsoft/BiomedParse)  
**Paper**: [Nature Methods 2024](https://aka.ms/biomedparse-paper)  
**Test Environment**: NVIDIA A10 24GB GPU

---

## 🎯 Results Summary

| Experiment | Mode | Task | Before Dice | After Dice | **Improvement** |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **2D CT Organs** | 2D | left/right kidney, liver | 0.6% | **91.0%** | 🏆 **+90.4%** |
| **3D Adrenal Glands** | 3D | left/right adrenal gland | 73.7% | **90.3%** | **+16.6%** |

### Key Findings

- 🏆 **Correct prompt extraction is critical**: Using "left kidney" instead of "kidney" improved Dice from 0% to 97%
- 📈 **3D mode works well for small organs**: Adrenal glands achieved 90%+ Dice
- ⚠️ **Input must be 0-255 range**: Do NOT normalize to 0-1

---

## 📊 Detailed Results

### 2D CT Organ Segmentation

![2D Comparison](./images/2d_comparison_final.png)

*GT=Green, Before=Orange, After=Cyan. The "Before" model predicts both kidneys when asked for "left kidney", while "After" correctly segments only the target organ.*

| Test Image | Prompt | Before | After | Improvement |
|------------|--------|--------|-------|-------------|
| slice025 | left kidney | 0.0% | **97.7%** | +97.7% |
| slice025 | right kidney | 0.0% | **97.6%** | +97.6% |
| slice030 | left kidney | 0.0% | **96.0%** | +96.0% |
| slice030 | liver | 3.0% | **92.0%** | +89.0% |
| slice030 | right kidney | 0.0% | **94.2%** | +94.2% |
| slice035 | left kidney | 0.4% | **68.7%** | +68.3% |
| **Average** | - | **0.6%** | **91.0%** | **+90.4%** |

### 3D Adrenal Gland Segmentation

![3D Comparison](./images/3d_finetune_comparison_v4.png)

*Green=Correct, Red=False Positive, Orange=Missed region*

| Organ | Before | After | Improvement |
|-------|--------|-------|-------------|
| Left Adrenal | 70.9% | **87.7%** | +16.8% |
| Right Adrenal | 76.4% | **92.8%** | +16.4% |
| **Average** | **73.7%** | **90.3%** | **+16.6%** |

---

## 🚀 Quick Start

### 2D Fine-tuning

```bash
# Clone BiomedParse
git clone https://github.com/microsoft/BiomedParse.git
cd BiomedParse

# Set environment variable
export BIOMEDPARSE_ROOT=$(pwd)

# Run 2D fine-tuning
python finetune_2d_prompt_fix.py \
    --data_dir /path/to/your/2d_data \
    --output_dir ./output \
    --epochs 30 \
    --lr 1e-5
```

### 3D Fine-tuning

```bash
python finetune_3d_adrenal.py \
    --data_path /path/to/CT_volume.npz \
    --output_dir ./output \
    --epochs 100 \
    --lr 1e-5
```

---

## 📁 Data Format

### 2D Dataset Structure

```
data_dir/
├── train/
│   ├── slice001_left_kidney.png      # Filename = prompt
│   ├── slice001_right_kidney.png
│   └── ...
├── train_mask/
│   ├── slice001_left_kidney_mask.png
│   └── ...
├── test/
└── test_mask/
```

**Important**: The filename (minus extension) becomes the text prompt!
- `slice001_left_kidney.png` → prompt = `"left kidney"`
- `slice002_liver.png` → prompt = `"liver"`

### 3D NPZ Format

```python
{
    "volume": np.array,           # Shape: (D, H, W), 0-255 range
    "left_adrenal_gland": np.array,  # Binary mask
    "right_adrenal_gland": np.array  # Binary mask
}
```

---

## 🏗️ Architecture

```mermaid
graph TD
    subgraph BiomedParse["BiomedParse v2 (371M params)"]
        IMG[CT Image<br/>1024×1024] --> ENC[Image Encoder<br/>SAM-based]
        TXT[Text Prompt<br/>'left kidney'] --> TENC[Text Encoder<br/>BiomedCLIP]
        ENC --> DEC[Transformer Decoder]
        TENC --> DEC
        DEC --> HEAD[Mask Head]
        HEAD --> OUT[Segmentation Mask<br/>1024×1024]
    end
    
    style IMG fill:#e1f5fe
    style TXT fill:#fff3e0
    style OUT fill:#e8f5e9
```

### 2D vs 3D Mode

```mermaid
graph LR
    subgraph 2D["2D Mode"]
        A1[Single Slice] --> B1[1024×1024 RGB]
        B1 --> C1[Per-slice Prediction]
    end
    
    subgraph 3D["3D Mode"]
        A2[Volume Stack] --> B2[D×H×W Grayscale]
        B2 --> C2[Volumetric Prediction]
    end
```

---

## ⚠️ Known Issues & Solutions

### Issue 1: Image Normalization

**Symptom**: Model outputs empty or incorrect masks

**Root Cause**: BiomedParse expects input in **0-255 range**, not 0-1

```python
# ❌ INCORRECT
img = img / 255.0

# ✅ CORRECT
img = img.astype(np.float32)  # Keep 0-255 range
```

### Issue 2: Prompt Mismatch

**Symptom**: Model predicts both kidneys when asked for "left kidney"

**Root Cause**: Prompt extraction returns "kidney" instead of "left kidney"

```python
# ❌ INCORRECT: Returns "kidney"
organ = fname.split("_")[-1].replace(".png", "")

# ✅ CORRECT: Returns "left kidney"
def get_prompt(fname):
    base = fname.replace(".png", "")
    parts = base.split("_")[1:]  # Skip slice number
    return " ".join(parts)
```

### Issue 3: Hydra Configuration Conflict

**Symptom**: `GlobalHydra is already initialized` error on second model load

**Solution**: Clear Hydra state before reinitializing

```python
from hydra.core.global_hydra import GlobalHydra
GlobalHydra.instance().clear()
initialize(config_path="configs/model", ...)
```

### Issue 4: Batch Size with Different Prompts

**Symptom**: Inconsistent predictions when batch contains different prompts

**Solution**: Use `batch_size=1` when prompts vary per sample

```python
DataLoader(dataset, batch_size=1)  # For different prompts per sample
```

---

## 🖥️ Environment

| Component | Value |
|-----------|-------|
| GPU | NVIDIA A10 24GB |
| Framework | PyTorch 2.0+ |
| Model | BiomedParse v2 (371M params) |
| Precision | FP16 (AMP) |

### Training Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Learning Rate | 1e-5 | Prevents catastrophic forgetting |
| Optimizer | AdamW | weight_decay=0.01 for regularization |
| Loss | Dice Loss | Optimal for segmentation tasks |
| Scheduler | CosineAnnealingLR | Smooth convergence |

---

## 📁 File Structure

```
BiomedParse-Fine-Tuning/
├── README.md                    # This file (English)
├── README-CN.md                 # Chinese version
├── finetune_2d_prompt_fix.py    # 2D training with correct prompt
├── finetune_3d_adrenal.py       # 3D adrenal gland training
├── visualize_2d.py              # 2D comparison generator
├── visualize_3d.py              # 3D comparison generator
└── images/
    ├── 2d_comparison_final.png  # 2D results
    └── 3d_finetune_comparison_v4.png  # 3D results
```

---

## 📚 References

- [BiomedParse GitHub](https://github.com/microsoft/BiomedParse)
- [BiomedParse Paper](https://aka.ms/biomedparse-paper) - Nature Methods, 2024
- [CT-AMOS Dataset](https://amos22.grand-challenge.org/)

---

## 🔗 Related Projects

- **[MedImageParse Agent](../../Agents/MedImageParse/)** - AI Agent application with Streamlit UI

---

*Verified on NVIDIA A10 24GB | December 2024*
