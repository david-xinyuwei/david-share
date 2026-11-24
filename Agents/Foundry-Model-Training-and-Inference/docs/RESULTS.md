# Results: test setup, method and full tables

[中文](RESULTS_CN.md) · back to the [README](../README.md)

This page holds the setup, the method, the full tables and the limits behind the four results under [Results](../README.md#results) in the README. How each number was taken, and the commands that repeat the checks, are in [TESTING.md](TESTING.md).

## Test setup

Two tests in East US 2, each in its own Foundry account with its own target deployment: Qwen3.8-27B model version 3 with the LoRA template on Global managed compute, one instance with 2 × H100 80 GB. Both used the GSM8K sample of this repository (449 training rows, 50 validation rows) and LoRA rank 32.

- **First test, 22 and 23 November 2026: adapter A, Managed Training.** A supervised fine-tuning job with the default training settings and seed 42, submitted in the portal; its adapter is adapter A. The same data and settings were also submitted through the API; that job is timed under [Time and cost](../README.md#time-and-cost), and its adapter was not deployed. A second adapter, trained with the same settings on `Text-Bug-Detection`, another sample set of [`microsoft-foundry/fine-tuning`](https://github.com/microsoft-foundry/fine-tuning), was deployed on the same target deployment and was not compared. The comparison and the speed test below are those of adapter A.
- **Second test, 23 November 2026: adapter B, Programmed Training.** A training loop on the test client, in another account whose subscription has Programmed Training access.

## Adapter A: Managed Training, first test

**Question.** Does the adapter deployment's name reach a different model than the target deployment's name, and what does an adapter trained on 449 rows change?

<img src="../images/test-topology-en.png" width="900" alt="Test topology. Test client: a Windows laptop outside Azure with Python 3.13 and a Microsoft Entra token from Azure CLI; 4 requests at a time for the 50-row comparison, 1 streamed request at a time for the speed test. It calls the account endpoint of a Foundry account in East US 2 over HTTPS. The endpoint forwards to the target deployment: Qwen3.8-27B model version 3 with the LoRA template on Global managed compute, 1 instance with 2 H100 80 GB GPUs, serving the base model and the GSM8K adapter of LoRA rank 32. The region where the GPUs run was not established by these tests. All clocks are on the test client.">

**Method.** The input is the 50 rows of `chat_validation.jsonl`, the same pinned file that `up.py` uploads. Each row's system and user turns were sent unchanged, and the reference answer was held back. Every row went once to the base model (`model` = the target deployment's name) and once to the GSM8K adapter (`model` = the adapter deployment's name): 100 calls, 4 at a time, with `temperature` 0, `reasoning_effort` `"none"` and `max_tokens` 800. The `model` field was the only difference between the two sides. Answers were scored on the test client in two ways: automatically, by comparing the last number in the answer with the reference answer, and by reading every row that an automatic check marked wrong for either side (12 rows). The speed test sent the same prompt 3 times per side, one streamed request at a time, with reasoning left at its default and `max_tokens` 600.

| Measured on the 50 validation rows | Base model (target deployment's name) | Base model + GSM8K adapter (adapter deployment's name) |
|---|---|---|
| Rows answered with HTTP 200 | 50 of 50 | 50 of 50 |
| Answers identical to the other side's | 0 of 50 | 0 of 50 |
| Mean answer length, completion tokens | 310.2 | 158.7 |
| Answers cut off at the 800-token limit | 2 of 50 | 0 of 50 |
| Answers that contain the training data's `####` marker | 0 of 50 | 6 of 50 |
| Answers that end like the training data (`#### <number>!!!`) | 0 of 50 | 0 of 50 |
| Correct, automatic score (last number in the answer) | 39 of 50 | 45 of 50 |
| Correct, after reading the 12 flagged rows | 44 of 50 | 46 of 50 |

| Streaming speed: the same prompt 3 times per side, one request at a time | Base model | Base model + GSM8K adapter |
|---|---|---|
| Tokens per second after the first token (reasoning and answer tokens) | 72.5 / 72.1 / 72.6 | 53.4 / 53.4 / 53.4 |
| Seconds to the first streamed token (reasoning or answer) | 2.16 / 1.15 / 1.28 | 1.63 / 1.38 / 1.30 |

What the numbers mean:

- **The adapter is active.** No answer is identical between the two sides, the adapter's answers are about half as long (158.7 against 310.2 completion tokens), and only the adapter uses the `####` marker. The response's `model` field differs too: the base model reports `qwen--qwen3.8-27b`, the adapter an internal ID of the form `rp-<hash>-1`, not the deployment name.
- **Accuracy is not shown to differ.** After reading the flagged rows, the base model has 44 correct answers and the adapter 46. The adapter alone is correct on 3 rows and the base model alone on 1; a two-sided sign test on those 4 rows gives p = 0.625. The automatic score of 39 against 45 overstates the gap: it takes the last number in the text, and 5 correct base-model answers end with a sentence that contains another number, as in the row-7 example under [result 4](../README.md#result-4-the-adapter-changes-how-the-model-answers-not-how-often-it-is-right) in the README ("in 2 hours").
- **The format is learned in part.** The sample job takes 6 optimizer steps (449 rows, 2 epochs, batch size 128). The adapter picked up the short style, used the marker in 6 of 50 answers and never produced the complete ending.
- **The adapter costs speed.** On this prompt the same GPUs generated 53.4 tokens per second with the adapter against 72.5 for the base model, about 26% fewer. The first token arrived after 1.15 to 2.16 seconds on both sides.

Limits: one adapter, one training seed, 50 rows, one request per row, one target deployment, one client; the two sides were measured one after the other (base model first), not interleaved. The speed test is a single-user measurement, not a capacity test; its token counts include reasoning tokens, and one of the six answers consisted of reasoning only. Scoring details are in [`TESTING.md`](TESTING.md).

## Adapter B: Programmed Training, second test

**Question.** Does an adapter trained with Programmed Training deploy on Managed compute like one from a Managed Training job, and what changes in the answers when the same 449 rows train the adapter for 56 optimizer steps instead of 6?

<img src="../images/test-topology-pt-en.png" width="900" alt="Second test. Test client: a Windows laptop outside Azure with Python 3.13, the Foundry fine-tuning cookbook and a Microsoft Entra token from Azure CLI; it runs the training loop (449 rows, batch size 16, 2 epochs) and the 50-row comparison with 4 requests at a time. Over HTTPS it reaches a second Foundry account and project in East US 2, which hold the Programmed Training session for Qwen/Qwen3.8-27B, the saved checkpoint as a model in the project (LoRA rank 32, base model version 3) and the account endpoint. The endpoint forwards to the target deployment: Qwen3.8-27B model version 3 with the LoRA template on Global managed compute, 1 instance with 2 H100 80 GB GPUs, serving the base model and the Programmed Training adapter. In order: train (56 batches of 16 rows; validation loss 0.91 before and 0.41 after), save the final checkpoint, deploy (target deployment Succeeded after 21 minutes, first HTTP 200 after 553 more seconds; adapter deployment Succeeded after 78 seconds), compare (the 50 validation rows go to the base model, then to the adapter). The region where the GPUs run was not established by these tests.">

**Method.** The second test ran in another Foundry account in East US 2, in a subscription that has Programmed Training access. Training followed the supervised chat-data recipe of the Foundry fine-tuning cookbook ([`programmed_training/docs/custom-data.md`](https://github.com/microsoft-foundry/fine-tuning/blob/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training/docs/custom-data.md)). A Python loop on the test client read the same two pinned GSM8K files, rendered each row with the cookbook's renderer for this model (`qwen3_8_low_reasoning`) and sent the batches to a training session for `Qwen/Qwen3.8-27B`. That loop is published as [`training/programmed_training_sft.py`](../training/programmed_training_sft.py): the functions that prepare the data and run the session are the ones that ran here. Settings: LoRA rank 32, 2 epochs, batch size 16, a learning rate that starts at 0.0001 and falls linearly to zero, seed 42, loss on the assistant's answer only. Before the first step, after the first epoch and at the end, the loop computed the loss on the 50 validation rows without updating the adapter. It saved the final checkpoint, which the project then listed as a LoRA model (rank 32) on base-model version 3. The model's ID has the same form as the ID of a Managed Training adapter: `azureai://accounts/<account>/projects/<project>/models/<model name>/versions/1`.

Deployment used the two requests of step 3 in [How a request moves](../README.md#how-a-request-moves): a target deployment with the same template, model version and GPUs as in the first test, then one adapter deployment that names the saved model by that ID. In this test a separate script sent the two requests; `infra/up.py --deploy --adapter-model` sends the same two. The cookbook has a deployment script of its own, `scripts/deploy_to_foundry.py`, described in [`docs/deployment-and-inference.md`](https://github.com/microsoft-foundry/fine-tuning/blob/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training/docs/deployment-and-inference.md). At that commit its only target is `Fireworks`, a provisioned deployment that needs a separate preview access; it has no Managed compute target, and this test did not use it.

The comparison repeated the method of the [adapter A section](#adapter-a-managed-training-first-test) on the same 50 rows with the same request settings: 100 calls, 4 at a time, base model first. The automatic score marked 11 answers of the base model wrong: 8 of them were, character for character, answers already read in the first test and kept that reading, and the other 3 were read. It marked 7 answers of the adapter wrong; each ends with `#### <number>!!!`, so the number compared is the adapter's final answer.

| Training on the 449 rows for 2 epochs | Managed Training job (first test) | Programmed Training session (second test) |
|---|---|---|
| Batch size | 128, the service default | 16, set in the loop |
| Optimizer steps | 6 | 56 |
| Learning rate | starts at 0.0001, falls linearly to zero | starts at 0.0001, falls linearly to zero |
| Validation loss on the 50 validation rows, first value reported | 0.91 | 0.91 |
| Validation loss on the 50 validation rows, last value reported | 0.52 | 0.41 |
| Training tokens | 213,000 billed | 219,652 counted by the loop |
| Cost of those tokens at list price, USD | 0.64 | 0.90, an estimate |
| Duration | 5.3 minutes from created to finished | 6 minutes for the loop, 9 minutes from starting the script to its exit |

| Measured on the 50 validation rows | Base model (second test) | Base model + Programmed Training adapter (second test) | For comparison: base model + Managed Training adapter (first test, from the table above) |
|---|---|---|---|
| Rows answered with HTTP 200 | 50 of 50 | 50 of 50 | 50 of 50 |
| Answers identical to the base model's in the same test | not applicable | 0 of 50 | 0 of 50 |
| Mean answer length, completion tokens | 311.2 | 115.7 | 158.7 |
| Answers cut off at the 800-token limit | 2 of 50 | 0 of 50 | 0 of 50 |
| Answers that contain the training data's `####` marker | 0 of 50 | 50 of 50 | 6 of 50 |
| Answers that end like the training data (`#### <number>!!!`) | 0 of 50 | 50 of 50 | 0 of 50 |
| Correct, automatic score (last number in the answer) | 39 of 50 | 43 of 50 | 45 of 50 |
| Correct, after reading the flagged rows | 44 of 50 | 43 of 50 | 46 of 50 |

Row 7 with the answers of the base model and of both adapters is shown under [result 4](../README.md#result-4-the-adapter-changes-how-the-model-answers-not-how-often-it-is-right) in the README.

What the numbers mean:

- **The adapter deploys and is called like a Managed Training adapter.** The adapter deployment reached `Succeeded` in 78 seconds, and its first call returned HTTP 200. The response's `model` field again carried an internal ID of the form `rp-<hash>-1`.
- **This adapter reproduces the training format in every answer.** All 50 answers end with `#### <number>!!!`. The Managed Training adapter used the marker in 6 of 50 answers and never produced the complete ending. The answers average 115.7 completion tokens, a little over one third of the base model's 311.2.
- **Accuracy is not shown to differ.** The base model has 44 correct answers and the adapter 43. The adapter alone is correct on 2 rows and the base model alone on 3; a two-sided sign test on those 5 rows gives p = 1.0. The automatic score of 39 against 43 undercounts the base model for the reason given in the previous section: 5 of its correct answers end with a sentence that contains another number.
- **The validation loss fell further than in the sample job.** It went from 0.91 to 0.42 after the first epoch and to 0.41 after the second; the 6-step job ended at 0.52. Both start at 0.91, as the same base model on the same 50 rows should if the two services compute the loss in the same way; that was not checked beyond this agreement.
- **The difference between the two adapters is not a verdict on the two approaches.** The two runs share the data, the base model and its version, 2 epochs, LoRA rank 32 and the learning-rate schedule. They differ in batch size, 16 against 128, and so in optimizer steps, 56 against 6. What a Managed Training job does inside (optimizer settings, prompt rendering) is not visible from outside, and Managed Training with batch size 16 was not run.

Limits: one session, one seed, 50 rows, one request per row, base model first and not interleaved. The Managed Training adapter was measured on another target deployment in another account, not side by side with this one; at `temperature` 0 the base model's own answers differed between the two tests on 8 of 50 rows. The speed test was not repeated for this adapter. The cost figures of the second test are estimates from token counts and list prices; its bill was not read.
