## VibeVoice Test

VibeVoice is a novel framework designed for generating **expressive, long-form, multi-speaker** conversational audio, such as podcasts, from text. It addresses significant challenges in traditional Text-to-Speech (TTS) systems, particularly in scalability, speaker consistency, and natural turn-taking. A core innovation of VibeVoice is its use of continuous speech tokenizers (Acoustic and Semantic) operating at an ultra-low frame rate of 7.5 Hz. 

These tokenizers efficiently preserve audio fidelity while significantly boosting computational efficiency for processing long sequences. VibeVoice employs a next-token diffusion framework, leveraging a Large Language Model (LLM) to understand textual context and dialogue flow, and a diffusion head to generate high-fidelity acoustic details. The model can synthesize speech up to 90 minutes long with up to 4 distinct speakers, surpassing the typical 1-2 speaker limits of many prior models.

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/2.png)

### Useful Link

Model weights on HF

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

Github project：

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*



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

