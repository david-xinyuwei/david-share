# Qwen3.8-27B LoRA on Microsoft Foundry: Train the Adapter with Managed Training or Programmed Training, Serve It on Managed Compute

[![Model](https://img.shields.io/badge/model-Qwen3.8--27B%20(preview)-0078D4)](#purpose)
[![Training](https://img.shields.io/badge/training-Managed%20Training%20%2B%20Programmed%20Training%20%C2%B7%20SFT-0078D4)](#managed-training-and-programmed-training)
[![Serving](https://img.shields.io/badge/serving-Managed%20compute%20%C2%B7%20LoRA%20adapters%20(preview)-0078D4)](#results)
[![Deploy](https://img.shields.io/badge/deploy-Bicep%20%2B%20Python-0078D4)](#steps)
[![Offline tests](https://img.shields.io/badge/offline%20tests-29%20unittest-0078D4)](docs/TESTING.md)

Author: Xinyu Wei · [中文](README_CN.md)

> **Draft.** Two runs are still open. `infra/up.py`, `infra/verify.py` and `infra/down.py` have not been executed as one sequence in a new resource group. `training/programmed_training_sft.py` has run its local preparation only: its training functions are the ones that ran the session reported under Results, but this script has not started a session, and `infra/up.py --adapter-model` has not created a deployment. The example outputs under Steps are written from the scripts. This note is removed after those runs.

## Purpose

A team that wants an open-weight model to answer in its own format usually has to find GPUs twice: once to fine-tune the model and once to serve the result. This test checks whether Microsoft Foundry takes over both for **Qwen3.8-27B** (preview): train a LoRA adapter with **Managed Training** or **Programmed Training** (preview), then serve it on **Managed compute** and call it. Both training approaches were run on the same data to answer four questions:

1. Does Qwen3.8-27B deploy on Managed compute? On how many GPUs, and how soon can it answer?
2. Does each training approach produce an adapter, and does the training work?
3. Do the adapters attach to the same GPUs and answer under their own names?
4. What does an adapter change in the model's answers?

The answers are under [Results](#results). How the two training approaches differ, with prices, regions and the adapters each supports, is under [Managed Training and Programmed Training](#managed-training-and-programmed-training). To reproduce the test in your own subscription, follow the [Steps](#steps).

<img src="images/architecture-en.png" width="900" alt="Architecture as a flow from left to right; the numbers are the step numbers under Steps. 2 Your data: you provide chat examples in JSONL, for example the GSM8K sample, and infra/up.py uploads them to Microsoft Foundry. 3 Train, in one of two ways: A, Managed Training, where you submit a job in the Foundry portal and Foundry runs the whole job; B, Programmed Training (preview), where the Python loop programmed_training_sft.py sends each step. Microsoft provides the training GPUs and bills per training token. Either way the output is a LoRA adapter listed in the project. 4 Deploy on Managed compute with infra/up.py --deploy: the target deployment runs the base model Qwen3.8-27B on one instance with 2 H100 80 GB GPUs, and adapter deployments, up to 8, attach to the same GPUs without adding a GPU; billing is per GPU-hour while the target exists, 15.82 USD per hour at list price. 6 Your app sends requests to one endpoint, and the model field picks the base model or an adapter; examples/chat.py is a minimal client. 7 infra/down.py deletes the adapter deployments, then the target deployment, and the GPU charge stops.">

What the figure shows: the whole path, with the number in each circle being the step number under [Steps](#steps). Step 2 uploads your training data. In step 3, Managed Training or Programmed Training trains a LoRA adapter on GPUs that Microsoft provides and bills per training token. In step 4, `infra/up.py --deploy` deploys the base model Qwen3.8-27B on Managed compute, one instance with 2 × H100 80 GB, and attaches each adapter to the same GPUs, up to 8, without adding a GPU. In step 6, your application picks the base model or an adapter with the `model` field. Step 7 removes the deployments, and the GPU charge stops. It is an original explanatory diagram.

Three things to know before you start: fine-tuning Qwen3.8-27B and [LoRA adapters on Managed compute](https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-lora-managed-compute) are preview features, with no service-level agreement, and Microsoft does not recommend them for production workloads; Managed compute [has no built-in content filtering](https://learn.microsoft.com/en-us/azure/foundry/concepts/managed-compute-overview); and the target deployment is billed per GPU-hour from creation until you delete it, with or without requests.

## Results

Four results, in the order of the work:

1. [Qwen3.8-27B deploys on Managed compute](#result-1-qwen38-27b-deploys-on-managed-compute): one instance with 2 × H100 80 GB, `Succeeded` 21 minutes after the request.
2. [Both training approaches produce an adapter, and the loss falls](#result-2-both-training-approaches-produce-an-adapter-and-the-loss-falls): the validation loss goes from 0.91 to 0.52 with Managed Training and from 0.91 to 0.41 with Programmed Training.
3. [The adapters deploy on the same GPUs](#result-3-the-adapters-deploy-on-the-same-gpus): 64 seconds per adapter deployment in the first test and 78 in the second, with no GPU added.
4. [The adapter changes how the model answers, not how often it is right](#result-4-the-adapter-changes-how-the-model-answers-not-how-often-it-is-right): shorter answers in the format of the training data; the difference in correct answers is within noise.

Where they come from: two tests in East US 2 on 22 and 23 November 2026, each in its own Foundry account, both on the GSM8K sample data of this repository. Adapter A was trained with Managed Training in the first test, adapter B with Programmed Training in the second. Test setup, method, full tables and limits: [`docs/RESULTS.md`](docs/RESULTS.md).

### Result 1: Qwen3.8-27B deploys on Managed compute

<table>
<tr>
<td width="50%"><img src="images/portal-target-succeeded.png" alt="Foundry portal, Models, Deployments, Managed-compute tab: one deployment of qwen--qwen3.8-27b with status Succeeded, deployment type Global Managed Compute, compute H100_80GB."></td>
<td width="50%"><img src="images/portal-playground.png" alt="Foundry portal, Playground of the target deployment: the question about Tom's apples and the answer 8."></td>
</tr>
<tr>
<td>Deployments page, Managed compute tab: the base model <code>qwen--qwen3.8-27b</code>, status Succeeded, Global Managed Compute, H100_80GB.</td>
<td>Playground of the same deployment: the base model answers a test question.</td>
</tr>
</table>

The base model is the open-weight Qwen3.8-27B from the Foundry model catalog, as published, with no training. `infra/up.py --deploy` creates its deployment with the LoRA-enabled template on one instance with 2 × H100 80 GB; this is the target deployment that adapters attach to. It reached `Succeeded` 21 minutes after the request, and the first call, 8 seconds later, returned HTTP 200; in the second test that first successful call came after 553 seconds (see [Time and cost](#time-and-cost)). The target deployment holds the GPUs and is the only item billed per hour: 15.82 USD at list price, with or without requests.

### Result 2: both training approaches produce an adapter, and the loss falls

<img src="images/training-loss-en.png" width="900" alt="Line chart in two panels with the same loss axis from 0.2 to 1.0; lower is better. Left, A, the Managed Training job of the first test, batch size 128, 6 optimizer steps: the training loss falls from 0.85 to 0.48; the validation loss on the 50 validation rows is 0.91 at step 1, 0.62 at step 3, the end of epoch 1, and 0.52 at step 6. Right, B, the Programmed Training session of the second test, batch size 16, 56 optimizer steps: the training loss falls from 0.90 and then moves from step to step; the validation loss is 0.91 before training, 0.42 after epoch 1 at step 28 and 0.41 after step 56.">

| Training on the 449 rows of the GSM8K sample, 2 epochs, LoRA rank 32 | Adapter A: Managed Training (first test) | Adapter B: Programmed Training (second test) |
|---|---|---|
| How you run it | submit a supervised fine-tuning job on the portal's Training page; Foundry runs the whole job ([step 3, option A](#3-train-the-adapter)) | run `training/programmed_training_sft.py`; your Python loop sends each step and Foundry executes it on its GPUs ([step 3, option B](#3-train-the-adapter)) |
| Batch size and optimizer steps | 128, the service default; 6 steps | 16, set in the loop; 56 steps |
| Validation loss on the 50 validation rows, first → last value reported | 0.91 → 0.52 | 0.91 → 0.42 after epoch 1 → 0.41 |
| Training tokens and their cost at list price | 213,000 billed, 0.64 USD | 219,652 counted by the loop, about 0.90 USD |
| Duration | 5.3 minutes from created to finished | 9 minutes from starting the script to its exit |
| Output | a LoRA adapter listed as a model in the project, deployed as adapter A | the same, deployed as adapter B |

What to look at:

- **The validation loss falls in both runs.** It is computed on the 50 validation rows, which neither run trains on: after training, the adapter predicts the reference answers of questions it has not seen better than the base model does. That is the evidence that training worked; what it changes in actual answers is [result 4](#result-4-the-adapter-changes-how-the-model-answers-not-how-often-it-is-right).
- **Both start at 0.91.** The same base model on the same 50 rows gives the same starting value in both services; that the two services compute the loss in the same way was not checked beyond this agreement.
- **B goes lower because it takes more steps; that does not make the approach better.** The two runs share the data, the base model, 2 epochs, LoRA rank 32 and the learning-rate schedule. They differ in batch size, 16 against 128, and so in optimizer steps, 56 against 6. Managed Training with batch size 16 was not run.
- **The training loss** (blue) is the loss on the batch that each step trains on. B's batches hold 16 rows, so it moves from step to step; the validation loss (orange) is the measure to compare.

### Result 3: the adapters deploy on the same GPUs

<img src="images/portal-two-adapters.png" width="700" alt="Foundry portal, Models, Deployments, Adapter deployments tab: two adapter deployments, both with deployment status Succeeded, both with the same target deployment of type Managed compute.">

Adapter deployments tab, first test: two adapter deployments on the same target deployment, both Succeeded.

Each adapter deployment names a trained adapter and the target deployment of result 1. In the first test each one reached `Succeeded` 64 seconds after the request; adapter B reached it in 78 seconds in the second test. An adapter deployment adds no GPU and is [not priced separately](https://learn.microsoft.com/en-us/azure/foundry/concepts/adapter-deployment-overview); one target deployment takes up to 8. Your application then picks the base model or an adapter with the `model` field of the same endpoint.

The screenshot is from the first test, so both adapters in it were trained with Managed Training: adapter A on the GSM8K sample, and a second adapter trained with the same settings on `Text-Bug-Detection`, another sample set of [`microsoft-foundry/fine-tuning`](https://github.com/microsoft-foundry/fine-tuning), deployed on the same target deployment. Only adapter A was compared with the base model.

The screenshots of results 1 and 3 are real portal screenshots, cropped; the subscription name and the values of the Created by column are covered. The deployment names in them belong to the test deployment. Yours are `qwen38-lora` and `qwen38-lora-<display name>` unless you pass `--target`. Where the sample data, the icons and the screenshots come from: [`NOTICE.md`](NOTICE.md).

### Result 4: the adapter changes how the model answers, not how often it is right

The same question went to the base model and to each adapter; only the `model` field of the request differed. It is row 7 of the validation file, sent with the row's system turn (`Reply user's question as accurately as possible.`):

> Fiona completed 36 math questions in an hour. Shirley was able to complete twice as many math questions within that same time, and Kiana completed half of the sum of Fiona and Shirley's math questions. If they each did the same number of questions the following hour, how many math questions did all three girls complete in 2 hours?

| Row 7, answered by | Base model Qwen3.8-27B | Adapter A, Managed Training | Adapter B, Programmed Training |
|---|---|---|---|
| Answer | 324, correct | 324, correct | 324, correct |
| Length, completion tokens | 385 | 65 | 149 |
| Last line | a sentence that states 324 | `The answer is: 324`, after `#### 324` | `#### 324!!!`, as in every training answer |

**Base model**, beginning and end of its answer:

```text
Here is the step-by-step solution:

**Step 1: Calculate the number of questions each girl completed in the first hour.**

*   **Fiona:** Completed 36 questions.
*   **Shirley:** Completed twice as many as Fiona.
    $$36 \times 2 = 72 \text{ questions}$$
[...]
**Answer:**
All three girls completed **324** math questions in 2 hours.
```

**Adapter A**, complete answer:

```text
36*2=72
72+36=108
108/2=54
54+72+36=162
162*2=324
#### 324
The answer is: 324
```

**Adapter B**, complete answer:

```text
Shirley completed 36*2=<<36*2=72>>72 math questions.
Fiona and Shirley completed 36+72=<<36+72=108>>108 math questions.
Kiana completed 108/2=<<108/2=54>>54 math questions.
All three girls completed 108+54=<<108+54=162>>162 math questions.
In 2 hours, they completed 162*2=<<162*2=324>>324 math questions.
#### 324!!!
```

On all 50 validation rows, with `temperature` 0 and each row sent once to each side:

| On the 50 validation rows | Base model, first test | Adapter A | Base model, second test | Adapter B |
|---|---|---|---|---|
| Mean answer length, completion tokens | 310.2 | 158.7 | 311.2 | 115.7 |
| Answers that end like the training data (`#### <number>!!!`) | 0 of 50 | 0 of 50 | 0 of 50 | 50 of 50 |
| Answers that contain the training data's `####` marker | 0 of 50 | 6 of 50 | 0 of 50 | 50 of 50 |
| Answers cut off at the 800-token limit | 2 of 50 | 0 of 50 | 2 of 50 | 0 of 50 |
| Correct, after reading every answer that the automatic score marked wrong | 44 of 50 | 46 of 50 | 44 of 50 | 43 of 50 |

What the numbers mean:

- **Both adapters are active.** On none of the 50 rows did an adapter give the same answer as the base model in the same test, and only the adapters use the training data's marker.
- **More optimizer steps, more of the training format.** Adapter A (6 steps) took on the short style, but used the marker in 6 of 50 answers and never the complete ending. Adapter B (56 steps) ends all 50 answers like the training data; its answers average 115.7 completion tokens, a little over one third of the base model's 311.2.
- **Accuracy is not shown to differ.** Adapter A alone is correct on 3 rows and its base model alone on 1 (two-sided sign test, p = 0.625); for adapter B the counts are 2 and 3 (p = 1.0). The GSM8K sample teaches an answer format; this page does not show that fine-tuning makes the model better at arithmetic.
- **The adapter costs speed.** With adapter A the same GPUs streamed 53.4 tokens per second against 72.5 for the base model, about 26% fewer (one prompt, 3 runs per side). The speed test was not repeated for adapter B.

Limits: one adapter per approach, one seed, 50 rows, one request per row, base model first and not interleaved. The two adapters were measured on different target deployments in different accounts; at `temperature` 0 the base model's own answers differed between the two tests on 8 of 50 rows. Method, scoring and full tables: [`docs/RESULTS.md`](docs/RESULTS.md).

### Time and cost

| Stage | Measured in the first test |
|---|---|
| Training job on the sample data, submitted in the portal | 5.3 minutes from created to finished |
| The same data and settings, submitted through the API | 9.0 minutes from created to finished; its 6 training steps took 77 seconds, the rest was queueing and preprocessing |
| Target deployment, from the request to `Succeeded` | 21 minutes |
| First successful call after `Succeeded` | 8 seconds |
| Each adapter deployment, from the request to `Succeeded` | 64 seconds (2 measured) |
| Deleting 2 adapter deployments and the target deployment | 5 minutes |
| Requests sent to the deployment while it existed | 164, all answered with HTTP 200 |

The second test, with the Programmed Training adapter, differed in one stage that matters when you deploy: the first successful call came 553 seconds after `Succeeded`, not 8 seconds. `up.py` keeps calling for 10 minutes before it stops.

| Stage in the second test | Measured |
|---|---|
| Programmed Training session on the sample data | 6 minutes for the loop's 56 steps; 9 minutes from starting the script to its exit |
| Target deployment, from the request to `Succeeded` | 21 minutes |
| First successful call after `Succeeded` | 553 seconds, about 9 minutes; the 25 calls before it returned HTTP 404 |
| The adapter deployment, from the request to `Succeeded` | 78 seconds |
| Deleting the adapter deployment and the target deployment | 5 minutes |
| Requests sent to the deployment while it existed | 127: 102 answered with HTTP 200, and 25 with HTTP 404 before the first success |

Cost: one hour of serving plus one Managed Training job comes to 16.46 USD at list price; every list price is under [Price and regions](#price-and-regions). `up.py` reads the current list price before it creates anything and prints it.

## Managed Training and Programmed Training

The two training approaches differ first in who runs the training loop. With **Managed Training** you submit data and settings, and Foundry runs the whole training job. With **Programmed Training** (preview) the loop runs on your own machine: your Python code decides how each step samples and updates the weights, and Foundry executes those operations on its GPUs. Neither approach needs a training GPU of yours, both produce a LoRA adapter, and the adapters deploy and are billed the same way. [Step 3](#3-train-the-adapter) offers both: option A submits a Managed Training job in the portal, and option B runs `training/programmed_training_sft.py`.

<img src="images/learn-training-approaches.png" width="684" alt="Table from Microsoft Learn with the columns Managed Training and Programmed Training (preview) and the rows How it works, Best for, Your control, Training methods and Example use cases. Managed Training: submit data and settings; Foundry runs the training job. Programmed Training: write a Python loop; Foundry executes training and sampling operations.">

Source: Microsoft Learn, [Training in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/overview#choose-your-training-approach), section "Choose your training approach". This is a screenshot of the table as the page showed it on 23 November 2026 (page last updated 17 November 2026).

### Price and regions

The table covers Qwen3.8-27B (preview) only. Methods, training types and regions come from that Microsoft Learn article, checked again on 24 November 2026 with no change; list prices come from the Azure Retail Prices API, read on 24 November 2026, in USD.

| Aspect, for Qwen3.8-27B (preview) | Managed Training | Programmed Training (preview) |
|---|---|---|
| Training methods | SFT and RFT. This repository uses SFT | no predefined method, you write the loop; the [samples repository](https://github.com/microsoft-foundry/fine-tuning/tree/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training) has recipes for SFT, reinforcement learning, preference learning, distillation and custom losses. This repository uses SFT |
| Access | no request needed | your subscription needs an [access approval](https://aka.ms/foundry-interactive-training-signup) before a session can start |
| Training type | Global or Developer. Global uses Microsoft's global capacity and does not guarantee data residency; Developer uses spare capacity, costs less, and a job can be preempted and resumed. This repository uses Global | Global only for now: the samples repository's [training.md](https://github.com/microsoft-foundry/fine-tuning/blob/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training/docs/training.md#training-type) lists `GlobalStandard` as available and `DatazoneStandard` and `DeveloperTier` as unavailable |
| Regions for the Foundry project | 10: Australia East, East US, East US 2, Korea Central, North Central US, Sweden Central, Switzerland North, UAE North, UK South, West US 3 | 11: the 10 on the left and Canada East |
| How it is billed | SFT per training token times the number of epochs; RFT per hour of training, with the grader model's tokens on top | four token categories, each at its own price: training, sampling, prefill and cached prefill |
| List price | SFT: 3.00 per million training tokens on Global, 1.50 on Developer. RFT: 80 per training hour on Global | Global, per million tokens: training 4.10, sampling 5.60, prefill 1.86, cached prefill 0.37 |
| Training cost of this repository's sample data (449 rows, 2 epochs) | 213,000 training tokens billed, 0.64, from the bill | 219,652 training tokens counted by the loop, about 0.90 at list price; the bill of the second test was not read |
| Deployment and inference | Managed compute only, no Serverless. This repository's target deployment runs on 2 × H100 80 GB with the Global deployment scope, at 7.91 per GPU-hour, 15.82 per hour; adapter deployments are not priced separately; requests are not priced per token | the same |

Apart from training and the target deployment, the test resource group's bill showed no other charge: the account, the project and the uploaded files have no hourly price. The rest of the article, with all 18 models, the 27 regions and the serverless deployment types, is summarized in [`docs/FOUNDRY_TRAINING.md`](docs/FOUNDRY_TRAINING.md).

### Which adapters can be deployed

| Where the adapter comes from | Can it be deployed on Managed compute | Source |
|---|---|---|
| a LoRA adapter trained by a Managed Training job in the same project | yes; adapter A of this repository, rank 32 | this repository's test, [result 3](#result-3-the-adapters-deploy-on-the-same-gpus) |
| a LoRA checkpoint saved by a Programmed Training session in the same project | yes; adapter B of this repository, rank 32 | this repository's test, [result 3](#result-3-the-adapters-deploy-on-the-same-gpus) |
| a LoRA adapter trained outside Foundry, for example on your own GPUs | not yet: Foundry cannot import an adapter trained elsewhere. At Ignite 2026 the product team said it plans to open the import of your own LoRA adapters very soon; no date was given | Microsoft Learn, [Adapter deployment overview](https://learn.microsoft.com/en-us/azure/foundry/concepts/adapter-deployment-overview): "You can't yet import your own adapters"; Q&A of the Ignite 2026 session [BRK246](https://ignite.microsoft.com/en-US/sessions/BRK246) |
| full model weights, not an adapter | not through an adapter deployment. BRK246 showed full weights in safetensors format being imported and deployed the same way as catalog models; the product team also said it plans to support merging an adapter into the base model. This repository tested neither | Ignite 2026 session [BRK246](https://ignite.microsoft.com/en-US/sessions/BRK246) |

An adapter that can be deployed must also match the base model and version it was trained on, run on a target deployment with a LoRA-enabled template, and fit the template's limits on adapter count, LoRA rank and memory; one target deployment takes up to 8 adapter deployments ([Deploy fine-tuned LoRA adapters to managed compute](https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-lora-managed-compute)).

## Steps

These steps reproduce the test above in your own subscription.

| Order | Where | What | Command | Takes about |
|---|---|---|---|---|
| 1 | your machine | get the code and sign in | `git clone`, `az login` | 2 minutes |
| 2 | your machine | create the Foundry resources and upload the sample data; no GPU | `python infra/up.py --resource-group <name> --location eastus2` | 5 minutes |
| 3 | Foundry portal, or your machine | train the adapter: A, Managed Training in the portal, or B, Programmed Training from a script | A: Training, then Train. B: `<cookbook python> training/programmed_training_sft.py --resource-group <name>` | A: 5 to 10 minutes. B: 9 minutes, after a one-time install |
| 4 | your machine | deploy the target and the adapter; the GPU charge starts | `python infra/up.py --resource-group <name> --deploy`; after 3B, add `--adapter-model <model name>=gsm8k-pt` | 25 to 35 minutes |
| 5 | your machine | check it | `python infra/verify.py --resource-group <name>` | 1 minute, or 5 minutes with `--full` |
| 6 | your machine | call it | `python examples/chat.py <chat URL> <deployment> "<question>"` | seconds |
| 7 | your machine | remove it; the GPU charge stops | `python infra/down.py --resource-group <name>` | 5 minutes |

In every command, replace `<name>` with the name of your resource group. `<cookbook python>` is the Python of the environment that option B of step 3 installs.

Prerequisites:

- **Roles.** Step 2 creates resources and a role assignment, which needs Owner, or Contributor together with Role Based Access Control Administrator, on the subscription or the resource group. It gives you Foundry User on the account, which the scripts need for files, jobs and model calls. Tested as Owner of the subscription.
- **Quota.** 2 GPUs of Global managed compute quota for `H100_80GB` in the subscription. Step 2 prints how many are used and how many you have. To get more, see [Request more quota](https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-models-managed#request-more-quota).
- **Region.** A region where [Global Managed Training lists Qwen3.8-27B](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/overview): Australia East, East US, East US 2, Korea Central, North Central US, Sweden Central, Switzerland North, UAE North, UK South or West US 3. The deployment was tested in East US 2 only.
- **Tools.** Python and the Azure CLI. Apart from option B of step 3, no Python package is installed. Tested with Python 3.13.15, Azure CLI 2.93.0 and Bicep CLI 0.49.2 (the Azure CLI installs Bicep on first use) on Windows 11. Linux and macOS were not tested.
- **Only for option B of step 3 (Programmed Training).** An [access approval](https://aka.ms/foundry-interactive-training-signup) for your subscription: request it through the preview sign-up form and wait for it before you start a session. A second Python environment that holds the [Programmed Training cookbook](https://github.com/microsoft-foundry/fine-tuning/tree/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training); the cookbook asks for Python 3.11 or newer, Git, and access to PyPI and Hugging Face. Tested with Python 3.13.15, as Owner of the subscription with the Foundry User and Azure AI Developer roles on the account. Whether Foundry User alone is enough to start a session was not tested.

### 1. Get the code and sign in

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Agents/Foundry-Model-Training-and-Inference
cd Agents/Foundry-Model-Training-and-Inference

az login
az account set --subscription "<subscription name or ID>"
python -m unittest discover -s tests
```

The last command runs the offline tests. It needs no Azure access and ends with:

```text
Ran 29 tests in <n>s

OK
```

### 2. Create the Foundry resources (no GPU)

```powershell
python infra/up.py --resource-group <name> --location eastus2
```

You will see lines like these. Values in angle brackets differ for each deployment:

```text
<time> [PASS] 1/7 Preflight: subscription <your subscription>; region eastus2; Global H100_80GB quota: <used> used of <limit> GPUs (the target needs 2); target list price 15.82 USD per hour (2 x 7.91)
<time> deploying infra/main.bicep into resource group <name> (eastus2) ...
<time> waiting for the Foundry User role to take effect (project API answered HTTP <code>) ...
<time> [PASS] 2/7 Azure resources (infra/main.bicep): account ftlora-<hash>, project lora-demo, endpoint https://ftlora-<hash>.services.ai.azure.com
<time> [PASS] 3/7 Sample data: gsm8k-train.jsonl 449 rows (file-<id>); gsm8k-validation.jsonl 50 rows (file-<id>)
<time> [INFO] 4/7 Trained adapter: no registered LoRA adapter: no training job yet

NEXT: train the adapter on the portal's Training page (about 5 to 10 minutes; list price about 0.64 USD).
  [six numbered portal steps, the same as in step 3 below]
Then run:  python infra/up.py --resource-group <name> --deploy
Or train it with Programmed Training (preview): training/programmed_training_sft.py, step 3 of the README.

RESULT: PASS   receipt: <home>/.foundry-lora/<name>/up-receipt.json
```

The line about the Foundry User role can repeat for a few minutes: a new role assignment needs time before the project accepts your token. Nothing created in this step has an hourly price.

| Created | Name | Notes |
|---|---|---|
| Resource group | `<name>` | created when it does not exist, with the tag `solution=foundry-managed-training-lora` |
| Foundry account | `ftlora-<hash>` | kind `AIServices`, key authentication disabled; the name is also the endpoint's subdomain |
| Foundry project | `lora-demo` | holds the files, the training jobs and the registered adapters |
| Role assignment | Foundry User for you, on the account | pass `--principal-id` and `--principal-type` to give it to another identity |
| Two uploaded files | `gsm8k-train.jsonl`, `gsm8k-validation.jsonl` | 449 and 50 rows, checked against a pinned SHA-256 |

The scripts keep their state outside the repository, in `<home>/.foundry-lora/<name>/`: `up-receipt.json`, `verify-report.json`, `down-receipt.json`, `run.log`, `state.json` and the downloaded sample files. Running the command again continues from what exists and changes nothing that is already in place.

| Parameter of `up.py` | Default | Meaning |
|---|---|---|
| `--resource-group` | required | the resource group to create or reuse |
| `--location` | `eastus2` | region of a new deployment; ignored once the resource group holds one |
| `--subscription` | the Azure CLI's current subscription | subscription name or ID |
| `--account-name` | `ftlora-<hash>` | Foundry account name; must be globally unique |
| `--project-name` | `lora-demo` | Foundry project name |
| `--target` | `qwen38-lora` | name of the target deployment; adapter deployments are named `<target>-<display name>` |
| `--deploy` | off | create the target and adapter deployments (step 4) |
| `--adapter-model NAME[=LABEL]` | none | also deploy this LoRA model of the project, such as the adapter that option B of step 3 saves; `LABEL` ends the adapter deployment's name; the option can be repeated |
| `--wait-training MINUTES` | 0 | keep checking for a registered adapter for this long |
| `--train-api` | off | submit the training job through the API (see step 3) |
| `--principal-id`, `--principal-type` | you | the identity that receives Foundry User |
| `--ignore-recent-teardown` | off | skip the waiting period after `down.py` (see step 4) |

### 3. Train the adapter

Choose one option, or do both: one target deployment serves up to 8 adapters.

| What differs | A. Managed Training, in the portal | B. Programmed Training (preview), from a script |
|---|---|---|
| Where the training runs | a job that Foundry runs from start to end on GPUs that Microsoft allocates | a loop on your machine; Foundry executes each step the loop sends, on GPUs that Microsoft operates |
| What you set | the data and the settings that the wizard offers | every step: the script sets batch size 16, 2 epochs, the learning rate and when to validate |
| What it needs beyond step 2 | nothing | the access approval and the cookbook's Python environment, see Prerequisites |
| What to expect for the sample data, as measured under [result 2](#result-2-both-training-approaches-produce-an-adapter-and-the-loss-falls) | 6 optimizer steps; 213,000 training tokens, 0.64 USD at list price; 5.3 minutes | 56 optimizer steps; 219,652 training tokens, about 0.90 USD at list price; 9 minutes |
| How step 4 finds the adapter | through its training job | by the model name that you pass with `--adapter-model` |

#### A. Managed Training, in the portal

1. Open [https://ai.azure.com](https://ai.azure.com), switch on **New Foundry** in the header and select the project `lora-demo`.
2. In the left menu select **Training**, then **Train**. The wizard **Train a model** opens.
3. **Basic details:** make sure **Supervised**, **qwen3.8-27b** and **Global** are selected. Select **Next**.
4. **Datasets:** set **Training data source** to `gsm8k-train.jsonl` and **Validation data source (optional)** to `gsm8k-validation.jsonl`. Select **Next**.
5. **Optional settings:** type `gsm8k` into **Enter a display name**. The numbers on this page were trained with seed `42`; enter it in the seed field to use the same seed. Leave **Number of epochs** and **Learning rate multiplier** on Default. Select **Submit**.
6. Wait until the job has finished. On the **Models** page, the **Models** tab then lists the adapter.

The display name becomes the end of the adapter deployment's name: `gsm8k` gives `qwen38-lora-gsm8k`. To check from your machine, run the command of step 2 again. Step 4 of its output changes to:

```text
<time> [PASS] 4/7 Trained adapter: qwen38-lora-gsm8k <- model_<id>-final/versions/1
```

Why the portal: in our tests a job submitted through the API finished as succeeded but did not register its adapter when the project had never run a job submitted in the portal (3 of 3 jobs, in two regions), so there was nothing to deploy. Jobs submitted in the portal registered their adapter (2 of 2), and so did API jobs submitted later in the same project (3 of 3). The cause is not known. `up.py --train-api` submits the job through the API for that later case; when a job succeeds without a registered adapter, `up.py` says so and starts no GPU.

#### B. Programmed Training, from a script

Install the Programmed Training cookbook once, in a folder outside this repository. The commands are those of its [quickstart](https://github.com/microsoft-foundry/fine-tuning/blob/0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9/programmed_training/docs/quickstart.md), at the commit this script was written against:

```powershell
git clone https://github.com/microsoft-foundry/fine-tuning.git
cd fine-tuning
git checkout 0b8bcfe9519ed382a5bc202f0f1b2ce65c22a2c9
cd programmed_training
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e . --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu
```

These commands and the next ones are written for PowerShell on Windows; on Linux or macOS the environment's Python is `.venv/bin/python` instead of `.venv\Scripts\python.exe`. Go back to this repository's folder and put the path of that environment's Python into `$py`. Then run the local preparation. It downloads the model's tokenizer from Hugging Face, renders every row and prints the plan. It does not sign in to Azure and starts no session:

```powershell
$py = "<cookbook folder>\programmed_training\.venv\Scripts\python.exe"
& $py training/programmed_training_sft.py --resource-group <name> --prepare
```

```text
<time> [PASS] 1/5 Sample data: gsm8k-train.jsonl 449 rows; gsm8k-validation.jsonl 50 rows; pinned SHA-256 checked
<time> [PASS] 2/5 Local preparation: 28 batches x 16 rows = 448 of 449 rows per epoch, 2 epochs, 56 optimizer steps; about 219768 training tokens, at the list price of 4.10 USD per million training tokens about 0.90 USD; validation: 50 rows, 12014 tokens per pass; longest row 592 tokens

RESULT: PASS   receipt: <home>/.foundry-lora/<name>/train-receipt.json

Nothing was sent to Azure. To train, run the same command without --prepare (billed per training token).
```

For the sample data the plan is always this one. Now train. The command opens one session, which is billed per training token until the script closes it:

```powershell
& $py training/programmed_training_sft.py --resource-group <name>
```

```text
<time> [PASS] 3/5 Project: account ftlora-<hash>, project lora-demo, endpoint https://ftlora-<hash>.services.ai.azure.com/api/projects/lora-demo
<time> starting ONE Programmed Training session on Qwen/Qwen3.8-27B (LoRA rank 32); billed per training token until the session is closed
Session ready: session_id=session_<id>
[progress lines of the cookbook's training loop]
Session closed: session_id=session_<id>
<time> [PASS] 4/5 Training session: session_<id>: 56 of 56 optimizer steps, <n> training tokens; training loss <n> -> <n>; validation loss <n> -> <n>; session closed; run folder <run folder>
<time> [PASS] 5/5 Saved adapter: model_<id>-final (LoRA rank 32) on qwen--qwen3.8-27b/versions/<version>

RESULT: PASS   receipt: <home>/.foundry-lora/<name>/train-receipt.json

Adapter : model_<id>-final  (a LoRA model of project lora-demo)
Deploy  : python infra/up.py --resource-group <name> --deploy --adapter-model model_<id>-final=gsm8k-pt
```

What success looks like: `56 of 56 optimizer steps`, a validation loss that falls (from 0.91 to 0.41 in our session), and the saved model's name in the last two lines. The session saves a checkpoint after each epoch; the project lists both as LoRA models, and step 5/5 names the final one. Copy the `Deploy` line: it is the command of step 4.

The loop is yours to change. Its settings are the `SETTINGS` constants at the top of the script, and `--prepare` shows the plan and the list price of a new setting before you pay for a session. A session is not resumed: running the command again starts a new session, which is billed again.

### 4. Deploy the target and the adapter (the GPU charge starts)

```powershell
python infra/up.py --resource-group <name> --deploy
```

```text
<time> [PASS] 4/7 Trained adapter: qwen38-lora-gsm8k <- model_<id>-final/versions/1
<time> creating target deployment qwen38-lora: 2 x H100_80GB, 15.82 USD per hour at list price, until you run down.py
<time> target deployment qwen38-lora: Creating (<n> min)
<time> target deployment qwen38-lora: Succeeded (<n> min)
<time> [PASS] 5/7 Target deployment: qwen38-lora: base qwen--qwen3.8-27b/versions/<version>, 2 x H100_80GB, Succeeded
<time> adapter deployment qwen38-lora-gsm8k: Succeeded (<n> s)
<time> [PASS] 6/7 Adapter deployments: 1 on qwen38-lora: qwen38-lora-gsm8k
<time> [PASS] 7/7 First calls: qwen38-lora -> '8' (served model qwen--qwen3.8-27b, <n> s); qwen38-lora-gsm8k -> '<answer>' (served model rp-<hash>-1, <n> s)

RESULT: PASS   receipt: <home>/.foundry-lora/<name>/up-receipt.json

Endpoint : https://ftlora-<hash>.services.ai.azure.com/openai/v1/chat/completions
Models   : "qwen38-lora" (base model) and "qwen38-lora-gsm8k" (base model + adapter)
Charge   : 15.82 USD per hour at list price for as long as "qwen38-lora" exists. Adapter deployments add nothing.
Check    : python infra/verify.py --resource-group <name>
Stop     : python infra/down.py --resource-group <name>
```

Steps 1/7 to 3/7 repeat first and change nothing. The command starts no GPU when no adapter is registered, when fewer than 2 GPUs of quota are free, or when `down.py` removed this resource group's target deployment less than 60 minutes earlier. That waiting period is a precaution, not a measured threshold: in our tests two target deployments created 23 and 33 seconds after a deletion reached `Succeeded` and then returned HTTP 404 to model calls, and one created 8 hours after a deletion worked. `--ignore-recent-teardown` skips the wait. While the target is new, step 7/7 can print `first call to qwen38-lora: HTTP 404; retrying in 30 s` for several minutes before the first answer: 8 seconds passed in one of our tests and 553 seconds in the other.

After option B, add the model's name. The training script printed the complete command in its `Deploy` line:

```powershell
python infra/up.py --resource-group <name> --deploy --adapter-model model_<id>-final=gsm8k-pt
```

```text
<time> [PASS] 4/7 Trained adapter: qwen38-lora-gsm8k-pt <- model_<id>-final/versions/1
```

The other lines are the ones shown above, with `qwen38-lora-gsm8k-pt` as the adapter deployment's name; `gsm8k-pt` is a label of your choice. If you trained with both options, this one command deploys both adapters on the same target deployment.

Every adapter that a Managed Training job registered and every model named with `--adapter-model` is deployed when it was trained on the same base-model version, up to 8 on the target deployment. The charge runs until step 7.

### 5. Check it

```powershell
python infra/verify.py --resource-group <name>
```

```text
<time> [PASS] Target deployment is Succeeded: qwen38-lora: Succeeded, model qwen--qwen3.8-27b/versions/<version>, 2 x H100_80GB
<time> [PASS] Adapter deployments are Succeeded: qwen38-lora-gsm8k: Succeeded
<time> [PASS] The base model answers under the target's name: HTTP 200, <n> s, answer '8', served model qwen--qwen3.8-27b
<time> [PASS] Adapter qwen38-lora-gsm8k answers under its own name: HTTP 200, <n> s, served model rp-<hash>-1 (base: qwen--qwen3.8-27b)
<time> [PASS] An unknown deployment name is rejected: HTTP 404 {"error": {"type": "invalid_request_error", "code": "DeploymentNotFound", [...]

RESULT: PASS   report: <home>/.foundry-lora/<name>/verify-report.json
```

`--full` repeats the comparison of [result 4](#result-4-the-adapter-changes-how-the-model-answers-not-how-often-it-is-right) on your deployment: the 50 validation rows through the base model and through the adapter, then the streaming speed test.

```text
<time> [PASS] Held-out rows through qwen38-lora: 50/50 answered; correct by last number <n>; mean <n> completion tokens; <n> cut at 800 tokens; <n> with '####'
<time> [PASS] Held-out rows through qwen38-lora-gsm8k: 50/50 answered; correct by last number <n>; mean <n> completion tokens; <n> cut at 800 tokens; <n> with '####'
<time> [PASS] The adapter changes the answers: <n> of 50 outputs identical to the base model's; rows saved to verify-rows-<time>.jsonl
<time> [PASS] Streaming speed of qwen38-lora: tokens per second <n> / <n> / <n>; first token after <n> / <n> / <n> s
<time> [PASS] Streaming speed of qwen38-lora-gsm8k: tokens per second <n> / <n> / <n>; first token after <n> / <n> / <n> s
```

The exit code is 0 when every check passes and 1 otherwise. The report lists each check; with `--full`, every answer is saved next to it so that you can read the rows yourself. "Correct by last number" is the automatic score described under Results and understates long answers. What each check proves and what was not tested: [`docs/TESTING.md`](docs/TESTING.md).

### 6. Call it from your code

```powershell
python examples/chat.py https://ftlora-<hash>.services.ai.azure.com/openai/v1/chat/completions qwen38-lora-gsm8k "A shop sells 12 pens for 3 dollars. How much do 48 pens cost?"
```

The script prints the answer, then the served model and the number of completion tokens. The request it sends is all an application needs:

```http
POST https://<account>.services.ai.azure.com/openai/v1/chat/completions
Authorization: Bearer <Microsoft Entra token for https://ai.azure.com>
Content-Type: application/json

{"model": "qwen38-lora-gsm8k", "messages": [{"role": "user", "content": "..."}], "max_tokens": 800, "temperature": 0, "reasoning_effort": "none"}
```

- `model` is a deployment name: `qwen38-lora` for the base model, `qwen38-lora-<display name>` for an adapter. No `api-version` and no key.
- `"reasoning_effort": "none"` asks for the answer directly. Without it the model reasons first and the reasoning counts against `max_tokens`: in the speed test, one answer spent its whole 600-token limit on reasoning.
- An application signs in with its own identity. Give that identity Foundry User on the account by running step 2 again with `--principal-id <object ID> --principal-type ServicePrincipal`.
- To serve an adapter trained on your own data, repeat step 3 with your files and another display name, then run step 4 again. The file format is described in [Customize a model with fine-tuning](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning).

### 7. Remove it

```powershell
python infra/down.py --resource-group <name>
```

```text
<time> to delete: adapter deployments ['qwen38-lora-gsm8k'], managed compute deployments ['qwen38-lora']
<time> adapter deployment qwen38-lora-gsm8k: deletion accepted (HTTP <code>)
<time> adapter deployment qwen38-lora-gsm8k: gone (<n> s)
<time> managed compute deployment qwen38-lora: deletion accepted (HTTP <code>)
<time> managed compute deployment qwen38-lora: gone (<n> s)
<time> [PASS] GPU deployments removed: deleted 1 adapter deployment(s) and 1 managed compute deployment(s); still present: none

RESULT: PASS   receipt: <home>/.foundry-lora/<name>/down-receipt.json
The hourly GPU charge has stopped. Account ftlora-<hash> and its trained adapters are kept; `python infra/down.py --resource-group <name> --all` removes them too.
```

The account, the project, the files and the trained adapters stay and have no hourly price, so step 4 can serve the same adapters again later. To remove everything:

```powershell
python infra/down.py --resource-group <name> --all
```

`--all` also deletes the project and the account, purges the soft-deleted account, and deletes the resource group when `up.py` created it and nothing else is in it. The exit code is 0 only when nothing is left.

### If a step stops

Each script stops with one line that names the cause and the action. The common ones:

| You see | Do |
|---|---|
| `Not signed in to Azure, or the subscription is not visible` | run `az login`, then `az account set --subscription "<name or ID>"` |
| `Global managed compute quota for H100_80GB has <n> free GPUs; the target needs 2` | request quota, or use a subscription that has it |
| `waiting for the Foundry User role to take effect`, repeated | wait; after 10 minutes the script stops and tells you which role to check |
| `job(s) succeeded without registering an adapter in the project` | submit the job on the portal's Training page (step 3, option A) |
| `this script needs the Python environment of the Programmed Training cookbook` | run `training/programmed_training_sft.py` with the Python of the cookbook environment (step 3, option B), not with the Python that runs the other scripts |
| `No Foundry account created by this repository in resource group` | run step 2 first, with the same `--resource-group` |
| `the project has no LoRA model with this name` | copy the model name from the `Deploy` line of step 3, option B; the message lists the project's LoRA models |
| `Two adapters would get the deployment name` | give one of them another label: `--adapter-model <model name>=<label>` |
| `There is no registered adapter to deploy yet, so no GPU was started` | finish step 3, then run step 4 again |
| `is Succeeded but its route answers HTTP` | run step 7, wait an hour, run step 4 again |
