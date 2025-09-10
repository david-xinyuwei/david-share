# Model Introduction: VibeVoice

**VibeVoice** is a long-form, multi-speaker conversational speech generation framework proposed by Microsoft in 2025. It combines a Large Language Model (LLM) with a **Next-Token Diffusion** decoder and an ultra-low frame rate continuous acoustic tokenizer, capable of generating up to **90 minutes** of high-fidelity dialogue with up to **4 speakers** in a single context. It outperforms many existing systems in both perceived audio quality and speaker consistency.

---

### Model Scales and Parameters
- **Versions**: VibeVoice-1.5B, VibeVoice-7B (core LLM based on Qwen2.5 series)
- **Sampling rate**: 24 kHz  
- **Acoustic tokenizer frame rate**: ~7.5 Hz (~3200× compression)
- **Inference settings**: ~10 denoising steps, supports CFG (~1.3) and DPM-Solver++ acceleration
- **Context window**: up to ~64K tokens (≈90 minutes of audio per generation)
- **Language support**: Best performance in English and Chinese

---

### Architecture Details
**Based on the provided configuration files:**

| Version | LLM Layers | Hidden Size | FFN Size | Attention Heads | KV Heads | Context Window | Acoustic Tokenizer VAE Dim | Semantic Tokenizer VAE Dim |
|---------|-----------|-------------|----------|----------------|----------|----------------|---------------------------|----------------------------|
| 1.5B    | 28        | 1,536       | 8,960    | 12             | 2        | 65,536         | 64                        | 128                        |
| 7B      | 28        | 3,584       | 18,944   | 28             | 4        | 32,768         | 64                        | 128                        |

- **Acoustic Tokenizer**  
  - σ-VAE with symmetric encoder–decoder  
  - Encoder depth: `3-3-3-3-3-3-8` layers, 32 filters per layer  
  - Downsampling ratios: `[8, 5, 5, 4, 2, 2]` → 3200× compression (24kHz → ~7.5 Hz)  
  - Mixer layer: depthwise conv + RMSNorm  
  - Latent dim: 64, fixed std dev (σ=0.5) for stable autoregression  

- **Semantic Tokenizer**  
  - Same encoder depth pattern as acoustic tokenizer  
  - VAE dim = 128, deterministic (`std_dist_type=none`)  
  - Used for ASR proxy pretraining, decoder discarded later  

- **Core LLM**  
  - Model type: Qwen2  
  - 28 Transformer decoder layers, silu activation, RMSNorm  
  - Rope positional embeddings (`rope_theta=1,000,000`)  
  - Context window: 65k (1.5B) / 32k (7B) tokens  

- **Diffusion Head**
  - Layers: 4, hidden size matches LLM  
  - DDPM with cosine beta schedule, 1,000 training steps, 10–20 inference steps  
  - Prediction type: v_prediction  
  - CFG blending between conditioned and unconditional paths  

---

### Multi-Speaker Dialogue Mechanism
- **Input Composition** per dialogue turn:
  1. Reference speaker embedding (from short audio clip, capturing timbre & prosody)
  2. Text script embedding (semantic content)
  3. Role identifier (speaker ID)  
- These are serialized into a single sequence passed into the LLM.  
- LLM **maintains per-speaker state** to ensure timbre consistency across turns.  
- Speaker changes are triggered by inserting the appropriate role ID + reference embedding at token boundaries.  
- Diffusion head predicts acoustic latent sequences per speech segment → acoustic decoder reconstructs waveform.  
- Supports **streaming generation** — output audio can be played while new tokens are produced.

---

### Key Features
- **Dual-tokenizer design**: Acoustic (σ-VAE) + Semantic (ASR proxy)
- **Low frame rate, high fidelity**: ~2:1 acoustic tokens to BPE tokens
- **Next-token diffusion**: Predicts continuous acoustic latent at each token
- **Multi-speaker control**: Explicit role IDs + reference audio embeddings
- **Efficient long-context modeling**: Large window (32k–65k tokens) with memory-optimized inference

---

### Performance Highlights (from the paper)
- **Subjective long-conversation listening tests**: 7B model scores equal to or better than competitors in realism, richness, and preference
- **Objective metrics**:
  - WER (Whisper large-v3 / Nemo): 1.5B slightly better
  - Speaker similarity (SIM): 7B significantly higher
- **Short-utterance generalization**: Maintains low CER/WER and high SIM on SEED Chinese/English test sets
- **Tokenizer reconstruction quality**: Leading PESQ, STOI, and UTMOS compared with similar models

---

### Advantages
- Stable generation of long-form audio
- Smooth multi-speaker switching with consistent timbre
- Natural expression, emotional richness
- High computational efficiency, scalable for long sequences

---

### Limitations
- Limited language effectiveness beyond English and Chinese
- No support for overlapping speech or non-speech audio
- Potential misuse risks due to high-fidelity voice cloning capability
- Official report advises against direct commercial or production deployment without further testing

---

### Suitable Use Cases
- Podcasts, interviews, storytelling, audio dramas
- Educational and training content with multiple speakers
- Offline conversational voice agent demos
- Authorized dubbing and accessibility reading

---

### Usage Notes
- This model is for research and educational purposes only
- Do not perform voice cloning without explicit permission
- Publishing or sharing audio generated by this model must comply with local laws and platform policies

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/2.png)

### Fast PoC steps

You could run VibeVoice model on Edge，if you run VibeVoice-7B, it will need ~20GB VRAM, NVIDIA A10 is enough.

```
conda create --name=VibeVoice python=3.11
conda activate VibeVoice
git clone https://github.com/vibevoice-community/VibeVoice.git
cd VibeVoice/
pip install -e .
apt-get install -y ffmpeg
python demo/gradio_demo.py --model_path vibevoice/VibeVoice-7B  --share
```

Running on Azure A10 GPU VM during model inference：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/3.png)

## Demo on A10 with 3 speakers in Chinese

https://github.com/user-attachments/assets/4023a592-666c-4e60-9352-60f6ace068af



### Demo on A100 with  2 speakers in English and Chinese

Running on Azure A100 GPU VM after load model to GPU：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/1.png)

**English Version Demo**:

https://github.com/user-attachments/assets/26533ef2-ba0e-4fea-9a45-fd72ec5b0918

**Chinese Version Demo:**

https://github.com/user-attachments/assets/976c0bb7-98c3-4007-ad78-0f324d595fd4



#### Refer to:

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*





```
## VibeVoice Multi-Speaker Architecture

```mermaid
flowchart LR
    subgraph Input["User Input"]
        A[Reference Audio 1 to N\n(Speaker Embeddings)]
        B[Text Script\n(with Role IDs)]
    end

    subgraph Tokenizers
        A --> C1[Acoustic Tokenizer\n(σ-VAE, 64-d, ~7.5Hz)]
        B --> C2[Semantic Tokenizer\n(VAE 128-d, deterministic)]
    end

    subgraph SequenceAssembly["Hybrid Sequence Assembly"]
        C1 --> D[Concat Acoustic & Semantic Tokens\n+ Role Identifiers]
        C2 --> D
    end

    subgraph LLM["Core LLM (Qwen2.5-based)"]
        D --> E[28-layer Transformer\nContext: 32K–65K Tokens]
    end

    subgraph Diffusion["Next-Token Diffusion Head"]
        E --> F[4-layer DDPM Head\n(v_prediction, CFG ~1.3)]
    end

    subgraph Decoder["Acoustic Decoder"]
        F --> G[Waveform Reconstruction\n24 kHz High Fidelity Audio]
    end

    subgraph Output["Streaming or Full Audio Output"]
        G --> H[Multi-Speaker Audio\n(Up to 4 Speakers, 90 min)]
    end
```
