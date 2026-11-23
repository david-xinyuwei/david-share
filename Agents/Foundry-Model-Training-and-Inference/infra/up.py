"""Deploy the solution. Run it again at any time: it continues from what already exists.

  python infra/up.py --resource-group <name> [--location eastus2]
      1 preflight   2 resource group + infra/main.bicep   3 upload the sample data   4 look for a trained adapter
      Nothing created here is billed while idle. While no adapter is registered, the script prints what to
      submit on the portal's Training page.

  python infra/up.py --resource-group <name> --deploy
      the same four steps, then   5 target deployment (2 x H100, billed per hour until you run down.py)
                                  6 one adapter deployment per trained adapter   7 first calls

  python infra/up.py --resource-group <name> --deploy --adapter-model <model name>=<label>
      also deploys a LoRA model of the project that no training job registered: the checkpoint saved by
      training/programmed_training_sft.py (Programmed Training). The option can be repeated.

Receipt: ~/.foundry-lora/<resource group>/up-receipt.json   Exit code: 0 = every step passed, 1 = stopped.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import foundry as f

BICEP = Path(__file__).resolve().parent / "main.bicep"
QUESTION = [{"role": "user", "content": "Tom has 3 apples and buys 5 more. How many apples does he have? Answer with a number."}]
TERMINAL = ("succeeded", "failed", "cancelled")


def parse_args():
    p = argparse.ArgumentParser(description="Create the Foundry resources, then (with --deploy) the GPU target and the adapters.")
    p.add_argument("--resource-group", required=True, help="resource group to create or reuse")
    p.add_argument("--location", help="Azure region for a new deployment (default eastus2)")
    p.add_argument("--subscription", help="subscription name or ID (default: the Azure CLI's current subscription)")
    p.add_argument("--account-name", help="Foundry account name (default: ftlora-<hash of the resource group>)")
    p.add_argument("--project-name", help="Foundry project name (default: lora-demo)")
    p.add_argument("--target", default=f.DEFAULT_TARGET, help="name of the target deployment (default %(default)s)")
    p.add_argument("--deploy", action="store_true", help="create the GPU target deployment and the adapter deployments (billed per hour)")
    p.add_argument("--adapter-model", action="append", default=[], metavar="NAME[=LABEL]",
                   help="also deploy this LoRA model of the project, for example the checkpoint that "
                        "training/programmed_training_sft.py saved; LABEL ends the adapter deployment's name (repeatable)")
    p.add_argument("--wait-training", type=int, default=0, metavar="MINUTES", help="wait up to this long for a registered adapter")
    p.add_argument("--train-api", action="store_true",
                   help="submit the training job through the API instead of the portal (see README: registers an adapter "
                        "only in a project that already ran a portal-submitted job)")
    p.add_argument("--principal-id", help="object ID that receives the Foundry User role (default: the signed-in identity)")
    p.add_argument("--principal-type", choices=("User", "Group", "ServicePrincipal"), help="type of --principal-id")
    p.add_argument("--ignore-recent-teardown", action="store_true",
                   help="create the target even though down.py removed one from this account less than an hour ago")
    return p.parse_args()


def preflight(args, receipt) -> dict:
    t0 = time.time()
    account = f.use_subscription(args.subscription)
    sub = account["id"]
    state = f.az(['provider', 'show', '--namespace', 'Microsoft.CognitiveServices', '--query', 'registrationState', '-o', 'tsv']).strip()
    if state != "Registered":
        raise f.Stop(f"Resource provider Microsoft.CognitiveServices is '{state}' in this subscription. "
                     "Run `az provider register --namespace Microsoft.CognitiveServices` and wait until it is Registered.")
    existing = f.find_solution(sub, args.resource_group, args.target)
    group = f.az(['group', 'show', '--name', args.resource_group, '-o', 'json'], check=False)
    group_location = json.loads(group)["location"] if group.strip() else None
    location = (existing.location if existing else None) or args.location or group_location or "eastus2"
    if args.location and location != args.location:
        f.log(f"note: this resource group already holds the deployment in {location}; --location {args.location} is ignored")
    notes = [f"subscription {account['name']}", f"region {location}"]
    if location not in f.TRAINING_REGIONS:
        notes.append("WARNING: Learn does not list this region for Global Managed Training of Qwen3.8-27B")
    q = f.quota(sub, location)
    need = f.GPUS_PER_INSTANCE
    if q is None:
        notes.append(f"{f.ACCELERATOR} quota could not be read")
    else:
        notes.append(f"Global {f.ACCELERATOR} quota: {q[0]} used of {q[1]} GPUs (the target needs {need})")
    gpu_price = f.list_price(f.PRICE_METERS["gpu"])
    hourly = round(gpu_price * need, 2) if gpu_price else None
    notes.append(f"target list price {hourly} USD per hour ({need} x {gpu_price})" if hourly else "list price could not be read")
    receipt.add("1/7 Preflight", "PASS", "; ".join(notes), time.time() - t0)
    return {"subscription": sub, "location": location, "group_exists": group_location is not None, "user": account.get("user") or {},
            "quota": q, "hourly": hourly, "existing": existing}


def principal(args, user: dict) -> tuple[str, str]:
    if args.principal_id:
        return args.principal_id, args.principal_type or "User"
    if user.get("type") == "servicePrincipal":
        return f.az(['ad', 'sp', 'show', '--id', user["name"], '--query', 'id', '-o', 'tsv']).strip(), "ServicePrincipal"
    return f.az(['ad', 'signed-in-user', 'show', '--query', 'id', '-o', 'tsv']).strip(), "User"


def provision(args, env, receipt) -> f.Solution:
    t0 = time.time()
    rg, location = args.resource_group, env["location"]
    if not env["group_exists"]:
        f.az(['group', 'create', '--name', rg, '--location', location, '--tags', f'solution={f.SOLUTION_TAG}', '-o', 'none'])
    pid, ptype = principal(args, env["user"])
    params = [f'location={location}', f'principalId={pid}', f'principalType={ptype}']
    if args.account_name or env["existing"]:
        params.append(f'accountName={args.account_name or env["existing"].account}')
    if args.project_name or env["existing"]:
        params.append(f'projectName={args.project_name or env["existing"].project}')
    f.log(f"deploying infra/main.bicep into resource group {rg} ({location}) ...")
    out = json.loads(f.az(['deployment', 'group', 'create', '--resource-group', rg, '--name', 'foundry-lora',
                           '--template-file', str(BICEP), '--parameters', *params, '--query', 'properties.outputs', '-o', 'json']))
    sol = f.Solution(env["subscription"], rg, out["accountName"]["value"], out["projectName"]["value"], location,
                     out["projectEndpoint"]["value"], args.target)
    # A new role assignment needs a few minutes before the data plane accepts the token.
    deadline, code = time.time() + 600, None
    while time.time() < deadline:
        code, _, body = f.http("GET", sol.openai + "/fine_tuning/jobs?limit=1", audience=f.AI_AUDIENCE)
        if code == 200:
            break
        f.log(f"waiting for the Foundry User role to take effect (project API answered HTTP {code}) ...")
        time.sleep(20)
    if code != 200:
        raise f.Stop(f"The project API still answers HTTP {code}: {f.brief(body)}. Check that your identity holds the "
                     "Foundry User role on the account, then run the same command again.")
    receipt.add("2/7 Azure resources (infra/main.bicep)", "PASS",
                f"account {sol.account}, project {sol.project}, endpoint {sol.endpoint}", time.time() - t0)
    return sol


def sample_data(sol, state, receipt) -> dict:
    t0 = time.time()
    cache = f.state_dir(sol.resource_group) / "data"
    cache.mkdir(exist_ok=True)
    files, parts = {}, []
    for part, meta in f.DATASET["files"].items():
        data = f.dataset_bytes(part, cache)
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        if len(rows) != meta["rows"] or not all(isinstance(r.get("messages"), list) for r in rows):
            raise f.Stop(f"{meta['source']}: expected {meta['rows']} chat rows, found {len(rows)}")
        files[part] = {"id": f.upload_file(sol, meta["upload_as"], data), "name": meta["upload_as"], "rows": len(rows)}
        parts.append(f"{meta['upload_as']} {len(rows)} rows ({files[part]['id']})")
    state["files"] = files
    f.save_state(sol.resource_group, state)
    receipt.add("3/7 Sample data", "PASS", "; ".join(parts), time.time() - t0)
    return files


def submit_job(sol, files) -> str:
    body = {"model": f.TRAINING_MODEL, "training_file": files["train"]["id"], "validation_file": files["validation"]["id"],
            "suffix": "gsm8k", "seed": 42, "trainingType": "GlobalStandard",
            "method": {"type": "supervised", "supervised": {"hyperparameters": {"n_epochs": 2}}}}
    code, _, job = f.http("POST", sol.openai + "/fine_tuning/jobs", body, audience=f.AI_AUDIENCE, timeout=300)
    if code not in (200, 201) or not isinstance(job, dict):
        raise f.Stop(f"The training job was not accepted: HTTP {code} {f.brief(job)}")
    f.log(f"training job {job['id']} submitted through the API (status {job.get('status')})")
    return job["id"]


def trained_adapters(args, sol, files, state, receipt) -> list[dict]:
    t0 = time.time()
    jobs = f.list_jobs(sol)
    adapters = f.adapters_to_deploy(jobs, f.project_models(sol), args.target, args.adapter_model)
    active = [j for j in jobs if j.get("status") not in TERMINAL]
    if args.train_api and not adapters and not active:
        state["apiJob"] = submit_job(sol, files)
        f.save_state(sol.resource_group, state)
        active = [{"id": state["apiJob"]}]
    wait = args.wait_training or (40 if args.train_api else 0)
    deadline, seen = time.time() + wait * 60, {}
    while not adapters and time.time() < deadline:
        time.sleep(30)
        jobs = f.list_jobs(sol)
        for j in jobs:
            if seen.get(j["id"]) != j.get("status"):
                seen[j["id"]] = j.get("status")
                f.log(f"training job {j['id']} ({j.get('display_name') or j.get('suffix')}): {j.get('status')}")
        adapters = f.adapters_to_deploy(jobs, f.project_models(sol), args.target, args.adapter_model)
        active = [j for j in jobs if j.get("status") not in TERMINAL]
        if not active and not adapters and any(j.get("status") == "succeeded" for j in jobs):
            break  # finished without registering an adapter: waiting longer does not help
    if adapters:
        receipt.add("4/7 Trained adapter", "PASS",
                    "; ".join(f"{a['name']} <- {a['sourceModelId'].split('/models/')[-1]}" for a in adapters), time.time() - t0)
        return adapters
    unregistered = [j["id"] for j in jobs if j.get("status") == "succeeded" and not f.source_model_id(j)]
    if unregistered:
        why = (f"{len(unregistered)} job(s) succeeded without registering an adapter in the project ({', '.join(unregistered[:3])}); "
               "submit the job on the portal's Training page")
    elif active:
        why = f"{len(active)} training job(s) still running; run the same command again when they are Completed"
    else:
        why = "no training job yet"
    receipt.add("4/7 Trained adapter", "FAIL" if args.deploy else "INFO", "no registered LoRA adapter: " + why, time.time() - t0)
    print(f"""
NEXT: train the adapter on the portal's Training page (about 5 to 10 minutes; list price about 0.64 USD).
  1. Open https://ai.azure.com with "New Foundry" switched on and select project "{sol.project}" (account {sol.account}).
  2. Left menu: Training, then the Train button.
  3. Basic details: make sure Supervised, qwen3.8-27b and Global are selected. Next.
  4. Datasets: Training data source = {files['train']['name']}, Validation data source (optional) = {files['validation']['name']}. Next.
  5. Optional settings: type gsm8k into "Enter a display name" (it ends the adapter deployment's name). To use the seed of
     the published numbers, enter 42 in the seed field. Leave epochs and learning rate on Default. Submit.
  6. Wait until the job is finished and the adapter is listed on the Models page, tab "Models".
Then run:  python infra/up.py --resource-group {sol.resource_group} --deploy
Or train it with Programmed Training (preview): training/programmed_training_sft.py, step 3 of the README.
""")
    if args.deploy:
        raise f.Stop("There is no registered adapter to deploy yet, so no GPU was started.")
    return []


def target_deployment(args, sol, env, adapters, state, receipt) -> list[dict]:
    t0 = time.time()
    base = adapters[0]["baseModel"]
    fitting = [a for a in adapters if a["baseModel"] == base]
    for a in adapters:
        if a["baseModel"] != base:
            f.log(f"note: adapter {a['name']} was trained on {a['baseModel']} and cannot share a target that runs {base}; skipped")
    code, _, body = f.http("GET", sol.target_url())
    if code == 200:
        running = body["properties"].get("model")
        if running != base:
            raise f.Stop(f"Target deployment {sol.target} runs {running}, but the adapter was trained on {base}. "
                         "Remove it with down.py, or pass --target with another name.")
        f.log(f"target deployment {sol.target} already exists ({f.state_of(body)})")
    else:
        q, need = env["quota"], f.GPUS_PER_INSTANCE
        if q is not None and q[1] - q[0] < need:
            raise f.Stop(f"Global managed compute quota for {f.ACCELERATOR} has {q[1] - q[0]} free GPUs; the target needs {need}. "
                         "Request quota: https://learn.microsoft.com/azure/foundry/how-to/deploy-models-managed#request-more-quota")
        last = state.get("lastTeardown")
        if last and not args.ignore_recent_teardown:
            minutes = (dt.datetime.now().astimezone() - dt.datetime.fromisoformat(last)).total_seconds() / 60
            if minutes < 60:
                raise f.Stop(f"down.py removed this resource group's target deployment {minutes:.0f} minutes ago. In our tests a target created seconds "
                             "after a deletion reached Succeeded and then returned HTTP 404 to model calls. Wait until an hour has "
                             "passed, or pass --ignore-recent-teardown.")
        request = {"sku": {"name": "GlobalManagedCompute", "capacity": 1},
                   "properties": {"model": base, "deploymentTemplate": f.LORA_TEMPLATE, "acceleratorType": f.ACCELERATOR,
                                  "versionUpgradeOption": "NoAutoUpgrade"}}
        rate = f"{env['hourly']} USD per hour at list price" if env["hourly"] else "billed per GPU-hour"
        f.log(f"creating target deployment {sol.target}: {f.GPUS_PER_INSTANCE} x {f.ACCELERATOR}, {rate}, until you run down.py")
        for _ in range(10):
            code, _, body = f.http("PUT", sol.target_url(), request)
            if code != 409:
                break
            f.log("the account is busy with another operation (HTTP 409); retrying in 30 s")
            time.sleep(30)
        if code not in (200, 201, 202):
            raise f.Stop(f"The target deployment was rejected: HTTP {code} {f.brief(body, 600)}")
    started, last_state, last_print = time.time(), None, 0.0
    while time.time() - started < 50 * 60:
        code, _, body = f.http("GET", sol.target_url())
        current = f.state_of(body) or f"HTTP {code}"
        if current != last_state or time.time() - last_print > 120:
            f.log(f"target deployment {sol.target}: {current} ({(time.time() - t0) / 60:.0f} min)")
            last_state, last_print = current, time.time()
        if current in ("Succeeded", "Failed", "Canceled"):
            break
        time.sleep(20)
    if last_state != "Succeeded":
        raise f.Stop(f"Target deployment {sol.target} ended as {last_state}: {f.brief(body, 600)}. "
                     f"It may still be billed: run `python infra/down.py --resource-group {sol.resource_group}`.")
    receipt.add("5/7 Target deployment", "PASS",
                f"{sol.target}: base {base.split('/models/')[-1]}, {body['properties'].get('totalAccelerators')} x {f.ACCELERATOR}, "
                f"Succeeded", time.time() - t0)
    return fitting


def adapter_deployments(sol, adapters, receipt) -> list[str]:
    t0, done = time.time(), []
    for a in adapters:
        started = time.time()
        code, _, body = f.http("GET", sol.adapter_url(a["name"]))
        if code == 200:
            current = body["properties"].get("sourceModelId")
            if current != a["sourceModelId"]:
                f.log(f"note: adapter deployment {a['name']} already serves {current}; its source cannot be changed in place. "
                      f"Delete it to serve the newer job, then run this command again.")
        else:
            request = {"properties": {"sourceModelId": a["sourceModelId"], "targetDeploymentName": sol.target}}
            for _ in range(20):  # the account accepts one write at a time
                code, _, body = f.http("PUT", sol.adapter_url(a["name"]), request)
                if code != 409:
                    break
                time.sleep(30)
            if code not in (200, 201, 202):
                raise f.Stop(f"Adapter deployment {a['name']} was rejected: HTTP {code} {f.brief(body, 600)}")
        current = None
        while time.time() - started < 30 * 60:
            code, _, body = f.http("GET", sol.adapter_url(a["name"]))
            current = f.state_of(body)
            if current in ("Succeeded", "Failed", "Canceled"):
                break
            time.sleep(15)
        if current != "Succeeded":
            raise f.Stop(f"Adapter deployment {a['name']} ended as {current}: {f.brief(body, 600)}")
        f.log(f"adapter deployment {a['name']}: Succeeded ({time.time() - started:.0f} s)")
        done.append(a["name"])
    receipt.add("6/7 Adapter deployments", "PASS", f"{len(done)} on {sol.target}: {', '.join(done)}", time.time() - t0)
    return done


def first_calls(sol, names, receipt) -> None:
    t0, lines = time.time(), []
    for model in [sol.target, *names]:
        code = reply = None
        for attempt in range(20):  # a new deployment can need a moment before its route answers
            code, reply, seconds = f.chat(sol, model, QUESTION)
            if code == 200:
                break
            f.log(f"first call to {model}: HTTP {code}; retrying in 30 s ({attempt + 1}/20)")
            time.sleep(30)
        if code != 200:
            receipt.add("7/7 First calls", "FAIL", f"{model}: HTTP {code} {f.brief(reply)}", time.time() - t0)
            raise f.Stop(f"{model} is Succeeded but its route answers HTTP {code}. The GPUs are billed while it exists: "
                         f"run `python infra/down.py --resource-group {sol.resource_group}`, wait an hour and deploy again.")
        lines.append(f"{model} -> {f.answer_text(reply).strip()[:40]!r} (served model {reply.get('model')}, {seconds} s)")
    receipt.add("7/7 First calls", "PASS", "; ".join(lines), time.time() - t0)


def main() -> int:
    args = parse_args()
    folder = f.state_dir(args.resource_group)
    receipt = f.Receipt(folder / "up-receipt.json", resourceGroup=args.resource_group, deploy=args.deploy)
    state = f.load_state(args.resource_group)
    try:
        env = preflight(args, receipt)
        sol = provision(args, env, receipt)
        files = sample_data(sol, state, receipt)
        adapters = trained_adapters(args, sol, files, state, receipt)
        if args.deploy:
            adapters = target_deployment(args, sol, env, adapters, state, receipt)
            names = adapter_deployments(sol, adapters, receipt)
            first_calls(sol, names, receipt)
    finally:
        status = receipt.close()
    print(f"\nRESULT: {status}   receipt: {receipt.path}")
    if args.deploy and status == "PASS":
        rate = f"{env['hourly']} USD per hour at list price" if env["hourly"] else "per GPU-hour"
        print(f"""
Endpoint : {sol.chat_url}
Models   : "{sol.target}" (base model) and {', '.join('"' + n + '"' for n in names)} (base model + adapter)
Charge   : {rate} for as long as "{sol.target}" exists. Adapter deployments add nothing.
Check    : python infra/verify.py --resource-group {sol.resource_group}
Stop     : python infra/down.py --resource-group {sol.resource_group}
""")
    elif status == "PASS" and adapters:
        named = "".join(f" --adapter-model {spec}" for spec in args.adapter_model)
        print(f"\nA trained adapter is registered. Start the GPU target with:  "
              f"python infra/up.py --resource-group {args.resource_group} --deploy{named}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    f.main_guard(main)
