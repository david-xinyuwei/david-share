# Kev Business Fine-Tuning and On-Device Validation

[English](Finetuning-and-On-Device-Validation-Report.md) | [中文](微调与端侧验证报告_20261027-130700.md)

The data is simulated: business policies and messages for the fictional AI PC vendor Contoso PC, not any real customer. Each recipe was trained once with seed 1. Conclusions describe that run, not stability across repeated training.

[Project home](../README.md) · [Local trial](../README.md#local-try) · [Train and update](../README.md#train-update) · [Verify](../README.md#verify) · [Experimental protocol](Experiment-Protocol.md)

This report retains the historical method, detailed results and analysis. The README owns business requirements, architecture and executable steps. The [single-request local trial](../README.md#local-result) added on 2026-10-28 is reported separately, not merged into these historical measurements.

## Findings

Interim report, 2026-10-27: training, PyTorch evaluation and device tests are complete within the recorded scope. Only recommended FT-cf configurations completed the 4B laptop tests.

- **Fine-tuning improves performance on this simulated data.** The business training set has 2,147 records; counterfactual augmentation raises FT-cf to 3,832. Both mix in 1,000 Kev replay records. Recommended FT-cf raises in-distribution support/assistant accuracy from 44.7%/67.1% to 86.9%/97.5% for 0.8B, and from 60.8%/81.8% to 95.9%/99.8% for 4B. On messages written by a different generator, out-of-distribution scores are 82.5%/94.4% and 91.4%/98.8%, respectively. FT and FT-cf both start from the release, not from each other.
- **Overall accuracy rises, but business thresholds need independent validation.** B0-policy is 10.5-30.2 percentage points below FT. Test-label-derived coverage at a 5% error budget is 84.5%/100% for 0.8B FT-cf and 100%/100% for 4B FT-cf on in-distribution data, versus 2.9%-43.2% for the released models. This is not a deployed fixed-threshold error guarantee. Public-task accuracy changes by -0.8 to +0.9 points, not crossing the predefined greater-than-2-point forgetting threshold, but Brier worsens.
- **Resources: one H100 NVL takes approximately 12-27 minutes and USD 1.8-4.1 at list price per training run.** With micro-batch 1, probes on the longest vendor records peak at 4,213 MiB for 0.8B and 18,547 MiB for 4B in `nvidia-smi`. Q8_0 files occupy 775 and 4,276 MiB; laptop peak working sets are 2,314 MiB for 0.8B and 9,609 MiB for 4B FT-cf.
- **llama.cpp directly runs the fine-tuned model.** 0.8B FT and FT-cf Q8_0 on Snapdragon X Elite CPU agree with PyTorch on at least 99.2% of questions, with 0.65-0.98 second median decisions. For 4B FT-cf Q8_0, support/assistant agreement is 99.4%/100%, with 3.6-4.1 second medians. Adreno is slower with greater disagreement. Q4_K_M saves memory, but was not shown to be faster and introduces more disagreement.
- **Unresolved weaknesses remain.** Onsite eligibility combines issue type, warranty, purchase age and region. Balanced accuracy is about 55% for 0.8B; 4B reaches 66.7% out of distribution, below B0-policy's 88.1%. For changed-answer questions involving purchase age, region and battery cycles, 0.8B scores only 36%-49%. All conclusions come from simulated data and one seed-1 training run per recipe.

## 1. Evaluation Goal

The business goal is a laptop-local decision model with accurate judgments, short response times, modest resource use and a customer-controlled update path. A hosted cloud service cannot simply be deployed on the device, and a generic model is not already adapted to vendor policies. This project tests Kev as a candidate; it does not compare proprietary cloud models.

Support triage and assistant routing each have 3 questions per record. The report examines business fine-tuning, policy following, calibration, general-task retention, training resources, device operation and engine agreement. Continuous business updates and automatic publication were not tested; two independently trained recipes do not establish them.

## 2. Method

<!-- SOURCE:TABLE:1 -->
| Stage| Method| Key settings| Code| 
| ---| ---| ---| ---| 
| Simulated private business data| Policy code computes labels; generators write messages from required facts without internal codes, warranty or queue names. About 35% receive a paired one-field change with a different label| Training/in-distribution: model A, 1,400 original messages per scenario. Out-of-distribution: another provider's model B, 300 per scenario, with region, network and phrasing shifts| [scripts/vendor_policy.py](../scripts/vendor_policy.py), [scripts/gen_vendor_data.py](../scripts/gen_vendor_data.py)| 
| Split| Hash splits by original-message group; paired records stay with the original| Training 70% / calibration 10% / development 10% / test 10%; out-of-distribution data is test-only| Same sizing principle| 
| Fine-tuning| Supervised fine-tuning with correct-answer cross-entropy, not reinforcement learning. The [training configuration](../验证结果/微调评测_20261027-220226/runs/0.8b/ft/training_config.json) sets `perm_kl`, `ord_w`, `label_smoothing`, `brier_w`, `focal_gamma` and `anchor_w` to 0. Follow Kev's native `--init_from` to load released LoRA/pointer-head weights, mix in 1,000 replay records, then fit temperature on calibration data| LoRA r16, 2 epochs, lr 2e-5, effective batch 8, bf16, seed 1| [scripts/remote_pipeline.sh](../scripts/remote_pipeline.sh), [scripts/remote_pipeline_v2.sh](../scripts/remote_pipeline_v2.sh)| 
| Second recipe: FT-cf| Initial results underuse device fields (section 3.3); add up to 3 one-policy-field counterfactuals per training message, recompute labels and train a separate recipe| Training set 2,147 → 3,832 records; micro-batch 4 × accumulation 2; other settings as FT| [scripts/augment_counterfactual.py](../scripts/augment_counterfactual.py), [scripts/remote_cf_round.sh](../scripts/remote_cf_round.sh)| 
| Quality evaluation| B0, B0-policy, FT and FT-cf use the same test set and `kev.benchmark`; paired bootstrap gives 95% difference intervals| Improvement requires interval lower bound > 0; a drop over 2 points on public transfer-v4 development triggers forgetting| [scripts/summarize_results.py](../scripts/summarize_results.py)| 
| Inference runtime| The llama.cpp b11935 converter exports fine-tuned checkpoints to GGUF, merging LoRA and temperature metadata with ggml-org's Kev-4B quantization settings; laptop `llama-server` evaluates each record through `/v1/systemone` and compares with PyTorch| Q8_0 and Q4_K_M; CPU and Adreno GPU (OpenCL)| [scripts/remote_export_gguf.sh](../scripts/remote_export_gguf.sh), [scripts/run_engine_eval.ps1](../scripts/run_engine_eval.ps1), [scripts/parity.py](../scripts/parity.py)| 
<!-- /SOURCE:TABLE:1 -->

The [experimental protocol](Experiment-Protocol.md) was fixed before results, with execution deviations recorded separately.

### Data Size and Quality Checks

<!-- SOURCE:TABLE:2 -->
| File| Records| Questions| Purpose| 
| ---| ---| ---| ---| 
| train| 2,147| 6,441| Training, plus 1,000 Kev replay records| 
| calib| 328| 984| Fit temperature| 
| dev_support / dev_assistant| 181 / 163| 543 / 489| Development set; not used for initial hyperparameter selection| 
| test_support / test_assistant| 170 / 159| 510 / 477| In-distribution evaluation| 
| ood_support / ood_assistant| 337 / 317| 1,011 / 951| Out-of-distribution evaluation| 
| policy_test_* / policy_ood_*| Same sizing principle| Same sizing principle| B0-policy: identical records with full vendor policy added to each question| 
<!-- /SOURCE:TABLE:2 -->

- **Public data projection**: generator model names are replaced by `llm-A` and `llm-B`. Other record content is unchanged, so public manifest hashes differ from experiment-time hashes.
- **Label verification**: recomputing labels from each record's own device fields produces no differences across 8 files and 3,802 records. See the [verification output](../验证结果/数据标签复核_20261027-130518.txt).
- **Majority-label baseline**: always choosing the most common label scores 54.5% on support and 58.3% on assistant. Onsite eligibility is 89% no. Accordingly, per-question balanced accuracy, the mean recall across labels, accompanies ordinary accuracy.
- **Repeated messages**: 19 assistant test records have exactly the same message as a training record, with different device state. Results also exclude these 19 records. No such overlap was found in the support test or either out-of-distribution set.
- **Out-of-distribution gap**: the generator refused to produce messages for 13 of 300 assistant cases involving security bypass or another user's account. Two retry rounds still failed, leaving that refusal class absent.

### A Real Test Record

This is the first record in `test_support.jsonl`, with option descriptions abbreviated. `state` is everything visible to the model: the actual customer message and device fields. Policy code supplies the three `label` values; the model does not see them. The original Chinese input is preserved verbatim.

<!-- SOURCE:FENCE:1 -->
```json
{
 "state": {
  "channel": "email",
  "message": "您好：\n请问我的 Contoso Nimbus 2-in-1 订单目前是什么状态？麻烦告知最新进度。\n谢谢\n李明",
  "device": {"product_line": "Nimbus 2-in-1", "region": "SG", "warranty_plan": "Accidental Damage 2Y",
             "days_since_purchase": 749, "battery_cycles": 202, "last_error_code": "none", "bios_version": "1.11"}
 },
 "questions": {
  "queue": {"type": "choice", "instructions": "Which Contoso support queue should take this case?",
            "criteria": {"remote_l1": "Remote software support ...", "depot_repair": "Mail-in repair ...", "...": "（共 8 个队列）"},
            "label": "sales_ops"},
  "onsite_eligible": {"type": "noul", "instructions": "Is the customer entitled to an onsite technician visit for this case?",
                      "label": false},
  "urgency": {"type": "score", "instructions": "How urgently must Contoso respond?",
              "criteria": ["Can wait", "Within this week", "Today", "Immediately: safety or data-loss risk"], "label": 0}
 }
}
```
<!-- /SOURCE:FENCE:1 -->

Many answers depend on fields absent from the message. The same loose-hinge complaint should receive onsite service with Premium Care 3Y, valid warranty and region CN/JP/DE/US, but mail-in or a paid quote after changing region to Singapore or passing warranty expiry. B0-policy embeds such policy text in every question, growing the support question section from about 950 to 4,600 characters per record. B0 retains short instructions.

## 3. Fine-Tuning Quality on PyTorch and H100

B0, B0-policy, FT and FT-cf use the same `kev.benchmark` evaluator and records. Accuracy is per question: 170 support records with 3 questions each produce 510 evaluated questions.

<a id="accuracy"></a>

### 3.1 Accuracy Before and After Fine-Tuning

<!-- TABLE:ACC -->
<!-- SOURCE:TABLE:3 -->
| Size| Test set| Questions| B0| B0-policy| FT| FT-cf| FT−B0 (percentage points, 95% interval)| FT−B0-policy| FT-cf−FT| 
| ---| ---| ---| ---| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution | 510| 44.7%| 60.8%| 86.5%| 86.9%| +41.8 (+36.3 ~ +47.1)| +25.7 (+22.5 ~ +28.9)| +0.4 (-2.0 ~ +2.8)| 
| 0.8B| Assistant: in-distribution | 477| 67.1%| 71.9%| 93.5%| 97.5%| +26.4 (+22.8 ~ +30.1)| +21.6 (+17.9 ~ +25.3)| +4.0 (+2.3 ~ +5.8)| 
| 0.8B| Support: out-of-distribution | 1,011| 43.0%| 62.8%| 81.6%| 82.5%| +38.6 (+35.0 ~ +42.1)| +18.8 (+16.2 ~ +21.4)| +0.9 (-0.9 ~ +2.6)| 
| 0.8B| Assistant: out-of-distribution | 951| 65.7%| 63.6%| 91.9%| 94.4%| +26.2 (+23.4 ~ +29.0)| +28.3 (+25.5 ~ +31.2)| +2.5 (+1.1 ~ +3.9)| 
| 4B| Support: in-distribution | 510| 60.8%| 63.3%| 93.5%| 95.9%| +32.7 (+28.7 ~ +36.8)| +30.2 (+25.9 ~ +34.4)| +2.4 (+0.6 ~ +4.1)| 
| 4B| Assistant: in-distribution | 477| 81.8%| 87.8%| 99.0%| 99.8%| +17.2 (+13.8 ~ +20.7)| +11.1 (+8.2 ~ +14.2)| +0.8 (+0.0 ~ +1.9)| 
| 4B| Support: out-of-distribution | 1,011| 60.7%| 63.2%| 88.8%| 91.4%| +28.1 (+25.0 ~ +31.2)| +25.6 (+22.4 ~ +28.7)| +2.6 (+1.0 ~ +4.2)| 
| 4B| Assistant: out-of-distribution | 951| 81.9%| 86.1%| 96.6%| 98.8%| +14.7 (+12.2 ~ +17.3)| +10.5 (+8.4 ~ +12.7)| +2.2 (+1.1 ~ +3.4)| 
<!-- /SOURCE:TABLE:3 -->

Paired differences are per question. The 95% intervals resample all records sharing the same original message together, 10,000 times. The protocol's `kev.compare` first computes accuracy by question type and then macro-averages; it supports the same direction:

<!-- SOURCE:TABLE:4 -->
| Size| Test set| FT−B0 (kev.compare)| FT-cf−B0 (kev.compare)| FT-cf−FT (kev.compare)| 
| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution | +41.8 (+36.7 ~ +47.5)| +42.2 (+36.7 ~ +47.8)| +0.4 (-2.0 ~ +2.7)| 
| 0.8B| Assistant: in-distribution | +22.6 (+19.0 ~ +26.4)| +25.5 (+22.0 ~ +28.8)| +2.8 (+1.3 ~ +4.7)| 
| 0.8B| Support: out-of-distribution | +38.6 (+35.2 ~ +42.5)| +39.5 (+36.3 ~ +43.1)| +0.9 (-0.9 ~ +2.5)| 
| 0.8B| Assistant: out-of-distribution | +22.9 (+20.3 ~ +25.6)| +24.7 (+22.1 ~ +27.4)| +1.8 (+0.6 ~ +2.9)| 
| 4B| Support: in-distribution | +32.7 (+28.4 ~ +36.9)| +35.1 (+31.0 ~ +39.2)| +2.4 (+0.2 ~ +4.3)| 
| 4B| Assistant: in-distribution | +14.5 (+11.5 ~ +17.5)| +15.1 (+11.9 ~ +18.1)| +0.6 (+0.0 ~ +1.4)| 
| 4B| Support: out-of-distribution | +28.1 (+25.0 ~ +31.4)| +30.7 (+27.5 ~ +33.7)| +2.6 (+1.0 ~ +4.3)| 
| 4B| Assistant: out-of-distribution | +13.4 (+11.1 ~ +15.7)| +15.3 (+12.7 ~ +17.8)| +1.9 (+0.8 ~ +3.1)| 
<!-- /SOURCE:TABLE:4 -->
<!-- /TABLE:ACC -->

- **Both model sizes improve.** In-distribution FT changes support/assistant scores from 44.7%/67.1% to 86.5%/93.5% for 0.8B and from 60.8%/81.8% to 93.5%/99.0% for 4B. Every FT-minus-B0 95% interval has a lower bound clearly above 0, including the protocol's macro-average definition. FT-cf adds another 0.4-4.0 points; the two 0.8B support intervals include 0. Both sizes satisfy the predeclared FT-cf selection rule in section 3.3.
- **Fine-tuning exceeds policy-only prompting.** B0-policy reaches 60.8%/71.9% for 0.8B and 63.3%/87.8% for 4B in distribution. FT adds roughly 11-30 points: +11.1 on 4B assistant, +25.7 on 0.8B support and +30.2 on 4B support. Prompting is not uniformly helpful: 0.8B out-of-distribution assistant falls to 63.6%, below B0's 65.7%. Policy text adds about 3,700 support or 1,800 assistant characters per record and increases device latency.
- **Gains persist after generator and distribution changes.** Model B, from another provider, writes the out-of-distribution messages, with more Singapore, offline and metered-network cases and two requests in one message. FT scores 81.6%/91.9% for 0.8B and 88.8%/96.6% for 4B, 1.6-4.9 points below in-distribution scores. FT-cf scores 82.5%/94.4% and 91.4%/98.8%, a 1.0-4.5-point drop. These are distribution-shift losses; the tables retain comparisons against B0.
- **Exact-message overlap does not account for the overall gain.** After removing the 19 overlapping assistant records, 0.8B FT still exceeds B0 by 27.6 points, with a 95% interval of +23.8 to +31.4.

### 3.2 Which Questions Improve

<!-- TABLE:PERQ -->
<!-- SOURCE:TABLE:5 -->
| Size| Test set| Question| Majority-label share| Accuracy: B0 / B0-policy / FT / FT-cf| Balanced accuracy: B0 / B0-policy / FT / FT-cf| 
| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution | Queue (8 choices)| 30.0%| 43.5% / 49.4% / 68.8% / 70.6%| 54.6% / 55.5% / 72.7% / 74.6%| 
| 0.8B| Support: in-distribution | Onsite eligibility (yes/no)| 89.4%| 48.2% / 89.4% / 90.6% / 90.0%| 63.7% / 50.0% / 55.6% / 55.2%| 
| 0.8B| Support: in-distribution | Urgency (4 levels)| 44.1%| 42.4% / 43.5% / 100.0% / 100.0%| 56.3% / 57.0% / 100.0% / 100.0%| 
| 0.8B| Assistant: in-distribution | Tool (14 choices)| 22.0%| 88.7% / 95.0% / 100.0% / 99.4%| 89.6% / 95.1% / 100.0% / 99.3%| 
| 0.8B| Assistant: in-distribution | Entirely local action (yes/no)| 74.2%| 33.3% / 26.4% / 88.1% / 97.5%| 54.3% / 48.8% / 84.8% / 96.7%| 
| 0.8B| Assistant: in-distribution | Confirmation before execution (yes/no)| 78.6%| 79.2% / 94.3% / 92.5% / 95.6%| 51.5% / 86.8% / 87.7% / 91.8%| 
| 0.8B| Support: out-of-distribution | Queue (8 choices)| 33.2%| 42.1% / 57.6% / 68.0% / 67.7%| 49.6% / 58.0% / 61.1% / 60.2%| 
| 0.8B| Support: out-of-distribution | Onsite eligibility (yes/no)| 92.3%| 52.8% / 91.4% / 92.3% / 92.3%| 58.6% / 49.5% / 51.8% / 55.3%| 
| 0.8B| Support: out-of-distribution | Urgency (4 levels)| 50.4%| 34.1% / 39.5% / 84.6% / 87.5%| 52.1% / 59.2% / 85.7% / 90.3%| 
| 0.8B| Assistant: out-of-distribution | Tool (14 choices)| 20.8%| 85.8% / 87.4% / 98.7% / 98.4%| 87.0% / 84.4% / 95.8% / 92.2%| 
| 0.8B| Assistant: out-of-distribution | Entirely local action (yes/no)| 76.3%| 32.2% / 22.4% / 89.9% / 95.0%| 53.3% / 44.6% / 82.8% / 92.1%| 
| 0.8B| Assistant: out-of-distribution | Confirmation before execution (yes/no)| 79.8%| 79.2% / 81.1% / 87.1% / 89.9%| 50.8% / 68.9% / 75.6% / 83.8%| 
| 4B| Support: in-distribution | Queue (8 choices)| 30.0%| 54.7% / 64.1% / 86.5% / 92.4%| 70.7% / 71.5% / 84.7% / 89.7%| 
| 4B| Support: in-distribution | Onsite eligibility (yes/no)| 89.4%| 68.8% / 72.9% / 94.1% / 95.3%| 70.3% / 84.9% / 79.6% / 85.1%| 
| 4B| Support: in-distribution | Urgency (4 levels)| 44.1%| 58.8% / 52.9% / 100.0% / 100.0%| 54.6% / 66.9% / 100.0% / 100.0%| 
| 4B| Assistant: in-distribution | Tool (14 choices)| 22.0%| 93.7% / 95.6% / 100.0% / 100.0%| 96.8% / 97.6% / 100.0% / 100.0%| 
| 4B| Assistant: in-distribution | Entirely local action (yes/no)| 74.2%| 73.6% / 77.4% / 98.7% / 100.0%| 62.3% / 82.4% / 98.4% / 100.0%| 
| 4B| Assistant: in-distribution | Confirmation before execution (yes/no)| 78.6%| 78.0% / 90.6% / 98.1% / 99.4%| 56.0% / 89.7% / 96.7% / 98.5%| 
| 4B| Support: out-of-distribution | Queue (8 choices)| 33.2%| 59.1% / 62.9% / 81.6% / 85.8%| 72.1% / 68.9% / 79.6% / 86.9%| 
| 4B| Support: out-of-distribution | Onsite eligibility (yes/no)| 92.3%| 68.5% / 78.0% / 93.2% / 93.8%| 63.6% / 88.1% / 64.6% / 66.7%| 
| 4B| Support: out-of-distribution | Urgency (4 levels)| 50.4%| 54.6% / 48.7% / 91.7% / 94.7%| 53.9% / 57.6% / 90.3% / 95.0%| 
| 4B| Assistant: out-of-distribution | Tool (14 choices)| 20.8%| 88.0% / 92.1% / 97.5% / 98.4%| 94.9% / 93.2% / 98.9% / 98.7%| 
| 4B| Assistant: out-of-distribution | Entirely local action (yes/no)| 76.3%| 78.2% / 77.3% / 99.1% / 99.4%| 64.6% / 80.1% / 98.5% / 99.1%| 
| 4B| Assistant: out-of-distribution | Confirmation before execution (yes/no)| 79.8%| 79.5% / 89.0% / 93.4% / 98.7%| 53.3% / 84.9% / 85.9% / 98.0%| 
<!-- /SOURCE:TABLE:5 -->
<!-- /TABLE:PERQ -->

Balanced accuracy averages recall separately for each label. If 89% of answers are no, predicting no throughout produces 89% ordinary accuracy but only 50% balanced accuracy.

- **Vendor-specific definitions gain the most.** Released Kev does not know Contoso's four urgency levels or fourteen tool responsibilities. For 0.8B FT, urgency rises from 42.4% to 100%, and tool selection from 88.7% to 100%.
- **State-dependent yes/no tasks also improve.** Whether an action stays local depends on network and enterprise-management fields. 0.8B rises from 33.3% to 88.1%, with balanced accuracy 54.3% to 84.8%. FT-cf reaches 97.5%, with 96.7% balanced accuracy.
- **Onsite eligibility requires the balanced metric.** With 89% no labels, 0.8B B0-policy's 89.4% accuracy and 50.0% balanced accuracy amount to predicting no throughout. FT scores 90.6% and 55.6%, still missing most eligible minority cases. 4B FT is better at 79.6% balanced accuracy but trails B0-policy at 84.9%; out of distribution, the gap is 64.6% versus 88.1%. FT-cf does not resolve it: 0.8B balanced accuracy is 55.2% in distribution and 55.3% out of distribution; 4B is 85.1% and 66.7%, still below out-of-distribution B0-policy at 88.1%. Eligibility requires four conditions together: hardware fault, Premium Care 3Y, valid warranty and region CN/JP/DE/US, as implemented by `support_labels` in `scripts/vendor_policy.py`. FT-cf changes only one field at a time.

<a id="policy-following"></a>

### 3.3 Policy Following When One Device Field Changes

Only questions whose answer differs from the original record are counted; recognizing the edited field is necessary to answer correctly.

<!-- TABLE:CF -->
<!-- SOURCE:TABLE:6 -->
| Size| Variant set| Questions| B0| B0-policy| FT| FT-cf| FT-cf−FT (percentage points, 95% interval)| 
| ---| ---| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: test variants | 172| 22.1%| 47.7%| 48.3%| 57.6%| +9.3 (-1.2 ~ +19.7)| 
| 0.8B| Assistant: test variants | 72| 36.1%| 33.3%| 48.6%| 81.9%| +33.3 (+20.5 ~ +46.7)| 
| 0.8B| Support: out-of-distribution variants | 316| 25.6%| 42.1%| 43.4%| 48.4%| +5.1 (-0.6 ~ +11.1)| 
| 0.8B| Assistant: out-of-distribution variants | 175| 41.1%| 48.6%| 46.3%| 81.7%| +35.4 (+25.4 ~ +45.2)| 
| 0.8B| Support: development variants | 176| 20.5%| —| 54.0%| 60.8%| +6.8 (-4.1 ~ +17.6)| 
| 0.8B| Assistant: development variants | 77| 36.4%| —| 50.6%| 79.2%| +28.6 (+13.8 ~ +43.6)| 
| 4B| Support: test variants | 172| 40.7%| 47.1%| 72.1%| 84.9%| +12.8 (+5.3 ~ +20.6)| 
| 4B| Assistant: test variants | 72| 40.3%| 70.8%| 86.1%| 100.0%| +13.9 (+5.9 ~ +22.5)| 
| 4B| Support: out-of-distribution variants | 316| 38.6%| 55.4%| 62.7%| 78.2%| +15.5 (+9.6 ~ +21.9)| 
| 4B| Assistant: out-of-distribution variants | 175| 50.3%| 79.4%| 84.0%| 98.3%| +14.3 (+8.4 ~ +20.6)| 
| 4B| Support: development variants | 176| 43.8%| —| 75.6%| 90.9%| +15.3 (+8.0 ~ +23.4)| 
| 4B| Assistant: development variants | 77| 54.5%| —| 89.6%| 100.0%| +10.4 (+4.1 ~ +16.9)| 
<!-- /SOURCE:TABLE:6 -->

By edited field, combining test and out-of-distribution variants and counting only changed-answer questions:

<!-- SOURCE:TABLE:7 -->
| Size| Edited field| Questions| B0| B0-policy| FT| FT-cf| 
| ---| ---| ---| ---| ---| ---| ---| 
| 0.8B| Battery cycles| 59| 0.0%| 27.1%| 35.6%| 49.2%| 
| 0.8B| Purchase age (days)| 198| 25.3%| 49.0%| 37.4%| 41.9%| 
| 0.8B| Region| 58| 51.7%| 41.4%| 43.1%| 36.2%| 
| 0.8B| Warranty plan| 173| 22.5%| 45.1%| 57.8%| 68.8%| 
| 0.8B| Power and battery| 56| 21.4%| 21.4%| 17.9%| 75.0%| 
| 0.8B| Enterprise-managed device| 72| 45.8%| 52.8%| 52.8%| 83.3%| 
| 0.8B| Network| 119| 44.5%| 49.6%| 57.1%| 84.0%| 
| 4B| Battery cycles| 59| 61.0%| 33.9%| 44.1%| 66.1%| 
| 4B| Purchase age (days)| 198| 38.9%| 51.0%| 64.1%| 84.8%| 
| 4B| Region| 58| 41.4%| 67.2%| 53.4%| 56.9%| 
| 4B| Warranty plan| 173| 31.8%| 55.5%| 79.8%| 88.4%| 
| 4B| Power and battery| 56| 26.8%| 96.4%| 76.8%| 98.2%| 
| 4B| Enterprise-managed device| 72| 40.3%| 59.7%| 90.3%| 98.6%| 
| 4B| Network| 119| 61.3%| 78.2%| 84.9%| 99.2%| 
<!-- /SOURCE:TABLE:7 -->

For paired records already in the original test set, the following is the fraction where both answers are correct:

<!-- SOURCE:TABLE:8 -->
| Size| Test set| Questions with changed ground truth| B0| B0-policy| FT| FT-cf| 
| ---| ---| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution | 31| 0.0%| 0.0%| 9.7%| 9.7%| 
| 0.8B| Assistant: in-distribution | 22| 0.0%| 0.0%| 13.6%| 63.6%| 
| 0.8B| Support: out-of-distribution | 48| 0.0%| 2.1%| 4.2%| 6.2%| 
| 0.8B| Assistant: out-of-distribution | 32| 0.0%| 3.1%| 3.1%| 59.4%| 
| 4B| Support: in-distribution | 31| 0.0%| 22.6%| 48.4%| 64.5%| 
| 4B| Assistant: in-distribution | 22| 4.5%| 59.1%| 90.9%| 100.0%| 
| 4B| Support: out-of-distribution | 48| 4.2%| 25.0%| 29.2%| 45.8%| 
| 4B| Assistant: out-of-distribution | 32| 3.1%| 50.0%| 65.6%| 96.9%| 
<!-- /SOURCE:TABLE:8 -->
<!-- /TABLE:CF -->

- **FT underuses device fields.** A paired example keeps the customer message and changes one policy field such as warranty, purchase age or network. A model applying that field should answer both correctly. Initial 0.8B FT manages only 9.7% of support pairs and 13.6% of assistant pairs; B0 and B0-policy score 0%. Most of its remaining 53 support-queue errors occur among onsite repair, mail-in, paid quote, accidental-damage claim and battery program, precisely the queues governed by those fields. This supports a distinction between recognizing the issue from text and applying company policy to the device record.
- **FT-cf adds targeted variants.** Each training message gets up to 3 variants, changing one policy field and recomputing labels. Product line stays fixed because the message can name the model. The extra 1,685 records expand training from 2,147 to 3,832. Separate variants use only development, test and out-of-distribution messages, never training messages. The rule was recorded before results: recommend FT-cf only when development-variant accuracy improves and original development accuracy drops by no more than 1 point.
- **Both sizes qualify.** On all development-variant questions, support/assistant scores rise from 78.9%/82.9% to 82.2%/92.8% for 0.8B, and from 89.1%/96.4% to 95.9%/100.0% for 4B. Original development scores do not fall: 87.7%/94.1% to 88.4%/97.5% for 0.8B, and 93.9%/98.4% to 95.2%/99.6% for 4B.
- **Assistant routing benefits most.** For changed-answer questions, 0.8B improves from 48.6% to 81.9% on test variants and from 46.3% to 81.7% out of distribution. 4B reaches 100.0% and 98.3%. Across network, enterprise management and power/battery fields, 0.8B moves from 17.9%-57.1% to 75.0%-84.0%.
- **Support policy gaps remain.** 0.8B changes only from 48.3% to 57.6% on test variants, with a 95% difference interval including 0. Purchase age, region and battery-cycle accuracy remains 41.9%, 36.2% and 49.2%. These policies require numeric thresholds or membership checks: warranty duration, battery cycles below 500 and purchase age no more than 730 days, and an onsite-region list. 4B support test variants improve from 72.1% to 84.9%, but region accuracy is 56.9%, below B0-policy's 67.2% on only 58 questions.
- **Original test pairs show a similar direction.** Both-correct assistant pairs rise from 13.6% to 63.6% for 0.8B and from 90.9% to 100% for 4B. Support remains 9.7% for 0.8B. These pairs were inspected while designing FT-cf, so they are reference results, not the selection set.
- **The trade-off is modest on this run.** Main-set accuracy improves by 0.4-4.0 points over FT. General-task accuracy is unchanged for 0.8B and 0.9 points above the released baseline for 4B, as described in section 3.5.

### 3.4 Can Confidence Guide Automation or Human Review

<a id="calibration-guide"></a>

**Calibration adjusts probabilities; it does not correct a wrong answer.** After fine-tuning, this project freezes the model weights, fits a temperature on labeled calibration data, and exports that parameter with the model to GGUF. The laptop's llama.cpp engine reads it during inference. Customers need neither laptop retraining nor a second model to judge each answer. The business application must decide whether to act or request human review; this repository does not implement that decision.

#### 3.4.1 Labels Are Not Target Probability Tables

A calibration record contains the business input, questions, candidate options and ground-truth labels. For a support ticket, the input combines the message and device record, and the routing label identifies the expected queue. The model receives the input and questions; labels are used for offline fitting and scoring. This project's [vendor_policy.py](../scripts/vendor_policy.py) computes labels from the simulated vendor's rules. Another language model does not grade the answers.

**A correct label of A does not establish that A's true probability is 80%.** A target probability distribution is generally unavailable for an individual question. Calibration concerns statistical reliability across enough representative, unseen questions: for example, predictions assigned approximately 80% probability should be correct approximately eight times out of ten. This describes the statistical meaning, not a result measured here.

All options in one mutually exclusive choice question sum to 100%, but normalization does not establish calibration. Both 40% / 30% / 30% and 80% / 10% / 10% satisfy that constraint. Do not add probabilities from different questions. A yes/no question has complementary probabilities; the API's `noul` field returns only the probability of yes. An ordinal question distributes probability across its grades. Multilabel classification, where several labels may apply simultaneously, is different and does not require the label probabilities to sum to 100%.

#### 3.4.2 Keep Four Data Roles Separate

- **Training data** updates LoRA and pointer-head weights to learn the business task.
- **Development data** supports recipe, checkpoint or stopping decisions. This project selects between FT and FT-cf using development results, not final test scores.
- **Calibration data** fits the probability transformation after weights are fixed. It is separate from this weight-training run, but it does participate in parameter fitting and is no longer untouched evaluation data.
- **Independent test data** evaluates answers, probability reliability and the error/coverage of any automated subset after the recipe, temperature and applicable business thresholds are fixed. Threshold selection and final acceptance also need separate data.

Before deployment acceptance, freeze the model, temperature and business thresholds. The historical pipeline trains, calibrates and evaluates FT and FT-cf separately, then selects using the predeclared development rule; it does not calibrate only the eventual winner. Test questions were inspected during error analysis and FT-cf design, with the limitations recorded in section 3.3. Inference applies the saved value; it does not refit it or normally have ground truth available. Group separation is not source independence: the calibration and training splits here use the same source and rules. Section 3.4.6 explains that limitation.

#### 3.4.3 What Changes in an Already-Trained Model

The model first produces raw option scores, or logits, rather than percentages. Temperature scaling computes `p_i(T) = exp(z_i / T) / sum_j exp(z_j / T)`, where `z_i` is an option's logit, T is positive and `p_i` is its probability. The implementation subtracts the maximum logit first for numerical stability; this does not change the mathematical result.

**The parameter changes the conversion from logits to probabilities, not the trained model weights.** The same input retains its raw scores. T = 1 adds no temperature adjustment; T > 1 flattens the distribution, while 0 < T < 1 sharpens it. Divide logits by T before softmax, not a returned percentage such as 60% by T.

T is dimensionless, not a Celsius temperature, accuracy score or acceptance threshold. As a mathematical illustration, probabilities of 80% / 10% / 10% at T = 1 become approximately 58.6% / 20.7% / 20.7% at T = 2. The leading option stays first. This is not a measurement from this experiment. Fit T across the calibration set rather than adjusting each question to a desired percentage.

The project invokes Kev's [calibrate_checkpoint.py](https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/scripts/calibrate_checkpoint.py). Its [temperature-fitting implementation](https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/kev/metrics.py) tries 121 values on a logarithmic grid from 0.25 to 4. For each value it recomputes probabilities from the same saved scores, then minimizes **mean negative log-likelihood, NLL, with equal weight per question**. NLL penalizes assigning little probability to the correct label. The objective is not accuracy or ECE directly.

Those 121 candidates are numbers, not models or training runs. They do not require a separate model forward pass per candidate. Ground truth selects T offline and is absent from customer inference requests. One shared scalar is fitted per checkpoint, not one value per question, so it cannot necessarily repair every class or example. The deployment control is the decision-temperature metadata in GGUF, not the ordinary `--temp` sampling setting used for generated chat text.

#### 3.4.4 Why Probabilities Matter When Ranking Is Correct

**The following examples are hypothetical, not measured results.** A question with A 40%, B 30%, C 30% selects the same winner as A 80%, B 10%, C 10%. If independent evidence supported the latter distribution, the former would understate A's probability. A single correct label of A does not supply that evidence or establish an exact 80% target.

Consider 100 tickets, of which 90 are routed correctly and 10 incorrectly. Assigning every selected answer 99% probability overstates reliability on that batch; assigning every selected answer 60% understates it. Here 60% is each selected option's probability, not measured model accuracy. Identical probabilities across all tickets are only a simplifying example; real questions usually have different probabilities.

A positive shared T preserves the ordering of logits and probabilities within a question. **For an argmax classification decision, temperature scaling changes neither the chosen label nor classification accuracy.** An application can still act differently: if automatic dispatch requires a maximum option probability of at least 90%, two predictions that both select onsite repair but report 60% and 96% cross that threshold differently. The 90% threshold is illustrative, not deployment guidance; select and independently validate it on representative data.

Rank preservation applies to argmax over the same logits. An ordinal API `score` is a probability-weighted expected grade and may change with temperature. Probability-based business thresholds may also be crossed. Quantization or a different inference engine can change the logits themselves, so the mathematical ranking property does not replace on-device acceptance.

#### 3.4.5 From a Detected Problem to a Customer Update

When answers meet business requirements but probabilities are too high or too low, keep the weights, refit T on calibration data, save a new version, and check probability quality on independent test data. **Do not stop at detecting a mismatch, or manually change a particular question from 40% to 80%.** If a shared temperature is insufficient, investigate data representativeness, labels and the calibration method, and improve training if needed. Calibration is not guaranteed to succeed.

When the model frequently selects the wrong answer, first inspect inputs, labels and the task definition. Add representative examples targeting the actual errors, fine-tune again or change models. Retraining should reflect an identified data or recipe change, not simply repeat the same run. Answer errors and probability errors can coexist; calibration cannot make an unsuitable model competent at the task.

A recorded example is the [US support request and response](../验证结果/本机试用_20261028-201046/support-us/result.json). The simulated customer describes failed keys without a drop or liquid damage. The model puts `sales_ops` first at 42.3%, mail-in repair at 31.3% and onsite repair at 26.2%, with smaller probabilities on the other options. The project's simulated policy requires onsite repair. The prediction is both diffuse and wrong, but the label, not low probability alone, establishes the error. The API `confidence` is approximately 34.1%, a different normalized score from the maximum option probability of 42.3%. No before/after-calibration pair was recorded for this request, so it does not show that calibration turned a confidently wrong answer into an uncertain one.

An application could request more information, user confirmation or human review for uncertain predictions. These are policy recommendations: **the current client has no automatic human handoff or fallback to another model**. If high-probability predictions are also frequently wrong, filtering only low-probability requests is insufficient. Restrict the affected automated decisions until representative independent tests meet business requirements.

The customer deliverable is **a GGUF containing the calibration parameters plus a matching inference engine**, not a claim that calibration has been completed. The model computes scores, the inference implementation converts them to probabilities, and the fitted parameters travel with the model. The [README's local trial](../README.md#local-try) and [training/update workflow](../README.md#train-update) explain deployment and calibration-only updates. No laptop retraining or separate calibration service is required.

#### 3.4.6 What This Temperature Fit Actually Demonstrated

The question was whether temperature scaling made a fixed checkpoint's probabilities better reflect the labels. The 0.8B FT-cf calibration split contains **984 labeled questions** excluded from its weight-training data. After saving scores, the pipeline invokes `scripts/calibrate_checkpoint.py --run "$FC" --rows "$R/ftcf-calib-raw/rows.json" --allow-in-distribution`. This is an excerpt of the [FT-cf pipeline](../scripts/remote_cf_round.sh), run in the Kev source directory: `$FC` identifies the `ft_cf` checkpoint and `$R` its size-specific run directory. The [raw calibration report](../验证结果/微调评测_20261027-220226/runs/0.8b/ftcf-calib-raw/report.json) and [fit log](../验证结果/微调评测_20261027-220226/runs/0.8b/calibrate_cf.log) preserve the results. Only T changes in this comparison; the checkpoint and questions stay fixed. It is not a before/after-fine-tuning comparison.

- **Fit-set result:** T is approximately 1.15; accuracy remains 93.0% → 93.0% and ECE changes from 0.011 → 0.008. ECE is dimensionless and lower is better. These are results on the data used to fit T, not independent test evidence.
- **Five-fold cross-validation:** folds separate source/record groups so related questions stay together. Each fit uses four folds and evaluates the remaining fold. Out-of-fold ECE is 0.005; the 95% bootstrap interval for out-of-fold minus raw ECE is [-0.009, 0.004]. It includes zero, and the log reports `separated=False`. This does not establish a statistically significant improvement. The final T is fitted on the full calibration set, not selected from the best fold or run.
- **Source limitation:** the run uses `--allow-in-distribution`. The upstream script cannot identify the custom sources through its built-in suites and explicitly records an in-distribution warning. Separate samples do not establish an independent data source. New customers or distributions require new validation; this T is not a universal constant.
- **Delivered value:** the [GGUF metadata](../验证结果/微调评测_20261027-220226/gguf/0.8b-cf/metadata.txt) stores `qwen35.decision.temperature.choice`, `.score` and `.noul` as FLOAT32, all at 1.148698329925537. Prose rounds this to 1.1486983 and the resource table to 1.15. These are display precisions of one parameter, not different runs, an accuracy value or a value refitted for each request.

In llama.cpp b11935, [server_decision_context::init and format_answer](https://github.com/ggml-org/llama.cpp/blob/b11935/tools/server/server-decision.cpp) read that metadata and scale scores before softmax. The [on-device run record](../验证结果/端侧引擎_20261027-124700/ftcf-kev-0.8b-Q8_0-cpu/run.json) identifies the loaded GGUF by hash and records the engine version. This establishes the recorded delivery and inference path, not acceptance of final quantized probabilities on real customer data. The calibration statistics above come from PyTorch; using probabilities for device-side decisions requires acceptance on the final file and target device.

Do not conflate API fields. For choice questions with K > 1 options, b11935 computes `confidence = max(0, (max(probabilities) - 1/K) / (1 - 1/K))`: uniform guessing maps to 0 and a certain choice to 1. It is neither accuracy nor the maximum option probability. ECE and error-budget coverage in this report use the evaluation rows' maximum option probability, not that derived API field. Specify which field a business threshold applies to; the values are not interchangeable.

#### 3.4.7 Historical Comparisons on the Test Sets

The table below compares probability quality and coverage for the released model, policy prompting, FT and FT-cf on fixed test sets. The columns differ in training as well as temperature. **Do not attribute their entire difference to calibration.** Section 2 identifies the inputs, splits and comparison arms; all original metrics and configurations are retained.

<!-- TABLE:CAL -->
<!-- SOURCE:TABLE:9 -->
| Size| Test set| ECE B0 / B0-policy / FT / FT-cf| Brier B0 / B0-policy / FT / FT-cf| Coverage at 5% error budget: B0 / B0-policy / FT / FT-cf| 
| ---| ---| ---| ---| ---| 
| 0.8B| Support: in-distribution | 0.048 / 0.140 / 0.023 / 0.030| 0.641 / 0.538 / 0.168 / 0.152| 2.9% / 18.4% / 84.7% / 84.5%| 
| 0.8B| Assistant: in-distribution | 0.095 / 0.175 / 0.011 / 0.013| 0.396 / 0.408 / 0.088 / 0.035| 13.0% / 17.2% / 97.1% / 100.0%| 
| 0.8B| Support: out-of-distribution | 0.074 / 0.134 / 0.050 / 0.064| 0.630 / 0.523 / 0.253 / 0.233| 6.1% / 29.9% / 65.4% / 69.9%| 
| 0.8B| Assistant: out-of-distribution | 0.080 / 0.125 / 0.023 / 0.017| 0.421 / 0.454 / 0.118 / 0.083| 6.7% / 11.6% / 92.6% / 98.8%| 
| 4B| Support: in-distribution | 0.043 / 0.058 / 0.023 / 0.019| 0.514 / 0.468 / 0.098 / 0.062| 19.8% / 17.5% / 96.7% / 100.0%| 
| 4B| Assistant: in-distribution | 0.143 / 0.213 / 0.023 / 0.008| 0.291 / 0.263 / 0.023 / 0.003| 43.2% / 71.5% / 100.0% / 100.0%| 
| 4B| Support: out-of-distribution | 0.044 / 0.059 / 0.041 / 0.023| 0.518 / 0.466 / 0.159 / 0.121| 18.5% / 14.2% / 84.1% / 91.2%| 
| 4B| Assistant: out-of-distribution | 0.144 / 0.213 / 0.005 / 0.009| 0.297 / 0.292 / 0.050 / 0.016| 44.4% / 61.6% / 100.0% / 100.0%| 
<!-- /SOURCE:TABLE:9 -->
<!-- /TABLE:CAL -->

**Expected calibration error, ECE**, compares stated confidence with observed accuracy within bins and takes the question-weighted average gap. Values closer to 0 are better. **Coverage at a 5% error budget** sorts test questions by confidence, then uses their labels to find the largest prefix with error no greater than 5%. It describes this test set's risk/coverage trade-off, not an independently selected deployment threshold.

Fine-tuned probabilities help evaluate routing, but cannot promise deployed error rates. FT ECE is at most 0.05 across tests: 0.011-0.023 in distribution and 0.005-0.050 out of distribution. FT-cf is below 0.03 except 0.8B out-of-distribution support at 0.064. B0-policy assistant ECE is 0.175 for 0.8B and 0.213 for 4B. Bin averages do not guarantee error above a chosen threshold, on a minority class or under a new distribution. Choose thresholds on independent data, freeze them, then validate.

Measured FT coverage in distribution is 84.7%/97.1% for 0.8B and 96.7%/100% for 4B; out of distribution it is 65.4%/92.6% and 84.1%/100%. FT-cf coverage is 84.5%/100% and 100%/100% in distribution, and 69.9%/98.8% and 91.2%/100% out of distribution. B0 ranges from 2.9% to 44.4% across the same definition. These remain evaluation statistics, not approval for unattended handling.

### 3.5 Retention of General Capability

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

The public transfer-v4 development set has 656 general decision questions unrelated to vendor tasks. Released scores were first reproduced on this VM, matching the author; see [public-baseline evidence](../验证结果/公开基线复现_20261027-123403).

**The predefined forgetting threshold is not triggered.** Both 0.8B recipes remain at 64.8%. FT changes 45 answers: 20 wrong-to-right, 20 right-to-wrong and 5 wrong-to-different-wrong. FT-cf changes 52: 22 become correct and 22 become wrong. 4B FT falls from 81.7% to 80.9%, a 0.8-point drop; FT-cf rises to 82.6%. None exceeds the protocol's greater-than-2-point drop threshold. This covers those 656 questions, not all general capabilities.

**General-task confidence worsens.** For FT, Brier rises from 0.430 to 0.560 on 0.8B and from 0.243 to 0.299 on 4B; FT-cf scores 0.574 and 0.269. Business calibration changes 0.8B temperature from 2.35 to 1.26 and sharpens probabilities. Recomputing FT at temperature 2.35 gives 0.490, still worse than the released score, so calibration does not explain the entire change. For mixed business/general use, fit separate temperatures or calibrate on mixed data.

## 4. Resource Requirements

### 4.1 Training on One H100 NVL

Hardware: one H100 NVL with 95,830 MiB GPU memory in Azure `Standard_NC40ads_H100_v5`.

<!-- TABLE:TRAIN -->
<!-- SOURCE:TABLE:12 -->
| Model and recipe| micro-batch × accum| Records processed (2 epochs)| Optimizer steps| 
| ---| ---| ---| ---| 
| 0.8B FT| 1 × 8| 6,294| 788| 
| 0.8B FT-cf| 4 × 2| 9,664| 1,208| 
| 4B FT| 4 × 2| 6,294| 788| 
| 4B FT-cf| 4 × 2| 9,664| 1,208| 
<!-- /SOURCE:TABLE:12 -->

<!-- SOURCE:TABLE:13 -->
| Model and recipe| Wall-clock time| Whole-device GPU peak (nvidia-smi)| PyTorch allocation peak| Calibration temperature| 
| ---| ---| ---| ---| ---| 
| 0.8B FT| 26.9 minutes| 4,555 MiB| 3,460 MiB| 1.26| 
| 0.8B FT-cf| 11.6 minutes| 7,573 MiB| 5,326 MiB| 1.15| 
| 4B FT| 15.7 minutes| 33,359 MiB| 22,581 MiB| 1.66| 
| 4B FT-cf| 20.1 minutes| 26,215 MiB| 22,641 MiB| 2.35| 
<!-- /SOURCE:TABLE:13 -->
<!-- /TABLE:TRAIN -->

- **Both sizes train on one GPU.** 0.8B FT uses micro-batch 1 and takes 26.9 minutes; 4B FT uses micro-batch 4 and takes 15.7. 0.8B FT-cf sees 54% more records, switches to micro-batch 4 and takes 11.6 minutes. Because both conditions change, the entire time difference cannot be attributed to micro-batch. With 9,664 processed records and micro-batch 4, 4B FT-cf takes 20.1 minutes. Effective batch is always 8. FT sees (2,147 + 1,000) × 2 = 6,294 records across epochs; FT-cf sees (3,832 + 1,000) × 2 = 9,664. All four `training_metrics.json` files report `truncated_records=0`.
- **Distinguish whole-device memory from tensor allocation.** `nvidia-smi` may include caches and other processes; PyTorch allocation excludes some runtime overhead. Neither single observed peak is a universal minimum specification.
- **The same model can have different whole-device peaks.** 4B allocation peaks are nearly equal at 22,581/22,641 MiB, while `nvidia-smi` differs by 7,144 MiB, 33,359 versus 26,215 MiB. Reserved caching is a hypothesis; whole-card sampling does not prove it.
- **Micro-batch 1 lowers memory.** With bf16, gradient checkpointing, `max_state 768`, batch 1 and accumulation 8, an 8-step probe on the 64 longest vendor records and no other GPU processes reaches whole-device peaks of 4,213/18,547 MiB for 0.8B/4B and allocation peaks of 3,365/17,375 MiB. See [probe status, logs and samples](../验证结果/微调评测_20261027-220226/runs/memory-probe). The probe omits replay records; full 0.8B FT at batch 1 allocates 3,460 MiB, about 3% more. Leave headroom.
- **List-price estimate, not billed cost.** Azure Retail Prices API lists USD 9.07 per hour in Spain Central on 2026-10-27; subscription discounts were not checked. Training alone costs about USD 1.8-4.1 per 0.8B run and USD 2.4-3.0 per 4B run. The whole experiment, including setup, baselines, both sizes and recipes, evaluation, conversion and memory probes, uses the VM for 2 hours 53 minutes, about USD 26.2 at list price.

### 4.2 Simulated-Message Generation Usage

<!-- SOURCE:TABLE:14 -->
| Generator model| Purpose| Original messages| Input tokens| Output tokens| 
| ---| ---| ---| ---| ---| 
| Model A| Training, calibration, development and in-distribution tests| 2 × 1,400| 268,857| 148,259| 
| Model B (another provider)| Out-of-distribution evaluation| 2 × 300 (287 successful assistant cases)| 151,947| 115,756| 
<!-- /SOURCE:TABLE:14 -->

Counts come from `data/contoso/*.usage.json`. Generator prices were not verified, so token usage is not converted into monetary cost.

### 4.3 Laptop Resources

The section 5 tables retain each configuration. Files are 528 MiB for 0.8B Q4_K_M and 775 MiB for Q8_0; 4B files are 2,893 and 4,276 MiB. With defaults on CPU, fine-tuned 0.8B uses 1,819-2,314 MiB peak working set and 4B FT-cf uses 6,842-9,609 MiB. Median decisions take 0.65-0.98 seconds for 0.8B and 3.6-4.8 seconds for 4B FT-cf on the 12-core Snapdragon X Elite.

### 4.4 Hardware Selection

<!-- SOURCE:TABLE:15 -->
| Stage| GPU required?| Measured hardware and usage (GPU memory is nvidia-smi peak)| Estimated minimum from memory measurements; these cards were not tested| 
| ---| ---| ---| ---| 
| Train 0.8B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 4,555 MiB GPU memory (micro-batch 1), 7,573 MiB (micro-batch 4)| 8 GB GPU memory (micro-batch 1)| 
| Train 4B| 1 GPU required; these scripts use NVIDIA CUDA| H100 NVL; 18,547 MiB (micro-batch 1, probe only), 26,215–33,359 MiB (micro-batch 4)| 24 GB GPU memory (micro-batch 1); over 40 GB for micro-batch 4| 
| GGUF export| No; CPU only| GPU host's CPU| —| 
| Laptop inference 0.8B (Q8_0)| No discrete GPU or NPU; CPU inference| 12-core Snapdragon X Elite; 2,314 MiB peak working set, 5,014 MiB commitment (defaults) or 2,119 MiB (`-c 2048 -ub 512`)| Size total RAM for this process plus the OS and other applications| 
| Laptop inference 4B FT-cf (Q8_0 / Q4_K_M)| No discrete GPU or NPU; CPU inference| 12-core Snapdragon X Elite; peak working set 9,609 / 6,842 MiB and commitment 8,884 / 7,495 MiB| Same sizing principle| 
<!-- /SOURCE:TABLE:15 -->

The 24 GB recommendation for 4B is an estimate: batch 1 was probed on 64 long records at 18,547 MiB, not fully trained. Full 0.8B training uses about 8% more whole-device memory than its probe, 4,555 versus 4,213 MiB. Applying that margin suggests about 20 GB for 4B, leaving roughly 4 GB on a 24 GB card.

The recipe uses `--dtype bf16`; verify support. Training times are measured only on H100 NVL, not smaller GPUs. `kev.benchmark` evaluation also used GPU, with memory not separately recorded, and is not required for deployed inference. The NPU was not tested; Adreno was slower than CPU.

## 5. llama.cpp on Snapdragon X Elite

Hardware: Snapdragon X Elite X1E80100 with 12 CPU cores and Adreno X1-85 GPU, driver 31.0.133.1, 64 GB RAM and Windows 11 Enterprise. See [device information](../验证结果/端侧引擎_20261027-124700/device_info.txt). Runtime: official llama.cpp b11935 Windows ARM64 CPU and Adreno OpenCL packages. Each run starts one `llama-server`, sends records sequentially to `/v1/systemone`, and records answers, probabilities and per-request timing before comparing with H100/PyTorch predictions for the same records.

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

Incomplete and excluded: `ft-kev-0.8b-Q8_0-cpu-ctx2048`, 144 support records without a summary; and `ft-kev-4b-Q4_K_M-cpu`, 36 support records without a summary.
<!-- /TABLE:ENGINE -->

**Definitions**: agreement is the fraction of question answers matching PyTorch, not correctness. Probability difference is mean total variation distance, 0 for identical distributions and 1 for completely disjoint ones. Request latency covers client send to receipt of all 3 answers: one record is one decision. p50 is the median; p90 is the time not exceeded by 90% of requests. The first 2 requests are warm-up and excluded. Peak working set is peak physical process memory; committed memory is process memory committed by the system, including some reserved overhead. The 4B FT-cf Q8_0 working set of 9,609 MiB exceeds its 8,884 MiB commitment; memory-mapped model pages are a possible explanation, not verified here.

### Finding 1: Fine-Tuned Weights Run on the Device

The converter merges LoRA into the base and writes calibration temperature into GGUF. FT temperatures are 1.2599 for 0.8B and 1.6625 for 4B, matching `head.pt`. For 0.8B FT Q8_0 CPU, accuracy exactly matches PyTorch at 86.5%/93.5%, answer agreement is 99.2%/99.6% and mean probability difference 0.007/0.004.

0.8B FT-cf Q8_0 uses temperature 1.1487 and agreement 99.2%/99.8%. Its one assistant disagreement has probabilities near 0.5, 0.528 versus 0.572; llama.cpp gets that question right, producing 97.7% versus 97.5% accuracy. 4B FT-cf Q8_0 uses 2.3511 and agrees on 507 of 510 support questions, 99.4%; the 3 differing choices have probabilities only 0.48-0.51. The engine gets one additional question right, 96.1% versus 95.9%. All 477 assistant answers agree, with 99.8% accuracy on both. Mean probability differences are 0.003/0.001. 4B FT was exported at 1.6625 but its device run stopped after 36 records and is excluded; only FT-cf completed for 4B.

### Finding 2: Quantization Trades Memory for Agreement

0.8B Q4_K_M saves about 250 MiB on disk and 500 MiB working set. Its support/assistant medians are 812/909 ms versus 669/822 ms for Q8_0, within the variability discussed below. Agreement drops to 94.9%/97.9%, with some probability differences of 0.46-0.58. Its support accuracy of 87.5%, 1 point above PyTorch, is a favorable quantization perturbation on this set, not evidence that it is generally better.

For 4B FT-cf, Q4_K_M saves 1,383 MiB on disk, 2,893 versus 4,276 MiB, and 2,767 MiB working set, 6,842 versus 9,609 MiB. Agreement falls from 99.4%/100% to 98.2%/99.8%, with individual probability differences up to 0.60. Support accuracy is 95.3%, 0.6 points below PyTorch: 6 questions move from PyTorch-correct to engine-wrong and 3 in the reverse direction. Timing cannot discriminate the formats in this run. Use Q8_0 by default; consider Q4_K_M when memory is constrained.

### Finding 3: Adreno OpenCL Is Slower Here

The same fine-tuned 0.8B Q8_0 model has a 1,035 ms support median on OpenCL versus 669 ms on CPU, agreement 97.6% versus 99.2%, about 3,400 MiB extra shared GPU memory, and 5,801 MiB process commitment. Initial loading takes 75 seconds and the next load 15 seconds. Kernel compilation and driver caching are plausible explanations, not proven attribution. A decision is one forward pass over roughly 300-500 tokens without text generation; startup and transfer overhead may dominate this short workload on a 12-core CPU. This is a hypothesis, not a profiling result.

### Finding 4: Runtime Parameters Affect Memory and Latency

Defaults `-c 8192 -b 2048 -ub 2048` and 4 slots give 0.8B Q8_0 commitment 5,014 MiB and working set 2,314 MiB. With `-c 2048 -ub 512`, commitment becomes 2,119 MiB without accuracy loss, but support median rises to 1,163 ms, about 1.2 seconds. Extra processing chunks are a hypothesis, not profiled. A context-only `-c 2048` run retaining `-ub 2048` stopped after 144 support records; individual parameter effects cannot be separated from that incomplete control.

### Finding 5: Policy Text Is More Expensive on the Device

With the same released 0.8B Q8_0 CPU settings, B0-policy increases median input tokens from 488 to 1,505 on support and from 456 to 813 on assistant. Medians increase from 666 to 4,353 ms and from 843 to 2,435 ms. Commitment grows from 5,016 to 5,899 MiB, for accuracy 60.6%/71.7%, comparable with PyTorch's 60.8%/71.9%. Fine-tuned 0.8B reaches 86.5%/93.5% in 669/822 ms on the same laptop.

### Finding 6: One Run Does Not Establish Small Latency Differences

0.8B FT and FT-cf Q8_0 have identical architecture and per-record input-token counts. Paired by record, FT-cf is 53 ms faster on support and 166 ms slower on assistant, approximately -8%/+20%. Its first device run overlapped a result-summary process and had an 841 ms support median; it was rerun on an idle laptop, and the tables use that rerun. Each configuration has one measured run, without controlled temperature or power state. Therefore Q4_K_M/Q8_0 differences of +21%/+11% are not ranked, whereas Adreno (+49%-76%), `-c 2048 -ub 512` (+44%/+74%) and B0-policy (2.9-6.5 times the latency) exceed that observed variation.

The three 4B runs, released Q4_K_M, FT-cf Q8_0 and FT-cf Q4_K_M, also have identical token counts per record. Paired medians differ by 7-24%; even the two same-architecture Q4_K_M runs differ by 23-24%, or +666 ms on support and +906 ms on assistant. At assistant record 139, the FT-cf Q8_0 run entered Modern Standby for 5.4 hours, supported by Kernel-Power events 506/507. Including that request yields a 4,115 ms median; excluding it gives 4,113 ms. Q4_K_M runs after resume, so the two formats cannot be ranked by latency. Only the roughly 3-5 second decision range is supported.

### NPU Boundary

NPU execution was not tested. llama.cpp's Windows Hexagon instructions at commit `7ecb57f7`, `docs/backend/snapdragon/windows.md`, require `bcdedit /set TESTSIGNING ON`, potentially disabling Secure Boot, and trusting a self-signed root certificate. Those changes weaken the managed device's security baseline, so this project tests only CPU and Adreno paths that do not require them.

## 6. Conclusions and Recommendations

### 6.1 Answers to the Four Questions

<!-- SOURCE:TABLE:19 -->
| Question| Answer| Evidence| 
| ---| ---| ---| 
| 1. Does fine-tuning adapt to business data?| Improves on this simulated data: FT-cf in-distribution support/assistant scores are 86.9% / 97.5% for 0.8B and 95.9% / 99.8% for 4B; the 95% improvement interval lower bound against release exceeds 0. Policy following improves, but onsite eligibility and 0.8B support fields remain weak| 3.1–3.3| 
| 2. Accuracy, confidence and general-task retention| FT exceeds policy prompting by 10.5–30.2 points. FT-cf in-distribution coverage at a 5% error budget is 84.5–100%, not a deployed fixed-threshold guarantee. Public accuracy changes by −0.8 to +0.9 points, without triggering the predefined forgetting threshold; Brier worsens| 3.1, 3.4, 3.5| 
| 3. Resource requirements| One H100 NVL: 12–27 minutes per run, USD 1.8–4.1 at list price. Batch-1 GPU peaks: 4,213 MiB for 0.8B and 18,547 MiB for 4B. Laptop Q8_0 files: 775 / 4,276 MiB; peak working sets: 2,314 MiB for 0.8B and 9,609 MiB for 4B FT-cf| Section 4| 
| 4. Device runtime| Official llama.cpp b11935 runs fine-tuned GGUF. On Snapdragon X Elite CPU, 0.8B Q8_0 agrees with PyTorch on at least 99.2%, with 0.65–0.98 second medians; 4B FT-cf Q8_0 gives 99.4% / 100% agreement and 3.6–4.1 seconds. CPU is faster than Adreno here| Section 5| 
<!-- /SOURCE:TABLE:19 -->

### 6.2 Guidance Within the Measured Scope

- **Evaluate 0.8B first, then 4B where quality needs justify it.** 0.8B FT-cf reaches 86.9%/97.5% in distribution, with a 775 MiB file and 0.65-0.98 second medians. 4B adds 9.0/2.3 points and handles field-dependent support rules better, at Q8_0 medians of 3.6-4.1 seconds and a 9,609 MiB working set, roughly 4-6 times the latency and 4 times the memory. Rule-heavy support merits evaluating 4B. Released 4B is not a substitute for tuning: its device scores of 59.0%/82.0% are 27.9/15.7 points below fine-tuned 0.8B, with 3.9-4.7 times the latency and about 3 times the working set.
- **Default to Q8_0 on CPU.** It best preserves training-runtime answers here and is not slower than Q4_K_M for 0.8B. Under a 4B memory constraint, Q4_K_M saves 2,767 MiB working set at a 0.6-point support-accuracy loss against PyTorch. Recheck on the vendor's own tests. The observed Adreno path is slower and less consistent.
- **Choose server parameters for device memory.** A single local user may not need 4 slots and an 8K context. The tested lower-memory combination cuts commitment from 5,014 to 2,119 MiB, with unchanged accuracy but medians rising from 669/822 to 1,163/1,184 ms. The context-only control did not finish, so complete that control before attributing the slowdown.
- **Explicitly train field-change cases.** Initial 0.8B FT answers only 48.3%/48.6% of changed-answer questions correctly. FT-cf raises assistant accuracy from 48.6% to 81.9% and 4B support from 72.1% to 84.9%. One-field variants do not resolve multi-condition onsite eligibility. Multi-field combinations and threshold-near values are proposed additions, not validated results of this experiment.
- **Validate thresholds before routing.** Choose on independent calibration/development data, freeze them, then evaluate coverage, errors and minority classes on unused data. Test-label-derived risk/coverage is not a deployable threshold. Human or cloud fallback needs explicit business approval and a separate implementation; the current client has neither.
- **Preserve checks when moving to real data.** Use policy-generated or human-reviewed labels, grouped splits, another-source out-of-distribution tests, paired cases and per-question PyTorch/device comparison. Reusable scripts are in `scripts/`.

### 6.3 Limits

- Simulated vendor policies, fields and model-generated messages are more regular than real customer data. Absolute real-world accuracy will differ. The report demonstrates the method and measured scale within this setup.
- One seed-1 training run per recipe: bootstrap intervals describe sample uncertainty, not seed or dataset-generation variation.
- Temperature is fit on in-distribution calibration data with `calibrate_checkpoint.py --allow-in-distribution`; the warning and out-of-distribution ECE remain part of the evidence.
- The 13 refused-message assistant cases are absent from out-of-distribution accuracy.
- One laptop and sequential requests: no concurrency, sustained thermal, battery or NPU tests. Each configuration has one run; same-architecture paired latencies can differ by 24%. The 4B Q8_0 standby incident is retained. Only recommended 4B FT-cf configurations completed; 4B FT stops after 36 records and is excluded.

## 7. Operations and Evidence

Executable commands are maintained only in the README to prevent two diverging runbooks:

<!-- SOURCE:TABLE:20 -->
| Task| Owning operational entry| Evidence retained here| 
| ---| ---| ---| 
| Use an existing model on the laptop| [Local trial](../README.md#local-try)| [Real local trial](../README.md#local-result), including incorrect answers| 
| Produce a new model from business data| [Train and update](../README.md#train-update)| Sections 2–4: method, data scale, accuracy and training resources| 
| Verify data, scoring and device agreement| [Verification](../README.md#verify)| Sections 3–5: complete historical matrices and raw evidence links| 
| Read original decision rules and deviations| [Experimental protocol](Experiment-Protocol.md)| The original protocol is retained, not rewritten to fit new results| 
<!-- /SOURCE:TABLE:20 -->

Optional complete message generation is `gen_vendor_data.py` with `sample → render → build → assemble`. Connection settings come from `GEN_BASE_URL`, `GEN_API_KEY` and `GEN_AUTH`. Reproducing with supplied data requires no new generation calls. New customer data and checkpoints need independent version directories; do not overwrite historical evidence and reuse old scores.