# Experimental Protocol

[English](Experiment-Protocol.md) | [中文](%5BNOTES%5D_实验协议_20261027-124000.md) · [Project home](../README.md) · [Detailed report](Finetuning-and-On-Device-Validation-Report.md)

Frozen on **2026-10-27 at 12:40, UTC-07:00**, before results. This English edition preserves the original protocol and its recorded deviations; it does not retroactively change the method.

## Question

Can a fictional AI PC vendor, Contoso PC, adapt open-weight Kev to its own business data so that its decisions become materially more accurate and better calibrated without unacceptable loss on general tasks?

## Simulated Data, Not Real Customer Data

| Dimension | Protocol setting |
|---|---|
| Scenario A: support-ticket triage | State is the customer message plus product line, region, warranty plan, purchase age, battery cycles and diagnostic code. Questions: queue selection, 8 choices; onsite eligibility, yes/no; urgency, 4 levels. |
| Scenario B: on-device assistant routing | State is the message plus network, enterprise-management status, power/battery and foreground application. Questions: tool selection, 14 choices; entirely local action, yes/no; confirmation required, yes/no. |
| Ground truth | Computed by vendor-policy code in `scripts/vendor_policy.py`, not judged by a large model. |
| Message text | A large model writes messages from required fact lists, without internal codes, warranty names or queue labels. About 60% Chinese and 40% English. |
| G1: training and in-distribution evaluation | Model A writes 1,400 original messages per scenario. About 35% also receive a paired case changing one device field and its policy label. |
| Splits | Hash by original-message group: training 70%, calibration 10%, development 10%, test 10%. Originals and pairs remain in the same split. |
| G2: out-of-distribution evaluation | Another provider's model B writes 300 cases per scenario, with more Singapore, offline and metered-network cases and two intents in one message. |

## Compared Configurations

All configurations use the same test set and `kev.benchmark` code.

| Configuration | Definition |
|---|---|
| B0 | Released Kev `@v1.0`, short question instructions, zero-shot. |
| B0-policy | The same release, with full vendor policy text in question instructions; prompting only. |
| FT | Continue from the Kev release: rank-16 LoRA plus pointer head, 2 epochs, learning rate 2e-5, micro-batch 1 with accumulation 8, bf16, 1,000 replay records from Kev's original training set, followed by temperature fitting on the calibration split. |

Run once for each size: Kev-0.8B and Kev-4B.

## Metrics and Decision Rules

- Primary metric: test-question accuracy, accompanied by Brier, ECE and coverage at a 5% error budget.
- Improvement: the paired-bootstrap 95% interval lower bound for FT minus B0 must exceed 0, using `kev.compare`. An interval crossing 0 is inconclusive.
- Out-of-distribution results use the same rule and are reported separately; smaller gains must remain visible.
- General-task retention: compare transfer-v4 development accuracy with B0. A drop greater than 2 percentage points triggers the forgetting criterion.
- Training completion: save checkpoint and SHA-256, reload in a fresh process, compare before/after on the same tests, and return raw predictions and metrics locally.
- One seed-1 training run: do not generalize its gain as a stable multi-run effect.

## Recorded Deviations

These additions document execution changes; they do not rewrite the frozen protocol.

| Time in UTC | Deviation and reason | Effect and retained boundary |
|---|---|---|
| 2026-10-27 19:4x | Out-of-distribution files were not ready for the first 0.8B baseline, so `b0-ood_*` was skipped. G2 text was completed after training started. | Rerun the same pipeline after training to fill only the out-of-distribution baseline and comparison. Do not retrain. |
| 2026-10-27 19:50 | 4B uses micro-batch 4 with accumulation 2, versus 0.8B's 1 × 8, to improve H100 utilization for slower 4B forward passes. | Effective batch remains 8; other hyperparameters are unchanged. Cross-size accumulation differs, but each size retains its own FT-versus-B0 comparison. |
| 2026-10-27 19:57 | Of 300 G2 assistant cases, 13 fail generation as `bad json` because model B refuses the security-bypass/other-account requests. Two retry rounds fail. | 287 original cases produce 317 records including pairs. This missing refusal class is disclosed separately. |
| 2026-10-27 19:55 | Use `convert_hf_to_gguf.py` bundled with llama.cpp b11935 to recognize the Kev checkpoint, download pinned base weights, merge LoRA and write head temperature into GGUF. Quantization follows the ggml-org/convert Kev-4B recipe. | Device evaluation uses this experiment's fine-tuned weights. The converter first passes a released-0.8B smoke test: 14 seconds, 322 tensors. |
| 2026-10-27 20:24 | Add independent FT-cf branches for 0.8B and 4B after the first recipe, without sharing GPU concurrently. Keep training messages, change one policy field and recompute labels, adding 1,685 variants. Product line stays fixed because messages can name it. Use micro-batch 4 × accumulation 2. | Initial 0.8B FT scores 86.5%/93.5%, but both-correct paired cases are only 9.7%/13.6%. This discovery used original test pairs, so selection instead uses new `dev_cf_*` variants; `test_cf_*` and `ood_cf_*` evaluate held-out messages. Recommend FT-cf only if development-variant accuracy improves and original development accuracy drops by no more than 1 point. Report both branches regardless. |
| 2026-10-27 21:48 | The first 0.8B FT-cf CPU run overlaps a result-summary process and produces an 841 ms support median. Queued device tests are stopped and the same command is rerun on an idle laptop. The rerun replaces the first result. | Accuracy remains 86.9%/97.7%; rerun medians are 646/984 ms. 4B laptop tests are moved after the training host is shut down. This is a historical deviation, not an instruction to stop resources now. |
| 2026-10-27 22:22 | The project owner chooses option A: test only recommended 4B FT-cf, one Q8_0 and one Q4_K_M run on CPU with defaults. Each configuration occupies the laptop CPU for about 20 minutes. | No completed 4B FT device-agreement or latency result. FT-cf PyTorch references come from `runs/4b/ftcf-test_*/rows.json`. |
| 2026-10-27 22:45 | During 4B FT-cf Q8_0, the laptop enters Modern Standby at 22:45:02 and resumes at 04:11:00 UTC next day, supported by Kernel-Power events 506/507. Assistant record 139 therefore takes 5.4 hours; Q8_0 finishes at 04:12. The command did not inhibit standby. | Accuracy and answer agreement are unaffected. Assistant median is 4,115 ms including the request and 4,113 ms without it. Q4_K_M runs after resume, under different conditions, so the quantizations are not directly ranked by latency. |