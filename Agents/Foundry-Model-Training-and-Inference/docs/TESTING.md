# Testing

[中文](TESTING_CN.md) · back to the [README](../README.md)

This page says what each check of the repository proves, how answers are scored, how the numbers in the README were measured, and what has not been tested.

## The four checks

| Check | Command | Needs | Proves | Does not prove |
|---|---|---|---|---|
| Offline tests | `python -m unittest discover -s tests -v` | Python only | the scripts' own decisions: which training jobs have a deployable adapter, which models named with `--adapter-model` are deployed, how adapter deployments are named, how a session's saved checkpoint and metrics are read, how answers are scored, when a receipt is PASS | that Azure accepts the requests |
| Local preparation for Programmed Training | `<cookbook python> training/programmed_training_sft.py --resource-group <name> --prepare` | the cookbook's Python environment; no Azure sign-in, about 3 minutes | both sample files have their pinned SHA-256; every row renders within 2,048 tokens and has answer tokens to train on; the plan for the session: 28 batches of 16 rows per epoch, 56 optimizer steps; the list price | that a session starts in your subscription; anything about the trained adapter |
| Deployment check | `python infra/verify.py --resource-group <name>` | a deployment (the GPUs are billed while it exists) | through the public endpoint: the target and the adapter deployments are `Succeeded`, the base model answers, each adapter answers and is served by a different model than the base, an unknown name is rejected | that an adapter improves anything |
| Full comparison | `python infra/verify.py --resource-group <name> --full` | the same deployment; 100 comparison calls and 6 streamed calls on top of the deployment check, about 5 minutes | on the 50 validation rows the adapter gives different answers than the base model; answer lengths; streaming speed | accuracy, see [How answers are scored](#how-answers-are-scored) |

## Offline tests

```powershell
python -m unittest discover -s tests -v
```

The 30 tests call no service. They feed the scripts the shapes of real service responses (job objects, project models) and check the decisions.

| Test class | Tests | What it asserts |
|---|---|---|
| `DeployableAdapters` | 7 | a succeeded job without a registered adapter is not deployable; an adapter is found through its job; a job that points to a model missing from the project is skipped; running and failed jobs are skipped; the newest job wins for one name; an adapter of another base model is excluded; at most 8 adapters per target |
| `AdapterNames` | 3 | the portal's display name is preferred over the job suffix; characters outside letters, digits, `.`, `_` and `-` are replaced; the name falls back to the job ID and stays within 64 characters |
| `NamedAdapters` | 7 | a project model named with `--adapter-model` is deployed under its label and needs no training job; without a label the model's name is used; an unknown name and a model that is not a LoRA model stop the script; so does a model of another base model; named adapters come before the adapters of jobs; a model that is named is listed once; two adapters with one deployment name stop the script |
| `Sessions` | 2 | the final checkpoint of a session is found by the session tag on the project model, and a model without that tag is not taken; the summary of a metrics file counts optimizer steps, training tokens and validation passes |
| `Scoring` | 5 | the reference format of the sample data is read; the `####` marker wins over later numbers; without a marker the last number is used; an answer without a number is not correct; a right answer followed by another number is scored wrong (the known limit described below) |
| `Receipts` | 2 | a receipt is PASS only when every step passed; an empty receipt is not a PASS |
| `Endpoints` | 4 | the chat route is on the account endpoint; the Azure Resource Manager URLs carry the API versions the requests were tested with; the adapter's ID is read from the job's Managed compute option; a list is read past an empty first page to the page that its `nextLink` names |

## Programmed Training script

`training/programmed_training_sft.py` runs in the Python environment of the Programmed Training cookbook. With `--prepare` it stops after step 2/5: it signs in to nothing and starts no session.

| Step | What it does | Passes when |
|---|---|---|
| 1/5 Sample data | downloads the two pinned GSM8K files, or reuses the copies that `up.py` downloaded | each file has its pinned SHA-256 |
| 2/5 Local preparation | renders every row with the cookbook's renderer for this model, builds the batches and reads the list price | every training row and every validation row renders within 2,048 tokens and has answer tokens to train on, and the batch counts equal the plan |
| 3/5 Project | finds the account and project that `up.py` created in the resource group | they exist |
| 4/5 Training session | opens one session, runs the loop, saves the final checkpoint and closes the session | the loop logged every planned optimizer step and at least 2 validation passes |
| 5/5 Saved adapter | lists the project's models, up to 12 times at intervals of 10 seconds | a LoRA model that carries the session in its tags and whose name ends in `-final` is listed |

No step fails on the value of a loss. The losses are printed so that you can compare them with the README.

How the script relates to the session reported in the README:

- **Same training code.** The functions that render the data and run the session (`prepare_custom_sft`, `run_custom_sft` and the 5 definitions they use) are the driver that ran the second test. The two files were compared as syntax trees: all 7 definitions are identical, and so are the model, the renderer and the settings.
- **Same plan.** `--prepare` was run from this repository, in the cookbook environment of the test client. Its plan equals the plan that the second test saved, in every field that does not name a folder: the SHA-256 of both files, 449 and 50 rows, 28 batches per epoch, 56 planned steps and 219,768 planned training tokens. The session itself counted 219,652: the 449 rows hold 110,106 tokens, an epoch trains 448 of them, and each epoch is shuffled again and leaves another row out.
- **Reading the service's answers.** `session_adapter`, `named_adapters` and `session_summary` in `infra/foundry.py` were run on the model records and the metrics file that the second test saved. They returned the model of the final checkpoint, the model ID that the test's adapter deployment named, and the 56 steps, 219,652 training tokens and losses reported in the README.
- **Run end to end.** On 24 November 2026 the script ran all five steps in a new resource group: one session, all 56 optimizer steps, 219,652 training tokens, validation loss from 0.91 to 0.41, and step 5/5 found the final checkpoint in the project; `up.py --deploy --adapter-model` then deployed it. See [The Steps run end to end](RESULTS.md#the-steps-run-end-to-end).

## Deployment check

`infra/verify.py` reads the deployment back from Azure Resource Manager and then calls the account endpoint the way an application does: a Microsoft Entra token for `https://ai.azure.com`, `model` set to a deployment name.

| Check | What it sends | Passes when |
|---|---|---|
| Target deployment is Succeeded | a read of the target deployment | its provisioning state is `Succeeded` |
| Adapter deployments are Succeeded | a list of the adapter deployments | at least one is attached to the target and all of them are `Succeeded` |
| The base model answers under the target's name | "Tom has 3 apples and buys 5 more. How many apples does he have? Answer with a number." | HTTP 200 and the answer contains 8 |
| Adapter `<name>` answers under its own name | the same question with `model` = the adapter deployment's name | HTTP 200, the answer contains 8, and the response's `model` differs from the base model's |
| An unknown deployment name is rejected | the same question with a made-up name | HTTP 404 |

`--full` adds:

| Check | What it sends | Passes when |
|---|---|---|
| Held-out rows through `<deployment>`, once for the base model and once for the adapter | the 50 validation rows, 4 at a time, `temperature` 0, `reasoning_effort` `"none"`, `max_tokens` 800, up to 3 attempts per row | all 50 rows are answered |
| The adapter changes the answers | nothing; it compares the two sets of answers | fewer than 50 answers are identical |
| Streaming speed of `<deployment>`, once per side | 3 streamed requests, one at a time, up to 600 tokens, reasoning at its default | every request yields a rate |

No check fails on the number of correct answers. The automatic score is printed and saved, and every answer is written to `verify-rows-<time>.jsonl` in the state directory so that the rows can be read.

## How answers are scored

Every reference answer of the sample data ends with `#### <number>!!!`. The automatic score takes the number after `####` when the answer has the marker, otherwise the last number in the answer, and compares it with the reference number.

This score is wrong for a correct answer that ends with another number. Row 5 of the validation file asks how many days one amoeba needs to become 16 amoebae; the reference answer is 8. The base model's answer ends `It will take **8** days for one amoeba to divide into 16 amoebae.` It is correct, and its last number is 16. The base model often closes with such a sentence; the adapter mostly ends with the number.

For the comparison in the README, every row that an automatic check marked wrong for either side was therefore read: 12 rows of 50.

| | Base model | Base model + GSM8K adapter |
|---|---|---|
| Correct by the automatic score | 39 of 50 | 45 of 50 |
| Correct answers the automatic score missed | 5 | 1 |
| Correct after reading | 44 of 50 | 46 of 50 |
| Rows still wrong (row numbers start at 0) | 9, 13, 24, 27, 33, 36; rows 13 and 27 were cut off at the 800-token limit | 9, 11, 13, 24 |

The two sides disagree on 4 rows: the adapter alone is correct on rows 27, 33 and 36, the base model alone on row 11. A two-sided sign test on 3 against 1 gives p = 0.625, so these 50 rows do not show a difference in accuracy. A second automatic check that looks for a final answer (the marker, a boxed number, the last bold number, "the answer is") was used only to choose rows for reading.

To score your own comparison, read `verify-rows-<time>.jsonl`: each line holds the row number, the deployment, the answer, the number the scorer took and the reference number.

## How the numbers in the README were measured

The test topology of each test is shown in [RESULTS.md](RESULTS.md): under [adapter A](RESULTS.md#adapter-a-managed-training-first-test) for the first test and [adapter B](RESULTS.md#adapter-b-programmed-training-second-test) for the second. All clocks are on the test client.

| Number | How it was taken |
|---|---|
| Training settings | read back from the job object: seed 42 (typed into the wizard), `n_epochs` 2, `batch_size` 128 and learning rate multiplier 1 (service defaults; **Number of epochs** and **Learning rate multiplier** were left on Default in the wizard) |
| Training job duration | `finished_at` minus `created_at` of the job object; it includes queueing and preprocessing |
| Training steps and their duration | the job's results file: 6 rows, `train_runtime` of the last row |
| Billed training tokens | the job event "Training tokens billed"; the job object's `trained_tokens` field shows a different, smaller number (163,164) |
| Target and adapter deployment time | from the accepted request to the first read that showed `Succeeded`, as seen by a polling client |
| Order of the two sides | one after the other, base model first, in one session on the same target deployment; the two sides were not interleaved |
| Answer length | `usage.completion_tokens` of each non-streamed answer; the mean over the 50 rows |
| Time to first token | from sending the request to the first streamed token, reasoning or answer; it includes the network and the prompt processing |
| Tokens per second | (completion tokens − 1) ÷ (time of the last chunk − time of the first token); completion tokens include reasoning tokens |
| Prices | the public Azure Retail Prices API, meters `Mngd H100_80GB Gl` and `Qwen38 27b SFT Gl 1M Tokens`, in USD |
| Second test: Programmed Training settings | read from the configuration that the loop saved before its first step: batch size 16, 2 epochs, learning rate 0.0001 with a linear schedule, LoRA rank 32, seed 42, at most 2,048 tokens per row. The 449 rows give 28 batches per epoch, so each epoch trains 448 rows and leaves 1 out |
| Second test: learning rate of both runs | the value logged at every optimizer step: the 6 values in the job's result file and the 56 values in the loop's metrics file all lie on a straight line from 0.0001 at the first step to zero one step after the last |
| Second test: validation loss | computed by the loop: the mean negative log-likelihood per answer token over the 50 validation rows (6,170 answer tokens), in a forward pass that does not update the adapter, before the first step, after 28 steps and after all 56. The Managed Training values are the `eval_loss` column of the result file of the job submitted in the portal, whose adapter is adapter A |
| Second test: token counts and cost | counted by the loop from the batches it sent: 219,652 training tokens in 56 steps and 36,042 tokens in 3 validation passes. The cost is the training tokens at the list price of the meter `Qwen38 27b Train Gl 1M Tokens`. Whether this meter is the one applied, how validation passes are charged and the bill itself were not checked |
| Second test: duration of the training | the loop's wall clock for the 56 steps and the 3 validation passes (363 seconds), and the time from starting the script to its exit (532 seconds), which adds preparing the data, creating the session and closing it |
| Second test: first call after `Succeeded` | a process on the test client sent one chat call about every 30 seconds, the first one 6 seconds after the first read that showed `Succeeded`. 25 calls returned HTTP 404 `The specified endpoint does not exist` (17 on `/openai/v1/chat/completions`, 8 on two other routes tried along the way); the call at 553 seconds returned HTTP 200 |
| Second test: scoring of the base model | the automatic score marked 11 answers wrong. 8 of them were identical in text to answers read in the first test and kept that reading; the other 3 were read: 2 were cut off at the 800-token limit, 1 gives another number than the reference |
| End-to-end run | the scripts' own output, saved per step: the start and exit time of each command, the `Succeeded (<n> min)`, `Succeeded (<n> s)` and `gone (<n> s)` lines and the `verify.py --full` lines; the answer counts come from the rows that `verify.py --full` saved. The portal job's numbers come from its job object, events and result file, the session's from its metrics file |

The speed test in the README used this prompt, in Chinese: "请用中文写一段约 300 字的说明：企业在 Azure 上用 Managed Compute 部署开源模型时，怎样根据业务量选择 GPU 型号和实例数。" `verify.py --full` sends the same prompt.

## Observations that differ from the documentation or have no known cause

- **The response's `model` field.** The [how-to](https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-lora-managed-compute) says a response returns the adapter deployment's name in `model`. The adapter's responses carried an internal ID of the form `rp-<hash>-1`. `verify.py` therefore checks only that it differs from the base model's value.
- **Jobs submitted through the API in a new project.** In two regions, 3 of 3 jobs submitted through the API in a project that had never run a portal-submitted job succeeded without registering an adapter in the project. Jobs submitted in the portal registered (2 of 2), and API jobs submitted afterwards in the same project registered (3 of 3). The cause is not known.
- **HTTP 404 after `Succeeded`.** Two target deployments created 23 and 33 seconds after a deletion emptied the account reached `Succeeded` and returned HTTP 404 to model calls. They still did at the last call before they were deleted, 18 and 23 minutes after `Succeeded`. One created 8 hours after a deletion answered after 8 seconds. In the second test the target was created in an account that held no deployment, and in which the test had deleted nothing. It also returned HTTP 404 after `Succeeded`, for 553 seconds, and then answered every call. So a 404 right after `Succeeded` can be temporary and does not need a deletion shortly before. Whether the two earlier targets would have answered after a longer wait is not known. The failure was not reproduced on purpose, and nothing between those gaps was tested; the 60-minute wait in `up.py` is a precaution. `up.py` repeats the first call for 10 minutes before it stops; the 553 seconds of the second test came close to that limit. In the end-to-end run the target was created in a new account, and its first call, 68 seconds after `Succeeded`, was answered.
- **A list whose first page is empty.** In the subscription of the end-to-end run, the Azure Resource Manager list of the accounts in the resource group returned an empty first page with a `nextLink`, and the account on the page it named. `infra/foundry.py` read only the first page then, so `training/programmed_training_sft.py` stopped at 3/5 with `No Foundry account created by this repository in resource group`. The scripts now follow `nextLink` to the last page, which an offline test covers; the session of the run started after that fix.
- **A Programmed Training session in the list of training jobs.** In the end-to-end run the session appeared in the project's list of training jobs as `session_<id>` with status `succeeded`, and its Managed compute option named the final checkpoint. Run offline on that saved list, the selection of `up.py` picks the checkpoint without `--adapter-model` as `qwen38-lora-<the last 8 characters of the session ID>`, and with the option only under its label.
- **A slower adapter deployment.** Adapter deployments reached `Succeeded` in 64 seconds (first test, 2 adapters), 78 seconds (second test) and 68 seconds (first adapter of the end-to-end run). The second adapter of the end-to-end run took 338 seconds. The cause is not known.
- **Base-model version of a target.** An adapter deployment request for an adapter trained on model version 3 was accepted on a target that ran version 7. That target never answered model calls, so the effect of such a pairing is unknown. `up.py` creates the target on the version the adapter names and sets `NoAutoUpgrade`.

## What has not been tested

- `infra/up.py --train-api` against Azure. The other commands of the Steps ran end to end on 24 November 2026; see [The Steps run end to end](RESULTS.md#the-steps-run-end-to-end).
- Linux and macOS; Python versions other than 3.13.
- Regions other than East US 2 for the deployment.
- A user who holds Foundry User on the account only. The tests ran as Owner of the subscription with Foundry User at subscription scope.
- More than 2 adapters on one target, more than 1 instance, concurrent users.
- Reading the answers of the end-to-end run by hand: its numbers of correct answers are the automatic score only.
- `training/programmed_training_sft.py` in a subscription without the Programmed Training approval, and run by a user who holds Foundry User only. The second test ran as Owner of the subscription with Foundry User and Azure AI Developer on the account.
- The cookbook installation commands of step 3 as the README gives them. They are the commands of the cookbook's quickstart; the cookbook environment of the test client existed before and was not rebuilt from them.
- The cookbook's own deployment route for a Programmed Training checkpoint (`scripts/deploy_to_foundry.py`, target `Fireworks`).
- Managed Training settings other than the defaults, including batch size 16; Programmed Training settings other than those in the table above; data other than the two sample sets.
