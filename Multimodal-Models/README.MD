# Multimodal Models

Projects on image and video generation, speech and voice, vision and vision-language models, and medical imaging. Each folder is a self-contained project with its own README.

[Back to the main page](../README.md)

- [Image and video generation](#image-and-video-generation)
- [Speech and voice](#speech-and-voice)
- [Vision and vision-language models](#vision-and-vision-language-models)
- [Medical imaging](#medical-imaging)
- [Archive](#archive)

## Image and video generation

| Project | What it covers |
|---|---|
| [MAI-Image-2-vs-GPT-Image-Benchmark](MAI-Image-2-vs-GPT-Image-Benchmark/) | MAI-Image-2.6 vs GPT-Image-2 and GPT-Image-2.5 across all quality tiers, measured in one session from one client, account and region |
| [Image-Generation-US-Region-Benchmark](Image-Generation-US-Region-Benchmark/) | The same comparison on US-region deployments: 9 configurations, 17 prompts, 2 rounds, 306 images |
| [GPT-Image-2-Token-Bucket-Benchmark](GPT-Image-2-Token-Bucket-Benchmark/) | GPT-Image-2 on Azure OpenAI: how the quality and size settings drive token usage, latency and image quality |
| [Flux](Flux/) | FLUX.1 image generation verification with the dev version |
| [Content-Safety-with-Flux-Image-Generation](Content-Safety-with-Flux-Image-Generation/) | Azure AI Content Safety screening for FLUX image generation |
| [Sora](Sora/) | Sora 2 video generation and remix API on Azure, with an architecture deep dive |

## Speech and voice

| Project | What it covers |
|---|---|
| [Meeting-Transcription-AMI-English](Meeting-Transcription-AMI-English/) | Six Azure speech paths on four far-field AMI meeting clips: word error rate, streaming latency, the clips and human transcripts (CC BY 4.0) |
| [Azure-Voice-Live](Azure-Voice-Live/) | Every component you can plug into Azure Voice Live, for speech recognition, models and voices, with the exact API values |
| [VibeVoice-TTS](VibeVoice-TTS/) | Microsoft VibeVoice: long-form multi-speaker speech generation |
| [STT-SFT](STT-SFT/) | Fine-tuning Whisper speech-to-text for the medical domain |
| [voice-wake-word](voice-wake-word/) | Wake-word detection with hard negative mining |
| [Chinese-PII-With-Azure-Speech-Service](Chinese-PII-With-Azure-Speech-Service/) | Chinese PII detection and anonymization with Microsoft Presidio and Azure Language |

For voice agents built on Voice Live, see [AI Agents: voice agents](../Agents/README.md#voice-agents).

## Vision and vision-language models

| Project | What it covers |
|---|---|
| [Florence-2](Florence-2/) | Florence-2 vision foundation model: evaluation and usage |
| [Phi3-vision-Fine-tuning](Phi3-vision-Fine-tuning/) | Fine-tuning Phi-3.5-Vision on custom datasets |
| [Phi3-vision-Inference-on-Edge](Phi3-vision-Inference-on-Edge/) | Phi-3 Vision inference on edge devices |
| [SFT-Phi-4-mm](SFT-Phi-4-mm/) | Supervised fine-tuning of the Phi-4 multimodal audio and vision encoders |
| [Use-Unsloth-to-fine-tune-VLM](Use-Unsloth-to-fine-tune-VLM/) | Fine-tuning vision-language models with Unsloth |
| [OmniParser](OmniParser/) | OmniParser for screen parsing and UI understanding |
| [Blueprint-Region-Detector](Blueprint-Region-Detector/) | Entity detection on architectural floor plans of different styles with SAM 2.1 and an auto-tuned connected-components branch |
| [Muse-WHAM](Muse-WHAM/) | Microsoft Muse / WHAM world model for games |
| [Computer-Vision-Workshop](Computer-Vision-Workshop/) | Hands-on workshop: text-to-image, GPT-4o, Phi-3 Vision and VLM fine-tuning |
| [Evolution-of-Computer-Vision](Evolution-of-Computer-Vision/) | How computer vision evolved from CNNs to vision-language models |

## Medical imaging

| Project | What it covers |
|---|---|
| [BiomedParse-Fine-Tuning](BiomedParse-Fine-Tuning/) | Fine-tuning BiomedParse for medical image segmentation |
| [MedImageParse](MedImageParse/) | Medical image segmentation agent driven by natural-language prompts |

## Archive

These projects stay in place so existing links keep working. The models, APIs or tool versions they use have since been superseded; check current documentation before reusing the steps.

| Project | What it covered |
|---|---|
| [Computer-Vision](Computer-Vision/) | Azure Computer Vision programs for Windows image analysis |
| [DeepSpeed-FT-Stable-Diffusion](DeepSpeed-FT-Stable-Diffusion/) | Fine-tuning Stable Diffusion with DeepSpeed |
| [E2E-Stable-Diffussion-on-A100-MIG](E2E-Stable-Diffussion-on-A100-MIG/) | Stable Diffusion on A100/H100 with MIG partitioning |
| [GPT-Image-1](GPT-Image-1/) | One GPT-Image-1 generation call on Azure OpenAI; see [GPT-Image-2-Token-Bucket-Benchmark](GPT-Image-2-Token-Bucket-Benchmark/) |
| [Image_super_Resolution](Image_super_Resolution/) | Image super-resolution with Real-ESRGAN at 2x, 4x and 8x |
| [Phi-3.5-Vision-and-Pixtral-vLLM](Phi-3.5-Vision-and-Pixtral-vLLM/) | Phi-3.5 Vision and Pixtral on vLLM |
| [SDXL-LoRA-Test](SDXL-LoRA-Test/) | SDXL LoRA training and testing |
| [Training-VIT-Run-Qianwen-VL](Training-VIT-Run-Qianwen-VL/) | Training a ViT and running Qwen-VL |
