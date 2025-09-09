## VibeVoice Test

VibeVoice is a novel framework designed for generating **expressive, long-form, multi-speaker** conversational audio, such as podcasts, from text. It addresses significant challenges in traditional Text-to-Speech (TTS) systems, particularly in scalability, speaker consistency, and natural turn-taking. A core innovation of VibeVoice is its use of continuous speech tokenizers (Acoustic and Semantic) operating at an ultra-low frame rate of 7.5 Hz. 



These tokenizers efficiently preserve audio fidelity while significantly boosting computational efficiency for processing long sequences. VibeVoice employs a next-token diffusion framework, leveraging a Large Language Model (LLM) to understand textual context and dialogue flow, and a diffusion head to generate high-fidelity acoustic details. The model can synthesize speech up to 90 minutes long with up to 4 distinct speakers, surpassing the typical 1-2 speaker limits of many prior models.

### Useful Link

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*





### PoC steps

```
conda create --name=VibeVoice python=3.11
git clone https://github.com/vibevoice-community/VibeVoice.git
pip install -e .
python demo/gradio_demo.py --model_path vibevoice/VibeVoice-7B  --share
```

### Demo effect

##### Chinese Version Demo：

https://github.com/user-attachments/assets/242918c2-ea02-41b6-9373-e65ad16efa9c





##### English Version Demo：

https://github.com/user-attachments/assets/7ecc7255-e7c3-405e-bf97-8e20861b9863
