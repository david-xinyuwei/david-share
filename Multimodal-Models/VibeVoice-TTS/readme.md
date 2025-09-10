# Model Introduction: VibeVoice

**VibeVoice** is a long-form, multi-speaker conversational speech generation framework proposed by Microsoft in 2025. It combines a Large Language Model (LLM) with a **Next-Token Diffusion** decoder and an ultra-low frame rate continuous acoustic tokenizer, capable of generating up to **90 minutes** of high-fidelity dialogue with up to **4 speakers** in a single context. It outperforms many existing systems in both perceived audio quality and speaker consistency.

### Model Scales and Parameters
- **Versions**: VibeVoice-1.5B, VibeVoice-7B (core LLM based on Qwen2.5 series)
- **Sampling rate**: 24 kHz  
- **Acoustic tokenizer frame rate**: ~7.5 Hz (~3200× compression)
- **Inference settings**: ~10 denoising steps, supports CFG (~1.3) and DPM-Solver++ acceleration
- **Context window**: up to ~64K tokens (≈90 minutes of audio per generation)
- **Language support**: Best performance in English and Chinese

### Key Features
- **Dual-tokenizer design**: Acoustic tokenizer (σ-VAE) and semantic tokenizer (ASR proxy task)
- **Low frame rate, high fidelity**: Acoustic tokens to text BPE ratio ~2:1, reducing long-context modeling overhead
- **Next-token diffusion**: Predicts acoustic latent at each LLM token for stable long-form generation
- **Multi-speaker control**: Combines reference voice + text script input to ensure timbre and semantic consistency
- **Efficient generation**: Achieves usable quality with few denoising steps; acceleration improves throughput

### Performance Highlights 
- **Subjective long-conversation listening tests**: 7B model scores equal to or better than competitors in realism, richness, and preference
- **Objective metrics**:
  - WER (Whisper large-v3 / Nemo): 1.5B slightly better
  - Speaker similarity (SIM): 7B significantly higher
- **Short-utterance generalization**: Maintains low CER/WER and high SIM on SEED Chinese/English test sets
- **Tokenizer reconstruction quality**: Leading PESQ, STOI, and UTMOS compared with similar models

### Advantages
- Stable generation of long-form audio
- Smooth multi-speaker switching with consistent timbre
- Natural expression, emotional richness
- High computational efficiency, scalable for long sequences

### Limitations
- Limited language effectiveness beyond English and Chinese
- No support for overlapping speech or non-speech audio
- Potential misuse risks due to high-fidelity voice cloning capability
- Official report advises against direct commercial or production deployment without further testing

### Suitable Use Cases
- Podcasts, interviews, storytelling, audio dramas
- Educational and training content with multiple speakers
- Offline conversational voice agent demos
- Authorized dubbing and accessibility reading

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

Running on Azure A10 GPU VM：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/3.png)

## Demo on A10 with 3 speakers in Chinese

https://github.com/user-attachments/assets/4023a592-666c-4e60-9352-60f6ace068af



### Demo on A100 with  2 speakers in English and Chinese

Running on Azure A100 GPU VM：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/1.png)

**English Version Demo**:

https://github.com/user-attachments/assets/26533ef2-ba0e-4fea-9a45-fd72ec5b0918

**Chinese Version Demo:**

https://github.com/user-attachments/assets/976c0bb7-98c3-4007-ad78-0f324d595fd4



#### Refer to:

```
Model weights on HF

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

Github project：

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*


```



