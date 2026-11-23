"""Train the sample LoRA adapter with Programmed Training (preview): the training loop runs on your machine,
and Foundry executes every step it sends on GPUs that Microsoft operates.

  <cookbook python> training/programmed_training_sft.py --resource-group <name> --prepare
      1 sample data   2 local preparation
      Local only: downloads the two sample files and the tokenizer, renders every row, prints the plan and the
      list price. No Azure sign-in, no session, no charge.

  <cookbook python> training/programmed_training_sft.py --resource-group <name>
      the same two steps, then   3 the project that infra/up.py created
                                 4 ONE training session (billed per training token)   5 the saved adapter
      Two epochs over the training rows, a validation pass before training and after each epoch, the final
      checkpoint saved as a LoRA model of the project, the session closed. Prints the model's name and the
      command that deploys it.

<cookbook python> is the Python of the Programmed Training cookbook's environment
(https://github.com/microsoft-foundry/fine-tuning, directory programmed_training; README step 3). The session
needs a subscription that is approved for the preview: https://aka.ms/foundry-interactive-training-signup

The loop follows the cookbook's docs/custom-data.md, "Supervised chat data" (prepare_custom_sft, run_custom_sft).
What differs from its four-row example, and why:
  - the held-out rows are a separate validation file, so the builder is a ChatDatasetBuilder that returns the
    two datasets; each file is read with the cookbook's own FromConversationFileBuilder;
  - every training row is also rendered alone: a batch holds floor(rows / batch size) * batch size rows after a
    shuffle in each epoch, so any row can reach the service and must not fail there;
  - evaluation and checkpoints happen once per epoch and at the end; the step cap equals the planned steps.

Receipt: ~/.foundry-lora/<resource group>/train-receipt.json   Run folder: .../programmed-training/run-<time>/
Exit code: 0 = every step passed, 1 = stopped.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))
import foundry  # noqa: E402

try:
    import chz
    from programmed_training.renderers import TrainOnWhat
    from programmed_training.supervised import train
    from programmed_training.supervised.data import FromConversationFileBuilder
    from programmed_training.supervised.types import ChatDatasetBuilder, ChatDatasetBuilderCommonConfig
    from programmed_training.tokenizer_utils import get_tokenizer
except ImportError as missing:
    sys.exit(f"STOPPED: this script needs the Python environment of the Programmed Training cookbook ({missing}). "
             "Install the cookbook as step 3 of the README describes and run the script with that environment's python.")

MODEL = "Qwen/Qwen3.8-27B"
RENDERER = "qwen3_8_low_reasoning"
# The loop is yours: change these and run --prepare to see the new plan. The numbers in the README used these values.
SETTINGS = {"batch_size": 16, "num_epochs": 2, "learning_rate": 1e-4, "lora_rank": 32, "max_length": 2048, "seed": 42}
LABEL = "gsm8k-pt"  # suggested end of the adapter deployment's name


# ---------------------------------------------------------------- the loop (the driver of the run reported in the README)

def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_count(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def common(batch_size: int, max_length: int) -> ChatDatasetBuilderCommonConfig:
    return ChatDatasetBuilderCommonConfig(
        model_name_for_tokenizer=MODEL, renderer_name=RENDERER, max_length=max_length, batch_size=batch_size,
        train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE, fail_on_truncation=True,
    )


@chz.chz
class TrainValidationFilesBuilder(ChatDatasetBuilder):
    """Training batches from one conversation file; the whole of a second file as the single evaluation batch."""

    train_file: str
    validation_file: str
    shuffle_seed: int = 0

    def build(self):
        c = self.common_config
        training, _ = FromConversationFileBuilder(
            common_config=c, file_path=self.train_file, test_size=0, shuffle_seed=self.shuffle_seed).build()
        evaluation, _ = FromConversationFileBuilder(
            common_config=common(row_count(self.validation_file), c.max_length),
            file_path=self.validation_file, test_size=0, shuffle_seed=self.shuffle_seed).build()
        return training, evaluation


def check_split(split, name: str) -> dict:
    """The cookbook's target/mask check on every rendered row, with the counts kept for the manifest."""
    rows = tokens = loss_tokens = longest = 0
    for index in range(len(split)):
        for datum in split.get_batch(index):
            targets = datum.loss_fn_inputs["target_tokens"].data
            weights = datum.loss_fn_inputs["weights"].data
            if len(targets) != len(weights) or not any(w > 0 for w in weights):
                raise ValueError(f"{name}: invalid target/mask lengths or no assistant loss tokens (batch {index})")
            rows += 1
            tokens += len(targets)
            loss_tokens += sum(1 for w in weights if w > 0)
            longest = max(longest, len(targets))
    return {"batches": len(split), "rows": rows, "tokens": tokens, "lossTokens": loss_tokens, "longestRowTokens": longest}


def prepare_custom_sft(train_file: str, validation_file: str, log_path: str, s: dict):
    digests = {"train": sha256(train_file), "validation": sha256(validation_file)}
    builder = TrainValidationFilesBuilder(
        common_config=common(s["batch_size"], s["max_length"]),
        train_file=train_file, validation_file=validation_file, shuffle_seed=s["seed"])
    per_epoch = row_count(train_file) // s["batch_size"]
    planned = per_epoch * s["num_epochs"]
    config = train.Config(
        log_path=log_path, model_name=MODEL, dataset_builder=builder, lora_rank=s["lora_rank"],
        learning_rate=s["learning_rate"], num_epochs=s["num_epochs"], max_steps=planned, seed=s["seed"],
        eval_every=per_epoch, save_every=per_epoch, pipeline_depth=1,
        preflight_dataset=True, sanitize_logs=True,
    )
    prepared = train.prepare_datasets(config)
    training, evaluation = prepared
    if not len(training) or evaluation is None or not len(evaluation):
        raise ValueError("Need training batches and a non-empty evaluation split")
    if len(training) != per_epoch or len(evaluation) != 1:
        raise ValueError(f"Unexpected batch counts: training {len(training)}, evaluation {len(evaluation)}")
    one_by_one, _ = FromConversationFileBuilder(
        common_config=common(1, s["max_length"]), file_path=train_file, test_size=0, shuffle_seed=s["seed"]).build()
    stats = {"trainingBatches": check_split(training, "training"), "evaluation": check_split(evaluation, "evaluation"),
             "everyTrainingRow": check_split(one_by_one, "training rows one by one")}
    if stats["everyTrainingRow"]["rows"] != row_count(train_file) or stats["evaluation"]["rows"] != row_count(validation_file):
        raise ValueError("Rendered row counts differ from the files")
    tokenizer = get_tokenizer(MODEL)
    datum = one_by_one.get_batch(0)[0]
    targets, weights = list(datum.loss_fn_inputs["target_tokens"].data), list(datum.loss_fn_inputs["weights"].data)
    example = {
        "modelInput": tokenizer.decode([t for chunk in datum.model_input.chunks for t in chunk.tokens]),
        "trainedTargets": tokenizer.decode([int(t) for t, w in zip(targets, weights) if w > 0]),
        "tokens": len(targets), "trainedTokens": sum(1 for w in weights if w > 0),
    }
    if sha256(train_file) != digests["train"] or sha256(validation_file) != digests["validation"]:
        raise ValueError("Dataset changed during validation; prepare it again")
    manifest = {
        "model_name": MODEL, "renderer_name": RENDERER, "train_file": train_file, "validation_file": validation_file,
        "train_sha256": digests["train"], "validation_sha256": digests["validation"], "split_seed": s["seed"],
        "train_rows": row_count(train_file), "validation_rows": row_count(validation_file),
        "training_batches": len(training), "evaluation_batches": len(evaluation), "planned_steps": planned,
        "eval_every": per_epoch, "save_every": per_epoch, "settings": s, "stats": stats, "log_path": log_path,
        "train_tokens_planned": stats["trainingBatches"]["tokens"] * s["num_epochs"],
        "config": json.loads(json.dumps(train.ml_log.dump_config(config), default=str)),
    }
    return config, prepared, manifest, example


async def run_custom_sft(config, prepared, manifest):
    """The cookbook's run_custom_sft, plus two printed lines (session ready, session closed)."""
    from azure.ai.finetuningsessions.aio import FineTuningSessionClient
    from azure.ai.finetuningsessions.models import LoRAConfig
    from azure.identity.aio import DefaultAzureCredential
    from programmed_training import checkpoint_utils
    from programmed_training.rl.train_azure import AzureSDKTrainingClient

    if not config.max_steps or config.max_steps < 1:
        raise ValueError("Use a positive step cap")
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise ValueError("Set AZURE_AI_PROJECT_ENDPOINT to the intended project URL")
    tokenizer = get_tokenizer(config.model_name)
    run = Path(config.log_path)
    run.mkdir(parents=True, exist_ok=False)  # Never overwrite or silently resume.
    logging.warning("This SFT run uses paid cloud resources and may incur charges.")
    async with DefaultAzureCredential() as credential:
        async with FineTuningSessionClient(
            endpoint=endpoint, credential=credential,
            credential_scopes=["https://ai.azure.com/.default"],
        ) as client:
            session_id = await client.create_session(
                base_model=config.model_name,
                lora_config=LoRAConfig(rank=config.lora_rank),
                type="training", timeout_sec=600.0,
            )
            print(f"Session ready: session_id={session_id}", flush=True)
            workload_error = None
            try:
                (run / "session.json").write_text(json.dumps({
                    **manifest, "session_id": session_id,
                    "model_name": config.model_name, "lora_rank": config.lora_rank,
                }, indent=2), encoding="utf-8")
                trainer = AzureSDKTrainingClient(client, session_id, tokenizer)
                await train.main(config, trainer, prepared_datasets=prepared)
                saved = checkpoint_utils.get_last_checkpoint(config.log_path)
                if saved is None or saved.get("name") != "final":
                    raise RuntimeError("No completed final training checkpoint in the ledger")
                return saved["state_path"]
            except BaseException as exc:
                workload_error = exc
                raise
            finally:
                try:
                    await client.close_session(session_id)
                    print(f"Session closed: session_id={session_id}", flush=True)
                except BaseException:
                    if workload_error is None:
                        raise
                    logging.exception("Session cleanup failed; inspect the owned session")


# ---------------------------------------------------------------- the steps around the loop

def parse_args():
    p = argparse.ArgumentParser(description="Train the sample LoRA adapter with Programmed Training (preview).")
    p.add_argument("--resource-group", required=True, help="the resource group that infra/up.py created (step 2 of the README)")
    p.add_argument("--subscription", help="subscription name or ID (default: the Azure CLI's current subscription)")
    p.add_argument("--prepare", action="store_true", help="stop after the local preparation: no sign-in, no session, no charge")
    return p.parse_args()


def sample_data(folder: Path, receipt) -> dict:
    t0 = time.time()
    cache = folder / "data"
    cache.mkdir(exist_ok=True)
    files = {}
    for part, meta in foundry.DATASET["files"].items():
        foundry.dataset_bytes(part, cache)  # downloaded once, checked against the pinned SHA-256
        files[part] = str(cache / meta["upload_as"])
    receipt.add("1/5 Sample data", "PASS",
                "; ".join(f"{Path(p).name} {row_count(p)} rows" for p in files.values()) + "; pinned SHA-256 checked", time.time() - t0)
    return files


def local_preparation(files: dict, work: Path, receipt):
    t0 = time.time()
    log_path = str(work / ("run-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")))
    config, prepared, manifest, example = prepare_custom_sft(files["train"], files["validation"], log_path, dict(SETTINGS))
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (work / "rendered_example.json").write_text(json.dumps(example, indent=1, ensure_ascii=False), encoding="utf-8")
    t, e, r = (manifest["stats"][k] for k in ("trainingBatches", "evaluation", "everyTrainingRow"))
    planned = manifest["train_tokens_planned"]
    price = foundry.list_price(foundry.PRICE_METERS["programmed"])
    cost = (f"at the list price of {price:.2f} USD per million training tokens about {planned * price / 1e6:.2f} USD"
            if price else "list price could not be read")
    receipt.add("2/5 Local preparation", "PASS",
                f"{t['batches']} batches x {SETTINGS['batch_size']} rows = {t['rows']} of {r['rows']} rows per epoch, "
                f"{SETTINGS['num_epochs']} epochs, {manifest['planned_steps']} optimizer steps; "
                f"about {planned} training tokens, {cost}; "
                f"validation: {e['rows']} rows, {e['tokens']} tokens per pass; longest row {r['longestRowTokens']} tokens",
                time.time() - t0)
    return config, prepared, manifest


def project(args, receipt) -> foundry.Solution:
    t0 = time.time()
    account = foundry.use_subscription(args.subscription)
    sol = foundry.require_solution(account["id"], args.resource_group, foundry.DEFAULT_TARGET)
    receipt.add("3/5 Project", "PASS", f"account {sol.account}, project {sol.project}, endpoint {sol.project_endpoint}",
                time.time() - t0)
    return sol


def training_session(sol, config, prepared, manifest, receipt) -> str:
    t0 = time.time()
    os.environ["AZURE_AI_PROJECT_ENDPOINT"] = sol.project_endpoint  # run_custom_sft reads the project from here
    foundry.log(f"starting ONE Programmed Training session on {MODEL} (LoRA rank {SETTINGS['lora_rank']}); "
          "billed per training token until the session is closed")
    try:
        asyncio.run(run_custom_sft(config, prepared, manifest))
    except BaseException as e:  # the loop closes its session itself; record the stop, then show the error
        receipt.add("4/5 Training session", "FAIL", f"{type(e).__name__}: {e}"[:400], time.time() - t0)
        raise
    run = Path(config.log_path)
    session_id = json.loads((run / "session.json").read_text(encoding="utf-8"))["session_id"]
    rows = [json.loads(line) for line in (run / "metrics.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    s = foundry.session_summary(rows)
    ok = s["steps"] == manifest["planned_steps"] and len(s["validationLoss"]) >= 2
    receipt.add("4/5 Training session", "PASS" if ok else "FAIL",
                f"{session_id}: {s['steps']} of {manifest['planned_steps']} optimizer steps, {s['trainingTokens']} training tokens; "
                + (f"training loss {s['trainingLoss'][0]:.2f} -> {s['trainingLoss'][-1]:.2f}; " if s["trainingLoss"] else "")
                + (f"validation loss {s['validationLoss'][0]:.2f} -> {s['validationLoss'][-1]:.2f}; " if s["validationLoss"] else "")
                + f"session closed; run folder {run}", time.time() - t0)
    if not ok:
        raise foundry.Stop(f"The session {session_id} ended before all planned steps were logged. Its files are in {run}.")
    return session_id


def saved_adapter(sol, session_id: str, receipt) -> dict:
    t0, model = time.time(), None
    for _ in range(12):  # the project lists the final checkpoint as a LoRA model
        model = foundry.session_adapter(foundry.project_models(sol), session_id)
        if model:
            break
        time.sleep(10)
    if not model:
        receipt.add("5/5 Saved adapter", "FAIL", f"the project lists no LoRA model for the final checkpoint of {session_id}",
                    time.time() - t0)
        raise foundry.Stop(f"The session {session_id} finished, but the project does not list its final checkpoint as a LoRA model yet. "
                     "Open the project's Models page in the portal; when the model is listed, deploy it with "
                     f"`python infra/up.py --resource-group {sol.resource_group} --deploy --adapter-model <model name>={LABEL}`.")
    base = (model.get("derivedModelInformation") or {}).get("baseModel") or ""
    receipt.add("5/5 Saved adapter", "PASS",
                f"{model['name']} (LoRA rank {(model.get('loraConfig') or {}).get('rank')}) on {base.split('/models/')[-1]}",
                time.time() - t0)
    return model


def main() -> int:
    args = parse_args()
    folder = foundry.state_dir(args.resource_group)
    work = folder / "programmed-training"
    work.mkdir(exist_ok=True)
    receipt = foundry.Receipt(folder / "train-receipt.json", resourceGroup=args.resource_group, prepareOnly=args.prepare)
    model = None
    try:
        files = sample_data(folder, receipt)
        config, prepared, manifest = local_preparation(files, work, receipt)
        if not args.prepare:
            sol = project(args, receipt)
            session_id = training_session(sol, config, prepared, manifest, receipt)
            model = saved_adapter(sol, session_id, receipt)
    finally:
        status = receipt.close()
    print(f"\nRESULT: {status}   receipt: {receipt.path}")
    if args.prepare and status == "PASS":
        print("\nNothing was sent to Azure. To train, run the same command without --prepare (billed per training token).")
    elif model:
        print(f"""
Adapter : {model['name']}  (a LoRA model of project {sol.project})
Deploy  : python infra/up.py --resource-group {args.resource_group} --deploy --adapter-model {model['name']}={LABEL}
""")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except foundry.Stop as stop:
        print(f"\nSTOPPED: {stop}", file=sys.stderr)
        sys.exit(1)
