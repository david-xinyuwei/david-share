# Decision Model on the Edge: Fine-Tuning and Inference Optimization

[English](README.md) | [中文](README_CN.md)

[![Model](https://img.shields.io/badge/model-Kev%200.8B%20%C2%B7%204B%20on%20Qwen3.5-0078D4)](https://github.com/jaredpalmer/kev)
[![Device](https://img.shields.io/badge/device-Snapdragon%20X%20Elite%20%C2%B7%20llama.cpp%20b11935-0078D4)](文档/Evaluation-Results.md#5-laptop-inference-engine)
[![Measured](https://img.shields.io/badge/measured-2026--10--27%20to%2011--01%20%C2%B7%20simulated%20vendor%20data-0078D4)](#results)
[![License](https://img.shields.io/badge/license-MIT-0078D4)](https://github.com/david-xinyuwei/david-share/blob/master/LICENSE)

> **Author**: Xinyu Wei - Senior Systems Engineer, Microsoft AI GBB

[Results at a Glance](#results-at-a-glance) · [Architecture](#architecture) · [Results](#results) · [Steps](#steps)

## Purpose

**Dedicated decision models are becoming a model class of their own**: TypeSafe's hosted Jev, the open-weight [Kev](https://github.com/jaredpalmer/kev) released in September 2026 (1.0 on October 1), and the dozen or so similar models that the current llama.cpp already serves. They generate no text; they pick an answer from the given options and return a probability, so one forward pass completes a routing, triage or grading decision — faster, steadier and cheaper than asking a chat model to write a paragraph and parsing it. But if such a model can only live in the cloud, it does not suit edge devices, offline scenarios or customers whose data must stay on site. So it has to meet two requirements:

1. **Run locally** — on a laptop's CPU and memory, with no cloud-model call.
2. **Accept business data for fine-tuning** — the customer's rules, fields and vocabulary must train into the model, and the model must be updatable when the rules change.

This project tests both with Kev (an open-weight decision model on Qwen3.5, 0.8B / 4B): fine-tune on business data on a GPU host, measure accuracy, latency and memory on a Snapdragon laptop, measure the inference-optimization levers one at a time — quantization, context length, compute backend, prompt length and model size — and then confirm that the same model file runs unchanged on an x86-64 virtual machine. **Training runs on a GPU host; routine inference stays on the laptop without cloud-model calls.** The data is fictional Contoso PC data, not customer data; there is no proprietary-cloud comparison and no production-readiness guarantee.

## Results at a Glance

### Training: Accuracy on the Same Questions

Inputs are simulated Contoso PC support and assistant records: a user message, device fields and three questions. Labels come from business-rule code. The table holds the H100 NVL / PyTorch evaluation path and questions fixed while comparing training recipes. Out-of-distribution sets change the text generator and field distribution. [Actual input example and test method](文档/Evaluation-Results.md#how-the-tests-work)

<!-- OVERVIEW:ACCURACY -->
<!-- SOURCE:TABLE:1 -->
| Parameter scale| Test set (questions)| GPU accuracy: released| GPU accuracy: FT-cf<br>3,832 business records, 2 epochs| GPU accuracy: C<br>4,038 business records, 4 epochs| Final recipe gain over released (percentage points)| 
| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution (510 questions)| 44.7%| 86.9%| **96.3%**| +51.6| 
| 0.8B| Assistant: in-distribution (477 questions)| 67.1%| 97.5%| **100.0%**| +32.9| 
| 0.8B| Support: out-of-distribution (1,011 questions)| 43.0%| 82.5%| **88.4%**| +45.4| 
| 0.8B| Assistant: out-of-distribution (951 questions)| 65.7%| 94.4%| **97.3%**| +31.5| 
| 4B| Support: in-distribution (510 questions)| 60.8%| 95.9%| Not run| +35.1| 
| 4B| Assistant: in-distribution (477 questions)| 81.8%| 99.8%| Not run| +18.0| 
| 4B| Support: out-of-distribution (1,011 questions)| 60.7%| 91.4%| Not run| +30.7| 
| 4B| Assistant: out-of-distribution (951 questions)| 81.9%| 98.8%| Not run| +16.9| 
<!-- /SOURCE:TABLE:1 -->
<!-- /OVERVIEW:ACCURACY -->

Released means no business fine-tuning. FT-cf uses 3,832 business records for 2 epochs; C adds 206 variants and uses 4,038 records for 4 epochs. Both also mix in 1,000 Kev replay records and train independently from the same released checkpoint; C does not continue from the FT-cf checkpoint. The 4B model has no C run, so its final gain uses FT-cf; 0.8B uses C. Gains are calculated from unrounded correct-answer counts.

### Inference: Accuracy, Speed and Resources

The two tables list only configurations actually run on the Snapdragon X Elite laptop, including delivered round-2 C. GPU accuracy above compares training recipes; laptop accuracy here checks the quantized deployment. They are different measurements, not interchangeable values. They use llama.cpp b11935 CPU, default settings, 170 support and 159 assistant requests, with three questions per request. Latency runs from client send to all answers received, excluding loading and two warm-up requests; memory is peak process working set. Each task answers three questions in one request; the loaded model handles subsequent tasks without reloading. The loading column uses the same server-log interval, from `loading model` to `model loaded`, in seconds; it is not full service startup or health-check waiting time. Each value comes from one retained run with uncontrolled filesystem-cache state, so it does not establish a fine-tuning speedup in startup. [Throughput in tasks per second is reported separately](文档/Evaluation-Results.md#concurrency-laptop), not inferred by inverting median latency. Each agreement value uses the PyTorch model of the same size and recipe as that row. BF16 models not run on the laptop are listed separately in the [GPU accuracy baseline](文档/Evaluation-Results.md#gpu-bf16-baseline).

<!-- OVERVIEW:INFERENCE -->
<!-- SOURCE:TABLE:2 -->
| Model (0.8B, Snapdragon X Elite CPU, default settings)| Weight quantization format| File (MiB)| Laptop accuracy (support / assistant)| Per-question agreement with its own PyTorch model| Time per task (support / assistant, ms, median)| Peak working set (MiB)| Model-loading stage (s, server log)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| Released B0, official Q8_0 package| W8 (Q8_0)| 775| 45.7% / 66.9%| 97.6% / 99.0%| 666 / 843| 2,323| 3.981| 
| Fine-tuned FT-cf, Q8_0| W8 (Q8_0)| 775| 86.9% / 97.7%| 99.2% / 99.8%| 646 / 984| 2,314| 1.483| 
| Fine-tuned FT, Q4_K_M (separate FT recipe, not FT-cf)| W4/W8 mix (custom Q4_K_M)| 528| 87.5% / 93.9%| 94.9% / 97.9%| 812 / 909| 1,819| 1.642| 
| Round-2 C, Q8_0 (delivered)| W8 (Q8_0)| 775| 96.9% / 99.6%| 98.6% / 99.6%| 635 / 905| 2,314| 2.236| 
<!-- /SOURCE:TABLE:2 -->

<!-- SOURCE:TABLE:3 -->
| Model (4B, Snapdragon X Elite CPU, default settings)| Weight quantization format| File (MiB)| Laptop accuracy (support / assistant)| Per-question agreement with its own PyTorch model| Time per task (support / assistant, ms, median)| Peak working set (MiB)| Model-loading stage (s, server log)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| Released B0, official Q4_K_M package| Q4_K_M (official mixed format)| 2,893| 59.0% / 82.0%| 93.1% / 97.3%| 3,022 / 3,790| 6,849| 7.820| 
| Fine-tuned FT-cf, Q8_0| W8 (Q8_0)| 4,276| 96.1% / 99.8%| 99.4% / 100.0%| 3,649 / 4,115| 9,609| 8.552| 
| Fine-tuned FT-cf, Q4_K_M| W4/W8 mix (custom Q4_K_M)| 2,893| 95.3% / 99.6%| 98.2% / 99.8%| 3,615 / 4,751| 6,842| 5.014| 
<!-- /SOURCE:TABLE:3 -->
<!-- /OVERVIEW:INFERENCE -->

The C row uses the first complete default-settings Snapdragon run. Other repeats, lean settings and x86-64 results remain in the [full device regression](文档/Evaluation-Results.md#round2-device). The 0.8B Q4_K_M row uses FT, not FT-cf or C; recipe differences cannot be attributed to quantization.

- **Fine-tuning improves business accuracy.** This does not show that fine-tuning accelerates an unchanged model architecture; individual timing differences do not establish causation.
- **Q8_0 stays closer to its own PyTorch answers.** Q4_K_M reduces file size but has lower per-question agreement. Unrun cells remain visible.
- **Keep the limits with the headline.** Data is simulated. Of 160 long-history records, 7 exceed the context window and are rejected. On the remaining 153 records, C answers 206/459 questions correctly (44.9%, excluding rejected requests). This test ran only on x86-64, and short-input accuracy cannot substitute for it. [Long-input cases and results](文档/Evaluation-Results.md#long-real)

## Architecture

Four recipes are compared throughout; their names are fixed here. **B0** is the released Kev model without training. **B0-policy** is the same released model with the full vendor policy text written into every question's prompt. **FT** is supervised fine-tuning of the released model on business data. **FT-cf** adds counterfactual variants to FT's data: the same message with one device field changed. **Round-2 C** is the FT-cf recipe plus 206 variants aimed at the weak fields, trained for 4 epochs. All four fine-tuned recipes start from the same release and are trained independently; **the final recommendation and delivered file is round-2 C** (`Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf`). FT-cf is its previous version: the full measurement campaign in sections 1–7 was run on FT-cf; C's GPU figures are in [the second round](文档/Evaluation-Results.md#round2), and its on-device figures on the x86-64 VM and the Snapdragon laptop in the [device regression](文档/Evaluation-Results.md#round2-device).

### Training: Business Data to a Model File

The laptop prepares separate training, calibration and test sets; released Kev is loaded on the Azure training host. Fine-tuning, calibration and evaluation precede export and quantization. The laptop receives the GGUF. [Parameters and return paths](文档/Core-Technology.md)

<img src="images/training-en.png" width="900" alt="Fine-tuning, calibration, evaluation, export and quantization: the customer laptop prepares the training, calibration and test sets; released Kev is loaded inside the Azure training host as the model input to supervised fine-tuning. Four numbered steps are supervised fine-tuning, temperature calibration, BF16 GGUF export and quantization to Q8_0 / Q4_K_M; between calibration and export sits an unnumbered evaluation-gate card whose two orange dashed exits return to fine-tuning (accuracy out of its interval) and to calibration (probabilities off only); the quantized GGUF returns to the same customer laptop; two execution-location lanes (local laptop, cloud training host), a legend and source footnote.">

*Original explanatory diagram: blue lines carry data; dashed lines return after evaluation failure. Sources and hashes: [images/provenance.json](images/provenance.json).*

### Everyday Inference: Decisions Stay on the Laptop

The business application sends the message, device fields and questions; llama-server returns option probabilities. This path neither trains nor calls a cloud model, and it does not execute business actions.

<img src="images/inference-en.png" width="900" alt="Unlabeled business input enters llama.cpp on the Windows on Arm laptop CPU. The fine-tuned GGUF returns structured answers and probabilities; the application owns subsequent actions.">

*Original explanatory diagram: the model returns answers and probabilities; the application owns subsequent actions. Source: [systemone_client.py](scripts/systemone_client.py).*

<a id="criteria"></a>

**Five separate checks: answers, confidence, latency, memory and generalization.**

<!-- SOURCE:TABLE:4 -->
| Dimension| Criterion| Questions to answer| How it is measured| Delivered model: 0.8B round-2 C, Q8_0 (previous FT-cf in parentheses)| What the result does not establish| 
| ---| ---| ---| ---| ---| ---| 
| Accuracy| ① Is the answer right?| Does the chosen queue, grade or yes/no match the reference answer?| Accuracy; also broken down on paired questions where one field changes and the answer must follow| Support 96.3%, assistant 100.0% (FT-cf 86.9% / 97.5%); paired questions that change the region 69.0% (FT-cf 36.2%); 96.5% / 99.8% on device in Q8_0 ([section 1](文档/Evaluation-Results.md#same-questions), [second round](文档/Evaluation-Results.md#round2), [device regression](文档/Evaluation-Results.md#round2-device))| High simulated-data scores do not establish real-business accuracy| 
| Accuracy| ② Is the confidence honest?| On the questions where it says 90%, is it right about nine times in ten?| ECE (lower is better); for the business, coverage and accuracy of the part auto-approved at confidence ≥ 90%| ECE 0.025 (FT-cf 0.030); a 90% threshold auto-releases 80.4% of questions with 99.8% accuracy on the released part (FT-cf: 73.1%, 100%) ([section 3](文档/Evaluation-Results.md#3-calibration-correct-ranking-does-not-guarantee-reliable-probabilities))| A change of data distribution requires refitting the calibration parameter| 
| Performance| ③ Latency| How long one request takes| Median time per request (ms), one request at a time| Snapdragon X Elite CPU: support 635 ms, assistant 905 ms (FT-cf 646 / 984); on the x86-64 VM C equals FT-cf (support 1,260 / 1,255 ms) ([section 5](文档/Evaluation-Results.md#5-laptop-inference-engine), [device regression](文档/Evaluation-Results.md#round2-device))| One run on one machine does not cover every laptop; concurrency does not raise throughput, see section 5| 
| Performance| ④ Resource use| How big a machine it needs| Peak process working set, CPU utilization during inference, model file size, service-readiness wait in seconds| 2,314 MiB on Snapdragon, commit charge 5,014 MiB (identical to FT-cf; 2,196 / 2,119 with `-c 2048`); file 775 MiB; service-readiness wait 2.6 s; 1,552 MiB and CPU 50% (8 / 16 threads) on x86-64 ([section 5](文档/Evaluation-Results.md#5-laptop-inference-engine), [section 6](文档/Evaluation-Results.md#6-hardware-requirements))| 4B needs about 3× the memory| 
| Generalization| ⑤ Generalization| How much of ① and ② survives on data it has never seen| Re-measure ① and ② on out-of-distribution questions with a different message generator and field distribution, and read the drop; then check 656 public questions to confirm prior capability is retained| Support accuracy 96.3% → 88.4% (down 7.9 points; FT-cf 86.9% → 82.5%); ECE 0.025 → 0.055, of which 0.029 is recoverable by refitting calibration; public questions 64.8% → 65.2% ([section 1](文档/Evaluation-Results.md#same-questions), [section 2](文档/Evaluation-Results.md#2-retention-of-general-capability), [second round](文档/Evaluation-Results.md#round2))| Out-of-distribution questions are still simulated business, not real customer data; every accuracy holds only for short inputs of ≤ 540 tokens — on real tickets with 3k–8k tokens of history it is 44.9% ([real long inputs](文档/Evaluation-Results.md#long-real))| 
<!-- /SOURCE:TABLE:4 -->

### Why Kev

Kev has downloadable decision-model weights that can be fine-tuned on business data. This project tests only 0.8B and 4B. Producer evaluations and product information below are not this project's business scores. [Selection evidence, original figure and limits](文档/Core-Technology.md#why-kev-is-a-candidate)

<!-- SOURCE:TABLE:5 -->
| Model| Nominal base-model parameter scale| transfer-v4 development accuracy (author's evaluation)| Training state limit (tokens)| Validated input length (tokens)| Weights and this project's scope| 
| ---| ---| ---| ---| ---| ---| 
| Microsoft-Decision-1| 9B (Qwen3.5-9B, post-trained by Microsoft)| Not evaluated on this suite| Not disclosed| Product commitment: 32,768 per request| Hosted in Microsoft Foundry, Preview; not tested in this project| 
| Jev| Not disclosed by the author| 85.7%| Not disclosed| Not disclosed| TypeSafe hosted API; not tested in this project| 
| Kev-27B| 27B| 85.1%| 32,768| 65,536| Open weights; not deployed in this project| 
| Kev-9B| 9B| 82.0%| 7,552| 8,192| Open weights; not deployed in this project| 
| Kev-4B| 4B| 81.7%| 7,552| 8,192| Open weights; fine-tuned and deployed on-device in this project| 
| Kev-0.8B| 0.8B| 64.8%| 7,552| 8,192| Open weights; fine-tuned and deployed on-device in this project| 
<!-- /SOURCE:TABLE:5 -->

## Results

### Findings and Evidence

- **Fine-tuning and generalization:** the overview matrices lead this page; all released, prompt-only, FT, FT-cf and round-2 A/B/C comparisons and remaining errors are in the [complete results](文档/Evaluation-Results.md#same-questions).
- **General capability:** 656 public questions check forgetting; probability quality is reported separately from accuracy. [Public-suite results](文档/Evaluation-Results.md#2-retention-of-general-capability)
- **Calibration:** temperature changes probabilities, not answer ranking. Probability drift and errors requiring retraining are separate. [Calibration boundary](文档/Evaluation-Results.md#3-calibration-correct-ranking-does-not-guarantee-reliable-probabilities)
- **Training resources:** round-2 C takes 22 min 42 s with 7,475 MiB peak device VRAM; multiple training seeds were not tested. [Training cost](文档/Evaluation-Results.md#4-training-resources)
- **CPU architectures:** the same C file agrees on 982/987 questions across Snapdragon and x86-64, not every question. The two machines are not a speed comparison. [Device regression](文档/Evaluation-Results.md#round2-device)
- **Concurrency and long inputs:** the five Snapdragon concurrency settings did not increase throughput with concurrency. Long-history accuracy is a separate limitation. [Concurrency](文档/Evaluation-Results.md#concurrency-laptop) · [Long inputs](文档/Evaluation-Results.md#long-real)
- **Local trial and second round:** earlier wrong answers, later corrections and disproved predictions remain visible; a response is not necessarily correct. [Local trial](文档/Evaluation-Results.md#local-result) · [Full second round](文档/Evaluation-Results.md#round2)

### Inference Optimization: Measured Levers

Each row uses the recorded comparison conditions. The CPU-architecture row changes machines and checks answers, not speed attribution. Unrun configurations stay unrun. [Method and individual runs](文档/Evaluation-Results.md#inference-optimization-which-levers-were-measured)

<!-- OVERVIEW:LEVERS -->
<!-- SOURCE:TABLE:6 -->
| Optimization lever| Comparison (baseline → change)| Accuracy (support / assistant)| Median support decision (ms)| Peak working set (MiB)| One-line conclusion| 
| ---| ---| ---| ---| ---| ---| 
| Weight quantization| 0.8B FT Q8_0 → Q4_K_M (CPU, default arguments)| 86.5% / 93.5% → 87.5% / 93.9%| 669 → 812| 2,314 → 1,819| File 247 MiB smaller and memory 495 MiB lower, but not faster; agreement with PyTorch fell from 99.2% / 99.6% to 94.9% / 97.9%. The 1-point higher accuracy is quantization noise that happened to favor correct answers, not an improvement| 
| Weight quantization| 4B FT-cf Q8_0 → Q4_K_M (CPU, default arguments)| 96.1% / 99.8% → 95.3% / 99.6%| 3,649 → 3,615| 9,609 → 6,842| File 1,383 MiB smaller and memory 2,767 MiB lower; support accuracy 0.6 points below PyTorch. Usable when 4B memory is tight| 
| Context length (`-c`) and batch size| 0.8B FT Q8_0 `-c 8192 -ub 2048` → `-c 2048 -ub 512`| 86.5% / 93.5% → unchanged| 669 → 1,163| 2,314 → 2,196 (commit charge 5,014 → 2,119)| Commit charge 2,895 MiB lower; the cost is 74% slower on support and 44% slower on assistant, accuracy unchanged. Inputs are only about 500 tokens, so most of the 8192 context was unused| 
| Compute backend| 0.8B FT Q8_0 CPU → Adreno GPU (OpenCL, `-ngl 99`)| 86.5% / 93.5% → 85.7% / 93.7%| 669 → 1,035| 2,314 → 4,105| The GPU is slower, the process working set is 1,791 MiB higher, about 3,400 MiB of shared GPU memory is used in addition, and agreement fell to 97.6% / 99.0%. Not the choice on this laptop| 
| Prompt length| Released 0.8B Q8_0, short description → full policy text in the prompt (B0-policy)| 45.7% / 66.9% → 60.6% / 71.7%| 666 → 4,353| 2,323 → 3,446| Median input tokens per record 488 → 1,505, 6.5× slower and 1.1 GB more memory; accuracy still far below fine-tuning (FT-cf 86.9% / 97.7%). Rules belong in the weights, not in every prompt| 
| Model size| Released 4B Q4_K_M → fine-tuned 0.8B FT-cf Q8_0 (both CPU, default arguments)| 59.0% / 82.0% → 86.9% / 97.7%| 3,022 → 646| 6,849 → 2,314| A fine-tuned small model beats an untuned larger one: 27.9 / 15.7 points more accurate, 3.9–4.7× faster, about one third of the memory| 
| Input length| 0.8B FT-cf Q8_0, x86-64 VM, input per question 220 → 7,700 tokens (same 40 tickets plus a synthetic log)| Not applicable (the padding is not a real question; cost only); real questions in the next row| 1,450 → 40,706| 1,552 → 5,061 (commit charge 4,254 → 5,970)| Time grows linearly with length at about 190 tokens per second; once the KV cache is filled the working set grows 3.3×. See the "Long inputs" subsection below| 
| Real long inputs| 0.8B round-2 C Q8_0, x86-64 VM, 160 tickets with a case history, 3,034–8,052 tokens per question, the history decides the answer| **44.9%** (same 160 records without history 63.1%; original short inputs 96.5%); 7 records over the window refused| 26,395 (without history 2,578)| 5,060 (commit charge 5,970)| Cannot read the history: not ignored but thrown off, controls 0 / 53; 8,192 is a hard wall. See [real long inputs](文档/Evaluation-Results.md#long-real)| 
| Concurrent requests| 0.8B FT-cf Q8_0, x86-64 VM, client requests in flight 1 → 8 (server: 4 slots)| 87.1% / 97.9% → 87.1% / 97.7%| 1,183 → 9,086| 1,399 → 1,401| Throughput does not grow (0.79 → 0.81 requests per second) while latency queues linearly with requests in flight; one request already saturates the 8 compute threads. `-np 8` does not add throughput either. See "Concurrency" below| 
| NPU (Hexagon)| Not tested| —| —| —| Requires driver test-signing on Windows, which was not enabled on the company laptop| 
| Speculative decoding, KV-cache reuse| Not applicable| —| —| —| The decision endpoint generates no tokens, so there is no decode phase; `--cache-ram 0` disables the prompt cache| 
| CPU architecture| 0.8B FT-cf Q8_0, Snapdragon X Elite laptop (ARM64 package) → AMD EPYC 7763 Azure VM (x64 package), both CPU with default settings| 86.9% / 97.7% → 87.1% / 97.9%| 646 → 1,168–1,255| 2,314 → 1,400–1,552| The same model file, llama.cpp release and arguments run unchanged on an x86-64 CPU: 983 of 987 answers are identical and two runs gave exactly the same results. The whole machine changed (processor, OS, 8 vs. 12 threads), so latency and memory differences are not attributed to the architecture| 
<!-- /SOURCE:TABLE:6 -->
<!-- /OVERVIEW:LEVERS -->

### Hardware Requirements

Measured hardware is distinguished from minimum configurations inferred from VRAM use. An inferred minimum was not necessarily tested.

<!-- OVERVIEW:HARDWARE -->
<!-- SOURCE:TABLE:7 -->
| Stage| GPU required?| Measured hardware and usage (GPU memory is nvidia-smi peak)| Estimated minimum from memory measurements; these cards were not tested| 
| ---| ---| ---| ---| 
| Train 0.8B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 4,555 MiB GPU memory (micro-batch 1), 7,573 MiB (micro-batch 4)| 8 GB GPU memory (micro-batch 1)| 
| Train 4B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 18,547 MiB (micro-batch 1, probe only), 26,215–33,359 MiB (micro-batch 4)| 24 GB GPU memory (micro-batch 1); over 40 GB for micro-batch 4| 
| GGUF export| No; CPU only| GPU host's CPU| —| 
| Laptop inference 0.8B (Q8_0; FT-cf and the delivered C measured identical)| No discrete GPU or NPU; CPU inference| Snapdragon X Elite, 12 cores; process peak working set 2,314 MiB, committed memory 5,014 MiB (default arguments) or 2,119 MiB (`-c 2048 -ub 512`), identical to the digit for both models| Size total RAM for this process plus the OS and other applications| 
| Laptop inference 4B FT-cf (Q8_0 / Q4_K_M)| No discrete GPU or NPU; CPU inference| 12-core Snapdragon X Elite; peak working set 9,609 / 6,842 MiB and commitment 8,884 / 7,495 MiB| Same sizing principle| 
| x86-64 CPU inference 0.8B (Q8_0), comparison: FT-cf and the delivered C| No GPU; CPU inference| AMD EPYC 7763 Azure VM, 8 vCPU; process peak working set 1,400–1,553 MiB, committed memory 4,253–4,254 MiB (default arguments, five runs across the two models); C with `-c 2048 -ub 512`: 1,421 / 1,360 MiB| Same sizing principle| 
<!-- /SOURCE:TABLE:7 -->
<!-- /OVERVIEW:HARDWARE -->

### Limits

Simulated data, one training seed, one Snapdragon laptop and one x86-64 VM; no customer-production acceptance, long-term stability or battery-power conclusion. Out-of-distribution sets are still simulated, and short-input scores are not long-input guarantees. [Complete limits](文档/Evaluation-Results.md#limits-of-the-conclusions)

## Steps

<!-- SOURCE:TABLE:8 -->
| Your task| Start here| Execution order| Expected result| 
| ---| ---| ---| ---| 
| Try an existing fine-tuned GGUF locally| [A. Local trial](文档/Operations-Guide.md#local-try)| Start runtime → send one request → edit a field and repeat| Real model response, measured timing and raw output files| 
| Produce a model or adapt to new business data| [B. Train and update](文档/Operations-Guide.md#train-update)| Data → train → calibrate → evaluate → export → update local model| A new checkpoint, evaluation and GGUF; not old-directory overwrite with skipped stages| 
| Recheck the reported results| [C. Verification](文档/Operations-Guide.md#verify)| Run offline tests or start a real model for full device evaluation| Keep code checks, historical evidence replay and fresh model execution distinct| 
<!-- /SOURCE:TABLE:8 -->

Run all commands from the project root, not the directory containing a detail document. First obtain the architecture-matched llama.cpp package and calibrated GGUF through [Operations A](文档/Operations-Guide.md#local-try). Large model files are not included in this repository.

### With a Model: Start and Send One Request

Start the service in the first PowerShell terminal and send the request in a second. Receiving option probabilities establishes a working call; correctness still needs comparison with the business rules.

<!-- SOURCE:FENCE:1 -->
```powershell
$Engine = 'C:\Tools\llama.cpp\b11935-cpu\llama-server.exe'
$Model = 'C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf'   # 交付的第二轮 C；上一版改用 Contoso-Kev-0.8B-FTcf-Q8_0.gguf
if (-not (Test-Path -LiteralPath $Engine)) { throw '找不到 llama-server' }
if (-not (Test-Path -LiteralPath $Model)) { throw '找不到微调 GGUF，请先取得模型' }
& $Engine -m $Model --alias contoso-kev-0.8b-r2c --host 127.0.0.1 --port 8080 `
    -c 8192 -b 2048 -ub 2048 -ngl 0 --cache-ram 0 --offline
```
<!-- /SOURCE:FENCE:1 -->

<!-- SOURCE:FENCE:2 -->
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8080/health
$Run = Join-Path '验证结果' ('本机试用_' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
python -B scripts\systemone_client.py --url http://127.0.0.1:8080/v1/systemone `
    --request data\contoso\examples\support.json --out "$Run\support-us"
```
<!-- /SOURCE:FENCE:2 -->

Region changes, the graphical trial, training, updates, offline tests and stop/restore instructions are in the [operations guide](文档/Operations-Guide.md). Offline checks do not invoke a model or establish a fresh training/performance run.

## Repository Deliverables

<!-- SOURCE:TABLE:9 -->
| Deliverable| Location| Purpose| 
| ---| ---| ---| 
| Simulated vendor data with policy-computed labels| [data/contoso/final](data/contoso/final); manifest and SHA-256: [manifest.json](data/contoso/final/manifest.json)| Training, calibration, development, in-distribution, out-of-distribution and variant evaluation| 
| Vendor policy and data generation| [scripts/vendor_policy.py](scripts/vendor_policy.py), [scripts/gen_vendor_data.py](scripts/gen_vendor_data.py), [scripts/augment_counterfactual.py](scripts/augment_counterfactual.py)| Adapt policies and fields to reuse the workflow with real business data| 
| GPU-host training and evaluation pipelines| [scripts/remote_setup.sh](scripts/remote_setup.sh), [scripts/remote_pipeline_v2.sh](scripts/remote_pipeline_v2.sh), [scripts/remote_cf_round.sh](scripts/remote_cf_round.sh), [scripts/remote_export_gguf.sh](scripts/remote_export_gguf.sh)| Baselines, fine-tuning, temperature calibration, evaluation, paired comparison and GGUF export| 
| Laptop device validation| [scripts/run_engine_eval.ps1](scripts/run_engine_eval.ps1), [scripts/systemone_client.py](scripts/systemone_client.py), [scripts/parity.py](scripts/parity.py)| Start llama-server, score and time request by request (including concurrency), compare with PyTorch per question| 
| Local browser trial page| [scripts/try_ui.py](scripts/try_ui.py)| Edit inputs in a browser form, see every option's probability, compare with the policy answer, watch process memory and CPU; Chinese/English| 
| Summaries and tests| [scripts/summarize_results.py](scripts/summarize_results.py), [scripts/summarize_engine.py](scripts/summarize_engine.py), [scripts/calibration_boundary.py](scripts/calibration_boundary.py), [tests/](tests/)| Every table is generated from raw results; offline "re-calibrate or retrain" decision; offline checks of data and scoring code| 
| Raw evidence| [Evidence directory](验证结果/)| Evaluation reports, predictions, training logs, GPU-memory samples and device records. Checkpoints and full result archives contain files above GitHub's 100 MB limit and are not included; reproduce them with the training steps| 
| Detailed report| [Detailed validation report](文档/Finetuning-and-On-Device-Validation-Report.md)| Full tables, per-question analysis and claim boundaries| 
<!-- /SOURCE:TABLE:9 -->

### Documentation

- [Core technology](文档/Core-Technology.md): model choice, algorithms, parameters and interface.
- [Complete evaluation results](文档/Evaluation-Results.md): method, every configuration, individual runs and failure boundaries.
- [Operations guide](文档/Operations-Guide.md): setup, use, training, updates, verification and script navigation.
- [First-round detailed report](文档/Finetuning-and-On-Device-Validation-Report.md) and [experiment protocol](文档/Experiment-Protocol.md): question-level breakdowns, original decision rules and deviations.
