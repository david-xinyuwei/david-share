# MAI-Image-2 vs GPT-Image-1.5: Azure AI Image Generation Benchmark

A fair, head-to-head latency benchmark comparing **MAI-Image-2** and **GPT-Image-1.5** on Azure, using identical prompts, resolution, quality settings, and testing environment.

## Key Results

| Metric | MAI-Image-2 | GPT-Image-1.5 | Difference |
|--------|:-----------:|:-------------:|:----------:|
| Pass Rate | 11/11 (100%) | 11/11 (100%) | Tie |
| **Avg Latency** | **22.7s** | **46.7s** | **MAI 2.1x faster** |
| Latency Range | 20.0s – 32.7s | 43.3s – 49.2s | MAI more stable |
| Resolution | 1024x1024 RGB | 1024x1024 RGB | Identical |
| Quality | high | high | Identical |

> MAI-Image-2 is consistently **2.1x faster** than GPT-Image-1.5 across all 11 test prompts, with no exceptions.

## Fair Comparison: 7-Dimension Alignment

To ensure a valid comparison, we aligned **all controllable variables** and only varied the model:

| Dimension | MAI-Image-2 | GPT-Image-1.5 | Aligned |
|-----------|:-----------:|:-------------:|:-------:|
| Prompt | 11 Surreal-style prompts | Same 11 prompts | ✅ |
| Resolution | 1024×1024 | 1024×1024 | ✅ |
| Quality | `high` (explicit) | `high` (explicit) | ✅ |
| Output Format | PNG 8-bit RGB | PNG 8-bit RGB | ✅ |
| Network | Same VM (East US) | Same VM (East US) | ✅ |
| Test Date | 2026-04-03 | 2026-04-03 | ✅ |
| **Model (Variable)** | MAI-Image-2 | gpt-image-1.5 | 🔀 |

Both models ran in the same script (`fair_comparison_r2.py`), alternating per prompt to minimize network/time bias.

## Per-Prompt Latency Comparison

| # | Prompt | MAI-Image-2 | GPT-Image-1.5 | Speedup |
|:-:|:-------|:-----------:|:-------------:|:-------:|
| 1 | Chrome kimono metallic maiden | 22.2s | 49.0s | 2.2x |
| 2 | Portal into mythical forest | 20.4s | 47.8s | 2.3x |
| 3 | Tiny astronaut hatching on moon | 20.6s | 49.2s | 2.4x |
| 4 | LOTR tiny red dragon macro | 20.0s | 43.6s | 2.2x |
| 5 | Fluffy creature fantasy | 20.3s | 48.3s | 2.4x |
| 6 | Hidden jungle cenote | 24.9s | 46.2s | 1.9x |
| 7 | Tech-savvy girl holographic UI | 32.7s | 46.7s | 1.4x |
| 8 | Universe fractal worlds | 24.6s | 48.2s | 2.0x |
| 9 | Fractal mythical creature | 21.7s | 43.3s | 2.0x |
| 10 | Angry cat playing drums | 21.4s | 43.9s | 2.0x |
| 11 | Monkey playing music | 20.5s | 47.0s | 2.3x |
| **AVG** | | **22.7s** | **46.7s** | **2.1x** |

## Side-by-Side Image Comparison

### Test 1: Chrome Kimono Metallic Maiden

| MAI-Image-2 (22.2s) | GPT-Image-1.5 (49.0s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/01_test.png) | ![GPT](images/gpt-image-1.5/01_test.png) |

### Test 2: Portal into Mythical Forest

| MAI-Image-2 (20.4s) | GPT-Image-1.5 (47.8s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/02_test.png) | ![GPT](images/gpt-image-1.5/02_test.png) |

### Test 3: Tiny Astronaut on Moon

| MAI-Image-2 (20.6s) | GPT-Image-1.5 (49.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/03_test.png) | ![GPT](images/gpt-image-1.5/03_test.png) |

### Test 4: LOTR Tiny Red Dragon

| MAI-Image-2 (20.0s) | GPT-Image-1.5 (43.6s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/04_test.png) | ![GPT](images/gpt-image-1.5/04_test.png) |

### Test 5: Fluffy Fantasy Creature

| MAI-Image-2 (20.3s) | GPT-Image-1.5 (48.3s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/05_test.png) | ![GPT](images/gpt-image-1.5/05_test.png) |

### Test 6: Hidden Jungle Cenote

| MAI-Image-2 (24.9s) | GPT-Image-1.5 (46.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/06_test.png) | ![GPT](images/gpt-image-1.5/06_test.png) |

### Test 7: Tech-Savvy Girl with Holographic UI

| MAI-Image-2 (32.7s) | GPT-Image-1.5 (46.7s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/07_test.png) | ![GPT](images/gpt-image-1.5/07_test.png) |

### Test 8: Universe Fractal Worlds

| MAI-Image-2 (24.6s) | GPT-Image-1.5 (48.2s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/08_test.png) | ![GPT](images/gpt-image-1.5/08_test.png) |

### Test 9: Fractal Mythical Creature

| MAI-Image-2 (21.7s) | GPT-Image-1.5 (43.3s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/09_test.png) | ![GPT](images/gpt-image-1.5/09_test.png) |

### Test 10: Angry Cat Playing Drums

| MAI-Image-2 (21.4s) | GPT-Image-1.5 (43.9s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/10_test.png) | ![GPT](images/gpt-image-1.5/10_test.png) |

### Test 11: Monkey Playing Music

| MAI-Image-2 (20.5s) | GPT-Image-1.5 (47.0s) |
|:---:|:---:|
| ![MAI](images/mai-image-2/11_test.png) | ![GPT](images/gpt-image-1.5/11_test.png) |

## API Differences

| Feature | MAI-Image-2 | GPT-Image-1.5 |
|---------|:-----------:|:-------------:|
| API Path | `/mai/v1/images/generations` | `/openai/deployments/{name}/images/generations` |
| Auth | **Entra ID only** | Key + Entra ID |
| Size Param | `width` / `height` (integers) | `size` (string, e.g. `"1024x1024"`) |
| Model Param | Required (`"MAI-Image-2"`) | Not needed (in deployment) |
| Quality Param | `low` / `medium` / `high` | `low` / `medium` / `high` |
| Pixel Resolution | 1024x1024 | 1024x1024 |
| Output Format | PNG 8-bit RGB | PNG 8-bit RGB |

## How to Reproduce

### Prerequisites

- Azure subscription with Azure AI Services resource
- MAI-Image-2 and gpt-image-1.5 model deployments
- Python 3.x with `requests` package
- Azure CLI (`az`) logged in

### Run the Fair Comparison

```bash
# Clone this repo
git clone https://github.com/david-xinyuwei/MAI-Image-2-vs-GPT-Image-Benchmark.git
cd MAI-Image-2-vs-GPT-Image-Benchmark

# Edit scripts/fair_comparison_r2.py to set your resource names and API key
# Then run:
pip install requests
python scripts/fair_comparison_r2.py
```

### Run Individual Model Tests

```bash
# MAI-Image-2 only (requires Entra ID auth)
python scripts/test_mai_image2.py

# GPT-Image-1.5 only (supports Key auth)
python scripts/test_gpt_image15.py
```

## Repository Structure

```
.
├── README.md
├── prompts.csv                          # 11 Surreal-style test prompts
├── scripts/
│   ├── fair_comparison_r2.py            # Unified comparison script (quality=high)
│   ├── test_mai_image2.py               # MAI-Image-2 standalone test
│   └── test_gpt_image15.py             # GPT-Image-1.5 standalone test
└── images/
    ├── mai-image-2/                     # 11 generated images from MAI-Image-2
    │   ├── 01_test.png ... 11_test.png
    └── gpt-image-1.5/                   # 11 generated images from GPT-Image-1.5
        ├── 01_test.png ... 11_test.png
```

## Expected Output

When you run `fair_comparison_r2.py`, you should see output like:

```
======================================================================
MAI-Image-2 vs GPT-Image-1.5 Fair Comparison (Round 2)
Unified params: 1024x1024, quality=high, b64_json
======================================================================
Prompts: 11
Entra token acquired
======================================================================

[1/11] Chrome kimono, a maiden surrounded by metallic flowers, earrings, orna...
  MAI: OK 22.2s 1473KB
  GPT: OK 49.0s 2212KB
...
======================================================================
RESULTS SUMMARY (quality=high, 1024x1024)
======================================================================
  # Prompt                      MAI Time   MAI KB   GPT Time   GPT KB   Ratio
----------------------------------------------------------------------
  1 Chrome kimono, a maide...      22.2s    1473      49.0s    2212    2.2x
  ...
----------------------------------------------------------------------
AVG                                22.7s    1507      46.7s    2035    2.1x

MAI: 11/11 passed | GPT: 11/11 passed
```

## Analysis

### Why is MAI-Image-2 faster?

MAI-Image-2 uses a proprietary MAI API path (`/mai/v1/`) that is separate from the standard OpenAI API infrastructure. This suggests Microsoft has optimized the serving infrastructure specifically for MAI models, resulting in consistently lower latency across all prompt types.

### Quality Considerations

This benchmark measures **latency only**, not subjective image quality. Both models produce high-quality 1024x1024 images at `quality=high`. Visual quality comparison should be done by examining the side-by-side images above — both models demonstrate strong prompt adherence and artistic quality.

### Recommendations

- For **latency-sensitive** applications (real-time UX, batch processing), MAI-Image-2 provides a clear 2x speed advantage
- For applications using the **standard OpenAI API**, GPT-Image-1.5 offers the benefit of a familiar API format and Key-based auth support
- Consider testing with your specific prompt types, as latency may vary by prompt complexity

## Cleanup

To delete the Azure deployments after testing:

```bash
# Delete gpt-image-1.5 deployment
az cognitiveservices account deployment delete \
  --name <your-resource-name> \
  --resource-group <your-resource-group> \
  --deployment-name gpt-image-1-5

# Delete MAI-Image-2 deployment
az cognitiveservices account deployment delete \
  --name <your-mai-resource> \
  --resource-group <your-resource-group> \
  --deployment-name mai-image-2
```

## Test Environment

- **Azure Region**: East US
- **Test Date**: April 3, 2026
- **Test Machine**: Azure VM in East US
- **Python**: 3.x + requests

## Author

Xinyu Wei (魏新宇)
