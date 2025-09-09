## VibeVoice Test

VibeVoice is a novel framework designed for generating **expressive, long-form, multi-speaker** conversational audio, such as podcasts, from text. It addresses significant challenges in traditional Text-to-Speech (TTS) systems, particularly in scalability, speaker consistency, and natural turn-taking. A core innovation of VibeVoice is its use of continuous speech tokenizers (Acoustic and Semantic) operating at an ultra-low frame rate of 7.5 Hz. 

These tokenizers efficiently preserve audio fidelity while significantly boosting computational efficiency for processing long sequences. VibeVoice employs a next-token diffusion framework, leveraging a Large Language Model (LLM) to understand textual context and dialogue flow, and a diffusion head to generate high-fidelity acoustic details. The model can synthesize speech up to 90 minutes long with up to 4 distinct speakers, surpassing the typical 1-2 speaker limits of many prior models.

### Useful Link

*https://huggingface.co/microsoft/VibeVoice-1.5B*

*https://huggingface.co/vibevoice/VibeVoice-7B*

*https://microsoft.github.io/VibeVoice/*

*https://github.com/microsoft/VibeVoice*



### Fast PoC steps

You could run VibeVoice model on Edge，if you run VibeVoice-7B, it will need ~20GB VRAM, NVIDIA A10 is enough.

```
conda create --name=VibeVoice python=3.11
git clone https://github.com/vibevoice-community/VibeVoice.git
pip install -e .
python demo/gradio_demo.py --model_path vibevoice/VibeVoice-7B  --share
```

![images](https://github.com/david-xinyuwei/david-share/blob/master/Multimodal-Models/VibeVoice-TTS/images/1.png)

### Demo effect

**English Version Demo:

https://github.com/user-attachments/assets/10cc7ef9-616f-48ad-879c-a93ee53f3794  

> Video loading slowly? [Click here to watch in a new tab](https://github.com/user-attachments/assets/10cc7ef9-616f-48ad-879c-a93ee53f3794  )

**Chinese Version Demo:**

https://github.com/user-attachments/assets/59d67e41-1bdd-4d3f-b36b-4bb2008fdf66  

> Video loading slowly? [Click here to watch in a new tab](https://github.com/user-attachments/assets/59d67e41-1bdd-4d3f-b36b-4bb2008fdf66 )
