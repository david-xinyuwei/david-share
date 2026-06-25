#!/usr/bin/env python3
"""FLEURS zh_cn CER baseline evaluation for Qwen3-ASR models.

Usage:
    python eval_fleurs_baseline.py --model Qwen/Qwen3-ASR-0.6B --max-samples 200
    python eval_fleurs_baseline.py --model Qwen/Qwen3-ASR-1.7B --max-samples 200
    python eval_fleurs_baseline.py --model /path/to/finetuned --max-samples 200
"""
import argparse
import json
import re
import time
from pathlib import Path

import jiwer
import torch
from datasets import load_dataset


def normalize_chinese(text: str) -> str:
    """Normalize text for CER computation: remove punctuation, lowercase."""
    text = text.strip().lower()
    text = re.sub(r"[\u3000\s]+", " ", text)
    text = re.sub(r"[，。！？、；：,.!?;:\"'()\[\]{}<>《》""''·…—\-]", "", text)
    text = text.replace(" ", "")
    return text


def compute_cer(references: list[str], hypotheses: list[str]) -> dict:
    """Compute CER using jiwer with character-level tokenization."""
    refs_norm = [normalize_chinese(r) for r in references]
    hyps_norm = [normalize_chinese(h) for h in hypotheses]

    # Filter out empty references
    valid = [(r, h) for r, h in zip(refs_norm, hyps_norm) if len(r) > 0]
    refs_norm = [r for r, _ in valid]
    hyps_norm = [h for _, h in valid]

    transform = jiwer.Compose([jiwer.ReduceToListOfListOfChars()])
    cer = jiwer.wer(refs_norm, hyps_norm, reference_transform=transform, hypothesis_transform=transform)

    # Also compute per-sample CER for stats
    per_sample = []
    for r, h in zip(refs_norm, hyps_norm):
        s_cer = jiwer.wer([r], [h], reference_transform=transform, hypothesis_transform=transform)
        per_sample.append(s_cer)

    import numpy as np
    arr = np.array(per_sample)
    return {
        "cer_overall": round(cer, 4),
        "cer_mean": round(float(arr.mean()), 4),
        "cer_median": round(float(np.median(arr)), 4),
        "cer_std": round(float(arr.std()), 4),
        "cer_p95": round(float(np.percentile(arr, 95)), 4),
        "num_samples": len(refs_norm),
        "num_perfect": int((arr == 0.0).sum()),
    }


def transcribe_qwen_asr(model_path: str, audio_paths: list[str], device: str = "cuda") -> list[str]:
    """Transcribe using qwen-asr package."""
    from qwen_asr import QwenASR
    model = QwenASR(model_path, device=device)
    results = []
    for path in audio_paths:
        text = model.transcribe(path)
        results.append(text if text else "")
    return results


def transcribe_transformers(model_path: str, audio_paths: list[str], device: str = "cuda") -> list[str]:
    """Fallback: transcribe using raw transformers."""
    from transformers import AutoModelForCausalLM, AutoProcessor
    import soundfile as sf

    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path, torch_dtype=torch.bfloat16, device_map=device, trust_remote_code=True
    )

    results = []
    for path in audio_paths:
        audio, sr = sf.read(path)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000

        conversation = [{"role": "user", "content": [
            {"type": "audio", "audio": f"file://{path}"},
        ]}]
        text = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
        inputs = processor(text=text, audios=[audio], sampling_rate=sr, return_tensors="pt").to(device)

        with torch.no_grad():
            output_ids = model.generate(**inputs, max_new_tokens=256)
        generated = output_ids[0, inputs.input_ids.shape[1]:]
        result = processor.decode(generated, skip_special_tokens=True).strip()
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="FLEURS zh_cn CER baseline")
    parser.add_argument("--model", default="Qwen/Qwen3-ASR-0.6B")
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output-dir", default="/root/asr_results")
    parser.add_argument("--backend", choices=["qwen-asr", "transformers"], default="qwen-asr")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"Loading FLEURS zh_cn {args.split} split...")
    ds = load_dataset("google/fleurs", "zh_cn", split=args.split, trust_remote_code=True)
    if args.max_samples and args.max_samples < len(ds):
        ds = ds.select(range(args.max_samples))
    print(f"  Loaded {len(ds)} samples")

    # Save audio to disk for transcription
    audio_dir = Path(args.output_dir) / "fleurs_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_paths = []
    references = []

    print("Extracting audio files...")
    import soundfile as sf
    for i, sample in enumerate(ds):
        audio = sample["audio"]["array"]
        sr = sample["audio"]["sampling_rate"]
        path = audio_dir / f"sample_{i:04d}.wav"
        sf.write(str(path), audio, sr)
        audio_paths.append(str(path))
        references.append(sample["transcription"])

    print(f"Transcribing with {args.model} (backend={args.backend})...")
    t0 = time.time()
    try:
        if args.backend == "qwen-asr":
            hypotheses = transcribe_qwen_asr(args.model, audio_paths, args.device)
        else:
            hypotheses = transcribe_transformers(args.model, audio_paths, args.device)
    except Exception as e:
        print(f"ERROR with {args.backend}: {e}")
        print("Falling back to transformers backend...")
        hypotheses = transcribe_transformers(args.model, audio_paths, args.device)
    elapsed = time.time() - t0

    print(f"  Transcription done in {elapsed:.1f}s")

    # Compute CER
    metrics = compute_cer(references, hypotheses)
    metrics["model"] = args.model
    metrics["backend"] = args.backend
    metrics["split"] = args.split
    metrics["elapsed_seconds"] = round(elapsed, 1)
    metrics["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"

    # Save results
    model_short = args.model.split("/")[-1].lower().replace("-", "_")
    output_file = Path(args.output_dir) / f"fleurs_cer_{model_short}.json"
    with open(output_file, "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*50}")
    print(f"Model: {args.model}")
    print(f"Samples: {metrics['num_samples']}")
    print(f"CER (overall): {metrics['cer_overall']*100:.2f}%")
    print(f"CER (mean±std): {metrics['cer_mean']*100:.2f}% ± {metrics['cer_std']*100:.2f}%")
    print(f"CER (median): {metrics['cer_median']*100:.2f}%")
    print(f"CER (P95): {metrics['cer_p95']*100:.2f}%")
    print(f"Perfect (CER=0): {metrics['num_perfect']}/{metrics['num_samples']}")
    print(f"Time: {elapsed:.1f}s ({elapsed/len(audio_paths):.2f}s/sample)")
    print(f"Saved: {output_file}")
    print(f"{'='*50}")

    # Save some examples for manual inspection
    examples_file = Path(args.output_dir) / f"fleurs_examples_{model_short}.json"
    examples = []
    for i in range(min(20, len(references))):
        examples.append({
            "id": i,
            "reference": references[i],
            "hypothesis": hypotheses[i],
            "cer": round(jiwer.wer(
                [normalize_chinese(references[i])],
                [normalize_chinese(hypotheses[i])],
                reference_transform=jiwer.Compose([jiwer.ReduceToListOfListOfChars()]),
                hypothesis_transform=jiwer.Compose([jiwer.ReduceToListOfListOfChars()])
            ), 4) if normalize_chinese(references[i]) else None,
        })
    with open(examples_file, "w") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
