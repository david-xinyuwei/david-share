# 模型

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

**VibeVoice** is a long-form, multi-speaker conversational speech generation framework proposed by Microsoft in 2025. It combines a Large Language Model (LLM) with a **Next-Token Diffusion** decoder and an ultra-low frame rate continuous acoustic tokenizer, capable of generating up to **90 minutes** of high-fidelity dialogue with up to **4 speakers** in a single context. It outperforms many existing systems in both perceived audio quality and speaker consistency.

---

### 模型
- **Versions**: VibeVoice-1.5B, VibeVoice-7B (core LLM based on Qwen2.5 series)
- **Sampling rate**: 24 kHz  
- **Acoustic tokenizer frame rate**: ~7.5 Hz (~3200× compression)
- **Inference settings**: ~10 denoising steps, supports CFG (~1.3) and DPM-Solver++ acceleration
- **Context window**: up to ~64K tokens (≈90 minutes of audio per generation)
- **Language support**: Best performance in English and Chinese

---

### 架构
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

### 功能特性
- **Dual-tokenizer design**: Acoustic (σ-VAE) + Semantic (ASR proxy)
- **Low frame rate, high fidelity**: ~2:1 acoustic tokens to BPE tokens
- **Next-token diffusion**: Predicts continuous acoustic latent at each token
- **Multi-speaker control**: Explicit role IDs + reference audio embeddings
- **Efficient long-context modeling**: Large window (32k–65k tokens) with memory-optimized inference

---

### 性能
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

### 限制
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

### 使用方法
- This model is for research and educational purposes only
- Do not perform voice cloning without explicit permission
- Publishing or sharing audio generated by this model must comply with local laws and platform policies

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/2.png)



### Detailed work process

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/5.png)

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/6.png)

##### **0. 输入（User Input）**

- **音色选择**：UI 中选择要使用的声音（Voice Profile）
   → 系统加载对应的 **说话人嵌入**（Speaker Embedding）用于生成 Acoustic Latent

- **文本脚本**：输入带角色标识的台词

  ```
  [角色A] Hi Bob, long time no see.
  [角色B] I’m good. Are you free this weekend?
  ```

##### **1. 特征提取（左下角 → Start）**

1. **Acoustic Latent（蓝色斜纹 + A）**
   - 来源：音色的参考音频（或预存 Voice Profile）
   - 由 **声学分词器（Acoustic Tokenizer, σ-VAE）** 编码得到
   - 维度：64-d，帧率约 7.5 Hz
   - 描述“声音该怎么说”（音色、韵律、情绪）
2. **Semantic Latent（橙色斜纹 + S）**
   - 来源：文本脚本或对应的转写语音
   - 由 **语义分词器（Semantic Tokenizer）** 编码得到
   - 维度：128-d，帧率约 7.5 Hz
   - 描述“应该说什么”（语义结构、句子节奏）

##### **2. 混合输入序列（Hybrid Sequence Assembly）**

- 将 **角色ID + Acoustic Latent + Semantic Latent + 文本token** 按时间顺序拼接
- 作用：给模型完整条件，确保在长对话中：
  - 正确的角色声音（Acoustic Latent）
  - 对应的内容（Semantic Latent）
  - 文本细节（token）

##### **3. LLM 处理（中间 VibeVoice 模块）**

- 核心：Qwen2 架构 LLM（28 层，1.5B/7B 参数，长上下文 32K–65K token）
- 根据混合序列理解上下文，保持不同角色的发音一致、对话内容连贯

##### **4. 扩散生成（右边虚线框）**

- **Diffusion Head（D）**：
   在每个 token 位置预测本片段的 **Acoustic Latent 序列**
- **Acoustic Decoder（A）**：
   将 Acoustic Latent 还原为 24 kHz 高保真波形输出

##### **5. 循环生成至结束**

每个虚线框就是一句或一小段音频：

```
条件（文本+Acoustic Latent+Semantic Latent）→ D预测 → A解码 → 音频
```

- 遇到角色切换时，替换角色ID和对应 Acoustic Latent
- 片段生成完即可播放，支持流式输出
- 持续到 <End> 标记，可长达 90 分钟

##### **总结**

```
音色 → Acoustic Latent（怎么说）
脚本 → Semantic Latent（说什么）
Acoustic Latent + Semantic Latent + 文本 → LLM → Diffusion Head → Acoustic Decoder → 音频输出
```



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

### Demo on A10 with 3 speakers in Chinese

https://github.com/user-attachments/assets/<resource-id>

### Demo on A10 with 2 speakers in Chinese with prompt emotion

Script：

```
Speaker 1: 大家好,今天啊……可真是个好日子啊？！

Speaker 2: 是啊是啊；天气这么好……心情也跟着亮堂起来啦～而且——我们今天要聊的，可是——超级有意思的东西呢……  

Speaker 1: 嗯？真的假的——我可是——专门推了个会——就为了过来听你们的——“神秘话题”哦？！该不会是……什么……AI阴谋论吧？

Speaker 2: 哎呀——别闹别闹！咳咳……其实啊——我们今天的主题，是……“微软全新的——VibeVoice 模型”！你们可知道吗？它呀——能让四个人——连说带唱——聊足九十分钟——不带重样的！啧——厉害吧？！  

Speaker 1: 别急——我来补充两句……它的声音啊，可不只是——“像真的”那么简单哦……那种……你知道的——轻轻的颤音、细微的呼吸声、还有那种……嗯——就是——特别自然的感觉啦～  

Speaker 2: 哇——你这么一说——我突然——鸡皮疙瘩都起来啦！那……能不能——让它模仿一下四声杜鹃的叫声 "咕咕咕咕"

Speaker 1: David——你这也太假了吧？！ 不过啊——VibeVoice——还真就……能生动得——“以假乱真”哦？  

Speaker 2: 嗯——不过啊——我们也得——提醒大家——科技很酷没错……但……也得负责任地——去用它呀……  

Speaker 1: 对——就像今天……我们是为了——开心、学习、分享——而来——唉——这才是最棒的……  
```

https://github.com/user-attachments/assets/<resource-id>

### Demo on A100 with  2 speakers in English and Chinese

Running on Azure A100 GPU VM after load model to GPU：

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/1.png)

**English Version Demo**:

https://github.com/user-attachments/assets/<resource-id>

**Chinese Version Demo:**

https://github.com/user-attachments/assets/<resource-id>









#### Refer to:

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*





