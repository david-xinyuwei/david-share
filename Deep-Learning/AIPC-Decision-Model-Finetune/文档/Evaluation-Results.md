# Complete Evaluation and Device Results

[English](Evaluation-Results.md) | [中文](评测与端侧结果全集.md)

[Project overview](../README.md) · [Core technology](Core-Technology.md) · [Operations](Operations-Guide.md)

### Validation Scenarios

Support-ticket triage and assistant routing are two evaluation scenarios, not the complete business requirement. Both require understanding the message and applying policies to device fields.

<!-- SOURCE:TABLE:1 -->
| Scenario| Model input| Questions to answer| 
| ---| ---| ---| 
| Support-ticket triage| Customer message + device record (product line, region, warranty, purchase age, battery cycles, diagnostic code)| Queue (8 choices), onsite eligibility (yes/no), urgency (4 levels)| 
| On-device assistant routing| User message + device state (network, enterprise management, power/battery, foreground application)| Tool (14 choices), entirely local action (yes/no), confirmation before execution (yes/no)| 
<!-- /SOURCE:TABLE:1 -->

Many answers depend on fields absent from the message. For the same loose-hinge complaint, Premium Care 3Y, an in-warranty device and a CN/JP/DE/US region imply onsite service. Singapore or an expired warranty changes the answer to mail-in service or a paid quote. Released Kev does not know these vendor rules.

The repository answers four questions:

1. **Fine-tuning**: does continued training on vendor data improve released Kev?
2. **Quality**: how much better is it than no training or policy text in the prompt? Can confidence inform automation versus human review, and is general capability retained?
3. **Resources**: how much GPU time and memory does training need, and what are model size, process memory and decision latency on the laptop?
4. **Runtime**: can llama.cpp run the fine-tuned model on Snapdragon X Elite, with results matching PyTorch, and does it still run on an x86-64 CPU?

## Results

### How the Tests Work

**Each pipeline step moves only one or two of the [five criteria](../README.md#criteria); the others must be re-checked for damage.** This is also why calibration has no pass/fail of its own: it owns only ②, and the verdict “good enough, or back to which step” comes from the evaluation that follows it.

<!-- SOURCE:TABLE:2 -->
| Pipeline step| Criterion it moves| What must be re-checked| Measured in this project (0.8B; delivered round-2 C, previous FT-cf in parentheses)| 
| ---| ---| ---| ---| 
| Data generation and splits (with counterfactual variants)| ① what can be learned; ⑤ forces the model to read fields instead of memorizing messages| Training, calibration and test sets do not overlap| Training set 2,147 → 3,832 → 4,038 records| 
| Fine-tuning (LoRA + pointer head)| ① answer correctness; side effect: sharper confidence| ⑤ public-question accuracy must not drop (threshold 2 percentage points)| Support 44.7% → 96.3% (FT-cf 86.9%); public questions 64.8% → 65.2% (FT-cf 64.8%)| 
| Calibration (fit one temperature T)| Only ②, confidence honesty| ① no answer changes| C: T = 2.83, calibration-set ECE 0.025 → 0.010 (FT-cf: T = 1.15, 0.011 → 0.008); 16 groups × 71 temperatures, answers identical to the digit| 
| Export GGUF (BF16)| Must change nothing| Per-question agreement with PyTorch| Agreement 99.2% / 99.8% (FT-cf, laptop); C's Q8_0 on x86-64 99.0% / 99.8%| 
| Quantization (Q8_0 / Q4_K_M)| ③ latency, ④ resource use| How much ① and ② were given up| File 1,447 → 775 / 528 MiB; 8-bit answer agreement 99.0–100%, 4-bit 94.9–98.2% (FT / FT-cf)| 
| Evaluation (`kev.benchmark`, on-device runs)| Moves nothing; measures only| All five| ① ② ⑤ on the GPU; ③ ④ and agreement on the laptop| 
| Post-launch monitoring| Moves nothing| Sample ① ② ⑤ and decide: leave / refit T only / retrain| [The rule in section 3](#3-calibration-correct-ranking-does-not-guarantee-reliable-probabilities)| 
<!-- /SOURCE:TABLE:2 -->

GPU time and memory spent on training are a cost of the pipeline, not a criterion of the model; they are listed separately in [section 4](#4-training-resources).

**Compared configurations** use the same records and the same `kev.benchmark` evaluator:

<!-- SOURCE:TABLE:3 -->
| Name| Method| 
| ---| ---| 
| B0| Released Kev (`jaredpalmer/kev-{0.8b,4b}@v1.0`), one-sentence question instructions, no training| 
| B0-policy| The same release with full vendor policy in each question (the support question section grows from about 950 to 4,600 characters per record)| 
| FT| Continue from the release with supervised fine-tuning (SFT): cross-entropy on the correct answer, not reinforcement learning; other loss weights are 0 in the [training configuration](../验证结果/微调评测_20261027-220226/runs/0.8b/ft/training_config.json). Rank-16 LoRA + pointer head, 2 epochs, lr 2e-5, effective batch 8, bf16, seed 1; mix in 1,000 Kev replay records; fit temperature on calibration data| 
| FT-cf| Add counterfactual variants to FT data: keep the training message, change one policy field and recompute labels (2,147 → 3,832 training records). This recipe addresses FT's poor field-change pairs; the selection rule was written into the [protocol](Experiment-Protocol.md) before its results| 
<!-- /SOURCE:TABLE:3 -->

**Test data** uses policy-computed labels. An original case and its field variants stay in one split. Group isolation does not guarantee distinct short messages across unrelated cases: 19 assistant test records have text also seen in training. The report includes a comparison excluding them.

<!-- SOURCE:TABLE:4 -->
| Test set| Records / questions| Message author| Purpose| 
| ---| ---| ---| ---| 
| Support and assistant: in-distribution| 170 / 510, 159 / 477| Model A, also used for training messages| Main results| 
| Support and assistant: out-of-distribution| 337 / 1,011, 317 / 951| Another provider's model B; more Singapore, offline and metered-network cases, with two intents in one message| Effect after changing generator and field distribution| 
| Support and assistant: test variants| 126 / 378, 70 / 210| Keep the test message and change one policy field| Whether the model applies policy to device fields| 
| Kev transfer-v4 development set| 656 questions| Kev author's public tasks| General-capability retention| 
<!-- /SOURCE:TABLE:4 -->

One support test record is shown below, with option descriptions abbreviated. The model sees `state`; policy code derives `label` from the device record, and the model never receives it. The Chinese message is retained verbatim because it is the actual test input, not untranslated documentation.

<!-- SOURCE:FENCE:1 -->
```json
{"state": {"channel": "email",
           "message": "您好：\n请问我的 Contoso Nimbus 2-in-1 订单目前是什么状态？麻烦告知最新进度。\n谢谢\n李明",
           "device": {"product_line": "Nimbus 2-in-1", "region": "SG", "warranty_plan": "Accidental Damage 2Y",
                      "days_since_purchase": 749, "battery_cycles": 202, "last_error_code": "none", "bios_version": "1.11"}},
 "questions": {"queue": {"type": "choice", "instructions": "Which Contoso support queue should take this case?", "label": "sales_ops"},
               "onsite_eligible": {"type": "noul", "label": false},
               "urgency": {"type": "score", "label": 0}}}
```
<!-- /SOURCE:FENCE:1 -->

The two diagrams in Purpose show the system as the customer runs it; the diagram below only shows how we measured: the same test set runs through both the PyTorch path and the laptop path. The PyTorch path and the ground-truth labels exist only during testing; routine device inference needs neither.

<img src="../images/validation-en.png" width="900" alt="The same unlabeled test inputs enter independent PyTorch on H100 and laptop llama.cpp paths. Both predictions enter scoring; labels are used only by the scorer. Accuracy and engine agreement are reported separately.">

*Original explanatory diagram. Accuracy against ground truth and agreement between engines are different metrics. PyTorch evaluation runs on the H100 VM; llama.cpp evaluation and request timing run on the Snapdragon laptop. Sources: [training/evaluation pipeline](../scripts/remote_pipeline_v2.sh), [device evaluation](../scripts/run_engine_eval.ps1), [per-question comparison](../scripts/parity.py). This test topology is not a dependency of routine device inference.*

The following results are **historical measurements from 2026-10-27**, separate from the later single-request trial.

**Measurement boundaries**:

<!-- SOURCE:TABLE:5 -->
| Metric| Measurement location| Measurement start and end| Excludes| 
| ---| ---| ---| ---| 
| Accuracy, Brier, ECE and coverage at the error budget| GPU VM, `kev.benchmark --device cuda`| Score each question once and aggregate by question| Latency| 
| 95% interval of paired differences| Laptop, `summarize_results.py` (10,000 message-group bootstrap samples); protocol `kev.compare` macro-average listed separately| Difference between two configurations on the same questions| Variation across random seeds| 
| Training time| GPU VM, bash `$SECONDS`| Training-process start → checkpoint saved, including base and released-checkpoint loading| Calibration and evaluation| 
| Training GPU memory| GPU VM: maximum `nvidia-smi` sample every 2 seconds and Kev's PyTorch allocation peak| While the training process runs| —| 
| Device request latency| Laptop, `systemone_client.py` → `127.0.0.1:8080`| Client sends one record → receives all 3 answers; sequential, not concurrent| First 2 warm-up requests and model loading| 
| Device process memory| Laptop: read `llama-server` process counters after evaluation| Peak working set (physical process memory) and committed process memory| —| 
| Agreement with PyTorch| Laptop, `parity.py`| Compare answers and probabilities question by question on the same file| —| 
<!-- /SOURCE:TABLE:5 -->

<a id="same-questions"></a>

### 1. Same Questions: Before and After Fine-Tuning

**The customer-facing comparison answers three questions: are business decisions more accurate, do improvements carry over to new questions, and does laptop execution cost change?** Every main-table row compares the same-size released model with the first-round FT-cf recipe, trained on business data plus field variants; the candidate is not changed to whichever model wins each metric. The delivered round-2 C (same recipe plus 206 variants, 4 epochs) gets its own table right after, on the same questions. Policy prompting and the first FT recipe remain separate experimental controls.

Accuracy in the first two tables comes from the same H100 NVL / PyTorch evaluation path. The third table measures laptop CPU latency and memory. These measurement locations are separate: PyTorch accuracy is not the quantized model's device accuracy. [Section 5](#5-laptop-inference-engine) retains the complete on-device results.

**Before and after use the same questions, options, labels and short question instructions for each accuracy or generalization comparison.** Support and assistant routing are different tasks, each compared within its own test set. Generalization uses out-of-distribution questions excluded from weight training, not training questions. The message generator and field distribution change, but the data remains simulated rather than real customer production data. Request hashes and question-level labels are retained in the [original evaluation records](../验证结果/微调评测_20261027-220226/runs).

<!-- TABLE:README_ACC -->
**Accuracy: the same business test questions**

<!-- SOURCE:TABLE:6 -->
| Parameter scale| Test set (questions)| Before fine-tuning: released accuracy| After fine-tuning: final-recipe accuracy| Gain (percentage points)| 
| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution (510 questions)| 44.7%| 86.9%| +42.2| 
| 0.8B| Assistant: in-distribution (477 questions)| 67.1%| 97.5%| +30.4| 
| 4B| Support: in-distribution (510 questions)| 60.8%| 95.9%| +35.1| 
| 4B| Assistant: in-distribution (477 questions)| 81.8%| 99.8%| +18.0| 
<!-- /SOURCE:TABLE:6 -->

**Generalization: the same out-of-distribution questions**

<!-- SOURCE:TABLE:7 -->
| Parameter scale| Test set (questions)| Before fine-tuning: released accuracy| After fine-tuning: final-recipe accuracy| Gain (percentage points)| 
| ---| ---| ---| ---| ---| 
| 0.8B| Support: out-of-distribution (1,011 questions)| 43.0%| 82.5%| +39.5| 
| 0.8B| Assistant: out-of-distribution (951 questions)| 65.7%| 94.4%| +28.7| 
| 4B| Support: out-of-distribution (1,011 questions)| 60.7%| 91.4%| +30.7| 
| 4B| Assistant: out-of-distribution (951 questions)| 81.9%| 98.8%| +16.9| 
<!-- /SOURCE:TABLE:7 -->
<!-- /TABLE:README_ACC -->

**Delivered model, round-2 C: the same questions, how much more it adds on top of FT-cf** (GPU / PyTorch evaluation, the same path as the table above; paired-difference 95% intervals use the cluster bootstrap over messages, 10,000 resamples; full comparison in [the second round](#round2))

<!-- SOURCE:TABLE:8 -->
| Parameter scale| Test set (questions)| Released| First-round FT-cf| Delivered round-2 C| C − FT-cf (points, 95% interval)| 
| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution (510 questions)| 44.7%| 86.9%| **96.3%**| +9.4 (+6.3 ~ +12.6)| 
| 0.8B| Assistant: in-distribution (477 questions)| 67.1%| 97.5%| **100.0%**| +2.5 (+1.3 ~ +3.9)| 
| 0.8B| Support: out-of-distribution (1,011 questions)| 43.0%| 82.5%| **88.4%**| +5.9 (+3.8 ~ +8.1)| 
| 0.8B| Assistant: out-of-distribution (951 questions)| 65.7%| 94.4%| **97.3%**| +2.8 (+1.5 ~ +4.2)| 
<!-- /SOURCE:TABLE:8 -->

4B had no second round; 0.8B C's in-distribution support accuracy of 96.3% passes 4B FT-cf's 95.9%, while its out-of-distribution 88.4% stays below 4B's 91.4%.

**Performance: the same laptop and requests, comparing latency and memory**

Both sides use Snapdragon X Elite X1E80100, llama.cpp b11935 CPU and `-c 8192 -b 2048 -ub 2048 --cache-ram 0`. Both 0.8B models use Q8_0; both 4B models use Q4_K_M. Performance effects are not attributed across model sizes. Each side completes the same 170 support requests and 159 assistant requests, with 3 questions per request. Request timing excludes model loading and warm-up; memory is the process peak working set across the run.

<!-- TABLE:README_PERFORMANCE -->
<!-- SOURCE:TABLE:9 -->
| Fixed model configuration| Performance metric (unit)| Before fine-tuning: released measurement| After fine-tuning: final-recipe measurement| 
| ---| ---| ---| ---| 
| 0.8B / Q8_0 / CPU| Support median request time (ms)| 666| 646| 
| 0.8B / Q8_0 / CPU| Assistant median request time (ms)| 843| 984| 
| 0.8B / Q8_0 / CPU| Peak process working set (MiB)| 2,323| 2,314| 
| 4B / Q4_K_M / CPU| Support median request time (ms)| 3,022| 3,615| 
| 4B / Q4_K_M / CPU| Assistant median request time (ms)| 3,790| 4,751| 
| 4B / Q4_K_M / CPU| Peak process working set (MiB)| 6,849| 6,842| 
<!-- /SOURCE:TABLE:9 -->
<!-- /TABLE:README_PERFORMANCE -->

These are [recorded device runs](../验证结果/端侧引擎_20261027-124700), not GPU evaluation timings. Case IDs, order, labels, input token counts and recorded core settings have been paired. The older device records lack per-request content hashes, so that comparison is not independent proof of byte-identical requests. Each configuration ran once and timing varies between runs: **the observations establish better accuracy, not faster inference caused by fine-tuning, nor that fine-tuning explains the entire latency difference.** The after column of this laptop table is FT-cf; the delivered C, measured on the same laptop, has a peak working set of 2,314 MiB and a commit charge of 5,014 MiB — both equal to FT-cf — and a support median of 635 ms ([device regression](#round2-device)).

#### Experimental Analysis: All Controls and Remaining Errors

The full released, policy-prompted, FT and FT-cf matrix remains in [report section 3.1](Finetuning-and-On-Device-Validation-Report.md#accuracy). [Section 3.3](Finetuning-and-On-Device-Validation-Report.md#policy-following) retains all field-variant results. Those controls explain the recipe choice rather than replacing the main before/after comparison. The field-variant metric counts questions whose correct answer changes with the field: 172 support questions and 72 assistant questions.

- **Both sizes improve on these tests.** Across four main test sets, FT exceeds B0 by 14.7-41.8 percentage points per question; every 95% interval has a lower bound above 0. FT-cf adds 0.4-4.0 points over FT, although the intervals for the two 0.8B support sets include 0. See [report section 3.1](Finetuning-and-On-Device-Validation-Report.md#accuracy) for intervals and the protocol's `kev.compare` definition.
- **Policy prompting is substantially below fine-tuning.** B0-policy is 10.5-30.2 points below FT. On the 0.8B out-of-distribution assistant set, it is worse than B0: 63.6% versus 65.7%.
- **Field-dependent policy application remains the main weakness.** For changed-answer questions, FT-to-FT-cf support/assistant accuracy rises from 48.3%/48.6% to 57.6%/81.9% for 0.8B, and from 72.1%/86.1% to 84.9%/100.0% for 4B. Combining test and out-of-distribution variants, 0.8B still scores only 41.9% on purchase age, 36.2% on region and 49.2% on battery cycles. See [report section 3.3](Finetuning-and-On-Device-Validation-Report.md#policy-following).
- **Selection was specified before the second recipe's results.** Recommend FT-cf only when development-variant accuracy improves and original development accuracy drops by no more than 1 percentage point. Both sizes qualify. On all development-variant questions, support/assistant scores change from 78.9%/82.9% to 82.2%/92.8% for 0.8B, and from 89.1%/96.4% to 95.9%/100.0% for 4B. Neither loses accuracy on original development questions.

### 2. Retention of General Capability

This is the second question under [criterion ⑤](../README.md#criteria): the previous section's out-of-distribution questions ask “does it still work on new business data”; this section asks whether, after adapting to the business, the model lost its prior general-task capability. Each before/after pair uses the same 656 public Kev questions. Both FT and FT-cf recipes are retained below; the delivered round-2 C scores 65.2% on the same set (+0.5 points over the release, below the trigger line; [second round](#round2)).

<!-- TABLE:PUBLIC -->
<!-- SOURCE:TABLE:10 -->
| Model and recipe| General questions| Released accuracy| Fine-tuned accuracy| Change (percentage points)| 
| ---| ---| ---| ---| ---| 
| 0.8B FT| 656| 64.8%| 64.8%| 0.0| 
| 0.8B FT-cf| 656| 64.8%| 64.8%| 0.0| 
| 4B FT| 656| 81.7%| 80.9%| -0.8| 
| 4B FT-cf| 656| 81.7%| 82.6%| +0.9| 
<!-- /SOURCE:TABLE:10 -->

**Confidence on general questions: lower Brier is better.**

<!-- SOURCE:TABLE:11 -->
| Model and recipe| Released Brier| Fine-tuned Brier| 
| ---| ---| ---| 
| 0.8B FT| 0.430| 0.560| 
| 0.8B FT-cf| 0.430| 0.574| 
| 4B FT| 0.243| 0.299| 
| 4B FT-cf| 0.243| 0.269| 
<!-- /SOURCE:TABLE:11 -->
<!-- /TABLE:PUBLIC -->

- **The predefined forgetting threshold was not triggered.** The threshold is an accuracy drop greater than 2 percentage points. Both 0.8B recipes remain at the released model's 64.8%. FT corrects 20 answers but breaks 20 others; FT-cf corrects 22 and breaks 22. The 4B FT score falls from 81.7% to 80.9%, or 5 fewer correct answers out of 656; FT-cf reaches 82.6%, or 6 more. This does not mean every general task is unchanged.
- **Confidence quality on general questions worsens.** Business calibration changes 0.8B's temperature from 2.35 to 1.26, making probabilities sharper. Recomputing 0.8B FT at the released temperature of 2.35 gives Brier 0.490, still worse than 0.430 before fine-tuning. Weight changes therefore also contribute. For 4B, FT at temperature 1.66 changes Brier from 0.243 to 0.299; FT-cf at 2.35 scores 0.269. A model serving both vendor and general decisions should be calibrated on mixed data.

### 3. Calibration: Correct Ranking Does Not Guarantee Reliable Probabilities

**Fine-tuning learns which answer to choose; calibration adjusts the probabilities assigned to those answers.** The model produces logits (the pointer-head scores z of the previous section) and converts them with `softmax(logits / T)`. T is a dimensionless positive number, not accuracy or a business threshold. An already-trained model can keep all its weights while T is refitted; repeating the same training run is unnecessary for a probability-only adjustment.

Calibration data supplies inputs, questions, candidate options and correct labels, not a target probability table. Vendor-policy code computes the labels here; a language model only generates simulated messages and does not judge calibration. Training data updates weights, development data selects a recipe, calibration data fits T, and data excluded from selection is used for acceptance. Inference applies the saved T without refitting it.

As a mathematical illustration, three options at 80% / 10% / 10% with T = 1 become approximately 58.6% / 20.7% / 20.7% with T = 2. This is not a measurement. Positive T preserves option ranking within a question and cannot repair a wrong first choice. It can change probabilities, expected ordinal scores and threshold decisions. Summing to 100% proves normalization, not calibration; one wrong prediction does not by itself establish failed calibration either.

The recorded 0.8B FT-cf fit uses **984 calibration questions** and reports T approximately 1.15. Fit-set accuracy stays at 93.0%, while ECE changes from 0.011 to 0.008. The five-fold cross-validation interval for the ECE difference includes zero, so **a statistically significant improvement is not established**. The delivered round-2 C, fitted on the same calibration questions, gets T = 2.83 (fit-set accuracy 96.6% unchanged, ECE 0.025 → 0.010): two more epochs made the model more over-confident and the calibration step pulled it back — the live example of "re-calibrate after retraining" ([second round](#round2)). The 121 candidate temperatures recompute probabilities from saved scores and compare mean NLL; they are not 121 training runs. [Report section 3.4](Finetuning-and-On-Device-Validation-Report.md#calibration-guide) contains the examples, actual command and raw evidence.

**Customers receive a GGUF with calibration parameters inside it.** The engine applies that temperature after loading the file; no separate calibration service is required. Requests for clarification or human review belong to the business application; this repository provides no automatic handoff or model fallback. If answer quality is inadequate, improve the data and training rather than just changing T. For a probability-only adjustment, use the [calibration-only update workflow](Operations-Guide.md#calibration-update).

#### When Re-Calibrating Is Enough and When Retraining Is Required: The Rule and the Measured Boundary

The decision rests on two facts, both computable offline from saved per-question results without re-running the model:

1. **Are the answers right (accuracy)?** Changing T changes no answer — a mathematical property, also checked numerically here: for all 16 model × test-set combinations, accuracy is identical to every digit at 71 temperatures between 0.5 and 4.0. So when accuracy is insufficient, or has fallen outside its earlier 95% interval on new data, **calibration can do nothing; only data and retraining can**.
2. **Are the probabilities right (ECE), and how much of the error can one scalar T remove?** Sweep T from 0.5 to 4.0 over the new data's per-question scores and take the T with the lowest ECE: the drop from the current T to that optimum is the part "re-calibration fixes"; the ECE left at the optimum is the part "calibration cannot fix". If the current T's ECE still lies inside its own 95% bootstrap interval, it is noise and nothing should change.

The table below is that boundary computed for both FT-cf sizes of this project ([scripts/calibration_boundary.py](../scripts/calibration_boundary.py), input = the raw scores saved by the GPU evaluation; the "best T" is chosen on the same test set, so it is an upper bound, not a deployable value):

<!-- SOURCE:TABLE:12 -->
| Model and test set| Accuracy (identical at every T; 95% interval)| ECE: uncalibrated, T = 1| ECE: shipped T (95% interval)| ECE: best T for this set| Most that re-calibration can remove| Not fixable by calibration| 
| ---| ---| ---| ---| ---| ---| ---| 
| 0.8B FT-cf, support · in distribution (510 questions)| 86.9% (83.7–89.8%)| 0.032| 0.030 (T = 1.15; 0.021–0.055)| 0.021 (T = 1.35)| 0.009| 0.021| 
| 0.8B FT-cf, assistant · in distribution (477 questions)| 97.5% (95.8–98.7%)| 0.005| 0.013 (T = 1.15; 0.008–0.025)| 0.005 (T = 1.0)| 0.007| 0.005| 
| 0.8B FT-cf, support · out of distribution (1,011 questions)| 82.5% (80.1–84.8%)| 0.074| **0.064** (T = 1.15; 0.051–0.086)| 0.016 (T = 2.15)| **0.048**| 0.016| 
| 0.8B FT-cf, assistant · out of distribution (951 questions)| 94.4% (92.8–95.8%)| 0.022| 0.018 (T = 1.15; 0.011–0.032)| 0.005 (T = 1.65)| 0.012| 0.005| 
| 4B FT-cf, support · in distribution (510 questions)| 95.9% (94.1–97.5%)| 0.023| 0.019 (T = 2.35; 0.012–0.035)| 0.012 (T = 1.65)| 0.007| 0.012| 
| 4B FT-cf, support · out of distribution (1,011 questions)| 91.4% (89.6–93.1%)| 0.057| 0.023 (T = 2.35; 0.016–0.040)| 0.015 (T = 2.8)| 0.008| 0.015| 
| 0.8B round-2 C (delivered), support · in-distribution (510 questions)| 96.3% (94.5–97.8%)| 0.022| 0.025 (T=2.83; 0.015–0.041)| 0.009 (T=1.55)| 0.016| 0.009| 
| 0.8B round-2 C (delivered), support · out-of-distribution (1,011 questions)| 88.4% (86.5–90.3%)| 0.087| 0.055 (T=2.83; 0.039–0.073)| 0.026 (T=4.0)| 0.029| 0.026| 
<!-- /SOURCE:TABLE:12 -->

Four conclusions for this project:

- **In distribution, the shipped T is already good enough; do not tune it.** In all six rows the shipped T's ECE lies inside its own 95% interval, and even the set's own optimal T would lower it by only 0.007–0.009, less than the interval width. The calibration lever is already inside the noise.
- **After a distribution shift, most of the support probability error is what calibration can fix.** Of the 0.8B out-of-distribution support ECE of 0.064, 0.048 disappears by refitting T from 1.15 to about 2.15, leaving 0.016 — the in-distribution level. This is the typical "the model is as accurate as before on the new data, merely over-confident" case: **the calibration-only update is the right move**. The price is flatter probabilities: at the same 90% automation threshold, coverage falls from 71.7% to 60.9% while accuracy of the automated part rises from 94.3% to 97.4%.
- **But the 4.4-point accuracy drop from 86.9% to 82.5% is untouched by calibration.** 82.5% already lies outside the in-distribution 95% interval (83.7–89.8%); that is the "must retrain" signal, and what retraining has to learn is what the out-of-distribution data adds — more Singapore, offline and metered-network cases and two requests in one message (see [the test data](#how-the-tests-work)). Calibration and retraining are not alternatives: in this case do both, retrain first, then refit T on the new data.
- **One scalar T cannot serve two distributions.** The optimal T for 0.8B support is 1.35 in distribution and 2.15 out of distribution; applied back to the in-distribution set, 2.15 gives ECE 0.031 (0.030 at the shipped T, 0.021 at the optimum 1.35) — no worse, but it also cannot reach the in-distribution optimum. Fit T on a calibration set from the same distribution as production traffic, and refit when that distribution changes. By question type, the 0.8B out-of-distribution support error concentrates in the urgency grade (ECE 0.107) and the queue choice (0.070); yes/no questions are better (0.042).

Operationally: after go-live, periodically sample a labeled batch of new data, run `kev.benchmark` once for per-question scores, then run `scripts/calibration_boundary.py`. Accuracy inside its interval and ECE inside its interval → change nothing; accuracy inside, ECE outside and mostly removable by T → refit T only ([steps](Operations-Guide.md#calibration-update)); accuracy outside its interval → add data and retrain, then calibrate. These thresholds are this project's simulated-data numbers; recompute them the same way on your own data.

<a id="gpu-bf16-baseline"></a>

### GPU Accuracy Baseline: Before Quantization

These two rows come from PyTorch evaluation on the GPU host, not from laptop runs. They retain FT-cf accuracy before quantization and BF16 file information; they do not supply laptop latency, memory or loading measurements. See the [quantized laptop comparison](#from-the-released-model-to-the-quantized-fine-tuned-model-accuracy-speed-and-resources-in-one-table).

<!-- SOURCE:TABLE:13 -->
| Model and recipe| Weight format| Weight precision (bits per weight)| File (MiB)| Support / assistant accuracy (GPU / PyTorch)| 
| ---| ---| ---| ---| ---| 
| 0.8B FT-cf| BF16| 16.0| 1,437| 86.9% / 97.5%| 
| 4B FT-cf| BF16| 16.0| 8,026| 95.9% / 99.8%| 
<!-- /SOURCE:TABLE:13 -->

Device agreement is measured against the PyTorch model of the same size and recipe: released against released, FT against FT, FT-cf against FT-cf, and round-2 C against round-2 C. Different fine-tuning versions do not share one reference model.

### 4. Training Resources

<!-- TABLE:TRAIN -->
<!-- SOURCE:TABLE:14 -->
| Model and recipe| micro-batch × accum| Records processed (2 epochs)| Optimizer steps| 
| ---| ---| ---| ---| 
| 0.8B FT| 1 × 8| 6,294| 788| 
| 0.8B FT-cf| 4 × 2| 9,664| 1,208| 
| 4B FT| 4 × 2| 6,294| 788| 
| 4B FT-cf| 4 × 2| 9,664| 1,208| 
<!-- /SOURCE:TABLE:14 -->

<!-- SOURCE:TABLE:15 -->
| Model and recipe| Wall-clock time| Whole-device GPU peak (nvidia-smi)| PyTorch allocation peak| Calibration temperature| 
| ---| ---| ---| ---| ---| 
| 0.8B FT| 26.9 minutes| 4,555 MiB| 3,460 MiB| 1.26| 
| 0.8B FT-cf| 11.6 minutes| 7,573 MiB| 5,326 MiB| 1.15| 
| 4B FT| 15.7 minutes| 33,359 MiB| 22,581 MiB| 1.66| 
| 4B FT-cf| 20.1 minutes| 26,215 MiB| 22,641 MiB| 2.35| 
<!-- /SOURCE:TABLE:15 -->
<!-- /TABLE:TRAIN -->

The delivered **0.8B round-2 C** is not in the first-round result package above; on the same basis: micro-batch 4 × accum 2, 4 epochs = 20,152 training records, 2,520 steps; wall clock 22 min 42 s, whole-card GPU memory peak 7,475 MiB, PyTorch allocation peak 5,311 MiB, calibration temperature 2.83 ([second round](#round2)). Memory equals FT-cf's; time grows linearly with the number of training records.

- 0.8B FT takes about 27 minutes with micro-batch 1. FT-cf uses micro-batch 4, sees 54% more training records and takes about 12 minutes. Data and micro-batch both change, so the entire time difference cannot be attributed to one parameter. At micro-batch 4 and 9,664 processed records, 4B FT-cf takes 20.1 minutes versus 11.6 minutes for 0.8B. Effective batch is 8 throughout.
- Here `nvidia-smi` samples whole-device memory, potentially including framework caches and other processes. PyTorch's allocation peak also excludes some runtime overhead. The two 4B allocation peaks are almost equal, 22,581/22,641 MiB, while whole-device peaks differ by 7,144 MiB. Caching is a possibility, not an established cause; tensor allocations alone are not a sufficient GPU-sizing rule.
- **Micro-batch 1 reduces memory demand.** An 8-step probe on the 64 longest vendor records, with bf16, gradient checkpointing, `max_state 768`, micro-batch 1 and accumulation 8, ran with no other GPU process. Whole-device peaks were 4,213 MiB for 0.8B and 18,547 MiB for 4B; PyTorch allocations were 3,365/17,375 MiB. The probe omitted Kev replay records. Full 0.8B FT at micro-batch 1 allocated 3,460 MiB, about 3% above its probe. Leave headroom.
- At this VM's list price of USD 9.07 per hour, one 0.8B training run costs approximately USD 1.8-4.1 and one 4B run USD 2.4-3.0. Source: Azure Retail Prices API, Spain Central, 2026-10-27. Actual subscription discounts were not checked.

### 5. Laptop Inference Engine

Test hardware: Snapdragon X Elite X1E80100, 12 CPU cores, 64 GB RAM, Adreno X1-85 GPU with driver 31.0.133.1, and Windows 11 Enterprise. Runtime: official llama.cpp b11935 Windows ARM64 CPU and Adreno OpenCL packages.

<!-- TABLE:ENGINE -->
<!-- SOURCE:TABLE:16 -->
| Model, quantization and runtime settings| Support accuracy: device (PyTorch)| Assistant accuracy: device (PyTorch)| Support agreement: device vs. PyTorch| Assistant agreement: device vs. PyTorch| 
| ---| ---| ---| ---| ---| 
| Released 0.8B<br>Q8_0 · CPU, default settings| 45.7% (44.7%)| 66.9% (67.1%)| 97.6%| 99.0%| 
| Released 0.8B<br>Q8_0 · CPU, defaults; full policy prompt (B0-policy)| 60.6% (60.8%)| 71.7% (71.9%)| 98.6%| 99.8%| 
| Released 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 43.7% (44.7%)| 66.5% (67.1%)| 94.9%| 96.4%| 
| Released 4B<br>Q4_K_M · CPU, default settings| 59.0% (60.8%)| 82.0% (81.8%)| 93.1%| 97.3%| 
| Fine-tuned FT 0.8B<br>Q4_K_M · CPU, default settings| 87.5% (86.5%)| 93.9% (93.5%)| 94.9%| 97.9%| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, default settings| 86.5% (86.5%)| 93.5% (93.5%)| 99.2%| 99.6%| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, -c 2048 -ub 512| 86.5% (86.5%)| 93.5% (93.5%)| 99.2%| 99.6%| 
| Fine-tuned FT 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 85.7% (86.5%)| 93.7% (93.5%)| 97.6%| 99.0%| 
| Fine-tuned FT-cf 0.8B<br>Q8_0 · CPU, default settings| 86.9% (86.9%)| 97.7% (97.5%)| 99.2%| 99.8%| 
| Fine-tuned FT-cf 4B<br>Q4_K_M · CPU, default settings| 95.3% (95.9%)| 99.6% (99.8%)| 98.2%| 99.8%| 
| Fine-tuned FT-cf 4B<br>Q8_0 · CPU, default settings| 96.1% (95.9%)| 99.8% (99.8%)| 99.4%| 100.0%| 
<!-- /SOURCE:TABLE:16 -->

<!-- SOURCE:TABLE:17 -->
| Model, quantization and runtime settings| Model file (MiB)| Peak working set (MiB)| Committed memory (MiB)| 
| ---| ---| ---| ---| 
| Released 0.8B<br>Q8_0 · CPU, default settings| 775| 2,323| 5,016| 
| Released 0.8B<br>Q8_0 · CPU, defaults; full policy prompt (B0-policy)| 775| 3,446| 5,899| 
| Released 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 775| 4,118| 5,809| 
| Released 4B<br>Q4_K_M · CPU, default settings| 2,893| 6,849| 7,497| 
| Fine-tuned FT 0.8B<br>Q4_K_M · CPU, default settings| 528| 1,819| 4,766| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, default settings| 775| 2,314| 5,014| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, -c 2048 -ub 512| 775| 2,196| 2,119| 
| Fine-tuned FT 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 775| 4,105| 5,801| 
| Fine-tuned FT-cf 0.8B<br>Q8_0 · CPU, default settings| 775| 2,314| 5,014| 
| Fine-tuned FT-cf 4B<br>Q4_K_M · CPU, default settings| 2,893| 6,842| 7,495| 
| Fine-tuned FT-cf 4B<br>Q8_0 · CPU, default settings| 4,276| 9,609| 8,884| 
<!-- /SOURCE:TABLE:17 -->

<!-- SOURCE:TABLE:18 -->
| Model, quantization and runtime settings| Support median request time (ms)| Assistant median request time (ms)| 
| ---| ---| ---| 
| Released 0.8B<br>Q8_0 · CPU, default settings| 666| 843| 
| Released 0.8B<br>Q8_0 · CPU, defaults; full policy prompt (B0-policy)| 4,353| 2,435| 
| Released 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 1,171| 1,378| 
| Released 4B<br>Q4_K_M · CPU, default settings| 3,022| 3,790| 
| Fine-tuned FT 0.8B<br>Q4_K_M · CPU, default settings| 812| 909| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, default settings| 669| 822| 
| Fine-tuned FT 0.8B<br>Q8_0 · CPU, -c 2048 -ub 512| 1,163| 1,184| 
| Fine-tuned FT 0.8B<br>Q8_0 · Adreno GPU (OpenCL), default settings| 1,035| 1,221| 
| Fine-tuned FT-cf 0.8B<br>Q8_0 · CPU, default settings| 646| 984| 
| Fine-tuned FT-cf 4B<br>Q4_K_M · CPU, default settings| 3,615| 4,751| 
| Fine-tuned FT-cf 4B<br>Q8_0 · CPU, default settings| 3,649| 4,115| 
<!-- /SOURCE:TABLE:18 -->

Incomplete runs excluded from the tables: `ft-kev-0.8b-Q8_0-cpu-ctx2048` (144 support records, no summary) and `ft-kev-4b-Q4_K_M-cpu` (36 support records, no summary).
<!-- /TABLE:ENGINE -->

#### From the Released Model to the Quantized Fine-Tuned Model: Accuracy, Speed and Resources in One Table

The two tables below contain only configurations actually run on the Snapdragon laptop: the released and fine-tuned Q8_0 / Q4_K_M models. Pre-quantization BF16 results are listed separately in the [GPU accuracy baseline](#gpu-bf16-baseline), not as laptop runs. Each agreement value compares the row with its own same-size, same-recipe PyTorch model; FT Q4_K_M must not use FT-cf as its reference.

<!-- SOURCE:TABLE:19 -->
| Model (0.8B, Snapdragon X Elite CPU, default settings)| Weight precision (bits per weight)| File (MiB)| Support / assistant accuracy| Per-question agreement with its own PyTorch model| Support / assistant median request time (ms)| Peak working set (MiB)| Model load (s)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| Released B0, official Q8_0 package| 8.5| 775| 45.7% / 66.9%| 97.6% / 99.0%| 666 / 843| 2,323| Not recorded| 
| Fine-tuned FT-cf, Q8_0| 8.5| 775| 86.9% / 97.7%| 99.2% / 99.8%| 646 / 984| 2,314| 2.6| 
| Fine-tuned FT, Q4_K_M (the FT-cf 4-bit file was not brought to the laptop; same-architecture FT stands in)| 5.8| 528| 87.5% / 93.9% (its BF16: 86.5% / 93.5%)| 94.9% / 97.9%| 812 / 909| 1,819| 2.5| 
<!-- /SOURCE:TABLE:19 -->

<!-- SOURCE:TABLE:20 -->
| Model (4B, Snapdragon X Elite CPU, default settings)| Weight precision (bits per weight)| File (MiB)| Support / assistant accuracy| Per-question agreement with its own PyTorch model| Support / assistant median request time (ms)| Peak working set (MiB)| Model load (s)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| Released B0, official Q4_K_M package| 5.8| 2,893| 59.0% / 82.0%| 93.1% / 97.3%| 3,022 / 3,790| 6,849| Not recorded| 
| Fine-tuned FT-cf, Q8_0| 8.5| 4,276| 96.1% / 99.8%| 99.4% / 100.0%| 3,649 / 4,115| 9,609| 10.7| 
| Fine-tuned FT-cf, Q4_K_M| 5.8| 2,893| 95.3% / 99.6%| 98.2% / 99.8%| 3,615 / 4,751| 6,842| 6.7| 
<!-- /SOURCE:TABLE:20 -->

- **Fine-tuning gains far outweigh quantization losses.** 0.8B: fine-tuning lifts support accuracy from 45.7% to 86.9% (+41.2 points); 8-bit quantization moves it by 0.0 / +0.2 points relative to BF16, and 506 of 510 support answers stay the same. 4B likewise: +37.1 points versus +0.2 / 0.0.
- **8-bit is near-lossless; 4-bit shows a visible loss.** Per-question agreement with BF16 is 99.2%–100% at 8 bits and 94.9%–98.2% at 4 bits, i.e. 2%–5% of the questions change their answer. The 0.8B 4-bit accuracy being 1 point above BF16 means a few changed answers happened to become correct, not that the model got better.
- **Quantization saves file size and memory, not time.** Files 1,437 → 775 → 528 MiB; peak working set 2,314 → 1,819 MiB; but a 4-bit request is not faster than 8-bit (812 vs. 646 ms), because llama.cpp's CPU kernels unpack 4-bit weights before computing.
- **"0.8B is small" refers to the parameter count, not the file.** 0.8B × 16 bits is a 1.4 GB file; only at 8 bits does it become 0.76 GB. Everything that runs on the laptop, and every device figure on this page, is the quantized file.
- **The delivered round-2 C was also measured in 4-bit** (x86-64 VM): support 95.3% versus Q8_0's 96.5%, agreement with PyTorch 97.1% versus 99.0%, no process-memory saving — the same conclusion as the FT 4-bit row above; details in the [device regression](#round2-device).
- **Load time**: Q8_0 0.8B 2.6 s, 4B 10.7 s; Q4_K_M 4B 6.7 s; smaller files load faster. The three released-model runs were the earliest manual runs and did not record load time.
- **Not done**: neither the released model's BF16 nor the fine-tuned BF16 ran on the laptop (the BF16 files stayed on the GPU host as quantization sources; the host has been released); As for the fine-tuning method, both this project and the Kev author's recipe train only the LoRA adapters and the pointer head; under the same LoRA recipe, 4B lifts the "change one field, the answer must follow" questions from 0.8B's 57.6% / 81.9% to 84.9% / 100% (section 1), so 0.8B's weakness is model capacity, not the adapter.

#### Inference Optimization: Which Levers Were Measured

The table below gathers the inference-side variables already measured in the three tables above. Each row changes one variable; values are taken directly from those tables (0.8B uses the FT rows, which cover the most configurations). "Not tested" marks a combination that was not run, not a conclusion. Each configuration ran once, and paired latency between two runs of the same architecture differed by up to 24% (see "Single-run latency varies" below), so latency differences within 20% are not interpreted. The last row, "CPU architecture", changes the whole machine; its values come from the next subsection and only answer whether the answers stay the same.

<!-- SOURCE:TABLE:21 -->
| Optimization lever| Comparison (baseline → change)| Accuracy (support / assistant)| Median support decision (ms)| Peak working set (MiB)| One-line conclusion| 
| ---| ---| ---| ---| ---| ---| 
| Weight quantization| 0.8B FT Q8_0 → Q4_K_M (CPU, default arguments)| 86.5% / 93.5% → 87.5% / 93.9%| 669 → 812| 2,314 → 1,819| File 247 MiB smaller and memory 495 MiB lower, but not faster; agreement with PyTorch fell from 99.2% / 99.6% to 94.9% / 97.9%. The 1-point higher accuracy is quantization noise that happened to favor correct answers, not an improvement| 
| Weight quantization| 4B FT-cf Q8_0 → Q4_K_M (CPU, default arguments)| 96.1% / 99.8% → 95.3% / 99.6%| 3,649 → 3,615| 9,609 → 6,842| File 1,383 MiB smaller and memory 2,767 MiB lower; support accuracy 0.6 points below PyTorch. Usable when 4B memory is tight| 
| Context length (`-c`) and batch size| 0.8B FT Q8_0 `-c 8192 -ub 2048` → `-c 2048 -ub 512`| 86.5% / 93.5% → unchanged| 669 → 1,163| 2,314 → 2,196 (commit charge 5,014 → 2,119)| Commit charge 2,895 MiB lower; the cost is 74% slower on support and 44% slower on assistant, accuracy unchanged. Inputs are only about 500 tokens, so most of the 8192 context was unused| 
| Compute backend| 0.8B FT Q8_0 CPU → Adreno GPU (OpenCL, `-ngl 99`)| 86.5% / 93.5% → 85.7% / 93.7%| 669 → 1,035| 2,314 → 4,105| The GPU is slower, the process working set is 1,791 MiB higher, about 3,400 MiB of shared GPU memory is used in addition, and agreement fell to 97.6% / 99.0%. Not the choice on this laptop| 
| Prompt length| Released 0.8B Q8_0, short description → full policy text in the prompt (B0-policy)| 45.7% / 66.9% → 60.6% / 71.7%| 666 → 4,353| 2,323 → 3,446| Median input tokens per record 488 → 1,505, 6.5× slower and 1.1 GB more memory; accuracy still far below fine-tuning (FT-cf 86.9% / 97.7%). Rules belong in the weights, not in every prompt| 
| Model size| Released 4B Q4_K_M → fine-tuned 0.8B FT-cf Q8_0 (both CPU, default arguments)| 59.0% / 82.0% → 86.9% / 97.7%| 3,022 → 646| 6,849 → 2,314| A fine-tuned small model beats an untuned larger one: 27.9 / 15.7 points more accurate, 3.9–4.7× faster, about one third of the memory| 
| Input length| 0.8B FT-cf Q8_0, x86-64 VM, input per question 220 → 7,700 tokens (same 40 tickets plus a synthetic log)| Not applicable (the padding is not a real question; cost only); real questions in the next row| 1,450 → 40,706| 1,552 → 5,061 (commit charge 4,254 → 5,970)| Time grows linearly with length at about 190 tokens per second; once the KV cache is filled the working set grows 3.3×. See the "Long inputs" subsection below| 
| Real long inputs| 0.8B round-2 C Q8_0, x86-64 VM, 160 tickets with a case history, 3,034–8,052 tokens per question, the history decides the answer| **44.9%** (same 160 records without history 63.1%; original short inputs 96.5%); 7 records over the window refused| 26,395 (without history 2,578)| 5,060 (commit charge 5,970)| Cannot read the history: not ignored but thrown off, controls 0 / 53; 8,192 is a hard wall. See [real long inputs](#long-real)| 
| Concurrent requests| 0.8B FT-cf Q8_0, x86-64 VM, client requests in flight 1 → 8 (server: 4 slots)| 87.1% / 97.9% → 87.1% / 97.7%| 1,183 → 9,086| 1,399 → 1,401| Throughput does not grow (0.79 → 0.81 requests per second) while latency queues linearly with requests in flight; one request already saturates the 8 compute threads. `-np 8` does not add throughput either. See "Concurrency" below| 
| NPU (Hexagon)| Not tested| —| —| —| Requires driver test-signing on Windows, which was not enabled on the company laptop| 
| Speculative decoding, KV-cache reuse| Not applicable| —| —| —| The decision endpoint generates no tokens, so there is no decode phase; `--cache-ram 0` disables the prompt cache| 
| CPU architecture| 0.8B FT-cf Q8_0, Snapdragon X Elite laptop (ARM64 package) → AMD EPYC 7763 Azure VM (x64 package), both CPU with default settings| 86.9% / 97.7% → 87.1% / 97.9%| 646 → 1,168–1,255| 2,314 → 1,400–1,552| The same model file, llama.cpp release and arguments run unchanged on an x86-64 CPU: 983 of 987 answers are identical and two runs gave exactly the same results. The whole machine changed (processor, OS, 8 vs. 12 threads), so latency and memory differences are not attributed to the architecture| 
<!-- /SOURCE:TABLE:21 -->

- **The device runs the fine-tuned model.** Export merges LoRA into the base and writes the calibrated temperature into GGUF: 1.2599 for 0.8B FT, 1.1487 for 0.8B FT-cf and 2.3511 for 4B FT-cf, each equal to its calibration result.
- **Q8_0 agrees with PyTorch almost question by question.** For 0.8B FT Q8_0 on CPU, accuracy matches PyTorch; 506/510 support and 475/477 assistant answers agree. FT-cf has 506 and 476 agreements; its sole assistant disagreement is close to 0.5 in both runtimes, 0.528 versus 0.572. For 4B FT-cf Q8_0, 507 support and all 477 assistant answers agree; the three support disagreements have selected-answer probabilities of only 0.48-0.51, and llama.cpp gets one additional question right, 96.1% versus 95.9%.
- **Prefer Q8_0 on CPU; consider Q4_K_M for 4B when memory is tight.** The reasons are the quantization and backend rows of the table above.
- **Memory can be traded for latency.** Defaults are `-c 8192 -b 2048 -ub 2048`, with 4 parallel slots. Changing to `-c 2048 -ub 512` reduces committed memory from 5,014 to 2,119 MiB without changing accuracy, but raises request time to about 1.2 seconds.
- **Policy prompts cost more on the device.** Median input tokens increase from 488 to 1,505 for support, and from 456 to 813 for assistant routing. One decision takes about 4.4 seconds and 2.4 seconds, respectively.
- **An untuned 4B model is not a substitute for tuning 0.8B.** On the same laptop CPU, released 4B Q4_K_M scores 59.0%/82.0%, versus 86.9%/97.7% for 0.8B FT-cf Q8_0, a deficit of 27.9/15.7 points. Median latency is 3,022/3,790 ms versus 646/984 ms, or 3.9-4.7 times as long. Peak working set is 6,849 versus 2,314 MiB, roughly 3 times as much.
- **Single-run latency varies; differences within 20% are not interpreted.** 0.8B FT and FT-cf have the same architecture and identical input-token counts per record. Paired by record, FT-cf is 53 ms faster on support and 166 ms slower on assistant, approximately -8%/+20%. Each configuration was measured once. Q4_K_M-versus-Q8_0 differences of +21% on support and +11% on assistant are of similar size, unlike Adreno (+49% to +76%), the smaller context/micro-batch (+74% support, +44% assistant) or policy prompting (2.9-6.5 times the latency).
- **For 4B, interpret only the order of magnitude: about 3-5 seconds per decision.** Across three 4B runs (released Q4_K_M, FT-cf Q8_0, FT-cf Q4_K_M), tokens also match per record, but paired medians differ by 7-24%; even released versus fine-tuned Q4_K_M differs by 23-24%. At assistant record 139 in the 4B FT-cf Q8_0 run, the laptop entered standby for 5.4 hours; including that request gives a 4,115 ms median, excluding it 4,113 ms. Q4_K_M ran after resume. This experiment cannot rank the two quantizations by speed.

#### On an x86-64 CPU: The Same Model File Runs Unchanged

The laptop above has an ARM processor. To answer "does it still run on an x86-64 CPU", the same model file (`Contoso-Kev-0.8B-FTcf-Q8_0.gguf`, SHA-256 identical to the laptop copy) was loaded on an Azure virtual machine: AMD EPYC 7763, 8 vCPU (16 threads, 2.45 GHz), 64 GB RAM, Windows Server 2025, no GPU. The runtime was `llama-b11935-bin-win-cpu-x64.zip` from the same release page, with unchanged server arguments (`-c 8192 -b 2048 -ub 2048 --cache-ram 0`). The same 170 support and 159 assistant requests ran twice and were compared with the same PyTorch per-question results. The client script on the same VM sent the requests to `127.0.0.1:8080` and timed them at the client, as on the laptop.

<!-- SOURCE:TABLE:22 -->
| Metric| Snapdragon X Elite laptop (ARM64 package; the FT-cf 0.8B row above)| AMD EPYC 7763 Azure VM (x64 package): run 1 / run 2| 
| ---| ---| ---| 
| Support accuracy (PyTorch on the same test set: 86.9%)| 86.9%| 87.1% / 87.1%| 
| Assistant accuracy (PyTorch on the same test set: 97.5%)| 97.7%| 97.9% / 97.9%| 
| Support agreement: device vs. PyTorch| 99.2%| 99.0% / 99.0%| 
| Assistant agreement: device vs. PyTorch| 99.8%| 99.6% / 99.6%| 
| Questions with the same answer as Snapdragon: support 510 / assistant 477| —| 507 / 476 (99.4% / 99.8%), identical in both runs| 
| Questions with the same answer across the two runs (987 total)| Single run| 987, probabilities identical to every digit| 
| Peak working set (MiB)| 2,314| 1,552 / 1,400| 
| Committed memory (MiB)| 5,014| 4,254 / 4,254| 
| Support median request time (ms)| 646| 1,255 / 1,168| 
| Assistant median request time (ms)| 984| 1,401 / 1,332| 
| Engine threads (llama-server default)| 12| 8| 
<!-- /SOURCE:TABLE:22 -->

- **The answers agree.** 983 of 987 questions get the same answer on both machines; the 4 that differ are all questions whose top two options have close probabilities (selected-answer probability 0.32–0.62). x86-64 gets 3 more right and 1 fewer, hence an accuracy 0.2 points higher — these are flips near 0.5, not a more accurate x86-64. The median per-question probability difference is 0.00003, the maximum 0.151. Agreement with PyTorch is 99.0% / 99.6%, the same level as Snapdragon's 99.2% / 99.8%.
- **Two runs on the same machine are exactly identical.** Answers and probabilities of all 987 questions match to every digit; only latency moves (support median 1,255 → 1,168 ms, a 7% difference).
- **Latency is not compared with the laptop.** This is an 8-vCPU virtual machine at 2.45 GHz against a 12-core laptop at 3.4 GHz, with 8 versus 12 engine threads; the only statement is that one decision takes about 1.2–1.4 seconds on this VM.
- **Memory is lower than on the laptop.** Peak working set 1,400–1,552 MiB versus 2,314 MiB, commitment 4,254 MiB versus 5,014 MiB, same arguments; the cause of the difference was not broken down.
<a id="round2-device"></a>

**The round-2 C model on the same machine: the accuracy gained on the GPU survives quantization and the engine.** The C model from the [second fine-tuning round](#round2) (more data + 4 epochs, calibration temperature T = 2.83) was exported as `Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf` (775 MiB, SHA-256 `c427ed7a…08ad05`, full value in the [export manifest](../验证结果/第二轮微调评测_20261101-101948/gguf/0.8b-r2C/gguf.sha256)) and loaded on the same VM as the table above, with the same engine package, the same server arguments and the same 329 requests, compared per question with the published FT-cf; then run once more with `-c 2048 -b 512 -ub 512` to see whether the lean arguments change any answer.

<!-- SOURCE:TABLE:23 -->
| Metric (same AMD EPYC 7763 VM, llama.cpp b11935 x64, CPU)| Published FT-cf Q8_0, default arguments| Round-2 C Q8_0, default arguments: run 1 / run 2| Round-2 C Q8_0, `-c 2048 -ub 512`| 
| ---| ---| ---| ---| 
| Support accuracy (510 questions; PyTorch on the GPU: FT-cf 86.9%, C 96.3%)| 87.1%| **96.5%** / 96.5%| 96.5%| 
| Assistant accuracy (477 questions; PyTorch on the GPU: FT-cf 97.5%, C 100.0%)| 97.9%| **99.8%** / 99.8%| 99.8%| 
| Support by question type: queue / onsite eligibility / urgency (170 questions each)| 71.8% / 90.0% / 99.4%| 92.9% / 98.2% / 98.2%| Same as left| 
| Onsite-eligible positives answered correctly (18)| 2| **17**| 17| 
| Agreement: device vs. each model's own PyTorch rows, support / assistant| 99.0% / 99.6%| 99.0% / 99.8%| 99.0% / 99.8%| 
| Per question against FT-cf: fixed / broken (987 questions)| Reference| 68 fixed, 11 broken| Same as left| 
| Questions with the same answer across the two runs and across the two argument sets (987 total)| —| 987, probabilities identical to every digit| 987, probabilities identical to every digit| 
| Peak working set (MiB)| 1,552| 1,552 / 1,553| **1,421**| 
| Committed memory (MiB)| 4,254| 4,253 / 4,254| **1,360**| 
| Support / assistant median request time (ms)| 1,255 / 1,401| 1,260 / 1,430; 1,236 / 1,401| 1,238 / 1,411| 
| Server-process CPU utilization (16 logical processors)| 50%| 50% / 50%| 50%| 
| Model file (MiB) / load time (s)| 775 / 2.6| 775 / 2.6| 775 / 2.5| 
<!-- /SOURCE:TABLE:23 -->

- **On-device accuracy equals the GPU figure.** Under Q8_0 + llama.cpp, C scores 96.5% on support and 99.8% on assistant, agreeing with its GPU-side PyTorch rows (96.3% / 100.0%) on 99.0% / 99.8% of questions — the same level as FT-cf's 99.0% / 99.6%: quantization and the engine cost C as little as they cost FT-cf. Against FT-cf question by question, C fixes 68 of 987 answers and breaks 11; the fixes concentrate on the queue (71.8% → 92.9%) and the onsite-eligible positives (2 of 18 correct → 17), the same picture as on the GPU; urgency loses 2 (169 → 167).
- **Performance is unchanged.** Same size, same quantization, same arguments: peak working set 1,552 MiB, commit charge 4,253 MiB, support median about 1.24–1.26 s — within the run-to-run spread of FT-cf on this machine. The second round's extra accuracy cost no latency or memory, because it changed the values of the weights, not the model's structure.
- **The lean arguments change no answer.** With `-c 2048 -ub 512`, answers and probabilities of all 987 questions are identical to the default run to every digit; commit charge drops 4,253 → 1,360 MiB (2,893 MiB less — the same effect as 5,014 → 2,119 for FT on the laptop: the KV cache is pre-allocated by `-c`), peak working set 1,552 → 1,421 MiB, latency unchanged. Deploy C with `-c 2048` as well.
- **Raw records**: [验证结果/端侧引擎_x64第二轮C_20261101-171344](../验证结果/端侧引擎_x64第二轮C_20261101-171344) (`machine.json`; per-request results, server log and per-question comparison for the three runs `r2c-kev-0.8b-Q8_0-cpu`, `-run2`, `-c2048-ub512`; `summary/`).
- **Three runs reproduce to the digit**: two with default arguments and one lean, all 987 answers and probabilities identical; only latency moves (support median 1,236–1,260 ms).

**The same C file back on the Snapdragon laptop: same machine, package and arguments as FT-cf, run again.** On 2026-11-01, on the Surface Laptop 7 of the table above (Snapdragon X Elite X1E80100, 12 cores, llama.cpp b11935 ARM64 CPU package), `Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf` (same SHA-256 as the x86-64 copy) was run the same three times ([script](../scripts/laptop_round2c_eval.ps1)):

<!-- SOURCE:TABLE:24 -->
| Metric (Snapdragon X Elite laptop, llama.cpp b11935 ARM64, CPU)| FT-cf Q8_0, default arguments (the 2026-10-27 run)| Round-2 C Q8_0, default arguments: run 1 / run 2| Round-2 C Q8_0, `-c 2048 -ub 512`| 
| ---| ---| ---| ---| 
| Support accuracy (510 questions; PyTorch on the GPU: FT-cf 86.9%, C 96.3%)| 86.9%| **96.9%** / 96.9%| 96.9%| 
| Assistant accuracy (477 questions; PyTorch on the GPU: FT-cf 97.5%, C 100.0%)| 97.7%| **99.6%** / 99.6%| 99.6%| 
| Agreement: device vs. each model's own PyTorch rows, support / assistant| 99.2% / 99.8%| 98.6% / 99.6%| 98.6% / 99.6%| 
| Per question against FT-cf: fixed / broken (987 questions)| Reference| 68 fixed, 8 broken| Same as left| 
| Questions with the same answer as the same file on x86-64 (987 total)| —| 982 (99.5%)| 982| 
| Questions with the same answer across the two runs and across the two argument sets (987 total)| —| 987, probabilities identical to every digit| 987, probabilities identical to every digit| 
| Peak working set (MiB)| 2,314| 2,314 / 2,313| **2,196**| 
| Committed memory (MiB)| 5,014| 5,014 / 5,014| **2,119**| 
| Support / assistant median request time (ms)| 646 / 984| 635 / 905; 626 / 907| 851 / 1,023| 
| Model file (MiB) / load time (s)| 775 / 2.6| 775 / 2.6| 775 / 4.7| 
<!-- /SOURCE:TABLE:24 -->

- **The laptop reaches the same conclusion as x86-64.** On Snapdragon, C scores 96.9% on support and 99.6% on assistant, 10.0 / 1.9 points above FT-cf, fixing 68 answers and breaking 8 against FT-cf question by question; the two CPUs running one file give the same answer on 982 of 987 questions, and the 5 that differ are all boundary questions whose top probability sits at 0.48–0.58 (median per-question probability difference 0.00001), so 96.9% versus 96.5% is a flip around p = 0.5, not one CPU being more accurate.
- **Memory is identical to FT-cf**: peak working set 2,314 MiB and commit charge 5,014 MiB, both figures equal to FT-cf's on 2026-10-27; with `-c 2048 -ub 512`, 2,196 / 2,119 MiB, matching FT's lean run on this laptop, with no answer changed. **The second round cost no memory — and that now holds on the customer's device class too.**
- **Latency is reported, not concluded.** Default-argument support median 635 / 626 ms (FT-cf then: 646); lean 851 ms — faster than FT's lean 1,163 ms in section 5, but the laptop carried background load at the time and single-run differences fall inside the 20% noise band stated in section 5, so C cannot be called faster or slower.
- **Three runs reproduce to the digit**, as on x86-64. The second default-argument run was interrupted externally after 135 records (the evaluation process disappeared; cause not established); its partial output is kept under `interrupted/` and not counted; the same script and file were then rerun in full, which is the "run 2" in the table.
- **Raw records**: [验证结果/端侧引擎_骁龙第二轮C_20261101-203702](../验证结果/端侧引擎_骁龙第二轮C_20261101-203702) (`machine.json`, per-request results, server logs and per-question comparisons for the three runs, `summary/`, interruption and recovery records).
- **C's 4-bit version (Q4_K_M, x86-64): smaller file, no memory saved, 1.2 points paid — the same conclusion as the first round.** Same VM, same arguments, `Contoso-Kev-0.8B-FTcf-R2C-Q4_K_M.gguf` (528 MiB, SHA-256 `26c04cab…2419e865`): support 95.3%, assistant 99.4% (Q8_0 96.5% / 99.8%); agreement with GPU PyTorch 97.1% / 99.4% (Q8_0 99.0% / 99.8%); against Q8_0 question by question, 969 of 987 answers are the same, 13 broken and 5 fixed, the losses concentrated on the queue question (92.9% → 89.4%). Peak working set 1,583 MiB and commit charge 4,532 MiB, slightly above Q8_0's 1,552 / 4,253 — the file is 247 MiB smaller, the process is not; median latency 925 / 1,076 ms (Q8_0 1,260 / 1,430) is a single run, reported only. C is therefore still delivered as Q8_0; 4-bit's standing matches the FT 4-bit row of the [quantization comparison](#from-the-released-model-to-the-quantized-fine-tuned-model-accuracy-speed-and-resources-in-one-table). Raw records in `r2c-kev-0.8b-Q4_K_M-cpu/` of the same folder.
- **Concurrency on Snapdragon was measured too** ([end of the next subsection](#concurrency-laptop)): throughput 0.85–1.15 requests per second across the five tiers does not grow with concurrency, `-np 8` does not help, and 981–985 of 987 answers match concurrency 1 — the same conclusions, item by item, as FT-cf on x86-64. **Still not measured**: C's Q4_K_M on Snapdragon.
- **Raw records**: [验证结果/端侧引擎_x64_20261030-234858](../验证结果/端侧引擎_x64_20261030-234858) — `machine.json` describes the machine and runtime, `ftcf-kev-0.8b-Q8_0-cpu-run1` and `-run2` hold each run's per-request results, server log, memory and per-question comparison, and `summary/` holds the summary tables. The 3 single requests of section 7 were also re-sent on this machine, with identical answers.

#### Concurrency: What Happens When Several Requests Arrive at Once

Every latency above was measured one request at a time. To answer "what if several people submit at once", the same x86-64 VM (AMD EPYC 7763, 8 vCPU / 16 threads; llama-server defaults to 8 compute threads) served the client with 1 / 2 / 4 / 8 requests kept in flight, each level completing the same 170 support + 159 assistant requests; the server kept its default 4 slots, and a final level repeated 8 in flight against 8 slots (`-np 8`). Per-request latency is still measured at the client from send to full answer, so it includes time queued at the server; throughput = completed requests ÷ wall time from the first send to the last answer. Model, runtime and server arguments are those of the previous subsection.

<!-- SOURCE:TABLE:25 -->
| Client requests in flight| Server slots (`-np`)| Support request time, median / p90 (ms)| Assistant request time, median / p90 (ms)| Throughput (completed requests per second, both test sets)| Server process CPU utilisation (16 threads busy = 100%)| Peak working set / commitment (MiB)| Support / assistant accuracy| Same answer as 1 in flight, per question (987 questions)| 
| ---| ---| ---| ---| ---| ---| ---| ---| ---| 
| 1| 4 (default)| 1,183 / 1,257| 1,329 / 1,394| 0.79| 50%| 1,399 / 4,253| 87.1% / 97.9%| Reference (answers and probabilities of all 987 questions identical to the sequential run in the previous subsection)| 
| 2| 4 (default)| 2,344 / 2,930| 2,654 / 3,227| 0.77| 50%| 1,552 / 4,253| 86.9% / 97.9%| 984 (99.7%)| 
| 4| 4 (default)| 2,811 / 6,966| 2,984 / 7,878| 0.82| 50%| 1,552 / 4,254| 87.1% / 97.9%| 981 (99.4%)| 
| 8| 4 (default)| 9,086 / 11,747| 10,492 / 13,132| 0.81| 50%| 1,401 / 4,254| 87.1% / 97.7%| 984 (99.7%)| 
| 8| 8| 6,704 / 18,084| 7,748 / 20,643| 0.82| 50%| 1,743 / 4,417| 87.5% / 97.9%| 981 (99.4%)| 
<!-- /SOURCE:TABLE:25 -->

- **Concurrency adds queueing, not throughput.** From 1 to 8 in flight, completed requests per second stay at 0.77–0.82; the per-request median rises from 1.2 s to 9.1 s (support), roughly "requests in flight × single-request time". One request's forward pass already saturates the engine's 8 compute threads (CPU utilisation is 50% at every level, i.e. 8 of the 16 logical processors), so several requests only take turns on the same CPU. This machine's ceiling is about 0.8 decisions per second, about 48 per minute.
- **More server slots do not help.** `-np 8` with 8 in flight gives the same throughput as `-np 4` (0.82 vs. 0.81 per second), a lower median but a higher p90 (18.1 s vs. 11.7 s): 8 requests admitted together contend for the same CPU, some finish early and some last, which is less even than queueing first and processing four at a time. Slots cap parallel admission; they are not compute.
- **Answers essentially unchanged, probabilities shift.** Under concurrency the server batches several requests together, which changes floating-point accumulation order, so most of the 987 probabilities differ from the sequential run in later decimals (maximum difference 0.10) and 3–6 answers flip; every flip is a question whose top two options sit near 0.50 (selected-answer probability 0.34–0.55), some flip right and some wrong, and accuracy moves within ±0.4 points. Sequential runs, by contrast, are identical to every digit.
- **Memory barely moves.** Peak working set 1,399–1,743 MiB, commitment 4,253–4,417 MiB; slots are reserved at start-up by `-c 8192`, so concurrency adds nothing.
- **Deployment implication:** plan an on-device decision service at about one request per second per machine, with extra requests queued rather than parallel; to serve more people from one machine, more cores or smaller inputs help, `-np` does not. These are 8-vCPU VM figures; the same five tiers were re-run on the Snapdragon laptop with the delivered C (below): absolute numbers on 12 cores are faster, the mechanism is the same.
- **Raw records**: [验证结果/端侧引擎_x64并发_20261031-013937](../验证结果/端侧引擎_x64并发_20261031-013937), one folder per level (`-c1` to `-c8np8`); `summary/concurrency.json` is the source of this table. How to run it: `-Concurrency` and `-Parallel` in step C1.

<a id="concurrency-laptop"></a>

**The same five tiers on the Snapdragon laptop, with the delivered round-2 C.** Same Snapdragon X Elite laptop (12 cores / 12 threads, llama-server's default 12 compute threads), same `Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf`, exactly the same five tiers as the table above, the same 170 support + 159 assistant requests and the same measurement ([script](../scripts/laptop_round2c_concurrency.ps1)). The laptop carried no other foreground load during the test; the gap between the round-14 sequential latency (support 635 / 626 ms) and this table's concurrency-1 value of 624 ms is the normal run-to-run spread of one laptop.

<!-- SOURCE:TABLE:26 -->
| Client requests in flight| Server slots (`-np`)| Support request time, median / p90 (ms)| Assistant request time, median / p90 (ms)| Throughput (completed requests per second, both test sets)| Server process CPU utilisation (12 threads busy = 100%)| Peak working set / commitment (MiB)| Support / assistant accuracy| Same answer as 1 in flight, per question (987 questions)| 
| ---| ---| ---| ---| ---| ---| ---| ---| ---| 
| 1| 4 (default)| 624 / 755| 997 / 1,516| 1.15| 59%| 2,314 / 5,014| 96.9% / 99.6%| Baseline (every one of the 987 answers equals the round-14 sequential run)| 
| 2| 4 (default)| 1,820 / 2,737| 2,082 / 3,292| 0.92| 55%| 2,314 / 5,014| 96.5% / 100.0%| 981 (99.4%)| 
| 4| 4 (default)| 2,893 / 7,491| 3,486 / 7,746| 0.90| 59%| 2,314 / 5,014| 96.9% / 99.8%| 984 (99.7%)| 
| 8| 4 (default)| 7,959 / 11,893| 9,487 / 16,800| 0.85| 54%| 2,316 / 5,014| 96.9% / 100.0%| 985 (99.8%)| 
| 8| 8| 5,619 / 16,186| 5,972 / 16,685| 0.97| 60%| 2,497 / 5,169| 96.9% / 99.8%| 984 (99.7%)| 
<!-- /SOURCE:TABLE:26 -->

- **The mechanism is unchanged on 12 cores: throughput does not grow with concurrency.** Concurrency 1 completes 1.15 requests per second (sequential; throughput = 1 ÷ latency), tiers 2–8 sit between 0.85 and 0.97, none above sequential; the support median rises from 0.6 s to 8.0 s (concurrency 8), still "requests in flight × single-request time" queueing. CPU utilization 54–60% (about 7 of 12 threads computing) is higher than the x86-64 50% because the core count differs, not because of concurrency. The laptop is faster than the VM (1.15 versus 0.79 requests per second), but the planning figure "about one request per second per machine" stands.
- **`-np 8` is equally useless on the laptop.** 8 slots with 8 in flight: throughput 0.97 versus 0.85 with 4 slots, a lower median (5.6 versus 8.0 s) but a higher p90 (16.2 versus 11.9 s) and 181 MiB more memory — the same conclusions, item by item, as on x86-64.
- **Answers mostly unchanged, but not "unchanged".** Question by question against concurrency 1, tiers 2–8 give the same answer on 981–985 of 987 questions (99.4–99.8%); the 2–6 flips per tier are all borderline questions whose chosen-answer probability lies between 0.44 and 0.59 (support record 42's queue question `battery_program` ↔ `sales_ops` at probability 0.487 ↔ 0.489, assistant record 3's `run_on_device`), some flipping to correct and some to wrong, accuracy within ±0.4 points; only 74–113 questions keep bit-identical probabilities (concurrency 1 against the round-14 sequential run: all 987 identical). Same cause as on x86-64: the floating-point accumulation order changes inside a batch.
- **Boundaries.** One run per tier; the concurrency-1 script does not record wall-clock throughput, so the table's 1.15 is derived from the sum of latencies; concurrency under Q4_K_M and under `-c 2048` was not measured; other laptops, battery power and thermal throttling were not measured.
- **Raw records**: [验证结果/端侧引擎_骁龙并发第二轮C_20261101-225349](../验证结果/端侧引擎_骁龙并发第二轮C_20261101-225349), one directory per tier (`r2c-kev-0.8b-Q8_0-cpu-c1` to `-c8np8`, each with `run.json`, `server.log`, and `rows.jsonl`, `summary.json`, `parity_vs_pytorch.json` under `support/` and `assistant/`); `summary/concurrency.json` is the source of this table, `machine.json` the machine and scope.

<a id="long-input"></a>

#### Long Inputs: How the Cost Grows, and Whether 0.8B Reads the History

On-device decision questions are normally a few hundred tokens: in this project each support question (message + 7 device fields + one question) is 77–291 tokens, median 158, and across 999 requests the KV cache was purged 0 times (`server.log` of the first x86-64 run). This subsection answers the ceiling question: "if an input approaches the author's validated 8,192 tokens, how long does the laptop take and how much memory does it use". Method: take the first 40 support test records, keep message, device fields and questions unchanged, and add a `device_log` field to the state filled with synthetic device-log lines until each question's input is about 7,700 tokens ([generator](../scripts/make_long_state.py)), then run exactly the same script and parameters as the other device rows on the same x86-64 VM. **This measures cost, not accuracy, and it cannot be used to say how long inputs affect the answers**: the padding is not a real question (there are no labels for an 8k-long case) and it is not neutral either (the model treats "heartbeat ok" log lines as evidence), so the fact that this run's answers differ from the short-input run shows neither that the model got worse nor that it did not. Knowing whether 0.8B is accurate at 8k requires real questions whose length itself carries information (tickets with repair history, conversation history or a diagnostic report, labels computed from the whole text) — which is what the "real questions" subsection below does.

<!-- SOURCE:TABLE:27 -->
| Configuration (0.8B FT-cf Q8_0, x86-64 VM, `-c 8192` × 4 slots)| Input per question (tokens)| Support request time, median / p90 (ms)| Peak working set (MiB)| Committed memory (MiB)| Server-process CPU utilization| 
| ---| ---| ---| ---| ---| ---| 
| Short input (original test set, first 40 records)| about 220 (473 for the three questions)| 1,450 / —| 1,552| 4,254| 50%| 
| Long input (same 40 records + device log)| about 7,700 (23,100 for the three questions)| **40,706 / 46,224**| **5,061**| **5,970**| 49%| 
<!-- /SOURCE:TABLE:27 -->

- **Time grows linearly with input length: 35× longer, 28× slower.** One 8k ticket takes 41 s at about 190 tokens per second with the CPU saturated throughout (50%, i.e. all 8 compute threads). This follows from the decision model's structure: every question re-reads the whole state (the server's `usage.input_tokens` is 23,100 = 3 questions × 7,700), and llama.cpp b11935 does not reuse the state cache for decision models. For reading whole documents on a laptop, the first limit is seconds, not the window.
- **The working set grows, not the commit charge.** Commit charge 4,254 → 5,970 MiB (+40%); peak working set 1,552 → 5,061 MiB (+226%). The KV cache was already reserved by `-c 8192`; short inputs never wrote it into physical memory, long inputs fill it. So the commit charge is the configuration's ceiling and the peak working set is what is really consumed: size a laptop by the former, judge headroom by the latter.
- **Four slots do not hold three 8k questions.** The server runs the three questions as three parallel rows of 7,700 tokens each; four 8,192-token slots share one KV pool, so every request triggers one "purge the previous request's KV and retry" (`purging slot`, 41 times in the log). Nothing failed, but `-c` must be sized as "longest input × parallel questions", not "longest input", and memory follows.
- **Laptop deployment advice: size `-c` to the real inputs.** Typical decision questions are ≤ 1,000 tokens; `-c 2048` is enough and cuts the commit charge from 5.0 GB to 2.1 GB (laptop, FT) and, for round-2 C on x86-64, from 4,253 to 1,360 MiB, with accuracy unchanged to the digit in both places ([lever table](#5-laptop-inference-engine), [C's comparison table](#round2-device)). Open 8192 only when long documents really must be read, and accept tens of seconds per request and the 5 GB class of memory. The other device rows in this document use 8192 to stay comparable with the first measurements, not as a recommendation.
- **Raw records**: [验证结果/端侧引擎_x64长输入_20261101-101318](../验证结果/端侧引擎_x64长输入_20261101-101318) (`run.json`, `server.log`, `support/rows.jsonl`); the short-input row is the same 40 records from the [first x86-64 run](../验证结果/端侧引擎_x64_20261030-234858).

<a id="long-real"></a>

**Real questions: the answer is in the history — did 0.8B read it? No.** The cost table answers "how long"; this subsection answers "how accurate". Method: the project's vendor policy plus three clauses that can only be decided from the history — H1 a battery already replaced once under the battery program is not replaced again (paid quote, `sales_ops`); H2 a remote fan-profile reset that was already tried and failed in an earlier ticket makes overheating a hardware fault (onsite / depot / quote by warranty and region); H3 a failing disk whose diagnostic report says "no backup" is urgency 3 (a report confirming a backup falls back to 2 / 1). Each ticket = the original short record (customer message + 7 device fields, same format as the training data) plus a `case_history` field (prior tickets, chat transcripts, a diagnostic report; 5,350–30,379 characters, median 10,541; 3,034–8,052 tokens per question, median 4,869). The three clauses are appended verbatim to every question's `instructions`. Of 160 records, 80 carry the decisive fact in the history (the answer must change; 54 of them have labels that differ from the short-record policy) and 80 are controls: an equally long history, but the fact is absent or the opposite (battery not yet replaced, reset not tried, backup confirmed), so the short-record answer stands — this stops "long history ⇒ change the answer" from scoring. The history text was written by a large language model from a per-case fact list ([generator](../scripts/gen_long_cases.py); the script lets it write text only, never decide a label; all labels come from `long_labels()`, and the three data files' SHA-256 are in `manifest.json`). Same x86-64 VM, same `-c 8192` four-slot arguments, same `Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf`, one request at a time; two further controls separate "long" from "new clause text": the same 160 records with `case_history` removed but the clause text kept ([longshort](../data/contoso/final/longshort_test_support.jsonl)), and with both the history and the clause text removed, i.e. exactly the training format ([longplain](../data/contoso/final/longplain_test_support.jsonl)); the latter two are labelled by the short-record policy.

<!-- SOURCE:TABLE:28 -->
| Same model, same machine, three runs| Input| Records / questions| All questions correct| Queue / onsite / urgency| Support request time, median / p90 (ms)| Input per question (tokens, median / max)| Peak working set / commitment (MiB)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| Real long inputs (labels from the whole text)| Short record + history + the three clauses| 160 (7 refused by the server) / 459| **44.9%** (206/459)| 26.1% / 77.1% / 31.4%| 26,395 / 37,560| 4,869 / 8,052| 5,060 / 5,970| 
| History removed, clause text kept (labels from the short record)| Short record + the three clauses| 160 / 480| 63.1% (303/480)| 36.9% / 79.4% / 73.1%| 2,578 / 2,792| 256 / 287| 1,722 / 4,427| 
| History and clause text removed = training format (labels from the short record)| Short record| 160 / 480| 84.0% (403/480)| 73.1% / 95.6% / 83.1%| 1,338 / 1,445| 166 / 197| 1,403 / 4,170| 
| Reference: the original short-input test set (section 1)| Short record| 170 / 510| 96.5%| 92.9% / 98.2% / 98.2%| 1,260 / —| 158 / 291| 1,552 / 4,253| 
<!-- /SOURCE:TABLE:28 -->

<!-- SOURCE:TABLE:29 -->
| Clause (the decisive fact appears only in the history)| Decisive records · affected question correct (the answer must change)| Control records · same question correct (the answer must not change)| Decisive records · the other two questions| Control records · the other two questions| 
| ---| ---| ---| ---| ---| 
| H1 battery already replaced → `sales_ops` (queue question)| 40.0% (10/25)| 0.0% (0/26)| 54.0% (27/50)| 57.7% (30/52)| 
| H2 reset already tried → hardware fault (queue question)| 52.0% (13/25)| 0.0% (0/27)| 46.0% (23/50)| 59.3% (32/54)| 
| H3 report says no backup → urgency 3 (urgency question)| 26.9% (7/26)| 83.3% (20/24)| 34.6% (18/52)| 54.2% (26/48)| 
| Total| **39.5% (30/76)**| **26.0% (20/77)**| 44.7% (68/152)| 57.1% (88/154)| 
<!-- /SOURCE:TABLE:29 -->

- **The conclusion first: this 0.8B cannot read 2k–8k tokens of business history. Only 44.9% of the questions are correct, less than half of the 96.5% on short inputs — and it is not "ignoring the history and answering the short record": that reference strategy would score 88.5% on the same questions, while the model's answers equal the short-record answers on only 42.9%.** The long input throws it off wholesale: the queue question answers `sales_ops` on 112 of 153 records (the labels contain 53), the urgency question answers 0 on 66 records (no label is 0). On the controls (history present, fact reversed) the affected H1 / H2 questions are correct on **0 of 53** — as soon as a battery or fan history appears it changes the answer, without checking whether the fact holds; the 83.3% on the H3 controls is only because the correct answer when a backup exists happens to be 1, towards which it is biased anyway. Nor do the 39.5% on decisive records count as reading: against the history-removed run the affected answer changed on 41/76, but the controls changed just as much.
- **The loss has two layers, and the two controls separate them.** Removing the history but appending the three clauses to `instructions` (no history + clauses) drops accuracy from 96.5% to 63.1%: queue 36.9%, urgency 73.1%. Removing the clause text as well, back to the training format (no history + no clauses), gives 84.0%. The gap between this 84.0% and section 1's 96.5% is not the model but the question mix: these 160 records cover only the battery / overheating / disk scenarios, and the short records of the 26 disk tickets deliberately omit the backup status (the short-record policy label is 3, the model has nothing to go on and answers 1–2, all 26 wrong); without those 26 it is 88.1%, and the overheating queue question (`remote_l1`) was already C's weakest class — on the same three scenarios of the original test set C scores 93.2% (109/117). So the "rule text changed" layer is 84.0% → 63.1%: during training each question's `instructions` were fixed, the model treats them as a format marker rather than a rule to read, and appending three clauses knocks the urgency question from 83.1% to 73.1% and the queue question from 73.1% to 36.9% — the same finding as "it does not follow a changed rule text" in section 2's rule-following test. Adding the history on top drops it to 44.9%: the second layer.
- **8k is not a soft limit but a hard wall.** 7 of 160 records were refused outright by llama-server: 2 with `400 request (… tokens) exceeds the available context size (8192 tokens)`, 5 with `500 Context size has been exceeded` (the three parallel questions did not fit the KV cache). Those 7 histories are 7,858–24,681 characters; the shortest, 7,858 characters, was refused too, because the server reserves slot space for "3 questions × the whole state". Beyond the window the answer is not wrong, it is never read; a deployment has to truncate or summarize in front of the model, not expect it to cope.
- **Latency and memory agree with the padded measurement above.** Median 26,395 ms per request (about 4,869 tokens per question), peak working set 5,060 MiB, commit charge 5,970 MiB, 146 KV purges — reading the history costs 20–40 s per request, and the result is still wrong.
- **Deployment implication: do not feed the history to this model directly.** Two routes are open: extract "battery replaced / reset tried / backup present" into fields in front of the model with rules or retrieval and add them to the state (short-record format, where the model reaches 96.5%), or fine-tune again with long-history samples (the training data contains no record with a history, and `max_state 768` cannot hold one). The second route needs the GPU host again and was not done on this page.
- **Boundaries of these numbers.** 160 records, one run, one x86-64 machine; the history text was generated by a model from fact lists, not exported from a customer system; the three clauses extend this project's policy and were not supplied by a customer; lengths 3,034–8,052 tokens, nothing above 8k was measured; the three runs share model and arguments and differ only in the input. They answer "can the delivered 0.8B C read 2k–8k tokens of business history as is" — no; they do not answer "could it after fine-tuning".
- **Raw records**: [验证结果/端侧引擎_x64长输入真题_20261101-224312](../验证结果/端侧引擎_x64长输入真题_20261101-224312) (`r2c-kev-0.8b-Q8_0-cpu-longreal/` long run, `…-longshort/` history-removed control, `…-longplain/` training-format control, each with `run.json`, `server.log`, `support/rows.jsonl`; `summary/long_summary.md` is the per-clause source, `summary/long_numbers.json` every number in this subsection, `machine.json` the machine and scope).

### 6. Hardware Requirements

<!-- SOURCE:TABLE:30 -->
| Stage| GPU required?| Measured hardware and usage (GPU memory is nvidia-smi peak)| Estimated minimum from memory measurements; these cards were not tested| 
| ---| ---| ---| ---| 
| Train 0.8B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 4,555 MiB GPU memory (micro-batch 1), 7,573 MiB (micro-batch 4)| 8 GB GPU memory (micro-batch 1)| 
| Train 4B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 18,547 MiB (micro-batch 1, probe only), 26,215–33,359 MiB (micro-batch 4)| 24 GB GPU memory (micro-batch 1); over 40 GB for micro-batch 4| 
| GGUF export| No; CPU only| GPU host's CPU| —| 
| Laptop inference 0.8B (Q8_0; FT-cf and the delivered C measured identical)| No discrete GPU or NPU; CPU inference| Snapdragon X Elite, 12 cores; process peak working set 2,314 MiB, committed memory 5,014 MiB (default arguments) or 2,119 MiB (`-c 2048 -ub 512`), identical to the digit for both models| Size total RAM for this process plus the OS and other applications| 
| Laptop inference 4B FT-cf (Q8_0 / Q4_K_M)| No discrete GPU or NPU; CPU inference| 12-core Snapdragon X Elite; peak working set 9,609 / 6,842 MiB and commitment 8,884 / 7,495 MiB| Same sizing principle| 
| x86-64 CPU inference 0.8B (Q8_0), comparison: FT-cf and the delivered C| No GPU; CPU inference| AMD EPYC 7763 Azure VM, 8 vCPU; process peak working set 1,400–1,553 MiB, committed memory 4,253–4,254 MiB (default arguments, five runs across the two models); C with `-c 2048 -ub 512`: 1,421 / 1,360 MiB| Same sizing principle| 
<!-- /SOURCE:TABLE:30 -->

- **Why the 24 GB estimate for 4B?** The micro-batch 1 result of 18,547 MiB is only a probe on 64 long vendor records, not a full run. Full 0.8B training used about 8% more whole-device memory than its probe, 4,555 versus 4,213 MiB. Applying that margin suggests about 20 GB for 4B, leaving roughly 4 GB on a 24 GB GPU. This is an estimate, not a tested minimum.
- **The recipe uses bf16**, through `--dtype bf16`; check hardware support. Training time was measured only on H100 NVL in section 4. Smaller, slower GPUs will take longer, but their duration was not measured.
- **PyTorch evaluation through `kev.benchmark` also ran on GPU.** Its memory was not recorded separately. It is not required for routine device inference.
- **The NPU was not tested.** Adreno GPU was slower than CPU, as described in section 5.

<a id="local-result"></a>

### 7. A Real Local Trial: A Response Is Not Necessarily Correct

On 2026-10-28, UTC-07:00, the Snapdragon X Elite X1E80100 laptop with about 64 GB RAM loaded **0.8B FT-cf Q8_0** with llama.cpp b11935 CPU. Single requests went to `127.0.0.1:8080/v1/systemone`. The server used `--offline`; each request answered 3 questions, without extra warm-up or calls to other models.

[Environment and model hashes](../验证结果/本机试用_20261028-201046/environment.public.json) match the historical FT-cf artifact. After 3 trial requests, sampled working set was 2,288.6 MiB and committed memory 4,988.7 MiB. These process samples do not replace the historical batch-memory measurements above. Public records retain measured values; original service logs stay local.

The support message was “我的AuraBook Pro 16有好几个按键突然失灵了，电脑没有摔过，也没有进过水。” It reports failed keys without a drop or liquid spill. The device had Premium Care 3Y and was purchased 731 days earlier. The second request changed only region US to SG. The assistant message was “帮我联系人工客服咨询保修。” Complete unlabeled inputs are in [data/contoso/examples](../data/contoso/examples); the quoted Chinese is the actual input.

<!-- SOURCE:TABLE:31 -->
| Trial request| Policy-required result| Actual model output| This single request (ms)| Raw request and response| 
| ---| ---| ---| ---| ---| 
| Support, region US| Onsite repair; eligible; urgency 1| `sales_ops` (orders/quotes); ineligible; most likely urgency 1. Wrong queue and onsite eligibility| 783.8| [support-us/result.json](../验证结果/本机试用_20261028-201046/support-us/result.json)| 
| Same support case, region SG| Mail-in repair; ineligible; urgency 1| `sales_ops`; ineligible; most likely urgency 1. Wrong queue| 617.2| [support-sg/result.json](../验证结果/本机试用_20261028-201046/support-sg/result.json)| 
| Assistant: contact human support| `support_chat`; subsequent action is not entirely local; no prior confirmation| All three answers match policy| 774.2| [assistant/result.json](../验证结果/本机试用_20261028-201046/assistant/result.json)| 
<!-- /SOURCE:TABLE:31 -->

**Local invocation works, but 0.8B is still unreliable on these warranty rules.** The region change reached the request and changed probabilities, but did not produce the correct queue change. The business scenario is simulated; the model output is real. For the assistant request, “not entirely local” describes the subsequent support-contact action. Decision inference itself stayed local and the client did not actually contact support.

These inputs reuse historical records `support-g1-11-00311` and `assistant-g1-12-00003`; they are not a new independent quality evaluation. The table reports single client timings, not a speed ranking or latency guarantee. Use [the local trial steps](Operations-Guide.md#local-try) to change inputs and inspect errors yourself.

The same 3 requests were re-sent on the x86-64 Azure virtual machine (AMD EPYC 7763, section 5): every answer is identical (`sales_ops`, `sales_ops`, `support_chat`, with the same onsite-eligibility and confirmation decisions) and probabilities differ by at most 0.016; the single-request times of 1,633–1,823 ms are VM figures and are not compared with the laptop. Records: [验证结果/本机试用_x64_20261030-135532](../验证结果/本机试用_x64_20261030-135532).

**The delivered round-2 C gets this ticket right.** The same "failed keys, US, Premium Care 3Y, day 731" ticket (`support-g1-11-00311` in the batch scoring) on the x86-64 VM: FT-cf answers `sales_ops` (42.3%) and not eligible for onsite; C answers `onsite_repair` (87.6%) and eligible (69.5%), urgency still 1, all three in line with the policy ([per-request results of the device regression](../验证结果/端侧引擎_x64第二轮C_20261101-171344/r2c-kev-0.8b-Q8_0-cpu/support/rows.jsonl)). This is the 90 added onsite positives of the second round at work; one correct ticket does not make the model reliable — the overall figures are in [the second round](#round2).

<a id="headroom"></a>

### How Much More Accuracy Is Available: What the Next Fine-Tuning Round Should Change

This section records the prediction first and the measurement second; they differ, and both are kept. The prediction was "more epochs will not help; different data and a larger size will", on this evidence:

<!-- SOURCE:TABLE:32 -->
| Clue| Metric| Reading at the time| 
| ---| ---| ---| 
| Development set versus test set| 0.8B FT-cf support: development set 88.4%, test set 86.9%| Neither over- nor under-fitting; converged after 2 epochs. More epochs on the same data are expected to add at most 1 point| 
| Where the errors are| "Change one field, the answer must follow" questions, 0.8B FT-cf by field: battery cycles 49.2%, days since purchase 41.9%, region 36.2% (below FT); onsite eligibility balanced accuracy about 55% (89% of the test answers are "no" and the model mostly answers "no")| Errors cluster on numeric thresholds (day 365 / 730 / 1095, 500 cycles) and multi-field rules, not random noise| 
| Larger size| Same LoRA recipe: 4B scores 84.9% / 100% on field-following questions, 84.8% on days since purchase and 66.1% on battery cycles| 0.8B is at its capacity limit; the weakness is model size, not the adapter| 
<!-- /SOURCE:TABLE:32 -->

<a id="round2"></a>

#### Second Round, Measured: More Data, More Epochs, Both

The first two predicted paths were each run once, plus their combination; all start from the same released Kev with the FT-cf recipe, and each changes exactly one thing:

- **A: more data, 2 epochs.** Training set 3,832 → 4,038 records ([generator](../scripts/augment_round2.py): 116 region-flip variants and 90 variants turned into onsite-repair positives; messages unchanged, labels recomputed by the policy code; onsite positives 186 → 308).
- **B: same data, 4 epochs.**
- **C: more data and 4 epochs.**

All trained and calibrated on the same H100 NVL and scored on the same test sets as section 1; paired-difference 95% intervals use the cluster bootstrap over messages, 10,000 resamples ([summary script](../scripts/summarize_round2.py)).

<!-- SOURCE:TABLE:33 -->
| Metric (0.8B)| FT-cf (published), 2 epochs| A: more data, 2 epochs| B: same data, 4 epochs| C: more data, 4 epochs| 
| ---| ---| ---| ---| ---| 
| Support · in-distribution accuracy (510 questions)| 86.9%| 88.0% (+1.2, interval −0.6 ~ +2.9)| 92.2% (+5.3, +2.3 ~ +8.2)| **96.3%** (+9.4, +6.3 ~ +12.6)| 
| Support · out-of-distribution accuracy (1,011 questions)| 82.5%| 83.3% (+0.8, −0.8 ~ +2.3)| 84.8% (+2.3, +0.6 ~ +4.0)| **88.4%** (+5.9, +3.8 ~ +8.1)| 
| Assistant · in / out of distribution| 97.5% / 94.4%| 97.5% / 94.7%| 99.8% / 97.5%| **100.0% / 97.3%**| 
| Support · out-of-distribution ECE| 0.064| 0.061| 0.073| **0.055**| 
| "Change one field, the answer must follow", 316 out-of-distribution questions| 48.4%| 52.5%| 66.8%| **76.9%**| 
| — of which the region field| 35.7%| 52.4%| 52.4%| **69.0%** (100% in distribution)| 
| — of which days since purchase| 37.4%| 38.2%| 67.9%| **78.6%**| 
| Onsite-eligible positives answered correctly: 18 in-distribution / 26 out-of-distribution| 2 / 3| 3 / 2| 7 / 1| **17 / 10**| 
| 656 public questions (prior capability; threshold: a 2-point drop)| 64.8%| 65.9% (+1.1)| 63.7% (−1.1)| 65.2% (+0.5)| 
| Training time / peak GPU memory| 11.6 min / 7.6 GB| 14 min 15 s / 13.6 GB| 21 min 58 s / 7.5 GB| 22 min 42 s / 7.5 GB| 
| Calibration temperature T| 1.15| 1.20| 2.41| 2.83| 
<!-- /SOURCE:TABLE:33 -->

The measurement overturned the first half of the prediction and showed why single-factor controls mislead:

- **"Converged after 2 epochs" was wrong.** A 1.5-point gap between development and test set rules out over-fitting, not under-training. Two more epochs on the same data (B) add 5.3 points of support accuracy and take the days-since-purchase field from 37.4% to 67.9%: the threshold rules are learnable; 2 epochs had not learned them.
- **"More data does not help" was wrong too, but A alone says exactly that.** Every interval of A contains 0 and onsite positives go from 2 to 3 correct. The same data at 4 epochs (C) takes the region field from 52.4% to 69.0% (100% in distribution) and onsite positives from 7 to 17: the 90 added onsite positives were simply never learned in 2 epochs. Data and epochs are not alternatives but additive; a "data only" or "epochs only" control each judges the other factor as zero.
- **What won is not "the number of fine-tuning rounds".** It is easy to read this as "fine-tune once more and it gets better": it is not that. A, B and C, like FT-cf, were each trained **once** from the released Kev; none continues from FT-cf. What changed is how many times that one training pass sees the data (epochs 2 → 4) and whether the data contains the 206 targeted samples. The value of each knob on its own is B (+5.3) and A (+1.2) in the table above; turned together they give C (+9.4). Nor should more epochs be expected to keep adding linearly: onsite positives are already 17 of 18, and the remaining errors sit on samples the training data does not contain (the battery-cycles field), which calls for more data, not more epochs; 6 or 8 epochs were not run, and the public-question 65.2% only shows that 4 epochs have not over-fitted yet.
- **C paid no price.** Out-of-distribution ECE fell from 0.064 to 0.055, the public questions rose 0.5 points, and training time equals B's; the calibration temperature rose from 1.15 to 2.83, i.e. the model became more over-confident and the calibration step pulled it back, which is exactly section 3's "re-calibrate after retraining".
- **The "larger size" clue still holds, but the gap shrank.** C's in-distribution support accuracy of 96.3% passes 4B FT-cf's 95.9% (which is a 2-epoch run without a second round); out of distribution, 88.4% is still 3 points behind 4B's 91.4%.
- **Still open**: the battery-cycles field did not move (C out of distribution 47.6%), and onsite positives out of distribution are still 10 of 26 correct. The next round should add battery-cycle variants near 500 and feed the out-of-distribution field mix (Singapore, offline) into training at the test set's proportions.
- **C has been regressed on device and is now the delivered model.** `Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf` (T = 2.83) scores 96.5% on support and 99.8% on assistant on the x86-64 VM, with 99.0% / 99.8% agreement against its GPU-side PyTorch rows, at the same memory and latency as FT-cf ([comparison table in section 5](#round2-device)); on that basis it replaces FT-cf as the file this project recommends and delivers ([first-screen table](../README.md#criteria), [steps A](Operations-Guide.md#local-try)). It was then re-measured on the Snapdragon laptop: support 96.9%, assistant 99.6%, memory identical to FT-cf to the digit (same comparison table). Raw records: [验证结果/第二轮微调评测_20261101-101948](../验证结果/第二轮微调评测_20261101-101948) (`runs/0.8b/r2-{A,B,C}-*`, `summary/round2_summary.md`, and the export logs and SHA-256 under `gguf/0.8b-r2{A,B,C}/`).

The third predicted path, **moving to 4B** (95.9% / 99.8% accuracy, but a 4.3 GB Q8_0 file, 3.6–4.1 s per decision and a 9.6 GB peak working set), remains a product trade-off rather than a training problem, and is less compelling after the second round. The fine-tuning method is not among the candidates: both this project and the Kev author's recipe train only the LoRA (rank 16) and the pointer head, and moving 1.4% of 0.8B's parameters lifted support accuracy from 45.7% to 96.3%, so LoRA is the default and sufficient choice. If real customer data is available, the next round should be run on it rather than on more simulated data.

### Limits of the Conclusions

- **Simulated data**: policies, fields and messages represent a fictional vendor. Model-generated messages follow fact lists and are more regular than real customer text. Absolute production accuracy will differ; this experiment establishes a working method, observed improvement and resource measurements for its scope.
- **One training run per recipe, seed 1**: the 95% intervals describe test-sample uncertainty, not variability across seeds or newly generated datasets.
- **In-distribution temperature calibration** uses `calibrate_checkpoint.py --allow-in-distribution`, which emits a warning for this choice. Out-of-distribution ECE tests the result of that choice.
- **A missing out-of-distribution assistant class**: the message generator refused 13 of 300 cases involving policy-bypassing or other-account actions, even after two retries. That class is absent from the assistant out-of-distribution test.
- **One Snapdragon laptop and one x86-64 virtual machine**: concurrency was measured on both machines, one configuration each (0.8B FT-cf Q8_0 on x86-64, 0.8B round-2 C Q8_0 on Snapdragon), one run per tier. Sustained thermal behavior, battery operation and NPU execution were not tested. Only the 4B FT-cf configurations completed; 4B FT stopped after 36 records and is excluded. On the laptop each configuration has one measured run, and paired latencies for identical architectures can differ by up to 24%. On x86-64 only 0.8B Q8_0 was measured (published FT-cf twice, round-2 C three times), on an Azure VM rather than a customer laptop; 4B, Q4_K_M and Intel processors were not tested. On Snapdragon the delivered round-2 C was run in Q8_0 three times sequentially (two default, one lean) and once per concurrency tier; Q4_K_M was not measured for it, and the laptop figures for every other configuration (FT, 4B, the quantization comparison, the lever table) remain the first-round FT / FT-cf runs.
- **The accuracies on this page hold for short inputs only; on long inputs the delivered model is not usable.** Every accuracy in sections 1–3 was measured on short inputs of 430–540 tokens (77–291 per question). The [real long-input set](#long-real) is the only long-input measurement with labels computed from the whole text: on 160 tickets carrying 2k–8k tokens of business history, round-2 C gets only 44.9% of the questions right, 0 of 53 on the controls, and 7 records above 8,192 tokens are refused by the server; removing the history and merely changing the rule text already drops it to 63.1%. These are 160 records, one run, one x86-64 machine; the history was written by a model from fact lists, and the three history clauses extend this project's policy rather than coming from a customer. The author's 8,192-token validation for 0.8B / 4B was on English contracts (CUAD), not on this project's business questions.
